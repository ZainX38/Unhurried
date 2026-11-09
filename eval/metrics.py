"""
Every clip ends in exactly one of three outcomes:
- "cut_off": the endpointer declared END before the caller had finished (end_ms < true_end_ms)
- "ended":   it declared END at or after the true end; the wait is end_ms - true_end_ms
- "no_end":  it never declared END (still listening when the clip ran out)
"""

from dataclasses import dataclass

OUTCOMES = ("cut_off", "ended", "no_end")


def outcome(end_ms: int | None, true_end_ms: int) -> tuple[str, int | None]:
    # Classify one clip. Returns (outcome, wait_ms); wait_ms is only set for "ended"
    if end_ms is None:
        return "no_end", None
    if end_ms < true_end_ms:
        return "cut_off", None
    return "ended", end_ms - true_end_ms


def percentile(values: list[int], p: float) -> float | None:
    # p-th percentile (0-100) with linear interpolation between neighbours, like numpy's default
    # The 50th percentile is the usual median. Returns None for an empty list.

    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * p / 100   # fractional index into the sorted list
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    frac = pos - low
    return ordered[low] + (ordered[high] - ordered[low]) * frac


@dataclass(frozen=True)
class GroupStats:
    n: int                      # clips in the group
    cut_offs: int
    cut_off_rate: float | None  # cut_offs / n, from 0 to 1; None if n == 0
    no_ends: int
    wait_median: float | None   # over "ended" clips only; None if there are none
    wait_p95: float | None


def group_stats(records: list[dict]) -> GroupStats:
    # Summarise one group's records
    n = len(records)
    cut_offs = sum(1 for r in records if r["outcome"] == "cut_off")
    no_ends = sum(1 for r in records if r["outcome"] == "no_end")
    waits = [r["wait_ms"] for r in records if r["outcome"] == "ended"]
    return GroupStats(
        n=n,
        cut_offs=cut_offs,
        cut_off_rate=cut_offs / n if n else None,
        no_ends=no_ends,
        wait_median=percentile(waits, 50),
        wait_p95=percentile(waits, 95),
    )


def summarize(records: list[dict]) -> dict[str, GroupStats]:
    # Per-group stats, keyed by group name. Each record needs group, outcome and wait_ms
    by_group: dict[str, list[dict]] = {}
    for r in records:
        if r["outcome"] not in OUTCOMES:
            raise ValueError(f"unknown outcome {r['outcome']!r}")
        by_group.setdefault(r["group"], []).append(r)
    return {group: group_stats(rs) for group, rs in by_group.items()}