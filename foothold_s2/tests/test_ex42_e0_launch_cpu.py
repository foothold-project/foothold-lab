"""E0 launch blockers from the N1 pre-check: chain parent stage, first-reset stage id, level-count receipts."""
from __future__ import annotations

import ast
import json
import pathlib
import types

import numpy as np
import pytest
import torch

from foothold_s2.scripts import ex42_training_entry as entry
from foothold_s2.terrains import ex42_exposure as ex

ROOT = pathlib.Path(__file__).resolve().parents[2]
TRAIN_START = ROOT / "foothold_s2" / "scripts" / "train_start.py"
TABLE = ROOT / "foothold_s2" / "curriculum" / "ex42-prep.yaml"
APPROVALS = ROOT / "foothold_s2" / "curriculum" / "ex42-approvals.yaml"
PARENT_DIR = pathlib.Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261108_123914/main/EX-42-B-stagezero_20261108_123914")
needs_parent = pytest.mark.skipif(not (PARENT_DIR / "manifest.json").is_file(), reason="real parent run not on this machine")


def _linux_profile(work, monkeypatch):
    names = ("A_LAYER_MARKER C_LAYER_LOCK EX41_PUSH250_OUTPUT EX41_STAGE_VIDEO_OUTPUT EX41_STAGE_VIDEO_SOURCE "
             "EX41_W78_VIDEO_ROOT FOOTHOLD_BASH FOOTHOLD_EX42_GATE_REPORT GPU0_EVAL_MARKER GPU0_TRAINING_MARKER "
             "GPU0_TRAINING_MARKER_ALT GPU1_EVAL_MARKER GPU1_TRAINING_MARKER GPU_JOBS_CONFIG GPU_JOBS_QUEUE "
             "ISAAC311_PYTHON ISAAC_CACHE_ROOT ISAACLAB_ROOT ISAAC_SIM_ROOT MAI_TMP_ROOT MAI_WORKTREE_ROOT "
             "PLAYLIST_ROOT RSL_RL_MODULE RUNNER_HOME S2_LAB_ROOT TELEGRAM_OUTBOX TELEGRAM_SCRIPT").split()
    for name in names:
        monkeypatch.setenv(name, str(work / name.lower()))
    monkeypatch.setenv("GPU0_UUID", "GPU-11111111-1111-1111-1111-111111111111")
    monkeypatch.setenv("GPU1_UUID", "GPU-22222222-2222-2222-2222-222222222222")
    monkeypatch.setenv("FOOTHOLD_MACHINE_PROFILE", str(ROOT / "machines/AI-WS01-linux.yaml"))
    from foothold_s2.machine_profile import load_machine_profile
    return load_machine_profile()


def _chain_kwargs(tmp_path, monkeypatch):
    from foothold_s2.tests.test_ex42_calibrate_cpu import mesh_fixture

    profile = _linux_profile(tmp_path, monkeypatch)
    run_dir = tmp_path / "s2_lab" / "e0_run"
    mesh_dir = tmp_path / "mesh"
    mesh_dir.mkdir()
    mesh = mesh_fixture(mesh_dir)
    argv = [profile["paths"]["conda_python"], "-m", "foothold_s2.ex42_eval_once",
            "--checkpoint", str(run_dir / "model_{iteration}.pt"), "--sha-from-manifest",
            "--out", str(tmp_path / "scores" / "p1_{iteration}"), "--device", "cuda:1",
            "--eval-seed", "42", "--mesh-dir", str(mesh_dir),
            "--expected-mesh-sha256", mesh["mesh_sha256"], "--p1-plan", str(TABLE),
            "--p1-approvals", str(APPROVALS), "--p1-stage-id", "E0", "--execute"]
    return dict(plan_path=TABLE, approvals_path=APPROVALS, parent_manifest_path=PARENT_DIR / "manifest.json",
                run_dir=run_dir, repo_root=ROOT, queue_path=tmp_path / "gpu_jobs_queue",
                score_argv_json=json.dumps(argv), machine_profile=profile, dispatch_path=tmp_path / "dispatch.json")


@needs_parent
def test_real_chain_builder_takes_the_e0_parent_only_with_the_e0_stage_id(tmp_path, monkeypatch):
    kwargs = _chain_kwargs(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="has not completed the pinned local update"):
        entry.build_ex42_training_chain(**kwargs)                              # what train_start did before
    chain = entry.build_ex42_training_chain(**kwargs, current_stage_id="E0")   # what it does now
    assert chain is not None


def test_train_start_passes_the_stage_id_to_the_chain_and_uses_it_in_the_first_reset_check():
    tree = ast.parse(TRAIN_START.read_text(encoding="utf-8"))
    build = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_build_ex42_chain")
    call = next(n for n in ast.walk(build) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "build_ex42_training_chain")
    kw = {k.arg: k.value for k in call.keywords}
    assert isinstance(kw["current_stage_id"], ast.Name) and kw["current_stage_id"].id == "EX42_STAGE_ID"
    src = TRAIN_START.read_text(encoding="utf-8")
    assert 'env.unwrapped._ex42_stage_id != EX42_STAGE_ID' in src
    assert 'env.unwrapped._ex42_stage_id != "EX42_0_T0_prime"' not in src
    assert "stage_id=EX42_STAGE_ID)" in src                                       # the runtime gets the same id
    assert 'EX42_STAGE_ID = _E_REQUESTS[0][0] if _E_REQUESTS else "EX42_0_T0_prime"' in src


def _fake_env(levels, types_, rows=10, cols=76):
    terrain = types.SimpleNamespace(terrain_levels=torch.as_tensor(levels), terrain_types=torch.as_tensor(types_),
                                    terrain_origins=torch.zeros(rows, cols, 3))
    return types.SimpleNamespace(num_envs=len(levels), device="cpu", scene=types.SimpleNamespace(terrain=terrain),
                                 _ex41_w86=object(), _ex40_dr_scale=1.0, _ex41_push_vmax_mps=1.0,
                                 _ex42_stage_id="E0",
                                 reward_manager=types.SimpleNamespace(get_term_cfg=lambda name: types.SimpleNamespace(weight=0.0)))


def test_level_counts_are_the_per_level_and_per_cell_histogram():
    env = _fake_env([5, 5, 4, 5, 0], [0, 0, 3, 22, 40])
    got = ex.level_counts(env.scene.terrain)
    assert got["per_level"] == [1, 0, 0, 0, 1, 3, 0, 0, 0, 0] and got["envs"] == 5
    assert got["per_column_level"] == {"0:5": 2, "3:4": 1, "22:5": 1, "40:0": 1}
    assert got["columns_used"] == [0, 3, 22, 40] and got["levels_max"] == 5


@needs_parent
def test_first_reset_receipt_reproduces_the_parent_histogram_after_restore():
    state = torch.load(PARENT_DIR / "model_1000.pt", map_location="cpu", weights_only=False)["env_state"]
    env = _fake_env(state["terrain_levels"], state["terrain_types"])
    got = ex.level_counts(env.scene.terrain)
    parent = torch.bincount(state["terrain_levels"], minlength=10).tolist()
    assert got["per_level"] == parent and sum(parent) == 3072 and got["levels_max"] <= 5
    assert max(got["columns_used"]) <= 22


def test_reset_readback_and_first_update_carry_the_level_counts(capsys):
    env = _fake_env([5, 4], [0, 1])
    readback = entry.build_stage_zero_reset_readback(
        env, types.SimpleNamespace(scale=1.0),
        {"w86": {"x": 1}, "initial_dr": {}, "terrain": {}})
    assert readback["terrain_level_counts"]["per_level"][5] == 1 and readback["stage_id"] == "E0"
    json.dumps(readback, sort_keys=True)                                          # JSON-safe, as train_start prints it
    runtime = entry.EX42StageZeroRuntime(stage_zero_plan=types.SimpleNamespace(stages=[object()]), plan_sha256="p",
                                         approval_sha256="a", parent_sha256="s", maximum_updates=250,
                                         push_vmax_mps=1.0, stage_id="E0")
    runtime.env = env
    runtime.on_update_start(1)
    line = next(l for l in capsys.readouterr().out.splitlines() if l.startswith("EX42_FIRST_UPDATE_LEVELS "))
    payload = json.loads(line.split(" ", 1)[1])
    assert payload["stage_id"] == "E0" and payload["per_level"][4] == 1 and payload["per_level"][5] == 1
    runtime.on_update_start(2)
    assert "EX42_FIRST_UPDATE_LEVELS" not in capsys.readouterr().out             # only the first update prints it


# ---- E0 parent load (N1 fourth start: "parent receipt is incomplete") ----
def _loader_runner(p_map_off, pcfg):
    from types import SimpleNamespace
    from foothold_s2.runners import start_runner

    class Loader:
        def __init__(self):
            self.calls = []

        def load_state_dict(self, *args, **kwargs):
            self.calls.append((args, kwargs))

    runner = object.__new__(start_runner.StartRunner)
    runner._resumed = False
    runner.current_learning_iteration = 0
    runner.ex41_pose_commands = True
    runner.ex41_critic_mirror = False
    runner.pcfg = dict(pcfg)
    runner.p_map_off = p_map_off
    runner.alg = SimpleNamespace(policy=Loader(), optimizer=Loader(), learning_rate=1.0)
    runner.perception = Loader()
    runner.adasmpl = Loader()
    runner.perception_optimizer = Loader()
    runner._apply_resume_adasmpl = lambda: None
    runner.load_map_switch_state = lambda *args: None
    runner.set_rng_state = lambda *_args: None
    return runner


@needs_parent
def test_real_m13000_checkpoint_and_real_receipt_load_with_stage_e0_and_are_refused_without_it():
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.runners import start_runner

    checkpoint, receipt = entry.inspect_ex42_stage_e0_parent(
        plan=EX42Plan.load(TABLE), approvals_path=APPROVALS, experiment_path=ROOT / "experiments" / "EX-42.yaml",
        parent_manifest_path=PARENT_DIR / "manifest.json")
    assert receipt["state"] == "parent_verified_for_stage_e0"
    pcfg = {**start_runner.MODE_DEFAULTS, **(checkpoint.get("perception_cfg") or {})}
    p_off = float(checkpoint["map_switch"]["p_map_off"])
    with pytest.raises(ValueError, match="parent receipt is incomplete"):          # what train_start did at :1184
        _loader_runner(p_off, pcfg).load_ex42_stage_zero_parent(checkpoint, receipt)
    runner = _loader_runner(p_off, pcfg)
    result = runner.load_ex42_stage_zero_parent(checkpoint, receipt, stage_e0=True)
    assert result["state"] == "loaded_for_ex42_stage_e0" and result["parent_cumulative_update"] == 13000
    assert result["local_iteration_origin"] == 0 and runner.current_learning_iteration == 0
    assert runner.alg.policy.calls[0][1] == {"strict": True}
    assert runner.alg.learning_rate == float(checkpoint["ppo_learning_rate"])


def test_train_start_passes_stage_e0_to_the_parent_load_and_no_other_stage_zero_literal_is_left_on_the_e0_path():
    tree = ast.parse(TRAIN_START.read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "attr", "") == "load_ex42_stage_zero_parent"]
    assert len(calls) == 1
    kw = {k.arg: k.value for k in calls[0].keywords}
    assert ast.unparse(kw["stage_e0"]) == "not EX42_CONTINUES_STAGE"          # the first E stage: parent m13000
    src = TRAIN_START.read_text(encoding="utf-8")
    # the self-resume branch no longer hard-codes the stage-zero 12000 origin: it reads the cumulative origin from the
    # validated resume proof, which an E1 boundary resume computes from its own parent (13250)
    resume = [i for i, line in enumerate(src.splitlines(), 1) if "12000 +" in line or "12001 +" in line]
    assert resume == []
    assert src.count('EX42_STAGE_ZERO_RESUME_PROOF["cumulative_update_origin"]') >= 2
