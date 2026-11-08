# 02: Test data (Recorded Turns)

**Status:** ready-for-agent (plumbing, Recipe B). **Needs from you first:** the recordings and the design notes below.
**Blocked by:** None (can start immediately)
**When:** Sun, 1.5–2 h

**What to build:** A reproducible set of clips where the true end of each answer is known, so any endpointer can be scored on whether it cut someone off.

## Understand

- You need clips where you know the true end of each answer, so you can say whether an endpointer cut someone off.
- Three groups:
  - **fluent** (the control)
  - **stammered** (Blocks and repetitions inserted)
  - **fluent with thinking pauses** (0.8–2 s pauses between chunks, e.g. reading digits in groups)
- A Block looks like a tiny burst of sound (60–150 ms, e.g. "m"), followed by 1–3 s of silence, then the word.
- A fixed random seed makes the script produce identical clips every run, so results are reproducible.

## Build

- **You:** record yourself reading 10 lines from `recording_script.md` (Northwind Energy answers: account numbers, yes/no, reason for calling). Real voice beats text-to-speech. Save them in `eval/data/recordings/`. Hiya1's `eval/recording_script.md` can be reused as the starting script.
- **You design** (write it in this ticket under "Design notes" before implementation starts):
  - the manifest columns (file, group, transcript, true_end_ms, notes)
  - where Blocks go (before digits, after "my")
  - the pause lengths
- **Claude writes** `eval/make_data.py`. It loads the recordings, inserts Blocks, repetitions and pauses at your positions, and writes the WAVs plus `eval/data/manifest.csv`.
- **You:** listen to 3 generated clips. Do they sound like what you intended?
- A small set of generated stammered clips is committed for the demo's "sample caller" (ticket 08). Raw recordings and anything large stay git-ignored unless you choose otherwise.

## Design notes (yours)

_To be filled in before implementation._

## Check yourself

- [ ] How is `true_end_ms` calculated for a clip with an inserted Block?
- [ ] Why is a fixed seed important?
- [ ] Why might these clips make a timing-based detector look better than it is?
- [ ] Why include a "fluent with thinking pauses" group?

## Acceptance

- [ ] `manifest.csv` lists every clip with a correct `true_end_ms`.
- [ ] Re-running the script produces identical files.
