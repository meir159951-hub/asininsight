"""
PPC Bid Manager, AI Agent that manages Amazon PPC campaigns.

Architecture:
1. Customer connects Amazon Seller Central via OAuth (Login with Amazon).
2. Background job fetches PPC data periodically via ppc_snapshot_fetcher.
3. LLM agent analyzes data and generates suggestions: bid changes,
   negative keywords, pause underperformers, scale winners.
4. Customer reviews suggestions on dashboard, approves with one click.
5. Approved changes pushed via Amazon Ads API.
6. State snapshotted before every change. 30-day rollback button reverts.
7. Performance tracked: AI auto-rollbacks if a change tanks the metric.

This module exposes:
- init_ppc_db()        : create tables on startup (called from server.py).
- register_routes(app) : register /ppc/* Flask routes (called from server.py).

Stage of implementation (2026-05-04):
- Schema + token encryption + OAuth flow wired (delegates to ppc_oauth)
- Snapshot fetcher wired (delegates to ppc_snapshot_fetcher)
- Suggestion generator + applier + rollback still TODO (weeks 4-6)

Why a single module instead of a package: matches existing server.py style.
We can split into a package once it grows past ~1500 lines.
"""

from __future__ import annotations

import json
import os
import time
import logging
import secrets
from functools import wraps
from typing import Any
from urllib.parse import urlencode, urlparse

from flask import (
    Blueprint, request, session, jsonify, redirect, render_template,
    current_app,
)

import ppc_oauth
import ppc_snapshot_fetcher
import ppc_suggestions
import ppc_csv_ingest

log = logging.getLogger("ppc_agent")

# ──────────────────────────────────────────────────────────────────────────
#  Config (read from env, set on Railway)
# ──────────────────────────────────────────────────────────────────────────

# From Amazon Solution Provider Portal (Sandbox app credentials saved
# 2026-05-04 in C:\Users\meir1\Documents\ASINInsight_Amazon_Credentials.txt).
SP_API_CLIENT_ID     = os.getenv("SP_API_CLIENT_ID", "")
SP_API_CLIENT_SECRET = os.getenv("SP_API_CLIENT_SECRET", "")
SP_API_APP_ID        = os.getenv("SP_API_APP_ID", "")

# OAuth callback URL must match what's registered with Amazon.
# In Sandbox we self-authorize; in Production this is the Login with Amazon
# redirect URI configured at developer.amazonservices.com.
SP_API_REDIRECT_URI = os.getenv(
    "SP_API_REDIRECT_URI",
    "https://asininsight.com/ppc/oauth/callback",
)

# Encryption key for OAuth refresh tokens at rest. Generated once with
# `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
# and stored as Railway env var. NEVER commit to git.
PPC_TOKEN_ENCRYPTION_KEY = os.getenv("PPC_TOKEN_ENCRYPTION_KEY", "")

# Amazon Ads API region (NA = US/CA/MX, EU, FE = Asia)
ADS_API_REGION = os.getenv("ADS_API_REGION", "NA")

# How fresh PPC data must be before we re-fetch. Amazon rate limits the API
# so we don't hammer it. 6 hours is enough granularity for daily-ish
# bid management without burning the request budget.
PPC_SNAPSHOT_TTL_SECONDS = 6 * 60 * 60

# Hard caps to stay inside Amazon Agent Policy (March 2026).
# Tier 2 = up to 499 ASINs per batch with single-batch approval; we
# stay well under that.
MAX_SUGGESTIONS_PER_CUSTOMER_PER_WEEK = 50
MAX_BID_CHANGE_PCT_PER_24H            = 20  # 20%/24h price change cap
ROLLBACK_WINDOW_DAYS                  = 30


# ──────────────────────────────────────────────────────────────────────────
#  DB schema, runs at startup, idempotent
# ──────────────────────────────────────────────────────────────────────────

def init_ppc_db(db_context_manager, database_url: str | None) -> None:
    """
    Create PPC-related tables. Called from server.py:_init_db().

    Args:
        db_context_manager: the _db() context manager from server.py.
        database_url:       truthy if Postgres, None if SQLite (controls
                            placeholder + SERIAL vs INTEGER PRIMARY KEY).
    """
    serial = "SERIAL PRIMARY KEY" if database_url else "INTEGER PRIMARY KEY AUTOINCREMENT"
    jsonb  = "JSONB" if database_url else "TEXT"

    try:
        with db_context_manager() as (cur, ph):
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS amazon_connections (
                    id                       {serial},
                    customer_id              TEXT NOT NULL,
                    seller_id                TEXT,
                    marketplace_id           TEXT NOT NULL DEFAULT 'ATVPDKIKX0DER',
                    refresh_token_encrypted  TEXT NOT NULL,
                    ads_profile_id           TEXT,
                    connected_at             REAL NOT NULL,
                    last_synced_at           REAL,
                    active                   INTEGER NOT NULL DEFAULT 1
                )
            """)

            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS ppc_snapshots (
                    id               {serial},
                    connection_id    INTEGER NOT NULL,
                    fetched_at       REAL NOT NULL,
                    data_type        TEXT NOT NULL,
                    data             {jsonb} NOT NULL,
                    snapshot_run_id  TEXT
                )
            """)

            # Additive migration: older deployments created ppc_snapshots
            # without snapshot_run_id. Adding the column on already-running
            # databases is idempotent thanks to the IF NOT EXISTS / try-except
            # below. snapshot_run_id is NULL on legacy rows; the suggestion
            # engine treats NULL as "single-row run" and falls back to the
            # per-data_type latest read so legacy data is still consumable.
            try:
                if database_url:
                    cur.execute(
                        "ALTER TABLE ppc_snapshots "
                        "ADD COLUMN IF NOT EXISTS snapshot_run_id TEXT"
                    )
                else:
                    cur.execute(
                        "ALTER TABLE ppc_snapshots ADD COLUMN snapshot_run_id TEXT"
                    )
            except Exception as e:
                # Already present (SQLite raises "duplicate column"): fine.
                # Any other failure is logged but non-fatal so the rest of
                # init_ppc_db can complete.
                log.debug("snapshot_run_id ALTER skipped: %s", e)

            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS ppc_suggestions (
                    id                 {serial},
                    connection_id      INTEGER NOT NULL,
                    campaign_id        TEXT,
                    ad_group_id        TEXT,
                    keyword_id         TEXT,
                    suggestion_type    TEXT NOT NULL,
                    current_value      {jsonb},
                    proposed_value     {jsonb},
                    reason             TEXT NOT NULL,
                    estimated_savings  REAL,
                    confidence         TEXT NOT NULL DEFAULT 'medium',
                    status             TEXT NOT NULL DEFAULT 'pending',
                    created_at         REAL NOT NULL,
                    decided_at         REAL,
                    applied_at         REAL
                )
            """)

            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS ppc_audit_log (
                    id              {serial},
                    connection_id   INTEGER NOT NULL,
                    suggestion_id   INTEGER,
                    action          TEXT NOT NULL,
                    before_value    {jsonb},
                    after_value     {jsonb},
                    api_response    {jsonb},
                    performed_at    REAL NOT NULL,
                    performed_by    TEXT NOT NULL
                )
            """)

            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS ppc_rollback_snapshots (
                    id                     {serial},
                    suggestion_id          INTEGER NOT NULL,
                    campaign_state_before  {jsonb} NOT NULL,
                    expires_at             REAL NOT NULL
                )
            """)

            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS ppc_performance_tracking (
                    id              {serial},
                    suggestion_id   INTEGER NOT NULL,
                    measured_at     REAL NOT NULL,
                    metric_type     TEXT NOT NULL,
                    value           REAL,
                    baseline_value  REAL
                )
            """)

            # Append-only decision log (Week 1 of MVP Hardening Plan).
            # One row per approve/reject. Never updated, never deleted by app
            # code. The DNA page (Week 2) and the outcome observer (Week 3)
            # both read from this table. Backfill of pre-Week-1 decided rows
            # is handled by ppc_suggestions.backfill_seller_decisions.
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS seller_decisions (
                    id                  {serial},
                    connection_id       INTEGER NOT NULL,
                    suggestion_id       INTEGER,
                    suggestion_type     TEXT NOT NULL,
                    keyword_id          TEXT,
                    ad_group_id         TEXT,
                    campaign_id         TEXT,
                    current_value       {jsonb},
                    proposed_value      {jsonb},
                    estimated_impact    REAL,
                    confidence          TEXT,
                    decision            TEXT NOT NULL,
                    edit_payload        {jsonb},
                    decided_at          REAL NOT NULL,
                    observation_due_at  REAL
                )
            """)

            # Decision outcomes (Track B of 2026-05-09 sprint).
            # Populated by the outcome observer cron after observation_due_at
            # passes on a seller_decisions row. Records the baseline at
            # decision time and the observed metrics at observation time, so
            # the dashboard can say "metrics moved from X to Y" without ever
            # claiming "our decision worked" (correlation, not causation).
            #
            # copy_status drives the anti-overclaim test: dashboard render
            # paths must read this column and pick honest copy ("metrics
            # moved" or "no clear change") rather than asserting causation.
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS decision_outcomes (
                    id                   {serial},
                    seller_decisions_id  INTEGER NOT NULL,
                    connection_id        INTEGER NOT NULL,
                    suggestion_type      TEXT NOT NULL,
                    decision             TEXT NOT NULL,
                    baseline             {jsonb},
                    observed             {jsonb},
                    classification       TEXT NOT NULL,
                    observed_at          REAL NOT NULL,
                    copy_status          TEXT NOT NULL DEFAULT 'observed'
                )
            """)

            log.info("PPC tables initialized")
    except Exception as e:
        log.warning("PPC DB init failed (non-fatal): %s", e)


# ──────────────────────────────────────────────────────────────────────────
#  Token encryption (refresh tokens stored encrypted at rest)
# ──────────────────────────────────────────────────────────────────────────

def _get_fernet():
    """Lazy-init the Fernet cipher. Fails fast if key missing in production."""
    if not PPC_TOKEN_ENCRYPTION_KEY:
        raise RuntimeError(
            "PPC_TOKEN_ENCRYPTION_KEY not set. Generate with: "
            "python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\" and set on Railway."
        )
    from cryptography.fernet import Fernet
    return Fernet(PPC_TOKEN_ENCRYPTION_KEY.encode())


def encrypt_token(plaintext: str) -> str:
    """Encrypt an OAuth refresh token for storage in DB."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt an OAuth refresh token retrieved from DB."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()


# ──────────────────────────────────────────────────────────────────────────
#  OAuth flow (delegates to ppc_oauth module)
# ──────────────────────────────────────────────────────────────────────────

def build_authorization_url(state: str) -> str:
    """
    Build the Amazon Seller Central authorization URL.

    For Sandbox apps, the URL is on sellercentral.amazon.com with
    application_id query param. For production it's on the same host
    but the developer must be approved.
    """
    if not SP_API_APP_ID:
        raise RuntimeError("SP_API_APP_ID not configured")

    params = {
        "application_id":   SP_API_APP_ID,
        "state":            state,
        "version":          "beta",  # Sandbox; remove for production
        "redirect_uri":     SP_API_REDIRECT_URI,
    }
    return (
        "https://sellercentral.amazon.com/apps/authorize/consent?"
        + urlencode(params)
    )


def exchange_oauth_code(spapi_oauth_code: str) -> dict[str, Any]:
    """
    Exchange the one-time oauth_code for a long-lived refresh_token.

    Thin delegate to ppc_oauth.exchange_oauth_code so callers within
    ppc_agent can keep using the original symbol; new modules should
    import directly from ppc_oauth.
    """
    return ppc_oauth.exchange_oauth_code(spapi_oauth_code)


# ──────────────────────────────────────────────────────────────────────────
#  Snapshot fetcher (delegates to ppc_snapshot_fetcher module)
# ──────────────────────────────────────────────────────────────────────────

def fetch_ppc_snapshot(connection_id: int) -> dict[str, Any]:
    """
    Fetch latest PPC data for one connection. Stores in ppc_snapshots.

    Thin delegate to ppc_snapshot_fetcher.fetch_ppc_snapshot.
    """
    return ppc_snapshot_fetcher.fetch_ppc_snapshot(connection_id)


# ──────────────────────────────────────────────────────────────────────────
#  Suggestion generator (TODO week 4)
# ──────────────────────────────────────────────────────────────────────────

def generate_suggestions(connection_id: int) -> list[dict[str, Any]]:
    """
    Run the rule-based suggestion engine for one connection.

    Thin delegate to `ppc_suggestions.generate_suggestions` which loads the
    latest ppc_snapshots row per data_type, runs all five rules, persists the
    output to ppc_suggestions, and returns the list. LLM polish on top of
    rule output is week 5; rules are the floor we never drop below.
    """
    return ppc_suggestions.generate_suggestions(connection_id)


# ──────────────────────────────────────────────────────────────────────────
#  Suggestion applier (TODO week 6)
# ──────────────────────────────────────────────────────────────────────────

def apply_suggestion(suggestion_id: int, customer_id: str) -> dict[str, Any]:
    """Apply an approved suggestion. Returns API response."""
    raise NotImplementedError("Suggestion applier, week 6 of MVP plan")


# ──────────────────────────────────────────────────────────────────────────
#  Rollback (TODO week 4 manual, week 5 auto)
# ──────────────────────────────────────────────────────────────────────────

def rollback_suggestion(suggestion_id: int, customer_id: str,
                        reason: str = "user_requested") -> dict[str, Any]:
    """Rollback an applied suggestion to its prior state."""
    raise NotImplementedError("Rollback, week 4 of MVP plan")


# ──────────────────────────────────────────────────────────────────────────
#  Internal DB helpers
# ──────────────────────────────────────────────────────────────────────────

def _insert_connection(customer_id: str, seller_id: str,
                       marketplace_id: str,
                       refresh_token_plaintext: str) -> int:
    """
    Encrypt the refresh_token and insert a new amazon_connections row.

    Returns the new connection_id.
    """
    from server import _db, DATABASE_URL

    encrypted = encrypt_token(refresh_token_plaintext)
    now = time.time()

    with _db() as (cur, ph):
        if DATABASE_URL:
            # Postgres supports RETURNING for the new row id
            cur.execute(
                f"""
                INSERT INTO amazon_connections
                  (customer_id, seller_id, marketplace_id,
                   refresh_token_encrypted, connected_at, active)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, 1)
                RETURNING id
                """,
                (customer_id, seller_id, marketplace_id, encrypted, now),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0
        else:
            cur.execute(
                f"""
                INSERT INTO amazon_connections
                  (customer_id, seller_id, marketplace_id,
                   refresh_token_encrypted, connected_at, active)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, 1)
                """,
                (customer_id, seller_id, marketplace_id, encrypted, now),
            )
            return int(cur.lastrowid or 0)


def _list_customer_connections(customer_id: str) -> list[dict[str, Any]]:
    """Return non-sensitive details of a customer's amazon_connections rows."""
    from server import _db

    with _db() as (cur, ph):
        cur.execute(
            f"""
            SELECT id, seller_id, marketplace_id, ads_profile_id,
                   connected_at, last_synced_at, active
            FROM amazon_connections
            WHERE customer_id = {ph}
            ORDER BY connected_at DESC
            """,
            (customer_id,),
        )
        rows = cur.fetchall()

    out = []
    for r in rows:
        out.append({
            "id":              r[0],
            "seller_id":       r[1],
            "marketplace_id":  r[2],
            "ads_profile_id":  r[3],
            "connected_at":    r[4],
            "last_synced_at":  r[5],
            "active":          bool(r[6]),
        })
    return out


# ──────────────────────────────────────────────────────────────────────────
#  Flask routes, exposed at /ppc/*
# ──────────────────────────────────────────────────────────────────────────

bp = Blueprint("ppc", __name__, url_prefix="/ppc")


# ──────────────────────────────────────────────────────────────────────────
#  CSRF defense: same-origin guard for state-changing POSTs
# ──────────────────────────────────────────────────────────────────────────
#
# WTF_CSRF_CHECK_DEFAULT is False in this app, so every state-changing route
# has to opt in. The frontend posts via fetch() with credentials and a JSON
# body, but does not currently carry a CSRF token, so a header-based CSRF
# check would be a behaviour break. Origin / Referer checking gives us
# practical CSRF defense for browsers without that wiring:
#
# - If SITE_URL is not configured (local dev), the check is a no-op and the
#   request goes through. Tests inherit this.
# - In production (SITE_URL set), the request must come from the same origin.
#   Browsers that omit Origin (older ones, some IE-derived) fall back to
#   Referer.
# - GET endpoints are NOT decorated; only state-changing POSTs need this.

def _request_origin() -> str:
    """Return Origin or Referer (parsed to scheme://host[:port]) or empty."""
    origin = request.headers.get("Origin", "")
    if origin:
        return origin.rstrip("/")
    referer = request.headers.get("Referer", "")
    if not referer:
        return ""
    try:
        parsed = urlparse(referer)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    except Exception:
        pass
    return ""


def _resolve_site_url() -> str:
    """
    Source of truth for the configured production origin.

    server.py defines SITE_URL as a module-level value loaded once from
    os.getenv("SITE_URL") at import time. The Flask app does NOT mirror that
    value into app.config, so reading from current_app.config would silently
    return an empty string in production and cause the same-origin guard to
    no-op.

    We read directly from the server module (lazy-imported to avoid the
    ppc_agent -> server cycle at module load), and fall back to the env var
    if for some reason the import is unavailable.
    """
    try:
        import server as _server
        raw = getattr(_server, "SITE_URL", "") or ""
    except Exception:
        raw = os.getenv("SITE_URL", "") or ""
    return raw.rstrip("/")


def require_same_origin(f):
    """
    Reject cross-origin POSTs.

    If SITE_URL is empty (typical for local dev / tests / sandbox), the guard
    is a no-op so the request goes through. In production with SITE_URL set,
    a request whose Origin (or Referer) does not match SITE_URL is rejected
    with HTTP 403.

    Reads SITE_URL from `server.SITE_URL` (the production source), not from
    `current_app.config`, because this app keeps SITE_URL as a module-level
    Python value rather than a Flask config key.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        site_url = _resolve_site_url()
        if not site_url:
            return f(*args, **kwargs)

        origin = _request_origin()
        if origin and origin == site_url:
            return f(*args, **kwargs)

        log.warning(
            "ppc_origin_rejected path=%s origin=%s referer=%s",
            request.path, request.headers.get("Origin", ""),
            request.headers.get("Referer", ""),
        )
        return jsonify({"error": "bad_origin"}), 403
    return wrapper


@bp.route("/connect", methods=["POST"])
@require_same_origin
def ppc_connect():
    """
    Start the Amazon OAuth flow. Customer clicks "Connect Amazon Account"
    and we redirect them to Amazon's authorization page.

    Stage 1 of OAuth flow.
    """
    if not session.get("customer_id"):
        return jsonify({"error": "Not logged in"}), 401

    state = secrets.token_urlsafe(32)
    session["ppc_oauth_state"] = state
    try:
        url = build_authorization_url(state)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    return redirect(url)


@bp.route("/oauth/callback", methods=["GET"])
def ppc_oauth_callback():
    """
    Amazon redirects here after the seller approves consent.

    Validates state (CSRF), exchanges the one-time code for a refresh_token
    via ppc_oauth.exchange_oauth_code, encrypts it, and inserts a new
    amazon_connections row tied to the current customer_id. Then redirects
    to /ppc/dashboard.

    Stage 2 of OAuth flow.
    """
    customer_id = session.get("customer_id")
    if not customer_id:
        return jsonify({"error": "Not logged in"}), 401

    state              = request.args.get("state", "")
    spapi_oauth_code   = request.args.get("spapi_oauth_code", "")
    selling_partner_id = request.args.get("selling_partner_id", "")

    expected_state = session.pop("ppc_oauth_state", None)
    if not expected_state or state != expected_state:
        log.warning(
            "OAuth state mismatch for customer_id=%s expected=%s got=%s",
            customer_id, bool(expected_state), bool(state),
        )
        return jsonify({"error": "Invalid OAuth state (CSRF protection)"}), 400

    if not spapi_oauth_code:
        return jsonify({"error": "Missing oauth code"}), 400

    # Exchange the code for tokens. Errors here fall into 3 buckets, surfaced
    # to the customer with appropriate HTTP status:
    # - LWA invalid_grant (bad code, expired)         400
    # - LWA invalid_client (our credentials wrong)    503 (operator alert)
    # - network failure                                503 (transient)
    try:
        tokens = ppc_oauth.exchange_oauth_code(spapi_oauth_code)
    except ppc_oauth.LWAError as e:
        if e.lwa_error_code == "invalid_grant":
            log.warning("OAuth code exchange invalid_grant for customer_id=%s",
                        customer_id)
            return jsonify({
                "error": "Authorization code was rejected by Amazon. "
                         "Please try connecting again."
            }), 400
        log.error("OAuth code exchange failed for customer_id=%s: %s",
                  customer_id, e)
        return jsonify({
            "error": "Could not complete connection with Amazon. "
                     "Please try again or contact support."
        }), 503

    refresh_token = tokens.get("refresh_token", "")
    if not refresh_token:
        log.error("LWA returned 200 but no refresh_token for customer_id=%s",
                  customer_id)
        return jsonify({"error": "Unexpected response from Amazon"}), 503

    try:
        connection_id = _insert_connection(
            customer_id      = str(customer_id),
            seller_id        = selling_partner_id,
            marketplace_id   = "ATVPDKIKX0DER",  # US default; week 5 detects from API
            refresh_token_plaintext = refresh_token,
        )
    except RuntimeError as e:
        # Token encryption key not configured.
        log.error("Connection insert failed: %s", e)
        return jsonify({"error": "Server not configured for token storage"}), 503
    except Exception as e:
        log.exception("Connection insert failed: %s", e)
        return jsonify({"error": "Could not save the connection"}), 503

    log.info("Created amazon_connections id=%d for customer_id=%s seller_id=%s",
             connection_id, customer_id, selling_partner_id)

    return redirect("/ppc/dashboard")


@bp.route("/dashboard", methods=["GET"])
def ppc_dashboard():
    """
    Render the PPC dashboard.

    Shows connected accounts, money-found total, and pending suggestions
    grouped by suggestion_type. The view is read-only: approve/reject buttons
    only update DB status; the applier (week 6) is what actually pushes
    changes to Amazon.
    """
    customer_id = session.get("customer_id")
    if not customer_id:
        return redirect("/")

    connections = _list_customer_connections(str(customer_id))
    suggestions_by_connection: dict[int, list[dict[str, Any]]] = {}
    cards_by_connection: dict[int, list[dict[str, Any]]] = {}
    ranking_by_connection: dict[int, dict[str, Any]] = {}
    skipped_by_connection: dict[int, list[dict[str, Any]]] = {}
    approved_by_connection: dict[int, list[dict[str, Any]]] = {}
    savings_by_connection: dict[int, float] = {}
    growth_by_connection: dict[int, float] = {}
    breakdown_by_connection: dict[int, dict[str, float]] = {}
    latest_snapshot_at_by_connection: dict[int, float | None] = {}

    for c in connections:
        cid = c["id"]
        try:
            sugs = ppc_suggestions.list_pending_suggestions(cid)
        except Exception as e:
            log.warning("Loading suggestions failed for connection_id=%d: %s", cid, e)
            sugs = []
        suggestions_by_connection[cid] = sugs
        cards = ppc_suggestions.build_card_views(sugs)
        cards_by_connection[cid]       = cards
        # Composite-score rank: top-N + overflow. Banners below keep the
        # full list so $ totals don't change when overflow is collapsed.
        ranking_by_connection[cid]     = ppc_suggestions.rank_recommendations(cards)
        # Seller memory pill (Task 3): items the engine suppressed
        # because the seller rejected the same suggestion within the
        # last REJECT_MEMORY_WINDOW_DAYS. Defensive: failures yield [].
        try:
            skipped_by_connection[cid] = ppc_suggestions.list_memory_skipped(cid)
        except Exception as e:
            log.warning("list_memory_skipped failed for connection_id=%d: %s", cid, e)
            skipped_by_connection[cid] = []
        # Approved projection block (Task 4): rows the seller approved
        # in the last 14 days, with their captured baseline. Render-only;
        # nothing in this list has been pushed to Amazon. Defensive: a
        # query failure must not block the rest of the dashboard.
        try:
            approved_by_connection[cid] = (
                ppc_suggestions.list_recently_approved_suggestions(cid)
            )
        except Exception as e:
            log.warning(
                "list_recently_approved_suggestions failed for connection_id=%d: %s",
                cid, e,
            )
            approved_by_connection[cid] = []
        savings_by_connection[cid]     = ppc_suggestions.savings_total(sugs)
        growth_by_connection[cid]      = ppc_suggestions.growth_opportunity_total(sugs)
        breakdown_by_connection[cid]   = ppc_suggestions.money_found_breakdown(sugs)
        latest_snapshot_at_by_connection[cid] = _latest_snapshot_at(cid)

    return render_template(
        "ppc_dashboard.html",
        connections=connections,
        customer_id=customer_id,
        suggestions_by_connection=suggestions_by_connection,
        cards_by_connection=cards_by_connection,
        ranking_by_connection=ranking_by_connection,
        skipped_by_connection=skipped_by_connection,
        approved_by_connection=approved_by_connection,
        savings_by_connection=savings_by_connection,
        growth_by_connection=growth_by_connection,
        breakdown_by_connection=breakdown_by_connection,
        latest_snapshot_at_by_connection=latest_snapshot_at_by_connection,
    )


def _latest_snapshot_at(connection_id: int) -> float | None:
    """Return the fetched_at of the most recent ppc_snapshots row, or None."""
    from server import _db
    try:
        with _db() as (cur, ph):
            cur.execute(
                f"""
                SELECT MAX(fetched_at)
                FROM ppc_snapshots
                WHERE connection_id = {ph}
                """,
                (connection_id,),
            )
            row = cur.fetchone()
            if not row or row[0] is None:
                return None
            return float(row[0])
    except Exception as e:
        log.warning("latest_snapshot_at failed for connection_id=%d: %s", connection_id, e)
        return None


@bp.route("/connections", methods=["GET"])
def list_connections():
    """JSON list of the current customer's amazon_connections."""
    customer_id = session.get("customer_id")
    if not customer_id:
        return jsonify({"error": "Not logged in"}), 401
    return jsonify({"connections": _list_customer_connections(str(customer_id))})


@bp.route("/suggestions", methods=["GET"])
def list_suggestions():
    """
    JSON list of pending suggestions for the logged-in customer's connections.

    Format:
        {
          "money_found_total": 123.45,
          "by_connection": {
              "<connection_id>": [<suggestion_dict>, ...],
              ...
          }
        }
    """
    customer_id = session.get("customer_id")
    if not customer_id:
        return jsonify({"error": "Not logged in"}), 401

    connections = _list_customer_connections(str(customer_id))
    payload: dict[str, Any] = {"by_connection": {}, "money_found_total": 0.0}
    grand_total = 0.0
    for c in connections:
        cid = c["id"]
        sugs = ppc_suggestions.list_pending_suggestions(cid)
        payload["by_connection"][str(cid)] = sugs
        grand_total += ppc_suggestions.money_found_total(sugs)
    payload["money_found_total"] = round(grand_total, 2)
    return jsonify(payload)


@bp.route("/suggestions/refresh", methods=["POST"])
@require_same_origin
def refresh_suggestions():
    """
    Re-run the rule engine for every connection the logged-in customer owns.

    Read-only with respect to Amazon: it only reads ppc_snapshots and writes
    ppc_suggestions. No Ads API calls. Use this when the seller wants the
    dashboard to reflect the latest snapshot without waiting for the next
    scheduled cron pass.
    """
    customer_id = session.get("customer_id")
    if not customer_id:
        return jsonify({"error": "Not logged in"}), 401

    connections = _list_customer_connections(str(customer_id))
    summary = []
    grand_total = 0.0
    for c in connections:
        cid = c["id"]
        try:
            sugs = ppc_suggestions.generate_suggestions(cid)
        except Exception as e:
            log.exception("refresh_suggestions failed for connection_id=%d: %s", cid, e)
            summary.append({"connection_id": cid, "error": str(e), "count": 0})
            continue
        money = ppc_suggestions.money_found_total(sugs)
        grand_total += money
        summary.append({"connection_id": cid, "count": len(sugs), "money_found": money})

    return jsonify({
        "summary": summary,
        "money_found_total": round(grand_total, 2),
    })


@bp.route("/suggestions/<int:sid>/approve", methods=["POST"])
@require_same_origin
def approve_suggestion(sid: int):
    """
    Mark a suggestion as approved in DB and capture an approval baseline.

    Read-only with respect to Amazon: this endpoint only updates
    ppc_suggestions.status from 'pending' to 'approved_pending_apply' and
    writes a `_approval_baseline` JSON block into current_value. The
    applier (week 6) is the worker that picks approved rows and pushes
    changes via the Ads API. Until the applier exists, approved suggestions
    sit in the queue and nothing reaches Amazon.

    The baseline payload (Task 4 / Minimal Proof of Impact) lets the
    dashboard render projection language without overclaiming. See
    `ppc_suggestions.build_approval_baseline` for the contract.
    """
    customer_id = session.get("customer_id")
    if not customer_id:
        return jsonify({"error": "Not logged in"}), 401

    updated = _approve_suggestion_with_baseline(sid, str(customer_id))
    if updated == 0:
        return jsonify({"error": "Suggestion not found or not yours"}), 404
    return jsonify({"status": ppc_suggestions.STATUS_APPROVED_PENDING_APPLY, "suggestion_id": sid})


@bp.route("/suggestions/<int:sid>/reject", methods=["POST"])
@require_same_origin
def reject_suggestion(sid: int):
    """
    Mark a suggestion as rejected. Nothing is sent to Amazon. The seller's
    rejection is recorded in the seller_decisions append-only log so the
    per-seller memory layer (Week 2) and the outcome observer (Week 3) can
    read it.
    """
    customer_id = session.get("customer_id")
    if not customer_id:
        return jsonify({"error": "Not logged in"}), 401

    updated = _reject_suggestion_with_log(sid, str(customer_id))
    if updated == 0:
        return jsonify({"error": "Suggestion not found or not yours"}), 404
    return jsonify({"status": ppc_suggestions.STATUS_REJECTED, "suggestion_id": sid})


def _set_suggestion_status(suggestion_id: int, customer_id: str,
                           new_status: str) -> int:
    """
    Update ppc_suggestions.status, but only for a row that belongs to one of
    this customer's connections. Returns the number of rows updated (0 means
    not found or not authorised).

    Does not call Amazon. Does not enqueue the apply. The apply path is week 6.
    """
    from server import _db

    now = time.time()
    with _db() as (cur, ph):
        # The IN sub-select scopes the update to this customer's connections,
        # so a malicious user passing someone else's suggestion id sees a
        # 'not found' rather than mutating someone else's data.
        cur.execute(
            f"""
            UPDATE ppc_suggestions
            SET status = {ph}, decided_at = {ph}
            WHERE id = {ph}
              AND status = 'pending'
              AND connection_id IN (
                  SELECT id FROM amazon_connections WHERE customer_id = {ph}
              )
            """,
            (new_status, now, suggestion_id, customer_id),
        )
        return int(cur.rowcount or 0)


def _approve_suggestion_with_baseline(suggestion_id: int,
                                       customer_id: str) -> int:
    """
    Approve a pending suggestion: flip status to approved_pending_apply,
    stamp decided_at, write `_approval_baseline` into current_value
    (Task 4), and append a row to seller_decisions (Week 1 of Hardening
    Plan / Task 6) so Adaptive Memory and Outcome Observer can read it.

    Tenant-scoped: cross-tenant attempts return 0 (route -> 404).
    Race-safe: the UPDATE re-checks `status = 'pending'`, so two
    concurrent approves can't both succeed.

    Does NOT call Amazon. The applier (week 6) is unrelated.

    The seller_decisions log INSERT is best-effort: if it fails, the
    status flip already happened and a warning is logged. We never
    block the user-facing path on logging.
    """
    from server import _db

    now = time.time()
    with _db() as (cur, ph):
        cur.execute(
            f"""
            SELECT current_value, proposed_value, estimated_savings,
                   suggestion_type, keyword_id, ad_group_id, campaign_id,
                   confidence
            FROM ppc_suggestions
            WHERE id = {ph}
              AND status = 'pending'
              AND connection_id IN (
                  SELECT id FROM amazon_connections WHERE customer_id = {ph}
              )
            """,
            (suggestion_id, customer_id),
        )
        row = cur.fetchone()
        if not row:
            return 0

        cv = ppc_suggestions._maybe_load_json(row[0])
        pv = ppc_suggestions._maybe_load_json(row[1])
        est_impact = float(row[2] or 0.0)
        suggestion_type = row[3] or ""
        keyword_id      = row[4]
        ad_group_id     = row[5]
        campaign_id     = row[6]
        confidence      = row[7]

        baseline = ppc_suggestions.build_approval_baseline(
            cv, pv, est_impact, now,
        )
        cv_with_baseline = dict(cv or {})
        cv_with_baseline["_approval_baseline"] = baseline
        cv_json = json.dumps(cv_with_baseline)

        cur.execute(
            f"""
            UPDATE ppc_suggestions
            SET status = {ph}, decided_at = {ph}, current_value = {ph}
            WHERE id = {ph}
              AND status = 'pending'
              AND connection_id IN (
                  SELECT id FROM amazon_connections WHERE customer_id = {ph}
              )
            """,
            (
                ppc_suggestions.STATUS_APPROVED_PENDING_APPLY,
                now,
                cv_json,
                suggestion_id,
                customer_id,
            ),
        )
        rowcount = int(cur.rowcount or 0)
        if rowcount == 0:
            # Race: another approve won between SELECT and UPDATE. Don't log.
            return 0

        # Resolve connection_id for the log row. We have customer_id +
        # suggestion_id; rather than another scoped subquery, look up the
        # row directly (we just confirmed it exists).
        cur.execute(
            f"SELECT connection_id FROM ppc_suggestions WHERE id = {ph}",
            (suggestion_id,),
        )
        cid_row = cur.fetchone()
        connection_id = int(cid_row[0]) if cid_row and cid_row[0] is not None else None

    # Log outside the transaction holding the suggestions UPDATE.
    # Best-effort: any failure here (DB outage, monkey-patched function in
    # tests, etc.) must not bubble up to the route, since the status flip
    # already succeeded.
    if connection_id is not None:
        try:
            ppc_suggestions.log_decision(
                connection_id    = connection_id,
                suggestion_id    = suggestion_id,
                suggestion_type  = suggestion_type,
                decision         = "approved",
                decided_at       = now,
                keyword_id       = keyword_id,
                ad_group_id      = ad_group_id,
                campaign_id      = campaign_id,
                current_value    = cv_with_baseline,
                proposed_value   = pv,
                estimated_impact = est_impact,
                confidence       = confidence,
            )
        except Exception as e:
            log.warning(
                "log_decision (approved) failed for sid=%d cid=%d: %s",
                suggestion_id, connection_id, e,
            )
    return rowcount


def _reject_suggestion_with_log(suggestion_id: int,
                                  customer_id: str) -> int:
    """
    Reject a pending suggestion: flip status to 'rejected', stamp
    decided_at, append a row to seller_decisions for memory + outcomes.

    Mirrors `_approve_suggestion_with_baseline` structure for consistency.
    Does NOT modify current_value (no baseline on rejection); the
    seller_decisions row is the immutable record.

    Tenant-scoped, race-safe, never calls Amazon.

    Log INSERT is best-effort.
    """
    from server import _db

    now = time.time()
    with _db() as (cur, ph):
        cur.execute(
            f"""
            SELECT current_value, proposed_value, estimated_savings,
                   suggestion_type, keyword_id, ad_group_id, campaign_id,
                   confidence
            FROM ppc_suggestions
            WHERE id = {ph}
              AND status = 'pending'
              AND connection_id IN (
                  SELECT id FROM amazon_connections WHERE customer_id = {ph}
              )
            """,
            (suggestion_id, customer_id),
        )
        row = cur.fetchone()
        if not row:
            return 0

        cv = ppc_suggestions._maybe_load_json(row[0])
        pv = ppc_suggestions._maybe_load_json(row[1])
        est_impact = float(row[2] or 0.0)
        suggestion_type = row[3] or ""
        keyword_id      = row[4]
        ad_group_id     = row[5]
        campaign_id     = row[6]
        confidence      = row[7]

        cur.execute(
            f"""
            UPDATE ppc_suggestions
            SET status = {ph}, decided_at = {ph}
            WHERE id = {ph}
              AND status = 'pending'
              AND connection_id IN (
                  SELECT id FROM amazon_connections WHERE customer_id = {ph}
              )
            """,
            (
                ppc_suggestions.STATUS_REJECTED,
                now,
                suggestion_id,
                customer_id,
            ),
        )
        rowcount = int(cur.rowcount or 0)
        if rowcount == 0:
            return 0

        cur.execute(
            f"SELECT connection_id FROM ppc_suggestions WHERE id = {ph}",
            (suggestion_id,),
        )
        cid_row = cur.fetchone()
        connection_id = int(cid_row[0]) if cid_row and cid_row[0] is not None else None

    if connection_id is not None:
        try:
            ppc_suggestions.log_decision(
                connection_id    = connection_id,
                suggestion_id    = suggestion_id,
                suggestion_type  = suggestion_type,
                decision         = "rejected",
                decided_at       = now,
                keyword_id       = keyword_id,
                ad_group_id      = ad_group_id,
                campaign_id      = campaign_id,
                current_value    = cv,
                proposed_value   = pv,
                estimated_impact = est_impact,
                confidence       = confidence,
            )
        except Exception as e:
            log.warning(
                "log_decision (rejected) failed for sid=%d cid=%d: %s",
                suggestion_id, connection_id, e,
            )
    return rowcount


@bp.route("/suggestions/<int:sid>/rollback", methods=["POST"])
@require_same_origin
def rollback(sid: int):
    """Customer clicks Rollback on an applied suggestion."""
    if not session.get("customer_id"):
        return jsonify({"error": "Not logged in"}), 401
    return jsonify({"status": "stub", "suggestion_id": sid})


# ──────────────────────────────────────────────────────────────────────────
#  CSV upload path (no Amazon connection required)
# ──────────────────────────────────────────────────────────────────────────
#
# Lets a seller upload their Sponsored Products Search Term Report CSV
# (downloaded manually from Seller Central) and run the same suggestion
# engine that the live OAuth path runs. Approval-first by construction:
# - no DB write
# - no Ads API call
# - no per-row Approve button (there's nothing to push to Amazon, so a
#   button labelled Approve would be misleading)
#
# The page exists so prospects can evaluate suggestion quality before
# committing to OAuth, and so existing free-tier sellers without
# Production approval still get value.

CSV_MAX_UPLOAD_BYTES = 8 * 1024 * 1024   # 8 MB. Larger reports are rare
                                         # and silently truncating is worse
                                         # than a clear 413.

# First few bytes of common file types sellers might upload by mistake.
# We catch them before passing to the CSV parser so the error message can
# tell them what we think they uploaded instead of "unrecognised columns".
_NON_CSV_MAGIC_BYTES: tuple[tuple[bytes, str], ...] = (
    (b"%PDF",                          "a PDF"),
    (b"PK\x03\x04",                    "a ZIP / Excel file (.xlsx)"),
    (b"\x89PNG",                       "a PNG image"),
    (b"\xff\xd8\xff",                  "a JPEG image"),
    (b"GIF87a",                        "a GIF image"),
    (b"GIF89a",                        "a GIF image"),
    (b"\xd0\xcf\x11\xe0",              "a legacy Excel file (.xls)"),
)


def _detect_non_csv_upload(raw: bytes) -> str | None:
    """
    Return a short label ("a PDF", etc) if the bytes look like a known
    non-CSV file format. Returns None otherwise. Only inspects the first
    8 bytes, which is enough to identify every format we care about.
    """
    head = raw[:8]
    for magic, label in _NON_CSV_MAGIC_BYTES:
        if head.startswith(magic):
            return label
    return None


# A small synthetic Sponsored Products Search Term Report. Used by
# /ppc/csv/sample.csv so prospects can download a working example and see
# what columns the parser needs. The figures are deliberately obviously
# fake (round numbers, "demo-" placeholders) so a screenshot of the
# rendered findings is unambiguous in marketing material. Every row is
# tuned so the engine fires at least one rule per kind:
#   - row 1: spend_no_sales      ($9 spend, 12 clicks, 0 sales)
#   - row 2: high_acos           ($35 cost / $40 sales -> 87% ACOS)
#   - row 3: scale_profitable    ($55 sales, 6% ACOS, 800 imps -> uplift)
#   - row 4: promote_search_term ($60 sales on a search-term not yet a kw)
_SAMPLE_CSV_BODY = (
    "Date,Campaign Name,Ad Group Name,Targeting,Match Type,"
    "Customer Search Term,Impressions,Clicks,Spend,"
    "7 Day Total Sales,7 Day Total Orders (#)\n"
    "2026-04-01,Demo Campaign,Demo AG,demo no sales,broad,demo no-sales term,820,12,$9.00,$0.00,0\n"
    "2026-04-02,Demo Campaign,Demo AG,demo high acos,phrase,demo high-acos term,1500,30,$35.00,$40.00,2\n"
    "2026-04-03,Demo Campaign,Demo AG,demo scale,exact,demo scale term,800,18,$3.50,$55.00,5\n"
    "2026-04-04,Demo Campaign,Demo AG,demo parent,broad,demo promotable term,950,16,$8.00,$60.00,4\n"
)


@bp.route("/csv", methods=["GET"])
def csv_upload_form():
    """Render the upload page. Read-only; never writes anything."""
    return render_template(
        "ppc_csv.html",
        suggestions=None,
        savings=0.0,
        growth=0.0,
        breakdown={},
        ingest_summary=None,
        error=None,
    )


@bp.route("/csv/sample.csv", methods=["GET"])
def csv_sample_download():
    """
    Serve a small synthetic Sponsored Products Search Term Report CSV.

    Why this exists: prospects landing on /ppc/csv often have not yet
    pulled their own report, and the seller Central export path (Reports
    > Advertising Reports > Search Term) takes 10-30 minutes to land in
    the seller's inbox. The sample lets them see exactly what columns
    the parser expects and lets them click through to a working set of
    findings without waiting for Amazon.

    Synthetic only. Contains no real seller data. Returned with a
    Content-Disposition header so browsers download instead of rendering.
    """
    return current_app.response_class(
        _SAMPLE_CSV_BODY,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
                'attachment; filename="asininsight-sample-search-term.csv"',
            "Cache-Control": "public, max-age=3600",
        },
    )


@bp.route("/csv/analyze", methods=["POST"])
@require_same_origin
def csv_analyze():
    """
    Parse uploaded CSV in memory, run analyze(), render results.

    Form fields:
        file (required): the search-term CSV file.

    Failure modes (all return the upload page with an inline error):
        - no file part            400
        - file too large          413
        - unrecognised CSV        422

    Success: 200 with the suggestions list, savings/growth totals, and
    a per-data_type ingest summary so the seller can see what was parsed.
    """
    if "file" not in request.files:
        return render_template(
            "ppc_csv.html",
            suggestions=None, savings=0.0, growth=0.0, breakdown={},
            ingest_summary=None,
            error="No file was attached. Choose a CSV and try again.",
        ), 400

    upload = request.files["file"]
    if not upload or not upload.filename:
        return render_template(
            "ppc_csv.html",
            suggestions=None, savings=0.0, growth=0.0, breakdown={},
            ingest_summary=None,
            error="The uploaded file was empty.",
        ), 400

    # Cheap upper bound: peek at content_length where the browser supplies
    # it. This is advisory; the real cap is enforced by reading at most
    # CSV_MAX_UPLOAD_BYTES below.
    content_length = request.content_length or 0
    if content_length and content_length > CSV_MAX_UPLOAD_BYTES:
        return render_template(
            "ppc_csv.html",
            suggestions=None, savings=0.0, growth=0.0, breakdown={},
            ingest_summary=None,
            error=(
                f"File is larger than {CSV_MAX_UPLOAD_BYTES // (1024 * 1024)} MB. "
                "Re-export with a narrower date range and try again."
            ),
        ), 413

    raw = upload.read(CSV_MAX_UPLOAD_BYTES + 1)
    if len(raw) > CSV_MAX_UPLOAD_BYTES:
        return render_template(
            "ppc_csv.html",
            suggestions=None, savings=0.0, growth=0.0, breakdown={},
            ingest_summary=None,
            error=(
                f"File is larger than {CSV_MAX_UPLOAD_BYTES // (1024 * 1024)} MB. "
                "Re-export with a narrower date range and try again."
            ),
        ), 413

    # Catch the common "wrong file" cases before we burn cycles on a CSV
    # parse. The decode-with-errors='replace' path below would technically
    # accept any bytes, but the resulting "unrecognised columns" error
    # would not tell the seller what they actually did wrong.
    non_csv = _detect_non_csv_upload(raw if isinstance(raw, bytes) else b"")
    if non_csv is not None:
        return render_template(
            "ppc_csv.html",
            suggestions=None, savings=0.0, growth=0.0, breakdown={},
            ingest_summary=None,
            error=(
                f"That looks like {non_csv}, not a CSV. Re-export the "
                "Search Term report from Seller Central, choose the CSV "
                "format, and upload that file."
            ),
        ), 415

    if isinstance(raw, bytes):
        text = raw.decode("utf-8-sig", errors="replace")
    else:
        text = str(raw)

    try:
        snapshot = ppc_csv_ingest.build_snapshot_from_csv(text)
    except ppc_csv_ingest.CSVIngestError as e:
        return render_template(
            "ppc_csv.html",
            suggestions=None, savings=0.0, growth=0.0, breakdown={},
            ingest_summary=None,
            error=str(e),
        ), 422
    except Exception:
        log.exception("csv_analyze unexpected failure")
        return render_template(
            "ppc_csv.html",
            suggestions=None, savings=0.0, growth=0.0, breakdown={},
            ingest_summary=None,
            error=(
                "Could not parse the file. Make sure it is a CSV exported "
                "from Seller Central > Reports > Advertising Reports > "
                "Search Term, not a screenshot or a PDF."
            ),
        ), 422

    suggestions = ppc_suggestions.analyze(snapshot)
    # CSV path is intentionally read-only: the suggestion list returned
    # here is rendered to the page only; nothing is written to
    # ppc_suggestions, ppc_audit_log, or anywhere else.
    cards     = ppc_suggestions.build_card_views(suggestions)
    ranking   = ppc_suggestions.rank_recommendations(cards)
    savings   = ppc_suggestions.savings_total(suggestions)
    growth    = ppc_suggestions.growth_opportunity_total(suggestions)
    breakdown = ppc_suggestions.money_found_breakdown(suggestions)
    ingest    = ppc_csv_ingest.summarise_ingest(snapshot)

    # Detect our own sample re-upload so we can flag the rendered findings
    # as demo data. Both signals must agree: filename matches the sample
    # asset AND the body contains the synthetic-only marker text. The
    # filename alone is too easy to spoof; the marker alone would
    # false-positive on a real seller who happens to use "asininsight
    # demo-marker" in a keyword (vanishingly unlikely). Together they're
    # tight enough for an honesty banner.
    is_sample = (
        (upload.filename or "").lower()
        == "asininsight-sample-search-term.csv"
        and "demo no-sales term" in text
    )

    log.info(
        "csv_analyze: rows search_terms=%d keywords=%d ad_groups=%d "
        "campaigns=%d -> %d suggestions, savings=$%.2f growth=$%.2f sample=%s",
        ingest.get("search_terms", 0), ingest.get("keywords", 0),
        ingest.get("ad_groups", 0),    ingest.get("campaigns", 0),
        len(suggestions), savings, growth, is_sample,
    )

    return render_template(
        "ppc_csv.html",
        suggestions=suggestions,
        cards=cards,
        ranking=ranking,
        savings=savings,
        growth=growth,
        breakdown=breakdown,
        ingest_summary=ingest,
        is_sample=is_sample,
        error=None,
    )


# ──────────────────────────────────────────────────────────────────────────
#  Admin: ppc_snapshots retention
# ──────────────────────────────────────────────────────────────────────────
#
# The retention worker (`ppc_snapshot_fetcher.run_retention`) deletes raw
# snapshot rows older than the configured window (default 90 days). The
# canonical caller is a Railway cron once per day. Until that cron is
# wired, this admin endpoint lets the founder trigger a run manually from
# a logged-in operator session.
#
# Authorisation: gated on a header `X-Admin-Token` matching env var
# `PPC_ADMIN_TOKEN`. If the env var is empty (typical for local dev) the
# endpoint refuses to run, so a misconfigured prod instance never exposes
# bulk DELETE to the public.

PPC_ADMIN_TOKEN = os.getenv("PPC_ADMIN_TOKEN", "")
DEFAULT_RETENTION_DAYS = 90


# ──────────────────────────────────────────────────────────────────────────
#  Admin: BSA Agent Policy kill switch (Week 1 of MVP Hardening Plan)
# ──────────────────────────────────────────────────────────────────────────
#
# Per Amazon's BSA Agent Policy (effective 2026-03-04, enforcement early June
# 2026): "All AI agents must ... cease access immediately if Amazon requests
# it." This admin endpoint exposes a single-call disconnect-all. When invoked:
#
#   - All `amazon_connections.active` rows are flipped to 0 atomically.
#   - The encrypted refresh_token is preserved (we don't delete it; killing
#     access does not require destroying the seller's reconnect path).
#   - A line is appended to ppc_audit_log with action='kill_switch' and
#     performed_by='admin' so the action is forensic-traceable.
#
# Authorisation: same `X-Admin-Token` gate as the retention endpoint. If
# `PPC_ADMIN_TOKEN` is empty, the endpoint refuses to run (503), so a
# misconfigured production instance cannot be triggered by a cold call.
#
# This is the BSA "kill switch" referenced in the agent self-identification
# string. It is exposed and code-backed; not a phrase in marketing.

def _kill_switch_disconnect_all() -> dict[str, int]:
    """
    Flip every amazon_connections row to inactive. Idempotent: re-running
    on an already-killed system updates 0 rows.

    Returns: {"deactivated": N}.

    Defensive: any unexpected error is re-raised so the caller (admin route
    or cron) can see the failure and decide what to do. We do not silently
    swallow.
    """
    from server import _db

    now = time.time()
    with _db() as (cur, ph):
        cur.execute(
            f"""
            UPDATE amazon_connections
            SET active = 0, last_synced_at = {ph}
            WHERE active = 1
            """,
            (now,),
        )
        deactivated = int(cur.rowcount or 0)

        # Forensic audit row. ppc_audit_log already exists for apply
        # operations; reusing it keeps audit history in one place.
        try:
            cur.execute(
                f"""
                INSERT INTO ppc_audit_log
                    (connection_id, suggestion_id, action,
                     before_value, after_value, api_response,
                     performed_at, performed_by)
                VALUES
                    ({ph}, NULL, {ph},
                     NULL, NULL, NULL,
                     {ph}, {ph})
                """,
                (
                    0,                              # connection_id 0 = global
                    "kill_switch",
                    now,
                    "admin",
                ),
            )
        except Exception as e:
            # Audit insert is best-effort. Do not undo the disconnect.
            log.warning("kill_switch audit insert failed: %s", e)

    log.warning(
        "BSA kill switch invoked: deactivated %d connections at %s",
        deactivated, now,
    )
    return {"deactivated": deactivated}


@bp.route("/admin/kill_switch/run", methods=["POST"])
@require_same_origin
def admin_kill_switch():
    """
    BSA Agent Policy kill switch. Disconnects all active Amazon connections
    in one call. Returns {"deactivated": N}.

    Authorisation: requires `X-Admin-Token` header matching env var
    `PPC_ADMIN_TOKEN`. If `PPC_ADMIN_TOKEN` is empty, returns 503.

    Read-only with respect to Amazon: no Ads API call. The kill switch is
    a local state change; the seller's Amazon account is not modified.
    """
    if not PPC_ADMIN_TOKEN:
        return jsonify({"error": "Kill switch admin not configured on this instance"}), 503

    sent_token = request.headers.get("X-Admin-Token", "")
    if not secrets.compare_digest(sent_token, PPC_ADMIN_TOKEN):
        log.warning("ppc_admin_kill_switch rejected: bad or missing X-Admin-Token")
        return jsonify({"error": "forbidden"}), 403

    try:
        result = _kill_switch_disconnect_all()
    except Exception as e:
        log.exception("admin_kill_switch failed: %s", e)
        return jsonify({"error": "kill switch failed"}), 500

    return jsonify(result)


# ──────────────────────────────────────────────────────────────────────────
#  Decision Audit page (Track B 2026-05-09 sprint)
# ──────────────────────────────────────────────────────────────────────────
#
# /ppc/audit shows a chronological log of every approve/reject decision
# the seller has made on this connection, with the baseline that was
# captured at decision time and the observed outcome (if the observer
# has run on that decision).
#
# /ppc/audit/export.csv produces a tax/agency-grade CSV of the same data.
#
# Anti-overclaim: the page never says "our decision worked." Outcome
# language is gated by classification + copy_status from
# decision_outcomes. Pending observations show "Awaiting observation
# window" rather than implying success.

@bp.route("/audit", methods=["GET"])
def ppc_audit():
    """
    Decision audit page. Shows every approve/reject the seller has made,
    plus observed outcomes when the observer has caught up to them.
    """
    customer_id = session.get("customer_id")
    if not customer_id:
        return redirect("/")

    connections = _list_customer_connections(str(customer_id))
    decisions_by_connection: dict[int, list[dict[str, Any]]] = {}
    counts_by_connection:    dict[int, dict[str, int]] = {}

    for c in connections:
        cid = c["id"]
        try:
            rows = ppc_suggestions.list_decisions_with_outcomes(cid)
        except Exception as e:
            log.warning("list_decisions_with_outcomes failed for cid=%d: %s", cid, e)
            rows = []
        decisions_by_connection[cid] = rows
        counts_by_connection[cid] = _audit_counts(rows)

    return render_template(
        "ppc_audit.html",
        connections=connections,
        decisions_by_connection=decisions_by_connection,
        counts_by_connection=counts_by_connection,
        classification_label=ppc_suggestions.audit_classification_label,
    )


def _audit_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Tally counts per category for the page header."""
    counts = {
        "total":              len(rows),
        "approved":           0,
        "rejected":           0,
        "metrics_moved_better": 0,
        "metrics_moved_worse":  0,
        "no_change":          0,
        "pending_observation": 0,
    }
    for r in rows:
        if r["decision"] == "approved":
            counts["approved"] += 1
        elif r["decision"] == "rejected":
            counts["rejected"] += 1
        cls = r.get("classification") or "pending_observation"
        if cls in counts:
            counts[cls] += 1
    return counts


@bp.route("/audit/export.csv", methods=["GET"])
def ppc_audit_export_csv():
    """
    CSV export of the decision audit log. Auditor-/accountant-grade:
    one row per decision, with baseline and observed metrics, and a
    footer line that documents the anti-overclaim posture.

    Authentication: customer must be logged in. We export only their
    connections.
    """
    customer_id = session.get("customer_id")
    if not customer_id:
        return jsonify({"error": "not authenticated"}), 401

    connections = _list_customer_connections(str(customer_id))
    if not connections:
        return jsonify({"error": "no connected accounts"}), 404

    import csv
    import io
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "decision_id", "connection_id", "decided_at_iso", "suggestion_type",
        "decision", "keyword_id", "keyword_label", "ad_group_id",
        "campaign_id", "estimated_impact_usd", "confidence",
        "baseline_cost_30d_usd", "baseline_sales_30d_usd",
        "baseline_clicks_30d", "baseline_acos_30d",
        "proposed_change", "observation_due_at_iso",
        "observed_at_iso", "observed_cost_30d_usd",
        "observed_sales_30d_usd", "observed_clicks_30d",
        "classification", "copy_status",
    ])

    total_rows = 0
    for c in connections:
        cid = c["id"]
        try:
            rows = ppc_suggestions.list_decisions_with_outcomes(cid, limit=10000)
        except Exception as e:
            log.warning("audit_export_csv: list failed for cid=%d: %s", cid, e)
            rows = []
        for r in rows:
            writer.writerow([
                r["id"], cid, r["decided_at_iso"], r["suggestion_type"],
                r["decision"], r["keyword_id"], r["keyword_label"],
                r["ad_group_id"], r["campaign_id"],
                f"{r['estimated_impact']:.2f}", r["confidence"],
                f"{r['baseline_cost_30d']:.2f}", f"{r['baseline_sales_30d']:.2f}",
                r["baseline_clicks_30d"],
                f"{r['baseline_acos_30d']:.4f}" if r["baseline_acos_30d"] is not None else "",
                r["proposed_summary"], r["observation_due_at_iso"],
                r["observed_at_iso"],
                f"{r['observed_cost_30d']:.2f}" if r["observed_cost_30d"] is not None else "",
                f"{r['observed_sales_30d']:.2f}" if r["observed_sales_30d"] is not None else "",
                r["observed_clicks_30d"] if r["observed_clicks_30d"] is not None else "",
                r["classification"], r["copy_status"],
            ])
            total_rows += 1

    # Anti-overclaim footer. CSV consumers (accountants, auditors)
    # should read this if they import the file.
    writer.writerow([])
    writer.writerow([
        "# ASINInsight does not write to Amazon. All proposed changes are queued",
        "# for the seller to apply manually. 'classification' describes how the",
        "# observed metrics moved relative to baseline, never causation.",
    ])

    csv_bytes = buf.getvalue().encode("utf-8-sig")  # BOM for Excel
    from flask import Response
    headers = {
        "Content-Disposition": 'attachment; filename="asininsight_decision_audit.csv"',
        "Content-Type": "text/csv; charset=utf-8",
    }
    log.info("audit_export_csv served %d rows for customer_id=%s", total_rows, customer_id)
    return Response(csv_bytes, headers=headers)


# ──────────────────────────────────────────────────────────────────────────
#  Outcome observer (Track B 2026-05-09 sprint)
# ──────────────────────────────────────────────────────────────────────────
#
# Reads `seller_decisions` rows whose observation_due_at has passed and
# which do not yet have a matching decision_outcomes row, locates the
# same keyword in the latest snapshot, and inserts a classified outcome.
#
# Honest scope:
#   - Read-only with respect to Amazon. No Ads API call.
#   - Deterministic: classify_outcome is pure; this function only
#     handles I/O.
#   - Idempotent: re-running on the same data does not create duplicates.
#   - Anti-overclaim: every inserted row has a copy_status that drives
#     the dashboard render path to use honest "metrics moved" language.

OBSERVATION_DEFAULT_LOOKBACK_DAYS = 14


def _build_observed_from_keyword(kw_row: dict[str, Any] | None) -> dict[str, Any]:
    """
    Map a snapshot keyword row to the dict shape classify_outcome expects.
    Pure: no DB, no clock. Returns {} if kw_row is None.

    Field map: keyword rows in `ppc_snapshots` use Amazon's wire-format
    field names ('cost', 'sales30d', 'clicks', 'impressions',
    'purchases30d'). The classifier and the approval baseline use the
    canonical underscored names ('cost_30d', 'sales_30d', etc.).
    """
    if not kw_row:
        return {}
    return {
        "cost_30d":        float(kw_row.get("cost", 0) or 0),
        "sales_30d":       float(kw_row.get("sales30d", 0) or 0),
        "clicks_30d":      int(kw_row.get("clicks", 0) or 0),
        "impressions_30d": int(kw_row.get("impressions", 0) or 0),
        "orders_30d":      int(kw_row.get("purchases30d", 0) or 0),
    }


def _extract_baseline_from_current_value(cv: Any) -> dict[str, Any]:
    """
    `current_value` may carry an `_approval_baseline` envelope written at
    approval time (see ppc_suggestions.build_approval_baseline). Return
    that envelope if present, else fall back to the cv itself which holds
    the fields at decision time for older rows.
    """
    cv_dict = ppc_suggestions._maybe_load_json(cv) if cv is not None else {}
    if not isinstance(cv_dict, dict):
        return {}
    baseline = cv_dict.get("_approval_baseline")
    if isinstance(baseline, dict) and baseline:
        return dict(baseline)
    # Fallback: fields directly on current_value. For pre-baseline rows
    # we still try to classify using whatever metric fields we have.
    return {
        k: v for k, v in cv_dict.items()
        if k in ("cost_30d", "sales_30d", "clicks_30d",
                 "impressions_30d", "orders_30d", "acos_30d")
    }


def run_outcome_observer(connection_id: int,
                          db_ctx_factory=None,
                          now: float | None = None,
                          lookback_days: int = OBSERVATION_DEFAULT_LOOKBACK_DAYS,
                          ) -> dict[str, int]:
    """
    Observe due seller_decisions rows and write decision_outcomes.

    Args:
        connection_id:    Amazon connection to observe.
        db_ctx_factory:   _db context manager from server.py. Required.
        now:              epoch seconds. Defaults to time.time().
        lookback_days:    informational only; observation_due_at is the
                          gate. Reserved for future eager-trigger logic.

    Returns:
        {
          "observed":           count of new decision_outcomes rows inserted
          "skipped_no_kw":      decisions whose keyword is missing from snapshot
          "skipped_existing":   decisions that already had an outcomes row
          "skipped_not_due":    not used here (observation_due_at gates query)
          "errors":             count of rows that hit unexpected errors
        }

    Defensive: any single-row error logs and continues to the next row.
    A snapshot load failure aborts the run with errors=1 and a logged
    exception, but never raises to the caller.
    """
    if db_ctx_factory is None:
        from server import _db
        db_ctx_factory = _db
    if now is None:
        now = time.time()

    stats = {
        "observed":         0,
        "skipped_no_kw":    0,
        "skipped_existing": 0,
        "skipped_not_due":  0,
        "errors":           0,
    }

    # 1. Load latest snapshot keywords for the connection.
    try:
        snapshots = ppc_suggestions._load_latest_snapshots(connection_id, db_ctx_factory)
    except Exception as e:
        log.warning("run_outcome_observer: snapshot load failed for cid=%d: %s", connection_id, e)
        stats["errors"] = 1
        return stats

    keywords_by_id: dict[str, dict[str, Any]] = {}
    for kw in snapshots.get("keywords", []) or []:
        kid = kw.get("keywordId")
        if kid:
            keywords_by_id[str(kid)] = kw

    # 2. Load due seller_decisions rows that don't yet have an outcomes row.
    try:
        with db_ctx_factory() as (cur, ph):
            cur.execute(
                f"""
                SELECT sd.id, sd.suggestion_type, sd.keyword_id, sd.decision,
                       sd.current_value, sd.proposed_value, sd.estimated_impact,
                       sd.decided_at, sd.observation_due_at
                FROM seller_decisions sd
                WHERE sd.connection_id = {ph}
                  AND sd.observation_due_at IS NOT NULL
                  AND sd.observation_due_at <= {ph}
                  AND NOT EXISTS (
                      SELECT 1 FROM decision_outcomes outr
                      WHERE outr.seller_decisions_id = sd.id
                  )
                ORDER BY sd.observation_due_at ASC
                """,
                (connection_id, now),
            )
            due_rows = cur.fetchall() or []
    except Exception as e:
        log.warning("run_outcome_observer: SELECT failed for cid=%d: %s", connection_id, e)
        stats["errors"] = 1
        return stats

    if not due_rows:
        return stats

    # 3. Classify and insert per row.
    for row in due_rows:
        sd_id, stype, keyword_id, decision, cv, pv, est_impact, decided_at, obs_due = row
        try:
            baseline = _extract_baseline_from_current_value(cv)
            kw = keywords_by_id.get(str(keyword_id)) if keyword_id else None
            if kw is None:
                # Keyword no longer in snapshot (paused, deleted, or
                # different ad-group). We still record an outcome row
                # marked appropriately, so the audit page can show
                # "no longer in snapshot" honestly.
                observed_metrics = {}
                outcome = {
                    "classification": "inconclusive",
                    "summary": "Keyword no longer present in latest snapshot.",
                    "metrics_delta": {},
                    "copy_status": "observed",
                }
                stats["skipped_no_kw"] += 1
            else:
                observed_metrics = _build_observed_from_keyword(kw)
                outcome = ppc_suggestions.classify_outcome(
                    suggestion_type=stype,
                    decision=decision,
                    baseline=baseline,
                    observed=observed_metrics,
                )

            with db_ctx_factory() as (cur, ph):
                cur.execute(
                    f"""
                    INSERT INTO decision_outcomes
                        (seller_decisions_id, connection_id, suggestion_type,
                         decision, baseline, observed, classification,
                         observed_at, copy_status)
                    VALUES
                        ({ph}, {ph}, {ph},
                         {ph}, {ph}, {ph}, {ph},
                         {ph}, {ph})
                    """,
                    (
                        sd_id, connection_id, stype,
                        decision, json.dumps(baseline or {}), json.dumps(observed_metrics or {}),
                        outcome["classification"],
                        now, outcome["copy_status"],
                    ),
                )
            stats["observed"] += 1
        except Exception as e:
            log.warning(
                "run_outcome_observer: failed for sd_id=%s cid=%d: %s",
                sd_id, connection_id, e,
            )
            stats["errors"] += 1
            continue

    return stats


@bp.route("/admin/observer/run", methods=["POST"])
@require_same_origin
def admin_run_observer():
    """
    Manually trigger the outcome observer for one connection.

    Body (JSON, required): {"connection_id": <int>}.
    Authorisation: same X-Admin-Token gate as other admin endpoints.

    Returns the stats dict from run_outcome_observer.
    """
    if not PPC_ADMIN_TOKEN:
        return jsonify({"error": "Observer admin not configured on this instance"}), 503

    sent_token = request.headers.get("X-Admin-Token", "")
    if not secrets.compare_digest(sent_token, PPC_ADMIN_TOKEN):
        log.warning("ppc_admin_observer rejected: bad or missing X-Admin-Token")
        return jsonify({"error": "forbidden"}), 403

    body = request.get_json(silent=True) or {}
    raw_cid = body.get("connection_id")
    try:
        connection_id = int(raw_cid)
    except (TypeError, ValueError):
        return jsonify({"error": "connection_id must be an integer"}), 400
    if connection_id < 1:
        return jsonify({"error": "connection_id must be >= 1"}), 400

    try:
        stats = run_outcome_observer(connection_id=connection_id)
    except Exception as e:
        log.exception("admin_run_observer failed: %s", e)
        return jsonify({"error": "observer run failed"}), 500

    return jsonify(stats)


@bp.route("/admin/retention/run", methods=["POST"])
@require_same_origin
def admin_run_retention():
    """
    Manually trigger ppc_snapshots retention. Returns the row count deleted.

    Body (optional JSON): {"days": 90}. Defaults to 90 if absent. Days must
    be a positive integer; non-integer values return 400.

    Approval-first note: this endpoint deletes our OWN cached copies of
    Amazon Ads data; it does NOT touch the seller's Amazon account in any
    way. There is no Ads API call on this code path.
    """
    if not PPC_ADMIN_TOKEN:
        return jsonify({"error": "Retention admin not configured on this instance"}), 503

    sent_token = request.headers.get("X-Admin-Token", "")
    if not secrets.compare_digest(sent_token, PPC_ADMIN_TOKEN):
        log.warning("ppc_admin_retention rejected: bad or missing X-Admin-Token")
        return jsonify({"error": "forbidden"}), 403

    body = request.get_json(silent=True) or {}
    raw_days = body.get("days", DEFAULT_RETENTION_DAYS)
    try:
        days = int(raw_days)
    except (TypeError, ValueError):
        return jsonify({"error": "days must be an integer"}), 400
    if days < 1:
        return jsonify({"error": "days must be >= 1"}), 400

    try:
        deleted = ppc_snapshot_fetcher.run_retention(days=days)
    except Exception as e:
        log.exception("admin_run_retention failed: %s", e)
        return jsonify({"error": "retention run failed"}), 500

    return jsonify({"deleted": deleted, "days": days})


def register_routes(app) -> None:
    """Called from server.py to attach the /ppc/* routes."""
    app.register_blueprint(bp)
    log.info("PPC Agent routes registered at /ppc/*")
