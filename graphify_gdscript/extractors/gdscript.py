"""GDScript AST Extractor for Graphify.

Extracts classes, inheritance, functions, signals, variables, node paths,
preloads/loads, signal emissions, connections, and calls from Godot GDScript (.gd) files.
Uses tree-sitter-gdscript with robust fallback scanning for high resilience.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

try:
    import tree_sitter_gdscript as tsgd
    from tree_sitter import Language, Parser
    _TS_LANGUAGE = Language(tsgd.language())
    _HAS_TREE_SITTER = True
except Exception:
    _TS_LANGUAGE = None
    _HAS_TREE_SITTER = False


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


def _read_source_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except Exception:
        return b""


def _read_text(node, source: bytes) -> str:
    if node is None:
        return ""
    try:
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def extract_gdscript(path: Path, root: Path | None = None) -> dict:
    """Extract AST nodes and edges from a .gd file.
    
    Returns a dict with:
        nodes: list of node dicts (id, label, kind, file_type, source_file, source_location, docstring, etc.)
        edges: list of edge dicts (source, target, relation, confidence, source_file, source_location, weight, context)
        metadata: dict with summary stats
    """
    source_bytes = _read_source_bytes(path)
    source_text = source_bytes.decode("utf-8", errors="replace")
    lines = source_text.splitlines()
    str_path = str(path.as_posix() if hasattr(path, "as_posix") else path)
    rel_path = str(path.relative_to(root).as_posix()) if root and path.is_relative_to(root) else path.name

    nodes: List[dict] = []
    edges: List[dict] = []
    seen_ids: Set[str] = set()

    def add_node(nid: str, label: str, line: int, kind: str = "symbol", **extra) -> None:
        if nid not in seen_ids:
            seen_ids.add(nid)
            node_data = {
                "id": nid,
                "label": label,
                "kind": kind,
                "file_type": "code",
                "language": "gdscript",
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

    file_nid = make_id(str_path)
    add_node(file_nid, rel_path, 1, kind="file")

    # Tree-sitter extraction
    class_name = path.stem
    base_class = "RefCounted"
    has_explicit_class_name = False
    
    if _HAS_TREE_SITTER and _TS_LANGUAGE is not None:
        parser = Parser(_TS_LANGUAGE)
        tree = parser.parse(source_bytes)
        root_node = tree.root_node

        # First pass: find class_name and extends
        for child in root_node.children:
            if child.type == "class_name_statement":
                # class_name <Identifier> [extends <Type>]
                for sub in child.children:
                    if sub.type == "name" or (sub.type == "identifier" and sub.prev_sibling and sub.prev_sibling.type == "class_name"):
                        class_name = _read_text(sub, source_bytes)
                        has_explicit_class_name = True
                    elif sub.type == "extends_statement":
                        type_sub = sub.child_by_field_name("type")
                        if type_sub:
                            base_class = _read_text(type_sub, source_bytes)
            elif child.type == "extends_statement":
                type_sub = child.child_by_field_name("type")
                if type_sub:
                    base_class = _read_text(type_sub, source_bytes)
                else:
                    # extends "res://..." or extends Node
                    txt = _read_text(child, source_bytes)
                    m = re.search(r'extends\s+([^\s\n#]+)', txt)
                    if m:
                        base_class = m.group(1).strip('"\'')

        class_nid = make_id(str_path, class_name)
        add_node(class_nid, class_name, 1, kind="class", base_class=base_class, explicit_name=has_explicit_class_name)
        add_edge(file_nid, class_nid, "contains", 1)

        # Base class edge
        if base_class:
            base_nid = make_id(base_class)
            add_node(base_nid, base_class, 1, kind="class_ref", external=True)
            add_edge(class_nid, base_nid, "extends", 1)

        # Walk AST for symbols and relations
        def walk_ast(n, current_class_nid: str, current_class_name: str, current_func_nid: str | None = None):
            line_no = n.start_point[0] + 1

            if n.type == "class_definition":
                # Inner class
                inner_name_node = n.child_by_field_name("name")
                inner_name = _read_text(inner_name_node, source_bytes) if inner_name_node else "InnerClass"
                inner_nid = make_id(str_path, current_class_name, inner_name)
                
                # Check inner class extends
                inner_base = "RefCounted"
                for c in n.children:
                    if c.type == "extends_statement":
                        ts = c.child_by_field_name("type")
                        if ts:
                            inner_base = _read_text(ts, source_bytes)
                
                add_node(inner_nid, f"{current_class_name}.{inner_name}", line_no, kind="inner_class", base_class=inner_base)
                add_edge(current_class_nid, inner_nid, "contains", line_no)
                if inner_base:
                    add_edge(inner_nid, make_id(inner_base), "extends", line_no)

                body = n.child_by_field_name("body")
                if body:
                    for c in body.children:
                        walk_ast(c, inner_nid, f"{current_class_name}.{inner_name}", None)
                return

            elif n.type == "signal_statement":
                # signal my_signal(arg1: int)
                name_node = n.child_by_field_name("name")
                sig_name = _read_text(name_node, source_bytes) if name_node else ""
                if not sig_name:
                    txt = _read_text(n, source_bytes)
                    m = re.search(r'signal\s+([A-Za-z0-9_]+)', txt)
                    if m:
                        sig_name = m.group(1)
                if sig_name:
                    sig_nid = make_id(str_path, current_class_name, sig_name)
                    add_node(sig_nid, f"{current_class_name}.{sig_name}", line_no, kind="signal", signal_name=sig_name)
                    add_edge(current_class_nid, sig_nid, "declares_signal", line_no)

            elif n.type == "variable_statement" or n.type == "const_statement":
                name_node = n.child_by_field_name("name")
                var_name = _read_text(name_node, source_bytes) if name_node else ""
                if var_name:
                    scope_nid = current_func_nid or current_class_nid
                    is_export = any("export" in _read_text(c, source_bytes) for c in n.children if c.type in ("annotations", "annotation"))
                    is_onready = any("onready" in _read_text(c, source_bytes) for c in n.children if c.type in ("annotations", "annotation"))
                    
                    var_nid = make_id(str_path, current_class_name, var_name)
                    if current_func_nid is None:
                        # Only track class-level member variables as graph nodes to keep graph focused
                        kind = "export_var" if is_export else ("onready_var" if is_onready else "variable")
                        add_node(var_nid, f"{current_class_name}.{var_name}", line_no, kind=kind, is_export=is_export, is_onready=is_onready)
                        add_edge(current_class_nid, var_nid, "contains", line_no)

                    # Look for node paths like $Sprite2D or %Hurtbox
                    for c in n.children:
                        if c.type == "get_node":
                            node_path_txt = _read_text(c, source_bytes)
                            node_path_clean = node_path_txt.lstrip("$%").strip('"\'')
                            path_nid = make_id("node_path", node_path_clean)
                            add_node(path_nid, node_path_txt, line_no, kind="node_reference", node_path=node_path_clean)
                            add_edge(var_nid if current_func_nid is None else current_func_nid, path_nid, "references_node", line_no)

            elif n.type == "function_definition":
                name_node = n.child_by_field_name("name")
                fn_name = _read_text(name_node, source_bytes) if name_node else "anonymous_func"
                is_static = any(_read_text(c, source_bytes) == "static" for c in n.children)
                
                fn_nid = make_id(str_path, current_class_name, fn_name)
                add_node(fn_nid, f"{current_class_name}.{fn_name}", line_no, kind="static_func" if is_static else "function", function_name=fn_name)
                add_edge(current_class_nid, fn_nid, "contains", line_no)

                body = n.child_by_field_name("body")
                if body:
                    for c in body.children:
                        walk_ast(c, current_class_nid, current_class_name, fn_nid)
                return

            elif n.type == "call":
                # Direct call e.g. move_and_slide(), preload("..."), load("...")
                fn_sub = n.child_by_field_name("function") or (n.children[0] if n.children else None)
                callee_name = _read_text(fn_sub, source_bytes) if fn_sub else ""
                
                caller_nid = current_func_nid or current_class_nid

                if callee_name in ("preload", "load"):
                    # Resource or scene loading
                    args = n.child_by_field_name("arguments")
                    arg_txt = _read_text(args, source_bytes) if args else ""
                    m = re.search(r'["\'](res://[^"\']+)["\']', arg_txt)
                    if m:
                        res_path = m.group(1)
                        res_nid = make_id(res_path)
                        res_kind = "scene_ref" if res_path.endswith(".tscn") else "resource_ref"
                        add_node(res_nid, res_path, line_no, kind=res_kind, res_path=res_path)
                        add_edge(caller_nid, res_nid, "preloads" if callee_name == "preload" else "loads", line_no)
                elif callee_name:
                    callee_nid = make_id(str_path, current_class_name, callee_name)
                    add_edge(caller_nid, callee_nid, "calls", line_no, confidence="INFERRED")

            elif n.type == "attribute":
                # Chained or member calls: e.g. GameManager.score_up(), EventBus.player_died.emit(), signal.connect(...)
                attr_txt = _read_text(n, source_bytes)
                caller_nid = current_func_nid or current_class_nid

                # Signal emission: X.emit(...) or emit_signal(...)
                if ".emit(" in attr_txt or attr_txt.endswith(".emit"):
                    # Extract target signal name
                    parts = [p.strip() for p in attr_txt.split(".")]
                    if len(parts) >= 2 and "emit" in parts[-1]:
                        sig_emitter = parts[0]
                        sig_target_name = parts[1] if len(parts) > 2 else parts[0]
                        sig_nid = make_id("signal", sig_target_name)
                        add_node(sig_nid, f"Signal:{sig_target_name}", line_no, kind="signal_ref")
                        add_edge(caller_nid, sig_nid, "emits", line_no)
                        
                        if len(parts) > 2:
                            # Autoload emitter e.g. EventBus.player_died.emit()
                            auto_nid = make_id("autoload", sig_emitter)
                            add_node(auto_nid, f"Autoload:{sig_emitter}", line_no, kind="autoload_ref")
                            add_edge(caller_nid, auto_nid, "uses_autoload", line_no)
                
                # Signal connection: X.connect(callback)
                elif ".connect(" in attr_txt:
                    parts = [p.strip() for p in attr_txt.split(".")]
                    sig_name = parts[-2] if len(parts) >= 2 else "signal"
                    # Try to extract the callback name from arguments
                    m = re.search(r'connect\(\s*([A-Za-z0-9_]+)\s*\)', attr_txt)
                    if m:
                        callback_name = m.group(1)
                        cb_nid = make_id(str_path, current_class_name, callback_name)
                        sig_nid = make_id("signal", sig_name)
                        add_node(sig_nid, f"Signal:{sig_name}", line_no, kind="signal_ref")
                        add_edge(sig_nid, cb_nid, "connects_to", line_no)

                # General member call: Object.method()
                else:
                    m = re.search(r'^([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)', attr_txt)
                    if m:
                        obj_name, method_name = m.group(1), m.group(2)
                        if obj_name not in ("self", "super"):
                            target_nid = make_id("symbol", obj_name, method_name)
                            add_node(target_nid, f"{obj_name}.{method_name}", line_no, kind="external_call", external=True)
                            add_edge(caller_nid, target_nid, "calls", line_no)

            elif n.type == "get_node":
                node_path_txt = _read_text(n, source_bytes)
                node_path_clean = node_path_txt.lstrip("$%").strip('"\'')
                path_nid = make_id("node_path", node_path_clean)
                add_node(path_nid, node_path_txt, line_no, kind="node_reference", node_path=node_path_clean)
                caller_nid = current_func_nid or current_class_nid
                add_edge(caller_nid, path_nid, "references_node", line_no)

            # Recurse for children
            for child in n.children:
                walk_ast(child, current_class_nid, current_class_name, current_func_nid)

        walk_ast(root_node, class_nid, class_name, None)

    else:
        # Regex fallback parser if tree-sitter is unavailable
        _extract_gdscript_regex(source_text, path, str_path, rel_path, file_nid, nodes, edges, seen_ids, add_node, add_edge)

    return {
        "nodes": nodes,
        "edges": edges,
        "input_tokens": len(source_text.split()),
        "output_tokens": 0,
        "file": str_path,
    }


def _extract_gdscript_regex(source_text: str, path: Path, str_path: str, rel_path: str,
                            file_nid: str, nodes: list, edges: list, seen_ids: set,
                            add_node, add_edge) -> None:
    """Resilient regex-based extractor for GDScript."""
    lines = source_text.splitlines()
    class_name = path.stem
    base_class = "RefCounted"

    # 1. Class name and extends
    for idx, line in enumerate(lines, 1):
        clean = line.strip()
        m_cn = re.match(r'^class_name\s+([A-Za-z0-9_]+)(?:\s+extends\s+([^\s\n#]+))?', clean)
        if m_cn:
            class_name = m_cn.group(1)
            if m_cn.group(2):
                base_class = m_cn.group(2).strip('"\'')
            break
        m_ext = re.match(r'^extends\s+([^\s\n#]+)', clean)
        if m_ext:
            base_class = m_ext.group(1).strip('"\'')

    class_nid = make_id(str_path, class_name)
    add_node(class_nid, class_name, 1, kind="class", base_class=base_class)
    add_edge(file_nid, class_nid, "contains", 1)
    if base_class:
        base_nid = make_id(base_class)
        add_node(base_nid, base_class, 1, kind="class_ref", external=True)
        add_edge(class_nid, base_nid, "extends", 1)

    curr_func_nid = None

    for idx, line in enumerate(lines, 1):
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue

        # Signal declaration
        m_sig = re.match(r'^signal\s+([A-Za-z0-9_]+)', clean)
        if m_sig:
            sig_name = m_sig.group(1)
            sig_nid = make_id(str_path, class_name, sig_name)
            add_node(sig_nid, f"{class_name}.{sig_name}", idx, kind="signal")
            add_edge(class_nid, sig_nid, "declares_signal", idx)
            continue

        # Function definition
        m_fn = re.match(r'^(static\s+)?func\s+([A-Za-z0-9_]+)\s*\(', clean)
        if m_fn:
            is_static = bool(m_fn.group(1))
            fn_name = m_fn.group(2)
            curr_func_nid = make_id(str_path, class_name, fn_name)
            add_node(curr_func_nid, f"{class_name}.{fn_name}", idx, kind="static_func" if is_static else "function")
            add_edge(class_nid, curr_func_nid, "contains", idx)
            continue

        # Reset func context if unindented non-comment line after func
        if not line.startswith(" ") and not line.startswith("\t") and curr_func_nid:
            if not m_fn:
                curr_func_nid = None

        caller_nid = curr_func_nid or class_nid

        # Preloads & loads
        for m_load in re.finditer(r'(preload|load)\s*\(\s*["\'](res://[^"\']+)["\']\s*\)', clean):
            callee_type, res_path = m_load.group(1), m_load.group(2)
            res_nid = make_id(res_path)
            kind = "scene_ref" if res_path.endswith(".tscn") else "resource_ref"
            add_node(res_nid, res_path, idx, kind=kind)
            add_edge(caller_nid, res_nid, "preloads" if callee_type == "preload" else "loads", idx)

        # Node paths ($Node, %Node)
        for m_node in re.finditer(r'([$%](?:[A-Za-z0-9_]+|"[^"]+"))', clean):
            node_txt = m_node.group(1)
            node_clean = node_txt.lstrip("$%").strip('"\'')
            path_nid = make_id("node_path", node_clean)
            add_node(path_nid, node_txt, idx, kind="node_reference", node_path=node_clean)
            add_edge(caller_nid, path_nid, "references_node", idx)

        # Signal emissions
        for m_emit in re.finditer(r'([A-Za-z0-9_]+)\.emit\(', clean):
            sig_name = m_emit.group(1)
            sig_nid = make_id("signal", sig_name)
            add_node(sig_nid, f"Signal:{sig_name}", idx, kind="signal_ref")
            add_edge(caller_nid, sig_nid, "emits", idx)
