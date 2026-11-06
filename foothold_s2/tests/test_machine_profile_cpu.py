from __future__ import annotations

from pathlib import Path
from pathlib import PureWindowsPath
import re

import pytest

from foothold_s2.machine_profile import load_machine_profile, machine_path


REPO = Path(__file__).resolve().parents[2]


def test_windows_profile_preserves_known_ops_check_install_and_roots():
    profile = load_machine_profile(
        environ={"FOOTHOLD_MACHINE_PROFILE": "machines/AI-WS01-windows.yaml"},
        platform="win32")
    paths = profile["paths"]
    assert PureWindowsPath(paths["isaaclab_root"]).as_posix() == "C:/isaac/IsaacLab"
    assert PureWindowsPath(paths["isaac_sim_root"]).as_posix() == "C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/isaacsim"
    assert PureWindowsPath(paths["conda_python"]).as_posix() == "C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe"
    assert PureWindowsPath(paths["rsl_rl_module"]).as_posix().endswith("/Lib/site-packages/rsl_rl/__init__.py")
    assert PureWindowsPath(paths["s2_lab_root"]).as_posix() == "C:/Users/AI-WS01/s2_lab"
    assert PureWindowsPath(paths["mai_tmp_root"]).as_posix() == "D:/mai-tmp"
    assert PureWindowsPath(paths["mai_worktree_root"]).as_posix() == "D:/mai-wt/foothold-lab"


def test_linux_profile_requires_explicitly_bound_machine_values():
    profile_file = REPO / "machines/AI-WS01-linux.yaml"
    values = {
        "FOOTHOLD_MACHINE_PROFILE": "machines/AI-WS01-linux.yaml",
        "ISAACLAB_ROOT": "/opt/isaaclab",
        "ISAAC_SIM_ROOT": "/opt/isaacsim",
        "ISAAC311_PYTHON": "/opt/conda/envs/isaac311/bin/python",
        "RSL_RL_MODULE": "/opt/conda/envs/isaac311/lib/python3.11/site-packages/rsl_rl/__init__.py",
        "S2_LAB_ROOT": "/srv/s2_lab",
        "MAI_TMP_ROOT": "/srv/mai-tmp",
        "MAI_WORKTREE_ROOT": "/srv/mai-wt/foothold-lab",
        "ISAAC_CACHE_ROOT": "/srv/isaac-cache",
        "FOOTHOLD_BASH": "/usr/bin/bash",
        "GPU_JOBS_CONFIG": "/srv/s2_lab/gpu_jobs/jobs.json",
        "GPU_JOBS_QUEUE": "/srv/mai-tmp/gpu/queue.json",
        "PLAYLIST_ROOT": "/srv/s2_lab/playlists",
        "C_LAYER_LOCK": "/srv/s2_lab/c_layer.lock",
        "A_LAYER_MARKER": "/srv/s2_lab/a_layer.marker",
        "EX41_STAGE_VIDEO_SOURCE": "/srv/foothold/scripter-stagevideo",
        "EX41_STAGE_VIDEO_OUTPUT": "/srv/mai-tmp/ex41-video",
        "EX41_W78_VIDEO_ROOT": "/srv/mai-tmp/ex41/w78-video",
        "RUNNER_HOME": "/srv/mai-tmp/runner",
        "TELEGRAM_OUTBOX": "/srv/telemetry/outbox",
        "TELEGRAM_SCRIPT": "/srv/telemetry/send.sh",
        "GPU0_TRAINING_MARKER": "/srv/markers/train0",
        "GPU0_TRAINING_MARKER_ALT": "/srv/markers/train0-alt",
        "GPU1_TRAINING_MARKER": "/srv/markers/train1",
        "GPU0_EVAL_MARKER": "/srv/markers/eval0",
        "GPU1_EVAL_MARKER": "/srv/markers/eval1",
        "EX41_PUSH250_OUTPUT": "/srv/mai-tmp/runner/push250",
    }
    loaded = load_machine_profile(environ=values, platform="linux")
    assert loaded["machine_id"] == "AI-WS01-linux"
    assert machine_path("isaaclab_root", environ=values, platform="linux") == Path("/opt/isaaclab")
    missing = dict(values)
    missing.pop("RSL_RL_MODULE")
    with pytest.raises(ValueError, match="RSL_RL_MODULE"):
        load_machine_profile(environ=missing, platform="linux")


def test_posix_requires_profile_selection_instead_of_windows_drive_defaults():
    with pytest.raises(ValueError, match="FOOTHOLD_MACHINE_PROFILE"):
        load_machine_profile(environ={}, platform="linux")


def test_active_ex42_launch_modules_have_no_machine_drive_literals():
    active = (
        REPO / "foothold_s2/ex41_start_preflight.py",
        REPO / "foothold_s2/runtime_environment.py",
        REPO / "foothold_s2/scripts/train_start.py",
        REPO / "foothold_s2/scripts/ex42_ops.py",
        REPO / "foothold_s2/run_ex42.ps1",
        REPO / "foothold_s2/scripts/ex41_startup.py",
        REPO / "foothold_s2/ex41_eval_once.py",
        REPO / "foothold_s2/ex41_score_watch.py",
        REPO / "foothold_s2/ex41_ops.py",
        REPO / "foothold_s2/eval/ex41_gpu_priority.py",
        REPO / "foothold_s2/eval/ex41_push250_watch.py",
        REPO / "foothold_s2/eval/ex41_push_ladder_bundle.py",
    )
    drive_literal = re.compile(r"(?i)(?<![A-Z0-9_])[A-Z]:[/\\]")
    for path in active:
        assert not drive_literal.search(path.read_text(encoding="utf-8")), path
