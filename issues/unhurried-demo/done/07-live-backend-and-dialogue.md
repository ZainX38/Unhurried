# 07: Live backend and dialogue

**Status:** ready-for-agent (plumbing, Recipe B; start with a short re-grill)
**Blocked by:** 05, 06
**When:** Tue, 3 h

**What to build:** A whole Call that works end to end without a browser. A WAV streamed into the server goes through the greeting, account number, Read-back, reason and confirmation, driven by your Endpointer and Completeness.

## Understand

- **WebSocket:** a connection that stays open, so the browser can stream audio frames to the server and the server can push events back (transcript, decision, bot reply). Normal HTTP is one request and one response, which is too slow for live audio.
- **Session:** one object per Call. It receives frames, runs VAD → STT → your Endpointer, and returns events. It has no networking code, so a whole Call can be tested without a socket (seam 1).
- **Dialogue state machine:** GREETING → ACCOUNT → REASON → CONFIRM → DONE. Each state sets `expected_slot` for Completeness (ACCOUNT → 8 digits, CONFIRM → yes/no).
- **Read-back** ("I have 4, 5, 2, 1, 8, 8, 3, 0. Is that right?") is the safety net: the caller confirms or says "no, it's…".
- **No loops:** at most one patient Re-prompt per Slot, then offer the keypad. Never "Sorry, I didn't catch that" twice.
- **Event loop:** FastAPI runs async. STT work runs in a thread (`asyncio.to_thread`) so it doesn't block other work.

## Build

- Claude writes the dialogue, session, VAD and server modules (Recipe B). Dialogue tests:
  - greeting → asks for the account number
  - 8 digits → moves to REASON
  - "no, it's…" at CONFIRM → back to ACCOUNT
  - keypad digits accepted in any state
- Session tests drive whole Calls with scripted frames and transcripts, with no socket.
- Test without a browser: a script that streams a WAV through the WebSocket and prints the events.

## Check yourself

- [ ] Trace one frame from the WebSocket to an Endpointer decision.
- [ ] Why does the session have no networking code?
- [ ] How does the dialogue state change what the Endpointer waits for?
- [ ] Why run STT in a thread?

## Acceptance

- [ ] A WAV streamed into the server completes the whole Call: greeting → account → reason → confirm.
