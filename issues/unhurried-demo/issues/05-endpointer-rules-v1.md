# Endpointer rules v1

Status: ready-for-human
Blocked by: 01, 04

## What

Zain writes the rules in the `UnhurriedEndpointer` hooks: silence thresholds per state, how Completeness shortens or lengthens the wait, memory of earlier Turns in the Call (for example a caller who has had Blocks before gets more patience), and Barge-in handling. Iterate against the harness.

## Acceptance

Harness passes: stammered Cut-off rate < 5%, fluent median Wait time ≤ 900 ms.
