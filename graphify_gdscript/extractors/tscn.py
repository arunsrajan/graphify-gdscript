"""Godot Scene (.tscn) Extractor for Graphify.

Parses Godot 3.x and 4.x scene text files (.tscn).
Extracts:
- Scene node hierarchy (root node and children)
- Attached GDScript scripts (via ExtResource)
- Instanced sub-scenes (PackedScene references)
- Signal connections ([connection signal="..." from="..." to="..." method="..."])
- External resources (textures, audio, materials)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


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


def parse_tag_attributes(tag_str: str) -> Dict[str, str]:
    """Parse key=value or key="value" inside an INI section tag like [node name="Foo" type="Bar"]."""
    attrs: Dict[str, str] = {}
    pattern = r'([A-Za-z0-9_]+)\s*=\s*(?:"([^"]*)"|([^\s\]]+))'
    for match in re.finditer(pattern, tag_str):
        key = match.group(1)
        val = match.group(2) if match.group(2) is not None else match.group(3)
        attrs[key] = val
    return attrs


def extract_tscn(path: Path, root: Path | None = None) -> dict:
    """Extract AST nodes and edges from a .tscn file."""
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

    def add_node(nid: str, label: str, line: int, kind: str = "scene_node", **extra) -> None:
        if nid not in seen_ids:
            seen_ids.add(nid)
            node_data = {
                "id": nid,
                "label": label,
                "kind": kind,
                "file_type": "scene",
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

    # Main scene node
    scene_nid = make_id(str_path)
    scene_name = path.stem
    add_node(scene_nid, f"Scene:{scene_name}", 1, kind="scene", scene_name=scene_name)

    # Resource registry: id -> {type, path}
    ext_resources: Dict[str, Dict[str, str]] = {}
    
    # Node tracking: node_path -> {name, type, line, script_res_id, instance_res_id, nid}
    scene_nodes: Dict[str, Dict[str, Any]] = {}
    root_node_name: str | None = None

    current_section = None
    current_node_dict: Dict[str, Any] | None = None

    for line_idx, line in enumerate(lines, 1):
        clean = line.strip()
        if not clean or clean.startswith(";"):
            continue

        # Tag lines like [node ...], [ext_resource ...], [connection ...]
        if clean.startswith("[") and clean.endswith("]"):
            tag_content = clean[1:-1]
            tag_type = tag_content.split()[0] if tag_content.split() else ""
            attrs = parse_tag_attributes(tag_content)

            current_section = tag_type

            if tag_type == "ext_resource":
                res_id = attrs.get("id")
                res_type = attrs.get("type", "")
                res_path = attrs.get("path", "")
                if res_id:
                    ext_resources[res_id] = {"type": res_type, "path": res_path, "line": line_idx}
                    # Also record node for external resource if it's a script or packed scene
                    if res_type in ("Script", "PackedScene"):
                        res_nid = make_id(res_path)
                        res_kind = "script_ref" if res_type == "Script" else "subscene_ref"
                        add_node(res_nid, res_path, line_idx, kind=res_kind, res_path=res_path)
                        add_edge(scene_nid, res_nid, "references_resource", line_idx)

            elif tag_type == "node":
                node_name = attrs.get("name", "UnnamedNode")
                node_type = attrs.get("type", "Node")
                parent = attrs.get("parent")
                instance_id = None
                
                # Check if instancing a subscene: instance=ExtResource("...")
                m_inst = re.search(r'instance=ExtResource\("?([A-Za-z0-9_]+)"?\)', tag_content)
                if m_inst:
                    instance_id = m_inst.group(1)

                if parent is None:
                    # Root node of the scene
                    root_node_name = node_name
                    node_path_str = "."
                elif parent == ".":
                    node_path_str = node_name
                else:
                    node_path_str = f"{parent}/{node_name}"

                node_nid = make_id(str_path, node_path_str)
                add_node(node_nid, f"{scene_name}:{node_path_str} ({node_type})", line_idx, kind="scene_node",
                         node_name=node_name, godot_type=node_type, scene_node_path=node_path_str)
                add_edge(scene_nid, node_nid, "contains_node", line_idx)

                # Parent-child edge
                if parent is not None:
                    parent_path_key = "." if parent == "." else parent
                    if parent_path_key in scene_nodes:
                        parent_nid = scene_nodes[parent_path_key]["nid"]
                        add_edge(parent_nid, node_nid, "child_node", line_idx)

                # Subscene instance edge
                if instance_id and instance_id in ext_resources:
                    sub_path = ext_resources[instance_id]["path"]
                    sub_nid = make_id(sub_path)
                    add_node(sub_nid, sub_path, line_idx, kind="subscene_ref", res_path=sub_path)
                    add_edge(node_nid, sub_nid, "instantiates_scene", line_idx)

                current_node_dict = {
                    "name": node_name,
                    "type": node_type,
                    "parent": parent,
                    "path": node_path_str,
                    "nid": node_nid,
                    "line": line_idx,
                }
                scene_nodes[node_path_str] = current_node_dict

            elif tag_type == "connection":
                # Signal connection: [connection signal="timeout" from="Timer" to="." method="_on_timer_timeout"]
                signal_name = attrs.get("signal", "")
                from_node = attrs.get("from", ".")
                to_node = attrs.get("to", ".")
                method_name = attrs.get("method", "")

                from_key = from_node if from_node in scene_nodes else ("." if from_node in (".", "") else from_node)
                to_key = to_node if to_node in scene_nodes else ("." if to_node in (".", "") else to_node)

                from_nid = scene_nodes[from_key]["nid"] if from_key in scene_nodes else make_id(str_path, from_node)
                to_nid = scene_nodes[to_key]["nid"] if to_key in scene_nodes else make_id(str_path, to_node)

                # Connect signal
                sig_nid = make_id("signal", signal_name)
                add_node(sig_nid, f"Signal:{signal_name}", line_idx, kind="signal_ref")
                add_edge(from_nid, sig_nid, "emits", line_idx)

                if method_name:
                    handler_nid = make_id(str_path, to_node, method_name)
                    add_node(handler_nid, f"{to_node}.{method_name}", line_idx, kind="signal_handler", method=method_name)
                    add_edge(sig_nid, handler_nid, "connects_to", line_idx, context=f"tscn_connection:{signal_name}->{method_name}")
                    add_edge(to_nid, handler_nid, "contains", line_idx)

        elif current_section == "node" and current_node_dict:
            # Check for script attachment: script = ExtResource("...")
            m_script = re.search(r'script\s*=\s*ExtResource\("?([A-Za-z0-9_]+)"?\)', clean)
            if m_script:
                res_id = m_script.group(1)
                if res_id in ext_resources:
                    script_info = ext_resources[res_id]
                    script_path = script_info["path"]
                    script_nid = make_id(script_path)
                    add_node(script_nid, script_path, line_idx, kind="script", res_path=script_path)
                    add_edge(current_node_dict["nid"], script_nid, "attaches_script", line_idx)
                    # Also link scene directly to its root script
                    if current_node_dict["path"] == ".":
                        add_edge(scene_nid, script_nid, "root_script", line_idx)

    return {
        "nodes": nodes,
        "edges": edges,
        "input_tokens": len(content.split()),
        "output_tokens": 0,
        "file": str_path,
    }
