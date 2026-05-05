"""
Amazon Ads API client wrapper for SellerCopilot.

Read-only HTTP client over the Amazon Ads API. Write operations land in
week 6 when we implement the suggestion applier. The client does three
jobs the raw SDK does not:

1. Plugs into ppc_oauth.get_active_token so all token management lives in
   one place. The python-amazon-ad-api package is in requirements.txt as
   a fallback option, but we use raw HTTP here to avoid duplicating the
   token cache between this module and the SDK.

2. Retries once on 401 by invalidating the cached token and refreshing.
   This handles the case where Amazon revokes a token before its declared
   expiry (rare but documented).

3. Self-identifies in User-Agent per Amazon's March 2026 Agent Policy.
   Every request carries SellerCopilot/1.0 (AI Agent) so Amazon can
   distinguish our automated traffic from the seller's manual activity.

Rate limit: best-effort 5 requests per second, process-local. Documented
as a known limitation; week 3 replaces with a Redis token bucket so
multi-worker gunicorn cannot collectively exceed Amazon's per-app ceiling.

Endpoints used:
- GET  /v2/profiles                     list seller's advertising profiles
- POST /sp/campaigns/list               Sponsored Products campaigns (v3)
- POST /sp/adGroups/list                Ad groups under a campaign (v3)
- POST /sp/keywords/list                Keywords under an ad group (v3)
- POST /reporting/reports               Async search-term report request
- GET  /reporting/reports/{reportId}    Poll report status

Docs: https://advertising.amazon.com/API/docs/en-us/
"""

from __future__ import annotations

import os
import gzip
import json
import time
import logging
import threading
from typing import Any

import requests

import ppc_oauth

log = logging.getLogger("ppc_ads_client")


# ──────────────────────────────────────────────────────────────────────────
#  Config (read from env, set on Railway)
# ──────────────────────────────────────────────────────────────────────────

# Amazon Ads has separate hosts per geographic region. Set ADS_API_REGION
# on Railway to "NA" (US/CA/MX), "EU" (UK/DE/FR/IT/ES), or "FE" (JP/AU).
_REGION_TO_BASE_URL = {
    "NA": "https://advertising-api.amazon.com",
    "EU": "https://advertising-api-eu.amazon.com",
    "FE": "https://advertising-api-fe.amazon.com",
}

ADS_API_REGION   = os.getenv("ADS_API_REGION", "NA")
ADS_API_BASE_URL = _REGION_TO_BASE_URL.get(ADS_API_REGION, _REGION_TO_BASE_URL["NA"])

# Required by Amazon's March 2026 Agent Policy. Self-identifies our agent
# in every API call. Format: ProductName/Version (Type, optional fields).
USER_AGENT = "SellerCopilot/1.0 (AI Agent)"

# Same client id used for LWA. Every Ads API call sends it as a header so
# Amazon can attribute the call to our registered Solution Provider app.
SP_API_CLIENT_ID = os.getenv("SP_API_CLIENT_ID", "")

# Network timeout. Ads list endpoints respond in seconds; reports take 1 to
# 10 minutes but are polled, not held open.
ADS_TIMEOUT_SECONDS = 30

# Search-term report polling. Amazon usually completes a 30-day report in
# 1 to 3 minutes. We cap at 10 minutes so a stuck report fails the snapshot
# job loudly rather than hanging the whole cron run.
REPORT_POLL_INTERVAL_SECONDS = 10
REPORT_POLL_MAX_SECONDS      = 600


# ──────────────────────────────────────────────────────────────────────────
#  Process-local rate limiter (5 req/s)
# ──────────────────────────────────────────────────────────────────────────
#  Each gunicorn worker maintains its own counter. With N workers we can
#  collectively exceed Amazon's per-app ceiling. Acceptable for MVP single-
#  worker deployment. Week 3 replaces with a Redis token bucket.

_RATE_LIMIT_PER_SECOND = 5
_rate_lock             = threading.Lock()
_request_times: list[float] = []


# ──────────────────────────────────────────────────────────────────────────
#  Custom exception
# ──────────────────────────────────────────────────────────────────────────

class AdsAPIError(Exception):
    """
    Raised when an Ads API call fails after retries are exhausted.

    Attributes:
        status_code:   HTTP status returned, or None on network failure.
        response_body: raw response body (truncated to 500 chars) for
                       diagnostics.
    """

    def __init__(self, message: str, status_code: int | None = None,
                 response_body: str | None = None) -> None:
        super().__init__(message)
        self.status_code   = status_code
        self.response_body = response_body


class _UnauthorizedError(Exception):
    """Internal sentinel for 401 responses. Triggers retry-with-fresh-token."""
    pass


# ──────────────────────────────────────────────────────────────────────────
#  Public client
# ──────────────────────────────────────────────────────────────────────────

class AdsClient:
    """
    Per-connection client for Amazon Ads API.

    Construct one per active amazon_connections row when running an agent
    job. Methods are stateless beyond the held connection_id and profile_id;
    safe to discard the instance after a snapshot job completes.

    Token management is delegated to ppc_oauth.get_active_token. This
    instance does not cache anything. The cache lives in ppc_oauth.
    """

    def __init__(self, connection_id: int, profile_id: str | None = None) -> None:
        """
        Args:
            connection_id: amazon_connections.id of the seller's account.
            profile_id:    Amazon Ads profile id. Required for everything
                           except list_profiles(). For multi-marketplace
                           sellers, the caller picks one profile per snapshot
                           run; week 5 surfaces this choice in the dashboard.
        """
        self.connection_id = connection_id
        self.profile_id    = profile_id

    # ── Public read methods ───────────────────────────────────────────

    def list_profiles(self) -> list[dict[str, Any]]:
        """
        List all advertising profiles the seller has authorized.

        Each profile maps to a single (account, marketplace) combination.
        A seller selling in US and DE has two profiles. The caller picks
        one or iterates all.

        Endpoint: GET /v2/profiles
        Profile id is NOT required for this call; this is the call that
        discovers which profile ids exist.
        """
        return self._request("GET", "/v2/profiles", profile_required=False)

    def list_campaigns(self, state_filter: list[str] | None = None) -> list[dict[str, Any]]:
        """
        List Sponsored Products campaigns for the active profile.

        Args:
            state_filter: optional list of states to include. Defaults to
                          ["ENABLED", "PAUSED"]. Use ["ENABLED", "PAUSED",
                          "ARCHIVED"] for full history (rarely needed for
                          ongoing optimisation).

        Endpoint: POST /sp/campaigns/list (Ads API v3)

        Returns the campaigns list. Pagination via nextToken is NOT
        implemented in v1; callers should be aware that very large accounts
        (>1000 campaigns) may be truncated. Documented limit; week 3 fix.
        """
        if state_filter is None:
            state_filter = ["ENABLED", "PAUSED"]
        body = {"stateFilter": {"include": state_filter}}
        result = self._request("POST", "/sp/campaigns/list", body=body)
        return result.get("campaigns", []) if isinstance(result, dict) else result

    def list_ad_groups(self, campaign_id: str) -> list[dict[str, Any]]:
        """
        List ad groups under a Sponsored Products campaign.

        Endpoint: POST /sp/adGroups/list
        """
        body = {"campaignIdFilter": {"include": [campaign_id]}}
        result = self._request("POST", "/sp/adGroups/list", body=body)
        return result.get("adGroups", []) if isinstance(result, dict) else result

    def list_keywords(self, ad_group_id: str) -> list[dict[str, Any]]:
        """
        List keywords under a Sponsored Products ad group.

        Endpoint: POST /sp/keywords/list
        """
        body = {"adGroupIdFilter": {"include": [ad_group_id]}}
        result = self._request("POST", "/sp/keywords/list", body=body)
        return result.get("keywords", []) if isinstance(result, dict) else result

    def get_search_term_report(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """
        Generate and download a Sponsored Products search-term report.

        Synchronous wrapper around the Ads Reports v3 API:
        1. POST /reporting/reports                request the report
        2. GET  /reporting/reports/{id}           poll status
        3. GET  download URL when status=COMPLETED
        4. Decompress gzipped JSON, return list of rows

        Args:
            start_date: ISO 8601 date "YYYY-MM-DD" inclusive.
            end_date:   ISO 8601 date "YYYY-MM-DD" inclusive.

        Returns:
            List of dicts, one per (search term, keyword, ad group) row.
            Empty list if there were no impressions in the period.

        Raises:
            AdsAPIError: on any API failure or if the report does not
                         complete within REPORT_POLL_MAX_SECONDS.
        """
        request_body = {
            "name": f"sp_search_term_{start_date}_to_{end_date}",
            "startDate": start_date,
            "endDate": end_date,
            "configuration": {
                "adProduct": "SPONSORED_PRODUCTS",
                "groupBy": ["searchTerm"],
                "columns": [
                    "campaignId", "adGroupId", "keywordId",
                    "keywordText", "matchType", "searchTerm",
                    "impressions", "clicks", "cost",
                    "purchases1d", "purchases7d", "purchases14d", "purchases30d",
                    "sales1d", "sales7d", "sales14d", "sales30d",
                ],
                "reportTypeId": "spSearchTerm",
                "timeUnit": "SUMMARY",
                "format": "GZIP_JSON",
            },
        }
        created = self._request("POST", "/reporting/reports", body=request_body)
        report_id = created.get("reportId") if isinstance(created, dict) else None
        if not report_id:
            raise AdsAPIError(
                "Report creation succeeded but no reportId returned",
                response_body=str(created)[:500],
            )

        download_url = self._poll_report(report_id)
        return self._download_report_json(download_url)

    # ── Internal: request, retry, poll, download ──────────────────────

    def _request(self, method: str, path: str, *,
                 body: dict[str, Any] | None = None,
                 profile_required: bool = True) -> Any:
        """
        Make an Ads API request with auth, rate-limiting, and 401-retry.

        Refreshes the cached token once on 401 and retries the request
        exactly once. After that, raises AdsAPIError. This shape stays
        within Amazon's recommendation that automated tools should not
        retry indefinitely on auth failures.
        """
        if profile_required and not self.profile_id:
            raise AdsAPIError(
                "profile_id is required for this call. "
                "Call list_profiles() first and pass the chosen id."
            )

        url = ADS_API_BASE_URL + path

        try:
            resp = self._do_request(method, url, body)
        except _UnauthorizedError:
            ppc_oauth.invalidate_cached_token(self.connection_id)
            log.info(
                "401 from Ads API on %s, refreshed token and retrying once",
                path,
            )
            try:
                resp = self._do_request(method, url, body)
            except _UnauthorizedError:
                raise AdsAPIError(
                    f"Ads API {method} {path} returned 401 even after "
                    f"token refresh. Connection may be revoked."
                )

        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError as e:
                raise AdsAPIError(
                    f"Ads API returned 200 but body was not JSON for {path}",
                    status_code=200,
                    response_body=resp.text[:500] if resp.text else None,
                ) from e

        raise AdsAPIError(
            f"Ads API {method} {path} failed with status {resp.status_code}",
            status_code=resp.status_code,
            response_body=resp.text[:500] if resp.text else None,
        )

    def _do_request(self, method: str, url: str,
                    body: dict[str, Any] | None) -> requests.Response:
        """
        Single HTTP call. Raises _UnauthorizedError on 401 so the caller
        can decide whether to retry. Other status codes are returned as-is
        and inspected by _request.
        """
        _rate_limit_throttle()

        access_token = ppc_oauth.get_active_token(self.connection_id)
        headers = {
            "Authorization":                        f"Bearer {access_token}",
            "Amazon-Advertising-API-ClientId":      SP_API_CLIENT_ID,
            "Content-Type":                         "application/json",
            "Accept":                               "application/json",
            "User-Agent":                           USER_AGENT,
        }
        if self.profile_id:
            headers["Amazon-Advertising-API-Scope"] = self.profile_id

        try:
            resp = requests.request(
                method,
                url,
                headers=headers,
                json=body,
                timeout=ADS_TIMEOUT_SECONDS,
            )
        except requests.RequestException as e:
            raise AdsAPIError(f"Network failure on Ads API call: {e}") from e

        if resp.status_code == 401:
            raise _UnauthorizedError()

        return resp

    def _poll_report(self, report_id: str) -> str:
        """
        Poll a report until status COMPLETED. Returns the download URL.
        Raises on FAILED, CANCELLED, or timeout.
        """
        deadline = time.time() + REPORT_POLL_MAX_SECONDS
        while time.time() < deadline:
            time.sleep(REPORT_POLL_INTERVAL_SECONDS)
            status = self._request("GET", f"/reporting/reports/{report_id}")
            state = status.get("status") if isinstance(status, dict) else None

            if state == "COMPLETED":
                url = status.get("url")
                if not url:
                    raise AdsAPIError(
                        f"Report {report_id} COMPLETED but no download url",
                        response_body=str(status)[:500],
                    )
                return url

            if state in ("FAILED", "CANCELLED"):
                raise AdsAPIError(
                    f"Report {report_id} ended in state {state}",
                    response_body=str(status)[:500],
                )

            log.debug("Report %s status=%s, polling again", report_id, state)

        raise AdsAPIError(
            f"Report {report_id} did not complete within "
            f"{REPORT_POLL_MAX_SECONDS}s. Try a smaller date range or "
            f"investigate Ads API health."
        )

    def _download_report_json(self, url: str) -> list[dict[str, Any]]:
        """
        Download the gzipped JSON report from the URL Amazon provides.

        The download URL is short-lived (signed S3 URL). Do not store it.
        """
        try:
            resp = requests.get(url, timeout=ADS_TIMEOUT_SECONDS)
        except requests.RequestException as e:
            raise AdsAPIError(f"Failed to download report: {e}") from e

        if resp.status_code != 200:
            raise AdsAPIError(
                f"Report download failed with status {resp.status_code}",
                status_code=resp.status_code,
                response_body=resp.text[:500] if resp.text else None,
            )

        try:
            decompressed = gzip.decompress(resp.content)
            data = json.loads(decompressed)
        except (OSError, ValueError) as e:
            raise AdsAPIError(f"Failed to parse report payload: {e}") from e

        if not isinstance(data, list):
            raise AdsAPIError(
                f"Report payload was not a JSON list. Got type {type(data).__name__}"
            )
        return data


# ──────────────────────────────────────────────────────────────────────────
#  Module-level helpers
# ──────────────────────────────────────────────────────────────────────────

def _rate_limit_throttle() -> None:
    """
    Best-effort process-local throttle. Sleeps if we have made
    _RATE_LIMIT_PER_SECOND requests in the last 1 second.

    Limitation: each gunicorn worker has its own counter. Multiple workers
    can collectively exceed Amazon's app-wide rate ceiling. Acceptable for
    MVP single-worker deployment; week 3 replaces with Redis token bucket.
    """
    with _rate_lock:
        now = time.time()
        while _request_times and _request_times[0] < now - 1.0:
            _request_times.pop(0)
        if len(_request_times) >= _RATE_LIMIT_PER_SECOND:
            sleep_until = _request_times[0] + 1.0
            sleep_for = max(0.0, sleep_until - now)
            if sleep_for > 0:
                time.sleep(sleep_for)
                now = time.time()
        _request_times.append(now)
