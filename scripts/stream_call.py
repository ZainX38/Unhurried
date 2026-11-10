"""Stream WAVs through the server's WebSocket as one Call and print the events (ticket 07).

Start the server first:   uv run uvicorn unhurried.server:app
Then, a whole Call from the recorded lines (account, yes, date of birth, yes, reason):

    uv run python scripts/stream_call.py eval/data/clips/fluent/{A1,C1,D1,C1,R1}.wav

Each WAV is one Turn; GAP_MS of silence goes after each so the Endpointer can end it.
CONTINUE decisions are not printed (there is one every 32 ms).
By default audio is sent as fast as possible: Endpointer timing comes from the frame
count, not the wall clock. --realtime paces it like a live microphone.

--caller behaves like the frontend's sample caller (ticket 08) instead of one long stream:
each WAV is one answer; after it, silence until the bot replies (at most 7 s); and if the
bot replies before the caller has finished speaking (cut off), the WAV stops and the same
answer is given again at the next question. "Finished speaking" is the clip's true_end_ms
from the manifest.csv next to it (the WAV may carry trailing silence after that). Frames go one at a time, each waiting for its decision,
so a cut-off is detected at the frame it happens.

    uv run python scripts/stream_call.py --caller --endpointer baseline         eval/data/demo/{A1_stammered,C2,C1,D1,C1,R2}.wav
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import threading
import time
from pathlib import Path

import numpy as np
from websockets.sync.client import connect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # for `eval`
from eval.audio import read_wav  # noqa: E402
from unhurried.stt import to_pcm16  # noqa: E402
from unhurried.vad import FRAME_MS, FRAME_SAMPLES, SAMPLE_RATE  # noqa: E402

GAP_MS = 3000
MAX_REPLY_WAIT_MS = 7000   # --caller: just past the 6 s PROMPT
MAX_REPLAYS = 3            # --caller: safety stop; the dialogue hands over first


def print_event(e: dict) -> None:
    if e["type"] == "transcript":
        print(f"           heard: {e['text']}")
    elif e["type"] == "decision" and e["action"] != "CONTINUE":
        print(f"{e['t_ms']:>7} ms {e['action']}: {e['reason']}")
    elif e["type"] == "bot":
        print(f"           BOT: {e['line']}")
    elif e["type"] == "state":
        print(f"           [{e['state']}] waiting for {e['expected_slot'] or '-'}  slots={e['slots']}")


class Caller:
    """--caller: one answer per WAV, replayed after a cut-off (see the module docstring)."""

    def __init__(self, ws) -> None:
        self.ws = ws
        self.states = 0     # state events seen; a new one means the bot replied
        self.done = False

    def _handle(self, e: dict) -> None:
        print_event(e)
        if e["type"] == "state":
            self.states += 1
            self.done = e["state"] == "DONE"

    def _send(self, frame: np.ndarray) -> None:
        """Send one frame and read events up to its decision (the server sends one per frame)."""
        self.ws.send(to_pcm16(frame))
        while True:
            try:
                e = json.loads(self.ws.recv(timeout=5))
            except TimeoutError:
                sys.exit(f"No decision from the server for the frame at {self.states} states; it stopped answering.")
            self._handle(e)
            if e["type"] == "decision" or self.done:   # no decisions come after DONE
                return

    def run(self, answers: list[tuple[str, np.ndarray, int]]) -> None:
        """answers: (name, audio, true_end_ms) per WAV."""
        while self.states == 0:                     # the greeting
            self._handle(json.loads(self.ws.recv(timeout=30)))
        silence = np.zeros(FRAME_SAMPLES, dtype=np.float32)
        i = replays = 0
        while i < len(answers) and not self.done:
            name, audio, true_end_ms = answers[i]
            print(f"--- caller: {name}" + (" (cut off, saying it again)" if replays else ""))
            before = self.states
            cut_off = False
            for k in range(0, len(audio) - FRAME_SAMPLES + 1, FRAME_SAMPLES):
                if self.done or self.states > before:
                    # A reply before the caller finished speaking is a cut-off.
                    cut_off = k * 1000 // SAMPLE_RATE < true_end_ms
                    break
                self._send(audio[k : k + FRAME_SAMPLES])
            if self.done:
                break
            if cut_off and replays < MAX_REPLAYS:
                replays += 1
                continue
            i, replays = i + 1, 0
            if self.states > before:   # the bot has already replied
                continue
            after = self.states                       # silence until the bot replies
            for _ in range(MAX_REPLY_WAIT_MS // FRAME_MS):
                if self.done or self.states > after:
                    break
                self._send(silence)


def true_end_ms(wav: Path) -> int:
    """When the caller stops speaking in this WAV: true_end_ms from the manifest.csv beside it,
    else the whole clip."""
    manifest = wav.parent / "manifest.csv"
    if manifest.exists():
        with open(manifest, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if Path(row["file"]).name == wav.name:
                    return int(row["true_end_ms"])
    return len(read_wav(wav)) * 1000 // SAMPLE_RATE


def print_events(ws, finished: threading.Event) -> None:
    for message in ws:
        e = json.loads(message)
        if e["type"] == "transcript":
            print(f"           heard: {e['text']}")
        elif e["type"] == "decision" and e["action"] != "CONTINUE":
            print(f"{e['t_ms']:>7} ms {e['action']}: {e['reason']}")
        elif e["type"] == "bot":
            print(f"           BOT: {e['line']}")
        elif e["type"] == "state":
            print(f"           [{e['state']}] waiting for {e['expected_slot'] or '-'}  slots={e['slots']}")
            if e["state"] == "DONE":
                finished.set()
                return


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("wavs", nargs="+", type=Path)
    parser.add_argument("--endpointer", choices=["patient", "baseline"], default="patient")
    parser.add_argument("--url", default="ws://127.0.0.1:8000/ws")
    parser.add_argument("--realtime", action="store_true")
    parser.add_argument("--caller", action="store_true", help="act like the frontend's sample caller")
    args = parser.parse_args()

    if args.caller:
        with connect(f"{args.url}?endpointer={args.endpointer}") as ws:
            caller = Caller(ws)
            caller.run([(wav.stem, read_wav(wav), true_end_ms(wav)) for wav in args.wavs])
        if not caller.done:
            print("Call did not reach DONE.")
            sys.exit(1)
        return

    gap = np.zeros(SAMPLE_RATE * GAP_MS // 1000, dtype=np.float32)
    audio = np.concatenate([part for wav in args.wavs for part in (read_wav(wav), gap)])

    finished = threading.Event()
    with connect(f"{args.url}?endpointer={args.endpointer}") as ws:
        reader = threading.Thread(target=print_events, args=(ws, finished), daemon=True)
        reader.start()
        for i in range(0, len(audio) - FRAME_SAMPLES + 1, FRAME_SAMPLES):
            if finished.is_set():
                break
            ws.send(to_pcm16(audio[i : i + FRAME_SAMPLES]))
            if args.realtime:
                time.sleep(FRAME_MS / 1000)
        finished.wait(timeout=10)   # let the last events arrive
    if not finished.is_set():
        print("Call did not reach DONE.")
        sys.exit(1)


if __name__ == "__main__":
    main()
