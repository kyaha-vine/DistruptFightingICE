# 🖱️ Mouse Click Integration

## What Was Added

The overlay now has a **960x640 red rectangle** at the center-right that captures mouse clicks and sends them to the chatbot.

## Visual Layout

```
Browser Window
┌──────────────────────────────────────────────────┐
│                                                  │
│  Coords: 480, 320      ┌──────────────────┐    │
│                        │                  │    │
│                        │                  │    │
│                        │   960 x 640      │    │
│                        │   Red Rectangle  │    │
│                        │   (Game Area)    │    │
│                        │                  │    │
│                        │                  │    │
│                        └──────────────────┘    │
│                                                  │
│         Vote for the next item!                 │
│              Time left: 15s                     │
│        🧊  🔥  💨  🧱  🎭                       │
└──────────────────────────────────────────────────┘
```

## Coordinate System

The red rectangle uses game coordinates:
- **Top-Left**: (0, 0)
- **Top-Right**: (960, 0)
- **Bottom-Left**: (0, 640)
- **Bottom-Right**: (960, 640)

## How It Works

1. **Visual Feedback**:
   - Hover over the red rectangle to see coordinates in real-time
   - Crosshair cursor appears when hovering
   - Rectangle flashes green when you click

2. **Mouse Release Detection**:
   - Click anywhere inside the red rectangle
   - Coordinates are converted to game space (0,0 to 960,640)
   - Data is sent to the chatbot via WebSocket

3. **Data Format Sent to Bot**:
```json
{
  "type": "mouse_click",
  "x": 480,
  "y": 320,
  "button": 0,
  "timestamp": 1702345678901
}
```

Where `button` is:
- 0 = Left click
- 1 = Middle click
- 2 = Right click

## What the Bot Does

When a mouse click is received, the bot:

1. **Logs to console**:
```
[MOUSE CLICK] LEFT button at game coords: (480, 320)
```

2. **Saves to `spawn_log.jsonl`**:
```json
{"type": "mouse_click", "x": 480, "y": 320, "button": "LEFT", "timestamp": 1702345678901, "ts": 1702345678.901}
```

3. **Ready for processing**: You can add code to:
   - Spawn items at clicked locations
   - Send coordinates to the game
   - Trigger game events
   - Broadcast to other clients

## Testing

1. **Start the bot**:
```bash
cd /home/analys/fight_rw_jv/TWITCH
python3 ./Twitch_chat_bot.py
```

2. **Start the HTTP server**:
```bash
python3 -m http.server 8000
```

3. **Open overlay in browser**:
```
http://localhost:8000/overlay.html
```

4. **Click inside the red rectangle**:
   - Watch the console for click messages
   - Check `spawn_log.jsonl` for saved clicks

## Integration Example

To use mouse clicks in your game, modify the bot to forward clicks:

```python
# In ws_client_handler, after receiving mouse click:
if data.get("type") == "mouse_click":
    # Forward to game or trigger action
    game_event = {
        "type": "spawn_at_position",
        "x": data.get("x"),
        "y": data.get("y")
    }
    await broadcast_to_ws_clients(game_event)
```

## Next Steps

You can now:
1. Connect your FightingICE game to listen for these coordinates
2. Use clicks to spawn items at specific locations
3. Create interactive overlays where viewers click to affect gameplay
4. Combine with Twitch voting: vote for item, click where to spawn it
