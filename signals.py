"""
signals.py

Standalone signal detectors for the critical Amazon health checks that
cross-metric patterns (patterns.py) do not capture on their own:

    * Buy Box share
    * Suppression / visibility-block risk
    * True profit margin (after COGS, FBA, and PPC)
    * 30-day trend movement on sessions, conversion rate, ACoS, and rank

Unlike patterns, these are single-axis diagnostics that produce a
severity tag and an impact_score; they run whether or not any cross-
metric pattern fires.

HONESTY NOTE
------------
Severity thresholds here are heuristic defaults, not benchmarks from a
proprietary dataset. Trend detection needs *_prev fields in the CSV;
when they are missing the trend path simply returns no signals instead
of raising.

STEP 1 SCAFFOLD
---------------
This file provides the dataclass, field helpers, the four core detectors,
and a `detect_all_signals` orchestrator. Severity thresholds and
impact_score scales are tuned to be conservative on a first pass and
will be refined once real seller CSVs land.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StandaloneSignal:
    """
    A single diagnostic signal produced by one of the detectors below.

    Attributes
    ----------
    name:
        Stable identifier (e.g. ``"buy_box"``, ``"trend_sessions"``).
        Downstream code keys off this.
    severity:
        ``"ok"`` | ``"low"`` | ``"medium"`` | ``"high"`` | ``"critical"``.
    explanation:
        One- or two-sentence seller-facing description of what was
        detected and what the numbers were.
    impact_score:
        0.0-10.0 magnitude, used by audit_engine.py for prioritisation.
        Rough mapping to severity: ok=0, low=1-3, medium=4-6,
        high=7-8, critical=9-10.
    """

    name: str
    severity: str
    explanation: str
    impact_score: float


# ---------------------------------------------------------------------------
# Field-access helpers (safe for partial CSVs)
# ---------------------------------------------------------------------------

def _num(product: dict[str, Any], key: str) -> float | None:
    """Return a numeric field as float, or None if missing / invalid."""
    value = product.get(key)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Signal 1: Buy Box analysis
#
#   Translates Buy Box share into a severity band. The lower the share,
#   the more of the listing's traffic converts for someone else.
# ---------------------------------------------------------------------------

def analyze_buy_box(product: dict[str, Any]) -> StandaloneSignal | None:
    bb = _num(product, "buy_box_pct")
    if bb is None:
        return None

    if bb >= 90:
        return StandaloneSignal(
            name="buy_box",
            severity="ok",
            explanation=f"Buy Box share healthy at {bb:.0f}%.",
            impact_score=0.0,
        )
    if bb >= 70:
        return StandaloneSignal(
            name="buy_box",
            severity="medium",
            explanation=(
                f"Buy Box share is soft at {bb:.0f}%. Roughly "
                f"{100 - bb:.0f}% of traffic-driven sales are leaking "
                f"to a competitor on this listing."
            ),
            impact_score=4.5,
        )
    if bb >= 50:
        return StandaloneSignal(
            name="buy_box",
            severity="high",
            explanation=(
                f"Buy Box share is weak at {bb:.0f}%. A competitor is "
                f"winning most of the last-mile conversion. Investigate "
                f"pricing and seller-performance metrics first."
            ),
            impact_score=7.0,
        )
    return StandaloneSignal(
        name="buy_box",
        severity="critical",
        explanation=(
            f"Buy Box share is critical at {bb:.0f}%. You are no "
            f"longer the default seller on your own listing; almost "
            f"every click converts for someone else."
        ),
        impact_score=9.0,
    )


# ---------------------------------------------------------------------------
# Signal 2: Suppression / Blocked-listing risk
#
#   Amazon does not surface suppression in a single CSV field. We infer
#   risk from combinations that almost always imply the listing is not
#   served normally: near-zero sessions on a mature listing, or a rank
#   so deep the listing is effectively hidden.
# ---------------------------------------------------------------------------

def detect_suppression_risk(product: dict[str, Any]) -> StandaloneSignal | None:
    sessions = _num(product, "sessions_30d")
    reviews = _num(product, "review_count")
    rank = _num(product, "organic_rank_top_keyword")

    flags: list[str] = []
    if sessions is not None and sessions < 50:
        flags.append("almost no session volume this month")
    if rank is not None and rank >= 300:
        flags.append("organic rank beyond page 20 on the main keyword")
    if (
        sessions is not None
        and reviews is not None
        and reviews > 50
        and sessions < 100
    ):
        flags.append("mature listing (50+ reviews) with near-zero traffic")

    if not flags:
        return None

    # These are indirect heuristics, not confirmation from Seller
    # Central. Cap severity at "medium" so the signal reads as a
    # hypothesis to investigate, not a confirmed defect. Two or more
    # flags stay at "medium" but raise impact_score so it still
    # surfaces in priority ranking.
    severity = "medium"
    impact = 6.0 if len(flags) >= 2 else 4.5
    return StandaloneSignal(
        name="suppression_risk",
        severity=severity,
        explanation=(
            "Visibility-block hypothesis (not confirmed without a "
            "Seller Central check): "
            + "; ".join(flags)
            + ". These are indirect indicators; verify Account Health "
            "and the live listing state before any marketing work."
        ),
        impact_score=impact,
    )


# ---------------------------------------------------------------------------
# Signal 3: True Profit Margin
#
#   Reports the post-fees, post-PPC margin as a percent of sale price
#   and flags a severity. Pure computation; relies only on price,
#   COGS, FBA, and (optionally) ACoS.
# ---------------------------------------------------------------------------

def calculate_true_profit_margin(product: dict[str, Any]) -> StandaloneSignal | None:
    price = _num(product, "price")
    cogs = _num(product, "cogs")
    fba = _num(product, "fba_fees")
    acos = _num(product, "acos")

    if price is None or cogs is None or fba is None or price <= 0:
        return None

    gross_margin = price - cogs - fba
    if acos is not None:
        net_unit_profit = gross_margin - (acos * price)
        includes_ppc = True
    else:
        net_unit_profit = gross_margin
        includes_ppc = False

    margin_pct = net_unit_profit / price
    after = "COGS, FBA, and PPC" if includes_ppc else "COGS and FBA"

    if margin_pct < 0:
        severity, impact = "critical", 9.0
        verdict = "every sale loses money"
    elif margin_pct < 0.10:
        severity, impact = "high", 7.0
        verdict = "below 10% leaves no buffer for ads, returns, or fee changes"
    elif margin_pct < 0.20:
        severity, impact = "medium", 4.5
        verdict = "tight - limits room to scale PPC or absorb fee increases"
    else:
        severity, impact = "ok", 0.0
        verdict = "healthy margin"

    return StandaloneSignal(
        name="true_profit_margin",
        severity=severity,
        explanation=(
            f"True margin after {after}: {margin_pct:.1%} "
            f"(${net_unit_profit:.2f}/unit) - {verdict}."
        ),
        impact_score=impact,
    )


# ---------------------------------------------------------------------------
# Signal 4: 30-Day Trend Analysis
#
#   Looks for meaningful declines in sessions, conversion rate, and
#   rank, plus meaningful climbs in ACoS. Requires optional
#   `<metric>_prev` fields on the product dict.
#
#   This detector returns a LIST (possibly empty) because a single ASIN
#   can move adversely on more than one axis.
# ---------------------------------------------------------------------------

def analyze_trends(product: dict[str, Any]) -> list[StandaloneSignal]:
    out: list[StandaloneSignal] = []

    # Sessions: flag a material drop (>20%).
    curr = _num(product, "sessions_30d")
    prev = _num(product, "sessions_30d_prev")
    if curr is not None and prev is not None and prev > 0:
        change = (curr - prev) / prev
        if change <= -0.20:
            out.append(StandaloneSignal(
                name="trend_sessions",
                severity="high" if change <= -0.35 else "medium",
                explanation=(
                    f"Sessions dropped {abs(change):.0%} in 30 days "
                    f"(from {prev:,.0f} to {curr:,.0f})."
                ),
                impact_score=7.0 if change <= -0.35 else 5.0,
            ))

    # Conversion rate: flag a drop (>15% relative).
    curr = _num(product, "conversion_rate")
    prev = _num(product, "conversion_rate_prev")
    if curr is not None and prev is not None and prev > 0:
        change = (curr - prev) / prev
        if change <= -0.15:
            out.append(StandaloneSignal(
                name="trend_conversion",
                severity="high" if change <= -0.30 else "medium",
                explanation=(
                    f"Conversion rate fell {abs(change):.0%} in 30 days "
                    f"(from {prev:.1%} to {curr:.1%})."
                ),
                impact_score=7.5 if change <= -0.30 else 5.5,
            ))

    # ACoS: flag a climb (>25% relative).
    curr = _num(product, "acos")
    prev = _num(product, "acos_prev")
    if curr is not None and prev is not None and prev > 0:
        change = (curr - prev) / prev
        if change >= 0.25:
            out.append(StandaloneSignal(
                name="trend_acos",
                severity="high" if change >= 0.50 else "medium",
                explanation=(
                    f"ACoS climbed {change:.0%} in 30 days "
                    f"(from {prev:.0%} to {curr:.0%})."
                ),
                impact_score=7.0 if change >= 0.50 else 5.0,
            ))

    # Organic rank: flag a material drop (10+ positions down).
    curr = _num(product, "organic_rank_top_keyword")
    prev = _num(product, "organic_rank_prev")
    if curr is not None and prev is not None:
        change = curr - prev      # rank increases = worse
        if change >= 10:
            out.append(StandaloneSignal(
                name="trend_rank",
                severity="high" if change >= 25 else "medium",
                explanation=(
                    f"Organic rank on the main keyword dropped "
                    f"{int(change)} positions (from #{int(prev)} to "
                    f"#{int(curr)}) in 30 days."
                ),
                impact_score=7.0 if change >= 25 else 5.0,
            ))

    return out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def detect_all_signals(product: dict[str, Any]) -> list[StandaloneSignal]:
    """
    Run every standalone detector on a product and return the
    non-None results. Trend detectors can contribute multiple
    signals; single-result detectors contribute zero or one.

    The list is NOT sorted here; ordering is the caller's concern so
    audit_engine.py can interleave signals with pattern findings
    using its own priority logic.
    """
    results: list[StandaloneSignal] = []

    for detector in (
        analyze_buy_box,
        detect_suppression_risk,
        calculate_true_profit_margin,
    ):
        signal = detector(product)
        if signal is not None:
            results.append(signal)

    results.extend(analyze_trends(product))
    return results
