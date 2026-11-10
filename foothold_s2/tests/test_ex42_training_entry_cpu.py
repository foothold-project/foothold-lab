from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.scripts import ex42_training_entry as entry
from foothold_s2.tests.test_ex42_chain_cpu import APPROVALS, ROOT, make_chain
from foothold_s2.runners.start_runner import StartRunner


def test_linux_chain_builder_binds_queue_path_to_machine_profile(tmp_path, monkeypatch):
    from foothold_s2.tests.test_ex42_calibrate_cpu import mesh_fixture

    plan = SimpleNamespace(document={"status": "preparation_only"})
    monkeypatch.setattr(entry.EX42Plan, "load", lambda _path: plan)
    monkeypatch.setattr(entry.EX42Runtime, "training_chain", lambda **kwargs: kwargs)
    queue_path = tmp_path / "gpu" / "queue.json"
    profile = {
        "machine_id": "AI-WS01-linux",
        "paths": {
            "conda_python": "/opt/conda/envs/isaac311/bin/python",
            "gpu_queue": str(queue_path),
        },
        "devices": {
            "training": {"cuda_index": 0, "device": "cuda:0", "uuid": "GPU-test0"},
            "p1_evaluation": {"cuda_index": 0, "device": "cuda:0", "uuid": "GPU-test0"},
            "screen": {"cuda_index": 1, "device": "cuda:1", "uuid": "GPU-test1"},
        },
    }
    mesh_dir = tmp_path / "mesh"
    mesh_dir.mkdir()
    mesh = mesh_fixture(mesh_dir)
    plan_path, approvals_path = tmp_path / "plan.yaml", tmp_path / "approvals.yaml"
    plan_path.write_text("plan")
    approvals_path.write_text("approvals")
    argv_template = [
        "/opt/conda/envs/isaac311/bin/python", "-m", "foothold_s2.ex42_eval_once",
        "--checkpoint", str(tmp_path / "run" / "model_{iteration}.pt"), "--sha-from-manifest",
        "--out", str(tmp_path / "scores" / "score_{iteration}"), "--device", "cuda:0",
        "--eval-seed", "42", "--mesh-dir", str(mesh_dir),
        "--expected-mesh-sha256", mesh["mesh_sha256"],
        "--p1-plan", str(plan_path), "--p1-approvals", str(approvals_path),
        "--p1-stage-id", "EX42_0_T0_prime", "--execute",
    ]
    kwargs = dict(
        plan_path=plan_path, approvals_path=approvals_path,
        parent_manifest_path=tmp_path / "parent" / "manifest.json", run_dir=tmp_path / "run",
        repo_root=tmp_path, queue_path=queue_path, score_argv_json=json.dumps(argv_template),
        machine_profile=profile,
    )
    built = entry.build_ex42_training_chain(**kwargs)
    assert built["queue_path"] == queue_path
    with pytest.raises(ValueError, match="queue path differs"):
        entry.build_ex42_training_chain(**{**kwargs, "queue_path": tmp_path / "other.json"})


def test_train_start_caller_builds_parent_verified_chain_and_attaches(tmp_path, monkeypatch):
    fixture_chain, run = make_chain(tmp_path)
    parent_manifest = Path(fixture_chain.parent["manifest_path"])
    monkeypatch.setattr(entry.EX42Plan, "load", lambda _path: fixture_chain.plan)
    runner = StartRunner.__new__(StartRunner)
    runner.log_dir = str(run)

    chain = entry.build_and_attach_ex42_training_chain(
        runner,
        plan_path=ROOT / "foothold_s2/curriculum/ex42-prep.yaml",
        approvals_path=APPROVALS,
        parent_manifest_path=parent_manifest,
        run_dir=run,
        repo_root=ROOT,
        queue_path=tmp_path / "queue.json",
        score_argv_json='["python", "-m", "known.p1", "--iteration", "{iteration}"]',
        p1_interval=250,
    )

    assert runner.ex42_training_chain is chain
    assert chain.plan.document["status"] == "preparation_only"
    assert chain.parent["checkpoint_sha256"] == fixture_chain.parent["checkpoint_sha256"]
    assert chain.score_argv_factory(250) == [
        "python", "-m", "known.p1", "--iteration", "250"]
    receipt = json.loads((run / "startup_receipt.json").read_text(encoding="utf-8"))
    assert receipt["state"] == "chain_ready_not_launch_authorized"
    assert receipt["production_launch_allowed"] is False


def test_chain_startup_receipt_is_the_only_output_allowed_after_chain_creation(tmp_path):
    run = tmp_path / "run"
    assert not run.exists()

    # make_chain constructs the real EX42TrainingChain, which creates the run
    # directory and writes startup_receipt.json before train_start's main().
    chain, actual_run = make_chain(tmp_path)
    assert actual_run == run
    receipt = entry.validate_ex42_stage_zero_chain_output(
        run,
        plan_sha256=chain.plan.sha256,
        parent_sha256=chain.parent["checkpoint_sha256"],
    )
    assert receipt["state"] == "chain_startup_receipt_verified"
    assert receipt["plan_sha256"] == chain.plan.sha256
    assert receipt["parent_sha256"] == chain.parent["checkpoint_sha256"]
    with pytest.raises(ValueError, match="identity differs"):
        entry.validate_ex42_stage_zero_chain_output(
            run,
            plan_sha256="0" * 64,
            parent_sha256=chain.parent["checkpoint_sha256"],
        )

    (run / "unexpected.txt").write_text("not this launch's receipt", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected contents"):
        entry.validate_ex42_stage_zero_chain_output(
            run,
            plan_sha256=chain.plan.sha256,
            parent_sha256=chain.parent["checkpoint_sha256"],
        )


def test_existing_chain_receipt_is_checked_before_a_builder_can_replace_it(tmp_path):
    chain, run = make_chain(tmp_path)
    receipt_path = run / "startup_receipt.json"
    original = json.loads(receipt_path.read_text(encoding="utf-8"))
    bad = dict(original, plan_sha256="bad")
    receipt_path.write_text(json.dumps(bad), encoding="utf-8")
    called = []

    with pytest.raises(ValueError, match="identity differs"):
        entry.build_stage_zero_chain_with_receipt_checks(
            run, plan_sha256=chain.plan.sha256,
            parent_sha256=chain.parent["checkpoint_sha256"],
            allow_existing_run=True, builder=lambda: called.append(True))

    assert called == []
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["plan_sha256"] == "bad"


def test_chain_receipt_is_revalidated_after_builder_replacement(tmp_path):
    chain, run = make_chain(tmp_path)

    def replace_receipt():
        row = json.loads((run / "startup_receipt.json").read_text(encoding="utf-8"))
        row["parent"] = dict(row["parent"], checkpoint_sha256="0" * 64)
        (run / "startup_receipt.json").write_text(json.dumps(row), encoding="utf-8")
        return chain

    with pytest.raises(ValueError, match="identity differs"):
        entry.build_stage_zero_chain_with_receipt_checks(
            run, plan_sha256=chain.plan.sha256,
            parent_sha256=chain.parent["checkpoint_sha256"],
            allow_existing_run=True, builder=replace_receipt)


def test_chain_receipt_validation_brackets_builder_before_kit():
    source = ROOT / "foothold_s2/scripts/train_start.py"
    text = source.read_text(encoding="utf-8")
    chain_build = text.index("build_stage_zero_chain_with_receipt_checks(")
    app_launcher = text.index("from isaaclab.app import AppLauncher")
    assert chain_build < app_launcher
    assert "EX42_TRAINING_CHAIN, EX42_STAGE_ZERO_CHAIN_RECEIPT = (" in text
    assert 'print("EX42_STAGE_ZERO_CHAIN_RECEIPT "' in text
    assert '"chain_startup_receipt": EX42_STAGE_ZERO_CHAIN_RECEIPT' in text
    assert '"resume_root_xy_readback": ex42_stage_zero_root_xy_readback' in text
    assert "allow_existing_run=EX42_STAGE_ZERO_RESUME_SAME_RUN" in text
    assert "EX-42 stage-zero output path appeared after CPU preflight" not in text


def test_resume_terrain_restore_precedes_the_real_reset_and_root_readback_follows_load():
    text = (ROOT / "foothold_s2/scripts/train_start.py").read_text(encoding="utf-8")
    local_init = text.index("ex42_stage_zero_root_xy_readback = None", text.index("def main("))
    checkpoint_load = text.index(
        "ex42_resume_saved = torch.load(\n                EX42_STAGE_ZERO_RESUME", local_init)
    restore = text.index("terrain_restore = restore_stage_zero_resume_terrain_before_reset(")
    reset = text.index("env.reset()", restore)
    load = text.index("runner.load(EX42_STAGE_ZERO_RESUME, map_location=\"cpu\")", reset)
    root_readback = text.index("build_stage_zero_resume_root_xy_readback(", load)
    learn = text.index("runner.learn(", root_readback)
    assert local_init < checkpoint_load < restore < reset < load < root_readback < learn
    assert "restore_stage_zero_resume_terrain_before_reset(\n                env, ex42_resume_saved)" in text
    assert "terrain_restore = restore_stage_zero_resume_terrain_before_reset(\n                env, EX42_STAGE_ZERO_CHECKPOINT)" not in text
    assert "EX42_SELF_RESUME_ROOT_XY_READBACK" in text


def test_stage_zero_runtime_reads_vector_fields_from_gym_unwrapped_env():
    import gymnasium as gym

    class FakeVectorEnv(gym.Env):
        num_envs = 4
        device = "cpu"

        def reset(self, *, seed=None, options=None):
            super().reset(seed=seed)
            return None, {}

        def step(self, action):
            return None, 0.0, False, False, {}

    from foothold_s2.scripts.ex42_training_entry import EX42StageZeroRuntime

    base = FakeVectorEnv()
    wrapped = gym.wrappers.OrderEnforcing(base)
    assert not hasattr(wrapped, "num_envs")
    assert not hasattr(wrapped, "device")
    assert wrapped.unwrapped.num_envs == 4
    assert wrapped.unwrapped.device == "cpu"

    runtime = EX42StageZeroRuntime(
        stage_zero_plan=SimpleNamespace(stages=[SimpleNamespace(id="T0_prime")]),
        plan_sha256="a" * 64,
        approval_sha256="b" * 64,
        parent_sha256="c" * 64,
        push_vmax_mps=2.0,
    )
    term = SimpleNamespace()
    runtime.attach_environment(wrapped, term)

    assert runtime.env is base
    assert runtime.env_stage.shape == (4,)
    assert runtime.env_stage.device.type == "cpu"
    assert term.stage_runtime is runtime
    assert base._ex42_stage_id == "EX42_0_T0_prime"


def test_stage_zero_command_slots_are_expanded_before_first_reset():
    import torch

    from foothold_s2.scripts.ex41_startup import configure_ex41_command_slots

    term = SimpleNamespace(
        slot_names=("forward", "walk_left", "walk_right", "spin_left", "spin_right"),
        slot_counts=torch.tensor([5, 7, 11, 13, 17], dtype=torch.long),
    )
    receipt = configure_ex41_command_slots(term)
    assert len(term.slot_names) == 13
    assert term.slot_counts.tolist() == [5, 7, 11, 13, 17, 0, 0, 0, 0, 0, 0, 0, 0]
    assert receipt["prior_slot_names"] == [
        "forward", "walk_left", "walk_right", "spin_left", "spin_right"]

    source = (ROOT / "foothold_s2/scripts/train_start.py").read_text(encoding="utf-8")
    ex42_branch = source[source.index("elif EX42_STAGE_ZERO_PLAN is not None:",
                                    source.index("env = gym.make")):]
    assert ex42_branch.index("configure_ex41_command_slots(command_term)") < ex42_branch.index("env.reset()")


def test_stage_zero_reset_readback_uses_json_contract_not_w86_runtime(tmp_path, monkeypatch):
    import gymnasium as gym

    from foothold_s2.rewards import stair_start_hist, w86_runtime

    class FakeIsaacEnv(gym.Env):
        num_envs = 2
        device = "cpu"

        def reset(self, *, seed=None, options=None):
            super().reset(seed=seed)
            return None, {}

        def step(self, action):
            return None, 0.0, False, False, {}

    monkeypatch.setattr(w86_runtime, "PhysicalSource", lambda _env: lambda: {})
    monkeypatch.setattr(stair_start_hist, "snapshot", lambda _env: {"counts": {}})
    raw = FakeIsaacEnv()
    runtime = w86_runtime.attach_runtime(
        raw, SimpleNamespace(is_ex41=True), tmp_path)
    assert isinstance(runtime, w86_runtime.W86Runtime)
    with pytest.raises(TypeError, match="not JSON serializable"):
        json.dumps(runtime)

    raw._ex42_stage_id = "EX42_0_T0_prime"
    raw._ex40_dr_scale = 1.0
    raw._ex41_push_vmax_mps = 2.0
    raw._ex40_dr_samples = {"reset": "verified"}
    raw.reward_manager = SimpleNamespace(
        get_term_cfg=lambda _name: SimpleNamespace(weight=0.0))
    wrapped = gym.wrappers.OrderEnforcing(raw)
    contract = {
        "initial_dr": {"scale": 1.0},
        "terrain": {"policy": "performance", "level_cap": 5},
        "w86": {"format": "ex41-w86-registration/1", "weights": {"swing": -10.0}},
    }
    readback = entry.build_stage_zero_reset_readback(
        wrapped, SimpleNamespace(scale=1.0), contract)
    encoded = json.dumps(readback, sort_keys=True)
    decoded = json.loads(encoded)
    assert decoded["w86"] == contract["w86"]
    assert decoded["w86_attached"] is True
    assert decoded["stage_id"] == "EX42_0_T0_prime"
    assert decoded["reset_event_samples"] == {"reset": "verified"}
    assert decoded["push_vmax_mps"] == 2.0
    assert decoded["lin_vel_z_weight"] == 0.0


def test_stage_zero_runtime_records_real_runner_pre_and_post_step_contract():
    import torch

    from foothold_s2.scripts.ex42_training_entry import EX42StageZeroRuntime

    class Env:
        num_envs = 3
        device = torch.device("cpu")

    env = Env()
    runtime = EX42StageZeroRuntime(
        stage_zero_plan=SimpleNamespace(stages=[SimpleNamespace(id="T0_prime")]),
        plan_sha256="a" * 64, approval_sha256="b" * 64,
        parent_sha256="c" * 64, push_vmax_mps=2.0)
    runtime.attach_environment(env, SimpleNamespace())
    runtime.attach_runner(SimpleNamespace(log_dir="run"))
    runtime.on_update_start(1)
    runtime.record_pre_step()
    with pytest.raises(RuntimeError, match="recorded twice"):
        runtime.record_pre_step()
    with pytest.raises(ValueError, match="done vector"):
        runtime.record_post_step(torch.zeros(2, dtype=torch.bool))
    runtime.record_post_step(torch.zeros(3, dtype=torch.bool))
    assert runtime.pre_step_count == runtime.post_step_count == 1
    assert env._ex40_dr_scale == 1.0
    assert env._ex41_push_vmax_mps == 2.0


def test_actual_m6000_parent_reward_push_runtime_and_model50_manifest(tmp_path, monkeypatch):
    """Answer known-input regression using the pinned, saved EX-41 m6000 checkpoint."""
    checkpoint_path = os.environ.get("EX42_W65_PARENT_CHECKPOINT")
    if not checkpoint_path:
        pytest.skip("set EX42_W65_PARENT_CHECKPOINT to the approved EX-41 m6000 checkpoint")
    import torch

    from foothold_s2.curriculum.ex40_dr_runtime import RuntimeReadback
    from foothold_s2.runners import start_runner as runner_module
    from foothold_s2.scripts.ex42_training_entry import (
        EX42StageZeroDRReadback, EX42StageZeroRuntime,
        apply_stage_zero_parent_reward_contract, configure_ex42_stage_zero_train_cfg,
    )

    parent_path = Path(checkpoint_path)
    parent_sha = hashlib.sha256(parent_path.read_bytes()).hexdigest()
    assert parent_sha == "1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613"
    parent = torch.load(parent_path, map_location="cpu", weights_only=False)
    assert parent["iter"] == 6000
    assert parent["model_state_dict"]["actor.0.weight"].shape[1] == 98
    assert parent["model_state_dict"]["critic.0.weight"].shape[1] == 666
    assert parent["ex41_pose_commands"] is True
    assert parent["ex41_w86_reward_weights"]["swing"] == pytest.approx(-10.0)
    assert parent["continuous_curriculum"]["push_vmax_mps"] == pytest.approx(2.0)

    cfg = SimpleNamespace(rewards=SimpleNamespace(lin_vel_z=SimpleNamespace(weight=-2.0)))
    reward_receipt = apply_stage_zero_parent_reward_contract(
        cfg, parent_sha256=parent_sha, parent_update=int(parent["iter"]))
    assert reward_receipt["weight"] == cfg.rewards.lin_vel_z.weight == 0.0
    transfer_cfg = configure_ex42_stage_zero_train_cfg(
        {}, parent, parent_path=parent_path, parent_sha256=parent_sha)
    assert transfer_cfg["ex42_stage_zero_push_vmax_mps"] == pytest.approx(2.0)

    class Env:
        def __init__(self):
            self._ex40_dr_scale = 0.0
            self.action_manager = SimpleNamespace(
                get_term=lambda _name: SimpleNamespace(_ex40_sample_counts=None))

    env = Env()
    base = RuntimeReadback(env, {}, 0.015, parent_sha)
    readback = EX42StageZeroDRReadback(base, transfer_cfg["ex42_stage_zero_push_vmax_mps"])
    runtime = EX42StageZeroRuntime(
        stage_zero_plan=SimpleNamespace(stages=[SimpleNamespace(id="T0_prime")]),
        plan_sha256="a" * 64, approval_sha256="b" * 64,
        parent_sha256=parent_sha, push_vmax_mps=parent["continuous_curriculum"]["push_vmax_mps"])
    runtime.env = env
    runtime.on_update_start(1)
    readback.update_start(1)
    assert env._ex40_dr_scale == readback.scale == 1.0
    assert env._ex41_push_vmax_mps == runtime.push_vmax_mps == 2.0

    start_source = (ROOT / "foothold_s2/runners/start_runner.py").read_text(encoding="utf-8")
    assert start_source.index("continuous.record_pre_step()") < start_source.index("self.env.step(actions.to")
    assert start_source.index("self.env.step(actions.to") < start_source.index("continuous.record_post_step(dones)")
    train_source = (ROOT / "foothold_s2/scripts/train_start.py").read_text(encoding="utf-8")
    ex42_branch = train_source[train_source.index("elif EX42_STAGE_ZERO_PLAN is not None:",
                                                 train_source.index("env = gym.make")):]
    assert "runner.ex40_dr_runtime = ex42_dr_readback" in ex42_branch

    runner = object.__new__(runner_module.StartRunner)
    runner.manifest = {"progress": {}}
    runner.manifest_dir = tmp_path
    runner.log_dir = str(tmp_path)
    runner.num_steps_per_env = 24
    runner.gpu_world_size = 1
    runner.continuous_curriculum = runtime
    runner._check_code = lambda _iteration: None
    published = {}
    monkeypatch.setattr(runner_module.run_manifest, "update_progress",
                        lambda _dir, _manifest, completed, steps, _checkpoint:
                            published.update(completed=completed, steps=steps))
    runner._manifest_checkpoint(50, "model_50.pt", 3072)
    assert published == {"completed": 50, "steps": 50 * 24 * 3072}


def test_stage_zero_config_and_live_reward_match_m6000_parent_contract():
    from foothold_s2.scripts.ex42_training_entry import (
        apply_stage_zero_parent_reward_contract, apply_stage_zero_parent_reward_manager,
    )

    parent_sha = "1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613"
    env_cfg = SimpleNamespace(rewards=SimpleNamespace(lin_vel_z=SimpleNamespace(weight=-2.0)))
    apply_stage_zero_parent_reward_contract(env_cfg, parent_sha256=parent_sha, parent_update=6000)
    assert env_cfg.rewards.lin_vel_z.weight == 0.0

    class RewardManager:
        def __init__(self):
            self.term = SimpleNamespace(weight=-2.0)

        def get_term_cfg(self, _name):
            return self.term

        def set_term_cfg(self, _name, cfg):
            self.term = cfg

    env = SimpleNamespace(reward_manager=RewardManager())
    receipt = apply_stage_zero_parent_reward_manager(
        env, parent_sha256=parent_sha, parent_update=6000)
    assert receipt["weight"] == env.reward_manager.term.weight == 0.0
    with pytest.raises(ValueError, match="pinned EX-41 m6000"):
        apply_stage_zero_parent_reward_manager(env, parent_sha256="0" * 64, parent_update=6000)


def test_p1_argv_requires_an_iteration_placeholder_and_expands_checkpoint_and_output():
    with pytest.raises(ValueError, match="contain an "):
        entry.make_score_argv_factory('["python", "-m", "known.p1"]')
    factory = entry.make_score_argv_factory(
        '["--checkpoint", "model_{iteration}.pt", "--out", "score_{iteration}"]')
    assert factory(250) == ["--checkpoint", "model_250.pt", "--out", "score_250"]


def test_resume_relocation_requires_receipt_and_preserves_manifest_and_checkpoint_sha(tmp_path):
    source = tmp_path / "windows-export"
    source.mkdir()
    target = tmp_path / "linux-import"
    plan_sha, approval_sha, parent_sha = "a" * 64, "b" * 64, "c" * 64
    checkpoint = source / "model_50.pt"
    saved = {
        "format": "foothold-start/1", "iter": 50,
        "model_state_dict": {}, "optimizer_state_dict": {}, "ppo_learning_rate": 2e-4,
        "perception_state_dict": {}, "perception_optimizer_state_dict": {},
        "adasmpl": {}, "normalization_state": {},
        "rng": {"torch": torch.get_rng_state(), "numpy": {"state": [1]}, "python": (1, 2, 3)},
        "map_switch": {"generator_state": torch.tensor([1], dtype=torch.uint8)},
        "env_state": {},
        "continuous_curriculum": {
            "format": "foothold-ex42-stage-zero-state/1", "iteration": 50,
            "maximum_updates": 1000, "plan_sha256": plan_sha,
            "approval_sha256": approval_sha, "parent_sha256": parent_sha,
            "stage_id": "EX42_0_T0_prime", "dr_scale": 1.0, "finished": False,
        },
        "ex42_parent_transfer": {
            "parent_sha256": parent_sha, "parent_cumulative_update": 12000,
            "map_input": "reconstruction", "force_gt": False,
        },
    }
    torch.save(saved, checkpoint)
    checkpoint_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    manifest = {
        "run": {"log_dir": str(source.resolve())},
        "progress": {"completed_updates": 50, "total_env_steps": 50 * 24 * 3072},
        "checkpoints": {checkpoint.name: checkpoint_sha},
    }
    source_manifest = source / "manifest.json"
    source_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    receipt = entry.make_ex42_resume_relocation_receipt(
        manifest_path=source_manifest, checkpoint_path=checkpoint,
        target_run_dir=target, plan_sha256=plan_sha,
        approval_sha256=approval_sha, parent_sha256=parent_sha)
    target.mkdir()
    target_checkpoint = target / checkpoint.name
    target_checkpoint.write_bytes(checkpoint.read_bytes())
    target_manifest = target / "manifest.json"
    target_manifest.write_bytes(source_manifest.read_bytes())
    receipt_path = target / "resume_relocation.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    args = {
        "checkpoint_path": target_checkpoint, "manifest_path": target_manifest,
        "plan_sha256": plan_sha, "approval_sha256": approval_sha,
        "parent_receipt": {"parent_sha256": parent_sha},
        "resume_smoke_updates": 5, "require_latest": True,
    }
    with pytest.raises(ValueError, match="explicit prior relocation receipt"):
        entry.validate_ex42_stage_zero_resume(**args)
    verified = entry.validate_ex42_stage_zero_resume(
        **args, relocation_receipt_path=receipt_path)
    assert verified["state"] == "manifest_checkpoint_self_resume_verified"
    assert verified["checkpoint_sha256"] == checkpoint_sha
    assert verified["source_manifest_sha256"] == receipt["manifest_sha256"]
    bad_receipt = dict(receipt, target_run_dir=str(tmp_path / "other-import"))
    receipt_path.write_text(json.dumps(bad_receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="relocation receipt"):
        entry.validate_ex42_stage_zero_resume(
            **args, relocation_receipt_path=receipt_path)
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    target_manifest.write_text(target_manifest.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="relocation receipt"):
        entry.validate_ex42_stage_zero_resume(
            **args, relocation_receipt_path=receipt_path)


def test_train_start_preparation_gate_precedes_kit_and_keeps_attachment_call():
    source = ROOT / "foothold_s2/scripts/train_start.py"
    text = source.read_text(encoding="utf-8")
    assert text.index("EX-42 preparation_only:") < text.index("from isaaclab.app import AppLauncher")
    assert text.index("EX42_SOURCE_LOCK_RECEIPT = audit_ex42_launch_source") < text.index(
        "from isaaclab.app import AppLauncher")
    assert "attach_ex42_training_chain(runner, EX42_TRAINING_CHAIN)" in text
    ast.parse(text)
