"""Download the small English Vosk model into models/ (git-ignored). About 40 MB; skips if present.

Usage:
    uv run python -m eval.download_model
"""

from __future__ import annotations

import tempfile
import urllib.request
import zipfile
from pathlib import Path

from unhurried.stt import DEFAULT_VOSK_MODEL, MODELS_DIR, VOSK_MODEL_URL


def main() -> None:
    if DEFAULT_VOSK_MODEL.is_dir():
        print(f"already there: {DEFAULT_VOSK_MODEL}")
        return
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "model.zip"
        print(f"downloading {VOSK_MODEL_URL} ...")
        urllib.request.urlretrieve(VOSK_MODEL_URL, archive)
        with zipfile.ZipFile(archive) as z:
            root = MODELS_DIR.resolve()
            for name in z.namelist():  # refuse entries that would land outside models/
                if not (root / name).resolve().is_relative_to(root):
                    raise ValueError(f"unsafe path in archive: {name}")
            z.extractall(root)
    print(f"-> {DEFAULT_VOSK_MODEL}")


if __name__ == "__main__":
    main()
