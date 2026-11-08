from __future__ import annotations

from types import SimpleNamespace
import hashlib
import json

import pytest

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_training_entry as entry
from foothold_s2.runners import start_runner


ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
TABLE = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
APPROVALS = ROOT / "foothold_s2/curriculum/ex42-approvals.yaml"


def _receipt():
    scope = {
        "stage_id": "EX42_0_T0_prime", "source_stage_id": "T0_prime",
        "start_update": 0, "maximum_updates": 1000,
        "parent_sha256": "1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613",
        "later_stages_authorized": False,
    }
    return {
        "state": "parent_verified_for_stage_zero",
        "parent_path": "C:/parent/model_6000.pt", "parent_sha256": scope["parent_sha256"],
        "parent_local_update": 6000, "parent_cumulative_update": 12000,
        "actor_input_dim": 98, "critic_input_dim": 666,
        "ex41_environment_state_restored": False,
        "ex41_curriculum_state_restored": False,
        "approval": {"state": "stage_zero_only_authorized", "scope": scope,
                      "approvals_sha256": "a" * 64,
                      "production_launch_allowed": False,
                      "later_stages_authorized": False},
    }


def test_w65_cli_requires_explicit_scope_and_rejects_unbounded_variants(tmp_path, monkeypatch):
    plan = EX42Plan.load(TABLE)
    checkpoint = {"format": "foothold-start/1", "iter": 6000}
    monkeypatch.setattr(entry, "inspect_ex42_stage_zero_parent",
                        lambda **_kwargs: (checkpoint, _receipt()))
    args = dict(
        plan_path=TABLE, approvals_path=APPROVALS,
        parent_manifest_path=tmp_path / "manifest.json", log_dir=tmp_path / "new-run",
        task=entry.STAGE_ZERO_TASK_ID, device="cuda:1", headless=True, distributed=False,
        max_iterations=1000, num_envs=3072, map_input="reconstruction", force_gt=False,
        approved_switch=True,
    )
    loaded_plan, loaded_ckpt, parent, request = entry.validate_ex42_stage_zero_cli(**args)
    assert loaded_plan.sha256 == plan.sha256
    assert loaded_ckpt is checkpoint
    assert parent["parent_cumulative_update"] == 12000
    assert request["max_iterations"] == 1000
    assert request["production_launch_allowed"] is False
    assert request["later_stages_authorized"] is False

    for change, message in (
        ({"approved_switch": False}, "explicit scoped approval"),
        ({"max_iterations": 1001}, "bounded to exactly 1000"),
        ({"device": "cuda:0"}, "cuda:1"),
        ({"force_gt": True}, "without forced GT"),
        ({"resume_from": "model_6000.pt"}, "not self-resume"),
    ):
        with pytest.raises(ValueError, match=message):
            entry.validate_ex42_stage_zero_cli(**(args | change))

    smoke = entry.validate_ex42_stage_zero_cli(
        **(args | {"device": "cuda:0", "resume_from": "model_350.pt",
                   "self_resume": True, "resume_smoke": True,
                   "resume_updates": 5}))
    assert smoke[3]["resume_smoke"] is True
    same_run = tmp_path / "same-run"
    same_run.mkdir()
    (same_run / "manifest.json").write_text("{}", encoding="utf-8")
    production_resume = entry.validate_ex42_stage_zero_cli(**(args | {
        "log_dir": same_run, "resume_from": same_run / "model_350.pt",
        "self_resume": True,
    }))
    assert production_resume[3]["self_resume"] is True
    with pytest.raises(ValueError, match="must continue in its source run directory"):
        entry.validate_ex42_stage_zero_cli(**(args | {
            "resume_from": "C:/other/model_350.pt", "self_resume": True,
        }))
    for change, message in (
        ({"device": "cuda:0", "resume_from": "model_350.pt", "self_resume": True}, "cuda:1"),
        ({"resume_from": "model_350.pt", "self_resume": True,
          "resume_smoke": True, "resume_updates": 6}, "one through five"),
    ):
        with pytest.raises(ValueError, match=message):
            entry.validate_ex42_stage_zero_cli(**(args | change))


def test_w65_stage_zero_self_resume_is_manifest_pinned_and_maps_350_to_351(tmp_path):
    import torch

    run = tmp_path / "source"
    run.mkdir()
    checkpoint_path = run / "model_350.pt"
    parent = _receipt()
    plan_sha = "p" * 64
    approval_sha = parent["approval"]["approvals_sha256"]
    checkpoint = {
        "format": "foothold-start/1", "iter": 350,
        "model_state_dict": {"actor": torch.tensor([1.0])},
        "optimizer_state_dict": {"state": {}, "param_groups": []},
        "ppo_learning_rate": 0.00038443359375,
        "perception_state_dict": {"encoder": torch.tensor([2.0])},
        "perception_optimizer_state_dict": {"state": {}, "param_groups": []},
        "adasmpl": {"p": 0.4},
        "normalization_state": {"running_buffers": {}},
        "rng": {"torch": torch.tensor([1]), "numpy": [1], "python": [1]},
        "map_switch": {"generator_state": torch.tensor([2]), "p_map_off": 0.1},
        "env_state": {"terrain_levels": torch.tensor([5]), "command_rng": torch.tensor([3])},
        "continuous_curriculum": {
            "format": "foothold-ex42-stage-zero-state/1", "iteration": 350,
            "maximum_updates": 1000, "plan_sha256": plan_sha,
            "approval_sha256": approval_sha, "parent_sha256": parent["parent_sha256"],
            "stage_id": "EX42_0_T0_prime", "dr_scale": 1.0, "finished": False,
        },
        "ex42_parent_transfer": {
            "parent_sha256": parent["parent_sha256"], "parent_cumulative_update": 12000,
            "map_input": "reconstruction", "force_gt": False,
        },
    }
    torch.save(checkpoint, checkpoint_path)
    checkpoint_sha = hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
    manifest_path = run / "manifest.json"
    manifest_path.write_text(json.dumps({
        "run": {"log_dir": str(run.resolve())},
        "progress": {"completed_updates": 400, "total_env_steps": 29_491_200},
        "checkpoints": {checkpoint_path.name: checkpoint_sha},
    }), encoding="utf-8")

    proof = entry.validate_ex42_stage_zero_resume(
        checkpoint_path=checkpoint_path, manifest_path=manifest_path,
        plan_sha256=plan_sha, approval_sha256=approval_sha,
        parent_receipt=parent, resume_smoke_updates=5, require_latest=False)
    assert proof["local_update_origin"] == 350
    assert proof["first_resumed_local_update"] == 351
    assert proof["cumulative_update_origin"] == 12350
    assert proof["first_resumed_cumulative_update"] == 12351
    assert proof["requested_updates"] == 5
    assert {"ppo_optimizer", "learning_rate", "normalization", "rng",
            "curriculum", "map_switch", "environment_terrain_and_command_rng"}.issubset(
                proof["restored_groups"])
    with pytest.raises(ValueError, match="not the manifest's latest"):
        entry.validate_ex42_stage_zero_resume(
            checkpoint_path=checkpoint_path, manifest_path=manifest_path,
            plan_sha256=plan_sha, approval_sha256=approval_sha,
            parent_receipt=parent)

    manifest_path.write_text(json.dumps({
        "run": {"log_dir": str(run.resolve())},
        "progress": {"completed_updates": 400, "total_env_steps": 29_491_200},
        "checkpoints": {checkpoint_path.name: "0" * 64},
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA is absent or differs"):
        entry.validate_ex42_stage_zero_resume(
            checkpoint_path=checkpoint_path, manifest_path=manifest_path,
            plan_sha256=plan_sha, approval_sha256=approval_sha,
            parent_receipt=parent, resume_smoke_updates=5, require_latest=False)


def test_resumed_one_based_stage_uses_next_update_without_double_increment():
    runtime = SimpleNamespace(plan=SimpleNamespace(is_ex41=False),
                              uses_one_based_updates=True)
    assert start_runner.resumed_loop_start(350, True, runtime) == 350
    assert start_runner.curriculum_update_number(runtime, 350) == 351
    zero_based = SimpleNamespace(plan=SimpleNamespace(is_ex41=False),
                                 uses_one_based_updates=False)
    assert start_runner.resumed_loop_start(350, True, zero_based) == 351


def test_stage_zero_adapter_uses_t0_prime_and_only_approved_dr_l5():
    plan = EX42Plan.load(TABLE)
    source, stage = entry.load_ex42_stage_zero_source(plan)
    assert stage.id == "T0_prime"
    assert stage.shares == plan.document["stage_zero"]["shares"]
    view = entry.make_ex42_stage_zero_plan_view(source, stage, _receipt())
    assert view.stages == [stage]
    assert view.initial_dr_scale == 1.0
    assert view.terrain_curriculum == "performance"
    assert view.is_ex41 is True


def test_stage_zero_runtime_is_bounded_and_continuable_only_under_same_pins():
    stage = SimpleNamespace(id="T0_prime")
    plan_view = SimpleNamespace(stages=[stage])
    runtime = entry.EX42StageZeroRuntime(
        stage_zero_plan=plan_view, plan_sha256="p" * 64,
        approval_sha256="a" * 64, parent_sha256="b" * 64,
        push_vmax_mps=2.0)
    assert runtime.uses_one_based_updates is True
    runtime.on_update_start(1)
    runtime.on_update_start(1000)
    with pytest.raises(ValueError, match="1..1000"):
        runtime.on_update_start(1001)
    state = runtime.state_dict()
    restored = entry.EX42StageZeroRuntime(
        stage_zero_plan=plan_view, plan_sha256="p" * 64,
        approval_sha256="a" * 64, parent_sha256="b" * 64,
        push_vmax_mps=2.0)
    restored.load_state_dict(state)
    restored.on_resume_checkpoint("model_1000.pt", 1000)
    assert restored.state_dict() == state
    state["plan_sha256"] = "x" * 64
    with pytest.raises(ValueError, match="plan_sha256 differs"):
        restored.load_state_dict(state)


def test_stage_zero_train_cfg_carries_parent_perception_and_save_interval():
    cfg = entry.configure_ex42_stage_zero_train_cfg(
        {"policy": {"class_name": "ActorCritic"}, "perception": {"force_gt": True}},
        {"perception_cfg": {"map_input": "reconstruction", "force_gt": False,
                            "p_map_off": 0.1}, "ppo_learning_rate": 0.00038,
         "continuous_curriculum": {"push_vmax_mps": 2.0}},
        parent_path="C:/parent/model_6000.pt", parent_sha256="b" * 64)
    assert cfg["max_iterations"] == 1000
    assert cfg["save_interval"] == 50
    assert cfg["ex41_pose_commands"] is True
    assert cfg["ex41_w86_required"] is True
    assert cfg["ex41_critic_mirror"] is False
    assert cfg["perception"]["force_gt"] is False
    assert cfg["ex42_stage_zero_parent"]["cumulative_update"] == 12000

    with pytest.raises(ValueError, match="reconstruction/PRED"):
        entry.configure_ex42_stage_zero_train_cfg(
            {}, {"perception_cfg": {"map_input": "gt", "force_gt": True}},
            parent_path="C:/parent/model_6000.pt", parent_sha256="b" * 64)


def test_real_start_runner_parent_transfer_uses_strict_models_and_saved_training_state():
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
    runner.pcfg = dict(start_runner.MODE_DEFAULTS)
    runner.pcfg.update(map_input="reconstruction", force_gt=False, p_map_off=0.1)
    runner.p_map_off = 0.1
    runner.alg = SimpleNamespace(policy=Loader(), optimizer=Loader(), learning_rate=1.0)
    runner.perception = Loader()
    runner.adasmpl = Loader()
    runner.perception_optimizer = Loader()
    runner._apply_resume_adasmpl = lambda: None
    runner.load_map_switch_state = lambda *args: None
    runner.set_rng_state = lambda *_args: None
    checkpoint = {
        "format": start_runner.CKPT_FORMAT, "iter": 6000,
        "ex41_pose_commands": True, "ex41_critic_mirror": False,
        "perception_cfg": dict(runner.pcfg),
        "map_switch": {"p_map_off": 0.1},
        "model_state_dict": {"policy": "state"},
        "perception_state_dict": {"perception": "state"},
        "adasmpl": {"p": 0.4}, "optimizer_state_dict": {"state": {}},
        "ppo_learning_rate": 0.00038443359375,
        "perception_optimizer_state_dict": {"state": {}},
        "rng": {"python": [], "numpy": [], "torch": []},
        "last_use_gt_frac": 0.2,
    }
    result = runner.load_ex42_stage_zero_parent(checkpoint, _receipt())
    assert result["state"] == "loaded_for_ex42_stage_zero"
    assert result["local_iteration_origin"] == 0
    assert runner.current_learning_iteration == 0
    assert runner.alg.learning_rate == checkpoint["ppo_learning_rate"]
    assert runner._last_use_gt_frac == 0.2
    assert runner.alg.policy.calls[0][1] == {"strict": True}
    assert "ex41_environment_state" in result["not_restored"]


def test_resume_terrain_selection_is_applied_before_reset_and_all_roots_follow_saved_origins():
    import torch

    count = 3072
    terrain_origins = torch.zeros((6, 4, 3), dtype=torch.float32)
    for level in range(6):
        for terrain_type in range(4):
            terrain_origins[level, terrain_type] = torch.tensor(
                [100.0 + level * 10.0 + terrain_type,
                 -100.0 + terrain_type * 20.0 + level, 0.0])
    levels = torch.arange(count, dtype=torch.int64) % 6
    terrain_types = torch.arange(count, dtype=torch.int64) % 4
    initial_origins = torch.zeros((count, 3), dtype=torch.float32)
    root_positions = initial_origins.clone()
    terrain = SimpleNamespace(
        terrain_levels=torch.zeros(count, dtype=torch.int64),
        terrain_types=torch.zeros(count, dtype=torch.int64),
        terrain_origins=terrain_origins,
        env_origins=initial_origins.clone(),
    )
    scene = SimpleNamespace(terrain=terrain, env_origins=terrain.env_origins)

    class FakeEnv:
        unwrapped = None

        def __init__(self):
            self.scene = scene
            self.robot = SimpleNamespace(data=SimpleNamespace(root_pos_w=root_positions))
            self.scene.robot = self.robot
            self.unwrapped = self

        def reset(self):
            # Mirror reset_root_state_uniform: default root pose + selected scene origin.
            offset = torch.tensor([0.1, -0.2, 0.0]).expand(count, 3)
            self.robot.data.root_pos_w.copy_(self.scene.env_origins + offset)

    env = FakeEnv()
    saved = {"env_state": {"terrain_levels": levels, "terrain_types": terrain_types}}
    expected_saved_origins = terrain_origins[levels, terrain_types, :2]
    before_distance = torch.linalg.vector_norm(root_positions[:, :2] - expected_saved_origins, dim=1)
    assert int((before_distance > 1.0).sum()) == count

    prepared = entry.restore_stage_zero_resume_terrain_before_reset(env, saved)
    assert prepared["restored_before_reset"] is True
    assert prepared["env_count"] == count
    assert torch.equal(terrain.env_origins, terrain_origins[levels, terrain_types])
    env.reset()
    after = entry.build_stage_zero_resume_root_xy_readback(
        env, pose_range={"x": (-0.5, 0.5), "y": (-0.5, 0.5)})
    assert after["env_count"] == count
    assert after["outside_reset_bounds_count"] == 0
    expected_distance = (0.1**2 + 0.2**2) ** 0.5
    assert after["distance_xy_m"]["mean"] == pytest.approx(expected_distance, rel=1e-4)
    assert after["distance_xy_m"]["max"] == pytest.approx(expected_distance, rel=1e-4)
