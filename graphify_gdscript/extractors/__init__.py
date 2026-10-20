"""Extractors for Godot GDScript and Engine assets."""
from graphify_gdscript.extractors.gdscript import extract_gdscript
from graphify_gdscript.extractors.tscn import extract_tscn
from graphify_gdscript.extractors.project_godot import extract_project_godot
from graphify_gdscript.extractors.tres import extract_tres

__all__ = [
    "extract_gdscript",
    "extract_tscn",
    "extract_project_godot",
    "extract_tres",
]
