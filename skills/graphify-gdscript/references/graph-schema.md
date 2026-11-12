# Graph schema

## Node kinds

| Kind | Meaning |
|---|---|
| `file` | A source file in the project |
| `class` / `inner_class` | A script's class, or a class nested in one |
| `function` / `static_func` | A method or static method |
| `signal` | A declared signal |
| `variable` / `export_var` / `onready_var` | Plain, `@export` and `@onready` members |
| `node_reference` | A `$Path` or `%UniqueName` lookup |
| `scene` / `scene_node` | A `.tscn` file and the nodes inside it |
| `autoload_singleton` | A global registered in `project.godot` |
| `resource` | A `.tres` resource |
| `*_ref` | Placeholder for a symbol used here but defined elsewhere |

## Edge relations

| Relation | Meaning |
|---|---|
| `contains` | A file, class or scene holds a member |
| `extends` / `extends_project_class` | Inheritance from an engine class / from another project script |
| `declares_signal` | A class declares a signal |
| `emits` | A function emits a signal |
| `connects_to` | A signal is connected to a callback, in code or in a `.tscn` `[connection]` |
| `calls` | A function calls another function |
| `references_node` | Code reads a node path |
| `uses_autoload` / `calls_singleton` | Code uses a global singleton / calls into its script |
| `preloads` / `loads` | Code preloads or loads a resource or scene |
| `contains_node` / `child_node` | Scene tree structure |
| `attaches_script` / `root_script` | A scene node uses a script |
| `instantiates_scene` | A scene instances another scene |
| `registers_autoload` | `project.godot` registers a singleton |
| `implemented_by` | A singleton is implemented by a script or scene |
| `instance_of_script` | A resource is backed by a script |

## Reading citations

Every result carries a project-relative path and line, written `scripts/player.gd L43`. Cite these exactly. A `*_ref` node or a `Signal:<name>` node with no declaration means the definition was not found in the project (for example an engine signal).
