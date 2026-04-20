"""
roi_calculator.py

Transforms a pattern match and the matching ASIN data into an estimated
monthly financial impact range with seller-friendly wording.

Used downstream by audit_engine.py to attach a dollar value to every
cross-metric finding surfaced by patterns.py.

HONESTY NOTE
------------
Impact estimates are model-based projections under typical execution
assumptions. They are not historical averages and not guarantees. Every
result exposes the inputs it relied on, a confidence level, and a
seller-facing explanation so the user can sanity-check the math before
acting on a number.

STEP 1 SCAFFOLD
---------------
This file currently provides the data model, field helpers, and the
dispatch plumbing. Per-pattern formulas are wired in Step 2. Until a
formula is registered for a pattern, calculate_roi returns a neutral
placeholder so audit_engine.py can render the finding without breaking.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ROIImpact:
    """
    Monthly financial impact produced for a single pattern match.

    Attributes
    ----------
    pattern_name:
        Matches ``CrossMetricPattern.name`` in patterns.py.
    min_impact:
        Conservative lower bound of the expected monthly dollar impact.
        ``None`` when the required inputs were not supplied.
    max_impact:
        Plausible upper bound under typical execution.
    monthly_units:
        Units sold per 30 days used in the calculation. Either the
        seller-provided ``units_ordered_30d`` or an estimate from
        ``sessions_30d * conversion_rate``. ``None`` when neither is
        available.
    confidence:
        ``"high"`` | ``"medium"`` | ``"low"``. Reflects how complete
        the inputs were and how leveraged the projection assumptions
        are.
    explanation:
        Seller-friendly wording describing what the range represents
        and which inputs it was derived from.
    """

    pattern_name: str
    min_impact: float | None
    max_impact: float | None
    monthly_units: float | None
    confidence: str
    explanation: str


# ---------------------------------------------------------------------------
# Field-access helpers (safe for partial CSVs)
# ---------------------------------------------------------------------------

def _num(product: dict[str, Any], key: str) -> float | None:
    """Return a numeric field as a float, or None if missing / invalid."""
    value = product.get(key)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Shared calculation helpers
#
# These are the building blocks that per-pattern formulas in Step 2 will
# compose. Keeping them here lets every calculator use the same contract
# for margin, unit volume, and post-PPC profit.
# ---------------------------------------------------------------------------

def _margin_per_unit(product: dict[str, Any]) -> float | None:
    """
    Contribution margin per unit after COGS and FBA fees, before PPC.
    Returns None if price, cogs, or fba_fees is missing.
    """
    price = _num(product, "price")
    cogs = _num(product, "cogs")
    fba = _num(product, "fba_fees")
    if price is None or cogs is None or fba is None:
        return None
    return price - cogs - fba


def _monthly_units(product: dict[str, Any]) -> float | None:
    """
    Units sold in the last 30 days.

    Preference order:
    1. Seller-provided ``units_ordered_30d``.
    2. Estimate from ``sessions_30d * conversion_rate``.
    """
    direct = _num(product, "units_ordered_30d")
    if direct is not None:
        return direct
    sessions = _num(product, "sessions_30d")
    cr = _num(product, "conversion_rate")
    if sessions is not None and cr is not None:
        return sessions * cr
    return None


def _per_unit_profit_after_ppc(product: dict[str, Any]) -> float | None:
    """
    Contribution per unit after COGS, FBA fees, and PPC attribution at
    the current ACoS. Negative means each sale is losing money.
    """
    margin = _margin_per_unit(product)
    price = _num(product, "price")
    acos = _num(product, "acos")
    if margin is None or price is None or acos is None:
        return None
    return margin - (acos * price)


# ---------------------------------------------------------------------------
# Insufficient-data fallback
# ---------------------------------------------------------------------------

def _insufficient(pattern_name: str, missing: list[str]) -> ROIImpact:
    """
    Build a consistent ROIImpact when required inputs are missing. The
    finding remains visible, but its dollar range is None and its
    confidence is "low" so the UI can dim or annotate it.
    """
    missing_text = ", ".join(missing) if missing else "required fields"
    return ROIImpact(
        pattern_name=pattern_name,
        min_impact=None,
        max_impact=None,
        monthly_units=None,
        confidence="low",
        explanation=(
            f"Dollar impact not computed: missing {missing_text}. "
            f"Add these columns to the CSV for a quantified estimate."
        ),
    )


# ---------------------------------------------------------------------------
# Per-pattern calculators (Batch 1: patterns 1-8)
#
# Each calculator:
#   - accepts the full product dict
#   - returns an ROIImpact with min/max in USD/month
#   - degrades to _insufficient(...) when required inputs are missing
#
# All assumptions below are deliberately conservative. The upper bound
# represents "typical execution under common conditions", not a
# best-case outcome.
# ---------------------------------------------------------------------------

def _roi_listing_over_promise(product: dict[str, Any]) -> ROIImpact:
    sessions = _num(product, "sessions_30d")
    cr = _num(product, "conversion_rate")
    margin = _margin_per_unit(product)

    missing = []
    if sessions is None:
        missing.append("sessions_30d")
    if cr is None:
        missing.append("conversion_rate")
    if margin is None:
        missing.append("price/cogs/fba_fees")
    if missing:
        return _insufficient("listing_over_promise", missing)

    # Conservative CR lift: +0.5 to +1.5 absolute percentage points.
    lift_lo, lift_hi = 0.005, 0.015
    lo = sessions * lift_lo * margin
    hi = sessions * lift_hi * margin
    return ROIImpact(
        pattern_name="listing_over_promise",
        min_impact=lo,
        max_impact=hi,
        monthly_units=sessions * cr,
        confidence="medium",
        explanation=(
            f"Closing the click-vs-conversion gap on ~{sessions:,.0f} "
            f"monthly sessions (a typical 0.5-1.5 point CR lift at "
            f"${margin:.2f} contribution/unit) is projected to add "
            f"${lo:,.0f}-${hi:,.0f} per month."
        ),
    )


def _roi_hidden_winner(product: dict[str, Any]) -> ROIImpact:
    sessions = _num(product, "sessions_30d")
    ctr = _num(product, "ctr")
    cr = _num(product, "conversion_rate")
    margin = _margin_per_unit(product)

    missing = []
    if sessions is None:
        missing.append("sessions_30d")
    if ctr is None or ctr <= 0:
        missing.append("ctr")
    if cr is None:
        missing.append("conversion_rate")
    if margin is None:
        missing.append("price/cogs/fba_fees")
    if missing:
        return _insufficient("hidden_winner", missing)

    # Back out impressions from sessions / CTR, then model a CTR lift.
    impressions = sessions / ctr
    ctr_lift_lo, ctr_lift_hi = 0.002, 0.005   # +0.2 to +0.5 absolute
    extra_sessions_lo = impressions * ctr_lift_lo
    extra_sessions_hi = impressions * ctr_lift_hi
    lo = extra_sessions_lo * cr * margin
    hi = extra_sessions_hi * cr * margin
    return ROIImpact(
        pattern_name="hidden_winner",
        min_impact=lo,
        max_impact=hi,
        monthly_units=sessions * cr,
        confidence="medium",
        explanation=(
            f"Raising CTR by 0.2-0.5 points on ~{impressions:,.0f} "
            f"monthly impressions, at the existing {cr:.1%} CR, is "
            f"projected to add ${lo:,.0f}-${hi:,.0f} per month."
        ),
    )


def _roi_ppc_waste_on_organic(product: dict[str, Any]) -> ROIImpact:
    spend = _num(product, "ad_spend_30d")
    if spend is None:
        return _insufficient("ppc_waste_on_organic", ["ad_spend_30d"])

    # A typical cleanup recovers 20-40% of ad spend when the ASIN
    # already owns top-15 organic rank on its main keyword.
    lo = spend * 0.20
    hi = spend * 0.40
    return ROIImpact(
        pattern_name="ppc_waste_on_organic",
        min_impact=lo,
        max_impact=hi,
        monthly_units=_monthly_units(product),
        confidence="high",
        explanation=(
            f"You already rank in the top 15 organically; cutting bids "
            f"on those keywords typically recovers 20-40% of the "
            f"${spend:,.0f}/mo ad spend (${lo:,.0f}-${hi:,.0f}/mo)."
        ),
    )


def _roi_buy_box_loss_healthy_stock(product: dict[str, Any]) -> ROIImpact:
    bb = _num(product, "buy_box_pct")
    units = _monthly_units(product)
    margin = _margin_per_unit(product)

    missing = []
    if bb is None or bb <= 0 or bb >= 100:
        missing.append("buy_box_pct")
    if units is None:
        missing.append("units_ordered_30d or sessions_30d+conversion_rate")
    if margin is None:
        missing.append("price/cogs/fba_fees")
    if missing:
        return _insufficient("buy_box_loss_healthy_stock", missing)

    # Units you lost because Buy Box was off.
    lost_units = units * (100.0 - bb) / bb
    # Typical recovery: 40-70% of the lost units in the first 1-2 months.
    lo = lost_units * 0.40 * margin
    hi = lost_units * 0.70 * margin
    return ROIImpact(
        pattern_name="buy_box_loss_healthy_stock",
        min_impact=lo,
        max_impact=hi,
        monthly_units=units,
        confidence="medium",
        explanation=(
            f"At {bb:.0f}% Buy Box share, ~{lost_units:,.0f} units/mo "
            f"are being diverted to competitors. Recovering 40-70% of "
            f"them returns ${lo:,.0f}-${hi:,.0f}/mo in profit."
        ),
    )


def _roi_underinvested_winner(product: dict[str, Any]) -> ROIImpact:
    sessions = _num(product, "sessions_30d")
    cr = _num(product, "conversion_rate")
    margin = _margin_per_unit(product)
    price = _num(product, "price")

    missing = []
    if sessions is None:
        missing.append("sessions_30d")
    if cr is None:
        missing.append("conversion_rate")
    if margin is None:
        missing.append("price/cogs/fba_fees")
    if missing:
        return _insufficient("underinvested_winner", missing)

    # Scaling assumptions: +50% to +150% sessions via PPC and SEO.
    # Net contribution = extra_units * (margin - target_acos * price).
    # Target ACoS of 25% is a realistic ceiling for a strong converter.
    target_acos = 0.25
    effective_margin = max(margin - (target_acos * (price or 0)), margin * 0.4)
    extra_sessions_lo = sessions * 0.5
    extra_sessions_hi = sessions * 1.5
    lo = extra_sessions_lo * cr * effective_margin
    hi = extra_sessions_hi * cr * effective_margin
    return ROIImpact(
        pattern_name="underinvested_winner",
        min_impact=lo,
        max_impact=hi,
        monthly_units=sessions * cr,
        confidence="medium",
        explanation=(
            f"This ASIN already converts at {cr:.1%}. Scaling sessions "
            f"50-150% at a realistic 25% target ACoS is projected to "
            f"add ${lo:,.0f}-${hi:,.0f}/mo in net profit."
        ),
    )


def _roi_reviews_killing_conversion(product: dict[str, Any]) -> ROIImpact:
    sessions = _num(product, "sessions_30d")
    cr = _num(product, "conversion_rate")
    margin = _margin_per_unit(product)
    rating = _num(product, "rating")

    missing = []
    if sessions is None:
        missing.append("sessions_30d")
    if margin is None:
        missing.append("price/cogs/fba_fees")
    if missing:
        return _insufficient("reviews_killing_conversion", missing)

    # Lift range depends on how bad the rating is. Below 3.8 the upside
    # is larger because the trust hit is steeper.
    lift_lo, lift_hi = 0.005, 0.015
    if rating is not None and rating < 3.8:
        lift_lo, lift_hi = 0.010, 0.025

    lo = sessions * lift_lo * margin
    hi = sessions * lift_hi * margin
    return ROIImpact(
        pattern_name="reviews_killing_conversion",
        min_impact=lo,
        max_impact=hi,
        monthly_units=(sessions * cr) if cr is not None else None,
        confidence="medium",
        explanation=(
            f"Lifting rating restores typical shopper trust. A "
            f"{lift_lo:.1%}-{lift_hi:.1%} absolute CR recovery on "
            f"{sessions:,.0f} sessions/mo at ${margin:.2f}/unit adds "
            f"${lo:,.0f}-${hi:,.0f}/mo."
        ),
    )


def _roi_unit_economics_loss(product: dict[str, Any]) -> ROIImpact:
    units = _monthly_units(product)
    per_unit = _per_unit_profit_after_ppc(product)
    price = _num(product, "price")

    missing = []
    if units is None:
        missing.append("units_ordered_30d or sessions_30d+conversion_rate")
    if per_unit is None:
        missing.append("price/cogs/fba_fees/acos")
    if price is None:
        missing.append("price")
    if missing:
        return _insufficient("unit_economics_loss", missing)

    # Three cases the pattern can fire under:
    #   per_unit < 0  -> real, measurable bleed.
    #   per_unit == 0 -> break-even; no loss but no margin to reinvest.
    #   per_unit > 0  -> defensive path (pattern should not have fired).
    if per_unit < 0:
        monthly_loss = abs(per_unit) * units
        lo = monthly_loss * 0.60      # partial fix (e.g. +5% price OR -10 pts ACoS)
        hi = monthly_loss * 1.20      # full fix + modest healthy-margin gain
        detail = (
            f"Each sale currently loses ${abs(per_unit):.2f} after COGS, "
            f"FBA, and PPC. Stopping the bleed on ~{units:,.0f} units/mo "
            f"preserves ${lo:,.0f}-${hi:,.0f}/mo in profit."
        )
        conf = "high"
    elif per_unit == 0:
        # Break-even: fix target is moving to a healthy 2-5% margin band.
        lo = (price * 0.02) * units
        hi = (price * 0.05) * units
        detail = (
            f"Breaking even on ~{units:,.0f} units/mo leaves nothing to "
            f"reinvest. Moving to a 2-5% healthy margin adds "
            f"${lo:,.0f}-${hi:,.0f}/mo."
        )
        conf = "medium"
    else:
        lo, hi = 0.0, 0.0
        detail = (
            "Per-unit economics are currently positive; no bleed to "
            "stop on this ASIN."
        )
        conf = "high"

    return ROIImpact(
        pattern_name="unit_economics_loss",
        min_impact=lo,
        max_impact=hi,
        monthly_units=units,
        confidence=conf,
        explanation=detail,
    )


def _roi_inventory_trap(product: dict[str, Any]) -> ROIImpact:
    spend = _num(product, "ad_spend_30d")
    if spend is None or spend <= 0:
        # No ad spend to recover; the real win is capital freed, which
        # we cannot express as a monthly recurring number here.
        return _insufficient("inventory_trap", ["ad_spend_30d"])

    lo = spend * 0.70
    hi = spend * 1.00
    return ROIImpact(
        pattern_name="inventory_trap",
        min_impact=lo,
        max_impact=hi,
        monthly_units=_monthly_units(product),
        confidence="high",
        explanation=(
            f"Stock is not moving; pausing the ${spend:,.0f}/mo ad "
            f"spend on this ASIN recovers ${lo:,.0f}-${hi:,.0f}/mo "
            f"immediately, with additional capital freed on liquidation."
        ),
    )


# ---------------------------------------------------------------------------
# Per-pattern calculators (Batch 2: patterns 9-15)
# ---------------------------------------------------------------------------

def _roi_restock_urgency(product: dict[str, Any]) -> ROIImpact:
    units = _monthly_units(product)
    margin = _margin_per_unit(product)

    missing = []
    if units is None:
        missing.append("units_ordered_30d or sessions_30d+conversion_rate")
    if margin is None:
        missing.append("price/cogs/fba_fees")
    if missing:
        return _insufficient("restock_urgency", missing)

    # Risk window: 0.5 to 1.5 months of lost contribution (lost sales
    # plus the 2-6 weeks of rank recovery after restock).
    base = units * margin
    lo = base * 0.5
    hi = base * 1.5
    return ROIImpact(
        pattern_name="restock_urgency",
        min_impact=lo,
        max_impact=hi,
        monthly_units=units,
        confidence="medium",
        explanation=(
            f"A stockout risks 0.5-1.5 months of the current "
            f"~{units:,.0f} units/mo run-rate at ${margin:.2f}/unit "
            f"(${lo:,.0f}-${hi:,.0f}), including rank recovery time."
        ),
    )


def _roi_ppc_addiction(product: dict[str, Any]) -> ROIImpact:
    spend = _num(product, "ad_spend_30d")
    if spend is None or spend <= 0:
        return _insufficient("ppc_addiction", ["ad_spend_30d"])

    # Building organic takes time; realistic run-rate savings are
    # 15-30% of current ad spend over a 3-6 month horizon.
    lo = spend * 0.15
    hi = spend * 0.30
    return ROIImpact(
        pattern_name="ppc_addiction",
        min_impact=lo,
        max_impact=hi,
        monthly_units=_monthly_units(product),
        confidence="low",
        explanation=(
            f"Building organic rank typically lets you pull back "
            f"15-30% of the ${spend:,.0f}/mo ad spend over 3-6 months "
            f"(${lo:,.0f}-${hi:,.0f}/mo at steady state)."
        ),
    )


def _roi_buy_box_war_on_ranked(product: dict[str, Any]) -> ROIImpact:
    bb = _num(product, "buy_box_pct")
    units = _monthly_units(product)
    margin = _margin_per_unit(product)

    missing = []
    if bb is None or bb <= 0 or bb >= 100:
        missing.append("buy_box_pct")
    if units is None:
        missing.append("units_ordered_30d or sessions_30d+conversion_rate")
    if margin is None:
        missing.append("price/cogs/fba_fees")
    if missing:
        return _insufficient("buy_box_war_on_ranked", missing)

    # Ranked ASINs already pull the clicks, but a price war is harder
    # to fully win back. Recovery: 30-60% of the diverted units.
    lost_units = units * (100.0 - bb) / bb
    lo = lost_units * 0.30 * margin
    hi = lost_units * 0.60 * margin
    return ROIImpact(
        pattern_name="buy_box_war_on_ranked",
        min_impact=lo,
        max_impact=hi,
        monthly_units=units,
        confidence="medium",
        explanation=(
            f"Rank brings shoppers in, but at {bb:.0f}% Buy Box share "
            f"~{lost_units:,.0f} units/mo go to a competitor. "
            f"Recovering 30-60% returns ${lo:,.0f}-${hi:,.0f}/mo."
        ),
    )


def _roi_weak_listing_foundation(product: dict[str, Any]) -> ROIImpact:
    sessions = _num(product, "sessions_30d")
    cr = _num(product, "conversion_rate")
    margin = _margin_per_unit(product)

    missing = []
    if sessions is None:
        missing.append("sessions_30d")
    if cr is None:
        missing.append("conversion_rate")
    if margin is None:
        missing.append("price/cogs/fba_fees")
    if missing:
        return _insufficient("weak_listing_foundation", missing)

    # Realistic relaunch: 1.2x-2.5x current sessions at 1.5-2.5% CR
    # within a quarter. Hard-capped at $2,500/mo so the number stays
    # credible on speculative projections. The cap is applied to the
    # max first, then min is clamped to the capped max so the range
    # never inverts on very high-volume ASINs.
    MAX_MONTHLY_CAP = 2500.0
    current_contribution = sessions * cr * margin
    lo_projected = (sessions * 1.2) * 0.015 * margin
    hi_projected = (sessions * 2.5) * 0.025 * margin
    hi = min(max(hi_projected - current_contribution, 0.0), MAX_MONTHLY_CAP)
    lo = min(max(lo_projected - current_contribution, 0.0), hi)
    return ROIImpact(
        pattern_name="weak_listing_foundation",
        min_impact=lo,
        max_impact=hi,
        monthly_units=sessions * cr,
        confidence="low",
        explanation=(
            f"A full relaunch (hero, title, keywords, reviews) typically "
            f"reaches 1.2x-2.5x sessions at 1.5-2.5% CR. Incremental "
            f"monthly profit over today: ${lo:,.0f}-${hi:,.0f} "
            f"(capped to stay realistic on speculative projections)."
        ),
    )


def _roi_review_starvation(product: dict[str, Any]) -> ROIImpact:
    sessions = _num(product, "sessions_30d")
    cr = _num(product, "conversion_rate")
    margin = _margin_per_unit(product)

    missing = []
    if sessions is None:
        missing.append("sessions_30d")
    if cr is None:
        missing.append("conversion_rate")
    if margin is None:
        missing.append("price/cogs/fba_fees")
    if missing:
        return _insufficient("review_starvation", missing)

    # Closing the review-trust gap typically lifts CR by 0.3-1.0
    # absolute points on an ASIN that already converts.
    lift_lo, lift_hi = 0.003, 0.010
    lo = sessions * lift_lo * margin
    hi = sessions * lift_hi * margin
    return ROIImpact(
        pattern_name="review_starvation",
        min_impact=lo,
        max_impact=hi,
        monthly_units=sessions * cr,
        confidence="medium",
        explanation=(
            f"Growing reviews past the trust threshold typically lifts "
            f"CR 0.3-1.0 points on {sessions:,.0f} sessions/mo at "
            f"${margin:.2f}/unit (${lo:,.0f}-${hi:,.0f}/mo)."
        ),
    )


def _roi_overbid_weak_listing(product: dict[str, Any]) -> ROIImpact:
    spend = _num(product, "ad_spend_30d")
    if spend is None or spend <= 0:
        return _insufficient("overbid_weak_listing", ["ad_spend_30d"])

    # Cutting bids on a weak listing is immediate savings; the range
    # reflects how aggressively you trim while the listing is fixed.
    lo = spend * 0.25
    hi = spend * 0.50
    return ROIImpact(
        pattern_name="overbid_weak_listing",
        min_impact=lo,
        max_impact=hi,
        monthly_units=_monthly_units(product),
        confidence="medium",
        explanation=(
            f"Trimming bids 25-50% on the ${spend:,.0f}/mo ad spend "
            f"while the listing is being fixed recovers "
            f"${lo:,.0f}-${hi:,.0f}/mo immediately."
        ),
    )


def _roi_discontinuation_candidate(product: dict[str, Any]) -> ROIImpact:
    spend = _num(product, "ad_spend_30d")
    units = _monthly_units(product)
    per_unit = _per_unit_profit_after_ppc(product)

    # Recurring monthly savings = stopping the ad spend drag, plus
    # stopping any per-unit loss if the economics are negative.
    ad_savings_lo = (spend * 0.70) if spend else 0.0
    ad_savings_hi = (spend * 1.00) if spend else 0.0
    loss_stopped = 0.0
    if units is not None and per_unit is not None and per_unit < 0:
        loss_stopped = abs(per_unit) * units

    lo = ad_savings_lo + loss_stopped * 0.5
    hi = ad_savings_hi + loss_stopped * 1.0
    if lo <= 0 and hi <= 0:
        return _insufficient(
            "discontinuation_candidate",
            ["ad_spend_30d or negative unit economics"],
        )
    return ROIImpact(
        pattern_name="discontinuation_candidate",
        min_impact=lo,
        max_impact=hi,
        monthly_units=units,
        confidence="medium",
        explanation=(
            f"Sunsetting this ASIN stops the ad-spend drag and any "
            f"per-unit loss, recovering ${lo:,.0f}-${hi:,.0f}/mo in "
            f"resources to redirect to scalable ASINs."
        ),
    )


# ---------------------------------------------------------------------------
# Dispatch table
#
# Maps pattern name to its calculator. Patterns not present here fall
# through to the neutral placeholder in calculate_roi().
# ---------------------------------------------------------------------------

_CALCULATORS: dict[str, Callable[[dict[str, Any]], ROIImpact]] = {
    "listing_over_promise":        _roi_listing_over_promise,
    "hidden_winner":               _roi_hidden_winner,
    "ppc_waste_on_organic":        _roi_ppc_waste_on_organic,
    "buy_box_loss_healthy_stock":  _roi_buy_box_loss_healthy_stock,
    "underinvested_winner":        _roi_underinvested_winner,
    "reviews_killing_conversion":  _roi_reviews_killing_conversion,
    "unit_economics_loss":         _roi_unit_economics_loss,
    "inventory_trap":              _roi_inventory_trap,
    "restock_urgency":             _roi_restock_urgency,
    "ppc_addiction":               _roi_ppc_addiction,
    "buy_box_war_on_ranked":       _roi_buy_box_war_on_ranked,
    "weak_listing_foundation":     _roi_weak_listing_foundation,
    "review_starvation":           _roi_review_starvation,
    "overbid_weak_listing":        _roi_overbid_weak_listing,
    "discontinuation_candidate":   _roi_discontinuation_candidate,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def calculate_roi(
    pattern_match: dict[str, Any],
    asin_data: dict[str, Any],
) -> ROIImpact:
    """
    Estimate the monthly financial impact of a single pattern match.

    Parameters
    ----------
    pattern_match:
        Dict describing the pattern that fired. Must contain at least
        ``{"name": <pattern_name>}``. Additional fields (severity,
        impact_type, etc.) are accepted and ignored so callers can
        pass a full record without reshaping it.
    asin_data:
        Product dict as loaded from the CSV, e.g.::

            {
                "asin": "B0...",
                "price": 24.99,
                "cogs": 6.50,
                "fba_fees": 4.20,
                "sessions_30d": 5200,
                "conversion_rate": 0.0219,
                ...
            }

    Returns
    -------
    ROIImpact
        A dollar range plus explanation. When a formula is not yet
        wired for the given pattern, a neutral placeholder is returned
        so audit_engine.py can still render the finding.
    """
    pattern_name = str(pattern_match.get("name") or "").strip()

    # Unknown or not-yet-wired pattern: return a neutral placeholder.
    if pattern_name not in _CALCULATORS:
        return ROIImpact(
            pattern_name=pattern_name or "unknown",
            min_impact=None,
            max_impact=None,
            monthly_units=_monthly_units(asin_data),
            confidence="low",
            explanation=(
                "ROI formula is not yet wired for this pattern. A "
                "monthly dollar range will appear once the formula is "
                "registered in Step 2 of roi_calculator.py."
            ),
        )

    calculator = _CALCULATORS[pattern_name]
    return calculator(asin_data)
