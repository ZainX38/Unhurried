# 08: Frontend

**Status:** ready-for-agent (plumbing, Recipe B)
**Blocked by:** 07
**When:** Tue, 2–3 h (Tuesday checkpoint)

**What to build:** A browser call to Northwind Energy, by mic or sample caller, with a Baseline / Unhurried toggle that shows the same Call failing and then succeeding, and a live "why it's waiting" panel.

## Understand

- **Mic capture:** the browser's `getUserMedia` gives raw audio, usually at 44.1 or 48 kHz. An AudioWorklet (a small script on the audio thread) resamples it to 16 kHz PCM16 and cuts 512-sample frames to send over the WebSocket.
- **Speech synthesis:** the browser's built-in `speechSynthesis` speaks the bot's replies. It's free and needs no setup; voices vary by OS.
- **Echo:** if the mic hears the bot's voice, the system thinks the caller is talking. Mute outgoing frames while the bot speaks and turn on `echoCancellation`.
- **The toggle is the demo:** the same Call fails in Baseline mode (cut off mid-Block) and succeeds in Unhurried mode. The "why it's waiting" panel shows your reason strings live.

## Build

- UI: call button, Baseline/Unhurried toggle, keypad (always visible), raw transcript, reason panel, bot reply text.
- A **sample caller** option that streams a committed WAV (one of your Recorded Turns with inserted Blocks, from ticket 02) instead of the mic, so the demo is reliable and nobody needs to stammer on cue. Piper TTS callers are "next steps".
- Test in Chrome with headphones, then with your own voice, pausing mid-account-number.

## Check yourself

- [ ] Why resample to 16 kHz in the browser?
- [ ] What causes echo, and how do you prevent it?
- [ ] Why include a sample caller as well as the mic?
- [ ] What exactly does the reason panel show, and where does it come from?

## Acceptance

- [ ] A full Call works in the browser with your voice.
- [ ] The toggle shows the Baseline failing and Unhurried succeeding on the sample caller.
