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
    # Gets called every frame (32ms)
    def step(self, is_speech: bool, frame_ms: int, transcript: str) -> Decision:
        ...

    # it resets the Turns for each prompt in the call. It basically clears the state for the new turn
    def reset(self) -> None:
        ...




