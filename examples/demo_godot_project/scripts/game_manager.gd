class_name GameManager
extends Node

## Central Game Orchestration Singleton
## Manages global high score, game loops, levels, and player lifecycles.

@export var max_lives: int = 3
var current_score: int = 0
var current_lives: int = 3
var active_player: CharacterBody2D = null

func _ready() -> void:
	current_lives = max_lives
	EventBus.player_damaged.connect(_on_player_damaged)
	EventBus.player_died.connect(_on_player_died)

func register_player(player: CharacterBody2D) -> void:
	active_player = player

func add_score(points: int) -> void:
	current_score += points
	EventBus.score_increased.emit(points, current_score)

func _on_player_damaged(new_health: int, damage_taken: int) -> void:
	if new_health <= 0:
		handle_life_lost()

func handle_life_lost() -> void:
	current_lives -= 1
	if current_lives <= 0:
		trigger_game_over()

func trigger_game_over() -> void:
	print("Game Over! Final Score: ", current_score)

func restart_game() -> void:
	current_score = 0
	current_lives = max_lives
	get_tree().reload_current_scene()
