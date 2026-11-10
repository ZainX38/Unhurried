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
ASK_REASON = "And what are you calling about today?"

# Keywords for each reason for calling. Matched as whole words or phrases in the
# transcript; the first intent with a match wins.
INTENTS: dict[str, set[str]] = {
    "billing": {"bill", "billing", "payment", "pay", "charge", "charged", "direct debit", "refund"},
    "moving home": {"moving home", "moving house", "moving out", "move", "moving"},
    "meter reading": {"meter reading", "meter", "reading"},
    "power cut": {"power cut", "no power", "outage", "electricity's off"},
}

CLOSING = {
    "billing": "Thanks, I'll put you through to our billing team.",
    "moving home": "Thanks, I'll put you through to our home moves team.",
    "meter reading": "Thanks, I'll put you through to our meter readings team.",
    "power cut": "Thanks, I'll put you through to our power cut team.",
}

HAND_OVER = "Let me put you through to someone who can help."
OFFER_KEYPAD_CONFIRM = "You can also press 1 for yes or 2 for no."

def find_intent(text: str) -> str | None:
    # First intent whose keyword appears as a whole word or phrase in the text
    padded = f" {' '.join(text.lower().split())} "   # Spaces at both ends, means whole words only

    for intent, keywords in INTENTS.items():
        if any(f" {k} " in padded for k in keywords):
            return intent
        
    return None


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
        # A failed answer: re prompt once, then offer the fallback, then hand over
        # The caller is never stuck in a loop
        self.retries += 1

        if self.retries == 1:
            return Reply(reprompt, slot, self.state)
        
        if self.retries == 2:
            return Reply(fallback, slot, self.state)
        
        self.slots["intent"] = "other"
        self.state = State.DONE

        return Reply(HAND_OVER, "", self.state)

    def _read_back_account(self) -> Reply:
        # Read the pending number back and ask the caller to confirm it
        self.state = State.CONFIRM_ACCOUNT
        self.retries = 0

        readback = ", ".join(self.pending)          # "45218830" -> "4, 5, 2, 1, 8, 8, 3, 0"

        return Reply(f"I heard {readback}. Is that right?", "confirm", self.state)

    def _answer(self, text: str) -> str | None:
        # 'yes', 'no' or None. 'No' wins: "no that's not right" contains "right" 
        words = [w.strip(",.") for w in text.lower().split()]

        if any(w in NEGATIONS for w in words):
            return "no"
        
        if any(w in YES_WORDS for w in words):
            return "yes"
        
        return None

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
            readback = ", ".join(self.pending)
            
            return self._failed(
                f"Just to check, is your account number {readback}? Please say yes or no.",
                OFFER_KEYPAD_CONFIRM, "confirm",
            )

        if self.state is State.DOB:
            # Read back the caller's own words, not a parsed date
            # If the speech recogniser misheard ("fortieth" for "fourteenth"), the caller can catch it
            words = text.lower().split()

            while words and words[0] in FILLERS:     # Drop leading "um", "huh"
                words.pop(0)

            if not words:
                # Only fillers: nothing to read back yet
                return self._failed("No rush. What's your date of birth?",
                                    "Take your time. Just say the day, month and year.",
                                    "date_of_birth")
            
            self.pending = " ".join(words)
            self.state = State.CONFIRM_DOB
            self.retries = 0

            return Reply(ASK_DOB_CONFIRM.format(self.pending), "confirm", self.state)

        if self.state is State.CONFIRM_DOB:
            answer = self._answer(text)

            if answer == "yes":
                self.slots["date_of_birth"] = self.pending
                self.pending = ""
                self.retries = 0
                self.state = State.REASON

                return Reply(ASK_REASON, "reason", self.state)
            
            if answer == "no":
                # The date was wrong: ask for it again
                self.pending = ""
                self.retries = 0
                self.state = State.DOB

                return Reply(ASK_DOB, "date_of_birth", self.state)

            # Neither yes nor no: re prompt with what we're confirming
            return self._failed(
                f"Just to check, is your date of birth {self.pending}? Please say yes or no.",
                OFFER_KEYPAD_CONFIRM, "confirm",
            )
                
        if self.state is State.REASON:
            intent = find_intent(text)

            if intent is not None:
                self.slots["intent"] = intent
                self.state = State.DONE

                return Reply(CLOSING[intent], "", self.state)

            # No keyword matched: hand over to a person instead of guessing
            self.slots["intent"] = "other"
            self.state = State.DONE

            return Reply("Thanks, I'll put you through to someone who can help.", "", self.state)

        raise NotImplementedError(f"no handling for {self.state.name} yet")
    
    def on_keypad(self, digits: str) -> Reply:
        # Typed digits take the same path as speech in every state
        # At a read-back, 1 means yes and 2 means no
        # Call is over at DONE
        if self.state is State.DONE:
            raise RuntimeError("call is over")
        
        if self.state in (State.CONFIRM_ACCOUNT, State.CONFIRM_DOB):
            digits = {"1": "yes", "2": "no"}.get(digits, digits)

        return self.on_turn(digits)