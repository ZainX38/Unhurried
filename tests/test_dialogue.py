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
