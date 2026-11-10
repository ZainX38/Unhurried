"""Cleanup tests (ticket 09): stammer and filler removal that never touches digits."""

from unhurried.cleanup import clean


def test_removes_fillers() -> None:
    assert clean("um i'm calling about my last bill") == "i'm calling about my last bill"


def test_collapses_a_repeated_word() -> None:
    assert clean("my my account number is") == "my account number is"


def test_collapses_a_sound_restart() -> None:
    assert clean("m-m-my account") == "my account"


def test_never_collapses_repeated_digit_words() -> None:
    # Could be a real 44: the Read-back resolves it, not Cleanup.
    assert clean("four four five two") == "four four five two"


def test_keeps_digit_homophones_and_double() -> None:
    assert clean("four for five to one") == "four for five to one"
    assert clean("double eight four") == "double eight four"


def test_never_collapses_a_repeated_homophone_next_to_a_digit() -> None:
    # "to to" between digits could be 22.
    assert clean("five to to one") == "five to to one"


def test_removes_a_filler_before_an_answer() -> None:
    assert clean("huh yes") == "yes"


def test_empty_stays_empty() -> None:
    assert clean("") == ""


def test_never_collapses_hyphenated_digits() -> None:
    assert clean("four-four five") == "four-four five"
