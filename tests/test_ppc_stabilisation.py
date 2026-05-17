"""
Stabilisation pass tests, covering the four PRODUCT_COMPLIANCE_AUDIT high
risks plus the new CSV ingest path:

1. invalid_grant on refresh flips amazon_connections.active = 0
2. snapshot_run_id keeps a coherent batch (no mixing fresh / stale rows)
3. ppc_snapshots retention deletes only rows older than the cutoff
4. CSV ingest parses a Sponsored Products Search Term Report and produces
   suggestions through `analyze`
5. /ppc/csv routes (GET form, POST analyze, error paths)

Patterns reuse the existing test infrastructure:
- in-memory sqlite + monkey-patched server._db
- ppc_oauth.requests.post mocked for LWA responses
- mock_ppc_data.seed_mock_snapshot for canonical snapshot fixtures

Run focused: `pytest tests/test_ppc_stabilisation.py -q`
"""

from __future__ import annotations

import io
import os
import sys
import json
import time
import sqlite3
from contextlib import contextmanager
from unittest.mock import patch, MagicMock

import pytest

# Make repo root importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test-only env vars consumed by server.py / ppc_agent.py / ppc_oauth.py at
# import time. Set before any of those modules are imported.
os.environ.setdefault("FLASK_SECRET_KEY",       "test_secret_key_xxxxxxxxxxxxxxxxxxxxxxxxx")
os.environ.setdefault("PPC_TOKEN_ENCRYPTION_KEY",
                      "rRiUz3xHGbXbBZI9xn-yY9JvJ6yL5y6KqzNc6VxQ1zU=")
os.environ.setdefault("SP_API_CLIENT_ID",     "test_client_id")
os.environ.setdefault("SP_API_CLIENT_SECRET", "test_client_secret")


# ──────────────────────────────────────────────────────────────────────────
#  Schema fixture (matches ppc_agent.init_ppc_db with snapshot_run_id)
# ──────────────────────────────────────────────────────────────────────────

_PPC_SCHEMA = """
    CREATE TABLE amazon_connections (
        id                       INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id              TEXT NOT NULL,
        seller_id                TEXT,
        marketplace_id           TEXT NOT NULL DEFAULT 'ATVPDKIKX0DER',
        refresh_token_encrypted  TEXT NOT NULL,
        ads_profile_id           TEXT,
        connected_at             REAL NOT NULL,
        last_synced_at           REAL,
        active                   INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE ppc_snapshots (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        connection_id    INTEGER NOT NULL,
        fetched_at       REAL NOT NULL,
        data_type        TEXT NOT NULL,
        data             TEXT NOT NULL,
        snapshot_run_id  TEXT
    );
    CREATE TABLE ppc_suggestions (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        connection_id     INTEGER NOT NULL,
        campaign_id       TEXT,
        ad_group_id       TEXT,
        keyword_id        TEXT,
        suggestion_type   TEXT NOT NULL,
        current_value     TEXT,
        proposed_value    TEXT,
        reason            TEXT NOT NULL,
        estimated_savings REAL,
        confidence        TEXT NOT NULL DEFAULT 'medium',
        status            TEXT NOT NULL DEFAULT 'pending',
        created_at        REAL NOT NULL,
        decided_at        REAL,
        applied_at        REAL
    );
    CREATE TABLE seller_decisions (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        connection_id       INTEGER NOT NULL,
        suggestion_id       INTEGER,
        suggestion_type     TEXT NOT NULL,
        keyword_id          TEXT,
        ad_group_id         TEXT,
        campaign_id         TEXT,
        current_value       TEXT,
        proposed_value      TEXT,
        estimated_impact    REAL,
        confidence          TEXT,
        decision            TEXT NOT NULL,
        edit_payload        TEXT,
        decided_at          REAL NOT NULL,
        observation_due_at  REAL
    );
"""


@pytest.fixture
def sqlite_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(_PPC_SCHEMA)
    yield conn
    conn.close()


@pytest.fixture
def db_ctx(sqlite_conn):
    @contextmanager
    def factory():
        cur = sqlite_conn.cursor()
        try:
            yield (cur, "?")
            sqlite_conn.commit()
        except Exception:
            sqlite_conn.rollback()
            raise
        finally:
            cur.close()
    return factory


@pytest.fixture
def patch_server_db(sqlite_conn, monkeypatch):
    """Patch server._db so module-level lazy imports see our in-memory DB."""
    @contextmanager
    def _db():
        cur = sqlite_conn.cursor()
        try:
            yield (cur, "?")
            sqlite_conn.commit()
        except Exception:
            sqlite_conn.rollback()
            raise
        finally:
            cur.close()

    import server
    monkeypatch.setattr(server, "_db", _db, raising=True)
    monkeypatch.setattr(server, "DATABASE_URL", "", raising=False)
    return _db


# ──────────────────────────────────────────────────────────────────────────
#  1. invalid_grant on refresh flips amazon_connections.active = 0
# ──────────────────────────────────────────────────────────────────────────

def _insert_active_connection(conn, connection_id=1, customer_id="cust_a"):
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO amazon_connections
            (id, customer_id, seller_id, marketplace_id, refresh_token_encrypted,
             connected_at, last_synced_at, active)
        VALUES (?, ?, 'A1MOCK', 'ATVPDKIKX0DER', 'enc-blob', ?, NULL, 1)
        """,
        (connection_id, customer_id, time.time()),
    )
    conn.commit()


def test_invalid_grant_during_refresh_marks_connection_inactive(
    sqlite_conn, patch_server_db,
):
    """LWA returns invalid_grant on refresh -> connection.active flips to 0."""
    import ppc_oauth

    _insert_active_connection(sqlite_conn, connection_id=42)

    fake_lwa_400 = MagicMock()
    fake_lwa_400.status_code = 400
    fake_lwa_400.json.return_value = {
        "error": "invalid_grant",
        "error_description": "Seller revoked access.",
    }
    fake_lwa_400.text = "{ ... }"

    # Clear the in-process cache so we hit the slow path that drives the
    # LWA call we're testing.
    ppc_oauth._token_cache.clear()

    with patch("ppc_oauth._read_encrypted_refresh_token", return_value="enc-blob"), \
         patch("ppc_agent.decrypt_token", return_value="plaintext-rt"), \
         patch("ppc_oauth.requests.post", return_value=fake_lwa_400):
        with pytest.raises(ppc_oauth.LWAError) as exc_info:
            ppc_oauth.get_active_token(connection_id=42)
        assert exc_info.value.lwa_error_code == "invalid_grant"

    cur = sqlite_conn.cursor()
    cur.execute("SELECT active FROM amazon_connections WHERE id = 42")
    assert cur.fetchone()[0] == 0, (
        "Connection must be flipped inactive after LWA invalid_grant on refresh."
    )


def test_invalid_grant_on_initial_exchange_does_not_flip_anything(
    sqlite_conn, patch_server_db,
):
    """
    The OAuth initial code-exchange has no connection_id yet (the row is
    inserted only on success). An invalid_grant there must NOT mutate any
    existing connection rows belonging to this or another customer.
    """
    import ppc_oauth

    _insert_active_connection(sqlite_conn, connection_id=99, customer_id="other")

    fake_lwa_400 = MagicMock()
    fake_lwa_400.status_code = 400
    fake_lwa_400.json.return_value = {"error": "invalid_grant", "error_description": ""}
    fake_lwa_400.text = "{}"

    with patch("ppc_oauth.requests.post", return_value=fake_lwa_400):
        with pytest.raises(ppc_oauth.LWAError) as exc_info:
            ppc_oauth.exchange_oauth_code("bad-code")
        assert exc_info.value.lwa_error_code == "invalid_grant"

    cur = sqlite_conn.cursor()
    cur.execute("SELECT active FROM amazon_connections WHERE id = 99")
    assert cur.fetchone()[0] == 1, (
        "Initial code-exchange invalid_grant must not flip unrelated rows."
    )


def test_mark_connection_inactive_idempotent(sqlite_conn, patch_server_db):
    """
    Calling mark_connection_inactive twice returns False the second time
    (no row was active -> nothing flipped). Cached token is dropped both
    times. Same-row re-entry must not error.
    """
    import ppc_oauth

    _insert_active_connection(sqlite_conn, connection_id=7)
    ppc_oauth._token_cache[7] = ("cached", time.time() + 3600)

    first  = ppc_oauth.mark_connection_inactive(7, reason="test1")
    second = ppc_oauth.mark_connection_inactive(7, reason="test2")
    assert first  is True
    assert second is False
    assert 7 not in ppc_oauth._token_cache


# ──────────────────────────────────────────────────────────────────────────
#  2. snapshot_run_id batch coherence
# ──────────────────────────────────────────────────────────────────────────

def _insert_snapshot_row(conn, connection_id, data_type, data_obj,
                         fetched_at, run_id):
    conn.cursor().execute(
        """
        INSERT INTO ppc_snapshots
          (connection_id, fetched_at, data_type, data, snapshot_run_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (connection_id, fetched_at, data_type, json.dumps(data_obj), run_id),
    )
    conn.commit()


def test_load_latest_snapshots_uses_complete_run_id(sqlite_conn, db_ctx):
    """
    Two runs exist:
      run-old: complete (all four required data_types present)
      run-new: ONLY campaigns (incomplete -> ignored by strategy 1)
    The loader must pick run-old's keywords and search_terms, not blank
    them just because run-new wrote a fresher campaigns row.
    """
    from ppc_suggestions import _load_latest_snapshots

    # run-old: complete
    for dt, payload in [
        ("campaigns",    [{"campaignId": "old-c"}]),
        ("ad_groups",    [{"adGroupId": "old-ag", "campaignId": "old-c", "defaultBid": 1.0}]),
        ("keywords",     [{"keywordId": "old-kw", "adGroupId": "old-ag",
                           "campaignId": "old-c", "keywordText": "old kw",
                           "matchType": "broad", "bid": 1.0, "state": "ENABLED"}]),
        ("search_terms", [{"keywordId": "old-kw", "adGroupId": "old-ag",
                           "campaignId": "old-c", "searchTerm": "old st",
                           "impressions": 10, "clicks": 1, "cost": 0.50,
                           "purchases30d": 0, "sales30d": 0}]),
    ]:
        _insert_snapshot_row(sqlite_conn, 1, dt, payload, 100.0, "run-old")

    # run-new: ONLY campaigns. Fresher fetched_at, but incomplete.
    _insert_snapshot_row(
        sqlite_conn, 1, "campaigns",
        [{"campaignId": "new-c"}], 200.0, "run-new",
    )

    out = _load_latest_snapshots(connection_id=1, db_ctx_factory=db_ctx)
    # Strategy 1 must pick run-old (the only complete one).
    assert out["campaigns"]    == [{"campaignId": "old-c"}]
    assert out["keywords"][0]["keywordId"]    == "old-kw"
    assert out["search_terms"][0]["searchTerm"] == "old st"


def test_load_latest_snapshots_falls_back_to_per_type_for_legacy_data(
    sqlite_conn, db_ctx,
):
    """
    Legacy rows (snapshot_run_id IS NULL) are still consumable through
    strategy 2 (per-data_type latest).
    """
    from ppc_suggestions import _load_latest_snapshots

    for dt, payload in [
        ("campaigns",    [{"campaignId": "legacy-c"}]),
        ("ad_groups",    [{"adGroupId": "legacy-ag", "campaignId": "legacy-c", "defaultBid": 1.0}]),
        ("keywords",     [{"keywordId": "legacy-kw", "adGroupId": "legacy-ag",
                           "campaignId": "legacy-c", "keywordText": "legacy",
                           "matchType": "exact", "bid": 1.0, "state": "ENABLED"}]),
        ("search_terms", [{"keywordId": "legacy-kw", "adGroupId": "legacy-ag",
                           "campaignId": "legacy-c", "searchTerm": "legacy",
                           "impressions": 10, "clicks": 1, "cost": 0.50,
                           "purchases30d": 0, "sales30d": 0}]),
    ]:
        # snapshot_run_id = None -> strategy 1 cannot pick it; strategy 2
        # reads per-data_type latest.
        _insert_snapshot_row(sqlite_conn, 1, dt, payload, 100.0, None)

    out = _load_latest_snapshots(connection_id=1, db_ctx_factory=db_ctx)
    assert out["campaigns"][0]["campaignId"] == "legacy-c"
    assert out["keywords"][0]["keywordText"] == "legacy"


def test_generate_suggestions_preserves_pending_when_run_incomplete(
    sqlite_conn, db_ctx,
):
    """
    With an incomplete latest run (campaigns only), the engine must NOT
    blow away prior pending suggestions: the dashboard would otherwise
    flicker to empty until the next complete fetch lands.
    """
    from ppc_suggestions import generate_suggestions

    # Pre-existing pending row (simulates an earlier complete run that
    # produced suggestions).
    sqlite_conn.cursor().execute(
        """
        INSERT INTO ppc_suggestions
          (connection_id, suggestion_type, reason, status, created_at)
        VALUES (1, 'spend_no_sales', 'preserved', 'pending', ?)
        """,
        (time.time(),),
    )
    sqlite_conn.commit()

    # Latest run: campaigns only. Missing ad_groups + keywords + search_terms.
    _insert_snapshot_row(
        sqlite_conn, 1, "campaigns",
        [{"campaignId": "c"}], 300.0, "incomplete-run",
    )

    generate_suggestions(connection_id=1, db_ctx_factory=db_ctx,
                         replace_pending=True)

    cur = sqlite_conn.cursor()
    cur.execute(
        "SELECT reason FROM ppc_suggestions WHERE connection_id = 1 AND status = 'pending'"
    )
    rows = [r[0] for r in cur.fetchall()]
    assert "preserved" in rows, (
        "Incomplete snapshot run must not wipe the previously pending list."
    )


# ──────────────────────────────────────────────────────────────────────────
#  3. Retention deletes rows older than cutoff
# ──────────────────────────────────────────────────────────────────────────

def test_run_retention_deletes_rows_older_than_cutoff(sqlite_conn, db_ctx):
    from ppc_snapshot_fetcher import run_retention

    now = time.time()
    very_old = now - 200 * 86400   # 200 days
    new      = now - 1   * 86400   # 1 day

    cur = sqlite_conn.cursor()
    cur.executemany(
        """
        INSERT INTO ppc_snapshots
          (connection_id, fetched_at, data_type, data, snapshot_run_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (1, very_old, "campaigns", "[]", "old-run"),
            (1, very_old, "keywords",  "[]", "old-run"),
            (1, new,      "campaigns", "[]", "new-run"),
            (1, new,      "keywords",  "[]", "new-run"),
        ],
    )
    sqlite_conn.commit()

    deleted = run_retention(days=90, db_ctx_factory=db_ctx)
    assert deleted == 2

    cur.execute("SELECT COUNT(*) FROM ppc_snapshots")
    remaining = cur.fetchone()[0]
    assert remaining == 2

    cur.execute("SELECT DISTINCT snapshot_run_id FROM ppc_snapshots")
    runs = {r[0] for r in cur.fetchall()}
    assert runs == {"new-run"}


def test_run_retention_zero_days_rejects(db_ctx):
    from ppc_snapshot_fetcher import run_retention
    with pytest.raises(ValueError):
        run_retention(days=0, db_ctx_factory=db_ctx)


def test_run_retention_no_op_when_table_is_younger_than_window(sqlite_conn, db_ctx):
    from ppc_snapshot_fetcher import run_retention

    cur = sqlite_conn.cursor()
    cur.execute(
        """
        INSERT INTO ppc_snapshots
          (connection_id, fetched_at, data_type, data, snapshot_run_id)
        VALUES (1, ?, 'campaigns', '[]', 'r')
        """,
        (time.time() - 5 * 86400,),
    )
    sqlite_conn.commit()

    deleted = run_retention(days=90, db_ctx_factory=db_ctx)
    assert deleted == 0


# ──────────────────────────────────────────────────────────────────────────
#  4. CSV ingest produces a snapshot the engine can analyse
# ──────────────────────────────────────────────────────────────────────────

# A minimal but realistic Sponsored Products Search Term Report CSV.
# Headers cover the three required (search_term, keyword, impressions)
# plus the money / order fields the rules read.
SEARCH_TERM_CSV = """\
Date,Campaign Name,Ad Group Name,Targeting,Match Type,Customer Search Term,Impressions,Clicks,Spend,7 Day Total Sales,7 Day Total Orders (#)
2026-04-01,Skincare,Skincare AG,moisturizer for dry skin,broad,moisturizer for dry winter skin,812,6,$6.90,$0.00,0
2026-04-02,Skincare,Skincare AG,moisturizer for dry skin,broad,best moisturizer dry skin face,240,2,$2.30,$0.00,0
2026-04-03,Skincare,Skincare AG,anti-aging serum,phrase,best anti-aging serum,3100,38,$41.80,$59.97,3
2026-04-04,Skincare,Skincare AG,hand cream,exact,hand cream,1500,22,$17.60,$112.00,8
2026-04-05,Pet Supplies,Pet AG,dog food,broad,organic dog treats,900,18,$14.40,$74.56,8
"""


def test_csv_ingest_parses_known_amazon_headers():
    from ppc_csv_ingest import parse_search_term_csv

    rows = parse_search_term_csv(SEARCH_TERM_CSV)
    assert len(rows) == 5

    by_term = {r["searchTerm"]: r for r in rows}
    assert "moisturizer for dry winter skin" in by_term
    waste = by_term["moisturizer for dry winter skin"]
    assert waste["impressions"] == 812
    assert waste["clicks"]      == 6
    assert waste["cost"]        == pytest.approx(6.90, abs=0.01)
    assert waste["sales30d"]    == 0.0

    high_acos = by_term["best anti-aging serum"]
    assert high_acos["cost"]     == pytest.approx(41.80, abs=0.01)
    assert high_acos["sales30d"] == pytest.approx(59.97, abs=0.01)
    assert high_acos["purchases30d"] == 3


def test_csv_ingest_build_snapshot_runs_through_engine():
    """End-to-end: CSV -> snapshot dict -> analyze() produces suggestions."""
    from ppc_csv_ingest import build_snapshot_from_csv
    from ppc_suggestions import analyze, savings_total, growth_opportunity_total

    snap = build_snapshot_from_csv(SEARCH_TERM_CSV)
    assert len(snap["search_terms"]) == 5
    assert len(snap["keywords"])     >= 4
    assert len(snap["campaigns"])    >= 2

    suggs = analyze(snap)
    types = {s["suggestion_type"] for s in suggs}
    # Waste keyword (moisturizer for dry skin) should fire spend_no_sales.
    assert "spend_no_sales" in types
    # Anti-aging serum should fire high_acos (~70%).
    assert "high_acos" in types
    # Organic dog treats has $74 sales over 30d and is not a keyword:
    # promote_search_term should fire.
    assert "promote_search_term" in types

    assert savings_total(suggs) > 0
    assert growth_opportunity_total(suggs) > 0


def test_csv_ingest_missing_required_columns_raises():
    from ppc_csv_ingest import parse_search_term_csv, CSVIngestError
    bad = "Date,Stuff\n2026-04-01,nothing useful\n"
    with pytest.raises(CSVIngestError):
        parse_search_term_csv(bad)


def test_csv_ingest_empty_input_raises():
    from ppc_csv_ingest import parse_search_term_csv, CSVIngestError
    with pytest.raises(CSVIngestError):
        parse_search_term_csv("")


def test_csv_ingest_money_parser_handles_punctuation():
    from ppc_csv_ingest import _parse_money
    assert _parse_money("$1,234.56")  == 1234.56
    assert _parse_money("(5.00)")     == -5.00
    assert _parse_money("")           == 0.0
    assert _parse_money(None)         == 0.0
    assert _parse_money("garbage")    == 0.0


def test_csv_ingest_keyword_id_is_stable_per_targeting():
    """Two rows with identical (text, ad_group, match) produce one keyword."""
    from ppc_csv_ingest import build_snapshot_from_csv
    snap = build_snapshot_from_csv(SEARCH_TERM_CSV)
    kw_ids = [k["keywordId"] for k in snap["keywords"]]
    # The two "moisturizer for dry skin / Skincare AG / broad" rows must
    # collapse to a single keyword.
    moisturizer_kws = [
        k for k in snap["keywords"]
        if k.get("keywordText") == "moisturizer for dry skin"
        and k.get("adGroupId") == "Skincare AG"
    ]
    assert len(moisturizer_kws) == 1
    assert len(kw_ids) == len(set(kw_ids))   # no duplicate ids


def test_csv_ingest_tolerates_utf8_bom():
    """
    Excel-saved CSVs prepend a BOM. Parser must accept it whether the upload
    arrives as bytes (the route uses utf-8-sig decode) or as a str that
    still has the BOM character at position 0.
    """
    from ppc_csv_ingest import parse_search_term_csv
    bom_text = "﻿" + SEARCH_TERM_CSV
    rows = parse_search_term_csv(bom_text)
    assert len(rows) == 5
    # Bytes-with-BOM via a stream (server.py does the same decode itself,
    # but ingest is documented to accept both shapes safely).
    bom_bytes = ("﻿" + SEARCH_TERM_CSV).encode("utf-8")
    rows_b = parse_search_term_csv(io.BytesIO(bom_bytes))
    assert len(rows_b) == 5


def test_csv_ingest_mixed_case_headers():
    """
    Sellers paste reports with inconsistent capitalisation. Header matching
    is case-insensitive after normalisation, so MIXED CASE must work.
    """
    from ppc_csv_ingest import parse_search_term_csv
    csv = (
        "DATE,Campaign Name,AD GROUP NAME,Targeting,MATCH TYPE,"
        "Customer Search Term,IMPRESSIONS,Clicks,SPEND (USD),"
        "7 Day Total Sales,7 Day Total Orders (#)\n"
        "2026-04-01,C,AG,kw,broad,kw,100,10,$5.00,$0,0\n"
    )
    rows = parse_search_term_csv(csv)
    assert len(rows) == 1
    assert rows[0]["searchTerm"]  == "kw"
    assert rows[0]["impressions"] == 100
    assert rows[0]["cost"]        == pytest.approx(5.00, abs=0.01)


def test_csv_ingest_skips_blank_rows_in_middle():
    """
    Real-world exports often include blank rows after a campaign rollover.
    Those must be skipped without aborting the whole parse.
    """
    from ppc_csv_ingest import parse_search_term_csv
    csv = (
        "Date,Campaign Name,Ad Group Name,Targeting,Match Type,"
        "Customer Search Term,Impressions,Clicks,Spend,"
        "7 Day Total Sales,7 Day Total Orders (#)\n"
        "2026-04-01,C,AG,kw,broad,kw1,10,1,$1,$0,0\n"
        "\n"
        ",,,,,,,,,,\n"
        "2026-04-02,C,AG,kw,broad,kw2,20,2,$2,$0,0\n"
    )
    rows = parse_search_term_csv(csv)
    terms = sorted(r["searchTerm"] for r in rows)
    assert terms == ["kw1", "kw2"]


def test_csv_ingest_zero_money_columns_does_not_crash():
    """
    A report missing Spend / Sales (uncommon but possible from a placement
    report dropped in by mistake) still parses, but every cost is 0. The
    suggestion engine then produces no waste-related output, which is the
    correct behaviour for this case.
    """
    from ppc_csv_ingest import build_snapshot_from_csv
    from ppc_suggestions import analyze
    csv = (
        "Date,Campaign Name,Ad Group Name,Targeting,Match Type,"
        "Customer Search Term,Impressions,Clicks\n"
        "2026-04-01,C,AG,kw,broad,kw1,500,5\n"
    )
    snap = build_snapshot_from_csv(csv)
    assert len(snap["search_terms"]) == 1
    assert snap["search_terms"][0]["cost"]     == 0.0
    assert snap["search_terms"][0]["sales30d"] == 0.0
    suggs = analyze(snap)
    # No spend, no signal: no waste / ACOS / promote suggestions.
    assert suggs == []


# ──────────────────────────────────────────────────────────────────────────
#  5. /ppc/csv routes
# ──────────────────────────────────────────────────────────────────────────

@pytest.fixture
def app():
    from server import app as flask_app
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def test_csv_upload_form_renders(client):
    """
    GET /ppc/csv returns the upload page (200) and does not require auth.
    The page must frame itself as a Preview of the PPC Agent (a beta
    bridge) - not as a report tool, audit, or downloadable findings
    product. This is a market-positioning guard, not just a copy test:
    if a future change accidentally retitles the page back to "Analyse"
    / "Findings" / "Audit" we want pytest to flag it before it ships.
    """
    resp = client.get("/ppc/csv")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # New agent-preview framing.
    assert "Preview the PPC Agent" in body
    assert "temporary beta bridge" in body
    assert "continuous monitoring" in body
    assert "approve / reject" in body.lower()
    # Approval-first language is preserved.
    assert "Approval-first" in body or "approval-first" in body.lower()
    assert "no amazon" in body.lower() or "never reaches amazon" in body.lower()
    # Anti-pattern guards: must NOT slide back into report-tool framing.
    assert "Analyse a Search Term Report" not in body
    assert "audit" not in body.lower()
    assert "PDF" not in body
    assert "report history" not in body.lower()


def test_csv_upload_form_does_not_use_report_product_framing(client):
    """
    Strategic guard: the CSV page must not drift back into the crowded
    report-tool category (PDF, audit, history, bulk). Separate test from
    the wording-positive test so a regression is easy to read.
    """
    resp = client.get("/ppc/csv")
    body = resp.get_data(as_text=True).lower()
    for forbidden in ("pdf export", "report history", "bulk csv",
                      "downloadable audit", "free audit",
                      "save this report"):
        assert forbidden not in body, f"forbidden report-tool phrase found: {forbidden!r}"


def test_csv_analyze_with_valid_file_renders_findings(client):
    """
    A valid CSV must produce a recommendations card titled in agent
    terms ("What the agent found"), not report terms ("Findings"), and
    each rule that fires on the fixture must surface as a Smart
    Recommendation Card with the agent-style type label (cycle-16).
    """
    data = {"file": (io.BytesIO(SEARCH_TERM_CSV.encode("utf-8")), "report.csv")}
    resp = client.post("/ppc/csv/analyze", data=data,
                       content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Agent-style heading replaces the old "Findings" report header.
    assert "What the agent found" in body
    # Each rule that should fire on this fixture must be visible via the
    # new Smart Recommendation Card type label.
    assert "Waste cleanup" in body
    assert "ACOS reduction" in body
    assert "Promote a search term" in body
    # Conservative-estimate marker for the seller.
    assert "Estimates only" in body
    # Read-only preview note appears on the card (no Approve button on CSV).
    assert "Read-only preview" in body


def test_csv_analyze_renders_smart_recommendation_card_shape(client):
    """CSV preview uses the same Smart Recommendation Card partial."""
    data = {"file": (io.BytesIO(SEARCH_TERM_CSV.encode("utf-8")), "report.csv")}
    resp = client.post("/ppc/csv/analyze", data=data,
                       content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    # The new card markup is in place; the old <article class="suggestion">
    # markup is gone.
    assert 'class="rec-card' in body
    assert 'class="suggestion"' not in body

    # Per-card sections present.
    assert "Why this matters" in body
    assert "Memory" in body
    assert "Recommended action" in body
    assert "Likely impact" in body
    assert "Learn more" in body

    # Default neutral memory hint.
    assert "No similar rejection found" in body

    # Risk badges + agent-style headlines render.
    assert ("LOW RISK" in body or "MEDIUM RISK" in body or "HIGH RISK" in body)


def test_csv_analyze_card_does_not_render_approve_buttons(client):
    """
    CSV preview is read-only by construction. The Smart Card on the CSV
    preview must NOT render Approve / Reject / Edit buttons (no live link
    to push a change). The page already has its own no-Amazon-write copy.
    """
    data = {"file": (io.BytesIO(SEARCH_TERM_CSV.encode("utf-8")), "report.csv")}
    resp = client.post("/ppc/csv/analyze", data=data,
                       content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # No approve / reject / edit buttons on preview cards.
    assert 'data-action="approve"' not in body
    assert 'data-action="reject"' not in body
    assert 'data-action="edit"' not in body
    # Read-only-mode footer note on the card.
    assert "Read-only preview" in body


def test_csv_analyze_card_anti_overclaim_no_past_tense_savings(client):
    """No realised-savings / guaranteed-savings copy on the CSV preview."""
    data = {"file": (io.BytesIO(SEARCH_TERM_CSV.encode("utf-8")), "report.csv")}
    resp = client.post("/ppc/csv/analyze", data=data,
                       content_type="multipart/form-data")
    body = resp.get_data(as_text=True).lower()
    for phrase in ("you saved", "we saved", "saved you", "guaranteed savings"):
        assert phrase not in body, f"misleading phrase '{phrase}' must not appear"


def test_csv_analyze_without_file_returns_400(client):
    resp = client.post("/ppc/csv/analyze", data={},
                       content_type="multipart/form-data")
    assert resp.status_code == 400
    body = resp.get_data(as_text=True)
    assert "No file" in body or "no file" in body.lower()


def test_csv_analyze_with_bad_csv_returns_422(client):
    bad = io.BytesIO(b"not,a,real,report\n1,2,3,4\n")
    resp = client.post(
        "/ppc/csv/analyze",
        data={"file": (bad, "garbage.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 422
    body = resp.get_data(as_text=True)
    assert ("Customer Search Term" in body
            or "Targeting" in body
            or "Missing recognised columns" in body)


def test_csv_analyze_findings_show_safety_disclaimer(client):
    """
    The findings page must reinforce: estimates only, no Amazon writes,
    file not stored, soft CTA to OAuth flow, and the CSV-specific bid /
    CPC clarifier so seller knows the dollar figures aren't the literal
    bid set in Seller Central.
    """
    data = {"file": (io.BytesIO(SEARCH_TERM_CSV.encode("utf-8")), "report.csv")}
    resp = client.post("/ppc/csv/analyze", data=data,
                       content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Cycle-12 wording: per-page disclaimer + post-findings safety footer.
    assert "Past performance does not guarantee" in body
    assert "no amazon api calls were made" in body.lower()
    assert "file is not stored" in body.lower()
    # Soft CTA back to live dashboard / OAuth path.
    assert "/ppc/dashboard" in body
    # Cycle-13 wording: CPC vs literal-bid clarifier so we don't imply we
    # have data we don't actually have from a CSV path.
    assert "cost-per-click" in body
    assert "literal bid" in body


def test_csv_sample_endpoint_serves_a_csv(client):
    """
    /ppc/csv/sample.csv must serve a downloadable CSV that the same engine
    can parse end-to-end. Beta sellers who don't yet have a Seller Central
    report use this to evaluate the product without waiting for the
    Reports queue. Header gates download (not inline render) and the body
    must produce at least one suggestion when fed back through analyze().
    """
    resp = client.get("/ppc/csv/sample.csv")
    assert resp.status_code == 200
    assert "csv" in resp.headers.get("Content-Type", "").lower()
    cd = resp.headers.get("Content-Disposition", "")
    assert "attachment" in cd
    assert ".csv" in cd

    # Round-trip: feed the served bytes back into the parser and the
    # engine. Confirms the sample is honest about what the CSV path
    # actually accepts.
    from ppc_csv_ingest import build_snapshot_from_csv
    from ppc_suggestions import analyze
    body = resp.get_data(as_text=True)
    snap = build_snapshot_from_csv(body)
    suggs = analyze(snap)
    assert len(suggs) >= 1, "Sample CSV must produce at least one finding."


def test_csv_upload_form_links_to_sample(client):
    """
    The upload form must link to /ppc/csv/sample.csv so the seller can
    discover the sample without reading docs.
    """
    resp = client.get("/ppc/csv")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "/ppc/csv/sample.csv" in body


def test_csv_analyze_flags_sample_upload_as_demo_data(client):
    """
    When a prospect downloads sellercopilot-sample-search-term.csv from
    /ppc/csv/sample.csv and re-uploads it, the findings page must show a
    'Demo data' banner so screenshots can't be confused with a real
    seller's PPC waste. Detection requires both: the canonical filename
    AND the synthetic-only marker text inside the body. Spoofing only the
    filename is not enough.
    """
    sample = client.get("/ppc/csv/sample.csv").get_data(as_text=True)
    data = {
        "file": (io.BytesIO(sample.encode("utf-8")),
                 "sellercopilot-sample-search-term.csv"),
    }
    resp = client.post("/ppc/csv/analyze", data=data,
                       content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Demo data" in body
    assert "synthetic numbers" in body or "not your real account" in body


def test_csv_analyze_does_not_flag_real_upload_as_demo(client):
    """
    A genuine seller upload (different filename, real-shaped data) must
    NOT trigger the demo-data banner.
    """
    data = {"file": (io.BytesIO(SEARCH_TERM_CSV.encode("utf-8")),
                     "my-real-report.csv")}
    resp = client.post("/ppc/csv/analyze", data=data,
                       content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Demo data" not in body


def test_csv_analyze_does_not_flag_filename_spoof_as_demo(client):
    """
    A seller who happens to name their file the same as our sample but
    whose CSV does not contain the synthetic marker must not see the
    demo banner. Both signals (filename + marker) are required.
    """
    data = {
        "file": (io.BytesIO(SEARCH_TERM_CSV.encode("utf-8")),
                 "sellercopilot-sample-search-term.csv"),
    }
    resp = client.post("/ppc/csv/analyze", data=data,
                       content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Demo data" not in body


@pytest.mark.parametrize(
    "magic, label_fragment",
    [
        (b"%PDF-1.4\n",         "PDF"),
        (b"PK\x03\x04\x14\x00", "ZIP"),    # also matches .xlsx
        (b"\x89PNG\r\n\x1a\n",  "PNG"),
        (b"\xff\xd8\xff\xe0",   "JPEG"),
    ],
)
def test_csv_analyze_rejects_non_csv_uploads_with_415(client, magic, label_fragment):
    """
    A seller who drags-and-drops a PDF / image / xlsx by mistake must get a
    targeted 'looks like a PDF, not a CSV' message rather than 'missing
    recognised columns'. Returns 415 Unsupported Media Type.
    """
    payload = magic + b"some garbage that is not csv data"
    data = {"file": (io.BytesIO(payload), "looks-wrong.bin")}
    resp = client.post("/ppc/csv/analyze", data=data,
                       content_type="multipart/form-data")
    assert resp.status_code == 415
    body = resp.get_data(as_text=True)
    assert label_fragment in body or label_fragment.lower() in body


def test_csv_analyze_does_not_write_to_db(client, sqlite_conn, patch_server_db):
    """
    The CSV path must never insert into ppc_suggestions or ppc_snapshots.
    Suggestions are rendered to the page only.
    """
    data = {"file": (io.BytesIO(SEARCH_TERM_CSV.encode("utf-8")), "report.csv")}
    resp = client.post("/ppc/csv/analyze", data=data,
                       content_type="multipart/form-data")
    assert resp.status_code == 200

    cur = sqlite_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM ppc_suggestions")
    assert cur.fetchone()[0] == 0, (
        "CSV analyse path must not persist suggestions to DB."
    )
    cur.execute("SELECT COUNT(*) FROM ppc_snapshots")
    assert cur.fetchone()[0] == 0, (
        "CSV analyse path must not persist snapshots to DB."
    )


# ──────────────────────────────────────────────────────────────────────────
#  6. Admin retention route gating
# ──────────────────────────────────────────────────────────────────────────

def test_admin_retention_route_refuses_when_token_unset(client):
    """If PPC_ADMIN_TOKEN is empty, the endpoint refuses to run (503)."""
    import ppc_agent
    # Default fixture state: no admin token set.
    assert ppc_agent.PPC_ADMIN_TOKEN == ""
    resp = client.post("/ppc/admin/retention/run")
    assert resp.status_code == 503


def test_admin_retention_route_rejects_bad_token(client, monkeypatch):
    import ppc_agent
    monkeypatch.setattr(ppc_agent, "PPC_ADMIN_TOKEN", "good-token")
    resp = client.post(
        "/ppc/admin/retention/run",
        headers={"X-Admin-Token": "wrong-token"},
    )
    assert resp.status_code == 403


def test_admin_retention_route_runs_with_correct_token(
    client, monkeypatch, sqlite_conn, patch_server_db,
):
    import ppc_agent
    monkeypatch.setattr(ppc_agent, "PPC_ADMIN_TOKEN", "good-token")

    # Seed two old + one new row.
    cur = sqlite_conn.cursor()
    now = time.time()
    cur.executemany(
        """
        INSERT INTO ppc_snapshots
          (connection_id, fetched_at, data_type, data, snapshot_run_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (1, now - 200 * 86400, "campaigns", "[]", "old"),
            (1, now - 200 * 86400, "keywords",  "[]", "old"),
            (1, now -   1 * 86400, "campaigns", "[]", "new"),
        ],
    )
    sqlite_conn.commit()

    resp = client.post(
        "/ppc/admin/retention/run",
        headers={"X-Admin-Token": "good-token"},
        json={"days": 90},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["deleted"] == 2
    assert body["days"]    == 90


def test_admin_retention_route_validates_days(client, monkeypatch):
    import ppc_agent
    monkeypatch.setattr(ppc_agent, "PPC_ADMIN_TOKEN", "good-token")

    # Non-integer
    resp = client.post(
        "/ppc/admin/retention/run",
        headers={"X-Admin-Token": "good-token"},
        json={"days": "many"},
    )
    assert resp.status_code == 400

    # Zero
    resp = client.post(
        "/ppc/admin/retention/run",
        headers={"X-Admin-Token": "good-token"},
        json={"days": 0},
    )
    assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────────────────
#  Top-N composite ranker on the CSV preview (cycle-17 / Task 2)
# ──────────────────────────────────────────────────────────────────────────

def _build_strong_csv(rows: int) -> str:
    """
    Build a Sponsored Products Search Term Report CSV with `rows` waste
    keywords each spending $200 on 80 clicks with zero orders. Every row
    is unique by ad-group + targeting so the engine emits one
    spend_no_sales suggestion per keyword that all pass the Task-2
    first-view filters.
    """
    header = (
        "Date,Campaign Name,Ad Group Name,Targeting,Match Type,"
        "Customer Search Term,Impressions,Clicks,Spend,"
        "7 Day Total Sales,7 Day Total Orders (#)"
    )
    lines = [header]
    for i in range(1, rows + 1):
        kw_text = f"strong waste keyword {i:02d}"
        st_text = f"strong waste term {i:02d}"
        lines.append(
            f"2026-04-{i:02d},Demo Campaign,Demo AG {i:02d},"
            f"{kw_text},broad,{st_text},2000,80,$200.00,$0.00,0"
        )
    return "\n".join(lines) + "\n"


def _split_primary_and_overflow_csv(body: str) -> tuple[str, str]:
    """Same partition trick as the dashboard test helper."""
    overflow_marker = '<details class="rec-overflow"'
    if overflow_marker in body:
        primary, _, overflow = body.partition(overflow_marker)
        return primary, overflow_marker + overflow
    return body, ""


def test_csv_preview_first_view_caps_at_five_cards(client):
    """8 strong recommendations -> 5 primary, 3 overflow."""
    csv_body = _build_strong_csv(8).encode("utf-8")
    resp = client.post(
        "/ppc/csv/analyze",
        data={"file": (io.BytesIO(csv_body), "strong.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    primary, overflow = _split_primary_and_overflow_csv(body)
    assert primary.count('class="rec-card')  == 5
    assert overflow.count('class="rec-card') == 3
    assert "Show 3 more" in body


def test_csv_preview_show_more_appears_with_overflow(client):
    """6 strong recommendations -> 5 primary, 1 overflow, 'Show 1 more'."""
    csv_body = _build_strong_csv(6).encode("utf-8")
    resp = client.post(
        "/ppc/csv/analyze",
        data={"file": (io.BytesIO(csv_body), "strong.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert '<details class="rec-overflow"' in body
    assert "Show 1 more" in body


def test_csv_preview_no_overflow_when_under_cap(client):
    """3 strong recommendations -> 3 primary, no overflow block."""
    csv_body = _build_strong_csv(3).encode("utf-8")
    resp = client.post(
        "/ppc/csv/analyze",
        data={"file": (io.BytesIO(csv_body), "strong.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert body.count('class="rec-card') == 3
    assert '<details class="rec-overflow"' not in body


def test_csv_preview_banners_use_full_list(client):
    """
    The savings banner must sum every produced suggestion, not just the
    top-N. With 8 × $200 spend_no_sales suggestions, the banner total
    must equal $1,600 regardless of how many are visible above the
    fold.
    """
    csv_body = _build_strong_csv(8).encode("utf-8")
    resp = client.post(
        "/ppc/csv/analyze",
        data={"file": (io.BytesIO(csv_body), "strong.csv")},
        content_type="multipart/form-data",
    )
    body = resp.get_data(as_text=True)
    # Each spend_no_sales fixture has cost_30d $200 -> estimated_savings
    # is rule-side full $200 -> savings_total = 8 * $200 = $1,600.
    assert "$1600.00" in body


# ──────────────────────────────────────────────────────────────────────────
#  Seller memory does NOT apply on the CSV preview (cycle-18 / Task 3)
# ──────────────────────────────────────────────────────────────────────────

def test_csv_preview_does_not_render_memory_pill(client):
    """
    CSV preview is read-only and has no decision history. The memory
    pill ('Skipped N you recently rejected') is dashboard-only and must
    not appear on /ppc/csv/analyze regardless of how many strong
    recommendations the report yields.
    """
    csv_body = _build_strong_csv(3).encode("utf-8")
    resp = client.post(
        "/ppc/csv/analyze",
        data={"file": (io.BytesIO(csv_body), "strong.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # No memory-pill markup leaks to the preview surface.
    assert 'class="rec-memory-pill"' not in body
    assert "Skipped" not in body or "you recently rejected" not in body
    # No resurfaced/skipped wording.
    assert "bringing it back" not in body
    assert "rejected this on" not in body


def test_csv_preview_cards_show_neutral_memory_hint(client):
    """
    Every card on the CSV preview falls through to the neutral memory
    copy because the path has no decision history.
    """
    csv_body = _build_strong_csv(3).encode("utf-8")
    resp = client.post(
        "/ppc/csv/analyze",
        data={"file": (io.BytesIO(csv_body), "strong.csv")},
        content_type="multipart/form-data",
    )
    body = resp.get_data(as_text=True)
    assert "No similar rejection found" in body


# ──────────────────────────────────────────────────────────────────────────
#  Approval projection block does NOT render on the CSV preview (Task 4)
# ──────────────────────────────────────────────────────────────────────────

def test_csv_preview_does_not_render_projection_block(client):
    """
    CSV preview has no DB-backed decisions, so the approved-projection
    block must never render. The four required disclaimer phrases must
    also be absent (they only make sense paired with an approved row).
    """
    csv_body = _build_strong_csv(3).encode("utf-8")
    resp = client.post(
        "/ppc/csv/analyze",
        data={"file": (io.BytesIO(csv_body), "strong.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    assert 'class="approved-projections"' not in body
    assert "Approved (pending apply)" not in body
    # Disclaimer phrases that go with the projection block.
    assert "Calculated from the prior 30 days" not in body
    assert "Nothing has been applied to Amazon yet" not in body
    assert "Real results will differ" not in body


# ──────────────────────────────────────────────────────────────────────────
#  BSA Agent Policy compliance (Week 1 of MVP Hardening Plan)
# ──────────────────────────────────────────────────────────────────────────
#
# Effective 2026-03-04. Enforcement starts early June 2026. Per the policy:
# "All AI agents must clearly identify themselves as automated systems at
# all times" and "cease access immediately if Amazon requests it." We
# satisfy both via:
#   - User-Agent self-identification in every Ads / LWA call.
#   - A code-backed kill switch that flips all amazon_connections rows to
#     inactive in one call.
#
# These tests assert both contracts at the unit level so accidental copy
# changes (e.g. shortening the User-Agent) fail loudly in CI.

def test_user_agent_self_identifies_as_automated_ai_agent():
    from ppc_ads_client import USER_AGENT
    ua_lower = USER_AGENT.lower()
    assert "sellercopilot" in ua_lower
    assert "automated" in ua_lower
    assert "ai agent" in ua_lower


def test_user_agent_declares_bsa_agent_policy_compliance():
    from ppc_ads_client import USER_AGENT
    assert "BSA-Agent-Policy" in USER_AGENT
    # Includes the effective date so an Amazon auditor sees we know the date.
    assert "2026-03-04" in USER_AGENT


def test_user_agent_includes_compliance_url():
    from ppc_ads_client import USER_AGENT
    assert "https://" in USER_AGENT
    assert "agent-policy" in USER_AGENT.lower()


def test_lwa_request_uses_compliant_user_agent(monkeypatch):
    """LWA calls must carry the same self-identification as Ads API calls."""
    from ppc_ads_client import USER_AGENT as EXPECTED_UA
    import ppc_oauth

    captured = {}

    class _FakeResp:
        status_code = 200
        text = ""
        def json(self):
            return {"access_token": "x", "expires_in": 3600}

    def fake_post(url, data=None, headers=None, timeout=None):
        captured["headers"] = headers or {}
        return _FakeResp()

    monkeypatch.setattr(ppc_oauth.requests, "post", fake_post)

    # Smallest call path that reaches _post_form: refresh_access_token.
    ppc_oauth.refresh_access_token(refresh_token="fake-refresh-token")

    assert captured["headers"].get("User-Agent") == EXPECTED_UA


# ──────────────────────────────────────────────────────────────────────────
#  Kill switch (BSA Agent Policy compliance, Week 1)
# ──────────────────────────────────────────────────────────────────────────

def test_kill_switch_route_refuses_when_token_unset(client):
    """If PPC_ADMIN_TOKEN is empty, the endpoint refuses to run (503)."""
    import ppc_agent
    assert ppc_agent.PPC_ADMIN_TOKEN == ""
    resp = client.post("/ppc/admin/kill_switch/run")
    assert resp.status_code == 503


def test_kill_switch_route_rejects_bad_token(client, monkeypatch):
    import ppc_agent
    monkeypatch.setattr(ppc_agent, "PPC_ADMIN_TOKEN", "good-token")
    resp = client.post(
        "/ppc/admin/kill_switch/run",
        headers={"X-Admin-Token": "wrong-token"},
    )
    assert resp.status_code == 403


def test_kill_switch_route_deactivates_all_active_connections(
    client, monkeypatch, sqlite_conn, patch_server_db,
):
    import ppc_agent
    cur = sqlite_conn.cursor()
    cur.execute(
        """
        INSERT INTO amazon_connections
            (id, customer_id, seller_id, marketplace_id,
             refresh_token_encrypted, connected_at, active)
        VALUES (1, 'cust_a', 'A1', 'ATVPDKIKX0DER', 'tok1', 0, 1)
        """,
    )
    cur.execute(
        """
        INSERT INTO amazon_connections
            (id, customer_id, seller_id, marketplace_id,
             refresh_token_encrypted, connected_at, active)
        VALUES (2, 'cust_b', 'A2', 'ATVPDKIKX0DER', 'tok2', 0, 1)
        """,
    )
    sqlite_conn.commit()

    monkeypatch.setattr(ppc_agent, "PPC_ADMIN_TOKEN", "good-token")
    resp = client.post(
        "/ppc/admin/kill_switch/run",
        headers={"X-Admin-Token": "good-token"},
    )
    assert resp.status_code == 200
    assert resp.get_json() == {"deactivated": 2}

    cur.execute("SELECT id, active FROM amazon_connections ORDER BY id")
    rows = cur.fetchall()
    assert rows == [(1, 0), (2, 0)]


def test_kill_switch_is_idempotent(
    client, monkeypatch, sqlite_conn, patch_server_db,
):
    import ppc_agent
    cur = sqlite_conn.cursor()
    cur.execute(
        """
        INSERT INTO amazon_connections
            (id, customer_id, seller_id, marketplace_id,
             refresh_token_encrypted, connected_at, active)
        VALUES (1, 'cust_a', 'A1', 'ATVPDKIKX0DER', 'tok1', 0, 1)
        """,
    )
    sqlite_conn.commit()
    monkeypatch.setattr(ppc_agent, "PPC_ADMIN_TOKEN", "good-token")

    first  = client.post("/ppc/admin/kill_switch/run", headers={"X-Admin-Token": "good-token"})
    second = client.post("/ppc/admin/kill_switch/run", headers={"X-Admin-Token": "good-token"})
    assert first.get_json() == {"deactivated": 1}
    assert second.get_json() == {"deactivated": 0}


def test_kill_switch_does_not_destroy_refresh_tokens(
    client, monkeypatch, sqlite_conn, patch_server_db,
):
    """
    The kill switch must flip active=0 but keep refresh_token_encrypted
    intact, so a seller can reconnect by simply re-OAuthing without
    re-encrypting from scratch.
    """
    import ppc_agent
    cur = sqlite_conn.cursor()
    cur.execute(
        """
        INSERT INTO amazon_connections
            (id, customer_id, seller_id, marketplace_id,
             refresh_token_encrypted, connected_at, active)
        VALUES (1, 'cust_a', 'A1', 'ATVPDKIKX0DER', 'tok-preserved', 0, 1)
        """,
    )
    sqlite_conn.commit()
    monkeypatch.setattr(ppc_agent, "PPC_ADMIN_TOKEN", "good-token")

    client.post("/ppc/admin/kill_switch/run", headers={"X-Admin-Token": "good-token"})

    cur.execute("SELECT refresh_token_encrypted FROM amazon_connections WHERE id = 1")
    assert cur.fetchone()[0] == "tok-preserved"
