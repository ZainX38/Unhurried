"""Energy VAD: labels each 32 ms frame of 16 kHz audio as speech or silence.

A frame is speech when its RMS level is above SPEECH_THRESHOLD_DB (dBFS).
There is no smoothing: the Baseline only counts silence, so a short dropout
inside a word just resets its count early, which is harmless.

-45 dBFS is the same threshold eval/make_data.py used to find `true_end_ms`,
so this VAD agrees with the ground truth almost exactly. That makes it an
optimistic VAD; Silero (later) gives an independent opinion.

Used by the evaluation (eval/run.py) and later by the live server (ticket 07).
"""

from __future__ import annotations

import numpy as np

SAMPLE_RATE = 16_000
FRAME_MS = 32
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000  # 512
SPEECH_THRESHOLD_DB = -45.0


def frame_db(frame: np.ndarray) -> float:
    """RMS level of one frame in dBFS (float samples in [-1, 1]). Digital silence is about -120."""
    return float(10 * np.log10(np.mean(np.square(frame, dtype=np.float64)) + 1e-12))


def is_speech(frame: np.ndarray, threshold_db: float = SPEECH_THRESHOLD_DB) -> bool:
    """True if this one 512-sample frame is speech. Raises ValueError on any other length."""
    if len(frame) != FRAME_SAMPLES:
        raise ValueError(f"expected a {FRAME_SAMPLES}-sample frame, got {len(frame)}")
    return frame_db(frame) > threshold_db


def speech_mask(samples: np.ndarray, threshold_db: float = SPEECH_THRESHOLD_DB) -> list[bool]:
    """is_speech for every whole frame of `samples`, in order. A trailing partial frame is dropped."""
    n = len(samples) // FRAME_SAMPLES
    frames = samples[: n * FRAME_SAMPLES].reshape(n, FRAME_SAMPLES).astype(np.float64)
    db = 10 * np.log10(np.mean(frames**2, axis=1) + 1e-12)
    return [bool(x) for x in db > threshold_db]
