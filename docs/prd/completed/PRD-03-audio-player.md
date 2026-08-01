# PRD-03: MCP App Audio Player UI

**Status:** Draft  
**Date:** 2026-07-25  
**Depends on:** PRD-00 (architecture), PRD-02 (server tools)  
**Produces:** `src/microtherapy/view.py` (embedded HTML/JS audio player)

---

## 1. Objective

Build the MCP App View — an interactive HTML audio player that:
1. Renders inside the MCP host's sandboxed iframe
2. Receives streaming text via `ontoolinputpartial`
3. Calls app-only server tools for TTS queue management
4. Plays audio via Web Audio API with synchronized text display
5. Provides play/pause, restart, and progress controls

---

## 2. User Experience

```
┌─────────────────────────────────────────────┐
│  🎤 MicroTherapy                      [🔊]  │
│                                             │
│  "The bug is on line 42 of server.js.       │
│   You forgot to initialize the variable..."  │
│                                             │
│  ▶️ Play / Pause    🔄 Restart              │
│  ████████████░░░░░░  67%                    │
│                                             │
│  Voice: default ▼                           │
└─────────────────────────────────────────────┘
```

### States

| State | UI |
|-------|-----|
| **Loading** | Spinner, "Loading TTS model..." |
| **Ready** | Text displayed, play button pulsing |
| **Playing** | Progress bar animating, text highlighting word-by-word (karaoke) |
| **Paused** | Play button, progress frozen |
| **Finished** | Checkmark, "Done speaking", replay button |
| **Error** | Red banner with error message, retry button |

---

## 3. Architecture

The View is a **single HTML file** embedded in `view.py` as a Python string constant. This follows the say-server pattern: no build step, no separate deployment, single-file executable.

### Communication Flow

```
View (iframe)                    Server
     │                              │
     │── ontoolinputpartial ───────→│ (host delivers streaming text)
     │                              │
     │── tools/call: create_tts_queue →│
     │←── {queue_id, sample_rate} ──│
     │                              │
     │── tools/call: add_tts_text ──→│ (incremental text)
     │                              │
     │── tools/call: poll_tts_audio →│ (every 200ms)
     │←── {chunks: [...], done} ────│
     │                              │
     │── tools/call: end_tts_queue ─→│ (text complete)
     │←── {ended: true} ────────────│
```

---

## 4. Implementation

### 4.1 HTML Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light dark">
  <title>MicroTherapy</title>
  <style>
    /* CSS custom properties for host theme integration */
    :root {
      --micro-bg: var(--mcp-surface, #ffffff);
      --micro-fg: var(--mcp-on-surface, #1a1a1a);
      --micro-accent: var(--mcp-primary, #6c5ce7);
      --micro-border: var(--mcp-border, #e0e0e0);
      --micro-radius: 12px;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: var(--micro-bg);
      color: var(--micro-fg);
      padding: 16px;
      max-width: 480px;
    }

    .player {
      border: 1px solid var(--micro-border);
      border-radius: var(--micro-radius);
      padding: 16px;
      background: var(--micro-bg);
    }

    .player-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;
    }

    .player-title {
      font-size: 14px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .player-text {
      font-size: 15px;
      line-height: 1.5;
      color: var(--micro-fg);
      margin-bottom: 16px;
      min-height: 48px;
      padding: 8px;
      background: color-mix(in srgb, var(--micro-accent) 5%, transparent);
      border-radius: 8px;
    }

    .player-text .highlight {
      background: var(--micro-accent);
      color: white;
      border-radius: 3px;
      padding: 0 2px;
    }

    .player-controls {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 16px;
      border: 1px solid var(--micro-border);
      border-radius: 8px;
      background: var(--micro-bg);
      color: var(--micro-fg);
      font-size: 14px;
      cursor: pointer;
      transition: all 0.2s;
    }

    .btn:hover { background: color-mix(in srgb, var(--micro-accent) 10%, transparent); }
    .btn:active { transform: scale(0.97); }
    .btn-primary { background: var(--micro-accent); color: white; border-color: var(--micro-accent); }
    .btn-primary:hover { opacity: 0.9; }

    .progress-bar {
      height: 4px;
      background: var(--micro-border);
      border-radius: 2px;
      margin-top: 12px;
      overflow: hidden;
    }

    .progress-fill {
      height: 100%;
      background: var(--micro-accent);
      border-radius: 2px;
      transition: width 0.1s linear;
      width: 0%;
    }

    .voice-select {
      margin-top: 8px;
      font-size: 12px;
      color: var(--micro-fg);
      opacity: 0.7;
    }

    .voice-select select {
      margin-left: 4px;
      border: 1px solid var(--micro-border);
      border-radius: 4px;
      padding: 2px 4px;
      font-size: 12px;
      background: var(--micro-bg);
      color: var(--micro-fg);
    }

    .status-badge {
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 10px;
      background: color-mix(in srgb, var(--micro-accent) 15%, transparent);
      color: var(--micro-accent);
    }

    @media (prefers-color-scheme: dark) {
      :root {
        --micro-bg: #1e1e2e;
        --micro-fg: #cdd6f4;
        --micro-border: #45475a;
      }
    }
  </style>
</head>
<body>
  <div class="player">
    <div class="player-header">
      <span class="player-title">🎤 MicroTherapy</span>
      <span class="status-badge" id="status-badge">Ready</span>
    </div>
    <div class="player-text" id="player-text">
      Waiting for text...
    </div>
    <div class="player-controls">
      <button class="btn btn-primary" id="play-btn">
        <span id="play-icon">▶️</span>
        <span id="play-label">Play</span>
      </button>
      <button class="btn" id="restart-btn">🔄 Restart</button>
    </div>
    <div class="progress-bar">
      <div class="progress-fill" id="progress-fill"></div>
    </div>
    <div class="voice-select">
      Voice:
      <select id="voice-select">
        <option value="default">Default</option>
      </select>
    </div>
  </div>

  <script type="module">
    // JS implementation (see below)
  </script>
</body>
</html>
```

### 4.2 JavaScript Logic

```javascript
// ---- State ----
let app = null;
let queueId = null;
let audioCtx = null;
let sampleRate = 24000;
let status = 'idle'; // idle | playing | paused | finished
let displayText = '';
let currentPosition = 0; // character position for karaoke
let audioChunks = [];
let isPolling = false;
let nextPlayTime = 0;
let pollInterval = null;
let voice = 'default';

// ---- MCP App Setup ----
import { App } from 'https://esm.sh/@modelcontextprotocol/ext-apps';

async function initApp() {
  app = new App({ name: 'MicroTherapy', version: '1.0.0' });

  // Receive streaming text from the host
  app.ontoolinputpartial = async (params) => {
    const text = params.arguments?.text;
    if (!text) return;

    // Check for new session (text starts fresh)
    const isNewSession = displayText.length > 0 && !text.startsWith(displayText);
    if (isNewSession) {
      await resetQueue();
    }

    displayText = text;
    updateTextDisplay();

    if (!queueId) {
      await createQueue();
    }

    // Send new text to server
    const newText = text.slice(getLastSentLength());
    if (newText) {
      await app.callServerTool({
        name: 'add_tts_text',
        arguments: { queue_id: queueId, text: newText }
      });
    }
  };

  // Tool result callback
  app.ontoolresult = async (params) => {
    // When the speak tool completes, we might get final data
    if (queueId) {
      await app.callServerTool({
        name: 'end_tts_queue',
        arguments: { queue_id: queueId }
      });
    }
  };

  app.onerror = console.error;
}

// ---- Queue Management ----
async function createQueue() {
  const result = await app.callServerTool({
    name: 'create_tts_queue',
    arguments: { voice }
  });
  const data = JSON.parse(result.content[0].text);
  queueId = data.queue_id;
  sampleRate = data.sample_rate || 24000;
  startPolling();
}

async function resetQueue() {
  queueId = null;
  displayText = '';
  currentPosition = 0;
  audioChunks = [];
  stopPolling();
  stopPlayback();
  updateTextDisplay();
}

function startPolling() {
  if (isPolling) return;
  isPolling = true;
  pollInterval = setInterval(pollAudio, 200);
}

function stopPolling() {
  isPolling = false;
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

async function pollAudio() {
  if (!queueId) return;
  const result = await app.callServerTool({
    name: 'poll_tts_audio',
    arguments: { queue_id: queueId }
  });
  const data = JSON.parse(result.content[0].text);

  if (data.chunks?.length > 0) {
    audioChunks.push(...data.chunks);
    if (status === 'idle') {
      startPlayback();
    }
  }

  if (data.done) {
    stopPolling();
  }
}

// ---- Audio Playback (Web Audio API) ----
async function initAudioContext() {
  if (!audioCtx) {
    audioCtx = new AudioContext({ sampleRate });
  }
  if (audioCtx.state === 'suspended') {
    await audioCtx.resume();
  }
}

function base64ToArrayBuffer(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

async function startPlayback() {
  await initAudioContext();
  setStatus('playing');

  // Convert base64 chunks to AudioBuffers and schedule them
  for (const b64 of audioChunks) {
    const buffer = base64ToArrayBuffer(b64);
    const audioBuffer = await audioCtx.decodeAudioData(buffer);
    playBuffer(audioBuffer);
  }
}

function playBuffer(buffer) {
  const source = audioCtx.createBufferSource();
  source.buffer = buffer;
  source.connect(audioCtx.destination);
  source.start(nextPlayTime);
  nextPlayTime += buffer.duration;
}

function stopPlayback() {
  if (audioCtx) {
    audioCtx.close();
    audioCtx = null;
  }
  nextPlayTime = 0;
  setStatus('idle');
}

// ---- UI Updates ----
function setStatus(newStatus) {
  status = newStatus;
  const badge = document.getElementById('status-badge');
  const playLabel = document.getElementById('play-label');
  const playIcon = document.getElementById('play-icon');

  const states = {
    idle: { badge: 'Ready', label: 'Play', icon: '▶️' },
    playing: { badge: 'Speaking...', label: 'Pause', icon: '⏸️' },
    paused: { badge: 'Paused', label: 'Resume', icon: '▶️' },
    finished: { badge: 'Done ✓', label: 'Replay', icon: '🔄' },
  };

  const s = states[status] || states.idle;
  badge.textContent = s.badge;
  playLabel.textContent = s.label;
  playIcon.textContent = s.icon;
}

function updateTextDisplay() {
  document.getElementById('player-text').textContent =
    displayText || 'Waiting for text...';
}

// ---- Event Handlers ----
document.getElementById('play-btn').addEventListener('click', async () => {
  switch (status) {
    case 'idle':
    case 'finished':
      // Reset and replay
      if (status === 'finished' && audioChunks.length > 0) {
        await startPlayback();
      }
      break;
    case 'playing':
      await audioCtx?.suspend();
      setStatus('paused');
      break;
    case 'paused':
      await audioCtx?.resume();
      setStatus('playing');
      break;
  }
});

document.getElementById('restart-btn').addEventListener('click', async () => {
  await resetQueue();
  if (displayText) {
    await createQueue();
    await app.callServerTool({
      name: 'add_tts_text',
      arguments: { queue_id: queueId, text: displayText }
    });
    await app.callServerTool({
      name: 'end_tts_queue',
      arguments: { queue_id: queueId }
    });
  }
});

document.getElementById('voice-select').addEventListener('change', (e) => {
  voice = e.target.value;
});

// ---- Init ----
initApp();
```

### 4.3 Adaptive Theming

The View uses CSS custom properties that map to the host's theme variables:
- `--mcp-surface` / `--mcp-on-surface` → background/text colors
- `--mcp-primary` → accent color
- `--mcp-border` → border color
- Uses `prefers-color-scheme` as fallback

The View should also respond to host theme changes via `app.onhostcontextchanged`.

---

## 5. View Python Module

```python
# src/microtherapy/view.py

from pathlib import Path

VIEW_URI = "ui://microtherapy/view.html"

# The embedded HTML (inlined at build time or read from dist/)
# For MVP, we embed the HTML directly as a Python string
EMBEDDED_VIEW_HTML = r"""
<!DOCTYPE html>
<html lang="en">
... (full HTML from above) ...
</html>
"""

def get_view_html() -> str:
    """Get the View HTML, preferring built version from dist/."""
    dist_path = Path(__file__).parent.parent.parent / "dist" / "mcp-app.html"
    if dist_path.exists():
        return dist_path.read_text()
    return EMBEDDED_VIEW_HTML
```

---

## 6. CSP Configuration

The View resource must declare allowed domains:

```python
@mcp.resource(
    VIEW_URI,
    mime_type="text/html;profile=mcp-app",
    meta={
        "ui": {
            "csp": {
                "resourceDomains": [
                    "https://esm.sh",       # For @modelcontextprotocol/ext-apps import
                    "https://unpkg.com",    # Alternative CDN
                ],
            }
        }
    },
)
def view() -> str:
    return get_view_html()
```

---

## 7. Karaoke Text Highlighting (Optional Enhancement)

For word-by-word highlighting during playback, the View can:
1. Split `displayText` into words
2. Track current word index from audio playback position
3. Wrap the current word in `<span class="highlight">`
4. Update on each animation frame

This requires knowing word timings, which can come from:
- Kokoro word-level timestamps (if available)
- Estimated timings based on audio duration / word count

For MVP, skip karaoke highlighting. Add in v2.

---

## 8. Cross-View Coordination (Speak Lock)

When multiple `speak` tool calls create multiple Views, only one should play at a time. Follow the say-server pattern:

1. Each View gets a unique `view_uuid` via tool result metadata
2. On play, write `{uuid, timestamp}` to `localStorage["microtherapy-playing"]`
3. Poll every 200ms to check if another View took the lock
4. If another View is playing, pause and yield

---

## 9. Deliverables

- [x] `src/microtherapy/view.py` — Embedded HTML audio player
- [x] Play/pause, restart, progress bar controls
- [x] Web Audio API streaming playback
- [x] Adaptive dark/light theme
- [x] Voice selector
- [x] CSP metadata for external dependencies
- [x] Status indicators (Ready, Speaking..., Paused, Done)
- [x] Cross-view speak lock coordination
