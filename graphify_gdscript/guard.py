"""Claude Code PreToolUse guard installed by `graphify-gdscript claude install`.

Invoked as `graphify-gdscript guard search` (matcher Bash|Grep) and
`graphify-gdscript guard read` (matcher Read|Glob). It reads the tool call JSON from
stdin and, when the Godot project being touched has a built graph, adds a short
additionalContext nudge toward `graphify-gdscript query` instead of raw grep/reads.

It never blocks a tool call: every error, and every call it does not recognise,
produces no output and exit code 0. It nudges at most once per session and kind so
it does not burn the tokens it exists to save. Only the standard library is imported
because the hook runs before every Read, Glob, Grep and Bash call.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Optional

GODOT_EXTS = (".gd", ".tscn", ".tres", ".godot")

_SEARCH_COMMAND = re.compile(
    r"(?:^|[|;&(]|\bxargs\b)\s*(?:sudo\s+)?"
    r"(?:grep|egrep|fgrep|rg|ag|ack|findstr|git\s+grep|select-string|sls)\b",
    re.IGNORECASE,
)

SEARCH_NUDGE = (
    "graphify-out/graph.json exists for this Godot project. Run "
    '`graphify-gdscript query "<question>"` (or `trace`, `path`, `explain`) before '
    "grepping raw files; grep only for lines the graph has already located."
)
READ_NUDGE = (
    "graphify-out/graph.json exists for this Godot project. Run "
    '`graphify-gdscript query "<question>"`, `trace "<signal>"`, `path "<A>" "<B>"` or '
    '`explain "<symbol>"` before reading raw .gd/.tscn/.tres files, then read only the '
    "lines the graph points to. Include this rule in subagent prompts that explore the project."
)


def _find_godot_root(start: Path) -> Optional[Path]:
    for candidate in (start, *start.parents):
        if (candidate / "project.godot").is_file():
            return candidate
    return None


def _graph_root(*hints: str) -> Optional[Path]:
    """The Godot project root holding a built graph, from the touched paths or the session dir."""
    starts = []
    for hint in hints:
        prefix = hint.split("*", 1)[0] if hint else ""
        if prefix:
            p = Path(prefix)
            starts.append(p if p.is_dir() else p.parent)
    starts.append(Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()))
    for start in starts:
        try:
            root = _find_godot_root(start.resolve())
        except (OSError, RuntimeError):
            continue
        if root is not None and (root / "graphify-out" / "graph.json").is_file():
            return root
    return None


def _first_time(session_id: str, kind: str, root: Path) -> bool:
    """True the first time this session nudges for ``kind`` in ``root``."""
    if not session_id:
        return True
    key = hashlib.sha256(f"{session_id}|{kind}|{root}".encode("utf-8")).hexdigest()[:24]
    marker = Path(tempfile.gettempdir()) / "graphify-gdscript-guard" / key
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.open("x").close()
        return True
    except FileExistsError:
        return False
    except OSError:
        return True


def evaluate(kind: str, payload: dict) -> Optional[str]:
    """Return the nudge text for a tool call, or None to stay silent."""
    tool_input = payload.get("tool_input", payload)
    if not isinstance(tool_input, dict):
        return None

    if kind == "search":
        command = str(tool_input.get("command") or "")
        is_grep_tool = not command and bool(tool_input.get("pattern"))
        if not (is_grep_tool or (command and _SEARCH_COMMAND.search(command))):
            return None
        root = _graph_root(str(tool_input.get("path") or ""))
        message = SEARCH_NUDGE
    elif kind == "read":
        values = [str(tool_input.get(k) or "") for k in ("file_path", "path", "pattern")]
        if not any(v.lower().replace("\\", "/").endswith(GODOT_EXTS) for v in values):
            return None
        root = _graph_root(*values)
        message = READ_NUDGE
    else:
        return None

    if root is None or not _first_time(str(payload.get("session_id") or ""), kind, root):
        return None
    return message


def run(kind: str) -> None:
    """Hook entry point: read stdin, print a PreToolUse payload or nothing. Never raises."""
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
        if not isinstance(payload, dict):
            return
        message = evaluate(kind, payload)
        if message:
            sys.stdout.write(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": message,
                }
            }) + "\n")
            sys.stdout.flush()
    except Exception:
        return
