import pytest

from unhurried.endpointer.baseline import Baseline
from unhurried.endpointer.types import Action, Decision, Endpointer

FRAME_MS = 32

# HELPERS
def speech(b: Baseline, frames: int = 1) -> list[Decision]:
    """Feed `frames` speech frames and return every decision."""
    return [b.step(True, FRAME_MS, "") for _ in range(frames)]
 
 
def silence(b: Baseline, frames: int) -> list[Decision]:
    """Feed `frames` silent frames and return every decision."""
    return [b.step(False, FRAME_MS, "") for _ in range(frames)]
 
 
def actions(decisions: list[Decision]) -> set[Action]:
    return {d.action for d in decisions}


# ACTUALS TESTS

def test_satisfies_endpointer_protocol() -> None:
    endpointer: Endpointer = Baseline()  # mypy/pyright flag this if signatures drift
    assert endpointer.step(True, FRAME_MS, "").action is Action.CONTINUE
 
 
@pytest.mark.parametrize("frames", [18, 19])  # 576 ms and 608 ms
def test_short_silence_continues(frames: int) -> None:
    b = Baseline()
    speech(b)
    assert actions(silence(b, frames)) == {Action.CONTINUE}
 
 
def test_just_under_threshold_continues() -> None:
    b = Baseline()
    speech(b)
    decisions = silence(b, 21)  # 672 ms, still under 700
    assert actions(decisions) == {Action.CONTINUE}
    assert b.silence_ms == 672
 
 
def test_threshold_hit_ends() -> None:
    b = Baseline()
    speech(b)
    decisions = silence(b, 22)  # 704 ms
    assert decisions[-1].action is Action.END
 
 
def test_first_end_is_frame_22_exactly() -> None:
    b = Baseline()
    speech(b)
    decisions = silence(b, 22)
    assert decisions[20].action is Action.CONTINUE  # 21st silent frame, 672 ms
    assert decisions[21].action is Action.END       # 22nd silent frame, 704 ms
    assert all(d.action is Action.CONTINUE for d in decisions[:21])
 
 
def test_speech_resets_the_silence_count() -> None:
    b = Baseline()
    decisions = speech(b) + silence(b, 20)  # 640 ms, under 700
    decisions += speech(b)                  # caller carries on: count goes back to 0
    decisions += silence(b, 20)             # another 640 ms, still under 700
    assert actions(decisions) == {Action.CONTINUE}
 
 
def test_silence_only_never_ends() -> None:
    b = Baseline()
    decisions = silence(b, 150)  # 4.8 s of silence before any speech
    assert actions(decisions) == {Action.CONTINUE}
    assert decisions[-1].reason == "no speech yet"
 
 
def test_reason_string_shows_silence_and_threshold() -> None:
    b = Baseline()
    speech(b)
    end = silence(b, 22)[-1]
    assert "704ms" in end.reason
    assert "700ms" in end.reason
 
 
def test_custom_threshold() -> None:
    b = Baseline(threshold_ms=320)
    speech(b)
    decisions = silence(b, 10)  # 10 x 32 = 320 ms, exactly the threshold
    assert decisions[8].action is Action.CONTINUE  # 288 ms
    assert decisions[9].action is Action.END       # 320 ms: >= means END on the boundary
 
 
def test_reset_clears_state() -> None:
    b = Baseline()
    speech(b)
    assert silence(b, 22)[-1].action is Action.END
    b.reset()
    assert b.silence_ms == 0
    assert b.heard_speech is False
    decisions = silence(b, 50)  # heard_speech cleared, so silence is not timed again
    assert actions(decisions) == {Action.CONTINUE}
 
 
def test_end_is_sticky_until_reset() -> None:
    b = Baseline()
    speech(b)
    silence(b, 22)
    assert speech(b)[0].action is Action.END       # speech after END does not reopen the turn
    assert silence(b, 5)[-1].action is Action.END
 
 
def test_threshold_must_be_positive() -> None:
    with pytest.raises(ValueError):
        Baseline(threshold_ms=0)

def test_reset_takes_the_slot_and_ignores_it() -> None:
    b = Baseline()
    speech(b)
    silence(b, 10)
    b.reset("account_number")  # Endpointer protocol: reset(expected_slot)
    # State cleared: silence before any speech never ends the Turn.
    assert actions(silence(b, 40)) == {Action.CONTINUE}
    speech(b)
    assert silence(b, 22)[-1].action is Action.END  # same 700 ms rule whatever the Slot
