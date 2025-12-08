# 🎮 How to Run the TWITCH Demos

## Prerequisites

Make sure the Twitch bot is running first:
```bash
cd /home/analys/fight_rw_jv/TWITCH
python3 ./Twitch_chat_bot.py
```

The bot creates a WebSocket server on `ws://localhost:8765` that both demos connect to.

---

## 📺 Demo 1: HTML Overlay (Browser)

### What it does:
- Shows a **visual overlay** of the voting process
- Displays all items with **live vote counts**
- Shows **countdown timer** during voting
- Announces the **winner** with animations
- Shows **placement instructions** for the winner

### How to run:

#### Option A: Direct File (Simple)
1. Open a web browser (Chrome, Firefox, Edge)
2. Press `Ctrl+O` (File → Open File)
3. Navigate to: `/home/analys/fight_rw_jv/TWITCH/overlay.html`
4. Open the file

#### Option B: HTTP Server (Recommended for OBS)
1. Start a simple HTTP server:
```bash
cd /home/analys/fight_rw_jv/TWITCH
python3 -m http.server 8000
```

2. Open browser and go to:
```
http://localhost:8000/overlay.html
```

3. **For OBS Studio:**
   - Add Source → Browser
   - URL: `http://localhost:8000/overlay.html`
   - Width: 1920, Height: 1080
   - Check "Refresh browser when scene becomes active"

### What you'll see:
```
┌─────────────────────────────────────────────────┐
│           Winner: 🔥 Power Core                 │
│    @username place it with !place left|mid|right│
└─────────────────────────────────────────────────┘

            Vote for the next item!
              Time left: 15s
     ┌──────┬──────┬──────┬──────┬──────┐
     │ 🧊   │ 🔥   │ 💨   │ 🧱   │ 🎭   │
     │Freeze│Power │ Wind │Shield│Chaos │
     │ 2    │ 5    │ 1    │ 0    │ 1    │
     │votes │votes │votes │votes │votes │
     └──────┴──────┴──────┴──────┴──────┘
```

---

## 🎨 Demo 2: Pygame Mini Game (Visual Demo)

### What it does:
- Shows **3 zones**: LEFT | MIDDLE | RIGHT
- When items are spawned, they appear in the chosen zone
- Shows the **emoji**, **item name**, and **who placed it**
- Items stack vertically in each zone

### How to run:

1. Make sure Pygame is installed:
```bash
pip install pygame
```

2. In a **NEW terminal** (keep bot running), run:
```bash
cd /home/analys/fight_rw_jv/TWITCH
python3 mini_game.py
```

### What you'll see:
```
┌────────────────────────────────────────┐
│ LEFT      │   MIDDLE    │    RIGHT     │
│           │             │              │
│           │    🔥       │              │
│           │ Power Core  │              │
│           │ by user123  │              │
│           │             │              │
│  🧊       │             │    💨        │
│Freeze Orb │             │ Wind Boots   │
│by user456 │             │ by user789   │
│           │             │              │
└────────────────────────────────────────┘
Spawn: 🔥 Power Core at middle by user123
```

---

## 🔄 Full Demo Workflow

### Terminal Setup:

**Terminal 1 - Bot:**
```bash
cd /home/analys/fight_rw_jv/TWITCH
python3 ./Twitch_chat_bot.py
```

**Terminal 2 - HTTP Server (optional for overlay):**
```bash
cd /home/analys/fight_rw_jv/TWITCH
python3 -m http.server 8000
```

**Terminal 3 - Mini Game (optional):**
```bash
cd /home/analys/fight_rw_jv/TWITCH
python3 mini_game.py
```

### Browser:
- Open: `http://localhost:8000/overlay.html`

### Twitch Chat:
- Go to your stream at `twitch.tv/aigameapg`
- Viewers vote with: `!item fire`
- Winner places with: `!place middle`

---

## 🎯 Testing Without Twitch

If you want to test locally without real Twitch viewers, you can:

1. Go to your own Twitch channel page
2. Use the chat to send commands yourself
3. Or create a simple test account and send commands from there

The bot will respond to any chat messages in the channel!

---

## 📊 What Each Demo Shows

| Feature | HTML Overlay | Pygame Mini Game |
|---------|-------------|------------------|
| Live votes | ✅ Yes | ❌ No |
| Countdown timer | ✅ Yes | ❌ No |
| Winner announcement | ✅ Yes | ❌ No |
| Spawned items | ❌ No | ✅ Yes (visual) |
| Placement zones | ❌ No | ✅ Yes (L/M/R) |
| OBS compatible | ✅ Yes | ❌ No |

**Best use case:**
- **Overlay**: For streaming - shows voting to viewers
- **Mini Game**: For testing/demo - visualizes where items spawn

---

## 🐛 Troubleshooting

**Overlay shows "Waiting for round":**
- Check if bot is running
- Open browser console (F12) - should see "Connected to WebSocket"
- Check WebSocket URL is `ws://localhost:8765`

**Mini game won't connect:**
- Check if bot is running
- Check terminal output for connection messages
- Make sure no firewall blocking port 8765

**No items appearing:**
- Vote during the 30-second voting window
- Wait for round to end
- Winner must use `!place` command within 15 seconds
