"""Godot project.godot Extractor for Graphify.

Parses project.godot configuration files.
Extracts:
- Project root node and metadata
- Main starting scene
- Autoload Singletons (Global classes/scenes like GameManager, EventBus)
- Global configurations and input actions
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


def extract_project_godot(path: Path, root: Path | None = None) -> dict:
    """Extract AST nodes and edges from project.godot."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {"nodes": [], "edges": [], "input_tokens": 0, "output_tokens": 0}

    lines = content.splitlines()
    str_path = str(path.as_posix() if hasattr(path, "as_posix") else path)
    
    nodes: List[dict] = []
    edges: List[dict] = []
    seen_ids: Set[str] = set()

    def add_node(nid: str, label: str, line: int, kind: str = "project", **extra) -> None:
        if nid not in seen_ids:
            seen_ids.add(nid)
            node_data = {
                "id": nid,
                "label": label,
                "kind": kind,
                "file_type": "config",
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

    project_name = path.parent.name or "GodotProject"
    project_nid = make_id(str_path)
    add_node(project_nid, f"Project:{project_name}", 1, kind="project_root", project_name=project_name)

    current_section = None
    autoloads: Dict[str, str] = {}
    main_scene: str | None = None

    for line_idx, line in enumerate(lines, 1):
        clean = line.strip()
        if not clean or clean.startswith(";"):
            continue

        if clean.startswith("[") and clean.endswith("]"):
            current_section = clean[1:-1].strip()
            continue

        if "=" in clean:
            k, v = clean.split("=", 1)
            key = k.strip().strip('"\'')
            val = v.strip().strip('"\'')

            if current_section == "application":
                if key == "config/name":
                    project_name = val
                elif key == "run/main_scene":
                    main_scene = val
                    main_scene_nid = make_id(val)
                    add_node(main_scene_nid, f"MainScene:{val}", line_idx, kind="main_scene", res_path=val)
                    add_edge(project_nid, main_scene_nid, "starts_with", line_idx, weight=2.0)

            elif current_section == "autoload":
                # GameManager="*res://scripts/game_manager.gd"
                auto_name = key
                raw_path = val.lstrip("*")
                autoloads[auto_name] = raw_path

                auto_nid = make_id("autoload", auto_name)
                target_res_nid = make_id(raw_path)

                add_node(auto_nid, f"Autoload:{auto_name}", line_idx, kind="autoload_singleton",
                         singleton_name=auto_name, res_path=raw_path)
                add_edge(project_nid, auto_nid, "registers_autoload", line_idx, weight=2.0)
                
                # Edge to the implementation script or scene
                add_node(target_res_nid, raw_path, line_idx, kind="script" if raw_path.endswith(".gd") else "scene", res_path=raw_path)
                add_edge(auto_nid, target_res_nid, "implemented_by", line_idx)

    return {
        "nodes": nodes,
        "edges": edges,
        "input_tokens": len(content.split()),
        "output_tokens": 0,
        "file": str_path,
        "project_name": project_name,
        "main_scene": main_scene,
        "autoloads": autoloads,
    }
