"""
Mock PPC snapshot data for SellerCopilot dev / tests.

Why this exists
---------------
Amazon Ads API access is gated behind a 4 to 8 week SP-API Production approval
plus a real Seller Central account with active campaigns. Until both are in
place we cannot exercise the suggestion engine end-to-end against live data.

This module builds a snapshot in the same shape `ppc_snapshot_fetcher` produces,
covers every recommendation rule with at least one positive case and one
negative case, and lets us insert that snapshot into `ppc_snapshots` exactly
the way the real fetcher would.

What is intentionally NOT done here
-----------------------------------
- We do not patch `ppc_snapshot_fetcher` to fall back to mocks. The real
  fetcher must keep failing loudly when Amazon credentials are missing.
- We do not invent fields Amazon does not return. Every key here matches the
  Ads API response shape exactly so the rules engine can be ported to live
  data with no schema drift.

Layout
------
- CAMPAIGNS / AD_GROUPS / KEYWORDS / SEARCH_TERMS / PROFILES are module-level
  constants. Tests import them directly and feed them to the rules engine
  without touching a database.
- `build_snapshot_payload()` returns a dict mapping data_type -> list[dict],
  the same shape `ppc_snapshot_fetcher` writes into `ppc_snapshots`.
- `seed_mock_snapshot(connection_id, db_context_manager)` inserts those
  payloads as ppc_snapshots rows, so the dashboard and DB-level tests can
  exercise the full read path.

Designed cases (each keyword/search-term in this file is here for a reason)
--------------------------------------------------------------------------
Campaign cmp-1 "Summer Skincare":
  kw-101 "moisturizer for dry skin"        rule: spend with no sales
  kw-102 "anti-aging serum"                rule: high ACOS
  kw-103 "hand cream"                      negative control (healthy)
Campaign cmp-2 "Winter Gear":
  kw-201 "wool socks"                      rule: bid too high vs ad group default
  kw-202 "thermal underwear"               rule: profitable to scale
Campaign cmp-3 "Pet Supplies":
  kw-301 "dog food"                        negative control (healthy ACOS)
  + search term "organic dog treats"       rule: search term to promote (no kw exists)
"""

from __future__ import annotations

import json
import secrets
import time
from typing import Any


# ──────────────────────────────────────────────────────────────────────────
#  Mock fixtures (one mock seller's account)
# ──────────────────────────────────────────────────────────────────────────

PROFILES: list[dict[str, Any]] = [
    {
        "profileId": 9999000001,
        "countryCode": "US",
        "currencyCode": "USD",
        "dailyBudget": 200.0,
        "timezone": "America/Los_Angeles",
        "marketplaceStringId": "ATVPDKIKX0DER",
        "accountInfo": {
            "marketplaceStringId": "ATVPDKIKX0DER",
            "id": "A1MOCKSELLERID01",
            "type": "seller",
            "name": "Mock Seller LLC",
        },
    },
]


CAMPAIGNS: list[dict[str, Any]] = [
    {
        "campaignId": "cmp-1",
        "name": "Summer Skincare",
        "campaignType": "sponsoredProducts",
        "targetingType": "manual",
        "state": "ENABLED",
        "dailyBudget": 60.0,
        "startDate": "2026-04-01",
    },
    {
        "campaignId": "cmp-2",
        "name": "Winter Gear",
        "campaignType": "sponsoredProducts",
        "targetingType": "manual",
        "state": "ENABLED",
        "dailyBudget": 80.0,
        "startDate": "2026-04-01",
    },
    {
        "campaignId": "cmp-3",
        "name": "Pet Supplies",
        "campaignType": "sponsoredProducts",
        "targetingType": "manual",
        "state": "ENABLED",
        "dailyBudget": 60.0,
        "startDate": "2026-04-01",
    },
]


AD_GROUPS: list[dict[str, Any]] = [
    {
        "adGroupId":   "ag-1",
        "campaignId":  "cmp-1",
        "name":        "Skincare AG",
        "defaultBid":  0.85,
        "state":       "ENABLED",
    },
    {
        "adGroupId":   "ag-2",
        "campaignId":  "cmp-2",
        "name":        "Winter AG",
        "defaultBid":  1.20,
        "state":       "ENABLED",
    },
    {
        "adGroupId":   "ag-3",
        "campaignId":  "cmp-3",
        "name":        "Pet AG",
        "defaultBid":  0.95,
        "state":       "ENABLED",
    },
]


KEYWORDS: list[dict[str, Any]] = [
    # ─ Campaign 1: Summer Skincare ────────────────────────────────────
    {
        "keywordId":   "kw-101",
        "adGroupId":   "ag-1",
        "campaignId":  "cmp-1",
        "keywordText": "moisturizer for dry skin",
        "matchType":   "broad",
        "bid":         0.95,
        "state":       "ENABLED",
    },
    {
        "keywordId":   "kw-102",
        "adGroupId":   "ag-1",
        "campaignId":  "cmp-1",
        "keywordText": "anti-aging serum",
        "matchType":   "phrase",
        "bid":         1.10,
        "state":       "ENABLED",
    },
    {
        "keywordId":   "kw-103",
        "adGroupId":   "ag-1",
        "campaignId":  "cmp-1",
        "keywordText": "hand cream",
        "matchType":   "exact",
        "bid":         0.75,
        "state":       "ENABLED",
    },
    # ─ Campaign 2: Winter Gear ────────────────────────────────────────
    {
        "keywordId":   "kw-201",
        "adGroupId":   "ag-2",
        "campaignId":  "cmp-2",
        "keywordText": "wool socks",
        "matchType":   "broad",
        "bid":         2.40,                # vs ag-2 default 1.20 -> 2x
        "state":       "ENABLED",
    },
    {
        "keywordId":   "kw-202",
        "adGroupId":   "ag-2",
        "campaignId":  "cmp-2",
        "keywordText": "thermal underwear",
        "matchType":   "exact",
        "bid":         1.05,
        "state":       "ENABLED",
    },
    # ─ Campaign 3: Pet Supplies ───────────────────────────────────────
    {
        "keywordId":   "kw-301",
        "adGroupId":   "ag-3",
        "campaignId":  "cmp-3",
        "keywordText": "dog food",
        "matchType":   "broad",
        "bid":         0.95,
        "state":       "ENABLED",
    },
]


# 30-day search-term report rows. Numbers are realistic for a mid-size FBA
# seller running ~$200/day across 3 campaigns. Each row includes the
# Sponsored Products report columns we requested in
# ppc_ads_client.get_search_term_report.
SEARCH_TERMS: list[dict[str, Any]] = [
    # ── kw-101 spend-with-no-sales: 8 clicks, $9.20 cost, 0 sales ──
    {
        "campaignId":   "cmp-1",
        "adGroupId":    "ag-1",
        "keywordId":    "kw-101",
        "keywordText":  "moisturizer for dry skin",
        "matchType":    "broad",
        "searchTerm":   "moisturizer for dry winter skin",
        "impressions":  812,
        "clicks":       6,
        "cost":         6.90,
        "purchases1d":  0, "purchases7d":  0, "purchases14d": 0, "purchases30d": 0,
        "sales1d":      0.0, "sales7d":      0.0, "sales14d":     0.0, "sales30d":     0.0,
    },
    {
        "campaignId":   "cmp-1",
        "adGroupId":    "ag-1",
        "keywordId":    "kw-101",
        "keywordText":  "moisturizer for dry skin",
        "matchType":    "broad",
        "searchTerm":   "best moisturizer dry skin face",
        "impressions":  240,
        "clicks":       2,
        "cost":         2.30,
        "purchases1d":  0, "purchases7d":  0, "purchases14d": 0, "purchases30d": 0,
        "sales1d":      0.0, "sales7d":      0.0, "sales14d":     0.0, "sales30d":     0.0,
    },
    # ── kw-102 high-ACOS: $42 cost, $60 sales -> ACOS 70% ──
    {
        "campaignId":   "cmp-1",
        "adGroupId":    "ag-1",
        "keywordId":    "kw-102",
        "keywordText":  "anti-aging serum",
        "matchType":    "phrase",
        "searchTerm":   "best anti-aging serum",
        "impressions":  3100,
        "clicks":       38,
        "cost":         41.80,
        "purchases1d":  1, "purchases7d":  2, "purchases14d": 2, "purchases30d": 3,
        "sales1d":      19.99, "sales7d":  39.98, "sales14d":     39.98, "sales30d":     59.97,
    },
    # ── kw-103 healthy control: $18 cost, $112 sales, ACOS 16% ──
    {
        "campaignId":   "cmp-1",
        "adGroupId":    "ag-1",
        "keywordId":    "kw-103",
        "keywordText":  "hand cream",
        "matchType":    "exact",
        "searchTerm":   "hand cream",
        "impressions":  1500,
        "clicks":       22,
        "cost":         17.60,
        "purchases1d":  3, "purchases7d":  6, "purchases14d": 8, "purchases30d": 8,
        "sales1d":      29.97, "sales7d":  84.93, "sales14d":     112.00, "sales30d":     112.00,
    },
    # ── kw-201 bid-too-high: bid 2.40 vs ag default 1.20 ──
    {
        "campaignId":   "cmp-2",
        "adGroupId":    "ag-2",
        "keywordId":    "kw-201",
        "keywordText":  "wool socks",
        "matchType":    "broad",
        "searchTerm":   "merino wool socks",
        "impressions":  1900,
        "clicks":       30,
        "cost":         63.00,           # ~2.10 cpc
        "purchases1d":  3, "purchases7d":  5, "purchases14d": 6, "purchases30d": 7,
        "sales1d":      54.95, "sales7d":  114.95, "sales14d":     144.93, "sales30d":     180.92,
    },
    # ── kw-202 profitable-to-scale: ACOS 12%, only 600 impressions ──
    {
        "campaignId":   "cmp-2",
        "adGroupId":    "ag-2",
        "keywordId":    "kw-202",
        "keywordText":  "thermal underwear",
        "matchType":    "exact",
        "searchTerm":   "thermal underwear",
        "impressions":  600,
        "clicks":       18,
        "cost":         16.80,
        "purchases1d":  2, "purchases7d":  4, "purchases14d": 5, "purchases30d": 5,
        "sales1d":      59.98, "sales7d":  119.96, "sales14d":     149.95, "sales30d":     149.95,
    },
    # ── kw-301 healthy control: ACOS 18%, normal volume ──
    {
        "campaignId":   "cmp-3",
        "adGroupId":    "ag-3",
        "keywordId":    "kw-301",
        "keywordText":  "dog food",
        "matchType":    "broad",
        "searchTerm":   "dog food",
        "impressions":  4200,
        "clicks":       60,
        "cost":         58.50,
        "purchases1d":  6, "purchases7d":  14, "purchases14d": 18, "purchases30d": 24,
        "sales1d":      89.94, "sales7d":  209.86, "sales14d":     269.82, "sales30d":     325.76,
    },
    # ── search-term-to-promote: "organic dog treats" performs well under
    #     kw-301 broad match and is NOT yet a keyword in any ad group. ──
    {
        "campaignId":   "cmp-3",
        "adGroupId":    "ag-3",
        "keywordId":    "kw-301",
        "keywordText":  "dog food",
        "matchType":    "broad",
        "searchTerm":   "organic dog treats",
        "impressions":  900,
        "clicks":       18,
        "cost":         14.40,
        "purchases1d":  3, "purchases7d":  6, "purchases14d": 7, "purchases30d": 8,
        "sales1d":      27.96, "sales7d":  55.92, "sales14d":     65.24, "sales30d":     74.56,
    },
]


# ──────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────

SNAPSHOT_DATA_TYPES = ("profiles", "campaigns", "ad_groups", "keywords", "search_terms")


def build_snapshot_payload() -> dict[str, list[dict[str, Any]]]:
    """
    Return the mock snapshot keyed by data_type.

    Same shape ppc_snapshot_fetcher hands to ppc_snapshots (one list of dicts
    per data_type). Convenient for unit tests that bypass the DB and feed the
    rules engine directly.
    """
    return {
        "profiles":     list(PROFILES),
        "campaigns":    list(CAMPAIGNS),
        "ad_groups":    list(AD_GROUPS),
        "keywords":     list(KEYWORDS),
        "search_terms": list(SEARCH_TERMS),
    }


def seed_mock_snapshot(connection_id: int, db_context_manager) -> dict[str, int]:
    """
    Insert the mock fixtures into ppc_snapshots as if the real fetcher had
    just run. Useful for local dev when you want the dashboard, /ppc/suggestions
    list, and the rules engine to all see the same data.

    Args:
        connection_id: amazon_connections.id row to attribute the snapshots to.
            The row does not have to exist; ppc_snapshots has no FK to it.
        db_context_manager: callable returning a context manager that yields
            (cursor, placeholder). Pass `server._db` in real code; in tests
            pass a fake context manager.

    Returns:
        Dict counting inserted rows per data_type.
    """
    payload = build_snapshot_payload()
    counts: dict[str, int] = {}
    now = time.time()
    # Mock seeds simulate a single complete fetch, so all five rows share
    # one snapshot_run_id. This keeps the seeder shape identical to the
    # real fetcher and exercises the batch-coherence path of
    # _load_latest_snapshots in tests.
    run_id = (
        f"mock-{connection_id}-{int(now * 1000)}-{secrets.token_hex(4)}"
    )

    with db_context_manager() as (cur, ph):
        for data_type in SNAPSHOT_DATA_TYPES:
            data = json.dumps(payload[data_type], default=str)
            # Backward-compat: if the test schema (or a legacy DB) has not
            # yet added the snapshot_run_id column, fall back to the
            # 4-column INSERT so existing test fixtures keep working
            # without a forced migration.
            try:
                cur.execute(
                    f"""
                    INSERT INTO ppc_snapshots
                      (connection_id, fetched_at, data_type, data, snapshot_run_id)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph})
                    """,
                    (connection_id, now, data_type, data, run_id),
                )
            except Exception:
                cur.execute(
                    f"""
                    INSERT INTO ppc_snapshots
                      (connection_id, fetched_at, data_type, data)
                    VALUES ({ph}, {ph}, {ph}, {ph})
                    """,
                    (connection_id, now, data_type, data),
                )
            counts[data_type] = len(payload[data_type])
    return counts
