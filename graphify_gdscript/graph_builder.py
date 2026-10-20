"""Godot Knowledge Graph Builder.

Scans Godot project roots, runs extractors across .gd, .tscn, project.godot, .tres,
and resolves cross-file references, autoloads, signal connections, and scene hierarchies.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import networkx as nx

from graphify_gdscript.extractors.gdscript import extract_gdscript, make_id, normalize_id
from graphify_gdscript.extractors.tscn import extract_tscn
from graphify_gdscript.extractors.project_godot import extract_project_godot
from graphify_gdscript.extractors.tres import extract_tres


class GodotGraphBuilder:
    def __init__(self, project_path: str | Path):
        self.project_path = Path(project_path).resolve()
        self.nodes: Dict[str, dict] = {}
        self.edges: List[dict] = []
        self.graph = nx.DiGraph()
        
        # Cross-file registries
        self.classes_by_name: Dict[str, str] = {}         # class_name -> class_nid
        self.files_by_res_path: Dict[str, str] = {}       # res://... -> file_nid
        self.autoloads: Dict[str, dict] = {}              # name -> {path, nid}
        self.signals_by_name: Dict[str, List[str]] = {}   # signal_name -> [sig_nids]
        self.scenes_by_res_path: Dict[str, str] = {}      # res://... -> scene_nid

        # Token analysis
        self.total_raw_words = 0
        self.total_raw_lines = 0

    def scan_files(self) -> Dict[str, List[Path]]:
        """Collect Godot files in the project directory."""
        files: Dict[str, List[Path]] = {
            "project": [],
            "gdscript": [],
            "scene": [],
            "resource": [],
        }

        proj_file = self.project_path / "project.godot"
        if proj_file.exists():
            files["project"].append(proj_file)

        for root, dirs, filenames in os.walk(self.project_path):
            # Ignore hidden or build dirs
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("graphify-out", ".godot", "build")]
            for f in filenames:
                p = Path(root) / f
                ext = p.suffix.lower()
                if ext == ".gd":
                    files["gdscript"].append(p)
                elif ext == ".tscn":
                    files["scene"].append(p)
                elif ext == ".tres":
                    files["resource"].append(p)

        return files

    def build(self) -> nx.DiGraph:
        """Run extraction and build the full cross-referenced knowledge graph."""
        file_map = self.scan_files()

        # 1. Extract project.godot first for autoloads and main scene
        for pf in file_map["project"]:
            res = extract_project_godot(pf, root=self.project_path)
            self._merge_extraction(res)
            for auto_name, auto_path in res.get("autoloads", {}).items():
                self.autoloads[auto_name] = {
                    "path": auto_path,
                    "nid": make_id("autoload", auto_name),
                }

        # 2. Extract all GDScript files
        for gdf in file_map["gdscript"]:
            res = extract_gdscript(gdf, root=self.project_path)
            self._merge_extraction(res)
            
            # Map res:// path
            rel = gdf.relative_to(self.project_path).as_posix()
            res_path = f"res://{rel}"
            file_nid = make_id(str(gdf))
            self.files_by_res_path[res_path] = file_nid
            self.files_by_res_path[rel] = file_nid

            # Count raw content
            try:
                txt = gdf.read_text(encoding="utf-8", errors="replace")
                self.total_raw_lines += len(txt.splitlines())
                self.total_raw_words += len(txt.split())
            except Exception:
                pass

        # 3. Extract all Scene files (.tscn)
        for scnf in file_map["scene"]:
            res = extract_tscn(scnf, root=self.project_path)
            self._merge_extraction(res)

            rel = scnf.relative_to(self.project_path).as_posix()
            res_path = f"res://{rel}"
            scene_nid = make_id(str(scnf))
            self.scenes_by_res_path[res_path] = scene_nid
            self.scenes_by_res_path[rel] = scene_nid

            try:
                txt = scnf.read_text(encoding="utf-8", errors="replace")
                self.total_raw_lines += len(txt.splitlines())
                self.total_raw_words += len(txt.split())
            except Exception:
                pass

        # 4. Extract all Resource files (.tres)
        for tresf in file_map["resource"]:
            res = extract_tres(tresf, root=self.project_path)
            self._merge_extraction(res)

            try:
                txt = tresf.read_text(encoding="utf-8", errors="replace")
                self.total_raw_lines += len(txt.splitlines())
                self.total_raw_words += len(txt.split())
            except Exception:
                pass

        # 5. Populate registry indexes from extracted nodes
        for nid, node in self.nodes.items():
            kind = node.get("kind")
            label = node.get("label", "")
            if kind == "class":
                self.classes_by_name[label] = nid
            elif kind == "signal":
                sig_name = node.get("signal_name") or label.split(".")[-1]
                self.signals_by_name.setdefault(sig_name, []).append(nid)

        # 6. Cross-reference resolution
        self._resolve_cross_references()

        # 7. Construct NetworkX graph
        for nid, data in self.nodes.items():
            self.graph.add_node(nid, **data)

        for edge in self.edges:
            src = edge["source"]
            tgt = edge["target"]
            if src in self.nodes and tgt in self.nodes:
                self.graph.add_edge(src, tgt, **edge)

        return self.graph

    def _merge_extraction(self, res: dict) -> None:
        """Merge a file's nodes and edges into builder collections."""
        for n in res.get("nodes", []):
            nid = n["id"]
            if nid not in self.nodes:
                self.nodes[nid] = n
            else:
                # Merge metadata
                self.nodes[nid].update(n)

        for e in res.get("edges", []):
            self.edges.append(e)

    def _resolve_cross_references(self) -> None:
        """Link loose references across scenes, scripts, autoloads, and signals."""
        new_edges = []

        for edge in self.edges:
            relation = edge["relation"]
            tgt = edge["target"]
            src = edge["source"]

            # If target is a res:// path node reference
            tgt_node = self.nodes.get(tgt)
            if tgt_node and tgt_node.get("res_path"):
                rp = tgt_node["res_path"]
                # Resolve to real script or scene node
                resolved_nid = self.files_by_res_path.get(rp) or self.scenes_by_res_path.get(rp)
                if resolved_nid and resolved_nid != tgt:
                    new_edges.append({
                        "source": src,
                        "target": resolved_nid,
                        "relation": relation,
                        "confidence": "RESOLVED",
                        "source_file": edge.get("source_file", ""),
                        "source_location": edge.get("source_location", ""),
                        "weight": edge.get("weight", 1.0),
                    })

            # Autoload references: link to autoload implementation script
            if relation == "uses_autoload":
                auto_name = tgt_node.get("label", "").replace("Autoload:", "") if tgt_node else ""
                if auto_name in self.autoloads:
                    auto_info = self.autoloads[auto_name]
                    impl_path = auto_info["path"]
                    resolved_nid = self.files_by_res_path.get(impl_path)
                    if resolved_nid:
                        new_edges.append({
                            "source": src,
                            "target": resolved_nid,
                            "relation": "calls_singleton",
                            "confidence": "RESOLVED",
                            "source_file": edge.get("source_file", ""),
                            "source_location": edge.get("source_location", ""),
                            "weight": 1.5,
                        })

            # Signal connections: link Signal:name to class signal declaration
            if relation == "emits" or relation == "connects_to":
                if tgt_node and tgt_node.get("kind") == "signal_ref":
                    sig_name = tgt_node.get("label", "").replace("Signal:", "")
                    if sig_name in self.signals_by_name:
                        for real_sig_nid in self.signals_by_name[sig_name]:
                            new_edges.append({
                                "source": src if relation == "emits" else real_sig_nid,
                                "target": real_sig_nid if relation == "emits" else tgt,
                                "relation": relation,
                                "confidence": "RESOLVED",
                                "source_file": edge.get("source_file", ""),
                                "source_location": edge.get("source_location", ""),
                                "weight": 1.2,
                            })

            # Extends resolution: if base class exists in project
            if relation == "extends":
                base_label = tgt_node.get("label") if tgt_node else None
                if base_label and base_label in self.classes_by_name:
                    real_base_nid = self.classes_by_name[base_label]
                    if real_base_nid != tgt:
                        new_edges.append({
                            "source": src,
                            "target": real_base_nid,
                            "relation": "extends_project_class",
                            "confidence": "RESOLVED",
                            "source_file": edge.get("source_file", ""),
                            "source_location": edge.get("source_location", ""),
                            "weight": 2.0,
                        })

        self.edges.extend(new_edges)

    def to_dict(self) -> dict:
        """Export serialized graph structure."""
        return {
            "nodes": list(self.nodes.values()),
            "edges": self.edges,
            "stats": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "total_files": len(self.files_by_res_path) + len(self.scenes_by_res_path),
                "raw_words": self.total_raw_words,
                "raw_lines": self.total_raw_lines,
                "estimated_raw_tokens": int(self.total_raw_words * 1.35),
            }
        }
