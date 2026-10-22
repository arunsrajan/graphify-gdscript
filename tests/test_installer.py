import json
from pathlib import Path

import pytest

from graphify_gdscript import installer as I
from graphify_gdscript.cli import main


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    proj = tmp_path / "proj"
    home.mkdir()
    proj.mkdir()
    (proj / "project.godot").write_text("config_version=5\n", encoding="utf-8")
    monkeypatch.setattr(I, "_home", lambda: home)
    for var in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "GRAPHIFY_GDSCRIPT_PROJECT", "CLAUDE_PROJECT_DIR"):
        monkeypatch.delenv(var, raising=False)
    return home, proj


def _snapshot(*roots):
    return {p: p.read_bytes() for root in roots for p in sorted(root.rglob("*")) if p.is_file()}


def _hook_commands(settings_path: Path):
    groups = json.loads(settings_path.read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
    return [h["command"] for g in groups for h in g["hooks"]]


def test_claude_install_writes_skill_rules_hooks_and_mcp(env):
    home, proj = env
    assert I.install("claude", proj, mcp=True) == 0

    skill = home / ".claude" / "skills" / "graphify-gdscript" / "SKILL.md"
    assert skill.read_text(encoding="utf-8") == I._asset("skill.md")
    assert "~/.claude/skills/graphify-gdscript/SKILL.md" in (home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "## graphify-gdscript" in (proj / "CLAUDE.md").read_text(encoding="utf-8")
    commands = _hook_commands(proj / ".claude" / "settings.json")
    assert any(c.endswith("guard search") for c in commands) and any(c.endswith("guard read") for c in commands)
    server = json.loads((proj / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["graphify-gdscript"]
    assert server["args"] == ["mcp"]


def test_install_is_idempotent(env):
    home, proj = env
    I.install("all", proj, mcp=True)
    before = _snapshot(home, proj)
    I.install("all", proj, mcp=True)
    assert _snapshot(home, proj) == before


def test_claude_install_keeps_existing_settings_and_other_hooks(env):
    _, proj = env
    settings = proj / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({
        "permissions": {"allow": ["Bash(ls:*)"]},
        "hooks": {"PreToolUse": [{"matcher": "Bash|Grep", "hooks": [
            {"type": "command", "command": "C:/x/graphify.exe hook-guard search"},
            {"type": "command", "command": "my-linter --check"},
        ]}]},
    }), encoding="utf-8")
    I.install("claude", proj)
    I.install("claude", proj)  # no duplicate hooks on re-run

    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["permissions"] == {"allow": ["Bash(ls:*)"]}
    commands = _hook_commands(settings)
    assert "my-linter --check" in commands and "C:/x/graphify.exe hook-guard search" in commands
    assert sum(c.endswith("guard search") and "graphify-gdscript" in c for c in commands) == 1

    I.uninstall("claude", proj)
    assert _hook_commands(settings) == ["C:/x/graphify.exe hook-guard search", "my-linter --check"]


def test_upstream_graphify_uninstall_leaves_our_hooks(env):
    upstream = pytest.importorskip("graphify.install")
    _, proj = env
    I.install("claude", proj)
    groups = json.loads((proj / ".claude" / "settings.json").read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
    assert upstream._strip_graphify_hooks(groups) == groups


def test_refuses_to_overwrite_invalid_json(env):
    _, proj = env
    settings = proj / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text("{ not json", encoding="utf-8")
    assert I.install("claude", proj) == 1
    assert settings.read_text(encoding="utf-8") == "{ not json"


def test_codex_install_uses_agents_skills_and_merges_config_toml(env):
    home, proj = env
    config = home / ".codex" / "config.toml"
    config.parent.mkdir()
    config.write_text('model = "gpt-5"\n\n[mcp_servers.other]\ncommand = "npx"\n', encoding="utf-8")

    I.install("codex", proj, mcp=True)
    assert (home / ".agents" / "skills" / "graphify-gdscript" / "SKILL.md").exists()
    assert "$graphify-gdscript" in (proj / "AGENTS.md").read_text(encoding="utf-8")
    text = config.read_text(encoding="utf-8")
    assert "[mcp_servers.other]" in text and "[mcp_servers.graphify-gdscript]" in text
    tomllib = pytest.importorskip("tomllib")
    parsed = tomllib.loads(text)
    assert parsed["mcp_servers"]["graphify-gdscript"]["args"] == ["mcp"]
    assert parsed["mcp_servers"]["other"]["command"] == "npx"

    I.uninstall("codex", proj)
    assert tomllib.loads(config.read_text(encoding="utf-8")) == {"model": "gpt-5", "mcp_servers": {"other": {"command": "npx"}}}
    assert not (proj / "AGENTS.md").exists()
    assert not (home / ".agents").exists()


def test_antigravity_install_writes_rule_workflow_and_mcp(env):
    home, proj = env
    I.install("antigravity", proj, mcp=True)
    assert (home / ".gemini" / "config" / "skills" / "graphify-gdscript" / "SKILL.md").exists()
    assert (proj / ".agents" / "rules" / "graphify-gdscript.md").read_text(encoding="utf-8").startswith("---\ntrigger: always_on")
    assert (proj / ".agents" / "workflows" / "graphify-gdscript.md").exists()
    config = json.loads((home / ".gemini" / "antigravity" / "mcp_config.json").read_text(encoding="utf-8"))
    assert config["mcpServers"]["graphify-gdscript"]["args"] == ["mcp", "${workspace.path}"]

    I.uninstall("antigravity", proj)
    assert not (proj / ".agents").exists()
    assert not (home / ".gemini").exists()


def test_project_scope_uses_bare_commands(env):
    _, proj = env
    I.install("claude", proj, project=True, mcp=True)
    assert (proj / ".claude" / "skills" / "graphify-gdscript" / "SKILL.md").exists()
    assert "graphify-gdscript guard read" in _hook_commands(proj / ".claude" / "settings.json")
    server = json.loads((proj / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["graphify-gdscript"]
    assert server["command"] == "graphify-gdscript"


def test_shared_project_skill_survives_until_last_user_uninstalls(env):
    _, proj = env
    I.install("codex", proj, project=True)
    I.install("antigravity", proj, project=True)
    skill = proj / ".agents" / "skills" / "graphify-gdscript" / "SKILL.md"
    I.uninstall("codex", proj, project=True)
    assert skill.exists()
    I.uninstall("antigravity", proj, project=True)
    assert not skill.exists()


def test_full_round_trip_restores_user_files(env):
    home, proj = env
    (home / ".claude").mkdir()
    (home / ".claude" / "CLAUDE.md").write_text("# graphify\n- upstream\n\n## My notes\nkeep me\n", encoding="utf-8")
    (proj / "CLAUDE.md").write_bytes(b"# My game\r\n\r\nNotes.\r\n")
    before = _snapshot(home, proj)

    I.install("all", proj, mcp=True)
    I.install("all", proj, project=True, mcp=True)
    I.uninstall("all", proj, project=True)
    I.uninstall("all", proj)
    after = {p: b for p, b in _snapshot(home, proj).items() if not p.name.endswith(".graphify-gdscript-bak")}
    assert after == before


def test_block_goes_before_upstream_section_and_survives_its_rewrite():
    content = "# graphify\n- upstream\n"
    ours = I.upsert_block(content, I.REGISTRATION_ID, I._claude_registration("x"))
    assert ours.index("graphify-gdscript-skill:start") < ours.index("# graphify\n")
    # Simulate upstream eating our start fence; we recover instead of duplicating.
    damaged = ours.replace("<!-- graphify-gdscript-skill:start -->\n", "")
    repaired = I.upsert_block(damaged, I.REGISTRATION_ID, I._claude_registration("x"))
    assert repaired.count("<!-- graphify-gdscript-skill:end -->") == 1
    assert repaired.count("# graphify-gdscript\n") == 1


def test_cli_platform_commands(env, capsys):
    home, proj = env
    with pytest.raises(SystemExit) as done:
        main(["claude", "install", str(proj)])
    assert done.value.code == 0
    assert (home / ".claude" / "skills" / "graphify-gdscript" / "SKILL.md").exists()
    with pytest.raises(SystemExit) as done:
        main(["uninstall", "--platform", "claude", str(proj)])
    assert done.value.code == 0
    assert not (home / ".claude" / "skills" / "graphify-gdscript").exists()


def test_repo_skill_copy_matches_packaged_skill():
    repo_copy = Path(__file__).resolve().parent.parent / "skills" / "graphify-gdscript" / "SKILL.md"
    assert repo_copy.read_text(encoding="utf-8") == I._asset("skill.md")
