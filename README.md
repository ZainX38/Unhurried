# Unhurried

A phone line that doesn't cut off callers who stammer.

## Run the demo

You need Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 18+, and Chrome.

```
uv sync
uv run python -m eval.download_model                  # once: the offline Vosk model
```

Then, in two terminals:

```
uv run uvicorn unhurried.server:app --port 8000       # terminal 1: backend
cd frontend && npm install && npm run dev             # terminal 2: frontend
```

Open http://localhost:5173. The Vite dev server proxies `/ws` to the backend on port 8000.

- **Line**: Baseline (ends a turn after 0.7 s of silence) or Unhurried (waits until the answer is complete). Switching it during a call starts the call again on the other line.
- **Play sample caller** streams recorded answers from `eval/data/demo/` through the same WebSocket as a microphone, so the demo works without anyone speaking. The script is: account number with a stammer, "No, it's 4 5 2 1 8 8 3 1" (correcting the read-back), yes, date of birth, yes, reason for calling.
  - It behaves like a caller who gets cut off. If the bot replies before the caller has finished speaking (the clip's `true_end_ms` in `eval/data/demo/manifest.csv`), the clip stops and the same answer is given again at the next question. A reply after that point is normal, and the next answer follows.
  - Between answers it waits for the bot to finish speaking, then sends silence until the bot replies (at most 7 s). It stops when the call ends or the script runs out.
  - The same caller runs from the command line: `uv run python scripts/stream_call.py --caller --endpointer baseline eval/data/demo/{A1_stammered,C2,C1,D1,C1,R2}.wav`
- **My microphone** captures 16 kHz mono PCM16 in the browser (an AudioWorklet resamples it) and mutes outgoing audio while the bot speaks. Use headphones.
- **Why it's waiting** shows the endpointer's latest decision and its reason, live.
- **Keypad** is always available as an alternative to speaking.
