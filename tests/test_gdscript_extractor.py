import tempfile
from pathlib import Path
import pytest
from graphify_gdscript.extractors.gdscript import extract_gdscript


def test_extract_gdscript_basic():
    code = """class_name Hero extends CharacterBody2D

signal mana_changed(current: int)
signal fallen

@export var max_mana: int = 50
@onready var shield = $ShieldNode
@onready var hurtbox = %SpecialHurtbox

func _ready() -> void:
    GameManager.init_hero(self)
    hurtbox.area_entered.connect(_on_area_entered)

func cast_spell(spell_name: String) -> void:
    mana_changed.emit(max_mana - 10)
    EventBus.spell_cast.emit(spell_name)

func _on_area_entered(area) -> void:
    pass

class SubHero extends Node:
    var sub_id: int = 1
"""
    with tempfile.NamedTemporaryFile("w", suffix=".gd", delete=False, encoding="utf-8") as f:
        f.write(code)
        f_path = Path(f.name)

    try:
        res = extract_gdscript(f_path)
        nodes = res["nodes"]
        edges = res["edges"]

        labels = {n["label"]: n for n in nodes}
        assert "Hero" in labels
        assert labels["Hero"]["kind"] == "class"
        assert "Hero.mana_changed" in labels
        assert labels["Hero.mana_changed"]["kind"] == "signal"
        assert "Hero.cast_spell" in labels
        assert labels["Hero.cast_spell"]["kind"] == "function"
        assert "$ShieldNode" in labels
        assert "%SpecialHurtbox" in labels
        assert "Hero.SubHero" in labels

        # Edge assertions
        edge_pairs = {(e["source"], e["target"], e["relation"]) for e in edges}
        assert any(e[2] == "declares_signal" for e in edge_pairs)
        assert any(e[2] == "contains" for e in edge_pairs)
        assert any(e[2] == "emits" for e in edge_pairs)
        assert any(e[2] == "connects_to" for e in edge_pairs)
        assert any(e[2] == "references_node" for e in edge_pairs)
    finally:
        f_path.unlink(missing_ok=True)
