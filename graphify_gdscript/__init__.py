"""Graphify GDScript: Knowledge Graphs & LLM Token Reduction for Godot Game Engine."""
from importlib import import_module

__version__ = "1.0.0"

# Exports load lazily: the Claude Code hook (`graphify-gdscript guard`) runs before every
# Read/Grep call and must not pay for importing networkx and tree-sitter.
_EXPORTS = {
    "extract_gdscript": "graphify_gdscript.extractors.gdscript",
    "extract_tscn": "graphify_gdscript.extractors.tscn",
    "extract_project_godot": "graphify_gdscript.extractors.project_godot",
    "extract_tres": "graphify_gdscript.extractors.tres",
    "GodotGraphBuilder": "graphify_gdscript.graph_builder",
    "detect_communities": "graphify_gdscript.cluster",
    "label_communities": "graphify_gdscript.cluster",
    "find_god_nodes": "graphify_gdscript.god_nodes",
    "TokenReductionEngine": "graphify_gdscript.token_optimizer",
    "patch_graphifyy": "graphify_gdscript.bridge_graphify",
}
__all__ = list(_EXPORTS)


def __getattr__(name):
    if name in _EXPORTS:
        value = getattr(import_module(_EXPORTS[name]), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
