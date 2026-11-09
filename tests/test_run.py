import csv
from pathlib import Path

import numpy as np
import pytest
from eval.audio import write_wav
from eval.run import (
    ORACLE_DELAY_MS, Clip, baseline_factory, load_clips, oracle_transcripts, parse_pieces, patient_factory,
    replay, run, stt_style, transcribe,
)
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


class Recorder(Baseline):
    """A 700 ms Baseline that remembers its reset() Slot and every transcript it was given."""

    def __init__(self) -> None:
        self.slots: list[str] = []
        self.transcripts: list[str | None] = []
        super().__init__(700)

    def reset(self, expected_slot: str = "") -> None:
        self.slots.append(expected_slot)
        super().reset(expected_slot)

    def step(self, is_speech: bool, frame_ms: int, transcript: str | None):
        self.transcripts.append(transcript)
        return super().step(is_speech, frame_ms, transcript)


def test_each_clip_gets_a_fresh_endpointer_reset_to_its_slot() -> None:
    built: list[Recorder] = []

    def factory() -> Recorder:
        built.append(Recorder())
        return built[-1]

    mask = frames((S, 5), (Q, 30))
    clips = [Clip(f"{s}.wav", "fluent", "L", s, ms(5), mask) for s in ("account_number", "date_of_birth")]
    records = run(clips, factory)
    assert len(built) == 2
    # [""] is the constructor's own reset(); then the harness resets to the clip's Slot.
    assert [r.slots[1:] for r in built] == [["account_number"], ["date_of_birth"]]
    # Same result for both: no state carried over from the first clip.
    assert records[0]["end_ms"] == records[1]["end_ms"]


# --- oracle transcript ---------------------------------------------------------------------

def test_stt_style_lowercases_and_drops_punctuation_but_keeps_apostrophes() -> None:
    assert stt_style("Yes, that's right.") == "yes that's right"
    assert stt_style("No,  it's 4 5") == "no it's 4 5"
    assert stt_style("4-") == "4-"  # a cut-off word keeps its hyphen


def test_piece_text_appears_oracle_delay_after_its_speech_ends() -> None:
    pieces = ((ms(10), "My account number is"), (ms(30), "4 5 2 1"))
    transcripts = oracle_transcripts(60, pieces)
    first_reveal = (ms(10) + ORACLE_DELAY_MS) // FRAME_MS  # 300 ms is not a whole frame: rounds up
    assert transcripts[first_reveal - 2] == ""  # the last frame that ends before 620 ms
    assert transcripts[first_reveal - 1] == ""
    assert transcripts[first_reveal] == "my account number is"
    assert transcripts[-1] == "my account number is 4 5 2 1"


def test_reveal_frame_is_the_first_whose_end_reaches_the_reveal_time() -> None:
    # Piece ends at 320 ms -> text out at 620 ms. Frame 19 ends at 640 ms, frame 18 at 608 ms.
    transcripts = oracle_transcripts(25, ((320, "yes"),))
    assert transcripts[18] == ""
    assert transcripts[19] == "yes"


def test_clip_without_pieces_is_timing_only() -> None:
    assert oracle_transcripts(3, None) == [None, None, None]


def test_replay_feeds_the_oracle_transcript_frame_by_frame() -> None:
    mask = frames((Q, 5), (S, 10), (Q, 30))
    r = Recorder()
    replay(mask, r, pieces=((ms(15), "Yes."),))
    reveal = (ms(15) + ORACLE_DELAY_MS + FRAME_MS - 1) // FRAME_MS  # frames until text is out
    assert r.transcripts[: reveal - 1] == [""] * (reveal - 1)
    assert r.transcripts[reveal - 1] == "yes"


def test_replay_without_pieces_passes_none() -> None:
    r = Recorder()
    replay(frames((S, 2), (Q, 3)), r)
    assert r.transcripts == [None] * 5


def test_parse_pieces_reads_the_manifest_columns() -> None:
    assert parse_pieces("100;250", "it's|4 5") == ((100, "it's"), (250, "4 5"))
    assert parse_pieces("", "") is None
    assert parse_pieces(None, None) is None  # older manifest without the columns
    with pytest.raises(ValueError, match="2 piece ends but 1"):
        parse_pieces("100;250", "it's")


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


def test_patient_factory_builds_a_fresh_patient_with_its_settings() -> None:
    factory = patient_factory(complete_ms=400)
    a, b = factory(), factory()
    assert a is not b
    assert (a.base_ms, a.complete_ms) == (700, 400)


# --- real STT transcripts (ticket 06) -------------------------------------------------------

class CountingSTT:
    """Fake STT: its transcript says how many frames it has been fed since reset()."""

    def __init__(self) -> None:
        self.resets = 0
        self.fed = 0

    def reset(self) -> None:
        self.resets += 1
        self.fed = 0

    def feed(self, frame: np.ndarray) -> None:
        assert len(frame) == FRAME_SAMPLES
        self.fed += 1

    def transcript(self) -> str:
        return f"frame {self.fed}"


def test_transcribe_gives_the_transcript_after_each_frame() -> None:
    stt = CountingSTT()
    samples = np.zeros(3 * FRAME_SAMPLES + 100, dtype=np.float32)  # trailing partial frame is dropped
    assert transcribe(samples, stt) == ("frame 1", "frame 2", "frame 3")
    assert stt.resets == 1


def test_load_clips_with_stt_lines_transcripts_up_with_the_mask(tmp_path: Path) -> None:
    [clip] = load_clips(write_tiny_manifest(tmp_path), CountingSTT())
    assert len(clip.transcripts) == len(clip.mask)
    assert clip.transcripts[0] == "frame 1"
    assert load_clips(write_tiny_manifest(tmp_path))[0].transcripts is None  # oracle: no STT run


def test_stt_transcripts_win_over_the_oracle_pieces() -> None:
    mask = frames((S, 2), (Q, 3))
    clip = Clip("x.wav", "fluent", "L", "reason", ms(2), mask, pieces=((ms(1), "oracle text"),),
                transcripts=("a", "b", "c", "d", "e"))
    assert list(clip.frame_transcripts()) == ["a", "b", "c", "d", "e"]
    r = Recorder()
    replay(mask, r, transcripts=clip.frame_transcripts())
    assert r.transcripts == ["a", "b", "c", "d", "e"]


def test_replay_rejects_transcripts_of_the_wrong_length() -> None:
    with pytest.raises(ValueError, match="2 transcripts for 3 frames"):
        replay(frames((S, 3)), Baseline(700), transcripts=["a", "b"])


def test_baseline_records_do_not_depend_on_the_transcripts() -> None:
    mask = frames((Q, 16), (S, 20), (Q, 32), (S, 20), (Q, 250))
    oracle = Clip("x.wav", "stammered", "A1", "account_number", ms(88), mask,
                  pieces=((ms(36), "my account number is"), (ms(88), "4 5 2 1 8 8 3 0")))
    words = Clip(*[getattr(oracle, f) for f in ("file", "group", "line", "slot", "true_end_ms", "mask")],
                 transcripts=tuple("for to won" for _ in mask))
    for t in (300, 700, 3000):
        assert run([oracle], baseline_factory(t)) == run([words], baseline_factory(t))
