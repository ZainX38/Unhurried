import csv
from pathlib import Path

import numpy as np
from eval.audio import write_wav
from eval.run import Clip, baseline_factory, load_clips, replay, run
from unhurried.endpointer.baseline import Baseline
from unhurried.vad import FRAME_MS, FRAME_SAMPLES

S, Q = True, False  # speech / quiet frame


def frames(*runs: tuple[bool, int]) -> list[bool]:
    """frames((Q, 16), (S, 20)) -> 16 quiet frames then 20 speech frames."""
    return [value for value, n in runs for _ in range(n)]


def ms(n_frames: int) -> int:
    return n_frames * FRAME_MS


# --- replay: hand-made masks (test fixtures only) ----------------------------------------

def test_block_longer_than_threshold_ends_inside_the_block() -> None:
    # 700 ms Baseline, ~1 s Block between two bursts of speech.
    mask = frames((Q, 16), (S, 20), (Q, 32), (S, 20), (Q, 250))
    true_end_ms = ms(16 + 20 + 32 + 20)
    end_ms, reason = replay(mask, Baseline(700))
    # 22nd silent frame of the Block = 704 ms of silence.
    assert end_ms == ms(16 + 20 + 22)
    assert end_ms < true_end_ms
    assert "704ms" in reason


def test_no_end_inside_the_clip_returns_none() -> None:
    mask = frames((Q, 16), (S, 40), (Q, 10))  # only 320 ms of silence after speech
    assert replay(mask, Baseline(700)) == (None, "")


def test_silence_only_never_ends() -> None:
    assert replay(frames((Q, 300)), Baseline(300)) == (None, "")


def test_first_end_is_returned_not_a_later_one() -> None:
    mask = frames((S, 5), (Q, 100))
    end_ms, _ = replay(mask, Baseline(320))  # 10 silent frames = 320 ms
    assert end_ms == ms(5 + 10)


def test_run_scores_the_block_clip_as_a_cut_off() -> None:
    mask = frames((Q, 16), (S, 20), (Q, 32), (S, 20), (Q, 250))
    clip = Clip("x.wav", "stammered", "A1", "account_number", ms(16 + 20 + 32 + 20), mask)
    [record] = run([clip], baseline_factory(700))
    assert record["outcome"] == "cut_off"


def test_run_scores_a_fluent_clip_with_its_wait() -> None:
    mask = frames((Q, 16), (S, 60), (Q, 250))
    clip = Clip("x.wav", "fluent", "A1", "account_number", ms(16 + 60), mask)
    [record] = run([clip], baseline_factory(700))
    assert record["outcome"] == "ended"
    assert record["end_ms"] == ms(16 + 60 + 22)
    assert record["wait_ms"] == ms(22)


def test_each_clip_gets_a_fresh_endpointer_built_from_its_slot() -> None:
    built: list[str] = []

    def factory(slot: str) -> Baseline:
        built.append(slot)
        return Baseline(700)

    mask = frames((S, 5), (Q, 30))
    clips = [Clip(f"{s}.wav", "fluent", "L", s, ms(5), mask) for s in ("account_number", "date_of_birth")]
    records = run(clips, factory)
    assert built == ["account_number", "date_of_birth"]
    # Same result for both: no state carried over from the first clip.
    assert records[0]["end_ms"] == records[1]["end_ms"]


# --- load_clips: a tiny real WAV + manifest ----------------------------------------------

def write_tiny_manifest(root: Path) -> Path:
    """One clip: 16 quiet frames, 20 frames of a loud tone, then 250 quiet frames (noise floor)."""
    rng = np.random.default_rng(0)
    t = np.arange(20 * FRAME_SAMPLES) / 16_000
    speech = (0.1 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)
    audio = np.concatenate([np.zeros(16 * FRAME_SAMPLES), speech, np.zeros(250 * FRAME_SAMPLES)]).astype(np.float32)
    audio += rng.normal(0.0, 1e-3, len(audio)).astype(np.float32)  # -60 dBFS floor
    write_wav(root / "clips" / "fluent" / "T1.wav", audio)

    manifest = root / "manifest.csv"
    with open(manifest, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["file", "group", "line", "slot", "transcript", "true_end_ms", "notes"])
        w.writerow(["clips/fluent/T1.wav", "fluent", "T1", "account_number", "hi", ms(36), ""])
    return manifest


def test_load_clips_reads_the_manifest_and_runs_the_vad(tmp_path: Path) -> None:
    [clip] = load_clips(write_tiny_manifest(tmp_path))
    assert (clip.file, clip.group, clip.slot, clip.true_end_ms) == ("clips/fluent/T1.wav", "fluent", "account_number", ms(36))
    assert clip.mask == frames((Q, 16), (S, 20), (Q, 250))  # no padding added: exactly the WAV's frames
