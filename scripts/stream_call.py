"""Stream WAVs through the server's WebSocket as one Call and print the events (ticket 07).

Start the server first:   uv run uvicorn unhurried.server:app
Then, a whole Call from the recorded lines (account, yes, date of birth, yes, reason):

    uv run python scripts/stream_call.py eval/data/clips/fluent/{A1,C1,D1,C1,R1}.wav

Each WAV is one Turn; GAP_MS of silence goes after each so the Endpointer can end it.
CONTINUE decisions are not printed (there is one every 32 ms).
By default audio is sent as fast as possible: Endpointer timing comes from the frame
count, not the wall clock. --realtime paces it like a live microphone.
"""

from __future__ import annotations

import argparse
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
    args = parser.parse_args()

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
