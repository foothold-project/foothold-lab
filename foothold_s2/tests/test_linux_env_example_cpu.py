"""machines/AI-WS01-linux.env.example fills the Linux training profile and fails closed on TODO."""
import importlib.util
from pathlib import Path

import pytest

from foothold_s2.machine_profile import load_machine_profile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_linux_env", ROOT / "machines/check_linux_env.py")
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)

ENV = (ROOT / "machines/AI-WS01-linux.env.example").read_text(encoding="utf-8")
YAML = (ROOT / "machines/AI-WS01-linux.yaml").read_text(encoding="utf-8")
TODO = {"ISAAC311_PYTHON", "RSL_RL_MODULE", "ISAAC_SIM_ROOT", "TELEGRAM_SCRIPT",
        "TELEGRAM_OUTBOX", "GPU0_UUID", "GPU1_UUID"}


def test_every_profile_variable_is_set_or_todo():
    values, todo = chk.parse_env(ENV)
    assert chk.coverage_problems(YAML, values, todo) == []
    assert todo == TODO
    assert len(chk.profile_vars(YAML)) == 29  # 27 path fields + GPU0_UUID + GPU1_UUID
    assert values["S2_LAB_ROOT"] == chk.FAKE_HOME + "/data/foothold/s2_lab"
    assert values["MAI_TMP_ROOT"] == chk.FAKE_HOME + "/mai/tmp"
    assert values["ISAAC_CACHE_ROOT"].startswith(chk.FAKE_HOME + "/mai/cache/")


def test_coverage_catches_a_missing_variable():
    values, todo = chk.parse_env(ENV)
    values.pop("GPU_JOBS_QUEUE")
    assert chk.coverage_problems(YAML, values, todo) == [
        "profile variable GPU_JOBS_QUEUE is neither set nor marked TODO-measure-on-linux"]


def test_loader_fails_closed_until_todo_values_are_measured():
    values, _ = chk.parse_env(ENV)
    with pytest.raises(ValueError, match="requires environment variable (ISAAC_SIM_ROOT|ISAAC311_PYTHON)"):
        load_machine_profile(profile=ROOT / "machines/AI-WS01-linux.yaml", environ=values, platform="linux")
    filled = dict(values, ISAAC311_PYTHON="/opt/conda/envs/isaac311/bin/python",
                  RSL_RL_MODULE="/opt/rsl_rl/__init__.py", ISAAC_SIM_ROOT="/opt/isaacsim")
    with pytest.raises(ValueError, match="GPU UUID missing"):
        load_machine_profile(profile=ROOT / "machines/AI-WS01-linux.yaml", environ=filled, platform="linux")
    filled.update(GPU0_UUID="uuid-a", GPU1_UUID="uuid-b")
    prof = load_machine_profile(profile=ROOT / "machines/AI-WS01-linux.yaml", environ=filled, platform="linux")
    assert prof["paths"]["gpu_queue"] == chk.FAKE_HOME + "/mai/tmp/gpu/queue.json"
    assert "telegram_script" not in prof["paths"]  # optional, unset until measured
    assert all(p.startswith("/") for p in prof["paths"].values())


def _ops_from(values):
    h = chk.FAKE_HOME
    t = lambda v: "~" + v[len(h):]
    return {"paths": {
        "gpu_root": t(values["MAI_TMP_ROOT"] + "/gpu"),
        "w78_video": t(values["EX41_W78_VIDEO_ROOT"]),
        "c_layer_priority": t(values["S2_LAB_ROOT"] + "/c_layer_m6000/priority"),
        "eval_root": t(values["S2_LAB_ROOT"] + "/EX41-RUN/eval/score-watch"),
        "p1_attempt_glob": t(values["S2_LAB_ROOT"] + "/ex41_main_*/eval/score-watch/model_*/attempt.json"),
        "baseline_m6000": t(values["S2_LAB_ROOT"] + "/EX40/map_modes.json"),
        "stage_table": t(values["MAI_WORKTREE_ROOT"] + "/X/ex41.yaml"),
        "worklist": t(values["MAI_WORKTREE_ROOT"] + "/X/WORKLIST.tsv"),
        "canon_retry": t(values["MAI_WORKTREE_ROOT"] + "/X/canon_retry.py"),
        "c_layer_out": t(values["MAI_TMP_ROOT"] + "/c_layer_m6000/out"),
    }}


def test_ops_check_passes_matching_and_catches_moved_s2_lab():
    values, _ = chk.parse_env(ENV)
    good = _ops_from(values)
    assert chk.ops_problems(values, good) == []
    bad = {"paths": dict(good["paths"], c_layer_priority="~/mai/data/s2_lab/c_layer_m6000/priority",
                         eval_root="~/mai/data/s2_lab/EX41-RUN/eval/score-watch")}
    got = chk.ops_problems(values, bad)
    assert len(got) == 3 and all("s2_lab" in line for line in got), got
