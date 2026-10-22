"""Community Detection and Subsystem Clustering for Godot Graph.

Uses modularity-based community detection (Louvain or Greedy Modularity) to
partition game nodes into semantic subsystems (e.g. Combat, UI/HUD, Movement, Singletons).
"""
from __future__ import annotations

import re
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

    # Communities come back as sets, whose order changes with Python's hash seed. Sort
    # nodes by degree (ties by id) and communities by size, so ids, labels and the
    # exported graph.json are the same on every run.
    ordered = [sorted(comm, key=lambda n: (-graph.degree(n), str(n))) for comm in raw_communities]
    ordered.sort(key=lambda nodes: (-len(nodes), str(nodes[0])))
    return {cid: nodes for cid, nodes in enumerate(ordered)}


# Nodes that name a community, most telling first.
_ANCHOR_PRIORITY = {"autoload_singleton": 4, "class": 3, "scene": 2, "resource": 1}

_UI_TYPES = {
    "control", "label", "button", "progressbar", "margincontainer", "vboxcontainer",
    "hboxcontainer", "gridcontainer", "panel", "panelcontainer", "texturerect", "richtextlabel",
    "canvaslayer", "lineedit", "textureprogressbar", "colorrect", "container", "itemlist",
}

# Role keywords, matched against whole words of member names and Godot node types.
# Entity names such as "player" or "enemy" are deliberately absent: they appear in
# every subsystem (player_damaged, active_player, PlayerInstance) and say nothing
# about what a subsystem does. List order breaks ties.
_ROLES = [
    ("Core Singletons", {"manager", "singleton", "autoload", "bus", "eventbus", "global", "game",
                         "score", "lives", "life", "restart", "state", "save", "settings", "pause"}),
    ("UI", {"hud", "ui", "gui", "menu", "button", "label", "screen", "panel", "dialog", "bar",
            "tooltip", "popup", *_UI_TYPES}),
    ("Combat", {"damage", "health", "hurtbox", "hitbox", "attack", "weapon", "bullet", "projectile",
                "fire", "shoot", "die", "death", "dead", "defeat", "kill", "gun", "ammo", "hit"}),
    ("Movement", {"move", "movement", "velocity", "speed", "jump", "gravity", "direction", "input",
                  "physics", "characterbody2d", "characterbody3d", "controller", "navigation", "dash"}),
    ("Audio", {"audio", "sound", "music", "sfx", "audiostreamplayer", "audiostreamplayer2d",
               "audiostreamplayer3d"}),
    ("World", {"level", "world", "spawner", "spawn", "map", "tilemap", "terrain", "room", "wave"}),
    ("Data", set()),  # scored from .tres resource nodes below
]

# Fallback role from what most of a community's nodes are.
_KIND_ROLES = {"scene_node": "Scene Tree", "function": "Logic", "static_func": "Logic",
               "signal": "Signals", "signal_ref": "Signals", "resource": "Data"}


def _name_words(data: dict) -> List[str]:
    """Words of a node's own name, without the owner prefix repeated on every member
    (``Enemy.take_damage`` -> take, damage), plus its Godot node type."""
    label = re.sub(r"\s*\([^)]*\)\s*$", "", str(data.get("label", "")))  # "Hitbox (Area2D)"
    if not label.startswith(("$", "%", "res://")):
        label = label.split(":")[-1]           # "Signal:health_changed", "enemy:Hitbox"
        if "/" not in label:
            label = label.split(".")[-1]       # "Enemy.take_damage"
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", label)  # camelCase -> words
    words = [w.lower() for w in re.split(r"[^A-Za-z0-9]+", spaced) if w]
    if data.get("godot_type"):
        words.append(str(data["godot_type"]).lower())
    return words


def _matches(word: str, keywords: Set[str]) -> bool:
    # Whole words, plus simple suffixes for longer keywords: damaged, defeated, spawner.
    return word in keywords or any(len(k) >= 4 and word.startswith(k) for k in keywords)


def _role(graph: nx.DiGraph, nids: List[str]) -> str:
    scores = {name: 0.0 for name, _ in _ROLES}
    kind_counts: Dict[str, int] = {}
    for nid in nids:
        data = graph.nodes.get(nid, {})
        kind = data.get("kind", "")
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        words = _name_words(data)
        for name, keywords in _ROLES:
            if keywords and any(_matches(w, keywords) for w in words):
                scores[name] += 1  # once per node, so long paths do not count extra
        if kind in ("autoload_singleton", "autoload_ref"):
            scores["Core Singletons"] += 2
        elif kind == "project_root":
            scores["Core Singletons"] += 1
        elif kind == "resource":
            scores["Data"] += 2

    best = max(_ROLES, key=lambda role: scores[role[0]])[0]  # max() keeps list order on ties
    if scores[best] >= 2:
        return best
    dominant = max(kind_counts, key=kind_counts.get) if kind_counts else ""
    return _KIND_ROLES.get(dominant, "")


def _anchor_name(data: dict) -> str:
    kind = data.get("kind")
    if kind == "autoload_singleton":
        return str(data.get("singleton_name") or data.get("label", "").replace("Autoload:", ""))
    if kind == "scene":
        return f"{data.get('scene_name') or data.get('label', '').replace('Scene:', '')}.tscn"
    if kind == "resource":
        return f"{data.get('resource_name') or data.get('label', '').replace('Resource:', '')}.tres"
    return str(data.get("label", ""))


def _anchors(graph: nx.DiGraph, nids: List[str]) -> List[str]:
    """Distinct names of the classes, autoloads, scenes and resources that define a community."""
    ranked = sorted(
        (nid for nid in nids if graph.nodes.get(nid, {}).get("kind") in _ANCHOR_PRIORITY),
        key=lambda nid: (-_ANCHOR_PRIORITY[graph.nodes[nid]["kind"]], -graph.degree(nid), _anchor_name(graph.nodes[nid])),
    )
    names: List[str] = []
    for nid in ranked:
        name = _anchor_name(graph.nodes[nid])
        if name and name not in names:
            names.append(name)
    if names:
        return names
    # No defining node: fall back to the file most of the community comes from.
    files: Dict[str, int] = {}
    for nid in nids:
        source = graph.nodes.get(nid, {}).get("source_file", "")
        if source:
            base = source.replace("\\", "/").rsplit("/", 1)[-1]
            files[base] = files.get(base, 0) + 1
    if files:
        return [max(files, key=files.get)]
    return [str(graph.nodes[nids[0]].get("label", nids[0]))] if nids else []


def label_communities(graph: nx.DiGraph, communities: Dict[int, List[str]]) -> Dict[int, str]:
    """Name each community after its defining classes / autoloads / scenes plus its role,
    e.g. "Enemy (Combat)", "EventBus & GameManager (Core Singletons)", "hud.tscn (UI)".
    Labels are unique within a graph."""
    anchors: Dict[int, List[str]] = {}
    roles: Dict[int, str] = {}
    for cid, nids in communities.items():
        anchors[cid] = _anchors(graph, nids) or [f"Subsystem {cid}"]
        roles[cid] = _role(graph, nids)

    def render(cid: int, n_anchors: int) -> str:
        head = " & ".join(anchors[cid][:n_anchors])
        return f"{head} ({roles[cid]})" if roles[cid] else head

    labels = {cid: render(cid, 2) for cid in communities}
    # Disambiguate collisions: name more of each community's anchors, then number them.
    for n_anchors in (3, 4):
        clashing = [cid for cid, text in labels.items() if list(labels.values()).count(text) > 1]
        for cid in clashing:
            labels[cid] = render(cid, n_anchors)
    seen: Dict[str, int] = {}
    for cid in communities:
        text = labels[cid]
        seen[text] = seen.get(text, 0) + 1
        if seen[text] > 1:
            labels[cid] = f"{text} #{seen[text]}"
    return labels
