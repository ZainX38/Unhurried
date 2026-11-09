from enum import Enum
from dataclasses import dataclass
from typing import Protocol

# Defines the only Actions the Endpointer can ever take
class Action(Enum):
    CONTINUE = "CONTINUE"   # Keeps listening
    END = "END"             # Turn is over
    PROMPT = "PROMPT"       # Gently say take your time and keep listening

# Decision is a fact about a frame. frozen=True makes sure it doesn't change
@dataclass(frozen=True)
class Decision:
    action: Action
    reason: str     # For debugging purposes, to see the reason of the action. It will be used to show live in demo


# Protocol used as it defines what methods an object should have
class Endpointer(Protocol):
    # Gets called every frame (32ms).
    # transcript is what the STT has heard so far this Turn. "" = STT running but nothing heard yet;
    # None = no STT at all (timing-only), so completeness must not be used.
    def step(self, is_speech: bool, frame_ms: int, transcript: str | None) -> Decision:
        ...

    # Called before each Turn with the Slot the bot just asked for. It clears the Turn's state
    # (an endpointer may keep call-level memory across Turns).
    def reset(self, expected_slot: str) -> None:
        ...




