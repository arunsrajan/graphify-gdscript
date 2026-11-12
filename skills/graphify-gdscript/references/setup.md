# Setup

The skill needs the `graphify-gdscript` command-line tool. It is not bundled in this skill and is not on PyPI; install it from its public repository (https://github.com/arunsrajan/graphify-gdscript), which is MIT licensed and open for audit.

## Requirements

- Python 3.9 or newer
- A Godot project containing `project.godot`
- Dependencies installed automatically with the tool: `networkx`, `tree-sitter`, `tree-sitter-gdscript`

## Install

```
pip install git+https://github.com/arunsrajan/graphify-gdscript.git
```

Use a virtual environment if you prefer to keep it isolated.

## Verify

```
graphify-gdscript --help
graphify-gdscript scan <path-to-godot-project>
```

A successful scan prints node, edge and subsystem counts and writes three files to `graphify-out/` inside the project:

| File | Contents |
|---|---|
| `graph.json` | The graph used for queries |
| `GRAPH_REPORT.md` | Architecture audit: god nodes, subsystems |
| `graph.html` | Interactive viewer |

Add `graphify-out/` to the project's `.gitignore` unless the team wants to commit it.

## Optional: MCP server

If your assistant supports the Model Context Protocol, register the stdio server so the agent can call the graph as tools:

```
graphify-gdscript mcp <path-to-godot-project>
```

Tools exposed: `gdscript_query_graph`, `gdscript_trace_signal`, `gdscript_shortest_path`, `gdscript_explain`, `gdscript_get_autoloads`, `gdscript_get_god_nodes`, `gdscript_token_reduction_report`, `gdscript_rebuild_graph`.

The server only reads the project folder you give it.

## Optional: always-on rules

`graphify-gdscript claude install`, `graphify-gdscript codex install` and `graphify-gdscript antigravity install` add rules that send the assistant to the graph before it greps raw files. Run `graphify-gdscript uninstall` to remove what they wrote.
