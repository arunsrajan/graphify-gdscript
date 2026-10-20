from pathlib import Path
import pytest
from graphify_gdscript.graph_builder import GodotGraphBuilder
from graphify_gdscript.cluster import detect_communities, label_communities
from graphify_gdscript.god_nodes import find_god_nodes


def test_graph_builder_on_demo_project():
    demo_path = Path(__file__).parent.parent / "examples" / "demo_godot_project"
    builder = GodotGraphBuilder(demo_path)
    G = builder.build()

    assert G.number_of_nodes() > 20
    assert G.number_of_edges() > 20

    # Verify communities
    communities = detect_communities(G)
    assert len(communities) > 0
    labels = label_communities(G, communities)
    assert len(labels) == len(communities)

    # Verify god nodes
    gods = find_god_nodes(G, top_k=5)
    assert len(gods) > 0
    assert any("Player" in g["label"] or "GameManager" in g["label"] for g in gods)
