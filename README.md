# Graphify GDScript (Godot Engine Plugin & Token Reduction Optimizer)

> **Architectural Knowledge Graphs & Deterministic GraphRAG for Godot 4.x / 3.x GDScript.**  
> Slashes LLM API token consumption by up to **99%** across all agentic AI IDEs (Antigravity, Cursor, Claude Code, Windsurf, Trae, Copilot).

---

## 🚀 Why Graphify-GDScript?

Godot Engine architectures decouple game logic across multiple file formats:
- **Scripts (`.gd`)**: Methods, signals, properties, node paths (`$Sprite2D`, `%Hurtbox`).
- **Scenes (`.tscn`)**: Node tree hierarchies, instanced sub-scenes, and visual signal connections (`[connection signal="..." from="..." to="..." method="..."]`).
- **Autoload Singletons (`project.godot`)**: Global singletons (`GameManager`, `EventBus`).
- **Resources (`.tres`)**: Script-backed game data.

### The Problem: Massive LLM Token Waste & Hallucinations
When developers prompt AI coding assistants in Cursor, Antigravity, or Claude Code about a Godot bug or feature:
- ❌ **Naive Full-Codebase Dumps**: The IDE feeds 50,000 to 200,000+ tokens into the prompt context window ($0.50 – $3.00+ per query).
- ❌ **Invisible Signal Wiring**: Because signal connections are saved in `.tscn` text files while emissions are in `.gd` files, LLMs miss the connections and hallucinate non-existent node paths or phantom signals.
- ❌ **Context Window Degradation**: Large context dumps lead to lost-in-the-middle degradation and slow response latency.

### The Solution: Deterministic GraphRAG & Token Pruning
**Graphify-GDScript** parses GDScript ASTs, scene trees, autoloads, and signal connections into a unified knowledge graph. When querying the codebase, it extracts **targeted ego-subgraphs (800–1,500 tokens)** containing only the connected classes, signals, methods, and line citations:
- ⚡ **90% – 99% Token Consumption Reduction**
- ⚡ **100% Deterministic Link Traversal** (Zero hallucinated node paths)
- ⚡ **Works with any LLM API provider** (Gemini, Claude, OpenAI, DeepSeek, Local Ollama)

---

## 📊 Token Savings Benchmark

| Project Scale | Naive Whole-Repo Context | Graphify Pruned Context | Token Reduction | Cost Savings per 100 Queries ($3/1M) |
|---|---|---|---|---|
| **Small Game (Demo)** | ~2,400 tokens | ~750 tokens | **68.7% SAVED** | ~$0.50 |
| **Medium Game (30 scripts, 20 scenes)** | ~85,000 tokens | ~1,250 tokens | **98.5% SAVED** | ~$25.10 |
| **Large Game (120 scripts, 80 scenes)** | ~280,000 tokens | ~1,600 tokens | **99.4% SAVED** | ~$83.50 |

---

## 🛠️ Components

Graphify-GDScript delivers a complete 4-tier solution:

1. **Godot Editor Plugin (`addons/graphify_gdscript/`)**:
   - An in-editor bottom panel dock for Godot 4.x.
   - Live project token reduction metrics and savings calculator.
   - One-click buttons to "Build Knowledge Graph", "Open Visualizer", and "Copy AI Context for Prompt".
2. **Core Python CLI & Library (`graphify-gdscript`)**:
   - Fast AST extraction via `tree-sitter-gdscript` with robust fallback scanning.
   - Scene hierarchy (`.tscn`) and autoload singleton parser.
   - Community detection (Louvain) & God Node centrality analysis.
   - Interactive dark-mode HTML visualizer (`graph.html`).
3. **Agentic AI IDE Slash Command (`/graphify-gdscript`)**:
   - Slash command skill ready for Antigravity, Cursor, Claude Code, and Windsurf.
   - Constrains context answers strictly to a token budget (e.g. `--budget 1500`).
4. **Model Context Protocol (MCP) Server**:
   - Stdio MCP server exposing tools: `gdscript_query_graph`, `gdscript_token_reduction_report`, `gdscript_trace_signal`, `gdscript_get_autoloads`, `gdscript_get_god_nodes`, `gdscript_rebuild_graph`.

---

## 📦 Installation

### 1. Python Engine & CLI
```bash
git clone https://github.com/developer/graphify-gdscript.git
cd graphify-gdscript
pip install -e .
```

### 2. Godot Editor Plugin
Install the addon into any Godot project:
```bash
graphify-gdscript install-plugin /path/to/my_godot_project
```
Then in Godot:
> **Project** &rarr; **Project Settings** &rarr; **Plugins** &rarr; Enable **"Graphify GDScript"**.

---

## 💻 CLI Usage

### Build Full Knowledge Graph & Visualizer
```bash
graphify-gdscript scan .
# Generates:
#   graphify-out/graph.html       - Interactive dark-mode network visualizer
#   graphify-out/graph.json       - GraphRAG database
#   graphify-out/GRAPH_REPORT.md  - Architecture & God Node audit
```

### Query Knowledge Graph within a Token Budget
```bash
graphify-gdscript query "how does player take damage and trigger game over" --budget 1500
```

### Audit Token Savings vs Whole-Repo Context
```bash
graphify-gdscript token-report .
```

### Run MCP Server for IDEs
```bash
graphify-gdscript mcp .
```

Register it with an **absolute** project path (IDEs may launch servers from a different working directory):
```bash
claude mcp add graphify-gdscript -- graphify-gdscript mcp /path/to/my_godot_project
```
Or in an `mcp.json` / `.mcp.json`:
```json
{
  "mcpServers": {
    "graphify-gdscript": {
      "command": "graphify-gdscript",
      "args": ["mcp", "/path/to/my_godot_project"]
    }
  }
}
```
The graph is built in the background right after the client connects. Call `gdscript_rebuild_graph` after editing project files to refresh it.

### Hook into Upstream `graphifyy`
```bash
graphify-gdscript patch-graphifyy
```

---

## 🤖 Slash Command Usage in Agentic AI IDEs

In Antigravity, Cursor, or Claude Code:

```bash
/graphify-gdscript query "where is weapon_fired signal connected and handled?"
/graphify-gdscript query "trace damage flow from enemy to player" --budget 1000
/graphify-gdscript trace "health_changed"
/graphify-gdscript token-report
```

---

## 🧩 Graph Taxonomy

### Nodes
- **`class`**: GDScript classes (`class_name Player extends CharacterBody2D`)
- **`scene`**: Godot scene files (`res://scenes/player.tscn`)
- **`scene_node`**: Scene hierarchy nodes (`Player/Hurtbox`, `Gun/BulletSpawner`)
- **`autoload_singleton`**: Global singletons (`GameManager`, `EventBus`)
- **`function`**: Methods (`_ready`, `take_damage`, `fire_weapon`)
- **`signal`**: Declared signals (`health_changed`, `player_died`)
- **`export_var` / `onready_var`**: Configured properties and node paths
- **`node_reference`**: Node paths (`$Sprite2D`, `$"Weapon/Gun"`, `%Hurtbox`)
- **`resource`**: Custom `.tres` resources

### Directed Edges
- **`contains`**: Class contains function / variable / inner class
- **`extends`**: Class inheritance (`Player` &rarr; `CharacterBody2D`)
- **`attaches_script`**: Scene node attaches `.gd` script
- **`child_node`**: Scene tree parent-child relationship
- **`instantiates_scene`**: Node instantiates packed scene (`bullet.tscn`)
- **`emits`**: Method emits signal (`health_changed.emit`)
- **`connects_to`**: Signal connects to target handler method
- **`references_node`**: Variable/method references node path
- **`uses_autoload` / `calls_singleton`**: Script calls global singleton
- **`preloads` / `loads`**: Script loads scene or resource

---

## 🧪 Testing

Run test suite:
```bash
python -m pytest tests -v
```

---

## 📄 License
MIT License.
