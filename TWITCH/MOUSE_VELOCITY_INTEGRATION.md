# 🎮 Mouse Velocity Integration with Game

## Overview

The Twitch bot now captures continuous mouse movement with velocity and sends it to the FightingICE game using protobuf messages, **only when an item is pending/selected**.

## How It Works

### 1. **Overlay (HTML) Tracking**

The overlay continuously tracks mouse position and calculates velocity:

- **On mousedown**: Start tracking
- **On mousemove**: Update position and calculate velocity (clamped -3 to 3)
- **Send loop**: Every 33ms (~30 Hz), send current coords + velocity
- **On mouseup**: Send final message with `terminate: true`

Display shows: `Coords: 480, 320 | V: (2, 1)` (X, Y velocity)

### 2. **Bot (Python) Processing**

The bot receives mouse events and:

1. **Checks pending status**: Is an item currently selected?
   - YES ✅ → Send to game via protobuf
   - NO ❌ → Ignore, don't send to game

2. **Sends to Game**: Protobuf `GrpcGameEvent` with:
   - `x, y`: Game coordinates (0-960, 0-640)
   - `vx, vy`: Velocity (-3 to 3)
   - `terminate`: `true` on mouse release, `false` while dragging
   - `event_id`: Auto-incremented for each placement

3. **Logs Everything**: All events saved to `spawn_log.jsonl`

## Data Flow

```
Browser Overlay
   ↓ (Mouse event every 33ms)
   │ {x, y, vx, vy, terminate}
   ↓
Twitch Bot WebSocket Handler
   ├─ Check: pending_placement exists?
   ├─ YES → send_game_event(x, y, vx, vy, terminate)
   │        ↓
   │        Game Socket (protobuf)
   │
   └─ NO → Ignore (log without sending)
```

## Example Scenario

### Round Flow:

1. **Round 16 starts** → Voting for items
2. **Round 16 ends** → "Fire" wins!
3. **Chosen winner announcement**: `@user123 place it!`
4. **pending_placement = {round: 16, item: "fire", user: "user123"}`
5. **User clicks red rectangle and drags**:
   - `mousemove` → Track position/velocity
   - Every 33ms → Send: `{x:100, y:200, vx:2, vy:1, terminate:false}`
   - **Bot receives** → "Item pending, sending to game!" ✅
6. **User releases mouse**:
   - `mouseup` → Send: `{x:150, y:250, vx:1, vy:0, terminate:true}`
   - **Bot receives** → Sends final event to game, increments event_id ✅
7. **Next round** → `pending_placement = None`
8. **User clicks again**:
   - Bot receives → "No item selected, ignoring" ❌

## Console Output Example

```
[MOUSE EVENT] Coords: (100, 200), Velocity: (2, 1), Terminate: false
[GAME] Item pending: fire, sending to game...
[GAME] Sent event: ID=0, X=100, Y=200, VX=2, VY=1, Term=false

[MOUSE EVENT] Coords: (150, 250), Velocity: (1, 0), Terminate: true
[GAME] Item pending: fire, sending to game...
[GAME] Sent event: ID=0, X=150, Y=250, VX=1, VY=0, Term=true

[MOUSE EVENT] Coords: (200, 300), Velocity: (2, 2), Terminate: false
[GAME] No item selected, ignoring mouse event
```

## Log File (`spawn_log.jsonl`)

When **item is pending** (sent to game):
```json
{"type": "mouse_event", "x": 100, "y": 200, "vx": 2, "vy": 1, "terminate": false, "item": "fire", "sent_to_game": true, "ts": 1702345678.901}
```

When **no item pending** (NOT sent to game):
```json
{"type": "mouse_event", "x": 200, "y": 300, "vx": 2, "vy": 2, "terminate": false, "sent_to_game": false, "ts": 1702345678.934}
```

## Game Connection

The bot connects to the game server at:
- **Host**: 127.0.0.1 (localhost)
- **Port**: 31415
- **Role**: 6 (Game Event Injector)

If the game isn't running, the bot logs a warning but continues to work (events are just not sent).

## Testing

1. **Start bot**: `python3 ./Twitch_chat_bot.py`
2. **Start server**: `python3 -m http.server 8000`
3. **Open overlay**: `http://localhost:8000/overlay.html`
4. **Wait for item** to be pending in Twitch chat
5. **Click and drag in red rectangle**
6. **Watch bot console** for:
   - ✅ `[GAME] Item pending: ... sending to game...`
   - ✅ `[GAME] Sent event: ...`

## Velocity Calculation

Velocity is calculated from frame-to-frame movement:

```javascript
vx = clampedX - lastX  // -3 to 3
vy = clampedY - lastY  // -3 to 3
```

Clamped to prevent unrealistic speeds.

## Important Notes

⚠️ **Mouse events ONLY sent to game when:**
- `pending_placement` is NOT None
- An item has been won and is waiting for placement
- Winner hasn't placed it yet (within 15 seconds)

⚠️ **If game is not running:**
- Bot will log: `[GAME] Connection failed: ...`
- Mouse events will still be logged to file
- Overlay still works normally

⚠️ **Event IDs:**
- Increment only on `terminate: true`
- So one drag = 1 event ID (multiple frames)
- Next placement starts at next ID
