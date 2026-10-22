"""Tests for agent graph snapshot persistence."""

import json
from pathlib import Path

import pytest

from strix.tools.agents_graph import agents_graph_actions as graph


@pytest.fixture
def _clean_graph(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(graph, "_agent_graph", {"nodes": {}, "edges": []})
    monkeypatch.setattr(graph, "_root_agent_id", None)

    class _FakeTracer:
        def get_run_dir(self) -> Path:
            return tmp_path

    monkeypatch.setattr("strix.telemetry.tracer.get_global_tracer", _FakeTracer)


def _add_node(agent_id: str, status: str) -> None:
    graph._agent_graph["nodes"][agent_id] = {
        "agent_id": agent_id,
        "name": f"agent-{agent_id}",
        "task": "test something",
        "status": status,
        "parent_id": None,
        "state": object(),  # runtime state must be excluded from snapshots
    }


@pytest.mark.usefixtures("_clean_graph")
def test_persist_writes_loadable_snapshot(tmp_path: Path) -> None:
    _add_node("a1", "running")
    graph._agent_graph["edges"].append(("root", "a1", "spawned"))
    graph.persist_agent_graph()

    snapshot_file = tmp_path / "agents_graph.json"
    assert snapshot_file.exists()
    data = json.loads(snapshot_file.read_text(encoding="utf-8"))
    assert data["nodes"]["a1"]["status"] == "running"
    assert "state" not in data["nodes"]["a1"]

    loaded = graph.load_agent_graph_snapshot(tmp_path)
    assert loaded is not None
    assert loaded["nodes"]["a1"]["name"] == "agent-a1"


@pytest.mark.usefixtures("_clean_graph")
def test_persist_is_atomic_no_tmp_left_behind(tmp_path: Path) -> None:
    _add_node("a1", "completed")
    graph.persist_agent_graph()
    assert not (tmp_path / "agents_graph.json.tmp").exists()


def test_load_missing_snapshot_returns_none(tmp_path: Path) -> None:
    assert graph.load_agent_graph_snapshot(tmp_path) is None


def test_persist_without_tracer_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("strix.telemetry.tracer.get_global_tracer", lambda: None)
    graph.persist_agent_graph()  # must not raise
