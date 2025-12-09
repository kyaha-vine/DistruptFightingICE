import asyncio
import json
import random
import contextlib
import time
import socket
import struct
from typing import Set, Any, Dict, Optional

from twitchio.ext import commands
import websockets

# Import protobuf message
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src_python')))
try:
    import message_pb2
    HAS_PROTOBUF = True
except ImportError:
    HAS_PROTOBUF = False
    print("[WARNING] message_pb2 not found, mouse events won't be sent to game")

# =========================
#   CONFIG
# =========================

MY_TOKEN = "oauth:27vu4fj6t3uk4nb1djbyzaf12a086y"  # <-- mets ton vrai token ici
MY_CHANNEL_NAME = "aigameapg"                   # <-- ton channel Twitch
WS_PORT = 8765
ROUND_DURATION = 30  # secondes de vote
LOG_FILE = "spawn_log.jsonl"  # "base de données" JSON (1 event par ligne)

# Items disponibles pour le vote
ITEMS: Dict[str, Dict[str, str]] = {
    "freeze": {"emoji": "🧊", "label": "Freeze Orb"},
    "fire":   {"emoji": "🔥", "label": "Power Core"},
    "wind":   {"emoji": "💨", "label": "Wind Boots"},
    "shield": {"emoji": "🧱", "label": "Shield Stone"},
    "chaos":  {"emoji": "🎭", "label": "Chaos Mask"},
}

# =========================
#   ÉTAT GLOBAL
# =========================

OVERLAY_CLIENTS: Set[Any] = set()
BOT_INSTANCE: Optional[Any] = None  # Global bot instance for sending messages
GAME_SOCKET: Optional[socket.socket] = None  # Socket to game server
GAME_EVENT_ID: int = 0  # Current event ID for game events

current_round_active: bool = False
current_votes: Dict[str, int] = {k: 0 for k in ITEMS.keys()}
current_round_id: int = 0

# votes_by_item["freeze"] = set(["user1", "user2"])
votes_by_item: Dict[str, Set[str]] = {k: set() for k in ITEMS.keys()}

# Info en attente de placement par le gagnant
# { "round_id": int, "item_key": str, "chosen_user": str }
pending_placement: Optional[Dict[str, Any]] = None


# =========================
#   LOG JSON
# =========================

def log_spawn_event(event: Dict[str, Any]):
    """Append l'event dans un fichier JSONL (une ligne JSON par event)."""
    data = dict(event)
    data["ts"] = time.time()
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
    except Exception as e:
        print("[LOG] Error writing JSON log:", e)


def connect_game_socket():
    """Connect to game server at localhost:31415"""
    global GAME_SOCKET
    try:
        if GAME_SOCKET:
            try:
                GAME_SOCKET.close()
            except:
                pass
        GAME_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        GAME_SOCKET.connect(('127.0.0.1', 31415))
        # Send role: 6 = Game Event Injector
        GAME_SOCKET.send(b'\x06')
        print("[GAME] Connected to game server at localhost:31415")
    except Exception as e:
        print(f"[GAME] Connection failed: {e}")
        GAME_SOCKET = None


def send_game_event(event_type: int, x: int, y: int, vx: int, vy: int, hx: int, hy: int, terminate: bool):
    """Send event to game server using protobuf"""
    global GAME_SOCKET, GAME_EVENT_ID
    
    if not HAS_PROTOBUF or not GAME_SOCKET:
        return
    
    try:
        event = message_pb2.GrpcGameEvent()
        event.event_id = GAME_EVENT_ID
        event.event_type = event_type
        event.x = x
        event.y = y
        event.vx = vx
        event.vy = vy
        event.hx = hx
        event.hy = hy
        event.time = 180
        event.terminate = terminate
        
        data = event.SerializeToString()
        GAME_SOCKET.send(struct.pack('<I', len(data)))
        GAME_SOCKET.send(data)
        
        print(f"[GAME] Sent event: ID={GAME_EVENT_ID}, X={x}, Y={y}, VX={vx}, VY={vy}, Term={terminate}")
        
        if terminate:
            GAME_EVENT_ID += 1
    except Exception as e:
        print(f"[GAME] Send failed: {e}")
        GAME_SOCKET = None
        connect_game_socket()  # Try to reconnect


async def broadcast_to_ws_clients(data: dict):
    """Envoie un JSON à tous les clients WebSocket (overlay + mini-jeu)."""
    if not OVERLAY_CLIENTS:
        return
    msg = json.dumps(data)
    dead = []
    for ws in OVERLAY_CLIENTS:
        try:
            await ws.send(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        OVERLAY_CLIENTS.discard(ws)


async def send_chat_message(message: str):
    """Send a message to Twitch chat."""
    global BOT_INSTANCE
    if BOT_INSTANCE:
        try:
            channel = BOT_INSTANCE.get_channel(MY_CHANNEL_NAME)
            if channel:
                await channel.send(message)
        except Exception as e:
            print(f"[CHAT ERROR] Failed to send message: {e}")


# =========================
#   TWITCH BOT
# =========================

class ChatBot(commands.Bot):
    def __init__(self):
        super().__init__(
            token=MY_TOKEN,
            prefix="!",
            initial_channels=[MY_CHANNEL_NAME],
        )

    async def event_ready(self):
        print("--- BOT CONNECTED ---")
        print(f"Logged as: {self.nick}")
        print(f"Joined channel: {MY_CHANNEL_NAME}")

    async def event_message(self, message):
        # Affichage pour debug
        author_name = message.author.name if message.author else "Unknown"
        print(f"[CHAT] {author_name}: {message.content}")

        # Ignorer les messages sans auteur ou envoyés par le bot lui-même
        if not message.author or getattr(message, "echo", False):
            return

        # Laisser TwitchIO gérer les commandes (!item, !items, !place)
        await self.handle_commands(message)

    @commands.command(name="items")
    async def items_command(self, ctx: commands.Context):
        """Affiche la liste des options."""
        items_list = " | ".join([f"{v['emoji']} {k}" for k, v in ITEMS.items()])
        await ctx.send(f"Available items: {items_list} | Vote with: !item <name>")

    @commands.command(name="item")
    async def item_command(self, ctx: commands.Context):
        """
        Utilisation dans le chat:
          !item freeze
          !item fire
          !item wind
          !item shield
          !item chaos
        """
        global current_votes, current_round_active, votes_by_item

        parts = ctx.message.content.split(maxsplit=1)
        if len(parts) < 2:
            await ctx.send("Usage: !item <freeze|fire|wind|shield|chaos>")
            return

        choice = parts[1].strip().lower()

        if choice not in ITEMS:
            await ctx.send("Unknown item. Try: freeze, fire, wind, shield, chaos.")
            return

        if not current_round_active:
            await ctx.send("No vote running right now. Wait for the next round!")
            return

        user = ctx.author.name if ctx.author else "Unknown"

        # Enregistrer le vote (compteur)
        current_votes[choice] = current_votes.get(choice, 0) + 1

        # Enregistrer le votant (1 ticket max par user pour le tirage)
        votes_by_item.setdefault(choice, set()).add(user)

        # Informer overlay
        data = {
            "type": "vote",
            "user": user,
            "item": choice,
            "emoji": ITEMS[choice]["emoji"],
            "count": current_votes[choice],
        }
        await broadcast_to_ws_clients(data)

    @commands.command(name="place")
    async def place_command(self, ctx: commands.Context):
        """
        Commande utilisée par le gagnant pour choisir la position :
            !place left
            !place middle
            !place right
        """
        global pending_placement

        print("[PLACE CMD] Received !place command")

        if pending_placement is None:
            await ctx.send("There is no item waiting for placement right now.")
            return

        chosen_user = pending_placement["chosen_user"]
        if not ctx.author or ctx.author.name != chosen_user:
            await ctx.send(f"Only {chosen_user} can place the item this round!")
            return

        parts = ctx.message.content.split()
        if len(parts) != 2:
            await ctx.send("Usage: !place <left|middle|right>")
            return

        raw_slot = parts[1].strip().lower()

        # tolérer quelques fautes / variantes
        if raw_slot in ("left", "gauche"):
            slot = "left"
        elif raw_slot in ("middle", "mid", "centre", "center", "midle"):
            slot = "middle"
        elif raw_slot in ("right", "droite"):
            slot = "right"
        else:
            await ctx.send("Invalid slot. Use: left, middle, or right.")
            return

        item_key = pending_placement["item_key"]
        round_id = pending_placement["round_id"]

        spawn_payload = {
            "type": "spawn_item",
            "round_id": round_id,
            "item_key": item_key,
            "emoji": ITEMS[item_key]["emoji"],
            "label": ITEMS[item_key]["label"],
            "chosen_user": chosen_user,
            "slot": slot,  # <-- c'est ça que ton jeu va utiliser
        }

        print(
            f"[SPAWN] round {round_id} -> item {item_key} placed by "
            f"{chosen_user} at slot '{slot}'"
        )

        # Log JSON
        log_spawn_event(spawn_payload)

        # Envoi aux clients WS (jeu + overlay)
        await broadcast_to_ws_clients(spawn_payload)

        # Announce placement in chat
        emoji = ITEMS[item_key]['emoji']
        label = ITEMS[item_key]['label']
        slot_display = slot.upper()
        await ctx.send(
            f"✅ {emoji} {label} spawned at {slot_display} by @{chosen_user}!"
        )

        # Placement effectué, on reset
        pending_placement = None


# =========================
#   BOUCLE DES ROUNDS
# =========================

async def rounds_loop():
    """Boucle infinie de rounds de vote."""
    global current_round_active, current_votes, current_round_id, votes_by_item, pending_placement

    await asyncio.sleep(3)  # petite pause avant le premier round

    while True:
        current_round_id += 1
        print(f"=== Starting round {current_round_id} ===")

        # Reset votes
        current_votes = {k: 0 for k in ITEMS.keys()}
        votes_by_item = {k: set() for k in ITEMS.keys()}
        pending_placement = None
        current_round_active = True

        # Announce round start in chat
        items_list = " | ".join([f"{v['emoji']} {k}" for k, v in ITEMS.items()])
        await send_chat_message(f"🎮 Round {current_round_id} starts! Vote with: !item <freeze|fire|wind|shield|chaos> | {ROUND_DURATION}s to vote!")

        # Signal de début de round
        start_payload = {
            "type": "round_start",
            "round_id": current_round_id,
            "duration": ROUND_DURATION,
            "options": [
                {"key": k, "emoji": v["emoji"], "label": v["label"]}
                for k, v in ITEMS.items()
            ],
        }
        await broadcast_to_ws_clients(start_payload)

        # Countdown announcements during voting
        # Vote for 30 seconds with countdown announcements
        countdown_times = [20, 10, 5]  # Announce at these seconds remaining
        elapsed = 0
        
        for i, wait_time in enumerate([10, 10, 5, 5]):  # 10s, 10s, 5s, 5s = 30s
            await asyncio.sleep(wait_time)
            elapsed += wait_time
            remaining = ROUND_DURATION - elapsed
            
            if remaining in countdown_times:
                await send_chat_message(f"⏰ {remaining} seconds left to vote!")
        current_round_active = False

        # Déterminer l’item gagnant
        max_votes = max(current_votes.values()) if current_votes else 0
        if max_votes == 0:
            winner_key = None
        else:
            winner_key = max(current_votes, key=lambda k: current_votes[k])

        if winner_key:
            winner = {
                "key": winner_key,
                "emoji": ITEMS[winner_key]["emoji"],
                "label": ITEMS[winner_key]["label"],
                "votes": current_votes[winner_key],
            }
            print(f"=== Round {current_round_id} winner: {winner} ===")
        else:
            winner = None
            print(f"=== Round {current_round_id}: no votes ===")

        # Broadcast résultat de vote (overlay)
        result_payload = {
            "type": "round_result",
            "round_id": current_round_id,
            "winner": winner,
            "votes": current_votes,
        }
        await broadcast_to_ws_clients(result_payload)

        # Announce results in chat
        if not winner:
            await send_chat_message(f"❌ Round {current_round_id} ended with no votes. Next round in 15 seconds...")
        else:
            # Show vote results
            vote_summary = " | ".join([f"{ITEMS[k]['emoji']} {v}" for k, v in current_votes.items() if v > 0])
            await send_chat_message(f"📊 Votes: {vote_summary}")

        # Si un item a gagné, choisir UN viewer parmi ceux qui ont voté pour lui
        if winner_key:
            voters = list(votes_by_item.get(winner_key, []))
            if voters:
                chosen_user = random.choice(voters)

                pending_placement = {
                    "round_id": current_round_id,
                    "item_key": winner_key,
                    "chosen_user": chosen_user,
                }

                # Announce winner and placement instructions in chat
                emoji = ITEMS[winner_key]["emoji"]
                label = ITEMS[winner_key]["label"]
                await send_chat_message(f"🏆 {emoji} {label} wins! @{chosen_user} place it with: !place <left|middle|right> - 15 seconds!")

                # Informer overlay + jeu que ce viewer doit placer l'item
                placement_request = {
                    "type": "placement_request",
                    "round_id": current_round_id,
                    "item_key": winner_key,
                    "emoji": ITEMS[winner_key]["emoji"],
                    "label": ITEMS[winner_key]["label"],
                    "chosen_user": chosen_user,
                    "hint": "Use !place <left|middle|right> in chat",
                }
                print(
                    f"[PLACE] round {current_round_id}: {chosen_user} can place {winner_key}"
                )
                await broadcast_to_ws_clients(placement_request)

        # Pause entre deux rounds
        await asyncio.sleep(15)


# =========================
#   WEBSOCKET SERVER
#   (ta version de websockets attend UN seul argument)
# =========================

async def ws_client_handler(websocket):
    print("[WS] Client connected")
    OVERLAY_CLIENTS.add(websocket)
    try:
        async for message in websocket:
            # Handle incoming messages from overlay
            try:
                data = json.loads(message)
                
                if data.get("type") == "mouse_event":
                    x = data.get("x", 0)
                    y = data.get("y", 0)
                    vx = data.get("vx", 0)
                    vy = data.get("vy", 0)
                    terminate = data.get("terminate", False)
                    
                    print(f"[MOUSE EVENT] Coords: ({x}, {y}), Velocity: ({vx}, {vy}), Terminate: {terminate}")
                    
                    # ONLY send to game if an item is pending (selected)
                    if pending_placement:
                        # Get item index (fire=0, freeze=1, etc.) - or use specific mapping
                        item_key = pending_placement['item_key']
                        item_index = list(ITEMS.keys()).index(item_key)
                        
                        # event_type: 0 during drag, item_index on release
                        event_type = item_index if terminate else 0
                        
                        print(f"[GAME] Item pending: {item_key} (index={item_index}), sending to game...")
                        send_game_event(event_type=event_type, x=x, y=y, vx=vx, vy=vy, hx=100 , hy=100, terminate=terminate)
                        
                        # Log event
                        log_event = {
                            "type": "mouse_event",
                            "x": x,
                            "y": y,
                            "vx": vx,
                            "vy": vy,
                            "terminate": terminate,
                            "item": pending_placement['item_key'],
                            "sent_to_game": True
                        }
                    else:
                        print(f"[GAME] No item selected, ignoring mouse event")
                        log_event = {
                            "type": "mouse_event",
                            "x": x,
                            "y": y,
                            "vx": vx,
                            "vy": vy,
                            "terminate": terminate,
                            "sent_to_game": False
                        }
                    
                    log_spawn_event(log_event)
                    
                else:
                    print(f"[WS] Received unknown message type: {data.get('type')}")
            except json.JSONDecodeError:
                print(f"[WS] Invalid JSON received: {message}")
    except Exception as e:
        print(f"[WS] Error: {e}")
    finally:
        OVERLAY_CLIENTS.discard(websocket)
        print("[WS] Client disconnected")


async def main():
    global BOT_INSTANCE
    
    # Try to connect to game server
    if HAS_PROTOBUF:
        connect_game_socket()
    
    async with websockets.serve(ws_client_handler, "0.0.0.0", WS_PORT):
        print(f"[WS] WebSocket server listening on ws://localhost:{WS_PORT}")

        bot = ChatBot()
        BOT_INSTANCE = bot  # Store bot instance globally
        rounds_task = asyncio.create_task(rounds_loop())

        try:
            await bot.start()
        finally:
            rounds_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await rounds_task


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bye")
