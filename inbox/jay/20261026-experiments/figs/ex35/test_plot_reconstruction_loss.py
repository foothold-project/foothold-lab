"""Known-input checks for the reconstruction-loss plot data reader."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from tensorboard.summary.writer.event_file_writer import EventFileWriter
from tensorboard.compat.proto.event_pb2 import Event
from tensorboard.compat.proto.summary_pb2 import Summary


MODULE = Path(__file__).with_name("plot_reconstruction_loss.py")
SPEC = importlib.util.spec_from_file_location("plot_reconstruction_loss", MODULE)
assert SPEC is not None and SPEC.loader is not None
plot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plot)


def make_events(directory: Path, steps: list[int]) -> Path:
    writer = EventFileWriter(str(directory))
    try:
        for step in steps:
            summary = Summary(value=[Summary.Value(tag="Loss/perception/l_tr", simple_value=step / 10)])
            writer.add_event(Event(step=step, summary=summary))
        writer.flush()
    finally:
        writer.close()
    return next(directory.glob("events.out.tfevents.*"))


def test_exact_scalar_steps(tmp_path: Path) -> None:
    event_file = make_events(tmp_path, [0, 1, 2])
    assert plot.read_scalar(event_file, "Loss/perception/l_tr", 0, 2) == pytest.approx([0, 0.1, 0.2])
    with pytest.raises(AssertionError, match="scalar missing"):
        plot.read_scalar(event_file, "Loss/perception/hb", 0, 2)
    with pytest.raises(AssertionError, match="expected 4 rows"):
        plot.read_scalar(event_file, "Loss/perception/l_tr", 0, 3)


def test_hole_with_same_row_count_rejected(tmp_path: Path) -> None:
    event_file = make_events(tmp_path, [0, 1, 3])
    with pytest.raises(AssertionError, match="missing, repeated or reordered"):
        plot.read_scalar(event_file, "Loss/perception/l_tr", 0, 2)
