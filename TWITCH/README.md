
# HOW TO RUN THE TWITCH BOT & OVERLAY


This project lets Twitch viewers influence a game in real time:

- A Twitch bot listens to chat commands (!item, !place).
- The bot broadcasts events to an overlay and/or the game via WebSocket.
- Optionally, a small Pygame "test game" shows the items visually.

----------------------------------------
1. PREREQUISITES (ALL PLATFORMS)
----------------------------------------

You need:

1. A Twitch account (and optionally a separate account for the bot)
2. A Twitch Chat OAuth token for the bot, in the form:
      oauth:xxxxxxxxxxxxxxxxxxxxxxxxxxxx
   You can get this from a Twitch OAuth generator (search “Twitch Chat OAuth token generator”).

3. The name of the Twitch channel you want the bot to join.
   Example:
      MY_CHANNEL_NAME = "aigameapg"

4. Python 3.10+ installed.
   - Windows: https://www.python.org/downloads/windows/
   - macOS: via official installer or Homebrew
   - Ubuntu: usually `python3` is already installed.

5. The project folder, for example:

   AI-Game/
     Twitch_chat_bot.py          # Twitch bot + WebSocket server
     overlay.html     # Browser/OBS overlay
     mini_game.py     # (optional) Pygame test client
     requirements.txt


----------------------------------------
2. CONFIGURE THE BOT (EDIT Twitch_chat_bot.py)
----------------------------------------

Open game.py in a text editor and set these values at the top:

   MY_TOKEN = "oauth:YOUR_REAL_TOKEN_HERE"
   MY_CHANNEL_NAME = "yourchannelname"

Leave the WebSocket port as default unless you know what you’re doing:

   WS_PORT = 8765


----------------------------------------
3. RUNNING THE TWITCH BOT (Twitch_chat_bot.py)
----------------------------------------

On ANY platform (Windows / Linux / macOS):

1) From the project folder, start the bot:

   python Twitch_chat_bot.py

3) If everything is correct, you should see messages like:

   [WS] WebSocket server listening on ws://localhost:8765
   --- BOT CONNECTED ---
   Logged as: BOT_NAME
   Joined channel: yourchannelname
   === Starting round 1 ===

Keep this terminal window open.


----------------------------------------
4. RUNNING THE OVERLAY (overlay.html)
----------------------------------------

The overlay connects to the WebSocket server at:
   ws://localhost:8765

There are two common ways to use it:


OPTION 1: Open in a normal web browser (for testing)

1) Open a browser (Chrome, Firefox, etc.).
2) You can either:
   - Open overlay.html directly (File → Open File...), OR
   - Run a small HTTP server:

In the project folder:
python -m http.server 8000

Then visit in the browser:
http://localhost:8000/overlay.html


OPTION 2: Use overlay.html in OBS as a Browser Source

1) In the project folder, start a small web server:

   python -m http.server 8000

2) In OBS:
   - Add a new Source → Browser.
   - Set the URL to:
       http://localhost:8000/overlay.html
   - Adjust width/height (e.g. 1920x1080) to match your scene.

3) The overlay will connect to:
   ws://localhost:8765
   and display votes, winning item, and placement info.


----------------------------------------
5. OPTIONAL: RUNNING THE MINI GAME (mini_game.py)
----------------------------------------

The mini game is a simple Pygame window that shows:

- Three columns: LEFT / MIDDLE / RIGHT
- Each time a spawn_item event is received from the bot,
  it draws the item (emoji + label + username) in the correct column.

To run it:

1) Open a NEW terminal.

2) Run:

   python mini_game.py

4) If the WebSocket connection succeeds, you should see:

   [GAME] WebSocket connected to ws://localhost:8765

5) When a viewer wins and uses !place left/middle/right,
   the item should appear in the corresponding column.


----------------------------------------
6. BASIC INTERACTION FROM TWITCH CHAT
----------------------------------------

While Twitch_chat_bot.py is running and the bot is connected:

1) During a voting round (e.g. 30 seconds), viewers can type:

   !item freeze
   !item fire
   !item wind
   !item shield
   !item chaos

2) After the round ends:
   - The bot chooses the winning item (highest votes).
   - It also chooses one random viewer among those who voted for that item.

3) That chosen viewer must then type in chat:

   !place left
   or
   !place middle
   or
   !place right

4) Once the !place command is accepted:
   - The bot broadcasts a `spawn_item` event via WebSocket.
   - The overlay and/or the mini game/game client display or spawn the item.
