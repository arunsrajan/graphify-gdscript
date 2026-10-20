class_name EventBus
extends Node

## Global Event Bus Autoload Singleton
## Acts as a central decoupler for signals across the entire game architecture.

signal player_damaged(new_health: int, damage_taken: int)
signal player_died
signal score_increased(points: int, total_score: int)
signal level_completed(level_number: int)
signal enemy_spawned(enemy_type: String)
