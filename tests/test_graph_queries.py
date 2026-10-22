from pathlib import Path

import pytest

from graphify_gdscript.graph_builder import GodotGraphBuilder
from graphify_gdscript.graph_queries import explain_node, find_nodes, shortest_path, trace_signal
from graphify_gdscript.project import resolve_project_root

DEMO = Path(__file__).resolve().parent.parent / "examples" / "demo_godot_project"


@pytest.fixture(scope="module")
def graph():
    return GodotGraphBuilder(DEMO).build()


def test_find_nodes_prefers_definitions(graph):
    best = find_nodes(graph, "Player")[0]
    assert graph.nodes[best]["kind"] == "class"


def test_trace_signal_spans_scripts_and_scenes(graph):
    text = trace_signal(graph, "player_died", DEMO)
    assert "declares_signal" in text and "emits" in text and "connects_to" in text
    assert "scripts/event_bus.gd" in text


def test_shortest_path_follows_signal_wiring(graph):
    text = shortest_path(graph, "Player", "trigger_game_over", DEMO)
    assert text.startswith("## Path: `Player` -> `GameManager.trigger_game_over`")
    assert "connects_to" in text


def test_shortest_path_reports_unknown_symbols(graph):
    assert "No node matches `nope_xyz`" in shortest_path(graph, "nope_xyz", "Player")


def test_explain_lists_relations(graph):
    text = explain_node(graph, "take_damage", DEMO)
    assert "Player.take_damage" in text and "scripts/player.gd L" in text and "### Incoming" in text


def test_project_root_detection(tmp_path, monkeypatch):
    monkeypatch.delenv("GRAPHIFY_GDSCRIPT_PROJECT", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(DEMO / "scenes")
    assert resolve_project_root(None) == DEMO.resolve()
    assert resolve_project_root("${workspace.path}") == DEMO.resolve()
    assert resolve_project_root(str(tmp_path)) == tmp_path.resolve()
