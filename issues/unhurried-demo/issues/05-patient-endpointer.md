# 05: Patient endpointer

**Status:** ready-for-human (core logic: short re-grill, then Recipe A; harness flag via Recipe B)
**Blocked by:** 03, 04
**When:** Mon, 2–3 h (Monday checkpoint: if this is done, you have a submission)

**What to build:** The heart of Unhurried. An endpointer that starts as fast as the Baseline and adds patience only when there is evidence the caller isn't done, with every decision explained, plotted as a point against the fixed-threshold curve.

Start with a 10-minute `/grill-with-docs` on the bonus values before coding.

## Understand

- **Patience** is how much silence ends the Turn. It starts at the Baseline's 700 ms, so a fluent, finished answer ends exactly as fast as with the Baseline.
- Evidence adds to it:

| Signal | Effect | Why |
|---|---|---|
| Completeness = `INCOMPLETE` | Silence alone can never end the Turn | If the answer is provably unfinished, ending is always wrong |
| Recent repetition in transcript ("my my") | +1000 ms for 8 s | Someone who just repeated a sound is likely to pause again |
| Completeness = `COMPLETE` structured answer (8/8 digits, clear yes/no) | Drop all bonuses → 700 ms | Nothing left to wait for; keeps fluent callers fast |
| Cap | Patience ≤ 4000 ms | Bounds the worst-case wait |
| 6 s of silence | `PROMPT`: "Take your time, you can also use the keypad", then keep listening | Never hang up on silence |

- Reason strings make every decision checkable, e.g. `silence 900ms < patience 2700ms: account has 4/8 digits`. They appear in the demo's "why it's waiting" panel.
- Safe failure: if the STT drops a digit, the answer looks `INCOMPLETE`, so the system waits until the gentle prompt. Waiting is the right direction to fail for this product.
- With Vosk, repetitions show up as repeated or wrong dictionary words, not "m-m-my" (see ticket 06's day-one notes).

## Build

- Files: `src/unhurried/endpointer/patient.py`, `tests/test_patient.py`. It calls your `completeness()` from ticket 04.
- Test cases:
  - fluent complete answer → ends at about 700 ms
  - 4/8 digits + 3 s silence → `CONTINUE`
  - repetition seen → patience 1700 ms
  - 8/8 digits → back to 700 ms
  - 6 s silence → `PROMPT`, then still listening
  - patience never exceeds 4000 ms
- Add a harness flag (`--endpointer patient`, Recipe B), run it, and plot your point on Sunday's curve.
- Optional experiment: a timing-only Block detector (a short burst then ≥ 500 ms silence → +2400 ms). Report it honestly either way.

## Check yourself

- [ ] Explain each signal, its value and why.
- [ ] Why does a complete structured answer drop all bonuses?
- [ ] Where does your point sit relative to the fixed-threshold curve, and what does that mean?
- [ ] What are the median and p95 extra wait for fluent callers, and why do they differ?

## Acceptance

- [ ] Patient tests pass.
- [ ] Your point is on the chart.
- [ ] `eval/results/results.md` is committed.
