# graphify-gdscript skill

Gives your AI coding assistant a knowledge graph of a Godot project, so it answers from a small, cited subgraph instead of reading every `.gd`, `.tscn` and `.tres` file.

## What it does

- Builds a graph of classes, functions, signals, scene trees, autoloads, node paths and resources.
- Links what text search misses: `.tscn` signal connections wired to `.gd` callbacks, autoload calls resolved to their scripts, preloaded scenes resolved to files.
- Answers `query`, `trace`, `path`, `explain` and `token-report` requests with file and line citations.
- Works on Godot 4.x and 3.x projects. Parsing is local and AST-based: no network calls, no API key.

## Requirements

The skill calls the `graphify-gdscript` command-line tool, which is a separate Python package. See [references/setup.md](references/setup.md) for install steps. Without it the skill cannot run.

## Use

Ask in plain language ("where is `player_damaged` connected?", "how does the Player reach the GameManager?") or invoke it directly:

```
/graphify-gdscript                    build or refresh the graph
/graphify-gdscript query "<question>"
/graphify-gdscript trace "<signal>"
/graphify-gdscript path "<A>" "<B>"
/graphify-gdscript explain "<symbol>"
/graphify-gdscript token-report
```

In Codex, use `$graphify-gdscript`.

## Files

| File | Purpose |
|---|---|
| `SKILL.md` | The instructions the agent follows |
| `references/setup.md` | Installing and verifying the CLI, optional MCP server |
| `references/graph-schema.md` | Node kinds, edge relations and what each means |
| `references/troubleshooting.md` | Common problems and fixes |
| `examples/` | Sample questions with real output from a demo project |

## Limits

The graph is static. Signals connected with computed names, node paths built from strings and code generated at runtime are not visible to it. The skill tells the agent to report those as gaps.

License: MIT.
