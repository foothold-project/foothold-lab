"""L2: the EX-38 m3001 W15 evaluation can be launched on ai-lx01. CPU only, no Kit, no GPU."""
from __future__ import annotations

import ast
import json
import os
import shlex
import subprocess
from pathlib import Path

import pytest

from foothold_s2 import basic_gait_eval_once as once
from foothold_s2 import basic_gait_kit as kit

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "foothold_s2/eval/l2_w15_linux.sh"
RUN_KIT = ROOT / "foothold_s2/eval/run_kit.sh"
REF = Path("/mnt/win-d/mai/data/foothold/s2_lab/basic_gait_runs/eval_w15/ex38/m3001")
NAMES = ("A_LAYER_MARKER C_LAYER_LOCK EX41_PUSH250_OUTPUT EX41_STAGE_VIDEO_OUTPUT EX41_STAGE_VIDEO_SOURCE "
         "EX41_W78_VIDEO_ROOT FOOTHOLD_EX42_GATE_REPORT GPU0_EVAL_MARKER GPU0_TRAINING_MARKER GPU0_TRAINING_MARKER_ALT "
         "GPU1_EVAL_MARKER GPU1_TRAINING_MARKER GPU_JOBS_CONFIG GPU_JOBS_QUEUE ISAAC_SIM_ROOT ISAACLAB_ROOT MAI_TMP_ROOT "
         "MAI_WORKTREE_ROOT PLAYLIST_ROOT RSL_RL_MODULE RUNNER_HOME S2_LAB_ROOT TELEGRAM_OUTBOX TELEGRAM_SCRIPT").split()


def linux_env(tmp_path, **over):
    env = {n: str(tmp_path / n.lower()) for n in NAMES}
    env.update(ISAAC311_PYTHON=str(tmp_path / "envs/isaac311/bin/python"), ISAAC_CACHE_ROOT=str(tmp_path / "cache/DerivedDataCache"),
               FOOTHOLD_BASH="/bin/bash", GPU0_UUID="GPU-11111111-1111-1111-1111-111111111111",
               GPU1_UUID="GPU-22222222-2222-2222-2222-222222222222",
               FOOTHOLD_MACHINE_PROFILE=str(ROOT / "machines/AI-WS01-linux.yaml"))
    env.update(over)
    return env


# ---- the two Python spots that held Windows places ----

def test_kit_cache_arg_is_unchanged_without_a_profile_and_follows_the_profile_with_one(tmp_path):
    assert kit.kit_cache_arg({}) == kit.KIT_CACHE_ARG
    assert kit.KIT_CACHE_VALUE == "--/UJITSO/datastore/localCachePath=D:/mai-cache/isaacsim-5.1/DerivedDataCache"
    env = linux_env(tmp_path)
    assert kit.kit_cache_arg(env) == "--kit_args=--/UJITSO/datastore/localCachePath=" + env["ISAAC_CACHE_ROOT"]
    assert kit.kit_cache_arg(env) != kit.KIT_CACHE_ARG and kit.kit_cache_arg(env).count("--kit_args=") == 1


def test_shell_default_keeps_git_bash_without_a_profile_and_uses_foothold_bash_with_one(tmp_path, monkeypatch):
    monkeypatch.delenv("FOOTHOLD_MACHINE_PROFILE", raising=False)
    assert once.shell_default() == "C:/Program Files/Git/bin/bash.exe"
    for key, value in linux_env(tmp_path).items():
        monkeypatch.setenv(key, value)
    assert once.shell_default() == "/bin/bash"


def test_the_chain_really_goes_through_the_new_functions():
    tree = ast.parse((ROOT / "foothold_s2/basic_gait_eval_once.py").read_text(encoding="utf-8"))
    run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run")
    calls = {n.func.id for n in ast.walk(run) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert {"shell_default", "kit_cache_arg"} <= calls
    assigns = [ast.unparse(n) for n in ast.walk(run) if isinstance(n, ast.Assign) and "BASIC_GAIT_KIT_ARG" in ast.unparse(n)]
    assert assigns == ["env['BASIC_GAIT_KIT_ARG'] = kit_cache_arg()"]


# ---- run_kit.sh ----

def _fake_python(tmp_path):
    py = tmp_path / "envs/isaac311/bin/python"
    py.parent.mkdir(parents=True)
    py.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@"\necho "CONDA_PREFIX=$CONDA_PREFIX"\necho "EULA=$OMNI_KIT_ACCEPT_EULA ORDER=$CUDA_DEVICE_ORDER"\n', encoding="utf-8")
    py.chmod(0o755)
    return py


@pytest.mark.skipif(os.uname().sysname != "Linux", reason="Linux branch")
def test_run_kit_uses_the_profile_interpreter_on_linux(tmp_path):
    py = _fake_python(tmp_path)
    out = tmp_path / "o"
    env = dict(os.environ, ISAAC311_PYTHON=str(py), MODULE="foothold_s2.eval.eval_map_modes", DEVICE="cuda:0")
    done = subprocess.run(["bash", str(RUN_KIT), str(out), "--task", "T", "--envs", "64"], env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    log = (out / "run.log").read_text(encoding="utf-8").splitlines()
    assert log[:2] == ["-m", "foothold_s2.eval.eval_map_modes"] and "--headless" in log and log[log.index("--device") + 1] == "cuda:0"
    assert f"CONDA_PREFIX={py.parent.parent}" in log and "EULA=YES ORDER=PCI_BUS_ID" in log
    env.pop("ISAAC311_PYTHON")
    missing = subprocess.run(["bash", str(RUN_KIT), str(tmp_path / "o2")], env=env, capture_output=True, text=True)
    assert missing.returncode != 0 and "ISAAC311_PYTHON is not set" in missing.stderr


def test_run_kit_keeps_the_windows_lines_verbatim():
    text = RUN_KIT.read_text(encoding="utf-8")
    for line in ('  ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311',
                 '  PY="$ENV/python.exe"',
                 '  export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"'):
        assert line in text
    assert text.index('"$(uname -s)" = "Linux"') < text.index("ENV=/c/Users")      # Windows lines sit in the else branch


# ---- same arguments as the Windows reference ----

pytestmark_ref = pytest.mark.skipif(not REF.is_dir(), reason="Windows reference attempt not on this host")


def _argvs(tmp_path):
    """Run the real run_sb_eval.sh with a fake Kit runner; the env is what basic_gait_eval_once.run builds."""
    fake = tmp_path / "fake_kit.sh"
    fake.write_text("#!/usr/bin/env bash\nOUT=$1; shift\nmkdir -p \"$OUT\"\nprintf '%s\\n' \"$@\" > \"$OUT/argv.txt\"\n"
                    "echo TURNPROBE_DONE > \"$OUT/run.log\"\necho '{}' > \"$OUT/map_modes.json\"\n", encoding="utf-8")
    ck = tmp_path / "model_3001.pt"
    ck.write_bytes(b"fixture")
    out = tmp_path / "eval"
    env = os.environ.copy()
    env.update(MODES=" ".join(once.MODES), COMMAND_SUITE="extended", BASIC_GAIT_KIT_RUNNER=str(fake),
               BASIC_GAIT_KIT_ARG=kit.kit_cache_arg(linux_env(tmp_path)))
    done = subprocess.run(["bash", str(ROOT / "foothold_s2/eval/run_sb_eval.sh"), "cuda:0", str(ck), str(out)],
                          cwd=ROOT, env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    read = lambda sub: (out / sub / "argv.txt").read_text(encoding="utf-8").splitlines()
    return ck, read


@pytestmark_ref
def test_map64_and_turn16_arguments_equal_the_windows_reference(tmp_path):
    attempt = next(REF.glob("attempt_*"))
    m = json.loads((attempt / "map64/map_modes.json").read_text(encoding="utf-8"))
    ck, read = _argvs(tmp_path)
    arg = lambda argv, flag: argv[argv.index(flag) + 1]
    map64 = read("map64")
    assert arg(map64, "--task") == m["task"] and int(arg(map64, "--envs")) == m["envs"] == 64
    assert int(arg(map64, "--steps")) == m["steps"] == 300 and arg(map64, "--command-suite") == m["command_suite"] == "extended"
    assert arg(map64, "--modes").split(",") == list(once.MODES) and set(m["modes"]) == set(once.MODES)
    assert "--fixed-terrain" in map64 and "--fixed-level" not in map64 and m["fixed_terrain"]["fixed_level"] is None
    assert m["run_identity"]["eval_seed"] == 42 and "--eval-seed" not in map64         # default 42 is what the reference used
    assert m["run_identity"]["device"] == "cuda:0" and m["terrain_tiles"] and len(m["terrain_tiles"]) == 64
    assert sorted(m["commands"]) == sorted(json.loads((attempt / "w15_verified.json").read_text())["commands"])
    for mode in once.MODES:
        probe = json.loads((attempt / f"turn16_{mode}/probe_result.json").read_text(encoding="utf-8"))
        turn = read(f"turn16_{mode}")
        assert arg(turn, "--map-mode") == mode == probe["map_mode"] and arg(turn, "--envs") == str(probe["envs"]) == "16"
        assert "--cases" in turn and arg(turn, "--cases") == "all" and "--forward-gaits" in turn and probe["forward_gaits"]
        assert "--fixed-terrain" in turn and arg(turn, "--task") == probe["task"]
    assert any(x.startswith("--kit_args=--/UJITSO/datastore/localCachePath=") for x in map64)


@pytestmark_ref
def test_the_reference_checkpoint_is_the_one_the_launcher_pins():
    attempt = next(REF.glob("attempt_*"))
    verified = json.loads((attempt / "w15_verified.json").read_text(encoding="utf-8"))
    assert verified["checkpoint_sha256"] == "7ff575f356c27ab6280fa2e01dce40f806bbfdd89d4306ae63c827b3ff16706c"
    assert "7ff575f356c27ab6280fa2e01dce40f806bbfdd89d4306ae63c827b3ff16706c" in SCRIPT.read_text(encoding="utf-8")
    assert "model_3001.pt" in SCRIPT.read_text(encoding="utf-8") and verified["checkpoint_iter"] == 3001


# ---- the one launch command ----

def test_launch_command_is_the_chain_on_cuda0_with_the_linux_environment(tmp_path):
    env = dict(os.environ, ISAAC311_PYTHON="/opt/isaac311/bin/python")
    printed = subprocess.run(["bash", str(SCRIPT), "print"], env=env, capture_output=True, text=True, check=True).stdout
    argv = shlex.split(printed)
    assert argv[0] == "env" and "OMNI_KIT_ACCEPT_EULA=YES" in argv and "CUDA_DEVICE_ORDER=PCI_BUS_ID" in argv
    assert "CUDA_VISIBLE_DEVICES" not in printed
    i = argv.index("/opt/isaac311/bin/python")
    assert argv[i + 1:i + 3] == ["-m", "foothold_s2.basic_gait_eval_chain_v3"]
    assert argv[argv.index("--device") + 1] == "cuda:0"
    assert argv[argv.index("--checkpoint") + 1].endswith("EX-38-basic-e1rew_20261029_123840_163180/model_3001.pt")
    assert argv[argv.index("--out") + 1].endswith("/basic_gait_runs/eval_w15/ex38_linux")
    assert f"PYTHONPATH={ROOT}" in argv


def test_run_refuses_a_wrong_checkpoint_and_an_existing_output(tmp_path):
    ck = tmp_path / "model_3001.pt"
    ck.write_bytes(b"not the checkpoint")
    env = dict(os.environ, ISAAC311_PYTHON="/bin/false", L2_CHECKPOINT=str(ck), L2_OUT=str(tmp_path / "out"))
    bad = subprocess.run(["bash", str(SCRIPT), "run"], env=env, capture_output=True, text=True)
    assert bad.returncode == 2 and "sha256 differs" in bad.stderr
    env["L2_CHECKPOINT"] = str(tmp_path / "missing.pt")
    assert "checkpoint missing" in subprocess.run(["bash", str(SCRIPT), "run"], env=env, capture_output=True, text=True).stderr
    no_env = {k: v for k, v in os.environ.items() if k != "ISAAC311_PYTHON"}
    assert "ISAAC311_PYTHON is not set" in subprocess.run(["bash", str(SCRIPT), "print"], env=no_env, capture_output=True, text=True).stderr


def test_compare_calls_w15_compare_twice_with_the_right_pairs(tmp_path):
    base = tmp_path / "runs/eval_w15"
    for sub in ("ex38/m3001", "ex38_repeat/cuda0/m3001", "ex38_repeat/cuda1/m3001", "ex38_linux/m3001"):
        d = base / sub / "attempt_1/map64"
        d.mkdir(parents=True)
        (d / "map_modes.json").write_text("{}")
    spy = tmp_path / "spy.py"
    spy.write_text("import sys; print('CALL', *sys.argv[1:])\n")
    fake_python = tmp_path / "py"
    fake_python.write_text('#!/usr/bin/env bash\nexec python3 "$@"\n')
    fake_python.chmod(0o755)
    env = dict(os.environ, ISAAC311_PYTHON=str(fake_python), W15_COMPARE=str(spy), L2_LAB_ROOT=str(tmp_path))
    (tmp_path / "basic_gait_runs").symlink_to(tmp_path / "runs")
    done = subprocess.run(["bash", str(SCRIPT), "compare"], env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    calls = [l.split() for l in done.stdout.splitlines() if l.startswith("CALL")]
    assert len(calls) == 2
    assert "/ex38/m3001/" in calls[0][1] and "/ex38_linux/m3001/" in calls[0][2] and "--json" in calls[0]
    assert "/ex38_repeat/cuda0/" in calls[1][1] and "/ex38_repeat/cuda1/" in calls[1][2]


def test_device_and_out_are_taken_from_the_environment(tmp_path):
    env = dict(os.environ, ISAAC311_PYTHON="/opt/isaac311/bin/python", L2_DEVICE="cuda:1", L2_OUT=str(tmp_path / "o1"))
    argv = shlex.split(subprocess.run(["bash", str(SCRIPT), "print"], env=env, capture_output=True, text=True, check=True).stdout)
    assert argv[argv.index("--device") + 1] == "cuda:1" and argv[argv.index("--out") + 1] == str(tmp_path / "o1")
    env["L2_DEVICE"] = "cuda:2"
    bad = subprocess.run(["bash", str(SCRIPT), "print"], env=env, capture_output=True, text=True)
    assert bad.returncode == 2 and "L2_DEVICE" in bad.stderr
