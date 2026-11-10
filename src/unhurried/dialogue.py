from dataclasses import dataclass, field
from enum import Enum

from unhurried.endpointer.completeness import extract_digits, FILLERS, NEGATIONS, YES_WORDS, ACCOUNT_DIGITS

class State(Enum):
    GREETING = "GREETING"
    ACCOUNT = "ACCOUNT"
    CONFIRM_ACCOUNT = "CONFIRM_ACCOUNT"
    DOB = "DOB"
    CONFIRM_DOB = "CONFIRM_DOB"
    REASON = "REASON"
    DONE = "DONE"


# Question wording
GREETING = "Thanks for calling Northwind Energy."
ASK_ACCOUNT = "Could you tell me your 8-digit account number?"
ASK_DOB = "Thanks. And what's your date of birth?"
ASK_ACCOUNT_AGAIN = "No rush. Could you tell me your 8-digit account number again?"
OFFER_KEYPAD_ACCOUNT = "You can also type your account number on the keypad."
ASK_DOB_CONFIRM = "I heard {}. Is that right?"


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
        self.pending = ""

        return Reply(f"{GREETING} {ASK_ACCOUNT}", "account_number", self.state)

    def _failed(self, reprompt: str, fallback: str, slot: str) -> Reply:
        # A failed answer: re-prompt once, then offer the fallback
        #Stays in the same state
        self.retries += 1
        line = reprompt if self.retries == 1 else fallback
        return Reply(line, slot, self.state)

    def _read_back_account(self) -> Reply:
        # Read the pending number back and ask the caller to confirm it
        self.state = State.CONFIRM_ACCOUNT
        self.retries = 0

        readback = ", ".join(self.pending)          # "45218830" -> "4, 5, 2, 1, 8, 8, 3, 0"
        return Reply(f"I heard {readback}. Is that right?", "confirm", self.state)

    def on_turn(self, text: str) -> Reply:
        # The caller finished speaking
        # Answer depends on question
        if self.state is State.ACCOUNT:
            digits = extract_digits(text)

            if len(digits) == ACCOUNT_DIGITS:
                self.pending = digits
                return self._read_back_account()

            # Wrong length: don't read back a number we know is wrong.
            return self._failed(ASK_ACCOUNT_AGAIN, OFFER_KEYPAD_ACCOUNT, "account_number")

        if self.state is State.CONFIRM_ACCOUNT:
            words = [w.strip(",.") for w in text.lower().split()]

            # "No" wins as "no that's not right" contains "right" but is not a yes
            if any(w in NEGATIONS for w in words):
                digits = extract_digits(text)

                if len(digits) == ACCOUNT_DIGITS:
                    self.pending = digits
                    return self._read_back_account()
                if digits:
                    # Some digits put the wrong count so ask for the whole number again
                    self.pending = ""
                    self.retries = 0
                    self.state = State.ACCOUNT
                    return Reply(ASK_ACCOUNT_AGAIN, "account_number", self.state)
                else:
                    # A plain "no": the number was wrong, so ask for it again
                    # Not a failed answer, so it doesn't count towards retries
                    self.pending = ""
                    self.retries = 0
                    self.state = State.ACCOUNT
                    return Reply(ASK_ACCOUNT, "account_number", self.state)

            elif any(w in YES_WORDS for w in words):
                # Confirmed: the number is now trusted, so it moves into slots.
                self.slots["account_number"] = self.pending
                self.pending = ""
                self.retries = 0
                self.state = State.DOB
                return Reply(ASK_DOB, "date_of_birth", self.state)

            # Neither yes nor no: reprompt, saying what we need and what we're confirming
            # Keep the pending number because the caller didn't say no
            self.retries += 1
            readback = ", ".join(self.pending)
            return Reply(
                f"Just to check, is your account number {readback}? Please say yes or no.",
                "confirm",
                self.state,
            )

        if self.state is State.DOB:
            # Read back the caller's own words, not a parsed date: if the speech
            # recogniser misheard ("fortieth" for "fourteenth"), the caller can catch it.
            words = text.lower().split()
            while words and words[0] in FILLERS:     # drop leading "um", "huh"
                words.pop(0)
            self.pending = " ".join(words)
            self.state = State.CONFIRM_DOB
            self.retries = 0
            return Reply(ASK_DOB_CONFIRM.format(self.pending), "confirm", self.state)

        raise NotImplementedError(f"no handling for {self.state.name} yet")
    
    def on_keypad(self, digits: str) -> Reply:
        # Typed digits at the account question take the same path as speech
        # The same 8-digit check, the same read-back and the same retries
        if self.state is State.ACCOUNT:
            return self.on_turn(digits)

        raise NotImplementedError(f"no keypad handling for {self.state.name} yet")