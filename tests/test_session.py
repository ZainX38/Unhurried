"""Session tests (ticket 07): whole Calls driven by arrays, with no socket and no Vosk."""

from dataclasses import dataclass, field

import numpy as np

from unhurried.endpointer.baseline import Baseline
from unhurried.endpointer.patient import PROMPT_MS, Patient
from unhurried.session import TAKE_YOUR_TIME, Session
from unhurried.vad import FRAME_MS, FRAME_SAMPLES

LOUD = np.full(FRAME_SAMPLES, 0.1, dtype=np.float32)    # -20 dBFS: speech
QUIET = np.zeros(FRAME_SAMPLES, dtype=np.float32)       # silence


def frames(frame: np.ndarray, ms: int) -> np.ndarray:
    return np.tile(frame, ms // FRAME_MS)


class FakeSTT:
    """Each Turn "hears" the next scripted text once speech has been fed."""

    def __init__(self, turns: list[str]) -> None:
        self.turns = list(turns)
        self.resets = 0
        self.reset()

    def reset(self) -> None:
        self.resets += 1
        self.text = self.turns.pop(0) if self.turns else ""
        self.heard = False

    def feed(self, frame: np.ndarray) -> None:
        self.heard = self.heard or float(np.abs(frame).max()) > 0.01

    def transcript(self) -> str:
        return self.text if self.heard else ""


@dataclass(frozen=True)
class Reply:
    line: str
    expected_slot: str
    state: str


@dataclass
class StubDialogue:
    """Answers with a fixed list of replies; records what it was given."""
    replies: list[Reply]
    turns: list[str] = field(default_factory=list)
    keypad_digits: list[str] = field(default_factory=list)
    slots: dict[str, str] = field(default_factory=dict)

    def start(self) -> Reply:
        return self.replies.pop(0)

    def on_turn(self, text: str) -> Reply:
        self.turns.append(text)
        return self.replies.pop(0)

    def on_keypad(self, digits: str) -> Reply:
        self.keypad_digits.append(digits)
        return self.replies.pop(0)


GREETING = Reply("Hello. What's your account number?", "account_number", "ACCOUNT")
READ_BACK = Reply("I have 4 5 2 1 8 8 3 0. Is that right?", "confirm", "CONFIRM_ACCOUNT")
BYE = Reply("Thanks, goodbye.", "", "DONE")


class SpyEndpointer(Baseline):
    def __init__(self) -> None:
        self.slots: list[str] = []
        super().__init__()

    def reset(self, expected_slot: str = "") -> None:
        self.slots.append(expected_slot)
        super().reset(expected_slot)


def of(events, kind):
    return [e for e in events if e["type"] == kind]


def test_start_says_the_greeting_and_waits_for_the_account_number() -> None:
    endpointer = SpyEndpointer()
    events = Session(endpointer, FakeSTT([]), StubDialogue([GREETING])).start()
    assert of(events, "bot") == [{"type": "bot", "line": GREETING.line}]
    assert of(events, "state")[0]["expected_slot"] == "account_number"
    assert endpointer.slots[-1] == "account_number"


def test_end_passes_the_transcript_to_the_dialogue_and_resets_for_the_next_slot() -> None:
    endpointer, stt = SpyEndpointer(), FakeSTT(["", "four five two one eight eight three oh"])
    dialogue = StubDialogue([GREETING, READ_BACK])
    session = Session(endpointer, stt, dialogue)
    session.start()

    events = session.feed(np.concatenate([frames(LOUD, 1600), frames(QUIET, 1000)]))

    assert dialogue.turns == ["four five two one eight eight three oh"]
    assert [e["action"] for e in of(events, "decision")].count("END") == 1
    assert of(events, "bot")[-1]["line"] == READ_BACK.line
    assert endpointer.slots[-1] == "confirm"
    assert of(events, "transcript")[0]["text"] == "four five two one eight eight three oh"


def test_feed_accepts_chunks_that_are_not_whole_frames() -> None:
    session = Session(Baseline(), FakeSTT([]), StubDialogue([GREETING]))
    session.start()
    assert session.feed(QUIET[:300]) == []
    assert len(of(session.feed(QUIET[:300]), "decision")) == 1
    assert session.t_ms == FRAME_MS


def test_patient_prompt_says_take_your_time_without_changing_the_dialogue() -> None:
    dialogue = StubDialogue([GREETING])
    session = Session(Patient(), FakeSTT(["", "four five two one"]), dialogue)
    session.start()

    events = session.feed(np.concatenate([frames(LOUD, 960), frames(QUIET, PROMPT_MS + 320)]))

    assert of(events, "bot") == [{"type": "bot", "line": TAKE_YOUR_TIME}]
    assert dialogue.turns == []


def test_keypad_goes_to_the_dialogue_and_starts_a_new_turn() -> None:
    endpointer, dialogue = SpyEndpointer(), StubDialogue([GREETING, READ_BACK])
    session = Session(endpointer, FakeSTT([]), dialogue)
    session.start()

    events = session.keypad("45218830")

    assert dialogue.keypad_digits == ["45218830"]
    assert of(events, "state")[0]["state"] == "CONFIRM_ACCOUNT"
    assert endpointer.slots[-1] == "confirm"


def test_a_whole_call_reaches_done_and_then_ignores_frames() -> None:
    turn = np.concatenate([frames(LOUD, 960), frames(QUIET, 1000)])
    dialogue = StubDialogue([GREETING, READ_BACK, BYE])
    session = Session(Baseline(), FakeSTT(["", "four five two one eight eight three oh", "yes"]), dialogue)
    session.start()

    session.feed(np.concatenate([turn, turn]))

    assert dialogue.turns == ["four five two one eight eight three oh", "yes"]
    assert session.done
    assert session.feed(turn) == []
    assert session.keypad("1") == []
