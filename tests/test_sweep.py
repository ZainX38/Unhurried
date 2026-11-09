import csv
from dataclasses import replace
from pathlib import Path

from eval.run import Clip, load_clips
from eval.sweep import (
    curve, meets_targets, misses_table, patient_points, summary_table, sweep, vosk_waits_longer_table, write_outputs,
)
from tests.test_run import frames, ms, write_tiny_manifest

S, Q = True, False


def test_cut_off_rate_falls_and_wait_rises_as_the_threshold_grows() -> None:
    fluent = Clip("f.wav", "fluent", "A1", "account_number", ms(16 + 60), frames((Q, 16), (S, 60), (Q, 250)))
    # ~1 s Block: cut off below ~1000 ms, survives above it.
    stammered = Clip("s.wav", "stammered", "A1", "account_number", ms(16 + 20 + 32 + 20),
                     frames((Q, 16), (S, 20), (Q, 32), (S, 20), (Q, 250)))
    points = sweep([fluent, stammered], [700, 1500])

    assert [p.threshold_ms for p in points] == [700, 1500]
    assert [p.stats["stammered"].cut_offs for p in points] == [1, 0]
    [(t1, wait1, rate1), (t2, wait2, rate2)] = curve(points)
    assert wait1 < wait2 and rate1 > rate2


def test_writes_table_per_clip_csv_and_chart(tmp_path: Path) -> None:
    points = sweep(load_clips(write_tiny_manifest(tmp_path)), [300, 700])
    out = tmp_path / "results"
    write_outputs(points, out)

    assert "| 300 |" in (out / "sweep.md").read_text(encoding="utf-8")
    with open(out / "sweep_clips.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["threshold_ms"] for r in rows] == ["300", "700"]
    assert (out / "sweep.png").stat().st_size > 0
    assert (out / "cutoff_by_threshold.png").stat().st_size > 0


def test_summary_marks_a_threshold_only_when_both_targets_are_met() -> None:
    fluent = Clip("f.wav", "fluent", "A1", "account_number", ms(16 + 60), frames((Q, 16), (S, 60), (Q, 250)))
    stammered = Clip("s.wav", "stammered", "A1", "account_number", ms(16 + 20 + 32 + 20),
                     frames((Q, 16), (S, 20), (Q, 32), (S, 20), (Q, 250)))
    # 700: fluent waits ~704 ms but the ~1 s Block is cut off. 1500: no cut-off but fluent waits ~1.5 s.
    points = sweep([fluent, stammered], [700, 1500])
    assert [meets_targets(p) for p in points] == [False, False]
    assert summary_table(points).count("❌") == 2

    # A short (320 ms) Block survives a 700 ms threshold and fluent waits ~704 ms: both targets met.
    short_block = Clip("s2.wav", "stammered", "A1", "account_number", ms(16 + 20 + 10 + 20),
                       frames((Q, 16), (S, 20), (Q, 10), (S, 20), (Q, 250)))
    [ok] = sweep([fluent, short_block], [700])
    assert meets_targets(ok) is True
    assert "✅" in summary_table([ok])

    # No stammered clips at all: the target can't be checked, so it is never "met".
    assert meets_targets(sweep([fluent], [700])[0]) is False


# --- Patient on the sweep (ticket 05) ------------------------------------------------------

def stammered_account_clip() -> Clip:
    """Account clip with a ~1 s Block after "my account number is": cut off by a 700 ms Baseline."""
    mask = frames((Q, 16), (S, 20), (Q, 32), (S, 20), (Q, 250))
    end = ms(16 + 20 + 32 + 20)
    pieces = ((ms(16 + 20), "My account number is"), (end, "4 5 2 7 3 6 1 0"))
    return Clip("s.wav", "stammered", "A1", "account_number", end, mask, pieces)


def fluent_account_clip() -> Clip:
    end = ms(16 + 60)
    return Clip("f.wav", "fluent", "A1", "account_number", end, frames((Q, 16), (S, 60), (Q, 250)),
                ((end, "my account number is 4 5 2 7 3 6 1 0"),))


def test_patient_survives_the_block_that_cuts_off_the_baseline() -> None:
    clips = [fluent_account_clip(), stammered_account_clip()]
    [baseline] = sweep(clips, [700])
    [patient] = patient_points(clips, [700])
    assert baseline.stats["stammered"].cut_offs == 1
    assert patient.stats["stammered"].cut_offs == 0
    assert patient.stats["fluent"].wait_median == baseline.stats["fluent"].wait_median  # same start
    assert meets_targets(patient) is True


def test_complete_ms_400_waits_less_on_a_complete_answer() -> None:
    [p700, p400] = patient_points([fluent_account_clip()], [700, 400])
    assert p400.stats["fluent"].wait_median < p700.stats["fluent"].wait_median


def test_writes_results_md_and_patient_csv_with_patients(tmp_path: Path) -> None:
    clips = [fluent_account_clip(), stammered_account_clip()]
    out = tmp_path / "results"
    write_outputs(sweep(clips, [700, 3000]), out, patient_points(clips, [700, 400]))
    md = (out / "results.md").read_text(encoding="utf-8")
    assert "| Baseline 700 ms |" in md
    assert "Baseline 3000 ms (first to meet the stammered target)" in md
    assert "**Patient, complete 400 ms**" in md
    assert "## Caveats" in md
    with open(out / "patient_clips.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["complete_ms"] for r in rows] == ["700", "700", "400", "400"]


def test_misses_table_lists_each_miss_once_with_its_settings() -> None:
    clip = Clip("r.wav", "stammered", "R2", "reason", ms(16 + 20 + 32 + 20),
                frames((Q, 16), (S, 20), (Q, 32), (S, 20), (Q, 250)),
                ((ms(16 + 20), "I want to set up"), (ms(16 + 20 + 32 + 20), "a payment plan")))
    table = misses_table(patient_points([clip], [700, 400]))
    assert table.count("r.wav") == 1
    assert "| cut_off | 700, 400 |" in table
    assert "free text" in table


def test_without_patients_no_results_md(tmp_path: Path) -> None:
    write_outputs(sweep([fluent_account_clip()], [700]), tmp_path)
    assert not (tmp_path / "results.md").exists()


# --- Vosk side by side (ticket 06) -----------------------------------------------------------

def with_vosk_text(clip: Clip, text: str) -> Clip:
    """The same clip, with a fixed "Vosk" transcript from the first frame on."""
    return replace(clip, transcripts=tuple(text for _ in clip.mask))


def test_misheard_digit_makes_the_patient_wait_where_the_baseline_ended() -> None:
    fluent = fluent_account_clip()
    # "ford" is not a digit or homophone, so only 7/8 digits are heard.
    misheard = with_vosk_text(fluent, "my account number is ford five two seven three six one oh")
    points = sweep([fluent], [700])
    patients = patient_points([fluent], [700]) + patient_points([misheard], [700], stt="vosk")
    table = vosk_waits_longer_table(points, patients, [misheard])
    assert table.count("f.wav") == 1
    assert "never ended; words INCOMPLETE: 7/8 digits" in table
    assert "PROMPT at" in table
    assert "`my account number is ford five two seven three six one oh`" in table


def test_vosk_heard_right_is_not_listed() -> None:
    fluent = fluent_account_clip()
    heard = with_vosk_text(fluent, "my account number is four five two seven three six one zero")
    patients = patient_points([fluent], [700]) + patient_points([heard], [700], stt="vosk")
    assert vosk_waits_longer_table(sweep([fluent], [700]), patients, [heard]) == "None."


def test_results_md_shows_oracle_and_vosk_side_by_side(tmp_path: Path) -> None:
    oracle = [fluent_account_clip(), stammered_account_clip()]
    vosk = [with_vosk_text(c, "my account number is four five two seven three six one zero") for c in oracle]
    patients = patient_points(oracle, [700]) + patient_points(vosk, [700], stt="vosk")
    out = tmp_path / "results"
    write_outputs(sweep(oracle, [700, 3000]), out, patients, vosk)
    md = (out / "results.md").read_text(encoding="utf-8")
    assert "**Patient (oracle transcripts), complete 700 ms**" in md
    assert "**Patient (Vosk transcripts), complete 700 ms**" in md
    assert "## Fluent clips where Vosk made the Patient wait longer than the Baseline" in md
    assert "--stt vosk" in md
    with open(out / "patient_clips.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["stt"] for r in rows] == ["oracle", "oracle", "vosk", "vosk"]
