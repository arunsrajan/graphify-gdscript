---
trigger: always_on
description: Consult the graphify-gdscript knowledge graph at graphify-out/ for Godot code and architecture questions.
---

## graphify-gdscript

This Godot project has a graphify-gdscript knowledge graph at graphify-out/.

Rules:
- For code or architecture questions, when `graphify-out/graph.json` exists, first run `graphify-gdscript query "<question>"` (CLI) or `gdscript_query_graph` (MCP). Use `graphify-gdscript trace "<signal>"` / `gdscript_trace_signal` for signal flow, `graphify-gdscript path "<A>" "<B>"` / `gdscript_shortest_path` for relationships and `graphify-gdscript explain "<symbol>"` / `gdscript_explain` for one symbol. Read raw .gd, .tscn, .tres or project.godot files only for lines the graph already located.
- Signals are often connected in .tscn files rather than code: trace before deciding a signal is unused.
- After modifying project files in this session, run `graphify-gdscript scan` (or `gdscript_rebuild_graph`) to keep the graph current.
