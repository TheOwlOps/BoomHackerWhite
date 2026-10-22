"""Tests for the scan budget guard (BaseAgent._enforce_scan_budget)."""

from typing import Any

import pytest

from strix.agents.base_agent import BaseAgent
from strix.agents.state import AgentState


class _FakeTracer:
    def __init__(self, cost: float, scan_config: dict[str, Any] | None = None) -> None:
        self._cost = cost
        self.scan_config = scan_config or {}
        self.status_updates: list[tuple[str, str, Any]] = []

    def get_total_llm_stats(self) -> dict[str, Any]:
        return {"cost": self._cost, "input_tokens": 0, "output_tokens": 0, "requests": 1}

    def update_agent_status(self, agent_id: str, status: str, error: Any = None) -> None:
        self.status_updates.append((agent_id, status, error))


def _make_agent() -> BaseAgent:
    agent = object.__new__(BaseAgent)
    agent.state = AgentState(task="budget test", max_iterations=300)
    agent.interactive = False
    return agent


def test_no_limit_no_enforcement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BHW_MAX_SCAN_COST_USD", raising=False)
    agent = _make_agent()
    assert agent._enforce_scan_budget(_FakeTracer(cost=999.0)) is None


def test_under_budget_is_quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BHW_MAX_SCAN_COST_USD", "10")
    agent = _make_agent()
    assert agent._enforce_scan_budget(_FakeTracer(cost=5.0)) is None
    assert not agent.state.context.get("budget_warned")


def test_warning_at_eighty_percent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BHW_MAX_SCAN_COST_USD", "10")
    agent = _make_agent()
    assert agent._enforce_scan_budget(_FakeTracer(cost=8.5)) is None
    assert agent.state.context.get("budget_warned") is True
    messages = [m.get("content", "") for m in agent.state.messages]
    assert any("BUDGET WARNING" in str(m) for m in messages)


def test_grace_period_then_termination(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BHW_MAX_SCAN_COST_USD", "10")
    agent = _make_agent()
    tracer = _FakeTracer(cost=10.5)
    # First call past 100%: warning bookkeeping starts, no termination yet.
    agent.state.context["budget_warn_iteration"] = agent.state.iteration
    assert agent._enforce_scan_budget(tracer) is None
    # After the five-iteration grace period the loop must terminate.
    agent.state.iteration += 5
    result = agent._enforce_scan_budget(tracer)
    assert result is not None
    assert result["success"] is False
    assert "budget" in result["error"].lower()


def test_immediate_termination_at_125_percent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BHW_MAX_SCAN_COST_USD", "10")
    agent = _make_agent()
    result = agent._enforce_scan_budget(_FakeTracer(cost=13.0))
    assert result is not None
    assert result["success"] is False


def test_limit_from_scan_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BHW_MAX_SCAN_COST_USD", raising=False)
    agent = _make_agent()
    tracer = _FakeTracer(cost=30.0, scan_config={"max_cost_usd": 20})
    result = agent._enforce_scan_budget(tracer)
    assert result is not None
    assert result["success"] is False
