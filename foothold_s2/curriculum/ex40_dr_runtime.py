"""Isaac Lab event adapters for the EX-40 staged domain-randomization contract.

The values are deliberately supplied by the reviewed EX-40 range table. This
module contains no guessed ranges and is imported only after Kit starts.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from foothold_s2.curriculum.ex40_dr import dr_scale, interpolate_range


def _rows(env_ids: Any, num_envs: int, device: Any):
    import torch

    if env_ids is None or isinstance(env_ids, slice):
        return torch.arange(num_envs, device=device)
    return torch.as_tensor(env_ids, dtype=torch.long, device=device).flatten()


def _scaled_interval(target: tuple[float, float], scale: float, neutral: float) -> tuple[float, float]:
    result = interpolate_range((neutral, neutral), target, scale)
    return float(result[0]), float(result[1])


def _record(env: Any, key: str, values: Any, target_envs: int | None = None) -> None:
    """Keep compact actual-sample aggregates for the next train_extra row."""
    import torch

    value = torch.as_tensor(values).detach().to(device="cpu", dtype=torch.float64).flatten()
    if value.numel() and not bool(torch.isfinite(value).all()):
        raise ValueError(f"EX-40 nonfinite realized sample: {key}")
    if not value.numel():
        return
    totals = getattr(env, "_ex40_dr_samples", None)
    if totals is None:
        totals = {}
        env._ex40_dr_samples = totals
    old = totals.get(key)
    item = {"count": int(value.numel()), "min": float(value.min()),
            "max": float(value.max()), "sum": float(value.sum()),
            "target_envs": int(target_envs if target_envs is not None else value.numel())}
    if old:
        item = {"count": old["count"] + item["count"],
                "min": min(old["min"], item["min"]),
                "max": max(old["max"], item["max"]),
                "sum": old["sum"] + item["sum"],
                "target_envs": old["target_envs"] + item["target_envs"]}
    totals[key] = item


def _stats(values: Any) -> dict:
    import torch

    value = torch.as_tensor(values).detach().to(device="cpu", dtype=torch.float64).flatten()
    if value.numel() and not bool(torch.isfinite(value).all()):
        raise ValueError("EX-40 nonfinite realized state")
    if not value.numel():
        return {"count": 0, "min": None, "max": None, "mean": None}
    return {"count": int(value.numel()), "min": float(value.min()),
            "max": float(value.max()), "mean": float(value.mean())}


def _ids_cpu(env_ids: Any, num_envs: int):
    import torch

    if env_ids is None or isinstance(env_ids, slice):
        return torch.arange(num_envs, dtype=torch.long, device="cpu")
    return torch.as_tensor(env_ids, dtype=torch.long, device="cpu").flatten()


def _require_all_joints(asset_cfg: Any, asset: Any, adapter_name: str) -> None:
    selected = asset_cfg.joint_ids
    if isinstance(selected, slice) and selected == slice(None):
        return
    if set(int(index) for index in selected) != set(range(asset.num_joints)):
        raise ValueError(f"EX-40 {adapter_name} requires a SceneEntityCfg selecting every joint")


def reset_base_com(env, env_ids, asset_cfg, target_range):
    """Restore reset rows, then call the installed Isaac Lab COM event."""
    import torch
    from isaaclab.envs.mdp import events

    asset = env.scene[asset_cfg.name]
    rows = _ids_cpu(env_ids, env.scene.num_envs)
    baseline = getattr(env, "_ex40_dr_com_baseline", None)
    current = asset.root_physx_view.get_coms().clone()
    if baseline is None:
        baseline = current.clone()
        env._ex40_dr_com_baseline = baseline
    current[rows] = baseline[rows]
    asset.root_physx_view.set_coms(current, rows)
    scale = float(getattr(env, "_ex40_dr_scale", 0.0))
    com_range = {axis: _scaled_interval(tuple(target_range[axis]), scale, 0.0)
                 for axis in ("x", "y", "z")}
    events.randomize_rigid_body_com(env, rows, com_range, asset_cfg)
    readback = asset.root_physx_view.get_coms()[rows, asset_cfg.body_ids, :3]
    _record(env, "base_com_offset_m", readback - baseline[rows, asset_cfg.body_ids, :3], len(rows))


def reset_actuator_gains(env, env_ids, asset_cfg, target_range):
    """Use the installed ManagerTermBase gain randomizer for reset rows."""
    import torch

    asset = env.scene[asset_cfg.name]
    _require_all_joints(asset_cfg, asset, "actuator-gain adapter")
    from isaaclab.envs.mdp import events
    from isaaclab.managers import EventTermCfg

    scale = float(getattr(env, "_ex40_dr_scale", 0.0))
    stiffness = _scaled_interval(tuple(target_range["stiffness_scale"]), scale, 1.0)
    damping = _scaled_interval(tuple(target_range["damping_scale"]), scale, 1.0)
    helper = getattr(env, "_ex40_dr_gain_event", None)
    if helper is None:
        helper_cfg = EventTermCfg(func=events.randomize_actuator_gains, mode="reset",
                                  params={"asset_cfg": asset_cfg, "operation": "scale"})
        helper = events.randomize_actuator_gains(helper_cfg, env)
        env._ex40_dr_gain_event = helper
    helper(env, env_ids, asset_cfg, stiffness_distribution_params=stiffness,
           damping_distribution_params=damping, operation="scale", distribution="uniform")
    rows = _rows(env_ids, env.scene.num_envs, asset.device)
    samples = []
    for actuator in asset.actuators.values():
        joints = actuator.joint_indices
        if isinstance(joints, slice):
            nominal_stiffness = asset.data.default_joint_stiffness[rows]
            nominal_damping = asset.data.default_joint_damping[rows]
        else:
            joints = joints.to(device=asset.device, dtype=torch.long)
            nominal_stiffness = asset.data.default_joint_stiffness[rows][:, joints]
            nominal_damping = asset.data.default_joint_damping[rows][:, joints]
        actual_stiffness = actuator.stiffness[rows]
        actual_damping = actuator.damping[rows]
        if bool((nominal_stiffness == 0).any()) or bool((nominal_damping == 0).any()):
            raise ValueError("EX-40 cannot measure actuator gain scale against zero nominal gain")
        samples.extend((actual_stiffness / nominal_stiffness, actual_damping / nominal_damping))
    _record(env, "actuator_gains", torch.cat([sample.reshape(-1) for sample in samples]), len(rows))


def reset_motor_strength(env, env_ids, asset_cfg, target_range):
    """Randomize DCMotor torque limits per reset row, from immutable baselines."""
    import torch
    from isaaclab.actuators import DCMotor

    asset = env.scene[asset_cfg.name]
    _require_all_joints(asset_cfg, asset, "motor-strength adapter")
    rows = _rows(env_ids, env.scene.num_envs, asset.device)
    scale = float(getattr(env, "_ex40_dr_scale", 0.0))
    low, high = _scaled_interval(tuple(target_range), scale, 1.0)
    baselines = getattr(env, "_ex40_dr_motor_baselines", None)
    if baselines is None:
        baselines = {}
        for name, actuator in asset.actuators.items():
            if not isinstance(actuator, DCMotor):
                raise TypeError(f"EX-40 motor-strength adapter requires DCMotor, got {name}:{type(actuator).__name__}")
            baselines[name] = {
                "effort_limit": actuator.effort_limit.detach().clone(),
                "saturation_effort": actuator._saturation_effort.detach().clone()
                    if torch.is_tensor(actuator._saturation_effort)
                    else torch.full_like(actuator.effort_limit, float(actuator._saturation_effort)),
            }
        env._ex40_dr_motor_baselines = baselines
    sampled = torch.empty((len(rows),), device=asset.device).uniform_(low, high)
    for name, actuator in asset.actuators.items():
        baseline = baselines[name]
        effort = baseline["effort_limit"]
        stall = baseline["saturation_effort"]
        if effort.ndim == 1:
            effort = effort.unsqueeze(0).expand(env.scene.num_envs, -1)
        if stall.ndim == 1:
            stall = stall.unsqueeze(0).expand(env.scene.num_envs, -1)
        if actuator.effort_limit.ndim == 1:
            actuator.effort_limit = effort.clone()
        if (not torch.is_tensor(actuator._saturation_effort)
                or actuator._saturation_effort.ndim == 1):
            actuator._saturation_effort = stall.clone()
        actuator.effort_limit[rows] = effort[rows] * sampled[:, None]
        actuator._saturation_effort[rows] = stall[rows] * sampled[:, None]
        actuator._vel_at_effort_lim = actuator.velocity_limit * (
            1 + actuator.effort_limit / actuator._saturation_effort)
    _record(env, "motor_strength_multiplier", sampled, len(rows))
    for actuator in asset.actuators.values():
        _record(env, "motor_effort_limit", actuator.effort_limit[rows], len(rows))
        _record(env, "motor_saturation_effort", actuator._saturation_effort[rows], len(rows))


def interval_push(env, env_ids, asset_cfg, target_range):
    """Call the installed Isaac Lab interval push and record applied velocity."""
    import torch
    from isaaclab.envs.mdp import events

    asset = env.scene[asset_cfg.name]
    if env_ids is None:
        rows = torch.arange(env.scene.num_envs, device=asset.device)
    else:
        rows = torch.as_tensor(env_ids, dtype=torch.long, device=asset.device).flatten()
    scale = float(getattr(env, "_ex40_dr_scale", 0.0))
    velocity_range = {axis: _scaled_interval(tuple(target_range.get(axis, (0.0, 0.0))), scale, 0.0)
                      for axis in ("x", "y", "z", "roll", "pitch", "yaw")}
    before = asset.root_physx_view.get_root_velocities()[rows].clone()
    events.push_by_setting_velocity(env, rows, velocity_range, asset_cfg)
    after = asset.root_physx_view.get_root_velocities()[rows].clone()
    _record(env, "push_velocity_delta", after - before, len(rows))


def install_runtime_events(env_cfg, ranges: dict, push_interval_s: tuple[float, float] | None,
                           delay_max_s: float = 0.015) -> dict:
    """Install EX-40 reset/interval terms and the delayed action before gym.make."""
    from isaaclab.managers import EventTermCfg, SceneEntityCfg
    from foothold_s2.tasks.delayed_action import DelayedJointPositionAction, DelayedJointPositionActionCfg

    missing = [key for key in ("base_com", "actuator_gains", "motor_strength", "delay_s", "push_velocity")
               if ranges.get(key) in (None, "", [], {})]
    if missing or push_interval_s in (None, "", [], {}):
        raise ValueError(f"EX-40 runtime event ranges remain incomplete: {missing + (['push_interval_s'] if push_interval_s is None else [])}")
    if not hasattr(env_cfg, "events") or env_cfg.events is None:
        raise ValueError("EX-40 env config has no event manager configuration")
    events = env_cfg.events
    robot = SceneEntityCfg("robot")
    base_body = SceneEntityCfg("robot", body_names="base")
    all_joints = SceneEntityCfg("robot", joint_names=".*")
    events.ex40_base_com = EventTermCfg(func=reset_base_com, mode="reset",
        params={"asset_cfg": base_body, "target_range": ranges["base_com"]})
    events.ex40_actuator_gains = EventTermCfg(func=reset_actuator_gains, mode="reset",
        params={"asset_cfg": all_joints, "target_range": ranges["actuator_gains"]})
    events.ex40_motor_strength = EventTermCfg(func=reset_motor_strength, mode="reset",
        params={"asset_cfg": all_joints, "target_range": ranges["motor_strength"]})
    events.ex40_push = EventTermCfg(func=interval_push, mode="interval",
        interval_range_s=tuple(push_interval_s), params={"asset_cfg": robot, "target_range": ranges["push_velocity"]})

    action = env_cfg.actions.joint_pos
    if not isinstance(action, DelayedJointPositionActionCfg):
        action = DelayedJointPositionActionCfg(
            asset_name=action.asset_name, joint_names=list(action.joint_names),
            scale=action.scale, use_default_offset=action.use_default_offset,
            offset=action.offset, clip=action.clip, preserve_order=action.preserve_order,
            debug_vis=action.debug_vis)
        env_cfg.actions.joint_pos = action
    action.max_delay_s = float(delay_max_s)
    action.dr_scale_from_env = True
    return {"reset_terms": ["ex40_base_com", "ex40_actuator_gains", "ex40_motor_strength"],
            "interval_terms": ["ex40_push"], "action": "DelayedJointPositionAction",
            "delay_max_s": float(delay_max_s)}


class RuntimeReadback:
    """Update scale hook and compact per-update realized-value receipt."""

    def __init__(self, env: Any, ranges: dict, delay_max_s: float = 0.015,
                 config_sha256: str | None = None, smoke: bool = False):
        self.env = env
        self.ranges = ranges
        self.delay_max_s = float(delay_max_s)
        self.config_sha256 = config_sha256
        self.smoke = bool(smoke)
        self.update = None
        self.schedule_update = None
        self.scale = 0.0
        self._first_update = True
        self.env._ex40_dr_scale = 0.0
        self.env._ex40_dr_samples = {}

    def update_start(self, update: int) -> None:
        from foothold_s2.curriculum.ex40_dr import smoke_schedule_update

        self.update = int(update)
        self.schedule_update = smoke_schedule_update(self.update) if self.smoke else self.update
        self.scale = dr_scale(self.schedule_update)
        self.env._ex40_dr_scale = self.scale
        if not self._first_update:
            self.env._ex40_dr_samples = {}
            action = self.env.action_manager.get_term("joint_pos")
            if hasattr(action, "_ex40_sample_counts"):
                action._ex40_sample_counts = None
        self._first_update = False

    def summary(self) -> dict:
        import torch

        samples = getattr(self.env, "_ex40_dr_samples", {})
        expected_sample_keys = ("base_com_offset_m", "actuator_gains", "motor_strength_multiplier",
                                "motor_effort_limit", "motor_saturation_effort", "push_velocity_delta")
        summary = {key: {"count": 0, "min": None, "max": None, "mean": None,
                         "target_envs": 0}
                   for key in expected_sample_keys}
        for key, values in samples.items():
            summary[key] = {"count": values["count"], "min": values["min"],
                            "max": values["max"], "mean": values["sum"] / values["count"],
                            "target_envs": values["target_envs"]}
        asset = self.env.scene["robot"]
        realized = {}
        com_baseline = getattr(self.env, "_ex40_dr_com_baseline", None)
        if com_baseline is not None:
            com = asset.root_physx_view.get_coms()
            realized["base_com_offset_m"] = _stats(com[..., :3] - com_baseline[..., :3])
        for name, actuator in asset.actuators.items():
            realized[f"{name}.stiffness"] = _stats(actuator.stiffness)
            realized[f"{name}.damping"] = _stats(actuator.damping)
            if hasattr(actuator, "effort_limit"):
                realized[f"{name}.effort_limit"] = _stats(actuator.effort_limit)
            if hasattr(actuator, "_saturation_effort"):
                realized[f"{name}.saturation_effort"] = _stats(actuator._saturation_effort)
        action = self.env.action_manager.get_term("joint_pos")
        delay = getattr(action, "delay", None)
        delay_summary = None
        if delay is not None:
            d = delay.detach().to(device="cpu", dtype=torch.int64)
            current_hist = torch.bincount(d, minlength=int(d.max().item()) + 1 if d.numel() else 1)
            dt = float(self.env.physics_dt)
            scheduled_max_substeps = int(math.floor(self.delay_max_s * self.scale / dt + 1e-9))
            reset_hist = getattr(action, "_ex40_sample_counts", None)
            if reset_hist is None:
                reset_hist = torch.zeros(scheduled_max_substeps + 1, dtype=torch.int64)
            else:
                reset_hist = reset_hist.detach().to(device="cpu", dtype=torch.int64)
            used = torch.nonzero(current_hist).flatten()
            realized_max = int(used.max()) if used.numel() else None
            delay_summary = {"count": int(d.numel()),
                             "reset_sample_count": int(reset_hist.sum()),
                             "observed_min_substeps": int(used.min()) if used.numel() else None,
                             "observed_max_substeps": realized_max,
                             "max_allowed_substeps": scheduled_max_substeps,
                             "current_histogram": current_hist.tolist(),
                             "reset_sample_histogram": reset_hist.tolist(),
                             "max_seconds": self.delay_max_s * self.scale,
                             "configured_max_seconds": self.delay_max_s * self.scale,
                             "observed_max_seconds": realized_max * dt if realized_max is not None else None,
                             "reset_sampled_delay_ms": [index * dt * 1000
                                 for index, count in enumerate(reset_hist.tolist()) if count],
                             "physics_dt_seconds": dt}
            realized["delay_substeps"] = _stats(d)
        self.env._ex40_dr_samples = {}
        return {"update": self.update, "schedule_update": self.schedule_update,
                "smoke_schedule": self.smoke, "scale": self.scale,
                "config_sha256": self.config_sha256,
                "target_ranges": {"base_com": self.ranges.get("base_com"),
                    "actuator_gains": self.ranges.get("actuator_gains"),
                    "motor_strength": self.ranges.get("motor_strength"),
                    "push_velocity": self.ranges.get("push_velocity"),
                    "delay_max_seconds": self.delay_max_s * self.scale},
                "actual_samples": summary, "realized_state": realized,
                "delay_readback": delay_summary,
                "observation_noise": {"mode": "fixed", "multiplier": 1.0},
                "pending_values": [name for name in ("push_velocity",)
                                   if self.ranges.get(name) is None]}

    def state_dict(self) -> dict:
        def cpu_state(value):
            if value is None:
                return None
            if isinstance(value, dict):
                return {key: cpu_state(item) for key, item in value.items()}
            return value.detach().to(device="cpu").clone()

        return {"format": "ex40-dr-runtime-readback/1", "config_sha256": self.config_sha256,
                "last_update": self.update, "schedule_update": self.schedule_update,
                "smoke_schedule": self.smoke, "scale": self.scale,
                "com_baseline": cpu_state(getattr(self.env, "_ex40_dr_com_baseline", None)),
                "motor_baselines": cpu_state(getattr(self.env, "_ex40_dr_motor_baselines", None))}

    def load_state_dict(self, state: dict, next_update: int) -> None:
        if not isinstance(state, dict):
            raise ValueError("EX-40 DR runtime state does not match checkpoint/config/next update")
        last_update = state.get("last_update")
        from foothold_s2.curriculum.ex40_dr import smoke_schedule_update
        saved_smoke = state.get("smoke_schedule", False)
        expected_schedule_update = (smoke_schedule_update(last_update)
                                    if saved_smoke and type(last_update) is int else last_update)
        initial_state = last_update is None and next_update in (0, 1) and state.get("scale") == 0.0
        continued_state = (type(last_update) is int and last_update >= 0
                           and last_update + 1 == next_update
                           and state.get("schedule_update") == expected_schedule_update
                           and state.get("scale") == dr_scale(expected_schedule_update))
        if (not isinstance(state, dict) or state.get("format") != "ex40-dr-runtime-readback/1"
                or state.get("config_sha256") != self.config_sha256
                or bool(saved_smoke) != self.smoke
                or (initial_state and state.get("schedule_update") is not None)
                or not (initial_state or continued_state)):
            raise ValueError("EX-40 DR runtime state does not match checkpoint/config/next update")
        self.update = last_update
        self.scale = float(state["scale"])
        self.env._ex40_dr_scale = self.scale
        import torch

        device = getattr(self.env, "device",
                         getattr(getattr(self.env, "scene", None), "device", "cpu"))
        com_baseline = state.get("com_baseline")
        if com_baseline is not None:
            self.env._ex40_dr_com_baseline = torch.as_tensor(com_baseline).to(device=device).clone()
        motor_baselines = state.get("motor_baselines")
        if motor_baselines is not None:
            self.env._ex40_dr_motor_baselines = {
                name: {key: torch.as_tensor(value).to(device=device).clone()
                       for key, value in values.items()}
                for name, values in motor_baselines.items()}


def validate_runtime_summary(row: dict, expected_update: int | None = None,
                             require_event_samples: bool = False,
                             ranges: dict | None = None) -> None:
    """Validate one Kit-produced train_extra receipt row, not a config mock."""
    from foothold_s2.curriculum.ex40_dr import dr_scale, smoke_schedule_update
    import yaml

    if ranges is None:
        ranges = yaml.safe_load((Path(__file__).with_name("ex40.yaml")).read_text(
            encoding="utf-8"))["domain_randomization"]["full_ranges"]

    receipt = row.get("ex40_dr") if isinstance(row, dict) else None
    if not isinstance(receipt, dict):
        raise ValueError("EX-40 DR train_extra readback missing")
    update = receipt.get("update")
    if type(update) is not int or (expected_update is not None and update != expected_update):
        raise ValueError("EX-40 DR readback update index mismatch")
    schedule_update = receipt.get("schedule_update", update)
    if receipt.get("smoke_schedule", False):
        if schedule_update != smoke_schedule_update(update):
            raise ValueError("EX-40 smoke schedule update differs from compressed stage mapping")
    elif schedule_update != update:
        raise ValueError("EX-40 production schedule update differs from train update")
    expected = dr_scale(schedule_update)
    if not math.isclose(float(receipt.get("scale", -1)), expected, abs_tol=1e-12):
        raise ValueError("EX-40 DR readback scale differs from schedule")
    if receipt.get("observation_noise") != {"mode": "fixed", "multiplier": 1.0}:
        raise ValueError("EX-40 observation noise must remain fixed at 1x")
    actual_samples = receipt.get("actual_samples")
    required_sample_keys = ("base_com_offset_m", "actuator_gains", "motor_strength_multiplier",
                            "motor_effort_limit", "motor_saturation_effort", "push_velocity_delta")
    if not isinstance(actual_samples, dict) or any(
            not isinstance(actual_samples.get(key), dict)
            or type(actual_samples[key].get("count")) is not int
            or actual_samples[key]["count"] < 0 for key in required_sample_keys):
        raise ValueError("EX-40 per-update DR event sample counters missing or malformed")
    if any(type(actual_samples[key].get("target_envs")) is not int
           or actual_samples[key]["target_envs"] < 0
           or actual_samples[key]["target_envs"] > actual_samples[key]["count"]
           for key in required_sample_keys):
        raise ValueError("EX-40 DR event target environment counts missing or invalid")
    if require_event_samples and any(actual_samples[key]["count"] <= 0 for key in required_sample_keys):
        raise ValueError("EX-40 reset/interval event did not produce actual samples")
    delay = receipt.get("delay_readback")
    if not isinstance(delay, dict) or delay.get("count", 0) <= 0:
        raise ValueError("EX-40 DR delayed-action reset readback missing")
    dt = float(delay.get("physics_dt_seconds", 0))
    if dt <= 0 or not math.isclose(float(delay.get("max_seconds", -1)), expected * 0.015, abs_tol=1e-12):
        raise ValueError("EX-40 DR delay scale or physics dt invalid")
    max_steps = int(math.floor(expected * 0.015 / dt + 1e-9))
    if (delay.get("max_allowed_substeps") != max_steps
            or (delay.get("observed_max_substeps") or 0) > max_steps):
        raise ValueError("EX-40 DR delay sampled values exceed the scaled schedule")
    if (not math.isclose(float(delay.get("configured_max_seconds", -1)), expected * 0.015, abs_tol=1e-12)
            or (delay.get("observed_max_seconds") is not None
                and not math.isclose(float(delay["observed_max_seconds"]),
                                     float(delay["observed_max_substeps"]) * dt, abs_tol=1e-12))):
        raise ValueError("EX-40 configured delay cap and realized sample readback disagree")
    realized = receipt.get("realized_state")
    if not isinstance(realized, dict) or not realized:
        raise ValueError("EX-40 DR actual per-update state readback missing")
    for key in ("base_com_offset_m", "delay_substeps"):
        state = realized.get(key)
        if not isinstance(state, dict) or type(state.get("count")) is not int or state["count"] <= 0:
            raise ValueError(f"EX-40 DR realized state readback missing: {key}")
    for suffix in (".stiffness", ".damping", ".effort_limit", ".saturation_effort"):
        states = [value for key, value in realized.items() if key.endswith(suffix)]
        if not states or any(not isinstance(value, dict) or value.get("count", 0) <= 0
                             for value in states):
            raise ValueError(f"EX-40 DR actuator readback missing: {suffix}")
    if delay.get("count") <= 0 or delay.get("reset_sample_count", 0) < 0:
        raise ValueError("EX-40 DR delayed-action current/reset readback missing")
    histogram = delay.get("current_histogram")
    reset_histogram = delay.get("reset_sample_histogram")
    if (not isinstance(histogram, list) or not histogram or sum(histogram) != delay["count"]
            or not isinstance(reset_histogram, list) or sum(reset_histogram) != delay["reset_sample_count"]
            or any(type(value) is not int or value < 0 for value in histogram + reset_histogram)
            or len(histogram) > max_steps + 1 or len(reset_histogram) > max_steps + 1):
        raise ValueError("EX-40 DR delay histogram does not match actual reset samples")
    pending = receipt.get("pending_values", [])
    if not isinstance(pending, list) or pending:
        raise ValueError("EX-40 pending DR range values remain unresolved")

    expected_target_ranges = {"base_com": ranges["base_com"],
        "actuator_gains": ranges["actuator_gains"],
        "motor_strength": ranges["motor_strength"],
        "push_velocity": ranges["push_velocity"],
        "delay_max_seconds": float(ranges.get("delay_s", [0.0, 0.015])[1]) * expected}
    if receipt.get("target_ranges") != expected_target_ranges:
        raise ValueError("EX-40 DR nominal targets or scale differ from configured ranges")

    def finite_stats(stats: dict, name: str) -> tuple[float, float, float]:
        if not isinstance(stats, dict) or type(stats.get("count")) is not int or stats["count"] <= 0:
            raise ValueError(f"EX-40 DR sample statistics missing: {name}")
        values = []
        for field in ("min", "max", "mean"):
            value = stats.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                raise ValueError(f"EX-40 DR sample statistics nonfinite: {name}.{field}")
            values.append(float(value))
        if values[0] > values[1] or not values[0] - 1e-9 <= values[2] <= values[1] + 1e-9:
            raise ValueError(f"EX-40 DR sample statistics inconsistent: {name}")
        return tuple(values)

    def within(stats: dict, bounds: tuple[float, float], name: str) -> None:
        low, high, _ = finite_stats(stats, name)
        if low < bounds[0] - 1e-6 or high > bounds[1] + 1e-6:
            raise ValueError(f"EX-40 DR realized samples exceed target range: {name}")

    def scaled(pair, neutral):
        return _scaled_interval(tuple(float(v) for v in pair), expected, neutral)

    sample_bounds = {
        "base_com_offset_m": (min(scaled(ranges["base_com"][axis], 0.0)[0]
                                   for axis in ("x", "y", "z")),
                              max(scaled(ranges["base_com"][axis], 0.0)[1]
                                   for axis in ("x", "y", "z"))),
        "actuator_gains": (min(scaled(ranges["actuator_gains"][key], 1.0)[0]
                                for key in ("stiffness_scale", "damping_scale")),
                           max(scaled(ranges["actuator_gains"][key], 1.0)[1]
                                for key in ("stiffness_scale", "damping_scale"))),
        "motor_strength_multiplier": scaled(ranges["motor_strength"], 1.0),
        "push_velocity_delta": (min(scaled(pair, 0.0)[0] for pair in ranges["push_velocity"].values()),
                                max(scaled(pair, 0.0)[1] for pair in ranges["push_velocity"].values())),
    }
    for key, bounds in sample_bounds.items():
        stats = actual_samples[key]
        if stats["count"]:
            within(stats, bounds, f"actual_samples.{key}")
    full_com = (min(float(v[0]) for v in ranges["base_com"].values()),
                max(float(v[1]) for v in ranges["base_com"].values()))
    within(realized["base_com_offset_m"], full_com, "realized_state.base_com_offset_m")
    for key, stats in realized.items():
        if key.endswith((".stiffness", ".damping", ".effort_limit", ".saturation_effort")):
            low, _, _ = finite_stats(stats, f"realized_state.{key}")
            if low <= 0:
                raise ValueError(f"EX-40 DR actuator readback must be positive: {key}")
