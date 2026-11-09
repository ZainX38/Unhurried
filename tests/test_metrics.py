import pytest

from eval.metrics import GroupStats, outcome, percentile, summarize


# OUTCOME 
def test_no_end() -> None:
    assert outcome(None, 2000) == ("no_end", None)


def test_cut_off_before_true_end() -> None:
    assert outcome(1500, 2000) == ("cut_off", None)


def test_ended_after_true_end_gives_wait() -> None:
    assert outcome(2704, 2000) == ("ended", 704)


def test_ending_exactly_on_true_end_is_not_a_cut_off() -> None:
    assert outcome(2000, 2000) == ("ended", 0)


# 95th PERCENTILE

def test_percentile_empty_is_none() -> None:
    assert percentile([], 50) is None


def test_median_odd_and_even() -> None:
    assert percentile([3, 1, 2], 50) == 2
    assert percentile([1, 2, 3, 4], 50) == 2.5


def test_p95_interpolates() -> None:
    values = list(range(0, 101))          # 0..100
    assert percentile(values, 95) == 95
    assert percentile([100, 200], 95) == 195   # 100 + 0.95 * 100


def test_single_value() -> None:
    assert percentile([704], 50) == 704
    assert percentile([704], 95) == 704


# SUMMARY

def rec(group: str, end_ms: int | None, true_end_ms: int = 1000) -> dict:
    out, wait = outcome(end_ms, true_end_ms)
    return {"group": group, "outcome": out, "wait_ms": wait}


def test_summarize_per_group() -> None:
    records = [
        rec("fluent", 1704), rec("fluent", 1800), rec("fluent", 500),   # 2 ended, 1 cut off
        rec("stammered", 400), rec("stammered", None),                  # 1 cut off, 1 no end
    ]
    stats = summarize(records)

    assert stats["fluent"] == GroupStats(
        n=3, cut_offs=1, cut_off_rate=1 / 3, no_ends=0, wait_median=752.0, wait_p95=795.2,
    )
    s = stats["stammered"]
    assert (s.n, s.cut_offs, s.cut_off_rate, s.no_ends) == (2, 1, 0.5, 1)
    assert s.wait_median is None and s.wait_p95 is None   # no clip ended normally


def test_no_end_and_cut_off_do_not_count_as_waits() -> None:
    stats = summarize([rec("g", 1100), rec("g", None), rec("g", 200)])["g"]
    assert stats.wait_median == 100
    assert stats.wait_p95 == 100


def test_unknown_outcome_raises() -> None:
    with pytest.raises(ValueError):
        summarize([{"group": "g", "outcome": "ended_early", "wait_ms": None}])