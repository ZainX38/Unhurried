"""Tests for the ticket 02 data script (eval/make_data.py) and its WAV helpers.

Most tests build tiny synthetic "recordings" (silence + a tone standing in for
speech) so the expected true ends are known exactly. One test runs on the real
committed recordings to check the counts and the acceptance criteria.
"""

from __future__ import annotations

import csv
import wave
from pathlib import Path

import numpy as np
import pytest

from eval import make_data as md
from eval.audio import SAMPLE_RATE, ms_to_samples, read_wav, write_wav

REAL_RECORDINGS = Path(__file__).parent.parent / "eval" / "data" / "recordings"


# --- helpers -----------------------------------------------------------------------

def tone(ms: int, level: float = 0.1) -> np.ndarray:
    """A 220 Hz tone: loud enough (~-23 dBFS) to count as speech."""
    t = np.arange(ms_to_samples(ms)) / SAMPLE_RATE
    return (level * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def zeros(ms: int) -> np.ndarray:
    return np.zeros(ms_to_samples(ms), dtype=np.float32)


def fake_recordings(root: Path) -> Path:
    """Two pieced lines (A1, C1) and one pause take, laid out like eval/data/recordings/."""
    rec = root / "recordings"
    rec.mkdir()
    # A1: three pieces, each 1 s silence + speech + 1 s silence.
    for i, speech_ms in enumerate([400, 300, 500], start=1):
        write_wav(rec / f"A1_{i}.wav", np.concatenate([zeros(1000), tone(speech_ms), zeros(1000)]))
    write_wav(rec / "C1_1.wav", np.concatenate([zeros(1000), tone(600), zeros(1000)]))
    # P_A2: speech, 1.2 s real pause, speech, 0.8 s pause, speech.
    write_wav(rec / "P_A2.wav", np.concatenate(
        [zeros(1000), tone(300), zeros(1200), tone(300), zeros(800), tone(300), zeros(900)]))
    (rec / "lines.csv").write_text(
        "line,slot,pieces,text,piece_texts\n"
        "A1,account_number,3,My account number is 4 5 2 1 8 8 3 0,My account number is|4 5 2 1|8 8 3 0\n"
        "C1,confirm,1,Yes,Yes\n"
        "P_A2,account_number,1,It's hang on 7 3 0 9 1 1 6 4,It's hang on 7 3 0 9 1 1 6 4\n",
        encoding="utf-8",
    )
    return rec


def build_fake(tmp_path: Path, name: str = "out") -> tuple[Path, list[dict]]:
    rec = tmp_path / "recordings" if (tmp_path / "recordings").exists() else fake_recordings(tmp_path)
    out = tmp_path / name
    return out, md.build(rec, out)


def assert_speech_ends_at(path: Path, true_end_ms: int) -> None:
    """Detected speech end in a written clip is true_end_ms, to within one 10 ms frame.

    Clips are not frame-aligned (gaps are random whole ms), so detection on the
    output can only be exact to the frame.
    """
    sp = md.detect_speech(read_wav(path), path.name)
    assert abs(sp.end - ms_to_samples(true_end_ms)) <= ms_to_samples(md.FRAME_MS)


def notes(row: dict) -> dict[str, int]:
    return {k: int(v) for k, v in (kv.split("=") for kv in row["notes"].split(";"))}


# --- audio helpers ---------------------------------------------------------------------

def test_read_wav_rejects_anything_but_16k_mono_16bit(tmp_path: Path) -> None:
    path = tmp_path / "stereo44k.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44_100)
        w.writeframes(b"\x00\x00" * 2 * 100)
    with pytest.raises(ValueError, match="expected 16000 Hz mono 16-bit"):
        read_wav(path)


def test_write_then_read_round_trips(tmp_path: Path) -> None:
    x = tone(100)
    write_wav(tmp_path / "t.wav", x)
    assert np.allclose(read_wav(tmp_path / "t.wav"), x, atol=1 / 32768)


# --- speech detection --------------------------------------------------------------------

def test_detect_speech_finds_tone_edges() -> None:
    x = np.concatenate([zeros(500), tone(300), zeros(700)])
    sp = md.detect_speech(x, "t")
    assert (sp.start, sp.end) == (ms_to_samples(500), ms_to_samples(800))


def test_detect_speech_raises_on_silence() -> None:
    with pytest.raises(ValueError, match="no speech"):
        md.detect_speech(zeros(1000), "silent.wav")


def test_count_long_pauses() -> None:
    x = np.concatenate([tone(200), zeros(600), tone(200), zeros(300), tone(200)])
    assert md.count_long_pauses(x, md.detect_speech(x, "t")) == 1


# --- groups and true ends --------------------------------------------------------------------

def test_fluent_true_end_is_end_of_last_piece(tmp_path: Path) -> None:
    out, rows = build_fake(tmp_path)
    row = next(r for r in rows if r["file"] == "clips/fluent/A1.wav")
    # lead + 3 pieces (speech + 30 ms margin each side) + 2 gaps, minus the last piece's trailing margin
    gaps_ms = row["true_end_ms"] - (500 + (400 + 300 + 500) + 2 * 60 - 30)
    assert 2 * 150 <= gaps_ms <= 2 * 300
    # Speech really stops at true_end_ms in the written (noisy) clip.
    assert_speech_ends_at(out / row["file"], row["true_end_ms"])


def test_stammered_true_end_is_fluent_plus_block(tmp_path: Path) -> None:
    out, rows = build_fake(tmp_path)
    fluent = next(r for r in rows if r["file"] == "clips/fluent/A1.wav")
    for v in (1, 2, 3):
        row = next(r for r in rows if r["file"] == f"clips/stammered/A1_v{v}.wav")
        n = notes(row)
        assert 60 <= n["burst_ms"] <= 150
        assert 1000 <= n["silence_ms"] <= 3000
        assert row["true_end_ms"] == fluent["true_end_ms"] + n["burst_ms"] + n["silence_ms"]
        assert_speech_ends_at(out / row["file"], row["true_end_ms"])


def test_c1_block_comes_before_any_words(tmp_path: Path) -> None:
    out, rows = build_fake(tmp_path)
    row = next(r for r in rows if r["file"] == "clips/stammered/C1_v1.wav")
    assert notes(row)["block_start_ms"] == md.LEAD_MS
    # The first speech in the clip is the burst, right after the lead.
    sp = md.detect_speech(read_wav(out / row["file"]), "clip")
    assert sp.start == ms_to_samples(md.LEAD_MS)


def test_pause_take_keeps_its_real_pauses(tmp_path: Path) -> None:
    out, rows = build_fake(tmp_path)
    row = next(r for r in rows if r["group"] == "pauses")
    assert row["true_end_ms"] == 1000 + 300 + 1200 + 300 + 800 + 300
    assert row["notes"] == "pauses_over_500ms=2"


def test_every_clip_ends_tail_after_true_end(tmp_path: Path) -> None:
    out, rows = build_fake(tmp_path)
    for row in rows:
        n_samples = len(read_wav(out / row["file"]))
        assert n_samples == ms_to_samples(row["true_end_ms"] + md.TAIL_MS), row["file"]


def test_inserted_silence_is_noise_floor_not_digital_zero(tmp_path: Path) -> None:
    out, rows = build_fake(tmp_path)
    x = read_wav(out / "clips/fluent/A1.wav")
    tail = x[-ms_to_samples(1000):]
    level_db = 20 * np.log10(np.sqrt(np.mean(tail**2)))
    assert np.count_nonzero(tail) > 0.9 * len(tail)
    assert abs(level_db - md.NOISE_FLOOR_DB) < 3


# --- piece ends and texts (oracle transcript, ticket 05) ---------------------------------------

def piece_ends(row: dict) -> list[int]:
    return [int(e) for e in row["piece_ends_ms"].split(";")]


def test_fluent_lists_each_piece_end_and_text(tmp_path: Path) -> None:
    out, rows = build_fake(tmp_path)
    row = next(r for r in rows if r["file"] == "clips/fluent/A1.wav")
    ends = piece_ends(row)
    assert len(ends) == 3
    assert ends == sorted(ends)
    assert ends[-1] == row["true_end_ms"]
    assert row["piece_texts"] == "My account number is|4 5 2 1|8 8 3 0"
    # Piece 1 is 400 ms of speech starting 30 ms (margin) after the 500 ms lead.
    assert ends[0] == md.LEAD_MS + 30 + 400


def test_stammered_piece_ends_shift_by_the_block_after_it(tmp_path: Path) -> None:
    out, rows = build_fake(tmp_path)
    fluent = piece_ends(next(r for r in rows if r["file"] == "clips/fluent/A1.wav"))
    row = next(r for r in rows if r["file"] == "clips/stammered/A1_v1.wav")
    n = notes(row)
    block = n["burst_ms"] + n["silence_ms"]
    # Block goes before piece 2: piece 1 unchanged, pieces 2 and 3 later by burst + silence.
    # The burst is a fragment, not a piece: still 3 ends, 3 texts.
    assert piece_ends(row) == [fluent[0], fluent[1] + block, fluent[2] + block]
    assert row["piece_texts"] == "My account number is|4 5 2 1|8 8 3 0"


def test_pause_takes_have_no_piece_timing(tmp_path: Path) -> None:
    _, rows = build_fake(tmp_path)
    row = next(r for r in rows if r["group"] == "pauses")
    assert (row["piece_ends_ms"], row["piece_texts"]) == ("", "")


def test_piece_texts_must_match_the_piece_count(tmp_path: Path) -> None:
    rec = fake_recordings(tmp_path)
    csv_path = rec / "lines.csv"
    csv_path.write_text(csv_path.read_text(encoding="utf-8").replace("4 5 2 1|8 8 3 0", "4 5 2 1 8 8 3 0"),
                        encoding="utf-8")
    with pytest.raises(ValueError, match="3 piece\\(s\\) but 2 piece text"):
        md.build(rec, tmp_path / "out")


def test_piece_texts_must_join_to_the_line_text(tmp_path: Path) -> None:
    rec = fake_recordings(tmp_path)
    csv_path = rec / "lines.csv"
    csv_path.write_text(csv_path.read_text(encoding="utf-8").replace("|8 8 3 0", "|8 8 3 1"), encoding="utf-8")
    with pytest.raises(ValueError, match="don't join"):
        md.build(rec, tmp_path / "out")


# --- reproducibility and outputs -----------------------------------------------------------

def test_rerun_gives_identical_files(tmp_path: Path) -> None:
    out1, _ = build_fake(tmp_path, "run1")
    out2, _ = build_fake(tmp_path, "run2")
    files1 = sorted(p.relative_to(out1) for p in out1.rglob("*") if p.is_file())
    files2 = sorted(p.relative_to(out2) for p in out2.rglob("*") if p.is_file())
    assert files1 == files2
    for rel in files1:
        assert (out1 / rel).read_bytes() == (out2 / rel).read_bytes(), rel


def test_missing_piece_file_is_reported(tmp_path: Path) -> None:
    rec = fake_recordings(tmp_path)
    (rec / "A1_2.wav").unlink()
    with pytest.raises(FileNotFoundError, match="A1_2.wav"):
        md.build(rec, tmp_path / "out")


@pytest.mark.skipif(not (REAL_RECORDINGS / "lines.csv").exists(), reason="real recordings not present")
def test_real_recordings_build_the_full_set(tmp_path: Path) -> None:
    rows = md.build(REAL_RECORDINGS, tmp_path)
    groups = [r["group"] for r in rows]
    assert (groups.count("fluent"), groups.count("stammered"), groups.count("pauses")) == (10, 30, 4)
    with open(tmp_path / "manifest.csv", newline="", encoding="utf-8") as f:
        manifest = list(csv.DictReader(f))
    assert list(manifest[0]) == md.MANIFEST_COLUMNS
    assert len(manifest) == 44
    for r in manifest:
        if r["group"] == "pauses":
            assert r["piece_ends_ms"] == ""
        else:
            assert int(r["piece_ends_ms"].split(";")[-1]) == int(r["true_end_ms"]), r["file"]
            assert " ".join(r["piece_texts"].split("|")) == r["transcript"], r["file"]
    assert sorted(p.name for p in (tmp_path / "demo").iterdir()) == [
        "A1_fluent.wav", "A1_stammered.wav", "C1.wav", "C2.wav", "D1.wav", "P_A2.wav",
        "R1.wav", "R2.wav", "manifest.csv"]
