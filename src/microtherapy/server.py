"""MicroTherapy MCP 2.0 Server — Streaming TTS for coding agents.

Usage:
    uv run microtherapy           # HTTP mode (default)
    uv run microtherapy --stdio   # stdio mode (for desktop clients)
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import sys
import time
import uuid
import wave

import uvicorn
from dotenv import load_dotenv
from mcp.server import MCPServer
from mcp_types._types import CallToolResult, TextContent
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response

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
        "bytes_generated": 0,
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
            _streams[queue_id]["bytes_generated"] = \
                _streams[queue_id].get("bytes_generated", 0) + len(chunk)
    except Exception as exc:
        logger.exception("Stream generation failed for %s: %s", queue_id, exc)
    finally:
        _streams[queue_id]["done"] = True


@server.tool(
    name="get_speak_audio",
    description="Get the next audio chunk for a streaming speak call.",
)
def get_speak_audio(audio_id: str, chunk_index: int = 0, count: int = 100) -> CallToolResult:
    """Return up to `count` audio chunks (concatenated PCM) starting at chunk_index."""
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
                text=json.dumps({"status": "done", "total_chunks": len(chunks)}),
            )])
        return CallToolResult(content=[TextContent(
            type="text",
            text=json.dumps({
                "status": "waiting",
                "progress_ms": stream.get("bytes_generated", 0) / 48,
            }),
        )])

    batch = chunks[chunk_index:chunk_index + count]
    pcm = b"".join(base64.b64decode(c) for c in batch)
    sample_rate = stream["sample_rate"]
    is_last = (chunk_index + len(batch)) >= len(chunks) and stream["done"]

    return CallToolResult(content=[TextContent(
        type="text",
        text=json.dumps({
            "status": "chunk",
            "chunk_index": chunk_index,
            "chunk_count": len(batch),
            "audio_b64": base64.b64encode(pcm).decode(),
            "sample_rate": sample_rate,
            "is_last": is_last,
            "progress_ms": stream.get("bytes_generated", 0) / 48,
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
    name="get_speak_status",
    description="Check whether a speak queue has finished generating, without downloading audio.",
)
def get_speak_status(audio_id: str) -> CallToolResult:
    """Lightweight status poll for the audio player."""
    stream = _streams.get(audio_id)
    if not stream:
        return CallToolResult(content=[TextContent(
            type="text",
            text=json.dumps({"status": "error", "error": "Unknown audio_id"}),
        )])

    if stream["done"]:
        return CallToolResult(content=[TextContent(
            type="text",
            text=json.dumps({
                "status": "complete",
                "progress_ms": stream.get("bytes_generated", 0) / 48,
                "chunk_count": len(stream["chunks"]),
            }),
        )])

    return CallToolResult(content=[TextContent(
        type="text",
        text=json.dumps({
            "status": "waiting",
            "progress_ms": stream.get("bytes_generated", 0) / 48,
        }),
    )])


@server.tool(
    name="get_full_audio",
    description="Get the complete audio as a WAV file (base64) for a speak queue.",
)
def get_full_audio(audio_id: str) -> CallToolResult:
    """Return the full concatenated WAV for a queue_id."""
    stream = _streams.get(audio_id)
    if not stream:
        return CallToolResult(content=[TextContent(
            type="text",
            text=json.dumps({"status": "error", "error": "Unknown audio_id"}),
        )])
    
    if not stream["done"]:
        return CallToolResult(content=[TextContent(
            type="text",
            text=json.dumps({
                "status": "waiting",
                "progress_ms": stream.get("bytes_generated", 0) / 48,
            }),
        )])
    
    chunks = stream["chunks"]
    if not chunks:
        return CallToolResult(content=[TextContent(
            type="text",
            text=json.dumps({"status": "error", "error": "No audio data"}),
        )])

    # Concatenate all PCM chunks and build WAV (cached)
    wav = _build_wav(audio_id)
    wav_b64 = base64.b64encode(wav).decode()
    return CallToolResult(content=[TextContent(
        type="text",
        text=json.dumps({
            "status": "complete",
            "audio_b64": wav_b64,
            "sample_rate": 24000,
            "duration_ms": len(wav) / 96,  # bytes→ms at 24kHz 16-bit mono
            "url": f"/audio/{audio_id}.wav",
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
                # scripts/styles/images/fonts (esm.sh importmap, player assets)
                "resourceDomains": ["https://esm.sh", "https://unpkg.com"],
                # fetch()/XHR — REQUIRED for the player to download WAV files
                "connectDomains": ["http://localhost:3001"],
            }
        }
    },
)
def view() -> str:
    return get_view_html()


# ---- Entry Points ----

@server.tool(
    name="test_play",
    description="Play a pre-made test beep to verify the audio pipeline.",
    meta={"ui": {"resourceUri": VIEW_URI}},
)
def test_play() -> CallToolResult:
    """Return a pre-made test WAV file (440Hz beep)."""
    import base64
    try:
        with open("assets/audio/test_beep.wav", "rb") as f:
            wav_b64 = base64.b64encode(f.read()).decode()
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=json.dumps({
                    "status": "ready",
                    "audio_b64": wav_b64,
                    "sample_rate": 24000,
                    "duration_ms": 1000,
                }),
            )],
            _meta={"ui": {"resourceUri": VIEW_URI}},
        )
    except FileNotFoundError:
        return CallToolResult(content=[TextContent(
            type="text",
            text=json.dumps({"status": "error", "error": "test_beep.wav not found"}),
        )])


def _build_wav(audio_id: str) -> bytes | None:
    """Build (and cache) the complete WAV for a finished stream."""
    stream = _streams.get(audio_id)
    if not stream or not stream["done"]:
        return None
    if stream.get("wav") is not None:
        return stream["wav"]
    chunks = stream["chunks"]
    if not chunks:
        return None
    all_pcm = b"".join(base64.b64decode(c) for c in chunks)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(stream.get("sample_rate", 24000))
        wf.writeframes(all_pcm)
    wav = buf.getvalue()
    stream["wav"] = wav
    return wav


async def audio_file_endpoint(request: Request) -> Response:
    """Serve the finished WAV as a plain file: GET /audio/{id}.wav"""
    audio_id = request.path_params.get("audio_id", "").removesuffix(".wav")
    wav = _build_wav(audio_id)
    if wav is None:
        return Response(status_code=404)
    return Response(content=wav, media_type="audio/wav", headers={
        "Cache-Control": "no-store",
    })


def create_app():
    global tts_model
    tts_model = TTSModel.load_model(default_voice="am_adam")
    app = server.streamable_http_app(stateless_http=True, host=HOST)
    app.add_route("/audio/{audio_id}.wav", audio_file_endpoint, methods=["GET"])
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
