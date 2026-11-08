# Completeness and Cleanup rules

Status: ready-for-human
Blocked by: 01

## What

- The agent first adds interfaces, stubs and test files: `completeness(slot, words, history) -> Complete | Incomplete | Unknown` (stub returns Unknown) and `cleanup(text, slot) -> str` (stub returns the text unchanged).
- Zain then writes the rules:
  - Completeness per Slot: account number length, a full date, a recognisable Intent.
  - Cleanup: remove stammered repetitions and fillers without changing meaning, and **never** collapse repeated digits ("double seven" and "7 7" survive).

## Acceptance

Table-driven tests in `tests/test_completeness.py` and `tests/test_cleanup.py`, including the repeated-digit cases.
