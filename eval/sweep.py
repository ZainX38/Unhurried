"""Sweep the Baseline's fixed silence threshold (ticket 03) and place the Patient on it (ticket 05).

Runs the VAD once per clip, then replays every clip at each threshold, and
through the Patient endpointer at each `complete_ms` setting, and writes:

- eval/results/sweep.md         summary vs the targets, then per-group cut-off rate, no-ends, wait median and p95
- eval/results/sweep_clips.csv  every per-clip record, with a threshold_ms column
- eval/results/sweep.png        stammered cut-off rate (y) vs fluent median wait (x), one point per threshold,
                                plus one point per Patient setting
- eval/results/results.md       Patient vs Baseline: summary, chart, per group, every Patient miss, caveats
- eval/results/patient_clips.csv  every Patient per-clip record, with a complete_ms column
- eval/results/cutoff_by_threshold.png  cut-off rate (y) vs threshold (x), one line per group

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
    DEFAULT_MANIFEST, GROUPS, ORACLE_DELAY_MS, RECORD_COLUMNS, RESULTS_DIR,
    Clip, baseline_factory, fmt_ms, fmt_rate, group_table, load_clips, patient_factory, run, write_csv,
)

THRESHOLDS_MS = [300, 500, 700, 1000, 1500, 2000, 3000, 4000]
PATIENT_COMPLETE_MS = [700, 400]  # Patient settings plotted against the curve

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
PATIENT = "#eb6834"  # second categorical slot (orange); validated against SERIES and SURFACE
# Fixed categorical order (blue, orange, aqua), so a group keeps its colour in every chart.
GROUP_COLORS = {"fluent": "#2a78d6", "stammered": "#eb6834", "pauses": "#1baf7a"}
# Shape as a second channel: where lines overlap, a large square shows under a small triangle.
GROUP_MARKERS = {"fluent": ("o", 64), "stammered": ("s", 110), "pauses": ("^", 50)}


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


@dataclass(frozen=True)
class PatientPoint:
    complete_ms: int
    records: list[dict]
    stats: dict  # group -> metrics.GroupStats


def patient_points(clips: list[Clip], complete_values: list[int] = PATIENT_COMPLETE_MS) -> list[PatientPoint]:
    """Replay the same clips through the Patient endpointer at each complete_ms setting."""
    points = []
    for c in complete_values:
        records = run(clips, patient_factory(c))
        points.append(PatientPoint(c, records, metrics.summarize(records)))
    return points


def meets_targets(p: SweepPoint | PatientPoint) -> bool:
    """Spec targets: fluent median Wait time <= 900 ms AND stammered Cut-off rate < 5%."""
    fluent, stammered = p.stats.get("fluent"), p.stats.get("stammered")
    return (
        fluent is not None and fluent.wait_median is not None
        and fluent.wait_median <= TARGET_FLUENT_WAIT_MS
        and stammered is not None and stammered.cut_off_rate is not None
        and stammered.cut_off_rate < TARGET_STAMMERED_CUT_OFF
    )


def summary_table(points: list[SweepPoint]) -> str:
    """One row per threshold: the two target numbers, fluent cut-offs, and whether both targets are met."""
    lines = [
        f"| threshold (ms) | stammered cut-off (target < {TARGET_STAMMERED_CUT_OFF:.0%}) "
        f"| fluent median wait (ms, target ≤ {TARGET_FLUENT_WAIT_MS}) | fluent cut-off | both targets met |",
        "| ---: | ---: | ---: | ---: | :---: |",
    ]
    for p in points:
        fluent, stammered = p.stats.get("fluent"), p.stats.get("stammered")
        lines.append(
            f"| {p.threshold_ms} | {fmt_rate(stammered)} | {fmt_ms(fluent.wait_median if fluent else None)} "
            f"| {fmt_rate(fluent)} | {'✅' if meets_targets(p) else '❌'} |"
        )
    return "\n".join(lines)


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


def chart_xy(stats: dict) -> tuple[float, float] | None:
    """(fluent median wait, stammered cut-off rate), or None if either is missing."""
    fluent, stammered = stats.get("fluent"), stats.get("stammered")
    if fluent is None or stammered is None:
        return None
    if fluent.wait_median is None or stammered.cut_off_rate is None:
        return None  # e.g. every fluent clip cut off: no wait to plot
    return fluent.wait_median, stammered.cut_off_rate


def curve(points: list[SweepPoint]) -> list[tuple[int, float, float]]:
    """(threshold, fluent median wait, stammered cut-off rate) for every threshold where both exist."""
    return [(p.threshold_ms, *xy) for p in points if (xy := chart_xy(p.stats)) is not None]


def plot(points: list[SweepPoint], path: Path, patients: list[PatientPoint] = ()) -> None:
    data = curve(points)
    patient_data = [(pp.complete_ms, *xy) for pp in patients if (xy := chart_xy(pp.stats)) is not None]
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
        ax.plot(waits, rates_pct, color=SERIES, lw=2, zorder=2, label="Baseline (fixed threshold)")
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

    for c, x, y in patient_data:
        # Diamond with a surface ring: a second channel besides colour, and it stays visible on the curve.
        ax.scatter([x], [y * 100], s=90, marker="D", color=PATIENT, edgecolor=SURFACE, linewidth=2, zorder=4,
                   label="Patient endpointer (label: complete_ms)" if c == patient_data[0][0] else None)
        # Settings sit close together, so only the number; the legend says what it is.
        ax.annotate(f"{c} ms", (x, y * 100), xytext=(0, -10), textcoords="offset points",
                    ha="center", va="top", color=INK, fontsize=8)

    if patient_data:
        fig.suptitle("Patient endpointer vs the fixed-threshold curve", color=INK, fontsize=11, x=0.02, ha="left")
        ax.set_title("Blue: one point per fixed silence threshold (ms). Orange: the Patient, which starts at 700 ms\n"
                     "and waits longer only when the words say the answer isn't finished.",
                     color=INK_SECONDARY, fontsize=9, loc="left", pad=10)
        ax.legend(loc="center right", frameon=False, fontsize=8, labelcolor=INK_SECONDARY)
    else:
        fig.suptitle("Baseline sweep: raising the fixed timeout costs fluent callers",
                     color=INK, fontsize=11, x=0.02, ha="left")
        ax.set_title("Each point is one fixed silence threshold (ms)", color=INK_SECONDARY, fontsize=9, loc="left", pad=10)
    ax.set_xlabel("fluent median wait time (ms)", color=INK_SECONDARY, fontsize=9)
    ax.set_ylabel("stammered cut-off rate (%)", color=INK_SECONDARY, fontsize=9)
    ax.set_ylim(-3, 105)
    ax.set_xlim(0, max([x for _, x, _ in data] + [x for _, x, _ in patient_data], default=1000) * 1.08)
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


def style_axes(fig, ax) -> None:
    """Shared chrome: light surface, hairline solid grid, muted ticks, no top/right spines."""
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)


def plot_cutoff_by_threshold(points: list[SweepPoint], path: Path) -> None:
    """Cut-off rate per group against the threshold. Lines overlap at 0% and 100%, so each
    line gets a surface-coloured ring and a direct label where the groups are most spread out."""
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    style_axes(fig, ax)

    ax.axhline(TARGET_STAMMERED_CUT_OFF * 100, color=MUTED, lw=1, ls=(0, (4, 3)), zorder=1)
    ax.text(1, TARGET_STAMMERED_CUT_OFF * 100 + 1, "stammered target < 5% ",
            color=INK_SECONDARY, fontsize=8, va="bottom", ha="right", transform=ax.get_yaxis_transform())

    thresholds = [p.threshold_ms for p in points]
    present = [g for g in GROUPS if any(g in p.stats for p in points)]
    spread = {}  # group -> (x, y) of its label
    for z, g in enumerate(present):
        xs = [p.threshold_ms for p in points if g in p.stats and p.stats[g].cut_off_rate is not None]
        ys = [p.stats[g].cut_off_rate * 100 for p in points if g in p.stats and p.stats[g].cut_off_rate is not None]
        if not xs:
            continue
        color = GROUP_COLORS.get(g, SERIES)
        marker, size = GROUP_MARKERS.get(g, ("o", 64))
        ax.plot(xs, ys, color=SURFACE, lw=5, zorder=2 + z, solid_capstyle="round")  # ring where lines cross
        ax.plot(xs, ys, color=color, lw=2, zorder=2 + z, marker=marker, markersize=size ** 0.5,
                markeredgecolor=SURFACE, markeredgewidth=1.5, label=g)
        # Label at the threshold where this group sits furthest from the others.
        others = [h for h in present if h != g]
        def gap(i: int) -> float:
            ds = [abs(ys[i] - points[i].stats[h].cut_off_rate * 100) for h in others
                  if h in points[i].stats and points[i].stats[h].cut_off_rate is not None]
            return min(ds, default=100)
        best = max(range(len(xs)), key=lambda i: (gap(i), -abs(ys[i] - 50)))
        spread[g] = (xs[best], ys[best])

    for g, (x, y) in spread.items():
        ax.annotate(g, (x, y), xytext=(8, 4), textcoords="offset points", color=INK, fontsize=9,
                    va="bottom", ha="left")

    ax.legend(loc="upper right", frameon=False, fontsize=8, labelcolor=INK_SECONDARY)
    fig.suptitle("Cut-off rate by fixed silence threshold", color=INK, fontsize=11, x=0.02, ha="left")
    ax.set_title("Share of each group's clips where the Baseline ended before the caller finished. "
                 "Where lines overlap,\nthe groups have the same rate (squares = stammered, triangles = pauses).",
                 color=INK_SECONDARY, fontsize=9, loc="left", pad=10)
    ax.set_xlabel("Baseline silence threshold (ms)", color=INK_SECONDARY, fontsize=9)
    ax.set_ylabel("cut-off rate (%)", color=INK_SECONDARY, fontsize=9)
    ax.set_xticks(thresholds)
    ax.tick_params(axis="x", labelrotation=0)
    ax.set_ylim(-3, 105)
    ax.set_xlim(0, max(thresholds, default=1000) * 1.05)

    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def comparison_table(points: list[SweepPoint], patients: list[PatientPoint]) -> str:
    """Patient settings next to the Baseline at 700 ms (same start) and at the first threshold
    that meets the stammered target (what a fixed timeout must cost to protect stammerers)."""
    rows: list[tuple[str, dict]] = []
    by_t = {p.threshold_ms: p for p in points}
    if 700 in by_t:
        rows.append(("Baseline 700 ms", by_t[700].stats))
    safe = next((p for p in points if (st := p.stats.get("stammered")) is not None
                 and st.cut_off_rate is not None and st.cut_off_rate < TARGET_STAMMERED_CUT_OFF), None)
    if safe is not None and safe.threshold_ms != 700:
        rows.append((f"Baseline {safe.threshold_ms} ms (first to meet the stammered target)", safe.stats))
    rows += [(f"**Patient, complete {pp.complete_ms} ms**", pp.stats) for pp in patients]

    lines = [
        f"| endpointer | stammered cut-off (target < {TARGET_STAMMERED_CUT_OFF:.0%}) "
        f"| fluent median wait (ms, target ≤ {TARGET_FLUENT_WAIT_MS}) | fluent p95 wait (ms) "
        f"| fluent cut-off | pauses cut-off | both targets met |",
        "| --- | ---: | ---: | ---: | ---: | ---: | :---: |",
    ]
    for name, stats in rows:
        fluent = stats.get("fluent")
        met = meets_targets(SweepPoint(0, [], stats))
        lines.append(
            f"| {name} | {fmt_rate(stats.get('stammered'))} | {fmt_ms(fluent.wait_median if fluent else None)} "
            f"| {fmt_ms(fluent.wait_p95 if fluent else None)} | {fmt_rate(fluent)} | {fmt_rate(stats.get('pauses'))} "
            f"| {'✅' if met else '❌'} |"
        )
    return "\n".join(lines)


def misses_table(patients: list[PatientPoint]) -> str:
    """Every clip the Patient cut off or never ended, with its reason, once per setting it happens in."""
    seen: dict[tuple[str, str, str], list[int]] = {}
    for pp in patients:
        for r in pp.records:
            if r["outcome"] != "ended":
                seen.setdefault((r["file"], r["outcome"], r["reason"]), []).append(pp.complete_ms)
    if not seen:
        return "None."
    lines = ["| clip | outcome | at complete_ms | reason at the END |", "| --- | --- | --- | --- |"]
    for (file, outcome, reason), settings in seen.items():
        lines.append(f"| {file} | {outcome} | {', '.join(map(str, settings))} | {reason or '-'} |")
    return "\n".join(lines)


# Short factual caveats only. Interpretation goes in the hand-written eval/results/discussion.md.
CAVEATS = f"""\
- Transcripts are an oracle, not STT: each piece's exact text appears {ORACLE_DELAY_MS} ms after its speech
  ends, lowercased and without punctuation. Real STT (ticket 06) adds mishearings and its own latency.
- A COMPLETE answer can only end the Turn once its last words are in the transcript, so no wait here is
  shorter than {ORACLE_DELAY_MS} ms, whatever `complete_ms` is.
- Pauses clips (P_*) have no piece timing and get `transcript=None`: timing-only, the same rule as the
  700 ms Baseline.
- The oracle text has no repeated words and every clip is one Turn, so the repetition bonus and call
  memory never fire in this run. They are tested only in `tests/test_patient.py`.
"""


def results_md(points: list[SweepPoint], patients: list[PatientPoint]) -> str:
    n = len(patients[0].records) if patients else 0
    out = [
        "# Results: Patient endpointer vs the Baseline",
        "",
        "Generated by `uv run python -m eval.sweep`; do not edit by hand. Interpretation: [discussion.md](discussion.md).",
        "",
        f"{n} clips from the manifest, same VAD, frames and scoring as [the Baseline sweep](sweep.md).",
        "`complete_ms` is the silence that ends a COMPLETE answer; base patience is 700 ms.",
        "",
        "## Summary",
        "",
        comparison_table(points, patients),
        "",
        "![Patient vs the fixed-threshold curve](sweep.png)",
        "",
        "## Per group",
        "",
    ]
    for pp in patients:
        out += [f"### Patient, complete {pp.complete_ms} ms", "", group_table(pp.stats), ""]
    out += ["## Every Patient miss", "", misses_table(patients), "", "## Caveats", "", CAVEATS]
    return "\n".join(out)


def write_outputs(points: list[SweepPoint], out_dir: Path, patients: list[PatientPoint] = ()) -> None:
    n = len(points[0].records) if points else 0
    md = [
        "# Baseline threshold sweep",
        "",
        f"{n} clips from the manifest, energy VAD (-45 dBFS, 32 ms frames), first `END` per clip, no padding.",
        "Cut-off = first END before `true_end_ms`. Wait time = first END − `true_end_ms`, on clips not cut off.",
        "\"No end\" = no END inside the clip: not a Cut-off, not in the wait stats.",
        "Median and p95 use linear interpolation (numpy's default). With 10 fluent and 4 pauses clips, p95 is close to the maximum.",
        "",
        "## Summary",
        "",
        summary_table(points),
        "",
        "![stammered cut-off vs fluent wait](sweep.png)",
        "",
        "![cut-off rate by threshold](cutoff_by_threshold.png)",
        "",
        "## Per group",
        "",
        sweep_table(points),
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sweep.md").write_text("\n".join(md), encoding="utf-8", newline="\n")
    rows = [{"threshold_ms": p.threshold_ms, **r} for p in points for r in p.records]
    write_csv(out_dir / "sweep_clips.csv", rows, ["threshold_ms", *RECORD_COLUMNS])
    plot(points, out_dir / "sweep.png", list(patients))
    plot_cutoff_by_threshold(points, out_dir / "cutoff_by_threshold.png")
    if patients:
        (out_dir / "results.md").write_text(results_md(points, list(patients)), encoding="utf-8", newline="\n")
        rows = [{"complete_ms": pp.complete_ms, **r} for pp in patients for r in pp.records]
        write_csv(out_dir / "patient_clips.csv", rows, ["complete_ms", *RECORD_COLUMNS])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR)
    parser.add_argument("--thresholds", type=int, nargs="+", default=THRESHOLDS_MS)
    parser.add_argument("--patient-complete-ms", type=int, nargs="*", default=PATIENT_COMPLETE_MS,
                        help="Patient settings to plot; pass none to plot the Baseline only")
    args = parser.parse_args()

    clips = load_clips(args.manifest)
    points = sweep(clips, args.thresholds)
    patients = patient_points(clips, args.patient_complete_ms)
    write_outputs(points, args.out, patients)
    print(sweep_table(points))
    for pp in patients:  # plain ASCII: the Windows console can't print the table's symbols
        fluent = pp.stats.get("fluent")
        print(f"Patient complete {pp.complete_ms} ms: stammered cut-off {fmt_rate(pp.stats.get('stammered'))}, "
              f"fluent median wait {fmt_ms(fluent.wait_median if fluent else None)} ms")
    print(f"-> {args.out / 'sweep.md'}, sweep_clips.csv, sweep.png"
          + (", results.md, patient_clips.csv" if patients else ""))


if __name__ == "__main__":
    main()
