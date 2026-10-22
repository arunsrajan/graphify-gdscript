## graphify-gdscript

This Godot project has a graphify-gdscript knowledge graph at graphify-out/ covering .gd scripts, .tscn scenes, project.godot autoloads, .tres resources, signals and node paths.

When the user types `/graphify-gdscript` (or `$graphify-gdscript` in Codex), use the installed graphify-gdscript skill before doing anything else.

Rules:
- When graphify-out/graph.json exists, run `graphify-gdscript query "<question>"` before your first grep, search or raw read of .gd, .tscn, .tres or project.godot files, and put this rule in every subagent prompt that explores the project. Use `graphify-gdscript trace "<signal>"` for signal flow, `graphify-gdscript path "<A>" "<B>"` for relationships and `graphify-gdscript explain "<symbol>"` for one symbol. Read raw files only for lines the graph already located.
- Signals are often connected in .tscn files rather than code: run `trace` before deciding a signal is unused.
- Read graphify-out/GRAPH_REPORT.md only for a broad architecture review.
- After modifying project files, run `graphify-gdscript scan` to keep the graph current (AST-only, no API cost).
