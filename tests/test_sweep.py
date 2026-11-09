import csv
from pathlib import Path

from eval.run import Clip, load_clips
from eval.sweep import curve, meets_targets, summary_table, sweep, write_outputs
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
