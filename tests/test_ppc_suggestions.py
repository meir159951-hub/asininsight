"""
Tests for ppc_suggestions.

Pattern: each rule has at least one positive-case test (the rule fires for
the keyword/search-term it should fire on) and one negative-case test (a
healthy keyword in the same dataset is NOT flagged).

The fixtures live in `mock_ppc_data` so the same dataset that exercises the
rules tonight is the one we wire into the dashboard for the demo. Drift
between test data and dashboard data is a future bug; this module shares
both with the rest of the codebase.
"""

from __future__ import annotations

import json

import pytest

import mock_ppc_data
from ppc_suggestions import (
    analyze,
    money_found_total,
    money_found_breakdown,
    count_by_type,
    summarize,
    savings_total,
    growth_opportunity_total,
    SAVINGS_RULE_TYPES,
    GROWTH_RULE_TYPES,
    _aggregate_keyword_perf,
)


# ──────────────────────────────────────────────────────────────────────────
#  Fixtures
# ──────────────────────────────────────────────────────────────────────────

@pytest.fixture
def snapshots():
    """Fresh copy of the mock snapshot per test (rules don't mutate, but to be safe)."""
    return mock_ppc_data.build_snapshot_payload()


@pytest.fixture
def all_suggestions(snapshots):
    return analyze(snapshots)


def _by_type(suggestions, suggestion_type):
    return [s for s in suggestions if s["suggestion_type"] == suggestion_type]


def _types_for_keyword(suggestions, keyword_id):
    return {s["suggestion_type"] for s in suggestions if s.get("keyword_id") == keyword_id}


# ──────────────────────────────────────────────────────────────────────────
#  Per-keyword performance roll-up
# ──────────────────────────────────────────────────────────────────────────

def test_aggregate_keyword_perf_sums_per_keyword(snapshots):
    """kw-101 has two search-term rows; their numbers should add up."""
    perf = _aggregate_keyword_perf(snapshots["search_terms"])
    p101 = perf.get("kw-101", {})
    # 6 + 2 = 8 clicks, 6.90 + 2.30 = 9.20 cost
    assert p101["clicks"]      == 8
    assert round(p101["cost"], 2) == 9.20
    assert p101["purchases30d"] == 0
    assert p101["sales30d"]    == 0.0


def test_aggregate_skips_rows_without_keyword_id():
    """Search-term rows without keywordId are ignored, never crash."""
    perf = _aggregate_keyword_perf([
        {"keywordId": "", "clicks": 5, "cost": 1.0, "sales30d": 1.0},
        {"clicks": 5, "cost": 1.0, "sales30d": 1.0},        # no key at all
        {"keywordId": "kw-x", "clicks": 3, "cost": 0.5, "sales30d": 7.0,
         "purchases30d": 1, "impressions": 10},
    ])
    assert list(perf.keys()) == ["kw-x"]
    assert perf["kw-x"]["sales30d"] == 7.0


# ──────────────────────────────────────────────────────────────────────────
#  Rule 1: spend_no_sales
# ──────────────────────────────────────────────────────────────────────────

def test_rule_spend_no_sales_fires_on_kw101(all_suggestions):
    """kw-101 has 8 clicks and $9.20 cost over 30 days, zero sales."""
    suggs = _by_type(all_suggestions, "spend_no_sales")
    matching = [s for s in suggs if s["keyword_id"] == "kw-101"]
    assert len(matching) == 1
    s = matching[0]
    assert s["proposed_value"] == {"state": "PAUSED"}
    assert s["estimated_savings"] == pytest.approx(9.20, abs=0.01)
    # Sample size is borderline ($9.20, 8 clicks): medium confidence is correct.
    assert s["confidence"] == "medium"
    assert "moisturizer for dry skin" in s["reason"]


def test_rule_spend_no_sales_high_confidence_at_higher_spend():
    """Above the $20 spend OR 20 click threshold the confidence is 'high'."""
    snap = {
        "campaigns":    [{"campaignId": "c"}],
        "ad_groups":    [{"adGroupId": "ag", "campaignId": "c", "defaultBid": 1.0}],
        "keywords":     [{"keywordId": "k", "adGroupId": "ag", "campaignId": "c",
                          "bid": 1.50, "keywordText": "noisy",
                          "matchType": "broad", "state": "ENABLED"}],
        "search_terms": [{
            "keywordId": "k", "adGroupId": "ag", "campaignId": "c",
            "searchTerm": "noisy", "matchType": "broad",
            "impressions": 4000, "clicks": 30, "cost": 32.50,
            "purchases30d": 0, "sales30d": 0.0,
        }],
    }
    suggs = analyze(snap)
    waste = _by_type(suggs, "spend_no_sales")
    assert len(waste) == 1
    assert waste[0]["confidence"] == "high"


def test_rule_spend_no_sales_does_not_fire_on_healthy_keyword(all_suggestions):
    """kw-103 ('hand cream') has $112 in sales — must not be flagged for waste."""
    types_103 = _types_for_keyword(all_suggestions, "kw-103")
    assert "spend_no_sales" not in types_103


def test_rule_spend_no_sales_below_min_cost_floor():
    """Cost below SPEND_NO_SALES_MIN_COST_USD does not trigger."""
    snap = {
        "campaigns":    [{"campaignId": "c", "name": "C"}],
        "ad_groups":    [{"adGroupId": "ag", "campaignId": "c", "defaultBid": 1.0}],
        "keywords": [{
            "keywordId":   "k", "adGroupId": "ag", "campaignId": "c",
            "keywordText": "tiny", "matchType": "exact", "bid": 0.5, "state": "ENABLED",
        }],
        "search_terms": [{
            "keywordId": "k", "adGroupId": "ag", "campaignId": "c",
            "searchTerm": "tiny", "matchType": "exact",
            "impressions": 200, "clicks": 6, "cost": 2.50,
            "purchases30d": 0, "sales30d": 0.0,
        }],
    }
    suggs = analyze(snap)
    # $2.50 < $5 min cost: should NOT fire even though clicks count is high.
    assert _by_type(suggs, "spend_no_sales") == []


def test_rule_spend_no_sales_below_min_clicks_floor():
    """Clicks below SPEND_NO_SALES_MIN_CLICKS does not trigger."""
    snap = {
        "campaigns":    [{"campaignId": "c", "name": "C"}],
        "ad_groups":    [{"adGroupId": "ag", "campaignId": "c", "defaultBid": 1.0}],
        "keywords": [{
            "keywordId":   "k", "adGroupId": "ag", "campaignId": "c",
            "keywordText": "rare", "matchType": "exact", "bid": 1.50, "state": "ENABLED",
        }],
        "search_terms": [{
            "keywordId": "k", "adGroupId": "ag", "campaignId": "c",
            "searchTerm": "rare", "matchType": "exact",
            "impressions": 1000, "clicks": 3, "cost": 12.00,
            "purchases30d": 0, "sales30d": 0.0,
        }],
    }
    # 3 clicks < 5 floor: not enough signal to call it waste.
    assert _by_type(analyze(snap), "spend_no_sales") == []


# ──────────────────────────────────────────────────────────────────────────
#  Rule 2: high_acos
# ──────────────────────────────────────────────────────────────────────────

def test_rule_high_acos_fires_on_kw102(all_suggestions):
    """kw-102: $41.80 cost, $59.97 sales -> ACOS ~70%."""
    suggs = _by_type(all_suggestions, "high_acos")
    matching = [s for s in suggs if s["keyword_id"] == "kw-102"]
    assert len(matching) == 1
    s = matching[0]
    cv = s["current_value"]
    # 41.80 / 59.97 ~= 0.697
    assert cv["acos_30d"] == pytest.approx(0.697, abs=0.005)
    # New bid scales by 0.30 / 0.697 ~= 0.43; old bid 1.10 -> new ~0.47
    assert s["proposed_value"]["bid"] < 1.10
    assert s["proposed_value"]["bid"] > 0.0
    # Estimated savings = cost - sales*target = 41.80 - 59.97*0.30 = ~23.81
    assert s["estimated_savings"] == pytest.approx(23.81, abs=0.05)


def test_rule_high_acos_does_not_fire_on_healthy_acos(all_suggestions):
    """kw-103 sits at 16% ACOS — must not be flagged as high."""
    types_103 = _types_for_keyword(all_suggestions, "kw-103")
    assert "high_acos" not in types_103


def test_rule_high_acos_does_not_fire_on_zero_sales(all_suggestions):
    """kw-101 has zero sales: must be in spend_no_sales bucket, not high_acos."""
    types_101 = _types_for_keyword(all_suggestions, "kw-101")
    assert "high_acos" not in types_101


# ──────────────────────────────────────────────────────────────────────────
#  Rule 3: bid_too_high
# ──────────────────────────────────────────────────────────────────────────

def test_rule_bid_too_high_fires_on_kw201(all_suggestions):
    """kw-201 bid 2.40 vs ag-2 default 1.20 -> 2.0x ratio."""
    suggs = _by_type(all_suggestions, "bid_too_high")
    matching = [s for s in suggs if s["keyword_id"] == "kw-201"]
    assert len(matching) == 1
    s = matching[0]
    cv = s["current_value"]
    assert cv["bid"]                  == pytest.approx(2.40, abs=0.01)
    assert cv["ad_group_default_bid"] == pytest.approx(1.20, abs=0.01)
    assert cv["ratio"]                == pytest.approx(2.00, abs=0.01)
    # Proposed bid = ad-group default * 1.1 = 1.32
    assert s["proposed_value"]["bid"] == pytest.approx(1.32, abs=0.01)


def test_rule_bid_too_high_does_not_fire_when_ratio_below_threshold(all_suggestions):
    """kw-202 bid 1.05 vs ag-2 default 1.20 -> ratio 0.875, must not fire."""
    types_202 = _types_for_keyword(all_suggestions, "kw-202")
    assert "bid_too_high" not in types_202


def test_rule_bid_too_high_ignores_tiny_bids():
    """A keyword whose bid is below BID_TOO_HIGH_MIN_BID is not flagged."""
    snap = {
        "campaigns":    [{"campaignId": "c"}],
        "ad_groups":    [{"adGroupId": "ag", "campaignId": "c", "defaultBid": 0.10}],
        "keywords":     [{"keywordId": "k", "adGroupId": "ag", "campaignId": "c",
                          "bid": 0.30, "keywordText": "tiny", "matchType": "exact",
                          "state": "ENABLED"}],
        "search_terms": [],
    }
    # 0.30 / 0.10 = 3x ratio, but 0.30 < 0.50 min bid, so must not fire.
    assert _by_type(analyze(snap), "bid_too_high") == []


# ──────────────────────────────────────────────────────────────────────────
#  Rule 4: scale_profitable
# ──────────────────────────────────────────────────────────────────────────

def test_rule_scale_profitable_fires_on_kw202(all_suggestions):
    """kw-202: $149.95 sales / $16.80 cost -> ACOS 11%, only 600 impressions."""
    suggs = _by_type(all_suggestions, "scale_profitable")
    matching = [s for s in suggs if s["keyword_id"] == "kw-202"]
    assert len(matching) == 1
    s = matching[0]
    cv = s["current_value"]
    assert cv["acos_30d"]        == pytest.approx(0.112, abs=0.005)
    assert cv["impressions_30d"] == 600
    # New bid is +20% of current: 1.05 * 1.2 = 1.26
    assert s["proposed_value"]["bid"] == pytest.approx(1.26, abs=0.01)
    # Estimated lift = 20% of $149.95 ~= $29.99
    assert s["estimated_savings"]     == pytest.approx(29.99, abs=0.05)


def test_rule_scale_profitable_does_not_fire_when_impressions_too_high(all_suggestions):
    """kw-301 has 4200 impressions — over headroom cap, must not fire."""
    types_301 = _types_for_keyword(all_suggestions, "kw-301")
    assert "scale_profitable" not in types_301


def test_rule_scale_profitable_does_not_fire_below_min_sales():
    """A profitable keyword with too little sales is below the noise floor."""
    snap = {
        "campaigns":    [{"campaignId": "c"}],
        "ad_groups":    [{"adGroupId": "ag", "campaignId": "c", "defaultBid": 1.0}],
        "keywords":     [{"keywordId": "k", "adGroupId": "ag", "campaignId": "c",
                          "bid": 1.0, "keywordText": "rare-good",
                          "matchType": "exact", "state": "ENABLED"}],
        "search_terms": [{
            "keywordId": "k", "adGroupId": "ag", "campaignId": "c",
            "searchTerm": "rare-good", "matchType": "exact",
            "impressions": 200, "clicks": 4, "cost": 2.00,
            "purchases30d": 1, "sales30d": 30.0,    # below $50 floor
        }],
    }
    assert _by_type(analyze(snap), "scale_profitable") == []


# ──────────────────────────────────────────────────────────────────────────
#  Rule 5: promote_search_term
# ──────────────────────────────────────────────────────────────────────────

def test_rule_promote_search_term_fires_on_organic_dog_treats(all_suggestions):
    """'organic dog treats' has $74 sales over 30d; not yet a keyword."""
    suggs = _by_type(all_suggestions, "promote_search_term")
    matching = [s for s in suggs
                if s["proposed_value"].get("add_keyword") == "organic dog treats"]
    assert len(matching) == 1
    s = matching[0]
    assert s["proposed_value"]["match_type"] == "exact"
    assert s["proposed_value"]["bid"] > 0
    assert s["current_value"]["sales_30d"]     == pytest.approx(74.56, abs=0.01)
    assert s["current_value"]["purchases_30d"] == 8


def test_rule_promote_search_term_skips_search_terms_that_already_match_keyword(all_suggestions):
    """Search term 'hand cream' equals an existing keyword text; must skip."""
    suggs = _by_type(all_suggestions, "promote_search_term")
    promoted_terms = {s["proposed_value"]["add_keyword"].lower() for s in suggs}
    assert "hand cream" not in promoted_terms
    assert "thermal underwear" not in promoted_terms
    assert "dog food" not in promoted_terms


def test_rule_promote_search_term_below_min_sales_floor():
    """Search term with <$50 sales over 30 days must not be promoted."""
    snap = {
        "campaigns":    [{"campaignId": "c"}],
        "ad_groups":    [{"adGroupId": "ag", "campaignId": "c", "defaultBid": 1.0}],
        "keywords":     [],         # no existing keywords
        "search_terms": [{
            "keywordId": None, "adGroupId": "ag", "campaignId": "c",
            "searchTerm": "low-volume term", "matchType": "broad",
            "impressions": 50, "clicks": 5, "cost": 2.0,
            "purchases30d": 1, "sales30d": 20.0,    # below $50
        }],
    }
    assert _by_type(analyze(snap), "promote_search_term") == []


def test_rule_high_acos_high_confidence_when_acos_over_100():
    """ACOS >= 100% (every click loses money) gets high confidence."""
    snap = {
        "campaigns":    [{"campaignId": "c"}],
        "ad_groups":    [{"adGroupId": "ag", "campaignId": "c", "defaultBid": 1.0}],
        "keywords":     [{"keywordId": "k", "adGroupId": "ag", "campaignId": "c",
                          "bid": 1.50, "keywordText": "burning",
                          "matchType": "phrase", "state": "ENABLED"}],
        "search_terms": [{
            "keywordId": "k", "adGroupId": "ag", "campaignId": "c",
            "searchTerm": "burning", "matchType": "phrase",
            "impressions": 1500, "clicks": 30, "cost": 60.00,
            "purchases30d": 1, "sales30d": 25.0,    # ACOS 240%
        }],
    }
    suggs = _by_type(analyze(snap), "high_acos")
    assert len(suggs) == 1
    assert suggs[0]["confidence"] == "high"


def test_rule_high_acos_medium_confidence_in_normal_range():
    """ACOS in the 50-100% band: real waste but not extreme; medium confidence."""
    suggs = analyze(mock_ppc_data.build_snapshot_payload())
    high_acos = [s for s in suggs
                 if s["suggestion_type"] == "high_acos" and s["keyword_id"] == "kw-102"]
    assert len(high_acos) == 1
    assert high_acos[0]["confidence"] == "medium"   # ~70% ACOS


def test_rule_bid_too_high_high_confidence_at_extreme_ratio():
    """Bid ratio >= 2.5x ad-group default = high confidence."""
    snap = {
        "campaigns":    [{"campaignId": "c"}],
        "ad_groups":    [{"adGroupId": "ag", "campaignId": "c", "defaultBid": 1.00}],
        "keywords":     [{"keywordId": "k", "adGroupId": "ag", "campaignId": "c",
                          "bid": 3.00, "keywordText": "extreme",
                          "matchType": "broad", "state": "ENABLED"}],
        "search_terms": [],
    }
    suggs = _by_type(analyze(snap), "bid_too_high")
    assert len(suggs) == 1
    assert suggs[0]["confidence"] == "high"


def test_rule_scale_profitable_high_confidence_with_strong_signal():
    """Low ACOS (<10%) + 5+ purchases earns high confidence."""
    snap = {
        "campaigns":    [{"campaignId": "c"}],
        "ad_groups":    [{"adGroupId": "ag", "campaignId": "c", "defaultBid": 1.0}],
        "keywords":     [{"keywordId": "k", "adGroupId": "ag", "campaignId": "c",
                          "bid": 0.80, "keywordText": "winner",
                          "matchType": "exact", "state": "ENABLED"}],
        "search_terms": [{
            "keywordId": "k", "adGroupId": "ag", "campaignId": "c",
            "searchTerm": "winner", "matchType": "exact",
            "impressions": 500, "clicks": 25, "cost": 12.0,
            "purchases30d": 8, "sales30d": 250.0,    # ACOS 4.8%
        }],
    }
    suggs = _by_type(analyze(snap), "scale_profitable")
    assert len(suggs) == 1
    assert suggs[0]["confidence"] == "high"


def test_rule_promote_search_term_high_confidence_with_strong_sample():
    """4+ purchases AND $100+ sales over 30 days earns high confidence."""
    snap = {
        "campaigns":    [{"campaignId": "c"}],
        "ad_groups":    [{"adGroupId": "ag", "campaignId": "c", "defaultBid": 1.0}],
        "keywords":     [],
        "search_terms": [{
            "keywordId": None, "adGroupId": "ag", "campaignId": "c",
            "searchTerm": "high-conviction term", "matchType": "broad",
            "impressions": 1000, "clicks": 25, "cost": 18.0,
            "purchases30d": 5, "sales30d": 130.0,
        }],
    }
    suggs = _by_type(analyze(snap), "promote_search_term")
    assert len(suggs) == 1
    assert suggs[0]["confidence"] == "high"


def test_rule_promote_search_term_below_min_purchases_floor():
    """High-revenue but single-purchase term is too noisy to promote."""
    snap = {
        "campaigns":    [{"campaignId": "c"}],
        "ad_groups":    [{"adGroupId": "ag", "campaignId": "c", "defaultBid": 1.0}],
        "keywords":     [],
        "search_terms": [{
            "keywordId": None, "adGroupId": "ag", "campaignId": "c",
            "searchTerm": "one-shot whale", "matchType": "broad",
            "impressions": 200, "clicks": 8, "cost": 4.0,
            "purchases30d": 1, "sales30d": 199.0,
        }],
    }
    assert _by_type(analyze(snap), "promote_search_term") == []


# ──────────────────────────────────────────────────────────────────────────
#  End-to-end smoke
# ──────────────────────────────────────────────────────────────────────────

def test_analyze_returns_all_five_rule_types_at_least_once(all_suggestions):
    """The mock dataset is engineered to fire every rule at least once."""
    types = {s["suggestion_type"] for s in all_suggestions}
    assert "spend_no_sales"      in types
    assert "high_acos"           in types
    assert "bid_too_high"        in types
    assert "scale_profitable"    in types
    assert "promote_search_term" in types


def test_money_found_total_sums_estimated_savings(all_suggestions):
    expected = round(sum(s["estimated_savings"] for s in all_suggestions), 2)
    assert money_found_total(all_suggestions) == expected
    assert money_found_total(all_suggestions) > 0


def test_money_found_breakdown_returns_all_canonical_keys(all_suggestions):
    bd = money_found_breakdown(all_suggestions)
    assert set(bd.keys()) == {
        "spend_no_sales",
        "high_acos",
        "bid_too_high",
        "scale_profitable",
        "promote_search_term",
    }
    # Every value is a float; sum equals money_found_total within rounding.
    assert all(isinstance(v, float) for v in bd.values())
    assert round(sum(bd.values()), 2) == money_found_total(all_suggestions)


def test_count_by_type_returns_all_canonical_keys(all_suggestions):
    counts = count_by_type(all_suggestions)
    assert set(counts.keys()) == {
        "spend_no_sales",
        "high_acos",
        "bid_too_high",
        "scale_profitable",
        "promote_search_term",
    }
    assert sum(counts.values()) == len(all_suggestions)


def test_summarize_empty_returns_no_pending_message():
    assert summarize([]) == "No pending suggestions for this account."


def test_summarize_includes_money_count_and_categories(all_suggestions):
    s = summarize(all_suggestions)
    assert "Found $" in s
    assert f"across {len(all_suggestions)} suggestions" in s
    # Every fired rule should be mentioned by its short label.
    counts = count_by_type(all_suggestions)
    if counts["spend_no_sales"]:
        assert "waste" in s
    if counts["high_acos"]:
        assert "high ACOS" in s
    if counts["bid_too_high"]:
        assert "overbid" in s
    if counts["scale_profitable"]:
        assert "scale opportunit" in s
    if counts["promote_search_term"]:
        assert "search term" in s


def test_savings_total_only_includes_waste_cutting_rules(all_suggestions):
    expected = sum(s["estimated_savings"] for s in all_suggestions
                   if s["suggestion_type"] in SAVINGS_RULE_TYPES)
    assert savings_total(all_suggestions) == pytest.approx(expected, abs=0.01)


def test_growth_opportunity_only_includes_growth_rules(all_suggestions):
    expected = sum(s["estimated_savings"] for s in all_suggestions
                   if s["suggestion_type"] in GROWTH_RULE_TYPES)
    assert growth_opportunity_total(all_suggestions) == pytest.approx(expected, abs=0.01)


def test_savings_plus_growth_equal_total(all_suggestions):
    """The two buckets together must reconstruct the headline number, no gaps."""
    total = round(savings_total(all_suggestions) + growth_opportunity_total(all_suggestions), 2)
    assert total == money_found_total(all_suggestions)


def test_savings_growth_buckets_are_disjoint():
    """No suggestion type appears in both buckets."""
    assert set(SAVINGS_RULE_TYPES).isdisjoint(set(GROWTH_RULE_TYPES))


def test_money_found_breakdown_zero_for_unfired_rules():
    """Buckets for rules that did not fire stay at 0.0."""
    snap = {
        "campaigns":    [{"campaignId": "c"}],
        "ad_groups":    [{"adGroupId": "ag", "campaignId": "c", "defaultBid": 1.0}],
        "keywords":     [{"keywordId": "k", "adGroupId": "ag", "campaignId": "c",
                          "bid": 1.0, "keywordText": "fine",
                          "matchType": "exact", "state": "ENABLED"}],
        "search_terms": [{
            "keywordId": "k", "adGroupId": "ag", "campaignId": "c",
            "searchTerm": "fine", "matchType": "exact",
            "impressions": 500, "clicks": 10, "cost": 8.0,
            "purchases30d": 4, "sales30d": 80.0,    # ACOS 10% but $80 < $50? actually >=, fires scale
        }],
    }
    bd = money_found_breakdown(analyze(snap))
    # Most categories should be zero; whichever rules fire are the only
    # ones with non-zero values.
    nonzero = {k: v for k, v in bd.items() if v > 0}
    assert set(nonzero.keys()) <= {"scale_profitable", "promote_search_term"}


def test_analyze_handles_empty_snapshot():
    """No data, no suggestions, no crash."""
    out = analyze({})
    assert out == []


def test_analyze_handles_keywords_with_no_search_term_rows():
    """Keyword exists but the report had no rows for it: silently produce nothing."""
    snap = {
        "campaigns":    [{"campaignId": "c"}],
        "ad_groups":    [{"adGroupId": "ag", "campaignId": "c", "defaultBid": 1.0}],
        "keywords":     [{"keywordId": "ghost", "adGroupId": "ag", "campaignId": "c",
                          "bid": 1.0, "keywordText": "phantom",
                          "matchType": "exact", "state": "ENABLED"}],
        "search_terms": [],
    }
    assert analyze(snap) == []


# ──────────────────────────────────────────────────────────────────────────
#  DB-backed flow (in-memory SQLite, no Postgres)
# ──────────────────────────────────────────────────────────────────────────

import sqlite3
from contextlib import contextmanager

from ppc_suggestions import (
    generate_suggestions,
    list_pending_suggestions,
    _load_latest_snapshots,
    _delete_pending_suggestions,
    _persist_suggestions,
    _atomic_replace_pending,
)
from mock_ppc_data import seed_mock_snapshot


@pytest.fixture
def sqlite_conn():
    """
    In-memory SQLite with the same schema ppc_agent.init_ppc_db creates.
    Re-using the actual DDL is overkill; this fixture is only what the
    suggestion engine touches.
    """
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE amazon_connections (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id     TEXT NOT NULL,
            seller_id       TEXT,
            marketplace_id  TEXT,
            ads_profile_id  TEXT,
            connected_at    REAL,
            last_synced_at  REAL,
            active          INTEGER NOT NULL DEFAULT 1
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
    """)
    yield conn
    conn.close()


@pytest.fixture
def db_ctx(sqlite_conn):
    """A context-manager factory shaped like server._db: yields (cursor, '?')."""
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


def test_load_latest_snapshots_returns_empty_lists_when_no_data(db_ctx):
    out = _load_latest_snapshots(connection_id=42, db_ctx_factory=db_ctx)
    assert out == {dt: [] for dt in (
        "profiles", "campaigns", "ad_groups", "keywords", "search_terms",
    )}


def test_load_latest_snapshots_picks_most_recent_row(db_ctx, sqlite_conn):
    """Two snapshots for the same data_type: only the newer wins."""
    import json as _json
    cur = sqlite_conn.cursor()
    cur.executemany(
        "INSERT INTO ppc_snapshots (connection_id, fetched_at, data_type, data) "
        "VALUES (?, ?, ?, ?)",
        [
            (1, 100.0, "campaigns", _json.dumps([{"campaignId": "old"}])),
            (1, 200.0, "campaigns", _json.dumps([{"campaignId": "new"}])),
        ],
    )
    sqlite_conn.commit()

    out = _load_latest_snapshots(connection_id=1, db_ctx_factory=db_ctx)
    assert out["campaigns"] == [{"campaignId": "new"}]


def test_seed_then_generate_suggestions_writes_rows(db_ctx, sqlite_conn):
    """End-to-end: mock seed -> generate -> ppc_suggestions populated."""
    seed_mock_snapshot(connection_id=7, db_context_manager=db_ctx)

    suggestions = generate_suggestions(
        connection_id=7, db_ctx_factory=db_ctx, replace_pending=True
    )
    assert len(suggestions) >= 5      # at least one per rule

    cur = sqlite_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM ppc_suggestions WHERE connection_id = 7")
    persisted = cur.fetchone()[0]
    assert persisted == len(suggestions)
    assert persisted >= 5


def test_replace_pending_wipes_old_pending_suggestions(db_ctx, sqlite_conn):
    """Re-running generate_suggestions does not duplicate rows."""
    seed_mock_snapshot(connection_id=7, db_context_manager=db_ctx)
    first  = generate_suggestions(7, db_ctx_factory=db_ctx, replace_pending=True)
    second = generate_suggestions(7, db_ctx_factory=db_ctx, replace_pending=True)

    cur = sqlite_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM ppc_suggestions WHERE connection_id = 7 AND status = 'pending'")
    assert cur.fetchone()[0] == len(second) == len(first)


def test_replace_pending_false_accumulates(db_ctx, sqlite_conn):
    """With replace_pending=False, two runs leave both batches in the table."""
    seed_mock_snapshot(connection_id=7, db_context_manager=db_ctx)
    first  = generate_suggestions(7, db_ctx_factory=db_ctx, replace_pending=False)
    second = generate_suggestions(7, db_ctx_factory=db_ctx, replace_pending=False)

    cur = sqlite_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM ppc_suggestions WHERE connection_id = 7")
    assert cur.fetchone()[0] == len(first) + len(second)


def test_replace_pending_does_not_touch_decided_suggestions(db_ctx, sqlite_conn):
    """Approved/rejected rows survive a re-run."""
    import time as _time
    cur = sqlite_conn.cursor()
    cur.execute(
        """
        INSERT INTO ppc_suggestions
          (connection_id, suggestion_type, reason, status, created_at)
        VALUES (7, 'spend_no_sales', 'old approved', 'approved_pending_apply', ?)
        """,
        (_time.time(),),
    )
    sqlite_conn.commit()

    seed_mock_snapshot(connection_id=7, db_context_manager=db_ctx)
    generate_suggestions(7, db_ctx_factory=db_ctx, replace_pending=True)

    cur.execute("SELECT COUNT(*) FROM ppc_suggestions WHERE status = 'approved_pending_apply'")
    assert cur.fetchone()[0] == 1   # the old approved row was preserved


def test_list_pending_suggestions_orders_by_confidence_then_savings(db_ctx, sqlite_conn):
    """High-confidence rows surface first; within a tier, larger savings first."""
    seed_mock_snapshot(connection_id=7, db_context_manager=db_ctx)
    generate_suggestions(7, db_ctx_factory=db_ctx, replace_pending=True)
    rows = list_pending_suggestions(7, db_ctx_factory=db_ctx)

    rank = {"high": 0, "medium": 1, "low": 2}
    pairs = [(rank.get(r["confidence"], 99), -r["estimated_savings"]) for r in rows]
    assert pairs == sorted(pairs)


def test_list_pending_suggestions_deserialises_json(db_ctx, sqlite_conn):
    seed_mock_snapshot(connection_id=7, db_context_manager=db_ctx)
    generate_suggestions(7, db_ctx_factory=db_ctx, replace_pending=True)
    rows = list_pending_suggestions(7, db_ctx_factory=db_ctx)
    assert rows
    for r in rows:
        assert isinstance(r["current_value"], dict)
        assert isinstance(r["proposed_value"], dict)


def test_persist_suggestions_returns_inserted_count(db_ctx):
    fake = [
        {
            "suggestion_type":  "spend_no_sales",
            "campaign_id":      "c", "ad_group_id": "ag", "keyword_id": "k",
            "current_value":    {"a": 1}, "proposed_value": {"b": 2},
            "reason":           "test", "estimated_savings": 1.23,
            "confidence":       "high",
        },
    ]
    inserted = _persist_suggestions(99, fake, db_ctx)
    assert inserted == 1


def test_analyze_handles_account_with_thousand_keywords():
    """
    Stress: 1000 keywords + ~5000 search-term rows. Verify the engine returns
    in a reasonable amount of time and produces sane output. Real Amazon FBA
    accounts at the upper Starter / Growth tier are in this range.
    """
    import time as _time
    n_kws = 1000
    keywords = []
    for i in range(n_kws):
        keywords.append({
            "keywordId":   f"kw-{i}",
            "adGroupId":   f"ag-{i % 50}",
            "campaignId":  f"cmp-{i % 10}",
            "keywordText": f"keyword text {i}",
            "matchType":   ["broad", "phrase", "exact"][i % 3],
            "bid":         0.50 + (i % 5) * 0.30,
            "state":       "ENABLED",
        })

    ad_groups = [
        {"adGroupId": f"ag-{j}", "campaignId": f"cmp-{j % 10}",
         "name": f"AG {j}", "defaultBid": 0.80, "state": "ENABLED"}
        for j in range(50)
    ]

    search_terms = []
    # 5 search-term rows per keyword to simulate the 30-day report shape.
    for i in range(n_kws):
        for k in range(5):
            search_terms.append({
                "campaignId":   f"cmp-{i % 10}",
                "adGroupId":    f"ag-{i % 50}",
                "keywordId":    f"kw-{i}",
                "keywordText":  f"keyword text {i}",
                "matchType":    ["broad", "phrase", "exact"][i % 3],
                "searchTerm":   f"st {i} variant {k}",
                "impressions":  100 + (i + k) * 3,
                "clicks":       (i + k) % 7,
                "cost":         ((i + k) % 7) * 0.40,
                "purchases1d":  0,
                "purchases7d":  (i + k) % 3,
                "purchases14d": (i + k) % 3,
                "purchases30d": (i + k) % 3,
                "sales1d":      0.0, "sales7d": 0.0, "sales14d": 0.0,
                "sales30d":     ((i + k) % 3) * 25.0,
            })

    snap = {
        "profiles":     [],
        "campaigns":    [{"campaignId": f"cmp-{j}", "name": f"C {j}"} for j in range(10)],
        "ad_groups":    ad_groups,
        "keywords":     keywords,
        "search_terms": search_terms,
    }

    started = _time.perf_counter()
    out = analyze(snap)
    elapsed = _time.perf_counter() - started

    # 1k keywords + 5k search-terms should finish in well under a second on a
    # laptop. Bumping the cap to 5s gives plenty of headroom for slow CI.
    assert elapsed < 5.0, f"analyze took {elapsed:.2f}s, too slow"
    assert isinstance(out, list)
    # Sanity: at least some rules fire on a realistic random distribution.
    assert len(out) > 0


def test_atomic_replace_rolls_back_on_insert_failure(db_ctx, sqlite_conn):
    """
    Atomicity guarantee: a failed INSERT after the DELETE rolls back, leaving
    the original pending list intact rather than wiping it to empty.
    """
    import time as _time
    cur = sqlite_conn.cursor()
    cur.execute(
        """
        INSERT INTO ppc_suggestions
          (connection_id, suggestion_type, reason, status, created_at)
        VALUES (7, 'spend_no_sales', 'original', 'pending', ?)
        """,
        (_time.time(),),
    )
    sqlite_conn.commit()

    # suggestion_type = None violates the NOT NULL constraint, so the second
    # row's INSERT raises after the first has already inserted; the whole
    # transaction must roll back to leave the original 'pending' row intact.
    malformed = [
        {"suggestion_type": "spend_no_sales", "reason": "ok",
         "campaign_id": "c", "ad_group_id": "ag", "keyword_id": "k",
         "current_value": {}, "proposed_value": {},
         "estimated_savings": 1.0, "confidence": "high"},
        {"suggestion_type": None, "reason": "broken",
         "campaign_id": "c", "ad_group_id": "ag", "keyword_id": "k",
         "current_value": {}, "proposed_value": {},
         "estimated_savings": 1.0, "confidence": "high"},
    ]

    with pytest.raises(Exception):
        _atomic_replace_pending(7, malformed, db_ctx)

    cur.execute(
        "SELECT reason FROM ppc_suggestions WHERE connection_id = 7 AND status = 'pending'"
    )
    rows = cur.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "original"


def test_load_latest_snapshots_handles_malformed_json(db_ctx, sqlite_conn):
    """A garbage payload is logged and treated as empty list, never crashes."""
    cur = sqlite_conn.cursor()
    cur.execute(
        "INSERT INTO ppc_snapshots (connection_id, fetched_at, data_type, data) "
        "VALUES (?, ?, ?, ?)",
        (1, 100.0, "campaigns", "{not-valid-json"),
    )
    sqlite_conn.commit()

    out = _load_latest_snapshots(connection_id=1, db_ctx_factory=db_ctx)
    assert out["campaigns"] == []


def test_analyze_handles_unicode_in_keyword_text():
    """Keywords with non-ASCII text don't break formatting / serialization."""
    snap = {
        "campaigns":    [{"campaignId": "c"}],
        "ad_groups":    [{"adGroupId": "ag", "campaignId": "c", "defaultBid": 1.0}],
        "keywords":     [{"keywordId": "k", "adGroupId": "ag", "campaignId": "c",
                          "bid": 1.0,
                          "keywordText": "natürliches öl für haut",
                          "matchType": "broad", "state": "ENABLED"}],
        "search_terms": [{
            "keywordId": "k", "adGroupId": "ag", "campaignId": "c",
            "searchTerm": "natürliches öl für haut", "matchType": "broad",
            "impressions": 1500, "clicks": 25, "cost": 30.00,
            "purchases30d": 0, "sales30d": 0.0,
        }],
    }
    suggs = analyze(snap)
    waste = _by_type(suggs, "spend_no_sales")
    assert len(waste) == 1
    assert "natürliches öl für haut" in waste[0]["reason"]


def test_delete_pending_only_deletes_pending(db_ctx, sqlite_conn):
    """The DELETE is filtered by status='pending'."""
    import time as _time
    cur = sqlite_conn.cursor()
    cur.executemany(
        "INSERT INTO ppc_suggestions "
        "(connection_id, suggestion_type, reason, status, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (5, "spend_no_sales", "p1", "pending",                _time.time()),
            (5, "high_acos",       "p2", "pending",                _time.time()),
            (5, "bid_too_high",    "p3", "approved_pending_apply", _time.time()),
        ],
    )
    sqlite_conn.commit()

    deleted = _delete_pending_suggestions(5, db_ctx)
    assert deleted == 2

    cur.execute("SELECT status FROM ppc_suggestions WHERE connection_id = 5")
    remaining = [row[0] for row in cur.fetchall()]
    assert remaining == ["approved_pending_apply"]


# ──────────────────────────────────────────────────────────────────────────
#  Smart Recommendation Card (cycle-16 / Task 1)
# ──────────────────────────────────────────────────────────────────────────

from ppc_suggestions import (   # noqa: E402  - intentional late import
    _evidence_multiplier,
    _sales_risk_multiplier,
    _action_multiplier,
    _risk_label,
    build_card_view,
    build_card_views,
    DEFAULT_TARGET_ACOS,
    DEFAULT_MEMORY_HINT_NEUTRAL,
    QUEUED_STATUS_NOTE,
)


# Evidence multiplier bands (clicks, spend) -> mult.

@pytest.mark.parametrize(
    "clicks,spend,expected",
    [
        (40,  75.0, 0.75),    # top band
        (50, 100.0, 0.75),    # well above top
        (25,  50.0, 0.65),    # mid band
        (39,  74.99, 0.65),   # just below top floor stays in mid
        (15,  25.0, 0.50),    # low band
        (24,  49.99, 0.50),   # below mid floor -> low
        (14,  25.0, 0.0),     # too few clicks
        (15,  24.99, 0.0),    # too little spend
        (0,    0.0, 0.0),     # no signal
    ],
)
def test_evidence_multiplier_bands(clicks, spend, expected):
    assert _evidence_multiplier(clicks, spend) == pytest.approx(expected)


# Sales-risk multiplier (orders, sales, spend, target) -> mult.

def test_sales_risk_multiplier_pure_waste_returns_one():
    """0 orders + 0 sales is the cleanest waste signal."""
    assert _sales_risk_multiplier(0, 0.0, 50.0, 0.30) == pytest.approx(1.00)


def test_sales_risk_multiplier_severe_bleed_returns_075():
    """ACOS at >= 2x target."""
    # spend $90, sales $100, target 30% -> ACOS 90% which is >= 60%
    assert _sales_risk_multiplier(2, 100.0, 90.0, 0.30) == pytest.approx(0.75)


def test_sales_risk_multiplier_moderate_bleed_returns_050():
    """ACOS at >= 1.5x target but below 2x."""
    # spend $50, sales $100, target 30% -> ACOS 50% (>= 45%, < 60%)
    assert _sales_risk_multiplier(2, 100.0, 50.0, 0.30) == pytest.approx(0.50)


def test_sales_risk_multiplier_healthy_returns_zero():
    """ACOS at or below target -> rule should not have fired in waste-shape."""
    # spend $20, sales $100, target 30% -> ACOS 20%
    assert _sales_risk_multiplier(5, 100.0, 20.0, 0.30) == pytest.approx(0.0)


# Action multiplier per rule type.

def test_action_multiplier_pause_is_full_credit():
    assert _action_multiplier("spend_no_sales") == pytest.approx(1.00)


def test_action_multiplier_bid_down_is_partial():
    assert _action_multiplier("high_acos") == pytest.approx(0.85)
    assert _action_multiplier("bid_too_high") == pytest.approx(0.85)


def test_action_multiplier_growth_is_smaller():
    assert _action_multiplier("scale_profitable") == pytest.approx(0.60)
    assert _action_multiplier("promote_search_term") == pytest.approx(0.60)


def test_action_multiplier_unknown_is_zero():
    assert _action_multiplier("unknown_rule") == pytest.approx(0.0)


# Risk label.

def test_risk_label_high_when_combined_zero():
    """Zero evidence + any action = HIGH RISK regardless of type."""
    assert _risk_label("spend_no_sales", 0.0, 1.0, 1.0, "high") == "HIGH RISK"
    assert _risk_label("high_acos",      0.0, 1.0, 0.85, "high") == "HIGH RISK"
    assert _risk_label("scale_profitable", 0.0, 0.0, 0.60, "high") == "HIGH RISK"


def test_risk_label_pause_with_signal_is_low():
    assert _risk_label("spend_no_sales", 0.75, 1.00, 1.00, "high") == "LOW RISK"
    assert _risk_label("spend_no_sales", 0.50, 1.00, 1.00, "medium") == "LOW RISK"


def test_risk_label_high_acos_with_signal_is_medium():
    assert _risk_label("high_acos", 0.75, 0.75, 0.85, "high") == "MEDIUM RISK"


def test_risk_label_bid_too_high_high_confidence_is_low():
    assert _risk_label("bid_too_high", 0.75, 1.00, 0.85, "high") == "LOW RISK"


def test_risk_label_bid_too_high_medium_confidence_is_medium():
    assert _risk_label("bid_too_high", 0.65, 1.00, 0.85, "medium") == "MEDIUM RISK"


def test_risk_label_growth_caps_at_medium():
    """Growth bets are inherently uncertain even with strong signal."""
    assert _risk_label("scale_profitable", 0.75, 1.00, 0.60, "high") == "MEDIUM RISK"
    assert _risk_label("promote_search_term", 0.75, 1.00, 0.60, "high") == "MEDIUM RISK"


# build_card_view shape.

def _make_spend_no_sales_suggestion(cost=80.0, clicks=50, kw="blue ceramic coffee mug"):
    return {
        "id": 1,
        "suggestion_type": "spend_no_sales",
        "campaign_id": "cmp-1",
        "ad_group_id": "ag-1",
        "keyword_id": "kw-101",
        "current_value": {
            "keyword_text": kw,
            "state": "ENABLED",
            "bid": 0.95,
            "cost_30d": cost,
            "clicks_30d": clicks,
            "purchases_30d": 0,
            "sales_30d": 0.0,
        },
        "proposed_value": {"state": "PAUSED"},
        "reason": f"Keyword '{kw}' burned cash with no sales.",
        "estimated_savings": cost,
        "confidence": "high",
    }


def test_build_card_view_returns_required_card_fields():
    """Card view includes every field the partial expects."""
    s = _make_spend_no_sales_suggestion()
    cv = build_card_view(s)
    required = {
        "id", "suggestion_type", "type_label", "status", "confidence",
        "is_lift", "risk_label", "headline", "financial_impact_text",
        "estimated_impact", "why_this_matters", "memory_hint",
        "recommended_action_lines", "reject_hint", "queued_status_note",
        "learn_more",
    }
    assert required.issubset(cv.keys())
    assert isinstance(cv["recommended_action_lines"], list)
    assert isinstance(cv["learn_more"], dict)


def test_build_card_view_waste_cleanup_uses_formula():
    """For waste cleanup with 0 sales, observed_waste = full spend; the
    headline applies evidence × sales-risk × action multipliers."""
    s = _make_spend_no_sales_suggestion(cost=166.0, clicks=83)
    cv = build_card_view(s)
    # 83 clicks, $166 spend -> evidence_multiplier = 0.75 (top band).
    # 0 orders, 0 sales -> sales_risk_multiplier = 1.00.
    # spend_no_sales -> action_multiplier = 1.00.
    # Estimated impact = 166 × 0.75 × 1.00 × 1.00 = 124.50.
    assert cv["risk_label"] == "LOW RISK"
    assert cv["type_label"] == "Waste cleanup"
    assert cv["estimated_impact"] == pytest.approx(124.5, abs=0.01)
    assert "~$124/month" in cv["financial_impact_text"] or "~$125/month" in cv["financial_impact_text"]
    lm = cv["learn_more"]
    assert lm["evidence_multiplier"] == pytest.approx(0.75)
    assert lm["sales_risk_multiplier"] == pytest.approx(1.00)
    assert lm["action_multiplier"] == pytest.approx(1.00)
    assert lm["target_acos_label"] == "30% default"
    assert "× 0.75" in lm["estimated_impact_formula"]


def test_build_card_view_thin_evidence_says_too_thin():
    """Below the lowest evidence band -> 'Impact too thin to estimate'."""
    s = _make_spend_no_sales_suggestion(cost=10.0, clicks=8)
    cv = build_card_view(s)
    assert cv["estimated_impact"] == pytest.approx(0.0)
    assert "too thin" in cv["financial_impact_text"].lower()
    assert cv["risk_label"] == "HIGH RISK"


def test_build_card_view_default_target_acos_30_percent():
    s = _make_spend_no_sales_suggestion()
    cv = build_card_view(s)
    assert cv["learn_more"]["target_acos_used"] == pytest.approx(0.30)
    assert cv["learn_more"]["target_acos_label"] == "30% default"


def test_build_card_view_seller_target_acos_override():
    s = _make_spend_no_sales_suggestion()
    cv = build_card_view(s, target_acos=0.25)
    assert cv["learn_more"]["target_acos_used"] == pytest.approx(0.25)
    assert "25%" in cv["learn_more"]["target_acos_label"]
    assert "your setting" in cv["learn_more"]["target_acos_label"]


def test_build_card_view_neutral_memory_hint_default():
    s = _make_spend_no_sales_suggestion()
    cv = build_card_view(s)
    assert cv["memory_hint"] == DEFAULT_MEMORY_HINT_NEUTRAL
    assert "No similar rejection found" in cv["memory_hint"]


def test_build_card_view_memory_hint_override():
    s = _make_spend_no_sales_suggestion()
    cv = build_card_view(
        s,
        memory_hint="Skipped because you rejected this on May 1.",
    )
    assert "Skipped because you rejected this on May 1." == cv["memory_hint"]


def test_build_card_view_queued_status_note_is_present():
    """Approve must always be qualified by 'does not send changes to Amazon'."""
    s = _make_spend_no_sales_suggestion()
    cv = build_card_view(s)
    assert cv["queued_status_note"] == QUEUED_STATUS_NOTE
    assert "does not send changes to Amazon yet" in cv["queued_status_note"]


def test_build_card_view_recommended_actions_for_waste():
    s = _make_spend_no_sales_suggestion(kw="blue ceramic coffee mug")
    cv = build_card_view(s)
    actions = cv["recommended_action_lines"]
    assert any("blue ceramic coffee mug" in line for line in actions)
    assert any("negative exact" in line.lower() for line in actions)


def test_build_card_view_reject_hint_per_type():
    """Each rule type has a deterministic 'why you might reject' line."""
    for stype in ("spend_no_sales", "high_acos", "bid_too_high",
                  "scale_profitable", "promote_search_term"):
        s = _make_spend_no_sales_suggestion()
        s["suggestion_type"] = stype
        cv = build_card_view(s)
        assert cv["reject_hint"], f"{stype} missing reject_hint"
        assert cv["reject_hint"].startswith("Reject if")


def test_build_card_view_anti_overclaim_no_past_tense_savings():
    """Card copy must never claim past-tense realised savings."""
    s = _make_spend_no_sales_suggestion()
    cv = build_card_view(s)
    blob = " ".join([
        cv["headline"],
        cv["financial_impact_text"],
        cv["why_this_matters"],
        cv["queued_status_note"],
    ] + cv["recommended_action_lines"])
    blob_lc = blob.lower()
    assert "you saved" not in blob_lc
    assert "we saved" not in blob_lc
    assert "saved you" not in blob_lc
    assert "guaranteed" not in blob_lc


def test_build_card_view_growth_rule_uses_lift_framing():
    """Growth rules must show '+/projected lift' framing, not savings."""
    s = {
        "id": 9,
        "suggestion_type": "promote_search_term",
        "campaign_id": "cmp-1",
        "ad_group_id": "ag-1",
        "keyword_id": None,
        "current_value": {
            "search_term": "organic dog treats",
            "matched_keyword_id": "kw-200",
            "sales_30d": 200.0,
            "purchases_30d": 8,
            "cost_30d": 60.0,
            "clicks_30d": 35,
            "implied_cpc": 1.71,
        },
        "proposed_value": {
            "add_keyword": "organic dog treats",
            "match_type": "exact",
            "bid": 1.80,
        },
        "reason": "demo",
        "estimated_savings": 30.0,
        "confidence": "high",
    }
    cv = build_card_view(s)
    assert cv["is_lift"] is True
    assert "projected lift" in cv["financial_impact_text"]
    # 35 clicks + $60 spend = mid evidence band (0.65). Action mult 0.60.
    # Combined = 0.65 * 0.60 = 0.39 > 0 -> MEDIUM RISK by growth-rule logic.
    assert cv["risk_label"] == "MEDIUM RISK"


def test_build_card_views_preserves_order():
    snaps = mock_ppc_data.build_snapshot_payload()
    suggs = analyze(snaps)
    cards = build_card_views(suggs)
    assert len(cards) == len(suggs)
    for s, c in zip(suggs, cards):
        assert s["suggestion_type"] == c["suggestion_type"]


def test_build_card_view_does_not_mutate_input():
    s = _make_spend_no_sales_suggestion()
    snapshot_before = dict(s)
    cv_before = dict(s["current_value"])
    build_card_view(s)
    assert s == snapshot_before
    assert s["current_value"] == cv_before


# ──────────────────────────────────────────────────────────────────────────
#  Top-N composite ranker (cycle-17 / Task 2)
# ──────────────────────────────────────────────────────────────────────────

from ppc_suggestions import (   # noqa: E402  - intentional late import
    _impact_score,
    _confidence_score,
    _actionability_score,
    _risk_score,
    _memory_score,
    composite_score,
    rank_recommendations,
    TOP_N_DEFAULT,
    FIRST_VIEW_MIN_IMPACT_USD,
    MEMORY_SCORE_DEFAULT,
)


# Component scores ────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "estimated_impact,expected",
    [
        (0,        0.0),
        (5.0,      1.0),
        (50.0,    10.0),
        (250.0,   50.0),
        (500.0,  100.0),
        (501.0,  100.0),     # capped
        (10000.0, 100.0),    # capped
        (-25.0,    0.0),     # negative clamped to 0
    ],
)
def test_impact_score_curve(estimated_impact, expected):
    assert _impact_score(estimated_impact) == pytest.approx(expected)


@pytest.mark.parametrize(
    "evidence_multiplier,expected",
    [
        (0.75, 100.0),
        (0.65,  70.0),
        (0.50,  40.0),
        (0.0,    0.0),
        (0.99,   0.0),    # not a known band
        (0.10,   0.0),
    ],
)
def test_confidence_score_bands(evidence_multiplier, expected):
    assert _confidence_score(evidence_multiplier) == pytest.approx(expected)


@pytest.mark.parametrize(
    "stype,expected",
    [
        ("spend_no_sales",      100.0),
        ("high_acos",            80.0),
        ("bid_too_high",         80.0),
        ("scale_profitable",     60.0),
        ("promote_search_term",  60.0),
        ("unknown",               0.0),
    ],
)
def test_actionability_score_per_type(stype, expected):
    assert _actionability_score(stype) == pytest.approx(expected)


@pytest.mark.parametrize(
    "label,expected",
    [
        ("LOW RISK",    100.0),
        ("MEDIUM RISK",  70.0),
        ("HIGH RISK",    40.0),
        ("",              0.0),
    ],
)
def test_risk_score_per_label(label, expected):
    assert _risk_score(label) == pytest.approx(expected)


def test_memory_score_default_constant_until_task3():
    """Real seller memory ships in Task 3. Until then, score is constant."""
    assert _memory_score() == pytest.approx(MEMORY_SCORE_DEFAULT)
    assert _memory_score() == pytest.approx(50.0)
    # Override path is wired but unused by build_card_view today.
    assert _memory_score(80.0) == pytest.approx(80.0)


# Composite score ─────────────────────────────────────────────────────────

def _make_card(stype="spend_no_sales", impact=125.0, evidence_mult=0.75,
               risk="LOW RISK", cid=1):
    """Minimal card-view shape that composite_score / ranker need."""
    return {
        "id": cid,
        "suggestion_type": stype,
        "estimated_impact": impact,
        "risk_label": risk,
        "learn_more": {"evidence_multiplier": evidence_mult},
    }


def test_composite_score_worked_example():
    """
    Worked example from the founder's brief:
      $125 monthly impact, evidence 0.75, spend_no_sales, LOW RISK
      impact = min(100, 125/5) = 25
      confidence = 100
      actionability = 100
      risk = 100
      memory = 50
      score = 25*.40 + 100*.25 + 100*.15 + 100*.10 + 50*.10
            = 10 + 25 + 15 + 10 + 5
            = 65.0
    """
    card = _make_card(impact=125.0)
    s = composite_score(card)
    assert s["impact_score"] == pytest.approx(25.0)
    assert s["confidence_score"] == pytest.approx(100.0)
    assert s["actionability_score"] == pytest.approx(100.0)
    assert s["risk_score"] == pytest.approx(100.0)
    assert s["memory_score"] == pytest.approx(50.0)
    assert s["score"] == pytest.approx(65.0)


def test_composite_score_zero_when_signal_zero():
    """
    Card with no evidence multiplier and HIGH RISK and 0 impact:
      impact=0, confidence=0, action=0, risk=40, memory=50
      score = 0 + 0 + 0 + 4 + 5 = 9.0
    """
    card = _make_card(stype="unknown_type", impact=0.0,
                      evidence_mult=0.0, risk="HIGH RISK")
    s = composite_score(card)
    assert s["score"] == pytest.approx(9.0)


def test_composite_score_does_not_mutate_card():
    card = _make_card()
    before = dict(card)
    before_lm = dict(card["learn_more"])
    composite_score(card)
    assert card == before
    assert card["learn_more"] == before_lm


# rank_recommendations: filters, ordering, overflow ─────────────────────────

def test_rank_recommendations_empty_returns_empty():
    out = rank_recommendations([])
    assert out == {"top": [], "hidden": [], "extra_count": 0}


def test_rank_recommendations_hard_filter_min_impact():
    """Cards under $50/month MUST NOT make the first view."""
    cards = [
        _make_card(cid=1, impact=49.99),       # below threshold
        _make_card(cid=2, impact=50.00),       # exactly at threshold (passes)
        _make_card(cid=3, impact=200.0),       # well above
    ]
    out = rank_recommendations(cards)
    top_ids = [c["id"] for c in out["top"]]
    assert 1 not in top_ids
    assert 2 in top_ids
    assert 3 in top_ids


def test_rank_recommendations_hard_filter_confidence_zero_excluded():
    """confidence_score == 0 (no evidence band hit) MUST NOT make the first view."""
    cards = [
        _make_card(cid=1, impact=200.0, evidence_mult=0.0),   # confidence 0
        _make_card(cid=2, impact=80.0,  evidence_mult=0.50),  # confidence 40
    ]
    out = rank_recommendations(cards)
    top_ids = [c["id"] for c in out["top"]]
    assert top_ids == [2]
    # The filter-failed card lands in hidden, not deleted.
    assert any(c["id"] == 1 for c in out["hidden"])


def test_rank_recommendations_top_n_default_is_five():
    """Default cap is 5. Anything beyond goes to hidden."""
    cards = [
        _make_card(cid=i, impact=100.0 + i * 5, evidence_mult=0.75)
        for i in range(1, 9)
    ]
    out = rank_recommendations(cards)
    assert len(out["top"]) == 5
    assert len(out["hidden"]) == 3
    assert out["extra_count"] == 3


def test_rank_recommendations_respects_explicit_limit():
    cards = [
        _make_card(cid=i, impact=100.0 + i, evidence_mult=0.75)
        for i in range(1, 6)
    ]
    out = rank_recommendations(cards, limit=3)
    assert len(out["top"]) == 3
    assert len(out["hidden"]) == 2


def test_rank_recommendations_one_strong_returns_one():
    """3-5 is a target / maximum, never a quota."""
    cards = [
        _make_card(cid=1, impact=300.0, evidence_mult=0.75),    # passes
        _make_card(cid=2, impact=10.0,  evidence_mult=0.75),    # below $50
        _make_card(cid=3, impact=80.0,  evidence_mult=0.0),     # confidence 0
    ]
    out = rank_recommendations(cards)
    assert [c["id"] for c in out["top"]] == [1]
    assert out["extra_count"] == 2


def test_rank_recommendations_orders_by_score_desc():
    """Higher composite score must appear earlier in `top`."""
    # Tweak only the actionability so the score order is predictable.
    high = _make_card(cid=10, stype="spend_no_sales", impact=200.0)   # action 100
    low  = _make_card(cid=20, stype="scale_profitable", impact=200.0,
                      risk="MEDIUM RISK")                              # action 60, risk 70
    out = rank_recommendations([low, high])
    assert [c["id"] for c in out["top"]] == [10, 20]


def test_rank_recommendations_tie_break_by_estimated_impact_then_id():
    """
    Same composite score should tie-break by estimated_impact DESC, then
    by id ASC. Construct two cards with identical scores to verify.
    """
    a = _make_card(cid=99, impact=200.0)
    b = _make_card(cid=11, impact=200.0)
    c = _make_card(cid=22, impact=200.0)
    out = rank_recommendations([a, b, c])
    # All three identical except id; tie-break ascending id.
    assert [x["id"] for x in out["top"]] == [11, 22, 99]


def test_rank_recommendations_tie_break_estimated_impact_first():
    """Same score AND same impact: id ASC. Bigger impact wins first."""
    a = _make_card(cid=1, impact=200.0)
    b = _make_card(cid=2, impact=400.0)   # larger impact, but impact_score
                                          # is capped at 100 so composite
                                          # score is identical to a.
    out = rank_recommendations([a, b])
    assert out["top"][0]["id"] == 2     # tie-broken on raw estimated_impact
    assert out["top"][1]["id"] == 1


def test_rank_recommendations_handles_missing_id():
    """Cards without an id (CSV preview path) sort last among equals."""
    a = _make_card(cid=None, impact=200.0)
    b = _make_card(cid=5,    impact=200.0)
    out = rank_recommendations([a, b])
    # Same score and impact; integer id beats None id.
    assert out["top"][0]["id"] == 5


def test_rank_recommendations_hidden_sorted_too():
    """Hidden bucket is sorted the same way so 'Show N more' reads sensibly."""
    cards = [
        _make_card(cid=1, impact=600.0,  evidence_mult=0.75),    # passes
        _make_card(cid=2, impact=400.0,  evidence_mult=0.75),
        _make_card(cid=3, impact=200.0,  evidence_mult=0.75),
        _make_card(cid=4, impact=100.0,  evidence_mult=0.75),
        _make_card(cid=5, impact=80.0,   evidence_mult=0.75),
        _make_card(cid=6, impact=70.0,   evidence_mult=0.75),    # 6th -> hidden
        _make_card(cid=7, impact=49.0,   evidence_mult=0.75),    # below filter
        _make_card(cid=8, impact=200.0,  evidence_mult=0.0),     # filter fail
    ]
    out = rank_recommendations(cards)
    assert len(out["top"]) == 5
    # Hidden list still in score-desc order (6 comes before 7 comes before 8).
    hidden_ids = [c["id"] for c in out["hidden"]]
    # 6: score uses impact_score 14, conf 100 = above 7 (score impact 9.8)
    # 8: confidence_score = 0, low score; sits at the bottom.
    assert hidden_ids[0] == 6
    assert hidden_ids[-1] == 8


def test_rank_recommendations_attaches_score_to_returned_cards():
    cards = [_make_card(cid=1, impact=200.0)]
    out = rank_recommendations(cards)
    assert "score" in out["top"][0]
    s = out["top"][0]["score"]
    assert "score" in s
    assert "impact_score" in s
    assert "confidence_score" in s
    assert "actionability_score" in s
    assert "risk_score" in s
    assert "memory_score" in s


def test_rank_recommendations_does_not_mutate_input():
    cards = [_make_card(cid=1, impact=200.0)]
    snapshot = [dict(c) for c in cards]
    snapshot_lm = [dict(c["learn_more"]) for c in cards]
    rank_recommendations(cards)
    assert cards == snapshot
    for c, lm_before in zip(cards, snapshot_lm):
        assert c["learn_more"] == lm_before
        # No score key was added to the input list.
        assert "score" not in c


def test_top_n_default_constant_is_five():
    """Brief constraint: 3-5 is a target/maximum. Default is 5."""
    assert TOP_N_DEFAULT == 5


def test_first_view_min_impact_constant_is_50():
    """Brief constraint: hard filter at $50/month."""
    assert FIRST_VIEW_MIN_IMPACT_USD == pytest.approx(50.0)


def test_rank_recommendations_real_engine_output():
    """
    End-to-end: take real engine output, rank it, confirm the contract.
    Mock data is small so most cards land in `hidden`; this is the
    correct conservative posture per Task 1's evidence formula.
    """
    snaps = mock_ppc_data.build_snapshot_payload()
    suggs = analyze(snaps)
    cards = build_card_views(suggs)
    out = rank_recommendations(cards)
    # Sum of top + hidden equals total card count.
    assert len(out["top"]) + len(out["hidden"]) == len(cards)
    assert out["extra_count"] == len(out["hidden"])
    # No card in `top` violates the filters.
    for c in out["top"]:
        assert c["estimated_impact"] >= FIRST_VIEW_MIN_IMPACT_USD
        assert c["score"]["confidence_score"] > 0


# ──────────────────────────────────────────────────────────────────────────
#  Minimal seller memory (cycle-18 / Task 3)
# ──────────────────────────────────────────────────────────────────────────

import time as _time         # noqa: E402  - intentional late import
import json as _json         # noqa: E402

from ppc_suggestions import (   # noqa: E402  - intentional late import
    REJECT_MEMORY_WINDOW_DAYS,
    MEMORY_SCORE_RESURFACED,
    MATERIAL_CHANGE_IMPACT_RATIO,
    MATERIAL_CHANGE_SPEND_RATIO,
    MATERIAL_CHANGE_ACOS_DELTA,
    _suggestion_signature,
    _is_material_change,
    _apply_memory_filter,
    _load_recent_rejections,
    list_memory_skipped,
    generate_suggestions as _generate_suggestions_real,
)


# Signature ───────────────────────────────────────────────────────────────

def test_suggestion_signature_is_stable_for_same_inputs():
    s = _make_spend_no_sales_suggestion()
    assert _suggestion_signature(s) == _suggestion_signature(s)


def test_suggestion_signature_keyword_level_uses_keyword_id():
    """Keyword-level rules: (suggestion_type, keyword_id)."""
    s1 = _make_spend_no_sales_suggestion()
    s1["keyword_id"] = "kw-aaa"
    s2 = _make_spend_no_sales_suggestion()
    s2["keyword_id"] = "kw-aaa"
    s3 = _make_spend_no_sales_suggestion()
    s3["keyword_id"] = "kw-bbb"
    assert _suggestion_signature(s1) == _suggestion_signature(s2)
    assert _suggestion_signature(s1) != _suggestion_signature(s3)


def test_suggestion_signature_differs_across_rule_types():
    a = _make_spend_no_sales_suggestion()
    b = dict(a); b["suggestion_type"] = "high_acos"
    assert _suggestion_signature(a) != _suggestion_signature(b)


def test_suggestion_signature_promote_search_term_normalises_text():
    """promote_search_term: (stype, ad_group_id, normalised search term)."""
    base = {
        "suggestion_type":  "promote_search_term",
        "ad_group_id":      "ag-1",
        "keyword_id":       None,
        "current_value": {
            "search_term": "  Organic Dog Treats  ",
        },
        "proposed_value": {
            "add_keyword": "organic dog treats",
            "match_type":  "exact",
            "bid":         1.85,
        },
    }
    other = dict(base)
    other_cv = dict(base["current_value"])
    other_cv["search_term"] = "organic dog treats"   # already lowercased
    other["current_value"] = other_cv
    assert _suggestion_signature(base) == _suggestion_signature(other)

    # Different ad-group -> different signature.
    different_ag = dict(base)
    different_ag["ad_group_id"] = "ag-2"
    assert _suggestion_signature(base) != _suggestion_signature(different_ag)


def test_suggestion_signature_falls_back_to_text_when_no_keyword_id():
    s = {
        "suggestion_type": "high_acos",
        "ad_group_id":     "ag-9",
        "keyword_id":      None,
        "current_value":   {"keyword_text": "blue ceramic coffee mug"},
    }
    sig = _suggestion_signature(s)
    assert sig[0] == "high_acos"
    assert sig[1] == "ag-9"
    assert "blue ceramic coffee mug" in sig[2]


# Material-change rule ───────────────────────────────────────────────────

def _rejected_row(estimated_savings=100.0, cost=100.0, sales=0.0):
    return {
        "suggestion_type":   "spend_no_sales",
        "campaign_id":       "cmp-1",
        "ad_group_id":       "ag-1",
        "keyword_id":        "kw-aaa",
        "current_value":     {"keyword_text": "demo kw",
                              "cost_30d": cost,
                              "sales_30d": sales,
                              "purchases_30d": 0,
                              "clicks_30d": 50},
        "proposed_value":    {"state": "PAUSED"},
        "estimated_savings": estimated_savings,
        "decided_at":        1000.0,
    }


def test_material_change_impact_threshold_is_50_percent():
    new = _make_spend_no_sales_suggestion(cost=100.0, clicks=50)
    new["estimated_savings"] = 150.0
    rejected = _rejected_row(estimated_savings=100.0)
    changed, reason = _is_material_change(new, rejected)
    assert changed
    assert "estimated impact rose" in reason


def test_material_change_impact_below_threshold_does_not_trigger():
    new = _make_spend_no_sales_suggestion(cost=100.0, clicks=50)
    new["estimated_savings"] = 149.0   # 1.49x; below 1.50x
    rejected = _rejected_row(estimated_savings=100.0)
    changed, _ = _is_material_change(new, rejected)
    assert changed is False


def test_material_change_spend_threshold_is_50_percent():
    new = _make_spend_no_sales_suggestion(cost=300.0, clicks=80)
    new["estimated_savings"] = 100.0   # impact unchanged
    rejected = _rejected_row(estimated_savings=100.0, cost=200.0)
    # 300 / 200 = 1.50 -> exactly at threshold
    changed, reason = _is_material_change(new, rejected)
    assert changed
    assert "spend increased" in reason


def test_material_change_acos_threshold_is_15_percentage_points():
    new = _make_spend_no_sales_suggestion(cost=100.0, clicks=50)
    new["estimated_savings"] = 100.0
    new["current_value"]["sales_30d"] = 100.0   # ACOS = 100%
    rejected = _rejected_row(estimated_savings=100.0, cost=100.0, sales=125.0)
    # ACOS jumped from 80% to 100%: 20pp >= 15pp -> material
    changed, reason = _is_material_change(new, rejected)
    assert changed
    assert "ACOS worsened" in reason


def test_material_change_acos_below_threshold_does_not_trigger():
    new = _make_spend_no_sales_suggestion(cost=100.0, clicks=50)
    new["estimated_savings"] = 100.0
    new["current_value"]["sales_30d"] = 100.0   # ACOS = 100%
    rejected = _rejected_row(estimated_savings=100.0, cost=100.0, sales=110.0)
    # ACOS jumped from 91% to 100%: ~9pp < 15pp -> not material
    changed, _ = _is_material_change(new, rejected)
    assert changed is False


def test_material_change_returns_false_when_nothing_moved():
    new = _make_spend_no_sales_suggestion(cost=100.0, clicks=50)
    new["estimated_savings"] = 100.0
    rejected = _rejected_row(estimated_savings=100.0, cost=100.0, sales=0.0)
    changed, reason = _is_material_change(new, rejected)
    assert changed is False
    assert reason == ""


def test_material_change_constants_match_spec():
    assert MATERIAL_CHANGE_IMPACT_RATIO == pytest.approx(1.50)
    assert MATERIAL_CHANGE_SPEND_RATIO  == pytest.approx(1.50)
    assert MATERIAL_CHANGE_ACOS_DELTA   == pytest.approx(0.15)
    assert REJECT_MEMORY_WINDOW_DAYS == 14
    assert MEMORY_SCORE_RESURFACED == pytest.approx(10.0)


# _apply_memory_filter ────────────────────────────────────────────────────

def test_apply_memory_filter_no_rejections_persists_all():
    new = [_make_spend_no_sales_suggestion()]
    out = _apply_memory_filter(new, [])
    assert len(out["persisted"]) == 1
    assert out["skipped"] == []


def test_apply_memory_filter_match_no_change_suppresses():
    new = _make_spend_no_sales_suggestion(cost=100.0, clicks=50)
    new["estimated_savings"] = 100.0
    new["keyword_id"] = "kw-aaa"
    rejected = _rejected_row(estimated_savings=100.0, cost=100.0)
    rejected["signature"] = _suggestion_signature(rejected)
    out = _apply_memory_filter([new], [rejected])
    assert out["persisted"] == []                    # suppressed
    assert len(out["skipped"]) == 1
    skip = out["skipped"][0]
    # Skip record carries everything the dashboard pill needs.
    assert skip["suggestion_type"] == "spend_no_sales"
    assert skip["label"] == "blue ceramic coffee mug"
    assert "Skipped" in skip["reason"]
    assert "rejected_at_iso"   in skip
    assert "next_eligible_iso" in skip


def test_apply_memory_filter_match_with_material_change_resurfaces():
    """
    Construct the new suggestion so that only the SPEND threshold
    trips (estimated_savings unchanged at $100, but cost_30d jumped
    from $100 to $300). The hint must call out spend, not impact.
    """
    new = _make_spend_no_sales_suggestion(cost=300.0, clicks=80)
    new["estimated_savings"] = 100.0     # unchanged: impact ratio 1.0x
    new["keyword_id"] = "kw-aaa"
    rejected = _rejected_row(estimated_savings=100.0, cost=100.0)
    rejected["signature"] = _suggestion_signature(rejected)
    out = _apply_memory_filter([new], [rejected])
    assert out["skipped"] == []
    assert len(out["persisted"]) == 1
    persisted = out["persisted"][0]
    mem = persisted["current_value"]["_memory"]
    assert mem["resurfaced"] is True
    assert mem["score_override"] == pytest.approx(10.0)
    assert "rejected this on" in mem["hint"]
    assert "bringing it back" in mem["hint"]
    assert "spend increased" in mem["hint"]


def test_apply_memory_filter_does_not_mutate_input():
    new = _make_spend_no_sales_suggestion(cost=300.0, clicks=80)
    new["keyword_id"] = "kw-aaa"
    snapshot = dict(new)
    cv_before = dict(new["current_value"])
    rejected = _rejected_row(estimated_savings=100.0, cost=100.0)
    rejected["signature"] = _suggestion_signature(rejected)
    _apply_memory_filter([new], [rejected])
    assert new == snapshot
    assert new["current_value"] == cv_before


# build_card_view + composite_score memory consumption ──────────────────

def test_build_card_view_uses_memory_hint_from_current_value():
    s = _make_spend_no_sales_suggestion(cost=300.0, clicks=80)
    s["current_value"]["_memory"] = {
        "resurfaced":         True,
        "rejected_at_iso":    "2026-05-01",
        "next_eligible_iso":  "2026-05-15",
        "score_override":     10.0,
        "hint": "You rejected this on 2026-05-01, but I'm bringing it back because spend increased from $100 to $300.",
        "label":              "blue ceramic coffee mug",
    }
    cv = build_card_view(s)
    assert cv["is_resurfaced"] is True
    assert cv["memory_score_override"] == pytest.approx(10.0)
    assert cv["memory_hint"].startswith("You rejected this on 2026-05-01")
    assert "bringing it back" in cv["memory_hint"]


def test_build_card_view_falls_back_to_neutral_hint_without_memory_meta():
    s = _make_spend_no_sales_suggestion()
    cv = build_card_view(s)
    assert cv["is_resurfaced"] is False
    assert cv["memory_score_override"] is None
    assert "No similar rejection found" in cv["memory_hint"]


def test_build_card_view_explicit_caller_memory_hint_wins_over_persisted():
    s = _make_spend_no_sales_suggestion()
    s["current_value"]["_memory"] = {"hint": "persisted hint"}
    cv = build_card_view(s, memory_hint="caller hint")
    assert cv["memory_hint"] == "caller hint"


def test_composite_score_uses_memory_score_override_when_present():
    """A resurfaced card with memory_score_override=10 must score lower
    than the same shape without the override (default 50)."""
    base = _make_card(stype="spend_no_sales", impact=200.0, evidence_mult=0.75,
                      risk="LOW RISK", cid=1)
    no_mem = composite_score(base)
    base_with_override = dict(base)
    base_with_override["memory_score_override"] = 10.0
    with_mem = composite_score(base_with_override)
    # Memory score weight is 0.10; (50-10) * 0.10 = 4.0 -> drops 4 points.
    assert no_mem["memory_score"] == pytest.approx(50.0)
    assert with_mem["memory_score"] == pytest.approx(10.0)
    assert with_mem["score"] == pytest.approx(no_mem["score"] - 4.0, abs=0.01)


def test_composite_score_default_memory_when_override_none():
    card = _make_card(impact=100.0)
    card["memory_score_override"] = None
    s = composite_score(card)
    assert s["memory_score"] == pytest.approx(50.0)


# Recent-rejection load + window logic ────────────────────────────────────

def _seed_rejected_row(sqlite_conn, *, connection_id, suggestion_type="spend_no_sales",
                       keyword_id="kw-aaa", ad_group_id="ag-1", current_value=None,
                       estimated_savings=100.0, decided_at=None):
    """Insert a rejected ppc_suggestions row with full per-Task-1 current_value."""
    if current_value is None:
        current_value = {
            "keyword_text":   "blue ceramic coffee mug",
            "cost_30d":       100.0,
            "sales_30d":      0.0,
            "clicks_30d":     50,
            "purchases_30d":  0,
            "bid":            0.95,
            "state":          "ENABLED",
        }
    if decided_at is None:
        decided_at = _time.time()
    cur = sqlite_conn.cursor()
    cur.execute(
        """
        INSERT INTO ppc_suggestions
          (connection_id, campaign_id, ad_group_id, keyword_id,
           suggestion_type, current_value, proposed_value, reason,
           estimated_savings, confidence, status, created_at, decided_at)
        VALUES (?, 'cmp-1', ?, ?, ?, ?, '{"state":"PAUSED"}', 'demo',
                ?, 'high', 'rejected', ?, ?)
        """,
        (connection_id, ad_group_id, keyword_id, suggestion_type,
         _json.dumps(current_value), estimated_savings,
         decided_at - 1, decided_at),
    )
    sqlite_conn.commit()
    return int(cur.lastrowid)


def test_load_recent_rejections_within_window(db_ctx, sqlite_conn):
    now = _time.time()
    _seed_rejected_row(sqlite_conn, connection_id=1,
                       decided_at=now - 1 * 86400)        # 1 day ago
    out = _load_recent_rejections(connection_id=1, db_ctx_factory=db_ctx, now=now)
    assert len(out) == 1
    assert "signature" in out[0]


def test_load_recent_rejections_outside_window_excluded(db_ctx, sqlite_conn):
    now = _time.time()
    _seed_rejected_row(sqlite_conn, connection_id=1,
                       decided_at=now - 30 * 86400)       # 30 days ago
    out = _load_recent_rejections(connection_id=1, db_ctx_factory=db_ctx, now=now)
    assert out == []


def test_load_recent_rejections_only_rejected_status(db_ctx, sqlite_conn):
    """Approved or pending rows must not contaminate the memory layer."""
    now = _time.time()
    cur = sqlite_conn.cursor()
    cur.execute(
        """
        INSERT INTO ppc_suggestions
          (connection_id, campaign_id, ad_group_id, keyword_id, suggestion_type,
           current_value, proposed_value, reason, estimated_savings, confidence,
           status, created_at, decided_at)
        VALUES (1, 'cmp', 'ag-1', 'kw-aaa', 'spend_no_sales',
                '{}', '{}', 'demo',
                100.0, 'high', 'approved_pending_apply', ?, ?)
        """,
        (now, now - 86400),
    )
    sqlite_conn.commit()
    out = _load_recent_rejections(connection_id=1, db_ctx_factory=db_ctx, now=now)
    assert out == []


# generate_suggestions: end-to-end memory behaviour ──────────────────────

def _seed_keyword_snapshot(sqlite_conn, *, connection_id=1, keyword_id="kw-aaa",
                            keyword_text="blue ceramic coffee mug",
                            cost=200.0, clicks=80, purchases=0, sales=0.0):
    """Seed a snapshot the engine will turn into a spend_no_sales suggestion."""
    now = _time.time()
    cur = sqlite_conn.cursor()
    cur.executemany(
        "INSERT INTO ppc_snapshots (connection_id, fetched_at, data_type, data) "
        "VALUES (?, ?, ?, ?)",
        [
            (connection_id, now, "campaigns",
             _json.dumps([{"campaignId": "cmp-1", "name": "Cmp"}])),
            (connection_id, now, "ad_groups",
             _json.dumps([{"adGroupId": "ag-1", "campaignId": "cmp-1",
                            "defaultBid": 0.95, "name": "Ag"}])),
            (connection_id, now, "keywords",
             _json.dumps([{"keywordId": keyword_id, "adGroupId": "ag-1",
                            "campaignId": "cmp-1", "keywordText": keyword_text,
                            "matchType": "exact", "bid": 0.95,
                            "state": "ENABLED"}])),
            (connection_id, now, "search_terms",
             _json.dumps([{"keywordId": keyword_id, "adGroupId": "ag-1",
                            "campaignId": "cmp-1", "searchTerm": keyword_text,
                            "impressions": 2000, "clicks": clicks,
                            "cost": cost, "purchases30d": purchases,
                            "sales30d": sales}])),
        ],
    )
    sqlite_conn.commit()


def test_generate_suggestions_suppresses_recent_rejection_no_change(db_ctx, sqlite_conn):
    """Reject within window + same metrics -> next run produces no pending row."""
    _seed_keyword_snapshot(sqlite_conn, cost=200.0, clicks=80)
    _seed_rejected_row(sqlite_conn, connection_id=1,
                       keyword_id="kw-aaa",
                       current_value={"keyword_text": "blue ceramic coffee mug",
                                       "cost_30d": 200.0, "sales_30d": 0.0,
                                       "clicks_30d": 80, "purchases_30d": 0,
                                       "bid": 0.95, "state": "ENABLED"},
                       estimated_savings=200.0,
                       decided_at=_time.time() - 1 * 86400)

    out = _generate_suggestions_real(connection_id=1, db_ctx_factory=db_ctx)
    assert out == [], "recently-rejected signature must not resurface"
    cur = sqlite_conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM ppc_suggestions WHERE connection_id=1 AND status='pending'"
    )
    assert cur.fetchone()[0] == 0, "no pending row should be persisted"


def test_generate_suggestions_resurfaces_with_material_change(db_ctx, sqlite_conn):
    """
    Reject within window + 50%+ spend increase -> the engine resurfaces
    the suggestion AND embeds memory metadata in current_value. Note
    that the spend_no_sales rule sets estimated_savings = cost, so a
    spend hike automatically also fires the impact threshold; the
    material-change check tries impact first, so the hint will read
    'estimated impact rose' (not 'spend increased') for this rule.
    """
    _seed_keyword_snapshot(sqlite_conn, cost=400.0, clicks=120)        # spend ↑↑
    _seed_rejected_row(sqlite_conn, connection_id=1,
                       keyword_id="kw-aaa",
                       current_value={"keyword_text": "blue ceramic coffee mug",
                                       "cost_30d": 200.0, "sales_30d": 0.0,
                                       "clicks_30d": 80, "purchases_30d": 0,
                                       "bid": 0.95, "state": "ENABLED"},
                       estimated_savings=200.0,
                       decided_at=_time.time() - 1 * 86400)

    out = _generate_suggestions_real(connection_id=1, db_ctx_factory=db_ctx)
    assert len(out) == 1
    persisted = out[0]
    mem = persisted["current_value"]["_memory"]
    assert mem["resurfaced"] is True
    assert mem["score_override"] == pytest.approx(10.0)
    # Either threshold can carry the reason; assert one of them.
    assert ("estimated impact rose" in mem["hint"]
            or "spend increased" in mem["hint"])


def test_generate_suggestions_outside_window_resurfaces_normally(db_ctx, sqlite_conn):
    """30-day-old rejection no longer suppresses; fresh card produced normally."""
    _seed_keyword_snapshot(sqlite_conn, cost=200.0, clicks=80)
    _seed_rejected_row(sqlite_conn, connection_id=1,
                       keyword_id="kw-aaa",
                       decided_at=_time.time() - 30 * 86400)

    out = _generate_suggestions_real(connection_id=1, db_ctx_factory=db_ctx)
    assert len(out) == 1
    # Outside window -> no _memory metadata attached.
    assert "_memory" not in (out[0]["current_value"] or {})


def test_list_memory_skipped_returns_skipped_after_rejection(db_ctx, sqlite_conn):
    """Dashboard pill data: list of skipped items, each with reason text."""
    _seed_keyword_snapshot(sqlite_conn, cost=200.0, clicks=80)
    _seed_rejected_row(sqlite_conn, connection_id=1, keyword_id="kw-aaa",
                       current_value={"keyword_text": "blue ceramic coffee mug",
                                       "cost_30d": 200.0, "sales_30d": 0.0,
                                       "clicks_30d": 80, "purchases_30d": 0,
                                       "bid": 0.95, "state": "ENABLED"},
                       estimated_savings=200.0,
                       decided_at=_time.time() - 2 * 86400)

    skipped = list_memory_skipped(connection_id=1, db_ctx_factory=db_ctx)
    assert len(skipped) == 1
    sk = skipped[0]
    assert sk["suggestion_type"] == "spend_no_sales"
    assert sk["label"] == "blue ceramic coffee mug"
    assert sk["rejected_at_iso"]
    assert sk["next_eligible_iso"]
    assert "Skipped" in sk["reason"]


def test_list_memory_skipped_empty_when_no_rejections(db_ctx, sqlite_conn):
    _seed_keyword_snapshot(sqlite_conn, cost=200.0, clicks=80)
    skipped = list_memory_skipped(connection_id=1, db_ctx_factory=db_ctx)
    assert skipped == []


def test_list_memory_skipped_empty_when_rejection_resurfaces(db_ctx, sqlite_conn):
    """Resurfaced (materially changed) rows are NOT skipped — they're persisted."""
    _seed_keyword_snapshot(sqlite_conn, cost=400.0, clicks=120)
    _seed_rejected_row(sqlite_conn, connection_id=1, keyword_id="kw-aaa",
                       estimated_savings=200.0,
                       current_value={"keyword_text": "blue ceramic coffee mug",
                                       "cost_30d": 200.0, "sales_30d": 0.0,
                                       "clicks_30d": 80, "purchases_30d": 0,
                                       "bid": 0.95, "state": "ENABLED"},
                       decided_at=_time.time() - 1 * 86400)

    skipped = list_memory_skipped(connection_id=1, db_ctx_factory=db_ctx)
    assert skipped == [], "materially-changed match resurfaces, doesn't skip"


# ──────────────────────────────────────────────────────────────────────────
#  Task 4 / Minimal Proof of Impact — approval baseline
# ──────────────────────────────────────────────────────────────────────────
#
# Tests for `build_approval_baseline` (pure) and
# `list_recently_approved_suggestions` (DB read). The route-level write
# path lives in tests/test_ppc_routes.py.

from ppc_suggestions import (   # noqa: E402  - intentional late import
    APPROVAL_NOTE,
    RECENT_APPROVED_DAYS_DEFAULT,
    build_approval_baseline,
    list_recently_approved_suggestions,
)


# build_approval_baseline ─────────────────────────────────────────────────

_FROZEN_NOW = 1746576000.0   # 2025-05-07 00:00 UTC, used as a fixed input


def test_build_approval_baseline_returns_required_fields():
    """Every key the dashboard reads must be populated, even with sparse cv."""
    out = build_approval_baseline({}, {}, 0.0, _FROZEN_NOW)
    required = {
        "approved_at", "approved_at_iso",
        "cost_30d", "sales_30d", "orders_30d", "clicks_30d", "acos_30d",
        "estimated_impact", "target_acos_used", "keyword_label", "note",
    }
    assert required <= set(out.keys())
    assert out["note"] == APPROVAL_NOTE


def test_build_approval_baseline_does_not_consult_clock():
    """`now` is an explicit input; two calls with the same `now` are equal."""
    cv = {"keyword_text": "x", "cost_30d": 10.0, "sales_30d": 0.0,
          "purchases_30d": 0, "clicks_30d": 4}
    a = build_approval_baseline(cv, {}, 5.0, _FROZEN_NOW)
    b = build_approval_baseline(cv, {}, 5.0, _FROZEN_NOW)
    assert a == b


def test_build_approval_baseline_captures_observed_metrics():
    cv = {
        "keyword_text":  "wireless headphones",
        "cost_30d":      200.0,
        "sales_30d":     0.0,
        "purchases_30d": 0,
        "clicks_30d":    80,
    }
    out = build_approval_baseline(cv, {}, 200.0, _FROZEN_NOW)
    assert out["cost_30d"]    == 200.0
    assert out["sales_30d"]   == 0.0
    assert out["orders_30d"]  == 0
    assert out["clicks_30d"]  == 80
    assert out["acos_30d"]    is None     # sales == 0 -> undefined ACOS
    assert out["keyword_label"] == "wireless headphones"
    assert out["estimated_impact"] == 200.0


def test_build_approval_baseline_acos_when_sales_present():
    cv = {"cost_30d": 60.0, "sales_30d": 200.0, "clicks_30d": 30,
          "purchases_30d": 4, "keyword_text": "kw"}
    out = build_approval_baseline(cv, {}, 0.0, _FROZEN_NOW)
    # 60 / 200 = 0.30 -> 30% ACOS at approval
    assert out["acos_30d"] == pytest.approx(0.30)


def test_build_approval_baseline_target_acos_from_proposed_value():
    cv = {"cost_30d": 100.0, "sales_30d": 200.0, "clicks_30d": 20,
          "purchases_30d": 2, "keyword_text": "kw"}
    out = build_approval_baseline(cv, {"target_acos": 0.30}, 0.0, _FROZEN_NOW)
    assert out["target_acos_used"] == pytest.approx(0.30)


def test_build_approval_baseline_target_acos_none_when_absent():
    cv = {"cost_30d": 100.0, "sales_30d": 200.0, "keyword_text": "kw"}
    out = build_approval_baseline(cv, {"state": "PAUSED"}, 0.0, _FROZEN_NOW)
    assert out["target_acos_used"] is None


def test_build_approval_baseline_handles_missing_fields_without_crashing():
    """A current_value with none of the metrics yields a valid baseline."""
    out = build_approval_baseline({"keyword_text": "x"}, None, 0.0, _FROZEN_NOW)
    assert out["cost_30d"]   == 0.0
    assert out["sales_30d"]  == 0.0
    assert out["orders_30d"] == 0
    assert out["clicks_30d"] == 0
    assert out["acos_30d"]   is None
    assert out["target_acos_used"] is None


def test_build_approval_baseline_uses_search_term_when_no_keyword_text():
    """promote_search_term cards have no keyword_text but do have a search_term."""
    cv = {"search_term": "blue mug", "cost_30d": 10.0}
    out = build_approval_baseline(cv, {"add_keyword": "blue mug"},
                                    0.0, _FROZEN_NOW)
    assert out["keyword_label"] == "blue mug"


def test_build_approval_baseline_does_not_mutate_inputs():
    cv = {"cost_30d": 10.0, "sales_30d": 5.0, "keyword_text": "kw"}
    pv = {"target_acos": 0.30}
    cv_copy = dict(cv)
    pv_copy = dict(pv)
    build_approval_baseline(cv, pv, 1.0, _FROZEN_NOW)
    assert cv == cv_copy
    assert pv == pv_copy


# list_recently_approved_suggestions ──────────────────────────────────────

def _seed_approved_with_baseline(sqlite_conn, *, connection_id=1,
                                   suggestion_type="spend_no_sales",
                                   keyword_id="kw-A1",
                                   ad_group_id="ag-1",
                                   cost_30d=200.0, sales_30d=0.0,
                                   clicks_30d=80, purchases_30d=0,
                                   estimated_savings=200.0,
                                   target_acos=None,
                                   keyword_text="blue mug",
                                   decided_at=None):
    """Seed an approved_pending_apply row with a built _approval_baseline."""
    if decided_at is None:
        decided_at = _time.time() - 1 * 86400      # 1 day ago
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
    cv["_approval_baseline"] = build_approval_baseline(
        cv, pv, estimated_savings, decided_at,
    )
    cur = sqlite_conn.cursor()
    cur.execute(
        """
        INSERT INTO ppc_suggestions
          (connection_id, campaign_id, ad_group_id, keyword_id, suggestion_type,
           current_value, proposed_value, reason, estimated_savings, confidence,
           status, created_at, decided_at)
        VALUES (?, 'cmp-1', ?, ?, ?, ?, ?, 'demo', ?, 'high',
                'approved_pending_apply', ?, ?)
        """,
        (connection_id, ad_group_id, keyword_id, suggestion_type,
         _json.dumps(cv), _json.dumps(pv), estimated_savings,
         decided_at - 1, decided_at),
    )
    sqlite_conn.commit()
    return int(cur.lastrowid)


def test_list_recently_approved_returns_empty_when_no_approvals(db_ctx, sqlite_conn):
    out = list_recently_approved_suggestions(connection_id=1, db_ctx_factory=db_ctx)
    assert out == []


def test_list_recently_approved_within_window(db_ctx, sqlite_conn):
    now = _time.time()
    _seed_approved_with_baseline(sqlite_conn, connection_id=1,
                                  decided_at=now - 1 * 86400)
    out = list_recently_approved_suggestions(connection_id=1,
                                              db_ctx_factory=db_ctx, now=now)
    assert len(out) == 1
    assert out[0]["status"] == "approved_pending_apply"


def test_list_recently_approved_outside_window_excluded(db_ctx, sqlite_conn):
    now = _time.time()
    _seed_approved_with_baseline(sqlite_conn, connection_id=1,
                                  decided_at=now - 30 * 86400)   # 30 days
    out = list_recently_approved_suggestions(connection_id=1,
                                              db_ctx_factory=db_ctx, now=now)
    assert out == []


def test_list_recently_approved_lifts_baseline_to_top_level(db_ctx, sqlite_conn):
    """Template doesn't walk current_value._approval_baseline; helper flattens."""
    _seed_approved_with_baseline(sqlite_conn, connection_id=1,
                                  cost_30d=180.0, sales_30d=0.0,
                                  clicks_30d=72, purchases_30d=0,
                                  estimated_savings=180.0)
    out = list_recently_approved_suggestions(connection_id=1, db_ctx_factory=db_ctx)
    row = out[0]
    assert row["cost_30d"]         == pytest.approx(180.0)
    assert row["sales_30d"]        == pytest.approx(0.0)
    assert row["clicks_30d"]       == 72
    assert row["orders_30d"]       == 0
    assert row["estimated_impact"] == pytest.approx(180.0)
    assert row["keyword_label"]    == "blue mug"
    assert row["acos_30d"]         is None
    assert row["note"]             == APPROVAL_NOTE
    assert row["has_baseline"]     is True


def test_list_recently_approved_excludes_pending_and_rejected(db_ctx, sqlite_conn):
    """Only approved_pending_apply rows count for the projection block."""
    cur = sqlite_conn.cursor()
    now = _time.time()
    cur.executemany(
        """
        INSERT INTO ppc_suggestions
          (connection_id, campaign_id, ad_group_id, keyword_id, suggestion_type,
           current_value, proposed_value, reason, estimated_savings, confidence,
           status, created_at, decided_at)
        VALUES (?, 'cmp', ?, ?, ?, ?, '{}', 'demo', ?, 'high', ?, ?, ?)
        """,
        [
            (1, 'ag-1', 'kw-pending',  'spend_no_sales', '{}',  10.0, 'pending',
             now, None),
            (1, 'ag-1', 'kw-rejected', 'spend_no_sales', '{}',  10.0, 'rejected',
             now, now - 86400),
        ],
    )
    sqlite_conn.commit()
    _seed_approved_with_baseline(sqlite_conn, connection_id=1,
                                  keyword_id="kw-approved")
    out = list_recently_approved_suggestions(connection_id=1, db_ctx_factory=db_ctx)
    assert len(out) == 1
    assert out[0]["keyword_id"] == "kw-approved"


def test_list_recently_approved_default_window_is_14_days(db_ctx, sqlite_conn):
    assert RECENT_APPROVED_DAYS_DEFAULT == 14
    now = _time.time()
    _seed_approved_with_baseline(sqlite_conn, connection_id=1,
                                  keyword_id="kw-13d",
                                  decided_at=now - 13 * 86400)
    _seed_approved_with_baseline(sqlite_conn, connection_id=1,
                                  keyword_id="kw-15d",
                                  decided_at=now - 15 * 86400)
    out = list_recently_approved_suggestions(connection_id=1,
                                              db_ctx_factory=db_ctx, now=now)
    assert [r["keyword_id"] for r in out] == ["kw-13d"]


def test_list_recently_approved_db_outage_returns_empty(db_ctx, sqlite_conn):
    """Defensive: a query failure must not break the dashboard."""
    sqlite_conn.execute("DROP TABLE ppc_suggestions")
    sqlite_conn.commit()
    out = list_recently_approved_suggestions(connection_id=1, db_ctx_factory=db_ctx)
    assert out == []


# ──────────────────────────────────────────────────────────────────────────
#  Decision log (Week 1 of MVP Hardening Plan / Task 6)
# ──────────────────────────────────────────────────────────────────────────

import pathlib
import re

from ppc_suggestions import (
    OBSERVATION_WINDOW_SECONDS,
    observation_due_at,
    log_decision,
    backfill_seller_decisions,
)


def test_observation_due_at_is_decided_plus_7_days():
    decided = 1_700_000_000.0
    assert observation_due_at(decided) == decided + 7 * 86400
    assert observation_due_at(decided) - decided == OBSERVATION_WINDOW_SECONDS


def test_observation_due_at_handles_none():
    assert observation_due_at(None) is None


def test_log_decision_inserts_row(db_ctx, sqlite_conn):
    new_id = log_decision(
        connection_id    = 7,
        suggestion_id    = 42,
        suggestion_type  = "spend_no_sales",
        decision         = "approved",
        decided_at       = 1_700_000_000.0,
        keyword_id       = "kw-101",
        ad_group_id      = "ag-1",
        campaign_id      = "cmp-1",
        current_value    = {"keyword_text": "demo waste term", "cost_30d": 187.0},
        proposed_value   = {"state": "PAUSED"},
        estimated_impact = 187.0,
        confidence       = "high",
        db_ctx_factory   = db_ctx,
    )
    assert isinstance(new_id, int) and new_id > 0
    cur = sqlite_conn.cursor()
    cur.execute(
        "SELECT connection_id, suggestion_id, suggestion_type, decision, "
        "       decided_at, observation_due_at, keyword_id "
        "FROM seller_decisions WHERE id = ?",
        (new_id,),
    )
    row = cur.fetchone()
    assert row is not None
    assert row[0] == 7
    assert row[1] == 42
    assert row[2] == "spend_no_sales"
    assert row[3] == "approved"
    assert row[4] == 1_700_000_000.0
    assert row[5] == 1_700_000_000.0 + 7 * 86400
    assert row[6] == "kw-101"


def test_log_decision_swallows_db_errors_returns_none(db_ctx, sqlite_conn):
    """If the DB write fails, return None, do not raise."""
    sqlite_conn.execute("DROP TABLE seller_decisions")
    sqlite_conn.commit()
    out = log_decision(
        connection_id    = 1,
        suggestion_id    = 1,
        suggestion_type  = "spend_no_sales",
        decision         = "approved",
        decided_at       = 1_700_000_000.0,
        db_ctx_factory   = db_ctx,
    )
    assert out is None


def test_log_decision_persists_jsonb_values(db_ctx, sqlite_conn):
    """current_value and proposed_value should round-trip via JSON."""
    cv = {"keyword_text": "abc", "cost_30d": 12.5, "_approval_baseline": {"foo": 1}}
    pv = {"state": "PAUSED", "bid": 0.95}
    new_id = log_decision(
        connection_id    = 1,
        suggestion_id    = 1,
        suggestion_type  = "spend_no_sales",
        decision         = "approved",
        decided_at       = 1_700_000_000.0,
        current_value    = cv,
        proposed_value   = pv,
        db_ctx_factory   = db_ctx,
    )
    cur = sqlite_conn.cursor()
    cur.execute(
        "SELECT current_value, proposed_value FROM seller_decisions WHERE id = ?",
        (new_id,),
    )
    cv_raw, pv_raw = cur.fetchone()
    assert json.loads(cv_raw) == cv
    assert json.loads(pv_raw) == pv


def _seed_decided_suggestion(conn, connection_id, status, decided_at,
                              suggestion_type="spend_no_sales",
                              estimated_savings=120.0):
    cur = conn.cursor()
    cv = json.dumps({"keyword_text": "kw " + status, "cost_30d": 100.0})
    pv = json.dumps({"state": "PAUSED"})
    cur.execute(
        """
        INSERT INTO ppc_suggestions
            (connection_id, campaign_id, ad_group_id, keyword_id,
             suggestion_type, current_value, proposed_value, reason,
             estimated_savings, confidence, status, created_at, decided_at)
        VALUES (?, 'cmp', 'ag', 'kw', ?, ?, ?, 'reason', ?, 'high', ?, ?, ?)
        """,
        (
            connection_id, suggestion_type, cv, pv,
            estimated_savings, status, decided_at - 1, decided_at,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def test_backfill_seller_decisions_inserts_existing_decisions(db_ctx, sqlite_conn):
    cid = 5
    sid_rejected = _seed_decided_suggestion(sqlite_conn, cid, "rejected", 1_700_000_000.0)
    sid_approved = _seed_decided_suggestion(sqlite_conn, cid, "approved_pending_apply", 1_700_010_000.0)
    sid_applied  = _seed_decided_suggestion(sqlite_conn, cid, "applied", 1_700_020_000.0)

    result = backfill_seller_decisions(connection_id=cid, db_ctx_factory=db_ctx)
    assert result["inserted"] == 3
    assert result["skipped_existing"] == 0

    cur = sqlite_conn.cursor()
    cur.execute(
        "SELECT suggestion_id, decision, observation_due_at "
        "FROM seller_decisions ORDER BY suggestion_id"
    )
    rows = cur.fetchall()
    assert len(rows) == 3
    by_sid = {r[0]: (r[1], r[2]) for r in rows}
    # Status -> decision mapping.
    assert by_sid[sid_rejected][0] == "rejected"
    assert by_sid[sid_approved][0] == "approved"
    assert by_sid[sid_applied][0]  == "approved"
    # observation_due_at = decided_at + 7 days for each.
    assert by_sid[sid_rejected][1] == 1_700_000_000.0 + 7 * 86400


def test_backfill_seller_decisions_is_idempotent(db_ctx, sqlite_conn):
    cid = 5
    _seed_decided_suggestion(sqlite_conn, cid, "rejected", 1_700_000_000.0)
    first  = backfill_seller_decisions(connection_id=cid, db_ctx_factory=db_ctx)
    second = backfill_seller_decisions(connection_id=cid, db_ctx_factory=db_ctx)
    assert first["inserted"] == 1
    assert second["inserted"] == 0
    assert second["skipped_existing"] == 1


def test_backfill_seller_decisions_skips_pending(db_ctx, sqlite_conn):
    cid = 5
    cur = sqlite_conn.cursor()
    cur.execute(
        """
        INSERT INTO ppc_suggestions
            (connection_id, suggestion_type, current_value, proposed_value,
             reason, estimated_savings, confidence, status, created_at)
        VALUES (?, 'spend_no_sales', '{}', '{}', 'r', 50.0, 'high', 'pending', ?)
        """,
        (cid, 1_700_000_000.0),
    )
    sqlite_conn.commit()
    result = backfill_seller_decisions(connection_id=cid, db_ctx_factory=db_ctx)
    assert result["inserted"] == 0
    cur.execute("SELECT COUNT(*) FROM seller_decisions")
    assert cur.fetchone()[0] == 0


def test_backfill_seller_decisions_db_outage_returns_zeros(db_ctx, sqlite_conn):
    sqlite_conn.execute("DROP TABLE ppc_suggestions")
    sqlite_conn.commit()
    out = backfill_seller_decisions(connection_id=1, db_ctx_factory=db_ctx)
    assert out == {"inserted": 0, "skipped_existing": 0, "skipped_no_decision": 0}


def test_seller_decisions_log_is_append_only_no_update_or_delete_in_codebase():
    """
    Append-only invariant for the seller_decisions table.

    Code-level enforcement: scan the project's Python source for any
    UPDATE seller_decisions or DELETE FROM seller_decisions statement.
    The table must only ever be INSERTed into. If a future change adds
    an UPDATE or DELETE path, this test fails loudly so the team can
    decide whether the immutability constraint is being relaxed
    intentionally.
    """
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    py_files = list(repo_root.glob("*.py")) + list((repo_root / "tests").glob("*.py"))

    update_re = re.compile(r"UPDATE\s+seller_decisions", re.IGNORECASE)
    delete_re = re.compile(r"DELETE\s+FROM\s+seller_decisions", re.IGNORECASE)

    offenders = []
    for path in py_files:
        # Skip this very test file: it talks about UPDATE/DELETE in a
        # docstring/regex but does not execute one.
        if path.name == "test_ppc_suggestions.py":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if update_re.search(text):
            offenders.append(f"{path.name}: UPDATE seller_decisions found")
        if delete_re.search(text):
            offenders.append(f"{path.name}: DELETE FROM seller_decisions found")

    assert not offenders, (
        "seller_decisions table is append-only. Found violations:\n"
        + "\n".join(offenders)
    )
