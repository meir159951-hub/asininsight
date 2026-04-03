"""
ASINInsight - Flask server with Paddle payments + Amazon SP-API
"""

import os
import hmac
import hashlib
import json
import requests
from pathlib import Path
from flask import (
    Flask, send_from_directory, redirect,
    request, session, jsonify
)
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__, static_folder=None)

secret_key = os.getenv("FLASK_SECRET_KEY")
if not secret_key:
    raise RuntimeError("FLASK_SECRET_KEY environment variable is not set")
app.secret_key = secret_key

# Secure session cookie settings
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Canonical site URL
SITE_URL = os.getenv("SITE_URL", "").rstrip("/")

# Paddle config
PADDLE_WEBHOOK_SECRET = os.getenv("PADDLE_WEBHOOK_SECRET", "")
PADDLE_API_KEY        = os.getenv("PADDLE_API_KEY", "")
PADDLE_PRICE_PRO      = os.getenv("PADDLE_PRICE_PRO", "")      # e.g. pri_01abc...
PADDLE_PRICE_AGENCY   = os.getenv("PADDLE_PRICE_AGENCY", "")   # e.g. pri_01xyz...
PADDLE_CLIENT_TOKEN   = os.getenv("PADDLE_CLIENT_TOKEN", "")   # public token for JS

# Amazon SP-API config (OAuth 2.0)
AMAZON_CLIENT_ID     = os.getenv("AMAZON_CLIENT_ID", "")
AMAZON_CLIENT_SECRET = os.getenv("AMAZON_CLIENT_SECRET", "")
AMAZON_REDIRECT_URI  = os.getenv("AMAZON_REDIRECT_URI", "")    # e.g. https://asininsight.com/amazon/callback


def get_base_url():
    return SITE_URL if SITE_URL else request.host_url.rstrip("/")


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.errorhandler(404)
def not_found(e):
    return send_from_directory(BASE_DIR, "error.html"), 404


@app.errorhandler(500)
def server_error(e):
    return send_from_directory(BASE_DIR, "error.html"), 500


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
    return send_from_directory(BASE_DIR, "logo_preview.html")


@app.route("/sample_data/<path:filename>")
def sample_data(filename):
    return send_from_directory(BASE_DIR / "sample_data", filename)


@app.route("/success")
def success():
    return send_from_directory(BASE_DIR, "success.html")


@app.route("/cancel")
def cancel():
    return redirect("/")


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
    """Return Paddle public tokens to the frontend (safe to expose)."""
    return jsonify({
        "client_token": PADDLE_CLIENT_TOKEN,
        "price_pro":    PADDLE_PRICE_PRO,
        "price_agency": PADDLE_PRICE_AGENCY,
    })


# ── Free plan ──────────────────────────────────────────────────────────────

@app.route("/checkout/free", methods=["POST"])
def checkout_free():
    session["plan"] = "free"
    return redirect("/tool")


# ── Paddle Webhook ─────────────────────────────────────────────────────────

@app.route("/webhook/paddle", methods=["POST"])
def paddle_webhook():
    """Verify Paddle webhook signature and update user plan."""
    raw_body = request.get_data()
    signature = request.headers.get("Paddle-Signature", "")

    # Verify signature
    if PADDLE_WEBHOOK_SECRET:
        try:
            parts = dict(p.split("=", 1) for p in signature.split(";"))
            ts = parts.get("ts", "")
            h1 = parts.get("h1", "")
            signed_payload = f"{ts}:{raw_body.decode()}"
            expected = hmac.new(
                PADDLE_WEBHOOK_SECRET.encode(),
                signed_payload.encode(),
                hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(expected, h1):
                return jsonify({"error": "invalid signature"}), 401
        except Exception:
            return jsonify({"error": "signature error"}), 400

    event = request.get_json(force=True)
    event_type = event.get("event_type", "")

    if event_type in ("subscription.activated", "subscription.updated", "transaction.completed"):
        data = event.get("data", {})
        items = data.get("items", [])
        for item in items:
            price_id = item.get("price", {}).get("id", "")
            if price_id == PADDLE_PRICE_AGENCY:
                # Store in DB in production — for now just log
                pass
            elif price_id == PADDLE_PRICE_PRO:
                pass

    return jsonify({"status": "ok"}), 200


# ── Email Report ───────────────────────────────────────────────────────────

SENDGRID_API_KEY   = os.getenv("SENDGRID_API_KEY", "")
EMAIL_FROM_ADDRESS = os.getenv("EMAIL_FROM_ADDRESS", "reports@asininsight.com")
EMAIL_FROM_NAME    = os.getenv("EMAIL_FROM_NAME", "ASINInsight")


@app.route("/api/send-report", methods=["POST"])
def send_report():
    """Send diagnosis summary email to user."""
    data = request.get_json(force=True)
    email  = (data.get("email") or "").strip()
    report = data.get("report", {})

    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Invalid email"}), 400

    if not SENDGRID_API_KEY:
        # No SendGrid configured — just return ok so UI doesn't break
        return jsonify({"ok": True, "note": "email_not_configured"})

    total     = report.get("total_asins", 0)
    critical  = report.get("critical_count", 0)
    weakest   = report.get("weakest_asin", "N/A")
    score     = report.get("weakest_score", 0)
    blockers  = report.get("top_blockers", [])

    blockers_html = "".join(f"<li style='margin-bottom:6px;'>⚠️ {b}</li>" for b in blockers) if blockers else "<li>No major blockers found.</li>"

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
        return jsonify({"ok": False, "error": "Email delivery failed"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Plan API ───────────────────────────────────────────────────────────────

@app.route("/api/plan")
def api_plan():
    return jsonify({
        "plan": session.get("plan", "free"),
        "amazon_connected": bool(session.get("amazon_access_token"))
    })


# ── Amazon SP-API OAuth ────────────────────────────────────────────────────

@app.route("/amazon/connect")
def amazon_connect():
    """Redirect user to Amazon to authorize our app."""
    if not AMAZON_CLIENT_ID:
        return jsonify({"error": "Amazon SP-API not configured yet"}), 503

    import secrets
    state = secrets.token_urlsafe(16)
    session["amazon_oauth_state"] = state

    params = {
        "application_id": AMAZON_CLIENT_ID,
        "state": state,
        "version": "beta",
    }
    auth_url = "https://sellercentral.amazon.com/apps/authorize/consent"
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return redirect(f"{auth_url}?{query}")


@app.route("/amazon/callback")
def amazon_callback():
    """Amazon redirects here after user authorizes."""
    state = request.args.get("state", "")
    spapi_oauth_code = request.args.get("spapi_oauth_code", "")
    selling_partner_id = request.args.get("selling_partner_id", "")

    if state != session.get("amazon_oauth_state"):
        return redirect("/?error=amazon_auth_failed")

    if not spapi_oauth_code:
        return redirect("/?error=amazon_no_code")

    # Exchange code for access token
    token_url = "https://api.amazon.com/auth/o2/token"
    try:
        resp = requests.post(token_url, data={
            "grant_type": "authorization_code",
            "code": spapi_oauth_code,
            "client_id": AMAZON_CLIENT_ID,
            "client_secret": AMAZON_CLIENT_SECRET,
            "redirect_uri": AMAZON_REDIRECT_URI,
        }, timeout=10)
        tokens = resp.json()
        session["amazon_access_token"]  = tokens.get("access_token")
        session["amazon_refresh_token"] = tokens.get("refresh_token")
        session["amazon_seller_id"]     = selling_partner_id
    except Exception:
        return redirect("/?error=amazon_token_failed")

    # If user has no plan yet, give them free
    if not session.get("plan"):
        session["plan"] = "free"

    return redirect("/tool?amazon=connected")


@app.route("/amazon/disconnect")
def amazon_disconnect():
    session.pop("amazon_access_token", None)
    session.pop("amazon_refresh_token", None)
    session.pop("amazon_seller_id", None)
    return jsonify({"status": "disconnected"})


# ── Amazon SP-API: pull inventory data ────────────────────────────────────

@app.route("/api/amazon/inventory")
def amazon_inventory():
    """Fetch inventory from Amazon SP-API and return as JSON."""
    access_token = session.get("amazon_access_token")
    if not access_token:
        return jsonify({"error": "not_connected"}), 401

    marketplace_id = request.args.get("marketplace", "ATVPDKIKX0DER")  # US by default

    headers = {
        "x-amz-access-token": access_token,
        "Content-Type": "application/json",
    }

    try:
        url = "https://sellingpartnerapi-na.amazon.com/fba/inventory/v1/summaries"
        params = {
            "details": "true",
            "granularityType": "Marketplace",
            "granularityId": marketplace_id,
            "marketplaceIds": marketplace_id,
        }
        resp = requests.get(url, headers=headers, params=params, timeout=15)

        if resp.status_code == 401:
            # Try to refresh token
            refreshed = _refresh_amazon_token()
            if refreshed:
                headers["x-amz-access-token"] = session.get("amazon_access_token")
                resp = requests.get(url, headers=headers, params=params, timeout=15)
            else:
                return jsonify({"error": "token_expired"}), 401

        return jsonify(resp.json()), resp.status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _refresh_amazon_token():
    """Refresh the Amazon access token using the refresh token."""
    refresh_token = session.get("amazon_refresh_token")
    if not refresh_token:
        return False
    try:
        resp = requests.post("https://api.amazon.com/auth/o2/token", data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": AMAZON_CLIENT_ID,
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
    print("ASINInsight server starting...")
    print("Landing page: http://localhost:5050")
    print("Tool:         http://localhost:5050/tool")
    app.run(host="0.0.0.0", port=5050, debug=False)
