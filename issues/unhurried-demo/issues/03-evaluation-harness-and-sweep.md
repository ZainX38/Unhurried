# 03: Evaluation harness and threshold sweep

**Status:** ready-for-human (core logic, Recipe A for the metrics; Recipe B, written by Claude, for the replay and sweep)
**Blocked by:** 01, 02
**When:** Sun, 2–3 h (Sunday checkpoint)

**What to build:** Replay every clip through any endpointer on a simulated clock, score Cut-offs and extra wait per group, and draw the fixed-threshold sweep curve that shows why raising a timeout costs everyone.

## Understand

- The harness replays each WAV frame by frame on a simulated clock (no real waiting), feeds the VAD results to an endpointer, and records the time it says `END`.
- **Do not add padding in the harness.** Every clip from ticket 02 already ends 8 s after `true_end_ms` (with a noise floor, not digital silence), which is enough for the 5 s Ceiling and the 6 s `PROMPT`. Replay each WAV exactly as it is. A clip still listening at the end counts as ended at the clip end (a lower bound).
- Read each clip's Slot from the manifest's `slot` column and start the Turn with it. Don't guess the Slot from the transcript.
- Metrics:
  - **Cut-off rate** per group = clips where `END` < `true_end_ms`, divided by the clips in the group.
  - **Extra wait** = your `END` minus the Baseline's `END`, on clips neither endpointer cut off, reported as median and p95.
- Sweep: run the Baseline with fixed thresholds of 500, 700, 1000, 1500, 2000 and 3000 ms. Plot stammered Cut-off rate (y) against fluent delay (x). The curve shows that raising a fixed timeout always costs everyone.

## Build

- **You write** `eval/metrics.py` (Recipe A). Test cases:
  - 3 clips, 1 cut off → 33%
  - extra waits [0, 0, 0, 2400] → median 0, p95 near 2400
  - empty group → no crash
- **Claude writes** (Recipe B):
  - `eval/run.py`: load the manifest, run the VAD, replay frames, collect `END` times
  - `eval/sweep.py`: loop over the thresholds and save `eval/results/sweep.md` and `sweep.png`
- Use an energy VAD first if Silero setup slows you down; switch to Silero (ONNX) once it works.
- Seam-2 unit tests may use **tiny hand-made Timelines** as fixtures with known answers (e.g. a 700 ms Baseline plus a 1 s Block gives exactly 1 Cut-off). These are test fixtures only and are never used for reported results.

## Check yourself

- [ ] Why replay on a simulated clock instead of real time?
- [ ] Why is extra wait only measured on clips neither endpointer cut off?
- [ ] Why median and p95 instead of the mean?
- [ ] What does each point on the sweep curve mean?

## Acceptance

- [ ] `eval/results/` has the Baseline sweep table and chart.
- [ ] You can explain the shape of the curve.
