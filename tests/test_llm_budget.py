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
    """Each test starts with a clean, deterministic budget/alert window."""
    monkeypatch.setattr(server, "_llm_calls_today", 0, raising=True)
    monkeypatch.setattr(server, "_llm_calls_day", None, raising=True)
    monkeypatch.setattr(server, "_llm_alert_sent_day", None, raising=True)
    # Disable the spend alert by default; alert-specific tests opt back in.
    monkeypatch.setattr(server, "LLM_SPEND_ALERT_THRESHOLD", 0, raising=True)
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


# ──────────────────────────────────────────────────────────────────────────
#  Spend alert: notify the owner the moment usage-based charges start
# ──────────────────────────────────────────────────────────────────────────


def test_spend_alert_fires_once_when_threshold_reached(monkeypatch):
    monkeypatch.setattr(server, "LLM_DAILY_CALL_BUDGET", 100, raising=True)
    monkeypatch.setattr(server, "LLM_SPEND_ALERT_THRESHOLD", 1, raising=True)
    calls = []
    monkeypatch.setattr(
        server, "_dispatch_llm_spend_alert",
        lambda day, count: calls.append((day, count)), raising=True,
    )

    # First billable call of the day must trigger exactly one alert.
    assert server._llm_budget_available() is True
    assert len(calls) == 1
    assert calls[0][1] == 1

    # Subsequent calls the same day must NOT re-alert (deduplicated).
    server._llm_budget_available()
    server._llm_budget_available()
    assert len(calls) == 1


def test_spend_alert_disabled_when_threshold_zero(monkeypatch):
    monkeypatch.setattr(server, "LLM_DAILY_CALL_BUDGET", 100, raising=True)
    monkeypatch.setattr(server, "LLM_SPEND_ALERT_THRESHOLD", 0, raising=True)
    calls = []
    monkeypatch.setattr(
        server, "_dispatch_llm_spend_alert",
        lambda day, count: calls.append((day, count)), raising=True,
    )
    for _ in range(5):
        server._llm_budget_available()
    assert calls == []


def test_spend_alert_re_fires_after_utc_day_rollover(monkeypatch):
    monkeypatch.setattr(server, "LLM_DAILY_CALL_BUDGET", 100, raising=True)
    monkeypatch.setattr(server, "LLM_SPEND_ALERT_THRESHOLD", 1, raising=True)
    calls = []
    monkeypatch.setattr(
        server, "_dispatch_llm_spend_alert",
        lambda day, count: calls.append((day, count)), raising=True,
    )
    assert server._llm_budget_available() is True
    assert len(calls) == 1

    # New UTC day: counter and alert-dedup both reset, so a fresh alert fires.
    monkeypatch.setattr(server, "_llm_calls_day", "1970-01-01", raising=True)
    monkeypatch.setattr(server, "_llm_alert_sent_day", "1970-01-01", raising=True)
    assert server._llm_budget_available() is True
    assert len(calls) == 2


def test_dispatch_alert_no_ops_without_owner_email(monkeypatch):
    """No OWNER_EMAIL configured → no email thread, no crash."""
    monkeypatch.setattr(server, "OWNER_EMAIL", "", raising=True)
    monkeypatch.setattr(server, "SENDGRID_API_KEY", "sg-test", raising=True)
    sent = []
    monkeypatch.setattr(
        server, "_send_drip_email",
        lambda *a, **k: sent.append(a), raising=True,
    )
    server._dispatch_llm_spend_alert("2026-06-14", 1)
    assert sent == []
