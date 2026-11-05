from __future__ import annotations

import ast
from pathlib import Path

import pytest

from foothold_s2.terrains.ex42 import (
    PAPER_EXT_SPECS,
    evaluation_dimensions,
    paper_ext_subterrains,
)
from foothold_s2.scripts.ex42_kit_probe import (
    KIT_PROBE_TIMEOUT_S,
    build_parser,
)


def test_paper_extension_specs_match_d182_dimensions_without_isaac_import():
    assert [row.kind for row in PAPER_EXT_SPECS] == [
        "slope_steep", "slope_steep_inv", "stairs_high", "stairs_high_inv"
    ]
    assert [row.range_value[1] for row in PAPER_EXT_SPECS] == [0.70, 0.70, 0.30, 0.30]
    assert PAPER_EXT_SPECS[0].range_key == "slope_range"
    assert PAPER_EXT_SPECS[2].range_key == "step_height_range"


def test_evaluation_scale_is_axis_named_and_keeps_other_dimensions():
    actual = evaluation_dimensions({
        "stone_gap_m": 0.30,
        "beam_width_m": 0.20,
        "stairs_support_m": 1.2,
        "slope_ratio": 0.70,
    })
    assert actual == pytest.approx({
        "stone_gap_m": 0.345,
        "beam_width_m": 0.17,
        "stairs_support_m": 1.02,
        "slope_ratio": 0.70,
    })


def test_eval_scale_rejects_non_finite_inputs():
    with pytest.raises(ValueError, match="finite"):
        evaluation_dimensions({"gap_m": float("nan")})


def test_kit_config_builder_fails_explicitly_without_isaac(monkeypatch):
    import builtins

    original = builtins.__import__

    def reject_isaac(name, *args, **kwargs):
        if name == "isaaclab.terrains":
            raise ImportError("pxr unavailable outside Kit")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_isaac)
    with pytest.raises(RuntimeError, match="require the Kit Python environment"):
        paper_ext_subterrains({
            "slope_steep": 1.0,
            "slope_steep_inv": 1.0,
            "stairs_high": 1.0,
            "stairs_high_inv": 1.0,
        })


def test_builder_rejects_unspecified_or_unapproved_kind_allocation():
    with pytest.raises(ValueError, match="name all four"):
        paper_ext_subterrains({"slope_steep": 1.0})


def test_kit_probe_is_cuda1_only_bounded_and_never_creates_or_trains_an_env():
    assert KIT_PROBE_TIMEOUT_S <= 15 * 60
    args = build_parser().parse_args([
        "--device", "cuda:1", "--headless",
        "--receipt", "D:/mai-tmp/runner/probe.json",
        "--done-file", "D:/mai-tmp/runner/probe.done",
    ])
    assert args.device == "cuda:1" and args.headless is True
    script = Path(__file__).parents[1] / "scripts/ex42_kit_probe.py"
    tree = ast.parse(script.read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert not any(isinstance(node.func, ast.Attribute)
                   and node.func.attr == "make"
                   and isinstance(node.func.value, ast.Name)
                   and node.func.value.id == "gym" for node in calls)
    assert not any(isinstance(node.func, ast.Name)
                   and node.func.id in {"train", "learn"} for node in calls)
