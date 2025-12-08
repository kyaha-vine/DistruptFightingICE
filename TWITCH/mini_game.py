import asyncio
import json
import contextlib

import pygame
import websockets

WS_URL = "ws://localhost:8765"

# Queue async pour recevoir les événements "spawn_item"
spawn_queue: asyncio.Queue = asyncio.Queue()


async def ws_client():
    """Client WebSocket pour écouter les messages (spawn_item, etc.)."""
    while True:
        try:
            async with websockets.connect(WS_URL) as ws:
                print("[GAME] WebSocket connected to", WS_URL)
                async for msg in ws:
                    data = json.loads(msg)
                    if data.get("type") == "spawn_item":
                        print("[GAME] Received spawn_item:", data)
                        await spawn_queue.put(data)
        except Exception as e:
            print("[GAME] WS error:", e)
            print("[GAME] Reconnecting in 3s...")
            await asyncio.sleep(3)


async def pygame_loop():
    """Boucle principale Pygame (async pour coexister avec ws_client)."""
    pygame.init()
    screen = pygame.display.set_mode((800, 450))
    pygame.display.set_caption("Mini Game - Twitch Items")
    clock = pygame.time.Clock()

    # Essayer une police emoji, sinon fallback
    try:
        emoji_font = pygame.font.SysFont("Segoe UI Emoji", 48)
    except Exception:
        emoji_font = pygame.font.SysFont(None, 48)

    font = pygame.font.SysFont(None, 32)
    small_font = pygame.font.SysFont(None, 22)

    running = True

    # Liste des items spawnés
    # chaque item: {"emoji": str, "label": str, "slot": "left|middle|right", "user": str}
    items_on_field = []

    last_info = "Waiting for spawn_item..."

    while running:
        # Gestion des events Pygame
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Récupérer tous les nouveaux spawn_items de la queue
        while True:
            try:
                data = spawn_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                items_on_field.append(
                    {
                        "emoji": data.get("emoji", "?"),
                        "label": data.get("label", "Item"),
                        "slot": data.get("slot", "middle"),
                        "user": data.get("chosen_user", "Unknown"),
                    }
                )
                last_info = (
                    f"Spawn: {data.get('emoji', '?')} "
                    f"{data.get('label', 'Item')} at {data.get('slot', 'middle')} "
                    f"by {data.get('chosen_user', 'Unknown')}"
                )

        # Dessin
        screen.fill((25, 25, 35))

        width, height = screen.get_size()

        # Dessiner 3 zones : left, middle, right
        left_x = width * 0.2
        middle_x = width * 0.5
        right_x = width * 0.8

        # lignes
        pygame.draw.line(screen, (80, 80, 80), (left_x, 0), (left_x, height), 1)
        pygame.draw.line(screen, (80, 80, 80), (middle_x, 0), (middle_x, height), 1)
        pygame.draw.line(screen, (80, 80, 80), (right_x, 0), (right_x, height), 1)

        # labels zone
        left_label = small_font.render("LEFT", True, (200, 200, 200))
        mid_label = small_font.render("MIDDLE", True, (200, 200, 200))
        right_label = small_font.render("RIGHT", True, (200, 200, 200))

        screen.blit(left_label, (left_x - left_label.get_width() // 2, 10))
        screen.blit(mid_label, (middle_x - mid_label.get_width() // 2, 10))
        screen.blit(right_label, (right_x - right_label.get_width() // 2, 10))

        # Dessiner les items spawnés
        # On empile les items verticalement par slot
        slot_positions = {
            "left": {"x": left_x, "y": height * 0.3},
            "middle": {"x": middle_x, "y": height * 0.3},
            "right": {"x": right_x, "y": height * 0.3},
        }
        slot_offsets = {"left": 0, "middle": 0, "right": 0}

        for it in items_on_field:
            slot = it["slot"]
            pos = slot_positions.get(slot, slot_positions["middle"])

            x = pos["x"]
            y = pos["y"] + slot_offsets[slot]

            # Emoji (si la police ne le supporte pas, ça donnera peut-être un carré, mais c'est ok)
            emoji_text = emoji_font.render(it["emoji"], True, (255, 255, 255))
            label_text = small_font.render(it["label"], True, (220, 220, 220))
            user_text = small_font.render(f"by {it['user']}", True, (180, 180, 255))

            screen.blit(
                emoji_text,
                (x - emoji_text.get_width() // 2, y - emoji_text.get_height() // 2),
            )
            screen.blit(
                label_text,
                (x - label_text.get_width() // 2, y + 20),
            )
            screen.blit(
                user_text,
                (x - user_text.get_width() // 2, y + 40),
            )

            slot_offsets[slot] += 80  # espace vertical entre items

        # Petit texte d'info (dernière action)
        info = small_font.render(last_info, True, (220, 220, 220))
        screen.blit(info, (10, height - 30))

        pygame.display.flip()
        clock.tick(60)
        # Yield pour laisser tourner l'event loop asyncio
        await asyncio.sleep(0)

    pygame.quit()


async def main():
    ws_task = asyncio.create_task(ws_client())
    try:
        await pygame_loop()
    finally:
        ws_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await ws_task


if __name__ == "__main__":
    asyncio.run(main())
