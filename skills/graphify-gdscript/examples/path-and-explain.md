# Example: path between symbols, and explain

Output below is real, from the demo Godot project in the repository's `examples/demo_godot_project`.

## Path

**User:** How does the Player reach the GameManager?

**Command:** `graphify-gdscript path "Player" "GameManager"`

```
## Path: `Player` -> `GameManager` (4 hops)

- `Player` --[contains]--> `Player.take_damage` (scripts/player.gd L40)
- `Player.take_damage` --[emits]--> `Signal:player_damaged` (scripts/player.gd L43)
- `Signal:player_damaged` --[connects_to]--> `GameManager._on_player_damaged` (scripts/game_manager.gd L14)
- `GameManager._on_player_damaged` <--[contains]-- `GameManager` (scripts/game_manager.gd L24)
```

**Expected agent answer:** The two are linked only through a signal. `Player.take_damage` emits `player_damaged` (`scripts/player.gd:L43`), which is connected to `GameManager._on_player_damaged` (`scripts/game_manager.gd:L14`). There is no direct call between them.

## Explain

**User:** What does `take_damage` on the player do?

**Command:** `graphify-gdscript explain "Player.take_damage"`

```
## `Player.take_damage` (function)
Defined at: scripts/player.gd L40

### Outgoing (7)
- --[emits]--> `Signal:health_changed` (L42)
- --[emits]--> `Signal:player_damaged` (L43)
- --[uses_autoload]--> `Autoload:EventBus` (L43)
- --[calls]--> `Player.die` (L46)

### Incoming (2)
- <--[contains]-- `Player` (L40)
- <--[calls]-- `Player._on_hurtbox_area_entered` (L53)
```

**Expected agent answer:** `Player.take_damage` (`scripts/player.gd:L40`) emits `health_changed` and `player_damaged` (through the `EventBus` autoload) and calls `Player.die` (`L46`). It is called from `_on_hurtbox_area_entered` (`L53`).
