# 06: Speech-to-text (Vosk)

**Status:** ready-for-agent (plumbing, Recipe B)
**Blocked by:** 03
**When:** Mon, 1.5–2 h

**What to build:** Real streaming transcripts in the harness, so the Endpointer sees the same imperfect words a live system would, with results shown side by side against timing-only.

## Understand

- Until now the harness used the manifest's transcripts. Real STT makes it honest: the transcripts now contain the mistakes a live system would see.
- **Vosk** (ADR 0002): local, free and offline, with no API key. It **streams partial words** as audio arrives, so there's no re-transcribing at each pause and no added delay. It transcribes repetitions literally instead of quietly deleting them. A streaming cloud API is mentioned as "next".
- Vosk has its own built-in silence segmentation. Its "final" results are treated only as transcript chunks and **never as Turn ends**: only our Endpointer decides.
- Adapter pattern: one small `stt.py` interface (feed audio frames, read the Turn's transcript so far, reset per Turn) so providers can be swapped without touching the Endpointer. That's a seam.

## Build

- A model download script for the small English Vosk model (git-ignored).
- The STT adapter, plus a harness flag `--stt vosk` that passes the partial transcript into each frame.
- Day-one checks (**do these yourself**): transcribe 3 stammered clips.
  - How does Vosk write digits ("four" vs "4", "oh")?
  - What does it output for repetitions and for sound repetitions like "m-m-my" (dictionary words only)?
  - Does it invent words during Blocks?

  Note the answers in `NOTES.md`; they affect tickets 04, 05 and 09.
- Re-run the harness with transcripts. Compare the results to timing-only and add both rows to `results.md`.

## Check yourself

- [ ] Why does streaming STT add less delay than re-transcribing at every pause, and where would that delay show up?
- [ ] Why must Vosk's own endpointing never be treated as a Turn end?
- [ ] What did Vosk do to repetitions and digits in your clips?
- [ ] What's the benefit of the `stt.py` adapter?

## Acceptance

- [ ] The harness runs with real transcripts.
- [ ] `results.md` shows timing-only and with-transcripts side by side.
