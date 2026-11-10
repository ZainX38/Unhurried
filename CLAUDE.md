## Project

Unhurried is a phone line that doesn't cut off callers who stammer. I am building it for Hiya Voice AI Challenge (Accessibility track).
Deadline: submit by Wed 11 Nov 12:30.

## Who writes what (important)

- **I write the core logic myself:** `endpointer/baseline.py`, `endpointer/patient.py`, `endpointer/completeness.py`, `eval/metrics.py`, `dialogue.py`, `cleanup.py`.
  For these, write tests from my cases with /tdd and give hints only. Do NOT write the implementation unless I explicitly ask.
- **You write plumbing** when asked: audio, data scripts, eval harness, STT adapter, session, server, frontend.
- Plan first: explain files, functions, inputs and outputs before any code. After writing code, give a short walkthrough.
- Never edit `NOTES.md` or `ai.md`. I write those myself.

## Stack

- Python 3.12, uv, FastAPI + WebSockets, pytest
- VAD: energy VAD (Silero optional). STT: Vosk `vosk-model-small-en-us-0.15` (offline, in `models/`, git-ignored)
- Frontend: React + TypeScript + Vite, browser mic at 16 kHz mono PCM16, browser speechSynthesis
- No API keys. No LLM anywhere in the decision path.

## Commands

- Tests: `uv run pytest`
- Download the Vosk model: `uv run python -m eval.download_model`
- Build test clips: `uv run python -m eval.make_data`
- Full evaluation: `uv run python -m eval.sweep --stt vosk`
- One run: `uv run python -m eval.run --endpointer patient --stt vosk`
- 

## Rules of the domain

- Audio frames are 32 ms (512 samples at 16 kHz, mono, int16).
- Endpointers are pure: no audio, network, file or clock code. Interface: `step(is_speech, frame_ms, transcript) -> Decision` and `reset(expected_slot)`.
- `transcript=None` means "no STT available" (timing only); `""` means "STT running, nothing heard yet". Don't mix them up.
- Vosk transcript = finished segments + current partial. A Vosk segment end never ends a turn.
- The endpointer never hangs up on silence: INCOMPLETE answers get a PROMPT at 6 s and keep listening. Patience ceiling 5 s.
- Completeness counts digits but never deletes them. Cleanup never collapses repeated digits; the read-back resolves them.
- Disfluency must never feed any fraud, risk or scoring logic.
- Don't add word rules just to fix a specific clip. A rule must hold as a general principle.

## Checks before saying a task is done

- `uv run pytest` is green.
- Any change to the harness or data: the Baseline outputs (`eval/results/sweep.md`, `sweep_clips.csv`) must stay byte-identical (`git diff --exit-code`).
- Report results honestly. Never hide misses or no-END clips.

## Out of scope (don't build unless I ask)

Barge-in, SEP-28k evaluation (ticket 10), business dashboard, LLM features, Piper TTS.