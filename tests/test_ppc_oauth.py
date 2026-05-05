"""
Smoke tests for ppc_oauth.

Coverage:
1. test_exchange_oauth_code_with_invalid_code_returns_error
   exchange_oauth_code raises LWAError with status_code=400 and
   lwa_error_code="invalid_grant" when LWA rejects the code.

2. test_get_active_token_caches_after_refresh
   First call to get_active_token hits LWA exactly once; the cache holds
   the access_token afterwards.

3. test_get_active_token_uses_cache_when_warm
   Second call within TTL does not call LWA again.

4. test_oauth_callback_state_mismatch_returns_400
   GET /ppc/oauth/callback with a state token that doesn't match the
   session's expected state returns HTTP 400.

Tests mock requests.post for LWA, _read_encrypted_refresh_token for DB,
and ppc_agent.decrypt_token for the encryption layer. No live HTTP, no
live DB, no live Amazon credentials needed.

Run with: pytest tests/test_ppc_oauth.py
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch, MagicMock

import pytest

# Make the repo root importable so `import ppc_oauth` works regardless of
# the directory pytest is invoked from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test-only env vars before importing the modules under test. ppc_oauth
# reads these at module load.
os.environ.setdefault("SP_API_CLIENT_ID",     "test_client_id")
os.environ.setdefault("SP_API_CLIENT_SECRET", "test_client_secret")
os.environ.setdefault("SP_API_REDIRECT_URI",  "https://test.example.com/ppc/oauth/callback")

import ppc_oauth  # noqa: E402
from ppc_oauth import (  # noqa: E402
    exchange_oauth_code, get_active_token, LWAError,
)


# ──────────────────────────────────────────────────────────────────────────
#  Fixtures
# ──────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_token_cache():
    """Clear the in-memory cache between tests so they don't bleed state."""
    ppc_oauth._token_cache.clear()
    yield
    ppc_oauth._token_cache.clear()


def _mock_lwa_response(status_code: int, body: dict) -> MagicMock:
    """Build a fake requests.Response that returns the given body."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = body
    mock_resp.text = str(body)
    return mock_resp


# ──────────────────────────────────────────────────────────────────────────
#  Test 1: invalid code returns LWAError with parsed error code
# ──────────────────────────────────────────────────────────────────────────

def test_exchange_oauth_code_with_invalid_code_returns_error():
    fake_response = _mock_lwa_response(
        status_code=400,
        body={
            "error":             "invalid_grant",
            "error_description": "The provided authorization grant is invalid.",
        },
    )

    with patch("ppc_oauth.requests.post", return_value=fake_response) as mock_post:
        with pytest.raises(LWAError) as exc_info:
            exchange_oauth_code("a_bad_oauth_code")

        # Caller should be able to branch on these two attributes.
        assert exc_info.value.status_code    == 400
        assert exc_info.value.lwa_error_code == "invalid_grant"

        # We should have hit LWA exactly once. No retry on 400.
        assert mock_post.call_count == 1


# ──────────────────────────────────────────────────────────────────────────
#  Test 2: get_active_token populates the cache after refresh
# ──────────────────────────────────────────────────────────────────────────

def test_get_active_token_caches_after_refresh():
    fake_lwa = _mock_lwa_response(
        status_code=200,
        body={
            "access_token":  "atoken_after_refresh",
            "token_type":    "bearer",
            "expires_in":    3600,
            "refresh_token": "ignored",
        },
    )

    with patch("ppc_oauth._read_encrypted_refresh_token",
               return_value="encrypted_blob") as mock_read, \
         patch("ppc_agent.decrypt_token",
               return_value="plaintext_refresh_token") as mock_decrypt, \
         patch("ppc_oauth.requests.post",
               return_value=fake_lwa) as mock_post:

        token = get_active_token(connection_id=999)

        assert token == "atoken_after_refresh"
        assert mock_read.call_count    == 1
        assert mock_decrypt.call_count == 1
        assert mock_post.call_count    == 1

        # Cache should now hold the new token with TTL roughly = expires_in.
        cached = ppc_oauth._token_cache.get(999)
        assert cached is not None
        cached_token, cached_expires_at = cached
        assert cached_token == "atoken_after_refresh"


# ──────────────────────────────────────────────────────────────────────────
#  Test 3: cache hit on second call avoids the LWA round-trip
# ──────────────────────────────────────────────────────────────────────────

def test_get_active_token_uses_cache_when_warm():
    fake_lwa = _mock_lwa_response(
        status_code=200,
        body={
            "access_token": "atoken_cached",
            "token_type":   "bearer",
            "expires_in":   3600,
        },
    )

    with patch("ppc_oauth._read_encrypted_refresh_token",
               return_value="encrypted_blob"), \
         patch("ppc_agent.decrypt_token",
               return_value="plaintext_refresh_token"), \
         patch("ppc_oauth.requests.post",
               return_value=fake_lwa) as mock_post:

        first  = get_active_token(connection_id=998)
        second = get_active_token(connection_id=998)

        assert first  == "atoken_cached"
        assert second == "atoken_cached"

        # Critical: only one LWA call across the two get_active_token calls.
        assert mock_post.call_count == 1


# ──────────────────────────────────────────────────────────────────────────
#  Test 4: OAuth callback rejects state mismatch
# ──────────────────────────────────────────────────────────────────────────

def test_oauth_callback_state_mismatch_returns_400():
    """
    Integration test against Flask's test_client. We import server (which
    mounts ppc_agent's blueprint), set up a session with the expected
    state token, then GET the callback with a different state. We expect
    HTTP 400 and an error message about CSRF.
    """
    # Set the encryption key before server imports run, so the route
    # handler does not fail later on token encryption (defensive even
    # though this test doesn't reach that code path).
    os.environ.setdefault(
        "PPC_TOKEN_ENCRYPTION_KEY",
        # Test-only key. Generated with Fernet.generate_key() once.
        "rRiUz3xHGbXbBZI9xn-yY9JvJ6yL5y6KqzNc6VxQ1zU=",
    )
    os.environ.setdefault("FLASK_SECRET_KEY", "test_secret_key_min_32_chars_long____")

    # Import here, after env vars set, so server.py picks them up.
    from server import app

    client = app.test_client()

    with client.session_transaction() as sess:
        sess["customer_id"]      = "test_customer_42"
        sess["ppc_oauth_state"]  = "expected_state_token_xyz"

    resp = client.get(
        "/ppc/oauth/callback"
        "?state=wrong_state_token"
        "&spapi_oauth_code=any_code"
        "&selling_partner_id=A1TEST"
    )

    assert resp.status_code == 400
    body = resp.get_json()
    assert body is not None
    assert "Invalid OAuth state" in body.get("error", "")
