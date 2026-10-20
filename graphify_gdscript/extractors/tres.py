"""Godot Resource (.tres) Extractor for Graphify.

Parses custom Godot resource files (.tres).
Links resources to their backing GDScript custom Resource classes.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Set


def normalize_id(s: str) -> str:
    """Normalize identifier for consistent graph node IDs."""
    import unicodedata
    cur = s
    for _ in range(6):
        nxt = unicodedata.normalize("NFKC", cur.casefold())
        if nxt == cur:
            break
        cur = nxt
    cur = re.sub(r"[^\w]+", "_", cur, flags=re.UNICODE)
    cur = re.sub(r"_+", "_", cur)
    return cur.strip("_")


def make_id(*parts: str) -> str:
    """Build a canonical node ID from one or more name parts."""
    return normalize_id("_".join(p.strip("_.") for p in parts if p))


def extract_tres(path: Path, root: Path | None = None) -> dict:
    """Extract AST nodes and edges from a .tres file."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {"nodes": [], "edges": [], "input_tokens": 0, "output_tokens": 0}

    lines = content.splitlines()
    str_path = str(path.as_posix() if hasattr(path, "as_posix") else path)
    rel_path = str(path.relative_to(root).as_posix()) if root and path.is_relative_to(root) else path.name

    nodes: List[dict] = []
    edges: List[dict] = []
    seen_ids: Set[str] = set()

    def add_node(nid: str, label: str, line: int, kind: str = "resource", **extra) -> None:
        if nid not in seen_ids:
            seen_ids.add(nid)
            node_data = {
                "id": nid,
                "label": label,
                "kind": kind,
                "file_type": "resource",
                "source_file": str_path,
                "source_location": f"L{line}",
            }
            node_data.update(extra)
            nodes.append(node_data)

    def add_edge(src: str, tgt: str, relation: str, line: int,
                 confidence: str = "EXTRACTED", weight: float = 1.0,
                 context: str | None = None) -> None:
        if not src or not tgt or src == tgt:
            return
        edge_data = {
            "source": src,
            "target": tgt,
            "relation": relation,
            "confidence": confidence,
            "source_file": str_path,
            "source_location": f"L{line}",
            "weight": weight,
        }
        if context:
            edge_data["context"] = context
        edges.append(edge_data)

    res_nid = make_id(str_path)
    res_name = path.stem
    add_node(res_nid, f"Resource:{res_name}", 1, kind="resource", resource_name=res_name)

    ext_scripts: Dict[str, str] = {}

    for line_idx, line in enumerate(lines, 1):
        clean = line.strip()
        if not clean or clean.startswith(";"):
            continue

        if clean.startswith("[ext_resource"):
            m_path = re.search(r'path="([^"]+)"', clean)
            m_id = re.search(r'id="([^"]+)"', clean)
            m_type = re.search(r'type="([^"]+)"', clean)
            if m_path and m_id:
                if not m_type or m_type.group(1) == "Script":
                    ext_scripts[m_id.group(1)] = m_path.group(1)

        elif "script = ExtResource(" in clean:
            m = re.search(r'script\s*=\s*ExtResource\("?([A-Za-z0-9_]+)"?\)', clean)
            if m and m.group(1) in ext_scripts:
                script_path = ext_scripts[m.group(1)]
                script_nid = make_id(script_path)
                add_node(script_nid, script_path, line_idx, kind="script", res_path=script_path)
                add_edge(res_nid, script_nid, "instance_of_script", line_idx)

    return {
        "nodes": nodes,
        "edges": edges,
        "input_tokens": len(content.split()),
        "output_tokens": 0,
        "file": str_path,
    }
