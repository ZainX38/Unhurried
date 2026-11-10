from dataclasses import dataclass
from enum import Enum

from unhurried.endpointer.completeness import extract_digits, YES_WORDS


class State(Enum):
    GREETING = "GREETING"
    ACCOUNT = "ACCOUNT"
    CONFIRM_ACCOUNT = "CONFIRM_ACCOUNT"
    DOB = "DOB"
    CONFIRM_DOB = "CONFIRM_DOB"
    REASON = "REASON"
    DONE = "DONE"


# Question wording
ASK_ACCOUNT = "Thanks for calling Northwind Energy. Could you tell me your 8-digit account number?"
ASK_DOB = "Thanks. And what's your date of birth?"


@dataclass(frozen=True)
class Reply:
    line: str            # What the bot says next
    expected_slot: str   # "account_number" | "date_of_birth" | "confirm" | "reason" | "" when DONE
    state: State         # The state AFTER this reply


class Dialogue:
    def __init__(self) -> None:
        self.state = State.GREETING
        self.slots: dict[str, str] = {}
        self.retries = 0        # Re pompts used for the current question
        self.pending = ""       # Heard but not yet confirmed, moves into slot on "yes "

    def start(self) -> Reply: 
        # Open call, it greets and asks for accounts number
        self.state = State.ACCOUNT
        self.slots = {}
        self.retries = 0

        return Reply(ASK_ACCOUNT, "account_number", self.state)

    def on_turn(self, text: str) -> Reply:
        # The caller finished speaking
        # Answer depends on the question
        if self.state is State.ACCOUNT:
            self.pending = extract_digits(text)
            self.state = State.CONFIRM_ACCOUNT
            readback = ", ".join(self.pending)          # "45218830" -> "4, 5, 2, 1, 8, 8, 3, 0"
            return Reply(f"I heard {readback}. Is that right?", "confirm", self.state)

        if self.state is State.CONFIRM_ACCOUNT:
            words = text.lower().split()
            if any(w in YES_WORDS for w in words):
                # Confirmed: the number is now trusted, so it moves into slots.
                self.slots["account_number"] = self.pending
                self.pending = ""
                self.retries = 0
                self.state = State.DOB
                return Reply(ASK_DOB, "date_of_birth", self.state)

        raise NotImplementedError(f"no handling for {self.state.name} yet")
    
    def on_keypad(self, digits: str) -> Reply:
        pass