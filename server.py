"""
ASINInsight - Flask server with Stripe payments
"""

import os
import stripe
from pathlib import Path
from flask import (
    Flask, send_from_directory, redirect,
    request, session, jsonify
)
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

app = Flask(__name__, static_folder=None)

secret_key = os.getenv("FLASK_SECRET_KEY")
if not secret_key:
    raise RuntimeError("FLASK_SECRET_KEY environment variable is not set")
app.secret_key = secret_key

# Secure session cookie settings
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Canonical site URL — set SITE_URL in Railway env vars to avoid Host header injection
SITE_URL = os.getenv("SITE_URL", "").rstrip("/")


def get_base_url():
    """Return the canonical site URL. Falls back to request host only if SITE_URL is not set."""
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


# ── Stripe Checkout ────────────────────────────────────────────────────────

@app.route("/checkout/pro", methods=["POST"])
def checkout_pro():
    try:
        base_url = get_base_url()
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "ASINInsight Pro",
                        "description": "Unlimited ASINs, portfolio analysis, category benchmarking"
                    },
                    "unit_amount": 4900,
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            }],
            success_url=f"{base_url}/verify?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base_url}/cancel",
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/checkout/agency", methods=["POST"])
def checkout_agency():
    try:
        base_url = get_base_url()
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "ASINInsight Agency",
                        "description": "Unlimited ASINs, white-label reports, API access, priority support"
                    },
                    "unit_amount": 19900,
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            }],
            success_url=f"{base_url}/verify?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base_url}/cancel",
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/checkout/free", methods=["POST"])
def checkout_free():
    session["plan"] = "free"
    return redirect("/tool")


# ── Plan API ───────────────────────────────────────────────────────────────

@app.route("/api/plan")
def api_plan():
    return jsonify({"plan": session.get("plan", "free")})


# ── Session verify ─────────────────────────────────────────────────────────

@app.route("/verify")
def verify():
    session_id = request.args.get("session_id")
    if not session_id:
        return redirect("/")

    # Prevent replay: if this session_id was already used, go straight to success
    if session.get("stripe_session_id") == session_id and session.get("plan") == "pro":
        return redirect("/success")

    try:
        stripe_session = stripe.checkout.Session.retrieve(session_id)
        if stripe_session.payment_status == "paid" or stripe_session.status == "complete":
            session["plan"] = "pro"
            session["stripe_session_id"] = session_id
    except Exception:
        pass
    return redirect("/success")


# ── Run ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("ASINInsight server starting...")
    print("Landing page: http://localhost:5050")
    print("Tool:         http://localhost:5050/tool")
    app.run(host="0.0.0.0", port=5050, debug=False)
