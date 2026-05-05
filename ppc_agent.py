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

import os
import time
import logging
import secrets
from typing import Any
from urllib.parse import urlencode

from flask import (
    Blueprint, request, session, jsonify, redirect, render_template,
)

import ppc_oauth
import ppc_snapshot_fetcher

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
                    id             {serial},
                    connection_id  INTEGER NOT NULL,
                    fetched_at     REAL NOT NULL,
                    data_type      TEXT NOT NULL,
                    data           {jsonb} NOT NULL
                )
            """)

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
    """Run rule-based + LLM analysis, store suggestions in DB."""
    raise NotImplementedError("Suggestion generator, week 4 of MVP plan")


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


@bp.route("/connect", methods=["POST"])
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
    """Render the PPC dashboard with connected accounts and pending suggestions."""
    customer_id = session.get("customer_id")
    if not customer_id:
        return redirect("/")

    connections = _list_customer_connections(str(customer_id))
    return render_template(
        "ppc_dashboard.html",
        connections=connections,
        customer_id=customer_id,
    )


@bp.route("/connections", methods=["GET"])
def list_connections():
    """JSON list of the current customer's amazon_connections."""
    customer_id = session.get("customer_id")
    if not customer_id:
        return jsonify({"error": "Not logged in"}), 401
    return jsonify({"connections": _list_customer_connections(str(customer_id))})


@bp.route("/suggestions", methods=["GET"])
def list_suggestions():
    """JSON list of pending suggestions for the logged-in customer."""
    if not session.get("customer_id"):
        return jsonify({"error": "Not logged in"}), 401
    return jsonify({"suggestions": []})


@bp.route("/suggestions/<int:sid>/approve", methods=["POST"])
def approve_suggestion(sid: int):
    """Customer approves a suggestion. Apply via Amazon Ads API."""
    if not session.get("customer_id"):
        return jsonify({"error": "Not logged in"}), 401
    return jsonify({"status": "stub", "suggestion_id": sid})


@bp.route("/suggestions/<int:sid>/reject", methods=["POST"])
def reject_suggestion(sid: int):
    """Customer rejects a suggestion. Mark as rejected, don't apply."""
    if not session.get("customer_id"):
        return jsonify({"error": "Not logged in"}), 401
    return jsonify({"status": "stub", "suggestion_id": sid})


@bp.route("/suggestions/<int:sid>/rollback", methods=["POST"])
def rollback(sid: int):
    """Customer clicks Rollback on an applied suggestion."""
    if not session.get("customer_id"):
        return jsonify({"error": "Not logged in"}), 401
    return jsonify({"status": "stub", "suggestion_id": sid})


def register_routes(app) -> None:
    """Called from server.py to attach the /ppc/* routes."""
    app.register_blueprint(bp)
    log.info("PPC Agent routes registered at /ppc/*")
