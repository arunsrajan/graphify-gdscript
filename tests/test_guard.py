import uuid

import pytest

from graphify_gdscript import guard


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "project.godot").write_text("config_version=5\n", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "player.gd").write_text("extends Node\n", encoding="utf-8")
    (tmp_path / "graphify-out").mkdir()
    (tmp_path / "graphify-out" / "graph.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    return tmp_path


def _call(kind, tool_input, session=None):
    return guard.evaluate(kind, {"session_id": session or uuid.uuid4().hex, "tool_input": tool_input})


def test_read_of_godot_file_is_nudged_once_per_session(project):
    session = uuid.uuid4().hex
    target = {"file_path": str(project / "scripts" / "player.gd")}
    assert _call("read", target, session) == guard.READ_NUDGE
    assert _call("read", target, session) is None


def test_glob_for_godot_files_is_nudged(project):
    assert _call("read", {"pattern": "**/*.gd", "path": str(project)}) == guard.READ_NUDGE


def test_non_godot_reads_are_ignored(project):
    assert _call("read", {"file_path": str(project / "README.md")}) is None


def test_searches(project):
    assert _call("search", {"command": "grep -rn health_changed scripts"}) == guard.SEARCH_NUDGE
    assert _call("search", {"command": "ls | rg take_damage"}) == guard.SEARCH_NUDGE
    assert _call("search", {"pattern": "take_damage"}) == guard.SEARCH_NUDGE  # Grep tool
    assert _call("search", {"command": 'git commit -m "add grep support"'}) is None
    assert _call("search", {"command": "ls -la"}) is None


def test_silent_without_a_graph(project):
    (project / "graphify-out" / "graph.json").unlink()
    assert _call("read", {"file_path": str(project / "scripts" / "player.gd")}) is None


def test_silent_outside_godot_projects(tmp_path, monkeypatch):
    (tmp_path / "graphify-out").mkdir()
    (tmp_path / "graphify-out" / "graph.json").write_text("{}", encoding="utf-8")  # e.g. upstream graphify's graph
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert _call("search", {"command": "grep foo"}) is None
