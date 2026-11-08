"""SOL-24i guarded-render copy of the SOL-24g measurement recorder.

This file is a new project-owned recorder. It does not edit the training runner,
task definitions, shared s2_lab files, or the existing seq_video validator.
The policy argument is a JSON object so the fixed seq_video positional contract
can carry the native task and terrain selection without a legacy repo path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any


COMMANDS = (
    ("forward_05", (0.5, 0.0, 0.0), 3.0),
    ("forward_10", (1.0, 0.0, 0.0), 3.0),
    ("yaw_left", (0.0, 0.0, 1.2), 3.0),
    ("yaw_right", (0.0, 0.0, -1.2), 3.0),
)
TOPDOWN_KINDS = {
    "stepping_stones_low", "flat", "stepping_stones_high",
    "balance_beams", "stepping_beams", "gaps",
}
HEIGHT_MAP_SHAPE = (32, 16)
HEIGHT_SCALE_M = (-1.0, 1.0)
DEPTH_SCALE_M = (0.0, 6.0)
LONG_COMMAND_RESAMPLE_S = 1.0e9
BASE_RECORDER_SHA256 = "662cd68906bdf99301830ef149e77c11a5d4b849c0938f0fcb7584fb0913afd6"
MEASUREMENT_RECORDER_SHA256 = "12547e29e15e0c9b1c0eb05cf1d460218292249b0750ec00eb73cfc906147ca0"


def _render_state(raw: Any, robot: Any, command_term: Any, sensor: Any) -> dict[str, Any]:
    """Read actual simulation, articulation, command and contact-clock state."""
    import numpy as np

    def values(value: Any) -> Any:
        if hasattr(value, "detach"):
            value = value.detach().cpu()
        return np.asarray(value).tolist()

    command = getattr(command_term, "commands", None)
    if command is None:
        command = command_term.vel_command_b
    return {
        "sim_time_s": float(raw.sim.current_time),
        "env_step": int(raw.common_step_counter),
        "root_pos_w": values(robot.data.root_pos_w[0]),
        "root_quat_w": values(robot.data.root_quat_w[0]),
        "root_lin_vel_b": values(robot.data.root_lin_vel_b[0]),
        "root_ang_vel_b": values(robot.data.root_ang_vel_b[0]),
        "command": values(command[0, :3]),
        "contact_timestamp": values(sensor._timestamp),
        "contact_timestamp_last_update": values(sensor._timestamp_last_update),
    }


def render_frame_guarded(raw: Any, robot: Any, command_term: Any, sensor: Any,
                         *, dark_threshold: float = 10.0,
                         max_retries: int = 30) -> tuple[Any, list[dict[str, Any]]]:
    """Retry RGB with the simulation render guard, never advancing the episode."""
    import numpy as np

    if max_retries < 0:
        raise ValueError("max_retries must be nonnegative")
    checks: list[dict[str, Any]] = []
    before = _render_state(raw, robot, command_term, sensor)
    frame = np.ascontiguousarray(raw.render())[..., :3]
    after = _render_state(raw, robot, command_term, sensor)
    if after != before:
        changed = [key for key in before if before[key] != after[key]]
        raise RuntimeError("render_state_changed " + json.dumps(
            {"phase": "initial", "changed": changed, "before": before, "after": after},
            allow_nan=False))
    brightness = float(frame.astype(np.float32).mean())
    for retry in range(1, max_retries + 1):
        if brightness > dark_threshold:
            break
        before = _render_state(raw, robot, command_term, sensor)
        raw.sim.render()
        frame = np.ascontiguousarray(raw.render(recompute=True))[..., :3]
        after = _render_state(raw, robot, command_term, sensor)
        brightness = float(frame.astype(np.float32).mean())
        record = {"retry": retry, "before": before, "after": after,
                  "mean_brightness": brightness}
        checks.append(record)
        if after != before:
            record["changed"] = [key for key in before if before[key] != after[key]]
            raise RuntimeError("render_state_changed " + json.dumps(record, allow_nan=False))
    if brightness <= dark_threshold:
        raise RuntimeError("render_still_dark " + json.dumps(
            {"mean_brightness": brightness, "retry_count": len(checks),
             "last_check": checks[-1] if checks else None}, allow_nan=False))
    return frame, checks


def configure_topdown_evaluation(env_cfg: Any, augmentation: Any) -> None:
    """Keep generator layout semantics while pinning evaluation terrain and augmentation."""
    env_cfg.scene.terrain.terrain_generator.curriculum = True
    env_cfg.curriculum.terrain_levels = None
    augmentation.enabled = False


def preload_kit_dependencies(import_module: Any, load_kit: Any) -> Any:
    """Load tensordict before Kit to avoid the known import-order access violation."""
    import_module("tensordict")
    return load_kit()


def pin_segment_command(env_cfg: Any, command_term: Any,
                        command: tuple[float, float, float]) -> None:
    """Pin reset/resample config and the live command to the active segment."""
    for cfg in (env_cfg, getattr(command_term, "cfg", None)):
        if cfg is not None:
            cfg.fixed_cmd = tuple(float(x) for x in command)
            cfg.resampling_time_range = (LONG_COMMAND_RESAMPLE_S, LONG_COMMAND_RESAMPLE_S)
    tensor = getattr(command_term, "commands", None)
    if tensor is None:
        tensor = command_term.vel_command_b
    try:
        import torch
        value = torch.as_tensor(command, dtype=tensor.dtype, device=tensor.device).reshape(1, 3)
    except (ImportError, AttributeError, TypeError):
        value = command
    tensor[:, :3] = value


def configure_physics_mode(env_cfg: Any, mode: str) -> dict[str, Any]:
    """Pin deterministic baseline physics or retain task training randomization."""
    if mode not in ("fixed", "training"):
        raise ValueError("physics_mode must be fixed or training")
    if mode == "fixed":
        events = getattr(env_cfg, "events", None)
        if events is not None:
            for name in ("add_base_mass", "base_com", "actuator_gains", "motor_strength",
                         "push_robot", "base_external_force_torque"):
                if hasattr(events, name):
                    setattr(events, name, None)
            material = getattr(events, "physics_material", None)
            params = getattr(material, "params", None)
            if params is not None:
                for key, value in (("static_friction_range", (0.8, 0.8)),
                                   ("dynamic_friction_range", (0.6, 0.6)),
                                   ("restitution_range", (0.0, 0.0))):
                    if key in params:
                        params[key] = value
        actions = getattr(env_cfg, "actions", None)
        joint_pos = getattr(actions, "joint_pos", None) if actions is not None else None
        if joint_pos is not None and hasattr(joint_pos, "max_delay_s"):
            joint_pos.max_delay_s = 0.0
        reset = getattr(events, "reset_robot_joints", None) if events is not None else None
        params = getattr(reset, "params", None)
        if params is not None:
            if "position_range" in params:
                params["position_range"] = (1.0, 1.0)
            if "velocity_range" in params:
                params["velocity_range"] = (0.0, 0.0)
        reset_base = getattr(events, "reset_base", None) if events is not None else None
        base_params = getattr(reset_base, "params", None)
        if base_params is not None:
            for key in ("pose_range", "velocity_range"):
                ranges = base_params.get(key)
                if isinstance(ranges, dict):
                    base_params[key] = {axis: (0.0, 0.0) for axis in ranges}
    return {"mode": mode, "applied_config": _plain_config(env_cfg)}


def _plain_config(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _plain_config(v) for k, v in value.items()}
    if hasattr(value, "detach") and hasattr(value, "cpu"):
        return _plain_config(value.detach().cpu().tolist())
    if hasattr(value, "tolist"):
        return _plain_config(value.tolist())
    if isinstance(value, (list, tuple)):
        return [_plain_config(v) for v in value]
    if hasattr(value, "__dict__"):
        return {str(k): _plain_config(v) for k, v in vars(value).items()
                if not str(k).startswith("_") and not callable(v)}
    return repr(value)


def physics_actual_readback(raw: Any) -> dict[str, Any]:
    """Record live simulator values when the runtime exposes them."""
    robot = raw.scene["robot"]
    data = getattr(robot, "data", None)
    view = getattr(robot, "root_physx_view", None)
    result: dict[str, Any] = {}
    for key, owners, attrs in (
        ("mass", (view, data), ("get_masses", "root_mass_w", "default_mass")),
        ("com", (view, data), ("get_coms", "root_com_pos_b", "default_com")),
        ("material", (view, data), ("get_material_properties", "default_material_properties")),
        ("stiffness", tuple(getattr(robot, "actuators", {}).values()) + (data,), ("stiffness", "default_joint_stiffness")),
        ("damping", tuple(getattr(robot, "actuators", {}).values()) + (data,), ("damping", "default_joint_damping")),
    ):
        found = None
        for owner in owners:
            if owner is None:
                continue
            for attr in attrs:
                candidate = getattr(owner, attr, None)
                if callable(candidate):
                    try:
                        candidate = candidate()
                    except Exception:
                        continue
                if candidate is not None:
                    found = _plain_config(candidate)
                    break
            if found is not None:
                break
        result[key] = found if found is not None else "unavailable"
    return result


def height_map_display(depth: Any, gt: Any, rough: Any, refined: Any) -> dict[str, Any]:
    """Return display planes with aligned height-map scale and separate depth scale."""
    import numpy as np
    depth_plane = np.asarray(depth, dtype=np.float32).squeeze()
    if depth_plane.shape != (60, 60):
        raise ValueError(f"depth image must be 60x60, got {depth_plane.shape}")
    result: dict[str, Any] = {"depth": depth_plane, "depth_scale": list(DEPTH_SCALE_M),
                              "height_scale_m": list(HEIGHT_SCALE_M)}
    for name, values in (("gt", gt), ("rough", rough), ("refined", refined)):
        plane = np.asarray(values, dtype=np.float32).squeeze()
        if plane.size != HEIGHT_MAP_SHAPE[0] * HEIGHT_MAP_SHAPE[1]:
            raise ValueError(f"{name} height map must contain 512 values")
        result[name] = plane.reshape(HEIGHT_MAP_SHAPE)
    return result


def exit_after_flush(code: int, stdout: Any = sys.stdout, stderr: Any = sys.stderr,
                     exit_fn: Any = os._exit) -> None:
    stdout.flush()
    stderr.flush()
    exit_fn(int(code))


def parse_spec(value: str) -> dict[str, Any]:
    try:
        spec = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("--policy must be a JSON object for record_sol23f") from exc
    if not isinstance(spec, dict):
        raise ValueError("policy spec must be an object")
    root = spec.get("source_root")
    if not isinstance(root, str) or not Path(root).is_absolute():
        raise ValueError("source_root must name the absolute fixed-code worktree")
    experiment = spec.get("experiment")
    if experiment not in ("B", "TD"):
        raise ValueError("experiment must be B or TD")
    spec.setdefault("seed", 42)
    spec.setdefault("map_mode", "saved")
    spec.setdefault("z_mode", "mean")
    spec.setdefault("act_mode", "mean")
    spec.setdefault("physics_mode", "fixed")
    if type(spec["seed"]) is not int:
        raise ValueError("seed must be an integer")
    if spec["map_mode"] not in ("saved", "pred", "gt"):
        raise ValueError("map_mode must be saved, pred, or gt")
    if spec["physics_mode"] not in ("fixed", "training"):
        raise ValueError("physics_mode must be fixed or training")
    if spec["z_mode"] != "mean" or spec["act_mode"] != "mean":
        raise ValueError("fixed evaluation requires mean latent and mean action")
    if experiment == "B":
        if spec.get("terrain", "rough") not in ("flat", "rough"):
            raise ValueError("B terrain must be flat or rough")
        spec.setdefault("terrain", "rough")
    else:
        if spec.get("terrain_type") not in TOPDOWN_KINDS:
            raise ValueError("TD terrain_type must be a registered native sparse type")
        if type(spec.get("level")) is not int or not 0 <= spec["level"] <= 9:
            raise ValueError("TD level must be an integer from 0 through 9")
    return spec


def validate_source_root(root: Path) -> None:
    source = root / "foothold_s2/eval/record_sol23f.py"
    if not source.is_file() or _sha(source) != BASE_RECORDER_SHA256:
        raise ValueError("fixed SOL-23f recorder source SHA mismatch")


def body_height_from_contact_feet(root_z: Any, foot_z: Any, contact: Any) -> float:
    """Root to contacting foot-center distance; NaN when no foot contacts."""
    import numpy as np
    feet = np.asarray(foot_z, dtype=np.float64)
    mask = np.asarray(contact, dtype=np.bool_)
    if feet.shape != (4,) or mask.shape != (4,):
        raise ValueError("four aligned foot positions and contacts required")
    return float(root_z - feet[mask].mean()) if mask.any() else float("nan")


def measurement_arrays(data: dict[str, list[Any]], foot_names: Any,
                       joint_names: Any, expected_steps: int) -> dict[str, Any]:
    """Close the extra NPZ contract before the parent can publish its receipt."""
    import numpy as np
    joints = len(joint_names)
    arrays = {
        "root_pos_w": np.asarray(data["root_pos_w"]),
        "root_quat_w": np.asarray(data["root_quat_w"]),
        "foot_pos_w": np.asarray(data["foot_xyz"]),
        "body_height_foot_center_m": np.asarray(data["body_height_foot_center_m"]),
        "policy_action": np.asarray(data["policy_action"]),
        "joint_pos_target_last_substep": np.asarray(data["joint_pos_target_last_substep"]),
        "applied_torque_last_substep": np.asarray(data["applied_torque_last_substep"]),
        "joint_target_valid": np.asarray(data["joint_target_valid"], dtype=np.bool_),
        "foot_names": np.asarray(foot_names),
        "joint_names": np.asarray(joint_names),
    }
    shapes = {"root_pos_w": (expected_steps, 3), "root_quat_w": (expected_steps, 4),
              "foot_pos_w": (expected_steps, 4, 3),
              "body_height_foot_center_m": (expected_steps,),
              "joint_pos_target_last_substep": (expected_steps, joints),
              "applied_torque_last_substep": (expected_steps, joints),
              "joint_target_valid": (expected_steps,), "foot_names": (4,),
              "joint_names": (joints,)}
    for key, shape in shapes.items():
        if arrays[key].shape != shape:
            raise ValueError(f"measurement {key} shape {arrays[key].shape} != {shape}")
    if arrays["policy_action"].ndim != 2 or arrays["policy_action"].shape[0] != expected_steps:
        raise ValueError("measurement policy_action shape mismatch")
    if not np.array_equal(arrays["joint_target_valid"], ~np.asarray(data["done"], dtype=np.bool_)):
        raise ValueError("joint target validity must exclude terminal reset rows")
    return arrays


def apply_map_mode(policy: Any, mode: str, map_input: str, saved_force_gt: bool,
                   tensor_ops: Any | None = None) -> dict[str, Any]:
    """Set inference and reset masks together; tensor_ops keeps this CPU-testable."""
    if mode not in ("saved", "pred", "gt"):
        raise ValueError("unknown map mode")
    if mode != "saved" and map_input == "none":
        raise ValueError("pred/gt map diagnostics require a reconstruction map input")
    if tensor_ops is None:
        import torch as tensor_ops
    use_gt = bool(saved_force_gt) if mode == "saved" else mode == "gt"
    policy.pstate.use_gt[...] = tensor_ops.full_like(policy.pstate.use_gt, use_gt)
    policy.no_gt = tensor_ops.full_like(policy.pstate.use_gt, use_gt)
    if not bool((policy.pstate.use_gt == use_gt).all()) or not bool((policy.no_gt == use_gt).all()):
        raise RuntimeError("map mode failed to initialize inference and reset flags")
    return {"requested": mode, "effective_use_gt": use_gt,
            "saved_force_gt": bool(saved_force_gt), "map_input": map_input}


def assert_map_mode(policy: Any, expected: bool) -> None:
    if not bool((policy.pstate.use_gt == expected).all()):
        raise RuntimeError("map use_gt flag changed across initial/reset boundary")


def validate_depth_delay(experiment: str, ticks: int) -> dict[str, Any]:
    if experiment == "TD" and ticks != 0:
        raise ValueError("START-TopDown requires checkpoint depth_delay_ticks=0")
    return {"depth_delay_ticks": ticks,
            "contract": "native TopDown zero-delay" if experiment == "TD" else "checkpoint/config value"}


def frame_steps(step_count: int, frame_count: int = 300) -> list[int]:
    if step_count <= 0 or frame_count <= 0:
        raise ValueError("step and frame counts must be positive")
    indices = [round(i * (step_count - 1) / (frame_count - 1)) for i in range(frame_count)]
    if len(set(indices)) != frame_count:
        raise ValueError("physics step rate cannot provide the requested distinct video frames")
    return indices


def step_contract(dt: float, duration_s: float = 12.0, fps: int = 25) -> dict[str, Any]:
    steps = int(round(duration_s / dt))
    indices = frame_steps(steps, int(round(duration_s * fps)))
    return {
        "duration_s": duration_s, "physics_dt_s": dt, "physics_steps": steps,
        "video_fps": fps, "video_frames": len(indices), "video_sample_step_indices": indices,
        "commands": [{"name": name, "target": list(cmd), "start_s": i * 3.0, "duration_s": span}
                     for i, (name, cmd, span) in enumerate(COMMANDS)],
        "policy_modes": {"latent": "mean", "action": "mean"},
    }


def termination_record(dones: Any, terms: dict[str, bool] | None,
                       timed_out: bool = False) -> dict[str, Any]:
    done = bool(dones)
    names = sorted(name for name, active in (terms or {}).items() if active)
    if not done:
        reason = "none"
    elif timed_out:
        reason = "time_out"
    elif names:
        reason = "termination_terms"
    else:
        reason = "terminated_unclassified"
    return {"done": done, "time_out": bool(timed_out), "reason": reason,
            "active_terms": names, "classification": "not_a_fall_judgment"}


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_atomic(path: Path, value: dict[str, Any]) -> None:
    temp = path.with_name(path.name + ".publishing")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, path)


def _argv_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", required=True, help="JSON experiment/task/map-mode spec")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--scene", choices=("flat", "rough"), required=True)
    parser.add_argument("--mp4", required=True)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--fps", type=int, default=25)
    parser.add_argument("--physics-mode", choices=("fixed", "training"))
    parser.add_argument("--plan-only", action="store_true", help="print CPU plan without importing Kit")
    return parser


def _source_hashes(repo: Path, experiment: str) -> dict[str, str]:
    files = ["foothold_s2/eval/record_sol23f.py", "foothold_s2/eval/adapters.py",
             "foothold_s2/eval/seq_video.py", "foothold_s2/eval/runtime.py",
             "foothold_s2/runners/start_runner.py", "foothold_s2/models/start_perception.py",
             "foothold_s2/x23f_tasks.py"]
    files += (["foothold_s2/tasks/s2_23f_b_cfg.py", "foothold_s2/tasks/s2_x23_cfg.py"]
              if experiment == "B" else ["foothold_s2/tasks/s2_23f_topdown_cfg.py",
                                          "foothold_s2/tasks/s2_23f_topdown_env.py",
                                          "foothold_s2/terrains/sol23f_topdown.py",
                                          "foothold_s2/terrains/s2_layout.py"])
    return {name: _sha(repo / name) for name in files}


def _configure_topdown(raw: Any, kind: str, level: int, seed: int) -> dict[str, Any]:
    from foothold_s2.terrains import sol23f_topdown
    from foothold_s2.terrains.s2_layout import Layout

    terrain = raw.scene.terrain
    layout = Layout(sol23f_topdown.PROPORTIONS, sol23f_topdown.NUM_COLS)
    matches = [i for i, name in enumerate(layout.names) if name == kind]
    if not matches:
        raise ValueError("requested TopDown type is absent from generated native layout")
    col = matches[0]
    terrain.terrain_levels[:] = level
    terrain.terrain_types[:] = col
    origins = terrain.terrain_origins[terrain.terrain_levels, terrain.terrain_types]
    terrain.env_origins[:] = origins
    raw.scene.env_origins[:] = origins
    terrain_generator = getattr(raw.cfg.scene.terrain, "terrain_generator", None)
    if terrain_generator is not None:
        terrain_generator.seed = seed
    if int(terrain.terrain_levels[0]) != level or int(terrain.terrain_types[0]) != col:
        raise RuntimeError("native TopDown selection did not stick")
    return {"terrain_type": kind, "terrain_type_index": col, "level": level,
            "seed": seed, "selection": "native generated side table and terrain origins"}


def _capture(spec: dict[str, Any]) -> None:
    import numpy as np
    import torch
    import av
    from PIL import Image, ImageDraw, ImageFont

    import importlib
    preload_kit_dependencies(importlib.import_module, lambda: None)
    from isaaclab.app import AppLauncher
    parser = _argv_parser()
    AppLauncher.add_app_launcher_args(parser)
    # Reparse the original argv with launcher options, but only after plan-only was ruled out.
    full_args = parser.parse_args()
    full_args.enable_cameras = True
    _app = AppLauncher(full_args).app
    repo = Path(spec["source_root"]).resolve()
    validate_source_root(repo)
    sys.path.insert(0, str(repo))
    env = None
    container = None
    try:
        import gymnasium as gym
        importlib.import_module("isaaclab_tasks")
        from isaaclab_tasks.utils import load_cfg_from_registry
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        importlib.import_module("foothold_s2.x23f_tasks")
        from foothold_s2.eval import adapters, terrain_sets

        task_id = ("FootholdS2-Go2-S2-23f-B-v0" if spec["experiment"] == "B"
                   else "FootholdS2-Go2-S2-23f-TopDown-v0")
        env_cfg = load_cfg_from_registry(task_id, "env_cfg_entry_point")
        agent_cfg = load_cfg_from_registry(task_id, "rsl_rl_cfg_entry_point")
        seed, device = spec["seed"], full_args.device
        env_cfg.seed = seed
        env_cfg.scene.num_envs = 1
        env_cfg.episode_length_s = 14.0
        env_cfg.sim.device = device
        physics_record = configure_physics_mode(env_cfg, spec["physics_mode"])
        env_cfg.viewer.resolution = (full_args.width, full_args.height)
        agent_cfg.seed, agent_cfg.device = seed, device
        if spec["experiment"] == "B":
            terrain = spec.get("terrain", full_args.scene)
            if terrain != full_args.scene:
                raise ValueError("B terrain in JSON must match seq_video scene argument")
            generator = terrain_sets.merged_generator(["random_rough"], 0.5, seed)
            generator.sub_terrains["random_rough"].noise_range = (
                (0.0, 0.003) if terrain == "flat" else (0.01, 0.06))
            env_cfg.scene.terrain.terrain_generator = generator
            env_cfg.scene.terrain.max_init_terrain_level = 0
            env_cfg.curriculum.terrain_levels = None
            task_selection = {"terrain": terrain, "terrain_generator": "random_rough",
                              "noise_range": list(generator.sub_terrains["random_rough"].noise_range),
                              "difficulty": 0.5, "seed": seed}
        else:
            generator = env_cfg.scene.terrain.terrain_generator
            generator.seed = seed
            from foothold_s2.sensors.start_obs import AUG
            configure_topdown_evaluation(env_cfg, AUG)
            task_selection = None

        command_cfg = env_cfg.commands.base_velocity
        command_cfg.fixed_cmd = COMMANDS[0][1]
        command_cfg.resampling_time_range = (LONG_COMMAND_RESAMPLE_S, LONG_COMMAND_RESAMPLE_S)

        gym_env = gym.make(task_id, cfg=env_cfg, render_mode="rgb_array")
        raw = gym_env.unwrapped
        if spec["experiment"] == "TD":
            task_selection = _configure_topdown(raw, spec["terrain_type"], spec["level"], seed)
        env = RslRlVecEnvWrapper(gym_env, clip_actions=agent_cfg.clip_actions)
        adapter = adapters.S2Adapter("open")
        built = {"gym_env": gym_env, "raw": raw, "env_cfg": env_cfg, "agent_cfg": agent_cfg,
                 "env": env}
        env, policy, policy_nn, obs = adapter.load_policy(built, full_args.checkpoint)
        runner = policy.runner
        # Do not inherit S2_Z/S2_ACT from a launcher shell: this protocol is mean/mean.
        policy.z_mode, policy.act_mode = spec["z_mode"], spec["act_mode"]
        delay_record = validate_depth_delay(spec["experiment"], int(runner.perception.cfg.depth_delay_ticks))
        saved_gt = bool(runner.perception.cfg.force_gt)
        map_record = apply_map_mode(policy, spec["map_mode"], runner.pcfg.get("map_input", "none"), saved_gt)
        expected_gt = map_record["effective_use_gt"]
        raw.reset()
        policy.reset(torch.ones(1, dtype=torch.bool, device=raw.device))
        assert_map_mode(policy, expected_gt)
        obs = env.get_observations()

        # Capture the same observation tick that feeds the policy, including depth,
        # ground truth, reconstructed rough/refined maps and the actual use_gt mask.
        perception = runner.perception
        original_advance = perception._advance
        map_snapshot: dict[str, Any] = {}

        def tapped_advance(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map):
            result = original_advance(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map)
            out = result[2]
            map_snapshot.clear()
            map_snapshot.update({"depth": depth2[0, -1].detach().float().cpu().numpy(),
                                 "gt_map": gt_map[0].detach().float().cpu().numpy(),
                                 "rough_map": out.get("rough", torch.empty(0)).reshape(-1).detach().float().cpu().numpy(),
                                 "refined_map": out.get("refined", torch.empty(0)).reshape(-1).detach().float().cpu().numpy(),
                                 "use_gt": bool(use_gt[0].item()),
                                 "first_after_reset": bool(first[0].item())})
            return result

        perception._advance = tapped_advance
        manager = raw.termination_manager
        term_names = tuple(manager.active_terms)
        original_compute = manager.compute
        termination_snapshot: dict[str, bool] = {}

        def capture_termination():
            done_result = original_compute()
            termination_snapshot.clear()
            for term_name in term_names:
                value = manager.get_term(term_name)
                termination_snapshot[term_name] = bool(value[0].item())
            return done_result

        manager.compute = capture_termination
        robot = raw.scene["robot"]
        sensor = raw.scene.sensors["contact_forces"]
        foot_robot_ids, foot_names = robot.find_bodies(".*_foot")
        foot_sensor_ids, sensor_names = sensor.find_bodies(".*_foot")
        if len(foot_robot_ids) != 4 or len(foot_sensor_ids) != 4 or foot_names != sensor_names:
            raise RuntimeError("four matching foot bodies are required")
        command_term = raw.command_manager.get_term("base_velocity")
        step_dt = float(raw.step_dt)
        contract = step_contract(step_dt)
        step_count, frame_indices = contract["physics_steps"], set(contract["video_sample_step_indices"])
        if len(frame_indices) != 300:
            raise RuntimeError("fixed capture contract requires exactly 300 distinct frames")
        output = Path(full_args.mp4).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists() or output.with_suffix(".json").exists() or output.with_name(output.stem + "_feet.npz").exists():
            raise FileExistsError("recorder output must be fresh")
        map_rows = []
        container = av.open(str(output), mode="w")
        stream = container.add_stream("libx264", rate=full_args.fps)
        stream.width, stream.height, stream.pix_fmt = full_args.width, full_args.height, "yuv420p"
        stream.options = {"crf": "20", "preset": "medium"}
        frame_count = 0
        data = {key: [] for key in ("t", "seg", "foot_xyz", "foot_contact", "joint_pos",
                                    "root_pos_w", "root_quat_w", "body_height_foot_center_m",
                                    "policy_action", "joint_pos_target_last_substep",
                                    "applied_torque_last_substep", "joint_target_valid",
                                    "roll", "pitch", "vx", "vy", "wz", "cmd", "done",
                                    "time_out", "termination_reason", "termination_terms",
                                    "map_use_gt", "map_first_after_reset")}
        min_brightness = float("inf")
        render_retry_checks: list[dict[str, Any]] = []
        resets = 0
        font = ImageFont.load_default()

        def write_command(command: tuple[float, float, float]) -> None:
            pin_segment_command(command_cfg, command_term, command)

        frame = None
        last_segment = None
        refresh_observation = True
        for _ in range(12):
            raw.render()
        for k in range(step_count):
            seg = min(3, int((k * step_dt) // 3.0))
            name, command, _span = COMMANDS[seg]
            write_command(command)
            if refresh_observation or seg != last_segment:
                obs = env.get_observations()
                refresh_observation = False
                last_segment = seg
            if k in frame_indices:
                robot_pos = robot.data.root_pos_w[0].detach().cpu().numpy()
                raw.sim.set_camera_view(eye=(robot_pos[0] - 0.4, robot_pos[1] - 1.9, robot_pos[2] + 0.55),
                                        target=(robot_pos[0] + 0.1, robot_pos[1], robot_pos[2] + 0.12))
                frame, retry_checks = render_frame_guarded(raw, robot, command_term, sensor)
                render_retry_checks.extend({"physics_tick": k, **check} for check in retry_checks)
                if frame.shape[:2] != (full_args.height, full_args.width):
                    frame = np.asarray(Image.fromarray(frame).resize((full_args.width, full_args.height)))
                brightness = float(frame.astype(np.float32).mean())
                min_brightness = min(min_brightness, brightness)
                rgba = Image.fromarray(frame)
                draw = ImageDraw.Draw(rgba, "RGBA")
                draw.rectangle((0, 0, full_args.width, 42), fill=(0, 0, 0, 170))
                actual = robot.data.root_lin_vel_b[0].detach().cpu().numpy()
                draw.text((10, 10), f"{full_args.label} | {name} | t={k * step_dt:.2f}s | cmd={command} | vx={actual[0]:.2f} | map={spec['map_mode']}", font=font, fill=(255, 255, 255, 255))
                pixels = np.asarray(rgba.convert("RGB"))
                for packet in stream.encode(av.VideoFrame.from_ndarray(pixels, format="rgb24")):
                    container.mux(packet)
                frame_count += 1

            root_pos_w = robot.data.root_pos_w[0].detach().cpu().numpy().copy()
            quat = robot.data.root_quat_w[0].detach().cpu().numpy().copy()
            roll = math.atan2(2 * (quat[0] * quat[1] + quat[2] * quat[3]), 1 - 2 * (quat[1] ** 2 + quat[2] ** 2))
            pitch = math.asin(max(-1.0, min(1.0, 2 * (quat[0] * quat[2] - quat[3] * quat[1]))))
            foot_xyz = robot.data.body_pos_w[0, foot_robot_ids].detach().cpu().numpy()
            forces = sensor.data.net_forces_w[0, foot_sensor_ids].detach()
            contact = (torch.linalg.vector_norm(forces, dim=-1) > 1.0).cpu().numpy()
            cmd_now = (command_term.commands if hasattr(command_term, "commands") else command_term.vel_command_b)[0, :3].detach().cpu().numpy()
            root_v = robot.data.root_lin_vel_b[0].detach().cpu().numpy()
            root_w = robot.data.root_ang_vel_b[0].detach().cpu().numpy()
            joint_pos = robot.data.joint_pos[0].detach().cpu().numpy().copy()

            with torch.inference_mode():
                actions = policy(obs)
                policy_action = actions[0].detach().cpu().numpy().copy()
                if map_snapshot:
                    if spec["map_mode"] == "pred" and map_snapshot["use_gt"]:
                        raise RuntimeError("pred mode consumed GT map on a policy tick")
                    map_rows.append({"t": k * step_dt, **map_snapshot})
                obs, _reward, dones, _extras = env.step(actions)
                done = bool(dones[0].item())
                terms = dict(termination_snapshot)
                timed_out = bool(getattr(raw, "reset_time_outs", torch.zeros_like(dones))[0].item())
                term = termination_record(done, terms, timed_out)
                # These are the last simulated substep's values, not a per-substep trace.
                # A terminal step may already have reset the articulation.
                if not done:
                    joint_target = robot.data.joint_pos_target[0].detach().cpu().numpy().copy()
                    applied_torque = robot.data.applied_torque[0].detach().cpu().numpy().copy()
                else:
                    joint_target = np.full(joint_pos.shape, np.nan, dtype=np.float32)
                    applied_torque = np.full(joint_pos.shape, np.nan, dtype=np.float32)
                policy_nn.reset(dones)
            if done:
                resets += 1
                assert_map_mode(policy, expected_gt)
                refresh_observation = True
            data["t"].append(k * step_dt)
            data["seg"].append(seg)
            data["foot_xyz"].append(foot_xyz)
            data["foot_contact"].append(contact)
            data["joint_pos"].append(joint_pos)
            data["root_pos_w"].append(root_pos_w)
            data["root_quat_w"].append(quat)
            data["body_height_foot_center_m"].append(
                body_height_from_contact_feet(root_pos_w[2], foot_xyz[:, 2], contact))
            data["policy_action"].append(policy_action)
            data["joint_pos_target_last_substep"].append(joint_target)
            data["applied_torque_last_substep"].append(applied_torque)
            data["joint_target_valid"].append(not done)
            data["roll"].append(roll)
            data["pitch"].append(pitch)
            data["vx"].append(float(root_v[0]))
            data["vy"].append(float(root_v[1]))
            data["wz"].append(float(root_w[2]))
            data["cmd"].append(cmd_now)
            data["done"].append(term["done"])
            data["time_out"].append(term["time_out"])
            data["termination_reason"].append(term["reason"])
            data["termination_terms"].append("|".join(term["active_terms"]))
            data["map_use_gt"].append(bool(map_rows[-1]["use_gt"]) if map_rows else expected_gt)
            data["map_first_after_reset"].append(bool(map_rows[-1]["first_after_reset"]) if map_rows else False)
        if frame_count != 300:
            raise RuntimeError(f"frame count {frame_count} != 300")
        if spec["map_mode"] == "pred" and any(row["use_gt"] for row in map_rows):
            raise RuntimeError("pred mode GT-use count must be zero")

        for packet in stream.encode():
            container.mux(packet)
        container.close()
        container = None

        npz_path = output.with_name(output.stem + "_feet.npz")
        map_t = np.asarray([row["t"] for row in map_rows], dtype=np.float64)
        map_arrays: dict[str, Any] = {}
        for key in ("depth", "gt_map", "rough_map", "refined_map"):
            values = [row[key] for row in map_rows]
            if values and all(value.size == values[0].size for value in values):
                map_arrays[key] = np.stack(values)
            else:
                map_arrays[key] = np.empty((0,), dtype=np.float32)
        np.savez_compressed(npz_path, t=np.asarray(data["t"], dtype=np.float64),
                            seg=np.asarray(data["seg"], dtype=np.int8), dt=np.float64(step_dt),
                            seg_s=np.float64(3.0), foot_z=np.asarray(data["foot_xyz"])[:, :, 2],
                            foot_xy=np.asarray(data["foot_xyz"])[:, :, :2],
                            foot_contact=np.asarray(data["foot_contact"], dtype=np.bool_),
                            **measurement_arrays(data, foot_names, robot.joint_names, step_count),
                            joint_pos=np.asarray(data["joint_pos"]), roll=np.asarray(data["roll"]),
                            pitch=np.asarray(data["pitch"]), vx=np.asarray(data["vx"]),
                            vy=np.asarray(data["vy"]), wz=np.asarray(data["wz"]),
                            command=np.asarray(data["cmd"]), done=np.asarray(data["done"], dtype=np.bool_),
                            time_out=np.asarray(data["time_out"], dtype=np.bool_),
                            termination_reason=np.asarray(data["termination_reason"], dtype="U40"),
                            termination_terms=np.asarray(data["termination_terms"], dtype="U256"),
                            map_t=map_t, map_use_gt=np.asarray([row["use_gt"] for row in map_rows], dtype=np.bool_),
                            map_first_after_reset=np.asarray([row["first_after_reset"] for row in map_rows], dtype=np.bool_),
                            depth=map_arrays["depth"], gt_map=map_arrays["gt_map"],
                            rough_map=map_arrays["rough_map"], refined_map=map_arrays["refined_map"])

        map_png = output.with_name(output.stem + "_maps.png")
        if map_rows:
            selected = [min(map_rows, key=lambda row: abs(row["t"] - target)) for target in (0.0, 3.0, 6.0, 9.0)]
            tiles = []
            names = ("depth", "gt_map", "rough_map", "refined_map")
            for row in selected:
                try:
                    display = height_map_display(row["depth"], row["gt_map"], row["rough_map"], row["refined_map"])
                except ValueError:
                    display = None
                for key in names:
                    tile_size = (120, 120) if key == "depth" else (120, 60)
                    if display is None:
                        tile = np.zeros((tile_size[1], tile_size[0]), dtype=np.uint8)
                    else:
                        arr = display["depth"] if key == "depth" else display[key.removesuffix("_map")]
                        lo, hi = display["depth_scale"] if key == "depth" else display["height_scale_m"]
                        tile = np.uint8(np.clip((arr - lo) / (hi - lo) * 255, 0, 255))
                        tile = np.asarray(Image.fromarray(tile).resize(tile_size))
                    tiles.append((key, row["t"], tile))
            sheet = Image.new("RGB", (4 * 120, 4 * 145), "white")
            draw = ImageDraw.Draw(sheet)
            for i, (name, timestamp, tile) in enumerate(tiles):
                x, y = (i % 4) * 120, (i // 4) * 145
                sheet.paste(Image.fromarray(tile).convert("RGB"), (x, y + 22 + (60 if name != "depth" else 0)))
                draw.text((x + 2, y + 3), f"{name} t={timestamp:.2f}s", fill="black", font=font)
            sheet.save(map_png)

        mode_observed = {"map_mode": map_record, "gt_use_count": int(sum(bool(row["use_gt"]) for row in map_rows)),
                         "map_samples": len(map_rows),
                         "gt_use_expected_zero": spec["map_mode"] == "pred"}
        metadata = {
            "format": "foothold-sol23f-capture/1", "label": full_args.label,
            "scene": full_args.scene, "experiment": spec["experiment"],
            "checkpoint": str(Path(full_args.checkpoint).resolve()),
            "checkpoint_sha256": _sha(Path(full_args.checkpoint)),
            "code_sha256": _sha(Path(__file__).resolve()), "sources_sha256": _source_hashes(repo, spec["experiment"]),
            "measurement_recorder": {"format": "sol24i/1", "path": str(Path(__file__).resolve()),
                                     "sha256": _sha(Path(__file__).resolve()),
                                     "base_recorder_sha256": BASE_RECORDER_SHA256,
                                      "measurement_base_sha256": MEASUREMENT_RECORDER_SHA256,
                                     "source_root": str(repo),
                                     "sample_time": "pre-step pose/feet/contact/joints and policy action; terminal flag from step",
                                     "height_definition": "root z minus mean contacting foot-center z; NaN without contact",
                                     "actuator_definition": "nonterminal last simulated substep only; terminal rows NaN"},
            "task_id": task_id, "task_selection": task_selection, "seed": spec["seed"],
            "policy_modes": {"latent": spec["z_mode"], "action": spec["act_mode"]},
            "perception_timing": delay_record,
            "map_modes": mode_observed, "step_contract": contract,
            "physics": {**physics_record, "actual_readback": physics_actual_readback(raw)},
            "segments": [[name, list(command), duration] for name, command, duration in COMMANDS],
            "frames": frame_count, "fps": full_args.fps, "duration_s": 12.0,
            "min_mean_brightness": min_brightness, "resets": resets,
            "render_retry_method": "sim.render then raw.render(recompute=True)",
            "render_retry_checks": render_retry_checks,
            "termination_semantics": "reset is recorded with active termination items; no automatic fall label",
            "map_image": ({"name": map_png.name, "receipt_included": False} if map_rows else None),
            "map_arrays": "aligned by map_t in the feet NPZ; empty for checkpoints without reconstruction maps",
            "map_display": {"height_shape": list(HEIGHT_MAP_SHAPE), "height_scale_m": list(HEIGHT_SCALE_M),
                            "depth_scale_m": list(DEPTH_SCALE_M)},
        }
        _json_atomic(output.with_suffix(".json"), metadata)
        print("SOL23F_CAPTURE", json.dumps({"frames": frame_count, "steps": step_count,
                                             "resets": resets, "map_mode": mode_observed,
                                             "npz": npz_path.name, "map_png": metadata["map_image"]}), flush=True)
    finally:
        if container is not None:
            container.close()


def main(argv: list[str] | None = None) -> int:
    parser = _argv_parser()
    # Parse known arguments first so the plan-only path does not import Kit.
    args, _remaining = parser.parse_known_args(argv)
    spec = parse_spec(args.policy)
    validate_source_root(Path(spec["source_root"]))
    if args.physics_mode is not None:
        spec["physics_mode"] = args.physics_mode
    if args.scene != spec.get("terrain", args.scene) and spec["experiment"] == "B":
        parser.error("B JSON terrain and seq_video scene must match")
    if args.plan_only:
        print(json.dumps({"format": "foothold-sol23f-plan/1", "label": args.label,
                          "scene": args.scene, "spec": spec, "commands": COMMANDS,
                          "target_frames": 300, "duration_s": 12.0,
                          "map_modes": ["saved", "pred", "gt"],
                          "receipt_consumer": "foothold_s2.eval.seq_video"}, indent=2))
        return 0
    try:
        _capture(spec)
    except BaseException:
        import traceback
        traceback.print_exc(file=sys.stderr)
        exit_after_flush(1)
    exit_after_flush(0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
