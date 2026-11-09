import numpy as np
import pytest

from unhurried.vad import FRAME_SAMPLES, SAMPLE_RATE, is_speech, speech_mask


def tone(db: float, n: int = FRAME_SAMPLES) -> np.ndarray:
    """A 200 Hz sine whose RMS level is `db` dBFS."""
    t = np.arange(n) / SAMPLE_RATE
    amplitude = 10 ** (db / 20) * np.sqrt(2)  # sine RMS = amplitude / sqrt(2)
    return (amplitude * np.sin(2 * np.pi * 200 * t)).astype(np.float32)


def noise_floor(n: int = FRAME_SAMPLES) -> np.ndarray:
    """The -60 dBFS Gaussian noise make_data lays over every clip."""
    return np.random.default_rng(0).normal(0.0, 10 ** (-60 / 20), n).astype(np.float32)


def test_loud_tone_is_speech() -> None:
    assert is_speech(tone(-20)) is True


def test_digital_silence_is_not_speech() -> None:
    assert is_speech(np.zeros(FRAME_SAMPLES, dtype=np.float32)) is False


def test_clip_noise_floor_is_not_speech() -> None:
    assert is_speech(noise_floor()) is False


@pytest.mark.parametrize("length", [0, 511, 513, 1024])
def test_wrong_frame_length_raises(length: int) -> None:
    with pytest.raises(ValueError):
        is_speech(np.zeros(length, dtype=np.float32))


def test_mask_has_one_value_per_whole_frame_and_drops_the_partial_one() -> None:
    audio = np.concatenate([noise_floor(), tone(-20), noise_floor(), tone(-20)[:100]])
    assert speech_mask(audio) == [False, True, False]


def test_mask_agrees_with_is_speech_frame_by_frame() -> None:
    audio = np.concatenate([tone(-20), noise_floor(), tone(-30), tone(-50)])
    frames = audio.reshape(-1, FRAME_SAMPLES)
    assert speech_mask(audio) == [is_speech(f) for f in frames]
