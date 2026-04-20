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
            "severity": severity,
            "confidence": pattern.confidence,
            "description": pattern.description,
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
    Sort everything into a unified ranking by priority score (desc),
    then return a lean record per entry suitable for the priority
    panel in the UI.
    """
    combined = [*patterns, *signals]
    combined.sort(key=lambda f: f["_priority"], reverse=True)

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

    # Aggregate dollar view across pattern ROIs.
    mins = [p["roi"]["min_monthly"] for p in patterns if p["roi"]["min_monthly"] is not None]
    maxes = [p["roi"]["max_monthly"] for p in patterns if p["roi"]["max_monthly"] is not None]
    aggregate_min = sum(mins) if mins else None
    aggregate_max = sum(maxes) if maxes else None
    biggest = max(maxes) if maxes else None

    score = _compute_score(patterns, signals)

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
            "score": score,
            "readiness": _readiness_label(score),
            "patterns_triggered": len(patterns),
            "signals_raised":     len(signals),
            "total_findings":     len(patterns) + len(signals),
            "aggregate_impact_min": aggregate_min,
            "aggregate_impact_max": aggregate_max,
            "aggregate_impact_display": _fmt_range(aggregate_min, aggregate_max),
            "biggest_single_opportunity": biggest,
            "caveat": (
                "Pattern impacts may overlap; the aggregate is an "
                "upper bound, not a strict sum of recoverable profit."
            ),
        },
        "patterns":          patterns,
        "signals":           signals,
        "priority_blockers": ranked,
        "action_plan":       action_plan,
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
