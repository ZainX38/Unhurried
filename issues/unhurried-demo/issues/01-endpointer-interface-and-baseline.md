# 01: Endpointer interface and Baseline

**Status:** ready-for-human (core logic, Recipe A: you write the code)
**Blocked by:** None (can start immediately)
**When:** Sun, 1–2 h

**What to build:** A pure Endpointer interface and the fixed-timeout Baseline behind it. Fake VAD frames go in, a Decision with a reason comes out, so both the evaluation and the live app can use the same code.

## Understand

- The Endpointer is a pure function: data in, decision out, with no audio, network or file code inside. That makes it testable with fake frames and usable by both the evaluation and the live app (ADR 0001).
- Interface: for each frame it receives `is_speech` (from the VAD), the frame duration (32 ms) and the latest partial transcript (empty for now). It returns a Decision (`CONTINUE`, `END` or `PROMPT`) plus a reason string.
- Baseline rule:
  - Count consecutive silent milliseconds. Speech resets the counter.
  - 700 ms or more → `END`.
  - Never `END` before any speech has been heard.
- This is a deep module: a tiny interface with all the logic inside (see the `codebase-design` skill).

## Build

- Files: `src/unhurried/endpointer/types.py`, `src/unhurried/endpointer/baseline.py`, `tests/test_baseline.py`.
- Your test cases (write these in plain English first):
  - 600 ms of silence after speech → `CONTINUE`
  - 704 ms of silence after speech → `END` (22 frames × 32 ms)
  - silence for 650 ms, then speech → counter resets, `CONTINUE`
  - silence only, no speech yet → never `END`
  - the reason string mentions the silence length, e.g. `silence 704ms >= 700ms`
- Plan-mode prompt: "Design the smallest interface for an endpointer that takes one VAD frame at a time and returns CONTINUE/END/PROMPT with a reason. No audio code inside."

## Check yourself

- [ ] Why does the Endpointer have no audio code?
- [ ] Why 32 ms frames, and how many samples is that at 16 kHz?
- [ ] What happens to the silence counter when speech returns?
- [ ] Why should the Baseline never `END` before speech starts?

## Acceptance

- [ ] All Baseline tests pass.
- [ ] You can explain `baseline.py` line by line.
