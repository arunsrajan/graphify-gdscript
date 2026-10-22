"""Locate the Godot project a command should operate on."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

GRAPH_DIR = "graphify-out"


def resolve_project_root(path: Optional[str] = None) -> Path:
    """Return the project root for ``path``, or auto-detect it when ``path`` is omitted.

    An explicit path is used as-is. Otherwise start from $GRAPHIFY_GDSCRIPT_PROJECT,
    $CLAUDE_PROJECT_DIR or the current directory, and walk up to the nearest folder
    holding ``project.godot`` (falling back to the start folder). MCP clients launch
    servers from varying working directories, and some pass an unexpanded placeholder
    such as ``${workspace.path}``, which is treated as "not given".
    """
    if path and "${" not in path:
        return Path(path).expanduser().resolve()

    start = Path.cwd()
    for var in ("GRAPHIFY_GDSCRIPT_PROJECT", "CLAUDE_PROJECT_DIR"):
        value = os.environ.get(var)
        if value and Path(value).is_dir():
            start = Path(value)
            break
    start = start.resolve()

    for candidate in (start, *start.parents):
        if (candidate / "project.godot").is_file():
            return candidate
    return start
