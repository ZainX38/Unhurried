"""Replay every clip through an endpointer on a simulated clock (ticket 03).

Each WAV is read as it is (no padding: make_data already gives every clip a
500 ms lead-in and an 8 s room-tone tail), cut into 32 ms frames, labelled by
the energy VAD, and fed frame by frame to a fresh endpointer built for that
clip's Slot. The time of the FIRST `END` is recorded; no END means "no end".
Scoring (Cut-off / Wait time / per-group stats) is eval/metrics.py.

Usage:
    uv run python -m eval.run --threshold 700
"""

from __future__ import annotations

import argparse
import csv
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from eval import metrics
from eval.audio import read_wav
from unhurried.endpointer.baseline import Baseline
from unhurried.endpointer.types import Action, Endpointer
from unhurried.vad import FRAME_MS, speech_mask

EVAL_DIR = Path(__file__).parent
DEFAULT_MANIFEST = EVAL_DIR / "data" / "manifest.csv"
RESULTS_DIR = EVAL_DIR / "results"

GROUPS = ("fluent", "stammered", "pauses")
RECORD_COLUMNS = ["file", "group", "line", "slot", "true_end_ms", "end_ms", "outcome", "wait_ms", "reason"]


@dataclass(frozen=True)
class Clip:
    """One manifest row plus its VAD output. `mask[i]` is frame i (time i*32 to (i+1)*32 ms)."""
    file: str
    group: str
    line: str
    slot: str
    true_end_ms: int
    mask: list[bool]


def load_clips(manifest: Path) -> list[Clip]:
    """Read the manifest and run the VAD on every clip once. WAV paths are relative to the manifest."""
    with open(manifest, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [
        Clip(
            file=r["file"],
            group=r["group"],
            line=r["line"],
            slot=r["slot"],
            true_end_ms=int(r["true_end_ms"]),
            mask=speech_mask(read_wav(manifest.parent / r["file"])),
        )
        for r in rows
    ]


def replay(mask: Sequence[bool], endpointer: Endpointer) -> tuple[int | None, str]:
    """Feed frames until the first END. Returns (end_ms, reason), or (None, "") if no END in the clip.

    end_ms is the END of the frame that produced the decision: that is the
    earliest moment a live system could act on it. PROMPT and CONTINUE both
    mean "keep listening", so only END stops the replay.
    """
    for i, is_speech in enumerate(mask):
        decision = endpointer.step(is_speech, FRAME_MS, "")  # no STT yet (ticket 06)
        if decision.action is Action.END:
            return (i + 1) * FRAME_MS, decision.reason
    return None, ""


def run(clips: Iterable[Clip], make_endpointer: Callable[[str], Endpointer]) -> list[dict]:
    """Replay each clip through a fresh endpointer built from its Slot; return one scored record per clip."""
    records = []
    for clip in clips:
        end_ms, reason = replay(clip.mask, make_endpointer(clip.slot))
        outcome, wait_ms = metrics.outcome(end_ms, clip.true_end_ms)
        records.append({
            "file": clip.file, "group": clip.group, "line": clip.line, "slot": clip.slot,
            "true_end_ms": clip.true_end_ms, "end_ms": end_ms,
            "outcome": outcome, "wait_ms": wait_ms, "reason": reason,
        })
    return records


def baseline_factory(threshold_ms: int) -> Callable[[str], Endpointer]:
    """The Baseline ignores the Slot, but takes it so every endpointer is built the same way."""
    return lambda slot: Baseline(threshold_ms)


# --- Output ------------------------------------------------------------------------------

def write_csv(path: Path, records: list[dict], columns: list[str]) -> None:
    """None is written as an empty cell (no END -> empty end_ms; no wait -> empty wait_ms)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def fmt_rate(stats) -> str:
    """'20% (6/30)', or '-' for an empty group."""
    if stats is None or stats.n == 0 or stats.cut_off_rate is None:
        return "-"
    return f"{stats.cut_off_rate:.0%} ({stats.cut_offs}/{stats.n})"


def fmt_ms(value) -> str:
    return "-" if value is None else f"{value:.0f}"


def group_table(stats: dict) -> str:
    """Markdown table: one row per group."""
    lines = [
        "| group | clips | cut-off rate | no end | wait median (ms) | wait p95 (ms) |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for g in GROUPS:
        s = stats.get(g)
        if s is None:
            continue
        lines.append(f"| {g} | {s.n} | {fmt_rate(s)} | {s.no_ends} | {fmt_ms(s.wait_median)} | {fmt_ms(s.wait_p95)} |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--threshold", type=int, default=700, help="Baseline silence threshold in ms")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()

    records = run(load_clips(args.manifest), baseline_factory(args.threshold))
    out = args.out / f"baseline_{args.threshold}_clips.csv"
    write_csv(out, records, RECORD_COLUMNS)

    print(f"Baseline {args.threshold} ms, {len(records)} clips\n")
    print(group_table(metrics.summarize(records)))
    print(f"\nper-clip records -> {out}")


if __name__ == "__main__":
    main()
