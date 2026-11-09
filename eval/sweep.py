"""Sweep the Baseline's fixed silence threshold (ticket 03).

Runs the VAD once per clip, then replays every clip at each threshold and writes:

- eval/results/sweep.md         per-group cut-off rate, no-ends, wait median and p95 per threshold
- eval/results/sweep_clips.csv  every per-clip record, with a threshold_ms column
- eval/results/sweep.png        stammered cut-off rate (y) vs fluent median wait (x), one point per threshold

Usage:
    uv run python -m eval.sweep
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # file output only, no window
import matplotlib.pyplot as plt  # noqa: E402

from eval import metrics  # noqa: E402
from eval.run import (  # noqa: E402
    DEFAULT_MANIFEST, GROUPS, RECORD_COLUMNS, RESULTS_DIR,
    Clip, baseline_factory, fmt_ms, fmt_rate, load_clips, run, write_csv,
)

THRESHOLDS_MS = [300, 500, 700, 1000, 1500, 2000, 3000, 4000]

# Targets from the spec: fluent median Wait time <= 900 ms, stammered Cut-off rate < 5%.
TARGET_FLUENT_WAIT_MS = 900
TARGET_STAMMERED_CUT_OFF = 0.05

# Chart colours (dataviz reference palette, light mode).
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SERIES = "#2a78d6"


@dataclass(frozen=True)
class SweepPoint:
    threshold_ms: int
    records: list[dict]
    stats: dict  # group -> metrics.GroupStats


def sweep(clips: list[Clip], thresholds: list[int] = THRESHOLDS_MS) -> list[SweepPoint]:
    """Replay the same clips (VAD already done) at each threshold."""
    points = []
    for t in thresholds:
        records = run(clips, baseline_factory(t))
        points.append(SweepPoint(t, records, metrics.summarize(records)))
    return points


def sweep_table(points: list[SweepPoint]) -> str:
    """One markdown table per group, one row per threshold."""
    out = []
    for g in GROUPS:
        if not any(g in p.stats for p in points):
            continue
        out += [
            f"### {g}",
            "",
            "| threshold (ms) | cut-off rate | no end | wait median (ms) | wait p95 (ms) |",
            "| ---: | ---: | ---: | ---: | ---: |",
        ]
        for p in points:
            s = p.stats.get(g)
            if s is None:
                continue
            out.append(f"| {p.threshold_ms} | {fmt_rate(s)} | {s.no_ends} | {fmt_ms(s.wait_median)} | {fmt_ms(s.wait_p95)} |")
        out.append("")
    return "\n".join(out)


def curve(points: list[SweepPoint]) -> list[tuple[int, float, float]]:
    """(threshold, fluent median wait, stammered cut-off rate) for every threshold where both exist."""
    xs = []
    for p in points:
        fluent, stammered = p.stats.get("fluent"), p.stats.get("stammered")
        if fluent is None or stammered is None:
            continue
        if fluent.wait_median is None or stammered.cut_off_rate is None:
            continue  # e.g. every fluent clip cut off: no wait to plot
        xs.append((p.threshold_ms, fluent.wait_median, stammered.cut_off_rate))
    return xs


def plot(points: list[SweepPoint], path: Path) -> None:
    data = curve(points)
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    # Target region: left of the wait target and below the cut-off target.
    ax.axvline(TARGET_FLUENT_WAIT_MS, color=MUTED, lw=1, ls=(0, (4, 3)), zorder=1)
    ax.axhline(TARGET_STAMMERED_CUT_OFF * 100, color=MUTED, lw=1, ls=(0, (4, 3)), zorder=1)
    ax.text(TARGET_FLUENT_WAIT_MS - 25, 0.45, f"fluent wait target ≤ {TARGET_FLUENT_WAIT_MS} ms",
            color=INK_SECONDARY, fontsize=8, va="center", ha="right", rotation=90,
            transform=ax.get_xaxis_transform())
    ax.text(0, TARGET_STAMMERED_CUT_OFF * 100 + 1, " stammered cut-off target < 5%",
            color=INK_SECONDARY, fontsize=8, va="bottom", ha="left", transform=ax.get_yaxis_transform())

    if data:
        thresholds, waits, rates = zip(*data)
        rates_pct = [r * 100 for r in rates]
        ax.plot(waits, rates_pct, color=SERIES, lw=2, zorder=2)
        ax.scatter(waits, rates_pct, s=64, color=SERIES, edgecolor=SURFACE, linewidth=2, zorder=3)
        fluent_cut = {p.threshold_ms: p.stats["fluent"] for p in points if "fluent" in p.stats}
        for t, x, y in data:  # the threshold is what identifies each point
            label = f"{t}"
            f = fluent_cut[t]
            if f.cut_offs:  # the median then only covers the fluent clips that survived
                label += f"\n{f.cut_offs}/{f.n} fluent\ncut off"
            top = y >= 0.95  # points on the 100% ceiling: label below so they don't collide
            ax.annotate(label, (x, y * 100), xytext=(0, -10) if top else (7, 5), textcoords="offset points",
                        ha="center" if top else "left", va="top" if top else "bottom",
                        color=INK_SECONDARY, fontsize=8, linespacing=1.1)

    fig.suptitle("Baseline sweep: raising the fixed timeout costs fluent callers",
                 color=INK, fontsize=11, x=0.02, ha="left")
    ax.set_title("Each point is one fixed silence threshold (ms)", color=INK_SECONDARY, fontsize=9, loc="left", pad=10)
    ax.set_xlabel("fluent median wait time (ms)", color=INK_SECONDARY, fontsize=9)
    ax.set_ylabel("stammered cut-off rate (%)", color=INK_SECONDARY, fontsize=9)
    ax.set_ylim(-3, 105)
    ax.set_xlim(0, max([x for _, x, _ in data], default=1000) * 1.08)
    ax.grid(True, color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)

    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def write_outputs(points: list[SweepPoint], out_dir: Path) -> None:
    n = len(points[0].records) if points else 0
    md = [
        "# Baseline threshold sweep",
        "",
        f"{n} clips from the manifest, energy VAD (-45 dBFS, 32 ms frames), first `END` per clip, no padding.",
        "Cut-off = first END before `true_end_ms`. Wait time = first END − `true_end_ms`, on clips not cut off.",
        "\"No end\" = no END inside the clip: not a Cut-off, not in the wait stats.",
        "Median and p95 use linear interpolation (numpy's default). With 10 fluent and 4 pauses clips, p95 is close to the maximum.",
        "",
        "![sweep](sweep.png)",
        "",
        sweep_table(points),
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sweep.md").write_text("\n".join(md), encoding="utf-8", newline="\n")
    rows = [{"threshold_ms": p.threshold_ms, **r} for p in points for r in p.records]
    write_csv(out_dir / "sweep_clips.csv", rows, ["threshold_ms", *RECORD_COLUMNS])
    plot(points, out_dir / "sweep.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR)
    parser.add_argument("--thresholds", type=int, nargs="+", default=THRESHOLDS_MS)
    args = parser.parse_args()

    points = sweep(load_clips(args.manifest), args.thresholds)
    write_outputs(points, args.out)
    print(sweep_table(points))
    print(f"-> {args.out / 'sweep.md'}, sweep_clips.csv, sweep.png")


if __name__ == "__main__":
    main()
