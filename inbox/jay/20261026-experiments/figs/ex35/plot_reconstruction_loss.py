"""Plot the recorded S-B10 and EX-35 map reconstruction losses.

Input is the original TensorBoard event file for each training segment.
Every requested scalar step must be present exactly once and finite.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator


TAGS = (
    ("Loss/perception/l_tr", "TR-Net map loss: rough MSE + refined L1"),
    ("Loss/perception/hb", "IE height-map decoder MSE"),
)


def read_scalar(event_file: Path, tag: str, first: int, last: int) -> list[float]:
    assert event_file.is_file(), f"event file missing: {event_file}"
    accumulator = EventAccumulator(str(event_file), size_guidance={"scalars": 0}).Reload()
    assert tag in accumulator.Tags()["scalars"], f"scalar missing: {tag} in {event_file}"
    rows = accumulator.Scalars(tag)
    assert len(rows) == last - first + 1, (
        f"{tag}: expected {last - first + 1} rows, got {len(rows)} in {event_file}"
    )
    steps = [row.step for row in rows]
    assert steps == list(range(first, last + 1)), (
        f"{tag}: missing, repeated or reordered steps in {event_file}: "
        f"first={steps[:3]}, last={steps[-3:]}"
    )
    values = [float(row.value) for row in rows]
    assert all(math.isfinite(value) for value in values), f"{tag}: nonfinite value in {event_file}"
    return values


def render(parent_events: Path, ex35_events: Path, excluded_events: Path, output: Path) -> None:
    # This short, superseded attempt overlaps EX-35 steps 1501-1502. Verify it,
    # then leave it out so neither step is counted twice in the plotted series.
    for tag, _ in TAGS:
        read_scalar(excluded_events, tag, 1501, 1502)
    series = [
        (tag, label, read_scalar(parent_events, tag, 0, 1500), read_scalar(ex35_events, tag, 1501, 2000))
        for tag, label in TAGS
    ]
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.90, bottom=0.23, hspace=0.34)
    for ax, (tag, label, parent, ex35) in zip(axes, series, strict=True):
        ax.plot(range(0, 1501), parent, color="#275d79", lw=1.3, label="S-B10 parent")
        ax.plot(range(1501, 2001), ex35, color="#c15c32", lw=1.5, label="EX-35 continuation")
        ax.axvline(1500.5, color="#444444", lw=0.9, ls=":")
        ax.set_ylabel("Logged loss")
        ax.set_title(f"{label}  ({tag})", loc="left", fontsize=11)
        ax.grid(alpha=0.2)
        ax.legend(loc="best")
    axes[-1].set_xlabel("TensorBoard training step")
    axes[-1].set_xlim(0, 2000)
    fig.suptitle("Map reconstruction losses: S-B10 to EX-35", fontsize=14)
    fig.text(
        0.08, 0.08,
        "Excluded overlapping two-step attempt (steps 1501-1502):\n"
        + str(excluded_events.resolve()),
        ha="left", va="top", fontsize=7, wrap=True,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=170)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-events", type=Path, required=True)
    parser.add_argument("--ex35-events", type=Path, required=True)
    parser.add_argument("--excluded-events", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render(args.parent_events, args.ex35_events, args.excluded_events, args.output)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
