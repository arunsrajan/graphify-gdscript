import json
import re

import networkx as nx

from graphify_gdscript.visualizer import VIS_NETWORK_SRI, VIS_NETWORK_URLS, generate_html_visualization


def _render(tmp_path, graph, communities=None, labels=None, stats=None):
    out = tmp_path / "graph.html"
    generate_html_visualization(graph, communities or {0: list(graph.nodes)}, labels or {0: "Core"},
                                stats or {"estimated_raw_tokens": 10000}, out)
    return out.read_text(encoding="utf-8")


def _sample_graph():
    g = nx.DiGraph()
    g.add_node("player", label="Player", kind="class", source_file="res/player.gd", source_location="L1")
    g.add_node("hit", label="Player.take_damage", kind="function")
    g.add_edge("player", "hit", relation="contains")
    return g


def test_all_placeholders_are_filled(tmp_path):
    page = _render(tmp_path, _sample_graph())
    assert not re.search(r"__[A-Z_]+__", page)


def test_graph_data_round_trips(tmp_path):
    page = _render(tmp_path, _sample_graph())
    nodes = json.loads(re.search(r"const nodesData = (.*);\n", page).group(1))
    edges = json.loads(re.search(r"const edgesData = (.*);\n", page).group(1))
    assert {n["label"] for n in nodes} == {"Player", "Player.take_damage"}
    assert edges[0]["relation"] == "contains"


def test_vis_network_is_pinned_with_integrity(tmp_path):
    page = _render(tmp_path, _sample_graph())
    assert all("@9.1.9/" in url for url in VIS_NETWORK_URLS)
    assert json.dumps(VIS_NETWORK_URLS) in page and VIS_NETWORK_SRI in page
    assert "unpkg.com/vis-network/" not in page  # the old floating "latest" URL


def test_canvas_container_cannot_grow_past_the_viewport(tmp_path):
    # Regression: as a plain flex child the canvas grew the container on every redraw,
    # pushing the whole graph below the visible area.
    page = _render(tmp_path, _sample_graph())
    container = re.search(r"\.main-container \{([^}]*)\}", page).group(1)
    network = re.search(r"#network \{([^}]*)\}", page).group(1)
    assert "min-height: 0" in container and "overflow: hidden" in container
    assert "position: absolute" in network and "inset: 0" in network


def test_labels_cannot_break_out_of_the_page(tmp_path):
    g = nx.DiGraph()
    g.add_node("evil", label='</script><img src=x onerror=alert(1)>', kind="node_reference")
    page = _render(tmp_path, g, labels={0: "<b>Combat</b>"})
    assert "</script><img" not in page
    assert "<b>Combat</b>" not in page and "&lt;b&gt;Combat&lt;/b&gt;" in page


def test_banner_uses_the_measured_query_size(tmp_path):
    page = _render(tmp_path, _sample_graph(), stats={"estimated_raw_tokens": 896, "query_tokens": 751})
    assert "~751" in page and "16.2% SAVED" in page
