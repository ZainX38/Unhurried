"""Tests for the STT adapter (ticket 06). The Vosk tests need the model: `uv run python -m eval.download_model`."""

from pathlib import Path

import numpy as np
import pytest

from eval.audio import read_wav
from eval.run import transcribe
from unhurried.stt import DEFAULT_VOSK_MODEL, STT, to_pcm16
from unhurried.vad import FRAME_SAMPLES

DEMO = Path(__file__).resolve().parents[1] / "eval" / "data" / "demo"
needs_model = pytest.mark.skipif(not DEFAULT_VOSK_MODEL.is_dir(), reason="Vosk model not downloaded")


def test_to_pcm16_is_the_exact_inverse_of_read_wav_scaling() -> None:
    pcm = np.array([-32768, -1, 0, 1, 12345, 32767], dtype="<i2")
    floats = pcm.astype(np.float32) / 32768.0  # what read_wav does
    assert to_pcm16(floats) == pcm.tobytes()


def test_to_pcm16_clips_out_of_range_samples() -> None:
    assert to_pcm16(np.array([2.0, -2.0], dtype=np.float32)) == np.array([32767, -32768], dtype="<i2").tobytes()


@pytest.fixture(scope="module")
def vosk() -> STT:
    from unhurried.stt import VoskSTT
    return VoskSTT()


@needs_model
def test_vosk_transcribes_a_fluent_clip(vosk: STT) -> None:
    transcripts = transcribe(read_wav(DEMO / "A1_fluent.wav"), vosk)
    assert transcripts[0] == ""
    assert transcripts[-1].startswith("my account number is")


@needs_model
def test_vosk_keeps_finished_segments_across_a_block(vosk: STT) -> None:
    # Vosk closes a segment inside the ~3 s Block; the words before it must stay in the transcript.
    transcripts = transcribe(read_wav(DEMO / "A1_stammered.wav"), vosk)
    first = next(i for i, t in enumerate(transcripts) if t.startswith("my account number is"))
    assert all(t.startswith("my account number is") for t in transcripts[first:])
    assert len(transcripts[-1].split()) > len(transcripts[first].split())  # digits arrived after the Block


@needs_model
def test_vosk_reset_starts_a_new_turn(vosk: STT) -> None:
    samples = read_wav(DEMO / "A1_fluent.wav")
    for i in range(200):
        vosk.feed(samples[i * FRAME_SAMPLES : (i + 1) * FRAME_SAMPLES])
    assert vosk.transcript() != ""
    vosk.reset()
    assert vosk.transcript() == ""


def test_missing_model_says_how_to_get_it(tmp_path: Path) -> None:
    from unhurried.stt import VoskSTT
    with pytest.raises(FileNotFoundError, match="download_model"):
        VoskSTT(tmp_path / "nope")
