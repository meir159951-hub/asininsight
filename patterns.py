"""
patterns.py - Cross-metric diagnostic patterns for ASIN analysis.

Each pattern examines a combination of metrics to surface compound issues
that single-metric rules cannot catch. A single low CTR is a data point;
a high CTR combined with a low conversion rate is a diagnosis.

HONESTY NOTE
------------
Detection thresholds here are heuristic, derived from public Amazon seller
best-practices (2024-2026), NOT from a proprietary benchmark dataset.
They are intentionally conservative to reduce false positives and should
be validated with real sellers before being trusted for high-stakes calls.

DESIGN
------
Every pattern is a `CrossMetricPattern` instance. The `conditions` field
holds a pure function `(product: dict) -> bool` that returns True when the
pattern matches the product. Missing fields should return False, never
raise, so partial CSVs don't break the pipeline.

Patterns are pure detection only. Financial impact (ROI) and prescriptive
wording are produced by other modules (roi_calculator.py, audit_engine.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CrossMetricPattern:
    """A compound diagnostic rule that inspects more than one metric."""

    name: str
    description: str
    conditions: Callable[[dict[str, Any]], bool]
    impact_type: str           # "conversion" | "traffic" | "ads" | "pricing" | "inventory" | ...
    confidence: str            # "high" | "medium" | "low"


# ---------------------------------------------------------------------------
# Field-access helpers (safe for partial CSVs)
# ---------------------------------------------------------------------------

def _num(product: dict[str, Any], key: str) -> float | None:
    """Return a numeric field as float, or None if missing/invalid."""
    value = product.get(key)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _has(product: dict[str, Any], *keys: str) -> bool:
    """True iff every key resolves to a finite numeric value."""
    return all(_num(product, k) is not None for k in keys)


# ---------------------------------------------------------------------------
# Pattern 1: Listing Over-Promise
#   High CTR + Low Conversion Rate.
#   Shoppers click but don't buy. The main image or title is winning the
#   click; something on the detail page is losing them (price, reviews,
#   image-vs-reality mismatch).
# ---------------------------------------------------------------------------

def _listing_over_promise(product: dict[str, Any]) -> bool:
    if not _has(product, "ctr", "conversion_rate"):
        return False
    ctr = _num(product, "ctr")  # fraction, e.g. 0.005 == 0.5%
    cr = _num(product, "conversion_rate")
    return ctr > 0.005 and cr < 0.02


# ---------------------------------------------------------------------------
# Pattern 2: Hidden Winner (Visibility Problem)
#   Low CTR + High Conversion Rate.
#   The listing converts well for the few shoppers that reach it. The
#   problem is upstream: main image or search placement is not winning
#   the click. Fix hero image and keyword targeting, not the detail page.
# ---------------------------------------------------------------------------

def _hidden_winner(product: dict[str, Any]) -> bool:
    if not _has(product, "ctr", "conversion_rate"):
        return False
    ctr = _num(product, "ctr")
    cr = _num(product, "conversion_rate")
    return ctr < 0.003 and cr > 0.03


# ---------------------------------------------------------------------------
# Pattern 3: PPC Waste on Organic Wins
#   High ACoS + Strong organic rank on the main keyword.
#   You are paying for ad clicks on searches where you already rank in
#   the top results organically. The ad is cannibalising free traffic.
#   Reduce bids on these keywords and redirect budget.
# ---------------------------------------------------------------------------

def _ppc_waste_on_organic(product: dict[str, Any]) -> bool:
    if not _has(product, "acos", "organic_rank_top_keyword"):
        return False
    acos = _num(product, "acos")              # fraction, e.g. 0.35 == 35%
    rank = _num(product, "organic_rank_top_keyword")
    return acos > 0.35 and rank <= 15


# ---------------------------------------------------------------------------
# Pattern 4: Buy Box Loss Despite Healthy Stock
#   Low Buy Box share + Days-of-cover indicates no inventory risk.
#   When stock is healthy but Buy Box share is weak, the cause is almost
#   always pricing (competitor undercutting) or seller-performance
#   metrics (late-shipment rate, order defect rate). Not inventory.
# ---------------------------------------------------------------------------

def _buy_box_loss_healthy_stock(product: dict[str, Any]) -> bool:
    if not _has(product, "buy_box_pct", "days_of_cover"):
        return False
    buy_box = _num(product, "buy_box_pct")    # percent, 0-100
    doc = _num(product, "days_of_cover")
    return buy_box < 70 and doc >= 14


# ---------------------------------------------------------------------------
# Pattern 5: Underinvested Winner (Scaling Opportunity)
#   High Conversion Rate + Low Traffic.
#   The listing converts at a rate that beats most ASINs in the catalog,
#   but session volume is low. This is the cheapest win in the portfolio:
#   pour budget into PPC and SEO on keywords this ASIN already converts.
# ---------------------------------------------------------------------------

def _underinvested_winner(product: dict[str, Any]) -> bool:
    if not _has(product, "conversion_rate", "sessions_30d"):
        return False
    cr = _num(product, "conversion_rate")
    sessions = _num(product, "sessions_30d")
    return cr > 0.03 and sessions < 1500


# ---------------------------------------------------------------------------
# Registered patterns
#   audit_engine.py imports CROSS_METRIC_PATTERNS and iterates over it.
#   Order in this list is also the default presentation order.
# ---------------------------------------------------------------------------

CROSS_METRIC_PATTERNS: list[CrossMetricPattern] = [
    CrossMetricPattern(
        name="listing_over_promise",
        description=(
            "High CTR combined with low conversion rate. Shoppers click the "
            "listing but do not buy on the detail page. The hero image or "
            "title is winning the click, but price, reviews, or an "
            "image-vs-reality mismatch is losing the sale."
        ),
        conditions=_listing_over_promise,
        impact_type="conversion",
        confidence="high",
    ),
    CrossMetricPattern(
        name="hidden_winner",
        description=(
            "Low CTR combined with high conversion rate. The detail page "
            "converts well, but the listing rarely wins the click in "
            "search. The bottleneck is upstream: hero image, title, or "
            "keyword placement, not the detail page."
        ),
        conditions=_hidden_winner,
        impact_type="traffic",
        confidence="high",
    ),
    CrossMetricPattern(
        name="ppc_waste_on_organic",
        description=(
            "High ACoS while the ASIN already ranks in the top 15 "
            "organic results for its main keyword. Ad spend is "
            "cannibalising free traffic. Lower bids on keywords where "
            "organic rank is already strong and redirect budget to "
            "searches where the ASIN is buried."
        ),
        conditions=_ppc_waste_on_organic,
        impact_type="ads",
        confidence="high",
    ),
    CrossMetricPattern(
        name="buy_box_loss_healthy_stock",
        description=(
            "Buy Box share is weak although inventory is healthy. The "
            "cause is almost always pricing (a competitor undercutting) "
            "or seller-performance metrics (late shipments, defect rate). "
            "Investigate competitor prices and account health before "
            "touching the listing."
        ),
        conditions=_buy_box_loss_healthy_stock,
        impact_type="pricing",
        confidence="high",
    ),
    CrossMetricPattern(
        name="underinvested_winner",
        description=(
            "Conversion rate is strong but session volume is low. This "
            "is typically the highest-ROI ASIN to scale: the listing "
            "already converts, the constraint is visibility. Increase "
            "PPC budget and invest in SEO for its top-converting "
            "keywords."
        ),
        conditions=_underinvested_winner,
        impact_type="traffic",
        confidence="medium",
    ),
]
