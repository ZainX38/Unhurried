# Event model, Endpointer interface and Baseline

Status: ready-for-agent

## What

- Typed, timestamped events (ms): `PromptStart(slot)`, `SpeechStart`, `SpeechEnd`, `Words(partial|final, text)`, `Tick`, `SystemSpeechStart` / `SystemSpeechEnd` (for Barge-in).
- An `Endpointer` protocol: `feed(event) -> Endpoint | None`. It is pure and has no clock of its own (ADR 0001).
- `BaselineEndpointer(timeout_ms)`: Endpoints after `timeout_ms` of continuous silence, judged on Ticks.
- An `UnhurriedEndpointer` skeleton with the 5 s Ceiling already enforced, plus clearly marked `# RULES:` hooks for ticket 05. The Completeness and Cleanup interfaces and stubs live in 06.

## Acceptance

- Unit tests for the Baseline: Endpoints exactly at timeout, resets on speech, never before speech has started.
- Unit test that the Ceiling fires at 5 s whatever the rules say.
- Lives in `src/unhurried/endpointer/`.
