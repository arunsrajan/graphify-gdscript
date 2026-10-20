"""Bridge to patch upstream graphifyy to support Godot GDScript and TSCN.

Dynamically registers .gd and .tscn into graphify.extract._DISPATCH and
graphify.detect.CODE_EXTENSIONS if graphify is installed.
"""
from __future__ import annotations

from pathlib import Path
from graphify_gdscript.extractors.gdscript import extract_gdscript
from graphify_gdscript.extractors.tscn import extract_tscn


def patch_graphifyy() -> bool:
    """Inject GDScript and TSCN extractors into graphify library if present."""
    try:
        import graphify.extract as ex
        import graphify.detect as de

        # Register extensions in detection
        de.CODE_EXTENSIONS.add(".gd")
        de.CODE_EXTENSIONS.add(".tscn")

        # Register extractors in dispatch table
        ex._DISPATCH[".gd"] = extract_gdscript
        ex._DISPATCH[".tscn"] = extract_tscn

        return True
    except Exception as e:
        return False
