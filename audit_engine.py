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

    Returns
    -------
    (agg_min, agg_max, per_driver_max)
        agg_* are None when no pattern has a numeric ROI.
    """
    by_driver_max: dict[str, float] = {}
    by_driver_min: dict[str, float] = {}
    for p in patterns:
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
        findings.append({
            "source": "pattern",
            "name": pattern.name,
            "impact_type": pattern.impact_type,
            "driver": PATTERN_DRIVER.get(pattern.name, pattern.name),
            "severity": severity,
            "confidence": pattern.confidence,
            "description": pattern.description,
            "triggered_by": _triggered_by(pattern.name, asin_data),
            "action_title": PATTERN_ACTION_TITLES.get(
                pattern.name, pattern.name.replace("_", " ").title()
            ),
            "roi": {
                "min_monthly": roi.min_impact,
                "max_monthly": roi.max_impact,
                "monthly_units": roi.monthly_units,
                "roi_confidence": roi.confidence,
                "explanation": roi.explanation,
                "range_display": _fmt_range(roi.min_impact, roi.max_impact),
            },
            "_priority": _priority_score_pattern(severity, roi),
        })
    return findings


def _build_signal_findings(asin_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Run standalone signals and drop the ``ok`` ones."""
    findings: list[dict[str, Any]] = []
    for signal in detect_all_signals(asin_data):
        if signal.severity == "ok":
            continue
        findings.append({
            "source": "signal",
            "name": signal.name,
            "severity": signal.severity,
            "impact_score": signal.impact_score,
            "explanation": signal.explanation,
            "action_title": SIGNAL_ACTION_TITLES.get(
                signal.name, signal.name.replace("_", " ").title()
            ),
            "_priority": float(signal.impact_score),
        })
    return findings


def _build_priority_ranking(
    patterns: list[dict[str, Any]],
    signals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Sort everything into a unified ranking. Tie-breakers (in order):
        1. priority score (descending)
        2. severity rank   (descending)
        3. pattern ROI max (descending; signals contribute 0)
        4. name            (alphabetical, for total determinism)

    The tie-breaker chain guarantees byte-identical output for a
    given input across runs and machines.
    """
    def _key(f: dict[str, Any]) -> tuple[float, float, float, str]:
        severity_weight = SEVERITY_RANK.get(f.get("severity", ""), 0.0)
        roi_max = 0.0
        if f["source"] == "pattern":
            roi_max = float(f.get("roi", {}).get("max_monthly") or 0.0)
        return (-f["_priority"], -severity_weight, -roi_max, f.get("name", ""))

    combined = [*patterns, *signals]
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
            "rank": idx,
            "source": f["source"],
            "name": f["name"],
            "severity": f["severity"],
            "action_title": f["action_title"],
            "headline": headline,
            "monthly_impact_range": impact_range,
            "priority_score": round(f["_priority"], 2),
        })
    return ranked


def _build_action_plan(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Turn the top-3 priority blockers into a numbered, do-this-first
    plan in seller language.
    """
    plan: list[dict[str, Any]] = []
    for step_num, item in enumerate(ranked[:3], start=1):
        plan.append({
            "step": step_num,
            "title": item["action_title"],
            "why": item["headline"],
            "estimated_impact": item.get("monthly_impact_range") or "see signal above",
            "severity": item["severity"],
        })
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
    patterns = _build_pattern_findings(asin_data)
    signals  = _build_signal_findings(asin_data)
    ranked   = _build_priority_ranking(patterns, signals)
    action_plan = _build_action_plan(ranked)

    # Naive sum across pattern ROIs (transparency only; may double-count).
    raw_mins = [p["roi"]["min_monthly"] for p in patterns if p["roi"]["min_monthly"] is not None]
    raw_maxes = [p["roi"]["max_monthly"] for p in patterns if p["roi"]["max_monthly"] is not None]
    naive_sum_min = sum(raw_mins) if raw_mins else None
    naive_sum_max = sum(raw_maxes) if raw_maxes else None

    # Preferred aggregate: deduped by driver (no double-counting).
    agg_min, agg_max, per_driver_max = _deduped_aggregate(patterns)
    biggest = max(raw_maxes) if raw_maxes else None

    score = _compute_score(patterns, signals)
    quality = _data_quality(asin_data)

    # Strip the private _priority key before returning.
    for p in patterns:
        p.pop("_priority", None)
    for s in signals:
        s.pop("_priority", None)

    return {
        "asin":     asin_data.get("asin") or asin_data.get("ASIN"),
        "title":    asin_data.get("title"),
        "category": asin_data.get("category"),
        "run_at":   datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "score":              score,
            "readiness":          _readiness_label(score),
            "patterns_triggered": len(patterns),
            "signals_raised":     len(signals),
            "total_findings":     len(patterns) + len(signals),
            # Primary (deduped by driver): the number we lead with.
            "aggregate_impact_min":     agg_min,
            "aggregate_impact_max":     agg_max,
            "aggregate_impact_display": _fmt_range(agg_min, agg_max),
            "aggregate_by_driver":      per_driver_max,
            # Naive sum retained for transparency only.
            "naive_sum_impact_min":     naive_sum_min,
            "naive_sum_impact_max":     naive_sum_max,
            "biggest_single_opportunity": biggest,
            "caveat": (
                "aggregate_impact_* deduplicates overlapping ROI by "
                "driver (e.g. multiple CR-lift patterns count once). "
                "naive_sum_* is exposed only to show the delta."
            ),
        },
        "data_quality":       quality,
        "assumptions_used":   MODEL_ASSUMPTIONS,
        "patterns":           patterns,
        "signals":            signals,
        "priority_blockers":  ranked,
        "action_plan":        action_plan,
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
