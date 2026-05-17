"""
PPC suggestion engine for SellerCopilot.

Reads the latest `ppc_snapshots` rows for one connection, runs five rules over
the data, and writes the findings to `ppc_suggestions`. The flow stays
read-only with respect to Amazon: nothing here calls the Ads API. The applier
(`apply_suggestion`, week 6) is what actually pushes approved changes back.

Rules implemented (one suggestion type per rule):

1. spend_no_sales       keyword burned cash with zero sales in 30 days
2. high_acos            ACOS above the threshold; bid down toward target
3. bid_too_high         keyword bid is materially above its ad-group default
4. scale_profitable     low ACOS plus impression headroom; bid up
5. promote_search_term  search term with real sales but no matching keyword

Public surface:
- `analyze(snapshots)`              pure: takes raw snapshot dict, returns suggestions
- `generate_suggestions(conn_id)`   end-to-end: load snapshot, analyze, persist
- `money_found_total(suggestions)`  sum of estimated_savings across pending items

Why two entry points: `analyze` lets tests assert each rule without spinning up
a database, while `generate_suggestions` is what the cron / dashboard call.

Threshold philosophy
--------------------
Every threshold below is conservative. Suggestions are reviewed by the seller
before any change hits Amazon, so a false-positive costs a click on "reject".
A false-negative costs real money the seller never sees flagged. Bias toward
flagging.

All money fields are USD floats. ACOS is stored as a fraction (0.50 = 50%).

Suggestion status state machine
-------------------------------
ppc_suggestions.status moves through these values. The engine here only ever
inserts 'pending' rows; later modules drive the rest.

    pending
       |  generate_suggestions wrote it after a snapshot.
       |
       +----> rejected                  (seller said no, recorded for memory)
       |
       +----> approved_pending_apply    (seller clicked Approve in dashboard;
       |                                 the applier is week 6, until then
       |                                 these rows queue without effect)
       |
       +----> applied                   (week 6: the applier pushed the change
                                         to Amazon Ads API; ppc_audit_log has
                                         the API response)

Re-running generate_suggestions with replace_pending=True (the default) wipes
'pending' rows only. Decided rows (rejected / approved_pending_apply / applied)
are preserved so the per-seller memory layer (week 5) can read them back.
"""

from __future__ import annotations

import json
import time
import logging
from typing import Any

log = logging.getLogger("ppc_suggestions")


# ──────────────────────────────────────────────────────────────────────────
#  Tunable thresholds. Codex review focus: are these defensible?
# ──────────────────────────────────────────────────────────────────────────

# Rule 1: spend_no_sales
SPEND_NO_SALES_MIN_COST_USD = 5.00     # at least $5 spent
SPEND_NO_SALES_MIN_CLICKS   = 5        # and at least 5 clicks (rules out noise)

# Rule 2: high_acos
HIGH_ACOS_THRESHOLD     = 0.50         # 50% ACOS -> flag
HIGH_ACOS_TARGET        = 0.30         # bid scales toward 30% target ACOS
HIGH_ACOS_MIN_COST_USD  = 5.00         # ignore keywords below this floor

# Rule 3: bid_too_high
BID_TOO_HIGH_RATIO   = 1.5             # bid >= 1.5 x ad-group default
BID_TOO_HIGH_MIN_BID = 0.50            # ignore tiny bids

# Rule 4: scale_profitable
SCALE_MAX_ACOS         = 0.20          # ACOS <= 20%
SCALE_MIN_SALES_USD    = 50.00         # at least $50 in sales (real signal)
SCALE_MAX_IMPRESSIONS  = 1000          # capped impressions = headroom to grow
SCALE_BID_UPLIFT       = 1.20          # +20% bid

# Rule 5: promote_search_term
SEARCH_TERM_PROMOTE_MIN_SALES_USD = 50.00
SEARCH_TERM_PROMOTE_MIN_PURCHASES = 2

SNAPSHOT_DATA_TYPES = ("profiles", "campaigns", "ad_groups", "keywords", "search_terms")

# Data types whose presence defines a "complete" snapshot run. profiles is
# excluded: it's an Amazon API-handshake artefact that the rules engine
# never reads. A run missing any of these four would force the engine to
# combine fresh rows with stale rows from a prior run, which is exactly
# the batch-coherence bug snapshot_run_id was added to prevent.
REQUIRED_DATA_TYPES = ("campaigns", "ad_groups", "keywords", "search_terms")


# ──────────────────────────────────────────────────────────────────────────
#  Suggestion status state machine constants
# ──────────────────────────────────────────────────────────────────────────
#
# Use these constants instead of string literals when checking or assigning
# the `status` column. The applier (week 6) consumes APPROVED_PENDING_APPLY
# rows and moves them to APPLIED.

STATUS_PENDING                = "pending"
STATUS_REJECTED               = "rejected"
STATUS_APPROVED_PENDING_APPLY = "approved_pending_apply"
STATUS_APPLIED                = "applied"

ALL_STATUSES = (
    STATUS_PENDING,
    STATUS_REJECTED,
    STATUS_APPROVED_PENDING_APPLY,
    STATUS_APPLIED,
)


# ──────────────────────────────────────────────────────────────────────────
#  Public, pure functions (no DB I/O)
# ──────────────────────────────────────────────────────────────────────────

def analyze(snapshots: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """
    Run every rule over an in-memory snapshot dict and return suggestions.

    `snapshots` keys: profiles, campaigns, ad_groups, keywords, search_terms.
    Each value is a list of dicts shaped like the corresponding Amazon Ads
    API response. See `mock_ppc_data.build_snapshot_payload()` for examples.

    Pure: deterministic, no clock dependence except via the data, no DB,
    no network. Tests call this directly.
    """
    keywords     = snapshots.get("keywords", []) or []
    ad_groups    = snapshots.get("ad_groups", []) or []
    search_terms = snapshots.get("search_terms", []) or []

    ad_groups_by_id = {
        ag.get("adGroupId"): ag for ag in ad_groups if ag.get("adGroupId")
    }
    perf = _aggregate_keyword_perf(search_terms)

    out: list[dict[str, Any]] = []
    out.extend(_rule_spend_no_sales(keywords, perf))
    out.extend(_rule_high_acos(keywords, perf))
    out.extend(_rule_bid_too_high(keywords, ad_groups_by_id, perf))
    out.extend(_rule_scale_profitable(keywords, perf))
    out.extend(_rule_promote_search_term(keywords, search_terms))
    return out


SAVINGS_RULE_TYPES = ("spend_no_sales", "high_acos", "bid_too_high")
GROWTH_RULE_TYPES  = ("scale_profitable", "promote_search_term")


def money_found_total(suggestions: list[dict[str, Any]]) -> float:
    """
    Sum of estimated_savings across the suggestion list.

    Note that the dollar field mixes two distinct amounts:
    - Savings from cutting waste (rules 1-3).
    - Incremental revenue from scaling winners and promoting search terms
      (rules 4-5).

    For dashboard presentation, prefer `savings_total` and
    `growth_opportunity_total` separately so the seller can tell the two
    apart. This combined number stays available for compatibility and for
    notification copy that wants a single headline figure.
    """
    return round(sum(float(s.get("estimated_savings", 0) or 0) for s in suggestions), 2)


def savings_total(suggestions: list[dict[str, Any]]) -> float:
    """
    Sum of estimated dollars the seller would *save* (real cost reduction)
    if the seller approves rules 1-3 (spend_no_sales, high_acos, bid_too_high).

    Use this number when wording matters: "real money you can save right now."
    """
    return round(sum(
        float(s.get("estimated_savings", 0) or 0)
        for s in suggestions
        if s.get("suggestion_type") in SAVINGS_RULE_TYPES
    ), 2)


def growth_opportunity_total(suggestions: list[dict[str, Any]]) -> float:
    """
    Sum of estimated incremental revenue from rules 4-5 (scale_profitable,
    promote_search_term).

    This is *projected* extra sales, not money already in hand. Wording in
    the UI should make the distinction explicit.
    """
    return round(sum(
        float(s.get("estimated_savings", 0) or 0)
        for s in suggestions
        if s.get("suggestion_type") in GROWTH_RULE_TYPES
    ), 2)


def count_by_type(suggestions: list[dict[str, Any]]) -> dict[str, int]:
    """
    Number of suggestions of each rule type. All five canonical keys are
    always present (zero if the rule didn't fire).
    """
    out = {
        "spend_no_sales":      0,
        "high_acos":           0,
        "bid_too_high":        0,
        "scale_profitable":    0,
        "promote_search_term": 0,
    }
    for s in suggestions:
        t = s.get("suggestion_type")
        if t in out:
            out[t] += 1
    return out


def summarize(suggestions: list[dict[str, Any]]) -> str:
    """
    Single-sentence English summary suitable for an email subject line or a
    Slack notification. Examples:

      "No pending suggestions for this account."
      "Found $126.52 across 7 suggestions: 1 waste, 1 high ACOS, 1 overbid,
       1 scale opportunity, 3 search terms to promote."

    Order matches the rule order in `analyze` so the sentence reads in the
    same shape across runs.
    """
    if not suggestions:
        return "No pending suggestions for this account."

    counts = count_by_type(suggestions)
    money  = money_found_total(suggestions)

    parts: list[str] = []
    if counts["spend_no_sales"]:
        parts.append(f"{counts['spend_no_sales']} waste")
    if counts["high_acos"]:
        parts.append(f"{counts['high_acos']} high ACOS")
    if counts["bid_too_high"]:
        parts.append(f"{counts['bid_too_high']} overbid")
    if counts["scale_profitable"]:
        parts.append(f"{counts['scale_profitable']} scale opportunit"
                     + ("y" if counts["scale_profitable"] == 1 else "ies"))
    if counts["promote_search_term"]:
        parts.append(f"{counts['promote_search_term']} search term"
                     + ("" if counts["promote_search_term"] == 1 else "s")
                     + " to promote")

    return f"Found ${money:.2f} across {len(suggestions)} suggestions: " + ", ".join(parts) + "."


def money_found_breakdown(suggestions: list[dict[str, Any]]) -> dict[str, float]:
    """
    Sum estimated_savings grouped by suggestion_type.

    Returned dict always contains the five canonical rule keys so the
    dashboard can render a stable order regardless of which rules fired.
    """
    out: dict[str, float] = {
        "spend_no_sales":      0.0,
        "high_acos":           0.0,
        "bid_too_high":        0.0,
        "scale_profitable":    0.0,
        "promote_search_term": 0.0,
    }
    for s in suggestions:
        t = s.get("suggestion_type")
        if t in out:
            out[t] += float(s.get("estimated_savings", 0) or 0)
    return {k: round(v, 2) for k, v in out.items()}


# ──────────────────────────────────────────────────────────────────────────
#  Smart Recommendation Card view
# ──────────────────────────────────────────────────────────────────────────
#
# `build_card_view(suggestion, ...)` transforms an engine-shaped suggestion
# dict into the fields the dashboard / CSV-preview card template renders:
# risk label, type label, one-sentence headline, evidence-weighted dollar
# impact, why-this-matters prose, neutral memory hint, recommended action
# bullets, queued-not-applied status note, and the Learn-more math block.
#
# The math is deliberately conservative: the headline shows an
# evidence-weighted "likely impact" smaller than the raw 30-day cost the
# rule already reports as `estimated_savings`. The raw number stays in
# `estimated_savings` for banner totals; the card is where SellerCopilot's
# per-recommendation explanation depth lives.
#
# Pure: no DB, no clock dependence except through inputs. Deterministic.

DEFAULT_TARGET_ACOS = 0.30   # 30% used when the seller has not provided one.
LOOKBACK_DAYS_DEFAULT = 30   # engine windows are 30 days by convention.

# Evidence multiplier thresholds (see CLAUDE_NEXT_WORK.md Task 1 spec).
# Higher click + spend volume => more confidence the signal is real.
_EVIDENCE_BANDS: tuple[tuple[int, float, float], ...] = (
    (40, 75.0, 0.75),
    (25, 50.0, 0.65),
    (15, 25.0, 0.50),
)

# Which rule types are reductions / pauses vs. growth bets. Used to pick
# the action multiplier and the lift-vs-savings framing on the card.
_PAUSE_TYPES   = ("spend_no_sales",)
_BID_DOWN_TYPES = ("high_acos", "bid_too_high")
_GROWTH_TYPES  = ("scale_profitable", "promote_search_term")

_ACTION_MULTIPLIER_BY_TYPE: dict[str, float] = {
    "spend_no_sales":      1.00,   # negative exact / pause: full credit
    "high_acos":           0.85,   # bid down on bleeding ACOS keyword
    "bid_too_high":        0.85,   # bid down toward ad-group default
    "scale_profitable":    0.60,   # growth bet: less certain return
    "promote_search_term": 0.60,
}

_TYPE_LABEL_BY_TYPE: dict[str, str] = {
    "spend_no_sales":      "Waste cleanup",
    "high_acos":           "ACOS reduction",
    "bid_too_high":        "Overbid cleanup",
    "scale_profitable":    "Scale a winner",
    "promote_search_term": "Promote a search term",
}

# Honest "why you might still reject this" counterweight per rule type.
# One sentence each. Deterministic. No LLM.
_REJECT_HINT_BY_TYPE: dict[str, str] = {
    "spend_no_sales":
        "Reject if this keyword is new and you want more time before "
        "pausing it.",
    "high_acos":
        "Reject if you run this keyword for visibility, not direct ROAS.",
    "bid_too_high":
        "Reject if you deliberately pay a premium on this keyword for "
        "top-of-page exposure.",
    "scale_profitable":
        "Reject if you need to keep the budget in another campaign first.",
    "promote_search_term":
        "Reject if you do not want this term locked to exact match yet.",
}

DEFAULT_MEMORY_HINT_NEUTRAL = (
    "No similar rejection found. If you reject this, I'll avoid surfacing "
    "this pattern again unless spend increases materially."
)

QUEUED_STATUS_NOTE = (
    "Approve records this decision. It does not send changes to Amazon yet."
)


def _evidence_multiplier(clicks: int, spend: float) -> float:
    """
    Confidence the signal is real, based on click and spend volume.
    Returns 0 when neither band qualifies.
    """
    clicks_i = int(clicks or 0)
    spend_f  = float(spend or 0)
    for click_floor, spend_floor, mult in _EVIDENCE_BANDS:
        if clicks_i >= click_floor and spend_f >= spend_floor:
            return mult
    return 0.0


def _sales_risk_multiplier(orders: int, sales: float, spend: float,
                           target_acos: float) -> float:
    """
    Weighting for "is the historical pattern bleed-shaped?":
      - 1.00 when there are zero orders and zero sales (pure waste case);
      - 0.75 when ACOS >= 2x the seller's target (severe bleed);
      - 0.50 when ACOS >= 1.5x target (moderate bleed);
      - 0    otherwise.
    """
    orders_i = int(orders or 0)
    sales_f  = float(sales or 0)
    spend_f  = float(spend or 0)
    target   = float(target_acos or DEFAULT_TARGET_ACOS)
    if orders_i == 0 and sales_f == 0:
        return 1.00
    if sales_f > 0:
        acos = spend_f / sales_f
        if acos >= target * 2:
            return 0.75
        if acos >= target * 1.5:
            return 0.50
    return 0.0


def _action_multiplier(suggestion_type: str) -> float:
    """How fully an approved action is expected to materialise as $."""
    return _ACTION_MULTIPLIER_BY_TYPE.get(suggestion_type, 0.0)


def _risk_label(suggestion_type: str, evidence_mult: float,
                sales_risk_mult: float, action_mult: float,
                confidence: str) -> str:
    """
    LOW / MEDIUM / HIGH RISK label expressing how likely the action is to
    hurt sales. Pause/negative-exact actions on zero-conversion waste are
    the safest class; bid-down on a bleeding-ACOS keyword carries some
    chance of losing marginal sales; growth bets are inherently uncertain.

    Deterministic. No randomness. No external state.

    Sales-risk multiplier is *only* defined for waste-shaped patterns;
    for growth rules we evaluate combined evidence using just (evidence ×
    action). Otherwise growth-on-healthy-keyword always zeroes out sales
    risk (no bleed) and gets falsely tagged HIGH.
    """
    if suggestion_type in _GROWTH_TYPES:
        combined = float(evidence_mult) * float(action_mult)
        # Growth bets carry inherent uncertainty even with strong evidence;
        # cap them at MEDIUM RISK on the scale.
        if combined <= 0:
            return "HIGH RISK"
        return "MEDIUM RISK"

    combined = float(evidence_mult) * float(sales_risk_mult) * float(action_mult)
    if combined <= 0:
        return "HIGH RISK"
    if suggestion_type in _PAUSE_TYPES:
        return "LOW RISK"
    if suggestion_type == "bid_too_high":
        return "LOW RISK" if confidence == "high" else "MEDIUM RISK"
    if suggestion_type == "high_acos":
        return "MEDIUM RISK"
    return "MEDIUM RISK"


def _extract_card_metrics(suggestion: dict[str, Any]) -> dict[str, float]:
    """
    Pull the metrics the card shows / the multipliers consume out of the
    suggestion's `current_value` payload, accounting for the rule-shape
    differences. Defaults to 0 for any field the rule didn't produce.
    """
    cv = suggestion.get("current_value") or {}
    stype = suggestion.get("suggestion_type", "")

    spend  = float(cv.get("cost_30d", 0) or 0)
    sales  = float(cv.get("sales_30d", 0) or 0)
    clicks = int(cv.get("clicks_30d", 0) or 0)

    if stype == "scale_profitable":
        # current_value lacks cost; derive from acos*sales when both exist.
        acos_30d = float(cv.get("acos_30d", 0) or 0)
        if spend == 0 and acos_30d > 0 and sales > 0:
            spend = round(acos_30d * sales, 2)

    if stype == "promote_search_term":
        # search-term aggregate uses purchases_30d, not sales-side orders.
        orders = int(cv.get("purchases_30d", 0) or 0)
    else:
        orders = int(cv.get("purchases_30d", 0) or 0)

    return {
        "spend":  spend,
        "sales":  sales,
        "clicks": clicks,
        "orders": orders,
    }


def _keyword_text(suggestion: dict[str, Any]) -> str:
    """Best-effort keyword / search-term display string."""
    cv = suggestion.get("current_value") or {}
    pv = suggestion.get("proposed_value") or {}
    if suggestion.get("suggestion_type") == "promote_search_term":
        return str(cv.get("search_term") or pv.get("add_keyword") or "search term")
    # Other rules surface keyword text in their reason string; pull from
    # current_value when present, fall back to a blank-safe default.
    return str(cv.get("keyword_text") or cv.get("keywordText") or "this keyword")


def _headline(suggestion: dict[str, Any], kw_text: str) -> str:
    """One-sentence headline. No marketing copy, no exclamation."""
    stype = suggestion.get("suggestion_type", "")
    if stype == "spend_no_sales":
        return f"Stop wasting spend on “{kw_text}”"
    if stype == "high_acos":
        return f"Bring “{kw_text}” ACOS back toward target"
    if stype == "bid_too_high":
        return f"Lower the overbid on “{kw_text}”"
    if stype == "scale_profitable":
        return f"Scale “{kw_text}” while ACOS is healthy"
    if stype == "promote_search_term":
        return f"Promote “{kw_text}” as an exact-match keyword"
    return f"Review “{kw_text}”"


def _financial_impact_text(estimated_impact: float, is_lift: bool) -> str:
    """Plain-English headline number. Present-conditional verbs only."""
    amount = max(0.0, float(estimated_impact or 0))
    if amount <= 0:
        return "Impact too thin to estimate"
    rounded = int(round(amount))
    if is_lift:
        return f"~${rounded}/month projected lift if approved"
    return f"~${rounded}/month avoidable spend"


def _why_this_matters(suggestion: dict[str, Any], metrics: dict[str, float]) -> str:
    """
    1-2 plain-English sentences citing spend, clicks, orders / sales, and
    (where relevant) what NOT to touch. Deterministic.
    """
    stype = suggestion.get("suggestion_type", "")
    spend  = metrics["spend"]
    sales  = metrics["sales"]
    clicks = metrics["clicks"]
    orders = metrics["orders"]
    cv = suggestion.get("current_value") or {}

    if stype == "spend_no_sales":
        return (
            f"This search-term theme spent ${spend:.0f} in the last 30 days "
            f"across {clicks} clicks and produced {orders} orders. "
            "I would block only the non-converting terms and leave any "
            "adjacent converters alone."
        )
    if stype == "high_acos":
        acos = float(cv.get("acos_30d", 0) or 0)
        return (
            f"This keyword spent ${spend:.0f} on ${sales:.0f} in sales over "
            f"30 days, an ACOS of {acos*100:.0f}%. Bidding down brings ACOS "
            "back toward target without pausing a keyword that does convert."
        )
    if stype == "bid_too_high":
        ratio = float(cv.get("ratio", 0) or 0)
        default_bid = float(cv.get("ad_group_default_bid", 0) or 0)
        return (
            f"This keyword bids {ratio:.1f}x the ad-group default of "
            f"${default_bid:.2f} on {clicks} clicks. Bringing the bid "
            "closer to the default keeps the keyword competitive while "
            "ending the overpay."
        )
    if stype == "scale_profitable":
        acos = float(cv.get("acos_30d", 0) or 0)
        impressions = int(cv.get("impressions_30d", 0) or 0)
        return (
            f"This keyword produced ${sales:.0f} in sales at ACOS "
            f"{acos*100:.0f}% on only {impressions} impressions over 30 days. "
            "Raising the bid buys more impressions while ACOS stays healthy."
        )
    if stype == "promote_search_term":
        return (
            f"This search term generated ${sales:.0f} from {orders} orders "
            "over 30 days but is not yet a keyword. Adding it as exact "
            "match captures the volume directly with a higher quality score."
        )
    return suggestion.get("reason", "")


def _recommended_action_lines(suggestion: dict[str, Any], kw_text: str) -> list[str]:
    """
    Bullet lines describing the proposed action concretely. Each line is a
    single self-contained statement so the template can render them as
    a `<ul>` without further parsing.
    """
    stype = suggestion.get("suggestion_type", "")
    cv = suggestion.get("current_value") or {}
    pv = suggestion.get("proposed_value") or {}
    if stype == "spend_no_sales":
        return [
            f"Add as negative exact: {kw_text}",
            "Pause the matching keyword if no other ad group needs it active.",
        ]
    if stype == "high_acos":
        cur_bid = float(cv.get("bid", 0) or 0)
        new_bid = float(pv.get("bid", 0) or 0)
        target  = float(pv.get("target_acos", DEFAULT_TARGET_ACOS) or DEFAULT_TARGET_ACOS)
        return [
            f"Lower bid: ${cur_bid:.2f} → ${new_bid:.2f}",
            f"Target ACOS: {int(round(target * 100))}%",
        ]
    if stype == "bid_too_high":
        cur_bid = float(cv.get("bid", 0) or 0)
        new_bid = float(pv.get("bid", 0) or 0)
        return [
            f"Lower bid: ${cur_bid:.2f} → ${new_bid:.2f}",
            f"Stay slightly above the ad-group default of "
            f"${float(cv.get('ad_group_default_bid', 0) or 0):.2f}.",
        ]
    if stype == "scale_profitable":
        cur_bid = float(cv.get("bid", 0) or 0)
        new_bid = float(pv.get("bid", 0) or 0)
        return [
            f"Raise bid: ${cur_bid:.2f} → ${new_bid:.2f}",
            "Cap raise if ACOS climbs above the rule's target.",
        ]
    if stype == "promote_search_term":
        bid = float(pv.get("bid", 0) or 0)
        match = str(pv.get("match_type", "exact"))
        return [
            f"Add as {match}-match keyword: {kw_text}",
            f"Suggested bid: ${bid:.2f}",
        ]
    return ["Review this suggestion in the dashboard."]


def _learn_more_block(suggestion: dict[str, Any],
                       metrics: dict[str, float],
                       target_acos: float,
                       evidence_mult: float,
                       sales_risk_mult: float,
                       action_mult: float,
                       observed_waste: float,
                       monthlyized_waste: float,
                       estimated_impact: float,
                       risk_label: str) -> dict[str, Any]:
    """Math + risk explanation surfaced in the collapsible Learn-more block."""
    is_default_target = abs(float(target_acos) - DEFAULT_TARGET_ACOS) < 1e-9
    target_label = (
        "30% default" if is_default_target
        else f"{int(round(target_acos * 100))}% (your setting)"
    )

    # Formula text: keep the multipliers visible so a sceptical seller can
    # trace the math from observed inputs to the headline number.
    formula_parts: list[str] = [f"${monthlyized_waste:.2f}"]
    if evidence_mult > 0:
        formula_parts.append(f"× {evidence_mult:.2f}")
    if sales_risk_mult > 0:
        formula_parts.append(f"× {sales_risk_mult:.2f}")
    if action_mult > 0:
        formula_parts.append(f"× {action_mult:.2f}")
    formula = " ".join(formula_parts) + f" = ~${estimated_impact:.2f}/month"

    stype = suggestion.get("suggestion_type", "")
    if risk_label == "LOW RISK" and stype == "spend_no_sales":
        risk_explanation = (
            "The blocked terms had zero orders. Pausing them is reversible "
            "and does not touch adjacent keywords that are converting."
        )
    elif risk_label == "LOW RISK":
        risk_explanation = (
            "Strong evidence and a narrow, reversible action. Limited "
            "downside if it does not produce the projected effect."
        )
    elif risk_label == "MEDIUM RISK":
        risk_explanation = (
            "Reasonable evidence but the action affects a keyword that "
            "still converts. Monitor for one to two weeks after approval."
        )
    else:
        risk_explanation = (
            "Evidence is thin or the action could materially change a "
            "campaign that is performing. Reject unless you have outside "
            "context that justifies the change."
        )

    return {
        "observed_spend":      round(metrics["spend"], 2),
        "attributed_sales":    round(metrics["sales"], 2),
        "orders":              int(metrics["orders"]),
        "clicks":              int(metrics["clicks"]),
        "target_acos_used":    round(float(target_acos), 4),
        "target_acos_label":   target_label,
        "observed_waste":      round(float(observed_waste), 2),
        "evidence_multiplier": round(float(evidence_mult), 2),
        "sales_risk_multiplier": round(float(sales_risk_mult), 2),
        "action_multiplier":   round(float(action_mult), 2),
        "estimated_impact":    round(float(estimated_impact), 2),
        "estimated_impact_formula": formula,
        "risk_explanation":    risk_explanation,
    }


def build_card_view(suggestion: dict[str, Any],
                    target_acos: float | None = None,
                    memory_hint: str | None = None) -> dict[str, Any]:
    """
    Compute the full Smart-Recommendation-Card view for one suggestion.

    Returns a flat dict the template can render without further branching.
    The original `suggestion` dict is not mutated.

    `target_acos`  override the 30% default (for sellers who provide one).
    `memory_hint`  override the neutral default with a memory-driven hint
                   (e.g. "Skipped because you rejected this on May 1");
                   pass None for the neutral pre-memory copy.
    """
    target = float(target_acos if target_acos is not None else DEFAULT_TARGET_ACOS)
    metrics = _extract_card_metrics(suggestion)
    stype = suggestion.get("suggestion_type", "")
    confidence = str(suggestion.get("confidence", "medium"))

    is_lift = stype in _GROWTH_TYPES

    em = _evidence_multiplier(metrics["clicks"], metrics["spend"])
    srm = _sales_risk_multiplier(
        orders=metrics["orders"],
        sales=metrics["sales"],
        spend=metrics["spend"],
        target_acos=target,
    )
    am = _action_multiplier(stype)

    # Headline financial impact: rule-aware so we never over-weight a
    # growth bet with sales-risk math meant for waste.
    if stype in _PAUSE_TYPES + _BID_DOWN_TYPES:
        observed_waste = max(0.0, metrics["spend"] - metrics["sales"] * target)
        monthlyized = observed_waste * (30.0 / float(LOOKBACK_DAYS_DEFAULT))
        estimated_impact = monthlyized * em * srm * am
    else:
        # Growth rules: use the rule's existing projected lift, weighted
        # only by the action multiplier (no waste-side multipliers).
        base = float(suggestion.get("estimated_savings", 0) or 0)
        observed_waste = 0.0
        monthlyized = base
        estimated_impact = base * am

    estimated_impact = round(estimated_impact, 2)
    risk_label = _risk_label(stype, em, srm, am, confidence)

    kw_text = _keyword_text(suggestion)

    # Seller-memory metadata (Task 3). Persisted alongside `current_value`
    # under the private `_memory` key by `_apply_memory_filter`. The card
    # exposes a memory hint and an optional memory-score override that
    # `composite_score` consumes for the resurfaced-card ranking penalty.
    cv_memory = (suggestion.get("current_value") or {}).get("_memory") or {}
    is_resurfaced = bool(cv_memory.get("resurfaced"))
    persisted_hint = cv_memory.get("hint")
    memory_score_override = cv_memory.get("score_override")
    # Memory kind drives visual treatment in the card template:
    # - "rejection_resurface" : amber badge "BACK FROM REJECTION"
    # - "approval_match"      : green badge "MATCHES YOUR PATTERN"
    # - None / "neutral"      : no badge
    memory_kind = cv_memory.get("kind") or (
        "rejection_resurface" if is_resurfaced else "neutral"
    )
    if memory_score_override is not None:
        try:
            memory_score_override = float(memory_score_override)
        except (TypeError, ValueError):
            memory_score_override = None

    # Hint precedence: explicit caller arg > persisted memory > neutral default.
    final_hint = memory_hint or persisted_hint or DEFAULT_MEMORY_HINT_NEUTRAL

    return {
        # identity / status
        "id":               suggestion.get("id"),
        "suggestion_type":  stype,
        "type_label":       _TYPE_LABEL_BY_TYPE.get(stype, stype),
        "status":           suggestion.get("status", STATUS_PENDING),
        "confidence":       confidence,
        "is_lift":          is_lift,
        # display
        "risk_label":       risk_label,
        "headline":         _headline(suggestion, kw_text),
        "financial_impact_text": _financial_impact_text(estimated_impact, is_lift),
        "estimated_impact": estimated_impact,
        "why_this_matters": _why_this_matters(suggestion, metrics),
        "memory_hint":      final_hint,
        "recommended_action_lines": _recommended_action_lines(suggestion, kw_text),
        "reject_hint":      _REJECT_HINT_BY_TYPE.get(stype, ""),
        "queued_status_note": QUEUED_STATUS_NOTE,
        # seller memory
        "is_resurfaced":         is_resurfaced,
        "memory_kind":           memory_kind,
        "memory_score_override": memory_score_override,
        # learn-more math
        "learn_more":       _learn_more_block(
            suggestion, metrics, target,
            em, srm, am,
            observed_waste, monthlyized, estimated_impact,
            risk_label,
        ),
        # raw engine values still available to the template if needed
        "estimated_savings": float(suggestion.get("estimated_savings", 0) or 0),
    }


def build_card_views(suggestions: list[dict[str, Any]],
                      target_acos: float | None = None) -> list[dict[str, Any]]:
    """Card-view dicts for a batch. Order preserved."""
    return [build_card_view(s, target_acos=target_acos) for s in suggestions]


# ──────────────────────────────────────────────────────────────────────────
#  Top-N ranker for the first-view dashboard / CSV preview
# ──────────────────────────────────────────────────────────────────────────
#
# Composite score per Smart Recommendation Card. Deterministic. No
# randomness, no clock dependence except through inputs.
#
# Component scores are normalised 0-100. The composite is a weighted
# sum, also 0-100, so a card with no signal is exactly 0 and a card
# with maximum signal is exactly 100.
#
# Hard filters apply to the FIRST VIEW only:
#   - estimated_impact >= $50/month
#   - confidence_score > 0
#
# Items that fail filters or exceed the top-N are surfaced behind a
# "Show N more" affordance so the long tail is not silently hidden.
#
# Tie-break is explicit: composite score DESC -> estimated_impact DESC
# -> id ASC. id is normalised so cards without an id (CSV preview path)
# sort last among equals rather than crashing.

TOP_N_DEFAULT = 5
FIRST_VIEW_MIN_IMPACT_USD = 50.0
MEMORY_SCORE_DEFAULT = 50.0   # Task 3 ships real memory; do not fake.

_RANKING_WEIGHTS: dict[str, float] = {
    "impact":        0.40,
    "confidence":    0.25,
    "actionability": 0.15,
    "risk":          0.10,
    "memory":        0.10,
}


def _impact_score(estimated_impact: float) -> float:
    """0-100 from monthly dollar impact: 1 point per $5/mo, capped at $500."""
    return float(min(100.0, max(0.0, float(estimated_impact or 0)) / 5.0))


def _confidence_score(evidence_multiplier: float) -> float:
    """Map the card's evidence band to a 0-100 score."""
    em = float(evidence_multiplier or 0)
    if abs(em - 0.75) < 1e-9:
        return 100.0
    if abs(em - 0.65) < 1e-9:
        return 70.0
    if abs(em - 0.50) < 1e-9:
        return 40.0
    return 0.0


_ACTIONABILITY_SCORE_BY_TYPE: dict[str, float] = {
    "spend_no_sales":      100.0,  # negative exact / pause: full credit
    "high_acos":            80.0,
    "bid_too_high":         80.0,
    "scale_profitable":     60.0,  # growth bet
    "promote_search_term":  60.0,
}


def _actionability_score(suggestion_type: str) -> float:
    return _ACTIONABILITY_SCORE_BY_TYPE.get(suggestion_type, 0.0)


_RISK_SCORE_BY_LABEL: dict[str, float] = {
    "LOW RISK":    100.0,
    "MEDIUM RISK":  70.0,
    "HIGH RISK":    40.0,
}


def _risk_score(risk_label: str) -> float:
    return _RISK_SCORE_BY_LABEL.get(risk_label, 0.0)


def _memory_score(value: float | None = None) -> float:
    """
    Memory-component score for the composite ranker.

    Default 50. When the caller passes an explicit value (Task 3:
    `MEMORY_SCORE_RESURFACED = 10` for cards that come back despite a
    recent rejection), that value wins. No clock dependence.
    """
    if value is None:
        return MEMORY_SCORE_DEFAULT
    return float(value)


def composite_score(card: dict[str, Any]) -> dict[str, float]:
    """
    Composite score and components for one card view.

    Returns a flat dict so callers (and tests) can inspect each
    component independently.

    Pure: input is not mutated.

    Memory-score override (Task 3): if the card carries a
    `memory_score_override` (set by `build_card_view` when the
    suggestion's `current_value._memory.score_override` is populated by
    `_apply_memory_filter`), that value is used instead of the default.
    """
    estimated_impact = float(card.get("estimated_impact", 0) or 0)
    evidence_mult = float(
        (card.get("learn_more") or {}).get("evidence_multiplier", 0) or 0
    )
    impact = _impact_score(estimated_impact)
    confidence = _confidence_score(evidence_mult)
    actionability = _actionability_score(card.get("suggestion_type", ""))
    risk = _risk_score(card.get("risk_label", ""))
    memory = _memory_score(card.get("memory_score_override"))
    score = (
        impact * _RANKING_WEIGHTS["impact"]
        + confidence * _RANKING_WEIGHTS["confidence"]
        + actionability * _RANKING_WEIGHTS["actionability"]
        + risk * _RANKING_WEIGHTS["risk"]
        + memory * _RANKING_WEIGHTS["memory"]
    )
    return {
        "impact_score":        round(impact, 2),
        "confidence_score":    round(confidence, 2),
        "actionability_score": round(actionability, 2),
        "risk_score":          round(risk, 2),
        "memory_score":        round(memory, 2),
        "score":               round(score, 2),
    }


def _passes_first_view_filters(card: dict[str, Any],
                               score: dict[str, float]) -> bool:
    """
    First-view hard filters per Task 2 spec:
      - estimated_impact >= $50/month
      - confidence_score > 0
    """
    if float(card.get("estimated_impact", 0) or 0) < FIRST_VIEW_MIN_IMPACT_USD:
        return False
    if score["confidence_score"] <= 0:
        return False
    return True


def rank_recommendations(cards: list[dict[str, Any]],
                          limit: int = TOP_N_DEFAULT) -> dict[str, Any]:
    """
    Rank Smart Recommendation Card views for the first-view dashboard /
    CSV preview.

    Each card is shallow-copied and augmented with a `score` dict. The
    return value is::

        {
            "top":         list[card],   # ≤ limit, hard-filter-passing
            "hidden":      list[card],   # everything not in top
            "extra_count": int,          # len(hidden)
        }

    Ordering across both buckets:
        composite score DESC -> estimated_impact DESC -> id ASC

    The original input list is not mutated; per-card dicts are shallow
    copies, so `learn_more` / `recommended_action_lines` references
    are shared (read-only).

    `limit` is the visible cap on `top`. The brief calls 3-5 a
    "target / maximum, not a quota": if only 1 card passes filters,
    `top` has length 1.
    """
    if not cards:
        return {"top": [], "hidden": [], "extra_count": 0}

    enriched: list[dict[str, Any]] = []
    for c in cards:
        copy = dict(c)
        copy["score"] = composite_score(c)
        enriched.append(copy)

    def sort_key(c: dict[str, Any]):
        cid = c.get("id")
        # Cards without an id (CSV preview path) sort last among equals
        # rather than crashing on None comparison. Use a sentinel large
        # enough to push None ids to the back deterministically.
        try:
            cid_norm = int(cid) if cid is not None else 10**12
        except (TypeError, ValueError):
            cid_norm = 10**12
        return (
            -float(c["score"]["score"]),
            -float(c.get("estimated_impact", 0) or 0),
            cid_norm,
        )

    enriched.sort(key=sort_key)

    top: list[dict[str, Any]] = []
    hidden: list[dict[str, Any]] = []
    n = max(0, int(limit))
    for c in enriched:
        if len(top) < n and _passes_first_view_filters(c, c["score"]):
            top.append(c)
        else:
            hidden.append(c)

    return {"top": top, "hidden": hidden, "extra_count": len(hidden)}


# ──────────────────────────────────────────────────────────────────────────
#  Minimal seller memory (cycle-18 / Task 3)
# ──────────────────────────────────────────────────────────────────────────
#
# Goal: SellerCopilot visibly remembers what the seller rejected, without
# building a vector store or a per-rule learning model. The whole layer
# is two helpers, one filter, and one render-side query:
#
#   _suggestion_signature(s)
#       deterministic identity tuple. Same input -> same tuple.
#
#   _is_material_change(new, old) -> (changed, reason)
#       per the brief's three thresholds (impact 50%+, spend 50%+,
#       ACOS worsened by 15 percentage points+).
#
#   _apply_memory_filter(new_suggestions, recent_rejections)
#       suppresses non-material-change matches; resurfaces material-
#       change matches with `_memory` metadata in current_value so the
#       card view can pull a hint and the ranker can apply the
#       resurfaced-card score override.
#
#   list_memory_skipped(connection_id, db_ctx_factory)
#       computes the skip list at dashboard render time by re-running
#       the engine against the latest snapshot. Avoids storing skipped
#       items as DB rows.
#
# Hard constraints from the brief:
#   - Use existing ppc_suggestions status + decided_at; do not add a
#     column. Memory metadata embeds inside `current_value` under the
#     private `_memory` key for resurfaced rows.
#   - Suppressed suggestions never appear in the first view or
#     "Show more"; they live only inside the memory pill.
#   - CSV preview has no decision history -> always falls through to
#     the neutral memory hint with no override.
#   - Do not fake positive memory from approvals yet.

REJECT_MEMORY_WINDOW_DAYS  = 14
MEMORY_SCORE_RESURFACED    = 10.0   # composite-score memory penalty
MATERIAL_CHANGE_IMPACT_RATIO = 1.50   # estimated impact must be at least 1.5x
MATERIAL_CHANGE_SPEND_RATIO  = 1.50   # cost_30d must be at least 1.5x
MATERIAL_CHANGE_ACOS_DELTA   = 0.15   # ACOS up by at least 15 percentage points


def _normalise_text(s: Any) -> str:
    return str(s or "").strip().lower()


def _suggestion_signature(s: dict[str, Any]) -> tuple:
    """
    Deterministic identity tuple for memory matching.

    - keyword-level rules (spend_no_sales / high_acos / bid_too_high /
      scale_profitable): (suggestion_type, keyword_id).
    - promote_search_term: (suggestion_type, ad_group_id, normalised
      search-term text).
    - fallback (used only when keyword_id is missing — e.g. CSV-derived
      cards that still managed to land in the DB): (suggestion_type,
      ad_group_id, normalised keyword text).
    """
    stype = s.get("suggestion_type", "") or ""

    if stype == "promote_search_term":
        cv = s.get("current_value") or {}
        pv = s.get("proposed_value") or {}
        st = _normalise_text(cv.get("search_term") or pv.get("add_keyword") or "")
        return (stype, s.get("ad_group_id") or "", st)

    kid = s.get("keyword_id")
    if kid:
        return (stype, kid)

    cv = s.get("current_value") or {}
    text = _normalise_text(cv.get("keyword_text") or cv.get("search_term") or "")
    return (stype, s.get("ad_group_id") or "", text)


def _compute_acos(cv: dict[str, Any]) -> float | None:
    spend = float((cv or {}).get("cost_30d", 0) or 0)
    sales = float((cv or {}).get("sales_30d", 0) or 0)
    if sales <= 0:
        return None
    return spend / sales


def _is_material_change(new_sugg: dict[str, Any],
                         rejected_row: dict[str, Any]) -> tuple[bool, str]:
    """
    Per the brief: a previously-rejected suggestion may resurface only
    if (a) estimated impact rose by 50%+, OR (b) spend rose by 50%+,
    OR (c) ACOS worsened by 15 percentage points+. Returns
    (changed, short reason). The reason is rendered verbatim into the
    "I'm bringing it back because ..." memory hint.
    """
    new_cv = new_sugg.get("current_value") or {}
    old_cv = rejected_row.get("current_value") or {}

    new_impact = float(new_sugg.get("estimated_savings", 0) or 0)
    old_impact = float(rejected_row.get("estimated_savings", 0) or 0)
    if old_impact > 0 and new_impact >= old_impact * MATERIAL_CHANGE_IMPACT_RATIO:
        return True, (
            f"estimated impact rose from ${old_impact:.0f} to ${new_impact:.0f}"
        )

    new_spend = float(new_cv.get("cost_30d", 0) or 0)
    old_spend = float(old_cv.get("cost_30d", 0) or 0)
    if old_spend > 0 and new_spend >= old_spend * MATERIAL_CHANGE_SPEND_RATIO:
        return True, (
            f"spend increased from ${old_spend:.0f} to ${new_spend:.0f}"
        )

    new_acos = _compute_acos(new_cv)
    old_acos = _compute_acos(old_cv)
    if new_acos is not None and old_acos is not None:
        if (new_acos - old_acos) >= MATERIAL_CHANGE_ACOS_DELTA:
            return True, (
                f"ACOS worsened from {old_acos * 100:.0f}% to "
                f"{new_acos * 100:.0f}%"
            )

    return False, ""


def _format_iso_date(epoch: float) -> str:
    """YYYY-MM-DD UTC. Used in memory hints; not localised intentionally."""
    import datetime
    if not epoch:
        return ""
    try:
        return datetime.datetime.fromtimestamp(
            float(epoch), tz=datetime.timezone.utc
        ).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def _label_for_memory(s: dict[str, Any]) -> str:
    """Best-effort short label used inside memory hints / pills."""
    cv = s.get("current_value") or {}
    pv = s.get("proposed_value") or {}
    if s.get("suggestion_type") == "promote_search_term":
        return str(cv.get("search_term") or pv.get("add_keyword") or "search term")
    return str(cv.get("keyword_text") or s.get("keyword_id") or "this keyword")


def _load_recent_rejections(connection_id: int,
                              db_ctx_factory,
                              now: float | None = None) -> list[dict[str, Any]]:
    """
    Load rejected ppc_suggestions rows whose decided_at lies inside the
    REJECT_MEMORY_WINDOW_DAYS window. Each row is returned with its
    `current_value` JSON parsed and a pre-computed `signature` tuple.

    Defensive: if the DB query fails, returns an empty list and logs a
    warning. Memory is a soft layer; an outage must not block the
    dashboard.
    """
    if db_ctx_factory is None:
        return []
    if now is None:
        now = time.time()
    cutoff = float(now) - REJECT_MEMORY_WINDOW_DAYS * 86400.0

    out: list[dict[str, Any]] = []
    try:
        with db_ctx_factory() as (cur, ph):
            cur.execute(
                f"""
                SELECT id, campaign_id, ad_group_id, keyword_id,
                       suggestion_type, current_value, proposed_value,
                       estimated_savings, decided_at
                FROM ppc_suggestions
                WHERE connection_id = {ph}
                  AND status        = '{STATUS_REJECTED}'
                  AND decided_at IS NOT NULL
                  AND decided_at   >= {ph}
                """,
                (connection_id, cutoff),
            )
            rows = cur.fetchall() or []
    except Exception as e:
        log.warning(
            "load_recent_rejections failed for connection_id=%d: %s",
            connection_id, e,
        )
        return []

    for r in rows:
        cv = _maybe_load_json(r[5])
        pv = _maybe_load_json(r[6])
        item = {
            "id":                r[0],
            "campaign_id":       r[1],
            "ad_group_id":       r[2],
            "keyword_id":        r[3],
            "suggestion_type":   r[4],
            "current_value":     cv,
            "proposed_value":    pv,
            "estimated_savings": float(r[7] or 0.0),
            "decided_at":        float(r[8]),
        }
        item["signature"] = _suggestion_signature(item)
        out.append(item)
    return out


def _apply_memory_filter(new_suggestions: list[dict[str, Any]],
                           recent_rejections: list[dict[str, Any]]
                           ) -> dict[str, list[dict[str, Any]]]:
    """
    Filter newly-analysed suggestions through the recent-rejection set.

    Returns::

        {
            "persisted": [...],   # to insert into ppc_suggestions
            "skipped":   [...],   # for the dashboard's memory pill
        }

    Suppression rule: a new suggestion is suppressed when its signature
    matches a recent rejection AND nothing material has changed.

    Resurface rule: when a recent-rejection match is materially
    different (impact / spend / ACOS thresholds), the new suggestion is
    kept and tagged with `current_value._memory` so the card view shows
    the seller "I'm bringing this back because ..." and the ranker
    applies a memory-score penalty.

    Pure with respect to inputs: per-suggestion dicts are shallow-
    copied where mutated (only the resurfaced ones).
    """
    if not new_suggestions:
        return {"persisted": [], "skipped": []}
    rejection_by_sig = {r["signature"]: r for r in recent_rejections}
    persisted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for s in new_suggestions:
        sig = _suggestion_signature(s)
        rejection = rejection_by_sig.get(sig)
        if rejection is None:
            persisted.append(s)
            continue

        rejected_at = float(rejection.get("decided_at") or 0.0)
        next_eligible_at = rejected_at + REJECT_MEMORY_WINDOW_DAYS * 86400.0
        rejected_iso = _format_iso_date(rejected_at)
        next_iso     = _format_iso_date(next_eligible_at)
        label = _label_for_memory(s)

        changed, reason = _is_material_change(s, rejection)
        if changed:
            new_cv = dict(s.get("current_value") or {})
            new_cv["_memory"] = {
                "resurfaced":         True,
                "rejected_at":        rejected_at,
                "rejected_at_iso":    rejected_iso,
                "next_eligible_at":   next_eligible_at,
                "next_eligible_iso":  next_iso,
                "score_override":     MEMORY_SCORE_RESURFACED,
                "change_reason":      reason,
                "label":              label,
                "hint": (
                    f"You rejected this on {rejected_iso}, but I'm "
                    f"bringing it back because {reason}."
                ),
            }
            new_s = dict(s)
            new_s["current_value"] = new_cv
            persisted.append(new_s)
        else:
            skipped.append({
                "signature":          list(sig),
                "suggestion_type":    s.get("suggestion_type"),
                "label":              label,
                "rejected_at":        rejected_at,
                "rejected_at_iso":    rejected_iso,
                "next_eligible_at":   next_eligible_at,
                "next_eligible_iso":  next_iso,
                "reason": (
                    f"Skipped \"{label}\" because you rejected the same "
                    f"recommendation on {rejected_iso}. I'll check again "
                    f"after {next_iso} unless spend changes materially."
                ),
            })

    return {"persisted": persisted, "skipped": skipped}


def list_memory_skipped(connection_id: int,
                         db_ctx_factory=None) -> list[dict[str, Any]]:
    """
    Return the current memory-skip list for the dashboard's memory pill.

    Re-runs `analyze` against the latest snapshot so the list always
    reflects what `generate_suggestions` would suppress on the next
    refresh. Cheap (the rules engine is pure and small); avoids storing
    skipped items as DB rows.

    Safe under outages: snapshot-load failure or DB error returns [].
    """
    if db_ctx_factory is None:
        from server import _db as db_ctx_factory   # lazy import to avoid cycle

    rejections = _load_recent_rejections(connection_id, db_ctx_factory)
    if not rejections:
        return []

    try:
        snapshots = _load_latest_snapshots(connection_id, db_ctx_factory)
    except Exception as e:
        log.warning(
            "list_memory_skipped: snapshot load failed for connection_id=%d: %s",
            connection_id, e,
        )
        return []

    new_suggestions = analyze(snapshots)
    return _apply_memory_filter(new_suggestions, rejections)["skipped"]


# ──────────────────────────────────────────────────────────────────────────
#  Approval memory: boost suggestions that match prior approvals
# ──────────────────────────────────────────────────────────────────────────
#
# The rejection memory layer (cycle-18) suppresses suggestions the seller
# already said no to. The approval memory layer (Track B 2026-05-09 sprint)
# does the symmetric move: when a fresh suggestion matches the
# signature-pattern of something the seller has approved in the last
# APPROVAL_MEMORY_WINDOW_DAYS, the card gets a boost in the ranker plus
# a transparent "you approved similar before" hint.
#
# The match is by suggestion_type alone (not by exact keyword), because
# approving a high_acos cut on kw-101 is a signal that the seller likes
# that rule, not specifically that keyword. If we matched on keyword we
# would only boost re-runs of the exact same row — usually impossible
# because approving a row removes it from the pending pool.

APPROVAL_MEMORY_WINDOW_DAYS = 30
MEMORY_SCORE_APPROVAL_MATCH = 80.0   # higher than DEFAULT 50, lower than max
APPROVAL_MATCH_MIN_COUNT    = 2      # need 2+ approvals of this type to count


def _load_recent_approvals(connection_id: int,
                            db_ctx_factory,
                            now: float | None = None) -> list[dict[str, Any]]:
    """
    Read recently approved (status = approved_pending_apply OR applied)
    suggestions for the connection within APPROVAL_MEMORY_WINDOW_DAYS.

    Defensive: a DB outage returns []. Memory boost is a soft layer; an
    outage must not block the dashboard.
    """
    if db_ctx_factory is None:
        return []
    if now is None:
        now = time.time()
    cutoff = float(now) - APPROVAL_MEMORY_WINDOW_DAYS * 86400.0

    try:
        with db_ctx_factory() as (cur, ph):
            cur.execute(
                f"""
                SELECT id, suggestion_type, decided_at
                FROM ppc_suggestions
                WHERE connection_id = {ph}
                  AND status IN ('{STATUS_APPROVED_PENDING_APPLY}', '{STATUS_APPLIED}')
                  AND decided_at IS NOT NULL
                  AND decided_at >= {ph}
                """,
                (connection_id, cutoff),
            )
            rows = cur.fetchall() or []
    except Exception as e:
        log.warning(
            "load_recent_approvals failed for connection_id=%d: %s",
            connection_id, e,
        )
        return []

    return [
        {
            "id":              r[0],
            "suggestion_type": r[1],
            "decided_at":      float(r[2] or 0.0),
        }
        for r in rows
    ]


def _approval_type_counts(recent_approvals: list[dict[str, Any]]) -> dict[str, int]:
    """Tally approvals by suggestion_type. Public-shape helper for tests."""
    counts: dict[str, int] = {}
    for a in recent_approvals or []:
        t = a.get("suggestion_type") or ""
        if not t:
            continue
        counts[t] = counts.get(t, 0) + 1
    return counts


def _apply_approval_memory_boost(new_suggestions: list[dict[str, Any]],
                                  recent_approvals: list[dict[str, Any]],
                                  ) -> list[dict[str, Any]]:
    """
    Tag suggestions whose suggestion_type matches a frequently-approved
    pattern with `current_value._memory = {kind: 'approval_match', ...}`.

    Pure: input list is shallow-copied for any item we mutate. Other
    items are passed through as-is.

    Behaviour:
      - count approvals per suggestion_type in the window
      - any type with >= APPROVAL_MATCH_MIN_COUNT approvals is "preferred"
      - new suggestions of a preferred type get _memory tagged
      - if a suggestion already carries a `_memory` envelope (e.g. a
        rejection-resurface), we leave it alone — rejection signal beats
        approval signal because the seller said no recently and we should
        not auto-overrule that.

    Returns: new list with the same length and order. Items are either
    the original or a shallow copy with current_value._memory populated.
    """
    if not new_suggestions:
        return []
    counts = _approval_type_counts(recent_approvals or [])
    preferred = {t for t, n in counts.items() if n >= APPROVAL_MATCH_MIN_COUNT}
    if not preferred:
        return list(new_suggestions)

    out: list[dict[str, Any]] = []
    for s in new_suggestions:
        stype = s.get("suggestion_type", "")
        if stype not in preferred:
            out.append(s)
            continue

        cv = dict(s.get("current_value") or {})
        existing_memory = cv.get("_memory") or {}
        if existing_memory:
            # Don't override rejection-resurface or any prior memory
            # state. Approval boost only applies to fresh suggestions.
            out.append(s)
            continue

        approval_count = counts[stype]
        cv["_memory"] = {
            "kind":           "approval_match",
            "resurfaced":     False,
            "hint":           f"You have approved {approval_count} {stype.replace('_', ' ')} suggestions in the last {APPROVAL_MEMORY_WINDOW_DAYS} days.",
            "score_override": MEMORY_SCORE_APPROVAL_MATCH,
        }
        new_s = dict(s)
        new_s["current_value"] = cv
        out.append(new_s)
    return out


# ──────────────────────────────────────────────────────────────────────────
#  Decision log (Week 1 of MVP Hardening Plan / Task 6)
# ──────────────────────────────────────────────────────────────────────────
#
# Append-only log of every approve/reject. Reads-from sources for:
#   - Adaptive Memory (Week 2): cluster + rule-type dampening based on
#     past rejection patterns.
#   - Decision DNA page (Week 2): per-rule accept rates + last-N
#     decisions list.
#   - Outcome Observer (Week 3): per-decision before-vs-after readings
#     scheduled at observation_due_at = decided_at + 7 days.
#
# Append-only invariant (enforced by code review + a dedicated test):
#   - Public surface: only `log_decision` (INSERT). No update / delete
#     helpers in this module. Backfill checks existence first; it never
#     overwrites an existing row.
#   - The DB schema does not enforce immutability via triggers (kept simple
#     across SQLite/Postgres). Discipline lives in code.
#
# Hard rules:
#   - Never block the user-facing path. If the log INSERT fails, the
#     approve / reject status flip already happened and we log a warning.
#     Memory and outcomes degrade gracefully.
#   - Tenant scoping is the caller's responsibility. The route enforces
#     it via `connection_id IN (SELECT id FROM amazon_connections WHERE
#     customer_id = ?)`. log_decision trusts its inputs.

OBSERVATION_WINDOW_SECONDS = 7 * 86400  # 7 days post-decision


def observation_due_at(decided_at: float | None) -> float | None:
    """Pure helper. Returns decided_at + 7 days, or None if input is None."""
    if decided_at is None:
        return None
    return float(decided_at) + OBSERVATION_WINDOW_SECONDS


def log_decision(connection_id: int,
                  suggestion_id: int | None,
                  suggestion_type: str,
                  decision: str,
                  decided_at: float,
                  *,
                  keyword_id: str | None = None,
                  ad_group_id: str | None = None,
                  campaign_id: str | None = None,
                  current_value: dict[str, Any] | None = None,
                  proposed_value: dict[str, Any] | None = None,
                  estimated_impact: float | None = None,
                  confidence: str | None = None,
                  edit_payload: dict[str, Any] | None = None,
                  db_ctx_factory=None,
                  ) -> int | None:
    """
    Append a row to seller_decisions. Returns the new row id, or None on
    failure. Defensive: any DB error is caught and logged so the caller's
    main path (approve/reject status flip) is never blocked by logging.

    decision: "approved" or "rejected". The caller chooses.
    """
    if db_ctx_factory is None:
        from server import _db as db_ctx_factory

    cv_json = json.dumps(current_value or {})
    pv_json = json.dumps(proposed_value or {})
    edit_json = json.dumps(edit_payload) if edit_payload is not None else None
    obs_due = observation_due_at(decided_at)

    try:
        with db_ctx_factory() as (cur, ph):
            cur.execute(
                f"""
                INSERT INTO seller_decisions
                    (connection_id, suggestion_id, suggestion_type,
                     keyword_id, ad_group_id, campaign_id,
                     current_value, proposed_value,
                     estimated_impact, confidence,
                     decision, edit_payload,
                     decided_at, observation_due_at)
                VALUES
                    ({ph}, {ph}, {ph},
                     {ph}, {ph}, {ph},
                     {ph}, {ph},
                     {ph}, {ph},
                     {ph}, {ph},
                     {ph}, {ph})
                """,
                (
                    connection_id, suggestion_id, suggestion_type,
                    keyword_id, ad_group_id, campaign_id,
                    cv_json, pv_json,
                    float(estimated_impact) if estimated_impact is not None else None,
                    confidence,
                    decision, edit_json,
                    float(decided_at), obs_due,
                ),
            )
            return int(getattr(cur, "lastrowid", 0) or 0) or None
    except Exception as e:
        log.warning(
            "log_decision failed for connection_id=%d suggestion_id=%s: %s",
            connection_id, suggestion_id, e,
        )
        return None


def backfill_seller_decisions(connection_id: int,
                                db_ctx_factory=None) -> dict[str, int]:
    """
    Read existing decided rows from ppc_suggestions for the connection and
    INSERT one row per decided suggestion into seller_decisions if not
    already present. Idempotent: re-runs are safe; duplicates by
    suggestion_id are skipped.

    Returns: {"inserted": N, "skipped_existing": M, "skipped_no_decision": K}.

    Defensive: per-row failures are logged but do not abort the run.

    Status mapping for the decision field:
        - 'rejected'                -> "rejected"
        - 'approved_pending_apply'  -> "approved"
        - 'applied'                 -> "approved" (was approved at decision time)

    Pending rows are skipped (no decision yet).
    """
    if db_ctx_factory is None:
        from server import _db as db_ctx_factory

    inserted = 0
    skipped_existing = 0
    skipped_no_decision = 0

    try:
        with db_ctx_factory() as (cur, ph):
            cur.execute(
                f"""
                SELECT id, campaign_id, ad_group_id, keyword_id,
                       suggestion_type, current_value, proposed_value,
                       estimated_savings, confidence, status, decided_at
                FROM ppc_suggestions
                WHERE connection_id = {ph}
                  AND status IN ('rejected', 'approved_pending_apply', 'applied')
                  AND decided_at IS NOT NULL
                """,
                (connection_id,),
            )
            rows = cur.fetchall() or []
    except Exception as e:
        log.warning(
            "backfill_seller_decisions: SELECT failed for connection_id=%d: %s",
            connection_id, e,
        )
        return {"inserted": 0, "skipped_existing": 0, "skipped_no_decision": 0}

    for r in rows:
        sid = r[0]
        decided = r[10]
        if decided is None:
            skipped_no_decision += 1
            continue

        # Idempotency check: skip if already logged.
        try:
            with db_ctx_factory() as (cur, ph):
                cur.execute(
                    f"SELECT 1 FROM seller_decisions WHERE suggestion_id = {ph} LIMIT 1",
                    (sid,),
                )
                if cur.fetchone() is not None:
                    skipped_existing += 1
                    continue
        except Exception as e:
            log.warning(
                "backfill_seller_decisions: existence check failed for sid=%s: %s",
                sid, e,
            )
            continue

        status = r[9] or ""
        if status == "rejected":
            decision = "rejected"
        elif status in ("approved_pending_apply", "applied"):
            decision = "approved"
        else:
            skipped_no_decision += 1
            continue

        cv = _maybe_load_json(r[5])
        pv = _maybe_load_json(r[6])

        new_id = log_decision(
            connection_id      = connection_id,
            suggestion_id      = sid,
            suggestion_type    = r[4] or "",
            decision           = decision,
            decided_at         = float(decided),
            keyword_id         = r[3],
            ad_group_id        = r[2],
            campaign_id        = r[1],
            current_value      = cv,
            proposed_value     = pv,
            estimated_impact   = float(r[7]) if r[7] is not None else None,
            confidence         = r[8],
            db_ctx_factory     = db_ctx_factory,
        )
        if new_id is not None:
            inserted += 1

    log.info(
        "backfill_seller_decisions connection_id=%d inserted=%d skipped_existing=%d skipped_no_decision=%d",
        connection_id, inserted, skipped_existing, skipped_no_decision,
    )
    return {
        "inserted":            inserted,
        "skipped_existing":    skipped_existing,
        "skipped_no_decision": skipped_no_decision,
    }


# ──────────────────────────────────────────────────────────────────────────
#  Approval baseline (Task 4 / Minimal Proof of Impact)
# ──────────────────────────────────────────────────────────────────────────
#
# When the seller approves a recommendation, we capture the metrics the
# decision was made on into `current_value._approval_baseline`. This gives
# the dashboard something honest to render later (a projection, not a
# realised result) and gives a future post-decision pass a reference
# point to compare against.
#
# Hard rules:
#   - We do not write to Amazon. Status flips to approved_pending_apply,
#     full stop. No applier here.
#   - The dashboard copy that reads the baseline must say "Projection
#     only" / "Calculated from the prior 30 days" / "Nothing has been
#     applied to Amazon yet" / "Real results will differ". The route does
#     not embed those strings; the template does. Anti-overclaim wording
#     ("you saved", "guaranteed", "realized savings") is forbidden.
#   - If a field is missing from current_value (e.g. CSV-derived rows that
#     never had purchases_30d), store 0 / None rather than guessing.
#   - No 7-day post-decision result is faked here. That's a future task.
#
# Public surface:
#   build_approval_baseline(current_value, proposed_value,
#                           estimated_impact, now)
#       -> dict, suitable for serialising into current_value._approval_baseline.
#
#   list_recently_approved_suggestions(connection_id, db_ctx_factory,
#                                      days=14, limit=20)
#       -> dashboard-ready rows with the baseline lifted to top level
#       so the template doesn't have to walk into _approval_baseline.

APPROVAL_NOTE = "No Amazon change was applied. Projection only."
RECENT_APPROVED_DAYS_DEFAULT = 14
RECENT_APPROVED_LIMIT_DEFAULT = 20


def build_approval_baseline(current_value: dict[str, Any] | None,
                             proposed_value: dict[str, Any] | None,
                             estimated_impact: float,
                             now: float) -> dict[str, Any]:
    """
    Pure builder for the `_approval_baseline` JSON payload.

    Inputs are the row's parsed `current_value`, `proposed_value`, and
    `estimated_savings` at approval time. `now` is epoch seconds.

    Output keys:
        approved_at         epoch seconds at approval
        approved_at_iso     YYYY-MM-DD UTC at approval
        cost_30d            observed spend in the 30 days before approval
        sales_30d           attributed sales in the same window
        orders_30d          attributed orders (from purchases_30d)
        clicks_30d          clicks in the same window
        acos_30d            cost / sales, or None if sales == 0
        estimated_impact    estimated_savings at approval time
        target_acos_used    proposed_value.target_acos if present, else None
        keyword_label       best-effort short label for dashboard render
        note                fixed disclaimer string

    Pure: does not consult the clock; `now` must be passed in.
    """
    cv = dict(current_value or {})
    pv = dict(proposed_value or {})

    cost   = float(cv.get("cost_30d", 0) or 0)
    sales  = float(cv.get("sales_30d", 0) or 0)
    orders = int(cv.get("purchases_30d", 0) or 0)
    clicks = int(cv.get("clicks_30d", 0) or 0)
    acos   = round(cost / sales, 4) if sales > 0 else None

    target_raw = pv.get("target_acos")
    target_acos: float | None
    try:
        target_acos = float(target_raw) if target_raw is not None else None
    except (TypeError, ValueError):
        target_acos = None

    label = (
        cv.get("keyword_text")
        or cv.get("search_term")
        or pv.get("add_keyword")
        or ""
    )

    return {
        "approved_at":      float(now),
        "approved_at_iso":  _format_iso_date(now),
        "cost_30d":         round(cost, 2),
        "sales_30d":        round(sales, 2),
        "orders_30d":       orders,
        "clicks_30d":       clicks,
        "acos_30d":         acos,
        "estimated_impact": round(float(estimated_impact or 0.0), 2),
        "target_acos_used": target_acos,
        "keyword_label":    str(label or ""),
        "note":             APPROVAL_NOTE,
    }


def list_recently_approved_suggestions(connection_id: int,
                                        db_ctx_factory=None,
                                        days: int = RECENT_APPROVED_DAYS_DEFAULT,
                                        limit: int = RECENT_APPROVED_LIMIT_DEFAULT,
                                        now: float | None = None,
                                        ) -> list[dict[str, Any]]:
    """
    Read recently approved (status = approved_pending_apply) suggestions
    for the dashboard's projection block.

    Returns dicts shaped like `list_pending_suggestions` rows with a
    flattened `_approval_baseline` so the template can render
    `row.cost_30d`, `row.estimated_impact`, etc directly.

    Defensive: any DB outage returns []. The projection block is a soft
    layer; an outage must not block the dashboard.
    """
    if db_ctx_factory is None:
        from server import _db as db_ctx_factory
    if now is None:
        now = time.time()
    cutoff = float(now) - max(int(days), 0) * 86400.0

    try:
        with db_ctx_factory() as (cur, ph):
            cur.execute(
                f"""
                SELECT id, campaign_id, ad_group_id, keyword_id,
                       suggestion_type, current_value, proposed_value,
                       reason, estimated_savings, confidence, status,
                       created_at, decided_at
                FROM ppc_suggestions
                WHERE connection_id = {ph}
                  AND status        = '{STATUS_APPROVED_PENDING_APPLY}'
                  AND decided_at IS NOT NULL
                  AND decided_at   >= {ph}
                ORDER BY decided_at DESC, id ASC
                """,
                (connection_id, cutoff),
            )
            rows = cur.fetchall() or []
    except Exception as e:
        log.warning(
            "list_recently_approved_suggestions failed for connection_id=%d: %s",
            connection_id, e,
        )
        return []

    out: list[dict[str, Any]] = []
    for r in rows[: max(int(limit), 0)]:
        cv = _maybe_load_json(r[5])
        pv = _maybe_load_json(r[6])
        baseline = (cv or {}).get("_approval_baseline") or {}
        item: dict[str, Any] = {
            "id":                r[0],
            "campaign_id":       r[1],
            "ad_group_id":       r[2],
            "keyword_id":        r[3],
            "suggestion_type":   r[4],
            "current_value":     cv,
            "proposed_value":    pv,
            "reason":            r[7] or "",
            "estimated_savings": float(r[8] or 0.0),
            "confidence":        r[9] or "medium",
            "status":            r[10] or STATUS_APPROVED_PENDING_APPLY,
            "created_at":        float(r[11] or 0.0),
            "decided_at":        float(r[12] or 0.0),
            "has_baseline":      bool(baseline),
            "approved_at":       float(baseline.get("approved_at", r[12] or 0.0)),
            "approved_at_iso":   baseline.get("approved_at_iso") or _format_iso_date(float(r[12] or 0.0)),
            "cost_30d":          float(baseline.get("cost_30d", 0.0) or 0.0),
            "sales_30d":         float(baseline.get("sales_30d", 0.0) or 0.0),
            "orders_30d":        int(baseline.get("orders_30d", 0) or 0),
            "clicks_30d":        int(baseline.get("clicks_30d", 0) or 0),
            "acos_30d":          baseline.get("acos_30d"),
            "estimated_impact":  float(baseline.get("estimated_impact", float(r[8] or 0.0)) or 0.0),
            "target_acos_used":  baseline.get("target_acos_used"),
            "keyword_label":     baseline.get("keyword_label") or "",
            "note":              baseline.get("note") or APPROVAL_NOTE,
        }
        out.append(item)
    return out


# ──────────────────────────────────────────────────────────────────────────
#  Decision audit page (Track B 2026-05-09 sprint)
# ──────────────────────────────────────────────────────────────────────────

AUDIT_DEFAULT_LIMIT = 200


def list_decisions_with_outcomes(connection_id: int,
                                  db_ctx_factory=None,
                                  limit: int = AUDIT_DEFAULT_LIMIT,
                                  ) -> list[dict[str, Any]]:
    """
    Read every decision the seller made on this connection, joined with
    its observed outcome (if the observer has run on it yet). Used by
    the /ppc/audit page and the export endpoints.

    Returns rows shaped for direct template / CSV / PDF rendering. Each
    row carries:
      id, suggestion_type, decision, keyword_label, decided_at,
      decided_at_iso, observation_due_at, observation_due_at_iso,
      baseline (cost_30d, sales_30d, etc), proposed_change_summary,
      classification (or 'pending_observation'),
      classification_summary, observed_at, observed_at_iso, copy_status

    Defensive: a DB outage returns []. Audit is a read-only view; an
    outage must never block other dashboard surfaces.

    Anti-overclaim: rows with no decision_outcomes match get
    classification='pending_observation' and copy_status='projection_only'
    so the template knows to say "no observation yet" instead of
    inventing a result.
    """
    if db_ctx_factory is None:
        from server import _db as db_ctx_factory

    try:
        with db_ctx_factory() as (cur, ph):
            cur.execute(
                f"""
                SELECT sd.id, sd.suggestion_type, sd.decision, sd.keyword_id,
                       sd.ad_group_id, sd.campaign_id, sd.current_value,
                       sd.proposed_value, sd.estimated_impact, sd.confidence,
                       sd.decided_at, sd.observation_due_at,
                       outr.classification, outr.observed,
                       outr.observed_at, outr.copy_status
                FROM seller_decisions sd
                LEFT JOIN decision_outcomes outr
                       ON outr.seller_decisions_id = sd.id
                WHERE sd.connection_id = {ph}
                ORDER BY sd.decided_at DESC, sd.id DESC
                """,
                (connection_id,),
            )
            rows = cur.fetchall() or []
    except Exception as e:
        log.warning(
            "list_decisions_with_outcomes failed for connection_id=%d: %s",
            connection_id, e,
        )
        return []

    out: list[dict[str, Any]] = []
    for r in rows[: max(int(limit), 0)]:
        cv = _maybe_load_json(r[6])
        pv = _maybe_load_json(r[7])
        baseline = (cv or {}).get("_approval_baseline") or {}
        observed_metrics = _maybe_load_json(r[13]) if r[13] is not None else {}

        # Honest classification: if no row in decision_outcomes yet, mark
        # explicitly. Do NOT default to 'metrics_moved_better' or anything
        # that implies success.
        classification = r[12] or "pending_observation"
        copy_status    = r[15] or ("observed" if r[12] else "projection_only")
        observed_at    = float(r[14]) if r[14] is not None else None

        item: dict[str, Any] = {
            "id":                     r[0],
            "suggestion_type":        r[1],
            "decision":               r[2],
            "keyword_id":             r[3] or "",
            "ad_group_id":            r[4] or "",
            "campaign_id":            r[5] or "",
            "estimated_impact":       float(r[8] or 0.0),
            "confidence":             r[9] or "medium",
            "decided_at":             float(r[10] or 0.0),
            "decided_at_iso":         _format_iso_date(float(r[10] or 0.0)),
            "observation_due_at":     float(r[11]) if r[11] is not None else None,
            "observation_due_at_iso": _format_iso_date(float(r[11])) if r[11] is not None else "",
            "baseline_cost_30d":      float(baseline.get("cost_30d", cv.get("cost_30d", 0)) or 0),
            "baseline_sales_30d":     float(baseline.get("sales_30d", cv.get("sales_30d", 0)) or 0),
            "baseline_clicks_30d":    int(baseline.get("clicks_30d", cv.get("clicks_30d", 0)) or 0),
            "baseline_acos_30d":      baseline.get("acos_30d", cv.get("acos_30d")),
            "keyword_label":          baseline.get("keyword_label") or cv.get("keyword_text") or r[3] or "",
            "proposed_summary":       _audit_proposed_summary(r[1], pv),
            "classification":         classification,
            "observed_cost_30d":      float(observed_metrics.get("cost_30d", 0) or 0) if observed_metrics else None,
            "observed_sales_30d":     float(observed_metrics.get("sales_30d", 0) or 0) if observed_metrics else None,
            "observed_clicks_30d":    int(observed_metrics.get("clicks_30d", 0) or 0) if observed_metrics else None,
            "observed_at":            observed_at,
            "observed_at_iso":        _format_iso_date(observed_at) if observed_at else "",
            "copy_status":            copy_status,
        }
        out.append(item)
    return out


def _audit_proposed_summary(suggestion_type: str, pv: dict[str, Any] | None) -> str:
    """Short human-readable summary of what the suggestion proposed."""
    pv = pv or {}
    if suggestion_type == "spend_no_sales":
        return "Pause keyword"
    if suggestion_type == "high_acos":
        target = pv.get("target_acos")
        return f"Bid down to {float(target) * 100:.0f}% target ACOS" if target else "Bid down toward target ACOS"
    if suggestion_type == "bid_too_high":
        new_bid = pv.get("bid")
        return f"Lower bid to ${float(new_bid):.2f}" if new_bid else "Lower bid to ad-group default"
    if suggestion_type == "scale_profitable":
        new_bid = pv.get("bid")
        return f"Raise bid to ${float(new_bid):.2f}" if new_bid else "Raise bid 20%"
    if suggestion_type == "promote_search_term":
        kw = pv.get("add_keyword")
        return f"Add '{kw}' as exact-match keyword" if kw else "Add as exact-match keyword"
    return suggestion_type


def audit_classification_label(classification: str) -> str:
    """
    Render-side label for a classification. Anti-overclaim by design:
    every label describes what the metrics did, never what we did. The
    test `test_no_summary_claims_causation` enforces this.
    """
    labels = {
        "metrics_moved_better":  "Metrics moved in the desired direction",
        "metrics_moved_worse":   "Metrics moved against the decision",
        "no_change":             "No clear change",
        "inconclusive":          "Not enough data yet",
        "not_applicable":        "Not classified",
        "pending_observation":   "Awaiting observation window",
    }
    return labels.get(classification, "Status unknown")


# ──────────────────────────────────────────────────────────────────────────
#  Rules
# ──────────────────────────────────────────────────────────────────────────

def _rule_spend_no_sales(keywords: list[dict[str, Any]],
                         perf: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    out = []
    for kw in keywords:
        kid = kw.get("keywordId")
        p = perf.get(kid, {}) if kid else {}
        cost   = float(p.get("cost", 0) or 0)
        clicks = int(p.get("clicks", 0) or 0)
        purch  = int(p.get("purchases30d", 0) or 0)

        if cost < SPEND_NO_SALES_MIN_COST_USD:
            continue
        if clicks < SPEND_NO_SALES_MIN_CLICKS:
            continue
        if purch > 0:
            continue

        # Confidence: more spend / more clicks => more certain it is waste,
        # not just a slow-converting keyword that needs more time.
        if cost >= 20.0 or clicks >= 20:
            confidence = "high"
        else:
            confidence = "medium"

        kw_text = kw.get("keywordText", "")
        out.append({
            "suggestion_type":  "spend_no_sales",
            "campaign_id":      kw.get("campaignId"),
            "ad_group_id":      kw.get("adGroupId"),
            "keyword_id":       kid,
            "current_value": {
                "keyword_text": kw_text,
                "state":      kw.get("state"),
                "bid":        kw.get("bid"),
                "cost_30d":   round(cost, 2),
                "clicks_30d": clicks,
                "purchases_30d": 0,
                "sales_30d":  0.0,
            },
            "proposed_value": {"state": "PAUSED"},
            "reason": (
                f"Keyword '{kw_text}' spent ${cost:.2f} on {clicks} clicks in "
                f"the last 30 days with zero sales. Pausing it stops the "
                f"bleed; re-enable later once the listing or ad copy improves."
            ),
            "estimated_savings": round(cost, 2),
            "confidence":        confidence,
        })
    return out


def _rule_high_acos(keywords: list[dict[str, Any]],
                    perf: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    out = []
    for kw in keywords:
        kid = kw.get("keywordId")
        p = perf.get(kid, {}) if kid else {}
        cost  = float(p.get("cost", 0) or 0)
        sales = float(p.get("sales30d", 0) or 0)

        if cost < HIGH_ACOS_MIN_COST_USD:
            continue
        if sales <= 0:
            continue   # spend_no_sales handles zero-sales keywords
        acos = cost / sales
        if acos < HIGH_ACOS_THRESHOLD:
            continue

        current_bid = float(kw.get("bid") or 0)
        # Scale current bid by (target / actual). If actual is 70% and target 30%,
        # we bid down by 30/70 ~= 0.43x. Floor at $0.02 (Amazon minimum).
        new_bid = max(0.02, round(current_bid * (HIGH_ACOS_TARGET / acos), 2)) if current_bid > 0 else 0.02
        target_cost = sales * HIGH_ACOS_TARGET
        est_savings = max(0.0, cost - target_cost)

        # Confidence: ACOS over 100% is unambiguous (every dollar of ad spend
        # returns less than a dollar in sales). 50-100% is real waste but
        # may have margin upside on the rest of the customer journey, so
        # we mark it medium rather than high.
        confidence = "high" if acos >= 1.0 else "medium"

        kw_text = kw.get("keywordText", "")
        purch  = int(p.get("purchases30d", 0) or 0)
        clicks_h = int(p.get("clicks", 0) or 0)
        out.append({
            "suggestion_type":  "high_acos",
            "campaign_id":      kw.get("campaignId"),
            "ad_group_id":      kw.get("adGroupId"),
            "keyword_id":       kid,
            "current_value": {
                "keyword_text": kw_text,
                "bid":       current_bid,
                "acos_30d":  round(acos, 3),
                "cost_30d":  round(cost, 2),
                "sales_30d": round(sales, 2),
                "clicks_30d": clicks_h,
                "purchases_30d": purch,
            },
            "proposed_value": {
                "bid":         new_bid,
                "target_acos": HIGH_ACOS_TARGET,
            },
            "reason": (
                f"Keyword '{kw_text}' has 30-day ACOS of {acos*100:.0f}%, "
                f"above the {HIGH_ACOS_THRESHOLD*100:.0f}% threshold. "
                f"Lowering the bid from ${current_bid:.2f} to ${new_bid:.2f} "
                f"brings ACOS toward the {HIGH_ACOS_TARGET*100:.0f}% target."
            ),
            "estimated_savings": round(est_savings, 2),
            "confidence":        confidence,
        })
    return out


def _rule_bid_too_high(keywords: list[dict[str, Any]],
                       ad_groups_by_id: dict[str, dict[str, Any]],
                       perf: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    out = []
    for kw in keywords:
        bid = kw.get("bid")
        if bid is None:
            continue
        bid = float(bid)
        if bid < BID_TOO_HIGH_MIN_BID:
            continue

        ag = ad_groups_by_id.get(kw.get("adGroupId"), {})
        default_bid = ag.get("defaultBid")
        if not default_bid or float(default_bid) <= 0:
            continue
        default_bid = float(default_bid)

        ratio = bid / default_bid
        if ratio < BID_TOO_HIGH_RATIO:
            continue

        # Suggest 10% above ad group default. Stays competitive without
        # paying 2x or more for the same impression share.
        target_bid = round(default_bid * 1.1, 2)

        kid = kw.get("keywordId")
        p = perf.get(kid, {}) if kid else {}
        clicks = int(p.get("clicks", 0) or 0)
        # Estimated savings assumes lower bid keeps ~half of clicks at
        # the difference in CPC. Conservative on purpose: real CPC at the
        # new bid will be lower than current bid but higher than zero.
        est_savings = round(max(0.0, (bid - target_bid)) * clicks * 0.5, 2)

        # Confidence: bigger ratio means the overpay is more obvious. 2.5x
        # is hard to justify; 1.5-2.5x might be a deliberate top-of-funnel
        # bid by the seller.
        confidence_local = "high" if ratio >= 2.5 else "medium"

        kw_text = kw.get("keywordText", "")
        cost_b  = float(p.get("cost", 0) or 0)
        sales_b = float(p.get("sales30d", 0) or 0)
        purch_b = int(p.get("purchases30d", 0) or 0)
        out.append({
            "suggestion_type":  "bid_too_high",
            "campaign_id":      kw.get("campaignId"),
            "ad_group_id":      kw.get("adGroupId"),
            "keyword_id":       kid,
            "current_value": {
                "keyword_text":         kw_text,
                "bid":                  bid,
                "ad_group_default_bid": default_bid,
                "ratio":                round(ratio, 2),
                "clicks_30d":           clicks,
                "cost_30d":             round(cost_b, 2),
                "sales_30d":            round(sales_b, 2),
                "purchases_30d":        purch_b,
            },
            "proposed_value": {"bid": target_bid},
            "reason": (
                f"Keyword '{kw_text}' is bid at ${bid:.2f}, "
                f"{ratio:.1f}x the ad group's default of ${default_bid:.2f}. "
                f"Lowering to ${target_bid:.2f} stays competitive while ending "
                f"the overpay."
            ),
            "estimated_savings": est_savings,
            "confidence":        confidence_local,
        })
    return out


def _rule_scale_profitable(keywords: list[dict[str, Any]],
                           perf: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    out = []
    for kw in keywords:
        kid = kw.get("keywordId")
        p = perf.get(kid, {}) if kid else {}
        sales       = float(p.get("sales30d", 0) or 0)
        cost        = float(p.get("cost", 0) or 0)
        impressions = int(p.get("impressions", 0) or 0)
        purch       = int(p.get("purchases30d", 0) or 0)

        if sales < SCALE_MIN_SALES_USD or cost <= 0 or purch <= 0:
            continue
        acos = cost / sales
        if acos > SCALE_MAX_ACOS:
            continue
        if impressions > SCALE_MAX_IMPRESSIONS:
            continue

        current_bid = float(kw.get("bid") or 0)
        new_bid = round(current_bid * SCALE_BID_UPLIFT, 2) if current_bid > 0 else 0.10
        # Conservative revenue lift: 20% bid uplift -> ~20% impression
        # uplift -> ~20% sales uplift, capped at SCALE_MAX_ACOS.
        est_lift = round(sales * (SCALE_BID_UPLIFT - 1.0), 2)

        # Confidence: lower ACOS + more purchases = stronger signal that
        # demand is real and not a one-shot whale.
        confidence = "high" if (acos < 0.10 and purch >= 5) else "medium"

        kw_text = kw.get("keywordText", "")
        clicks_s = int(p.get("clicks", 0) or 0)
        out.append({
            "suggestion_type":  "scale_profitable",
            "campaign_id":      kw.get("campaignId"),
            "ad_group_id":      kw.get("adGroupId"),
            "keyword_id":       kid,
            "current_value": {
                "keyword_text":    kw_text,
                "bid":             current_bid,
                "acos_30d":        round(acos, 3),
                "cost_30d":        round(cost, 2),
                "sales_30d":       round(sales, 2),
                "clicks_30d":      clicks_s,
                "purchases_30d":   purch,
                "impressions_30d": impressions,
            },
            "proposed_value": {
                "bid":               new_bid,
                "expected_acos_max": SCALE_MAX_ACOS,
            },
            "reason": (
                f"Keyword '{kw_text}' has 30-day ACOS of {acos*100:.0f}% "
                f"on ${sales:.2f} in sales but only {impressions} impressions. "
                f"Raising the bid from ${current_bid:.2f} to ${new_bid:.2f} "
                f"buys more impressions while keeping ACOS healthy."
            ),
            "estimated_savings": est_lift,
            "confidence":        confidence,
        })
    return out


def _rule_promote_search_term(keywords: list[dict[str, Any]],
                              search_terms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Find search terms that already convert well but are not yet keywords.

    A search term is "not yet a keyword" if no row in `keywords` has the same
    text (case-insensitive, trimmed) regardless of ad group or match type.
    Adding it as exact match in the same ad group captures the volume
    directly with a higher quality score and lower CPC than the broad-match
    parent that surfaced it.
    """
    existing_keyword_texts = {
        (kw.get("keywordText") or "").strip().lower()
        for kw in keywords
    }
    existing_keyword_texts.discard("")

    # Aggregate search-term performance by (term, ad_group). Same term in
    # different ad groups gets separate suggestions because the seller may
    # want it added in only one of them.
    by_term: dict[tuple[str, Any], dict[str, Any]] = {}
    for st in search_terms:
        term_raw = (st.get("searchTerm") or "").strip()
        if not term_raw:
            continue
        if term_raw.lower() in existing_keyword_texts:
            continue
        agid = st.get("adGroupId")
        key = (term_raw.lower(), agid)
        if key not in by_term:
            by_term[key] = {
                "search_term":         term_raw,
                "ad_group_id":         agid,
                "campaign_id":         st.get("campaignId"),
                "matched_keyword_id":  st.get("keywordId"),
                "impressions":         0,
                "clicks":              0,
                "cost":                0.0,
                "purchases30d":        0,
                "sales30d":            0.0,
            }
        agg = by_term[key]
        agg["impressions"]   += int(st.get("impressions", 0) or 0)
        agg["clicks"]        += int(st.get("clicks", 0) or 0)
        agg["cost"]          += float(st.get("cost", 0) or 0)
        agg["purchases30d"]  += int(st.get("purchases30d", 0) or 0)
        agg["sales30d"]      += float(st.get("sales30d", 0) or 0)

    out = []
    for agg in by_term.values():
        if agg["sales30d"] < SEARCH_TERM_PROMOTE_MIN_SALES_USD:
            continue
        if agg["purchases30d"] < SEARCH_TERM_PROMOTE_MIN_PURCHASES:
            continue

        # Bid suggestion: their actual CPC plus 5%. If clicks were zero
        # (shouldn't happen given purchases > 0), fall back to a small floor.
        cpc = (agg["cost"] / agg["clicks"]) if agg["clicks"] else 0.50
        new_bid = round(max(0.10, cpc * 1.05), 2)

        # Conservative incremental revenue estimate: 15% of current sales.
        # Going from broad-match-via-parent to exact-match typically improves
        # quality score and impression share; tighter math comes once we
        # have post-apply tracking data (week 5).
        est_lift = round(agg["sales30d"] * 0.15, 2)

        # Confidence: bigger samples => more certain it is a real winner
        # and not a coincidence. 4+ orders + $100+ in 30 days is hard to
        # explain by chance.
        confidence = (
            "high"
            if (agg["purchases30d"] >= 4 and agg["sales30d"] >= 100.0)
            else "medium"
        )

        out.append({
            "suggestion_type":  "promote_search_term",
            "campaign_id":      agg["campaign_id"],
            "ad_group_id":      agg["ad_group_id"],
            "keyword_id":       None,
            "current_value": {
                "search_term":        agg["search_term"],
                "matched_keyword_id": agg["matched_keyword_id"],
                "sales_30d":          round(agg["sales30d"], 2),
                "purchases_30d":      agg["purchases30d"],
                "cost_30d":           round(agg["cost"], 2),
                "clicks_30d":         agg["clicks"],
                "implied_cpc":        round(cpc, 2),
            },
            "proposed_value": {
                "add_keyword": agg["search_term"],
                "match_type":  "exact",
                "bid":         new_bid,
            },
            "reason": (
                f"Search term '{agg['search_term']}' generated "
                f"${agg['sales30d']:.2f} in sales from {agg['purchases30d']} "
                f"orders over 30 days but is not yet a keyword. Adding it as "
                f"exact match at ${new_bid:.2f} captures the volume directly "
                f"with a higher quality score."
            ),
            "estimated_savings": est_lift,
            "confidence":        confidence,
        })
    return out


# ──────────────────────────────────────────────────────────────────────────
#  Per-keyword performance roll-up
# ──────────────────────────────────────────────────────────────────────────

def _aggregate_keyword_perf(search_terms: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """
    Sum impressions, clicks, cost, purchases30d, sales30d per keywordId.

    Search-term rows from Amazon's report are keyed by (search_term, keyword,
    ad_group). To know how a *keyword* performed in 30 days we sum every row
    that points at it. Keywords with no rows in the search-term report (no
    impressions in window) get nothing here; the rules treat that as
    "no signal" rather than "no sales".
    """
    perf: dict[str, dict[str, float]] = {}
    for st in search_terms:
        kid = st.get("keywordId")
        if not kid:
            continue
        if kid not in perf:
            perf[kid] = {
                "impressions":  0,
                "clicks":       0,
                "cost":         0.0,
                "purchases30d": 0,
                "sales30d":     0.0,
            }
        p = perf[kid]
        p["impressions"]  += int(st.get("impressions", 0) or 0)
        p["clicks"]       += int(st.get("clicks", 0) or 0)
        p["cost"]         += float(st.get("cost", 0) or 0)
        p["purchases30d"] += int(st.get("purchases30d", 0) or 0)
        p["sales30d"]     += float(st.get("sales30d", 0) or 0)
    return perf


# ──────────────────────────────────────────────────────────────────────────
#  End-to-end (DB-backed) entry point
# ──────────────────────────────────────────────────────────────────────────

def generate_suggestions(connection_id: int,
                         db_ctx_factory=None,
                         replace_pending: bool = True) -> list[dict[str, Any]]:
    """
    Load the latest snapshot per data_type for `connection_id`, run all rules,
    and persist results to ppc_suggestions.

    Atomicity:
        When `replace_pending=True`, the DELETE of old pending rows and the
        INSERT of new rows happen inside a single context-manager block, i.e.
        a single transaction. If the INSERT fails the rollback restores the
        prior pending list, so the dashboard never enters an empty state due
        to a partially-committed refresh.

    Batch coherence (snapshot_run_id):
        `_load_latest_snapshots` now picks the most recent COMPLETE
        snapshot_run_id (i.e. one that holds rows for every required
        data_type) and reads only that run's rows. If no complete run
        exists yet, the loader falls back to per-data_type latest reads
        for backward compatibility with rows written before the column
        existed. When the loader signals an incomplete batch (any required
        data_type is empty), `replace_pending` is silently downgraded to
        False so a half-finished fetch cannot blank out the dashboard.

    Args:
        connection_id:     amazon_connections.id row.
        db_ctx_factory:    callable returning the (cursor, placeholder)
                           context manager. Defaults to `server._db`. Tests
                           pass a fake.
        replace_pending:   if True (default), all previously pending
                           suggestions for this connection are deleted before
                           the new batch is inserted. Keeps the dashboard in
                           sync with the latest analysis. Set False if you
                           want to accumulate (rare).

    Returns:
        List of suggestion dicts as produced by `analyze`. Same content also
        in ppc_suggestions table.
    """
    if db_ctx_factory is None:
        from server import _db as db_ctx_factory   # lazy import to avoid cycle

    snapshots   = _load_latest_snapshots(connection_id, db_ctx_factory)
    suggestions = analyze(snapshots)

    # Don't blank out the dashboard from an incomplete fetch. If the most
    # recent snapshot run is missing any of campaigns / ad_groups /
    # keywords / search_terms, the rules engine can still produce
    # meaningful output for whatever exists, but the prior batch's pending
    # list is more useful to the seller than an empty board.
    incomplete = any(not snapshots.get(dt) for dt in REQUIRED_DATA_TYPES)
    if replace_pending and incomplete:
        log.warning(
            "generate_suggestions connection_id=%d found incomplete snapshot "
            "(missing one of %s); preserving prior pending rows. "
            "Re-run after the next complete fetch.",
            connection_id, list(REQUIRED_DATA_TYPES),
        )
        replace_pending = False

    # Seller memory (cycle-18 / Task 3): suppress signatures rejected in
    # the last REJECT_MEMORY_WINDOW_DAYS unless metrics changed
    # materially. Resurfaced rows carry `_memory` metadata under
    # current_value so the card view shows the explanation and the
    # ranker applies the memory-score penalty.
    rejections = _load_recent_rejections(connection_id, db_ctx_factory)
    filtered = _apply_memory_filter(suggestions, rejections)
    suggestions = filtered["persisted"]
    skipped_count = len(filtered["skipped"])

    # Approval memory (Track B 2026-05-09): boost suggestions whose
    # rule type the seller has approved >= APPROVAL_MATCH_MIN_COUNT
    # times in the last APPROVAL_MEMORY_WINDOW_DAYS. Defensive: a
    # failure here must not block the dashboard, so we wrap and fall
    # back to the un-boosted list on error.
    try:
        approvals = _load_recent_approvals(connection_id, db_ctx_factory)
        suggestions = _apply_approval_memory_boost(suggestions, approvals)
    except Exception as e:
        log.warning(
            "approval memory boost failed for connection_id=%d: %s",
            connection_id, e,
        )

    if replace_pending:
        _atomic_replace_pending(connection_id, suggestions, db_ctx_factory)
    elif suggestions:
        _persist_suggestions(connection_id, suggestions, db_ctx_factory)

    log.info(
        "generate_suggestions connection_id=%d returned=%d skipped_memory=%d "
        "types=%s incomplete=%s",
        connection_id, len(suggestions), skipped_count,
        sorted({s["suggestion_type"] for s in suggestions}),
        incomplete,
    )
    return suggestions


def _atomic_replace_pending(connection_id: int,
                            new_suggestions: list[dict[str, Any]],
                            db_ctx_factory) -> None:
    """
    Single-transaction wipe-and-replace for pending suggestions.

    Both the DELETE of existing pending rows and the INSERT of `new_suggestions`
    run within one cursor / one commit. The context manager's exception path
    rolls back, so a failure in the middle of the inserts leaves the prior
    pending list intact.
    """
    now = time.time()
    with db_ctx_factory() as (cur, ph):
        cur.execute(
            f"""
            DELETE FROM ppc_suggestions
            WHERE connection_id = {ph} AND status = 'pending'
            """,
            (connection_id,),
        )
        for s in new_suggestions:
            cur.execute(
                f"""
                INSERT INTO ppc_suggestions (
                    connection_id, campaign_id, ad_group_id, keyword_id,
                    suggestion_type, current_value, proposed_value,
                    reason, estimated_savings, confidence, status, created_at
                ) VALUES (
                    {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 'pending', {ph}
                )
                """,
                (
                    connection_id,
                    s.get("campaign_id"),
                    s.get("ad_group_id"),
                    s.get("keyword_id"),
                    s["suggestion_type"],
                    json.dumps(s.get("current_value") or {}),
                    json.dumps(s.get("proposed_value") or {}),
                    s.get("reason", ""),
                    float(s.get("estimated_savings", 0.0) or 0.0),
                    s.get("confidence", "medium"),
                    now,
                ),
            )


# ──────────────────────────────────────────────────────────────────────────
#  DB helpers
# ──────────────────────────────────────────────────────────────────────────

def _load_latest_snapshots(connection_id: int, db_ctx_factory) -> dict[str, list[dict[str, Any]]]:
    """
    Return {data_type: list[dict]} for one coherent snapshot batch.

    Two-strategy load to balance correctness with backward compatibility:

    Strategy 1 (preferred): pick the most recent snapshot_run_id that
        holds a row for every required data_type and read only that run's
        rows. This guarantees no mixing of fresh keywords with stale
        search-terms from a half-completed prior run (the bug
        snapshot_run_id was added to fix).

    Strategy 2 (fallback, legacy): if no run_id satisfies the
        completeness check (snapshot_run_id is NULL on rows written before
        the migration, or no complete run exists yet), read the latest
        single row per data_type independently. This is the historical
        behaviour and is still useful for first-time analyses where only
        partial data has been fetched. The caller decides what to do
        with an incomplete result via the REQUIRED_DATA_TYPES check in
        generate_suggestions.

    Missing data_types map to an empty list rather than KeyError so
    callers can treat partial snapshots uniformly.

    `snapshot_run_id` may be missing from the schema entirely on very old
    deployments. The query path below catches that and reverts to
    strategy 2.
    """
    out: dict[str, list[dict[str, Any]]] = {dt: [] for dt in SNAPSHOT_DATA_TYPES}

    with db_ctx_factory() as (cur, ph):
        run_id = _pick_latest_complete_run_id(cur, ph, connection_id)
        if run_id is not None:
            # Strategy 1: load one coherent run.
            cur.execute(
                f"""
                SELECT data_type, data
                FROM ppc_snapshots
                WHERE connection_id = {ph} AND snapshot_run_id = {ph}
                """,
                (connection_id, run_id),
            )
            for data_type, payload in cur.fetchall() or []:
                out[data_type] = _decode_snapshot_payload(
                    payload, connection_id, data_type,
                )
            return out

        # Strategy 2: per-data_type latest. Used for legacy data without
        # run_ids and for first-fetch states where no single run is
        # complete yet.
        for data_type in SNAPSHOT_DATA_TYPES:
            cur.execute(
                f"""
                SELECT data
                FROM ppc_snapshots
                WHERE connection_id = {ph} AND data_type = {ph}
                ORDER BY fetched_at DESC
                LIMIT 1
                """,
                (connection_id, data_type),
            )
            row = cur.fetchone()
            if row is None:
                out[data_type] = []
                continue
            out[data_type] = _decode_snapshot_payload(
                row[0], connection_id, data_type,
            )
    return out


def _pick_latest_complete_run_id(cur, ph, connection_id: int) -> str | None:
    """
    Return the snapshot_run_id of the most recent run that contains a row
    for every REQUIRED_DATA_TYPES, or None if no such run exists (or if the
    snapshot_run_id column is not present in the schema yet).

    "Most recent" is decided by MAX(fetched_at) within each run_id.
    """
    try:
        cur.execute(
            f"""
            SELECT snapshot_run_id, MAX(fetched_at) AS latest_at
            FROM ppc_snapshots
            WHERE connection_id = {ph}
              AND snapshot_run_id IS NOT NULL
              AND data_type IN ({', '.join([ph] * len(REQUIRED_DATA_TYPES))})
            GROUP BY snapshot_run_id
            HAVING COUNT(DISTINCT data_type) = {ph}
            ORDER BY latest_at DESC
            LIMIT 1
            """,
            (connection_id, *REQUIRED_DATA_TYPES, len(REQUIRED_DATA_TYPES)),
        )
        row = cur.fetchone()
    except Exception as e:
        # Likely cause: the snapshot_run_id column does not exist on this
        # database (very old deployment that never ran init_ppc_db after
        # the migration was added). Strategy 2 will still work.
        log.debug(
            "snapshot_run_id lookup failed (probably legacy schema): %s", e,
        )
        return None

    if not row or row[0] is None:
        return None
    return str(row[0])


def _decode_snapshot_payload(payload: Any, connection_id: int,
                             data_type: str) -> list[dict[str, Any]]:
    """
    Normalise the `data` column value to a list of dicts.

    Accepts:
    - bytes / bytearray  (some Postgres configs return JSONB as bytes)
    - str                (SQLite TEXT, or Postgres JSONB returned as text)
    - list / dict        (Postgres JSONB usually decodes to native Python)

    Malformed or unknown payloads log a warning and return [] so the
    rules engine sees "no signal" instead of crashing.
    """
    if payload is None:
        return []
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8", errors="replace")
    if isinstance(payload, str):
        try:
            return json.loads(payload) or []
        except (TypeError, ValueError):
            log.warning(
                "ppc_snapshots row for connection_id=%d data_type=%s "
                "could not be parsed as JSON; treating as empty",
                connection_id, data_type,
            )
            return []
    if isinstance(payload, list):
        return payload
    # Anything else (single dict, etc.) is unexpected; log and ignore.
    return []


def _delete_pending_suggestions(connection_id: int, db_ctx_factory) -> int:
    """Wipe all pending suggestions for this connection. Returns rows deleted."""
    with db_ctx_factory() as (cur, ph):
        cur.execute(
            f"""
            DELETE FROM ppc_suggestions
            WHERE connection_id = {ph} AND status = 'pending'
            """,
            (connection_id,),
        )
        deleted = cur.rowcount or 0
    return deleted


def _persist_suggestions(connection_id: int,
                         suggestions: list[dict[str, Any]],
                         db_ctx_factory) -> int:
    """
    Insert each suggestion as a 'pending' row in ppc_suggestions. Returns the
    number of rows inserted.

    Postgres JSONB and SQLite TEXT columns both accept a JSON string, so we
    always serialise current_value / proposed_value before insert.
    """
    inserted = 0
    now = time.time()
    with db_ctx_factory() as (cur, ph):
        for s in suggestions:
            cur.execute(
                f"""
                INSERT INTO ppc_suggestions (
                    connection_id, campaign_id, ad_group_id, keyword_id,
                    suggestion_type, current_value, proposed_value,
                    reason, estimated_savings, confidence, status, created_at
                ) VALUES (
                    {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 'pending', {ph}
                )
                """,
                (
                    connection_id,
                    s.get("campaign_id"),
                    s.get("ad_group_id"),
                    s.get("keyword_id"),
                    s["suggestion_type"],
                    json.dumps(s.get("current_value") or {}),
                    json.dumps(s.get("proposed_value") or {}),
                    s.get("reason", ""),
                    float(s.get("estimated_savings", 0.0) or 0.0),
                    s.get("confidence", "medium"),
                    now,
                ),
            )
            inserted += 1
    return inserted


def list_pending_suggestions(connection_id: int, db_ctx_factory=None) -> list[dict[str, Any]]:
    """
    Read pending suggestions for the dashboard. Returns rows shaped like the
    dicts `analyze` produces, with `id`, `created_at`, and `status` added.
    """
    if db_ctx_factory is None:
        from server import _db as db_ctx_factory

    out: list[dict[str, Any]] = []
    with db_ctx_factory() as (cur, ph):
        cur.execute(
            f"""
            SELECT id, campaign_id, ad_group_id, keyword_id,
                   suggestion_type, current_value, proposed_value,
                   reason, estimated_savings, confidence, status, created_at
            FROM ppc_suggestions
            WHERE connection_id = {ph} AND status = 'pending'
            ORDER BY
                CASE confidence WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                COALESCE(estimated_savings, 0) DESC,
                id ASC
            """,
            (connection_id,),
        )
        rows = cur.fetchall() or []

    for r in rows:
        cv = _maybe_load_json(r[5])
        pv = _maybe_load_json(r[6])
        out.append({
            "id":                r[0],
            "campaign_id":       r[1],
            "ad_group_id":       r[2],
            "keyword_id":        r[3],
            "suggestion_type":   r[4],
            "current_value":     cv,
            "proposed_value":    pv,
            "reason":            r[7] or "",
            "estimated_savings": float(r[8] or 0.0),
            "confidence":        r[9] or "medium",
            "status":            r[10] or "pending",
            "created_at":        float(r[11] or 0.0),
        })
    return out


def _maybe_load_json(value: Any) -> dict[str, Any]:
    """Postgres JSONB returns dict; SQLite returns JSON string. Normalise."""
    if value is None:
        return {}
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode("utf-8", errors="replace")
        except Exception:
            return {}
    if isinstance(value, str):
        try:
            return json.loads(value) or {}
        except (TypeError, ValueError):
            return {}
    if isinstance(value, dict):
        return value
    return {}


# ──────────────────────────────────────────────────────────────────────────
#  Decision outcome classification (Track B of 2026-05-09 sprint)
# ──────────────────────────────────────────────────────────────────────────
#
# Pure functions that take a baseline (captured at decision time) and an
# observation (captured later by the outcome observer) and return a
# classification + honest summary string.
#
# CRITICAL ANTI-OVERCLAIM RULE:
#   The summary MUST describe what the metrics did, never what SellerCopilot
#   did. The product cannot write to Amazon, so any change is at most
#   correlated with the decision, never caused by it. Test
#   `test_decision_outcomes.py::test_no_summary_claims_causation` enforces
#   this in CI.
#
# Classification values:
#   "metrics_moved_better"   metric of interest moved >=10% in the desired direction
#   "metrics_moved_worse"    metric of interest moved >=10% in the wrong direction
#   "no_change"              within +/-10%, no clear movement
#   "inconclusive"           insufficient data (e.g. <5 clicks observed)
#   "not_applicable"         we cannot classify (e.g. rejected without baseline)

OUTCOME_THRESHOLD_RATIO       = 0.10   # 10% relative change to count as moved
OUTCOME_MIN_CLICKS_OBSERVED   = 5      # below this, classify inconclusive
OUTCOME_DEFAULT_LOOKBACK_DAYS = 14     # observation window

# Forbidden phrasings — used by tests and a runtime guard. Adding new
# language here triggers the anti-overclaim test to catch any future
# regression. Keep these in lower case for case-insensitive matching.
OUTCOME_CAUSATION_FORBIDDEN_PHRASES: tuple[str, ...] = (
    "our decision worked",
    "our recommendation worked",
    "we improved",
    "we caused",
    "sellercopilot improved",
    "sellercopilot increased",
    "sellercopilot decreased",
    "as a result of our",
    "due to our",
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Coerce to float without raising. Returns default on bad input."""
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return default


def _safe_acos(spend: float, sales: float) -> float | None:
    """ACOS = spend / sales. None when sales == 0 (undefined)."""
    if sales <= 0:
        return None
    return spend / sales


def _direction_for(suggestion_type: str) -> dict[str, str]:
    """
    Per rule type, which baseline metric do we expect to move and in
    which direction if the suggestion plays out as the engine predicted.

    Returns a dict whose keys are metric field names in baseline/observed
    and whose values are 'down' / 'up' / 'stable'.
    """
    if suggestion_type == "spend_no_sales":
        # We expect cost to drop near zero post-pause.
        return {"cost_30d": "down"}
    if suggestion_type in ("high_acos", "bid_too_high"):
        # We expect cost down (less waste) and ACOS down.
        return {"cost_30d": "down", "acos": "down"}
    if suggestion_type == "scale_profitable":
        # We expect impressions and sales up. ACOS may rise but should
        # stay within target band. Cost is allowed to rise.
        return {"impressions_30d": "up", "sales_30d": "up"}
    if suggestion_type == "promote_search_term":
        # New keyword: we expect sales attribution to appear at the
        # keyword level after promotion. Watching sales_30d up.
        return {"sales_30d": "up"}
    return {}


def _summarise_metric_change(field: str, old: float, new: float) -> str:
    """
    Human-readable description of one metric's movement. Always describes
    the metric itself, never claims causation. Currency fields use $.
    """
    money_fields = {"cost_30d", "sales_30d"}
    pct_fields   = {"acos"}

    if old == 0 and new == 0:
        return f"{field} stayed at 0"

    if field in money_fields:
        return f"{field} moved from ${old:.0f} to ${new:.0f}"
    if field in pct_fields:
        # Already a ratio in baseline; show as percentage points
        return f"{field} moved from {old * 100:.0f}% to {new * 100:.0f}%"
    return f"{field} moved from {old:.0f} to {new:.0f}"


def _relative_change(old: float, new: float) -> float | None:
    """
    Relative change. None when old == 0 (undefined) and new != 0.
    Sign convention: positive when new > old.
    """
    if old == 0:
        return None
    return (new - old) / abs(old)


def classify_outcome(
    suggestion_type: str,
    decision: str,
    baseline: dict[str, Any] | None,
    observed: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Compare baseline to observed and return a classification + summary.

    Args:
        suggestion_type: one of the 5 rule types from analyze().
        decision:        'approved' or 'rejected'.
        baseline:        dict from `_approval_baseline` (or current_value
                         at rejection time, when we have one). May contain
                         cost_30d, sales_30d, acos, clicks_30d, etc.
        observed:        dict from a re-fetch of the same metric after the
                         observation window.

    Returns:
        {
          "classification": str,    # one of OUTCOME_* values above
          "summary":        str,    # honest one-sentence description
          "metrics_delta":  dict,   # per-field old/new/relative
          "copy_status":    str,    # 'observed' or 'projection_only'
        }
    """
    base = dict(baseline or {})
    obs  = dict(observed or {})

    # Rejected decisions: we do not currently capture a rejection
    # baseline, so we cannot honestly classify what would have happened.
    # Codex flagged this as Track B follow-up — for now, mark as N/A.
    if decision == "rejected":
        return {
            "classification": "not_applicable",
            "summary":        "Rejected suggestions are not classified yet (rejection baseline not captured).",
            "metrics_delta":  {},
            "copy_status":    "projection_only",
        }

    # Inconclusive: too few clicks observed to draw any signal.
    obs_clicks = _safe_float(obs.get("clicks_30d"))
    if obs_clicks < OUTCOME_MIN_CLICKS_OBSERVED:
        return {
            "classification": "inconclusive",
            "summary":        f"Not enough activity yet to classify (observed {int(obs_clicks)} clicks, threshold {OUTCOME_MIN_CLICKS_OBSERVED}).",
            "metrics_delta":  {},
            "copy_status":    "observed",
        }

    direction_map = _direction_for(suggestion_type)
    if not direction_map:
        return {
            "classification": "not_applicable",
            "summary":        "Outcome classification is not defined for this suggestion type yet.",
            "metrics_delta":  {},
            "copy_status":    "projection_only",
        }

    deltas: dict[str, dict[str, Any]] = {}
    favorable_count   = 0
    unfavorable_count = 0
    no_change_count   = 0
    summary_parts: list[str] = []

    for field, expected_dir in direction_map.items():
        if field == "acos":
            old_v = _safe_acos(_safe_float(base.get("cost_30d")), _safe_float(base.get("sales_30d")))
            new_v = _safe_acos(_safe_float(obs.get("cost_30d")),  _safe_float(obs.get("sales_30d")))
            if old_v is None or new_v is None:
                deltas[field] = {"old": old_v, "new": new_v, "relative": None}
                continue
            rel = _relative_change(old_v, new_v)
            deltas[field] = {"old": old_v, "new": new_v, "relative": rel}
            summary_parts.append(_summarise_metric_change(field, old_v, new_v))
        else:
            old_v = _safe_float(base.get(field))
            new_v = _safe_float(obs.get(field))
            rel = _relative_change(old_v, new_v)
            deltas[field] = {"old": old_v, "new": new_v, "relative": rel}
            summary_parts.append(_summarise_metric_change(field, old_v, new_v))

        if rel is None:
            continue

        # Classify per-field
        if abs(rel) < OUTCOME_THRESHOLD_RATIO:
            no_change_count += 1
            continue

        # Direction matters: 'down' is favorable when rel < 0.
        if expected_dir == "down":
            if rel <= -OUTCOME_THRESHOLD_RATIO:
                favorable_count += 1
            elif rel >= OUTCOME_THRESHOLD_RATIO:
                unfavorable_count += 1
        elif expected_dir == "up":
            if rel >= OUTCOME_THRESHOLD_RATIO:
                favorable_count += 1
            elif rel <= -OUTCOME_THRESHOLD_RATIO:
                unfavorable_count += 1

    # Aggregate classification
    if favorable_count > 0 and unfavorable_count == 0:
        classification = "metrics_moved_better"
    elif unfavorable_count > 0 and favorable_count == 0:
        classification = "metrics_moved_worse"
    elif favorable_count == 0 and unfavorable_count == 0:
        classification = "no_change"
    else:
        # Mixed: at least one field moved each way. Be honest, not loud.
        classification = "no_change"

    summary = ". ".join(summary_parts) if summary_parts else "No measurable change."
    if not summary.endswith("."):
        summary += "."

    # Anti-overclaim guard: a runtime safety net. The CI test is the
    # primary defence; this is a belt-and-braces fallback.
    lowered = summary.lower()
    for forbidden in OUTCOME_CAUSATION_FORBIDDEN_PHRASES:
        if forbidden in lowered:
            summary = "Metrics moved (full breakdown in audit log)."
            break

    return {
        "classification": classification,
        "summary":        summary,
        "metrics_delta":  deltas,
        "copy_status":    "observed",
    }
