#!/usr/bin/env python3
# python_server_deploy.py
#
# This version is for DEPLOYMENT or when overlay.html/js are hosted externally (e.g. on Twitch).
# It DOES NOT serve static files.
# It ONLY handles:
# 1. WebSocket connections (/ws)
# 2. Twitch Chat Bot
# 3. Game Communication (Protobuf)
# 4. Voting Logic

import os
import ssl
import json
import time
import asyncio
import contextlib
import random
import socket
import struct
from pathlib import Path
from typing import Dict, Set, Any, Optional
import sys

# Add src_python to path for protobuf
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src_python'))
try:
    import message_pb2
except ImportError:
    print("Warning: message_pb2 not found. Game events will not be sent.")
    message_pb2 = None

import certifi
import aiohttp
from aiohttp import web, TCPConnector
from aiohttp_cors import setup, ResourceOptions
from twitchio.ext import commands

# =========================
# Protobuf (optional)
# =========================
# Configured above


# =========================
# SSL FIX (Cross-platform)
# =========================
# This is primarily for Windows/macOS but safe to keep on Linux
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
_ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl._create_default_https_context = lambda: _ssl_context  # noqa

# =========================
# Configuration
# =========================
HTTP_HOST = "0.0.0.0"
HTTP_PORT = 8080

ROUND_DURATION = 10
ROUND_BREAK_SECONDS = 5
PLACEMENT_TIMEOUT = 5

TWITCH_TOKEN = os.environ.get("TWITCH_TOKEN", "oauth:facx4e33l8089ysaih1ttihovdd6de").strip()
TWITCH_CHANNEL = os.environ.get("TWITCH_CHANNEL", "aigameapg").strip()

LOG_FILE = "spawn_log.jsonl"

ITEMS: Dict[str, Dict[str, str]] = {
    "freeze":  {"emoji": "🧊", "label": "Freeze Orb"},
    "fire":    {"emoji": "🔥", "label": "Power Core"},
    "wind":    {"emoji": "💨", "label": "Wind Boots"},
    "shield":  {"emoji": "🧱", "label": "Shield Stone"},
    "chaos":   {"emoji": "🎭", "label": "Chaos Mask"},
    "warp":    {"emoji": "🌀", "label": "Space Warp"},
    "bomb":    {"emoji": "⏳", "label": "Time Bomb"},
    "spout":   {"emoji": "🌋", "label": "Flame Spout"},
}

# =========================
# Global state
# =========================
clients: Set[web.WebSocketResponse] = set()

# WS -> twitch_user_id map (so we can authorize winner)
ws_user_id: Dict[web.WebSocketResponse, Optional[str]] = {}

BOT_INSTANCE: Optional["ChatBot"] = None

current_round_active: bool = False
current_round_id: int = 0
current_votes: Dict[str, int] = {k: 0 for k in ITEMS.keys()}

# Track voters by item using Twitch user_id (not only names)
votes_by_item_ids: Dict[str, Set[str]] = {k: set() for k in ITEMS.keys()}
user_id_to_name: Dict[str, str] = {}  # id -> latest name

round_end_ts: float = 0.0

# pending placement:
# { "round_id": int, "item_key": str, "chosen_user": str, "chosen_user_id": str, "ts": float }
pending_placement: Optional[Dict[str, Any]] = None

# Game socket
# GAME_SOCKET and send_game_event removed as requested
game_writer = None
game_event_id = 0
active_mouse_start = (0, 0)

ITEM_TYPE_MAP = {
    "freeze": 1,
    "fire": 2,
    "wind": 3,
    "shield": 4,
    "chaos": 5,
    "warp": 6,
    "bomb": 7,
    "spout": 8
}


# =========================
# Helpers
# =========================
def compute_remaining_seconds() -> int:
    if not current_round_active:
        return 0
    remain = int(round_end_ts - time.time())
    return max(0, remain)

def build_state_payload() -> dict:
    return {
        "type": "state",
        "round": {
            "active": current_round_active,
            "round_id": current_round_id,
            "duration_remaining": compute_remaining_seconds(),
        },
        "options": [{"key": k, "emoji": v["emoji"], "label": v["label"]} for k, v in ITEMS.items()],
        "votes": current_votes,
        "pending_placement": pending_placement,
    }

async def broadcast_ws(data: dict) -> None:
    if not clients:
        return
    msg = json.dumps(data, ensure_ascii=False)
    dead = []
    for ws in list(clients):
        try:
            await ws.send_str(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)
        ws_user_id.pop(ws, None)

async def send_state(ws: web.WebSocketResponse) -> None:
    await ws.send_str(json.dumps(build_state_payload(), ensure_ascii=False))

async def send_chat_message(message: str) -> None:
    global BOT_INSTANCE
    if not BOT_INSTANCE:
        return
    try:
        channel = BOT_INSTANCE.get_channel(TWITCH_CHANNEL)
        if channel:
            await channel.send(message)
    except Exception as e:
        print(f"[CHAT ERROR] Failed to send message: {e}")

# place_item_in_game removed as requested

async def register_vote(user_id: str, item_key: str):
    global current_votes, votes_by_item_ids, user_id_to_name

    # Check if user already voted
    previous_vote = None
    for k, voters in votes_by_item_ids.items():
        if user_id in voters:
            previous_vote = k
            break
    
    if previous_vote == item_key:
        return # Already voted for this item

    if previous_vote:
        # Remove previous vote
        votes_by_item_ids[previous_vote].discard(user_id)
        current_votes[previous_vote] = max(0, current_votes.get(previous_vote, 1) - 1)
        
        # Broadcast update for the old item
        await broadcast_ws({
            "type": "vote",
            "item": previous_vote,
            "emoji": ITEMS[previous_vote]["emoji"],
            "count": current_votes[previous_vote],
        })
    
    # Add new vote
    current_votes[item_key] = current_votes.get(item_key, 0) + 1
    votes_by_item_ids.setdefault(item_key, set()).add(user_id)

    # Broadcast update for the new item
    await broadcast_ws({
        "type": "vote",
        "item": item_key,
        "emoji": ITEMS[item_key]["emoji"],
        "count": current_votes[item_key],
    })

# =========================
# Twitch bot
# =========================
class ChatBot(commands.Bot):
    def __init__(self):
        self._custom_connector = TCPConnector(ssl=False)
        self._custom_session = aiohttp.ClientSession(connector=self._custom_connector)

        super().__init__(
            token=TWITCH_TOKEN,
            prefix="!",
            initial_channels=[TWITCH_CHANNEL],
        )
        self._http.session = self._custom_session

    async def event_ready(self):
        print(f"--- BOT CONNECTED: {self.nick} --- (channel: {TWITCH_CHANNEL})")

    async def event_message(self, message):
        # Check for echo (bot's own message)
        if getattr(message, "echo", False):
            print(f"[CHAT] [BOT]: {message.content}")
            return

        # If author is missing, it's likely the bot itself (in some twitchio versions)
        # or a system message. We treat it as the bot to avoid "Unknown".
        if not message.author:
            print(f"[CHAT] [BOT*]: {message.content}")
            return

        print(f"[CHAT] {message.author.name}: {message.content}")
        await self.handle_commands(message)

    @commands.command(name="items")
    async def items_command(self, ctx: commands.Context):
        items_list = " | ".join([f"{v['emoji']} {k}" for k, v in ITEMS.items()])
        await ctx.send(f"Available items: {items_list} | Vote with: !item <name>")

    @commands.command(name="item")
    async def item_command(self, ctx: commands.Context):
        global current_round_active

        parts = ctx.message.content.split(maxsplit=1)
        if len(parts) < 2:
            await ctx.send("Usage: !item <item_key>")
            return

        choice = parts[1].strip().lower()
        if choice not in ITEMS:
            await ctx.send(f"Unknown item. Try: {', '.join(ITEMS.keys())}")
            return

        if not current_round_active:
            await ctx.send("No vote running right now. Wait for the next round!")
            return

        author = ctx.author
        user_name = author.name if author else "Unknown"
        user_id = str(getattr(author, "id", "")) if author else ""

        if not user_id:
            return

        # remember name
        user_id_to_name[user_id] = user_name

        await register_vote(user_id, choice)

    @commands.command(name="place")
    async def place_command(self, ctx: commands.Context):
        # Deprecated: Placement is now done via overlay click
        await ctx.send("Please click on the overlay to place your item!")

async def connect_game_socket():
    global game_writer
    try:
        _, writer = await asyncio.open_connection('127.0.0.1', 31415)
        writer.write(b'\x06') # Role: Game Event Injector
        await writer.drain()
        game_writer = writer
        print("Connected to game server.")
    except Exception as e:
        print(f"Game connection failed: {e}")
        game_writer = None

async def send_game_event(event_type, x, y, vx, vy, terminate):
    global game_writer, game_event_id
    if not message_pb2: return
    
    if game_writer is None:
        await connect_game_socket()
        if game_writer is None: return

    try:
        event = message_pb2.GrpcGameEvent()
        event.event_id = game_event_id
        event.event_type = event_type
        event.x = int(x)
        event.y = int(y)
        event.vx = int(vx)
        event.vy = int(vy)
        event.time = 180
        event.terminate = terminate
        
        data = event.SerializeToString()
        game_writer.write(struct.pack('<I', len(data)))
        game_writer.write(data)
        await game_writer.drain()
        print(f"Sent Game Event: Type={event_type}, X={x}, Y={y}, VX={vx}, VY={vy}, Term={terminate}")

        if terminate:
            game_event_id += 1
    except Exception as e:
        print(f"Failed to send game event: {e}")
        game_writer = None

async def handle_game_mouse_event(m_state, x, y, ws):
    global active_mouse_start, pending_placement
    
    user_id = ws_user_id.get(ws)
    # Check if this user is the chosen one
    if not pending_placement or str(pending_placement.get("chosen_user_id")) != str(user_id):
        return

    if m_state == 0: # Hover
        await send_game_event(0, x, y, 0, 0, False)
        
    elif m_state == 1: # Start
        active_mouse_start = (x, y)
        
    elif m_state == 3: # End
        start_x, start_y = active_mouse_start
        dx = x - start_x
        dy = y - start_y
        
        vx = int(dx / 20)
        vy = int(dy / 20)
        
        item_key = pending_placement.get("item_key")
        item_type = max(min(ITEM_TYPE_MAP.get(item_key, 1),5),0)
        
        await send_game_event(item_type, start_x, start_y, vx, vy, True)

# =========================
# Rounds loop
# =========================
async def rounds_loop():
    global current_round_active, current_votes, current_round_id, votes_by_item_ids, pending_placement, round_end_ts

    await asyncio.sleep(3)

    while True:
        current_round_id += 1
        print(f"=== Starting round {current_round_id} ===")

        current_votes = {k: 0 for k in ITEMS.keys()}
        votes_by_item_ids = {k: set() for k in ITEMS.keys()}
        pending_placement = None

        current_round_active = True
        round_end_ts = time.time() + ROUND_DURATION

        items_list = " | ".join([f"{v['emoji']} {k}" for k, v in ITEMS.items()])
        await send_chat_message(
            f"🎮 Round {current_round_id} starts! Vote with: !item <name> | {ROUND_DURATION}s | {items_list}"
        )

        await broadcast_ws({
            "type": "round_start",
            "round_id": current_round_id,
            "duration": ROUND_DURATION,
            "options": [{"key": k, "emoji": v["emoji"], "label": v["label"]} for k, v in ITEMS.items()],
        })

        for remaining in (20, 10, 5):
            await asyncio.sleep(max(0, round_end_ts - time.time() - remaining))
            if current_round_active and remaining > 0:
                await send_chat_message(f"⏰ {remaining} seconds left to vote!")

        await asyncio.sleep(max(0, round_end_ts - time.time()))
        
        # Wait a bit for final "locked in" votes or timeout votes to arrive
        await asyncio.sleep(0.5)

        current_round_active = False
        round_end_ts = 0.0

        max_votes = max(current_votes.values()) if current_votes else 0
        winner_key = max(current_votes, key=lambda k: current_votes[k]) if max_votes > 0 else None

        winner = None
        if winner_key:
            winner = {
                "key": winner_key,
                "emoji": ITEMS[winner_key]["emoji"],
                "label": ITEMS[winner_key]["label"],
                "votes": current_votes[winner_key],
            }

        await broadcast_ws({
            "type": "round_result",
            "round_id": current_round_id,
            "winner": winner,
            "votes": current_votes,
        })

        if not winner_key:
            await send_chat_message(f"❌ Round {current_round_id} ended with no votes. Next round in {ROUND_BREAK_SECONDS}s...")
            await asyncio.sleep(ROUND_BREAK_SECONDS)
            continue

        vote_summary = " | ".join([f"{ITEMS[k]['emoji']} {v}" for k, v in current_votes.items() if v > 0])
        await send_chat_message(f"📊 Votes: {vote_summary}")

        # Choose winner among voters (by user_id)
        voter_ids = list(votes_by_item_ids.get(winner_key, []))
        if voter_ids:
            chosen_user_id = random.choice(voter_ids)
            chosen_user = user_id_to_name.get(chosen_user_id, "Overlay Viewer")

            pending_placement = {
                "round_id": current_round_id,
                "item_key": winner_key,
                "chosen_user": chosen_user,
                "chosen_user_id": chosen_user_id,
                "ts": time.time(),
            }

            # Only mention user if we actually know their name (from chat)
            # Otherwise just say "A viewer" or similar
            if chosen_user == "Overlay Viewer":
                msg = (f"🏆 {ITEMS[winner_key]['emoji']} {ITEMS[winner_key]['label']} wins! "
                       f"A viewer is placing it! ({PLACEMENT_TIMEOUT}s)")
            else:
                msg = (f"🏆 {ITEMS[winner_key]['emoji']} {ITEMS[winner_key]['label']} wins! "
                       f"@{chosen_user} - Click the overlay to place it! ({PLACEMENT_TIMEOUT}s)")
            
            await send_chat_message(msg)

            await broadcast_ws({
                "type": "placement_request",
                "round_id": current_round_id,
                "item_key": winner_key,
                "emoji": ITEMS[winner_key]["emoji"],
                "label": ITEMS[winner_key]["label"],
                "chosen_user": chosen_user,
                "chosen_user_id": chosen_user_id,
                "hint": "Click the overlay to place your item!",
            })

        await asyncio.sleep(ROUND_BREAK_SECONDS)

# =========================
# HTTP / WS Handlers (aiohttp)
# =========================
@web.middleware
async def log_middleware(request, handler):
    # Only log non-WS requests to keep console clean
    if "/ws" not in request.path:
        print(f"[HTTP] {request.method} {request.path}")
    return await handler(request)

async def ws_handler(request: web.Request):
    global pending_placement

    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)

    clients.add(ws)
    ws_user_id[ws] = None

    print(f"[WS] client connected. clients={len(clients)} path={request.path}")

    await send_state(ws)

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except Exception:
                    continue

                t = data.get("type")

                if t == "ping":
                    await ws.send_str(json.dumps({"type": "pong", "t": int(time.time() * 1000)}))
                    continue

                # Save twitch_user_id from overlay_hello (no prompt needed)
                if t == "overlay_hello":
                    tid = data.get("twitch_user_id")
                    ws_user_id[ws] = str(tid) if tid else None
                    await send_state(ws)
                    continue

                # ✅ Handle click votes from overlay
                if t == "vote_click":
                    if not current_round_active:
                        continue
                    
                    item_key = data.get("item")
                    if item_key not in ITEMS:
                        continue

                    user_id = ws_user_id.get(ws)
                    if not user_id:
                        # If user hasn't granted permissions, we can't track their vote uniquely
                        # For now, we ignore anonymous votes to prevent spam
                        continue

                    # Use cached name if available, else generic
                    # user_name = user_id_to_name.get(user_id, "Overlay Viewer")

                    await register_vote(user_id, item_key)
                    continue

                if t in ("get_state", "sync"):
                    await send_state(ws)
                    continue

                # Mouse events
                if t == "mouse_event":
                    m_state = int(data.get("mouse_type", 0)) # 0=Hover, 1=Start, 2=Drag, 3=End
                    x = int(data.get("x", 0))
                    y = int(data.get("y", 0))

                    # Print every mouse message as requested
                    print(f"[MOUSE] Type: {m_state}, X: {x}, Y: {y}")
                    
                    await handle_game_mouse_event(m_state, x, y, ws)
                    
                    await broadcast_ws({
                        "type": "mouse_event",
                        "mouse_type": m_state,
                        "x": x,
                        "y": y
                    })
                    continue

            elif msg.type == web.WSMsgType.ERROR:
                print(f"[WS] error: {ws.exception()}")

    finally:
        clients.discard(ws)
        ws_user_id.pop(ws, None)
        print(f"[WS] client disconnected. clients={len(clients)}")

    return ws

async def health_handler(request: web.Request):
    return web.json_response({
        "ok": True,
        "clients": len(clients),
        "round_active": current_round_active,
        "round_id": current_round_id,
        "pending": pending_placement,
    })

# =========================
# Main
# =========================
async def main():
    global BOT_INSTANCE

    # Game socket removed

    app = web.Application(middlewares=[log_middleware])

    # CORS is still needed because the overlay (hosted on Twitch) 
    # will be connecting to this server (hosted elsewhere)
    cors = setup(app, defaults={
        "*": ResourceOptions(allow_credentials=True, expose_headers="*", allow_headers="*")
    })

    r_ws1 = app.router.add_get("/ws", ws_handler)
    r_ws2 = app.router.add_get("/ws/", ws_handler)
    r_health = app.router.add_get("/health", health_handler)

    for r in [r_ws1, r_ws2, r_health]:
        cors.add(r)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, HTTP_HOST, HTTP_PORT)
    await site.start()

    print("\n--- SERVER RUNNING (DEPLOY MODE) ---")
    print(f"WS:     ws://{HTTP_HOST}:{HTTP_PORT}/ws")
    print(f"Health: http://{HTTP_HOST}:{HTTP_PORT}/health")
    print("Note: Static files (overlay.html/js) are NOT served by this script.")
    print("      They should be hosted by Twitch or another web server.\n")

    bot = ChatBot()
    BOT_INSTANCE = bot

    rounds_task = asyncio.create_task(rounds_loop())

    try:
        await bot.start()
    finally:
        rounds_task.cancel()
        with contextlib.suppress(Exception):
            await rounds_task

        with contextlib.suppress(Exception):
            await runner.cleanup()

        with contextlib.suppress(Exception):
            await bot._custom_session.close()

if __name__ == "__main__":
    asyncio.run(main())
