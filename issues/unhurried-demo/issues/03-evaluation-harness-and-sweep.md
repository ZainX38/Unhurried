# 03: Evaluation harness and threshold sweep

**Status:** ready-for-human (core logic, Recipe A for the metrics; Recipe B, written by Claude, for the replay and sweep)
**Blocked by:** 01, 02
**When:** Sun, 2–3 h (Sunday checkpoint)

**What to build:** Replay every clip through any endpointer on a simulated clock, score Cut-offs and extra wait per group, and draw the fixed-threshold sweep curve that shows why raising a timeout costs everyone.

## Understand

- The harness replays each WAV frame by frame (32 ms frames, 512 samples at 16 kHz) on a simulated clock (no real waiting), calls `step(is_speech, 32, transcript)` on a fresh endpointer per clip, and records the time of the **first** `END` (the end of that frame). `transcript` is `""` until STT exists (ticket 06).
- **Do not add padding in the harness.** Every clip from ticket 02 already ends 8 s after `true_end_ms` (with a noise floor, not digital silence), which is enough for the 5 s Ceiling and the 6 s `PROMPT`. Clips also already start with a 500 ms lead-in. Replay each WAV exactly as it is. A clip with no `END` inside it is recorded as **no end**: not a Cut-off, and left out of the Wait time stats (reported as its own count).
- Read each clip's Slot from the manifest's `slot` column and build the endpointer for the Turn with it (`make_endpointer(slot)`). Don't guess the Slot from the transcript.
- Metrics:
  - **Cut-off rate** per group = clips where the first `END` < `true_end_ms`, divided by the clips in the group.
  - **Wait time** = first `END` − `true_end_ms`, only on clips that were not Cut off (and had an `END`), reported per group as median and p95.
  - Per-clip records are written as CSV next to the summary.
  - (Extra wait, your `END` minus the Baseline's `END` on clips neither cut off, is for comparing two endpointers in ticket 05.)
- Sweep: run the Baseline with fixed thresholds of 300, 500, 700, 1000, 1500, 2000, 3000 and 4000 ms. Plot stammered Cut-off rate (y) against fluent median Wait time (x). The curve shows that raising a fixed timeout always costs everyone.

## Build

- **You write** `eval/metrics.py` (Recipe A). Test cases:
  - 3 clips, 1 cut off → 33%
  - waits [0, 0, 0, 2400] → median 0, p95 near 2400
  - empty group → no crash
  - `END` exactly at `true_end_ms` → not a Cut-off, wait 0
  - no `END` → "no end", not a Cut-off, not in the wait stats
- **Claude writes** (Recipe B):
  - `src/unhurried/vad.py`: energy VAD on 32 ms frames
  - `eval/run.py`: load the manifest, run the VAD, replay frames, collect first `END` times, write per-clip CSV
  - `eval/sweep.py`: loop over the thresholds and save `eval/results/sweep.md`, `sweep_clips.csv` and `sweep.png`
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
