"""
ASINInsight - Flask server with Paddle payments + Amazon SP-API
"""

import os
import csv
import io
import hmac
import hashlib
import html
import time
import secrets
import sqlite3
import logging
import threading
import requests
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlencode
from flask import (
    Flask, send_from_directory, redirect,
    request, session, jsonify
)
from dotenv import load_dotenv

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__, static_folder=None)

secret_key = os.getenv("FLASK_SECRET_KEY")
_INSECURE_KEY_EXAMPLES = {
    "asininsight-secret-2026-xk9mp3",
    "change_me", "secret", "dev", "development",
}
if not secret_key:
    raise RuntimeError("FLASK_SECRET_KEY is not set. Generate one with: "
                       "python -c \"import secrets; print(secrets.token_hex(32))\"")
if len(secret_key) < 32:
    raise RuntimeError(f"FLASK_SECRET_KEY is too short ({len(secret_key)} chars). "
                       "Must be at least 32 random characters. "
                       "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\"")
if secret_key.lower() in _INSECURE_KEY_EXAMPLES:
    raise RuntimeError("FLASK_SECRET_KEY is still set to an example/default value. "
                       "Replace it with: python -c \"import secrets; print(secrets.token_hex(32))\"")
app.secret_key = secret_key

app.config["SESSION_COOKIE_NAME"]      = "sid"          # non-revealing name
app.config["SESSION_COOKIE_SECURE"]    = True
app.config["SESSION_COOKIE_HTTPONLY"]  = True
app.config["SESSION_COOKIE_SAMESITE"]  = "Lax"          # Strict breaks Amazon/Paddle OAuth redirects
app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 24 * 30  # 30 days
app.config["SESSION_REFRESH_EACH_REQUEST"] = False       # don't reset timer on every GET

SITE_URL = os.getenv("SITE_URL", "").rstrip("/")

PADDLE_WEBHOOK_SECRET = os.getenv("PADDLE_WEBHOOK_SECRET", "")
PADDLE_API_KEY        = os.getenv("PADDLE_API_KEY", "")
PADDLE_PRICE_PRO      = os.getenv("PADDLE_PRICE_PRO", "")
PADDLE_PRICE_AGENCY   = os.getenv("PADDLE_PRICE_AGENCY", "")
PADDLE_CLIENT_TOKEN   = os.getenv("PADDLE_CLIENT_TOKEN", "")

AMAZON_CLIENT_ID     = os.getenv("AMAZON_CLIENT_ID", "")
AMAZON_CLIENT_SECRET = os.getenv("AMAZON_CLIENT_SECRET", "")
AMAZON_REDIRECT_URI  = os.getenv("AMAZON_REDIRECT_URI", "")

SENDGRID_API_KEY   = os.getenv("SENDGRID_API_KEY", "")
EMAIL_FROM_ADDRESS = os.getenv("EMAIL_FROM_ADDRESS", "reports@asininsight.com")
EMAIL_FROM_NAME    = os.getenv("EMAIL_FROM_NAME", "ASINInsight")

# Railway gives postgres:// but psycopg2 requires postgresql://
DATABASE_URL = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)

if not PADDLE_WEBHOOK_SECRET:
    if SITE_URL:
        # Production with no webhook secret = unsigned webhooks can activate any plan.
        # Fail hard so the misconfiguration is caught at startup, not at payment time.
        raise RuntimeError(
            "PADDLE_WEBHOOK_SECRET is required when SITE_URL is set (production). "
            "Get it from: Paddle Dashboard → Developer → Notifications → [webhook] → Secret key. "
            "Add it to your Railway environment variables."
        )
    log.warning("PADDLE_WEBHOOK_SECRET is not set — webhook signature verification is disabled (dev only)")

WEBHOOK_MAX_AGE_SECONDS = 300

# ── Rate limiter (in-memory, thread-safe) ─────────────────────────────────
_rate_lock = threading.Lock()
_email_rate: dict[str, list[float]] = {}
EMAIL_RATE_LIMIT  = 3
EMAIL_RATE_WINDOW = 3600

# Diagnose endpoint: 30 requests per hour per IP (generous for legit use,
# blocks scrapers and accidental loops)
_diagnose_rate: dict[str, list[float]] = {}
DIAGNOSE_RATE_LIMIT  = 30
DIAGNOSE_RATE_WINDOW = 3600

# Hard cap on CSV upload size — prevents memory exhaustion from huge files
_MAX_CSV_BYTES = 2 * 1024 * 1024  # 2 MB
# Hard cap on ASINs per request — prevents multi-minute CPU spikes
_MAX_ASINS_PER_REQUEST = 200

# ── CSRF — double-submit cookie ────────────────────────────────────────────
# The token lives in a non-HttpOnly cookie so frontend JS can read it.
# The server checks that every state-changing POST also submits the token
# as X-CSRF-Token header (AJAX) or _csrf hidden field (form POSTs).
# This pattern stops cross-site form attacks without requiring server-side
# token storage — compatible with our stateless HTML+JS architecture.
CSRF_COOKIE_NAME   = "_csrf"
CSRF_COOKIE_SECURE = bool(SITE_URL)   # Secure flag on in prod, off in dev

# ── Activate rate limit (separate from diagnose) ───────────────────────────
# Prevents customer_id enumeration via repeated /api/paddle/activate calls.
_activate_rate: dict[str, list[float]] = {}
ACTIVATE_RATE_LIMIT  = 10   # attempts per window
ACTIVATE_RATE_WINDOW = 300  # 5 minutes

# ── Idempotency cache (in-memory, thread-safe) ────────────────────────────
_events_lock = threading.Lock()
_processed_events: OrderedDict[str, bool] = OrderedDict()
_PROCESSED_EVENTS_MAX = 10_000


# ── Database layer ─────────────────────────────────────────────────────────

def _get_pg_conn():
    import psycopg2
    return psycopg2.connect(DATABASE_URL)


def _get_sqlite_conn():
    path = BASE_DIR / "asininsight.db"
    return sqlite3.connect(str(path))


@contextmanager
def _db():
    """Yield (cursor, placeholder). Commit on success, rollback on error."""
    if DATABASE_URL:
        conn        = _get_pg_conn()
        placeholder = "%s"
    else:
        conn        = _get_sqlite_conn()
        placeholder = "?"
    try:
        cur = conn.cursor()
        yield cur, placeholder
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _init_db():
    """Create tables if they don't exist. Logs a warning instead of crashing on failure."""
    try:
        with _db() as (cur, ph):
            cur.execute("""
                CREATE TABLE IF NOT EXISTS paid_customers (
                    customer_id     TEXT PRIMARY KEY,
                    plan            TEXT NOT NULL,
                    subscription_id TEXT NOT NULL DEFAULT '',
                    updated_at      REAL NOT NULL
                )
            """)
        log.info("Database initialised")
    except Exception as e:
        log.warning("DB init failed (will retry on first request): %s", e)


def _db_upsert_customer(customer_id: str, plan: str, subscription_id: str):
    now = time.time()
    sql = (
        f"INSERT INTO paid_customers (customer_id, plan, subscription_id, updated_at) "
        f"VALUES (%s, %s, %s, %s) "
        f"ON CONFLICT (customer_id) DO UPDATE SET plan=%s, subscription_id=%s, updated_at=%s"
        if DATABASE_URL else
        f"INSERT INTO paid_customers (customer_id, plan, subscription_id, updated_at) "
        f"VALUES (?, ?, ?, ?) "
        f"ON CONFLICT(customer_id) DO UPDATE SET plan=?, subscription_id=?, updated_at=?"
    )
    with _db() as (cur, ph):
        cur.execute(sql, (customer_id, plan, subscription_id, now, plan, subscription_id, now))


def _db_delete_customer(customer_id: str):
    with _db() as (cur, ph):
        cur.execute(
            f"DELETE FROM paid_customers WHERE customer_id = {ph}",
            (customer_id,)
        )


def _db_get_customer(customer_id: str) -> dict | None:
    with _db() as (cur, ph):
        cur.execute(
            f"SELECT plan, subscription_id FROM paid_customers WHERE customer_id = {ph}",
            (customer_id,)
        )
        row = cur.fetchone()
    return {"plan": row[0], "subscription_id": row[1]} if row else None


_init_db()


# ── Rate limiter ───────────────────────────────────────────────────────────

def _check_email_rate(ip: str) -> bool:
    now = time.time()
    window_start = now - EMAIL_RATE_WINDOW
    with _rate_lock:
        hits = [t for t in _email_rate.get(ip, []) if t > window_start]
        if len(hits) >= EMAIL_RATE_LIMIT:
            return False
        hits.append(now)
        _email_rate[ip] = hits
        stale = [k for k, v in _email_rate.items() if not v]
        for k in stale:
            del _email_rate[k]
    return True


def _check_diagnose_rate(ip: str) -> bool:
    """Return True if the IP is within the /api/diagnose rate limit."""
    now = time.time()
    window_start = now - DIAGNOSE_RATE_WINDOW
    with _rate_lock:
        hits = [t for t in _diagnose_rate.get(ip, []) if t > window_start]
        if len(hits) >= DIAGNOSE_RATE_LIMIT:
            return False
        hits.append(now)
        _diagnose_rate[ip] = hits
        stale = [k for k, v in _diagnose_rate.items() if not v]
        for k in stale:
            del _diagnose_rate[k]
    return True


def _client_ip(req) -> str:
    """Extract real client IP, preferring the first hop of X-Forwarded-For."""
    return req.headers.get("X-Forwarded-For", req.remote_addr).split(",")[0].strip()


def _is_same_origin(req) -> bool:
    """
    Soft same-origin guard for API endpoints.

    Checks that the request's Origin or Referer matches our own SITE_URL.
    This blocks casual cross-site AJAX abuse from other domains.
    It does NOT replace authentication — it is a defense-in-depth layer.

    Bypassed when SITE_URL is not configured (dev/test mode).
    Webhooks, health checks, and non-API routes are not affected.
    """
    if not SITE_URL:
        return True  # Dev/test mode — no restriction
    origin  = req.headers.get("Origin", "").rstrip("/")
    referer = req.headers.get("Referer", "")
    site    = SITE_URL.rstrip("/")
    return origin == site or referer.startswith(site + "/") or referer.startswith(site + "?")


# ── Activate rate limiter ─────────────────────────────────────────────────

def _check_activate_rate(ip: str) -> bool:
    """10 activation attempts per 5 min per IP — blocks customer_id brute-force."""
    now = time.time()
    window_start = now - ACTIVATE_RATE_WINDOW
    with _rate_lock:
        hits = [t for t in _activate_rate.get(ip, []) if t > window_start]
        if len(hits) >= ACTIVATE_RATE_LIMIT:
            return False
        hits.append(now)
        _activate_rate[ip] = hits
    return True


# ── CSRF helpers ───────────────────────────────────────────────────────────

def _csrf_set_cookie(response):
    """
    Attach a CSRF token cookie to any HTML response that doesn't already have one.
    NOT HttpOnly — the frontend JS must be able to read it.
    """
    if not request.cookies.get(CSRF_COOKIE_NAME):
        token = secrets.token_hex(32)
        response.set_cookie(
            CSRF_COOKIE_NAME,
            token,
            max_age=86400 * 7,           # 7 days
            secure=CSRF_COOKIE_SECURE,
            httponly=False,              # intentionally readable by JS
            samesite="Strict",
            path="/",
        )
    return response


def _csrf_valid(req) -> bool:
    """
    Double-submit CSRF check: the token submitted in X-CSRF-Token header
    or _csrf form field must match the _csrf cookie value.

    Bypassed when SITE_URL is not set (dev / local test mode).
    Paddle webhook uses its own HMAC — never routed through this check.
    """
    if not SITE_URL:
        return True  # dev bypass
    cookie_val = req.cookies.get(CSRF_COOKIE_NAME, "")
    header_val = req.headers.get("X-CSRF-Token", "")
    form_val   = req.form.get("_csrf", "")
    submitted  = header_val or form_val
    if not cookie_val or not submitted:
        return False
    return hmac.compare_digest(cookie_val, submitted)


# ── CORS preflight handler ─────────────────────────────────────────────────

@app.before_request
def handle_cors_preflight():
    """
    Respond to CORS preflight OPTIONS requests for /api/* routes.
    This allows browsers to POST JSON/form-data to our own domain only.
    Non-API routes are unaffected.
    """
    if request.method == "OPTIONS" and request.path.startswith("/api/"):
        resp = app.make_response("")
        resp.headers["Access-Control-Allow-Origin"]  = SITE_URL or "*"
        resp.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Requested-With, X-CSRF-Token"
        resp.headers["Access-Control-Max-Age"]        = "86400"
        resp.headers["Vary"] = "Origin"
        return resp, 204


@app.before_request
def redirect_www():
    """Redirect www.asininsight.com → asininsight.com."""
    host = request.host.lower()
    if host.startswith("www."):
        url = request.url.replace("://www.", "://", 1)
        return redirect(url, code=301)


# ── Security headers ───────────────────────────────────────────────────────

@app.after_request
def add_security_headers(response):
    path = request.path

    # ── Universal hardening headers ───────────────────────────────────────
    response.headers["X-Content-Type-Options"]             = "nosniff"
    response.headers["X-Frame-Options"]                    = "SAMEORIGIN"
    response.headers["Referrer-Policy"]                    = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"]          = "max-age=63072000; includeSubDomains; preload"
    response.headers["X-Permitted-Cross-Domain-Policies"]  = "none"

    # Permissions-Policy: disable every browser feature we don't use.
    # 'payment=()' is intentional — Paddle opens its own overlay, not a
    # Payment Request API flow, so we don't need to grant this permission.
    response.headers["Permissions-Policy"] = (
        "accelerometer=(), ambient-light-sensor=(), autoplay=(), battery=(), "
        "camera=(), cross-origin-isolated=(), display-capture=(), "
        "document-domain=(), encrypted-media=(), execution-while-not-rendered=(), "
        "execution-while-out-of-viewport=(), fullscreen=(), geolocation=(), "
        "gyroscope=(), keyboard-map=(), magnetometer=(), microphone=(), "
        "midi=(), navigation-override=(), payment=(), picture-in-picture=(), "
        "publickey-credentials-get=(), screen-wake-lock=(), sync-xhr=(), "
        "usb=(), web-share=(), xr-spatial-tracking=()"
    )

    # Content-Security-Policy.
    # 'unsafe-inline' for script-src and style-src is required because all
    # JS and CSS is currently inline in the HTML files (no bundler step).
    # TODO: extract inline scripts to separate .js files and replace
    # 'unsafe-inline' with per-file hashes or a nonce-based approach.
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.paddle.com; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:; "
        "connect-src 'self' https://sandbox-api.paddle.com https://api.paddle.com; "
        "frame-src https://sandbox-buy.paddle.com https://buy.paddle.com; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )

    # ── Cache control — no-store only where it matters ────────────────────
    # Static assets (sample data, logos) can be cached normally.
    # API responses, account pages, and checkout flows must not be cached.
    is_sensitive = (
        path.startswith("/api/") or
        path.startswith("/webhook/") or
        path.startswith("/amazon/") or
        path in ("/tool", "/success", "/checkout/free", "/health")
    )
    if is_sensitive:
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"]        = "no-cache"
    # HTML pages: no-cache (always revalidate) but allow browser to store
    elif response.content_type.startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache"

    # ── CORS — restrict API endpoints to own domain ───────────────────────
    if path.startswith("/api/"):
        response.headers["Access-Control-Allow-Origin"] = SITE_URL or "*"
        response.headers["Vary"] = "Origin"

    # ── CSRF cookie — attach to HTML page responses ───────────────────────
    if response.content_type.startswith("text/html"):
        _csrf_set_cookie(response)

    return response


_ERROR_HTML_FALLBACK = """<!DOCTYPE html>
<html><head><title>Error</title>
<style>body{font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f8fafc;}
.box{text-align:center;padding:40px;}</style></head>
<body><div class="box">
<h1 style="font-size:48px;margin:0">⚠️</h1>
<h2 style="color:#0f172a">Something went wrong</h2>
<p style="color:#64748b">Please try again or <a href="/">go back home</a>.</p>
</div></body></html>"""


def _error_page(code: int):
    try:
        return send_from_directory(BASE_DIR, "error.html"), code
    except Exception:
        return _ERROR_HTML_FALLBACK, code


@app.errorhandler(404)
def not_found(e):
    return _error_page(404)


@app.errorhandler(500)
def server_error(e):
    return _error_page(500)


# ── Health check ───────────────────────────────────────────────────────────

@app.route("/health")
def health():
    """Used by Railway to verify the server is alive."""
    return jsonify({"status": "ok"}), 200


# ── Pages ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "landing.html")


@app.route("/tool")
def tool():
    if not session.get("plan"):
        return redirect("/")
    return send_from_directory(BASE_DIR, "app.html")


@app.route("/logo.svg")
def logo():
    return send_from_directory(BASE_DIR, "logo.svg")


@app.route("/logo_b.svg")
def logo_b():
    return send_from_directory(BASE_DIR, "logo_b.svg")


@app.route("/logo_preview.html")
def logo_preview():
    if SITE_URL:
        return _error_page(404)  # dev-only artifact — not served in production
    return send_from_directory(BASE_DIR, "logo_preview.html")


@app.route("/sample_data/<path:filename>")
def sample_data(filename):
    return send_from_directory(BASE_DIR / "sample_data", filename)


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(BASE_DIR / "static", filename)


@app.route("/blog")
def blog():
    return send_from_directory(BASE_DIR, "blog.html")


@app.route("/blog/high-acos-fix")
def blog_high_acos():
    return send_from_directory(BASE_DIR / "blog", "high-acos-fix.html")


@app.route("/blog/ctr-fix")
def blog_ctr_fix():
    return send_from_directory(BASE_DIR / "blog", "ctr-fix.html")


@app.route("/blog/business-report-guide")
def blog_business_report():
    return send_from_directory(BASE_DIR / "blog", "business-report-guide.html")


@app.route("/sitemap.xml")
def sitemap():
    return send_from_directory(BASE_DIR / "static", "sitemap.xml",
                                mimetype="application/xml")


@app.route("/robots.txt")
def robots():
    return send_from_directory(BASE_DIR / "static", "robots.txt",
                                mimetype="text/plain")


@app.route("/pricing")
def pricing():
    return send_from_directory(BASE_DIR, "pricing.html")


@app.route("/success")
def success():
    return send_from_directory(BASE_DIR, "success.html")


@app.route("/cancel")
def cancel():
    # Send back to pricing with a flag — pricing.html shows a "no charge" notice
    return redirect("/pricing?cancelled=1")


@app.route("/privacy")
def privacy():
    return send_from_directory(BASE_DIR, "privacy.html")


@app.route("/terms")
def terms():
    return send_from_directory(BASE_DIR, "terms.html")


@app.route("/refund")
def refund():
    return send_from_directory(BASE_DIR, "refund.html")


# ── Paddle config for frontend ─────────────────────────────────────────────

@app.route("/api/paddle-config")
def paddle_config():
    environment = "sandbox" if PADDLE_CLIENT_TOKEN.startswith("test_") else "production"
    return jsonify({
        "client_token": PADDLE_CLIENT_TOKEN,
        "price_pro":    PADDLE_PRICE_PRO,
        "price_agency": PADDLE_PRICE_AGENCY,
        "environment":  environment,
        "ready":        bool(PADDLE_CLIENT_TOKEN and PADDLE_PRICE_PRO and PADDLE_PRICE_AGENCY),
    })


# ── Free plan ──────────────────────────────────────────────────────────────

@app.route("/checkout/free", methods=["POST"])
def checkout_free():
    if not _csrf_valid(request):
        log.warning("CSRF check failed on /checkout/free (IP: %s)", _client_ip(request))
        return _error_page(403)
    session["plan"]   = "free"
    session.permanent = True
    return redirect("/tool")


# ── Paddle Webhook ─────────────────────────────────────────────────────────

@app.route("/webhook/paddle", methods=["POST"])
def paddle_webhook():
    raw_body  = request.get_data()
    signature = request.headers.get("Paddle-Signature", "")

    if PADDLE_WEBHOOK_SECRET:
        try:
            parts = dict(p.split("=", 1) for p in signature.split(";"))
            ts    = parts.get("ts", "")
            h1    = parts.get("h1", "")

            if not ts or not h1:
                return jsonify({"error": "malformed signature"}), 400

            try:
                event_ts  = int(ts)
                event_age = time.time() - event_ts
                # Reject replays (too old) AND fabricated future timestamps
                if event_age > WEBHOOK_MAX_AGE_SECONDS:
                    log.warning("Webhook replay rejected: age=%.0fs", event_age)
                    return jsonify({"error": "webhook timestamp too old"}), 400
                if event_age < -30:
                    log.warning("Webhook future timestamp rejected: age=%.0fs", event_age)
                    return jsonify({"error": "webhook timestamp in future"}), 400
            except (ValueError, OverflowError):
                return jsonify({"error": "invalid timestamp"}), 400

            try:
                signed_payload = f"{ts}:{raw_body.decode('utf-8')}"
            except UnicodeDecodeError:
                return jsonify({"error": "invalid payload encoding"}), 400

            expected = hmac.new(
                PADDLE_WEBHOOK_SECRET.encode(),
                signed_payload.encode(),
                hashlib.sha256
            ).hexdigest()

            # Both values are hex strings — compare_digest prevents timing attacks
            if not isinstance(h1, str) or not hmac.compare_digest(expected, h1):
                log.warning("Paddle webhook signature mismatch")
                return jsonify({"error": "invalid signature"}), 401
        except Exception:
            log.exception("Unexpected error verifying Paddle webhook signature")
            return jsonify({"error": "signature error"}), 400

    event = request.get_json(force=True, silent=True)
    if not event or not isinstance(event, dict):
        return jsonify({"error": "invalid json"}), 400

    event_type = event.get("event_type", "")
    event_id   = event.get("notification_id", "")

    # Idempotency: check AND mark in a single lock to eliminate race condition
    with _events_lock:
        if event_id and event_id in _processed_events:
            log.info("Skipping duplicate Paddle event: %s", event_id)
            return jsonify({"status": "ok"}), 200
        if event_id:
            _processed_events[event_id] = True
            if len(_processed_events) > _PROCESSED_EVENTS_MAX:
                for _ in range(1000):
                    _processed_events.popitem(last=False)

    if event_type in ("subscription.activated", "subscription.updated", "transaction.completed"):
        data            = event.get("data", {})
        customer_id     = data.get("customer_id", "")
        subscription_id = data.get("id", "")
        items           = data.get("items", [])

        if isinstance(items, list):
            for item in items:
                price_id = item.get("price", {}).get("id", "")
                if not price_id or not customer_id:
                    continue
                if PADDLE_PRICE_AGENCY and price_id == PADDLE_PRICE_AGENCY:
                    plan = "agency"
                elif PADDLE_PRICE_PRO and price_id == PADDLE_PRICE_PRO:
                    plan = "pro"
                else:
                    continue

                try:
                    _db_upsert_customer(customer_id, plan, subscription_id)
                    log.info("Plan updated to %s | customer=%s | sub=%s", plan, customer_id, subscription_id)
                except Exception as e:
                    log.error("DB error saving customer %s: %s", customer_id, e)
                    return jsonify({"error": "db error"}), 500

    elif event_type in ("subscription.cancelled", "subscription.paused"):
        data        = event.get("data", {})
        customer_id = data.get("customer_id", "")
        if customer_id:
            try:
                _db_delete_customer(customer_id)
                log.info("Plan revoked | customer=%s | event=%s", customer_id, event_type)
            except Exception as e:
                log.error("DB error revoking customer %s: %s", customer_id, e)
                return jsonify({"error": "db error"}), 500

    return jsonify({"status": "ok"}), 200


# ── Paddle post-checkout activation ───────────────────────────────────────

@app.route("/api/paddle/activate", methods=["POST"])
def paddle_activate():
    ip = _client_ip(request)
    if not _check_activate_rate(ip):
        return jsonify({"ok": False, "error": "Too many requests. Please wait and try again."}), 429

    data        = request.get_json(force=True, silent=True) or {}
    customer_id = (data.get("customer_id") or "").strip()[:100]

    if not customer_id:
        return jsonify({"ok": False, "error": "missing customer_id"}), 400

    # Paddle customer IDs always start with "ctm_" followed by alphanumeric chars.
    # Reject anything else — prevents garbage DB lookups and brute-force enumeration.
    if (not customer_id.startswith("ctm_")
            or len(customer_id) < 10
            or not customer_id[4:].replace("-", "").isalnum()):
        return jsonify({"ok": False, "error": "invalid customer_id"}), 400

    try:
        record = _db_get_customer(customer_id)
    except Exception:
        return jsonify({"ok": False, "error": "db error"}), 500

    if not record:
        return jsonify({"ok": False, "error": "payment_not_confirmed"}), 402

    session["plan"]                   = record["plan"]
    session["paddle_customer_id"]     = customer_id
    session["paddle_subscription_id"] = record.get("subscription_id", "")
    session.permanent                 = True   # honour the 30-day lifetime
    return jsonify({"ok": True, "plan": record["plan"]})


# ── Email Report ───────────────────────────────────────────────────────────

@app.route("/api/send-report", methods=["POST"])
def send_report():
    client_ip = _client_ip(request)
    if not _check_email_rate(client_ip):
        return jsonify({"ok": False, "error": "Too many requests. Please try again later."}), 429

    data   = request.get_json(force=True, silent=True) or {}
    email  = (data.get("email") or "").strip()[:254]
    report = data.get("report") or {}

    if not isinstance(report, dict):
        return jsonify({"ok": False, "error": "Invalid report"}), 400

    if not email or "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"ok": False, "error": "Invalid email"}), 400

    if not SENDGRID_API_KEY:
        return jsonify({"ok": True, "note": "email_not_configured"})

    try:
        total    = int(report.get("total_asins") or 0)
        critical = int(report.get("critical_count") or 0)
        score    = int(report.get("weakest_score") or 0)
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "Invalid report data"}), 400

    weakest = html.escape(str(report.get("weakest_asin") or "N/A")[:100])

    raw_blockers = report.get("top_blockers")
    if not isinstance(raw_blockers, list):
        raw_blockers = []
    blockers = [html.escape(str(b)) for b in raw_blockers[:5] if b]

    blockers_html = (
        "".join(f"<li style='margin-bottom:6px;'>⚠️ {b}</li>" for b in blockers)
        if blockers else "<li>No major blockers found.</li>"
    )

    html_body = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:560px;margin:0 auto;background:#f8fafc;padding:32px 16px;">
      <div style="background:#fff;border-radius:16px;padding:32px;box-shadow:0 1px 4px rgba(0,0,0,.06);">
        <div style="font-size:24px;font-weight:800;color:#0f172a;margin-bottom:4px;">ASIN<span style="color:#2563eb;">Insight</span></div>
        <p style="color:#64748b;font-size:14px;margin:0 0 24px;">Your diagnosis report is ready</p>
        <div style="background:#eff6ff;border-radius:12px;padding:20px;margin-bottom:24px;">
          <div style="font-size:13px;color:#1e40af;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px;">Portfolio Summary</div>
          <div style="display:flex;gap:24px;flex-wrap:wrap;">
            <div><div style="font-size:28px;font-weight:800;color:#0f172a;">{total}</div><div style="font-size:12px;color:#64748b;">ASINs analyzed</div></div>
            <div><div style="font-size:28px;font-weight:800;color:#991b1b;">{critical}</div><div style="font-size:12px;color:#64748b;">Critical issues</div></div>
            <div><div style="font-size:28px;font-weight:800;color:#0f172a;">{score}</div><div style="font-size:12px;color:#64748b;">Weakest score</div></div>
          </div>
        </div>
        <div style="margin-bottom:24px;">
          <div style="font-size:13px;color:#374151;font-weight:600;margin-bottom:10px;">🔴 Top Issues — {weakest}</div>
          <ul style="margin:0;padding-left:20px;color:#374151;font-size:14px;line-height:1.7;">
            {blockers_html}
          </ul>
        </div>
        <a href="https://asininsight.com/tool" style="display:block;text-align:center;background:#1d4ed8;color:#fff;text-decoration:none;padding:14px 24px;border-radius:8px;font-weight:600;font-size:15px;">
          View Full Report →
        </a>
        <p style="margin:24px 0 0;font-size:12px;color:#94a3b8;text-align:center;">
          ASINInsight · <a href="https://asininsight.com/privacy" style="color:#94a3b8;">Privacy</a> · <a href="https://asininsight.com/terms" style="color:#94a3b8;">Terms</a>
        </p>
      </div>
    </div>
    """

    try:
        sg_resp = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {SENDGRID_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "personalizations": [{"to": [{"email": email}]}],
                "from": {"email": EMAIL_FROM_ADDRESS, "name": EMAIL_FROM_NAME},
                "subject": f"Your ASINInsight Report — {total} ASINs, {critical} Critical Issues",
                "content": [{"type": "text/html", "value": html_body}],
            },
            timeout=10,
        )
        if sg_resp.status_code in (200, 202):
            return jsonify({"ok": True})
        log.error("SendGrid non-2xx: status=%s body=%s", sg_resp.status_code, sg_resp.text[:200])
        return jsonify({"ok": False, "error": "Email delivery failed. Please try again."}), 500
    except Exception as e:
        log.error("SendGrid exception: %s", e)
        return jsonify({"ok": False, "error": "Email delivery failed. Please try again."}), 500


# ── Detection layer ───────────────────────────────────────────────────────
#
# Converts raw Amazon Business Report CSV rows into structured blockers.
# Pipeline: raw CSV row  →  normalize()  →  detect()  →  /api/diagnose
#
# All thresholds are MVP heuristics — label clearly, revisit with real data.

# ── CSV structure validator ────────────────────────────────────────────────
#
# Amazon Business Report CSVs always contain at least a handful of well-known
# column headers. We check for 2+ matches before parsing to reject:
#   • binary files accidentally uploaded
#   • arbitrary Excel/CSV exports from other systems
#   • path-traversal payloads disguised as CSV
#   • oversized header-injection attempts
#
_CSV_KNOWN_HEADERS: frozenset[str] = frozenset({
    "asin", "(child) asin",
    "sessions", "sessions - total", "sessions_30d",
    "unit session percentage", "unit session percentage - total",
    "units ordered", "ordered units",
    "ordered product sales", "ordered product sales - total",
    "click-through rate (ctr)", "click through rate",
    "page views", "page views - total",
    "buy box percentage", "featured offer percentage",
    "average customer review",
})


def _validate_csv_structure(first_line: str) -> tuple[bool, str | None]:
    """
    Verify the first CSV row contains ≥2 known Amazon Business Report headers.
    Returns (is_valid, error_message_or_None).
    """
    if not first_line or len(first_line) > 8192:
        return False, "CSV header row is missing or too long to be a valid Business Report."
    lower = first_line.lower()
    hits  = sum(1 for h in _CSV_KNOWN_HEADERS if h in lower)
    if hits < 2:
        return False, (
            "This doesn't look like an Amazon Business Report. "
            "Please download the 'Detail Page Sales and Traffic by Child Item' CSV "
            "from Seller Central → Reports → Business Reports."
        )
    return True, None


# Column name → internal key mapping (covers all known Amazon report variants)
_COL_MAP: dict[str, str] = {
    # ASIN
    "(child) asin":                   "asin",
    "asin":                           "asin",
    "title":                          "title",
    "category":                       "category",
    # Traffic
    "sessions":                       "sessions_30d",
    "sessions - total":               "sessions_30d",
    "sessions_30d":                   "sessions_30d",
    "page views":                     "page_views",
    "page views - total":             "page_views",
    # CTR
    "click-through rate (ctr)":       "ctr",
    "click through rate":             "ctr",
    "ctr":                            "ctr",
    # Conversion
    "unit session percentage":        "conversion_rate",
    "unit session percentage - total":"conversion_rate",
    "conversion rate":                "conversion_rate",
    "conversion_rate":                "conversion_rate",
    "cvr":                            "conversion_rate",
    "units ordered":                  "units_ordered_30d",
    "ordered units":                  "units_ordered_30d",
    "units_ordered_30d":              "units_ordered_30d",
    # Revenue / price
    "ordered product sales":          "revenue_30d",
    "ordered product sales - total":  "revenue_30d",
    "revenue_30d":                    "revenue_30d",
    "price":                          "price",
    # Ads
    "ad spend":                       "ad_spend_30d",
    "advertising spend":              "ad_spend_30d",
    "ad_spend_30d":                   "ad_spend_30d",
    "ad sales":                       "ad_sales_30d",
    "advertising sales":              "ad_sales_30d",
    "ad_sales_30d":                   "ad_sales_30d",
    "acos":                           "acos",
    "advertising cost of sale":       "acos",
    # Inventory
    "days of cover":                  "days_of_cover",
    "days_of_cover":                  "days_of_cover",
    "afn fulfillable quantity":       "units_available",
    "units available":                "units_available",
    # Trust
    "average customer review":        "rating",
    "customer rating":                "rating",
    "rating":                         "rating",
    "customer reviews":               "review_count",
    "number of customer reviews":     "review_count",
    "review_count":                   "review_count",
    # Listing quality
    "images count":                   "images_count",
    "number of images":               "images_count",
    "images_count":                   "images_count",
    "bullet count":                   "bullet_count",
    "number of bullets":              "bullet_count",
    "bullet_count":                   "bullet_count",
    "has a+":                         "has_a_plus",
    "has_a_plus":                     "has_a_plus",
    "a+ content":                     "has_a_plus",
    # Buy Box
    "buy box percentage":             "buy_box_pct",
    "buy box %":                      "buy_box_pct",
    "buy_box_pct":                    "buy_box_pct",
    "featured offer percentage":      "buy_box_pct",
}

# Fields that are ratios (0–1 range); % strings divided by 100
_RATIO_FIELDS = {"conversion_rate", "ctr", "acos", "buy_box_pct"}


def _normalize_value(key: str, raw) -> float | int | bool | None:
    """Convert a raw cell value to the correct Python type for key."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        return raw
    if key in ("asin", "title", "category"):
        text = str(raw).strip()
        return text or None
    if key == "has_a_plus":
        return str(raw).strip().lower() in ("1", "true", "yes", "y")
    s = str(raw).strip().replace(",", "").replace("$", "")
    is_pct = s.endswith("%")
    try:
        n = float(s[:-1] if is_pct else s)
    except ValueError:
        return None
    if is_pct:
        return n / 100.0
    # If key is a ratio field but value > 1.5 it was expressed as a percentage without %
    if key in _RATIO_FIELDS and n > 1.5:
        return n / 100.0
    return n


def normalize(row: dict) -> dict:
    """Map any raw CSV/JSON row to internal field names."""
    out: dict = {}
    for raw_key, value in row.items():
        canon = _COL_MAP.get(raw_key.strip().lower())
        if canon and canon not in out:
            v = _normalize_value(canon, value)
            if v is not None:
                out[canon] = v
    # Pass through any key already in canonical form that wasn't mapped above
    for k, v in row.items():
        if k in _COL_MAP.values() and k not in out:
            nv = _normalize_value(k, v)
            if nv is not None:
                out[k] = nv
    return out


def parse_csv_text(text: str) -> list[dict]:
    """Convert a raw Amazon CSV into diagnose-ready ASIN payloads."""
    if not text or not text.strip():
        return []
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    items: list[dict] = []
    for index, row in enumerate(reader, start=1):
        if not isinstance(row, dict) or not any(str(v or "").strip() for v in row.values()):
            continue
        cleaned = {str(k).strip(): v for k, v in row.items() if k is not None}
        lowered = {k.lower(): v for k, v in cleaned.items()}
        metrics = normalize(cleaned)
        asin = str(metrics.get("asin") or lowered.get("asin") or lowered.get("(child) asin") or f"ROW-{index}").strip()
        if not asin:
            continue
        metrics["asin"] = asin
        item = {"asin": asin, "metrics": metrics, "blockers": []}
        title = str(lowered.get("title") or "").strip()
        category = str(lowered.get("category") or "").strip()
        if title:
            item["title"] = title
        if category:
            item["category"] = category
        items.append(item)
    return items


def _safe_decode_csv(raw: bytes) -> tuple[str | None, str | None]:
    """
    Decode raw CSV bytes with UTF-8 (BOM-stripped) then Latin-1 fallback.
    Returns (text, None) on success, (None, error_message) on failure.
    Rejects payloads with excessive null bytes (binary disguised as text).
    """
    # Heuristic: >1% null bytes = likely binary, not CSV
    if raw.count(b"\x00") > max(1, len(raw) // 100):
        return None, "Uploaded file appears to be binary, not a CSV."
    try:
        return raw.decode("utf-8-sig", errors="strict"), None
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode("latin-1"), None
    except Exception:
        return None, "File could not be decoded. Please save it as UTF-8 CSV and try again."


def _extract_diagnose_items(req) -> tuple[list[dict], str | None]:
    uploaded = req.files.get("file") or req.files.get("csv")
    if uploaded and uploaded.filename:
        raw = uploaded.read()
        if len(raw) > _MAX_CSV_BYTES:
            return [], f"File too large. Maximum size is {_MAX_CSV_BYTES // (1024*1024)} MB."
        text, err = _safe_decode_csv(raw)
        if err:
            return [], err
        first_line = (text or "").split("\n")[0]
        ok, struct_err = _validate_csv_structure(first_line)
        if not ok:
            return [], struct_err
        items = parse_csv_text(text)
        return items, (None if items else "No valid ASIN rows found in the CSV.")

    if (req.mimetype or "").startswith("text/csv"):
        raw = req.get_data(cache=False)
        if len(raw) > _MAX_CSV_BYTES:
            return [], f"File too large. Maximum size is {_MAX_CSV_BYTES // (1024*1024)} MB."
        text, err = _safe_decode_csv(raw)
        if err:
            return [], err
        first_line = (text or "").split("\n")[0]
        ok, struct_err = _validate_csv_structure(first_line)
        if not ok:
            return [], struct_err
        items = parse_csv_text(text)
        return items, (None if items else "No valid ASIN rows found in the CSV.")

    data = req.get_json(force=True, silent=True) or {}
    csv_text = data.get("csv_text") or data.get("csv")
    if isinstance(csv_text, str) and csv_text.strip():
        if len(csv_text.encode()) > _MAX_CSV_BYTES:
            return [], f"CSV text too large. Maximum size is {_MAX_CSV_BYTES // (1024*1024)} MB."
        first_line = csv_text.split("\n")[0]
        ok, struct_err = _validate_csv_structure(first_line)
        if not ok:
            return [], struct_err
        items = parse_csv_text(csv_text)
        return items, (None if items else "No valid ASIN rows found in the CSV.")

    if "asins" in data and isinstance(data["asins"], list):
        items = [a for a in data["asins"][:_MAX_ASINS_PER_REQUEST] if isinstance(a, dict)]
        return items, (None if items else "No valid ASIN entries provided.")

    if any(k in data for k in ("asin", "blockers", "score", "metrics")):
        return [data], None

    return [], "Provide an ASIN, ASIN list, or CSV file."


# ── Confidence layer (multi-factor) ──────────────────────────────────────
#
# Confidence reflects three independent factors:
#   1. Are the key metrics for this area present in the data?
#   2. Is the sample size large enough to trust the signal?
#   3. Is the signal strong (far from the threshold) or just barely crossing it?
#
# Score starts at 3 (high). Each limiting factor deducts points.
#   Score 3 → 'high'    (all signals clear, data complete)
#   Score 2 → 'medium'  (one limiting factor)
#   Score ≤1 → 'low'    (data sparse, signal marginal, or key field missing)
#
# Confidence is NEVER set to 'high' when the data doesn't support it.

_REQUIRED_FIELDS: dict[str, list[str]] = {
    "traffic":       ["ctr", "sessions_30d"],
    "ads":           ["acos", "ad_spend_30d"],
    "inventory":     ["days_of_cover"],
    "conversion":    ["conversion_rate", "sessions_30d"],
    "trust-rating":  ["rating", "review_count"],
    "trust-reviews": ["review_count"],
    "listing":       [],
    "buy_box":       ["buy_box_pct"],
}


def _confidence(area: str, m: dict, gap: float = 0.5) -> tuple[str, str | None]:
    """
    Multi-factor confidence: (level, note).
    level — 'high' | 'medium' | 'low'
    note  — plain-English reason for any degradation, or None.
    """
    score = 3
    notes: list[str] = []

    ses     = float(m.get("sessions_30d") or 0)
    reviews = int(m.get("review_count") or 0)
    spend   = float(m.get("ad_spend_30d") or 0)

    # Factor 1 — required key fields present?
    missing = [f for f in _REQUIRED_FIELDS.get(area, []) if not m.get(f)]
    if missing:
        score -= 2
        notes.append(f"key data missing ({', '.join(missing)})")

    # Factor 2 — sample size adequate for this area?
    if area == "traffic":
        if ses < 100:    score -= 2; notes.append("fewer than 100 sessions — unreliable sample")
        elif ses < 300:  score -= 1; notes.append("fewer than 300 sessions")
    elif area in ("conversion", "listing"):
        if reviews < 10:   score -= 2; notes.append("fewer than 10 reviews")
        elif reviews < 25: score -= 1; notes.append("fewer than 25 reviews")
    elif area in ("trust-rating", "trust-reviews"):
        if reviews < 5:    score -= 2; notes.append("fewer than 5 reviews — too few to judge")
        elif reviews < 15: score -= 1; notes.append("fewer than 15 reviews")
    elif area == "ads":
        if spend < 50:    score -= 2; notes.append("less than $50 ad spend — insufficient data")
        elif spend < 200:  score -= 1; notes.append("less than $200 ad spend")

    # Factor 3 — signal strength (how far past the threshold?)
    if gap < 0.20:
        score -= 1
        notes.append("metric is close to the healthy benchmark")

    level = "high" if score >= 3 else ("medium" if score == 2 else "low")
    return level, ("; ".join(notes) if notes else None)


# ── Gap scoring ────────────────────────────────────────────────────────────

def _gap_score(area: str, m: dict) -> float:
    """
    Normalized distance from healthy benchmark: 0.0 (at benchmark) to 1.0 (worst).
    Used to weight priority and calibrate confidence. All benchmarks are MVP heuristics.
    """
    ctr     = float(m.get("ctr") or 0)
    acos    = float(m.get("acos") or 0)
    cover   = float(m.get("days_of_cover") or 99)
    cvr     = float(m.get("conversion_rate") or 0)
    box     = float(m.get("buy_box_pct") or 1)
    rating  = float(m.get("rating") or 0)
    reviews = int(m.get("review_count") or 0)

    if area == "traffic":
        # Benchmark: 0.40% CTR. No CTR data → assume moderate gap.
        return min(max((0.004 - ctr) / 0.004, 0.0), 1.0) if ctr > 0 else 0.5
    if area == "ads":
        # Benchmark: 30% ACOS. Worst case: 100% ACOS.
        return min(max((acos - 0.30) / 0.70, 0.0), 1.0) if acos > 0 else 0.0
    if area == "inventory":
        # Benchmark: 14 days of cover.
        return min(max((14 - cover) / 14, 0.0), 1.0) if cover < 14 else 0.0
    if area == "conversion":
        # Benchmark: 2.5% CVR. No CVR data → assume moderate gap.
        return min(max((0.025 - cvr) / 0.025, 0.0), 1.0) if cvr > 0 else 0.5
    if area == "buy_box":
        # 0% buy box = 1.0 gap; 100% buy box = 0.0 gap.
        return min(max(1.0 - box, 0.0), 1.0)
    if area == "trust-rating":
        # Benchmark: 4.0 stars.
        return min(max((4.0 - rating) / 4.0, 0.0), 1.0) if rating > 0 else 0.5
    if area == "trust-reviews":
        # Benchmark: 25 reviews.
        return min(max((25 - reviews) / 25, 0.0), 1.0) if reviews > 0 else 0.8
    return 0.5


# ── Priority scoring ───────────────────────────────────────────────────────

_SEV_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def _priority_score(sev: str, gap: float) -> float:
    """severity² × (0.5 + gap×0.5) — urgency × distance from benchmark."""
    return (_SEV_RANK.get(sev, 1) ** 2) * (0.5 + gap * 0.5)


# ── Soft-zone thresholds (Task 2: consistency across similar inputs) ────────
#
# Prevents cliff-edge severity flips when a metric is within 10% of a boundary.
# Example: CTR 0.0019 vs 0.0021 should both produce "high", not "critical"/"high".
# A 10% soft zone around each boundary returns the milder severity.
# This ensures small real-world measurement variations don't produce large output swings.

_SOFT_ZONE = 0.10  # MVP heuristic: 10% band around each threshold


def _soft_sev(
    value: float,
    thresholds: list[tuple[float, str, str]],
    direction: str = "below",
) -> str:
    """
    Assign severity with hysteresis to prevent boundary cliff edges.

    thresholds: list of (boundary, severity_if_crossed, milder_severity)
                ordered from most to least severe boundary.
    direction:  'below' — fires when value < boundary (CTR, CVR, cover, rating)
                'above' — fires when value > boundary (ACOS)

    Within SOFT_ZONE of a boundary → use milder_severity.
    Outside all thresholds → returns 'none' (no rule fires).
    Only applies to continuous float metrics; integer fields use direct comparison.
    """
    _EPS = 1e-9  # float tolerance: prevents IEEE 754 rounding from excluding exact boundaries
    for boundary, sev, milder in thresholds:
        if direction == "below":
            if value < boundary:
                # Relative distance from boundary. +EPS handles float imprecision at
                # exact N% (e.g. (0.002-0.0018)/0.002 = 0.100000000005 without the tolerance).
                if (boundary - value) / boundary <= _SOFT_ZONE + _EPS:
                    return milder
                return sev
        else:  # above
            if value > boundary:
                if (value - boundary) / boundary <= _SOFT_ZONE + _EPS:
                    return milder
                return sev
    return "none"


# ── Validation layer (Task 1: accuracy) ────────────────────────────────────
#
# After detecting blockers, each one is cross-checked against the raw metrics
# to confirm the supporting signal is actually present.
# If the key metric is absent or doesn't show a problem, confidence is downgraded
# and a validation_warning is attached.

_AREA_VALIDATORS: dict[str, object] = {
    "traffic":       lambda m: float(m.get("ctr") or 0) > 0,
    "ads":           lambda m: float(m.get("acos") or 0) > 0 and float(m.get("ad_spend_30d") or 0) > 0,
    "inventory":     lambda m: 0 < float(m.get("days_of_cover") or 99) < 14,
    "conversion":    lambda m: float(m.get("conversion_rate") or 0) > 0 and float(m.get("sessions_30d") or 0) > 0,
    "trust-rating":  lambda m: 0 < float(m.get("rating") or 0) < 4.0 and int(m.get("review_count") or 0) >= 5,
    "trust-reviews": lambda m: 0 < int(m.get("review_count") or 0) < 25,
    "listing":       lambda m: True,
    "buy_box":       lambda m: float(m.get("buy_box_pct") or 0) > 0,
}


def _validate_blocker(blocker: dict, m: dict) -> dict:
    """
    Verify a blocker's area is supported by the underlying metrics.
    Returns the blocker unchanged if valid, or with downgraded confidence
    and a validation_warning if the supporting metric is absent or inconsistent.
    """
    area      = blocker.get("area", "")
    validator = _AREA_VALIDATORS.get(area)
    if validator is None:
        return blocker

    try:
        supported = validator(m)
    except Exception:
        supported = False

    if not supported:
        conf     = blocker.get("confidence", "medium")
        downgrade = {"high": "medium", "medium": "low", "low": "low"}
        return {
            **blocker,
            "confidence":         downgrade[conf],
            "validation_warning": (
                f"Diagnosis may not fully match the data — "
                f"the key metric for '{area}' is absent or shows no problem."
            ),
        }
    return blocker


# ── Contradiction detection (Task 5: sanity checks) ────────────────────────
#
# Detects logically inconsistent metric combinations that reduce overall confidence.
# These don't block the diagnosis but are surfaced as data_quality warnings.

def _detect_contradictions(m: dict) -> list[str]:
    """
    Return a list of mixed-signal descriptions found in the metrics.
    Each entry is a plain-English statement a seller can understand.
    """
    contradictions: list[str] = []

    ctr     = float(m.get("ctr") or 0)
    cvr     = float(m.get("conversion_rate") or 0)
    ses     = float(m.get("sessions_30d") or 0)
    acos    = float(m.get("acos") or 0)
    spend   = float(m.get("ad_spend_30d") or 0)
    rating  = float(m.get("rating") or 0)
    reviews = int(m.get("review_count") or 0)
    cover   = float(m.get("days_of_cover") or 99)

    # Healthy CTR but very low sessions → impression volume is the constraint, not CTR
    if ctr >= 0.004 and ses > 0 and ses < 200:
        contradictions.append(
            f"CTR is healthy ({ctr:.2%}) but sessions are low ({int(ses)}) — "
            "the problem is insufficient impressions, not click rate."
        )

    # Very strong conversion flagged as a conversion issue → contradicts itself
    if cvr > 0.05 and ses > 100:
        contradictions.append(
            f"Conversion rate is {cvr:.1%} — well above the 2.5% baseline. "
            "Conversion is unlikely to be the main constraint."
        )

    # ACOS flagged but spend is negligible → reading is statistically unreliable
    if acos > 0.35 and 0 < spend < 20:
        contradictions.append(
            f"ACOS is {acos:.0%} but total ad spend is only ${spend:.0f} — "
            "too little data for a reliable ACOS diagnosis."
        )

    # Strong rating and significant review base → trust is not the bottleneck
    if rating >= 4.5 and reviews >= 20:
        contradictions.append(
            f"Rating is {rating:.1f} with {reviews} reviews — "
            "trust signals are strong; a different metric is the likely constraint."
        )

    # Very low sessions with critical inventory → actual sell-through risk is lower than cover implies
    if 0 < cover < 5 and ses < 50:
        contradictions.append(
            f"Inventory cover is {int(cover)} days but sessions are very low ({int(ses)}) — "
            "actual stockout risk may be lower than the days-of-cover number suggests."
        )

    return contradictions


# ── Data completeness check (Task 5: sanity checks) ────────────────────────

_CORE_FIELDS: dict[str, str] = {
    "sessions_30d":    "sessions",
    "conversion_rate": "conversion rate",
    "ctr":             "CTR",
    "days_of_cover":   "inventory cover",
    "rating":          "rating",
    "review_count":    "review count",
}


def _check_completeness(m: dict) -> tuple[list[str], bool]:
    """
    Returns (list_of_missing_field_labels, is_partial_diagnosis).
    is_partial_diagnosis = True when ≥2 core fields are absent.
    A partial diagnosis still runs but its confidence is structurally limited.
    """
    missing = [label for field, label in _CORE_FIELDS.items() if not m.get(field)]
    return missing, len(missing) >= 2


# ── Rule definitions ───────────────────────────────────────────────────────

def _build_rules(m: dict) -> list[dict]:
    """
    Produce candidate blockers for all 8 detection areas.

    Design principles applied here:
    - Soft-zone thresholds (Task 2): ±10% around each boundary prevents cliff edges
    - Explicit WHY strings (Task 3): every why includes metric value + threshold + implication
    - weight overrides default PEN for inventory (cascading-damage justification)
    - All thresholds are MVP heuristics — revisit with real conversion data
    """
    ctr     = float(m.get("ctr") or 0)
    ses     = float(m.get("sessions_30d") or 0)
    cvr     = float(m.get("conversion_rate") or 0)
    acos    = float(m.get("acos") or 0)
    spend   = float(m.get("ad_spend_30d") or 0)
    cover   = float(m.get("days_of_cover") or 99)
    rating  = float(m.get("rating") or 0)
    reviews = int(m.get("review_count") or 0)
    imgs    = int(m.get("images_count") or 0)
    bullets = int(m.get("bullet_count") or 0)
    aplus   = m.get("has_a_plus")   # True | False | None (unknown)
    box     = float(m.get("buy_box_pct") or 1.0)

    rules: list[dict] = []

    # ── Traffic / CTR ─────────────────────────────────────────────────────
    # Thresholds: <0.20% = critical, <0.40% = high (MVP heuristics)
    # Soft zones: values within 10% of each boundary use the milder severity
    if ses > 0 and ctr > 0:
        sev = _soft_sev(ctr,
            [(0.002, "critical", "high"), (0.004, "high", "medium")],
            direction="below")
        if sev in ("critical", "high", "medium"):
            is_crit = ctr < 0.002 * (1 - _SOFT_ZONE)
            rules.append({"area": "traffic", "severity": sev,
                "type": "CTR critically low" if is_crit else "CTR below benchmark",
                "why":  (f"CTR of {ctr:.2%} is "
                         f"{'below the 0.20% critical floor' if is_crit else 'below the 0.40% benchmark'}. "
                         "Competitors are winning clicks on the same search page without spending more. "
                         "A buyer spends under 0.5 seconds scanning each result — "
                         "the hero image is the only thing they evaluate before clicking or scrolling past."),
                "action": ("1. Reshoot hero image on pure white (RGB 255/255/255), product filling 85% of frame — no text overlays. "
                           "2. Study your top 3 competitors' thumbnails: note the angle, lighting, and scale cues. "
                           "3. Run the new image for exactly 7 days before changing anything else." if sev == "critical" else
                           "1. A/B test a new main image — same product, different angle or background. "
                           "2. Compare your hero image to the top 3 competitors in your subcategory. "
                           "3. Run each variant for 7 days before judging results."),
                "weight": None})

    # ── Ads / ACOS ───────────────────────────────────────────────────────
    # Thresholds: >70% = critical, >50% = high, >35% = medium (MVP heuristics)
    if acos > 0 and spend > 0:
        sev = _soft_sev(acos,
            [(0.70, "critical", "high"), (0.50, "high", "medium"), (0.35, "medium", "low")],
            direction="above")
        if sev in ("critical", "high", "medium"):
            waste = int(spend * (1.0 - 0.30 / max(acos, 0.01))) if acos > 0.30 else 0
            is_crit = acos > 0.70 * (1 + _SOFT_ZONE)
            rules.append({"area": "ads", "severity": sev,
                "type": ("ACOS critically high" if is_crit else
                         "ACOS above target"    if sev == "high" else "ACOS elevated"),
                "why":  (f"ACOS is {acos:.0%} — "
                         f"{'above the 70% critical threshold' if is_crit else 'above the 30% profitability target'}. "
                         + (f"~${waste:,}/month in ad spend is returning less than 30 cents of margin per dollar. "
                            if waste > 0 else "")
                         + "You are likely paying for clicks from irrelevant search terms or competitor keywords "
                         "that will never convert at your price point."),
                "action": ("1. Download your Search Term Report (Ads → Reports). Sort by spend. "
                           "Pause every keyword with ACOS above 80% and fewer than 2 orders in 30 days. "
                           "2. Convert your top 10 keywords from broad match to exact match. "
                           "3. Cut daily budget by 40% until ACOS drops below 50%." if sev == "critical" else
                           "1. Download your Search Term Report. Find keywords above 60% ACOS and pause them. "
                           "2. Check match types — broad match is the most common source of wasted spend. "
                           "3. Set a weekly ACOS target equal to your margin and reduce bids on anything above it." if sev == "high" else
                           "1. Review your Search Term Report weekly — pause keywords above 50% ACOS. "
                           "2. Lower bids by 10% on any keyword above your target ACOS. "
                           "3. Check for budget exhaustion early in the day, which can distort your ACOS reading."),
                "weight": None})

    # ── Inventory / Days of cover ────────────────────────────────────────
    # Thresholds: ≤5 days = critical, ≤10 = high, <14 = medium (MVP heuristics)
    # weight override: critical=65, high=25 — cascading damage justification:
    #   a stockout simultaneously destroys organic rank, BSR, and PPC quality score,
    #   making total impact far greater than any single metric issue.
    if 0 < cover < 14:
        sev = _soft_sev(cover,
            [(5, "critical", "high"), (10, "high", "medium"), (14, "medium", "low")],
            direction="below")
        if sev in ("critical", "high", "medium"):
            is_crit = cover < 5 * (1 - _SOFT_ZONE)
            wt = 65 if sev == "critical" else (25 if sev == "high" else None)
            rules.append({"area": "inventory", "severity": sev,
                "type": ("Stockout imminent" if is_crit else
                         "Low inventory"     if sev == "high" else "Inventory running low"),
                "why":  (f"Only {int(cover)} days of cover — "
                         f"{'crossing the 5-day critical threshold' if is_crit else 'below the 10-day caution threshold'}. "
                         "A stockout simultaneously destroys organic rank, Best Seller Rank, and PPC quality score. "
                         "Recovery takes 4–8 weeks of lost sales and ad spend — "
                         "far more costly than holding extra inventory ever would."),
                "action": ("1. Create an FBA shipment today — not this week. "
                           "2. Cut Sponsored Products budget by 60% to slow sell-through while replenishment is in transit. "
                           "3. If you cannot restock in time, activate FBM as a bridge to protect organic rank." if sev == "critical" else
                           "1. Create an FBA shipment this week — monitor units daily. "
                           "2. If daily sell-through is faster than expected, reduce bids to slow it down." if sev == "high" else
                           "1. Plan a replenishment shipment within the next 7 days. "
                           "2. After this restock, raise your reorder point so you never get this close again."),
                "weight": wt})

    # ── Conversion / CVR ─────────────────────────────────────────────────
    # Thresholds: <1.0% = critical, <2.5% = high (MVP heuristics)
    if ses > 0 and cvr > 0:
        sev = _soft_sev(cvr,
            [(0.01, "critical", "high"), (0.025, "high", "medium")],
            direction="below")
        if sev in ("critical", "high", "medium"):
            is_crit = cvr < 0.01 * (1 - _SOFT_ZONE)
            rules.append({"area": "conversion", "severity": sev,
                "type": "Conversion critically low" if is_crit else "Conversion below benchmark",
                "why":  (f"Conversion rate is {cvr:.1%} — "
                         f"{'below the 1.0% critical floor' if is_crit else 'below the 2.5% Amazon benchmark'}. "
                         "Traffic is arriving but the page is not closing the sale. "
                         "The three most common causes: price above competitors, a main image that sets "
                         "wrong expectations, or a recurring complaint in 1-star reviews "
                         "that buyers read before purchasing."),
                "action": ("1. Read every 1-star review — find the single most-repeated complaint and fix it in Bullet 1. "
                           "2. Check your price vs. the top 3 bestsellers in your subcategory. "
                           "If you are 10%+ higher, test a $2–3 reduction. "
                           "3. Add a lifestyle image showing the product in use — this alone lifts CVR 5–15%. "
                           "4. Do not increase ad spend until CVR exceeds 2%." if sev == "critical" else
                           "1. Rewrite Bullet 1 to lead with the buyer's core use case, not product specs. "
                           "2. Compare your price to the subcategory bestseller — stay within 10%. "
                           "3. Add lifestyle and scale-reference images showing the product in context."),
                "weight": None})

    # ── Trust — rating ────────────────────────────────────────────────────
    # Thresholds: <3.5 = critical, <4.0 = high (MVP heuristics)
    # Require ≥5 reviews before trusting the rating signal
    if 0 < rating < 4.0 and reviews >= 5:
        sev = _soft_sev(rating,
            [(3.5, "critical", "high"), (4.0, "high", "medium")],
            direction="below")
        if sev in ("critical", "high", "medium"):
            is_crit = rating < 3.5 * (1 - _SOFT_ZONE)
            rules.append({"area": "trust-rating", "severity": sev,
                "type": "Rating critically low" if is_crit else "Rating below threshold",
                "why":  (f"Rating is {rating:.1f} stars — "
                         f"{'below 3.5, which suppresses Buy Box eligibility' if is_crit else 'below the 4.0 threshold buyers use to filter results'}. "
                         "Most Amazon buyers use the default 4-star filter — your listing is invisible to them "
                         "regardless of how much you spend on ads. "
                         "The fix is not more reviews. It is fixing whatever is causing the negative ones."),
                "action": ("1. Read every 1-star and 2-star review this week. Find the most-repeated complaint — "
                           "this is your listing's #1 defect. Fix it in the product or description. "
                           "2. Use Amazon's 'Request a Review' button on all recent orders. "
                           "3. Do not scale ad spend until you reach 4.0+ — every click lands on a listing that loses trust." if sev == "critical" else
                           "1. Read your most recent 1-star reviews and find the pattern. "
                           "2. Fix the top complaint in the product, packaging, or description. "
                           "3. Use 'Request a Review' on your last 30–60 orders in Seller Central."),
                "weight": None})

    # ── Trust — review count ──────────────────────────────────────────────
    # Thresholds use direct comparison (integer field — soft zones don't apply)
    # <10 = critical, <15 = high, <25 = medium (MVP heuristics)
    if 0 < reviews < 25:
        sev = "critical" if reviews < 10 else ("high" if reviews < 15 else "medium")
        rules.append({"area": "trust-reviews", "severity": sev,
            "type": "Insufficient reviews",
            "why":  (f"Only {reviews} reviews — "
                     f"{'below the 10-review floor where most buyers refuse to convert' if reviews < 10 else 'below the 25-review threshold for reliable conversion'}. "
                     "Social proof is the #1 conversion driver on Amazon. "
                     "Ad spend is structurally inefficient at this stage — buyers who click your listing "
                     "check the reviews before buying, and a thin review count sends them to a competitor."),
            "action": ("1. Use the 'Request a Review' button in Seller Central on every eligible order from the last 90 days. "
                       "2. If brand-registered, enroll in Amazon Vine — generates 1–30 reviews at no cost. "
                       "3. Do not scale ad spend until you reach 25+ reviews at 4.0+."),
            "weight": None})

    # ── Listing quality ───────────────────────────────────────────────────
    listing_issues: list[str] = []
    if imgs > 0 and imgs < 5:
        listing_issues.append(f"only {imgs} images (Amazon recommends 7+)")
    if bullets > 0 and bullets < 5:
        listing_issues.append(f"only {bullets} bullets (need 5)")
    if aplus is False:  # False = explicitly no A+; None = not provided, skip
        listing_issues.append("no A+ content")
    if listing_issues:
        sev = "high" if len(listing_issues) >= 2 else "medium"
        rules.append({"area": "listing", "severity": sev,
            "type": "Listing content gaps",
            "why":  ("Listing has " + " and ".join(listing_issues) + ". "
                     "Thin content signals low quality to the Amazon algorithm and "
                     "reduces buyer confidence before they reach the Add to Cart button."),
            "action": ("Add A+ content (any basic template) and 3+ lifestyle/scale images. "
                       "A+ alone improves conversion 5–10% on average without any ranking cost."),
            "weight": None})

    # ── Buy Box ───────────────────────────────────────────────────────────
    # Thresholds: <50% = critical, <80% = high (MVP heuristics)
    if 0 < box < 0.80:
        sev = _soft_sev(box,
            [(0.50, "critical", "high"), (0.80, "high", "medium")],
            direction="below")
        if sev in ("critical", "high", "medium"):
            is_crit = box < 0.50 * (1 - _SOFT_ZONE)
            rules.append({"area": "buy_box", "severity": sev,
                "type": "Buy Box suppressed",
                "why":  (f"Buy Box percentage is {box:.0%} — "
                         f"{'below 50%, which disqualifies Sponsored Products entirely' if is_crit else 'below the 80% threshold for efficient ad performance'}. "
                         "Every 'Add to Cart' click goes to a competing offer. "
                         "Below 50%, Sponsored Products cannot run at all — "
                         "you are paying for impressions that convert for your competitor."),
                "action": ("1. Check who holds the Buy Box — view your listing while logged out of Seller Central. "
                           "2. Match or beat the lowest-price FBA offer, even by $0.01. "
                           "3. Check your Seller Feedback score — below 95% suppresses Buy Box eligibility. "
                           "4. If you are the only seller and still losing it, contact Seller Support." if sev == "critical" else
                           "1. Identify the competing offer and match their FBA price. "
                           "2. Monitor Buy Box % daily for 7 days after any price change. "
                           "3. Ensure your seller metrics (feedback, order defect rate) are above Amazon's thresholds."),
                "weight": None})

    return rules


# ── detect() — full pipeline ────────────────────────────────────────────────

def detect(metrics: dict) -> list[dict]:
    """
    Full detection pipeline: rules → gap → confidence → validation → top 5.

    Steps:
      1. Build candidate rules (_build_rules)
      2. Compute gap score per area
      3. Assign multi-factor confidence + note (_confidence)
      4. Score priority: severity² × (0.5 + gap×0.5)
      5. Validate each blocker against raw metrics (_validate_blocker)
      6. Keep the highest-priority blocker per area
      7. Sort by priority_score descending, return top 5

    Each returned blocker includes:
      severity, area, type, why, action, weight, gap,
      confidence, confidence_note (if degraded),
      priority_score, validation_warning (if mismatch detected).
    """
    rules = _build_rules(metrics)

    scored: list[dict] = []
    for r in rules:
        gap              = _gap_score(r["area"], metrics)
        conf, conf_note  = _confidence(r["area"], metrics, gap)
        ps               = _priority_score(r["severity"], gap)
        b = {**r, "gap": gap, "confidence": conf, "priority_score": round(ps, 3)}
        if conf_note:
            b["confidence_note"] = conf_note
        scored.append(b)

    # Task 1: validate every blocker
    validated = [_validate_blocker(b, metrics) for b in scored]

    # Keep best per area
    best_per_area: dict[str, dict] = {}
    for b in validated:
        area = b["area"]
        if area not in best_per_area or b["priority_score"] > best_per_area[area]["priority_score"]:
            best_per_area[area] = b

    return sorted(best_per_area.values(), key=lambda x: x["priority_score"], reverse=True)[:5]


# ── Diagnosis ──────────────────────────────────────────────────────────────

@app.route("/api/diagnose", methods=["POST"])
def api_diagnose():
    # Authentication — must have an active session (free or paid plan).
    # This stops anonymous API scraping and brute-force data extraction.
    if not session.get("plan"):
        return jsonify({"error": "Authentication required."}), 401

    # Same-origin guard — block cross-site AJAX calls from other domains
    if not _is_same_origin(request):
        log.warning("Rejected cross-origin /api/diagnose request (IP: %s, Origin: %s)",
                    _client_ip(request), request.headers.get("Origin", "none"))
        return jsonify({"error": "Request origin not permitted."}), 403

    # Rate limit — 30 requests / hour / IP
    ip = _client_ip(request)
    if not _check_diagnose_rate(ip):
        return jsonify({"error": "Too many requests. Please wait a few minutes and try again."}), 429

    items, error = _extract_diagnose_items(request)
    if error:
        return jsonify({"error": error}), 400

    # Cap total ASINs to prevent runaway processing
    if len(items) > _MAX_ASINS_PER_REQUEST:
        items = items[:_MAX_ASINS_PER_REQUEST]
        log.info("Truncated request to %d ASINs (IP: %s)", _MAX_ASINS_PER_REQUEST, ip)

    SEV_W = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    PEN   = {"critical": 26, "high": 9, "medium": 4, "low": 2}
    FOLLOW = {
        "traffic":    "Check CTR daily for 7 days — no 20%+ lift? Test a second hero image variant.",
        "conversion": "Check conversion after 14 days. Still below 2.5%? Audit price vs. bestseller.",
        "ads":        "Pull ACOS in 7 days. Still above 50%? Pause the 3 highest-spend keywords.",
        "trust":      "Track rating weekly. Target 4.2+ within 60 days of fixing the main complaint.",
        "inventory":  "Monitor units vs. shipment ETA daily. Pause ads if cover drops below 3 days.",
        "listing":    "Check conversion 14 days after the content update to confirm the lift.",
        "seo":        "Check organic rank on your top keyword 30 days after keyword changes.",
    }

    def _n(v):
        if v in (None, ""): return 0.0
        if isinstance(v, (int, float)): return float(v)
        s = str(v).strip().replace(",", "").replace("$", "")
        pct = s.endswith("%")
        try: n = float(s[:-1] if pct else s)
        except ValueError: return 0.0
        return n / 100 if pct else n

    def _r(v):
        n = _n(v); return n / 100 if n > 1.5 else n

    def _mx(item):
        m = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
        g = lambda k: m.get(k) if m.get(k) is not None else item.get(k)
        return (_r(g("conversion_rate")), _n(g("sessions_30d")), _n(g("price")),
                _r(g("acos")), _n(g("ad_spend_30d")), _r(g("ctr")),
                _n(g("days_of_cover")) or 99, _n(g("rating")), int(_n(g("review_count"))))

    def _action(area, cvr, ses, prc, acos, spend, ctr, cover, rating, reviews, fb):
        if "traffic" in area and ctr > 0:
            missed = max(0, int((1 - ctr) * 1000))
            return (
                f"Your CTR of {ctr:.2%} means {missed} out of every 1,000 buyers "
                "scroll past your listing without clicking. "
                "1. Reshoot hero image on pure white (RGB 255/255/255) — product filling 85% of frame, no text overlays. "
                "2. Study your top 3 competitors' thumbnails: note the angle, lighting, and scale cues. "
                "3. Run the new image for exactly 7 days — do not touch bids or title until you have that data."
            )
        if "ads" in area and acos > 0.45 and spend > 0:
            waste = int(spend * (1 - 0.30 / max(acos, 0.01)))
            return (
                f"ACOS {acos:.0%} means you spend ${acos:.2f} for every $1.00 in ad sales — "
                f"at standard margins you are losing money on every ad-driven order. "
                f"~${waste:,}/month is wasted vs. a 30% target. "
                "1. Download your Search Term Report (Ads → Reports → Search Terms). Sort by spend. "
                "Pause every keyword with ACOS above 80% and fewer than 2 orders in 30 days. "
                "2. Convert your top 10 keywords from broad match to exact match — broad match is the #1 leak. "
                "3. Cut daily budget by 40% until ACOS drops below 50%."
            )
        if "inventory" in area and 0 < cover < 14:
            return (
                f"You have {int(cover)} days before a potential stockout — act today, not this week. "
                "A stockout collapses organic rank, destroys BSR, and resets PPC quality score. "
                "Recovery takes 4–8 weeks of lost sales and increased ad spend. "
                "1. Create an FBA shipment today. "
                "2. Cut Sponsored Products budget by 60% immediately to slow sell-through. "
                "3. If restocking in time is impossible, activate FBM as a bridge to protect organic rank."
            )
        if "conversion" in area and cvr > 0:
            return (
                f"CVR of {cvr:.1%} means traffic is arriving but the listing is not closing the sale. "
                "1. Read every 1-star review this week — find the single most-repeated complaint "
                "and fix it in Bullet 1 (not with marketing language — with an honest answer). "
                "2. Check your price vs. the top 3 subcategory bestsellers — if you are 10%+ higher, "
                "test a $2–3 reduction for 14 days. "
                "3. Add a lifestyle image showing the product in use — this alone lifts CVR 5–15%."
            )
        if "trust" in area:
            if 0 < rating < 4.0:
                return (
                    f"Rating {rating:.1f} puts you below the 4-star filter most buyers use — "
                    "you are invisible to a large portion of your potential customers. "
                    "1. Read every 1-star and 2-star review this week. Identify the single most-repeated complaint. "
                    "2. Fix that complaint — whether it is a product defect or a listing that sets wrong expectations. "
                    "3. Use Amazon's 'Request a Review' button on every order in the last 90 days. "
                    "4. Do not scale ad spend until you reach 4.0+ — every click lands on a listing that loses trust."
                )
            if 0 < reviews < 25:
                return (
                    f"Only {reviews} reviews means most buyers will hesitate before purchasing. "
                    "Social proof is the #1 conversion driver on Amazon — a thin review count sends buyers to a competitor. "
                    "1. Use Seller Central's 'Request a Review' button on every eligible order from the last 90 days. "
                    "2. If brand-registered, enroll in Amazon Vine — generates 1–30 reviews at no cost. "
                    "3. Pause paid ad spend until you reach 25+ reviews at 4.0+."
                )
        if "buy_box" in area:
            return (
                "Competitors are winning your Add to Cart clicks — you are paying for impressions that convert for someone else. "
                "1. Check who holds the Buy Box — view your listing while logged out of Seller Central. "
                "2. Match or beat the lowest-price FBA offer, even by $0.01. "
                "3. Check your Seller Feedback score — below 95% suppresses Buy Box eligibility."
            )
        if "listing" in area:
            return (
                "Your listing is missing content that directly drives conversion. "
                "1. Add A+ content using any basic template — A+ alone improves CVR 5–10% on average. "
                "2. Add at least 3 new images: lifestyle (product in use), scale reference, detail shot. "
                "3. Rewrite Bullet 1 to lead with the buyer's primary use case — not product specs."
            )
        return fb

    all_b, total = [], 0
    for item in items:
        # ── Auto-detection: if no pre-classified blockers, run detect() ──
        raw_bls = item.get("blockers") if isinstance(item.get("blockers"), list) else []
        if not raw_bls:
            m_raw = item.get("metrics") if isinstance(item.get("metrics"), dict) else item
            m_norm = normalize(m_raw)
            raw_bls = detect(m_norm)

        bls = [b for b in raw_bls if isinstance(b, dict)]

        # ── Penalty calculation — use weight override when present ────────
        pen = 0
        for b in bls:
            sev = b.get("severity", "low")
            override = b.get("weight")
            if override is not None:
                pen += int(override)
            else:
                pen += PEN.get(sev, 2) + (8 if sev == "critical" else 0)

        rs = item.get("score")
        total += int(_n(rs)) if rs not in (None, "") else max(100 - pen, 0)
        cvr, ses, prc, acos, spend, ctr, cover, rating, reviews = _mx(item)
        for b in bls:
            if isinstance(b, dict):
                area = str(b.get("area") or b.get("type") or "general").lower()[:40]
                entry: dict = {
                    "title":       str(b.get("type") or b.get("area") or "Issue")[:80],
                    "area":        area,
                    "severity":    str(b.get("severity", "medium")).lower(),
                    "explanation": str(b.get("why", ""))[:500],
                    "action":      _action(area, cvr, ses, prc, acos, spend, ctr, cover, rating, reviews,
                                          str(b.get("action", ""))[:300]),
                    # Carry confidence metadata so overall_confidence reflects real data quality
                    "confidence":  str(b.get("confidence", "medium")),
                }
                if b.get("confidence_note"):
                    entry["confidence_note"]  = str(b["confidence_note"])[:200]
                if b.get("validation_warning"):
                    entry["validation_warning"] = str(b["validation_warning"])[:200]
                all_b.append(entry)

    score = round(total / len(items))
    by_area: dict = {}
    for b in all_b:
        if b["area"] not in by_area or SEV_W.get(b["severity"], 9) < SEV_W.get(by_area[b["area"]]["severity"], 9):
            by_area[b["area"]] = b
    ranked = sorted(by_area.values(), key=lambda x: SEV_W.get(x["severity"], 9))
    top    = ranked[0] if ranked else None
    urgent = sum(1 for b in all_b if b["severity"] in ("critical", "high"))
    iw     = "issue" if urgent == 1 else "issues"

    if not ranked:
        headline = "This ASIN looks healthy — no significant blockers detected."
    elif urgent >= 3 and top["severity"] == "critical":
        headline = f"{urgent} critical {iw} compounding each other — start with {top['area']}, fix in order."
    elif top["severity"] == "critical":
        headline = f"Critical {top['area']} problem — fix this before scaling anything."
    elif urgent >= 3:
        headline = f"{urgent} urgent {iw} compounding each other — fix them in order, not all at once."
    elif urgent == 1:
        headline = f"One fix needed in {top['area']} — address it and results improve within 14 days."
    else:
        headline = f"Main opportunity is in {top['area']} — one focused change can move the needle."

    # ── Data quality: contradictions + completeness (Task 5) ──────────────
    all_contradictions: list[str] = []
    all_missing: list[str]        = []
    is_partial                    = False
    for item in items:
        m_raw  = item.get("metrics") if isinstance(item.get("metrics"), dict) else item
        m_norm = normalize(m_raw)
        missing_fields, partial = _check_completeness(m_norm)
        if partial:
            is_partial = True
        all_missing.extend(missing_fields)
        all_contradictions.extend(_detect_contradictions(m_norm))
    # Deduplicate
    all_contradictions = list(dict.fromkeys(all_contradictions))
    all_missing        = list(dict.fromkeys(all_missing))

    # ── Overall confidence (Task 4) ─────────────────────────────────────
    # Worst-case confidence across all top blockers.
    # Also penalised for partial diagnosis or detected contradictions.
    conf_levels = [b.get("confidence", "medium") for b in ranked[:5]]
    conf_order  = {"high": 3, "medium": 2, "low": 1}
    if conf_levels:
        min_conf = min(conf_levels, key=lambda c: conf_order.get(c, 2))
    else:
        min_conf = "high"
    if is_partial and conf_order.get(min_conf, 2) > 1:
        min_conf = {"high": "medium", "medium": "low"}.get(min_conf, min_conf)
    if len(all_contradictions) >= 2 and conf_order.get(min_conf, 2) > 1:
        min_conf = {"high": "medium", "medium": "low"}.get(min_conf, min_conf)
    overall_confidence = min_conf

    # ── Problems list — include confidence + warnings ────────────────────
    def _build_problem(b: dict) -> dict:
        base = {
            "title":       b["title"],
            "severity":    b["severity"],
            "detail":      b["explanation"] or f"{b['area'].title()} needs attention.",
            "explanation": b["explanation"] or f"{b['area'].title()} needs attention.",
            "confidence":  b.get("confidence", "medium"),
        }
        if b.get("confidence_note"):
            base["confidence_note"] = b["confidence_note"]
        if b.get("validation_warning"):
            base["validation_warning"] = b["validation_warning"]
        return base

    problems = [_build_problem(b) for b in ranked[:5]] or \
               [{"title": "No major issues detected", "severity": "low",
                 "detail": "All metrics are within healthy range. Keep monitoring weekly.",
                 "explanation": "All metrics are within healthy range. Keep monitoring weekly.",
                 "confidence": "high"}]

    recs = [{"step": s, "action": b["action"],
             "why": b["explanation"] or f"Fixing {b['area']} directly improves performance.",
             "follow_up": FOLLOW.get(b["area"], "Re-run the diagnosis in 14 days to confirm improvement.")}
            for s, b in enumerate(ranked[:5], 1) if b["action"]] or \
           [{"step": 1, "action": "Check CTR and conversion in Seller Central for the last 30 days.",
             "why": "These two numbers reveal exactly where traffic is leaking.",
             "follow_up": "If either drops 15%+ week-over-week, re-run the diagnosis immediately."}]

    ta, rev = (top["area"] if top else ""), None
    for item in (items if not ranked else sorted(items, key=lambda a: a.get("score") or 100)):
        cvr, ses, prc, acos, spend, ctr, cover, *_ = _mx(item)
        if not ranked:
            if ses > 0 and prc > 0 and cvr > 0:
                _base = f"Generating ~${int(ses*cvr*prc):,}/month at current traffic."
                if ses < 300:
                    rev = (_base + " Note: fewer than 300 sessions — estimate may shift "
                           "significantly as traffic grows.")
                else:
                    rev = (_base + " Ready to scale — more sessions at this conversion rate "
                           "adds revenue directly.")
            break
        if "inventory" in ta and cover < 14 and ses > 0 and prc > 0 and cvr > 0:
            rev = (f"Stockout risk: ~${int((ses/30)*cvr*prc*max(14-cover,0)):,} in lost revenue "
                   f"and weeks of organic rank if you go OOS at {int(cover)} days of cover.")
            break
        if "traffic" in ta and 0 < ctr < 0.0042 and ses > 0 and prc > 0:
            # Sanity check: CTR revenue projection unreliable without social proof
            _reviews_for_rev = int(_n(item.get("review_count") or
                                      (item.get("metrics") or {}).get("review_count") or 0))
            if _reviews_for_rev >= 15:
                extra = int(ses * (0.004 / max(ctr, 0.0001) - 1))
                rev = (f"Fixing CTR from {ctr:.2%} to 0.40% → ~{extra:,} more sessions/month "
                       f"→ ~${int(extra * max(cvr, 0.025) * prc):,} in additional revenue.")
            else:
                rev = ("CTR is low, but with fewer than 15 reviews the revenue projection "
                       "is unreliable. Build social proof first, then scale traffic.")
            break
        if "ads" in ta and spend > 0 and acos > 0.35:
            rev = (f"Cutting ACOS from {acos:.0%} to 30% saves "
                   f"~${int(spend*(1 - 0.30/max(acos, 0.01))):,}/month in wasted ad spend.")
            break
        if ses > 0 and prc > 0 and cvr > 0:
            lo = int(max((max(cvr * 1.30, 0.025) - cvr) * ses, 0) * prc * 0.65)
            hi = int(max((max(cvr * 1.30, 0.025) - cvr) * ses, 0) * prc * 1.05)
            if lo > 0:
                rev = f"A 30% conversion improvement could add ${lo:,}–${hi:,}/month at current traffic."
        break

    rev = rev or (
        "Healthy ASIN — focus on scaling traffic." if not ranked else
        f"{urgent} urgent {iw} are suppressing revenue. Fix the top blocker first." if urgent >= 3 else
        "Fixing the top blocker typically recovers 15–25% of suppressed revenue within 30–60 days."
    )

    # ── Build data_quality block ─────────────────────────────────────────
    data_quality: dict = {"overall_confidence": overall_confidence}
    if is_partial:
        data_quality["partial_diagnosis"]    = True
        data_quality["partial_diagnosis_note"] = (
            f"Missing data: {', '.join(all_missing)}. "
            "Diagnosis covers only the metrics that were provided."
        )
    if all_contradictions:
        data_quality["mixed_signals"] = all_contradictions
    if all_missing:
        data_quality["missing_fields"] = all_missing

    return jsonify({
        "overall_score":            score,
        "headline":                 headline,
        "problems":                 problems,
        "recommendations":          recs[:5],
        "revenue_impact":           rev,
        "estimated_revenue_impact": rev,
        "overall_confidence":       overall_confidence,
        "data_quality":             data_quality,
        "model_used":               "rule-based",
    })


@app.route("/api/plan")
def api_plan():
    return jsonify({
        "plan":             session.get("plan", "free"),
        "amazon_connected": bool(session.get("amazon_access_token")),
    })


# ── Amazon SP-API OAuth ────────────────────────────────────────────────────

@app.route("/amazon/connect")
def amazon_connect():
    if not AMAZON_CLIENT_ID:
        # Browser navigation — redirect instead of raw JSON
        return redirect("/tool?error=amazon_not_configured")

    state = secrets.token_urlsafe(16)
    session["amazon_oauth_state"] = state

    params = {
        "application_id": AMAZON_CLIENT_ID,
        "state":          state,
        "version":        "beta",
    }
    auth_url = "https://sellercentral.amazon.com/apps/authorize/consent"
    return redirect(f"{auth_url}?{urlencode(params)}")


@app.route("/amazon/callback")
def amazon_callback():
    state              = request.args.get("state", "")
    spapi_oauth_code   = request.args.get("spapi_oauth_code", "")
    selling_partner_id = request.args.get("selling_partner_id", "")

    expected_state = session.pop("amazon_oauth_state", None)
    if not expected_state or state != expected_state:
        return redirect("/?error=amazon_auth_failed")

    if not spapi_oauth_code:
        return redirect("/?error=amazon_no_code")

    token_url = "https://api.amazon.com/auth/o2/token"
    try:
        resp = requests.post(token_url, data={
            "grant_type":    "authorization_code",
            "code":          spapi_oauth_code,
            "client_id":     AMAZON_CLIENT_ID,
            "client_secret": AMAZON_CLIENT_SECRET,
            "redirect_uri":  AMAZON_REDIRECT_URI,
        }, timeout=10)
        resp.raise_for_status()
        tokens = resp.json()
        if not tokens.get("access_token"):
            return redirect("/?error=amazon_token_failed")
        session["amazon_access_token"]  = tokens["access_token"]
        session["amazon_refresh_token"] = tokens.get("refresh_token", "")
        session["amazon_seller_id"]     = selling_partner_id
    except Exception:
        return redirect("/?error=amazon_token_failed")

    if not session.get("plan"):
        session["plan"] = "free"
    session.permanent = True

    return redirect("/tool?amazon=connected")


@app.route("/amazon/disconnect", methods=["POST"])
def amazon_disconnect():
    """POST + CSRF check — prevents cross-site disconnection attacks."""
    if not _csrf_valid(request):
        log.warning("CSRF check failed on /amazon/disconnect (IP: %s)", _client_ip(request))
        return jsonify({"error": "Invalid request."}), 403
    session.pop("amazon_access_token", None)
    session.pop("amazon_refresh_token", None)
    session.pop("amazon_seller_id", None)
    return jsonify({"status": "disconnected"})


# ── Amazon SP-API: pull inventory data ────────────────────────────────────

@app.route("/api/amazon/inventory")
def amazon_inventory():
    access_token = session.get("amazon_access_token")
    if not access_token:
        return jsonify({"error": "not_connected"}), 401

    marketplace_id = request.args.get("marketplace", "ATVPDKIKX0DER")
    headers = {
        "x-amz-access-token": access_token,
        "Content-Type":       "application/json",
    }

    try:
        url = "https://sellingpartnerapi-na.amazon.com/fba/inventory/v1/summaries"
        params = {
            "details":         "true",
            "granularityType": "Marketplace",
            "granularityId":   marketplace_id,
            "marketplaceIds":  marketplace_id,
        }
        resp = requests.get(url, headers=headers, params=params, timeout=15)

        if resp.status_code == 401:
            refreshed = _refresh_amazon_token()
            if refreshed:
                headers["x-amz-access-token"] = session.get("amazon_access_token")
                resp = requests.get(url, headers=headers, params=params, timeout=15)
            else:
                return jsonify({"error": "token_expired"}), 401

        return jsonify(resp.json()), resp.status_code

    except Exception as e:
        log.error("Amazon inventory API error (IP: %s): %s", _client_ip(request), e)
        return jsonify({"error": "Failed to fetch inventory data. Please try again."}), 500


def _refresh_amazon_token() -> bool:
    refresh_token = session.get("amazon_refresh_token")
    if not refresh_token:
        return False
    try:
        resp = requests.post("https://api.amazon.com/auth/o2/token", data={
            "grant_type":    "refresh_token",
            "refresh_token": refresh_token,
            "client_id":     AMAZON_CLIENT_ID,
            "client_secret": AMAZON_CLIENT_SECRET,
        }, timeout=10)
        tokens = resp.json()
        if "access_token" in tokens:
            session["amazon_access_token"] = tokens["access_token"]
            return True
    except Exception:
        pass
    return False


# ── Run ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("ASINInsight server starting...")
    log.info("Landing page: http://localhost:5050")
    log.info("Tool:         http://localhost:5050/tool")
    app.run(host="0.0.0.0", port=5050, debug=False)
