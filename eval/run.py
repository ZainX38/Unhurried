"""Replay every clip through an endpointer on a simulated clock (ticket 03).

Each WAV is read as it is (no padding: make_data already gives every clip a
500 ms lead-in and an 8 s room-tone tail), cut into 32 ms frames, labelled by
the energy VAD, and fed frame by frame to a fresh endpointer that has been
`reset()` to that clip's Slot. The time of the FIRST `END` is recorded; no END
means "no end". Scoring (Cut-off / Wait time / per-group stats) is eval/metrics.py.

Transcripts come from one of two sources (`--stt`):

- oracle (default): for clips with piece timing (fluent, stammered), each piece's
  text is revealed ORACLE_DELAY_MS after that piece's speech ends, lowercased and
  without punctuation like Vosk output. Clips without piece timing (the P_* takes)
  get transcript=None: timing-only.
- vosk (ticket 06): every clip, P_* included, is streamed through Vosk in the same
  32 ms frames the VAD sees; frame i gets the transcript after Vosk has heard frame i.
  Each clip is transcribed once and reused by every endpointer setting.

Usage:
    uv run python -m eval.run --threshold 700
    uv run python -m eval.run --endpointer patient --complete-ms 400
    uv run python -m eval.run --endpointer patient --stt vosk
"""

from __future__ import annotations

import argparse
import csv
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from eval import metrics
from eval.audio import read_wav
from unhurried.endpointer.baseline import Baseline
from unhurried.endpointer.patient import Patient
from unhurried.endpointer.types import Action, Endpointer
from unhurried.stt import STT
from unhurried.vad import FRAME_MS, FRAME_SAMPLES, speech_mask

EVAL_DIR = Path(__file__).parent
DEFAULT_MANIFEST = EVAL_DIR / "data" / "manifest.csv"
RESULTS_DIR = EVAL_DIR / "results"

GROUPS = ("fluent", "stammered", "pauses")
RECORD_COLUMNS = ["file", "group", "line", "slot", "true_end_ms", "end_ms", "outcome", "wait_ms", "reason"]

# How long after a piece's speech ends its text appears. A guess at streaming STT latency;
# real Vosk latency is measured in ticket 06.
ORACLE_DELAY_MS = 300

Pieces = tuple[tuple[int, str], ...]  # (speech end in ms, text) per piece, in order


@dataclass(frozen=True)
class Clip:
    """One manifest row plus its VAD output. `mask[i]` is frame i (time i*32 to (i+1)*32 ms).

    `transcripts` (real STT, one per frame) wins over `pieces` (the oracle). With neither,
    the clip runs timing-only (transcript=None).
    """
    file: str
    group: str
    line: str
    slot: str
    true_end_ms: int
    mask: list[bool]
    pieces: Pieces | None = None
    transcripts: tuple[str, ...] | None = None

    def frame_transcripts(self) -> Sequence[str | None]:
        """The transcript the endpointer sees at each frame."""
        if self.transcripts is not None:
            return self.transcripts
        return oracle_transcripts(len(self.mask), self.pieces)


def parse_pieces(ends: str | None, texts: str | None) -> Pieces | None:
    """Manifest columns "1830;3900;7671" and "a|b|c" -> ((1830, "a"), ...). Empty or missing -> None."""
    if not ends or not texts:
        return None
    end_list = [int(e) for e in ends.split(";")]
    text_list = texts.split("|")
    if len(end_list) != len(text_list):
        raise ValueError(f"{len(end_list)} piece ends but {len(text_list)} piece texts: {ends!r} / {texts!r}")
    return tuple(zip(end_list, text_list))


def transcribe(samples: np.ndarray, stt: STT) -> tuple[str, ...]:
    """Stream one clip through the STT in VAD-sized frames: entry i is the transcript after frame i.
    Same framing as speech_mask (a trailing partial frame is dropped), so it lines up with the mask."""
    stt.reset()
    out = []
    for i in range(len(samples) // FRAME_SAMPLES):
        stt.feed(samples[i * FRAME_SAMPLES : (i + 1) * FRAME_SAMPLES])
        out.append(stt.transcript())
    return tuple(out)


def load_clips(manifest: Path, stt: STT | None = None) -> list[Clip]:
    """Read the manifest and run the VAD (and the STT, if given) on every clip once.
    WAV paths are relative to the manifest. The oracle pieces are kept either way."""
    with open(manifest, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    clips = []
    for r in rows:
        samples = read_wav(manifest.parent / r["file"])
        clips.append(Clip(
            file=r["file"],
            group=r["group"],
            line=r["line"],
            slot=r["slot"],
            true_end_ms=int(r["true_end_ms"]),
            mask=speech_mask(samples),
            pieces=parse_pieces(r.get("piece_ends_ms"), r.get("piece_texts")),
            transcripts=transcribe(samples, stt) if stt is not None else None,
        ))
    return clips


def stt_style(text: str) -> str:
    """Make written text look like Vosk output: lowercase, no punctuation, single spaces.
    Apostrophes stay ("it's" is a word completeness knows)."""
    kept = "".join(ch for ch in text.lower() if ch.isalnum() or ch in " '-")
    return " ".join(kept.split())


def oracle_transcripts(n_frames: int, pieces: Pieces | None) -> list[str | None]:
    """The transcript at each frame: every piece whose text is out by the end of that frame
    (speech end + ORACLE_DELAY_MS), joined. None for every frame when there are no pieces."""
    if pieces is None:
        return [None] * n_frames
    out = []
    for i in range(n_frames):
        now = (i + 1) * FRAME_MS
        out.append(" ".join(stt_style(text) for end, text in pieces if end + ORACLE_DELAY_MS <= now))
    return out


def replay(mask: Sequence[bool], endpointer: Endpointer, pieces: Pieces | None = None,
           transcripts: Sequence[str | None] | None = None) -> tuple[int | None, str]:
    """Feed frames until the first END. Returns (end_ms, reason), or (None, "") if no END in the clip.

    `transcripts` (one per frame, from real STT) wins over `pieces` (the oracle).

    end_ms is the END of the frame that produced the decision: that is the
    earliest moment a live system could act on it. PROMPT and CONTINUE both
    mean "keep listening", so only END stops the replay.
    """
    if transcripts is None:
        transcripts = oracle_transcripts(len(mask), pieces)
    if len(transcripts) != len(mask):
        raise ValueError(f"{len(transcripts)} transcripts for {len(mask)} frames")
    for i, is_speech in enumerate(mask):
        decision = endpointer.step(is_speech, FRAME_MS, transcripts[i])
        if decision.action is Action.END:
            return (i + 1) * FRAME_MS, decision.reason
    return None, ""


def run(clips: Iterable[Clip], make_endpointer: Callable[[], Endpointer]) -> list[dict]:
    """Replay each clip through a fresh endpointer, reset to the clip's Slot; one scored record per clip.

    Fresh per clip because every clip is a different caller: no call memory carries over.
    """
    records = []
    for clip in clips:
        endpointer = make_endpointer()
        endpointer.reset(clip.slot)
        end_ms, reason = replay(clip.mask, endpointer, transcripts=clip.frame_transcripts())
        outcome, wait_ms = metrics.outcome(end_ms, clip.true_end_ms)
        records.append({
            "file": clip.file, "group": clip.group, "line": clip.line, "slot": clip.slot,
            "true_end_ms": clip.true_end_ms, "end_ms": end_ms,
            "outcome": outcome, "wait_ms": wait_ms, "reason": reason,
        })
    return records


def baseline_factory(threshold_ms: int) -> Callable[[], Endpointer]:
    return lambda: Baseline(threshold_ms)


def patient_factory(complete_ms: int = 700, base_ms: int = 700) -> Callable[[], Endpointer]:
    return lambda: Patient(base_ms=base_ms, complete_ms=complete_ms)


def make_stt(name: str) -> STT | None:
    """--stt value -> STT instance. None for the oracle (it needs no audio)."""
    if name == "oracle":
        return None
    from unhurried.stt import VoskSTT
    return VoskSTT()


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
    parser.add_argument("--endpointer", choices=["baseline", "patient"], default="baseline")
    parser.add_argument("--threshold", type=int, default=700, help="Baseline silence threshold in ms")
    parser.add_argument("--complete-ms", type=int, default=700,
                        help="Patient: silence that ends a COMPLETE answer, in ms")
    parser.add_argument("--stt", choices=["oracle", "vosk"], default="oracle",
                        help="transcript source: the manifest's piece timing, or real Vosk transcripts")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()

    if args.endpointer == "patient":
        factory, name, label = (patient_factory(args.complete_ms), f"patient_{args.complete_ms}",
                                f"Patient (complete {args.complete_ms} ms)")
    else:
        factory, name, label = baseline_factory(args.threshold), f"baseline_{args.threshold}", f"Baseline {args.threshold} ms"
    if args.stt == "vosk":
        name, label = f"{name}_vosk", f"{label}, Vosk transcripts"

    records = run(load_clips(args.manifest, make_stt(args.stt)), factory)
    out = args.out / f"{name}_clips.csv"
    write_csv(out, records, RECORD_COLUMNS)

    print(f"{label}, {len(records)} clips\n")
    print(group_table(metrics.summarize(records)))
    print(f"\nper-clip records -> {out}")


if __name__ == "__main__":
    main()
