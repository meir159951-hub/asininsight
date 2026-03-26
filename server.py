"""
ASINInsight - Flask server with Stripe payments
"""

import os
import stripe
from pathlib import Path
from flask import (
    Flask, send_from_directory, redirect,
    request, session, url_for, jsonify
)
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")

app = Flask(__name__, static_folder=None)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")

# ── Pages ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "landing.html")


@app.route("/tool")
def tool():
    # Free plan: always accessible
    # Pro plan: check session
    return send_from_directory(BASE_DIR, "app.html")


@app.route("/sample_data/<path:filename>")
def sample_data(filename):
    return send_from_directory(BASE_DIR / "sample_data", filename)


@app.route("/success")
def success():
    return send_from_directory(BASE_DIR, "success.html")


@app.route("/cancel")
def cancel():
    return redirect("/")


# ── Stripe Checkout ────────────────────────────────────────────────────────

@app.route("/checkout/pro", methods=["POST"])
def checkout_pro():
    try:
        base_url = request.host_url.rstrip("/")
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
                    "unit_amount": 4900,  # $49.00
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            }],
            success_url=f"{base_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base_url}/cancel",
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/checkout/agency", methods=["POST"])
def checkout_agency():
    try:
        base_url = request.host_url.rstrip("/")
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
                    "unit_amount": 19900,  # $199.00
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            }],
            success_url=f"{base_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base_url}/cancel",
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/checkout/free", methods=["POST"])
def checkout_free():
    session["plan"] = "free"
    return redirect("/tool")


# ── Session verify ─────────────────────────────────────────────────────────

@app.route("/verify")
def verify():
    session_id = request.args.get("session_id")
    if not session_id:
        return redirect("/")
    try:
        stripe_session = stripe.checkout.Session.retrieve(session_id)
        if stripe_session.payment_status == "paid" or stripe_session.status == "complete":
            session["plan"] = "pro"
            session["stripe_session_id"] = session_id
    except Exception:
        pass
    return redirect("/tool")


# ── Run ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("ASINInsight server starting...")
    print("Landing page: http://localhost:5050")
    print("Tool:         http://localhost:5050/tool")
    app.run(host="0.0.0.0", port=5050, debug=False)
