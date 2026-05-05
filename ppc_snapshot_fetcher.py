"""
Daily PPC snapshot fetcher for SellerCopilot.

Orchestrates the periodic pull of PPC data from Amazon Ads API into the
local Postgres ppc_snapshots table. The suggestion generator reads from
those snapshots; it never re-fetches from Ads API. This separates the slow
(network-bound) data acquisition from the fast (local-only) analysis.

Schedule: every PPC_SNAPSHOT_TTL_SECONDS (6 hours by default, defined in
ppc_agent.py). The cron entry point is fetch_all_active_connections()
which iterates amazon_connections rows whose last_synced_at is older than
the staleness threshold.

Per-connection fetch order:
1. Profiles                    so we know which Ads scope to use
2. Campaigns                   ENABLED + PAUSED only
3. Ad groups per campaign
4. Keywords per ad group
5. Search-term report (30d)    slow (1 to 10 min via async report API)

All raw responses are stored as JSON in ppc_snapshots. Postgres uses JSONB,
SQLite stores the same value as TEXT (the schema in ppc_agent.py handles
both).

Failure handling: each step is wrapped in try/except. A failed step is
recorded in the summary but does not abort later steps. We accept a
partial snapshot over no snapshot, because suggestions can still be made
from campaigns + ad groups even if the search-term report failed.
"""

from __future__ import annotations

import json
import time
import logging
from datetime import date, timedelta
from typing import Any

import ppc_ads_client

log = logging.getLogger("ppc_snapshot_fetcher")


# ──────────────────────────────────────────────────────────────────────────
#  Config
# ──────────────────────────────────────────────────────────────────────────

# How far back the search-term report covers. 30 days matches the window
# Amazon's organic ranking signals are computed on, so suggestions reflect
# the same period the algorithm uses.
SEARCH_TERM_LOOKBACK_DAYS = 30

# How stale a connection's last sync can be before fetch_all_active picks
# it up. Same effective default as ppc_agent.PPC_SNAPSHOT_TTL_SECONDS.
SYNC_STALENESS_SECONDS = 6 * 60 * 60


# ──────────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────────

def fetch_ppc_snapshot(connection_id: int) -> dict[str, Any]:
    """
    Fetch a complete PPC snapshot for one connection and store in DB.

    Idempotent: re-running for the same connection within the staleness
    window simply writes another snapshot row. The suggestion generator
    reads the most recent row per data_type.

    Args:
        connection_id: amazon_connections.id of the seller's account.

    Returns:
        Summary dict with counts and any errors. Shape:
        {
          "connection_id":      int,
          "profiles_count":     int,
          "campaigns_count":    int,
          "ad_groups_count":    int,
          "keywords_count":     int,
          "search_terms_count": int,
          "errors":             list[str],
          "started_at":         float (epoch seconds),
          "finished_at":        float (epoch seconds),
        }

    Never raises. All exceptions are caught and recorded in summary["errors"]
    so a single failing connection does not abort a multi-connection cron run.
    """
    started_at = time.time()
    summary: dict[str, Any] = {
        "connection_id":      connection_id,
        "profiles_count":     0,
        "campaigns_count":    0,
        "ad_groups_count":    0,
        "keywords_count":     0,
        "search_terms_count": 0,
        "errors":             [],
        "started_at":         started_at,
        "finished_at":        None,
    }

    # Step 1: profiles. Without this we cannot make any other Ads API call.
    profiles: list[dict[str, Any]] = []
    try:
        client_no_profile = ppc_ads_client.AdsClient(connection_id)
        profiles = client_no_profile.list_profiles()
        summary["profiles_count"] = len(profiles)
        _store_snapshot(connection_id, "profiles", profiles)
    except Exception as e:
        msg = f"profiles fetch failed: {e}"
        log.warning("connection_id=%d %s", connection_id, msg)
        summary["errors"].append(msg)
        summary["finished_at"] = time.time()
        return summary

    if not profiles:
        summary["errors"].append("no profiles returned by Amazon Ads API")
        summary["finished_at"] = time.time()
        return summary

    # For v1 we always use the first profile. Multi-profile sellers will
    # need explicit selection in the dashboard (week 5).
    profile_id = str(profiles[0].get("profileId", ""))
    if not profile_id:
        summary["errors"].append("first profile has no profileId field")
        summary["finished_at"] = time.time()
        return summary

    client = ppc_ads_client.AdsClient(connection_id, profile_id=profile_id)

    # Step 2: campaigns
    campaigns: list[dict[str, Any]] = []
    try:
        campaigns = client.list_campaigns()
        summary["campaigns_count"] = len(campaigns)
        _store_snapshot(connection_id, "campaigns", campaigns)
    except Exception as e:
        msg = f"campaigns fetch failed: {e}"
        log.warning("connection_id=%d %s", connection_id, msg)
        summary["errors"].append(msg)

    # Step 3: ad groups per campaign. Failures per-campaign are recorded
    # but do not abort. We collect all ad groups in a single list.
    all_ad_groups: list[dict[str, Any]] = []
    for c in campaigns:
        cid = str(c.get("campaignId", ""))
        if not cid:
            continue
        try:
            ad_groups = client.list_ad_groups(cid)
            all_ad_groups.extend(ad_groups)
        except Exception as e:
            summary["errors"].append(
                f"ad_groups fetch failed for campaign {cid}: {e}"
            )
    summary["ad_groups_count"] = len(all_ad_groups)
    _store_snapshot(connection_id, "ad_groups", all_ad_groups)

    # Step 4: keywords per ad group
    all_keywords: list[dict[str, Any]] = []
    for ag in all_ad_groups:
        agid = str(ag.get("adGroupId", ""))
        if not agid:
            continue
        try:
            kws = client.list_keywords(agid)
            all_keywords.extend(kws)
        except Exception as e:
            summary["errors"].append(
                f"keywords fetch failed for ad_group {agid}: {e}"
            )
    summary["keywords_count"] = len(all_keywords)
    _store_snapshot(connection_id, "keywords", all_keywords)

    # Step 5: search-term report. This is the slow step (1 to 10 minutes
    # via the async Reports v3 API). Failures here are common when Amazon's
    # report queue is backed up; we tolerate them and rely on the next
    # scheduled run.
    try:
        end_date   = date.today()
        start_date = end_date - timedelta(days=SEARCH_TERM_LOOKBACK_DAYS)
        st_rows = client.get_search_term_report(
            start_date.isoformat(),
            end_date.isoformat(),
        )
        summary["search_terms_count"] = len(st_rows)
        _store_snapshot(connection_id, "search_terms", st_rows)
    except Exception as e:
        msg = f"search_term_report fetch failed: {e}"
        log.warning("connection_id=%d %s", connection_id, msg)
        summary["errors"].append(msg)

    # Step 6: update last_synced_at so the cron skips this connection on
    # the next pass within the staleness window.
    try:
        _update_last_synced(connection_id)
    except Exception as e:
        summary["errors"].append(f"last_synced_at update failed: {e}")

    summary["finished_at"] = time.time()
    log.info(
        "snapshot complete connection_id=%d duration=%.1fs "
        "profiles=%d campaigns=%d ad_groups=%d keywords=%d search_terms=%d errors=%d",
        connection_id, summary["finished_at"] - summary["started_at"],
        summary["profiles_count"], summary["campaigns_count"],
        summary["ad_groups_count"], summary["keywords_count"],
        summary["search_terms_count"], len(summary["errors"]),
    )
    return summary


def fetch_all_active_connections() -> dict[str, int]:
    """
    Iterate all active connections whose last sync is older than
    SYNC_STALENESS_SECONDS, run fetch_ppc_snapshot for each.

    This is the cron entry point. Call once per hour from a scheduled job
    (Railway cron, GitHub Actions schedule, or a background thread). Only
    connections actually due for a refresh are processed, so re-running the
    cron more frequently than the staleness window is a no-op.

    Returns:
        {
          "considered": int,  number of connections checked
          "fetched":    int,  number where fetch_ppc_snapshot completed
          "errored":    int,  number where the fetch returned errors
        }
    """
    from server import _db  # lazy import, server imports ppc_agent which
                            # imports this module's caller

    cutoff = time.time() - SYNC_STALENESS_SECONDS
    counts = {"considered": 0, "fetched": 0, "errored": 0}

    with _db() as (cur, ph):
        cur.execute(
            f"""
            SELECT id
            FROM amazon_connections
            WHERE active = 1
              AND (last_synced_at IS NULL OR last_synced_at < {ph})
            ORDER BY id
            """,
            (cutoff,),
        )
        rows = cur.fetchall()

    counts["considered"] = len(rows)

    for (conn_id,) in rows:
        try:
            summary = fetch_ppc_snapshot(conn_id)
            counts["fetched"] += 1
            if summary["errors"]:
                counts["errored"] += 1
        except Exception as e:
            log.exception(
                "Unhandled exception in fetch_ppc_snapshot for connection_id=%d: %s",
                conn_id, e,
            )
            counts["errored"] += 1

    log.info(
        "fetch_all_active_connections done considered=%d fetched=%d errored=%d",
        counts["considered"], counts["fetched"], counts["errored"],
    )
    return counts


# ──────────────────────────────────────────────────────────────────────────
#  Internal DB helpers
# ──────────────────────────────────────────────────────────────────────────

def _store_snapshot(connection_id: int, data_type: str,
                    data: list[dict[str, Any]]) -> None:
    """
    Insert one snapshot row. The data list is JSON-serialised before insert.
    Postgres column is JSONB; SQLite is TEXT. Both accept the same payload.
    """
    from server import _db

    payload = json.dumps(data, default=str)
    now = time.time()

    with _db() as (cur, ph):
        cur.execute(
            f"""
            INSERT INTO ppc_snapshots (connection_id, fetched_at, data_type, data)
            VALUES ({ph}, {ph}, {ph}, {ph})
            """,
            (connection_id, now, data_type, payload),
        )


def _update_last_synced(connection_id: int) -> None:
    """Mark this connection as freshly synced so the cron skips it next pass."""
    from server import _db

    now = time.time()
    with _db() as (cur, ph):
        cur.execute(
            f"UPDATE amazon_connections SET last_synced_at = {ph} WHERE id = {ph}",
            (now, connection_id),
        )
