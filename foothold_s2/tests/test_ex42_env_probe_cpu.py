from __future__ import annotations

import ast
from pathlib import Path

import pytest

from foothold_s2.scripts.ex42_env_probe import (
    KIT_PROBE_TIMEOUT_S,
    build_parser,
    validate_probe_request,
)


def test_environment_probe_request_is_limited_to_cuda1_and_five_steps():
    assert validate_probe_request("cuda:1", 3) == 3
    for device, steps in (("cuda:0", 3), ("cuda:1", 0), ("cuda:1", 6)):
        with pytest.raises(ValueError):
            validate_probe_request(device, steps)


def test_environment_probe_cli_has_small_bounded_step_count_and_receipt_paths():
    args = build_parser().parse_args([
        "--device", "cuda:1", "--steps", "3",
        "--receipt", "D:/mai-tmp/runner/env_probe.json",
        "--done-file", "D:/mai-tmp/runner/env_probe.done",
    ])
    assert (args.device, args.steps, args.headless) == ("cuda:1", 3, True)
    assert str(args.receipt).endswith("env_probe.json")
    assert str(args.done_file).endswith("env_probe.done")
    assert KIT_PROBE_TIMEOUT_S <= 15 * 60


def test_kit_environment_probe_creates_and_steps_only_the_tiny_probe_env():
    script = Path(__file__).parents[1] / "scripts/ex42_env_probe.py"
    tree = ast.parse(script.read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert any(isinstance(node.func, ast.Attribute) and node.func.attr == "make"
               and isinstance(node.func.value, ast.Name) and node.func.value.id == "gym"
               for node in calls)
    assert any(isinstance(node.func, ast.Attribute) and node.func.attr == "step"
               for node in calls)
    assert not any(isinstance(node.func, ast.Name) and node.func.id in {"train", "learn"}
                   for node in calls)
