# Synthetic timeline generator

Status: ready-for-agent
Blocked by: 01, 02

## What

Generate symbolic Calls (a sequence of Prompts and Turns) as event streams with a ground-truth Turn end per Turn:

- Slot-appropriate word content (digits, dates, reasons).
- Words arrive about 250 ms after they are spoken (STT delay).
- Fluent between-word pauses, plus stammers placed per the Severity group: Blocks (silence mid-Turn), prolongations, and sound/word repetitions (words duplicated in the transcript).
- Simulated Ticks (for example every 50 ms).
- Fixed seed, so it is reproducible.

## Acceptance

- Parameters come from ticket 02's table, kept in one config file.
- Tests: same seed gives identical output; Turn end is after the last word; severe callers have more and longer Blocks than mild callers.
