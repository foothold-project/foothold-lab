from __future__ import annotations

import ast
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import gymnasium as gym
import pytest
import torch

import foothold_s2.scripts.ex41_startup as ex41_startup
from foothold_s2.curriculum.ex41_fixed import baseline_counts
from foothold_s2.scripts.ex41_startup import (
    attach_ex41_stand_runtime_data,
    capture_first_observation,
    configure_ex41_train_cfg,
    first_observation_readback,
    install_end_by_warning_watch,
    install_initial_dr_scale,
    load_fixed_plan,
    prepare_ex41_env_cfg,
    require_production_authorization,
    production_launch_status,
    require_production_launch,
    write_production_launch_receipt,
    validate_output_with_launch_receipt,
    set_live_initial_dr_scale,
    run_rehearsal_dr_proof,
    validate_rehearsal_dr_samples,
    validate_rehearsal_request,
    validate_rehearsal_resume_request,
    validate_startup_smoke_request,
    verify_ex41_start_readback,
    verify_m6000_parent,
    write_ex41_start_readback,
)


REPO = Path(__file__).resolve().parents[2]
TABLE = REPO / "foothold_s2/curriculum/ex41-fixed5000.yaml"


def test_ex41_task_registration_and_config_entrypoint_source():
    __import__("foothold_s2.sb_tasks")

    spec = gym.spec("FootholdS2-Go2-S2-SB-v0")
    module_name, class_name = spec.kwargs["env_cfg_entry_point"].split(":", 1)
    config_path = REPO.joinpath(*module_name.split(".")).with_suffix(".py")
    tree = ast.parse(config_path.read_text(encoding="utf-8"), filename=str(config_path))
    assert class_name == "FootholdS2SBEnvCfg"
    assert any(isinstance(node, ast.ClassDef) and node.name == class_name for node in tree.body)
    source = (REPO / "foothold_s2/scripts/train_start.py").read_text(encoding="utf-8")
    assert source.index("import foothold_s2.sb_tasks") < source.index("@hydra_task_config")


def _assert_gpu0_marker_lifecycle(source: str) -> None:
    tree = ast.parse(source)
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    claim_line = next(node.lineno for node in ast.walk(tree)
                      if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                      and node.func.id == "_claim_ex41_gpu0_busy_marker")
    launcher_line = next(node.lineno for node in ast.walk(tree)
                         if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                         and node.func.id == "AppLauncher")
    gym_line = next(node.lineno for node in ast.walk(main)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "gym"
                    and node.func.attr == "make")
    assert claim_line < launcher_line < gym_line, "GPU0 busy marker must precede Kit and env creation"
    entry = next(node for node in tree.body if isinstance(node, ast.If)
                 and isinstance(node.test, ast.Compare)
                 and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__")
    try_node = next(node for node in entry.body if isinstance(node, ast.Try))
    assert try_node.finalbody and any(
        isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "_clear_ex41_gpu0_busy_marker"
        for final_node in try_node.finalbody for node in ast.walk(final_node)
    ), "GPU0 busy marker must clear in process finally"
    assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
               and isinstance(node.func.value, ast.Name) and node.func.value.id == "atexit"
               and node.func.attr == "register" for node in ast.walk(tree)), (
                   "GPU0 busy marker must clear if module startup fails before main")


def test_ex41_gpu0_marker_wraps_shared_production_rehearsal_and_smoke_path():
    source = (REPO / "foothold_s2/scripts/train_start.py").read_text(encoding="utf-8")
    _assert_gpu0_marker_lifecycle(source)
    claim = source.index("_claim_ex41_gpu0_busy_marker(marker_run, marker_iteration)")
    assert claim < source.index("app_launcher = AppLauncher(args_cli)")
    assert source.index("_write_ex41_gpu0_marker_receipt(log_dir)") < source.index(
        "env = gym.make(args_cli.task, cfg=env_cfg)")
    helper = source[source.index("def _claim_ex41_gpu0_busy_marker"):source.index("def _clear_ex41_gpu0_busy_marker")]
    assert "EX41_PLAN is None" in helper and "args_cli.device" in helper
    assert "wait_for_gpu0_python_idle()" in helper


def test_ex41_gpu0_marker_lifecycle_test_detects_removed_claim_mutation():
    source = (REPO / "foothold_s2/scripts/train_start.py").read_text(encoding="utf-8")
    mutated = source.replace("    _claim_ex41_gpu0_busy_marker(marker_run, marker_iteration)\n", "", 1)
    with pytest.raises(StopIteration):
        _assert_gpu0_marker_lifecycle(mutated)


def test_real_fixed_plan_has_pinned_m6000_dr_half_and_26_maintenance_cells():
    plan = load_fixed_plan(TABLE)
    baseline = baseline_counts(plan)
    assert plan.parent_update == 6000
    assert plan.initial_dr_scale == 0.5
    assert len(baseline) == 26
    assert plan.fixed_schedule["duration_updates"] == 6000


def test_d172_committed_w71_and_explicit_launch_switch():
    """D172 records W71 readiness; production still needs the lead switch."""
    plan = load_fixed_plan(TABLE)
    snapshot = ex41_startup.authorization_snapshot(plan)
    assert snapshot["config"]["values"]["w71_ready"] is True
    denied = production_launch_status(plan, lead_approved=False, snapshot=snapshot)
    allowed = production_launch_status(plan, lead_approved=True, snapshot=snapshot)
    assert denied["production_launch_allowed"] is False
    assert denied["reason"] == "lead_approval_switch_missing"
    assert allowed["production_launch_allowed"] is True
    assert allowed["w71_ready"] is True


def test_d172_w71_reaches_actual_fixed_runtime_start_and_hydra_wiring(tmp_path):
    from foothold_s2.curriculum.continuous import make_runtime
    from foothold_s2.curriculum import w72
    from foothold_s2.tests.ex41_runtime_fixture import attach_consumer

    plan = load_fixed_plan(TABLE)
    snapshot = ex41_startup.authorization_snapshot(plan)
    assert "w71_ready" in w72.BOOLS and "w71_ready" in w72.SNAPSHOT_BOOL_FIELDS
    assert type(snapshot["config"]["values"]["w71_ready"]) is bool
    changes = w72.validate_change(
        {**snapshot["config"]["values"], "w71_ready": False},
        snapshot["config"]["values"], snapshot["approvals"],
    )
    assert {row["path"]: row["decision_id"] for row in changes}["w71_ready"] == "D172"

    runtime = make_runtime(plan, 4, "cpu", tmp_path / "w71-start")
    attach_consumer(runtime)
    runtime.start(plan.parent_sha256)
    assert runtime._started is True
    assert runtime._snapshot["config"]["values"]["w71_ready"] is True
    assert runtime._receipt["status"] == "applied"
    assert runtime._receipt["config_sha256"] == snapshot["config_sha256"]
    assert runtime._receipt["approval_sha256"] == snapshot["approval_sha256"]

    source = (REPO / "foothold_s2/scripts/train_start.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    assert any(isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
               and d.func.id == "hydra_task_config" for d in main.decorator_list)
    assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
               and isinstance(node.func.value, ast.Name) and node.func.value.id == "ex41_runtime"
               and node.func.attr == "start" for node in ast.walk(main))


def test_current_production_boundary_refuses_unverified_w71(monkeypatch):
    plan = load_fixed_plan(TABLE)
    monkeypatch.setattr(ex41_startup, "authorization_snapshot",
                        lambda _plan: {"config": {"values": {"w71_ready": False}}})
    with pytest.raises(ValueError, match="W71 consumer is not verified"):
        require_production_authorization(plan)


def test_production_launch_requires_w71_and_one_explicit_lead_switch(tmp_path, monkeypatch):
    plan = load_fixed_plan(TABLE)
    snapshot = {"config":{"values":{"w71_ready":False}}}
    monkeypatch.setattr(ex41_startup, "authorization_snapshot", lambda _plan: snapshot)
    denied = production_launch_status(plan, lead_approved=False)
    assert denied["production_launch_allowed"] is False
    assert denied["reason"] == "lead_approval_switch_missing"
    with pytest.raises(ValueError, match="lead_approval_switch_missing"):
        require_production_launch(plan, lead_approved=False)
    with pytest.raises(ValueError, match="w71_not_ready"):
        require_production_launch(plan, lead_approved=True)

    snapshot["config"]["values"]["w71_ready"] = True
    allowed = production_launch_status(plan, lead_approved=True)
    assert allowed["production_launch_allowed"] is True
    assert allowed["w71_ready"] is True
    monkeypatch.setattr(ex41_startup, "_require_ex41_run_path", lambda path: Path(path))
    receipt_path = write_production_launch_receipt(
        tmp_path / "run", plan, {"sha256":plan.parent_sha256}, allowed)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["production_launch_allowed"] is True
    assert receipt["lead_approval_switch"] is True and receipt["w71_ready"] is True
    assert receipt["kit_started"] is False
    assert validate_output_with_launch_receipt(tmp_path / "run", receipt_path) == (tmp_path / "run").resolve()
    (tmp_path / "run" / "unexpected.txt").write_text("not an authorized pre-Kit artifact")
    with pytest.raises(ValueError, match="unexpected pre-Kit files"):
        validate_output_with_launch_receipt(tmp_path / "run", receipt_path)


def test_fixed_runtime_only_allows_unverified_w71_in_bounded_rehearsal(tmp_path):
    from foothold_s2.curriculum.continuous import make_runtime

    plan = load_fixed_plan(TABLE)
    values = {"ppo": {"entropy_coef": 0.01, "desired_kl": 0.01},
              "dr": {"target_scale": 0.5, "ramp_updates": 0},
              "reward_weights": {"zero_yaw": -0.5, "swing": -10.0, "stumble": -2.0},
              "command_share_bias": {"walk": 0.0, "spin": 0.0, "side": 0.0,
                                     "diag_fwd": 0.0, "diag_back": 0.0},
              "heading_forward_fraction": 0.3, "critic_mirror": False,
              "terrain_level_cap": 5, "w71_ready": False, "episode_length_s": 20.0}
    production = make_runtime(plan, 64, "cpu", tmp_path / "production")
    with pytest.raises(ValueError, match="verified W71 consumer"):
        production._check_values(values)
    rehearsal = make_runtime(plan, 64, "cpu", tmp_path / "rehearsal",
                             allow_w71_unverified=True)
    rehearsal._check_values(values)


def test_entrypoint_authorization_precedes_app_import_and_wires_consumers():
    source = (REPO / "foothold_s2/scripts/train_start.py").read_text(encoding="utf-8")
    assert source.index("require_production_authorization(EX41_PLAN)") < source.index(
        "from isaaclab.app import AppLauncher")
    assert "--ex41-production-launch-approved" in source
    assert source.index("require_production_launch(") < source.index(
        "from isaaclab.app import AppLauncher")
    assert "write_production_launch_receipt(" in source
    assert "prepare_ex41_env_cfg(env_cfg, EX41_PLAN)" in source
    assert "attach_runtime(env.unwrapped, EX41_PLAN, log_dir)" in source
    assert "configure_ex41_command_slots(command_term)" in source
    assert source.index("runner.ex40_dr_runtime = ex41_dr_readback") < source.index("ex41_runtime.attach(runner, command_term)")
    assert "ex41_runtime.max_updates = args_cli.ex41_rehearsal_updates" in source
    assert source.index("ex41_runtime.max_updates = args_cli.ex41_rehearsal_updates") < source.index(
        "remaining = max(0, ex41_runtime.max_updates - completed)")
    assert "EX-41 DR readback runtime was not created before runner attachment" in source
    assert "ex41_runtime.start(EX41_PLAN.parent_sha256)" in source
    assert "runner.load_ex41_parent()" in source
    assert "runner.ex41_w86_required" in source
    end_by = source.index("install_end_by_warning_watch(")
    assert source.rfind("if not (EX41_REHEARSAL or EX41_STARTUP_SMOKE):", 0, end_by) > source.rfind("if EX41_PLAN is not None:", 0, end_by)
    assert '"end_by_watch": ex41_end_by_receipt' in source
    assert source.index("prepare_ex41_env_cfg(env_cfg, EX41_PLAN)") < source.index("gym.make(")
    startup_source = (REPO / "foothold_s2/scripts/ex41_startup.py").read_text(encoding="utf-8")
    assert "prepare_pose_env_cfg(env_cfg)" in startup_source


def test_ex41_env_preparation_calls_pose_producer_and_records_contract(monkeypatch):
    called = []
    rewards = {"track_ang_vel": 1.0, "track_lin_vel": 2.0, "joint_acc": -1e-7,
               "hip_pos_penalty": -0.05, "thigh_calf_pos_l1": -0.01,
               "four_foot_contact_at_stop": 0.1, "stand_gap": -0.2,
               "stand_load": -0.1, "zero_yaw": -0.5, "swing": -10.0,
               "stumble": -2.0, "knee_effort_margin": 0.0,
               "joint_limit_margin": 0.0, "feet_air_time": 0.0, "foot_slip": 0.0}
    stand_cfg = {"gap_weight": -0.2, "load_weight": -0.1,
                 "load_fraction": 0.05, "ramp_s": 0.5}
    basic = SimpleNamespace(
        validate_settings=lambda weights, **kwargs: {"weights": weights, **kwargs},
        apply_settings=lambda cfg, settings: called.append(("basic", settings)),
        apply_ex39_settings=lambda cfg: {"thigh_calf_pos_l1": -0.01},
        apply_ex40_stand_settings=lambda cfg, config: called.append(("stand", config)))
    monkeypatch.setitem(sys.modules, "foothold_s2.rewards.basic_gait_bundle", basic)
    monkeypatch.setitem(sys.modules, "foothold_s2.curriculum.ex41", SimpleNamespace(
        prepare_terrain_cfg=lambda cfg, plan: {"terrain": "fixed"}))
    monkeypatch.setitem(sys.modules, "foothold_s2.curriculum.ex40_dr_runtime", SimpleNamespace(
        install_runtime_events=lambda *args, **kwargs: {"events": "installed"}))
    monkeypatch.setitem(sys.modules, "foothold_s2.rewards.w86_runtime", SimpleNamespace(
        prepare_env_cfg=lambda cfg, plan: {"weights": ["swing"]}))

    def zero_pose_command(_env):
        return None

    def attach_pose(cfg):
        called.append(cfg)
        cfg.observations.pose_cmd = SimpleNamespace(
            pose_cmd=SimpleNamespace(func=zero_pose_command),
            enable_corruption=False,
            concatenate_terms=True,
        )

    monkeypatch.setitem(sys.modules, "foothold_s2.sensors.start_obs", SimpleNamespace(
        apply_ex41_pose_observation=attach_pose,
        zero_pose_command=zero_pose_command))
    terms = {name: SimpleNamespace(func=lambda env, *args, **kwargs: None)
             for name in ("ex40_base_com", "ex40_actuator_gains", "ex40_motor_strength")}
    cfg = SimpleNamespace(observations=SimpleNamespace(), events=SimpleNamespace(**terms))
    plan = SimpleNamespace(domain_randomization={"full_ranges": {"delay_s": [0., .015]},
                                                  "push_interval_s": [10., 15.]},
                           initial_dr_scale=.5, stages=[SimpleNamespace(rewards=rewards)],
                           stand_cfg=stand_cfg)

    receipt = prepare_ex41_env_cfg(cfg, plan)

    assert called[0][0] == "basic"
    assert called[0][1]["weights"] == {key: rewards[key] for key in
                                        ("track_ang_vel", "track_lin_vel", "joint_acc", "hip_pos_penalty")}
    assert called[1] == ("stand", stand_cfg)
    assert called[2] == cfg
    assert cfg.observations.pose_cmd is not None
    assert receipt["pose_observation"] == {
        "group": "pose_cmd", "shape_per_env": [2],
        "columns": ["height_delta_m", "body_roll_rad"],
        "configured_value": [0.0, 0.0],
        "producer": "foothold_s2.sensors.start_obs.zero_pose_command",
        "applied": True}
    assert receipt["reward_contract"]["first_stage_weights"] == rewards


def test_attached_stand_runtime_data_uses_realized_per_env_mass(monkeypatch):
    recorded = []
    monkeypatch.setitem(sys.modules, "foothold_s2.rewards.basic_gait_bundle",
                        SimpleNamespace(StandSensorEvidence=SimpleNamespace(
                            from_env=lambda env: recorded.append(env) or {"attached": True})))
    class PhysXView:
        def get_masses(self):
            return torch.tensor([[1.0, 2.0], [1.5, 2.5]])
    robot = SimpleNamespace(root_physx_view=PhysXView())
    raw = SimpleNamespace(scene={"robot": robot}, num_envs=2, device="cpu")
    receipt = attach_ex41_stand_runtime_data(SimpleNamespace(unwrapped=raw))
    assert torch.equal(raw._ex40_total_mass_kg, torch.tensor([3.0, 4.0]))
    assert raw._ex40_stand_evidence == {"attached": True} and recorded == [raw]
    assert receipt == {"num_envs": 2, "mass_min_kg": 3.0, "mass_max_kg": 4.0,
                       "source": "root_physx_view.get_masses"}


def _first_obs(envs=3, pose=None):
    return {"policy": torch.zeros(envs, 45), "depth": torch.zeros(envs, 60, 60),
            "gt_map": torch.zeros(envs, 512), "gt_feet": torch.zeros(envs, 100),
            "base_vel": torch.zeros(envs, 3), "contacts": torch.zeros(envs, 4),
            "pose_cmd": torch.zeros(envs, 2) if pose is None else pose}


def test_first_observation_readback_validates_dimensions_and_zero_pose_columns():
    receipt = first_observation_readback(_first_obs(), expected_envs=3)
    assert receipt["groups"] == {"policy": [45], "depth": [60, 60], "gt_map": [512],
                                 "gt_feet": [100], "base_vel": [3], "contacts": [4],
                                 "pose_cmd": [2]}
    assert receipt["pose_cmd"]["zero_by_column"] == [True, True]
    assert receipt["pose_cmd"]["shape"] == [3, 2]
    bad = _first_obs(pose=torch.tensor([[0., 0.], [0., .1], [0., 0.]]))
    with pytest.raises(ValueError, match="columns are not both zero"):
        first_observation_readback(bad, expected_envs=3)


def test_first_observation_capture_does_not_read_environment_twice():
    class Env:
        num_envs = 3

        def __init__(self):
            self.calls = 0

        def get_observations(self):
            self.calls += 1
            return _first_obs()

    env = Env()
    original = env.get_observations
    with capture_first_observation(env) as receipt:
        observed = env.get_observations()
    assert env.calls == 1
    assert env.get_observations == original
    assert observed["pose_cmd"].shape == (3, 2)
    assert receipt["pose_cmd"]["zero_by_column"] == [True, True]


def test_train_cfg_requires_pose_and_w86_with_pinned_parent(tmp_path):
    plan = load_fixed_plan(TABLE)
    parent = tmp_path / "model_6000.pt"
    parent.write_bytes(b"test checkpoint placeholder")
    params = tmp_path / "params"
    params.mkdir()
    (params / "agent.yaml").write_text("perception:\n  p_map_off: 0.1\n", encoding="utf-8")
    cfg = configure_ex41_train_cfg({}, plan, parent)
    assert cfg["ex41_pose_commands"] is True
    assert cfg["ex41_w86_required"] is True
    assert cfg["max_iterations"] == 6501
    assert cfg["perception"]["p_map_off"] == 0.1
    assert cfg["ex41_parent"] == {"path": str(parent.resolve()),
                                  "sha256": plan.parent_sha256, "iteration": 6000}


def test_parent_receipt_distinguishes_checkpoint_iteration_from_manifest_progress(tmp_path):
    import hashlib

    run = tmp_path / "run"
    params = run / "params"
    params.mkdir(parents=True)
    checkpoint = run / "model_6000.pt"
    checkpoint.write_bytes(b"m6000 bytes")
    env_path, agent_path = params / "env.yaml", params / "agent.yaml"
    env_path.write_text("scene: {num_envs: 3072}\n", encoding="utf-8")
    agent_path.write_text("save_interval: 50\n", encoding="utf-8")
    checkpoint_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    env_sha = hashlib.sha256(env_path.read_bytes()).hexdigest()
    agent_sha = hashlib.sha256(agent_path.read_bytes()).hexdigest()
    (run / "manifest.json").write_text(json.dumps({
        "checkpoints": {checkpoint.name: checkpoint_sha},
        "progress": {"completed_updates": 8001},
    }), encoding="utf-8")
    plan = SimpleNamespace(parent_update=6000, parent_sha256=checkpoint_sha,
                           baseline_env_yaml_sha256=env_sha,
                           baseline_agent_yaml_sha256=agent_sha)

    receipt = verify_m6000_parent(plan, checkpoint)
    assert receipt["parent_checkpoint_update"] == 6000
    assert receipt["manifest_completed_updates"] == 8001
    assert receipt["sha256"] == checkpoint_sha


def test_rehearsal_config_is_bounded_and_uses_isolated_output(tmp_path):
    plan = load_fixed_plan(TABLE)
    parent = tmp_path / "model_6000.pt"
    parent.write_bytes(b"known parent")
    params = tmp_path / "params"
    params.mkdir()
    (params / "agent.yaml").write_text("perception:\n  p_map_off: 0.1\n", encoding="utf-8")
    configured = configure_ex41_train_cfg(
        {"ex41_w86_required": True, "save_interval": 100}, plan, parent,
        rehearsal_updates=10)
    assert configured["max_iterations"] == 10
    assert configured["save_interval"] == 1
    assert configured["ex41_rehearsal"] is True

    output = tmp_path / "s2_lab" / "ex41_rehearsal_20261102_164500"
    output.parent.mkdir()
    assert validate_rehearsal_request(10, output, "cuda:0", True) == output
    with pytest.raises(ValueError, match="exactly 10"):
        validate_rehearsal_request(11, output, "cuda:0", True)
    with pytest.raises(ValueError, match="headless cuda:0"):
        validate_rehearsal_request(10, output, "cuda:1", True)
    output.mkdir()
    (output / "unexpected.txt").write_text("must reject", encoding="utf-8")
    with pytest.raises(ValueError, match="new or empty"):
        validate_rehearsal_request(10, output, "cuda:0", True)


def test_production_path_smoke_is_bounded_but_keeps_production_authorization_false(tmp_path):
    plan = load_fixed_plan(TABLE)
    parent = tmp_path / "model_6000.pt"
    parent.write_bytes(b"known parent")
    params = tmp_path / "params"
    params.mkdir()
    (params / "agent.yaml").write_text("perception:\n  p_map_off: 0.1\n", encoding="utf-8")
    configured = configure_ex41_train_cfg(
        {"ex41_w86_required": True, "save_interval": 100}, plan, parent,
        startup_smoke_updates=10)
    assert configured["max_iterations"] == 10
    assert configured["save_interval"] == 10
    assert configured["ex41_startup_smoke"] is True
    assert "ex41_rehearsal" not in configured

    output = Path("C:/Users/AI-WS01/s2_lab/ex41_smoke_20261103_235959")
    assert validate_startup_smoke_request(10, output, "cuda:0", True) == output
    assert ex41_startup._require_ex41_run_path(output) == output
    with pytest.raises(ValueError, match="exactly 10"):
        validate_startup_smoke_request(11, output, "cuda:0", True)
    with pytest.raises(ValueError, match="headless cuda:0"):
        validate_startup_smoke_request(10, output, "cuda:1", True)
    with pytest.raises(ValueError, match="C:/Users/AI-WS01/s2_lab"):
        validate_startup_smoke_request(10, "C:/Users/AI-WS01/s2_lab/ex41_main_20261103_235959/main/run",
                                       "cuda:0", True)
    status = production_launch_status(plan, lead_approved=False, snapshot={"config":{"values":{"w71_ready":True}}})
    assert status["production_launch_allowed"] is False
    assert status["reason"] == "lead_approval_switch_missing"


def test_rehearsal_resume_accepts_only_latest_completed_same_run_model(tmp_path):
    run = tmp_path / "s2_lab" / "ex41_rehearsal_20261103_003500"
    run.mkdir(parents=True)
    checkpoint = run / "model_10.pt"
    checkpoint.write_bytes(b"known model 10")
    (run / "manifest.json").write_text(json.dumps({
        "progress": {"completed_updates": 10},
        "modes": {"ex41": {"rehearsal": {"enabled": True}}},
    }), encoding="utf-8")
    (run / "train_start_status.json").write_text(
        json.dumps({"state": "done", "iter": 10}), encoding="utf-8")

    assert validate_rehearsal_resume_request(
        12, run, checkpoint, "cuda:0", True) == run.resolve()
    with pytest.raises(ValueError, match="one or two new updates"):
        validate_rehearsal_resume_request(13, run, checkpoint, "cuda:0", True)
    with pytest.raises(ValueError, match="headless cuda:0"):
        validate_rehearsal_resume_request(12, run, checkpoint, "cuda:1", True)

    (run / "train_start_status.json").write_text(
        json.dumps({"state": "starting", "iter": 10}), encoding="utf-8")
    with pytest.raises(ValueError, match="still alive or has no PID"):
        validate_rehearsal_resume_request(12, run, checkpoint, "cuda:0", True)


def test_rehearsal_resume_retry_requires_failure_receipt_and_dead_process(tmp_path, monkeypatch):
    run = tmp_path / "s2_lab" / "ex41_rehearsal_20261103_003600"
    run.mkdir(parents=True)
    checkpoint = run / "model_10.pt"
    checkpoint.write_bytes(b"known model 10")
    (run / "manifest.json").write_text(json.dumps({
        "progress": {"completed_updates": 10},
        "modes": {"ex41": {"rehearsal": {"enabled": True}}},
    }), encoding="utf-8")
    (run / "train_start_status.json").write_text(
        json.dumps({"state": "failed", "iter": 10, "pid": 991234}), encoding="utf-8")
    alerts = run / "ex41_reports" / "alerts.jsonl"
    alerts.parent.mkdir()
    alerts.write_text(json.dumps({"kind": "nonzero_process_exit", "rc": 1}) + "\n",
                      encoding="utf-8")

    monkeypatch.setattr(ex41_startup, "_process_is_alive", lambda pid: False)
    assert validate_rehearsal_resume_request(
        12, run, checkpoint, "cuda:0", True) == run.resolve()

    monkeypatch.setattr(ex41_startup, "_process_is_alive", lambda pid: True)
    with pytest.raises(ValueError, match="still alive"):
        validate_rehearsal_resume_request(12, run, checkpoint, "cuda:0", True)

    monkeypatch.setattr(ex41_startup, "_process_is_alive", lambda pid: False)
    alerts.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="failure alert"):
        validate_rehearsal_resume_request(12, run, checkpoint, "cuda:0", True)


def test_resume_dr_baselines_move_from_cpu_checkpoint_to_environment_device():
    from torch._subclasses.fake_tensor import FakeTensorMode

    mode = FakeTensorMode(allow_non_fake_inputs=True)
    with mode:
        raw = SimpleNamespace(
            device=torch.device("cuda:0"),
            _ex40_dr_com_baseline=torch.arange(21, dtype=torch.float32).reshape(1, 3, 7),
            _ex40_dr_motor_baselines={"legs": {
                "stiffness": torch.ones((1, 12), dtype=torch.float32),
                "damping": torch.full((1, 12), 2.0, dtype=torch.float32),
            }},
        )
        com_cpu = raw._ex40_dr_com_baseline
        motors_cpu = raw._ex40_dr_motor_baselines["legs"]["stiffness"]
        runtime_env = SimpleNamespace(
            device=torch.device("cpu"),
            _ex40_dr_com_baseline=torch.ones((1, 1, 7)),
        )
        runtime_cpu = runtime_env._ex40_dr_com_baseline
        receipt = ex41_startup.normalize_ex41_dr_baselines(
            raw, additional_envs=(runtime_env,))

        assert raw._ex40_dr_com_baseline.device == torch.device("cuda:0")
        assert raw._ex40_dr_com_baseline.shape == com_cpu.shape
        assert raw._ex40_dr_motor_baselines["legs"]["stiffness"].device == torch.device("cuda:0")
        assert raw._ex40_dr_motor_baselines["legs"]["damping"].device == torch.device("cuda:0")
        assert com_cpu.device == torch.device("cpu")
        assert motors_cpu.device == torch.device("cpu")
        assert runtime_env._ex40_dr_com_baseline.device == torch.device("cuda:0")
        assert runtime_cpu.device == torch.device("cpu")
        assert receipt["device"] == "cuda:0"
        assert receipt["com_baseline"]["from_device"] == "cpu"
        assert receipt["com_baseline"]["to_device"] == "cuda:0"
        assert receipt["owners"][1]["_ex40_dr_com_baseline"]["from_device"] == "cpu"
        assert receipt["owners"][1]["_ex40_dr_com_baseline"]["to_device"] == "cuda:0"


def test_resume_dr_reset_guard_normalizes_actual_event_env_before_consumers():
    from torch._subclasses.fake_tensor import FakeTensorMode

    mode = FakeTensorMode(allow_non_fake_inputs=True)
    calls = []
    with mode:
        action = SimpleNamespace(delay=torch.zeros(2, dtype=torch.long),
                                 _prev=torch.ones((2, 12)),
                                 _ex40_sample_counts=torch.ones((3,), dtype=torch.long))
        actuator = SimpleNamespace(stiffness=torch.ones((2, 12)),
                                   damping=torch.ones((2, 12)),
                                   effort_limit=torch.ones((2, 12)),
                                   _saturation_effort=torch.ones((2, 12)))
        robot = SimpleNamespace(
            data=SimpleNamespace(default_joint_stiffness=torch.ones((2, 12)),
                                 default_joint_damping=torch.ones((2, 12))),
            actuators={"legs": actuator},
        )
        raw = SimpleNamespace(
            device=torch.device("cuda:0"),
            _ex40_dr_scale=0.5,
            _ex40_dr_com_baseline=torch.ones((2, 1, 7)),
            _ex40_dr_motor_baselines={"legs": {"effort_limit": torch.ones((2, 12))}},
            _ex40_dr_gain_baselines={"legs": {"stiffness": torch.ones((2, 12))}},
            _ex40_dr_delay_baseline=torch.zeros((2,), dtype=torch.long),
            action_manager=SimpleNamespace(get_term=lambda _name: action),
            scene={"robot": robot},
        )
        cfg = SimpleNamespace(events=SimpleNamespace(**{
            name: SimpleNamespace(func=lambda env, *args, **kwargs: calls.append(env))
            for name in ("ex40_base_com", "ex40_actuator_gains", "ex40_motor_strength")
        }))
        install_initial_dr_scale(cfg, 0.5)
        cfg.events.ex40_base_com.func(raw, env_ids=[0])

        assert calls == [raw]
        assert raw._ex40_dr_com_baseline.device == torch.device("cuda:0")
        assert raw._ex40_dr_motor_baselines["legs"]["effort_limit"].device == torch.device("cuda:0")
        assert raw._ex40_dr_gain_baselines["legs"]["stiffness"].device == torch.device("cuda:0")
        assert raw._ex40_dr_delay_baseline.device == torch.device("cuda:0")
        assert action.delay.device == torch.device("cuda:0")
        assert action._prev.device == torch.device("cuda:0")
        assert action._ex40_sample_counts.device == torch.device("cuda:0")
        assert robot.data.default_joint_stiffness.device == torch.device("cuda:0")
        assert robot.data.default_joint_damping.device == torch.device("cuda:0")
        assert actuator.stiffness.device == torch.device("cuda:0")
        assert actuator.damping.device == torch.device("cuda:0")
        assert actuator.effort_limit.device == torch.device("cuda:0")
        assert actuator._saturation_effort.device == torch.device("cuda:0")
        assert raw._ex41_dr_device_guard["reset_term"] == "ex40_base_com"
        assert raw._ex41_dr_device_guard["action_delay"]["to_device"] == "cuda:0"


def test_reset_base_com_restores_env_device_baseline_through_cpu_physx_contract(monkeypatch):
    from types import ModuleType
    from torch._subclasses.fake_tensor import FakeTensorMode

    from foothold_s2.curriculum import ex40_dr_runtime

    calls = {}

    class PhysXView:
        def get_coms(self):
            return torch.zeros((2, 1, 7), device="cpu")

        def set_coms(self, coms, env_ids):
            calls["set_device"] = str(coms.device)
            calls["set_env_ids_device"] = str(env_ids.device)

    class Scene(dict):
        num_envs = 2

    def randomize_rigid_body_com(env, env_ids, com_range, asset_cfg):
        calls["event_env_ids_device"] = str(env_ids.device)
        calls["event_scale"] = env._ex40_dr_scale

    isaaclab = ModuleType("isaaclab")
    isaaclab_envs = ModuleType("isaaclab.envs")
    isaaclab_mdp = ModuleType("isaaclab.envs.mdp")
    isaaclab_mdp.events = SimpleNamespace(randomize_rigid_body_com=randomize_rigid_body_com)
    monkeypatch.setitem(sys.modules, "isaaclab", isaaclab)
    monkeypatch.setitem(sys.modules, "isaaclab.envs", isaaclab_envs)
    monkeypatch.setitem(sys.modules, "isaaclab.envs.mdp", isaaclab_mdp)
    monkeypatch.setattr(ex40_dr_runtime, "_record", lambda *args, **kwargs: None)

    mode = FakeTensorMode(allow_non_fake_inputs=True)
    with mode:
        raw = SimpleNamespace(
            device=torch.device("cuda:0"),
            scene=Scene(robot=SimpleNamespace(root_physx_view=PhysXView())),
            _ex40_dr_scale=0.8,
            _ex40_dr_com_baseline=torch.ones((2, 1, 7), device="cuda:0"),
        )
        cfg = SimpleNamespace(name="robot", body_ids=slice(None))
        ex40_dr_runtime.reset_base_com(
            raw, torch.tensor([1], dtype=torch.long), cfg,
            {"x": (-0.05, 0.05), "y": (-0.05, 0.05), "z": (-0.05, 0.05)},
        )

    assert raw._ex40_dr_com_baseline.device == torch.device("cuda:0")
    assert calls == {"set_device": "cpu", "set_env_ids_device": "cpu",
                     "event_env_ids_device": "cpu", "event_scale": 0.8}


def test_runtime_readback_summary_bridges_cpu_physx_com_to_env_device_baseline(monkeypatch):
    from torch._subclasses.fake_tensor import FakeTensorMode

    from foothold_s2.curriculum import ex40_dr_runtime

    captured = []
    monkeypatch.setattr(
        ex40_dr_runtime, "_stats",
        lambda values: captured.append((str(values.device), tuple(values.shape))) or {"count": 2},
    )
    mode = FakeTensorMode(allow_non_fake_inputs=True)
    with mode:
        env = SimpleNamespace(
            device=torch.device("cuda:0"),
            scene={"robot": SimpleNamespace(
                root_physx_view=SimpleNamespace(
                    get_coms=lambda: torch.zeros((2, 1, 7), device="cpu")),
                actuators={},
            )},
            action_manager=SimpleNamespace(get_term=lambda _name: SimpleNamespace(delay=None)),
            physics_dt=0.005,
            _ex40_dr_com_baseline=torch.ones((2, 1, 7), device="cuda:0"),
            _ex40_dr_samples={},
        )
        result = ex40_dr_runtime.RuntimeReadback(env, ranges={}).summary()

    assert result["realized_state"]["base_com_offset_m"] == {"count": 2}
    assert captured == [("cuda:0", (2, 1, 3))]


def test_end_by_is_an_alert_only_budget_plus_extension_and_buffer(tmp_path):
    plan = load_fixed_plan(TABLE)
    started = datetime(2026, 11, 3, tzinfo=timezone.utc)
    events = []
    runtime = SimpleNamespace(
        clock=SimpleNamespace(elapsed=0, pause_used=0, extension=0, extension_decided=False),
        on_update_start=lambda update: events.append(("update", update)) or "continue",
        _write=lambda row: events.append(("event", row)),
    )
    receipt = install_end_by_warning_watch(
        runtime, tmp_path, plan, now=started,
        clock_now=lambda: datetime.fromisoformat(receipt["end_by"]) + timedelta(seconds=1),
        seconds_per_update=26.3, deliver=False)
    expected_end = started + timedelta(seconds=6000 * 26.3)
    expected_deadline = expected_end + timedelta(seconds=(1000 + 500) * 26.3 + 86400)
    assert datetime.fromisoformat(receipt["expected_end_at"]) == expected_end
    assert datetime.fromisoformat(receipt["end_by"]) == expected_deadline
    assert receipt["action"] == "warning_only" and receipt["training_stop_on_deadline"] is False
    assert runtime.on_update_start(251) == "continue"
    assert runtime.on_update_start(501) == "continue"
    assert [row[1]["event"] for row in events if row[0] == "event"] == ["end_by_warning"]
    alert = json.loads((tmp_path / "ex41_reports/alerts.jsonl").read_text().splitlines()[0])
    assert alert["kind"] == "end_by_warning" and alert["training_stop_on_deadline"] is False
    assert json.loads((tmp_path / "ex41_reports/end_by_watch.json").read_text())["action"] == "warning_only"


def _known_scale_08_dr_row(ranges):
    from foothold_s2.curriculum.ex40_dr import interpolate_range

    def stat(bounds):
        low, high = bounds
        return {"count": 64, "min": low, "max": high,
                "mean": (low + high) / 2, "target_envs": 64}

    com_bounds = [interpolate_range((0.0, 0.0), ranges["base_com"][axis], 0.8)
                  for axis in ("x", "y", "z")]
    gain_bounds = [interpolate_range((1.0, 1.0), ranges["actuator_gains"][name], 0.8)
                   for name in ("stiffness_scale", "damping_scale")]
    motor_bounds = interpolate_range((1.0, 1.0), ranges["motor_strength"], 0.8)
    push_bounds = [interpolate_range((0.0, 0.0), pair, 0.8)
                   for pair in ranges["push_velocity"].values()]
    actual = {
        "base_com_offset_m": stat((min(x[0] for x in com_bounds), max(x[1] for x in com_bounds))),
        "actuator_gains": stat((min(x[0] for x in gain_bounds), max(x[1] for x in gain_bounds))),
        "motor_strength_multiplier": stat(motor_bounds),
        "motor_effort_limit": stat((0.1, 1.0)),
        "motor_saturation_effort": stat((0.1, 1.0)),
        "push_velocity_delta": stat((min(x[0] for x in push_bounds), max(x[1] for x in push_bounds))),
    }
    allowed_delay = int((ranges["delay_s"][1] * 0.8) / 0.005)
    return {"scale": 0.8, "actual_samples": actual,
            "delay_readback": {"reset_sample_count": 64,
                               "configured_max_seconds": ranges["delay_s"][1] * 0.8,
                               "observed_max_substeps": allowed_delay,
                               "max_allowed_substeps": allowed_delay}}


def test_rehearsal_dr_proof_requires_actual_scale_08_sample_ranges_and_delay():
    plan = load_fixed_plan(TABLE)
    row = _known_scale_08_dr_row(plan.domain_randomization["full_ranges"])
    checked = validate_rehearsal_dr_samples(row, plan.domain_randomization["full_ranges"])
    assert checked["scale"] == 0.8
    assert all(value == 64 for value in checked["sample_counts"].values())
    row["actual_samples"]["motor_strength_multiplier"]["max"] += 0.01
    with pytest.raises(ValueError, match="outside scale 0.8 range"):
        validate_rehearsal_dr_samples(row, plan.domain_randomization["full_ranges"])


def test_rehearsal_dr_proof_forces_interval_event_then_restores_half_scale(tmp_path):
    plan = load_fixed_plan(TABLE)
    ranges = plan.domain_randomization["full_ranges"]

    class Events:
        def __init__(self):
            self.calls = []

        def apply(self, mode, **kwargs):
            self.calls.append((mode, kwargs))

    class Env:
        def __init__(self):
            self._ex41_initial_dr_scale_applied = None
            self.event_manager = Events()
            self.resets = 0
            self.device = "cpu"
            self.unwrapped = self

        def reset(self):
            self.resets += 1
            if self._ex41_initial_dr_scale_applied is None:
                self._ex41_initial_dr_scale_applied = 0.5

    class Readback:
        def __init__(self, env):
            self.env = env
            self.scale = 0.5

        def summary(self):
            return _known_scale_08_dr_row(ranges) | {"scale": self.scale}

    env = Env()
    dr = Readback(env)
    result = run_rehearsal_dr_proof(env, dr, ranges, tmp_path, plan.sha256, 0.015)
    assert result["state"] == "verified"
    assert env.resets == 3
    assert env.event_manager.calls == [("interval", {"dt": 15.0})]
    assert env._ex40_dr_scale == dr.scale == 0.5
    saved = json.loads((tmp_path / "ex41_dr_scale_08_readback.json").read_text(encoding="utf-8"))
    assert saved["state"] == "verified" and saved["scale"] == 0.8
    repeated = run_rehearsal_dr_proof(env, dr, ranges, tmp_path, plan.sha256, 0.015)
    assert repeated == json.loads(json.dumps(result, allow_nan=False))
    assert env.resets == 3


def test_training_entry_keeps_dr_08_opt_in_and_marks_rehearsal_followups_explicitly():
    source = (REPO / "foothold_s2/scripts/train_start.py").read_text(encoding="utf-8")
    branch = source[source.index("if resume_path is None:"):source.index("ex41_w86_receipt = attach_runtime")]
    assert "if EX41_REHEARSAL and args_cli.ex41_rehearsal_dr_08:" in branch
    assert "run_rehearsal_dr_proof(" in branch
    resume = source[source.index("runner.load(resume_path, map_location=\"cpu\")"):]
    assert resume.index("normalize_ex41_dr_baselines(") < resume.index("restored_state = runner.state_dict()")
    assert "additional_envs=(dr_runtime_env,)" in resume
    assert '"dr_baseline_device_readback": dr_device_receipt' in resume
    for receipt_field in (
        '"local_update_origin": runner.current_learning_iteration',
        '"first_completed_update": runner.current_learning_iteration + 1',
        '"new_process_resume_u5": ("verified_state_readback" if resume_state_comparison else',
        '"schedule_boundary_0_8": ("not_requested" if not args_cli.ex41_rehearsal_dr_08',
        '"score_watch_26_cells_once": "separate_oneoff_ready_not_run"',
        '"dr_scale_08": "not_requested" if not args_cli.ex41_rehearsal_dr_08 else "forced_reset_readback"',
        '_pre.add_argument("--ex41_rehearsal_dr_08", action="store_true")',
        'parser.add_argument("--ex41_rehearsal_dr_08", action="store_true"',
    ):
        assert receipt_field in source


def test_initial_dr_is_seeded_once_and_later_stage_scale_survives_resets():
    import inspect

    calls = []
    def event(env, env_ids, asset_cfg, target_range):
        calls.append((env._ex40_dr_scale, env_ids, asset_cfg, target_range))
    cfg = SimpleNamespace(events=SimpleNamespace(**{
        name: SimpleNamespace(func=event)
        for name in ("ex40_base_com", "ex40_actuator_gains", "ex40_motor_strength")
    }))
    receipt = install_initial_dr_scale(cfg, 0.5)
    env = SimpleNamespace(_ex40_dr_scale=0.)
    expected_signature = inspect.signature(event)
    for name in receipt["reset_terms"]:
        wrapped = getattr(cfg.events, name).func
        assert inspect.signature(wrapped) == expected_signature
        wrapped(env, env_ids=[0], asset_cfg="robot", target_range={"x": 1})
    assert receipt["before_first_reset"] is True
    assert len(calls) == 3 and all(scale == 0.5 for scale, *_ in calls)
    assert env._ex41_initial_dr_scale_applied == 0.5

    # A later W72 stage may raise scale; the next reset must not put it back
    # to the startup value before any of the existing DR consumers run.
    env._ex40_dr_scale = 1.0
    calls.clear()
    for name in receipt["reset_terms"]:
        getattr(cfg.events, name).func(
            env, env_ids=[1], asset_cfg="robot", target_range={"x": 1})
    assert len(calls) == 3 and all(scale == 1.0 for scale, *_ in calls)
    assert env._ex40_dr_scale == 1.0


def test_rng_restore_normalizes_checkpoint_rng_tensors_to_cpu(monkeypatch):
    import foothold_s2.runners.start_runner as start_runner

    seen = {}

    class MappedState:
        def cpu(self):
            seen["cpu_called"] = True
            return torch.tensor([1, 2, 3], dtype=torch.uint8)

    monkeypatch.setattr(start_runner.torch, "set_rng_state",
                        lambda value: seen.update(device=value.device.type, dtype=str(value.dtype)))
    monkeypatch.setattr(start_runner.np.random, "set_state", lambda _value: None)
    monkeypatch.setattr(start_runner.random, "setstate", lambda _value: None)
    start_runner.StartRunner.set_rng_state({"torch": MappedState(), "numpy": object(),
                                            "python": object()})
    assert seen == {"cpu_called": True, "device": "cpu", "dtype": "torch.uint8"}


def test_existing_dr_runtime_readback_is_set_to_half_before_rollout():
    runtime, env = SimpleNamespace(scale=0.), SimpleNamespace(_ex40_dr_scale=0.)
    assert set_live_initial_dr_scale(runtime, env, 0.5) == {
        "runtime_scale": 0.5, "env_scale": 0.5}


def test_ex41_command_slot_counter_expands_and_preserves_existing_counts():
    from foothold_s2.scripts.ex41_startup import configure_ex41_command_slots

    term = SimpleNamespace(slot_names=("forward", "walk_left", "walk_right", "spin_left", "spin_right"),
                           slot_counts=torch.tensor([10, 11, 12, 13, 14]))
    receipt = configure_ex41_command_slots(term)
    assert len(term.slot_names) == 13 and term.slot_names[:5] == (
        "forward", "walk_left", "walk_right", "spin_left", "spin_right")
    assert term.slot_counts.tolist() == [10, 11, 12, 13, 14, 0, 0, 0, 0, 0, 0, 0, 0]
    assert receipt["preserved_counts"] == 60


def test_u21_reloads_manifest_yaml_parent_and_first_reset_dr(tmp_path, monkeypatch):
    import foothold_s2.scripts.ex41_startup as startup
    from foothold_s2.runners.manifest import yaml_flat

    def reject_legacy_drive_guard(_path):
        raise AssertionError("U21 must share the approved output path validator")

    monkeypatch.setattr(startup, "_require_d_drive", reject_legacy_drive_guard)

    run = tmp_path / "u21"
    params = run / "params"
    params.mkdir(parents=True)
    parent = run / "model_6000.pt"
    parent.write_bytes(b"pinned parent bytes")
    plan = SimpleNamespace(sha256="a" * 64, effective_sha256="b" * 64,
                           parent_sha256=__import__("hashlib").sha256(parent.read_bytes()).hexdigest())
    env_yaml = params / "env.yaml"
    agent_yaml = params / "agent.yaml"
    env_yaml.write_text("scene:\n  num_envs: 2\n", encoding="utf-8")
    agent_yaml.write_text("max_iterations: 6501\n", encoding="utf-8")
    parent_receipt = {"checkpoint": str(parent.resolve()), "sha256": plan.parent_sha256}
    modes = {"ex41": {"plan_sha256": plan.sha256,
                       "effective_sha256": plan.effective_sha256,
                       "parent": parent_receipt,
                       "initial_dr_contract": {"scale": 0.5, "before_first_reset": True}}}
    manifest = {"modes": modes,
                "yaml": {"env": yaml_flat(str(env_yaml)), "agent": yaml_flat(str(agent_yaml))}}
    (run / "manifest.json").write_text(__import__("json").dumps(manifest), encoding="utf-8")
    env = SimpleNamespace(unwrapped=SimpleNamespace(_ex41_initial_dr_scale_applied=0.5,
                                                    _ex40_dr_scale=0.5))
    runtime = SimpleNamespace(scale=0.5)

    receipt = verify_ex41_start_readback(run, plan, parent_receipt, manifest, env, runtime)
    assert receipt["status"] == "verified"
    assert receipt["first_reset_dr_scale"] == 0.5
    assert write_ex41_start_readback(run, receipt).is_file()

    env.unwrapped._ex41_initial_dr_scale_applied = 0.25
    with pytest.raises(ValueError, match="first-reset DR readback"):
        verify_ex41_start_readback(run, plan, parent_receipt, manifest, env, runtime)
    env.unwrapped._ex41_initial_dr_scale_applied = 0.5
    env.unwrapped._ex40_dr_scale = 0.25
    with pytest.raises(ValueError, match="first-reset DR readback"):
        verify_ex41_start_readback(run, plan, parent_receipt, manifest, env, runtime)
    env.unwrapped._ex40_dr_scale = 0.5
    runtime.scale = 0.25
    with pytest.raises(ValueError, match="first-reset DR readback"):
        verify_ex41_start_readback(run, plan, parent_receipt, manifest, env, runtime)


def test_ex41_shared_output_validator_accepts_d164_c_main_shape():
    from pathlib import Path
    from foothold_s2.scripts.ex41_startup import _require_ex41_run_path

    run = Path("C:/Users/AI-WS01/s2_lab/ex41_main_20990101_000000/main/EX41-cpu-contract")
    assert _require_ex41_run_path(run) == run.resolve()


def test_u21_rejects_disk_manifest_yaml_and_parent_sha_mismatch(tmp_path):
    import hashlib
    import json
    from foothold_s2.runners.manifest import yaml_flat

    run = tmp_path / "u21_bad"
    params = run / "params"
    params.mkdir(parents=True)
    parent = run / "model_6000.pt"
    parent.write_bytes(b"pinned parent bytes")
    plan = SimpleNamespace(sha256="a" * 64, effective_sha256="b" * 64,
                           parent_sha256=hashlib.sha256(parent.read_bytes()).hexdigest())
    env_yaml = params / "env.yaml"
    agent_yaml = params / "agent.yaml"
    env_yaml.write_text("scene:\n  num_envs: 2\n", encoding="utf-8")
    agent_yaml.write_text("max_iterations: 6501\n", encoding="utf-8")
    parent_receipt = {"checkpoint": str(parent.resolve()), "sha256": plan.parent_sha256}
    modes = {"ex41": {"plan_sha256": plan.sha256,
                       "effective_sha256": plan.effective_sha256,
                       "parent": parent_receipt,
                       "initial_dr_contract": {"scale": 0.5, "before_first_reset": True}}}
    manifest = {"modes": modes,
                "yaml": {"env": yaml_flat(str(env_yaml)), "agent": yaml_flat(str(agent_yaml))}}
    disk = run / "manifest.json"
    disk.write_text(json.dumps(manifest), encoding="utf-8")
    env = SimpleNamespace(unwrapped=SimpleNamespace(_ex41_initial_dr_scale_applied=0.5,
                                                    _ex40_dr_scale=0.5))
    runtime = SimpleNamespace(scale=0.5)

    env_yaml.write_text("scene:\n  num_envs: 3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="persisted env.yaml"):
        verify_ex41_start_readback(run, plan, parent_receipt, manifest, env, runtime)
    env_yaml.write_text("scene:\n  num_envs: 2\n", encoding="utf-8")
    parent.write_bytes(b"changed parent")
    with pytest.raises(ValueError, match="parent checkpoint SHA changed"):
        verify_ex41_start_readback(run, plan, parent_receipt, manifest, env, runtime)
