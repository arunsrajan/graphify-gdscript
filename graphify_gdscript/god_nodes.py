"""God Node and Architectural Centrality Analysis for Godot Projects.

Identifies the critical bottleneck hubs, singletons, signal buses, and core orchestrators
in a Godot codebase using degree centrality and betweenness centrality.
"""
from __future__ import annotations

from typing import Dict, List, Any
import networkx as nx


def find_god_nodes(graph: nx.DiGraph, top_k: int = 5) -> List[Dict[str, Any]]:
    """Identify the top God Nodes in the Godot project with explanations."""
    if graph.number_of_nodes() == 0:
        return []

    degree_dict = dict(graph.degree())
    in_degree_dict = dict(graph.in_degree())
    out_degree_dict = dict(graph.out_degree())

    try:
        betweenness_dict = nx.betweenness_centrality(graph, k=min(50, graph.number_of_nodes()), seed=42)
    except Exception:
        betweenness_dict = {n: 0.0 for n in graph.nodes}

    # Rank nodes by combined degree and betweenness
    scored_nodes = []
    max_deg = max(degree_dict.values()) if degree_dict else 1

    for nid in graph.nodes:
        data = graph.nodes[nid]
        deg = degree_dict.get(nid, 0)
        in_deg = in_degree_dict.get(nid, 0)
        out_deg = out_degree_dict.get(nid, 0)
        betw = betweenness_dict.get(nid, 0.0)

        # Composite score
        score = (deg / max_deg) * 0.7 + betw * 0.3
        scored_nodes.append((nid, score, deg, in_deg, out_deg, betw))

    scored_nodes.sort(key=lambda x: x[1], reverse=True)

    results: List[Dict[str, Any]] = []
    for nid, score, deg, in_deg, out_deg, betw in scored_nodes[:top_k]:
        data = graph.nodes[nid]
        label = data.get("label", nid)
        kind = data.get("kind", "node")
        source_file = data.get("source_file", "")

        # Generate architectural explanation
        if kind == "autoload_singleton" or "autoload" in label.lower():
            role = "Global Singleton: Orchestrates state and API across all game systems"
        elif "signal" in kind or "signal" in label.lower():
            role = "Central Signal Hub: Broadcasts events across decoupled game subsystems"
        elif "scene" in kind:
            role = "Root Orchestrator Scene: Houses major child nodes and game components"
        elif in_deg > out_deg:
            role = "High-Dependency Sink: Heavily relied upon by other scripts/scenes"
        elif out_deg > in_deg:
            role = "High-Control Source: Invokes or configures numerous external components"
        else:
            role = "Core Architectural Bridge: Connects multiple gameplay mechanics"

        results.append({
            "id": nid,
            "label": label,
            "kind": kind,
            "degree": deg,
            "in_degree": in_deg,
            "out_degree": out_deg,
            "betweenness": round(betw, 4),
            "source_file": source_file,
            "architectural_role": role,
        })

    return results
