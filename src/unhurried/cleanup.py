"""Transcript Cleanup (ticket 09): what the caller meant, for display and Slots only.

Completeness and the Endpointer read the RAW text: repetitions are evidence of stammering.
"""

from unhurried.endpointer.completeness import (
    FILLERS, REPEATS, is_digit_homophone, is_digit_token,
)


def protected(words: list[str], i: int) -> bool:
    """Words Cleanup may never change: digits, homophones next to digits, "double"/"triple"."""
    w = words[i]
    return is_digit_token(w) or is_digit_homophone(words, i) or w in REPEATS


def unrestart(w: str) -> str:
    """ "m-m-my" -> "my": every piece before the last is the start of the last. "x-ray" stays."""
    *starts, last = w.split("-")
    if not starts or any(is_digit_token(s) for s in starts):
        return w                          # "four-four" may be a real 44
    return last if all(last.startswith(s) for s in starts) else w


def clean(text: str) -> str:
    words = [unrestart(w) for w in text.split() if w not in FILLERS]
    out: list[str] = []
    for i, w in enumerate(words):
        if i > 0 and w == words[i - 1] and not protected(words, i):
            continue                      # "my my" -> "my"
        out.append(w)
    return " ".join(out)
