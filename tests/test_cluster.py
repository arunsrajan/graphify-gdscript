import os
import subprocess
import sys
from pathlib import Path

import networkx as nx
import pytest

from graphify_gdscript.cluster import detect_communities, label_communities
from graphify_gdscript.graph_builder import GodotGraphBuilder

REPO = Path(__file__).resolve().parent.parent
DEMO = REPO / "examples" / "demo_godot_project"


@pytest.fixture(scope="module")
def demo():
    graph = GodotGraphBuilder(DEMO).build()
    communities = detect_communities(graph)
    return graph, communities, label_communities(graph, communities)


def test_demo_labels_are_distinct_and_descriptive(demo):
    _, _, labels = demo
    assert sorted(labels.values()) == sorted([
        "Player (Combat)",
        "EventBus & GameManager (Core Singletons)",
        "Enemy (Combat)",
        "HUD (UI)",
        "hud.tscn & main.tscn (UI)",
        "GameManager (Core Singletons)",
        "player.tscn & weapon_data.tres (Combat)",
        "enemy.tscn (Combat)",
    ])


def test_each_label_names_something_inside_its_community(demo):
    graph, communities, labels = demo
    for cid, label in labels.items():
        head = label.split(" (")[0]
        member_text = " ".join(str(graph.nodes[n].get("label", "")) for n in communities[cid])
        for name in head.split(" & "):
            assert name.replace(".tscn", "").replace(".tres", "") in member_text, (label, name)


def _graph(*members):
    """members: (node_id, label, kind[, source_file]) tuples, chained into one component."""
    g = nx.DiGraph()
    for i, (nid, label, kind, *src) in enumerate(members):
        g.add_node(nid, label=label, kind=kind, source_file=src[0] if src else "")
        if i:
            g.add_edge(members[0][0], nid, relation="contains")
    return g


def test_entity_names_do_not_decide_the_role():
    # "player" shows up in every subsystem; UI vocabulary should win here.
    g = _graph(("hud", "HUD", "class"), ("a", "HUD._on_player_damaged", "function"),
               ("b", "HUD.active_player", "variable"), ("c", "HUD.score_label", "variable"),
               ("d", "hud:Margin/HealthBar (ProgressBar)", "scene_node"),
               ("e", "hud:Margin/Menu (MarginContainer)", "scene_node"))
    g.nodes["d"]["godot_type"] = "ProgressBar"
    g.nodes["e"]["godot_type"] = "MarginContainer"
    assert label_communities(g, {0: list(g.nodes)}) == {0: "HUD (UI)"}


def test_falls_back_to_source_file_without_a_defining_node():
    g = _graph(("a", "do_thing", "function", "/p/scripts/util.gd"),
               ("b", "other_thing", "function", "/p/scripts/util.gd"))
    assert label_communities(g, {0: ["a", "b"]}) == {0: "util.gd (Logic)"}


def test_colliding_labels_are_made_unique():
    g = nx.union(_graph(("u1", "Util", "class"), ("f1", "Util.go", "function")),
                 _graph(("u2", "Util", "class"), ("f2", "Util.stop", "function")))
    labels = label_communities(g, {0: ["u1", "f1"], 1: ["u2", "f2"]})
    assert len(set(labels.values())) == 2
    assert labels[0].startswith("Util") and labels[1] == labels[0] + " #2"


def test_communities_and_labels_do_not_depend_on_hash_seed():
    script = ("from graphify_gdscript.graph_builder import GodotGraphBuilder;"
              "from graphify_gdscript.cluster import detect_communities, label_communities;"
              f"G = GodotGraphBuilder(r'{DEMO}').build(); c = detect_communities(G);"
              "print(c); print(label_communities(G, c))")
    outputs = {
        subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, cwd=REPO,
                       env={**os.environ, "PYTHONHASHSEED": seed}, check=True).stdout
        for seed in ("1", "4")
    }
    assert len(outputs) == 1
