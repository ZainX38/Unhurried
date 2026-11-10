"""One Call, with no networking (ticket 07).

Frames in, events out: VAD -> STT -> Endpointer, and on END the Turn's text goes to
the Dialogue, whose next Prompt sets the Slot the Endpointer waits for.

There is no socket, clock or audio device here, so a whole Call can be tested by
feeding arrays (seam 1). The server only moves bytes and JSON in and out of this.
Events are plain dicts, ready for json.dumps:

    {"type": "transcript", "text": raw, "clean": ...}       only when the text changes
    {"type": "decision", "action": ..., "reason": ..., "t_ms": ...}   every frame
    {"type": "bot", "line": ...}
    {"type": "state", "state": ..., "expected_slot": ..., "slots": {...}}

Cleanup is for display and Slots only: the Endpointer reads the raw text, because
repetitions are evidence of stammering.

No barge-in: frames keep being processed while the bot "speaks".
"""

from __future__ import annotations

from typing import Any, Protocol

import numpy as np

from unhurried.cleanup import clean
from unhurried.endpointer.types import Action, Endpointer
from unhurried.stt import STT
from unhurried.vad import FRAME_MS, FRAME_SAMPLES, is_speech

TAKE_YOUR_TIME = "Take your time, I'm still listening."

Event = dict[str, Any]


class Reply(Protocol):
    line: str
    expected_slot: str
    state: Any   # dialogue.State; sent by name


class Dialogue(Protocol):
    slots: dict[str, str]

    def start(self) -> Reply: ...
    def on_turn(self, text: str) -> Reply: ...
    def on_keypad(self, digits: str) -> Reply: ...


def state_name(state: Any) -> str:
    return getattr(state, "name", str(state))


class Session:
    def __init__(self, endpointer: Endpointer, stt: STT, dialogue: Dialogue) -> None:
        self.endpointer = endpointer
        self.stt = stt
        self.dialogue = dialogue
        self.done = False
        self.t_ms = 0                                   # Call time, from frame count
        self._buffer = np.zeros(0, dtype=np.float32)    # leftover samples < one frame
        self._last_text = ""

    def start(self) -> list[Event]:
        """Greet the caller and ask the first question."""
        return self._apply(self.dialogue.start())

    def feed(self, samples: np.ndarray) -> list[Event]:
        """Any number of 16 kHz float samples; processed in whole 32 ms frames."""
        self._buffer = np.concatenate([self._buffer, np.asarray(samples, dtype=np.float32)])
        events: list[Event] = []
        while len(self._buffer) >= FRAME_SAMPLES and not self.done:
            frame, self._buffer = self._buffer[:FRAME_SAMPLES], self._buffer[FRAME_SAMPLES:]
            events += self._step(frame)
        return events

    def keypad(self, digits: str) -> list[Event]:
        """Keypad digits replace the spoken Turn, in any state."""
        if self.done:
            return []
        return self._apply(self.dialogue.on_keypad(digits))

    def _step(self, frame: np.ndarray) -> list[Event]:
        self.t_ms += FRAME_MS
        speech = is_speech(frame)
        self.stt.feed(frame)
        text = self.stt.transcript()

        events: list[Event] = []
        if text != self._last_text:
            self._last_text = text
            events.append({"type": "transcript", "text": text, "clean": clean(text)})

        decision = self.endpointer.step(speech, FRAME_MS, text)
        events.append({"type": "decision", "action": decision.action.value,
                       "reason": decision.reason, "t_ms": self.t_ms})

        if decision.action is Action.PROMPT:
            events.append({"type": "bot", "line": TAKE_YOUR_TIME})
        elif decision.action is Action.END:
            events += self._apply(self.dialogue.on_turn(clean(text)))
        return events

    def _apply(self, reply: Reply) -> list[Event]:
        """Say the reply and start a new Turn for the Slot it asks for."""
        self.endpointer.reset(reply.expected_slot)
        self.stt.reset()
        self._last_text = ""
        self.done = state_name(reply.state) == "DONE"
        return [
            {"type": "bot", "line": reply.line},
            {"type": "state", "state": state_name(reply.state),
             "expected_slot": reply.expected_slot, "slots": dict(self.dialogue.slots)},
        ]
