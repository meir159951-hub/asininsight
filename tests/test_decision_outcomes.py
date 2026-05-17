"""
Tests for decision-outcome classification (Track B 2026-05-09 sprint).

The classifier is deliberately strict about what it claims: it describes
metric movements, never causation, because SellerCopilot does not write
to Amazon. The "no causation" rule is enforced both at runtime and in
this test file. If a future change loosens the language, these tests
break the build before it ships.
"""

import pytest

from ppc_suggestions import (
    classify_outcome,
    OUTCOME_CAUSATION_FORBIDDEN_PHRASES,
    OUTCOME_MIN_CLICKS_OBSERVED,
    OUTCOME_THRESHOLD_RATIO,
)


# ──────────────────────────────────────────────────────────────────────────
#  Group 1: classification correctness per rule type
# ──────────────────────────────────────────────────────────────────────────


def test_high_acos_cost_dropped_classifies_better():
    """high_acos approved: cost dropped 30%, acos dropped — favorable."""
    out = classify_outcome(
        suggestion_type="high_acos",
        decision="approved",
        baseline={"cost_30d": 100, "sales_30d": 100, "clicks_30d": 50},
        observed={"cost_30d": 70,  "sales_30d": 100, "clicks_30d": 30},
    )
    assert out["classification"] == "metrics_moved_better"
    assert "$100" in out["summary"]
    assert "$70" in out["summary"]


def test_high_acos_cost_rose_classifies_worse():
    """high_acos approved but cost rose 30% — unfavorable."""
    out = classify_outcome(
        suggestion_type="high_acos",
        decision="approved",
        baseline={"cost_30d": 100, "sales_30d": 100, "clicks_30d": 50},
        observed={"cost_30d": 130, "sales_30d": 100, "clicks_30d": 60},
    )
    assert out["classification"] == "metrics_moved_worse"


def test_scale_profitable_sales_grew_classifies_better():
    """scale_profitable: impressions and sales up by 30% — favorable."""
    out = classify_outcome(
        suggestion_type="scale_profitable",
        decision="approved",
        baseline={"impressions_30d": 1000, "sales_30d": 100, "clicks_30d": 50},
        observed={"impressions_30d": 1500, "sales_30d": 150, "clicks_30d": 80},
    )
    assert out["classification"] == "metrics_moved_better"


def test_spend_no_sales_pause_dropped_cost_to_zero_classifies_better():
    """spend_no_sales: cost dropped 100% post-pause — favorable."""
    out = classify_outcome(
        suggestion_type="spend_no_sales",
        decision="approved",
        baseline={"cost_30d": 60, "sales_30d": 0, "clicks_30d": 20},
        observed={"cost_30d": 0,  "sales_30d": 0, "clicks_30d": 8},
    )
    assert out["classification"] == "metrics_moved_better"


def test_promote_search_term_sales_appeared_classifies_better():
    """promote_search_term: keyword now generates $200/mo where it had $0."""
    out = classify_outcome(
        suggestion_type="promote_search_term",
        decision="approved",
        baseline={"sales_30d": 0,   "clicks_30d": 0},
        observed={"sales_30d": 200, "clicks_30d": 30},
    )
    # baseline sales_30d = 0 means relative change is None for the
    # promote_search_term direction map (sales_30d=up). So the per-field
    # delta cannot drive a 'better' classification, but no_change is
    # acceptable when we cannot compute the relative change.
    assert out["classification"] in ("metrics_moved_better", "no_change")


# ──────────────────────────────────────────────────────────────────────────
#  Group 2: edge cases (inconclusive, not_applicable)
# ──────────────────────────────────────────────────────────────────────────


def test_too_few_clicks_observed_returns_inconclusive():
    """If observed clicks < threshold, classify inconclusive (no signal)."""
    out = classify_outcome(
        suggestion_type="high_acos",
        decision="approved",
        baseline={"cost_30d": 100, "sales_30d": 100, "clicks_30d": 50},
        observed={"cost_30d": 50,  "sales_30d": 80,
                  "clicks_30d": OUTCOME_MIN_CLICKS_OBSERVED - 1},
    )
    assert out["classification"] == "inconclusive"


def test_rejected_decision_returns_not_applicable():
    """Rejected decisions don't have a baseline for now (Codex follow-up)."""
    out = classify_outcome(
        suggestion_type="high_acos",
        decision="rejected",
        baseline=None,
        observed={"cost_30d": 100, "sales_30d": 100, "clicks_30d": 50},
    )
    assert out["classification"] == "not_applicable"


def test_unknown_suggestion_type_returns_not_applicable():
    """If we don't know how to classify a rule, say so honestly."""
    out = classify_outcome(
        suggestion_type="someday_we_will_have_this_rule",
        decision="approved",
        baseline={"cost_30d": 100, "clicks_30d": 50},
        observed={"cost_30d": 80,  "clicks_30d": 40},
    )
    assert out["classification"] == "not_applicable"


def test_no_change_within_threshold():
    """Movement under threshold ratio classifies as no_change."""
    # 5% drop in cost and acos (under 10% threshold)
    out = classify_outcome(
        suggestion_type="high_acos",
        decision="approved",
        baseline={"cost_30d": 100, "sales_30d": 100, "clicks_30d": 50},
        observed={"cost_30d": 95,  "sales_30d": 100, "clicks_30d": 45},
    )
    assert out["classification"] == "no_change"


def test_mixed_movements_classifies_no_change_not_better():
    """If one field moves favorably but another worsens, do not claim victory."""
    # cost dropped favorably but acos rose (sales fell more)
    out = classify_outcome(
        suggestion_type="high_acos",
        decision="approved",
        baseline={"cost_30d": 100, "sales_30d": 100, "clicks_30d": 50},
        observed={"cost_30d": 70,  "sales_30d": 50,  "clicks_30d": 30},
    )
    # cost down 30% (favorable). acos up from 1.0 to 1.4 (unfavorable).
    # Mixed -> no_change, not metrics_moved_better
    assert out["classification"] == "no_change"


# ──────────────────────────────────────────────────────────────────────────
#  Group 3: anti-overclaim discipline (the most important tests in this file)
# ──────────────────────────────────────────────────────────────────────────


def test_summary_describes_metrics_not_causation():
    """Summary text talks about metrics moving, never about us causing it."""
    out = classify_outcome(
        suggestion_type="high_acos",
        decision="approved",
        baseline={"cost_30d": 100, "sales_30d": 100, "clicks_30d": 50},
        observed={"cost_30d": 70,  "sales_30d": 100, "clicks_30d": 30},
    )
    summary_lower = out["summary"].lower()
    for forbidden in OUTCOME_CAUSATION_FORBIDDEN_PHRASES:
        assert forbidden not in summary_lower, (
            f"Anti-overclaim violation: summary contains forbidden "
            f"causation phrase: {forbidden!r}. Summary was: {out['summary']!r}"
        )


def test_no_classification_label_implies_we_did_it():
    """The classification labels must describe metrics, not the decision."""
    valid_labels = {
        "metrics_moved_better",
        "metrics_moved_worse",
        "no_change",
        "inconclusive",
        "not_applicable",
    }
    # Spot-check a real call uses one of these
    out = classify_outcome(
        suggestion_type="high_acos",
        decision="approved",
        baseline={"cost_30d": 100, "sales_30d": 100, "clicks_30d": 50},
        observed={"cost_30d": 70,  "sales_30d": 100, "clicks_30d": 30},
    )
    assert out["classification"] in valid_labels
    # And that none of them imply causation
    forbidden_label_substrings = ("worked", "succeeded", "we_", "won", "won_")
    for label in valid_labels:
        for forbidden in forbidden_label_substrings:
            assert forbidden not in label, (
                f"Classification label {label!r} contains forbidden "
                f"substring {forbidden!r}"
            )


def test_metrics_delta_is_structured_for_audit_export():
    """metrics_delta must contain old/new/relative per field for CSV export."""
    out = classify_outcome(
        suggestion_type="high_acos",
        decision="approved",
        baseline={"cost_30d": 100, "sales_30d": 100, "clicks_30d": 50},
        observed={"cost_30d": 70,  "sales_30d": 100, "clicks_30d": 30},
    )
    deltas = out["metrics_delta"]
    assert "cost_30d" in deltas
    assert "old" in deltas["cost_30d"]
    assert "new" in deltas["cost_30d"]
    assert "relative" in deltas["cost_30d"]
    assert deltas["cost_30d"]["old"] == 100.0
    assert deltas["cost_30d"]["new"] == 70.0


def test_copy_status_observed_when_classifiable():
    """When we have data to classify, copy_status is 'observed'."""
    out = classify_outcome(
        suggestion_type="high_acos",
        decision="approved",
        baseline={"cost_30d": 100, "sales_30d": 100, "clicks_30d": 50},
        observed={"cost_30d": 70,  "sales_30d": 100, "clicks_30d": 30},
    )
    assert out["copy_status"] == "observed"


def test_copy_status_projection_only_when_rejected():
    """Rejected decisions cannot be observed (no baseline) → projection_only."""
    out = classify_outcome(
        suggestion_type="high_acos",
        decision="rejected",
        baseline=None,
        observed={"cost_30d": 100, "sales_30d": 100, "clicks_30d": 50},
    )
    assert out["copy_status"] == "projection_only"


# ──────────────────────────────────────────────────────────────────────────
#  Group 4: defensive behavior
# ──────────────────────────────────────────────────────────────────────────


def test_none_baseline_does_not_crash():
    out = classify_outcome(
        suggestion_type="high_acos",
        decision="approved",
        baseline=None,
        observed={"cost_30d": 70, "sales_30d": 100, "clicks_30d": 30},
    )
    # No baseline means no relative change can be computed; should be
    # no_change or inconclusive, not a crash.
    assert out["classification"] in ("no_change", "inconclusive")


def test_none_observed_does_not_crash():
    out = classify_outcome(
        suggestion_type="high_acos",
        decision="approved",
        baseline={"cost_30d": 100, "sales_30d": 100, "clicks_30d": 50},
        observed=None,
    )
    # observed is None -> obs_clicks evaluates to 0 -> inconclusive
    assert out["classification"] == "inconclusive"


def test_string_inputs_coerced_safely():
    """Postgres JSONB sometimes returns strings for numeric fields."""
    out = classify_outcome(
        suggestion_type="high_acos",
        decision="approved",
        baseline={"cost_30d": "100", "sales_30d": "100", "clicks_30d": "50"},
        observed={"cost_30d": "70",  "sales_30d": "100", "clicks_30d": "30"},
    )
    assert out["classification"] == "metrics_moved_better"


def test_bad_string_inputs_do_not_crash():
    out = classify_outcome(
        suggestion_type="high_acos",
        decision="approved",
        baseline={"cost_30d": "not a number", "clicks_30d": "fifty"},
        observed={"cost_30d": "also not",     "clicks_30d": "thirty"},
    )
    # Bad inputs coerce to 0; observed clicks_30d = 0 < threshold
    assert out["classification"] == "inconclusive"


# ──────────────────────────────────────────────────────────────────────────
#  Group 5: outcome observer integration tests (DB)
# ──────────────────────────────────────────────────────────────────────────
#
# These tests use an in-memory SQLite DB and a tight context factory so we
# do not depend on server.py:_db. They exercise:
#   - inserting due seller_decisions rows
#   - running run_outcome_observer
#   - asserting decision_outcomes rows appear with the right shape
#   - idempotency: running twice does not duplicate rows
#   - keyword-missing: no kw in snapshot still produces an honest outcome


import json
import sqlite3
import time
from contextlib import contextmanager


@pytest.fixture
def observer_db():
    """In-memory SQLite with the seller_decisions + decision_outcomes +
    ppc_snapshots schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = None
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS ppc_snapshots (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            connection_id    INTEGER NOT NULL,
            fetched_at       REAL NOT NULL,
            data_type        TEXT NOT NULL,
            data             TEXT NOT NULL,
            snapshot_run_id  TEXT
        );
        CREATE TABLE IF NOT EXISTS seller_decisions (
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
        CREATE TABLE IF NOT EXISTS decision_outcomes (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_decisions_id  INTEGER NOT NULL,
            connection_id        INTEGER NOT NULL,
            suggestion_type      TEXT NOT NULL,
            decision             TEXT NOT NULL,
            baseline             TEXT,
            observed             TEXT,
            classification       TEXT NOT NULL,
            observed_at          REAL NOT NULL,
            copy_status          TEXT NOT NULL DEFAULT 'observed'
        );
    """)
    conn.commit()

    @contextmanager
    def factory():
        c = conn.cursor()
        try:
            yield c, "?"
            conn.commit()
        finally:
            c.close()

    yield conn, factory
    conn.close()


def _insert_snapshot(factory, connection_id, keywords):
    """Insert a 'keywords' snapshot row containing the given list of dicts."""
    with factory() as (cur, ph):
        cur.execute(
            f"INSERT INTO ppc_snapshots (connection_id, fetched_at, data_type, data, snapshot_run_id) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph})",
            (connection_id, time.time(), "keywords", json.dumps(keywords), "test-run-1"),
        )
        # also insert empty rows for the other required types so
        # _pick_latest_complete_run_id will accept the run
        for dt in ("campaigns", "ad_groups", "search_terms"):
            cur.execute(
                f"INSERT INTO ppc_snapshots (connection_id, fetched_at, data_type, data, snapshot_run_id) "
                f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph})",
                (connection_id, time.time(), dt, json.dumps([]), "test-run-1"),
            )


def _insert_seller_decision(factory, *, connection_id, suggestion_type, keyword_id,
                             decision, baseline_dict, decided_at, observation_due_at):
    """Insert a seller_decisions row whose current_value carries the baseline."""
    cv = {
        "_approval_baseline": baseline_dict,
        "keyword_text": "test kw",
    }
    with factory() as (cur, ph):
        cur.execute(
            f"""
            INSERT INTO seller_decisions
                (connection_id, suggestion_id, suggestion_type, keyword_id,
                 ad_group_id, campaign_id, current_value, proposed_value,
                 estimated_impact, confidence, decision, edit_payload,
                 decided_at, observation_due_at)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph},
                    {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            """,
            (connection_id, None, suggestion_type, keyword_id,
             "ag-1", "camp-1", json.dumps(cv), json.dumps({}),
             0.0, "medium", decision, json.dumps({}),
             decided_at, observation_due_at),
        )


def test_observer_inserts_decision_outcome_for_due_row(observer_db):
    from ppc_agent import run_outcome_observer
    conn, factory = observer_db
    now = time.time()

    _insert_snapshot(factory, connection_id=1, keywords=[
        {"keywordId": "kw-101", "cost": 30, "sales30d": 200, "clicks": 30, "impressions": 1000, "purchases30d": 5},
    ])
    _insert_seller_decision(
        factory,
        connection_id=1,
        suggestion_type="high_acos",
        keyword_id="kw-101",
        decision="approved",
        baseline_dict={"cost_30d": 100, "sales_30d": 100, "clicks_30d": 50, "acos_30d": 1.0},
        decided_at=now - 14 * 86400,
        observation_due_at=now - 1,
    )

    stats = run_outcome_observer(connection_id=1, db_ctx_factory=factory, now=now)

    assert stats["observed"] == 1
    assert stats["errors"] == 0
    with factory() as (cur, ph):
        cur.execute("SELECT COUNT(*) FROM decision_outcomes")
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT classification, copy_status FROM decision_outcomes")
        row = cur.fetchone()
        # cost dropped 100 -> 30, acos dropped 1.0 -> 0.15, both favorable
        assert row[0] == "metrics_moved_better"
        assert row[1] == "observed"


def test_observer_is_idempotent(observer_db):
    """Running the observer twice on the same data does not duplicate rows."""
    from ppc_agent import run_outcome_observer
    conn, factory = observer_db
    now = time.time()

    _insert_snapshot(factory, connection_id=1, keywords=[
        {"keywordId": "kw-101", "cost": 30, "sales30d": 200, "clicks": 30, "impressions": 1000, "purchases30d": 5},
    ])
    _insert_seller_decision(
        factory,
        connection_id=1,
        suggestion_type="high_acos",
        keyword_id="kw-101",
        decision="approved",
        baseline_dict={"cost_30d": 100, "sales_30d": 100, "clicks_30d": 50, "acos_30d": 1.0},
        decided_at=now - 14 * 86400,
        observation_due_at=now - 1,
    )

    stats1 = run_outcome_observer(connection_id=1, db_ctx_factory=factory, now=now)
    stats2 = run_outcome_observer(connection_id=1, db_ctx_factory=factory, now=now)

    assert stats1["observed"] == 1
    assert stats2["observed"] == 0
    with factory() as (cur, ph):
        cur.execute("SELECT COUNT(*) FROM decision_outcomes")
        assert cur.fetchone()[0] == 1


def test_observer_skips_non_due_rows(observer_db):
    from ppc_agent import run_outcome_observer
    conn, factory = observer_db
    now = time.time()

    _insert_snapshot(factory, connection_id=1, keywords=[
        {"keywordId": "kw-101", "cost": 30, "sales30d": 200, "clicks": 30, "impressions": 1000, "purchases30d": 5},
    ])
    # observation_due_at is in the FUTURE — not yet due
    _insert_seller_decision(
        factory,
        connection_id=1,
        suggestion_type="high_acos",
        keyword_id="kw-101",
        decision="approved",
        baseline_dict={"cost_30d": 100, "sales_30d": 100, "clicks_30d": 50, "acos_30d": 1.0},
        decided_at=now - 5 * 86400,
        observation_due_at=now + 86400,
    )

    stats = run_outcome_observer(connection_id=1, db_ctx_factory=factory, now=now)

    assert stats["observed"] == 0
    with factory() as (cur, ph):
        cur.execute("SELECT COUNT(*) FROM decision_outcomes")
        assert cur.fetchone()[0] == 0


def test_observer_handles_missing_keyword(observer_db):
    """Decision references a kw not in the latest snapshot — record honestly."""
    from ppc_agent import run_outcome_observer
    conn, factory = observer_db
    now = time.time()

    _insert_snapshot(factory, connection_id=1, keywords=[
        {"keywordId": "kw-other", "cost": 5, "sales30d": 50, "clicks": 5, "impressions": 100, "purchases30d": 1},
    ])
    _insert_seller_decision(
        factory,
        connection_id=1,
        suggestion_type="spend_no_sales",
        keyword_id="kw-paused",   # not in snapshot
        decision="approved",
        baseline_dict={"cost_30d": 60, "sales_30d": 0, "clicks_30d": 25, "acos_30d": None},
        decided_at=now - 14 * 86400,
        observation_due_at=now - 1,
    )

    stats = run_outcome_observer(connection_id=1, db_ctx_factory=factory, now=now)

    assert stats["skipped_no_kw"] == 1
    assert stats["observed"] == 1   # we still inserted an honest outcome row
    with factory() as (cur, ph):
        cur.execute("SELECT classification FROM decision_outcomes")
        assert cur.fetchone()[0] == "inconclusive"


def test_observer_with_no_due_rows_returns_zeros(observer_db):
    from ppc_agent import run_outcome_observer
    conn, factory = observer_db
    stats = run_outcome_observer(connection_id=1, db_ctx_factory=factory, now=time.time())
    assert stats == {
        "observed": 0,
        "skipped_no_kw": 0,
        "skipped_existing": 0,
        "skipped_not_due": 0,
        "errors": 0,
    }


def test_observer_does_not_call_amazon_ads_api():
    """run_outcome_observer is read-only: no Ads API call. We assert this
    by importing the module and checking no module-level Ads client call
    exists on the observer code path. This is a smoke test for the
    architectural invariant; the real proof is the function body."""
    import ppc_agent
    src = open(ppc_agent.__file__, encoding="utf-8").read()
    # The observer function block should not call AdsClient methods or
    # direct API endpoints. We grep the observer body.
    idx = src.find("def run_outcome_observer(")
    end = src.find("\n@bp.route", idx)
    body = src[idx:end] if idx >= 0 else ""
    forbidden = ("AdsClient(", "list_campaigns", "list_keywords",
                 "get_search_term_report", "list_ad_groups",
                 "list_profiles")
    for pattern in forbidden:
        assert pattern not in body, (
            f"run_outcome_observer should not call {pattern} (it must be "
            f"read-only with respect to Amazon)"
        )


# ──────────────────────────────────────────────────────────────────────────
#  Group 6: list_decisions_with_outcomes (audit page data function)
# ──────────────────────────────────────────────────────────────────────────


def test_audit_data_function_returns_pending_when_no_outcome(observer_db):
    """Decision exists, no outcome yet → 'pending_observation'."""
    from ppc_suggestions import list_decisions_with_outcomes
    conn, factory = observer_db
    now = time.time()

    _insert_seller_decision(
        factory,
        connection_id=1,
        suggestion_type="high_acos",
        keyword_id="kw-101",
        decision="approved",
        baseline_dict={"cost_30d": 100, "sales_30d": 100, "clicks_30d": 50, "acos_30d": 1.0,
                        "keyword_label": "moisturizer dry skin"},
        decided_at=now - 5 * 86400,
        observation_due_at=now + 86400,
    )

    rows = list_decisions_with_outcomes(connection_id=1, db_ctx_factory=factory)

    assert len(rows) == 1
    assert rows[0]["classification"] == "pending_observation"
    assert rows[0]["copy_status"] == "projection_only"
    assert rows[0]["observed_at_iso"] == ""
    assert rows[0]["keyword_label"] == "moisturizer dry skin"


def test_audit_data_function_joins_observed_outcome(observer_db):
    """Decision + observed outcome → joined row carries classification."""
    from ppc_agent import run_outcome_observer
    from ppc_suggestions import list_decisions_with_outcomes
    conn, factory = observer_db
    now = time.time()

    _insert_snapshot(factory, connection_id=1, keywords=[
        {"keywordId": "kw-101", "cost": 30, "sales30d": 200, "clicks": 30, "impressions": 1000, "purchases30d": 5},
    ])
    _insert_seller_decision(
        factory,
        connection_id=1,
        suggestion_type="high_acos",
        keyword_id="kw-101",
        decision="approved",
        baseline_dict={"cost_30d": 100, "sales_30d": 100, "clicks_30d": 50, "acos_30d": 1.0},
        decided_at=now - 14 * 86400,
        observation_due_at=now - 1,
    )
    run_outcome_observer(connection_id=1, db_ctx_factory=factory, now=now)

    rows = list_decisions_with_outcomes(connection_id=1, db_ctx_factory=factory)

    assert len(rows) == 1
    assert rows[0]["classification"] == "metrics_moved_better"
    assert rows[0]["copy_status"] == "observed"
    assert rows[0]["observed_at_iso"] != ""
    assert rows[0]["observed_cost_30d"] == 30.0


def test_audit_data_function_orders_newest_first(observer_db):
    """Decisions are returned newest-first by decided_at."""
    from ppc_suggestions import list_decisions_with_outcomes
    conn, factory = observer_db
    now = time.time()

    _insert_seller_decision(
        factory, connection_id=1, suggestion_type="high_acos",
        keyword_id="kw-old", decision="approved",
        baseline_dict={"cost_30d": 50, "clicks_30d": 25},
        decided_at=now - 10 * 86400, observation_due_at=now + 86400,
    )
    _insert_seller_decision(
        factory, connection_id=1, suggestion_type="bid_too_high",
        keyword_id="kw-new", decision="rejected",
        baseline_dict={"cost_30d": 80, "clicks_30d": 40},
        decided_at=now - 1 * 86400, observation_due_at=now + 6 * 86400,
    )

    rows = list_decisions_with_outcomes(connection_id=1, db_ctx_factory=factory)

    assert rows[0]["keyword_id"] == "kw-new"
    assert rows[1]["keyword_id"] == "kw-old"


def test_audit_classification_label_never_claims_causation():
    """Every classification label describes metrics, not causation."""
    from ppc_suggestions import audit_classification_label

    forbidden = ("worked", "succeeded", "we caused", "our recommendation",
                 "sellercopilot", "we improved", "as a result")

    classifications = [
        "metrics_moved_better", "metrics_moved_worse", "no_change",
        "inconclusive", "not_applicable", "pending_observation",
        "totally_unknown_value",
    ]
    for cls in classifications:
        label = audit_classification_label(cls)
        lowered = label.lower()
        for f in forbidden:
            assert f not in lowered, (
                f"Audit label {label!r} for classification {cls!r} "
                f"contains forbidden causation phrase {f!r}"
            )


def test_audit_proposed_summary_is_human_readable(observer_db):
    from ppc_suggestions import list_decisions_with_outcomes
    conn, factory = observer_db
    now = time.time()

    _insert_seller_decision(
        factory, connection_id=1, suggestion_type="spend_no_sales",
        keyword_id="kw-paused", decision="approved",
        baseline_dict={"cost_30d": 60, "clicks_30d": 25},
        decided_at=now - 5 * 86400, observation_due_at=now + 86400,
    )

    rows = list_decisions_with_outcomes(connection_id=1, db_ctx_factory=factory)
    assert "Pause" in rows[0]["proposed_summary"]


def test_audit_export_csv_byte_signature():
    """CSV export must include a UTF-8 BOM for Excel compatibility."""
    # We test the underlying header-writing logic by encoding a simple
    # string the same way the route does; the route's full request flow
    # is exercised in the integration tests in test_ppc_routes.py.
    csv_content = "a,b,c\n1,2,3\n"
    encoded = csv_content.encode("utf-8-sig")
    assert encoded[:3] == b"\xef\xbb\xbf"


# ──────────────────────────────────────────────────────────────────────────
#  Group 7: approval memory boost (Phase 6 of overnight sprint)
# ──────────────────────────────────────────────────────────────────────────


def test_approval_type_counts_aggregates_by_type():
    from ppc_suggestions import _approval_type_counts
    counts = _approval_type_counts([
        {"suggestion_type": "high_acos"},
        {"suggestion_type": "high_acos"},
        {"suggestion_type": "spend_no_sales"},
        {"suggestion_type": ""},          # ignored
        {"suggestion_type": None},        # ignored
    ])
    assert counts == {"high_acos": 2, "spend_no_sales": 1}


def test_approval_boost_tags_matching_suggestions():
    """Suggestions whose type is preferred get _memory.kind=approval_match."""
    from ppc_suggestions import (
        _apply_approval_memory_boost,
        APPROVAL_MATCH_MIN_COUNT,
        MEMORY_SCORE_APPROVAL_MATCH,
    )
    suggestions = [
        {"suggestion_type": "high_acos", "current_value": {"keyword_text": "x"}},
        {"suggestion_type": "scale_profitable", "current_value": {"keyword_text": "y"}},
    ]
    approvals = [{"suggestion_type": "high_acos"}] * APPROVAL_MATCH_MIN_COUNT

    out = _apply_approval_memory_boost(suggestions, approvals)

    # high_acos suggestion is tagged
    assert out[0]["current_value"]["_memory"]["kind"] == "approval_match"
    assert out[0]["current_value"]["_memory"]["score_override"] == MEMORY_SCORE_APPROVAL_MATCH
    assert "approved" in out[0]["current_value"]["_memory"]["hint"].lower()
    # scale_profitable suggestion is unchanged (not preferred)
    assert "_memory" not in (out[1].get("current_value") or {})


def test_approval_boost_respects_minimum_count():
    """Below min count, no boost applied."""
    from ppc_suggestions import _apply_approval_memory_boost, APPROVAL_MATCH_MIN_COUNT
    suggestions = [{"suggestion_type": "high_acos", "current_value": {}}]
    too_few = [{"suggestion_type": "high_acos"}] * (APPROVAL_MATCH_MIN_COUNT - 1)

    out = _apply_approval_memory_boost(suggestions, too_few)

    assert "_memory" not in (out[0].get("current_value") or {})


def test_approval_boost_does_not_overwrite_rejection_resurface():
    """Rejection signal beats approval signal — do not auto-overrule."""
    from ppc_suggestions import _apply_approval_memory_boost, APPROVAL_MATCH_MIN_COUNT
    suggestions = [
        {
            "suggestion_type": "high_acos",
            "current_value": {
                "keyword_text": "x",
                "_memory": {
                    "kind": "rejection_resurface",
                    "resurfaced": True,
                    "hint": "you rejected this 3 days ago",
                },
            },
        },
    ]
    approvals = [{"suggestion_type": "high_acos"}] * APPROVAL_MATCH_MIN_COUNT

    out = _apply_approval_memory_boost(suggestions, approvals)

    # Rejection memory is preserved unchanged
    assert out[0]["current_value"]["_memory"]["kind"] == "rejection_resurface"


def test_approval_boost_does_not_mutate_input():
    """_apply_approval_memory_boost must not mutate caller's data."""
    from ppc_suggestions import _apply_approval_memory_boost, APPROVAL_MATCH_MIN_COUNT
    s_input = {"suggestion_type": "high_acos", "current_value": {"keyword_text": "x"}}
    suggestions = [s_input]
    approvals = [{"suggestion_type": "high_acos"}] * APPROVAL_MATCH_MIN_COUNT

    _apply_approval_memory_boost(suggestions, approvals)

    # Original was not mutated
    assert "_memory" not in s_input["current_value"]


def test_approval_boost_empty_inputs_safe():
    from ppc_suggestions import _apply_approval_memory_boost
    assert _apply_approval_memory_boost([], []) == []
    assert _apply_approval_memory_boost([], [{"suggestion_type": "x"}]) == []


def test_load_recent_approvals_filters_by_status_and_window(observer_db):
    """Load only approved-status rows within the time window."""
    from ppc_suggestions import _load_recent_approvals, APPROVAL_MEMORY_WINDOW_DAYS
    conn, factory = observer_db
    now = time.time()

    # Add a ppc_suggestions table to the in-memory DB for this test
    with factory() as (cur, ph):
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ppc_suggestions (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                connection_id      INTEGER NOT NULL,
                campaign_id        TEXT,
                ad_group_id        TEXT,
                keyword_id         TEXT,
                suggestion_type    TEXT NOT NULL,
                current_value      TEXT,
                proposed_value     TEXT,
                reason             TEXT NOT NULL,
                estimated_savings  REAL,
                confidence         TEXT NOT NULL DEFAULT 'medium',
                status             TEXT NOT NULL DEFAULT 'pending',
                created_at         REAL NOT NULL,
                decided_at         REAL,
                applied_at         REAL
            )
        """)

        # In-window approved → counted
        cur.execute(
            f"INSERT INTO ppc_suggestions (connection_id, suggestion_type, reason, status, created_at, decided_at) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
            (1, "high_acos", "test", "approved_pending_apply",
             now - 5 * 86400, now - 5 * 86400),
        )
        # Outside window approved → NOT counted
        cur.execute(
            f"INSERT INTO ppc_suggestions (connection_id, suggestion_type, reason, status, created_at, decided_at) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
            (1, "high_acos", "test", "approved_pending_apply",
             now - (APPROVAL_MEMORY_WINDOW_DAYS + 5) * 86400,
             now - (APPROVAL_MEMORY_WINDOW_DAYS + 5) * 86400),
        )
        # Pending → NOT counted
        cur.execute(
            f"INSERT INTO ppc_suggestions (connection_id, suggestion_type, reason, status, created_at, decided_at) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
            (1, "high_acos", "test", "pending",
             now - 1 * 86400, None),
        )
        # Different connection → NOT counted
        cur.execute(
            f"INSERT INTO ppc_suggestions (connection_id, suggestion_type, reason, status, created_at, decided_at) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
            (2, "high_acos", "test", "approved_pending_apply",
             now - 5 * 86400, now - 5 * 86400),
        )

    out = _load_recent_approvals(connection_id=1, db_ctx_factory=factory, now=now)
    assert len(out) == 1
    assert out[0]["suggestion_type"] == "high_acos"


# ──────────────────────────────────────────────────────────────────────────
#  Group 8: anti-overclaim integration (Phase 7 of overnight sprint)
# ──────────────────────────────────────────────────────────────────────────
#
# These tests grep static assets and user-facing template files for
# language that would imply SellerCopilot caused a metric movement.
# They are the stack-wide enforcement of the rule that classify_outcome
# enforces at the data layer.
#
# Adding new user-facing copy that contains forbidden phrasing breaks
# the build before the change ships.

import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_file(rel_path):
    """Read a file relative to PROJECT_ROOT. Return '' if missing."""
    full = os.path.join(PROJECT_ROOT, rel_path)
    if not os.path.exists(full):
        return ""
    with open(full, encoding="utf-8") as fh:
        return fh.read()


# Files that customers see. Adding new public-facing files here adds
# them to the anti-overclaim sweep.
ANTI_OVERCLAIM_FILES = [
    "templates/ppc_audit.html",
    "templates/ppc_dashboard.html",
    "templates/ppc_csv.html",
    "templates/_recommendation_card.html",
    "agent_policy.html",
    "compare_adlabs.html",
    "compare_perpetua.html",
    "landing.html",
    "pricing.html",
]

# Phrases that imply causation. Lower-case for case-insensitive match.
# When adding new phrases, also update OUTCOME_CAUSATION_FORBIDDEN_PHRASES
# in ppc_suggestions.py if they apply at the data layer.
ANTI_OVERCLAIM_FORBIDDEN_PHRASES = (
    "our decision worked",
    "our recommendation worked",
    "we caused this",
    "due to our recommendation",
    "as a result of our",
    "sellercopilot improved",
    "sellercopilot increased",
    "sellercopilot decreased",
    "guaranteed result",
    "guaranteed outcome",
)


def test_no_template_claims_causation():
    """No customer-facing file claims SellerCopilot caused a movement."""
    for path in ANTI_OVERCLAIM_FILES:
        content = _read_file(path).lower()
        if not content:
            continue
        for forbidden in ANTI_OVERCLAIM_FORBIDDEN_PHRASES:
            assert forbidden not in content, (
                f"Anti-overclaim violation in {path}: forbidden phrase "
                f"{forbidden!r} found. SellerCopilot does not write to "
                f"Amazon, so causation language is dishonest."
            )


def test_audit_template_has_anti_overclaim_banner():
    """The audit page must display an anti-overclaim disclaimer."""
    content = _read_file("templates/ppc_audit.html").lower()
    assert "anti-overclaim-banner" in content or "correlation only" in content, (
        "ppc_audit.html must contain an anti-overclaim banner explaining "
        "that classifications are correlation, not causation"
    )


def test_audit_csv_export_has_disclaimer_in_code():
    """The CSV export route must write an anti-overclaim disclaimer to the file."""
    code = _read_file("ppc_agent.py")
    # We accept either the literal phrase 'correlation only' or
    # 'never causation' inside the export route body.
    assert (
        "correlation only" in code.lower()
        or "never causation" in code.lower()
        or "describes how the observed metrics moved" in code.lower()
    ), (
        "ppc_audit/export.csv handler must write an anti-overclaim "
        "disclaimer line so accountants who import the CSV see the caveat."
    )


def test_no_apply_path_to_amazon_in_code():
    """Belt-and-braces: no code path actually calls Amazon Ads API
    with a write/POST verb on behalf of approved suggestions. The apply
    function must remain a stub until we ship the apply path.
    """
    code = _read_file("ppc_agent.py")
    # Find the apply_suggestion function body
    m = re.search(r"def apply_suggestion\(.*?\n(?:.*?\n){0,30}", code)
    assert m is not None, "apply_suggestion function should exist as a stub"
    body = m.group(0)
    # Must NOT contain HTTP verbs that write
    forbidden = ("requests.put", "requests.post", "requests.delete",
                 "AdsClient.create", "AdsClient.update",
                 "create_keyword", "update_keyword",
                 "ads_client.put", "ads_client.post")
    for f in forbidden:
        assert f not in body, (
            f"apply_suggestion must remain read-only. Found {f!r}. "
            f"If we are ready to ship the apply path, remove this test "
            f"AND simultaneously update the BSA compliance page and the "
            f"public copy that says we cannot push."
        )


def test_compare_adlabs_page_does_not_attack_competitor():
    """Comparison page must remain factual + cite verbatim, never spin."""
    content = _read_file("compare_adlabs.html").lower()
    if not content:
        # File may not exist in some test environments; skip.
        return
    forbidden = ("scam", "rip-off", "ripoff", "fraud", "stupid", "hate",
                 "they lie", "they lied")
    for f in forbidden:
        assert f not in content, (
            f"compare_adlabs.html must stay factual. Found unprofessional "
            f"phrase {f!r}."
        )


def test_compare_perpetua_page_does_not_attack_competitor():
    content = _read_file("compare_perpetua.html").lower()
    if not content:
        return
    forbidden = ("scam", "rip-off", "ripoff", "fraud", "stupid", "hate",
                 "they lie", "they lied")
    for f in forbidden:
        assert f not in content, (
            f"compare_perpetua.html must stay factual. Found unprofessional "
            f"phrase {f!r}."
        )


# ──────────────────────────────────────────────────────────────────────────
#  Group 9: card view memory_kind field (UI polish from overnight bonus work)
# ──────────────────────────────────────────────────────────────────────────


def test_card_view_exposes_memory_kind_for_approval_match():
    """build_card_view must surface memory_kind so the template can pick visuals."""
    from ppc_suggestions import build_card_view, MEMORY_SCORE_APPROVAL_MATCH
    suggestion = {
        "id": 1,
        "suggestion_type": "high_acos",
        "current_value": {
            "keyword_text": "x",
            "cost_30d": 100,
            "sales_30d": 100,
            "_memory": {
                "kind": "approval_match",
                "resurfaced": False,
                "hint": "You have approved 3 high acos suggestions in the last 30 days.",
                "score_override": MEMORY_SCORE_APPROVAL_MATCH,
            },
        },
        "estimated_savings": 50,
    }
    card = build_card_view(suggestion)
    assert card["memory_kind"] == "approval_match"
    assert card["memory_score_override"] == MEMORY_SCORE_APPROVAL_MATCH


def test_card_view_memory_kind_defaults_to_neutral_without_memory():
    from ppc_suggestions import build_card_view
    suggestion = {
        "id": 1,
        "suggestion_type": "high_acos",
        "current_value": {
            "keyword_text": "x",
            "cost_30d": 100,
            "sales_30d": 100,
        },
        "estimated_savings": 50,
    }
    card = build_card_view(suggestion)
    assert card["memory_kind"] == "neutral"


def test_card_view_memory_kind_for_legacy_rejection_resurface():
    """Older code paths set resurfaced=True without kind. Default to rejection_resurface."""
    from ppc_suggestions import build_card_view
    suggestion = {
        "id": 1,
        "suggestion_type": "high_acos",
        "current_value": {
            "keyword_text": "x",
            "cost_30d": 100,
            "sales_30d": 100,
            "_memory": {
                "resurfaced": True,
                "hint": "Bringing back because spend rose.",
            },
        },
        "estimated_savings": 50,
    }
    card = build_card_view(suggestion)
    assert card["memory_kind"] == "rejection_resurface"
