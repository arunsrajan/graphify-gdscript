class_name Enemy
extends CharacterBody2D

## Base Alien Enemy
## Advances towards bottom of screen, takes damage, awards score on defeat.

signal defeated(points: int)

@export var health: int = 50
@export var speed: float = 120.0
@export var score_reward: int = 150

@onready var hitbox: Area2D = $Hitbox

func _physics_process(delta: float) -> void:
	velocity = Vector2.DOWN * speed
	move_and_slide()

func take_damage(amount: int) -> void:
	health -= amount
	if health <= 0:
		defeat()

func defeat() -> void:
	defeated.emit(score_reward)
	GameManager.add_score(score_reward)
	queue_free()

func _on_hitbox_body_entered(body: Node2D) -> void:
	if body is Player:
		body.take_damage(25)
		queue_free()
