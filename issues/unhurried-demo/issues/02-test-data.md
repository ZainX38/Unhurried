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

- **You:** record the 10 lines (in pieces, 26 files) and 4 natural-pause takes from `eval/recording_sprit.md`, covering all four Slots. Real voice beats text-to-speech. Save them with `lines.csv` in `eval/data/recordings/`.
- **You design** (write it in this ticket under "Design notes" before implementation starts):
  - the manifest columns (file, group, transcript, true_end_ms, notes)
  - where Blocks go (before digits, after "my")
  - the pause lengths
- **Claude writes** `eval/make_data.py`. It loads the recordings, inserts Blocks, repetitions and pauses at your positions, and writes the WAVs plus `eval/data/manifest.csv`.
- **You:** listen to 3 generated clips. Do they sound like what you intended?
- A small set of generated stammered clips is committed for the demo's "sample caller" (ticket 08). Raw recordings and anything large stay git-ignored unless you choose otherwise.

## Design notes (yours)

Recording plan: `eval/recording_sprit.md`. Inputs in `eval/data/recordings/`: 26 piece files for 10 lines (`A1`–`A4`, `D1`–`D2`, `R1`–`R2`, `C1`–`C2`), 4 natural-pause takes (`P_A2`, `P_A4`, `P_D1`, `P_R1`), and `lines.csv` (`line, slot, pieces, text`). Slots are `account_number`, `date_of_birth`, `reason` and `confirm`, exactly as `lines.csv` spells them.

### Input format and conversion

- The raw recordings (48 kHz / 44.1 kHz stereo) are converted **once** with ffmpeg by `eval/convert_recordings.py`, to 16 kHz mono 16-bit. The originals move to `eval/data/recordings/originals/` (git-ignored). The converted files are committed so reviewers can rebuild the data without ffmpeg.
- `eval/audio.py` `read_wav` is strict: it raises on anything that isn't 16 kHz mono 16-bit. No resampling in Python and no extra dependency.

### Common processing (all groups)

- **Speech detection.** Use 10 ms frames. A frame is speech when its RMS is above **-45 dBFS** (speech in these files peaks around -25 dBFS). Speech start is the first speech frame and speech end is the end of the last one. Pieces are trimmed to speech with a **30 ms margin** on each side.
- **`true_end_ms`** is always the end of the last speech frame of the final piece (or take), measured from the start of the clip. It uses the same definition in every group.
- **No room tone exists.** The recorder's noise suppression made every non-speech stretch exact digital zero, including the pauses inside the `P_*` takes. So:
  - Inserted silence (gaps, Block silences, padding) is **zeros**, which matches the recordings' own silence, so splices are invisible.
  - Then a **seeded Gaussian noise floor at -60 dBFS RMS** is added over the **whole** clip, in every group. Without it an energy VAD gets perfect digital silence, which no phone line gives. -60 dBFS is well under the -45 dBFS speech threshold.
- **Fades.** A 10 ms fade-in and fade-out on every placed piece and burst, so cuts don't click.
- **Padding lives only in the clips.** Fluent and stammered clips start with 500 ms of lead. Every clip ends **8 s after `true_end_ms`**. 8 s, not 6 s, because the 5 s Ceiling needs room, and so does ticket 05's `PROMPT` at 6 s of silence measured from the VAD's last speech frame. VAD hangover and 32 ms frames push that a little later than `true_end_ms`, so a 6 s tail would cut the `PROMPT` off. The harness (ticket 03) adds no padding of its own.
- **Seed.** `SEED = 2026`. One `random.Random(SEED)` draws every gap, burst and silence in a fixed order (lines in `lines.csv` order, then variants 1–3). Each clip's noise floor uses its own generator seeded from `SEED` and the clip name. Re-running produces byte-identical WAVs and manifest.

### fluent (10 clips)

- Trim each piece, then join them in order with a gap of **150–300 ms** between pieces (whole ms, uniform, seeded).
- `true_end_ms` = the speech end of the last piece.

### stammered (30 clips: 10 lines × 3 variants)

- **Gaps.** The same gaps as that line's fluent clip, so the only difference from fluent is the Block.
- **Block** = **burst** (the first 60–150 ms of the piece, starting at its speech onset) + **1–3 s of silence**, then the piece in full. Burst and silence are whole ms, uniform, seeded, and drawn per variant.
- **Where the Block goes:**
  - **A lines, C2, D lines:** before piece 2, the first digit or date piece.
  - **R1, R2:** before piece 2 ("my last bill", "a payment plan"), where the answer content starts.
  - **C1:** at the very start, right after the 500 ms lead. This deliberately tests a Block before any words.
- `true_end_ms` = fluent `true_end_ms` + burst + Block silence. This is exact, because everything after the Block is only shifted.
- No repetitions in v1.

### pauses (4 clips)

- The `P_*` takes as recorded, with nothing trimmed or edited (they keep their own lead), and the real pauses untouched.
- Zeros are appended so the clip ends 8 s after the detected speech end, then the noise floor is added.
- `true_end_ms` = the detected speech end of the take.

### Manifest (`eval/data/manifest.csv`)

| Column | Meaning |
| --- | --- |
| `file` | clip path relative to `eval/data/`, e.g. `clips/stammered/A1_v2.wav` |
| `group` | `fluent`, `stammered` or `pauses` |
| `line` | source line, e.g. `A1` or `P_A2` |
| `slot` | from `lines.csv`; the eval (ticket 03) starts each Turn with this Slot instead of guessing it from the transcript |
| `transcript` | `text` from `lines.csv` |
| `true_end_ms` | true Turn end in ms from clip start |
| `notes` | for stammered clips: `block_start_ms=…;burst_ms=…;silence_ms=…`. For pauses: `pauses_over_500ms=N`. Empty for fluent |

### Outputs and git

- **Committed:** the converted recordings and `lines.csv` (`eval/data/recordings/`), plus the demo samples.
- **Git-ignored:** `eval/data/recordings/originals/`, `eval/data/clips/` and `eval/data/manifest.csv`. All three are regenerated by `uv run python -m eval.make_data`.
- **Demo samples (ticket 08 sample caller):** `eval/data/demo/` holds `A1_fluent.wav`, `A1_stammered.wav` (variant 1), `P_A2.wav` and a 3-row `manifest.csv` in the same columns. The script writes these too, so they always match a regeneration.

## Check yourself

- [ ] How is `true_end_ms` calculated for a clip with an inserted Block?
- [ ] Why is a fixed seed important?
- [ ] Why might these clips make a timing-based detector look better than it is?
- [ ] Why include a "fluent with thinking pauses" group?

## Acceptance

- [ ] `manifest.csv` lists every clip with a correct `true_end_ms`.
- [ ] Re-running the script produces identical files.
