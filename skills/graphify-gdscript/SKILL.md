---
name: graphify-gdscript
description: "Godot Engine GDScript knowledge graph generator and LLM token reduction optimizer. Turns any Godot project (.gd, .tscn, project.godot, .tres) into an architectural knowledge graph with community clustering, god nodes, cross-file signal resolution, and GraphRAG token-budgeted search that slashes LLM prompt token consumption by up to 99%."
---

# /graphify-gdscript

Turn any Godot Game Engine project into a navigable, high-density knowledge graph. Resolves GDScript classes, methods, node paths (`$Node`, `%UniqueNode`), scene hierarchies (`.tscn`), autoload singletons (`project.godot`), and signal connections across decoupled systems.

Massively slashes LLM prompt token consumption for any API provider (Gemini, Claude, OpenAI, DeepSeek, Local Ollama) by replacing massive full-codebase context dumps with targeted subgraphs.

## Usage

```bash
/graphify-gdscript                                   # full extraction & graph generation on current directory
/graphify-gdscript <path>                            # run on specific Godot project path
/graphify-gdscript query "<question>"                # GraphRAG search constrained to token budget (default 1500 tokens)
/graphify-gdscript query "<question>" --budget 800   # ultra-compact context (cap answer context at N tokens)
/graphify-gdscript query "<question>" --mode dfs     # deep call chain tracing (DFS)
/graphify-gdscript trace "<signal_name>"             # trace signal emissions, .tscn connections, and callbacks
/graphify-gdscript token-report                      # audit token reduction & cost savings vs whole-repo dump
/graphify-gdscript mcp                               # start Model Context Protocol stdio server for IDEs
/graphify-gdscript install-plugin <project_path>     # install Godot Editor Plugin to project addons/
/graphify-gdscript patch-graphifyy                   # hook into upstream graphifyy to enable .gd & .tscn
```

## Why Godot Projects Waste Massive LLM Tokens

Godot architectures decouple logic across:
1. **Scripts (`.gd`)**: Methods, signals, variables, node paths (`$Sprite2D`, `%Hurtbox`).
2. **Scenes (`.tscn`)**: Node tree hierarchies, instanced sub-scenes, and visual signal connections (`[connection signal="..." ...]`).
3. **Autoloads (`project.godot`)**: Global Singletons (`GameManager`, `EventBus`).
4. **Resources (`.tres`)**: Custom script-backed data resources.

In naive LLM workflows, an AI assistant dumps 50,000 to 200,000+ tokens into context windows trying to trace a single bug, often hallucinating missing signal connections because connections are defined in `.tscn` files rather than `.gd` files.

**Graphify-GDScript resolves this deterministically:**
- Connects `.tscn` signal bindings to `.gd` callback methods.
- Connects autoload references to singleton scripts.
- Extracts subgraphs within a strict token budget (e.g. 1,000 to 1,500 tokens).
- **Reduces token consumption by 90% to 99%** while providing 100% deterministic link traversal and exact file citations (`L{line}`).

---

## Agent Execution Workflow

When invoked with `/graphify-gdscript` in an agentic AI IDE (Antigravity, Cursor, Claude Code, Windsurf, Trae):

### 1. For Query Commands (`/graphify-gdscript query "<question>"`)
If `graphify-out/graph.json` exists or a question was asked:
Run:
```powershell
graphify-gdscript query "<question>" --budget 1500
```
Use the pruned knowledge subgraph returned by the tool to answer the user's question. Cite the exact file paths and line numbers provided in the subgraph.

### 2. For Build / Scan Commands (`/graphify-gdscript [path]`)
Run:
```powershell
graphify-gdscript scan "<path>"
```
Outputs generated in `<path>/graphify-out/`:
- `graph.html`: Interactive dark-mode network visualizer with search, subsystem filters, and token reduction banner.
- `graph.json`: Full GraphRAG JSON database of Godot entities and relations.
- `GRAPH_REPORT.md`: Architectural audit report surfacing God Nodes and Subsystems.

Report the summary to the user:
- Total Nodes and Edges extracted.
- Top God Nodes (e.g. `GameManager`, `EventBus`, `Player`).
- Identified Subsystem Communities (e.g., Combat System, UI & HUD, Player Controller).
- Exact Token Consumption Reduction (e.g., ~120,000 raw tokens -> ~1,400 graph tokens = 98.8% saved).

### 3. For Signal Tracing (`/graphify-gdscript trace "<signal_name>"`)
Trace where the signal is declared, where it is emitted (in `.gd` code), and where it is connected (in `.tscn` or code):
```powershell
graphify-gdscript query "signal <signal_name> emission connection" --budget 1000
```

### 4. For Godot Editor Integration
To install the Godot Editor Plugin dock into the project:
```powershell
graphify-gdscript install-plugin "<path_to_godot_project>"
```
Instruct the user to enable "Graphify GDScript" in Godot:
`Project -> Project Settings -> Plugins -> Enable 'Graphify GDScript'`.

---

## Entity and Edge Schema

### Node Kinds
- `class`: GDScript classes (`class_name Hero extends Node`)
- `scene`: Godot scene roots (`Scene:player.tscn`)
- `scene_node`: Nodes inside scenes (`test_scene:Gun/BulletSpawner`)
- `autoload_singleton`: Global autoloads from `project.godot` (`Autoload:GameManager`)
- `function`: Methods (`Player.take_damage`, `Player._physics_process`)
- `signal`: Signal declarations (`Player.health_changed`)
- `export_var` / `onready_var`: Exported variables and onready node references
- `node_reference`: Node paths (`$Sprite2D`, `$"Weapon/Gun"`, `%Hurtbox`)
- `resource`: Custom `.tres` resources

### Edge Relations
- `contains`: Class contains method / variable / inner class
- `extends`: Class inheritance (`Player` extends `CharacterBody2D`)
- `attaches_script`: Scene node attaches `.gd` script
- `contains_node` / `child_node`: Scene tree hierarchy
- `instantiates_scene`: Node instances packed sub-scene
- `emits`: Method emits signal (`health_changed.emit`)
- `connects_to`: Signal connects to target handler method
- `references_node`: Variable references node path
- `uses_autoload` / `calls_singleton`: Script accesses global singleton
- `preloads` / `loads`: Script loads resource or scene
