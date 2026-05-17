"""
Flask route tests for the PPC suggestion endpoints.

Covers:
- /ppc/suggestions                 GET  list pending per connection
- /ppc/suggestions/refresh         POST run engine for the customer's connections
- /ppc/suggestions/<id>/approve    POST flip status to approved_pending_apply
- /ppc/suggestions/<id>/reject     POST flip status to rejected
- Cross-tenant safety              customer B cannot mutate customer A's row

Routing strategy:
- We import the real `server.app` to exercise the wired blueprint.
- We monkey-patch `server._db` with an in-memory sqlite context manager so the
  tests do not touch the project's local asininsight.db file.

Each route does `from server import _db` lazily inside the function body, so
patching server._db at test setup time propagates to every call without us
having to touch ppc_agent's locals.
"""

from __future__ import annotations

import os
import sys
import json
import time
import sqlite3
from contextlib import contextmanager

import pytest

# Make repo root importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test-only env vars consumed by server.py / ppc_agent.py at import time.
os.environ.setdefault("FLASK_SECRET_KEY",       "test_secret_key_xxxxxxxxxxxxxxxxxxxxxxxxx")
os.environ.setdefault(
    "PPC_TOKEN_ENCRYPTION_KEY",
    "rRiUz3xHGbXbBZI9xn-yY9JvJ6yL5y6KqzNc6VxQ1zU=",   # generated with Fernet.generate_key()
)
os.environ.setdefault("SP_API_CLIENT_ID",     "test_client_id")
os.environ.setdefault("SP_API_CLIENT_SECRET", "test_client_secret")

from mock_ppc_data import seed_mock_snapshot   # noqa: E402


# ──────────────────────────────────────────────────────────────────────────
#  Fixtures
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
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        connection_id INTEGER NOT NULL,
        fetched_at    REAL NOT NULL,
        data_type     TEXT NOT NULL,
        data          TEXT NOT NULL
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
def app():
    """Real Flask app with PPC blueprint already registered."""
    from server import app as flask_app
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(monkeypatch):
    """
    Replace server._db with a context manager backed by an in-memory sqlite.
    Yields the underlying connection so tests can seed and assert directly.
    """
    conn = sqlite3.connect(":memory:")
    conn.executescript(_PPC_SCHEMA)

    @contextmanager
    def _db():
        cur = conn.cursor()
        try:
            yield (cur, "?")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    import server
    monkeypatch.setattr(server, "_db", _db, raising=True)
    monkeypatch.setattr(server, "DATABASE_URL", "", raising=False)

    yield conn
    conn.close()


def _insert_connection(conn, customer_id: str, connection_id: int = 1) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO amazon_connections
            (id, customer_id, seller_id, marketplace_id, refresh_token_encrypted,
             connected_at, last_synced_at, active)
        VALUES (?, ?, ?, 'ATVPDKIKX0DER', 'enc-blob', ?, NULL, 1)
        """,
        (connection_id, customer_id, f"A1MOCK{customer_id}", time.time()),
    )
    conn.commit()
    return connection_id


def _login(client, customer_id: str = "cust_a"):
    with client.session_transaction() as sess:
        sess["customer_id"] = customer_id


def _seed_pending_suggestion(conn, connection_id: int,
                             suggestion_type: str = "spend_no_sales",
                             estimated_savings: float = 9.20) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ppc_suggestions
          (connection_id, campaign_id, ad_group_id, keyword_id,
           suggestion_type, current_value, proposed_value, reason,
           estimated_savings, confidence, status, created_at)
        VALUES
          (?, 'cmp-1', 'ag-1', 'kw-101',
           ?, '{"bid":0.95}', '{"state":"PAUSED"}', 'demo reason',
           ?, 'high', 'pending', ?)
        """,
        (connection_id, suggestion_type, estimated_savings, time.time()),
    )
    conn.commit()
    return int(cur.lastrowid)


def _seed_strong_waste_suggestion(
    conn, connection_id: int, *,
    keyword_id: str = "kw-200",
    keyword_text: str = "demo waste term",
    cost_30d: float = 200.0,
    clicks_30d: int = 80,
    estimated_savings: float | None = None,
) -> int:
    """
    Seed a 'spend_no_sales' suggestion that the Task-1 card view will
    score above the Task-2 first-view filters ($50/month + confidence > 0).

    Cost $200, clicks 80, 0 orders, 0 sales -> evidence band 0.75,
    sales-risk 1.00, action 1.00 -> estimated_impact = $150/month.
    """
    cur = conn.cursor()
    if estimated_savings is None:
        estimated_savings = cost_30d
    cv = json.dumps({
        "keyword_text": keyword_text,
        "state":          "ENABLED",
        "bid":            0.95,
        "cost_30d":       cost_30d,
        "clicks_30d":     clicks_30d,
        "purchases_30d":  0,
        "sales_30d":      0.0,
    })
    cur.execute(
        """
        INSERT INTO ppc_suggestions
          (connection_id, campaign_id, ad_group_id, keyword_id,
           suggestion_type, current_value, proposed_value, reason,
           estimated_savings, confidence, status, created_at)
        VALUES
          (?, 'cmp-strong', 'ag-strong', ?,
           'spend_no_sales', ?, '{"state":"PAUSED"}', 'strong waste reason',
           ?, 'high', 'pending', ?)
        """,
        (connection_id, keyword_id, cv, estimated_savings, time.time()),
    )
    conn.commit()
    return int(cur.lastrowid)


# ──────────────────────────────────────────────────────────────────────────
#  /ppc/suggestions GET
# ──────────────────────────────────────────────────────────────────────────

def test_list_suggestions_requires_login(client, db):
    resp = client.get("/ppc/suggestions")
    assert resp.status_code == 401


def test_list_suggestions_empty_when_no_connections(client, db):
    _login(client)
    resp = client.get("/ppc/suggestions")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["by_connection"] == {}
    assert body["money_found_total"] == 0.0


def test_list_suggestions_returns_pending_rows(client, db):
    cid = _insert_connection(db, "cust_a", connection_id=1)
    _seed_pending_suggestion(db, cid, "spend_no_sales", 9.20)
    _seed_pending_suggestion(db, cid, "high_acos",      23.81)
    _login(client, "cust_a")

    resp = client.get("/ppc/suggestions")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "1" in body["by_connection"]
    rows = body["by_connection"]["1"]
    assert len(rows) == 2
    types = {r["suggestion_type"] for r in rows}
    assert types == {"spend_no_sales", "high_acos"}
    assert body["money_found_total"] == pytest.approx(33.01, abs=0.01)


def test_list_suggestions_does_not_leak_other_customers_data(client, db):
    _insert_connection(db, "cust_a", connection_id=1)
    _insert_connection(db, "cust_b", connection_id=2)
    _seed_pending_suggestion(db, 2, "high_acos", 99.99)
    _login(client, "cust_a")

    resp = client.get("/ppc/suggestions")
    body = resp.get_json()
    # cust_a has no connections of their own with suggestions; cust_b's must
    # not appear under cust_a's session.
    assert body["money_found_total"] == 0.0
    assert "2" not in body["by_connection"]


# ──────────────────────────────────────────────────────────────────────────
#  /ppc/suggestions/refresh POST
# ──────────────────────────────────────────────────────────────────────────

def test_refresh_runs_engine_and_returns_summary(client, db):
    cid = _insert_connection(db, "cust_a", connection_id=1)

    @contextmanager
    def _db():
        cur = db.cursor()
        try:
            yield (cur, "?")
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            cur.close()

    seed_mock_snapshot(connection_id=cid, db_context_manager=_db)

    _login(client, "cust_a")
    resp = client.post("/ppc/suggestions/refresh")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["money_found_total"] > 0
    assert any(s["connection_id"] == cid and s["count"] >= 5 for s in body["summary"])

    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM ppc_suggestions WHERE connection_id = 1 AND status = 'pending'")
    assert cur.fetchone()[0] >= 5


def test_refresh_requires_login(client, db):
    resp = client.post("/ppc/suggestions/refresh")
    assert resp.status_code == 401


def test_refresh_with_no_connections_returns_zero(client, db):
    """A logged-in customer with no connected Amazon accounts gets 0/0."""
    _login(client, "cust_a")
    resp = client.post("/ppc/suggestions/refresh")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["money_found_total"] == 0.0
    assert body["summary"] == []


# ──────────────────────────────────────────────────────────────────────────
#  Origin / Referer guard on PPC POST routes
# ──────────────────────────────────────────────────────────────────────────

def test_origin_guard_noop_when_site_url_unset(client, db):
    """Local dev / tests: SITE_URL is empty, the guard is a no-op."""
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_suggestion(db, cid)
    _login(client, "cust_a")

    # No Origin header at all; should still succeed because SITE_URL is "".
    resp = client.post(f"/ppc/suggestions/{sid}/approve")
    assert resp.status_code == 200


def test_origin_guard_rejects_cross_origin_post_when_site_url_set(client, db, monkeypatch):
    """Production: server.SITE_URL set, Origin from another host => 403.

    Note: the guard reads server.SITE_URL (the production source), NOT
    app.config. The patch must hit the module-level value to mirror prod.
    """
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_suggestion(db, cid)
    _login(client, "cust_a")

    import server
    monkeypatch.setattr(server, "SITE_URL", "https://app.example.com", raising=False)

    resp = client.post(
        f"/ppc/suggestions/{sid}/approve",
        headers={"Origin": "https://attacker.example.net"},
    )
    assert resp.status_code == 403


def test_origin_guard_allows_matching_origin(client, db, monkeypatch):
    """Production: server.SITE_URL set, Origin matches => allowed."""
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_suggestion(db, cid)
    _login(client, "cust_a")

    import server
    monkeypatch.setattr(server, "SITE_URL", "https://app.example.com", raising=False)

    resp = client.post(
        f"/ppc/suggestions/{sid}/approve",
        headers={"Origin": "https://app.example.com"},
    )
    assert resp.status_code == 200


def test_origin_guard_falls_back_to_referer_when_origin_missing(client, db, monkeypatch):
    """Some browsers omit Origin; Referer host must match SITE_URL."""
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_suggestion(db, cid)
    _login(client, "cust_a")

    import server
    monkeypatch.setattr(server, "SITE_URL", "https://app.example.com", raising=False)

    good_referer = client.post(
        f"/ppc/suggestions/{sid}/approve",
        headers={"Referer": "https://app.example.com/ppc/dashboard"},
    )
    # The first call already approved the suggestion; create a fresh one.
    sid2 = _seed_pending_suggestion(db, cid)
    bad_referer = client.post(
        f"/ppc/suggestions/{sid2}/approve",
        headers={"Referer": "https://attacker.example.net/page"},
    )

    assert good_referer.status_code == 200
    assert bad_referer.status_code  == 403


def test_origin_guard_reads_production_source_not_app_config(client, db, monkeypatch):
    """
    Codex regression test (cycle 9 review): the guard must enforce when
    server.SITE_URL is set even if nothing seeds app.config["SITE_URL"].
    Earlier code path read from app.config and silently no-op'd in prod.
    """
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_suggestion(db, cid)
    _login(client, "cust_a")

    # Set ONLY the production source. Do not touch app.config["SITE_URL"].
    import server
    monkeypatch.setattr(server, "SITE_URL", "https://prod.example.com", raising=False)

    # Make sure no test-only seeded config sneaks past us.
    from flask import current_app  # noqa: F401  (just to highlight intent)

    resp = client.post(
        f"/ppc/suggestions/{sid}/approve",
        headers={"Origin": "https://attacker.example.net"},
    )
    assert resp.status_code == 403, (
        "Origin guard must read server.SITE_URL, not app.config; "
        "if this test fails the guard is no-oping in production."
    )


# ──────────────────────────────────────────────────────────────────────────
#  /ppc/suggestions/<id>/approve POST
# ──────────────────────────────────────────────────────────────────────────

def test_approve_flips_status_to_approved_pending_apply(client, db):
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_suggestion(db, cid)
    _login(client, "cust_a")

    resp = client.post(f"/ppc/suggestions/{sid}/approve")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "approved_pending_apply"

    cur = db.cursor()
    cur.execute("SELECT status, decided_at FROM ppc_suggestions WHERE id = ?", (sid,))
    status, decided_at = cur.fetchone()
    assert status == "approved_pending_apply"
    assert decided_at is not None


def test_approve_a_suggestion_owned_by_another_customer_returns_404(client, db):
    """Cross-tenant: cust_b cannot mutate cust_a's row."""
    cid_a = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_suggestion(db, cid_a)
    _insert_connection(db, "cust_b", connection_id=2)
    _login(client, "cust_b")

    resp = client.post(f"/ppc/suggestions/{sid}/approve")
    assert resp.status_code == 404

    cur = db.cursor()
    cur.execute("SELECT status FROM ppc_suggestions WHERE id = ?", (sid,))
    assert cur.fetchone()[0] == "pending"   # untouched


def test_approve_already_decided_suggestion_returns_404(client, db):
    """Approve only acts on pending rows; second approval is rejected."""
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_suggestion(db, cid)
    _login(client, "cust_a")

    first  = client.post(f"/ppc/suggestions/{sid}/approve")
    second = client.post(f"/ppc/suggestions/{sid}/approve")
    assert first.status_code  == 200
    assert second.status_code == 404


def test_approve_requires_login(client, db):
    resp = client.post("/ppc/suggestions/1/approve")
    assert resp.status_code == 401


# ──────────────────────────────────────────────────────────────────────────
#  /ppc/suggestions/<id>/reject POST
# ──────────────────────────────────────────────────────────────────────────

def test_reject_flips_status(client, db):
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_suggestion(db, cid)
    _login(client, "cust_a")

    resp = client.post(f"/ppc/suggestions/{sid}/reject")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "rejected"

    cur = db.cursor()
    cur.execute("SELECT status FROM ppc_suggestions WHERE id = ?", (sid,))
    assert cur.fetchone()[0] == "rejected"


def test_reject_does_not_touch_amazon(client, db):
    """Reject is purely a DB status change; no Amazon API call possible."""
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_suggestion(db, cid)
    _login(client, "cust_a")

    # If a route accidentally tried to call Amazon, requests would get used.
    # We don't mock anything network-shaped; the test only passes if the
    # implementation never reached out.
    resp = client.post(f"/ppc/suggestions/{sid}/reject")
    assert resp.status_code == 200


def test_reject_cross_tenant_returns_404(client, db):
    cid_a = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_suggestion(db, cid_a)
    _insert_connection(db, "cust_b", connection_id=2)
    _login(client, "cust_b")

    resp = client.post(f"/ppc/suggestions/{sid}/reject")
    assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────────────
#  /ppc/dashboard (HTML render)
# ──────────────────────────────────────────────────────────────────────────

def test_dashboard_renders_with_no_connections(client, db):
    """Logged-in customer with no Amazon accounts: dashboard still renders."""
    _login(client, "cust_a")
    resp = client.get("/ppc/dashboard")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "PPC Dashboard"               in body
    assert "Connect Amazon Account"      in body


def test_dashboard_renders_with_seeded_suggestions(client, db):
    """Dashboard renders the seeded suggestions and money-found total."""
    cid = _insert_connection(db, "cust_a", connection_id=1)

    @contextmanager
    def _db():
        cur = db.cursor()
        try:
            yield (cur, "?")
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            cur.close()

    seed_mock_snapshot(connection_id=cid, db_context_manager=_db)
    # Seed pending suggestions via the engine.
    import ppc_suggestions
    ppc_suggestions.generate_suggestions(cid, db_ctx_factory=_db)

    _login(client, "cust_a")
    resp = client.get("/ppc/dashboard")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Two-bucket money banner: separate savings vs growth opportunity wording.
    assert "Money you can save"            in body
    assert "Growth opportunity"            in body
    assert "Estimates only, not a guarantee" in body
    assert "Spend with no sales"           in body or "spend_no_sales" in body
    # The reason string from the engine must reach the page.
    assert "moisturizer for dry skin" in body
    # Per-type breakdown is rendered with the short labels (Waste / ACOS / etc).
    assert "Waste"                    in body
    assert "Promote"                  in body
    # Approve / Reject buttons must exist for each suggestion.
    assert "data-action=\"approve\"" in body
    assert "data-action=\"reject\""  in body
    # Stale-snapshot marker is included in the markup (JS toggles visibility
    # when the snapshot is older than 24h).
    assert "stale-marker" in body


def test_dashboard_redirects_unauthenticated(client, db):
    """Anonymous visitor goes to '/' rather than seeing a 401."""
    resp = client.get("/ppc/dashboard")
    assert resp.status_code in (302, 303)
    location = resp.headers.get("Location", "")
    assert location.endswith("/") or location == "/"


def test_dashboard_subtitle_does_not_imply_live_apply(client, db):
    """
    Old subtitle said "Nothing reaches Amazon until you click Approve."
    That is misleading: Approve only queues, the live applier is not yet
    built. Dashboard must explicitly disclose that approving queues, and
    must NOT phrase Approve as the trigger that pushes to Amazon.

    Per SELLERCOPILOT_POSITIONING_UPDATE.md section 8, "approval-first" is
    now trust scaffolding rather than the headline; the page leads with
    the decision-assistant framing.
    """
    _login(client, "cust_a")
    resp = client.get("/ppc/dashboard")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # New decision-assistant framing leads the page.
    assert "personal PPC decision assistant" in body
    # Honest queue language is present.
    assert "queues" in body or "queued" in body or "queue" in body
    # Decision history wording (foundation for seller memory).
    assert "decision history" in body
    # Live applier disclosure: nothing reaches Amazon yet.
    assert "live apply" in body or "live applier" in body
    assert "Seller Central" in body
    assert ("not sent to amazon" in body.lower()
            or "nothing is sent to amazon" in body.lower())
    # The misleading sentence must be gone.
    assert "Nothing reaches Amazon until you click Approve" not in body


def test_dashboard_renders_decision_message_slots(client, db):
    """
    Each suggestion must carry both a queued-after-approve and a
    rejected-after-reject decision message in the markup. They are hidden
    by default and revealed by JS once the route returns 200, so the
    seller never sees a faded row with no explanation.
    """
    cid = _insert_connection(db, "cust_a", connection_id=1)

    @contextmanager
    def _db():
        cur = db.cursor()
        try:
            yield (cur, "?")
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            cur.close()

    seed_mock_snapshot(connection_id=cid, db_context_manager=_db)
    import ppc_suggestions
    ppc_suggestions.generate_suggestions(cid, db_ctx_factory=_db)

    _login(client, "cust_a")
    resp = client.get("/ppc/dashboard")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Both decision-message variants must be present in the markup.
    # Class renamed in cycle-16 (Smart Recommendation Card).
    assert 'class="rec-decision-msg approved"' in body
    assert 'class="rec-decision-msg rejected"' in body
    # Wording must be unambiguous about queued state, no live push.
    assert "Not sent to Amazon yet" in body
    assert "Removed from this rotation" in body
    # Wording about decision history (foundation for seller memory).
    assert "decision history" in body
    # Card-side queued status note: tells the seller approve only records.
    assert "Approve records this decision" in body
    assert "does not send changes to Amazon yet" in body


# ──────────────────────────────────────────────────────────────────────────
#  Smart Recommendation Card (cycle-16 / Task 1)
# ──────────────────────────────────────────────────────────────────────────

def test_dashboard_renders_smart_recommendation_card_shape(client, db):
    """
    Dashboard must render the new <article class="rec-card"> partial,
    not the old <article class="suggestion"> markup. The card carries:
      - a risk badge (LOW/MEDIUM/HIGH RISK)
      - the agent-style type label (Waste cleanup, ACOS reduction, etc.)
      - a one-sentence headline
      - a financial-impact line
      - "Why this matters" prose
      - a Memory section
      - a Recommended action list
      - Approve / Reject / Edit buttons (Edit reserved + disabled)
      - Learn more details element
    """
    cid = _insert_connection(db, "cust_a", connection_id=1)

    @contextmanager
    def _db():
        cur = db.cursor()
        try:
            yield (cur, "?")
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            cur.close()

    seed_mock_snapshot(connection_id=cid, db_context_manager=_db)
    import ppc_suggestions
    ppc_suggestions.generate_suggestions(cid, db_ctx_factory=_db)

    _login(client, "cust_a")
    resp = client.get("/ppc/dashboard")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    # New card markup is in place.
    assert 'class="rec-card' in body
    assert 'class="suggestion"' not in body, "old .suggestion markup should be gone"

    # Risk badge classes are present (at least one of the three).
    assert ("risk-low" in body) or ("risk-medium" in body) or ("risk-high" in body)
    # At least one risk label string surfaces.
    assert ("LOW RISK" in body) or ("MEDIUM RISK" in body) or ("HIGH RISK" in body)

    # At least one agent-style type label is present (mock data fires
    # all five rules, so the strongest of the labels must show).
    type_labels = ["Waste cleanup", "ACOS reduction", "Overbid cleanup",
                   "Scale a winner", "Promote a search term"]
    assert any(label in body for label in type_labels), \
        "no agent-style type label rendered"

    # Per-card sections.
    assert "Why this matters" in body
    assert "Memory" in body
    assert "Recommended action" in body
    assert "Likely impact" in body

    # Buttons: Approve, Reject, Edit (disabled placeholder).
    assert 'data-action="approve"' in body
    assert 'data-action="reject"' in body
    assert 'data-action="edit"' in body
    assert "Edit (coming soon)" in body
    # The Edit button is reserved but not active yet.
    assert 'aria-disabled="true"' in body

    # Learn more block.
    assert "<details" in body
    assert "Learn more" in body
    assert "Estimated impact formula" in body

    # Default neutral memory hint.
    assert "No similar rejection found" in body


def test_dashboard_card_has_queued_status_note(client, db):
    """The recommendation card must always disclose that Approve only records."""
    cid = _insert_connection(db, "cust_a", connection_id=1)

    @contextmanager
    def _db():
        cur = db.cursor()
        try:
            yield (cur, "?")
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            cur.close()

    seed_mock_snapshot(connection_id=cid, db_context_manager=_db)
    import ppc_suggestions
    ppc_suggestions.generate_suggestions(cid, db_ctx_factory=_db)

    _login(client, "cust_a")
    body = client.get("/ppc/dashboard").get_data(as_text=True)

    assert "Approve records this decision. It does not send changes to Amazon yet." in body


def test_dashboard_card_anti_overclaim_no_past_tense_savings(client, db):
    """
    No past-tense realised-savings phrasing is allowed on the dashboard:
    the live applier does not exist yet, so any "you saved $X" copy is
    misleading.
    """
    cid = _insert_connection(db, "cust_a", connection_id=1)

    @contextmanager
    def _db():
        cur = db.cursor()
        try:
            yield (cur, "?")
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            cur.close()

    seed_mock_snapshot(connection_id=cid, db_context_manager=_db)
    import ppc_suggestions
    ppc_suggestions.generate_suggestions(cid, db_ctx_factory=_db)

    _login(client, "cust_a")
    body = client.get("/ppc/dashboard").get_data(as_text=True).lower()

    # The literal misleading phrases.
    for phrase in ("you saved", "we saved", "saved you", "guaranteed savings"):
        assert phrase not in body, f"misleading phrase '{phrase}' must not appear"


def test_approve_route_marks_status_and_renders_decided_state_on_reload(
    client, db,
):
    """
    Approve flips the row to approved_pending_apply (DB-only). On the
    next dashboard render we don't refetch decided rows, but the route's
    JSON contract must still be DB-only and the card markup must support
    decided state via the rec-decision-msg.{approved,rejected} blocks.
    """
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_suggestion(db, cid)
    _login(client, "cust_a")

    resp = client.post(f"/ppc/suggestions/{sid}/approve")
    assert resp.status_code == 200

    cur = db.cursor()
    cur.execute("SELECT status FROM ppc_suggestions WHERE id = ?", (sid,))
    assert cur.fetchone()[0] == "approved_pending_apply"

    # Card shape must contain both decided slots so the JS can reveal
    # the right one without a server round-trip.
    body = client.get("/ppc/dashboard").get_data(as_text=True)
    # The pending row was filtered out of the live list (engine returns
    # only pending) so we just assert the partial is intact for any
    # future card render. We re-seed a pending row to prove that.
    sid2 = _seed_pending_suggestion(db, cid)
    body = client.get("/ppc/dashboard").get_data(as_text=True)
    assert 'class="rec-decision-msg approved"' in body
    assert 'class="rec-decision-msg rejected"' in body


# ──────────────────────────────────────────────────────────────────────────
#  Top-N composite ranker on the live dashboard (cycle-17 / Task 2)
# ──────────────────────────────────────────────────────────────────────────

def _split_primary_and_overflow(body: str) -> tuple[str, str]:
    """
    Slice the rendered dashboard HTML into (primary, overflow) sections so
    we can count rec-cards in each independently. Markup contract:
      - Primary list:  <div class="suggestions-list" id="suggestions-...">
      - Overflow:      <details class="rec-overflow" id="overflow-...">
    """
    overflow_marker = '<details class="rec-overflow"'
    if overflow_marker in body:
        primary, _, overflow = body.partition(overflow_marker)
        return primary, overflow_marker + overflow
    return body, ""


def test_dashboard_first_view_caps_at_five_cards(client, db):
    """
    Seed 8 strong waste suggestions; only 5 must appear in the primary
    list. The remaining 3 must appear inside the rec-overflow block,
    behind 'Show 3 more'.
    """
    cid = _insert_connection(db, "cust_a", connection_id=1)
    for i in range(1, 9):                                # 8 strong cards
        _seed_strong_waste_suggestion(
            db, cid,
            keyword_id=f"kw-strong-{i:02d}",
            keyword_text=f"strong waste term {i:02d}",
            cost_30d=200.0 + i,                          # tie-break by impact
            clicks_30d=80,
        )
    _login(client, "cust_a")
    body = client.get("/ppc/dashboard").get_data(as_text=True)

    primary, overflow = _split_primary_and_overflow(body)
    primary_count  = primary.count('class="rec-card')
    overflow_count = overflow.count('class="rec-card')
    total_count    = body.count('class="rec-card')

    assert primary_count == 5, \
        f"primary list rendered {primary_count} cards, expected 5"
    assert overflow_count == 3, \
        f"overflow rendered {overflow_count} cards, expected 3"
    assert total_count == 8, "every seeded card must render somewhere"
    # Show-N-more affordance text.
    assert "Show 3 more" in body


def test_dashboard_show_more_affordance_appears_when_overflow(client, db):
    """A single overflow item still surfaces 'Show 1 more'."""
    cid = _insert_connection(db, "cust_a", connection_id=1)
    for i in range(1, 7):                                # 6 strong cards
        _seed_strong_waste_suggestion(
            db, cid,
            keyword_id=f"kw-overflow-{i:02d}",
            keyword_text=f"overflow term {i:02d}",
            cost_30d=180.0 + i,
            clicks_30d=80,
        )
    _login(client, "cust_a")
    body = client.get("/ppc/dashboard").get_data(as_text=True)

    primary, overflow = _split_primary_and_overflow(body)
    assert primary.count('class="rec-card')  == 5
    assert overflow.count('class="rec-card') == 1
    assert "Show 1 more" in body
    assert '<details class="rec-overflow"' in body


def test_dashboard_no_overflow_when_under_cap(client, db):
    """Three strong cards render exactly three; no overflow block."""
    cid = _insert_connection(db, "cust_a", connection_id=1)
    for i in range(1, 4):
        _seed_strong_waste_suggestion(
            db, cid,
            keyword_id=f"kw-under-{i:02d}",
            keyword_text=f"under term {i:02d}",
            cost_30d=180.0 + i,
            clicks_30d=80,
        )
    _login(client, "cust_a")
    body = client.get("/ppc/dashboard").get_data(as_text=True)

    assert body.count('class="rec-card') == 3
    assert '<details class="rec-overflow"' not in body
    # No "Show N more" affordance when nothing was hidden.
    assert "Show " not in body or "Show 0 more" not in body


def test_dashboard_one_strong_recommendation_shows_one(client, db):
    """
    Brief constraint: 3-5 is a target / maximum, not a quota. Single
    strong card must render alone in the primary list.
    """
    cid = _insert_connection(db, "cust_a", connection_id=1)
    _seed_strong_waste_suggestion(
        db, cid,
        keyword_id="kw-only-strong",
        keyword_text="only strong term",
        cost_30d=200.0,
        clicks_30d=80,
    )
    # Plus a weak suggestion that fails the first-view filters.
    _seed_pending_suggestion(db, cid, "spend_no_sales", estimated_savings=2.0)

    _login(client, "cust_a")
    body = client.get("/ppc/dashboard").get_data(as_text=True)

    primary, overflow = _split_primary_and_overflow(body)
    assert primary.count('class="rec-card')  == 1, \
        "exactly one strong card belongs in the primary list"
    # The weak one is in overflow (filter-failed cards still appear there).
    assert overflow.count('class="rec-card') == 1
    assert "Show 1 more" in body


def test_dashboard_savings_banner_uses_full_list_not_top_only(client, db):
    """
    Banner totals must reflect every pending suggestion, not just the
    top-5 cards. If the banner only summed the visible top-N, sellers
    would see different numbers when they collapse / expand the
    overflow block.
    """
    cid = _insert_connection(db, "cust_a", connection_id=1)
    for i in range(1, 9):                                # 8 strong cards
        _seed_strong_waste_suggestion(
            db, cid,
            keyword_id=f"kw-banner-{i:02d}",
            keyword_text=f"banner term {i:02d}",
            cost_30d=200.0,
            clicks_30d=80,
            estimated_savings=100.0,                     # explicit
        )
    _login(client, "cust_a")
    body = client.get("/ppc/dashboard").get_data(as_text=True)

    # Sum across all 8 = $800 (savings). Hardcoded check, not a regex
    # against the banner area, because $800 is an unambiguous string.
    assert "$800.00" in body, \
        "savings banner must sum the full list (8 × $100)"


def test_dashboard_top_cards_are_ranked_higher_than_overflow(client, db):
    """
    The composite ranker must place a $300/mo card above a $60/mo card
    when both pass filters.
    """
    cid = _insert_connection(db, "cust_a", connection_id=1)
    # Big card -> definitely top.
    _seed_strong_waste_suggestion(
        db, cid, keyword_id="kw-big", keyword_text="big big big",
        cost_30d=600.0, clicks_30d=200,
    )
    # Five smaller cards. If only "big" makes it (say all 5 are below
    # filters), test still proves big is first; if some smaller ones
    # also pass, big should still be first by score.
    for i in range(1, 6):
        _seed_strong_waste_suggestion(
            db, cid,
            keyword_id=f"kw-small-{i}",
            keyword_text=f"small term {i}",
            cost_30d=100.0,
            clicks_30d=50,
        )
    _login(client, "cust_a")
    body = client.get("/ppc/dashboard").get_data(as_text=True)
    primary, _ = _split_primary_and_overflow(body)
    # The big card's keyword text appears before the small ones'.
    big_idx   = primary.find("big big big")
    small_idx = primary.find("small term 1")
    assert big_idx >= 0, "big strong card must render in the primary list"
    if small_idx >= 0:
        assert big_idx < small_idx, \
            "high-score card must come before low-score cards"


# ──────────────────────────────────────────────────────────────────────────
#  Minimal seller memory on the live dashboard (cycle-18 / Task 3)
# ──────────────────────────────────────────────────────────────────────────

def _seed_rejected_recently(db, *, connection_id, keyword_id="kw-skip",
                             keyword_text="rejected demo term",
                             cost_30d=200.0, clicks_30d=80,
                             estimated_savings=200.0, decided_days_ago=2):
    """
    Insert a rejected row matching what _seed_strong_waste_suggestion
    produces. decided_days_ago controls window membership.
    """
    cv = json.dumps({
        "keyword_text":   keyword_text,
        "state":          "ENABLED",
        "bid":            0.95,
        "cost_30d":       cost_30d,
        "clicks_30d":     clicks_30d,
        "purchases_30d":  0,
        "sales_30d":      0.0,
    })
    cur = db.cursor()
    decided_at = time.time() - decided_days_ago * 86400
    cur.execute(
        """
        INSERT INTO ppc_suggestions
          (connection_id, campaign_id, ad_group_id, keyword_id, suggestion_type,
           current_value, proposed_value, reason, estimated_savings, confidence,
           status, created_at, decided_at)
        VALUES (?, 'cmp-strong', 'ag-strong', ?, 'spend_no_sales',
                ?, '{"state":"PAUSED"}', 'demo',
                ?, 'high', 'rejected', ?, ?)
        """,
        (connection_id, keyword_id, cv, estimated_savings,
         decided_at - 1, decided_at),
    )
    db.commit()
    return int(cur.lastrowid)


def _seed_snapshot_for_keyword(db, *, connection_id, keyword_id, keyword_text,
                                ad_group_id="ag-strong", campaign_id="cmp-strong",
                                cost=200.0, clicks=80,
                                purchases=0, sales=0.0):
    """Seed a snapshot the engine will turn into a spend_no_sales suggestion."""
    now = time.time()
    cur = db.cursor()
    # Use INSERT-OR-IGNORE-ish logic: just appending is fine because
    # the test schema has no unique constraint on (connection_id, data_type).
    cur.executemany(
        "INSERT INTO ppc_snapshots (connection_id, fetched_at, data_type, data) "
        "VALUES (?, ?, ?, ?)",
        [
            (connection_id, now, "campaigns",
             json.dumps([{"campaignId": campaign_id, "name": "Cmp"}])),
            (connection_id, now, "ad_groups",
             json.dumps([{"adGroupId": ad_group_id, "campaignId": campaign_id,
                          "defaultBid": 0.95, "name": "Ag"}])),
            (connection_id, now, "keywords",
             json.dumps([{"keywordId": keyword_id, "adGroupId": ad_group_id,
                          "campaignId": campaign_id, "keywordText": keyword_text,
                          "matchType": "exact", "bid": 0.95, "state": "ENABLED"}])),
            (connection_id, now, "search_terms",
             json.dumps([{"keywordId": keyword_id, "adGroupId": ad_group_id,
                          "campaignId": campaign_id, "searchTerm": keyword_text,
                          "impressions": 2000, "clicks": clicks, "cost": cost,
                          "purchases30d": purchases, "sales30d": sales}])),
        ],
    )
    db.commit()


def test_dashboard_renders_memory_pill_when_skipped_present(client, db):
    """
    Seller rejects a recommendation 2 days ago. The same recommendation
    would re-fire on today's snapshot. The dashboard must render the
    memory pill 'Skipped 1 recommendation you recently rejected'.
    """
    cid = _insert_connection(db, "cust_a", connection_id=1)
    _seed_snapshot_for_keyword(
        db, connection_id=cid,
        keyword_id="kw-skip-1",
        keyword_text="blue ceramic coffee mug",
    )
    _seed_rejected_recently(
        db, connection_id=cid,
        keyword_id="kw-skip-1",
        keyword_text="blue ceramic coffee mug",
        decided_days_ago=2,
    )
    _login(client, "cust_a")
    body = client.get("/ppc/dashboard").get_data(as_text=True)
    assert 'class="rec-memory-pill"' in body
    assert "Skipped 1 recommendation you recently rejected" in body
    # Pill carries the seller's own keyword and dates.
    assert "blue ceramic coffee mug" in body
    assert "Rejected on " in body
    assert "Next check after " in body


def test_dashboard_no_memory_pill_when_no_recent_rejections(client, db):
    """No rejection history -> no pill. Quiet UI is correct."""
    cid = _insert_connection(db, "cust_a", connection_id=1)
    _seed_snapshot_for_keyword(
        db, connection_id=cid,
        keyword_id="kw-fresh",
        keyword_text="fresh kw",
    )
    _login(client, "cust_a")
    body = client.get("/ppc/dashboard").get_data(as_text=True)
    assert 'class="rec-memory-pill"' not in body
    assert "you recently rejected" not in body


def test_dashboard_suppressed_does_not_appear_in_primary_or_overflow(client, db):
    """
    The suppressed signature must not surface as a card anywhere on the
    page — neither in the primary top-N list nor in the 'Show N more'
    overflow. Only inside the memory pill.
    """
    cid = _insert_connection(db, "cust_a", connection_id=1)
    _seed_snapshot_for_keyword(
        db, connection_id=cid,
        keyword_id="kw-suppressed",
        keyword_text="suppressed term unique 12345",
    )
    _seed_rejected_recently(
        db, connection_id=cid,
        keyword_id="kw-suppressed",
        keyword_text="suppressed term unique 12345",
        decided_days_ago=3,
    )
    # Trigger the engine to do the suppression and write the empty
    # pending list.
    import ppc_suggestions
    ppc_suggestions.generate_suggestions(
        cid,
        db_ctx_factory=_make_db_factory(db),
    )
    _login(client, "cust_a")
    body = client.get("/ppc/dashboard").get_data(as_text=True)

    # The keyword text shows up only inside the memory pill, never as
    # a rec-card.
    pill_start = body.find('class="rec-memory-pill"')
    pill_end   = body.find("</details>", pill_start) if pill_start >= 0 else -1
    assert pill_start >= 0
    pill_section = body[pill_start:pill_end]
    rest_of_page = body[:pill_start] + body[pill_end:]

    assert "suppressed term unique 12345" in pill_section
    assert "suppressed term unique 12345" not in rest_of_page


def test_dashboard_resurfaced_card_shows_memory_hint(client, db):
    """
    Reject 2 days ago, spend then doubled in the new snapshot ->
    resurfaced card. The card must render the 'I'm bringing it back
    because ...' hint and pull the memory_score_override into ranking.
    """
    cid = _insert_connection(db, "cust_a", connection_id=1)
    _seed_snapshot_for_keyword(
        db, connection_id=cid,
        keyword_id="kw-resurfaced",
        keyword_text="resurfaced term unique abc",
        cost=400.0, clicks=120,                      # spend ↑↑
    )
    _seed_rejected_recently(
        db, connection_id=cid,
        keyword_id="kw-resurfaced",
        keyword_text="resurfaced term unique abc",
        cost_30d=200.0, clicks_30d=80,
        estimated_savings=200.0,
        decided_days_ago=2,
    )
    import ppc_suggestions
    ppc_suggestions.generate_suggestions(
        cid,
        db_ctx_factory=_make_db_factory(db),
    )
    _login(client, "cust_a")
    body = client.get("/ppc/dashboard").get_data(as_text=True)

    # The card is on the page (not just in the pill).
    assert "resurfaced term unique abc" in body
    # Memory hint surfaces in the card's Memory section.
    assert "bringing it back" in body
    # Either reason variant per Task 3 spec.
    assert ("estimated impact rose" in body
            or "spend increased" in body)
    # Pill should NOT include the resurfaced item — it's persisted, not
    # skipped. Only suppressed items live in the pill.
    pill_start = body.find('class="rec-memory-pill"')
    if pill_start >= 0:
        pill_end = body.find("</details>", pill_start)
        pill_section = body[pill_start:pill_end]
        assert "resurfaced term unique abc" not in pill_section


def _make_db_factory(db):
    """Factory that yields a fresh (cursor, '?') context manager per call,
    matching server._db's contract for memory-layer DB access."""
    @contextmanager
    def _factory():
        cur = db.cursor()
        try:
            yield (cur, "?")
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            cur.close()
    return _factory


# ──────────────────────────────────────────────────────────────────────────
#  Task 4 / Minimal Proof of Impact — approve baseline + dashboard
# ──────────────────────────────────────────────────────────────────────────


def _seed_pending_with_metrics(
    conn, connection_id: int, *,
    keyword_id: str = "kw-A1",
    keyword_text: str = "wireless headphones",
    cost_30d: float = 200.0,
    sales_30d: float = 0.0,
    clicks_30d: int = 80,
    purchases_30d: int = 0,
    estimated_savings: float = 200.0,
    target_acos: float | None = None,
    suggestion_type: str = "spend_no_sales",
) -> int:
    cv: dict = {
        "keyword_text":  keyword_text,
        "cost_30d":      cost_30d,
        "sales_30d":     sales_30d,
        "clicks_30d":    clicks_30d,
        "purchases_30d": purchases_30d,
        "bid":           0.95,
        "state":         "ENABLED",
    }
    pv: dict = {"state": "PAUSED"}
    if target_acos is not None:
        pv["target_acos"] = target_acos
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ppc_suggestions
          (connection_id, campaign_id, ad_group_id, keyword_id,
           suggestion_type, current_value, proposed_value, reason,
           estimated_savings, confidence, status, created_at)
        VALUES (?, 'cmp-1', 'ag-1', ?, ?, ?, ?, 'demo', ?, 'high',
                'pending', ?)
        """,
        (connection_id, keyword_id, suggestion_type,
         json.dumps(cv), json.dumps(pv), estimated_savings, time.time()),
    )
    conn.commit()
    return int(cur.lastrowid)


def test_approve_route_writes_approval_baseline_into_current_value(client, db):
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_with_metrics(db, cid)
    _login(client, "cust_a")

    resp = client.post(f"/ppc/suggestions/{sid}/approve")
    assert resp.status_code == 200

    cur = db.cursor()
    cur.execute("SELECT current_value, status FROM ppc_suggestions WHERE id = ?", (sid,))
    row = cur.fetchone()
    cv = json.loads(row[0])
    assert row[1] == "approved_pending_apply"
    assert "_approval_baseline" in cv
    baseline = cv["_approval_baseline"]
    for key in ("approved_at", "approved_at_iso", "cost_30d", "sales_30d",
                "orders_30d", "clicks_30d", "estimated_impact",
                "target_acos_used", "keyword_label", "note"):
        assert key in baseline


def test_approve_route_baseline_captures_observed_metrics(client, db):
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_with_metrics(
        db, cid,
        cost_30d=180.0, sales_30d=0.0,
        clicks_30d=72, purchases_30d=0,
        estimated_savings=180.0,
    )
    _login(client, "cust_a")
    assert client.post(f"/ppc/suggestions/{sid}/approve").status_code == 200

    cur = db.cursor()
    cur.execute("SELECT current_value FROM ppc_suggestions WHERE id = ?", (sid,))
    baseline = json.loads(cur.fetchone()[0])["_approval_baseline"]
    assert baseline["cost_30d"]         == pytest.approx(180.0)
    assert baseline["sales_30d"]        == pytest.approx(0.0)
    assert baseline["clicks_30d"]       == 72
    assert baseline["orders_30d"]       == 0
    assert baseline["estimated_impact"] == pytest.approx(180.0)
    assert baseline["acos_30d"]         is None
    assert baseline["keyword_label"]    == "wireless headphones"


def test_approve_route_baseline_captures_target_acos_when_present(client, db):
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_with_metrics(
        db, cid,
        suggestion_type="high_acos",
        cost_30d=100.0, sales_30d=200.0,
        clicks_30d=50, purchases_30d=4,
        target_acos=0.30,
        estimated_savings=40.0,
    )
    _login(client, "cust_a")
    assert client.post(f"/ppc/suggestions/{sid}/approve").status_code == 200

    cur = db.cursor()
    cur.execute("SELECT current_value FROM ppc_suggestions WHERE id = ?", (sid,))
    baseline = json.loads(cur.fetchone()[0])["_approval_baseline"]
    assert baseline["target_acos_used"] == pytest.approx(0.30)
    assert baseline["acos_30d"]         == pytest.approx(0.50)   # 100/200


def test_approve_route_baseline_does_not_clobber_other_current_value_fields(client, db):
    """The baseline must merge under _approval_baseline; other keys stay put."""
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_with_metrics(db, cid, keyword_text="kw text X")
    _login(client, "cust_a")
    assert client.post(f"/ppc/suggestions/{sid}/approve").status_code == 200

    cur = db.cursor()
    cur.execute("SELECT current_value FROM ppc_suggestions WHERE id = ?", (sid,))
    cv = json.loads(cur.fetchone()[0])
    assert cv["keyword_text"] == "kw text X"
    assert cv["bid"]          == 0.95
    assert cv["state"]        == "ENABLED"
    assert "_approval_baseline" in cv


def test_approve_route_remains_db_only_no_amazon_write(client, db):
    """
    No mocks here — the test only passes if the approve path never reached
    out for an HTTP / Ads-API call. Mirrors test_reject_does_not_touch_amazon.
    """
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_with_metrics(db, cid)
    _login(client, "cust_a")

    resp = client.post(f"/ppc/suggestions/{sid}/approve")
    assert resp.status_code == 200
    assert resp.get_json() == {
        "status": "approved_pending_apply",
        "suggestion_id": sid,
    }
    # applied_at must remain None: the applier worker is not built yet.
    cur = db.cursor()
    cur.execute("SELECT applied_at FROM ppc_suggestions WHERE id = ?", (sid,))
    assert cur.fetchone()[0] is None


def test_approve_route_cross_tenant_does_not_write_baseline(client, db):
    """A cust_b approve attempt on cust_a's row must leave current_value clean."""
    cid_a = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_with_metrics(db, cid_a)
    _insert_connection(db, "cust_b", connection_id=2)
    _login(client, "cust_b")

    resp = client.post(f"/ppc/suggestions/{sid}/approve")
    assert resp.status_code == 404

    cur = db.cursor()
    cur.execute("SELECT current_value, status FROM ppc_suggestions WHERE id = ?", (sid,))
    cv_str, status = cur.fetchone()
    cv = json.loads(cv_str)
    assert status == "pending"
    assert "_approval_baseline" not in cv


def test_dashboard_renders_projection_block_with_required_copy(client, db):
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_with_metrics(db, cid)
    _login(client, "cust_a")
    assert client.post(f"/ppc/suggestions/{sid}/approve").status_code == 200

    body = client.get("/ppc/dashboard").get_data(as_text=True)
    # Section markup
    assert 'class="approved-projections"' in body
    # Four required disclaimer phrases (verbatim per Task 4 spec)
    assert "Projection only" in body
    assert "Calculated from the prior 30 days" in body
    assert "Nothing has been applied to Amazon yet" in body
    assert "Real results will differ" in body


def test_dashboard_projection_block_renders_keyword_label_and_impact(client, db):
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_with_metrics(
        db, cid, keyword_text="wireless headphones",
        cost_30d=180.0, estimated_savings=180.0,
    )
    _login(client, "cust_a")
    assert client.post(f"/ppc/suggestions/{sid}/approve").status_code == 200

    body = client.get("/ppc/dashboard").get_data(as_text=True)
    assert "wireless headphones" in body
    assert "$180.00" in body
    assert "Projected impact" in body


def test_dashboard_projection_block_anti_overclaim(client, db):
    """Approved-row block must not contain past-tense / guarantee wording."""
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_with_metrics(db, cid)
    _login(client, "cust_a")
    assert client.post(f"/ppc/suggestions/{sid}/approve").status_code == 200

    body = client.get("/ppc/dashboard").get_data(as_text=True).lower()
    for phrase in (
        "you saved",
        "we saved",
        "saved you",
        "guaranteed",
        "realized savings",
        "realised savings",
    ):
        assert phrase not in body, f"forbidden phrase '{phrase}' must not appear"


def test_dashboard_no_projection_block_when_no_approvals(client, db):
    """Empty approved set -> the section must not render at all."""
    cid = _insert_connection(db, "cust_a", connection_id=1)
    _seed_pending_with_metrics(db, cid)
    _login(client, "cust_a")

    body = client.get("/ppc/dashboard").get_data(as_text=True)
    assert 'class="approved-projections"' not in body


def test_dashboard_projection_block_excludes_old_approvals(client, db):
    """Approved more than 14 days ago must not appear in the projection block."""
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_with_metrics(db, cid, keyword_text="ancient term zzz")
    _login(client, "cust_a")
    assert client.post(f"/ppc/suggestions/{sid}/approve").status_code == 200

    # Backdate the approval by 30 days.
    cur = db.cursor()
    cur.execute(
        "UPDATE ppc_suggestions SET decided_at = ? WHERE id = ?",
        (time.time() - 30 * 86400, sid),
    )
    db.commit()

    body = client.get("/ppc/dashboard").get_data(as_text=True)
    assert 'class="approved-projections"' not in body
    assert "ancient term zzz" not in body


# ──────────────────────────────────────────────────────────────────────────
#  Decision log writes (Week 1 of MVP Hardening Plan / Task 6)
# ──────────────────────────────────────────────────────────────────────────

def test_approve_writes_seller_decisions_row(client, db):
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_strong_waste_suggestion(
        db, cid,
        keyword_id="kw-log-approve",
        keyword_text="logged approve term",
    )
    _login(client, "cust_a")

    resp = client.post(f"/ppc/suggestions/{sid}/approve")
    assert resp.status_code == 200

    cur = db.cursor()
    cur.execute(
        "SELECT connection_id, suggestion_id, suggestion_type, decision, "
        "       decided_at, observation_due_at, keyword_id, ad_group_id "
        "FROM seller_decisions WHERE suggestion_id = ?",
        (sid,),
    )
    row = cur.fetchone()
    assert row is not None, "approve route must write to seller_decisions"
    assert row[0] == cid
    assert row[1] == sid
    assert row[2] == "spend_no_sales"
    assert row[3] == "approved"
    decided_at = row[4]
    obs_due    = row[5]
    assert decided_at is not None
    assert obs_due == decided_at + 7 * 86400
    assert row[6] == "kw-log-approve"
    assert row[7] == "ag-strong"


def test_reject_writes_seller_decisions_row(client, db):
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_strong_waste_suggestion(
        db, cid,
        keyword_id="kw-log-reject",
        keyword_text="logged reject term",
    )
    _login(client, "cust_a")

    resp = client.post(f"/ppc/suggestions/{sid}/reject")
    assert resp.status_code == 200

    cur = db.cursor()
    cur.execute(
        "SELECT decision, decided_at, observation_due_at, keyword_id "
        "FROM seller_decisions WHERE suggestion_id = ?",
        (sid,),
    )
    row = cur.fetchone()
    assert row is not None, "reject route must write to seller_decisions"
    assert row[0] == "rejected"
    assert row[2] == row[1] + 7 * 86400
    assert row[3] == "kw-log-reject"


def test_approve_log_captures_current_value_and_baseline(client, db):
    """The log row's current_value should include _approval_baseline."""
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_strong_waste_suggestion(db, cid)
    _login(client, "cust_a")

    resp = client.post(f"/ppc/suggestions/{sid}/approve")
    assert resp.status_code == 200

    cur = db.cursor()
    cur.execute(
        "SELECT current_value FROM seller_decisions WHERE suggestion_id = ?",
        (sid,),
    )
    cv = json.loads(cur.fetchone()[0])
    assert "_approval_baseline" in cv
    assert "approved_at" in cv["_approval_baseline"]


def test_reject_log_does_not_carry_approval_baseline(client, db):
    """Reject path should not inject _approval_baseline."""
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_strong_waste_suggestion(db, cid)
    _login(client, "cust_a")

    resp = client.post(f"/ppc/suggestions/{sid}/reject")
    assert resp.status_code == 200

    cur = db.cursor()
    cur.execute(
        "SELECT current_value FROM seller_decisions WHERE suggestion_id = ?",
        (sid,),
    )
    cv = json.loads(cur.fetchone()[0])
    assert "_approval_baseline" not in cv


def test_approve_log_failure_does_not_block_status_flip(client, db, monkeypatch):
    """If log_decision raises, the approve still succeeds and status flips."""
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_strong_waste_suggestion(db, cid)
    _login(client, "cust_a")

    import ppc_suggestions
    def boom(*a, **kw):
        raise RuntimeError("log path on fire")
    monkeypatch.setattr(ppc_suggestions, "log_decision", boom)

    resp = client.post(f"/ppc/suggestions/{sid}/approve")
    # Approve route must not surface log_decision exceptions to the seller.
    # The status flip already happened; logging is best-effort.
    assert resp.status_code == 200
    cur = db.cursor()
    cur.execute("SELECT status FROM ppc_suggestions WHERE id = ?", (sid,))
    status = cur.fetchone()[0]
    assert status == "approved_pending_apply"
    # And no log row was written (the boom function did not reach the DB).
    cur.execute("SELECT COUNT(*) FROM seller_decisions WHERE suggestion_id = ?", (sid,))
    assert cur.fetchone()[0] == 0


def test_reject_cross_tenant_does_not_write_log(client, db):
    """Cross-tenant reject must not produce a seller_decisions row."""
    cid_a = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_pending_suggestion(db, cid_a)
    _insert_connection(db, "cust_b", connection_id=2)
    _login(client, "cust_b")

    resp = client.post(f"/ppc/suggestions/{sid}/reject")
    assert resp.status_code == 404

    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM seller_decisions WHERE suggestion_id = ?", (sid,))
    assert cur.fetchone()[0] == 0


def test_approve_then_second_approve_does_not_write_two_log_rows(client, db):
    """The second approve hits 404 (status no longer pending) and must not log."""
    cid = _insert_connection(db, "cust_a", connection_id=1)
    sid = _seed_strong_waste_suggestion(db, cid)
    _login(client, "cust_a")

    first = client.post(f"/ppc/suggestions/{sid}/approve")
    second = client.post(f"/ppc/suggestions/{sid}/approve")
    assert first.status_code == 200
    assert second.status_code == 404

    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM seller_decisions WHERE suggestion_id = ?", (sid,))
    assert cur.fetchone()[0] == 1
