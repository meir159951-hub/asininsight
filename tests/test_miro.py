"""
Tests for miro.py — the lead orchestrator agent.

Miro coordinates the specialist agents (Listing Audit + PPC) and merges
their findings into one cross-domain priority list. These tests pin the
orchestration contract: agents run only when their input is present,
findings normalize correctly, and the merged ranking puts the most urgent
(and, within a tier, the most valuable) action first.
"""

import miro


# ──────────────────────────────────────────────────────────────────────────
#  Agent gating: a runner returns None when its input is absent
# ──────────────────────────────────────────────────────────────────────────

def test_audit_agent_skips_without_store():
    assert miro.run_audit_agent({}) is None


def test_ppc_agent_skips_without_snapshots():
    assert miro.run_ppc_agent({}) is None


def test_miro_runs_only_agents_with_input():
    # Only PPC input present -> only the PPC agent reports back.
    import mock_ppc_data
    briefing = miro.default_miro().run(
        {"snapshots": mock_ppc_data.build_snapshot_payload()}
    )
    names = {a.name for a in briefing.agents}
    assert names == {"PPC"}


# ──────────────────────────────────────────────────────────────────────────
#  Normalization: specialist output maps onto the shared Finding shape
# ──────────────────────────────────────────────────────────────────────────

def test_audit_findings_carry_priority_and_ref():
    import audit_engine
    store = audit_engine.load_store(audit_engine.DEFAULT_INPUT)
    result = miro.run_audit_agent({"store": store})
    assert result is not None
    assert result.findings, "demo store should surface audit findings"
    for f in result.findings:
        assert f.agent == "Listing Audit"
        assert f.priority in miro.PRIORITY_RANK
        assert f.ref  # ASIN should be attached for traceability


def test_ppc_findings_carry_dollar_impact():
    import mock_ppc_data
    result = miro.run_ppc_agent(
        {"snapshots": mock_ppc_data.build_snapshot_payload()}
    )
    assert result is not None
    assert result.findings
    assert any(f.impact_usd and f.impact_usd > 0 for f in result.findings)


# ──────────────────────────────────────────────────────────────────────────
#  Merge + rank: one priority list across both domains
# ──────────────────────────────────────────────────────────────────────────

def test_priorities_sorted_by_priority_then_dollars():
    import audit_engine, mock_ppc_data
    context = {
        "store": audit_engine.load_store(audit_engine.DEFAULT_INPUT),
        "snapshots": mock_ppc_data.build_snapshot_payload(),
    }
    briefing = miro.default_miro().run(context)
    keys = [f.sort_key() for f in briefing.priorities]
    assert keys == sorted(keys), "priorities must be ranked, most urgent first"


def test_top_n_caps_the_priority_list():
    import audit_engine, mock_ppc_data
    context = {
        "store": audit_engine.load_store(audit_engine.DEFAULT_INPUT),
        "snapshots": mock_ppc_data.build_snapshot_payload(),
    }
    briefing = miro.Miro(top_n=3).run(context)
    assert len(briefing.priorities) <= 3


def test_briefing_serializes_and_renders():
    import audit_engine, mock_ppc_data
    context = {
        "store": audit_engine.load_store(audit_engine.DEFAULT_INPUT),
        "snapshots": mock_ppc_data.build_snapshot_payload(),
    }
    briefing = miro.default_miro().run(context)
    as_dict = briefing.to_dict()
    assert "headline" in as_dict and as_dict["agents"]
    text = briefing.render_text()
    assert "MIRO" in text


def test_new_agent_plugs_in_without_changing_merge():
    # A made-up specialist proves the registration contract: register a
    # runner that emits a critical finding and Miro ranks it to the top.
    def inventory_agent(context):
        if not context.get("inventory"):
            return None
        return miro.AgentResult(
            name="Inventory",
            headline="1 stockout risk",
            findings=[
                miro.Finding(
                    agent="Inventory",
                    area="Stockout",
                    priority="critical",
                    title="SKU-1 runs out in 3 days",
                    detail="3 days of cover left.",
                    recommendation="Reorder now.",
                    impact_usd=None,
                    ref="SKU-1",
                )
            ],
        )

    m = miro.Miro().register("Inventory", inventory_agent)
    briefing = m.run({"inventory": [{"sku": "SKU-1"}]})
    assert briefing.priorities[0].agent == "Inventory"
    assert briefing.priorities[0].priority == "critical"
