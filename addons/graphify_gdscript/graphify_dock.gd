@tool
extends Control

const TokenEstimator = preload("token_estimator.gd")

@onready var label_scripts: Label = $VBox/Grid/ValScripts
@onready var label_scenes: Label = $VBox/Grid/ValScenes
@onready var label_raw_tokens: Label = $VBox/Grid/ValRawTokens
@onready var label_graph_tokens: Label = $VBox/Grid/ValGraphTokens
@onready var label_savings: Label = $VBox/Banner/LabelSavings

@onready var btn_generate: Button = $VBox/Actions/BtnGenerate
@onready var btn_open_viz: Button = $VBox/Actions/BtnOpenViz
@onready var btn_copy_prompt: Button = $VBox/Actions/BtnCopyPrompt

@onready var query_input: LineEdit = $VBox/QuerySection/QueryInput
@onready var btn_run_query: Button = $VBox/QuerySection/BtnRunQuery
@onready var log_output: TextEdit = $VBox/LogOutput

var last_metrics: Dictionary = {}
var _worker: Thread

func _ready() -> void:
	if not Engine.is_editor_hint():
		return

	refresh_metrics()
	if btn_generate:
		btn_generate.pressed.connect(_on_btn_generate_pressed)
	if btn_open_viz:
		btn_open_viz.pressed.connect(_on_btn_open_viz_pressed)
	if btn_copy_prompt:
		btn_copy_prompt.pressed.connect(_on_btn_copy_prompt_pressed)
	if btn_run_query:
		btn_run_query.pressed.connect(_on_btn_run_query_pressed)

func refresh_metrics() -> void:
	last_metrics = TokenEstimator.calculate_project_metrics("res://")
	
	if label_scripts:
		label_scripts.text = str(last_metrics.get("script_count", 0))
	if label_scenes:
		label_scenes.text = str(last_metrics.get("scene_count", 0))
	if label_raw_tokens:
		label_raw_tokens.text = "~" + str(last_metrics.get("estimated_raw_tokens", 0)) + " tokens"
	if label_graph_tokens:
		label_graph_tokens.text = "~" + str(last_metrics.get("avg_graph_tokens", 1500)) + " tokens"
	if label_savings:
		var pct = last_metrics.get("percent_saved", 0.0)
		label_savings.text = "⚡ %0.1f%% TOKEN REDUCTION SAVINGS" % pct

func _exit_tree() -> void:
	if _worker:
		_worker.wait_to_finish()
		_worker = null

func _python_cmd() -> String:
	return "python" if OS.get_name() == "Windows" else "python3"

# Runs the CLI on a worker thread so the editor stays responsive during long scans.
func _run_cli(args: Array, on_done: Callable) -> void:
	if _worker:
		if _worker.is_alive():
			_log("[Graphify] A previous command is still running, please wait...")
			return
		_worker.wait_to_finish()
	_set_busy(true)
	_worker = Thread.new()
	_worker.start(_cli_thread.bind(args, on_done))

func _cli_thread(args: Array, on_done: Callable) -> void:
	var output: Array = []
	var exit_code := OS.execute(_python_cmd(), ["-m", "graphify_gdscript.cli"] + args, output, true)
	_finish_cli.call_deferred(exit_code, output, on_done)

func _finish_cli(exit_code: int, output: Array, on_done: Callable) -> void:
	if _worker:
		_worker.wait_to_finish()
		_worker = null
	_set_busy(false)
	on_done.call(exit_code, output)

func _set_busy(busy: bool) -> void:
	for b in [btn_generate, btn_run_query]:
		if b:
			b.disabled = busy

func _log(msg: String) -> void:
	if log_output:
		log_output.text += msg + "\n"

func _on_btn_generate_pressed() -> void:
	_log("[Graphify] Generating Godot Architecture Knowledge Graph...")
	
	var global_res = ProjectSettings.globalize_path("res://")
	_run_cli(["scan", global_res], _on_scan_done)

func _on_scan_done(exit_code: int, output: Array) -> void:
	if exit_code == 0:
		_log("[Graphify] Success! Knowledge Graph generated at: res://graphify-out/")
		for l in output:
			_log(str(l))
	else:
		_log("[Graphify] Scan failed (exit code %d). Is graphify-gdscript installed for '%s'? Try `graphify-gdscript scan` in a terminal." % [exit_code, _python_cmd()])
		for l in output:
			_log(str(l))
	refresh_metrics()

func _on_btn_open_viz_pressed() -> void:
	var html_path = ProjectSettings.globalize_path("res://graphify-out/graph.html")
	if FileAccess.file_exists("res://graphify-out/graph.html"):
		# A plain OS path, as Godot's docs advise: "file://" + "C:/..." is a malformed URL on Windows.
		OS.shell_open(html_path)
		_log("[Graphify] Opened interactive graph visualizer in browser.")
	else:
		_log("[Graphify] graph.html not found. Click 'Generate Knowledge Graph' first.")

func _on_btn_copy_prompt_pressed() -> void:
	var report_path = "res://graphify-out/GRAPH_REPORT.md"
	if FileAccess.file_exists(report_path):
		var file = FileAccess.open(report_path, FileAccess.READ)
		var text = file.get_as_text()
		DisplayServer.clipboard_set(text)
		_log("[Graphify] Copied Graph Architecture Summary to Clipboard! Ready to paste into AI chat.")
	else:
		var text = "# Godot Project Context\nScripts: %s, Scenes: %s, Raw Tokens: %s\n" % [
			last_metrics.get("script_count"), last_metrics.get("scene_count"), last_metrics.get("estimated_raw_tokens")
		]
		DisplayServer.clipboard_set(text)
		_log("[Graphify] Copied project metrics summary to Clipboard.")

func _on_btn_run_query_pressed() -> void:
	var q = query_input.text.strip_edges()
	if q.is_empty():
		_log("[Graphify] Please enter a question or keyword to query.")
		return

	_log("[Graphify] Querying graph for: \"" + q + "\" (Budget: 1500 tokens)...")
	var global_res = ProjectSettings.globalize_path("res://")
	_run_cli(["query", q, global_res], _on_query_done)

func _on_query_done(exit_code: int, output: Array) -> void:
	if exit_code != 0:
		_log("[Graphify] Query failed (exit code %d):" % exit_code)
	for l in output:
		_log(str(l))
