"""Community Detection and Subsystem Clustering for Godot Graph.

Uses modularity-based community detection (Louvain or Greedy Modularity) to
partition game nodes into semantic subsystems (e.g. Combat, UI/HUD, Movement, Singletons).
"""
from __future__ import annotations

from typing import Dict, List, Set, Any
import networkx as nx
from networkx.algorithms.community import louvain_communities, greedy_modularity_communities


def detect_communities(graph: nx.DiGraph) -> Dict[int, List[str]]:
    """Detect communities in the graph and return community_id -> list of node IDs."""
    if graph.number_of_nodes() == 0:
        return {}

    # Convert to undirected graph for community detection
    undirected = graph.to_undirected()

    try:
        raw_communities = louvain_communities(undirected, seed=42)
    except Exception:
        try:
            raw_communities = list(greedy_modularity_communities(undirected))
        except Exception:
            # Fallback: connected components
            raw_communities = list(nx.connected_components(undirected))

    communities: Dict[int, List[str]] = {}
    for cid, comm in enumerate(raw_communities):
        # Sort nodes by degree within community
        sorted_nodes = sorted(comm, key=lambda n: graph.degree(n), reverse=True)
        communities[cid] = sorted_nodes

    return communities


def label_communities(graph: nx.DiGraph, communities: Dict[int, List[str]]) -> Dict[int, str]:
    """Generate meaningful labels for game engine communities based on prominent node types."""
    labels: Dict[int, str] = {}

    for cid, nids in communities.items():
        kinds: Dict[str, int] = {}
        names: List[str] = []

        for nid in nids[:10]:
            data = graph.nodes.get(nid, {})
            label = data.get("label", "").lower()
            kind = data.get("kind", "")
            kinds[kind] = kinds.get(kind, 0) + 1

            clean_name = label.split(":")[-1].split(".")[-1]
            if clean_name and clean_name not in ("gd", "tscn", "res"):
                names.append(clean_name)

        # Keyword heuristics tailored to Godot games
        haystack = " ".join(names).lower()
        if any(w in haystack for w in ("player", "character", "movement", "controller", "input")):
            labels[cid] = "Player & Movement Subsystem"
        elif any(w in haystack for w in ("enemy", "combat", "damage", "health", "weapon", "bullet", "hurtbox")):
            labels[cid] = "Combat & Damage System"
        elif any(w in haystack for w in ("hud", "ui", "menu", "gui", "button", "screen", "label")):
            labels[cid] = "UI & HUD Interface"
        elif any(w in haystack for w in ("manager", "eventbus", "autoload", "game", "global", "singleton")):
            labels[cid] = "Core Singletons & Event Bus"
        elif any(w in haystack for w in ("audio", "sound", "music", "sfx")):
            labels[cid] = "Audio & Sound System"
        elif any(w in haystack for w in ("level", "world", "spawner", "map", "tilemap")):
            labels[cid] = "World & Level Progression"
        else:
            primary_name = names[0].capitalize() if names else f"Subsystem {cid}"
            labels[cid] = f"{primary_name} Module"

    return labels
