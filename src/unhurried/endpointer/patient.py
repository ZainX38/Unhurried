"""Patient endpointer: like Baseline, but how long it waits depends on the words.

- COMPLETE answer (e.g. 8/8 digits): end after complete_ms, all bonuses dropped.
- INCOMPLETE answer (e.g. 4/8 digits): never end on silence; prompt once at 6 s.
- UNSURE (free text, no transcript): base_ms plus bonuses for recent stammering,
  capped at CEILING_MS.

Word rules live only in completeness(); this class only decides how patient to be.
Disfluency here only ever makes the system MORE patient. It is never a risk signal.
"""

from unhurried.endpointer.types import Action, Decision
from unhurried.endpointer.completeness import DIGIT_WORDS, Status, completeness

PROMPT_MS = 6000              # incomplete answer this long in silence -> gentle prompt
CEILING_MS = 5000             # patience never grows beyond this
REPETITION_BONUS_MS = 1000    # extra patience after a repetition ("my my", "m-m-my")
REPETITION_WINDOW_MS = 8000   # how long that bonus lasts after the repetition was heard
CALL_MEMORY_BONUS_MS = 500    # extra patience in later turns if the caller stammered earlier

# Slots with a fixed format: speech with no words yet means the answer hasn't started.
FORMATTED_SLOTS = {"account_number", "date_of_birth"}


def is_restart(word: str) -> bool:
    """A hyphenated restart: an earlier piece starts the final piece.
    "m-m-my", "i-it's" and "4-4-4521" are restarts; "well-known" and "t-shirt" are not."""
    pieces = word.split("-")
    last = pieces[-1]
    return bool(last) and any(p and last.startswith(p) for p in pieces[:-1])


def is_digit_word(word: str) -> bool:
    """"eight", "oh" or "8": doubled digits are normal in numbers ("8 8"), not a stammer."""
    return word in DIGIT_WORDS or word.isdigit()


def count_repetitions(transcript: str) -> int:
    """Simple repetition count until clean-up exists: the same word twice in a row
    ("my my") plus hyphenated restarts ("m-m-my" counts once). Doubled digits are
    skipped, because account numbers often contain them."""
    words = transcript.lower().split()
    repeats = sum(1 for a, b in zip(words, words[1:]) if a == b and not is_digit_word(a))
    restarts = sum(1 for w in words if is_restart(w))
    return repeats + restarts


class Patient:
    def __init__(self, base_ms: int = 700, complete_ms: int = 700) -> None:
        if base_ms <= 0 or complete_ms <= 0:
            raise ValueError("base_ms and complete_ms must be positive")
        # Settings: never change during a call.
        self.base_ms = base_ms
        self.complete_ms = complete_ms
        # Call memory: kept across turns. Only set from real evidence (a repetition).
        self.stammered_this_call = False
        # Turn state.
        self.reset("")

    def reset(self, expected_slot: str) -> None:
        """Start a new turn: store the slot, clear turn state, KEEP call memory."""
        # A repetition in the turn that just finished counts for the rest of the call.
        if getattr(self, "repeated_this_turn", False):
            self.stammered_this_call = True
        self.expected_slot = expected_slot
        self.heard_speech = False
        self.silence_ms = 0
        self.turn_ms = 0                     # time since the turn started
        self.repetitions_seen = 0
        self.last_repetition_ms: int | None = None
        self.repeated_this_turn = False
        self.prompted = False                # PROMPT only once per turn
        self.end_reason: str | None = None   # END is sticky until reset()

    def step(self, is_speech: bool, frame_ms: int, transcript: str | None) -> Decision:
        self.turn_ms += frame_ms
        if self.end_reason is not None:
            return Decision(Action.END, f"already ended: {self.end_reason}")

        # Watch for NEW repetitions on every frame. The transcript is cumulative, so
        # only an increase in the count starts the window again.
        if transcript is not None:
            reps = count_repetitions(transcript)
            if reps > self.repetitions_seen:
                self.repetitions_seen = reps
                self.last_repetition_ms = self.turn_ms
                self.repeated_this_turn = True

        # 1. Speech: the caller is talking, so restart the silence count.
        if is_speech:
            self.heard_speech = True
            self.silence_ms = 0
            return Decision(Action.CONTINUE, "speech")

        # 2. Silence before the caller has said anything: don't time it.
        if not self.heard_speech:
            return Decision(Action.CONTINUE, "no speech yet")

        # 3. Silence after speech: what do the words say?
        self.silence_ms += frame_ms
        if transcript is None:
            status, clue = Status.UNSURE, "no transcript (timing only)"
        elif transcript.strip() == "" and self.expected_slot in FORMATTED_SLOTS:
            status, clue = Status.INCOMPLETE, "speech heard, no words yet"
        else:
            status, clue = completeness(transcript, self.expected_slot)

        # d. Incomplete: never end on silence. Prompt once, then keep listening.
        if status is Status.INCOMPLETE:
            if self.silence_ms >= PROMPT_MS and not self.prompted:
                self.prompted = True
                return Decision(Action.PROMPT, f"still incomplete after {PROMPT_MS // 1000} s: {clue}")
            return Decision(Action.CONTINUE, f"silence {self.silence_ms}ms, incomplete: {clue}")

        # e./f. How patient to be.
        if status is Status.COMPLETE:
            patience = self.complete_ms
            clue = f"complete: {clue}"
        else:
            patience, bonuses = self.base_ms, []
            if self.last_repetition_ms is not None and self.turn_ms - self.last_repetition_ms <= REPETITION_WINDOW_MS:
                patience += REPETITION_BONUS_MS
                bonuses.append(f"+{REPETITION_BONUS_MS} repetition")
            if self.stammered_this_call:
                patience += CALL_MEMORY_BONUS_MS
                bonuses.append(f"+{CALL_MEMORY_BONUS_MS} stammered earlier in call")
            if patience > CEILING_MS:
                patience = CEILING_MS
                bonuses.append(f"capped at {CEILING_MS}")
            clue = f"unsure: {clue}" + (f" ({', '.join(bonuses)})" if bonuses else "")

        # g. Compare silence with patience.
        if self.silence_ms >= patience:
            self.end_reason = f"silence {self.silence_ms}ms >= patience {patience}ms: {clue}"
            return Decision(Action.END, self.end_reason)
        return Decision(Action.CONTINUE, f"silence {self.silence_ms}ms < patience {patience}ms: {clue}")