# 04: Completeness rules

**Status:** ready-for-human (core logic, Recipe A: you write the code)
**Blocked by:** None (can start immediately)
**When:** Mon, 1.5–2 h

**What to build:** A pure `completeness(transcript, expected_slot)` that says whether the words so far form a finished answer to what the line just asked, with a human-readable reason.

## Understand

- Silence alone can't tell "stuck" from "finished", but words can: "my account number is" is obviously unfinished.
- Call state is the strongest, cheapest signal: the system knows what it just asked. If it asked for an 8-digit account number and has heard 4 digits, the caller isn't done.
- Three answers, not two: `COMPLETE`, `INCOMPLETE`, `UNSURE`. `UNSURE` means "the rules can't tell"; the Endpointer then behaves normally.
- Why rules, not an LLM:
  - rules run in microseconds (an LLM takes hundreds of ms, which is added delay)
  - they give checkable reasons ("4/8 digits")
  - they can't time out or hallucinate
- **STT is Vosk (ADR 0002)**, so transcripts arrive as dictionary words: "four five two one", never "4521" and never "4-". Digit words therefore must count.

## Build

- Files: `src/unhurried/endpointer/completeness.py`, `tests/test_completeness.py`.
- Function: `completeness(transcript, expected_slot) → (status, reason)`, where `expected_slot` is e.g. `"account_number"`, `"yes_no"` or `"free_text"`.
- Table-driven test cases (aim for 15 or more):
  - "my account number is" → `INCOMPLETE` (ends with "is")
  - "it's four five two one" with the account slot → `INCOMPLETE` (4/8 digits)
  - "four five two one eight eight three oh" → `COMPLETE` (8/8)
  - "my account number is four five and" → `INCOMPLETE` (ends on "and"; replaces the old "4-" case, which Vosk can't produce)
  - "yes" with the yes/no slot → `COMPLETE`
  - "I'm calling about my bill" with free text → `UNSURE`
  - "" (nothing heard yet) → `UNSURE`
- Decide yourself: does "oh" count as zero? What about "double four"?

## Check yourself

- [ ] Why is "4/8 digits" stronger evidence than any timing signal?
- [ ] Why does `UNSURE` exist?
- [ ] Give two reasons rules beat an LLM here, and one case where an LLM would help.
- [ ] What happens if the STT mishears one digit as a word?

## Acceptance

- [ ] 15 or more completeness tests pass.
- [ ] Every rule returns a human-readable reason.
