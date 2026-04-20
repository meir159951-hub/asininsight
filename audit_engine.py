"""
audit_engine.py

Integrator for the Phase A brain. This module is the only entry point
other code (CLI, app.html bridge, future API) should need. It pulls
together:

    * patterns.py        - 15 cross-metric diagnostic patterns
    * roi_calculator.py  - per-pattern monthly $ impact ranges
    * signals.py         - standalone health signals (Buy Box, margin,
                           trends, suppression risk)

and produces a structured, seller-friendly audit for a single ASIN.

PUBLIC API
----------
    run_full_audit(asin_data: dict) -> dict
        Runs the full pipeline on one product dict.

    run_store_audit(store_data: dict) -> dict
        Convenience wrapper that audits every product in a store JSON.

OUTPUT SHAPE
------------
See ``run_full_audit`` for the exact dict returned. The shape is
designed to be consumed directly by the frontend without reshaping,
while staying readable when printed as JSON.

HONESTY NOTE
------------
Severity and priority here are ordinal, not absolute. Score penalties
and tier thresholds are heuristic defaults; they do not come from a
proprietary benchmark dataset. Every dollar figure exposes the inputs
it relied on via the underlying ROIImpact.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from patterns import CROSS_METRIC_PATTERNS
from roi_calculator import ROIImpact, calculate_roi
from signals import StandaloneSignal, detect_all_signals


# ---------------------------------------------------------------------------
# Paths & CLI defaults
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR / "sample_data" / "demo_store.json"
OUTPUT_DIR = BASE_DIR / "output"


# ---------------------------------------------------------------------------
# Severity, score, and priority tuning
# ---------------------------------------------------------------------------

# Unified priority scale (also used for score penalties).
SEVERITY_RANK: dict[str, float] = {
    "critical": 10.0,
    "high":     7.0,
    "medium":   4.0,
    "low":      2.0,
    "ok":       0.0,
}

SCORE_PENALTY: dict[str, int] = {
    "critical": 15,
    "high":      8,
    "medium":    4,
    "low":       2,
}

# Patterns whose severity is intrinsic (independent of the ROI number).
# For everything else, severity is derived from ROI magnitude.
PATTERN_SEVERITY_OVERRIDES: dict[str, str] = {
    "unit_economics_loss":        "critical",
    "restock_urgency":            "critical",
    "reviews_killing_conversion": "high",
    "buy_box_loss_healthy_stock": "high",
    "buy_box_war_on_ranked":      "high",
    "inventory_trap":             "high",
    "weak_listing_foundation":    "high",
    "overbid_weak_listing":       "high",
    "discontinuation_candidate":  "high",
}

# Short action-verb titles in seller language (one per pattern).
PATTERN_ACTION_TITLES: dict[str, str] = {
    "listing_over_promise":        "Fix the listing-vs-reality gap",
    "hidden_winner":               "Win more search clicks",
    "ppc_waste_on_organic":        "Reclaim ad spend on keywords you already own",
    "buy_box_loss_healthy_stock":  "Investigate Buy Box loss",
    "underinvested_winner":        "Scale a proven converter",
    "reviews_killing_conversion":  "Repair the product rating",
    "unit_economics_loss":         "Stop the per-unit bleed",
    "inventory_trap":              "Free dead inventory",
    "restock_urgency":             "Replenish before stockout",
    "ppc_addiction":               "Build organic rank to reduce ad dependency",
    "buy_box_war_on_ranked":       "Counter the Buy Box price war",
    "weak_listing_foundation":     "Relaunch the listing",
    "review_starvation":           "Grow reviews to unlock further scale",
    "overbid_weak_listing":        "Trim ad bids until the listing is fixed",
    "discontinuation_candidate":   "Sunset this ASIN",
}

SIGNAL_ACTION_TITLES: dict[str, str] = {
    "buy_box":            "Recover Buy Box share",
    "suppression_risk":   "Rule out listing suppression",
    "true_profit_margin": "Protect unit profit",
    "trend_sessions":     "Investigate the traffic drop",
    "trend_conversion":   "Investigate the conversion drop",
    "trend_acos":         "Investigate the rising ACoS",
    "trend_rank":         "Investigate the rank drop",
}


# ---------------------------------------------------------------------------
# Data-quality contract
#
# These two lists define what the CSV must contain for a full audit
# and what it may contain for additional signals. The audit runs on
# partial data, but the report explicitly names what was missing so
# the seller never mistakes a thin audit for a thorough one.
# ---------------------------------------------------------------------------

REQUIRED_CSV_FIELDS: list[str] = [
    "asin", "title",
    "sessions_30d", "conversion_rate", "ctr",
    "price", "cogs", "fba_fees",
    "buy_box_pct", "acos", "ad_spend_30d",
    "rating", "review_count",
    "days_of_cover", "organic_rank_top_keyword",
]

OPTIONAL_CSV_FIELDS: list[str] = [
    "category", "units_ordered_30d",
    "sessions_30d_prev", "conversion_rate_prev",
    "acos_prev", "organic_rank_prev",
]


# ---------------------------------------------------------------------------
# Anti-double-counting
#
# Several patterns target the same underlying lever (e.g. multiple
# patterns all move conversion rate). When aggregating monthly impact
# we group findings by their driver and keep only the largest ROI per
# driver, then sum across distinct drivers. The naive sum is also
# surfaced so callers can see the difference.
# ---------------------------------------------------------------------------

PATTERN_DRIVER: dict[str, str] = {
    "listing_over_promise":        "cr_uplift",
    "reviews_killing_conversion":  "cr_uplift",
    "review_starvation":           "cr_uplift",
    "hidden_winner":               "traffic_uplift",
    "underinvested_winner":        "traffic_uplift",
    "ppc_waste_on_organic":        "ppc_savings",
    "ppc_addiction":               "ppc_savings",
    "overbid_weak_listing":        "ppc_savings",
    "inventory_trap":              "ppc_savings",
    "buy_box_loss_healthy_stock":  "buy_box_recovery",
    "buy_box_war_on_ranked":       "buy_box_recovery",
    "unit_economics_loss":         "unit_economics",
    "restock_urgency":             "revenue_protection",
    "weak_listing_foundation":     "listing_relaunch",
    "discontinuation_candidate":   "sunset_savings",
}


# ---------------------------------------------------------------------------
# Explainability
#
# For every pattern, this map lists the metrics whose current value
# caused the match. audit_engine attaches these values under
# `triggered_by` on each pattern finding so the UI can answer
# "why did this fire?" without re-reading the product dict.
# ---------------------------------------------------------------------------

PATTERN_TRIGGER_FIELDS: dict[str, list[str]] = {
    "listing_over_promise":        ["ctr", "conversion_rate"],
    "hidden_winner":               ["ctr", "conversion_rate"],
    "ppc_waste_on_organic":        ["acos", "organic_rank_top_keyword"],
    "buy_box_loss_healthy_stock":  ["buy_box_pct", "days_of_cover"],
    "underinvested_winner":        ["conversion_rate", "sessions_30d"],
    "reviews_killing_conversion":  ["rating", "sessions_30d"],
    "unit_economics_loss":         ["price", "cogs", "fba_fees", "acos"],
    "inventory_trap":              ["days_of_cover", "conversion_rate"],
    "restock_urgency":             ["days_of_cover", "conversion_rate"],
    "ppc_addiction":               ["ad_spend_30d", "organic_rank_top_keyword"],
    "buy_box_war_on_ranked":       ["organic_rank_top_keyword", "buy_box_pct"],
    "weak_listing_foundation":     ["sessions_30d", "organic_rank_top_keyword", "review_count"],
    "review_starvation":           ["conversion_rate", "review_count"],
    "overbid_weak_listing":        ["acos", "conversion_rate", "rating"],
    "discontinuation_candidate":   ["conversion_rate", "rating", "review_count"],
}


# ---------------------------------------------------------------------------
# Commercial impact category per pattern
#
# Used to split the aggregate so the first commercial number a seller
# sees separates revenue gain from cost savings from loss prevention.
# Summing these categories is apples-to-apples; summing across them
# mixes three different commercial stories and is exposed only as a
# bounded upper estimate.
# ---------------------------------------------------------------------------

PATTERN_IMPACT_CATEGORY: dict[str, str] = {
    "listing_over_promise":        "profit_gain",
    "hidden_winner":               "profit_gain",
    "ppc_waste_on_organic":        "cost_savings",
    "buy_box_loss_healthy_stock":  "profit_gain",
    "underinvested_winner":        "profit_gain",
    "reviews_killing_conversion":  "profit_gain",
    "unit_economics_loss":         "loss_prevention",
    "inventory_trap":              "cost_savings",
    "restock_urgency":             "loss_prevention",
    "ppc_addiction":               "cost_savings",
    "buy_box_war_on_ranked":       "profit_gain",
    "weak_listing_foundation":     "profit_gain",
    "review_starvation":           "profit_gain",
    "overbid_weak_listing":        "cost_savings",
    "discontinuation_candidate":   "cost_savings",
}


# ---------------------------------------------------------------------------
# Per-pattern assumptions: which entries in MODEL_ASSUMPTIONS shaped
# each pattern's ROI number. Attached to every finding so a reader can
# trace the number back to its stated assumption.
# ---------------------------------------------------------------------------

PATTERN_ASSUMPTIONS: dict[str, list[str]] = {
    "listing_over_promise":        ["cr_lift_range", "impact_type"],
    "hidden_winner":               ["cr_lift_range", "impact_type"],
    "ppc_waste_on_organic":        ["ppc_savings_range", "impact_type"],
    "buy_box_loss_healthy_stock":  ["buy_box_recovery", "impact_type"],
    "underinvested_winner":        ["traffic_scaling", "impact_type"],
    "reviews_killing_conversion":  ["cr_lift_range", "impact_type"],
    "unit_economics_loss":         ["impact_type"],
    "inventory_trap":              ["ppc_savings_range", "impact_type"],
    "restock_urgency":             ["impact_type"],
    "ppc_addiction":               ["ppc_savings_range", "impact_type"],
    "buy_box_war_on_ranked":       ["buy_box_recovery", "impact_type"],
    "weak_listing_foundation":     ["relaunch_cap", "impact_type"],
    "review_starvation":           ["cr_lift_range", "impact_type"],
    "overbid_weak_listing":        ["ppc_savings_range", "impact_type"],
    "discontinuation_candidate":   ["ppc_savings_range", "impact_type"],
}


# ---------------------------------------------------------------------------
# Discontinuation dominance: when discontinuation_candidate fires,
# improvement patterns that target the same ASIN are suppressed from
# the priority ranking and action plan so the audit never recommends
# "fix" and "sunset" simultaneously. Suppressed patterns stay in the
# patterns list with an explicit `suppressed_by` marker.
# ---------------------------------------------------------------------------

IMPROVEMENT_DRIVERS: set[str] = {
    "cr_uplift",
    "traffic_uplift",
    "buy_box_recovery",
    "listing_relaunch",
    "ppc_savings",
    "revenue_protection",
}


# ---------------------------------------------------------------------------
# Metric interpretation bands and display formatting.
#
# Used to enrich triggered_by so each value carries its formatted
# display AND a plain-language read ("weak", "healthy", "strong")
# drawn from the same thresholds the patterns use to fire.
# ---------------------------------------------------------------------------

def _fmt_pct_frac(v: float) -> str:   return f"{v * 100:.1f}%"   # 0.006 -> "0.6%"
def _fmt_pct_whole(v: float) -> str:  return f"{v:.0f}%"         # 85 -> "85%"
def _fmt_rating(v: float) -> str:     return f"{v:.1f}"
def _fmt_count(v: float) -> str:      return f"{v:,.0f}"
def _fmt_rank(v: float) -> str:       return f"#{v:.0f}"
def _fmt_money_field(v: float) -> str:return f"${v:,.2f}"

FIELD_FORMATTERS: dict[str, Any] = {
    "ctr":                        _fmt_pct_frac,
    "conversion_rate":            _fmt_pct_frac,
    "acos":                       _fmt_pct_frac,
    "buy_box_pct":                _fmt_pct_whole,
    "rating":                     _fmt_rating,
    "review_count":               _fmt_count,
    "sessions_30d":               _fmt_count,
    "units_ordered_30d":          _fmt_count,
    "days_of_cover":              _fmt_count,
    "organic_rank_top_keyword":   _fmt_rank,
    "price":                      _fmt_money_field,
    "cogs":                       _fmt_money_field,
    "fba_fees":                   _fmt_money_field,
    "ad_spend_30d":               _fmt_money_field,
}

# bands = ordered list of (strict_upper_bound, label). Last entry
# captures "and above". Thresholds match the levels patterns use to fire.
FIELD_BANDS: dict[str, list[tuple[float, str]]] = {
    "ctr":                       [(0.003, "weak"),    (0.005, "healthy"), (float("inf"), "strong")],
    "conversion_rate":           [(0.02,  "weak"),    (0.04,  "healthy"), (float("inf"), "strong")],
    "acos":                      [(0.25,  "strong"),  (0.35,  "healthy"), (0.50, "concern"), (float("inf"), "critical")],
    "buy_box_pct":               [(50,    "critical"),(70,    "weak"),    (90,   "soft"),    (float("inf"), "healthy")],
    "rating":                    [(4.0,   "risk"),    (4.3,   "acceptable"), (float("inf"), "strong")],
    "review_count":              [(25,    "scarce"),  (100,   "growing"), (float("inf"), "established")],
    "days_of_cover":             [(14,    "low"),     (90,    "healthy"), (float("inf"), "trapped")],
    "organic_rank_top_keyword":  [(11,    "top"),     (21,    "page1"),   (51,   "weak"),    (float("inf"), "buried")],
}


# ---------------------------------------------------------------------------
# Model assumptions exposed in every audit output. Documents what the
# ROI numbers represent without requiring the reader to open the
# calculator source.
# ---------------------------------------------------------------------------

MODEL_ASSUMPTIONS: dict[str, str] = {
    "cr_lift_range":        "0.3-1.5 absolute percentage points",
    "ppc_savings_range":    "15-50% of current ad spend",
    "traffic_scaling":      "50-150% session growth modelled at 25% target ACoS",
    "buy_box_recovery":     "30-70% of diverted units in the first 1-2 months",
    "relaunch_cap":         "weak_listing_foundation hard-capped at $2,500/mo",
    "trend_window":         "30-day current vs 30-day prior (optional *_prev fields)",
    "impact_type":          "monthly profit contribution, not revenue",
    "aggregation":          "deduplicated by driver; naive sum also exposed for comparison",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _pattern_severity(pattern_name: str, roi: ROIImpact) -> str:
    """
    Resolve a pattern's severity. Hard overrides win; otherwise derive
    from the max ROI magnitude so a $4,000/mo opportunity is not
    lumped with a $150/mo one.
    """
    if pattern_name in PATTERN_SEVERITY_OVERRIDES:
        return PATTERN_SEVERITY_OVERRIDES[pattern_name]
    max_impact = roi.max_impact if roi.max_impact is not None else 0.0
    if max_impact >= 1000:
        return "high"
    if max_impact >= 300:
        return "medium"
    return "low"


def _priority_score_pattern(severity: str, roi: ROIImpact) -> float:
    """
    0-10 priority score for a pattern finding, matched in scale to
    StandaloneSignal.impact_score so the two can be ranked together.
    """
    score = SEVERITY_RANK.get(severity, 0.0)
    if roi.max_impact is not None:
        if roi.max_impact >= 2000:
            score += 2.0
        elif roi.max_impact >= 1000:
            score += 1.0
    if roi.confidence == "low":
        score -= 1.0
    elif roi.confidence == "high":
        score += 0.5
    return max(0.0, min(score, 10.0))


def _fmt_money(amount: float | None) -> str:
    return "n/a" if amount is None else f"${amount:,.0f}"


def _fmt_range(lo: float | None, hi: float | None) -> str:
    if lo is None and hi is None:
        return "n/a"
    if lo is None or hi is None or abs((hi or 0) - (lo or 0)) < 1:
        return _fmt_money(hi if hi is not None else lo)
    return f"{_fmt_money(lo)}-{_fmt_money(hi)}/mo"


def _compute_score(patterns: list[dict], signals: list[dict]) -> int:
    """Simple 100-based health score. Penalties sum across all findings."""
    score = 100
    for p in patterns:
        score -= SCORE_PENALTY.get(p["severity"], 2)
    for s in signals:
        score -= SCORE_PENALTY.get(s["severity"], 2)
    return max(0, min(score, 100))


def _readiness_label(score: int) -> str:
    if score >= 85:
        return "Strong"
    if score >= 65:
        return "Watch"
    if score >= 45:
        return "At Risk"
    return "Critical"


def _data_quality(asin_data: dict[str, Any]) -> dict[str, Any]:
    """
    Report which required / optional CSV fields are present. A thin
    audit must never masquerade as a thorough one, so the result is
    surfaced in every output under the ``data_quality`` key.
    """
    def _missing(key: str) -> bool:
        v = asin_data.get(key)
        return v is None or v == ""

    missing_required = [f for f in REQUIRED_CSV_FIELDS if _missing(f)]
    missing_optional = [f for f in OPTIONAL_CSV_FIELDS if _missing(f)]
    total_req = len(REQUIRED_CSV_FIELDS)
    present_req = total_req - len(missing_required)
    quality_score = round((present_req / total_req) * 100) if total_req else 0
    if quality_score >= 90:
        label = "full"
    elif quality_score >= 60:
        label = "partial"
    else:
        label = "minimal"
    return {
        "label": label,
        "quality_score": quality_score,
        "required_total": total_req,
        "required_present": present_req,
        "missing_required_fields": missing_required,
        "missing_optional_fields": missing_optional,
    }


def _triggered_by(pattern_name: str, asin_data: dict[str, Any]) -> dict[str, Any]:
    """
    Snapshot the metric values that caused a pattern to match.
    Values are returned verbatim (no rounding or scaling) so the
    reader can sanity-check the match.
    """
    fields = PATTERN_TRIGGER_FIELDS.get(pattern_name, [])
    return {f: asin_data.get(f) for f in fields}


def _deduped_aggregate(
    patterns: list[dict[str, Any]],
) -> tuple[float | None, float | None, dict[str, float]]:
    """
    Prevent ROI double-counting by grouping patterns under a shared
    driver and keeping only the largest impact per driver.

    Only considers patterns that are active (not suppressed by
    discontinuation dominance and not grouped under a sibling winner).

    Returns
    -------
    (agg_min, agg_max, per_driver_max)
        agg_* are None when no active pattern has a numeric ROI.
    """
    by_driver_max: dict[str, float] = {}
    by_driver_min: dict[str, float] = {}
    for p in patterns:
        if p.get("suppressed_by") or p.get("grouped_under"):
            continue
        driver = PATTERN_DRIVER.get(p["name"], p["name"])
        roi = p["roi"]
        hi = roi.get("max_monthly")
        if hi is None:
            continue
        if driver not in by_driver_max or hi > by_driver_max[driver]:
            by_driver_max[driver] = hi
            by_driver_min[driver] = roi.get("min_monthly") or 0.0
    if not by_driver_max:
        return None, None, {}
    agg_min = sum(by_driver_min.values())
    agg_max = sum(by_driver_max.values())
    return agg_min, agg_max, by_driver_max


# ---------------------------------------------------------------------------
# Input sanitation
# ---------------------------------------------------------------------------

_PCT_FRAC_FIELDS = {"ctr", "conversion_rate", "acos"}  # stored as 0-1
_PCT_WHOLE_FIELDS = {"buy_box_pct"}                    # stored as 0-100
_RATING_FIELDS = {"rating"}


def _sanitize_inputs(asin_data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """
    Clamp obviously out-of-bounds values so a corrupt row in the CSV
    cannot drive a misleading audit. Returns a shallow copy plus a
    list of human-readable notes describing each clamp applied.
    """
    out = dict(asin_data)
    notes: list[str] = []

    def _maybe_float(key: str) -> float | None:
        v = out.get(key)
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    # Fractional percentages: keep within [0, 1].
    for key in _PCT_FRAC_FIELDS:
        v = _maybe_float(key)
        if v is None:
            continue
        # ACoS of 200% is a real scenario; we only clamp at the extreme
        # (values >10 are almost certainly unit errors).
        upper = 10.0 if key == "acos" else 1.0
        if v < 0:
            notes.append(f"{key} was {v:g}; clamped to 0.")
            out[key] = 0.0
        elif v > upper:
            notes.append(f"{key} was {v:g}; clamped to {upper:g}.")
            out[key] = upper

    # Whole-number percentages: keep within [0, 100].
    for key in _PCT_WHOLE_FIELDS:
        v = _maybe_float(key)
        if v is None:
            continue
        if v < 0:
            notes.append(f"{key} was {v:g}; clamped to 0.")
            out[key] = 0.0
        elif v > 100:
            notes.append(f"{key} was {v:g}; clamped to 100.")
            out[key] = 100.0

    # Ratings: keep within [0, 5].
    for key in _RATING_FIELDS:
        v = _maybe_float(key)
        if v is None:
            continue
        if v < 0:
            notes.append(f"{key} was {v:g}; clamped to 0.")
            out[key] = 0.0
        elif v > 5:
            notes.append(f"{key} was {v:g}; clamped to 5.")
            out[key] = 5.0

    return out, notes


def _consistency_warnings(asin_data: dict[str, Any]) -> list[str]:
    """
    Cross-field sanity. These are warnings, not errors - the audit
    still runs on the data as supplied, but the report surfaces any
    contradictions the seller should resolve at the source.
    """
    def _num(k: str) -> float | None:
        v = asin_data.get(k)
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    warnings: list[str] = []

    sessions = _num("sessions_30d")
    units = _num("units_ordered_30d")
    cr = _num("conversion_rate")
    if units is not None and sessions is not None and units > sessions:
        warnings.append(
            f"units_ordered_30d ({units:g}) exceeds sessions_30d "
            f"({sessions:g}); check your export."
        )
    if (
        sessions is not None and cr is not None and units is not None
        and sessions > 0 and units > 0
    ):
        implied = sessions * cr
        if implied > 0 and (units / implied > 3 or implied / units > 3):
            warnings.append(
                f"units_ordered_30d ({units:g}) and sessions*CR "
                f"({implied:.0f}) disagree by more than 3x."
            )

    ad_spend = _num("ad_spend_30d")
    ad_sales = _num("ad_sales_30d")
    if ad_spend is not None and ad_spend > 0 and ad_sales is not None and ad_sales == 0:
        warnings.append(
            f"ad_spend_30d=${ad_spend:g} with ad_sales_30d=$0; "
            f"either the spend is wasted or ad_sales is missing."
        )

    price = _num("price")
    cogs = _num("cogs")
    fba = _num("fba_fees")
    if price is not None and cogs is not None and cogs > price:
        warnings.append(
            f"cogs (${cogs:g}) exceeds price (${price:g}); each sale "
            f"loses money before fees and PPC."
        )
    if price is not None and fba is not None and fba > price:
        warnings.append(
            f"fba_fees (${fba:g}) exceeds price (${price:g}); the "
            f"fee line alone exceeds what the buyer pays."
        )

    return warnings


def _is_low_volume(asin_data: dict[str, Any]) -> bool:
    """
    True when the sample size makes pattern detection statistically
    unreliable. Used to downgrade every pattern's confidence by one
    level and append a note to the summary.
    """
    def _num(k: str) -> float | None:
        v = asin_data.get(k)
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    sessions = _num("sessions_30d")
    units = _num("units_ordered_30d")
    if sessions is not None and sessions < 200:
        return True
    if units is not None and units < 10:
        return True
    return False


def _interpret_metric(field: str, value: Any) -> dict[str, Any]:
    """
    Turn a raw field value into {value, display, read} so triggered_by
    can be shown to a seller without manual interpretation.
    """
    if value is None or value == "":
        return {"value": None, "display": "n/a", "read": "missing"}
    try:
        num = float(value)
    except (TypeError, ValueError):
        return {"value": value, "display": str(value), "read": "unknown"}

    fmt = FIELD_FORMATTERS.get(field)
    display = fmt(num) if fmt else str(num)

    bands = FIELD_BANDS.get(field)
    if not bands:
        return {"value": num, "display": display, "read": "raw"}

    read = bands[-1][1]
    for threshold, label in bands:
        if num < threshold:
            read = label
            break
    return {"value": num, "display": display, "read": read}


def _enriched_triggered_by(
    pattern_name: str, asin_data: dict[str, Any]
) -> dict[str, Any]:
    """Formatted + interpreted version of the raw _triggered_by."""
    fields = PATTERN_TRIGGER_FIELDS.get(pattern_name, [])
    return {f: _interpret_metric(f, asin_data.get(f)) for f in fields}


# ---------------------------------------------------------------------------
# Confidence justification
#
# Every actionable finding carries a `confidence_reason` alongside its
# confidence label so a reader can tell why the label was assigned. For
# patterns the reason is synthesised from the triggered metric reads;
# for signals it is a curated line that names the underlying evidence.
# ---------------------------------------------------------------------------

_SIGNAL_CONFIDENCE_REASONS: dict[str, str] = {
    "buy_box": (
        "Buy Box share is below the 90% healthy threshold; the gap "
        "between current share and 100% is the proportion of clicks "
        "converting for a competitor on the listing."
    ),
    "suppression_risk": (
        "Traffic pattern is inconsistent with a normally-served "
        "listing. This is a hypothesis from indirect indicators; "
        "confirmation requires a Seller Central check."
    ),
    "true_profit_margin": (
        "Margin is computed directly from price, COGS, FBA fees, and "
        "ACoS in the uploaded row - no projection or modelling."
    ),
    "trend_sessions": (
        "Current vs prior 30-day session counts show a drop larger "
        "than typical month-to-month noise."
    ),
    "trend_conversion": (
        "Conversion rate dropped meaningfully versus the prior 30 "
        "days; not explained by the small-sample range."
    ),
    "trend_acos": (
        "ACoS climbed materially versus the prior 30 days, outside "
        "typical bid-adjustment drift."
    ),
    "trend_rank": (
        "Organic rank on the main keyword fell more than 10 "
        "positions in 30 days - a meaningful structural move."
    ),
}


def _confidence_reason_pattern(finding: dict[str, Any]) -> str:
    """
    Synthesise a one-line justification from the pattern's triggered
    metrics and their interpreted reads.
    """
    enriched = finding.get("triggered_by_interpreted", {})
    parts: list[str] = []
    for field, view in enriched.items():
        if not isinstance(view, dict) or view.get("value") is None:
            continue
        pretty = field.replace("_30d", " (30d)").replace("_", " ")
        parts.append(f"{pretty} is {view['display']} ({view['read']})")
    if not parts:
        return "Pattern matched on the fields available in the row."
    return "Matched because " + "; ".join(parts) + "."


def _confidence_reason_signal(finding: dict[str, Any]) -> str:
    return _SIGNAL_CONFIDENCE_REASONS.get(
        finding.get("name", ""),
        finding.get("explanation", "")[:180] or "Signal matched on its own evidence.",
    )


# ---------------------------------------------------------------------------
# Core problem + sanity
# ---------------------------------------------------------------------------

def _build_core_problem(ranked: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    The single dominant issue the seller should act on first. Always
    matches priority_blockers[0] and action_plan[0]; adds a short
    `why_this_one` so the reader understands why it outranked the rest.
    """
    if not ranked:
        return None
    top = ranked[0]
    why = _explain_core_selection(ranked)
    return {
        "name":                 top["name"],
        "source":                top["source"],
        "severity":              top["severity"],
        "driver":                top.get("driver"),
        "action_title":          top["action_title"],
        "headline":              top["headline"],
        "monthly_impact_range":  top.get("monthly_impact_range"),
        "priority_score":        top["priority_score"],
        "why_this_one":          why,
    }


def _explain_core_selection(ranked: list[dict[str, Any]]) -> str:
    top = ranked[0]
    if len(ranked) == 1:
        return (
            f"Only one active finding ({top['severity']} severity); "
            f"it is the focus by default."
        )
    gap = top["priority_score"] - ranked[1]["priority_score"]
    if gap >= 2:
        return (
            f"Dominant: priority score {top['priority_score']:.1f} "
            f"vs next-highest {ranked[1]['priority_score']:.1f}."
        )
    return (
        f"Selected on severity ({top['severity']}) and priority score "
        f"{top['priority_score']:.1f}; next finding scores "
        f"{ranked[1]['priority_score']:.1f}."
    )


def _derive_narrative_theme(core: dict[str, Any] | None) -> str | None:
    """
    One-word theme for the seller-facing headline of the audit, drawn
    from the core problem's driver or signal name.
    """
    if core is None:
        return None
    driver = core.get("driver")
    theme_map = {
        "cr_uplift":          "conversion",
        "traffic_uplift":     "traffic",
        "ppc_savings":        "ads",
        "buy_box_recovery":   "pricing",
        "unit_economics":     "unit economics",
        "revenue_protection": "inventory",
        "listing_relaunch":   "listing",
        "sunset_savings":     "portfolio",
    }
    if driver and driver in theme_map:
        return theme_map[driver]
    # Signals
    name = core.get("name", "")
    if name.startswith("trend_"):
        return "trend"
    signal_theme = {
        "buy_box":            "pricing",
        "suppression_risk":   "visibility",
        "true_profit_margin": "unit economics",
    }
    return signal_theme.get(name)


def _sanity_notes(
    asin_data: dict[str, Any],
    patterns: list[dict[str, Any]],
    summary: dict[str, Any],
) -> list[str]:
    """
    Final realism pass. Emits notes only when a number could feel
    exaggerated to an experienced seller relative to the ASIN's
    current size or data quality.
    """
    notes: list[str] = []

    def _n(k: str) -> float | None:
        v = asin_data.get(k)
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    sessions = _n("sessions_30d")
    units = _n("units_ordered_30d")
    price = _n("price")
    cr = _n("conversion_rate")

    current_revenue: float | None = None
    if units is not None and price is not None:
        current_revenue = units * price
    elif sessions is not None and cr is not None and price is not None:
        current_revenue = sessions * cr * price

    if current_revenue is not None and current_revenue > 0:
        combined_max = (
            summary.get("aggregate_by_category", {}).get("combined_upper_bound_max")
        )
        if combined_max is not None and combined_max > current_revenue * 2:
            notes.append(
                f"Combined upper-bound opportunity (${combined_max:,.0f}/mo) "
                f"exceeds current monthly revenue (${current_revenue:,.0f}); "
                f"treat the combined number as an upper bound, not a "
                f"realistic single-month gain."
            )

        for p in patterns:
            if p.get("suppressed_by") or p.get("grouped_under"):
                continue
            roi_max = p["roi"].get("max_monthly")
            if roi_max is not None and roi_max > current_revenue * 1.5:
                notes.append(
                    f"{p['name']} projects ${roi_max:,.0f}/mo at the top "
                    f"of its range, which is >1.5x current monthly "
                    f"revenue; verify inputs before acting on the high end."
                )

    if summary.get("low_volume_note"):
        notes.append(
            "Low data volume reduces reliability; treat impact ranges as "
            "directional, not precise."
        )

    if asin_data.get("asin") is None and asin_data.get("ASIN") is None:
        notes.append("No ASIN in the uploaded row; results cannot be matched back to the listing.")

    return notes


# ---------------------------------------------------------------------------
# Post-processing: suppression, grouping, severity, confidence
# ---------------------------------------------------------------------------

def _apply_discontinuation_dominance(
    patterns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    When discontinuation_candidate fires, every improvement pattern
    (cr_uplift / traffic_uplift / buy_box_recovery / ppc_savings /
    listing_relaunch / revenue_protection) is tagged as suppressed so
    the audit never tells the seller to "fix and sunset" at once.
    """
    disc_fired = any(p["name"] == "discontinuation_candidate" for p in patterns)
    if not disc_fired:
        return patterns
    for p in patterns:
        if p["name"] == "discontinuation_candidate":
            continue
        driver = p.get("driver")
        if driver in IMPROVEMENT_DRIVERS or p["name"] == "unit_economics_loss":
            p["suppressed_by"] = "discontinuation_candidate"
    return patterns


def _apply_sibling_grouping(
    patterns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Patterns that share a driver (e.g. listing_over_promise and
    reviews_killing_conversion both under cr_uplift) must not occupy
    separate top-findings slots. Within each driver, keep the
    highest-ROI one as the active finding; mark the rest with
    `grouped_under`. Suppressed patterns are skipped.

    Tie-break for "highest ROI" on equal max_impact:
    (1) severity rank descending, (2) name alphabetical.
    """
    active = [p for p in patterns if not p.get("suppressed_by")]

    by_driver: dict[str, list[dict[str, Any]]] = {}
    for p in active:
        by_driver.setdefault(p["driver"], []).append(p)

    for driver, group in by_driver.items():
        if len(group) <= 1:
            continue

        def _rank_key(item: dict[str, Any]) -> tuple[float, float, str]:
            roi_max = float(item["roi"].get("max_monthly") or 0.0)
            sev_rank = SEVERITY_RANK.get(item.get("severity", ""), 0.0)
            return (-roi_max, -sev_rank, item["name"])

        group_sorted = sorted(group, key=_rank_key)
        winner = group_sorted[0]
        for loser in group_sorted[1:]:
            loser["grouped_under"] = winner["name"]
    return patterns


def _apply_conditional_severity(
    patterns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Override severity on patterns where the intrinsic "critical" tag
    would otherwise over-weight a tiny absolute dollar impact.
    Specifically: restock_urgency and unit_economics_loss drop to
    "medium" when their max monthly impact is below $500. This keeps
    the priority layer honest on niche / low-velocity ASINs.
    """
    SMALL_IMPACT_FLOOR = 500.0
    volatile = {"restock_urgency", "unit_economics_loss"}
    for p in patterns:
        if p["name"] not in volatile:
            continue
        max_impact = p["roi"].get("max_monthly")
        if max_impact is not None and max_impact < SMALL_IMPACT_FLOOR:
            p["severity"] = "medium"
    return patterns


def _downgrade_confidence(
    patterns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Drop every pattern's confidence one level when the audit is
    running on a statistically thin sample. ROI numbers stay but the
    confidence tag tells the seller to treat them as directional.
    """
    step_down = {"high": "medium", "medium": "low", "low": "low"}
    for p in patterns:
        p["confidence"] = step_down.get(p.get("confidence", "low"), "low")
        p["roi"]["roi_confidence"] = step_down.get(
            p["roi"].get("roi_confidence", "low"), "low"
        )
    return patterns


def _recompute_priorities(
    patterns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Priority scores depend on severity and confidence; both can change
    during post-processing, so recompute after all mutations. Patterns
    that are suppressed or grouped get priority 0 so they fall out of
    priority_blockers and action_plan naturally.
    """
    for p in patterns:
        if p.get("suppressed_by") or p.get("grouped_under"):
            p["_priority"] = 0.0
            continue
        roi_stub = ROIImpact(
            pattern_name=p["name"],
            min_impact=p["roi"].get("min_monthly"),
            max_impact=p["roi"].get("max_monthly"),
            monthly_units=p["roi"].get("monthly_units"),
            confidence=p["roi"].get("roi_confidence", "medium"),
            explanation="",
        )
        p["_priority"] = _priority_score_pattern(p["severity"], roi_stub)
    return patterns


def _split_aggregate(
    patterns: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Break the deduped aggregate into three commercially distinct
    buckets so the seller never sees revenue gain, cost savings, and
    loss prevention summed as one headline number.
    """
    buckets: dict[str, dict[str, dict[str, float]]] = {
        "profit_gain":     {},
        "cost_savings":    {},
        "loss_prevention": {},
    }
    for p in patterns:
        if p.get("suppressed_by") or p.get("grouped_under"):
            continue
        hi = p["roi"].get("max_monthly")
        if hi is None:
            continue
        category = PATTERN_IMPACT_CATEGORY.get(p["name"], "profit_gain")
        driver = p.get("driver") or p["name"]
        cell = buckets[category].setdefault(driver, {"min": 0.0, "max": 0.0})
        if hi > cell["max"]:
            cell["max"] = hi
            cell["min"] = p["roi"].get("min_monthly") or 0.0

    def _bucket_totals(bucket: dict[str, dict[str, float]]) -> dict[str, Any]:
        if not bucket:
            return {"min": None, "max": None, "display": "n/a"}
        lo = sum(v["min"] for v in bucket.values())
        hi = sum(v["max"] for v in bucket.values())
        return {"min": lo, "max": hi, "display": _fmt_range(lo, hi)}

    totals = {
        "profit_gain":     _bucket_totals(buckets["profit_gain"]),
        "cost_savings":    _bucket_totals(buckets["cost_savings"]),
        "loss_prevention": _bucket_totals(buckets["loss_prevention"]),
    }
    combined_min = sum(
        t["min"] for t in totals.values() if t["min"] is not None
    ) or None
    combined_max = sum(
        t["max"] for t in totals.values() if t["max"] is not None
    ) or None
    return {
        "by_category":           totals,
        "combined_upper_bound_min": combined_min,
        "combined_upper_bound_max": combined_max,
        "combined_upper_bound_display": _fmt_range(combined_min, combined_max),
        "note": (
            "Profit gain, cost savings, and loss prevention are three "
            "distinct stories. combined_upper_bound_* is the sum across "
            "categories and is an upper bound, not a guaranteed total."
        ),
    }


# ---------------------------------------------------------------------------
# Stage builders
# ---------------------------------------------------------------------------

def _build_pattern_findings(asin_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Run every cross-metric pattern and, for each match, compute ROI."""
    findings: list[dict[str, Any]] = []
    for pattern in CROSS_METRIC_PATTERNS:
        try:
            fired = bool(pattern.conditions(asin_data))
        except Exception:
            # A buggy pattern must not take down the audit.
            fired = False
        if not fired:
            continue

        roi = calculate_roi({"name": pattern.name}, asin_data)
        severity = _pattern_severity(pattern.name, roi)
        assumption_keys = PATTERN_ASSUMPTIONS.get(pattern.name, ["impact_type"])
        finding = {
            "source":         "pattern",
            "name":           pattern.name,
            "impact_type":    pattern.impact_type,
            "impact_category":PATTERN_IMPACT_CATEGORY.get(pattern.name, "profit_gain"),
            "driver":         PATTERN_DRIVER.get(pattern.name, pattern.name),
            "severity":       severity,
            "confidence":     pattern.confidence,
            "description":    pattern.description,
            # Raw values preserved for backward compatibility; the
            # enriched version carries display + band read.
            "triggered_by":              _triggered_by(pattern.name, asin_data),
            "triggered_by_interpreted":  _enriched_triggered_by(pattern.name, asin_data),
            "assumptions_applied":       assumption_keys,
            "action_title":              PATTERN_ACTION_TITLES.get(
                pattern.name, pattern.name.replace("_", " ").title()
            ),
            # Post-processing markers, defaulted to None.
            "suppressed_by":  None,
            "grouped_under":  None,
            "roi": {
                "min_monthly":    roi.min_impact,
                "max_monthly":    roi.max_impact,
                "monthly_units":  roi.monthly_units,
                "roi_confidence": roi.confidence,
                "explanation":    roi.explanation,
                "range_display":  _fmt_range(roi.min_impact, roi.max_impact),
            },
            "_priority": _priority_score_pattern(severity, roi),
        }
        finding["confidence_reason"] = _confidence_reason_pattern(finding)
        findings.append(finding)
    return findings


def _build_signal_findings(asin_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Run standalone signals and drop the ``ok`` ones."""
    findings: list[dict[str, Any]] = []
    for signal in detect_all_signals(asin_data):
        if signal.severity == "ok":
            continue
        finding = {
            "source":       "signal",
            "name":         signal.name,
            "severity":     signal.severity,
            "impact_score": signal.impact_score,
            "explanation":  signal.explanation,
            "action_title": SIGNAL_ACTION_TITLES.get(
                signal.name, signal.name.replace("_", " ").title()
            ),
            "_priority":    float(signal.impact_score),
        }
        finding["confidence_reason"] = _confidence_reason_signal(finding)
        findings.append(finding)
    return findings


def _build_priority_ranking(
    patterns: list[dict[str, Any]],
    signals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Sort active findings into a unified ranking. Patterns that are
    suppressed (by discontinuation) or grouped (sibling with same
    driver) are excluded so the blocker list never shows redundant
    or contradictory entries.

    Tie-breakers (in order):
        1. priority score        (descending)
        2. severity rank         (descending)
        3. ROI max for patterns,
           impact_score for signals (descending) - this prevents
           patterns from systematically out-ranking signals in ties
        4. name                  (alphabetical, for total determinism)

    The chain guarantees byte-identical output across runs.
    """
    def _key(f: dict[str, Any]) -> tuple[float, float, float, str]:
        severity_weight = SEVERITY_RANK.get(f.get("severity", ""), 0.0)
        if f["source"] == "pattern":
            tie_value = float(f.get("roi", {}).get("max_monthly") or 0.0) / 100.0
        else:
            tie_value = float(f.get("impact_score") or 0.0)
        return (-f["_priority"], -severity_weight, -tie_value, f.get("name", ""))

    active_patterns = [
        p for p in patterns
        if not p.get("suppressed_by") and not p.get("grouped_under")
    ]
    combined = [*active_patterns, *signals]
    combined.sort(key=_key)

    ranked: list[dict[str, Any]] = []
    for idx, f in enumerate(combined, start=1):
        if f["source"] == "pattern":
            headline = f["description"].split(".")[0].strip() + "."
            impact_range = f["roi"]["range_display"]
        else:
            headline = f["explanation"]
            impact_range = None

        ranked.append({
            "rank":                 idx,
            "source":               f["source"],
            "name":                 f["name"],
            "severity":             f["severity"],
            "driver":               f.get("driver"),
            "action_title":         f["action_title"],
            "headline":             headline,
            "monthly_impact_range": impact_range,
            "priority_score":       round(f["_priority"], 2),
        })
    return ranked


def _build_action_plan(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Turn the top priority blockers into a numbered, do-this-first
    plan in seller language - deduping by driver so the top 3 steps
    always target 3 distinct commercial levers.

    A signal without a driver is treated as its own lever and is
    always admissible regardless of any pattern driver seen before.
    """
    seen_drivers: set[str] = set()
    plan: list[dict[str, Any]] = []
    for item in ranked:
        driver = item.get("driver")
        if item["source"] == "pattern" and driver:
            if driver in seen_drivers:
                continue
            seen_drivers.add(driver)
        plan.append({
            "step": len(plan) + 1,
            "title": item["action_title"],
            "why": item["headline"],
            "estimated_impact": item.get("monthly_impact_range") or "see signal above",
            "severity": item["severity"],
        })
        if len(plan) >= 3:
            break
    return plan


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def run_full_audit(asin_data: dict[str, Any]) -> dict[str, Any]:
    """
    Run the full ASIN audit pipeline.

    Parameters
    ----------
    asin_data:
        One product dict, e.g. a single row from the uploaded CSV.
        Partial data is safe: every detector degrades gracefully when
        an input is missing.

    Returns
    -------
    dict
        Structured audit with this shape::

            {
              "asin": ...,
              "title": ...,
              "category": ...,
              "run_at": "<iso timestamp>",
              "summary": {
                "score": 0-100,
                "readiness": "Strong|Watch|At Risk|Critical",
                "patterns_triggered": int,
                "signals_raised": int,
                "total_findings": int,
                "aggregate_impact_min": float | None,   # sum of pattern mins
                "aggregate_impact_max": float | None,   # sum of pattern maxes
                "biggest_single_opportunity": float | None,
              },
              "patterns": [ ... pattern findings ... ],
              "signals":  [ ... signal findings  ... ],
              "priority_blockers": [ ... ranked list ... ],
              "action_plan":       [ top-3 steps ],
            }
    """
    # ---- 1. Sanitize the raw input row. -------------------------------
    sanitized, clamp_notes = _sanitize_inputs(asin_data)

    # ---- 2. Data quality + consistency. -------------------------------
    quality = _data_quality(sanitized)
    quality["clamp_notes"] = clamp_notes
    quality["consistency_warnings"] = _consistency_warnings(sanitized)
    low_volume = _is_low_volume(sanitized)
    quality["low_volume_flag"] = low_volume

    # ---- 3. Build raw findings on the sanitized row. ------------------
    patterns = _build_pattern_findings(sanitized)
    signals  = _build_signal_findings(sanitized)

    # ---- 4. Post-processing (discontinuation dominance, sibling
    #         grouping, conditional severity, low-volume downgrade). ---
    patterns = _apply_discontinuation_dominance(patterns)
    patterns = _apply_sibling_grouping(patterns)
    patterns = _apply_conditional_severity(patterns)
    if low_volume:
        patterns = _downgrade_confidence(patterns)
    patterns = _recompute_priorities(patterns)

    # ---- 5. Unified ranking and action plan on active findings.
    #         Ranking is capped at top-3 so the seller sees a short,
    #         scan-in-10-seconds list. Core problem is blockers[0].
    ranked_full = _build_priority_ranking(patterns, signals)
    ranked = ranked_full[:3]
    # Re-number ranks 1..N so slot == position in the truncated list.
    for idx, blk in enumerate(ranked, start=1):
        blk["rank"] = idx
    action_plan = _build_action_plan(ranked)
    core_problem = _build_core_problem(ranked)
    narrative_theme = _derive_narrative_theme(core_problem)

    # ---- 6. Naive sum (transparency only; may double-count). ---------
    raw_mins = [
        p["roi"]["min_monthly"] for p in patterns
        if p["roi"]["min_monthly"] is not None
        and not p.get("suppressed_by") and not p.get("grouped_under")
    ]
    raw_maxes = [
        p["roi"]["max_monthly"] for p in patterns
        if p["roi"]["max_monthly"] is not None
        and not p.get("suppressed_by") and not p.get("grouped_under")
    ]
    naive_sum_min = sum(raw_mins) if raw_mins else None
    naive_sum_max = sum(raw_maxes) if raw_maxes else None

    # ---- 7. Primary aggregate (deduped by driver). -------------------
    agg_min, agg_max, per_driver_max = _deduped_aggregate(patterns)
    biggest = max(raw_maxes) if raw_maxes else None

    # ---- 8. Aggregate split by commercial category. ------------------
    aggregate_by_category = _split_aggregate(patterns)

    # ---- 9. Score. ----------------------------------------------------
    #          Suppressed / grouped patterns do not penalize the score
    #          (they are already represented by their dominant sibling).
    score_patterns = [
        p for p in patterns
        if not p.get("suppressed_by") and not p.get("grouped_under")
    ]
    score = _compute_score(score_patterns, signals)

    # ---- 10. Counts for the summary. ---------------------------------
    active_patterns_count = len(score_patterns)

    # ---- 11. Strip the private _priority key before returning. -------
    for p in patterns:
        p.pop("_priority", None)
    for s in signals:
        s.pop("_priority", None)

    # ---- 12. Summary wrapper. ----------------------------------------
    summary = {
        "score":               score,
        "readiness":           _readiness_label(score),
        # Core problem: single source of truth. Matches blockers[0].
        "core_problem":        core_problem,
        "narrative_theme":     narrative_theme,
        "patterns_triggered":  len(patterns),
        "patterns_active":     active_patterns_count,
        "patterns_suppressed": sum(1 for p in patterns if p.get("suppressed_by")),
        "patterns_grouped":    sum(1 for p in patterns if p.get("grouped_under")),
        "signals_raised":      len(signals),
        "total_findings":      len(patterns) + len(signals),
        # Primary aggregate (deduped by driver) - kept for backward compat.
        "aggregate_impact_min":     agg_min,
        "aggregate_impact_max":     agg_max,
        "aggregate_impact_display": _fmt_range(agg_min, agg_max),
        "aggregate_by_driver":      per_driver_max,
        # New: split aggregate so profit gain, cost savings, and loss
        # prevention are not summed into one misleading headline.
        "aggregate_by_category":    aggregate_by_category,
        "primary_display_key":      "aggregate_by_category",
        # Retained for transparency; callers should not display these.
        "naive_sum_impact_min":     naive_sum_min,
        "naive_sum_impact_max":     naive_sum_max,
        "biggest_single_opportunity": biggest,
        "caveat": (
            "aggregate_by_category splits profit gain, cost savings, "
            "and loss prevention - three different commercial stories. "
            "aggregate_impact_* retains the deduped-by-driver number "
            "for backward compatibility. naive_sum_* is exposed for "
            "transparency only and must not be shown to sellers."
        ),
    }
    if low_volume:
        summary["low_volume_note"] = (
            "Sample size is thin (sessions < 200 or units < 10); all "
            "pattern confidences have been downgraded one level."
        )

    # Final realism pass: surface only notes that would materially
    # affect how a seller reads the numbers (exaggerated ROI vs
    # current size, thin sample, unidentifiable row).
    sanity_notes = _sanity_notes(sanitized, patterns, summary)
    summary["sanity_notes"] = sanity_notes

    return {
        "asin":     sanitized.get("asin") or sanitized.get("ASIN"),
        "title":    sanitized.get("title"),
        "category": sanitized.get("category"),
        "run_at":   datetime.now().isoformat(timespec="seconds"),
        "summary":             summary,
        "data_quality":        quality,
        "assumptions_used":    MODEL_ASSUMPTIONS,
        "patterns":            patterns,
        "signals":             signals,
        "priority_blockers":   ranked,
        "action_plan":         action_plan,
    }


def run_store_audit(store_data: dict[str, Any]) -> dict[str, Any]:
    """Run ``run_full_audit`` against every product in a store JSON."""
    products = store_data.get("products", []) or []
    audits = [run_full_audit(p) for p in products]
    audits.sort(key=lambda a: a["summary"]["score"])
    return {
        "store_name":   store_data.get("store_name"),
        "marketplace":  store_data.get("marketplace"),
        "seller_type":  store_data.get("seller_type"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "audits":       audits,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run ASINsight audit on a store JSON file."
    )
    parser.add_argument(
        "--input", type=Path, default=DEFAULT_INPUT,
        help="Path to a store JSON file (default: sample_data/demo_store.json).",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Optional path to write the JSON result. Prints to stdout otherwise.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    with args.input.open("r", encoding="utf-8") as handle:
        store = json.load(handle)
    result = run_store_audit(store)
    payload = json.dumps(result, indent=2, default=str)

    if args.output:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(f"Audit written to {args.output}")
    else:
        print(payload)


if __name__ == "__main__":
    main()
