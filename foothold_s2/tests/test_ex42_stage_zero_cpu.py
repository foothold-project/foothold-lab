from __future__ import annotations

from types import SimpleNamespace

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
