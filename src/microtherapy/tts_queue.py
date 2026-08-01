"""TTS queue manager for concurrent audio generation."""

import asyncio
import base64
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from microtherapy.tts import TTSModel

logger = logging.getLogger(__name__)


@dataclass
class TTSQueue:
    """State for a single TTS generation session."""

    queue_id: str
    voice: str
    full_text: str = ""
    audio_chunks: list[bytes] = field(default_factory=list)
    chunks_sent: int = 0
    done: bool = False
    created_at: float = field(default_factory=time.time)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class TTSQueueManager:
    """Manages concurrent TTS processing queues."""

    def __init__(self) -> None:
        self._queues: dict[str, TTSQueue] = {}
        self._tts_model: "TTSModel | None" = None

    def set_model(self, model: "TTSModel") -> None:
        """Set the shared TTS model instance."""
        self._tts_model = model

    def create_queue(self, voice: str) -> str:
        """Create a new TTS queue. Returns queue_id."""
        queue_id = uuid.uuid4().hex[:12]
        self._queues[queue_id] = TTSQueue(queue_id=queue_id, voice=voice)
        # Auto-cleanup after 5 minutes
        asyncio.get_event_loop().call_later(300, lambda: self._queues.pop(queue_id, None))
        return queue_id

    def add_text(self, queue_id: str, text: str) -> int:
        """
        Add or update text for a queue.
        If text starts with existing text, it's a replacement (fuller version).
        Otherwise it's appended.
        Returns number of new characters.
        """
        q = self._queues[queue_id]
        old_len = len(q.full_text)
        if text.startswith(q.full_text):
            q.full_text = text
        else:
            q.full_text += text
        return len(q.full_text) - old_len

    async def generate_audio(self, queue_id: str) -> None:
        """Generate audio for current queue text in background."""
        q = self._queues[queue_id]
        async with q._lock:
            if not self._tts_model:
                logger.error("TTS queue %s: no TTS model set! Call set_model() first.", queue_id)
                return
            if not q.full_text.strip():
                logger.warning("TTS queue %s: empty text, skipping generation.", queue_id)
                return
            try:
                logger.info(
                    "TTS queue %s: starting generation for %d chars: %r",
                    queue_id, len(q.full_text), q.full_text[:80],
                )
                audio = await self._tts_model.generate_full(q.full_text)
                q.audio_chunks.append(audio)
                logger.info(
                    "TTS queue %s: generation complete — %d bytes of audio",
                    queue_id, len(audio),
                )
            except Exception as exc:
                logger.exception(
                    "TTS queue %s: generation FAILED for text=%r — error: %s",
                    queue_id, q.full_text[:80], exc,
                )

    def get_new_chunks(self, queue_id: str) -> list[str]:
        """Get base64-encoded audio chunks since last poll."""
        q = self._queues[queue_id]
        new_chunks = q.audio_chunks[q.chunks_sent :]
        q.chunks_sent = len(q.audio_chunks)
        return [base64.b64encode(c).decode() for c in new_chunks]

    def is_done(self, queue_id: str) -> bool:
        """Check if queue has been ended."""
        return self._queues[queue_id].done

    def end_queue(self, queue_id: str) -> None:
        """Signal end of text input."""
        self._queues[queue_id].done = True
