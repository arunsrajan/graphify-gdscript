"""Focused graph lookups shared by the CLI and the MCP server: signal traces,
shortest paths between symbols, and single-symbol explanations."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

import networkx as nx


def _is_reference(data: dict) -> bool:
    kind = data.get("kind", "")
    return kind.endswith("_ref") or kind == "external_call"


def _location(data: dict, root: Optional[Path]) -> str:
    source = data.get("source_file", "")
    if not source:
        return ""
    shown = Path(source).name
    if root is not None:
        try:
            shown = Path(source).resolve().relative_to(root.resolve()).as_posix()
        except (ValueError, OSError):
            pass
    loc = data.get("source_location", "")
    return f"{shown} {loc}".strip()


def find_nodes(graph: nx.DiGraph, term: str, limit: int = 5) -> List[str]:
    """Rank nodes whose label or id matches ``term``: exact > last segment > substring.

    Definitions outrank the placeholder ``*_ref`` nodes, and better-connected nodes
    win ties.
    """
    wanted = term.strip().lower()
    if not wanted:
        return []
    scored = []
    for nid, data in graph.nodes(data=True):
        label = str(data.get("label", "")).lower()
        bare = re.sub(r"\s*\(.*\)$", "", label)
        last = re.split(r"[.:/]", bare)[-1]
        if wanted in (label, bare, str(nid).lower()):
            score = 100
        elif wanted == last:
            score = 80
        elif wanted in label:
            score = 40
        else:
            continue
        if _is_reference(data):
            score -= 15
        score += min(graph.degree(nid), 10)
        scored.append((score, nid))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [nid for _, nid in scored[:limit]]


def trace_signal(graph: nx.DiGraph, signal_name: str, root: Optional[Path] = None) -> str:
    """Every declaration, emission and connection of a signal, across scripts and scenes."""
    wanted = signal_name.strip().lower()

    def node_signal_name(nid: str) -> str:
        data = graph.nodes.get(nid, {})
        if data.get("kind") == "signal":
            return (data.get("signal_name") or data.get("label", "").split(".")[-1]).lower()
        if data.get("kind") == "signal_ref":
            return data.get("label", "").replace("Signal:", "").lower()
        return ""

    lines: List[str] = []
    for u, v, data in graph.edges(data=True):
        rel = data.get("relation", "")
        if rel not in ("emits", "connects_to", "declares_signal"):
            continue
        if wanted not in (node_signal_name(u), node_signal_name(v)):
            continue
        src = graph.nodes[u].get("label", u)
        tgt = graph.nodes[v].get("label", v)
        where = _location(data, root)
        line = f"- `{src}` --[{rel}]--> `{tgt}`" + (f" ({where})" if where else "")
        if line not in lines:
            lines.append(line)

    body = "\n".join(lines) if lines else "No matching signal connections found."
    return f"## Signal Trace for: `{signal_name}`\n\n{body}"


def shortest_path(graph: nx.DiGraph, source: str, target: str, root: Optional[Path] = None) -> str:
    """The shortest chain of relations linking two symbols, ignoring edge direction."""
    sources = find_nodes(graph, source, limit=3)
    targets = find_nodes(graph, target, limit=3)
    missing = [term for term, found in ((source, sources), (target, targets)) if not found]
    if missing:
        return "No node matches " + " or ".join(f"`{m}`" for m in missing) + "."

    # Walk edges both ways, but make going against an edge cost more, so real call and
    # signal flow beats "both of these happen to use EventBus" when lengths tie.
    # (Built explicitly rather than with to_undirected(as_view=True), whose set-based
    # neighbour order made the choice between equal paths change with the hash seed.)
    walk = nx.DiGraph()
    walk.add_nodes_from(graph.nodes)
    for u, v in graph.edges:
        walk.add_edge(u, v, cost=1.0)
    for u, v in graph.edges:
        if not walk.has_edge(v, u):
            walk.add_edge(v, u, cost=1.5)

    # Best-ranked pair that is connected at all, so "Player" means the Player class
    # rather than whichever Player method happens to sit closest to the target.
    best: Optional[List[str]] = None
    for s, t in sorted(((s, t) for s in sources for t in targets if s != t),
                       key=lambda pair: sources.index(pair[0]) + targets.index(pair[1])):
        try:
            best = nx.shortest_path(walk, s, t, weight="cost")
            break
        except nx.NetworkXNoPath:
            continue
    if best is None:
        return f"No path connects `{source}` and `{target}` in the graph."

    label = lambda nid: graph.nodes[nid].get("label", nid)  # noqa: E731
    lines = [f"## Path: `{label(best[0])}` -> `{label(best[-1])}` ({len(best) - 1} hops)\n"]
    for u, v in zip(best, best[1:]):
        if graph.has_edge(u, v):
            data, arrow = graph.edges[u, v], f"--[{graph.edges[u, v].get('relation', '')}]-->"
        else:
            data, arrow = graph.edges[v, u], f"<--[{graph.edges[v, u].get('relation', '')}]--"
        where = _location(data, root)
        lines.append(f"- `{label(u)}` {arrow} `{label(v)}`" + (f" ({where})" if where else ""))
    return "\n".join(lines)


def explain_node(graph: nx.DiGraph, term: str, root: Optional[Path] = None, max_edges: int = 25) -> str:
    """One symbol with its location and every relation wired into or out of it."""
    matches = find_nodes(graph, term, limit=6)
    if not matches:
        return f"No node matches `{term}`."
    nid = matches[0]
    data = graph.nodes[nid]
    lines = [f"## `{data.get('label', nid)}` ({data.get('kind', 'node')})"]
    where = _location(data, root)
    if where:
        lines.append(f"Defined at: {where}")
    for key in ("base_class", "godot_type", "res_path", "node_path"):
        if data.get(key):
            lines.append(f"{key}: `{data[key]}`")

    def edge_lines(edges, outgoing: bool) -> List[str]:
        out = []
        for u, v, edata in list(edges)[:max_edges]:
            other = graph.nodes[v if outgoing else u].get("label", v if outgoing else u)
            arrow = f"--[{edata.get('relation', '')}]-->" if outgoing else f"<--[{edata.get('relation', '')}]--"
            loc = edata.get("source_location", "")
            out.append(f"- {arrow} `{other}`" + (f" ({loc})" if loc else ""))
        return out

    out_edges = list(graph.out_edges(nid, data=True))
    in_edges = list(graph.in_edges(nid, data=True))
    if out_edges:
        lines.append(f"\n### Outgoing ({len(out_edges)})")
        lines.extend(edge_lines(out_edges, outgoing=True))
    if in_edges:
        lines.append(f"\n### Incoming ({len(in_edges)})")
        lines.extend(edge_lines(in_edges, outgoing=False))
    others = [graph.nodes[m].get("label", m) for m in matches[1:]]
    if others:
        lines.append("\nOther matches: " + ", ".join(f"`{o}`" for o in others))
    return "\n".join(lines)
