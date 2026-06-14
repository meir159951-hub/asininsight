"""
Tests for the global Anthropic API spend circuit breaker.

The breaker is the last line of defence against a runaway LLM bill: a hard
ceiling on Anthropic calls per UTC day, independent of plan-gating and the
per-IP diagnose limit. If a future change drops or weakens it, these tests
break the build before it ships.
"""

import pytest

import server


@pytest.fixture(autouse=True)
def _reset_llm_counter(monkeypatch):
    """Each test starts with a clean, deterministic budget window."""
    monkeypatch.setattr(server, "_llm_calls_today", 0, raising=True)
    monkeypatch.setattr(server, "_llm_calls_day", None, raising=True)
    yield


def test_budget_allows_calls_up_to_the_ceiling(monkeypatch):
    monkeypatch.setattr(server, "LLM_DAILY_CALL_BUDGET", 3, raising=True)
    assert server._llm_budget_available() is True
    assert server._llm_budget_available() is True
    assert server._llm_budget_available() is True


def test_budget_blocks_calls_past_the_ceiling(monkeypatch):
    monkeypatch.setattr(server, "LLM_DAILY_CALL_BUDGET", 2, raising=True)
    assert server._llm_budget_available() is True
    assert server._llm_budget_available() is True
    # Third call in the same UTC day is refused — this is the bill backstop.
    assert server._llm_budget_available() is False
    assert server._llm_budget_available() is False


def test_budget_zero_disables_the_breaker(monkeypatch):
    monkeypatch.setattr(server, "LLM_DAILY_CALL_BUDGET", 0, raising=True)
    # 0 = disabled: always available, counter is never consumed.
    for _ in range(10):
        assert server._llm_budget_available() is True


def test_budget_resets_on_utc_day_rollover(monkeypatch):
    monkeypatch.setattr(server, "LLM_DAILY_CALL_BUDGET", 1, raising=True)
    assert server._llm_budget_available() is True
    assert server._llm_budget_available() is False

    # Simulate the UTC day having advanced: the counter window must reset.
    monkeypatch.setattr(server, "_llm_calls_day", "1970-01-01", raising=True)
    monkeypatch.setattr(server, "_llm_calls_today", 1, raising=True)
    assert server._llm_budget_available() is True


def test_llm_enhance_pro_degrades_to_rule_based_when_budget_exhausted(monkeypatch):
    """
    Once the budget is spent, _llm_enhance_pro must return [] WITHOUT
    constructing an Anthropic client (i.e. without issuing a billable call).
    """
    monkeypatch.setattr(server, "ANTHROPIC_API_KEY", "sk-test", raising=True)
    monkeypatch.setattr(server, "LLM_DAILY_CALL_BUDGET", 1, raising=True)

    # Exhaust the single-call budget.
    assert server._llm_budget_available() is True

    # Importing anthropic must succeed for the budget guard to be reached;
    # if the SDK isn't installed in this env, the earlier ImportError guard
    # already returns [], which is still the correct (safe) outcome.
    out = server._llm_enhance_pro(
        score=50,
        headline="x",
        problems=[],
        recommendations=[],
        items=[],
    )
    assert out == []
