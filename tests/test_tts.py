"""Tests for TTS module."""

import os
import pytest
from microtherapy.tts import TTSModel


# Ensure HF cache uses writable directory
os.environ.setdefault("HF_HOME", os.path.expanduser("~/.cache/huggingface"))


class TestTTSModel:
    def test_init_no_load(self):
        """TTSModel() should not load the model (lazy init)."""
        model = TTSModel("assets/audio/prompt.wav")
        assert not model.loaded
        assert model.prompt_audio_path == "assets/audio/prompt.wav"

    def test_silent_wav(self):
        wav = TTSModel._silent_wav()
        assert len(wav) > 0
        assert wav[:4] == b"RIFF"

    def test_silent_wav_valid(self):
        """Silent WAV should be parseable."""
        import io, wave
        wav = TTSModel._silent_wav()
        with wave.open(io.BytesIO(wav), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 24000
