# PRD-02: MCP 2.0 Server Implementation

**Status:** Draft  
**Date:** 2026-07-25  
**Depends on:** PRD-00 (architecture), PRD-01 (TTS engine)  
**Produces:** `src/microtherapy/server.py`, `src/microtherapy/queue.py`

---

## 1. Objective

Build the core MCP 2.0 server that:
1. Exposes a public `speak` tool for coding agents to call
2. Exposes private (app-only) tools for the audio player View
3. Serves the MCP App UI resource (`ui://` scheme)
4. Runs over Streamable HTTP transport (protocol version `2026-07-28`)

---

## 2. Tool Inventory

### 2.1 Public Tools (visible to the LLM/agent)

| Tool | Description | Parameters |
|------|-------------|------------|
| `speak` | Speak text aloud using TTS. Triggers the audio player View. | `text: str` — English text to speak<br>`voice: str = "default"` — Voice name<br>`autoPlay: bool = True` — Start playing immediately |
| `list_voices` | List available TTS voices. | (none) |

### 2.2 App-Only Tools (only callable by the View, `visibility: ["app"]`)

| Tool | Description | Parameters |
|------|-------------|------------|
| `create_tts_queue` | Create a new TTS processing queue. | `voice: str = "default"` |
| `add_tts_text` | Append text to an existing queue for synthesis. | `queue_id: str`<br>`text: str` |
| `poll_tts_audio` | Poll for new audio chunks from a queue. | `queue_id: str` |
| `end_tts_queue` | Signal end of text, finalize the queue. | `queue_id: str` |

---

## 3. Server Implementation

### 3.1 Technology Choice: FastMCP

Use `mcp.server.fastmcp.FastMCP` (from the say-server pattern) for its simpler API:

```python
from mcp.server.fastmcp import FastMCP
from mcp import types
from mcp.types import Icon

mcp = FastMCP("MicroTherapy", icons=[SPEAKER_ICON])
```

**Alternative:** Use `mcp.server.MCPServer` directly for more control. FastMCP is recommended for MVP.

### 3.2 Server Setup

```python
# src/microtherapy/server.py

import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Annotated

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp import types
from mcp.types import Icon
from pydantic import Field
from starlette.middleware.cors import CORSMiddleware

from microtherapy.tts import TTSModel
from microtherapy.queue import TTSQueueManager
from microtherapy.view import get_view_html, VIEW_URI

logger = logging.getLogger(__name__)

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "3001"))

# Speaker icon (SVG data URI)
SPEAKER_ICON = Icon(
    src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
        "viewBox='0 0 24 24' fill='none' stroke='currentColor' "
        "stroke-width='2'%3E%3Cpolygon points='11 5 6 9 2 9 2 15 "
        "6 15 11 19 11 5'/%3E%3Cpath d='M15.54 8.46a5 5 0 0 1 0 7.07'"
        "/%3E%3Cpath d='M19.07 4.93a10 10 0 0 1 0 14.14'/%3E%3C/svg%3E",
    mimeType="image/svg+xml",
)

mcp = FastMCP("MicroTherapy", icons=[SPEAKER_ICON])

# Global state
tts_model: TTSModel | None = None
queue_manager: TTSQueueManager = TTSQueueManager()
```

### 3.3 Public Tool: `speak`

```python
@mcp.tool(meta={
    "ui": {"resourceUri": VIEW_URI},
    "ui/resourceUri": VIEW_URI,  # legacy key
})
def speak(
    text: Annotated[str, Field(
        description="The English text to speak aloud. Keep it concise "
                    "and natural-sounding."
    )] = "Hello! I'm your coding assistant.",
    voice: Annotated[str, Field(
        description="Voice to use. Call list_voices() for options."
    )] = "default",
    autoPlay: Annotated[bool, Field(
        description="Start playing automatically. Browsers may block "
                    "autoplay until user interaction."
    )] = True,
) -> list[types.TextContent]:
    """Speak English text aloud using text-to-speech.

    Use this tool when you want to speak to the user rather than
    just writing text. The user will hear your response through
    their speakers/headphones.

    Triggers:
    - "speak ...", "say ...", "read this aloud"
    - "...; say it", "...; speak it"
    - "tell me ...", "narrate ..."

    The audio player renders directly in the chat with play/pause
    controls. Click to play/pause, double-click to restart.

    Note: English only. Non-English text may produce poor results.
    """
    return [types.TextContent(
        type="text",
        text=f"Speaking with voice '{voice}'. "
             f"Click play to listen, or the audio will auto-play."
    )]
```

### 3.4 Public Tool: `list_voices`

```python
@mcp.tool()
def list_voices() -> list[types.TextContent]:
    """List all available TTS voices."""
    voices = {
        "default": "Default voice (neutral, clear)",
        # Add more as prompt audio files are added
    }
    return [types.TextContent(
        type="text",
        text=json.dumps(voices, indent=2)
    )]
```

### 3.5 App-Only Tools

```python
# ---- Queue Management (app-only) ----

@mcp.tool(meta={"ui": {"visibility": ["app"]}})
async def create_tts_queue(voice: str = "default") -> list[types.TextContent]:
    """Create a new TTS queue. Called by the audio player View."""
    queue_id = queue_manager.create_queue(voice)
    return [types.TextContent(
        type="text",
        text=json.dumps({
            "queue_id": queue_id,
            "sample_rate": 24000,
        })
    )]

@mcp.tool(meta={"ui": {"visibility": ["app"]}})
async def add_tts_text(
    queue_id: str,
    text: str,
) -> list[types.TextContent]:
    """Add text to a TTS queue. Called incrementally as text streams in."""
    new_chars = queue_manager.add_text(queue_id, text)
    # Trigger async audio generation in background
    asyncio.create_task(queue_manager.generate_audio(queue_id))
    return [types.TextContent(
        type="text",
        text=json.dumps({"added": new_chars})
    )]

@mcp.tool(meta={"ui": {"visibility": ["app"]}})
def poll_tts_audio(queue_id: str) -> list[types.TextContent]:
    """Poll for new audio chunks. Called by the View on a timer."""
    chunks = queue_manager.get_new_chunks(queue_id)
    response = {
        "chunks": chunks,  # list of base64-encoded WAV/PCM chunks
        "done": queue_manager.is_done(queue_id),
    }
    return [types.TextContent(
        type="text",
        text=json.dumps(response)
    )]

@mcp.tool(meta={"ui": {"visibility": ["app"]}})
def end_tts_queue(queue_id: str) -> list[types.TextContent]:
    """Signal end of text. Finalizes audio generation."""
    queue_manager.end_queue(queue_id)
    return [types.TextContent(
        type="text",
        text=json.dumps({"ended": True})
    )]
```

### 3.6 UI Resource

```python
@mcp.resource(
    VIEW_URI,
    mime_type="text/html;profile=mcp-app",
    meta={
        "ui": {
            "csp": {
                "resourceDomains": ["https://esm.sh", "https://unpkg.com"],
            }
        }
    },
)
def view() -> str:
    """View HTML resource — the audio player UI."""
    return get_view_html()
```

---

## 4. TTS Queue Manager

```python
# src/microtherapy/queue.py

import asyncio
import base64
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class TTSQueue:
    queue_id: str
    voice: str
    full_text: str = ""
    audio_chunks: list[bytes] = field(default_factory=list)
    chunks_sent: int = 0  # Index of last chunk sent to client
    done: bool = False
    created_at: float = field(default_factory=time.time)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

class TTSQueueManager:
    def __init__(self):
        self._queues: dict[str, TTSQueue] = {}
        self._tts_model = None

    def set_model(self, model):
        self._tts_model = model

    def create_queue(self, voice: str) -> str:
        queue_id = uuid.uuid4().hex[:12]
        self._queues[queue_id] = TTSQueue(queue_id=queue_id, voice=voice)
        return queue_id

    def add_text(self, queue_id: str, text: str) -> int:
        """Add text. Returns number of new characters."""
        q = self._queues[queue_id]
        old_len = len(q.full_text)
        # Only append the new portion
        if text.startswith(q.full_text):
            q.full_text = text  # Replace with fuller version
        else:
            q.full_text += text
        return len(q.full_text) - old_len

    async def generate_audio(self, queue_id: str):
        """Generate audio for current text in background."""
        q = self._queues[queue_id]
        async with q._lock:
            if not self._tts_model or not q.full_text:
                return
            audio = await self._tts_model.generate_full(q.full_text)
            q.audio_chunks.append(audio)

    def get_new_chunks(self, queue_id: str) -> list[str]:
        """Get base64-encoded chunks since last poll."""
        q = self._queues[queue_id]
        new_chunks = q.audio_chunks[q.chunks_sent:]
        q.chunks_sent = len(q.audio_chunks)
        return [base64.b64encode(c).decode() for c in new_chunks]

    def is_done(self, queue_id: str) -> bool:
        return self._queues[queue_id].done

    def end_queue(self, queue_id: str):
        q = self._queues[queue_id]
        q.done = True
        # Cleanup after 60 seconds
        asyncio.get_event_loop().call_later(
            60, lambda: self._queues.pop(queue_id, None)
        )
```

---

## 5. HTTP Transport Setup

### 5.1 Streamable HTTP App

```python
def create_app():
    """Create the ASGI app for HTTP mode."""
    # Load TTS model
    global tts_model
    tts_model = TTSModel.load_model()
    queue_manager.set_model(tts_model)

    # Create Streamable HTTP app
    app = mcp.streamable_http_app(stateless_http=True, host=HOST)

    # CORS for browser-based MCP hosts
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app
```

### 5.2 Entry Point

```python
def main():
    """Entry point: stdio mode or HTTP mode."""
    logging.basicConfig(level=logging.INFO)

    if "--stdio" in sys.argv:
        # stdio mode (for desktop clients)
        global tts_model
        tts_model = TTSModel.load_model()
        queue_manager.set_model(tts_model)
        mcp.run(transport="stdio")
    else:
        # HTTP mode
        app = create_app()
        print(f"MicroTherapy listening on http://{HOST}:{PORT}/mcp")
        uvicorn.run(app, host=HOST, port=PORT)

if __name__ == "__main__":
    main()
```

---

## 6. MCP 2.0 Protocol Compliance

### 6.1 Request Headers

Every HTTP request to `/mcp` must include:

```http
POST /mcp HTTP/1.1
Content-Type: application/json
MCP-Protocol-Version: 2026-07-28
Mcp-Method: tools/call
Mcp-Name: speak
```

### 6.2 Request Body

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "speak",
    "arguments": {
      "text": "The bug is on line 42 of server.js",
      "voice": "default",
      "autoPlay": true
    },
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientInfo": {
        "name": "ExampleClient",
        "version": "1.0.0"
      },
      "io.modelcontextprotocol/clientCapabilities": {}
    }
  }
}
```

### 6.3 SSE Streaming Responses

When the server responds with SSE:

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
X-Accel-Buffering: no

event: notifications/progress
data: {"jsonrpc":"2.0","method":"notifications/progress","params":{...}}

event: message
data: {"jsonrpc":"2.0","id":1,"result":{...}}
```

---

## 7. Tool Visibility & Security

| Tool | Visibility | Rationale |
|------|-----------|-----------|
| `speak` | Public (LLM-visible) | This is the main entry point |
| `list_voices` | Public | Agent needs to know voice options |
| `create_tts_queue` | App-only | Internal queue management |
| `add_tts_text` | App-only | Only the View should feed text |
| `poll_tts_audio` | App-only | Only the View needs audio chunks |
| `end_tts_queue` | App-only | Only the View signals completion |

App-only tools use `meta={"ui": {"visibility": ["app"]}}`.

---

## 8. Deliverables

- [x] `src/microtherapy/server.py` — Main server with all tools, resources, and HTTP transport
- [x] `src/microtherapy/queue.py` — `TTSQueueManager` for concurrent audio generation
- [x] MCP 2.0 protocol compliance (version `2026-07-28`, stateless, `_meta`, headers)
- [x] Both stdio and HTTP transport modes
- [x] App-only tool visibility restrictions
