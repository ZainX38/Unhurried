from enum import Enum


class Status(Enum):
    COMPLETE = "COMPLETE"      # answer looks finished
    INCOMPLETE = "INCOMPLETE"  # unfinished, so wait longer
    UNSURE = "UNSURE"          # can't tell


# Words that can't end a finished answer: the caller is mid-sentence.
# Prepositions are included because an answer can't end on one ("I'm calling about").
DANGLING = {
    "is", "its", "it's", "and", "the", "my", "a",
    "about", "for", "with", "of", "to", "from",
    "double", "triple",
}

# Hesitation sounds: the caller is thinking, not finished.
FILLERS = {"um", "uh", "er", "erm", "hmm"}

# Spoken digits. "oh" is zero when people read out numbers.
DIGIT_WORDS = {
    "zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}
ACCOUNT_DIGITS = 8

# "double eight" = 88, "triple oh" = 000: common when UK callers read out numbers.
REPEATS = {"double": 2, "triple": 3}

YES_WORDS = {"yes", "yeah", "yep", "yup", "correct", "right"}
NO_WORDS = {"no", "nope", "nah"}

MONTHS = {"january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"}
# Ordinal day words. "twenty first" and "thirty first" are covered by "first".
DAY_WORDS = {"first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth",
             "ninth", "tenth", "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth",
             "sixteenth", "seventeenth", "eighteenth", "nineteenth", "twentieth", "thirtieth"}
YEAR_STARTS = {"nineteen", "twenty"}   # "nineteen ninety nine", "twenty twenty"

# The Slots the dialogue and the eval manifest use, spelled exactly as in lines.csv.
SLOTS = {"account_number", "date_of_birth", "reason", "confirm"}


def count_digits(words: list[str]) -> int:
    """Digits heard so far: spoken digit words, each numeral character ("4521" adds 4),
    and "double"/"triple" before a single digit ("double eight" adds 2)."""
    total = 0
    for i, w in enumerate(words):
        if w in REPEATS:
            nxt = words[i + 1] if i + 1 < len(words) else ""
            if nxt in DIGIT_WORDS or (len(nxt) == 1 and nxt.isdigit()):
                # The next word counts once on its own, so add the extra copies here.
                total += REPEATS[w] - 1
        elif w in DIGIT_WORDS:
            total += 1
        else:
            total += sum(1 for ch in w if ch.isdigit())
    return total


def account_status(words: list[str]) -> tuple[Status, str]:
    """Compare the digits heard with the expected account number length."""
    digits = count_digits(words)
    if digits < ACCOUNT_DIGITS:
        return Status.INCOMPLETE, f"{digits}/{ACCOUNT_DIGITS} digits"
    if digits == ACCOUNT_DIGITS:
        return Status.COMPLETE, f"{digits}/{ACCOUNT_DIGITS} digits"
    # Too many digits: probably a stammered repeat or a mishearing. The count can't
    # say whether the caller is done, so don't claim either way.
    return Status.UNSURE, f"{digits} digits, expected {ACCOUNT_DIGITS}"


def is_day(w: str) -> bool:
    # "fourteenth", or a numeral day like "14" / "14th"
    return w in DAY_WORDS or (w.rstrip("stndrh").isdigit() and len(w.rstrip("stndrh")) <= 2)


def has_year(words: list[str]) -> bool:
    """A year after the month: "1999", "nineteen ninety nine", "two thousand and four"."""
    for i, w in enumerate(words):
        if w.isdigit() and len(w) == 4:
            return True
        if w == "thousand":
            return True
        # "nineteen ninety", but not "twenty first" (that's a day)
        if w in YEAR_STARTS and i + 1 < len(words) and words[i + 1] not in DAY_WORDS:
            return True
    return False


def dob_status(words: list[str]) -> tuple[Status, str]:
    """Day, month and year all heard? Lists whatever is missing."""
    month_at = next((i for i, w in enumerate(words) if w in MONTHS), None)
    missing = []
    if not any(is_day(w) for w in words):
        missing.append("day")
    if month_at is None:
        missing.append("month")
    if month_at is None or not has_year(words[month_at + 1:]):
        missing.append("year")
    if missing:
        return Status.INCOMPLETE, "missing " + ", ".join(missing)
    return Status.COMPLETE, "day, month, year"


def completeness(transcript: str, slot: str) -> tuple[Status, str]:
    # A misspelled slot must fail loudly: silently returning UNSURE would switch the rules off.
    if slot not in SLOTS:
        raise ValueError(f"unknown slot {slot!r}, expected one of {sorted(SLOTS)}")

    # Lowercase once, so every check below ignores capitals.
    words = transcript.lower().split()

    # Nothing heard yet: the transcript can't tell us anything.
    if not words:
        return Status.UNSURE, "nothing heard"

    # Confirmation runs first: "no it's ..." is a correction, judged by its digits,
    # not by the general dangling-word check.
    if slot == "confirm":
        if words[0] in NO_WORDS:
            rest = words[1:]
            # Digits after "no" mean a correction: judge it like an account number.
            if count_digits(rest) > 0:
                status, reason = account_status(rest)
                return status, f"correction: {reason}"
            # "no it's", "no um": a correction is on its way.
            if rest and (rest[-1] in DANGLING or rest[-1] in FILLERS or rest[-1].endswith("-")):
                return Status.INCOMPLETE, f"correction coming: ends with '{rest[-1]}'"
            # A plain "no", or "no that's not right": the answer itself is finished.
            return Status.COMPLETE, f"heard '{words[0]}'"
        for w in words:
            if w in YES_WORDS:
                return Status.COMPLETE, f"heard '{w}'"

    last = words[-1]

    # Ends on a hesitation sound: the caller is still thinking.
    if last in FILLERS:
        return Status.INCOMPLETE, f"ends with filler '{last}'"

    # Ends on a word that needs something after it: the caller isn't finished.
    if last in DANGLING:
        return Status.INCOMPLETE, f"ends with '{last}'"

    # Last word cut off mid-way ("4-", "m-"): the caller is restarting it.
    if last.endswith("-"):
        return Status.INCOMPLETE, f"ends mid-word '{last}': restart coming"

    if slot == "account_number":
        return account_status(words)

    if slot == "date_of_birth":
        return dob_status(words)

    if slot == "confirm":
        # Words, but neither yes nor no ("hmm let me think"): can't tell, so let timing decide.
        return Status.UNSURE, "no yes or no heard"

    # slot == "reason". Free text has no format to check, so only the general rules above apply.
    return Status.UNSURE, "free text"