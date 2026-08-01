#!/usr/bin/env python3
"""
Kokoro-82M TTS test.
Saves generated audio to assets/audio/kokoro_test/

Usage:
    uv run python scripts/kokoro_test.py [--text "Hello world"] [--voice af_heart]
"""

from __future__ import annotations

import argparse
import json
import time
import wave
from pathlib import Path

import numpy as np

OUTPUT_DIR = Path("assets/audio/kokoro_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Kokoro-82M TTS test")
    parser.add_argument("--text", default="I love cheese! This is a test of Kokoro TTS.", help="Text to synthesize")
    parser.add_argument("--voice", default="af_heart", help="Voice name (default: af_heart)")
    parser.add_argument("--lang", default="a", help="Language code: a=American, b=British")
    args = parser.parse_args()

    print(f"🟢 Kokoro-82M Test")
    print(f"   Text: {args.text!r}")
    print(f"   Voice: {args.voice}")
    print(f"   Language: {args.lang}")
    print()

    # ── Load Kokoro pipeline ───────────────────────────────
    print("Loading Kokoro pipeline...")
    t0 = time.time()

    from kokoro import KPipeline

    pipeline = KPipeline(lang_code=args.lang)
    sample_rate = getattr(pipeline, 'sample_rate', 24000)  # Kokoro default
    print(f"Pipeline loaded in {time.time() - t0:.1f}s")
    print(f"Sample rate: {sample_rate} Hz")
    voices = getattr(pipeline, 'voices', None)
    if voices:
        print(f"Voices: {list(voices)[:5] if not isinstance(voices, list) else voices[:5]}...")

    # ── Generate ───────────────────────────────────────────
    print(f"\nGenerating...")
    t0 = time.time()

    result = pipeline(args.text, voice=args.voice)

    # result is a generator yielding (graphemes, phonemes, audio) tuples
    all_audio = []
    total_samples = 0
    for i, (graphemes, phonemes, audio) in enumerate(result):
        # audio may be torch Tensor or numpy array
        if hasattr(audio, 'numpy'):
            audio_np = audio.numpy()
        else:
            audio_np = np.asarray(audio)
        all_audio.append(audio_np)
        total_samples += len(audio_np)
        duration_ms = len(audio_np) / sample_rate * 1000
        rms = float(np.sqrt(np.mean(audio_np.astype(np.float32) ** 2)))
        peak = float(np.max(np.abs(audio_np)))
        print(f"  segment {i}: {len(audio)} samples ({duration_ms:.0f}ms) — RMS={rms:.4f}, peak={peak:.4f}")

    gen_time = time.time() - t0
    total_duration = total_samples / sample_rate
    print(f"\nGenerated in {gen_time:.1f}s")
    print(f"Total: {len(all_audio)} segments, {total_samples} samples, {total_duration:.2f}s audio")
    print(f"RTF (real-time factor): {gen_time / total_duration:.1f}x")

    # ── Concatenate and save ───────────────────────────────
    if all_audio:
        full = np.concatenate([np.asarray(a) for a in all_audio])
        # Convert to int16 PCM
        full_i16 = (full * 32767).clip(-32768, 32767).astype(np.int16)

        wav_path = OUTPUT_DIR / f"kokoro_{args.voice}_{int(time.time())}.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(full_i16.tobytes())

        print(f"\n✓ WAV saved: {wav_path} ({wav_path.stat().st_size} bytes)")

        # Stats
        f32 = full.astype(np.float32)
        stats = {
            "model": "Kokoro-82M",
            "voice": args.voice,
            "lang": args.lang,
            "text": args.text,
            "sample_rate": sample_rate,
            "segments": len(all_audio),
            "total_samples": int(total_samples),
            "total_duration_s": round(total_duration, 2),
            "gen_time_s": round(gen_time, 1),
            "rtf": round(gen_time / total_duration, 1),
            "rms": float(np.sqrt(np.mean(f32 ** 2))),
            "peak": float(np.max(np.abs(f32))),
            "dc_offset": float(np.mean(f32)),
        }
        stats_path = OUTPUT_DIR / "stats.json"
        stats_path.write_text(json.dumps(stats, indent=2))
        print(f"✓ Stats saved: {stats_path}")

        print(f"\n📊 Analysis:")
        print(f"   Duration: {total_duration:.2f}s (expected ~{len(args.text.split())*0.3:.1f}s for speech)")
        print(f"   RMS: {stats['rms']:.4f}")
        print(f"   Peak: {stats['peak']:.4f}")
        print(f"   DC offset: {stats['dc_offset']:.6f}")

        # Check for clipping
        clipped = np.sum(np.abs(f32) > 0.99)
        if clipped > 0:
            print(f"   ⚠ Clipping: {clipped} samples")
        else:
            print(f"   ✓ No clipping")

        # Check if it's mostly silence
        silent = np.sum(np.abs(f32) < 0.001) / len(f32)
        print(f"   Silent samples: {silent*100:.1f}%")
        if silent > 0.5:
            print(f"   ⚠ More than 50% silence — audio may be bad!")
        else:
            print(f"   ✓ Good")

        print(f"\n🔊 Listen: {wav_path}")
    else:
        print("\n⚠ No audio generated!")


if __name__ == "__main__":
    main()
