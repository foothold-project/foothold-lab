"""Actual module CLI guards for the bounded EX-40 smoke route."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def _launch(tmp_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    args = [
        sys.executable, "-m", "foothold_s2.ex40_launch",
        "--arm", "B", "--device", "cuda:0",
        "--end-by", "2026-11-01T00:00:00+09:00",
        "--log-root", str(tmp_path / "logs"),
        "--score-dir", str(tmp_path / "scores"),
        *extra,
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(args, cwd=ROOT, env=env, text=True,
                          encoding="utf-8", capture_output=True, check=False)


def test_official_smoke_cli_emits_bounded_cpu_receipt(tmp_path: Path) -> None:
    result = _launch(tmp_path, "--smoke")
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["state"] == "CPU_PREPARED_NOT_LAUNCHED"
    assert receipt["kit_verified"] is False
    assert receipt["training_started"] is False
    assert receipt["parser"]["max_iterations"] == 18
    assert "--curriculum-kit-smoke" in receipt["argv"]
    assert "--basic-stage" in receipt["argv"]
    assert receipt["argv"][receipt["argv"].index("--basic-stage") + 1] == "smoke"
    assert not (tmp_path / "logs").exists()


def test_official_main_cli_still_refuses_unverified_adapter(tmp_path: Path) -> None:
    result = _launch(tmp_path)
    assert result.returncode == 2
    assert "runtime adapter is not verified" in result.stderr
    assert not (tmp_path / "logs").exists()


def test_official_resume_cli_still_refuses_before_reading_spec(tmp_path: Path) -> None:
    result = _launch(tmp_path, "--resume-spec", str(tmp_path / "missing-resume.json"))
    assert result.returncode == 2
    assert "runtime adapter is not verified" in result.stderr
    assert "missing-resume.json" not in result.stderr
    assert not (tmp_path / "logs").exists()
