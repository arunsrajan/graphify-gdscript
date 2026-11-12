# Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `graphify-gdscript: command not found` | The tool is not installed, or its Python scripts folder is not on PATH. See `setup.md`. |
| "No Godot project files found in path" / "No Godot (.gd, .tscn, project.godot) files found" | The command ran outside a Godot project. Run it inside the project, or pass the project path as the last argument. |
| `trace` says "No matching signal connections found" | The name is not a signal. `take_damage` is a function; use `explain` for functions and `trace` for signals such as `player_damaged`. |
| Results look stale after editing files | Run `graphify-gdscript scan` again (or the `gdscript_rebuild_graph` MCP tool). It is AST-only and has no API cost. |
| A symbol resolves to several matches | Pass the qualified name (`Player.take_damage`) instead of the bare name. The output lists other matches. |
| A signal seems unused | It may be connected only in a `.tscn` file or with a computed name in code. `trace` covers scene connections; report computed names as gaps. |
| `query` returns too little | Raise `--budget` (default in the skill is 1500) or use `--mode dfs` to follow a deep call chain. |
| Odd characters in Windows terminal output | Set `PYTHONIOENCODING=utf-8`. |
