from unhurried.endpointer.types import Action, Decision

class Baseline:
    def __init__(self, threshold_ms: int = 700) -> None:
        self.threshold_ms = threshold_ms
        if threshold_ms <= 0:
            raise ValueError("threshold_ms must be positive")

        # Calls reset() as state needs to be cleared for each Turn
        self.reset()

    # Resets the state. The Baseline only looks at silence, so it ignores the Slot.
    def reset(self, expected_slot: str = "") -> None:
        self.silence_ms = 0
        self.heard_speech = False
            

    def step(self, is_speech: bool, frame_ms: int, transcript: str | None) -> Decision:
        if self.silence_ms >= self.threshold_ms:
            return Decision(Action.END, f"already ended: silence {self.silence_ms}ms >= {self.threshold_ms}ms")

        # Speaking: Speech is detected, so restart silence count
        if is_speech:
            self.heard_speech = True
            self.silence_ms = 0
            return Decision(Action.CONTINUE, "speech")

        # Waiting: Silence before speech, heard_speech = False
        if not self.heard_speech:
            return Decision(Action.CONTINUE, "no speech yet")

        # Spoke and went quiet: If silence after speech, count it and compare it with the threshold
        self.silence_ms += frame_ms
        if self.silence_ms >= self.threshold_ms:
            # If silence is greater or equal to 700ms, return Decision
            return Decision(Action.END, f"silence {self.silence_ms}ms >= {self.threshold_ms}ms")

        return Decision(Action.CONTINUE, f"silence {self.silence_ms}ms < {self.threshold_ms}ms")


