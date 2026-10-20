class_name Player
extends CharacterBody2D

## Player Ship Controller
## Handles 2D vector movement, weapon firing, hurtbox triggers, and health state.

signal health_changed(current: int, max_hp: int)
signal fired_bullet(position: Vector2)

const BulletScene = preload("res://scenes/bullet.tscn")

@export var max_health: int = 100
@export var speed: float = 400.0

@onready var sprite: Sprite2D = $Sprite2D
@onready var hurtbox: Area2D = %Hurtbox
@onready var gun_mount: Node2D = $GunMount

var current_health: int = 100

func _ready() -> void:
	current_health = max_health
	GameManager.register_player(self)
	hurtbox.area_entered.connect(_on_hurtbox_area_entered)

func _physics_process(delta: float) -> void:
	var dir = Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	velocity = dir * speed
	move_and_slide()

	if Input.is_action_just_pressed("ui_accept"):
		fire_weapon()

func fire_weapon() -> void:
	var bullet = BulletScene.instantiate()
	bullet.global_position = gun_mount.global_position
	get_parent().add_child(bullet)
	fired_bullet.emit(gun_mount.global_position)

func take_damage(amount: int) -> void:
	current_health = clampi(current_health - amount, 0, max_health)
	health_changed.emit(current_health, max_health)
	EventBus.player_damaged.emit(current_health, amount)
	
	if current_health <= 0:
		die()

func die() -> void:
	EventBus.player_died.emit()
	queue_free()

func _on_hurtbox_area_entered(area: Area2D) -> void:
	take_damage(20)
