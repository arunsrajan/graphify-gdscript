# Example: trace a signal

Output below is real, from the demo Godot project in the repository's `examples/demo_godot_project`.

**User:** Who listens to `player_damaged`?

**Command:** `graphify-gdscript trace "player_damaged"`

**Graph output:**

```
- `EventBus` --[declares_signal]--> `EventBus.player_damaged` (scripts/event_bus.gd L7)
- `Signal:player_damaged` --[connects_to]--> `GameManager._on_player_damaged` (scripts/game_manager.gd L14)
- `Signal:player_damaged` --[connects_to]--> `HUD._on_player_damaged` (scripts/hud.gd L12)
- `Player.take_damage` --[emits]--> `Signal:player_damaged` (scripts/player.gd L43)
- `Player.take_damage` --[emits]--> `EventBus.player_damaged` (scripts/player.gd L43)
```

**Expected agent answer:**

> **Answer:** `player_damaged` is declared on the `EventBus` autoload, emitted by `Player.take_damage`, and handled by `GameManager` and `HUD`.
>
> **Evidence:**
> - `scripts/event_bus.gd:L7` declares the signal
> - `scripts/player.gd:L43` emits it
> - `scripts/game_manager.gd:L14` connects it to `_on_player_damaged`
> - `scripts/hud.gd:L12` connects it to `_on_player_damaged`
>
> **Gaps:** none found.
