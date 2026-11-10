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
FILLERS = {"um", "uh", "er", "erm", "hmm", "huh"}

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

# Any of these means the caller is saying no. Checked BEFORE yes words,
# because "not right" contains "right".
NEGATIONS = NO_WORDS | {"not", "wrong"}

MONTHS = {"january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"}
# Ordinal day words. "twenty first" and "thirty first" are covered by "first".
DAY_WORDS = {"first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth",
             "ninth", "tenth", "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth",
             "sixteenth", "seventeenth", "eighteenth", "nineteenth", "twentieth", "thirtieth"}
YEAR_STARTS = {"nineteen", "twenty"}   # "nineteen ninety nine", "twenty twenty"

# The Slots the dialogue and the eval manifest use, spelled exactly as in lines.csv.
SLOTS = {"account_number", "date_of_birth", "reason", "confirm"}

HOMOPHONES = {"for": "4", "to": "2", "too": "2", "won": "1", "ate": "8"}


def is_digit_token(w: str) -> bool:
    """A real digit: a digit word ("four", "oh") or a numeral ("4", "4521")."""
    return w in DIGIT_WORDS or w.isdigit()


def is_digit_homophone(words: list[str], i: int) -> bool:
    """words[i] is a homophone used as a digit: a neighbour is a real digit ("five to one", not "looking for")."""
    if words[i] not in HOMOPHONES:
        return False
    before = words[i - 1] if i > 0 else ""
    after = words[i + 1] if i + 1 < len(words) else ""
    return is_digit_token(before) or is_digit_token(after)


def digits_in(words: list[str]) -> str:
    """The digits heard, in order: spoken digit words, numerals, "double"/"triple" repeats,
    and homophones used as digits"""
    out: list[str] = []
    for i, w in enumerate(words):
        if w in REPEATS:
            nxt = words[i + 1] if i + 1 < len(words) else ""
            digit = DIGIT_WORDS.get(nxt) or (nxt if len(nxt) == 1 and nxt.isdigit() else "")
            if digit:
                # The next word adds itself once, so add the extra copies here.
                out.append(digit * (REPEATS[w] - 1))
        elif w in DIGIT_WORDS:
            out.append(DIGIT_WORDS[w])
        elif w in HOMOPHONES:
            if is_digit_homophone(words, i):
                out.append(HOMOPHONES[w])
        else:
            out.append("".join(ch for ch in w if ch.isdigit()))
    return "".join(out)


def count_digits(words: list[str]) -> int:
    return len(digits_in(words))


def extract_digits(text: str) -> str:
    # Public helper for the dialogue: all digits in a transcript, e.g. for the read-back
    return digits_in(text.lower().split())


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


ORDINAL_ENDINGS = ("th", "st", "nd", "rd")


def ordinal_before_month(words: list[str], month_at: int | None) -> bool:
    """An ordinal-shaped word right before the month ("fortieth march", "the fortieth of march") is a day,
    valid or not: STT mishears days ("fourteenth" -> "fortieth"), and checking validity is the read-back's job.
    Only that position: "birth" and "and" end in -th/-nd too."""
    if month_at is None:
        return False
    at = month_at - 2 if month_at >= 2 and words[month_at - 1] == "of" else month_at - 1
    if at < 0:
        return False
    w = words[at]
    return w.isalpha() and w.endswith(ORDINAL_ENDINGS) and w not in DANGLING


def dob_status(words: list[str]) -> tuple[Status, str]:
    """Day, month and year all heard? Lists whatever is missing."""
    month_at = next((i for i, w in enumerate(words) if w in MONTHS), None)
    missing = []
    if not any(is_day(w) for w in words) and not ordinal_before_month(words, month_at):
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
        # Skip hesitation at the start ("huh yes", "um no it's ...").
        while words and words[0] in FILLERS:
            words = words[1:]
        if not words:
            return Status.UNSURE, "nothing heard"

        # No before yes: "that's not right" contains "right" but means no.
        neg_at = next((i for i, w in enumerate(words) if w in NEGATIONS), None)
        if neg_at is not None:
            rest = words[neg_at + 1:]
            # Digits after the "no" mean a correction: judge it like an account number.
            if count_digits(rest) > 0:
                status, reason = account_status(rest)
                return status, f"correction: {reason}"
            # "no it's", "no um": a correction is on its way.
            if rest and (rest[-1] in DANGLING or rest[-1] in FILLERS or rest[-1].endswith("-")):
                return Status.INCOMPLETE, f"correction coming: ends with '{rest[-1]}'"
            # A plain "no" or "that's not right": the answer itself is finished.
            return Status.COMPLETE, f"heard '{words[neg_at]}'"

        for w in words:
            if w in YES_WORDS:
                return Status.COMPLETE, f"heard '{w}'"

    last = words[-1]

    # Ends on a hesitation sound: the caller is still thinking.
    if last in FILLERS:
        return Status.INCOMPLETE, f"ends with filler '{last}'"

    # Ends on a word that needs something after it: the caller isn't finished.
    # Except a homophone counted as a digit ("six for"): that's the last digit, not a preposition.
    counted_as_digit = slot == "account_number" and is_digit_homophone(words, len(words) - 1)
    if last in DANGLING and not counted_as_digit:
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