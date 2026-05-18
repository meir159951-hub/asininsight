"""
PPC OAuth helper, Amazon Login With Amazon (LWA) token exchange and refresh.

This module handles the three OAuth operations needed to connect a seller's
Amazon Seller Central account to ASINInsight:

1. exchange_oauth_code: one-time exchange of the authorization code returned
   by Amazon after the seller approves consent. Returns a long-lived
   refresh_token that we encrypt and store in amazon_connections.

2. refresh_access_token: short-lived access tokens expire every hour. This
   function exchanges a stored refresh_token for a fresh access_token.

3. get_active_token: high-level helper that reads the encrypted refresh_token
   from amazon_connections, decrypts it via ppc_agent.decrypt_token, refreshes
   if needed, caches the access_token for its TTL, and returns it. This is the
   function the rest of the codebase calls to get a usable access_token.

LWA endpoint: https://api.amazon.com/auth/o2/token
LWA docs:     https://developer.amazon.com/docs/login-with-amazon/web-docs.html

Stage of implementation (2026-05): first real implementation. The cache is
in-memory for now. Redis migration is week 3 of the MVP plan. Single-process
gunicorn is safe with this implementation; once we move to multi-worker we
will see redundant LWA refresh calls (one per worker per hour per connection)
but no incorrect tokens. The Redis migration removes the redundancy.
"""

from __future__ import annotations

import os
import time
import logging
import threading
from typing import Any

import requests

log = logging.getLogger("ppc_oauth")

# ──────────────────────────────────────────────────────────────────────────
#  Config (read from env, set on Railway)
# ──────────────────────────────────────────────────────────────────────────

SP_API_CLIENT_ID     = os.getenv("SP_API_CLIENT_ID", "")
SP_API_CLIENT_SECRET = os.getenv("SP_API_CLIENT_SECRET", "")
SP_API_REDIRECT_URI  = os.getenv(
    "SP_API_REDIRECT_URI",
    "https://asininsight.com/ppc/oauth/callback",
)

# LWA token endpoint. Same URL handles both the initial code exchange and
# subsequent refresh_token grants. Differentiated only by the grant_type
# field in the form body.
LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"

# Network timeout for LWA calls. LWA usually responds in well under a second
# in healthy regions; 10 seconds is conservative without making the OAuth
# callback feel hung to the seller.
LWA_TIMEOUT_SECONDS = 10

# Refresh access tokens slightly before they actually expire. If LWA tells
# us "expires_in: 3600", we treat the token as expired at 3540 to avoid
# the boundary case where SP-API rejects an almost-expired token.
TOKEN_EXPIRY_BUFFER_SECONDS = 60


# ──────────────────────────────────────────────────────────────────────────
#  In-memory cache for access tokens
# ──────────────────────────────────────────────────────────────────────────
#  Keyed by connection_id. Value is (access_token, expires_at_epoch).
#  A lock guards reads and writes so concurrent requests don't double-call
#  LWA when the cache is cold.
#
#  TODO(week 3): replace with Redis-backed cache so multi-worker gunicorn
#  shares the cache. Until then, every gunicorn worker maintains its own
#  copy and we accept O(workers) extra LWA calls per hour per connection.

_token_cache: dict[int, tuple[str, float]] = {}
# Reentrant: get_active_token() holds this lock when it calls
# mark_connection_inactive() on invalid_grant, and mark_connection_inactive()
# in turn calls invalidate_cached_token() which re-acquires the lock. A
# plain Lock would deadlock the calling thread.
_token_cache_lock = threading.RLock()


# ──────────────────────────────────────────────────────────────────────────
#  Custom exception
# ──────────────────────────────────────────────────────────────────────────

class LWAError(Exception):
    """
    Raised when LWA returns a non-success response or the network call fails.

    Attributes:
        status_code:    HTTP status code returned by LWA, or None on network
                        failure.
        lwa_error_code: the error code string from LWA's JSON body when
                        present (for example "invalid_grant", "invalid_client",
                        "unauthorized_client"). None when LWA didn't return
                        parseable JSON.

    Callers can branch on lwa_error_code to distinguish "the seller revoked
    our app" (invalid_grant) from "our credentials are wrong"
    (invalid_client). The first case means we should mark the connection
    inactive in DB; the second means we should alert the founder.
    """

    def __init__(self, message: str, status_code: int | None = None,
                 lwa_error_code: str | None = None) -> None:
        super().__init__(message)
        self.status_code    = status_code
        self.lwa_error_code = lwa_error_code


# ──────────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────────

def exchange_oauth_code(spapi_oauth_code: str) -> dict[str, Any]:
    """
    Exchange a one-time oauth_code for a long-lived refresh_token.

    Called once per seller, from the OAuth callback handler in ppc_agent.py
    after Amazon redirects the seller back from the consent screen.

    Args:
        spapi_oauth_code: the value of the spapi_oauth_code query parameter
            that Amazon appends to our redirect_uri when the seller approves.
            One-time use; expires within minutes.

    Returns:
        Dict with keys:
        - refresh_token: long-lived token. Caller MUST encrypt with
          ppc_agent.encrypt_token before storing in amazon_connections.
        - access_token:  short-lived token, usable immediately for ~1 hour.
        - token_type:    always "bearer" per LWA spec.
        - expires_in:    seconds until access_token expires (typically 3600).

    Raises:
        LWAError: on non-2xx response or network failure. The exception's
            lwa_error_code field tells the caller which class of failure
            it was (invalid_grant, invalid_client, etc).
    """
    if not spapi_oauth_code:
        raise LWAError("oauth_code is empty")
    if not SP_API_CLIENT_ID or not SP_API_CLIENT_SECRET:
        raise LWAError(
            "SP_API_CLIENT_ID or SP_API_CLIENT_SECRET not configured. "
            "Set both env vars on Railway before connecting an account."
        )

    payload = {
        "grant_type":    "authorization_code",
        "code":          spapi_oauth_code,
        "redirect_uri":  SP_API_REDIRECT_URI,
        "client_id":     SP_API_CLIENT_ID,
        "client_secret": SP_API_CLIENT_SECRET,
    }

    return _post_to_lwa(payload, operation="exchange_oauth_code")


def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    """
    Exchange a long-lived refresh_token for a fresh access_token.

    Called whenever an access_token expires. Most of the time, callers should
    use get_active_token() instead, which handles caching. Use this function
    directly only when you need to bypass the cache (for example in tests
    or when explicitly forcing a refresh after a 401).

    Args:
        refresh_token: the decrypted refresh_token previously obtained from
            exchange_oauth_code. Stays valid until the seller revokes our
            app from their Seller Central settings, or Amazon expires it
            for inactivity (currently no documented inactivity expiry).

    Returns:
        Dict with keys:
        - access_token: fresh token, usable for ~1 hour.
        - token_type:   "bearer".
        - expires_in:   seconds until expiry.

        Note: LWA does NOT return a new refresh_token on this call. The
        original refresh_token stays valid and must continue to be used.

    Raises:
        LWAError: on non-2xx response or network failure. If the seller
            revoked our app from Seller Central, LWA returns "invalid_grant"
            and the caller should mark the connection inactive in DB.
    """
    if not refresh_token:
        raise LWAError("refresh_token is empty")
    if not SP_API_CLIENT_ID or not SP_API_CLIENT_SECRET:
        raise LWAError(
            "SP_API_CLIENT_ID or SP_API_CLIENT_SECRET not configured."
        )

    payload = {
        "grant_type":    "refresh_token",
        "refresh_token": refresh_token,
        "client_id":     SP_API_CLIENT_ID,
        "client_secret": SP_API_CLIENT_SECRET,
    }

    return _post_to_lwa(payload, operation="refresh_access_token")


def get_active_token(connection_id: int) -> str:
    """
    Return a valid access_token for the given connection.

    This is the function the rest of the codebase calls when it needs to make
    an SP-API or Ads API request. It handles caching, decryption of the stored
    refresh_token, and refresh-on-expiry transparently.

    Behaviour:
    1. Check the in-memory cache. If we have an access_token with at least
       TOKEN_EXPIRY_BUFFER_SECONDS of life left, return it.
    2. Otherwise, read the encrypted refresh_token from amazon_connections,
       decrypt it via ppc_agent.decrypt_token, exchange it at LWA for a
       fresh access_token, cache it, return it.

    The lock ensures only one caller per connection_id hits LWA at a time,
    even under concurrent requests. Other callers wait briefly and read the
    refreshed entry from the cache (the double-check pattern below).

    Args:
        connection_id: amazon_connections.id of the seller's connected
            account. Caller is responsible for ensuring the connection
            belongs to the current customer (typically by filtering on
            customer_id when fetching the id from a query).

    Returns:
        access_token string, valid for at least TOKEN_EXPIRY_BUFFER_SECONDS.

    Raises:
        ValueError: if no active connection exists with that id.
        LWAError:   if the LWA refresh call fails.
    """
    now = time.time()

    # Fast path: cached and still valid.
    with _token_cache_lock:
        cached = _token_cache.get(connection_id)
        if cached is not None:
            access_token, expires_at = cached
            if expires_at - now > TOKEN_EXPIRY_BUFFER_SECONDS:
                return access_token

    # Slow path. Read the encrypted refresh_token from DB.
    encrypted_refresh = _read_encrypted_refresh_token(connection_id)
    if not encrypted_refresh:
        raise ValueError(
            f"No active connection found for connection_id={connection_id}. "
            f"The connection may not exist, may be marked inactive, or may "
            f"have been deleted."
        )

    # Lazy import to avoid circular dependency. ppc_agent imports this
    # module's OAuth functions at module top, so we cannot import ppc_agent
    # at our module top.
    from ppc_agent import decrypt_token
    plaintext_refresh = decrypt_token(encrypted_refresh)

    # Critical section: only one refresh per connection at a time. The
    # double-check below handles the case where another thread refreshed
    # while this one was reading from DB and decrypting.
    with _token_cache_lock:
        cached = _token_cache.get(connection_id)
        if cached is not None:
            access_token, expires_at = cached
            if expires_at - time.time() > TOKEN_EXPIRY_BUFFER_SECONDS:
                return access_token

        # Refresh from LWA. Two failure classes need different handling:
        # - invalid_grant   the seller revoked us, or the refresh_token
        #                   expired. Flip the connection inactive so the
        #                   cron stops trying and the dashboard can prompt
        #                   for reconnect. Then re-raise so the caller
        #                   sees the failure.
        # - anything else   surface the original LWAError unchanged.
        try:
            result = refresh_access_token(plaintext_refresh)
        except LWAError as e:
            if e.lwa_error_code == "invalid_grant":
                # mark_connection_inactive opens its own DB connection and
                # does not block on _token_cache_lock; safe to call from
                # within this critical section.
                try:
                    mark_connection_inactive(
                        connection_id,
                        reason="lwa_invalid_grant_on_refresh",
                    )
                except Exception:
                    log.exception(
                        "mark_connection_inactive failed during invalid_grant "
                        "handling for connection_id=%d", connection_id,
                    )
            raise

        access_token = result["access_token"]
        expires_in   = int(result.get("expires_in", 3600))
        expires_at   = time.time() + expires_in

        _token_cache[connection_id] = (access_token, expires_at)
        log.info(
            "Refreshed access_token for connection_id=%d, expires_in=%ds",
            connection_id, expires_in,
        )
        return access_token


def invalidate_cached_token(connection_id: int) -> None:
    """
    Drop the cached access_token for a connection.

    Call this when an SP-API or Ads API call returns 401 Unauthorized: the
    cached token may have been revoked or expired earlier than expected.
    The next call to get_active_token will refresh from LWA.

    Safe to call even if the connection_id has no cached token.
    """
    with _token_cache_lock:
        if _token_cache.pop(connection_id, None) is not None:
            log.info("Invalidated cached token for connection_id=%d", connection_id)


def mark_connection_inactive(connection_id: int, reason: str) -> bool:
    """
    Flip amazon_connections.active = 0 for the given connection.

    Called when LWA returns `invalid_grant` on a refresh attempt, which means
    the seller revoked our app from Seller Central (or Amazon expired the
    refresh token). The connection cannot be used to call Ads / SP-API
    again until the seller re-authorises us. The dashboard already displays
    inactive connections with a "reconnect" badge.

    Side effects, in order:
    1. UPDATE amazon_connections SET active = 0 WHERE id = ?  (only if currently active)
    2. Drop any cached access_token for the same connection.

    Args:
        connection_id: amazon_connections.id row.
        reason:        short string for the log line. Tracks why we flipped
                       so an operator scanning logs can distinguish revoke
                       events from operator-initiated deactivation.

    Returns:
        True  if a row was actually flipped from active to inactive.
        False if the row did not exist or was already inactive.

    Lazy-imports `server._db` for the same reason as
    `_read_encrypted_refresh_token`: server -> ppc_agent -> ppc_oauth would
    close the import cycle if we did it at module top.
    """
    from server import _db

    flipped = False
    try:
        with _db() as (cur, ph):
            cur.execute(
                f"""
                UPDATE amazon_connections
                SET active = 0
                WHERE id = {ph} AND active = 1
                """,
                (connection_id,),
            )
            flipped = bool(cur.rowcount)
    except Exception as e:
        # Don't let the inactive-flip failure mask the original LWA error;
        # log and return False so the caller still raises the underlying
        # LWAError to surface the auth problem.
        log.warning(
            "mark_connection_inactive failed for connection_id=%d reason=%s err=%s",
            connection_id, reason, e,
        )
        return False

    # Whether or not we flipped the row, drop any cached access_token. A
    # stale cache entry would otherwise mask the inactive flag for an hour.
    invalidate_cached_token(connection_id)

    if flipped:
        log.warning(
            "Marked connection_id=%d INACTIVE reason=%s. Seller must reconnect.",
            connection_id, reason,
        )
    return flipped


# ──────────────────────────────────────────────────────────────────────────
#  Internal helpers
# ──────────────────────────────────────────────────────────────────────────

def _post_to_lwa(payload: dict[str, str], operation: str) -> dict[str, Any]:
    """
    Internal: POST a form-encoded payload to LWA, parse the response, raise
    LWAError on any non-success outcome.

    Centralises error handling so exchange_oauth_code and refresh_access_token
    behave identically with respect to errors and logging.

    Args:
        payload:   form fields to send (grant_type, code or refresh_token,
                   client_id, client_secret, etc).
        operation: short label for logs and error messages, identifying
                   which public function called us.

    Returns:
        Parsed JSON body on success.

    Raises:
        LWAError: on any failure mode.
    """
    # Import lazily to avoid a circular dependency: ppc_ads_client also
    # imports from ppc_oauth.
    from ppc_ads_client import USER_AGENT as _BSA_USER_AGENT

    try:
        resp = requests.post(
            LWA_TOKEN_URL,
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept":       "application/json",
                # BSA Agent Policy self-identification (2026-03-04).
                # LWA is part of Amazon's surface area; the policy says
                # "AI agents must self-identify at all times", not just
                # on Ads API.
                "User-Agent":   _BSA_USER_AGENT,
            },
            timeout=LWA_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        log.warning("LWA network failure during %s: %s", operation, e)
        raise LWAError(f"LWA network failure during {operation}: {e}") from e

    # Success path: LWA returns 200 with a JSON body containing access_token.
    if resp.status_code == 200:
        try:
            data = resp.json()
        except ValueError as e:
            raise LWAError(
                f"LWA returned 200 but body was not JSON during {operation}"
            ) from e

        # Sanity check the response shape so downstream code can rely on
        # access_token being present on every success return.
        if "access_token" not in data:
            raise LWAError(
                f"LWA 200 response missing access_token during {operation}. "
                f"Got keys: {list(data.keys())}"
            )
        return data

    # Error path: LWA puts the error code in the JSON body's "error" field
    # and a human-readable description in "error_description".
    lwa_error_code = None
    lwa_error_desc = ""
    try:
        body = resp.json()
        lwa_error_code = body.get("error")
        lwa_error_desc = body.get("error_description", "")
    except ValueError:
        # Not JSON. Use the raw text (truncated) for diagnostics.
        lwa_error_desc = resp.text[:200]

    log.warning(
        "LWA %s failed: status=%d error=%s description=%s",
        operation, resp.status_code, lwa_error_code, lwa_error_desc,
    )
    raise LWAError(
        f"LWA {operation} failed with status {resp.status_code}: "
        f"{lwa_error_code or 'unknown_error'}, {lwa_error_desc}",
        status_code=resp.status_code,
        lwa_error_code=lwa_error_code,
    )


def _read_encrypted_refresh_token(connection_id: int) -> str | None:
    """
    Internal: read the encrypted refresh_token for an active connection.

    Returns None if the connection does not exist, has been marked inactive,
    or the row's encrypted token field is empty.

    Lazy import of server._db avoids circular dependency at module load:
    server.py imports ppc_agent which imports this module, so importing
    server at our top level would close the cycle.
    """
    from server import _db

    with _db() as (cur, ph):
        cur.execute(
            f"""
            SELECT refresh_token_encrypted
            FROM amazon_connections
            WHERE id = {ph} AND active = 1
            """,
            (connection_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        # Postgres returns memoryview for some text types in some configs;
        # normalise to str so callers don't need to.
        token = row[0]
        return str(token) if token is not None else None
