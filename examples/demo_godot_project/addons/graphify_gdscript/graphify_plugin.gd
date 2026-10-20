@tool
extends EditorPlugin

const DockScene = preload("graphify_dock.tscn")
var dock_instance: Control

func _enter_tree() -> void:
	dock_instance = DockScene.instantiate()
	# Add to Editor Bottom Panel with custom title and icon
	add_control_to_bottom_panel(dock_instance, "Graphify GDScript")
	
	# Add Tool Menu Items
	add_tool_menu_item("Graphify: Generate Knowledge Graph", Callable(self, "_on_menu_generate"))
	add_tool_menu_item("Graphify: Open Architecture Visualizer", Callable(self, "_on_menu_open_viz"))
	add_tool_menu_item("Graphify: Copy AI Context Summary", Callable(self, "_on_menu_copy_context"))

func _exit_tree() -> void:
	if dock_instance:
		remove_control_from_bottom_panel(dock_instance)
		dock_instance.queue_free()

	remove_tool_menu_item("Graphify: Generate Knowledge Graph")
	remove_tool_menu_item("Graphify: Open Architecture Visualizer")
	remove_tool_menu_item("Graphify: Copy AI Context Summary")

func _on_menu_generate() -> void:
	if dock_instance and dock_instance.has_method("_on_btn_generate_pressed"):
		dock_instance._on_btn_generate_pressed()
	make_bottom_panel_item_visible(dock_instance)

func _on_menu_open_viz() -> void:
	if dock_instance and dock_instance.has_method("_on_btn_open_viz_pressed"):
		dock_instance._on_btn_open_viz_pressed()

func _on_menu_copy_context() -> void:
	if dock_instance and dock_instance.has_method("_on_btn_copy_prompt_pressed"):
		dock_instance._on_btn_copy_prompt_pressed()
