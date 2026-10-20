@tool
class_name GraphifyTokenEstimator
extends RefCounted

## Calculates Godot project code volume, raw LLM tokens, and estimated savings.

static func calculate_project_metrics(root_dir: String = "res://") -> Dictionary:
	var files: Array[String] = []
	_scan_dir(root_dir, files)

	var total_words: int = 0
	var total_lines: int = 0
	var script_count: int = 0
	var scene_count: int = 0

	for file_path in files:
		var ext = file_path.get_extension().to_lower()
		if ext == "gd":
			script_count += 1
		elif ext == "tscn":
			scene_count += 1

		var file = FileAccess.open(file_path, FileAccess.READ)
		if file:
			var content = file.get_as_text()
			var lines = content.split("\n")
			total_lines += lines.size()
			for l in lines:
				var words = l.strip_edges().split(" ", false)
				total_words += words.size()

	# 1 word in code ≈ 1.35 LLM tokens
	var estimated_raw_tokens: int = int(total_words * 1.35)
	var avg_graph_context_tokens: int = 1500
	var tokens_saved: int = maxi(estimated_raw_tokens - avg_graph_context_tokens, 0)
	var percent_saved: float = 0.0
	if estimated_raw_tokens > 0:
		percent_saved = (float(tokens_saved) / float(estimated_raw_tokens)) * 100.0

	return {
		"script_count": script_count,
		"scene_count": scene_count,
		"total_lines": total_lines,
		"total_words": total_words,
		"estimated_raw_tokens": estimated_raw_tokens,
		"avg_graph_tokens": avg_graph_context_tokens,
		"tokens_saved": tokens_saved,
		"percent_saved": percent_saved,
		"estimated_cost_saved_usd": (float(tokens_saved) / 1000000.0) * 3.0
	}

static func _scan_dir(dir_path: String, out_files: Array[String]) -> void:
	var dir = DirAccess.open(dir_path)
	if not dir:
		return

	dir.list_dir_begin()
	var file_name = dir.get_next()

	while file_name != "":
		if file_name.begins_with(".") or file_name == "graphify-out" or file_name == "addons":
			file_name = dir.get_next()
			continue

		var full_path = dir_path.path_join(file_name)
		if dir.current_is_dir():
			_scan_dir(full_path, out_files)
		else:
			var ext = file_name.get_extension().to_lower()
			if ext in ["gd", "tscn", "tres", "godot"]:
				out_files.append(full_path)

		file_name = dir.get_next()
	dir.list_dir_end()
