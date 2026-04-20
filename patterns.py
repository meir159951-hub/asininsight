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
    acos = _num(product, "acos")              # fraction, e.g. 0.45 == 45%
    rank = _num(product, "organic_rank_top_keyword")
    return acos > 0.45 and rank <= 15


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
# Pattern 6: Reviews Killing Conversion
#   Low product rating combined with meaningful session volume.
#   Traffic reaches the listing but bleeds out on the detail page because
#   review sentiment shakes shopper confidence. Fix the drivers of low
#   ratings before spending more on traffic.
# ---------------------------------------------------------------------------

def _reviews_killing_conversion(product: dict[str, Any]) -> bool:
    if not _has(product, "rating", "sessions_30d"):
        return False
    rating = _num(product, "rating")
    sessions = _num(product, "sessions_30d")
    return rating < 4.0 and sessions > 500


# ---------------------------------------------------------------------------
# Pattern 7: Unit Economics Loss
#   Per-unit contribution is negative or near-zero once COGS, FBA fees,
#   and PPC attribution at the current ACoS are deducted from the sale
#   price. Every sale loses money or breaks even. Fix pricing or cost
#   structure before any marketing or scaling work.
# ---------------------------------------------------------------------------

def _unit_economics_loss(product: dict[str, Any]) -> bool:
    if not _has(product, "price", "cogs", "fba_fees", "acos"):
        return False
    price = _num(product, "price")
    cogs = _num(product, "cogs")
    fba = _num(product, "fba_fees")
    acos = _num(product, "acos")
    per_unit_profit = price - cogs - fba - (acos * price)
    return per_unit_profit <= 0


# ---------------------------------------------------------------------------
# Pattern 8: Inventory Trap (Dead Stock)
#   Days-of-cover is very high while conversion rate is weak. Working
#   capital is tied up in stock that does not move. Stop scaling ad
#   spend on this ASIN; consider a price promotion or liquidation
#   before the next purchase order.
# ---------------------------------------------------------------------------

def _inventory_trap(product: dict[str, Any]) -> bool:
    if not _has(product, "days_of_cover", "conversion_rate"):
        return False
    doc = _num(product, "days_of_cover")
    cr = _num(product, "conversion_rate")
    return doc > 90 and cr < 0.015


# ---------------------------------------------------------------------------
# Pattern 9: Restock Urgency
#   Days-of-cover is low while the ASIN converts actively. A stockout
#   does not just stop sales - it typically costs organic rank for
#   weeks after restock. Pause PPC scaling and replenish stock before
#   adding more traffic.
# ---------------------------------------------------------------------------

def _restock_urgency(product: dict[str, Any]) -> bool:
    if not _has(product, "days_of_cover", "conversion_rate"):
        return False
    doc = _num(product, "days_of_cover")
    cr = _num(product, "conversion_rate")
    return doc < 14 and cr > 0.02


# ---------------------------------------------------------------------------
# Pattern 10: PPC Addiction (Paid Traffic Without Organic Lift)
#   Meaningful ad spend is being deployed while organic rank on the
#   main keyword is still buried (> 30). Paid traffic is renting
#   visibility, not building it. The ACoS floor will not drop until
#   organic rank improves.
# ---------------------------------------------------------------------------

def _ppc_addiction(product: dict[str, Any]) -> bool:
    if not _has(product, "ad_spend_30d", "organic_rank_top_keyword"):
        return False
    spend = _num(product, "ad_spend_30d")
    rank = _num(product, "organic_rank_top_keyword")
    return spend > 300 and rank > 30


# ---------------------------------------------------------------------------
# Pattern 11: Buy Box War on a Ranked ASIN
#   The ASIN ranks in the top 10 organically but Buy Box share is
#   soft. Rank is pulling shoppers to the listing; an aggressive FBM
#   competitor or price war is peeling off the sale at the last moment.
#   Investigate competitor pricing and any FBM offers on the listing.
# ---------------------------------------------------------------------------

def _buy_box_war_on_ranked(product: dict[str, Any]) -> bool:
    if not _has(product, "organic_rank_top_keyword", "buy_box_pct"):
        return False
    rank = _num(product, "organic_rank_top_keyword")
    buy_box = _num(product, "buy_box_pct")
    return rank <= 10 and buy_box < 80


# ---------------------------------------------------------------------------
# Pattern 12: Weak Listing Foundation
#   Sessions, organic rank, and review count are all weak together.
#   This is not an optimisation problem: the listing lacks every
#   ingredient a first-page ASIN needs. Treat as a relaunch (main
#   image, title, keywords, compliant review generation), not a tweak.
# ---------------------------------------------------------------------------

def _weak_listing_foundation(product: dict[str, Any]) -> bool:
    if not _has(product, "sessions_30d", "organic_rank_top_keyword", "review_count"):
        return False
    sessions = _num(product, "sessions_30d")
    rank = _num(product, "organic_rank_top_keyword")
    reviews = _num(product, "review_count")
    return sessions < 300 and rank > 50 and reviews < 15


# ---------------------------------------------------------------------------
# Pattern 13: Review Starvation
#   Conversion is healthy but the review count is far below the level
#   shoppers use as a trust anchor. The ASIN converts despite the gap;
#   closing it usually unlocks additional conversion gains and allows
#   PPC to scale more efficiently.
# ---------------------------------------------------------------------------

def _review_starvation(product: dict[str, Any]) -> bool:
    if not _has(product, "conversion_rate", "review_count"):
        return False
    cr = _num(product, "conversion_rate")
    reviews = _num(product, "review_count")
    return cr > 0.025 and reviews < 20


# ---------------------------------------------------------------------------
# Pattern 14: Overbidding on a Weak Listing
#   ACoS is high while the detail page is weak - either low conversion
#   or low rating. Every extra dollar of ad spend magnifies a problem
#   that lives on the listing. Fix the listing before touching bids.
# ---------------------------------------------------------------------------

def _overbid_weak_listing(product: dict[str, Any]) -> bool:
    if not _has(product, "acos"):
        return False
    acos = _num(product, "acos")
    if acos <= 0.50:
        return False
    cr = _num(product, "conversion_rate")
    rating = _num(product, "rating")
    weak_cr = cr is not None and cr < 0.02
    weak_rating = rating is not None and rating < 4.0
    return weak_cr or weak_rating


# ---------------------------------------------------------------------------
# Pattern 15: Discontinuation Candidate
#   Conversion, rating, and review count are all weak together. This
#   ASIN is a candidate for sunset, not optimisation. Keep it only if
#   there is a strategic reason (bundling, catalog coverage); otherwise
#   the operating cost likely outweighs the margin it produces.
# ---------------------------------------------------------------------------

def _discontinuation_candidate(product: dict[str, Any]) -> bool:
    if not _has(product, "conversion_rate", "rating", "review_count"):
        return False
    cr = _num(product, "conversion_rate")
    rating = _num(product, "rating")
    reviews = _num(product, "review_count")
    return cr < 0.015 and rating < 4.0 and reviews < 25


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
    CrossMetricPattern(
        name="reviews_killing_conversion",
        description=(
            "Low product rating combined with meaningful session "
            "volume. Traffic reaches the listing but bleeds out on "
            "the detail page because review sentiment shakes shopper "
            "confidence. Fix the drivers of low ratings before "
            "spending more on traffic."
        ),
        conditions=_reviews_killing_conversion,
        impact_type="reviews",
        confidence="high",
    ),
    CrossMetricPattern(
        name="unit_economics_loss",
        description=(
            "Per-unit profit is negative or near-zero after COGS, FBA "
            "fees, and PPC attribution at the current ACoS. Every sale "
            "loses money or breaks even. Fix pricing or cost structure "
            "before any marketing or scaling work."
        ),
        conditions=_unit_economics_loss,
        impact_type="pricing",
        confidence="high",
    ),
    CrossMetricPattern(
        name="inventory_trap",
        description=(
            "Days-of-cover is very high while conversion rate is weak. "
            "Working capital is tied up in stock that does not move. "
            "Stop scaling ad spend on this ASIN; consider a price "
            "promotion or liquidation before the next purchase order."
        ),
        conditions=_inventory_trap,
        impact_type="inventory",
        confidence="high",
    ),
    CrossMetricPattern(
        name="restock_urgency",
        description=(
            "Inventory cover is low while the ASIN converts actively. "
            "A stockout will not only stop sales but typically costs "
            "organic rank for weeks. Pause PPC scaling and replenish "
            "stock before adding more traffic."
        ),
        conditions=_restock_urgency,
        impact_type="inventory",
        confidence="high",
    ),
    CrossMetricPattern(
        name="ppc_addiction",
        description=(
            "Meaningful ad spend is being deployed while organic rank "
            "on the main keyword is still buried. Paid traffic is "
            "renting visibility, not building it. The ACoS floor will "
            "not drop until organic rank improves."
        ),
        conditions=_ppc_addiction,
        impact_type="ads",
        confidence="medium",
    ),
    CrossMetricPattern(
        name="buy_box_war_on_ranked",
        description=(
            "The ASIN ranks in the top 10 organically but Buy Box "
            "share is soft. Rank is pulling shoppers in; an aggressive "
            "FBM competitor or a price war is peeling off the sale "
            "at the last moment. Investigate competitor pricing and "
            "any FBM offers on the listing."
        ),
        conditions=_buy_box_war_on_ranked,
        impact_type="pricing",
        confidence="high",
    ),
    CrossMetricPattern(
        name="weak_listing_foundation",
        description=(
            "Sessions, organic rank, and review count are all weak "
            "together. This is not an optimisation problem - the "
            "listing lacks every ingredient a first-page ASIN needs. "
            "Treat as a relaunch (main image, title, keywords, "
            "compliant review generation), not a tweak."
        ),
        conditions=_weak_listing_foundation,
        impact_type="listing",
        confidence="high",
    ),
    CrossMetricPattern(
        name="review_starvation",
        description=(
            "Conversion is healthy but the review count is far below "
            "the level shoppers use as a trust anchor. The ASIN "
            "converts despite the gap; closing it usually unlocks "
            "additional conversion and lets PPC scale further."
        ),
        conditions=_review_starvation,
        impact_type="reviews",
        confidence="medium",
    ),
    CrossMetricPattern(
        name="overbid_weak_listing",
        description=(
            "ACoS is high while the detail page is weak - either low "
            "conversion or low rating. Every extra dollar of ad spend "
            "magnifies a problem that lives on the listing. Fix the "
            "listing first; do not raise bids."
        ),
        conditions=_overbid_weak_listing,
        impact_type="ads",
        confidence="high",
    ),
    CrossMetricPattern(
        name="discontinuation_candidate",
        description=(
            "Conversion, rating, and review count are all weak "
            "together. This ASIN is a candidate for sunset, not "
            "optimisation. Keep it only if there is a strategic reason "
            "(bundling, catalog coverage); otherwise operating cost "
            "likely outweighs margin."
        ),
        conditions=_discontinuation_candidate,
        impact_type="portfolio",
        confidence="medium",
    ),
]
