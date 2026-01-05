let SERVER_HOST = "https://spending-vector-mba-cannon.trycloudflare.com";
const WS_PATH = "/ws";

// Configuration
const DEBUG = false; // Toggle this to show/hide debug box
const GAME_WIDTH = 960;
const GAME_HEIGHT = 640;
const VIDEO_WIDTH = 1920;
const VIDEO_HEIGHT = 1080;
const MARGIN_LEFT = 0;
const MARGIN_TOP = 50;
const MARGIN_RIGHT = 450;
const MARGIN_BOTTOM = 50;
const VIEW_WIDTH = VIDEO_WIDTH - MARGIN_LEFT - MARGIN_RIGHT;
const VIEW_HEIGHT = VIDEO_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM;

function logDebug(msg) {
  if (!DEBUG) return;
  const box = document.getElementById("debug-box");
  const content = document.getElementById("debug-content");
  if (box && content) {
    box.style.display = "block";
    const line = document.createElement("div");
    line.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
    content.prepend(line); // Newest on top
    // Limit history
    if (content.children.length > 5) content.lastChild.remove();
  }
  console.log(`[DEBUG] ${msg}`);
}

let ws = null;

// ✅ We no longer ask username with prompt.
// We identify the viewer using Twitch Extension auth userId (numeric string).
let myTwitchUserId = null;

let roundActive = false;
let roundEndTime = null;
let selectedItemKey = null; // Track user's selection
let isLockedIn = false;

const NO_VOTE_EMOJI = "😶";

// Automatically identify viewer via Twitch extension
if (window.Twitch && window.Twitch.ext) {
  window.Twitch.ext.onAuthorized((auth) => {
    // console.log("Extension Authorized", auth);

    // ✅ This is the real Twitch userId when identity is enabled.
    // If overlay is opened outside of Twitch extension context, it can be null.
    if (auth && auth.userId) {
      myTwitchUserId = String(auth.userId)
      logDebug(`Authorized as: ${myTwitchUserId}`);

      if (!ws || ws.readyState === WebSocket.CLOSED) {
        connectWS();
      }
    }
  });
}

function connectWS() {
  if (!myTwitchUserId) {
      logDebug("Waiting for Twitch Auth...");
      return;
  }

  const host = SERVER_HOST.replace(/^https?:\/\//i, "").split("/")[0];
  const url = `wss://${host}${WS_PATH}`;
  logDebug(`Connecting to WS: ${url}`);
  ws = new WebSocket(url);

  ws.onopen = () => {
    logDebug("WS Connected");
    // document.getElementById("dot").className = "dot ok";
    // document.getElementById("status-text").textContent = "CONNECTED";

    // ✅ tell server who we are (no username prompt)
    ws.send(
      JSON.stringify({
        type: "overlay_hello",
        want_state: true,
        twitch_user_id: myTwitchUserId,
      })
    );
  };

  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    // logDebug(`RX: ${data.type}`); // Optional: log every message type
    handleMessage(data);
  };

  ws.onclose = () => {
    logDebug("WS Closed. Reconnecting...");
    // document.getElementById("dot").className = "dot";
    setTimeout(connectWS, 2000);
  };
}

function handleMessage(data) {
  if (data.type === "round_start") {
    logDebug(`Round Start: ${data.round_id}`);
    roundActive = true;
    roundEndTime = Date.now() + data.duration * 1000;
    selectedItemKey = null; // Reset selection on new round
    isLockedIn = false;

    document.getElementById("winner-banner").classList.remove("show");
    document.getElementById("mouse-zone").classList.remove("active");
    resetMouseVisuals(); // Clear old arrows
    document.getElementById("root").style.display = "block"; // Show voting UI

    renderItems(data.options, {});
  } else if (data.type === "vote_update") {
    // Full refresh of vote counts
    const votes = data.votes || {};
    Object.keys(votes).forEach(key => {
        const count = votes[key];
        const voteEl = document.querySelector(`[data-key="${key}"] .votes`);
        if (voteEl) {
            voteEl.textContent = count === 0 ? `${NO_VOTE_EMOJI} 0 VOTES` : `${count} VOTES`;
        }
    });
  } else if (data.type === "vote") {
    // logDebug(`Vote update: ${data.item} = ${data.count}`); // Too spammy?
    const voteEl = document.querySelector(`[data-key="${data.item}"] .votes`);
    if (voteEl) {
      const c = Number(data.count || 0);
      voteEl.textContent = c === 0 ? `${NO_VOTE_EMOJI} 0 VOTES` : `${c} VOTES`;
    }
  } else if (data.type === "placement_request") {
    logDebug(`Placement Request: ${data.chosen_user}`);
    roundActive = false; // ✅ Safety: Ensure voting is disabled immediately
    const banner = document.getElementById("winner-banner");
    document.getElementById("root").style.display = "none"; // Hide voting UI

    // ✅ Unlock mouse ONLY for the winner
    const winnerId = data.chosen_user_id ? String(data.chosen_user_id) : null;
    const isWinner =
      myTwitchUserId && winnerId && String(myTwitchUserId) === String(winnerId);

    // Always reset visuals on new placement request to clear previous round's drawings
    resetMouseVisuals();

    const emojiEl = document.getElementById("winner-emoji");
    const userEl = document.getElementById("winner-user");

    if (isWinner) {
      logDebug("You are the winner! Mouse unlocked.");
      document.getElementById("mouse-zone").classList.add("active");
      
      emojiEl.textContent = "🏆";
      userEl.style.color = "#00ff6a"; // Green
      userEl.textContent = "YOU WON!";
      document.getElementById("winner-item-text").textContent = 
        `Place your ${data.emoji} ${data.label} now!`;
        
      // Hide banner for winner so they can click underneath
      // CSS handles pointer-events: none on the banner now.
      
      // Class 'active' handles pointer-events: auto via CSS
    } else {
      document.getElementById("mouse-zone").classList.remove("active");
      
      emojiEl.textContent = "🍀";
      userEl.style.color = "#ffcc00"; // Yellow
      userEl.textContent = `${data.emoji} ${data.label} WON!`;
      document.getElementById("winner-item-text").textContent = "Better luck next round!";
      
      // Banner is visible but non-blocking via CSS
    }

    banner.classList.add("show");
  } else if (data.type === "place_update") {
    logDebug(`Place Update: ${data.place}`);
    // Everyone sees the chosen place
    const banner = document.getElementById("winner-banner");
    const place = (data.place || "").toUpperCase();

    document.getElementById("winner-user").textContent = `@${data.chosen_user}`;
    document.getElementById("winner-item-text").textContent = `CHOSEN PLACE: ${place}`;

    banner.classList.add("show");

    // Winner controls stop after placement
    document.getElementById("mouse-zone").classList.remove("active");
  } else if (data.type === "placement_complete") {
    logDebug("Placement Complete");
    // Just in case: hide mouse controls
    document.getElementById("mouse-zone").classList.remove("active");
    document.getElementById("winner-banner").classList.remove("show"); // Hide banner
  } else if (data.type === "mouse_event") {
    handleRemoteMouse(data);
  } else if (data.type === "state" || data.type === "sync") {
    logDebug("State Sync Received");
    if (data.round) {
      roundActive = !!data.round.active;
      roundEndTime = Date.now() + data.round.duration_remaining * 1000;
    }
    renderItems(data.options, data.votes || {});
  }
}

function renderItems(options, votes) {
  const container = document.getElementById("items");
  if (!options) return;

  container.innerHTML = "";
  options.forEach((opt) => {
    const count = votes[opt.key] || 0;
    const div = document.createElement("div");
    div.className = "item";
    if (opt.key === selectedItemKey) {
      div.classList.add("selected");
      if (isLockedIn) div.classList.add("locked");
    }
    div.setAttribute("data-key", opt.key);
    div.style.cursor = "pointer"; 
    div.style.userSelect = "none"; // Prevent text selection

    const handleClick = (e) => {
        if (!roundActive) return;
        
        // Always allow changing vote (override)
        selectedItemKey = opt.key;
        isLockedIn = true; // Treat as locked immediately for visual feedback

        // Update UI
        document.querySelectorAll('.item').forEach(el => {
            el.classList.remove('selected');
            el.classList.remove('locked');
            el.style.transform = ""; 
        });
        div.classList.add('selected');
        div.classList.add('locked');

        logDebug(`Vote sent: ${opt.key}`);
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: "vote_click",
                item: opt.key
            }));
        }
        
        // Visual feedback
        div.style.transition = "transform 0.1s ease-out";
        div.style.transform = "scale(0.95)";
        setTimeout(() => {
             div.style.transform = "scale(1.05)";
             setTimeout(() => div.style.transform = "", 100);
        }, 100);
    };

    div.onclick = handleClick;
    // Touch support handled by click usually, but for responsiveness:
    // div.ontouchstart = handleClick; // Can cause double firing with click, stick to click or handle carefully

    const voteText = count === 0 ? `${NO_VOTE_EMOJI} 0 VOTES` : `${count} VOTES`;

    div.innerHTML = `
      <div class="emoji">${opt.emoji}</div>
      <div class="label">${opt.label}</div>
      <div class="votes">${voteText}</div>
    `;
    container.appendChild(div);
  });
}
function createCursor(id, zone) {
    let cursor = document.getElementById(id);
    if (!cursor) {
        cursor = document.createElement('div');
        cursor.id = id;
        Object.assign(cursor.style, {
            position: 'absolute',
            width: '20px',
            height: '20px',
            border: '2px solid cyan',
            borderRadius: '50%',
            pointerEvents: 'none',
            transform: 'translate(-50%, -50%)',
            display: 'none',
            zIndex: '100',
            boxShadow: '0 0 5px cyan'
        });
        zone.appendChild(cursor);
    }
    return cursor;
}

function createArrow(id, zone) {
    let arrow = document.getElementById(id);
    if (!arrow) {
        arrow = document.createElement('div');
        arrow.id = id;
        Object.assign(arrow.style, {
            position: 'absolute',
            height: '4px',
            backgroundColor: 'yellow',
            transformOrigin: '0 50%',
            pointerEvents: 'none',
            display: 'none',
            zIndex: '99',
            boxShadow: '0 0 5px yellow'
        });
        zone.appendChild(arrow);
    }
    return arrow;
}

function resetMouseVisuals() {
    const ids = ['local-mouse-cursor', 'local-mouse-arrow', 'remote-mouse-cursor', 'remote-mouse-arrow'];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });
}

function initMouse() {
  const zone = document.getElementById("mouse-zone");
  // Ensure zone is positioned so absolute children are relative to it
  zone.style.position = 'relative'; 

  let isDragging = false;
  let startLocalX = 0;
  let startLocalY = 0;
  let startGameX = 0;
  let startGameY = 0;

  // Create visual elements if they don't exist
  let cursor = createCursor('local-mouse-cursor', zone);
  let arrow = createArrow('local-mouse-arrow', zone);

  // Helper to send mouse event
  const sendMouseEvent = (type, x, y) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: "mouse_event",
        mouse_type: type,
        x: x,
        y: y
      }));
    }
  };

  const updateArrow = (x1, y1, x2, y2) => {
      const dx = x2 - x1;
      const dy = y2 - y1;
      const length = Math.sqrt(dx * dx + dy * dy);
      const angle = Math.atan2(dy, dx) * 180 / Math.PI;
      
      arrow.style.left = `${x1}px`;
      arrow.style.top = `${y1}px`;
      arrow.style.width = `${length}px`;
      arrow.style.transform = `rotate(${angle}deg)`;
      arrow.style.display = 'block';
  };

  const onMove = (e) => {
    // Only listen if active (winner)
    if (!zone.classList.contains("active")) return;

    const rect = zone.getBoundingClientRect();
    const localX = e.clientX - rect.left;
    const localY = e.clientY - rect.top;

    // Local -> Video -> Game Area -> Game Logic
    const vidX = (localX / rect.width) * VIDEO_WIDTH;
    const vidY = (localY / rect.height) * VIDEO_HEIGHT;
    const gX = vidX - MARGIN_LEFT;
    const gY = vidY - MARGIN_TOP;
    
    let gameX = Math.round((gX / VIEW_WIDTH) * GAME_WIDTH);
    let gameY = Math.round((gY / VIEW_HEIGHT) * GAME_HEIGHT);

    // Update HUD
    // document.getElementById("xy").textContent = `${gameX}, ${gameY}`;
    
    // Visuals: Type 0 (Hover)
    cursor.style.display = 'block';
    cursor.style.left = `${localX}px`;
    cursor.style.top = `${localY}px`;

    if (isDragging) {
        // Clamp vector to 100 units
        let dx = gameX - startGameX;
        let dy = gameY - startGameY;
        const len = Math.sqrt(dx*dx + dy*dy);
        
        if (len > 100) {
            const scale = 100 / len;
            dx *= scale;
            dy *= scale;
            gameX = Math.round(startGameX + dx);
            gameY = Math.round(startGameY + dy);
        }

        // Convert back to local for arrow drawing
        // Game Logic -> Game Area -> Video -> Local
        const cGX = (gameX / GAME_WIDTH) * VIEW_WIDTH;
        const cGY = (gameY / GAME_HEIGHT) * VIEW_HEIGHT;
        const cVidX = cGX + MARGIN_LEFT;
        const cVidY = cGY + MARGIN_TOP;
        
        const clampedLocalX = (cVidX / VIDEO_WIDTH) * rect.width;
        const clampedLocalY = (cVidY / VIDEO_HEIGHT) * rect.height;

        // Type 2 (Drag) - Update Arrow
        updateArrow(startLocalX, startLocalY, clampedLocalX, clampedLocalY);
    }

    // Type 0 (Hover) or Type 2 (Hold/Drag)
    const type = isDragging ? 2 : 0;
    sendMouseEvent(type, gameX, gameY);
  };

  const onDown = (e) => {
    if (!zone.classList.contains("active")) return;

    isDragging = true;
    
    const rect = zone.getBoundingClientRect();
    startLocalX = e.clientX - rect.left;
    startLocalY = e.clientY - rect.top;
    
    const vidX = (startLocalX / rect.width) * VIDEO_WIDTH;
    const vidY = (startLocalY / rect.height) * VIDEO_HEIGHT;
    const gX = vidX - MARGIN_LEFT;
    const gY = vidY - MARGIN_TOP;
    
    startGameX = Math.round((gX / VIEW_WIDTH) * GAME_WIDTH);
    startGameY = Math.round((gY / VIEW_HEIGHT) * GAME_HEIGHT);
    
    // Type 1 (Press/Start) - Vector Origin
    sendMouseEvent(1, startGameX, startGameY);

    // Show arrow start
    updateArrow(startLocalX, startLocalY, startLocalX, startLocalY);
  };

  const onUp = (e) => {
    if (isDragging) {
        isDragging = false;

        const rect = zone.getBoundingClientRect();
        const localX = e.clientX - rect.left;
        const localY = e.clientY - rect.top;

        const vidX = (localX / rect.width) * VIDEO_WIDTH;
        const vidY = (localY / rect.height) * VIDEO_HEIGHT;
        const gX = vidX - MARGIN_LEFT;
        const gY = vidY - MARGIN_TOP;

        let gameX = Math.round((gX / VIEW_WIDTH) * GAME_WIDTH);
        let gameY = Math.round((gY / VIEW_HEIGHT) * GAME_HEIGHT);

        // Clamp vector to 100 units
        let dx = gameX - startGameX;
        let dy = gameY - startGameY;
        const len = Math.sqrt(dx*dx + dy*dy);
        
        if (len > 100) {
            const scale = 100 / len;
            dx *= scale;
            dy *= scale;
            gameX = Math.round(startGameX + dx);
            gameY = Math.round(startGameY + dy);
        }

        // Type 3 (Release/End) - Vector End
        sendMouseEvent(3, gameX, gameY);
        
        // Stop listening
        zone.classList.remove("active");
        cursor.style.display = 'none';
        // Arrow remains visible until next round
    }
  };

  zone.addEventListener("mousemove", onMove);
  zone.addEventListener("mousedown", onDown);
  zone.addEventListener("mouseup", onUp);
  zone.addEventListener("mouseleave", onUp);
  
  // Touch support
  zone.addEventListener("touchmove", (e) => {
      e.preventDefault();
      const touch = e.touches[0];
      onMove(touch);
  });
  zone.addEventListener("touchstart", (e) => {
      e.preventDefault();
      const touch = e.touches[0];
      onDown(touch);
  });
  zone.addEventListener("touchend", (e) => {
      e.preventDefault();
      // For touchend, we might not have a touch object with coordinates in changedTouches
      // But onUp uses 'e' mainly for coordinates if we wanted to be precise.
      // However, we can just use the last known position or just trigger the release.
      // Let's just call onUp with a dummy event or the last touch if needed.
      // Actually, onUp uses e.clientX. We need to get it from changedTouches.
      const touch = e.changedTouches[0];
      onUp(touch);
  });
}

let remoteStartGameX = 0;
let remoteStartGameY = 0;

function handleRemoteMouse(data) {
    // If we are the one driving (active), ignore remote echo to prevent jitter
    // Also check user_id if available to be doubly sure
    if (document.getElementById("mouse-zone").classList.contains("active")) return;
    if (myTwitchUserId && data.user_id && String(data.user_id) === String(myTwitchUserId)) return;

    const zone = document.getElementById("mouse-zone");
    const rect = zone.getBoundingClientRect();
    
    // Game Logic -> Game Area -> Video -> Local
    const gX = (data.x / GAME_WIDTH) * VIEW_WIDTH;
    const gY = (data.y / GAME_HEIGHT) * VIEW_HEIGHT;
    const vidX = gX + MARGIN_LEFT;
    const vidY = gY + MARGIN_TOP;
    
    const localX = (vidX / VIDEO_WIDTH) * rect.width;
    const localY = (vidY / VIDEO_HEIGHT) * rect.height;

    // Ensure elements exist
    let cursor = createCursor('remote-mouse-cursor', zone);
    let arrow = createArrow('remote-mouse-arrow', zone);
    
    if (!cursor || !arrow) return;

    const type = data.mouse_type; // 0=Hover, 1=Start, 2=Drag, 3=End

    if (type === 0) { // Hover
        cursor.style.display = 'block';
        cursor.style.left = `${localX}px`;
        cursor.style.top = `${localY}px`;
    } else if (type === 1) { // Start
        remoteStartGameX = data.x;
        remoteStartGameY = data.y;
        
        cursor.style.display = 'block';
        cursor.style.left = `${localX}px`;
        cursor.style.top = `${localY}px`;
        
        // Start arrow (zero length)
        updateVisualArrow(arrow, localX, localY, localX, localY);
    } else if (type === 2) { // Drag
        cursor.style.display = 'block';
        cursor.style.left = `${localX}px`;
        cursor.style.top = `${localY}px`;
        
        // Calculate start pos in current local pixels
        // Game Logic -> Game Area -> Video -> Local
        const sGX = (remoteStartGameX / GAME_WIDTH) * VIEW_WIDTH;
        const sGY = (remoteStartGameY / GAME_HEIGHT) * VIEW_HEIGHT;
        const sVidX = sGX + MARGIN_LEFT;
        const sVidY = sGY + MARGIN_TOP;
        
        const startLocalX = (sVidX / VIDEO_WIDTH) * rect.width;
        const startLocalY = (sVidY / VIDEO_HEIGHT) * rect.height;
        
        // If remoteStartGameX/Y are 0 (missed type 1 packet), try to infer or just skip arrow
        if (remoteStartGameX !== 0 || remoteStartGameY !== 0) {
             updateVisualArrow(arrow, startLocalX, startLocalY, localX, localY);
        }
    } else if (type === 3) { // End
        cursor.style.display = 'none';
        // Arrow remains visible
    }
}

function updateVisualArrow(arrowEl, x1, y1, x2, y2) {
      const dx = x2 - x1;
      const dy = y2 - y1;
      const length = Math.sqrt(dx * dx + dy * dy);
      const angle = Math.atan2(dy, dx) * 180 / Math.PI;
      
      arrowEl.style.left = `${x1}px`;
      arrowEl.style.top = `${y1}px`;
      arrowEl.style.width = `${length}px`;
      arrowEl.style.transform = `rotate(${angle}deg)`;
      arrowEl.style.display = 'block';
}

function updateTimer() {
  const timerDiv = document.getElementById("timer");
  if (roundActive && roundEndTime) {
    const rem = Math.max(0, Math.ceil((roundEndTime - Date.now()) / 1000));
    timerDiv.textContent = `TIME: ${rem}s`;
    
    if (rem === 0) {
      roundActive = false;
      document.getElementById("root").style.display = "none"; // Hide voting UI when time is up
    }
  } else {
    timerDiv.textContent = "WAITING...";
    if (!roundActive) {
      document.getElementById("root").style.display = "none"; // Ensure hidden if not active
    }
  }
  requestAnimationFrame(updateTimer);
}

window.addEventListener("DOMContentLoaded", () => {
  // connectWS(); // Wait for onAuthorized
  initMouse();
  updateTimer();
});
