import pytest

from unhurried.endpointer.completeness import Status, completeness

# (transcript, slot, expected status, fragment the reason must contain)
CASES = [
    ("", "account_number", Status.UNSURE, "nothing heard"),
    ("my account number is", "account_number", Status.INCOMPLETE, "ends with 'is'"),
    ("MY ACCOUNT NUMBER IS", "account_number", Status.INCOMPLETE, "ends with 'is'"),
    ("let me just find the letter", "account_number", Status.INCOMPLETE, "0/8 digits"),
    ("four five two one", "account_number", Status.INCOMPLETE, "4/8 digits"),
    ("four five two one eight eight three zero", "account_number", Status.COMPLETE, "8/8 digits"),
    ("four five two one eight eight three oh", "account_number", Status.COMPLETE, "8/8 digits"),
    ("4521 8830", "account_number", Status.COMPLETE, "8/8 digits"),
    ("double eight four five two one three oh", "account_number", Status.COMPLETE, "8/8 digits"),
    ("yes my account number is two six zero four nine nine one eight", "account_number", Status.COMPLETE, "8/8 digits"),
    ("four four five two one eight eight three oh", "account_number", Status.UNSURE, "9 digits"),
    ("4-", "account_number", Status.INCOMPLETE, "restart"),
    ("yes", "confirm", Status.COMPLETE, "yes"),
    ("no it's", "confirm", Status.INCOMPLETE, "correction"),
    ("no it's four five two one eight eight three one", "confirm", Status.COMPLETE, "8/8 digits"),
    ("no that is not right", "confirm", Status.COMPLETE, "heard 'no'"),
    ("hmm let me think", "confirm", Status.UNSURE, "no yes or no"),
    ("I'm calling about my", "reason", Status.INCOMPLETE, "ends with 'my'"),
    ("i'm calling about um", "reason", Status.INCOMPLETE, "filler"),
    ("I'm calling about my bill", "reason", Status.UNSURE, "free text"),
    ("fourteenth of March", "date_of_birth", Status.INCOMPLETE, "missing year"),
    ("fourteenth of March nineteen ninety nine", "date_of_birth", Status.COMPLETE, "day, month, year"),
    ("the second of october two thousand and four", "date_of_birth", Status.COMPLETE, "day, month, year"),
]


@pytest.mark.parametrize(("transcript", "slot", "expected", "fragment"), CASES)
def test_completeness(transcript: str, slot: str, expected: Status, fragment: str) -> None:
    status, reason = completeness(transcript, slot)
    assert status is expected
    assert fragment in reason


@pytest.mark.parametrize("transcript", ["", "four five two one"])
def test_unknown_slot_raises(transcript: str) -> None:
    # A typo in a slot name must fail loudly, not quietly switch the rules off.
    with pytest.raises(ValueError, match="acount_number"):
        completeness(transcript, "acount_number")
