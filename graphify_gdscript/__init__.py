"""Graphify GDScript: Knowledge Graphs & LLM Token Reduction for Godot Game Engine."""
from graphify_gdscript.extractors.gdscript import extract_gdscript
from graphify_gdscript.extractors.tscn import extract_tscn
from graphify_gdscript.extractors.project_godot import extract_project_godot
from graphify_gdscript.extractors.tres import extract_tres
from graphify_gdscript.graph_builder import GodotGraphBuilder
from graphify_gdscript.cluster import detect_communities, label_communities
from graphify_gdscript.god_nodes import find_god_nodes
from graphify_gdscript.token_optimizer import TokenReductionEngine
from graphify_gdscript.bridge_graphify import patch_graphifyy

__version__ = "1.0.0"
__all__ = [
    "extract_gdscript",
    "extract_tscn",
    "extract_project_godot",
    "extract_tres",
    "GodotGraphBuilder",
    "detect_communities",
    "label_communities",
    "find_god_nodes",
    "TokenReductionEngine",
    "patch_graphifyy",
]
