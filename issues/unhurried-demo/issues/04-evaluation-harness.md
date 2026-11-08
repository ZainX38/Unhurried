# Evaluation harness and timeout sweep

Status: ready-for-agent
Blocked by: 01, 03

## What

- Replay 1,000 Calls per Severity group through any `Endpointer`.
- Per group: Cut-off rate, plus Wait time median and p95 (for Turns that were not Cut off). A Cut-off counts even when Barge-in would have recovered it.
- Sweep the Baseline timeout from 300 ms to 4 s, plot the Cut-off rate vs. Wait time curve, and overlay Unhurried as a point.
- `uv run python -m eval.run` writes a JSON summary and a PNG to `eval/results/`, and prints pass/fail against the targets (stammered Cut-off rate < 5%, fluent median Wait time ≤ 900 ms).
