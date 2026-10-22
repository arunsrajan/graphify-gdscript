import shutil
from pathlib import Path

from setuptools import setup, find_packages
from setuptools.command.build_py import build_py

ROOT = Path(__file__).resolve().parent
GODOT_ADDON = ROOT / "addons" / "graphify_gdscript"


class build_py_with_godot_addon(build_py):
    """Ship the Godot editor addon inside the package as graphify_gdscript/godot_addon/.

    The canonical copy stays at addons/graphify_gdscript/, where Godot expects an addon;
    `graphify-gdscript install-plugin` copies the packaged one into a project. Editable
    installs skip this and read addons/ straight from the checkout.
    """

    def run(self):
        super().run()
        if getattr(self, "editable_mode", False):
            return
        target = Path(self.build_lib) / "graphify_gdscript" / "godot_addon"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(GODOT_ADDON, target, ignore=shutil.ignore_patterns(".*", "*.import", "__pycache__"))


setup(
    name="graphify-gdscript",
    version="1.0.0",
    packages=find_packages(),
    package_data={"graphify_gdscript": ["assets/*.md"]},
    cmdclass={"build_py": build_py_with_godot_addon},
    install_requires=[
        "networkx>=3.0",
        "tree-sitter>=0.22.0",
        "tree-sitter-gdscript>=6.1.0",
    ],
    entry_points={
        "console_scripts": [
            "graphify-gdscript = graphify_gdscript.cli:main",
        ],
    },
)
