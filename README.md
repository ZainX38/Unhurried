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
- **Play sample caller** streams recorded answers from `eval/data/demo/` through the same WebSocket as a microphone, so the demo works without anyone speaking.
- **My microphone** captures 16 kHz mono PCM16 in the browser (an AudioWorklet resamples it) and mutes outgoing audio while the bot speaks. Use headphones.
- **Why it's waiting** shows the endpointer's latest decision and its reason, live.
- **Keypad** is always available as an alternative to speaking.
