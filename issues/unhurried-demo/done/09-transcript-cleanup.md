# 09: Transcript Cleanup

**Status:** ready-for-human (core logic, Recipe A; the raw vs clean view in the frontend is Recipe B)
**Blocked by:** 08 (only for the frontend view; the pure function and its tests can start any time)
**When:** Tue, 1.5 h

**What to build:** A pure Cleanup that turns a stammered transcript into what the caller meant without ever changing meaning (especially digits), shown side by side with the raw transcript in a live Call.

## Understand

- Cleanup turns "my my my account is …" into "my account is …", so the dialogue reads the right answer and the business sees a clean record.
- **The golden rule:** never change meaning, especially digits.
- **Vosk changes the digit problem** (ADR 0002). Transcripts are dictionary words ("four four four five two one"), with no hyphenated restarts like "4-4-4521". So the "restart pattern proves extras" signal from Hiya1 isn't available. Repeated digit words may be genuine (44445123) or a stammer, and the text alone can't tell which.
  - **Decide yourself:** never collapse repeated digit words (the agreed default from grilling), or flag runs for Read-back? Either way, Read-back is the safety net.
- Ambiguous cases are kept and **flagged**, and the Read-back catches them.
- "oh" is not a filler: callers say it for zero.
- Rules, not an LLM: an LLM rewrite reads more naturally but could silently change a digit, which is unacceptable for account numbers.

## Build

- Files: `src/unhurried/cleanup.py`, `tests/test_cleanup.py`. Return the raw text, the cleaned text and a list of edits made.
- Test cases, rewritten for Vosk's word output. Confirm or adjust them using your ticket 06 day-one notes:
  - "my my my account" → "my account"
  - "um I want" → "I want"
  - "I I I want to pay" → "I want to pay"
  - "four four five two one" → unchanged (could be a real number)
  - "four four four five two one" → unchanged + flagged (your decision above)
  - "oh four" → unchanged
  - whatever Vosk outputs for "m-m-my" and "sssso" in your clips → your expected cleaned form
- The raw vs clean side-by-side view in the frontend (Recipe B).

## Check yourself

- [ ] Why is "four four five two one" never changed?
- [ ] Why can't Cleanup tell a repeated digit from a stammered one with Vosk, and what does it do instead?
- [ ] What's the safety net if Cleanup gets a digit wrong?
- [ ] Why not use an LLM here?

## Acceptance

- [ ] Cleanup tests pass.
- [ ] Raw and clean transcripts show side by side in a live Call.
