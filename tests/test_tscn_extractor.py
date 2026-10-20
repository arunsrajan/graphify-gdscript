import tempfile
from pathlib import Path
import pytest
from graphify_gdscript.extractors.tscn import extract_tscn


def test_extract_tscn_hierarchy_and_signals():
    tscn_text = """[gd_scene load_steps=3 format=3 uid="uid://test12345"]

[ext_resource type="Script" path="res://scripts/hero.gd" id="1_hero"]
[ext_resource type="PackedScene" path="res://scenes/spell.tscn" id="2_spell"]

[node name="Hero" type="CharacterBody2D"]
script = ExtResource("1_hero")

[node name="Sprite" type="Sprite2D" parent="."]

[node name="SpellCastPoint" parent="." instance=ExtResource("2_spell")]

[node name="Hurtbox" type="Area2D" parent="."]

[connection signal="area_entered" from="Hurtbox" to="." method="_on_area_entered"]
"""
    with tempfile.NamedTemporaryFile("w", suffix=".tscn", delete=False, encoding="utf-8") as f:
        f.write(tscn_text)
        f_path = Path(f.name)

    try:
        res = extract_tscn(f_path)
        nodes = res["nodes"]
        edges = res["edges"]

        labels = {n["label"] for n in nodes}
        assert any("Scene:" in l for l in labels)
        assert any("res://scripts/hero.gd" in l for l in labels)
        assert any("res://scenes/spell.tscn" in l for l in labels)
        assert any("Signal:area_entered" in l for l in labels)

        relations = {e["relation"] for e in edges}
        assert "contains_node" in relations
        assert "child_node" in relations
        assert "attantiates_scene" in relations or "instantiates_scene" in relations
        assert "attaches_script" in relations
        assert "connects_to" in relations
    finally:
        f_path.unlink(missing_ok=True)
