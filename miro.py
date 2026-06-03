"""
miro.py — the lead orchestrator agent.

Miro is the top-level agent for the business. It does not analyze raw data
itself; it coordinates the specialist agents and merges their output into a
single prioritized briefing — one "what should I do next" view across the
whole company.

Today two specialists run under Miro:
- Listing Audit  (audit_engine.py)   — listing health and conversion issues
- PPC            (ppc_suggestions.py) — advertising waste and growth upside

Design
------
Each specialist is wrapped as an agent runner: given a shared context, it
returns a normalized `AgentResult` (a one-line headline plus a list of
`Finding`s), or None when its input isn't present. Miro runs the registered
agents, collects their findings, ranks them into one cross-domain priority
list, and produces a `Briefing`.

Adding a new agent (inventory, pricing, reviews, ...) is just writing a
runner that returns `Finding`s and registering it — Miro's merge/rank logic
stays unchanged.

Pure and dependency-free: deterministic, no DB, no network. The web layer
(server.py / ppc_agent.py) can call into `default_miro().run(context)` and
render the result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import audit_engine
import ppc_suggestions


# Shared priority vocabulary used across every agent so findings from
# different domains can be ranked against each other.
PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


@dataclass
class Finding:
    """A single normalized action surfaced by a specialist agent."""

    agent: str               # which sub-agent produced it ("Listing Audit", "PPC")
    area: str                # sub-domain, e.g. "Conversion", "Wasted Spend"
    priority: str            # critical | high | medium | low
    title: str               # short headline
    detail: str              # why it matters
    recommendation: str      # what to do about it
    impact_usd: float | None = None  # dollar impact when known, else None
    ref: str = ""            # ASIN / keyword id for traceability

    def sort_key(self) -> tuple[int, float]:
        # Higher priority first; within a priority, larger dollar impact first.
        return (PRIORITY_RANK.get(self.priority, 99), -(self.impact_usd or 0.0))


@dataclass
class AgentResult:
    """What a specialist agent reports back to Miro."""

    name: str
    headline: str
    findings: list[Finding] = field(default_factory=list)


# A runner takes Miro's shared context and returns its result, or None when
# the context doesn't contain the input this agent needs.
AgentRunner = Callable[[dict[str, Any]], "AgentResult | None"]


# --------------------------------------------------------------------------
# Specialist agent #1: Listing Audit (wraps audit_engine.py)
# --------------------------------------------------------------------------

def run_audit_agent(context: dict[str, Any]) -> AgentResult | None:
    store = context.get("store")
    if not store:
        return None

    products = store.get("products", []) or []
    issues: list[audit_engine.Issue] = []
    for product in products:
        issues.extend(audit_engine.evaluate_product(product))

    score = audit_engine.calculate_store_score(products, issues)
    label = audit_engine.health_label(score)

    findings = [
        Finding(
            agent="Listing Audit",
            area=issue.area,
            priority=issue.severity,
            title=f"{issue.product_title}: {issue.area} issue",
            detail=issue.reason,
            recommendation=issue.recommendation,
            impact_usd=None,  # audit issues are qualitative, not dollar-scored
            ref=issue.asin,
        )
        for issue in audit_engine.build_priority_actions(issues)
    ]

    headline = (
        f"Listing health {score}/100 ({label}) — "
        f"{len(issues)} issue(s) across {len(products)} product(s)"
    )
    return AgentResult(name="Listing Audit", headline=headline, findings=findings)


# --------------------------------------------------------------------------
# Specialist agent #2: PPC (wraps ppc_suggestions.py)
# --------------------------------------------------------------------------

# Human-readable labels and a priority floor per PPC rule type.
_PPC_AREA = {
    "spend_no_sales":      "Wasted Spend",
    "high_acos":           "High ACoS",
    "bid_too_high":        "Overbidding",
    "scale_profitable":    "Growth",
    "promote_search_term": "Growth",
}
_PPC_SAVINGS_TYPES = set(ppc_suggestions.SAVINGS_RULE_TYPES)


def _ppc_priority(suggestion: dict[str, Any]) -> str:
    """Map a PPC suggestion to the shared priority vocabulary.

    Waste-cutting actions (real money saved) outrank growth bets. Confidence
    nudges a savings action between high and medium.
    """
    stype = suggestion.get("suggestion_type", "")
    confidence = suggestion.get("confidence", "medium")
    if stype in _PPC_SAVINGS_TYPES:
        return "high" if confidence == "high" else "medium"
    return "low"  # growth opportunities: upside, not urgent


def run_ppc_agent(context: dict[str, Any]) -> AgentResult | None:
    snapshots = context.get("snapshots")
    if not snapshots:
        return None

    suggestions = ppc_suggestions.analyze(snapshots)
    savings = ppc_suggestions.savings_total(suggestions)
    growth = ppc_suggestions.growth_opportunity_total(suggestions)

    findings = []
    for s in suggestions:
        kw_text = (s.get("current_value") or {}).get("keyword_text", "") or "keyword"
        findings.append(
            Finding(
                agent="PPC",
                area=_PPC_AREA.get(s.get("suggestion_type", ""), "PPC"),
                priority=_ppc_priority(s),
                title=f"'{kw_text}': {_PPC_AREA.get(s.get('suggestion_type',''), 'PPC')}",
                detail=s.get("reason", ""),
                recommendation=_ppc_recommendation(s),
                impact_usd=float(s.get("estimated_savings", 0) or 0),
                ref=str(s.get("keyword_id") or ""),
            )
        )

    headline = (
        f"PPC: ${savings:,.2f} to save now, ${growth:,.2f} growth upside "
        f"across {len(suggestions)} suggestion(s)"
    )
    return AgentResult(name="PPC", headline=headline, findings=findings)


def _ppc_recommendation(suggestion: dict[str, Any]) -> str:
    proposed = suggestion.get("proposed_value") or {}
    if proposed.get("state") == "PAUSED":
        return "Pause this keyword to stop the bleed; re-enable after the listing improves."
    if "bid" in proposed:
        return f"Adjust bid to ${proposed['bid']}."
    stype = suggestion.get("suggestion_type", "")
    if stype == "scale_profitable":
        return "Raise the bid to capture more profitable volume."
    if stype == "promote_search_term":
        return "Promote this converting search term to an exact-match keyword."
    return "Review and apply the proposed change."


# --------------------------------------------------------------------------
# Miro: the orchestrator
# --------------------------------------------------------------------------

@dataclass
class Briefing:
    """Miro's merged, cross-domain output."""

    agents: list[AgentResult]
    priorities: list[Finding]

    def headline(self) -> str:
        total_savings = sum(
            f.impact_usd or 0.0
            for f in self.priorities
            if f.agent == "PPC" and (f.impact_usd or 0) > 0
        )
        crit = sum(1 for f in self.priorities if f.priority in ("critical", "high"))
        return (
            f"Miro reviewed {len(self.agents)} agent(s): "
            f"{crit} high-priority action(s), ${total_savings:,.2f} on the table."
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "headline": self.headline(),
            "agents": [
                {"name": a.name, "headline": a.headline, "findings": len(a.findings)}
                for a in self.agents
            ],
            "priorities": [
                {
                    "agent": f.agent,
                    "area": f.area,
                    "priority": f.priority,
                    "title": f.title,
                    "detail": f.detail,
                    "recommendation": f.recommendation,
                    "impact_usd": f.impact_usd,
                    "ref": f.ref,
                }
                for f in self.priorities
            ],
        }

    def render_text(self) -> str:
        lines = ["=" * 70, f"  MIRO — Company Briefing", "=" * 70, ""]
        lines.append(self.headline())
        lines.append("")
        lines.append("Agents under Miro:")
        for a in self.agents:
            lines.append(f"  • {a.name}: {a.headline}")
        lines.append("")
        lines.append("Top priorities across the whole business:")
        if not self.priorities:
            lines.append("  (nothing actionable right now — everything looks healthy)")
        for i, f in enumerate(self.priorities, 1):
            impact = f" (${f.impact_usd:,.2f})" if f.impact_usd else ""
            lines.append(f"  {i}. [{f.priority.upper():8}] {f.agent} — {f.title}{impact}")
            lines.append(f"      → {f.recommendation}")
        lines.append("")
        return "\n".join(lines)


class Miro:
    """The lead agent: registers specialists and merges their findings."""

    NAME = "Miro"

    def __init__(self, top_n: int = 7) -> None:
        self.top_n = top_n
        self._agents: list[tuple[str, AgentRunner]] = []

    def register(self, name: str, runner: AgentRunner) -> "Miro":
        self._agents.append((name, runner))
        return self

    def run(self, context: dict[str, Any]) -> Briefing:
        results: list[AgentResult] = []
        for _name, runner in self._agents:
            result = runner(context)
            if result is not None:
                results.append(result)

        merged: list[Finding] = []
        for r in results:
            merged.extend(r.findings)
        merged.sort(key=Finding.sort_key)

        return Briefing(agents=results, priorities=merged[: self.top_n])


def default_miro() -> Miro:
    """Miro pre-wired with the specialists that exist today."""
    return (
        Miro()
        .register("Listing Audit", run_audit_agent)
        .register("PPC", run_ppc_agent)
    )


# --------------------------------------------------------------------------
# Demo: run Miro against the bundled sample data.
#   python3 miro.py
# --------------------------------------------------------------------------

def _demo_context() -> dict[str, Any]:
    context: dict[str, Any] = {}
    try:
        context["store"] = audit_engine.load_store(audit_engine.DEFAULT_INPUT)
    except Exception:  # noqa: BLE001 — demo only, missing data is fine
        pass
    try:
        import mock_ppc_data
        context["snapshots"] = mock_ppc_data.build_snapshot_payload()
    except Exception:  # noqa: BLE001
        pass
    return context


if __name__ == "__main__":
    briefing = default_miro().run(_demo_context())
    print(briefing.render_text())
