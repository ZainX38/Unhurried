"""One-off helper: convert raw recordings to 16 kHz, mono, 16-bit PCM WAV.

Phones and laptops record at 44.1/48 kHz stereo, but Vosk, the VAD and
`make_data.py` only accept 16 kHz mono 16-bit. Rather than resample in Python
(which would need an extra dependency), we convert once with ffmpeg and commit
the converted files.

What it does, for every WAV in `eval/data/recordings/`:

1. Moves the original into `eval/data/recordings/originals/` (git-ignored),
   unless an original with that name is already there.
2. Runs ffmpeg on the original and writes the converted file back to
   `eval/data/recordings/<same name>.wav`.

Running it again is safe: it always converts from `originals/`, so it never
converts an already-converted file twice.

Usage:
    uv run python -m eval.convert_recordings
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

RECORDINGS_DIR = Path(__file__).parent / "data" / "recordings"
ORIGINALS_DIR = RECORDINGS_DIR / "originals"

# The one format everything downstream accepts (see eval/audio.py).
TARGET_RATE = 16_000


def ffmpeg_convert(src: Path, dst: Path) -> None:
    """Convert `src` to 16 kHz mono 16-bit PCM WAV at `dst` using ffmpeg."""
    cmd = [
        "ffmpeg",
        "-y",                      # overwrite dst without asking
        "-loglevel", "error",      # only print real problems
        "-i", str(src),
        "-ac", "1",                # mono: ffmpeg averages the channels
        "-ar", str(TARGET_RATE),   # resample to 16 kHz
        "-c:a", "pcm_s16le",       # 16-bit signed little-endian PCM
        "-map_metadata", "-1",     # drop tags (dates, encoder names)...
        "-fflags", "+bitexact",    # ...so the same input gives the same bytes
        str(dst),
    ]
    subprocess.run(cmd, check=True)


def main() -> int:
    if shutil.which("ffmpeg") is None:
        print("ffmpeg not found on PATH. Install it first (e.g. winget install ffmpeg).")
        return 1

    ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)

    # Every name we know about: files at the top level plus any already-moved originals.
    names = sorted({p.name for p in RECORDINGS_DIR.glob("*.wav")}
                   | {p.name for p in ORIGINALS_DIR.glob("*.wav")})

    for name in names:
        top = RECORDINGS_DIR / name
        original = ORIGINALS_DIR / name

        # First run: keep the untouched recording before we overwrite anything.
        if not original.exists():
            shutil.move(top, original)

        ffmpeg_convert(original, top)
        print(f"converted {name}")

    print(f"{len(names)} files -> {RECORDINGS_DIR} (originals in {ORIGINALS_DIR})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
