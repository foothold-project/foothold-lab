"""CPU contract and known-input checks for the N21 record-only DR lane."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from foothold_s2.curriculum.ex40_dr_runtime import RuntimeReadback
from foothold_s2.eval import eval_dr_mode, n21_dr_record
from foothold_s2.eval.map_mode_cells import N21_COMMANDS


ROOT = Path(__file__).resolve().parents[2]


def _request(**changes):
    values = dict(
        dr_mode="on", dr_scale=1.0, n21_record_only=True, command_suite="n21", commands="all",
        modes="eval_gt,eval_pred,probe_prop_only", terrain_set="n21-continuous",
        fixed_terrain=True, fixed_level=2, envs=64,
        n21_point="stage_end", n21_stage="E0",
    )
    values.update(changes)
    return SimpleNamespace(**values)


def _physical_env(torch, *, changed):
    n = 2
    shift = 5.0 if changed else 0.0
    materials = torch.tensor([
        [[0.8 + shift, 0.6 + shift, 0.0], [0.9 + shift, 0.7 + shift, 0.0]],
        [[1.0 + shift, 0.5 + shift, 0.0], [1.1 + shift, 0.4 + shift, 0.0]],
    ])
    masses = torch.tensor([[10.0 + shift, 2.0], [10.5 + shift, 2.0]])
    coms = torch.zeros((n, 2, 3))
    coms[:, 0, 0] = 0.02 + shift
    view = SimpleNamespace(get_masses=lambda: masses, get_material_properties=lambda: materials,
                           get_coms=lambda: coms)
    stiffness = torch.tensor([[20.0 + shift, 21.0 + shift], [22.0 + shift, 23.0 + shift]])
    damping = torch.tensor([[1.0 + shift, 1.1 + shift], [1.2 + shift, 1.3 + shift]])
    effort = torch.tensor([[30.0 + shift, 31.0 + shift], [32.0 + shift, 33.0 + shift]])
    saturation = torch.tensor([[40.0 + shift, 41.0 + shift], [42.0 + shift, 43.0 + shift]])
    actuator = SimpleNamespace(stiffness=stiffness, damping=damping,
                               effort_limit=effort, _saturation_effort=saturation)
    actuator.joint_names = ["joint0", "joint1"]
    asset = SimpleNamespace(root_physx_view=view, actuators={"legs": actuator})
    asset.body_names = ["base", "leg"]
    action = SimpleNamespace(delay=torch.tensor([0, 2]))
    class Scene(dict):
        num_envs = n

    scene = Scene(robot=asset)
    env = SimpleNamespace(scene=scene,
                          action_manager=SimpleNamespace(get_term=lambda _name: action),
                          physics_dt=0.005)
    env._ex40_dr_com_baseline = torch.zeros((n, 2, 3))
    env._ex40_dr_motor_baselines = {"legs": {"effort_limit": torch.full((2,), 30.0),
                                               "saturation_effort": torch.full((2,), 40.0)}}
    return env


def test_n21_selector_is_exact_and_rejects_scope_drift():
    assert tuple(N21_COMMANDS) == tuple(n21_dr_record.N21_COMMANDS)
    assert len(N21_COMMANDS) == 8
    assert n21_dr_record.terrain_spec("n21-continuous")["kinds"] == list(n21_dr_record.CONTINUOUS_KINDS)
    assert len(n21_dr_record.CONTINUOUS_KINDS) == 7
    assert n21_dr_record.terrain_spec("n21-flat")["fixed_level"] == 2
    n21_dr_record.validate_request(_request())
    off_request = _request(dr_mode="off", dr_scale=0.0)
    n21_dr_record.validate_request(off_request)
    n21_dr_record.validate_entrypoint(off_request)
    for bad in (_request(dr_scale=0.8),
                _request(modes="eval_gt,eval_pred"), _request(terrain_set="sparse50"),
                _request(envs=7), _request(fixed_level=1),
                _request(n21_point="parent_e0", n21_stage="E0"),
                _request(n21_point="stage_end", n21_stage="EX42_0_T0_prime")):
        with pytest.raises(ValueError):
            n21_dr_record.validate_request(bad)
    with pytest.raises(ValueError, match="requires --n21-record-only"):
        n21_dr_record.validate_entrypoint(_request(n21_record_only=False))
    with pytest.raises(ValueError, match="--n21-record-only"):
        n21_dr_record.validate_entrypoint(_request(
            dr_mode="off", n21_record_only=False, terrain_set="n21-flat"))


def test_approval_readback_uses_real_ex42_file_and_stage_scale():
    approval = n21_dr_record.approval_record(
        n21_dr_record.DEFAULT_APPROVAL, "EX42_0_T0_prime", 1.0)
    assert approval["decision_id"] == "lead-relay-teamlead-20261106-1725-dr-1.0-fixed"
    assert len(approval["sha256"]) == 64
    assert approval["range_source"]["path"].endswith("ex41-fixed5000.yaml")
    assert approval["range_source"]["normalized_sha256"] == "92d77208d823d59fc28d2672cdeaacaa4c30a15f2e84ab0da9bac046cf2c155c"
    with pytest.raises(ValueError, match="approved parent range source"):
        n21_dr_record.approval_record(
            n21_dr_record.DEFAULT_APPROVAL, "EX42_0_T0_prime", 1.0,
            dr_table_path=n21_dr_record.DEFAULT_APPROVAL)
    with pytest.raises(ValueError, match="approved stage scale"):
        n21_dr_record.approval_record(n21_dr_record.DEFAULT_APPROVAL, "EX42_0_T0_prime", 0.8)


def test_cpu_physx_tensor_readback_preserves_actual_per_env_values():
    torch = pytest.importorskip("torch")
    off = RuntimeReadback(_physical_env(torch, changed=False), {}, 0.015)
    on = RuntimeReadback(_physical_env(torch, changed=True), {}, 0.015)
    off_values = off.per_env_actual()
    on_values = on.per_env_actual()
    assert off_values["env_ids"] == [0, 1]
    assert on_values["body_names"] == ["base", "leg"]
    assert on_values["actuator_gains_by_env_joint"]["legs"]["joint_names"] == ["joint0", "joint1"]
    assert on_values["mass_kg_by_env_body"][0][0] != off_values["mass_kg_by_env_body"][0][0]
    assert on_values["material_coefficients_by_env_shape"][0][0][0] != off_values["material_coefficients_by_env_shape"][0][0][0]
    assert on_values["base_com_offset_m_by_env_body"][0][0][0] != off_values["base_com_offset_m_by_env_body"][0][0][0]
    assert on_values["com_local_pose_by_env_body"][0][0][0] != off_values["com_local_pose_by_env_body"][0][0][0]
    assert on_values["actuator_gains_by_env_joint"]["legs"]["stiffness"][0][0] != off_values["actuator_gains_by_env_joint"]["legs"]["stiffness"][0][0]
    assert on_values["motor_strength_by_env_joint"]["legs"]["effort_multiplier"][0][0] != off_values["motor_strength_by_env_joint"]["legs"]["effort_multiplier"][0][0]
    assert on_values["delay_substeps_by_env"] == off_values["delay_substeps_by_env"] == [0, 2]
    assert on_values["delay_seconds_by_env"] == [0.0, 0.01]


def test_dr_scale_is_pinned_before_first_reset():
    table = eval_dr_mode.load_table(eval_dr_mode.DEFAULT_TABLE)
    mode = eval_dr_mode.DRMode("on", 1.0, table, eval_seed=42)
    mode._record = {"env_scale_before_first_reset": None}
    raw = SimpleNamespace()
    assert mode.after_make(raw) == 1.0
    assert raw._ex40_dr_scale == 1.0
    mode.begin(raw, "eval_gt/fwd0.5", total_steps=300, num_envs=64, dt=0.02)
    assert raw._ex40_dr_scale == mode.readback.scale == 1.0


def test_wrapper_initial_reset_happens_after_dr_hook_for_on_and_off():
    events = []

    class RawEnv:
        @property
        def unwrapped(self):
            return self

        def reset(self):
            events.append("reset")
            if mode_name[0] == "on":
                assert self._ex40_dr_scale == 1.0

    class FakeMode:
        def after_make(self, raw):
            events.append("after_make")
            if mode_name[0] == "on":
                raw._ex40_dr_scale = 1.0

    class FakeWrapper:
        def __init__(self, raw_env, *, clip_actions):
            events.append(("wrapper", clip_actions))
            self.unwrapped = raw_env.unwrapped
            raw_env.reset()

    for selected_mode in ("on", "off"):
        mode_name = [selected_mode]
        events.clear()
        raw_env = RawEnv()

        def fake_gym_make(task, *, cfg):
            assert task == "n21-task" and cfg == "cfg"
            events.append("gym_make")
            return raw_env

        wrapped, raw = eval_dr_mode.make_wrapped_env_after_dr_ready(
            fake_gym_make, FakeWrapper, "n21-task", "cfg", True, FakeMode())
        assert events == ["gym_make", "after_make", ("wrapper", True), "reset"]
        assert wrapped.unwrapped is raw is raw_env


def test_n21_separate_receipt_is_rejected_by_existing_dr_off_guard():
    completed = {
        "dr_mode": {"mode": "on", "scale": 1.0},
        "dr": {"mode": "on", "scale": 1.0}, "dr_off": [],
        "fixed_terrain": {"fixed_level": 2, "num_envs": 64},
        "modes": {mode: dict.fromkeys(N21_COMMANDS, {}) for mode in n21_dr_record.MAP_MODES},
        "n21_point": "stage_end", "n21_stage": "E0",
    }
    approval = n21_dr_record.approval_record(n21_dr_record.DEFAULT_APPROVAL, "E0", 1.0)
    doc = n21_dr_record.receipt(completed, approval=approval, terrain_set="n21-flat")
    assert doc["schema"] == n21_dr_record.N21_SCHEMA and doc["record_only"] is True
    with pytest.raises(RuntimeError, match="DR 켠 평가"):
        eval_dr_mode.require_dr_off_document(doc, where="N21 test receipt")
    incomplete = dict(completed, modes={**completed["modes"], "eval_gt": {"fwd0.5": {}}})
    with pytest.raises(ValueError, match="representative command cells"):
        n21_dr_record.receipt(incomplete, approval=approval, terrain_set="n21-flat")


def test_n21_dr_off_receipt_uses_same_schema_and_existing_consumer_accepts_it():
    disabled = ["physics_material", "add_base_mass"]
    completed = {
        "dr_mode": n21_dr_record.off_mode_record(disabled),
        "dr_off": disabled,
        "fixed_terrain": {"fixed_level": 2, "num_envs": 64},
        "envs": 64,
        "command_suite": "n21",
        "modes": {mode: dict.fromkeys(N21_COMMANDS, {}) for mode in n21_dr_record.MAP_MODES},
        "n21_point": "parent_e0", "n21_stage": "EX42_0_T0_prime",
    }
    approval = n21_dr_record.approval_record(
        n21_dr_record.DEFAULT_APPROVAL, "EX42_0_T0_prime", None)
    doc = n21_dr_record.receipt(completed, approval=approval, terrain_set="n21-flat")
    assert doc["schema"] == n21_dr_record.N21_SCHEMA
    assert doc["record_only"] is True and doc["n21_point"] == "parent_e0"
    assert "dr" not in doc
    assert doc["dr_mode"] == n21_dr_record.off_mode_record(disabled)
    assert set(doc["dr_mode"]["runtime_events_fired"].values()) == {0}
    assert eval_dr_mode.require_dr_off_document(doc, where="N21 DR-off receipt") is doc
    from foothold_s2.curriculum.ex41_scoring import maintenance_counts_from_map_modes
    with pytest.raises(ValueError, match="map64 extended"):
        maintenance_counts_from_map_modes(doc, {})


def test_n21_dr_off_runtime_is_noop_with_zero_effective_scale_and_events():
    from foothold_s2.eval.adapters import disable_eval_randomization

    events = SimpleNamespace(physics_material=object(), add_base_mass=object())
    joint_pos = SimpleNamespace(max_delay_s=0.015)
    env_cfg = SimpleNamespace(events=events, actions=SimpleNamespace(joint_pos=joint_pos))
    disabled = disable_eval_randomization(env_cfg)
    assert disabled == list(n21_dr_record.N21_DR_OFF_EVENTS)
    assert joint_pos.max_delay_s == 0.0
    args = _request(dr_mode="off", dr_scale=0.0)
    mode = eval_dr_mode.DRMode.from_args(args, env_cfg=env_cfg, capture_per_env=True)
    raw = SimpleNamespace()
    assert mode.mode == "off" and mode.scale is None and mode.table is None
    assert mode.after_make(raw) is None
    assert mode.begin(raw, "eval_gt/fwd0.5", 60, 64, 0.02) is None
    assert mode.step(raw, 0) is False
    result = {}
    assert mode.collect(raw, "eval_gt/fwd0.5", result) is None
    assert "dr" not in result
    rec = n21_dr_record.off_mode_record(disabled)
    assert rec["scale"] == 0.0
    assert set(rec["runtime_events_fired"].values()) == {0}


def test_eval_map_modes_dr_on_path_and_receipt_are_explicit_and_ordered():
    source = (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text(encoding="utf-8")
    ast.parse(source)
    assert '"--dr-mode"' not in source  # shared option definitions are owned by eval_dr_mode.add_arguments
    assert "eval_dr_mode.add_arguments(parser)" in source
    assert "n21_dr_record.validate_entrypoint(args)" in source
    assert 'n21_table_fingerprint != n21_approval["range_source"]["sha256"]' in source
    assert "DRMode.from_args(args, env_cfg, capture_per_env=parser_n21)" in source
    assert "adapters.disable_eval_randomization(env_cfg) if args.dr_mode == \"off\" else []" in source
    assert "eval_dr_mode.make_wrapped_env_after_dr_ready(" in source
    assert 'elif parser_n21:\n    res["dr_mode"] = n21_dr_record.off_mode_record(dr_off)' in source
    helper = (ROOT / "foothold_s2/eval/eval_dr_mode.py").read_text(encoding="utf-8")
    assert helper.index("raw_env = gym_make(task, cfg=env_cfg)") < helper.index("dr_mode.after_make(raw)")
    assert helper.index("dr_mode.after_make(raw)") < helper.index("env = vecenv_wrapper(")
    assert "dr_mode.begin(raw, rollout_key" in source and "dr_mode.step(raw, k)" in source
    assert "n21_record_only.json" in source
