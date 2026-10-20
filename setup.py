from setuptools import setup, find_packages

setup(
    name="graphify-gdscript",
    version="1.0.0",
    packages=find_packages(),
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
