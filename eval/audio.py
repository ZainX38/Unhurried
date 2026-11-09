"""Small, strict WAV helpers shared by the data script and (later) the eval harness.

Everything in the eval works on one format only: 16 kHz, mono, 16-bit PCM.
`read_wav` refuses anything else instead of silently converting, so a wrong
file is caught at load time rather than producing subtly wrong timings.
Convert raw recordings first with `eval/convert_recordings.py`.

Samples are handled as float32 numpy arrays in [-1.0, 1.0].
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16_000
SAMPLES_PER_MS = SAMPLE_RATE // 1000  # 16 samples = 1 ms, so ms <-> samples is exact


def read_wav(path: Path) -> np.ndarray:
    """Load a 16 kHz mono 16-bit WAV as float32 in [-1, 1]. Raise ValueError on any other format."""
    with wave.open(str(path), "rb") as w:
        rate, channels, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        if (rate, channels, width) != (SAMPLE_RATE, 1, 2):
            raise ValueError(
                f"{path}: expected 16000 Hz mono 16-bit, got {rate} Hz, "
                f"{channels} channel(s), {width * 8}-bit. "
                "Run `uv run python -m eval.convert_recordings` first."
            )
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0


def write_wav(path: Path, samples: np.ndarray) -> None:
    """Write float samples as 16 kHz mono 16-bit WAV, clipping anything outside [-1, 1]."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(np.round(samples * 32768.0), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())


def ms_to_samples(ms: int) -> int:
    return ms * SAMPLES_PER_MS


def samples_to_ms(n: int) -> int:
    """Exact when n is a multiple of 16; every length make_data builds is."""
    return n // SAMPLES_PER_MS
