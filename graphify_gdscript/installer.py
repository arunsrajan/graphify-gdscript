"""Install graphify-gdscript into AI coding assistants: Claude Code, Codex and Google Antigravity.

Modelled on the upstream graphify installer (https://github.com/Graphify-Labs/graphify),
but everything it writes uses its own names: the ``graphify-gdscript`` skill folder,
comment-delimited ``graphify-gdscript`` blocks in CLAUDE.md / AGENTS.md, the
``graphify-gdscript guard`` hooks and a ``graphify-gdscript`` MCP entry. An upstream
graphify install and this one can live side by side, and neither removes the other.

Scopes, per platform:
  default    the skill goes into the assistant's user-level skills folder; the always-on
             instructions (and Claude hooks) go into the project directory given.
  --project  the skill goes into the project as well, and every command written into
             config is the bare ``graphify-gdscript`` (no machine-specific path), so the
             files can be committed for the whole team.
  --mcp      also register the graphify-gdscript MCP server with the assistant.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

NAME = "graphify-gdscript"
ASSETS = Path(__file__).parent / "assets"
VERSION_FILE = ".graphify_gdscript_version"
PLATFORMS = ("claude", "codex", "antigravity")

# Blocks we own inside shared markdown files are fenced by these comment lines, so an
# update or uninstall never touches a line outside them.
SECTION_ID = "graphify-gdscript"            # always-on rules in CLAUDE.md / AGENTS.md
REGISTRATION_ID = "graphify-gdscript-skill"  # skill registration in .claude/CLAUDE.md
_BLOCK_HEADINGS = {SECTION_ID: f"## {NAME}", REGISTRATION_ID: f"# {NAME}"}
# Section headings the upstream graphify installer writes and rewrites.
_UPSTREAM_HEADINGS = ("# graphify", "## graphify")

ANTIGRAVITY_RULE = Path(".agents") / "rules" / f"{NAME}.md"
ANTIGRAVITY_WORKFLOW = Path(".agents") / "workflows" / f"{NAME}.md"

_HOOK_COMMAND = re.compile(r"graphify-gdscript(?:\.exe)?\"?\s+guard\s+(?:search|read)\b", re.IGNORECASE)


class InstallError(Exception):
    """An install step that must stop rather than damage the user's files."""


def _home() -> Path:
    return Path.home()


def _version() -> str:
    from graphify_gdscript import __version__
    return __version__


def _asset(name: str) -> str:
    path = ASSETS / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        raise InstallError(f"packaged file {path} is missing; reinstall graphify-gdscript") from e


def _say(label: str, message: str) -> None:
    print(f"  {label:<22}->  {message}")


# ---------------------------------------------------------------------------
# Text and JSON files we share with the user
# ---------------------------------------------------------------------------

def _read_keep_newline(path: Path) -> Tuple[str, str]:
    """Read ``path`` with bare-\\n text plus the file's own line ending, to restore on write."""
    raw = path.read_bytes().decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in raw else "\n"
    return raw.replace("\r\n", "\n").replace("\r", "\n"), newline


def _write_keep_newline(path: Path, text: str, newline: str = "\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if newline != "\n":
        text = text.replace("\n", newline)
    path.write_text(text, encoding="utf-8", newline="")


def _fences(block_id: str) -> Tuple[str, str]:
    return f"<!-- {block_id}:start -->", f"<!-- {block_id}:end -->"


def _block_spans(lines: List[str], block_id: str) -> Optional[List[Tuple[int, int]]]:
    """Line spans (inclusive) of every ``block_id`` block; None if a block is never closed.

    An end fence whose start fence is gone (another tool rewrote the lines above it) is
    recovered from the block's own heading, so the block is replaced rather than duplicated.
    """
    start_tag, end_tag = _fences(block_id)
    heading = _BLOCK_HEADINGS.get(block_id)
    spans, i, floor = [], 0, 0
    while i < len(lines):
        line = lines[i].strip()
        if line == start_tag:
            for j in range(i + 1, len(lines)):
                if lines[j].strip() == end_tag:
                    spans.append((i, j))
                    i = floor = j
                    break
            else:
                return None
        elif line == end_tag and heading:
            for k in range(i - 1, floor - 1, -1):
                if lines[k].strip() == heading:
                    spans.append((k, i))
                    floor = i
                    break
        i += 1
    return spans


def upsert_block(content: str, block_id: str, body: str) -> str:
    """Insert or refresh the fenced ``block_id`` block holding ``body``; other text is untouched.

    A new block goes before any upstream graphify section: upstream graphify replaces from
    its ``# graphify`` / ``## graphify`` heading down to the next heading of that level,
    which would otherwise swallow the first line of a block placed after it.
    """
    start_tag, end_tag = _fences(block_id)
    block = [start_tag, *body.strip("\n").split("\n"), end_tag]
    lines = content.split("\n")
    spans = _block_spans(lines, block_id)
    if spans is None:
        raise InstallError(f"found '{start_tag}' without a matching '{end_tag}'; fix or remove it and re-run")
    if not spans:
        upstream = next((i for i, line in enumerate(lines) if line.strip() in _UPSTREAM_HEADINGS), None)
        if upstream is not None:
            head = lines[:upstream]
            while head and not head[-1].strip():
                head.pop()
            return "\n".join(head + ([""] if head else []) + block + [""] + lines[upstream:])
        text = content.rstrip("\n")
        return (text + "\n\n" if text else "") + "\n".join(block) + "\n"
    first_start, first_end = spans[0]
    out = lines[:first_start] + block
    prev_end = first_end
    for start, end in spans[1:]:  # drop duplicates left by hand edits
        out += lines[prev_end + 1:start]
        prev_end = end
    out += lines[prev_end + 1:]
    return "\n".join(out)


def remove_block(content: str, block_id: str) -> Optional[str]:
    """``content`` without any ``block_id`` block, or None if there is none to remove."""
    lines = content.split("\n")
    spans = _block_spans(lines, block_id)
    if not spans:
        return None
    kept, prev = [], 0
    for start, end in spans:
        kept += lines[prev:start]
        prev = end + 1
    kept += lines[prev:]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip("\n")
    return text + "\n" if text else ""


def _upsert_file_block(path: Path, block_id: str, body: str, label: str) -> None:
    existed = path.exists()
    content, newline = _read_keep_newline(path) if existed else ("", "\n")
    updated = upsert_block(content, block_id, body)
    if existed and updated == content:
        _say(label, f"already up to date ({path})")
        return
    _write_keep_newline(path, updated, newline)
    _say(label, f"{'updated' if existed else 'created'} {path}")


def _remove_file_block(path: Path, block_id: str, label: str) -> bool:
    if not path.exists():
        return False
    content, newline = _read_keep_newline(path)
    cleaned = remove_block(content, block_id)
    if cleaned is None:
        return False
    if cleaned.strip():
        _write_keep_newline(path, cleaned, newline)
        _say(label, f"section removed from {path}")
    else:
        path.unlink()
        _say(label, f"deleted {path} (nothing else was in it)")
    return True


def _load_json(path: Path) -> dict:
    """Existing JSON config for a read-modify-write; refuses rather than clobbering bad JSON."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as e:
        raise InstallError(f"refusing to modify {path}: it is not valid JSON ({e})") from e
    if not isinstance(data, dict):
        raise InstallError(f"refusing to modify {path}: expected a JSON object")
    return data


def _write_json(path: Path, data: dict) -> bool:
    """Write ``data``, keeping one backup of the previous file. False when nothing changed."""
    output = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    newline = "\n"
    if path.exists():
        current, newline = _read_keep_newline(path)
        if current == output:
            return False
        shutil.copy2(path, path.with_name(path.name + ".graphify-gdscript-bak"))
    _write_keep_newline(path, output, newline)
    return True


def _write_or_delete_json(path: Path, data: dict) -> None:
    """Uninstall helper: write ``data`` back, or delete the file when nothing is left in it."""
    if data:
        _write_json(path, data)
    else:
        path.unlink()
        _prune_empty_dirs(path.parent, stop_at=2)


def _write_owned_file(path: Path, text: str, label: str) -> None:
    """Write a file graphify-gdscript owns outright (Antigravity rule/workflow)."""
    if path.exists() and path.read_text(encoding="utf-8") == text:
        _say(label, f"already up to date ({path})")
        return
    existed = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    _say(label, f"{'updated' if existed else 'created'} {path}")


def _remove_owned_file(path: Path, label: str) -> bool:
    if not path.exists():
        return False
    path.unlink()
    _say(label, f"removed {path}")
    _prune_empty_dirs(path.parent, stop_at=2)
    return True


def _prune_empty_dirs(directory: Path, stop_at: int) -> None:
    for d in [directory, *directory.parents][:stop_at]:
        try:
            d.rmdir()
        except OSError:
            break


# ---------------------------------------------------------------------------
# Skill files
# ---------------------------------------------------------------------------

def claude_config_dir() -> Path:
    return Path(os.environ["CLAUDE_CONFIG_DIR"]) if os.environ.get("CLAUDE_CONFIG_DIR") else _home() / ".claude"


def codex_home() -> Path:
    return Path(os.environ["CODEX_HOME"]) if os.environ.get("CODEX_HOME") else _home() / ".codex"


def skill_path(platform: str, project_dir: Optional[Path] = None) -> Path:
    """Where ``platform`` reads the skill: the project when ``project_dir`` is given, else user-level.

    Codex reads ``.agents/skills`` (repo) and ``~/.agents/skills`` (user); Antigravity reads
    ``.agents/skills`` (workspace) and ``~/.gemini/config/skills`` (global).
    """
    if project_dir is not None:
        folder = {"claude": Path(".claude") / "skills"}.get(platform, Path(".agents") / "skills")
        return project_dir / folder / NAME / "SKILL.md"
    if platform == "claude":
        return claude_config_dir() / "skills" / NAME / "SKILL.md"
    if platform == "codex":
        return _home() / ".agents" / "skills" / NAME / "SKILL.md"
    if platform == "antigravity":
        return _home() / ".gemini" / "config" / "skills" / NAME / "SKILL.md"
    raise InstallError(f"unknown platform '{platform}'")


def install_skill(platform: str, project_dir: Optional[Path] = None) -> Path:
    dst = skill_path(platform, project_dir)
    src = _asset("skill.md")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        current = dst.read_text(encoding="utf-8", errors="replace")
        if current == src:
            _say("skill", f"already up to date ({dst})")
            (dst.parent / VERSION_FILE).write_text(_version(), encoding="utf-8")
            return dst
        backup = dst.with_name("SKILL.md.bak")
        shutil.copy2(dst, backup)
        _say("previous skill", f"saved to {backup}")
    tmp = dst.with_name("SKILL.md.tmp")
    tmp.write_text(src, encoding="utf-8", newline="")  # keep LF: frontmatter parsers expect it
    os.replace(tmp, dst)
    (dst.parent / VERSION_FILE).write_text(_version(), encoding="utf-8")
    _say("skill", f"installed {dst}")
    return dst


def remove_skill(platform: str, project_dir: Optional[Path] = None) -> bool:
    dst = skill_path(platform, project_dir)
    removed = False
    for f in (dst, dst.with_name("SKILL.md.bak"), dst.with_name("SKILL.md.tmp"), dst.parent / VERSION_FILE):
        if f.exists():
            f.unlink()
            removed = True
    if removed:
        _say("skill", f"removed {dst}")
        _prune_empty_dirs(dst.parent, stop_at=3)  # e.g. graphify-gdscript/, skills/, .agents/
    return removed


# ---------------------------------------------------------------------------
# Commands written into assistant config
# ---------------------------------------------------------------------------

def resolve_executable(project: bool = False) -> str:
    """The command assistants should run: bare for committed project config, else an absolute path.

    An absolute path keeps hooks and MCP servers working when the Python scripts folder is
    not on the assistant's PATH (common for GUI apps on Windows). Forward slashes survive
    Git Bash, cmd.exe and PowerShell alike.
    """
    if project:
        return NAME
    found = shutil.which(NAME)
    if not found:
        bin_dir = Path(sys.executable).parent
        for candidate in (bin_dir / f"{NAME}.exe", bin_dir / NAME, bin_dir / "Scripts" / f"{NAME}.exe"):
            if candidate.exists():
                found = str(candidate)
                break
    return (found or NAME).replace("\\", "/")


def _mcp_server_entry(project: bool, args: Optional[List[str]] = None) -> dict:
    return {"command": resolve_executable(project), "args": args or ["mcp"]}


def _upsert_mcp_json(path: Path, entry: dict, label: str) -> None:
    config = _load_json(path)
    servers = config.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise InstallError(f"refusing to modify {path}: 'mcpServers' is not an object")
    servers[NAME] = entry
    changed = _write_json(path, config)
    _say(label, f"MCP server {'registered in' if changed else 'already registered in'} {path}")


def _remove_mcp_json(path: Path, label: str) -> bool:
    if not path.exists():
        return False
    try:
        config = _load_json(path)
    except InstallError:
        return False
    servers = config.get("mcpServers")
    if not isinstance(servers, dict) or NAME not in servers:
        return False
    del servers[NAME]
    if not servers:
        del config["mcpServers"]
    _write_or_delete_json(path, config)
    _say(label, f"MCP server removed from {path}")
    return True


# ---------------------------------------------------------------------------
# Claude Code
# ---------------------------------------------------------------------------

def _claude_registration(skill_ref: str) -> str:
    return (
        f"# {NAME}\n"
        f"- **{NAME}** (`{skill_ref}`) - Godot GDScript knowledge graph and token-budgeted "
        f"code context. Trigger: `/{NAME}`\n"
        f"When the user types `/{NAME}`, use the installed {NAME} skill before doing anything else."
    )


def _guard_hooks(project: bool) -> List[dict]:
    exe = resolve_executable(project)
    if " " in exe:
        exe = f'"{exe}"'
    return [
        {"matcher": "Bash|Grep",
         "hooks": [{"type": "command", "command": f"{exe} guard search", "timeout": 10}]},
        {"matcher": "Read|Glob",
         "hooks": [{"type": "command", "command": f"{exe} guard read", "timeout": 10}]},
    ]


def _is_our_hook(entry: object) -> bool:
    return (isinstance(entry, dict) and entry.get("type") == "command"
            and isinstance(entry.get("command"), str) and bool(_HOOK_COMMAND.search(entry["command"])))


def _strip_our_hooks(groups: list) -> list:
    """Drop only graphify-gdscript's hook entries; other tools' hooks (even in a shared group) stay."""
    kept = []
    for group in groups:
        entries = group.get("hooks") if isinstance(group, dict) else None
        if not isinstance(entries, list):
            kept.append(group)
            continue
        remaining = [e for e in entries if not _is_our_hook(e)]
        if len(remaining) == len(entries):
            kept.append(group)
        elif remaining:
            kept.append({**group, "hooks": remaining})
    return kept


def install_claude_hooks(project_dir: Path, project: bool) -> None:
    path = project_dir / ".claude" / "settings.json"
    settings = _load_json(path)
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict) or not isinstance(hooks.setdefault("PreToolUse", []), list):
        raise InstallError(f"refusing to modify {path}: unexpected 'hooks' layout")
    hooks["PreToolUse"] = _strip_our_hooks(hooks["PreToolUse"]) + _guard_hooks(project)
    changed = _write_json(path, settings)
    _say("Claude hooks", f"PreToolUse guard {'registered in' if changed else 'already in'} {path}")


def remove_claude_hooks(project_dir: Path) -> bool:
    removed = False
    for name in ("settings.json", "settings.local.json"):
        path = project_dir / ".claude" / name
        if not path.exists():
            continue
        try:
            settings = _load_json(path)
        except InstallError:
            continue
        hooks = settings.get("hooks")
        groups = hooks.get("PreToolUse") if isinstance(hooks, dict) else None
        if not isinstance(groups, list):
            continue
        filtered = _strip_our_hooks(groups)
        if filtered == groups:
            continue
        if filtered:
            hooks["PreToolUse"] = filtered
        else:
            del hooks["PreToolUse"]
            if not hooks:
                del settings["hooks"]
        _write_or_delete_json(path, settings)
        _say("Claude hooks", f"removed from {path}")
        removed = True
    return removed


def install_claude(project_dir: Path, *, project: bool = False, mcp: bool = False) -> List[Path]:
    """Skill + skill registration + CLAUDE.md rules + PreToolUse guard (+ .mcp.json)."""
    touched = []
    if project:
        skill = install_skill("claude", project_dir)
        registry = project_dir / ".claude" / "CLAUDE.md"
        skill_ref = f".claude/skills/{NAME}/SKILL.md"
        touched += [project_dir / ".claude"]
    else:
        skill = install_skill("claude")
        registry = claude_config_dir() / "CLAUDE.md"
        skill_ref = (f"~/.claude/skills/{NAME}/SKILL.md" if not os.environ.get("CLAUDE_CONFIG_DIR")
                     else skill.as_posix())
    _upsert_file_block(registry, REGISTRATION_ID, _claude_registration(skill_ref), "skill registry")
    _upsert_file_block(project_dir / "CLAUDE.md", SECTION_ID, _asset("always-on.md"), "CLAUDE.md")
    install_claude_hooks(project_dir, project)
    touched += [project_dir / "CLAUDE.md", project_dir / ".claude" / "settings.json"]
    if mcp:
        _upsert_mcp_json(project_dir / ".mcp.json", _mcp_server_entry(project), "Claude MCP")
        touched.append(project_dir / ".mcp.json")
    return touched


def uninstall_claude(project_dir: Path, *, project: bool = False) -> bool:
    removed = False
    if project:
        removed |= remove_skill("claude", project_dir)
        removed |= _remove_file_block(project_dir / ".claude" / "CLAUDE.md", REGISTRATION_ID, "skill registry")
    else:
        removed |= remove_skill("claude")
        removed |= _remove_file_block(claude_config_dir() / "CLAUDE.md", REGISTRATION_ID, "skill registry")
    removed |= _remove_file_block(project_dir / "CLAUDE.md", SECTION_ID, "CLAUDE.md")
    removed |= _remove_file_block(project_dir / "CLAUDE.local.md", SECTION_ID, "CLAUDE.local.md")
    removed |= remove_claude_hooks(project_dir)
    removed |= _remove_mcp_json(project_dir / ".mcp.json", "Claude MCP")
    return removed


# ---------------------------------------------------------------------------
# Codex
# ---------------------------------------------------------------------------

def _toml_table_spans(lines: List[str]) -> List[Tuple[int, int]]:
    """Spans of our [mcp_servers.graphify-gdscript] table and its sub-tables."""
    header = re.compile(r'^\s*\[\s*mcp_servers\s*\.\s*(?:"graphify-gdscript"|graphify-gdscript)\s*(?:\.[^\]]*)?\]\s*(?:#.*)?$')
    spans, i = [], 0
    while i < len(lines):
        if header.match(lines[i]):
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith("["):
                j += 1
            while j > i + 1 and not lines[j - 1].strip():  # leave trailing blank lines outside
                j -= 1
            spans.append((i, j))
            i = j
        else:
            i += 1
    return spans


def _check_toml(text: str, path: Path) -> None:
    try:
        import tomllib
    except ImportError:  # Python < 3.11: skip validation
        return
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise InstallError(f"refusing to modify {path}: not valid TOML ({e})") from e


def upsert_codex_mcp(content: str, entry: dict) -> str:
    table = [
        f"[mcp_servers.{NAME}]",
        f"command = {json.dumps(entry['command'])}",
        "args = [" + ", ".join(json.dumps(a) for a in entry["args"]) + "]",
    ]
    lines = content.split("\n")
    spans = _toml_table_spans(lines)
    if not spans:
        text = content.rstrip("\n")
        return (text + "\n\n" if text else "") + "\n".join(table) + "\n"
    out, prev = [], 0
    for n, (start, end) in enumerate(spans):
        out += lines[prev:start] + (table if n == 0 else [])
        prev = end
    out += lines[prev:]
    return "\n".join(out)


def remove_codex_mcp(content: str) -> Optional[str]:
    lines = content.split("\n")
    spans = _toml_table_spans(lines)
    if not spans:
        return None
    out, prev = [], 0
    for start, end in spans:
        out += lines[prev:start]
        prev = end
    out += lines[prev:]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip("\n")
    return text + "\n" if text else ""


def _codex_config_path(project_dir: Path, project: bool) -> Path:
    return project_dir / ".codex" / "config.toml" if project else codex_home() / "config.toml"


def install_codex(project_dir: Path, *, project: bool = False, mcp: bool = False) -> List[Path]:
    """Skill (invoked as $graphify-gdscript) + AGENTS.md rules (+ config.toml MCP server)."""
    touched = []
    skill = install_skill("codex", project_dir if project else None)
    if project:
        touched.append(skill.parent)
    _upsert_file_block(project_dir / "AGENTS.md", SECTION_ID, _asset("always-on.md"), "AGENTS.md")
    touched.append(project_dir / "AGENTS.md")
    if mcp:
        path = _codex_config_path(project_dir, project)
        current, newline = _read_keep_newline(path) if path.exists() else ("", "\n")
        _check_toml(current, path)
        updated = upsert_codex_mcp(current, _mcp_server_entry(project))
        _check_toml(updated, path)
        if updated != current:
            if path.exists():
                shutil.copy2(path, path.with_name(path.name + ".graphify-gdscript-bak"))
            _write_keep_newline(path, updated, newline)
        _say("Codex MCP", f"MCP server {'registered in' if updated != current else 'already in'} {path}")
        if project:
            touched.append(path)
    return touched


def uninstall_codex(project_dir: Path, *, project: bool = False) -> bool:
    removed = False
    # Codex and Antigravity share the project skill folder; keep it while Antigravity uses it.
    if not project or not (project_dir / ANTIGRAVITY_RULE).exists():
        removed |= remove_skill("codex", project_dir if project else None)
    removed |= _remove_file_block(project_dir / "AGENTS.md", SECTION_ID, "AGENTS.md")
    for path in {_codex_config_path(project_dir, project), _codex_config_path(project_dir, not project)}:
        if not path.exists():
            continue
        content, newline = _read_keep_newline(path)
        cleaned = remove_codex_mcp(content)
        if cleaned is None:
            continue
        if cleaned.strip():
            shutil.copy2(path, path.with_name(path.name + ".graphify-gdscript-bak"))
            _write_keep_newline(path, cleaned, newline)
        else:
            path.unlink()
            _prune_empty_dirs(path.parent, stop_at=1)
        _say("Codex MCP", f"MCP server removed from {path}")
        removed = True
    return removed


# ---------------------------------------------------------------------------
# Google Antigravity
# ---------------------------------------------------------------------------

def antigravity_mcp_config() -> Path:
    return _home() / ".gemini" / "antigravity" / "mcp_config.json"


def install_antigravity(project_dir: Path, *, project: bool = False, mcp: bool = False) -> List[Path]:
    """Skill + always-on rule + /graphify-gdscript workflow (+ mcp_config.json server)."""
    touched = []
    skill = install_skill("antigravity", project_dir if project else None)
    if project:
        touched.append(skill.parent)
    _write_owned_file(project_dir / ANTIGRAVITY_RULE, _asset("antigravity-rule.md"), "Antigravity rule")
    _write_owned_file(project_dir / ANTIGRAVITY_WORKFLOW, _asset("antigravity-workflow.md"), "Antigravity workflow")
    touched += [project_dir / ANTIGRAVITY_RULE, project_dir / ANTIGRAVITY_WORKFLOW]
    if mcp:
        # Antigravity only has a user-level MCP config; ${workspace.path} points the server
        # at whichever workspace is open (and is auto-detected if left unexpanded).
        entry = _mcp_server_entry(project=False, args=["mcp", "${workspace.path}"])
        _upsert_mcp_json(antigravity_mcp_config(), entry, "Antigravity MCP")
    return touched


def uninstall_antigravity(project_dir: Path, *, project: bool = False) -> bool:
    removed = False
    agents_md = project_dir / "AGENTS.md"
    codex_uses_skill = agents_md.exists() and _fences(SECTION_ID)[0] in agents_md.read_text(encoding="utf-8", errors="replace")
    if not project or not codex_uses_skill:
        removed |= remove_skill("antigravity", project_dir if project else None)
    removed |= _remove_owned_file(project_dir / ANTIGRAVITY_RULE, "Antigravity rule")
    removed |= _remove_owned_file(project_dir / ANTIGRAVITY_WORKFLOW, "Antigravity workflow")
    removed |= _remove_mcp_json(antigravity_mcp_config(), "Antigravity MCP")
    return removed


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

_INSTALLERS: Dict[str, Callable[..., List[Path]]] = {
    "claude": install_claude, "codex": install_codex, "antigravity": install_antigravity,
}
_UNINSTALLERS: Dict[str, Callable[..., bool]] = {
    "claude": uninstall_claude, "codex": uninstall_codex, "antigravity": uninstall_antigravity,
}
_NEXT_STEP = {
    "claude": f"In Claude Code, type:  /{NAME}",
    "codex": f"In Codex, type:  ${NAME}",
    "antigravity": f"In Antigravity, type:  /{NAME}",
}
_DISPLAY = {"claude": "Claude Code", "codex": "Codex", "antigravity": "Google Antigravity"}


def expand_platforms(platform: str) -> List[str]:
    if platform == "all":
        return list(PLATFORMS)
    if platform not in PLATFORMS:
        raise InstallError(f"unknown platform '{platform}'. Choose from: {', '.join(PLATFORMS)}, all")
    return [platform]


def install(platform: str, project_dir: Path, *, project: bool = False, mcp: bool = False) -> int:
    try:
        targets = expand_platforms(platform)
        project_dir = project_dir.resolve()
        touched: List[Path] = []
        for name in targets:
            print(f"\n{NAME} -> {_DISPLAY[name]}{' (project scope)' if project else ''}")
            touched += _INSTALLERS[name](project_dir, project=project, mcp=mcp)
    except InstallError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print("\nDone.")
    for name in targets:
        print(f"  {_NEXT_STEP[name]}")
    print(f"  Build the graph now:  {NAME} scan \"{project_dir}\"")
    if not mcp:
        print(f"  Add --mcp to also register the {NAME} MCP server.")
    if project:
        rel: List[str] = []
        for p in touched:
            try:
                text = p.relative_to(project_dir).as_posix()
            except ValueError:
                continue
            if text not in rel:
                rel.append(text)
        rel = [r for r in rel if not any(r.startswith(other + "/") for other in rel)]
        print("\nProject-scoped install. Commit these for your team:")
        print("  git add " + " ".join(rel))
    return 0


def uninstall(platform: str, project_dir: Path, *, project: bool = False) -> int:
    try:
        targets = expand_platforms(platform)
        project_dir = project_dir.resolve()
        for name in targets:
            print(f"\n{NAME} -> {_DISPLAY[name]}: uninstalling{' (project scope)' if project else ''}")
            if not _UNINSTALLERS[name](project_dir, project=project):
                print("  nothing to remove")
    except InstallError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print("\nDone.")
    return 0
