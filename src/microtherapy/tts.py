"""Kokoro-82M TTS wrapper for MicroTherapy.

Wraps the Kokoro KPipeline to provide a clean async API
for the MCP server. Supports streaming via chunked full-audio output.
"""

from __future__ import annotations

import asyncio
import datetime
import io
import logging
import os
import wave
from pathlib import Path
from typing import AsyncIterator

import numpy as np

logger = logging.getLogger(__name__)

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent

_DEBUG_SAVE_AUDIO = os.environ.get("MICROTHERAPY_DEBUG_SAVE_AUDIO", "").strip().lower() in (
    "1", "true", "yes", "on"
)
_DEBUG_AUDIO_DIR = _PACKAGE_ROOT / "assets" / "audio"

SAMPLE_RATE = 24000
SAMPLE_WIDTH = 2
NUM_CHANNELS = 1
CHUNK_DURATION_MS = 80
SAMPLES_PER_CHUNK = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)  # 1920
BYTES_PER_CHUNK = SAMPLES_PER_CHUNK * SAMPLE_WIDTH  # 3840

VOICES: dict[str, dict[str, str]] = {
    "af_alloy":   {"lang": "a", "name": "Alloy (American Female)"},
    "af_aoede":   {"lang": "a", "name": "Aoede (American Female)"},
    "af_bella":   {"lang": "a", "name": "Bella (American Female)"},
    "af_heart":   {"lang": "a", "name": "Heart (American Female)"},
    "af_jessica": {"lang": "a", "name": "Jessica (American Female)"},
    "af_kore":    {"lang": "a", "name": "Kore (American Female)"},
    "af_nicole":  {"lang": "a", "name": "Nicole (American Female)"},
    "af_nova":    {"lang": "a", "name": "Nova (American Female)"},
    "af_river":   {"lang": "a", "name": "River (American Female)"},
    "af_sarah":   {"lang": "a", "name": "Sarah (American Female)"},
    "af_sky":     {"lang": "a", "name": "Sky (American Female)"},
    "am_adam":    {"lang": "a", "name": "Adam (American Male)"},
    "am_echo":    {"lang": "a", "name": "Echo (American Male)"},
    "am_eric":    {"lang": "a", "name": "Eric (American Male)"},
    "am_fenrir":  {"lang": "a", "name": "Fenrir (American Male)"},
    "am_liam":    {"lang": "a", "name": "Liam (American Male)"},
    "am_michael": {"lang": "a", "name": "Michael (American Male)"},
    "am_onyx":    {"lang": "a", "name": "Onyx (American Male)"},
    "am_puck":    {"lang": "a", "name": "Puck (American Male)"},
    "am_santa":   {"lang": "a", "name": "Santa (American Male)"},
    "bf_alice":    {"lang": "b", "name": "Alice (British Female)"},
    "bf_emma":     {"lang": "b", "name": "Emma (British Female)"},
    "bf_isabella": {"lang": "b", "name": "Isabella (British Female)"},
    "bf_lily":     {"lang": "b", "name": "Lily (British Female)"},
    "bm_daniel":   {"lang": "b", "name": "Daniel (British Male)"},
    "bm_fable":    {"lang": "b", "name": "Fable (British Male)"},
    "bm_george":   {"lang": "b", "name": "George (British Male)"},
    "bm_lewis":    {"lang": "b", "name": "Lewis (British Male)"},
    "default": {"lang": "a", "name": "Adam (Default)"},
}


class TTSModel:
    """Wraps Kokoro-82M KPipeline for streaming TTS."""

    def __init__(self, default_voice: str = "am_adam") -> None:
        self._default_voice = default_voice
        self._pipelines: dict[str, object] = {}
        self._loaded = False

    @classmethod
    def load_model(cls, default_voice: str = "am_adam") -> "TTSModel":
        model = cls(default_voice)
        model._load_pipeline()
        return model

    def _load_pipeline(self) -> None:
        if self._loaded:
            return
        self._get_pipeline("a")
        self._loaded = True

    def _get_pipeline(self, lang_code: str):
        if lang_code not in self._pipelines:
            from kokoro import KPipeline
            logger.info("Loading Kokoro pipeline for lang=%s...", lang_code)
            self._pipelines[lang_code] = KPipeline(lang_code=lang_code)
            logger.info("Kokoro pipeline loaded (lang=%s).", lang_code)
        return self._pipelines[lang_code]

    @property
    def sample_rate(self) -> int:
        return SAMPLE_RATE

    @property
    def loaded(self) -> bool:
        return self._loaded

    @staticmethod
    def _to_int16(audio) -> np.ndarray:
        if hasattr(audio, 'numpy'):
            audio = audio.numpy()
        audio_np = np.asarray(audio, dtype=np.float32)
        return (audio_np * 32767).clip(-32768, 32767).astype(np.int16)

    @staticmethod
    def _to_pcm(audio: np.ndarray) -> bytes:
        return TTSModel._to_int16(audio).tobytes()

    @staticmethod
    def _save_debug(wav_bytes: bytes, text: str) -> str | None:
        if not _DEBUG_SAVE_AUDIO:
            return None
        _DEBUG_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in text[:40])
        fpath = _DEBUG_AUDIO_DIR / f"debug_{ts}_{safe}.wav"
        fpath.write_bytes(wav_bytes)
        logger.info("DEBUG: Saved audio to %s (%d bytes)", fpath, len(wav_bytes))
        return str(fpath)

    async def generate_full(self, text: str, voice: str | None = None) -> bytes:
        voice = voice or self._default_voice
        # Resolve "default" to the actual default voice (am_adam) since Kokoro
        # does not have a voices/default.pt file.
        if voice == "default":
            voice = self._default_voice
        vi = VOICES.get(voice, VOICES[self._default_voice])
        lang = vi["lang"]
        logger.info("Kokoro generate_full: voice=%s, text=%r", voice, text[:80])
        if not text.strip():
            return self._silent_wav()

        loop = asyncio.get_event_loop()

        def _run() -> bytes:
            pipeline = self._get_pipeline(lang)
            result = pipeline(text, voice=voice)
            all_audio = []
            for _, _, audio in result:
                all_audio.append(audio.numpy() if hasattr(audio, 'numpy') else np.asarray(audio))
            if not all_audio:
                return self._silent_wav()
            full = np.concatenate(all_audio)
            logger.info("Kokoro: generated %.2fs audio", len(full) / SAMPLE_RATE)
            i16 = (full * 32767).clip(-32768, 32767).astype(np.int16)
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(NUM_CHANNELS)
                wf.setsampwidth(SAMPLE_WIDTH)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(i16.tobytes())
            wav = buf.getvalue()
            self._save_debug(wav, text)
            return wav

        return await loop.run_in_executor(None, _run)

    async def generate_stream(self, text: str, voice: str | None = None) -> AsyncIterator[bytes]:
        voice = voice or self._default_voice
        # Resolve "default" to the actual default voice (am_adam) since Kokoro
        # does not have a voices/default.pt file.
        if voice == "default":
            voice = self._default_voice
        vi = VOICES.get(voice, VOICES[self._default_voice])
        lang = vi["lang"]
        logger.info("Kokoro stream: voice=%s, text=%r", voice, text[:80])
        if not text.strip():
            return

        loop = asyncio.get_event_loop()
        queue: asyncio.Queue[bytes | None] = asyncio.Queue()

        def _run() -> None:
            try:
                pipeline = self._get_pipeline(lang)
                result = pipeline(text, voice=voice)
                all_audio = []
                for _, _, audio in result:
                    all_audio.append(audio.numpy() if hasattr(audio, 'numpy') else np.asarray(audio))
                if not all_audio:
                    asyncio.run_coroutine_threadsafe(queue.put(None), loop)
                    return
                full = np.concatenate(all_audio).astype(np.float32)
                total = len(full)
                logger.info("Kokoro stream: %.2fs audio, chunking", total / SAMPLE_RATE)
                offset = 0
                while offset < total:
                    end = min(offset + SAMPLES_PER_CHUNK, total)
                    chunk = full[offset:end]
                    if len(chunk) < SAMPLES_PER_CHUNK:
                        chunk = np.pad(chunk, (0, SAMPLES_PER_CHUNK - len(chunk)))
                    pcm = TTSModel._to_pcm(chunk)
                    asyncio.run_coroutine_threadsafe(queue.put(pcm), loop)
                    offset = end
            except Exception as exc:
                logger.exception("Kokoro streaming error: %s", exc)
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)

        task = loop.run_in_executor(None, _run)
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk
        await task

    @staticmethod
    def _silent_wav(duration_ms: int = 100) -> bytes:
        num = int(SAMPLE_RATE * duration_ms / 1000)
        silence = np.zeros(num, dtype=np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(NUM_CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(silence.tobytes())
        return buf.getvalue()

    def reset_stream(self) -> None:
        pass


def get_voice_config(voice_name: str = "default") -> dict[str, str]:
    if voice_name not in VOICES:
        logger.warning("Unknown voice '%s', falling back to default.", voice_name)
        voice_name = "default"
    return VOICES[voice_name]
