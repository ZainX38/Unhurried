"""Dialogue tests (ticket 07). The user writes dialogue.py; these drive it through its public interface only."""

from unhurried.dialogue import Dialogue, State


def test_start_greets_and_asks_for_the_account_number() -> None:
    dialogue = Dialogue()

    reply = dialogue.start()

    assert "account number" in reply.line.lower()
    assert reply.expected_slot == "account_number"
    assert reply.state is State.ACCOUNT
    assert dialogue.state is State.ACCOUNT


def test_eight_spoken_digits_are_read_back_for_confirmation() -> None:
    dialogue = Dialogue()
    dialogue.start()

    reply = dialogue.on_turn("four five two one eight eight three zero")

    assert "4, 5, 2, 1, 8, 8, 3, 0" in reply.line
    assert reply.expected_slot == "confirm"
    assert reply.state is State.CONFIRM_ACCOUNT


def test_yes_to_the_read_back_saves_the_account_number_and_asks_for_date_of_birth() -> None:
    dialogue = Dialogue()
    dialogue.start()
    dialogue.on_turn("four five two one eight eight three zero")

    reply = dialogue.on_turn("yes")

    assert "date of birth" in reply.line.lower()
    assert reply.expected_slot == "date_of_birth"
    assert reply.state is State.DOB
    assert dialogue.slots["account_number"] == "45218830"


def test_a_filler_before_yes_still_confirms() -> None:
    # Vosk often hears "huh" at the start of a Turn.
    dialogue = Dialogue()
    dialogue.start()
    dialogue.on_turn("four five two one eight eight three zero")

    reply = dialogue.on_turn("huh yes")

    assert reply.state is State.DOB
    assert dialogue.slots["account_number"] == "45218830"


def test_no_with_a_new_number_reads_back_the_correction() -> None:
    dialogue = Dialogue()
    dialogue.start()
    dialogue.on_turn("four five two one eight eight three zero")

    reply = dialogue.on_turn("no it's four five two one eight eight three one")

    assert "4, 5, 2, 1, 8, 8, 3, 1" in reply.line
    assert reply.expected_slot == "confirm"
    assert reply.state is State.CONFIRM_ACCOUNT
    assert "account_number" not in dialogue.slots


def test_a_plain_no_asks_for_the_account_number_again() -> None:
    dialogue = Dialogue()
    dialogue.start()
    dialogue.on_turn("four five two one eight eight three zero")

    reply = dialogue.on_turn("no")

    assert "account number" in reply.line.lower()
    assert reply.expected_slot == "account_number"
    assert reply.state is State.ACCOUNT
    assert "account_number" not in dialogue.slots


def test_an_answer_with_no_yes_or_no_at_the_read_back_gets_a_re_prompt() -> None:
    dialogue = Dialogue()
    dialogue.start()
    dialogue.on_turn("four five two one eight eight three zero")

    reply = dialogue.on_turn("five two one eight eight three zero")

    assert "yes or no" in reply.line.lower()
    assert "4, 5, 2, 1, 8, 8, 3, 0" in reply.line      # repeats the number it is asking about
    assert reply.expected_slot == "confirm"
    assert reply.state is State.CONFIRM_ACCOUNT
    assert "account_number" not in dialogue.slots


def test_a_short_account_number_gets_one_re_prompt_then_the_keypad() -> None:
    dialogue = Dialogue()
    dialogue.start()

    first = dialogue.on_turn("four five two")
    second = dialogue.on_turn("four five two")

    # Once: ask again, patiently. No read-back of a number that is too short.
    assert "account number" in first.line.lower()
    assert "is that right" not in first.line.lower()
    assert first.expected_slot == "account_number"
    assert first.state is State.ACCOUNT
    # Twice: never the same question a third time, offer the keypad instead.
    assert "keypad" in second.line.lower()
    assert second.line != first.line
    assert second.state is State.ACCOUNT
    assert "account_number" not in dialogue.slots


def test_keypad_digits_at_account_are_read_back() -> None:
    dialogue = Dialogue()
    dialogue.start()

    reply = dialogue.on_keypad("45218830")

    assert "4, 5, 2, 1, 8, 8, 3, 0" in reply.line
    assert reply.expected_slot == "confirm"
    assert reply.state is State.CONFIRM_ACCOUNT


def at_dob() -> Dialogue:
    dialogue = Dialogue()
    dialogue.start()
    dialogue.on_turn("four five two one eight eight three zero")
    dialogue.on_turn("yes")
    return dialogue


def test_date_of_birth_is_read_back_in_the_callers_words() -> None:
    # Real Vosk output for "the fourteenth of March nineteen ninety nine": the read-back
    # is what lets the caller catch "fortieth".
    dialogue = at_dob()

    reply = dialogue.on_turn("their fortieth of march nineteen ninety nine")

    assert "fortieth of march nineteen ninety nine" in reply.line.lower()
    assert reply.expected_slot == "confirm"
    assert reply.state is State.CONFIRM_DOB
    assert "date_of_birth" not in dialogue.slots


def test_yes_to_the_date_read_back_saves_it_and_asks_the_reason() -> None:
    dialogue = at_dob()
    dialogue.on_turn("their fortieth of march nineteen ninety nine")

    reply = dialogue.on_turn("yes")

    assert reply.expected_slot == "reason"
    assert reply.state is State.REASON
    assert dialogue.slots["date_of_birth"] == "their fortieth of march nineteen ninety nine"
