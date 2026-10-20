import tempfile
from pathlib import Path
import pytest
from graphify_gdscript.extractors.project_godot import extract_project_godot


def test_extract_project_godot():
    godot_config = """config_version=5

[application]
config/name="EpicQuest"
run/main_scene="res://scenes/world.tscn"

[autoload]
GameManager="*res://scripts/game_manager.gd"
EventBus="*res://scripts/event_bus.gd"
"""
    with tempfile.NamedTemporaryFile("w", suffix=".godot", delete=False, encoding="utf-8") as f:
        f.write(godot_config)
        f_path = Path(f.name)

    try:
        res = extract_project_godot(f_path)
        assert res["project_name"] == "EpicQuest"
        assert res["main_scene"] == "res://scenes/world.tscn"
        assert "GameManager" in res["autoloads"]
        assert "EventBus" in res["autoloads"]

        nodes = res["nodes"]
        labels = {n["label"] for n in nodes}
        assert any("Project:" in l for l in labels)
        assert any("Autoload:GameManager" in l for l in labels)
        assert any("Autoload:EventBus" in l for l in labels)
    finally:
        f_path.unlink(missing_ok=True)
