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
# Dispatch table
#
# Populated in Step 2. Each entry will map a pattern name (matching
# CROSS_METRIC_PATTERNS[*].name) to a function with the shape:
#
#     (product: dict) -> ROIImpact
#
# Keeping it here now lets tests and audit_engine.py depend on the
# public API without waiting for individual formulas.
# ---------------------------------------------------------------------------

_CALCULATORS: dict[str, Callable[[dict[str, Any]], ROIImpact]] = {}


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
