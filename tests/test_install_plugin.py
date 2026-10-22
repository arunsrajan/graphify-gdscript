import filecmp
from pathlib import Path

import pytest

from graphify_gdscript.cli import godot_addon_source, main

REPO = Path(__file__).resolve().parent.parent
CANONICAL = REPO / "addons" / "graphify_gdscript"


def _files(root: Path):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def test_install_plugin_copies_the_addon(tmp_path):
    (tmp_path / "project.godot").write_text("config_version=5\n", encoding="utf-8")
    with pytest.raises(SystemExit) as done:
        main(["install-plugin", str(tmp_path)])
    assert done.value.code == 0
    installed = tmp_path / "addons" / "graphify_gdscript"
    assert _files(installed) == _files(CANONICAL)
    assert "plugin.cfg" in _files(installed)


def test_packaged_addon_wins_over_checkout(tmp_path):
    package_dir = tmp_path / "site-packages" / "graphify_gdscript"
    packaged = package_dir / "godot_addon"
    packaged.mkdir(parents=True)
    (packaged / "plugin.cfg").write_text("[plugin]\n", encoding="utf-8")
    assert godot_addon_source(package_dir) == packaged


def test_checkout_addon_used_for_editable_installs():
    assert godot_addon_source(REPO / "graphify_gdscript") == CANONICAL


def test_missing_addon_is_reported(tmp_path):
    assert godot_addon_source(tmp_path / "graphify_gdscript") is None


def test_demo_project_addon_matches_canonical():
    demo = REPO / "examples" / "demo_godot_project" / "addons" / "graphify_gdscript"
    assert _files(demo) == _files(CANONICAL)
    _, mismatch, errors = filecmp.cmpfiles(CANONICAL, demo, _files(CANONICAL), shallow=False)
    assert not mismatch and not errors, f"examples/ addon differs from addons/: {mismatch or errors}"
