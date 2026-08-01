"""MicroTherapy MCP 2.0 Server — Streaming TTS for coding agents.

Usage:
    uv run microtherapy           # HTTP mode (default)
    uv run microtherapy --stdio   # stdio mode (for desktop clients)
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import sys
import time
import uuid

import uvicorn
from dotenv import load_dotenv
from mcp.server import MCPServer
from mcp_types._types import CallToolResult, TextContent
from starlette.middleware.cors import CORSMiddleware

from microtherapy.tts import TTSModel
from microtherapy.view import get_view_html, VIEW_URI

load_dotenv()

logger = logging.getLogger(__name__)

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "3001"))

server = MCPServer(name="MicroTherapy", version="0.2.0")

tts_model: TTSModel | None = None

# ── Streaming state ─────────────────────────────────────────────
_streams: dict[str, dict] = {}


# ---- Public Tools ----

@server.tool(
    name="speak",
    description=(
        "Speak English text aloud using TTS. "
        "Triggers an audio player in the chat. "
        "Use when you want to speak to the user rather than just write."
    ),
    meta={"ui": {"resourceUri": VIEW_URI}},
)
async def speak(
    text: str = "Hello! I'm your coding assistant.",
    voice: str = "default",
    autoPlay: bool = True,
) -> CallToolResult:
    """Start streaming TTS generation. Returns queue_id immediately."""
    logger.info("speak: voice=%r, text=%r", voice, text[:80])

    queue_id = uuid.uuid4().hex[:12]
    _streams[queue_id] = {
        "chunks": [],
        "done": False,
        "text": text,
        "voice": voice,
        "autoPlay": autoPlay,
        "sample_rate": 24000,
        "created": time.time(),
    }

    # Launch background generation
    asyncio.create_task(_generate_stream(queue_id, text, voice))

    return CallToolResult(
        content=[TextContent(
            type="text",
            text=json.dumps({
                "status": "streaming",
                "queue_id": queue_id,
                "text": text,
                "voice": voice,
                "autoPlay": autoPlay,
            }),
        )],
        _meta={"ui": {"resourceUri": VIEW_URI}},
    )


async def _generate_stream(queue_id: str, text: str, voice: str = "default") -> None:
    """Background task: generate TTS and store chunks."""
    try:
        async for chunk in tts_model.generate_stream(text, voice=voice):
            b64 = base64.b64encode(chunk).decode()
            _streams[queue_id]["chunks"].append(b64)
    except Exception as exc:
        logger.exception("Stream generation failed for %s: %s", queue_id, exc)
    finally:
        _streams[queue_id]["done"] = True


@server.tool(
    name="get_speak_audio",
    description="Get the next audio chunk for a streaming speak call.",
)
def get_speak_audio(audio_id: str, chunk_index: int = 0) -> CallToolResult:
    """Return the next audio chunk for a given queue_id."""
    stream = _streams.get(audio_id)
    if not stream:
        return CallToolResult(content=[TextContent(
            type="text",
            text=json.dumps({"status": "error", "error": "Unknown audio_id"}),
        )])

    chunks = stream["chunks"]
    if chunk_index >= len(chunks):
        if stream["done"]:
            # Clean up old streams
            if time.time() - stream["created"] > 300:
                _streams.pop(audio_id, None)
            return CallToolResult(content=[TextContent(
                type="text",
                text=json.dumps({"status": "done"}),
            )])
        return CallToolResult(content=[TextContent(
            type="text",
            text=json.dumps({"status": "waiting"}),
        )])

    b64 = chunks[chunk_index]
    sample_rate = stream["sample_rate"]
    is_last = chunk_index >= len(chunks) - 1 and stream["done"]

    return CallToolResult(content=[TextContent(
        type="text",
        text=json.dumps({
            "status": "chunk",
            "chunk_index": chunk_index,
            "audio_b64": b64,
            "sample_rate": sample_rate,
            "is_last": is_last,
        }),
    )])


@server.tool(name="list_voices", description="List available TTS voices.")
def list_voices() -> CallToolResult:
    from microtherapy.tts import VOICES
    voices = {k: v["name"] for k, v in VOICES.items()}
    return CallToolResult(content=[TextContent(
        type="text",
        text=json.dumps(voices, indent=2),
    )])


@server.tool(
    name="get_latest_speak",
    description="Get the most recent speak queue for the audio player.",
)
def get_latest_speak() -> CallToolResult:
    """Return the most recent streaming speak session info."""
    if not _streams:
        return CallToolResult(content=[TextContent(
            type="text",
            text=json.dumps({"status": "no_streams"}),
        )])

    # Find the most recent stream by creation time
    latest_id = max(_streams.keys(), key=lambda k: _streams[k].get("created", 0))
    stream = _streams[latest_id]

    # Only return if it was created in the last 60 seconds
    if time.time() - stream.get("created", 0) > 60:
        return CallToolResult(content=[TextContent(
            type="text",
            text=json.dumps({"status": "no_recent_streams"}),
        )])

    return CallToolResult(content=[TextContent(
        type="text",
        text=json.dumps({
            "status": "streaming",
            "queue_id": latest_id,
            "text": stream.get("text", ""),
            "voice": stream.get("voice", "default"),
            "autoPlay": stream.get("autoPlay", True),
        }),
    )])


@server.tool(
    name="get_full_audio",
    description="Get the complete audio as a WAV file (base64) for a speak queue.",
)
def get_full_audio(audio_id: str) -> CallToolResult:
    """Return the full concatenated WAV for a queue_id."""
    import io
    import wave
    
    stream = _streams.get(audio_id)
    if not stream:
        return CallToolResult(content=[TextContent(
            type="text",
            text=json.dumps({"status": "error", "error": "Unknown audio_id"}),
        )])
    
    if not stream["done"]:
        return CallToolResult(content=[TextContent(
            type="text",
            text=json.dumps({"status": "waiting"}),
        )])
    
    chunks = stream["chunks"]
    if not chunks:
        return CallToolResult(content=[TextContent(
            type="text",
            text=json.dumps({"status": "error", "error": "No audio data"}),
        )])
    
    # Concatenate all PCM chunks and build WAV
    all_pcm = b"".join(base64.b64decode(c) for c in chunks)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(all_pcm)
    
    wav_b64 = base64.b64encode(buf.getvalue()).decode()
    return CallToolResult(content=[TextContent(
        type="text",
        text=json.dumps({
            "status": "complete",
            "audio_b64": wav_b64,
            "sample_rate": 24000,
            "duration_ms": len(all_pcm) / 48,  # bytes→ms: 2 bytes/sample, 48 bytes/ms at 24kHz
        }),
    )])


# ---- App-Only Tools ----
# (none currently — audio is embedded directly in speak results)

# ---- UI Resource ----

@server.resource(
    VIEW_URI,
    name="MicroTherapy Audio Player",
    mime_type="text/html;profile=mcp-app",
    meta={
        "ui": {
            "csp": {
                "resourceDomains": ["https://esm.sh", "https://unpkg.com", "http://localhost:3002"],
            }
        }
    },
)
def view() -> str:
    return get_view_html()


# ---- Entry Points ----

def create_app():
    global tts_model
    tts_model = TTSModel.load_model(default_voice="am_adam")
    app = server.streamable_http_app(stateless_http=True, host=HOST)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )
    return app


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    debug_save = os.environ.get("MICROTHERAPY_DEBUG_SAVE_AUDIO", "")
    if debug_save:
        logger.info(
            "MICROTHERAPY_DEBUG_SAVE_AUDIO=%s — audio will be saved to assets/audio/",
            debug_save,
        )

    if "--stdio" in sys.argv:
        logger.info("MicroTherapy starting in stdio mode...")
        global tts_model
        tts_model = TTSModel.load_model(prompt_audio_path="assets/audio/prompt.wav")
        server.run(transport="stdio")
    else:
        app = create_app()
        logger.info("MicroTherapy listening on http://%s:%s/mcp", HOST, PORT)
        uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
