"""Build the Recorded Turn test clips (ticket 02) from the recordings.

Input:  eval/data/recordings/   converted 16 kHz mono WAVs + lines.csv
Output: eval/data/clips/<group>/*.wav, eval/data/manifest.csv, eval/data/demo/

Three groups, each clip with an exact `true_end_ms` (where the answer really ends):

- fluent     pieces of a line trimmed and joined with short natural gaps
- stammered  the fluent join with a Block (short burst + long silence) inserted
             before the digit/date piece, 3 variants per line
- pauses     the single-take P_* recordings with their real thinking pauses

Fluent and stammered rows also list where each piece's speech ends and what
was said in it (`piece_ends_ms`, `piece_texts`), so the harness can reveal an
"oracle transcript" piece by piece (ticket 05). P_* rows leave both empty:
there is no piece timing inside a single take, so they run timing-only.

The full design (and why) is in issues/unhurried-demo/issues/02-test-data.md,
under "Design notes". Everything random comes from a fixed seed, so running this
twice gives byte-identical files.

Usage:
    uv run python -m eval.make_data
"""

from __future__ import annotations

import argparse
import csv
import random
import shutil
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from eval.audio import SAMPLES_PER_MS, ms_to_samples, read_wav, samples_to_ms, write_wav

# --- Constants (all from the design notes) -----------------------------------

SEED = 2026

FRAME_MS = 10              # speech detection works on 10 ms frames
SPEECH_THRESHOLD_DB = -45  # frame RMS above this (dBFS) counts as speech; speech peaks ~-25
TRIM_MARGIN_MS = 30        # keep this much audio either side of detected speech
FADE_MS = 10               # fade in/out on every placed segment so cuts don't click

LEAD_MS = 500              # silence before the first word (fluent + stammered clips)
TAIL_MS = 8000             # clip ends this long after true_end_ms: Ceiling (5 s) + PROMPT (6 s) + slack
NOISE_FLOOR_DB = -60       # RMS of the Gaussian noise added over every whole clip

GAP_MS = (150, 300)        # fluent gap between pieces (inclusive range)
BURST_MS = (60, 150)       # Block burst: first part of the blocked piece
BLOCK_SILENCE_MS = (1000, 3000)
VARIANTS = 3               # stammered variants per line

# Lines whose Block goes at the very start (before piece 1) instead of before piece 2.
# C1 is a single piece and deliberately tests a Block before any words.
BLOCK_AT_START = {"C1"}

DATA_DIR = Path(__file__).parent / "data"
MANIFEST_COLUMNS = ["file", "group", "line", "slot", "transcript", "true_end_ms",
                    "piece_ends_ms", "piece_texts", "notes"]
PIECE_SEP = "|"            # separates piece texts in lines.csv and the manifest
PIECE_END_SEP = ";"        # separates piece end times in the manifest

# Demo samples committed for the ticket 08 "sample caller": (source clip, demo file name).
DEMO_CLIPS = [
    ("clips/fluent/A1.wav", "A1_fluent.wav"),
    ("clips/stammered/A1_v1.wav", "A1_stammered.wav"),
    ("clips/pauses/P_A2.wav", "P_A2.wav"),
    # The rest of a sample Call: yes, date of birth, reason (R1 and R2 both map to billing).
    ("clips/fluent/C1.wav", "C1.wav"),
    ("clips/fluent/D1.wav", "D1.wav"),
    ("clips/fluent/R1.wav", "R1.wav"),
    ("clips/fluent/R2.wav", "R2.wav"),
]


# --- Data types ---------------------------------------------------------------

@dataclass(frozen=True)
class Line:
    """One row of lines.csv."""
    line: str        # e.g. "A1" or "P_A2"
    slot: str        # account_number | date_of_birth | reason | confirm
    pieces: int      # number of piece files (1 for P_* takes)
    text: str        # what was said, without pause marks
    piece_texts: tuple[str, ...]  # what was said in each piece; joined with spaces they give `text`


@dataclass(frozen=True)
class Speech:
    """Where speech is inside a recording, in samples (end is exclusive)."""
    start: int
    end: int


# --- Speech detection -----------------------------------------------------------

def frame_db(x: np.ndarray) -> np.ndarray:
    """RMS level of each 10 ms frame in dBFS. A trailing partial frame is ignored."""
    n = len(x) // ms_to_samples(FRAME_MS)
    frames = x[: n * ms_to_samples(FRAME_MS)].reshape(n, -1)
    return 10 * np.log10(np.mean(frames**2, axis=1) + 1e-12)


def speech_mask(x: np.ndarray) -> np.ndarray:
    """True for every 10 ms frame that counts as speech."""
    return frame_db(x) > SPEECH_THRESHOLD_DB


def detect_speech(x: np.ndarray, name: str) -> Speech:
    """First and last speech frame, snapped to frame boundaries (so lengths stay whole ms)."""
    idx = np.flatnonzero(speech_mask(x))
    if len(idx) == 0:
        raise ValueError(f"{name}: no speech found (nothing above {SPEECH_THRESHOLD_DB} dBFS)")
    frame = ms_to_samples(FRAME_MS)
    return Speech(start=int(idx[0]) * frame, end=(int(idx[-1]) + 1) * frame)


def count_long_pauses(x: np.ndarray, speech: Speech, min_ms: int = 500) -> int:
    """Number of non-speech runs of at least `min_ms` between the first and last word."""
    frame = ms_to_samples(FRAME_MS)
    inside = speech_mask(x)[speech.start // frame : speech.end // frame]
    pauses, run = 0, 0
    for is_speech in inside:
        if is_speech:
            pauses += run * FRAME_MS >= min_ms
            run = 0
        else:
            run += 1
    return pauses


# --- A trimmed piece -------------------------------------------------------------

@dataclass(frozen=True)
class Piece:
    """A piece trimmed to its speech plus margin, remembering where the speech sits inside it."""
    audio: np.ndarray
    speech_start: int   # sample index of speech onset inside `audio`
    speech_end: int     # sample index just after the last speech frame inside `audio`


def trim(x: np.ndarray, name: str) -> Piece:
    """Cut a recording down to its speech, keeping TRIM_MARGIN_MS either side."""
    sp = detect_speech(x, name)
    margin = ms_to_samples(TRIM_MARGIN_MS)
    lo = max(0, sp.start - margin)
    hi = min(len(x), sp.end + margin)
    # lo/hi are frame-aligned except at the file edges; pad with zeros so lengths stay whole ms.
    audio = x[lo:hi]
    pad = (-len(audio)) % SAMPLES_PER_MS
    audio = np.concatenate([audio, np.zeros(pad, dtype=np.float32)])
    return Piece(audio=audio, speech_start=sp.start - lo, speech_end=sp.end - lo)


# --- Building a clip ---------------------------------------------------------------

def faded(seg: np.ndarray) -> np.ndarray:
    """Copy of `seg` with a linear 10 ms fade-in and fade-out (shorter if the segment is tiny)."""
    out = seg.astype(np.float32).copy()
    n = min(ms_to_samples(FADE_MS), len(out) // 2)
    if n > 0:
        ramp = np.linspace(0.0, 1.0, n, endpoint=False, dtype=np.float32)
        out[:n] *= ramp
        out[-n:] *= ramp[::-1]
    return out


class ClipBuilder:
    """Lays segments end to end on a timeline that starts silent (zeros).

    `cursor` is the current position in samples. `place()` writes audio at the
    cursor and moves it on; `silence()` just moves it on, leaving zeros, which
    matches the recordings' own (noise-suppressed) silence.
    """

    def __init__(self) -> None:
        self.parts: list[np.ndarray] = []
        self.cursor = 0

    def silence(self, ms: int) -> None:
        self.parts.append(np.zeros(ms_to_samples(ms), dtype=np.float32))
        self.cursor += ms_to_samples(ms)

    def place(self, seg: np.ndarray) -> int:
        """Append a faded segment; return the sample where it starts."""
        start = self.cursor
        self.parts.append(faded(seg))
        self.cursor += len(seg)
        return start

    def finish(self, true_end: int) -> np.ndarray:
        """Pad with zeros so the clip ends exactly TAIL_MS after `true_end`."""
        audio = np.concatenate(self.parts) if self.parts else np.zeros(0, dtype=np.float32)
        total = true_end + ms_to_samples(TAIL_MS)
        if len(audio) > total:  # can't happen with a 30 ms margin, but never cut audio silently
            raise ValueError("segment runs past the tail; TAIL_MS too short?")
        return np.concatenate([audio, np.zeros(total - len(audio), dtype=np.float32)])


def add_noise_floor(audio: np.ndarray, clip_name: str, seed: int) -> np.ndarray:
    """Add Gaussian noise at NOISE_FLOOR_DB over the whole clip.

    The recordings' silence is exact digital zero (recorder noise suppression),
    which would hand an energy VAD perfect silence. A quiet, constant noise floor
    makes every group, and every splice, look like the same real line.
    Each clip gets its own generator, seeded from `seed` and the clip name, so the
    noise is the same on every run whatever order clips are built in.
    """
    rng = np.random.default_rng(seed + zlib.crc32(clip_name.encode()))
    std = 10 ** (NOISE_FLOOR_DB / 20)  # RMS of zero-mean Gaussian noise = its std
    return audio + rng.normal(0.0, std, len(audio)).astype(np.float32)


# --- Groups ----------------------------------------------------------------------------

def build_fluent(pieces: list[Piece], gaps_ms: list[int]) -> tuple[np.ndarray, list[int]]:
    """Join trimmed pieces with the given gaps.

    Returns (audio, piece_ends): where each piece's speech ends, in samples.
    The last one is the true end.
    """
    clip = ClipBuilder()
    clip.silence(LEAD_MS)
    piece_ends = []
    for i, piece in enumerate(pieces):
        if i > 0:
            clip.silence(gaps_ms[i - 1])
        start = clip.place(piece.audio)
        piece_ends.append(start + piece.speech_end)
    return clip.finish(piece_ends[-1]), piece_ends


def build_stammered(
    pieces: list[Piece], gaps_ms: list[int], block_before: int, burst_ms: int, silence_ms: int
) -> tuple[np.ndarray, list[int], int]:
    """Fluent join plus a Block before piece index `block_before`.

    The Block is a burst (the first `burst_ms` of that piece, from its speech
    onset) followed by `silence_ms` of silence; then the piece plays in full.
    Returns (audio, piece_ends, block_start), the last two in samples. The burst
    is not a piece: it is a fragment, so it adds no end and no text.
    """
    clip = ClipBuilder()
    clip.silence(LEAD_MS)
    piece_ends = []
    block_start = 0
    for i, piece in enumerate(pieces):
        if i > 0:
            clip.silence(gaps_ms[i - 1])
        if i == block_before:
            onset = piece.speech_start
            block_start = clip.place(piece.audio[onset : onset + ms_to_samples(burst_ms)])
            clip.silence(silence_ms)
        start = clip.place(piece.audio)
        piece_ends.append(start + piece.speech_end)
    return clip.finish(piece_ends[-1]), piece_ends, block_start


def build_pause_take(x: np.ndarray, name: str) -> tuple[np.ndarray, int, int]:
    """A P_* take as recorded (no trimming), padded so it ends TAIL_MS after speech.

    Returns (audio, true_end in samples, number of pauses >= 500 ms).
    """
    sp = detect_speech(x, name)
    total = sp.end + ms_to_samples(TAIL_MS)
    # Untouched audio (no fades, no trimming at the front): the real pauses stay as recorded.
    # Append zeros for the tail; only if the take's own tail were longer than TAIL_MS
    # (never in practice) would we cut it, so every clip has the same tail.
    audio = np.concatenate([x, np.zeros(max(0, total - len(x)), dtype=np.float32)])[:total]
    return audio, sp.end, count_long_pauses(x, sp)


# --- Driver ---------------------------------------------------------------------------------

def load_lines(recordings: Path) -> list[Line]:
    """Read lines.csv and check every piece file it promises exists, and that the
    piece texts match the piece count and add up to the line's text."""
    with open(recordings / "lines.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if rows and "piece_texts" not in rows[0]:
        raise ValueError("lines.csv has no piece_texts column (pieces separated by '|')")
    lines = [Line(r["line"], r["slot"], int(r["pieces"]), r["text"], tuple(r["piece_texts"].split(PIECE_SEP)))
             for r in rows]
    for ln in lines:
        if len(ln.piece_texts) != ln.pieces:
            raise ValueError(f"{ln.line}: {ln.pieces} piece(s) but {len(ln.piece_texts)} piece text(s)")
        if " ".join(ln.piece_texts) != ln.text:
            raise ValueError(f"{ln.line}: piece texts {ln.piece_texts} don't join to {ln.text!r}")
        for path in piece_paths(recordings, ln):
            if not path.exists():
                raise FileNotFoundError(f"lines.csv lists {ln.line} with {ln.pieces} piece(s) but {path} is missing")
    return lines


def piece_paths(recordings: Path, ln: Line) -> list[Path]:
    """P_A2 -> [P_A2.wav]; A1 with 3 pieces -> [A1_1.wav, A1_2.wav, A1_3.wav]."""
    if ln.line.startswith("P_"):
        return [recordings / f"{ln.line}.wav"]
    return [recordings / f"{ln.line}_{i}.wav" for i in range(1, ln.pieces + 1)]


def build(recordings: Path, data_dir: Path, seed: int = SEED) -> list[dict]:
    """Generate every clip, the manifest and the demo folder. Returns the manifest rows."""
    rng = random.Random(seed)  # every gap/burst/silence draw, in a fixed order
    lines = load_lines(recordings)

    clips_dir = data_dir / "clips"
    if clips_dir.exists():
        shutil.rmtree(clips_dir)  # generated only: start clean so no stale clips survive

    rows: list[dict] = []

    def emit(rel: str, group: str, ln: Line, audio: np.ndarray, true_end: int, notes: str,
             piece_ends: list[int] | None = None) -> None:
        """piece_ends=None: no piece timing (P_* takes), so both piece columns stay empty."""
        write_wav(data_dir / rel, add_noise_floor(audio, rel, seed))
        rows.append({"file": rel, "group": group, "line": ln.line, "slot": ln.slot,
                     "transcript": ln.text, "true_end_ms": samples_to_ms(true_end),
                     "piece_ends_ms": PIECE_END_SEP.join(str(samples_to_ms(e)) for e in piece_ends or []),
                     "piece_texts": PIECE_SEP.join(ln.piece_texts) if piece_ends else "",
                     "notes": notes})

    for ln in lines:  # lines.csv order keeps the random draws stable
        paths = piece_paths(recordings, ln)

        if ln.line.startswith("P_"):
            audio, true_end, n_pauses = build_pause_take(read_wav(paths[0]), paths[0].name)
            emit(f"clips/pauses/{ln.line}.wav", "pauses", ln, audio, true_end, f"pauses_over_500ms={n_pauses}")
            continue

        pieces = [trim(read_wav(p), p.name) for p in paths]

        # fluent: one draw per gap; stammered reuses these so only the Block differs.
        gaps = [rng.randint(*GAP_MS) for _ in range(len(pieces) - 1)]
        audio, piece_ends = build_fluent(pieces, gaps)
        emit(f"clips/fluent/{ln.line}.wav", "fluent", ln, audio, piece_ends[-1], "", piece_ends)

        # stammered: Block before piece 2 (index 1), or at the very start for C1.
        block_before = 0 if ln.line in BLOCK_AT_START else 1
        for v in range(1, VARIANTS + 1):
            burst = rng.randint(*BURST_MS)
            silence = rng.randint(*BLOCK_SILENCE_MS)
            audio, piece_ends, block_start = build_stammered(pieces, gaps, block_before, burst, silence)
            notes = f"block_start_ms={samples_to_ms(block_start)};burst_ms={burst};silence_ms={silence}"
            emit(f"clips/stammered/{ln.line}_v{v}.wav", "stammered", ln, audio, piece_ends[-1], notes, piece_ends)

    write_manifest(data_dir / "manifest.csv", rows)
    write_demo(data_dir, rows)
    return rows


def write_manifest(path: Path, rows: list[dict]) -> None:
    # newline="\n" so the file is byte-identical on Windows and elsewhere.
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_demo(data_dir: Path, rows: list[dict]) -> None:
    """Copy the committed demo samples into data/demo/ with their own small manifest."""
    demo_dir = data_dir / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    by_file = {r["file"]: r for r in rows}
    demo_rows = []
    for src, name in DEMO_CLIPS:
        if src not in by_file:   # a partial set of recordings (tests) doesn't build every demo source
            continue
        shutil.copyfile(data_dir / src, demo_dir / name)
        demo_rows.append({**by_file[src], "file": f"demo/{name}"})
    write_manifest(demo_dir / "manifest.csv", demo_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--recordings", type=Path, default=DATA_DIR / "recordings")
    parser.add_argument("--out", type=Path, default=DATA_DIR, help="writes clips/, manifest.csv and demo/ here")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    rows = build(args.recordings, args.out, args.seed)
    counts = {g: sum(r["group"] == g for r in rows) for g in ("fluent", "stammered", "pauses")}
    print(f"{len(rows)} clips {counts} -> {args.out / 'manifest.csv'}")


if __name__ == "__main__":
    main()
