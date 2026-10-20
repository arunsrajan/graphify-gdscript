class_name HUD
extends CanvasLayer

## Heads Up Display (HUD)
## Subscribes to global EventBus and Player signals to render score and health.

@onready var score_label: Label = $Margin/VBox/ScoreLabel
@onready var health_bar: ProgressBar = $Margin/VBox/HealthBar

func _ready() -> void:
	EventBus.score_increased.connect(_on_score_increased)
	EventBus.player_damaged.connect(_on_player_damaged)
	EventBus.player_died.connect(_on_player_died)

func _on_score_increased(points: int, total_score: int) -> void:
	score_label.text = "Score: " + str(total_score)

func _on_player_damaged(new_health: int, damage_taken: int) -> void:
	health_bar.value = new_health

func _on_player_died() -> void:
	score_label.text = "PLAYER DOWN"
