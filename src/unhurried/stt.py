"""Streaming speech-to-text behind one small interface (ticket 06, ADR 0002).

The Endpointer only ever sees `transcript()`: what the STT has heard so far this Turn.
Providers can be swapped (Vosk now, a streaming cloud API later) without touching it.

Vosk splits audio into segments at its own silences and emits a "final" result for each.
Those finals are only transcript chunks, never Turn ends: only the Endpointer decides.
`PartialResult` restarts empty after every final, so the transcript is every finished
segment plus the current partial. A final may rewrite the partial it replaces
("fourteenth" -> "fortieth"), so the transcript is not guaranteed to only grow.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

import numpy as np

SAMPLE_RATE = 16_000
VOSK_MODEL_NAME = "vosk-model-small-en-us-0.15"
VOSK_MODEL_URL = f"https://alphacephei.com/vosk/models/{VOSK_MODEL_NAME}.zip"
MODELS_DIR = Path(__file__).resolve().parents[2] / "models"  # repo root, git-ignored
DEFAULT_VOSK_MODEL = MODELS_DIR / VOSK_MODEL_NAME


class STT(Protocol):
    def reset(self) -> None:
        """Start a new Turn: forget everything heard so far."""
        ...

    def feed(self, frame: np.ndarray) -> None:
        """One frame of 16 kHz mono float samples in [-1, 1]."""
        ...

    def transcript(self) -> str:
        """Everything heard this Turn, lowercase words separated by single spaces. "" if nothing yet."""
        ...


def to_pcm16(frame: np.ndarray) -> bytes:
    """Float samples -> little-endian 16-bit PCM. Exact inverse of eval.audio.read_wav's scaling."""
    return np.clip(np.round(frame * 32768.0), -32768, 32767).astype("<i2").tobytes()


class VoskSTT:
    """Vosk, streaming. The model is loaded once; each reset() starts a fresh recognizer."""

    def __init__(self, model_dir: Path = DEFAULT_VOSK_MODEL) -> None:
        from vosk import Model, SetLogLevel  # imported here so the rest of the package works without vosk

        if not Path(model_dir).is_dir():
            raise FileNotFoundError(
                f"Vosk model not found at {model_dir}. Run `uv run python -m eval.download_model` first."
            )
        SetLogLevel(-1)  # Kaldi logs every model load and segment to stderr
        self._model = Model(str(model_dir))
        self.reset()

    def reset(self) -> None:
        from vosk import KaldiRecognizer

        self._recognizer = KaldiRecognizer(self._model, SAMPLE_RATE)
        self._finished: list[str] = []
        self._partial = ""

    def feed(self, frame: np.ndarray) -> None:
        if self._recognizer.AcceptWaveform(to_pcm16(frame)):
            # Vosk closed a segment: keep its text, the partial starts again from empty.
            text = json.loads(self._recognizer.Result())["text"]
            if text:
                self._finished.append(text)
            self._partial = ""
        else:
            self._partial = json.loads(self._recognizer.PartialResult())["partial"]

    def transcript(self) -> str:
        return " ".join(t for t in (*self._finished, self._partial) if t)
