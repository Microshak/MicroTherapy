#!/usr/bin/env python3
"""Generate Kokoro test samples for ALL English voices."""

import time
import wave
from pathlib import Path

import numpy as np

OUTPUT_DIR = Path("assets/audio/kokoro_voices")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VOICES = {
    # American Female
    "a": [
        "af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica",
        "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    ],
    # American Male
    "a_m": [
        "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam",
        "am_michael", "am_onyx", "am_puck", "am_santa",
    ],
    # British Female
    "b": [
        "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    ],
    # British Male
    "b_m": [
        "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
    ],
}

from kokoro import KPipeline

# Cache pipelines by language
pipelines = {}

for lang, voices in VOICES.items():
    # Map to actual language code (strip _m suffix)
    lang_code = lang[0]  # 'a' or 'b'

    if lang_code not in pipelines:
        print(f"Loading Kokoro pipeline for lang={lang_code}...")
        pipelines[lang_code] = KPipeline(lang_code=lang_code)

    pipeline = pipelines[lang_code]

    for voice in voices:
        text = f"Hello, my name is {voice.replace('_', ' ').replace('af ', '').replace('am ', '').replace('bf ', '').replace('bm ', '')}."

        print(f"  Generating {voice}...", end=" ", flush=True)
        t0 = time.time()

        result = pipeline(text, voice=voice)
        all_audio = []
        for graphemes, phonemes, audio in result:
            all_audio.append(audio.numpy() if hasattr(audio, 'numpy') else np.asarray(audio))

        if all_audio:
            full = np.concatenate(all_audio)
            full_i16 = (full * 32767).clip(-32768, 32767).astype(np.int16)

            fname = f"{voice}.wav"
            wav_path = OUTPUT_DIR / fname
            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(full_i16.tobytes())

            duration = len(full) / 24000
            print(f"{duration:.1f}s ✓")
        else:
            print("FAILED")

print(f"\n✓ All samples saved to: {OUTPUT_DIR}/")
print(f"  {len(list(OUTPUT_DIR.glob('*.wav')))} files")
