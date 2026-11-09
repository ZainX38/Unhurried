"""Tests for the Patient endpointer (ticket 05).

Frames are 32 ms, so silence thresholds land on the first frame at or past them:
700 ms -> 22 frames (704), 400 ms -> 13 (416), 1700 ms -> 54 (1728), 6000 ms -> 188 (6016).
"""

import pytest

from unhurried.endpointer.patient import (
    CEILING_MS, PROMPT_MS, Patient, count_repetitions, is_restart,
)
from unhurried.endpointer.types import Action, Decision, Endpointer

FRAME_MS = 32
ACCOUNT_4 = "my account number is 4 5 2 1"
ACCOUNT_8 = "my account number is 4 5 2 7 3 6 1 0"   # no doubled digit
REASON = "i want to set up a payment plan"            # free text: UNSURE


# --- helpers ---------------------------------------------------------------------------

def turn(slot: str, base_ms: int = 700, complete_ms: int = 700) -> Patient:
    p = Patient(base_ms, complete_ms)
    p.reset(slot)
    return p


def speech(p: Patient, transcript: str | None, frames: int = 5) -> list[Decision]:
    return [p.step(True, FRAME_MS, transcript) for _ in range(frames)]


def silence(p: Patient, transcript: str | None, frames: int) -> list[Decision]:
    return [p.step(False, FRAME_MS, transcript) for _ in range(frames)]


def first_end(decisions: list[Decision]) -> int | None:
    """Silent frames until the first END (1-based), or None."""
    return next((i + 1 for i, d in enumerate(decisions) if d.action is Action.END), None)


def frames_for(ms: int) -> int:
    return -(-ms // FRAME_MS)  # first frame whose silence reaches ms


# --- protocol ----------------------------------------------------------------------------

def test_satisfies_endpointer_protocol() -> None:
    endpointer: Endpointer = Patient()
    endpointer.reset("account_number")
    assert endpointer.step(True, FRAME_MS, "").action is Action.CONTINUE


@pytest.mark.parametrize("kwargs", [{"base_ms": 0}, {"complete_ms": -1}])
def test_rejects_non_positive_settings(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        Patient(**kwargs)


# --- COMPLETE: as fast as the Baseline ------------------------------------------------------

def test_fluent_complete_answer_ends_at_700ms() -> None:
    p = turn("account_number")
    speech(p, ACCOUNT_8)
    decisions = silence(p, ACCOUNT_8, 40)
    assert first_end(decisions) == frames_for(700)
    assert "8/8 digits" in decisions[frames_for(700) - 1].reason


def test_complete_ms_400_ends_sooner() -> None:
    p = turn("account_number", complete_ms=400)
    speech(p, ACCOUNT_8)
    assert first_end(silence(p, ACCOUNT_8, 40)) == frames_for(400)


def test_complete_drops_the_repetition_bonus() -> None:
    p = turn("account_number")
    text = "my my account number is 4 5 2 7 3 6 1 0"
    speech(p, text)
    assert first_end(silence(p, text, 80)) == frames_for(700)


# --- INCOMPLETE: never ends on silence --------------------------------------------------------

def test_four_of_eight_digits_and_3s_silence_continues() -> None:
    p = turn("account_number")
    speech(p, ACCOUNT_4)
    decisions = silence(p, ACCOUNT_4, frames_for(3000))
    assert {d.action for d in decisions} == {Action.CONTINUE}
    assert "4/8 digits" in decisions[-1].reason


def test_incomplete_prompts_once_at_6s_then_keeps_listening() -> None:
    p = turn("account_number")
    speech(p, ACCOUNT_4)
    decisions = silence(p, ACCOUNT_4, 300)  # 9.6 s of silence
    prompts = [i + 1 for i, d in enumerate(decisions) if d.action is Action.PROMPT]
    assert prompts == [frames_for(PROMPT_MS)]
    assert first_end(decisions) is None


def test_answer_finishing_after_the_prompt_then_ends() -> None:
    p = turn("account_number")
    speech(p, ACCOUNT_4)
    silence(p, ACCOUNT_4, 200)  # prompted
    speech(p, ACCOUNT_4)
    assert first_end(silence(p, ACCOUNT_8, 40)) == frames_for(700)


def test_speech_with_no_words_yet_is_incomplete_on_formatted_slots() -> None:
    for slot in ("account_number", "date_of_birth"):
        p = turn(slot)
        speech(p, "")
        decisions = silence(p, "", 100)
        assert first_end(decisions) is None, slot
        assert "no words yet" in decisions[-1].reason


def test_speech_with_no_words_yet_falls_back_to_timing_on_free_slots() -> None:
    for slot in ("reason", "confirm"):
        p = turn(slot)
        speech(p, "")
        assert first_end(silence(p, "", 40)) == frames_for(700), slot


# --- transcript=None: timing-only ------------------------------------------------------------

def test_no_transcript_behaves_like_the_baseline_even_on_account() -> None:
    p = turn("account_number")
    speech(p, None)
    decisions = silence(p, None, 40)
    assert first_end(decisions) == frames_for(700)
    assert "timing only" in decisions[frames_for(700) - 1].reason


def test_silence_before_any_speech_never_ends() -> None:
    p = turn("reason")
    assert first_end(silence(p, "", 300)) is None


# --- repetition bonus ------------------------------------------------------------------------

def test_repetition_gives_patience_1700() -> None:
    p = turn("reason")
    text = "i want to to set up a payment plan"
    speech(p, text)
    decisions = silence(p, text, 80)
    assert first_end(decisions) == frames_for(1700)
    assert "patience 1700ms" in decisions[frames_for(1700) - 1].reason
    assert "repetition" in decisions[frames_for(1700) - 1].reason


def test_hyphenated_restart_counts_as_repetition() -> None:
    p = turn("reason")
    text = "i want to s-s-set up a payment plan"
    speech(p, text)
    assert first_end(silence(p, text, 80)) == frames_for(1700)


def test_repetition_bonus_expires_after_8s() -> None:
    p = turn("reason")
    text = "i want to to set up a payment plan"
    speech(p, text, frames=1)
    speech(p, text, frames=frames_for(8000) + 1)  # same count, so the window doesn't restart
    assert first_end(silence(p, text, 80)) == frames_for(700)


@pytest.mark.parametrize("word, expected", [
    ("m-m-my", True), ("i-it's", True), ("4-4521", True),
    ("well-known", False), ("t-shirt", False), ("4-", False),
])
def test_is_restart(word: str, expected: bool) -> None:
    assert is_restart(word) is expected


def test_doubled_digits_are_not_a_repetition() -> None:
    # "8 8" in an account number is the number, not a stammer. Every A line and C2 has one.
    assert count_repetitions("my account number is 4 5 2 1 8 8 3 0") == 0
    assert count_repetitions("no it's 4 5 2 1 8 8 3 1") == 0


# --- call memory and reset ---------------------------------------------------------------------

def run_turn(p: Patient, slot: str, text: str) -> None:
    p.reset(slot)
    speech(p, text)
    silence(p, text, 300)


def test_repetition_earlier_in_the_call_adds_500ms_to_later_turns() -> None:
    p = Patient()
    run_turn(p, "reason", "i want to to set up a payment plan")
    p.reset("reason")
    speech(p, REASON)
    decisions = silence(p, REASON, 80)
    assert first_end(decisions) == frames_for(1200)
    assert "stammered earlier in call" in decisions[frames_for(1200) - 1].reason


def test_fluent_earlier_turn_adds_nothing() -> None:
    p = Patient()
    run_turn(p, "reason", REASON)
    p.reset("reason")
    speech(p, REASON)
    assert first_end(silence(p, REASON, 80)) == frames_for(700)


def test_fluent_account_with_doubled_digit_does_not_mark_the_call() -> None:
    # A fluent caller reading "8 8" must not pay +500 ms on every later turn.
    p = Patient()
    run_turn(p, "account_number", "my account number is 4 5 2 1 8 8 3 0")
    p.reset("reason")
    speech(p, REASON)
    assert first_end(silence(p, REASON, 80)) == frames_for(700)


def test_reset_clears_turn_state_after_an_end() -> None:
    p = turn("reason")
    speech(p, REASON)
    assert first_end(silence(p, REASON, 40)) is not None
    p.reset("account_number")
    assert p.step(False, FRAME_MS, "").action is Action.CONTINUE  # not "already ended"
    speech(p, ACCOUNT_4)
    assert first_end(silence(p, ACCOUNT_4, 100)) is None  # new slot's rules apply


def test_reset_clears_the_prompt_flag() -> None:
    p = turn("account_number")
    speech(p, ACCOUNT_4)
    silence(p, ACCOUNT_4, 200)
    p.reset("account_number")
    speech(p, ACCOUNT_4)
    assert any(d.action is Action.PROMPT for d in silence(p, ACCOUNT_4, 200))


def test_end_is_sticky_until_reset() -> None:
    p = turn("reason")
    speech(p, REASON)
    silence(p, REASON, 40)
    assert p.step(True, FRAME_MS, REASON).action is Action.END


# --- ceiling ---------------------------------------------------------------------------------

def test_patience_never_exceeds_the_ceiling() -> None:
    # 4500 + 1000 repetition + 500 call memory = 6000 -> capped at 5000.
    p = Patient(base_ms=4500)
    run_turn(p, "reason", "i want to to set up a payment plan")
    p.reset("reason")
    text = "i i want to set up a payment plan"
    speech(p, text)
    decisions = silence(p, text, 200)
    assert first_end(decisions) == frames_for(CEILING_MS)
    assert f"capped at {CEILING_MS}" in decisions[frames_for(CEILING_MS) - 1].reason


# --- transcript rewrites (ticket 06: a Vosk final can rewrite its partial) -------------------

def test_completeness_is_recomputed_every_frame_from_the_current_transcript() -> None:
    # 8 digits in the partial, then the segment's final drops one ("two" -> "the"): no longer COMPLETE.
    p = turn("account_number")
    speech(p, ACCOUNT_8)
    silence(p, ACCOUNT_8, frames_for(700) - 5)
    rewritten = "my account number is 4 5 the 7 3 6 1 0"
    later = silence(p, rewritten, frames_for(6000))
    assert first_end(later) is None
    assert "7/8 digits" in later[-1].reason
    # And back: a rewrite that completes the answer ends it on the next frames.
    assert first_end(silence(p, ACCOUNT_8, 1)) == 1
