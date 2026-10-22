---
name: graphify-gdscript
description: "Godot GDScript knowledge graph. Use for any question about a Godot project's code or architecture (.gd scripts, .tscn scenes, project.godot autoloads, .tres resources, signals, node paths) - especially when graphify-out/graph.json exists. Builds the graph, answers questions from a token-budgeted subgraph, traces signals across scenes and scripts, and finds paths between symbols."
---

# /graphify-gdscript

Turns a Godot 4.x / 3.x project into a knowledge graph of classes, functions, signals, scene trees, autoloads, node paths and resources, with the cross-file links an LLM usually misses: `.tscn` signal connections wired to `.gd` callbacks, autoload calls resolved to singleton scripts, and preloaded scenes resolved to their files.

Answer from the graph first; read raw files only for lines the graph has already located.

## Usage

```
/graphify-gdscript                         # build or refresh the graph for the current project
/graphify-gdscript <path>                  # build the graph for a Godot project at <path>
/graphify-gdscript query "<question>"      # answer from a token-budgeted subgraph
/graphify-gdscript trace "<signal>"        # where a signal is declared, emitted and connected
/graphify-gdscript path "<A>" "<B>"        # how two symbols are connected
/graphify-gdscript explain "<symbol>"      # one symbol and everything wired to it
/graphify-gdscript token-report            # token savings compared with pasting the whole repo
```

In Codex, invoke the skill as `$graphify-gdscript`.

## What to run

The CLI finds the project root by walking up to `project.godot`, so run commands from anywhere inside the project, or pass a path as the last argument.

| Request | Command |
|---|---|
| build / refresh (no args, or a path) | `graphify-gdscript scan [<path>]` |
| `query "<q>"` | `graphify-gdscript query "<q>" --budget 1500` (add `--mode dfs` for deep call chains) |
| `trace "<signal>"` | `graphify-gdscript trace "<signal>"` |
| `path "<A>" "<B>"` | `graphify-gdscript path "<A>" "<B>"` |
| `explain "<symbol>"` | `graphify-gdscript explain "<symbol>"` |
| `token-report` | `graphify-gdscript token-report` |

After a scan, report the node and edge counts, the top god nodes, the subsystem communities and the token reduction. Outputs land in `graphify-out/`: `graph.json` (the graph), `GRAPH_REPORT.md` (architecture audit) and `graph.html` (interactive viewer).

When the graphify-gdscript MCP server is connected, prefer its tools over the CLI: `gdscript_query_graph`, `gdscript_trace_signal`, `gdscript_shortest_path`, `gdscript_explain`, `gdscript_get_autoloads`, `gdscript_get_god_nodes`, `gdscript_token_reduction_report`, and `gdscript_rebuild_graph` after editing files.

## Rules

- For a code or architecture question about a Godot project, run `query`, `trace`, `path` or `explain` before your first grep or raw read of `.gd`, `.tscn`, `.tres` or `project.godot` files. Put this rule in every subagent prompt that explores the project.
- Cite the file paths and `L<line>` locations the graph returns. Never invent node paths, signals or autoloads the graph does not show.
- Signals are often connected in `.tscn` files, not in code. Use `trace` before concluding a signal is unused.
- After editing project files, run `graphify-gdscript scan` (or `gdscript_rebuild_graph`) so the graph stays current. It is AST-only and has no API cost.

## Graph schema

Node kinds: `class`, `inner_class`, `function`, `static_func`, `signal`, `variable`, `export_var`, `onready_var`, `node_reference` (`$Path`, `%Unique`), `scene`, `scene_node`, `autoload_singleton`, `resource`, `file`, plus `*_ref` placeholders for symbols used but defined elsewhere.

Edge relations: `contains`, `extends`, `extends_project_class`, `declares_signal`, `emits`, `connects_to`, `calls`, `references_node`, `uses_autoload`, `calls_singleton`, `preloads`, `loads`, `contains_node`, `child_node`, `attaches_script`, `root_script`, `instantiates_scene`, `registers_autoload`, `implemented_by`, `instance_of_script`.
