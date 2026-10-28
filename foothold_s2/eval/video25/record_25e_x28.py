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
import re
import subprocess
import sys
from typing import Any


WALK_TURN_COMMANDS = (
    ("walk_turn_left_05", (0.5, 0.0, 0.35), 3.0),
    ("walk_turn_right_05", (0.5, 0.0, -0.35), 3.0),
    ("walk_turn_left_08", (0.8, 0.0, 0.5), 3.0),
    ("walk_turn_right_08", (0.8, 0.0, -0.5), 3.0),
)
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
B_REVIEW_TERRAIN_TYPES = {"pyramid_stairs", "boxes", "hf_pyramid_slope", "balance_beams"}
CAPTURE_EXPERIMENTS = ("B", "TD", "G0B", "SB")
SPARSE_GEOMETRY_SEED = 20261026
SPARSE_EVAL_SEED = 42
SPARSE_ENV_COUNT = 64
SPARSE_COMMAND = ("fwd1.0", (1.0, 0.0, 0.0), 18.0)
MAP_MODES_BY_EXPERIMENT = {
    "B": ("saved", "pred", "gt"), "TD": ("saved", "pred", "gt"),
    "G0B": ("none",), "SB": ("eval_gt", "probe_prop_only", "eval_pred"),
}
ROUGH_SAFE_START_X_M = -1.0
HEIGHT_MAP_SHAPE = (32, 16)
HEIGHT_SCALE_M = (-1.0, 1.0)
DEPTH_SCALE_M = (0.0, 6.0)
LONG_COMMAND_RESAMPLE_S = 1.0e9
BASE_RECORDER_SHA256 = "662cd68906bdf99301830ef149e77c11a5d4b849c0938f0fcb7584fb0913afd6"
MEASUREMENT_RECORDER_SHA256 = "12547e29e15e0c9b1c0eb05cf1d460218292249b0750ec00eb73cfc906147ca0"
EX35_SOURCE_PROFILE = "EX-35"
EX35_SOURCE_ROOT = "C:/mai/wt/foothold-lab/impl-ex35-07fc"
EX35_SOURCE_HEAD = "07fc5e73b1122d6a4e8ab01fc922af998db4651a"
EX35_SOURCE_TREE = "11805aa49f8bef1732919190d294aa25fb34afbd"
EX35_RECORDER_SHA256 = "ce86aec23ffa6e863cab746ac4da5e4504ebbe2919be1f85f2ad7af6aa7979e2"
EX35_SOURCE_FILE_SHA256 = {
    "foothold_s2/sb_tasks.py": "8e9d8d91d4a841706ca9f70bfbe78805682d203b8cdb2130c525e53b65f9f99a",
    "foothold_s2/eval/adapters.py": "4987bc196a9a455b409341607be75a05a3a34f275a3b8ceb1086c2a61ed214ff",
    "foothold_s2/tasks/s2_sb_cfg.py": "26cd26be1716a5167c153b4cb55474ce57ea926dff3ba9b5970a6dbf89d77241",
    "foothold_s2/tasks/agents/s2_sb_ppo_cfg.py": "3da547f7e10e53e0d816e4caf097c721fe9ea96eda8a22fc6a35d59f8ed3d1fe",
    "foothold_s2/commands/mixed_command.py": "57115f26ecfd206e8191faecd8f857609344ccada1dcf7c88b47926297837b6c",
    "foothold_s2/commands/mixed_core.py": "bf3a8aa469114fae1cd9b247ac3aa639ac96fe4fad449578d80bcbb2d1f6a219",
    "foothold_s2/sol23f_contract.py": "b7f58a71cd6e86f598a9b6a3c7427c5cebb7b0ec7f347f544c6078557d0ac40c",
    "foothold_s2/runners/start_runner.py": "ff3406e8c22ba935f2cbe9c596b46b42c2156926a251b43f6747905f9e827e34",
}
W03_PROFILE = "W03"                                        # W03 촬영: 평가에 쓴 고정 사본과 같은 코드, 세 정본 저장본만
W03_SOURCE_ROOT = "C:/mai/wt/foothold-lab/eval-x27m4"
W03_SOURCE_HEAD = "496e0cfed7fffe704b91c22f52f89572a5bab20e"
W03_RECORDER_SHA256 = "ce86aec23ffa6e863cab746ac4da5e4504ebbe2919be1f85f2ad7af6aa7979e2"
W03_CHECKPOINT_SHA256 = ("4d987818", "eba0fbdd")           # 부모 m1500 · EX-35 m2000 (앞 8 자리, 아래 B1500 은 평가 때 기록한 값을 spec 에서 받는다)
W03_FIXED_LEVEL_KINDS = "fixed64"                          # 연속 지형 64 env 평가 배치(map64 = 레벨 0..2, hardlevel = 레벨 L)
W03_SUCCESS_FWD_M = 3.0                                    # SELECTION_RULE.md v2: 성공 = alive_end 참 그리고 body_vx_integral_m >= 3.0(몸 앞쪽 방향 이동 거리, 시작 yaw 가 무작위인 연속 칸에서도 뜻이 같다), 실패 = alive_end 거짓
EX35_CHECKPOINT = "C:/mai/wt/foothold-lab/impl-sb/logs/rsl_rl/foothold_s2_sb/2026-10-26_01-17-47_sb-main_resume_20261026_232446_120476/model_2000.pt"
EX35_CHECKPOINT_SHA256 = "eba0fbdd7e8cdb2f4a3750ee1125e55063fbb36eb9d1377692fad26f850fb548"


def _render_state(raw: Any, robot: Any, command_term: Any, sensor: Any,
                  env_index: int = 0) -> dict[str, Any]:
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
        "root_pos_w": values(robot.data.root_pos_w[env_index]),
        "root_quat_w": values(robot.data.root_quat_w[env_index]),
        "root_lin_vel_b": values(robot.data.root_lin_vel_b[env_index]),
        "root_ang_vel_b": values(robot.data.root_ang_vel_b[env_index]),
        "command": values(command[env_index, :3]),
        "contact_timestamp": values(sensor._timestamp),
        "contact_timestamp_last_update": values(sensor._timestamp_last_update),
    }


def render_frame_guarded(raw: Any, robot: Any, command_term: Any, sensor: Any,
                         *, dark_threshold: float = 10.0,
                         max_retries: int = 30,
                         env_index: int = 0) -> tuple[Any, list[dict[str, Any]]]:
    """Retry RGB with the simulation render guard, never advancing the episode."""
    import numpy as np

    if max_retries < 0:
        raise ValueError("max_retries must be nonnegative")
    checks: list[dict[str, Any]] = []
    before = _render_state(raw, robot, command_term, sensor, env_index)
    frame = np.ascontiguousarray(raw.render())[..., :3]
    after = _render_state(raw, robot, command_term, sensor, env_index)
    if after != before:
        changed = [key for key in before if before[key] != after[key]]
        raise RuntimeError("render_state_changed " + json.dumps(
            {"phase": "initial", "changed": changed, "before": before, "after": after},
            allow_nan=False))
    brightness = float(frame.astype(np.float32).mean())
    for retry in range(1, max_retries + 1):
        if brightness > dark_threshold:
            break
        before = _render_state(raw, robot, command_term, sensor, env_index)
        raw.sim.render()
        frame = np.ascontiguousarray(raw.render(recompute=True))[..., :3]
        after = _render_state(raw, robot, command_term, sensor, env_index)
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


def configure_capture_start(env_cfg: Any, x_m: float = ROUGH_SAFE_START_X_M) -> dict[str, Any]:
    """Keep the standard four-command order while moving the later turns inside the tile."""
    events = getattr(env_cfg, "events", None)
    reset = getattr(events, "reset_base", None) if events is not None else None
    params = getattr(reset, "params", None)
    pose = params.get("pose_range") if isinstance(params, dict) else None
    if not isinstance(pose, dict) or "x" not in pose:
        raise ValueError("reset_base.pose_range.x is required to pin the R17 start offset")
    pose["x"] = (float(x_m), float(x_m))
    return {"offset_x_m": float(x_m), "source": "reset_base.pose_range.x"}


def lighting_profile_settings(profile: str = "inherit", *, intensity: float | None = None,
                              angle_deg: float = 1.0, azimuth_deg: float = 45.0,
                              elevation_deg: float = 45.0, shadows: bool = True,
                              three_point_intensity: float | None = None,
                              three_point_angle_deg: float = 12.0,
                              three_point_elevation_deg: float = 45.0,
                              three_point_shadows: bool = True,
                              dome_intensity: float | None = None) -> dict[str, Any]:
    """Validate inherited, three-point, dome, or mixed scene lighting candidates."""
    supported = ("inherit", "current_plus_directional", "three_point", "dome",
                 "dome_plus_three_point")
    if profile not in supported:
        raise ValueError("lighting profile must be one of " + ", ".join(supported))
    reference = {"inherit_probe_mean_rgb8": 76.1, "v2_flat_probe_mean_rgb8": 183.0,
                 "sun_5000_shadows_on_probe_mean_rgb8": 224.9,
                 "sun_5000_shadows_off_probe_mean_rgb8": 222.3,
                 "target_probe_mean_rgb8": 150.0,
                 "target_scope": "between inherit and v2_flat; do not infer from intensity alone"}
    if profile == "inherit":
        if intensity is not None or three_point_intensity is not None or dome_intensity is not None:
            raise ValueError("light intensities require a non-inherit profile")
        return {"profile": "inherit", "explicit_directional_light": False,
                "brightness_calibration": "not_requested", "brightness_reference": reference}
    if profile == "current_plus_directional":
        if intensity is None or not math.isfinite(float(intensity)) or float(intensity) <= 0:
            raise ValueError("current_plus_directional requires a positive explicit intensity")
        if not math.isfinite(float(angle_deg)) or not 0.0 <= float(angle_deg) <= 180.0:
            raise ValueError("directional angle must be from 0 through 180 degrees")
        if not math.isfinite(float(azimuth_deg)) or not math.isfinite(float(elevation_deg)):
            raise ValueError("direction angles must be finite")
        if not 0.0 < float(elevation_deg) < 90.0:
            raise ValueError("directional source elevation must be between 0 and 90 degrees")
        return {"profile": profile, "explicit_directional_light": True,
                "intensity": float(intensity), "angle_deg": float(angle_deg),
                "azimuth_deg": float(azimuth_deg), "elevation_deg": float(elevation_deg),
                "shadows": bool(shadows), "brightness_calibration": "pending_still_review",
                "brightness_reference": reference}

    needs_three_point = profile in ("three_point", "dome_plus_three_point")
    needs_dome = profile in ("dome", "dome_plus_three_point")
    tp_intensity = (50.0 if three_point_intensity is None else float(three_point_intensity))
    dom_intensity = (0.05 if dome_intensity is None else float(dome_intensity))
    if needs_three_point and (not math.isfinite(tp_intensity) or tp_intensity <= 0):
        raise ValueError("three-point intensity must be positive and finite")
    if needs_dome and (not math.isfinite(dom_intensity) or dom_intensity <= 0):
        raise ValueError("dome intensity must be positive and finite")
    if not math.isfinite(float(three_point_angle_deg)) or not 0.0 <= float(three_point_angle_deg) <= 180.0:
        raise ValueError("three-point angle must be from 0 through 180 degrees")
    if not math.isfinite(float(three_point_elevation_deg)) or not 0.0 < float(three_point_elevation_deg) < 90.0:
        raise ValueError("three-point elevation must be between 0 and 90 degrees")
    return {"profile": profile, "explicit_directional_light": needs_three_point,
            "three_point": ({"count": 3, "intensity": tp_intensity, "angle_deg": float(three_point_angle_deg),
                             "azimuths_deg": [45.0, 165.0, 285.0],
                             "elevation_deg": float(three_point_elevation_deg),
                             "shadows": bool(three_point_shadows)} if needs_three_point else None),
            "dome": ({"intensity": dom_intensity} if needs_dome else None),
            "brightness_calibration": "pending_still_review",
            "brightness_reference": reference}


def apply_lighting_to_stage(stage: Any, profile: dict[str, Any]) -> dict[str, Any]:
    """Apply the selected lights to a USD stage without requiring Kit for CPU tests."""
    if profile.get("profile") == "inherit":
        return dict(profile)
    from pxr import Gf, Sdf, UsdGeom, UsdLux

    profile_name = profile.get("profile")
    if profile_name == "current_plus_directional":
        profile = dict(profile)
        profile["three_point"] = {"count": 1, "intensity": float(profile["intensity"]),
                                  "angle_deg": float(profile["angle_deg"]),
                                  "azimuths_deg": [float(profile["azimuth_deg"])],
                                  "elevation_deg": float(profile["elevation_deg"]),
                                  "shadows": bool(profile["shadows"])}
        profile["dome"] = None

    created = []
    dome_cfg = profile.get("dome")
    if dome_cfg:
        path = Sdf.Path("/World/RunnerDomeLight")
        dome = UsdLux.DomeLight.Define(stage, path)
        dome.CreateIntensityAttr(float(dome_cfg["intensity"]))
        created.append({"prim_path": str(path), "type": "DomeLight",
                        "intensity": float(dome_cfg["intensity"])})
    three = profile.get("three_point")
    if three:
        directions = []
        for index, azimuth in enumerate(three["azimuths_deg"], start=1):
            if profile_name == "current_plus_directional":
                path = Sdf.Path("/World/RunnerDirectionalLight")
            else:
                path = Sdf.Path(f"/World/RunnerThreePointLight_{index}")
            light = UsdLux.DistantLight.Define(stage, path)
            light.CreateIntensityAttr(float(three["intensity"]))
            light.CreateAngleAttr(float(three["angle_deg"]))
            shadow_api = UsdLux.ShadowAPI.Apply(light.GetPrim())
            shadow_api.CreateShadowEnableAttr(bool(three["shadows"]))
            az = math.radians(float(azimuth))
            el = math.radians(float(three["elevation_deg"]))
            source = Gf.Vec3d(math.cos(el) * math.cos(az),
                              math.cos(el) * math.sin(az), math.sin(el))
            rays = -source
            rotation = Gf.Rotation(Gf.Vec3d(0.0, 0.0, -1.0), rays)
            xform = UsdGeom.Xformable(light.GetPrim())
            xform.ClearXformOpOrder()
            xform.AddOrientOp().Set(Gf.Quatf(rotation.GetQuat()))
            directions.append({"prim_path": str(path), "azimuth_deg": float(azimuth),
                               "source_xyz": list(source), "rays_xyz": list(rays)})
            created.append({"prim_path": str(path), "type": "DistantLight",
                            "intensity": float(three["intensity"]),
                            "angle_deg": float(three["angle_deg"]), "shadows": bool(three["shadows"])})
    return dict(profile, prims=created, brightness_calibration="pending_still_review")


def hide_nonselected_robot_roots(stage: Any, robot_prim_template: str,
                                selected_env_id: int, expected_env_count: int, keep_env_ids=()) -> dict[str, Any]:
    """Hide non-selected cloned robot visuals using USD visibility only.

    The articulated robots, sensors, terrain and policy environment remain in
    the stage. Only the root Imageable visibility attribute is authored.
    """
    from pxr import UsdGeom

    template = str(robot_prim_template).replace("{ENV_REGEX_NS}", "/World/envs/env_.*")
    if "env_.*" not in template:
        raise ValueError(f"robot prim template has no env namespace wildcard: {template}")
    prefix, suffix = template.split("env_.*", 1)
    pattern = re.compile(r"^" + re.escape(prefix) + r"env_(\d+)" + re.escape(suffix) + r"$")
    roots: dict[int, Any] = {}
    for prim in stage.Traverse():
        match = pattern.match(str(prim.GetPath()))
        if match:
            env_id = int(match.group(1))
            if env_id in roots:
                raise ValueError(f"duplicate robot root for env {env_id}")
            roots[env_id] = prim
    expected_ids = set(range(int(expected_env_count)))
    if set(roots) != expected_ids:
        missing = sorted(expected_ids - set(roots))
        extra = sorted(set(roots) - expected_ids)
        raise ValueError(f"robot root inventory mismatch; missing={missing}, extra={extra}")
    if not 0 <= int(selected_env_id) < int(expected_env_count):
        raise ValueError("selected env id is outside the robot inventory")

    hidden_paths = []
    for env_id, prim in sorted(roots.items()):
        if env_id == int(selected_env_id) or env_id in tuple(keep_env_ids):
            continue
        imageable = UsdGeom.Imageable(prim)
        if not imageable:
            raise ValueError(f"robot root is not imageable: {prim.GetPath()}")
        imageable.MakeInvisible()
        hidden_paths.append(str(prim.GetPath()))
    return {"enabled": True, "method": "usd_imageable_visibility",
            "physics_or_policy_config_changed": False,
            "selected_env_id": int(selected_env_id),
            "environment_count": int(expected_env_count),
            "visible_robot_root": str(roots[int(selected_env_id)].GetPath()),
            "hidden_robot_roots": hidden_paths}


def define_target_marker(stage: Any, *, path: str = "/World/RunnerSelectedEnvMarker",
                         radius_m: float = 0.06, height_above_root_m: float = 0.08) -> tuple[Any, dict[str, Any]]:
    """Create a render-only, non-colliding marker which follows one captured robot."""
    from pxr import Gf, Sdf, UsdGeom

    sphere = UsdGeom.Sphere.Define(stage, Sdf.Path(path))
    sphere.CreateRadiusAttr(float(radius_m))
    sphere.CreateDisplayColorAttr([Gf.Vec3f(1.0, 0.82, 0.02)])
    xform = UsdGeom.Xformable(sphere.GetPrim())
    translate = xform.AddTranslateOp()
    return translate, {"enabled": True, "method": "render_only_usd_sphere",
                       "prim_path": path, "radius_m": float(radius_m),
                       "height_above_root_m": float(height_above_root_m),
                       "collision_or_rigid_body_api_added": False}


def update_target_marker(translate_op: Any, root_pos_w: Any,
                         height_above_root_m: float = 0.08) -> tuple[float, float, float]:
    """Move the marker above the selected robot without changing its state."""
    from pxr import Gf

    x, y, z = (float(value) for value in root_pos_w[:3])
    position = (x, y, z + float(height_above_root_m))
    translate_op.Set(Gf.Vec3d(*position))
    return position


def apply_lighting_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Apply optional USD lighting; inherited scene lighting stays untouched."""
    if profile.get("profile") == "inherit":
        return dict(profile)
    import omni.usd
    return apply_lighting_to_stage(omni.usd.get_context().get_stage(), profile)


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
    if experiment not in CAPTURE_EXPERIMENTS:
        raise ValueError("experiment must be B, TD, G0B, or SB")
    source_profile = spec.get("source_profile")
    if source_profile not in (None, EX35_SOURCE_PROFILE, W03_PROFILE):
        raise ValueError("source_profile must be omitted, EX-35 or W03")
    if source_profile == EX35_SOURCE_PROFILE and experiment != "SB":
        raise ValueError("EX-35 source profile requires the S-B task")
    spec.setdefault("seed", 42)
    spec.setdefault("map_mode", {"G0B": "none", "SB": "eval_gt"}.get(experiment, "saved"))
    spec.setdefault("z_mode", "mean")
    spec.setdefault("act_mode", "mean")
    spec.setdefault("physics_mode", "sparse_eval_reference" if spec.get("terrain_set") in ("sparse50", W03_FIXED_LEVEL_KINDS) else "fixed")
    if type(spec["seed"]) is not int:
        raise ValueError("seed must be an integer")
    if spec["map_mode"] not in MAP_MODES_BY_EXPERIMENT[experiment]:
        raise ValueError("map_mode is incompatible with experiment")
    if spec["physics_mode"] not in ("fixed", "training", "sparse_eval_reference"):
        raise ValueError("physics_mode must be fixed or training")
    if spec["z_mode"] != "mean" or spec["act_mode"] != "mean":
        raise ValueError("fixed evaluation requires mean latent and mean action")
    if experiment in ("B", "G0B", "SB"):
        terrain_type = spec.get("terrain_type")
        if terrain_type is not None:
            if experiment != "B" or terrain_type not in B_REVIEW_TERRAIN_TYPES:
                raise ValueError("terrain_type must name a supported B review terrain")
            expected_terrain = "sparse" if terrain_type == "balance_beams" else "rough"
            if spec.get("terrain", expected_terrain) != expected_terrain:
                raise ValueError("terrain label must match the selected terrain_type")
            spec.setdefault("terrain", expected_terrain)
        elif spec.get("terrain_set") != "sparse50" and spec.get("terrain", "rough") not in ("flat", "rough"):
            raise ValueError("terrain must be flat or rough")
        elif spec.get("terrain_set") != "sparse50":
            spec.setdefault("terrain", "rough")
    elif experiment == "TD":
        if spec.get("terrain_type") not in TOPDOWN_KINDS:
            raise ValueError("TD terrain_type must be a registered native sparse type")
        if type(spec.get("level")) is not int or not 0 <= spec["level"] <= 9:
            raise ValueError("TD level must be an integer from 0 through 9")
    if spec.get("terrain_set") == W03_FIXED_LEVEL_KINDS and spec.get("w03_reference") is not True:
        raise ValueError("fixed64 capture is only defined for the W03 selection reference (w03_reference=true)")
    if spec.get("w03_reference") is True and (source_profile != W03_PROFILE or spec.get("terrain_set") not in ("sparse50", W03_FIXED_LEVEL_KINDS)):
        raise ValueError("w03_reference requires source_profile W03 and terrain_set sparse50 or fixed64")
    if spec.get("terrain_set") == W03_FIXED_LEVEL_KINDS:
        if spec["physics_mode"] != "sparse_eval_reference" or experiment not in ("B", "SB"):
            raise ValueError("fixed64 requires sparse_eval_reference physics and experiment B or SB")
        if spec.get("fixed_terrain") is not True or type(spec.get("fixed_level")) is not int or not 0 <= spec["fixed_level"] <= 9:
            raise ValueError("fixed64 requires fixed_terrain=true and fixed_level 0 through 9")
        if spec.get("map64_levels") is True and spec["fixed_level"] != 0:
            raise ValueError("map64 layout uses the level-less assignment: give fixed_level 0 only as a placeholder")
        if type(spec.get("envs")) is not int or spec["envs"] != SPARSE_ENV_COUNT or type(spec.get("env_id")) is not int or not 0 <= spec["env_id"] < SPARSE_ENV_COUNT:
            raise ValueError("fixed64 requires 64 envs and env_id 0 through 63")
        if spec.get("seed", SPARSE_EVAL_SEED) != SPARSE_EVAL_SEED or spec.get("command") != list(SPARSE_COMMAND[1]) or spec.get("duration_s") != SPARSE_COMMAND[2]:
            raise ValueError("fixed64 capture is seed 42, forward 1.0 m/s, 18 s")
        if type(spec.get("col")) is not int or not isinstance(spec.get("kind"), str) or spec.get("selection_role") not in ("success", "fail"):
            raise ValueError("fixed64 requires kind, col and selection_role success or fail")
        for key in ("eval_root", "reference_arrays"):
            if not isinstance(spec.get(key), str) or not Path(spec[key]).is_absolute():
                raise ValueError(f"fixed64 requires an absolute {key}")
        if not isinstance(spec.get("reference_arrays_sha256"), str) or not isinstance(spec.get("checkpoint_sha256"), str):
            raise ValueError("fixed64 requires reference_arrays_sha256 and checkpoint_sha256")
    if spec.get("terrain_set") == "sparse50":
        if spec["physics_mode"] != "sparse_eval_reference":
            raise ValueError("sparse50 must use sparse_eval_reference physics mode")
        if experiment != "SB" and spec.get("w03_reference") is not True:
            raise ValueError("sparse50 fixed-cell capture requires experiment SB")
        if spec.get("fixed_terrain") is not True or type(spec.get("fixed_level")) is not int:
            raise ValueError("sparse50 requires fixed_terrain=true and fixed_level")
        if not 0 <= spec["fixed_level"] <= 9:
            raise ValueError("sparse50 fixed_level must be 0 through 9")
        if type(spec.get("envs")) is not int or spec["envs"] != SPARSE_ENV_COUNT:
            raise ValueError("sparse50 capture must preserve the evaluation's 64 environments")
        if type(spec.get("env_id")) is not int or not 0 <= spec["env_id"] < SPARSE_ENV_COUNT:
            raise ValueError("sparse50 env_id must be 0 through 63")
        if spec.get("geometry_seed") != SPARSE_GEOMETRY_SEED:
            raise ValueError("sparse50 geometry_seed must match the evaluation")
        if type(spec.get("seed", SPARSE_EVAL_SEED)) is not int or spec.get("seed", SPARSE_EVAL_SEED) != SPARSE_EVAL_SEED:
            raise ValueError("sparse50 evaluation seed must be 42")
        if spec.get("kind") not in TOPDOWN_KINDS or type(spec.get("col")) is not int:
            raise ValueError("sparse50 requires the selected tile kind and column")
        if not 0 <= spec["col"] < 50 or spec.get("start_yaw_rad", 0.0) != 0.0:
            raise ValueError("sparse50 requires a valid column and +x start yaw")
        if spec.get("command") != list(SPARSE_COMMAND[1]):
            raise ValueError("sparse50 capture command must be forward 1.0 m/s")
        if spec.get("duration_s") != SPARSE_COMMAND[2]:
            raise ValueError("sparse50 capture duration must be 18 seconds")
        checkpoint_sha = spec.get("checkpoint_sha256")
        if not isinstance(checkpoint_sha, str) or re.fullmatch(r"[0-9a-f]{64}", checkpoint_sha) is None:
            raise ValueError("sparse50 requires the evaluation checkpoint SHA256")
        for key in ("eval_root", "reference_arrays") if spec.get("w03_reference") is True else ("eval_root", "reference_eval_json", "reference_arrays"):
            candidate = spec.get(key)
            if not isinstance(candidate, str) or not Path(candidate).is_absolute():
                raise ValueError(f"sparse50 requires an absolute {key}")
        if spec.get("selection_role") not in (("success", "fail") if spec.get("w03_reference") is True else ("crossed", "fell")):
            raise ValueError("sparse50 selection_role is invalid")
        if spec.get("w03_reference") is True and not isinstance(spec.get("reference_arrays_sha256"), str):
            raise ValueError("w03 sparse50 requires reference_arrays_sha256")
    return spec


def sparse_capture_plan(*, env_id: int, fixed_level: int, map_mode: str,
                        kind: str, col: int) -> dict[str, Any]:
    """Pure plan for one env on the fixed sparse50 evaluation layout."""
    if map_mode not in MAP_MODES_BY_EXPERIMENT["SB"]:
        raise ValueError("sparse50 map_mode must be eval_gt or probe_prop_only")
    if type(env_id) is not int or not 0 <= env_id < SPARSE_ENV_COUNT:
        raise ValueError("sparse50 env_id must be 0 through 63")
    if type(fixed_level) is not int or not 0 <= fixed_level <= 9:
        raise ValueError("sparse50 fixed_level must be 0 through 9")
    if kind not in TOPDOWN_KINDS or type(col) is not int or not 0 <= col < 50:
        raise ValueError("sparse50 selected tile kind/column is invalid")
    return {"terrain_set": "sparse50", "fixed_terrain": True,
            "fixed_level": fixed_level, "geometry_seed": SPARSE_GEOMETRY_SEED,
            "seed": SPARSE_EVAL_SEED, "envs": SPARSE_ENV_COUNT, "env_id": env_id,
            "kind": kind, "col": col, "start_yaw_rad": 0.0,
            "map_mode": map_mode, "command_name": SPARSE_COMMAND[0],
            "command": list(SPARSE_COMMAND[1]), "duration_s": SPARSE_COMMAND[2],
            "fps": 25, "frames": 450, "physics_mode": "sparse_eval_reference"}


def select_sparse_env_pair(map_modes_path: str | Path, arrays_path: str | Path,
                           *, kind: str = "balance_beams", level: int = 0,
                           threshold_m: float = 6.5, fall_height_m: float = 0.25) -> dict[str, Any]:
    """Select one same fixed cell with a clear crossing and a separate fall."""
    import numpy as np

    meta = json.loads(Path(map_modes_path).read_text(encoding="utf-8"))
    if meta.get("terrain_set") != "sparse50":
        raise ValueError("reference is not sparse50")
    tiles = meta.get("fixed_terrain", {}).get("tiles", [])
    env_count = meta.get("envs")
    if type(env_count) is not int or env_count != len(tiles):
        raise ValueError("reference fixed terrain tile list does not match env count")
    stem = Path(arrays_path).name
    mode = "probe_prop_only" if stem.startswith("arrays_probe_prop_only_") else (
        "eval_gt" if stem.startswith("arrays_eval_gt_") else None)
    if mode is None or "fwd1.0" not in stem:
        raise ValueError("reference arrays must be fwd1.0 from eval_gt or probe_prop_only")
    assignment_hash = meta.get("fixed_terrain", {}).get("assignment_sha256")
    if assignment_hash and meta.get("terrain_hash", {}).get(f"{mode}/fwd1.0") != assignment_hash:
        raise ValueError("reference array terrain hash does not match fixed assignment")
    with np.load(arrays_path, allow_pickle=False) as arrays:
        required = {"fwd", "alive", "pos", "dones", "dt", "tile_len_m"}
        if not required.issubset(arrays.files):
            raise ValueError("reference arrays are missing required sparse fields")
        fwd = np.asarray(arrays["fwd"], dtype=np.float64)
        alive = np.asarray(arrays["alive"], dtype=bool)
        pos = np.asarray(arrays["pos"], dtype=np.float64)
        dt = float(arrays["dt"])
        tile_len = float(arrays["tile_len_m"])
    steps = int(meta.get("steps", 0))
    if fwd.shape != (steps, env_count) or alive.shape != fwd.shape or pos.shape != (steps, env_count, 3):
        raise ValueError("reference array shapes do not match map_modes envs/steps")
    if not math.isclose(dt, 0.02, abs_tol=1e-9) or steps != 900 or not math.isclose(tile_len, 8.0, abs_tol=1e-9):
        raise ValueError("reference is not the 900-step, 0.02s, 8m sparse evaluation")
    fell = np.logical_or.accumulate((pos[:, :, 2] < fall_height_m) & alive, axis=0)
    usable = alive & ~fell
    maximum = np.where(usable, fwd, -np.inf).max(axis=0)
    maximum = np.where(np.isfinite(maximum), maximum, 0.0)
    crossed = maximum >= threshold_m
    fell_any = fell[-1]
    candidates = []
    for tile in tiles:
        env_id = int(tile["env"])
        if tile.get("kind") != kind or int(tile.get("level", -1)) != level:
            continue
        candidates.append({"env_id": env_id, "kind": kind, "level": level,
                           "col": int(tile["col"]), "crossed": bool(crossed[env_id]),
                           "fell": bool(fell_any[env_id]), "fwd_max_m": float(maximum[env_id]),
                           "alive_at_end": bool(alive[-1, env_id])})
    by_cell: dict[int, list[dict[str, Any]]] = {}
    for row in candidates:
        by_cell.setdefault(row["col"], []).append(row)
    pairs = []
    for col, rows in sorted(by_cell.items()):
        crossings = [row for row in rows if row["crossed"] and not row["fell"]]
        falls = [row for row in rows if row["fell"] and not row["crossed"]]
        if crossings and falls:
            pairs.append((crossings[0], falls[0]))
    if not pairs:
        raise ValueError("no same fixed cell has one crossing and one fall")
    crossed_row, fell_row = pairs[0]
    return {"terrain_set": "sparse50", "map_mode": mode, "fixed_level": level,
            "kind": kind, "col": crossed_row["col"],
            "crossed_env": crossed_row["env_id"], "fell_env": fell_row["env_id"],
            "crossed_env_fwd_max_m": crossed_row["fwd_max_m"],
            "fell_env_fwd_max_m": fell_row["fwd_max_m"],
            "threshold_m": threshold_m, "fall_height_m": fall_height_m,
            "candidate_rows": candidates}


def validate_w03_reference(spec: dict[str, Any]) -> dict[str, Any]:
    """W03: the chosen env must come from the canon's own 300-step eval_gt fwd1.0 arrays by the pre-registered rule (SELECTION_RULE.md)."""
    import numpy as np

    path = Path(spec["reference_arrays"])
    if _sha(path) != spec["reference_arrays_sha256"]:
        raise ValueError("w03 reference arrays SHA256 differs from the selection record")
    if not path.name.startswith("env_arrays_eval_gt_fwd1.0"):
        raise ValueError("w03 reference must be the eval_gt fwd1.0 arrays")
    with np.load(path, allow_pickle=True) as z:
        env = int(spec["env_id"])
        row = {"kind": str(z["kind"][env]), "level": int(z["terrain_level"][env]), "col": int(z["terrain_col"][env]),
               "alive_end": bool(z["alive_end"][env]), "fwd_end_m": float(z["fwd_end_m"][env]), "body_vx_integral_m": float(z["body_vx_integral_m"][env]), "n_env": int(len(z["kind"]))}
        ids = np.where((z["kind"].astype(str) == spec["kind"]) & (z["terrain_level"].astype(int) == row["level"]))[0]
        succ = [int(i) for i in ids if bool(z["alive_end"][i]) and float(z["body_vx_integral_m"][i]) >= W03_SUCCESS_FWD_M]
        fail = [int(i) for i in ids if not bool(z["alive_end"][i])]
    if row["n_env"] != SPARSE_ENV_COUNT or row["kind"] != spec["kind"] or row["col"] != spec["col"]:
        raise ValueError("w03 selected env kind/column differs from the evaluation arrays")
    if spec.get("terrain_set") == W03_FIXED_LEVEL_KINDS and spec.get("map64_levels") is not True and row["level"] != spec["fixed_level"]:
        raise ValueError("w03 selected env level differs from the evaluation arrays")
    if spec.get("terrain_set") == "sparse50" and row["level"] != spec["fixed_level"]:
        raise ValueError("w03 selected env level differs from the evaluation arrays")
    expected = (succ if spec["selection_role"] == "success" else fail)
    if not expected or expected[0] != env:
        raise ValueError("w03 selected env is not the lowest-numbered env of its role under the registered rule")
    return {"rule": "SELECTION_RULE.md", "role": spec["selection_role"], "env_row": row, "n_success": len(succ), "n_fail": len(fail),
            "reference_arrays": str(path.resolve()), "reference_arrays_sha256": spec["reference_arrays_sha256"], "success_fwd_m": W03_SUCCESS_FWD_M,
            "evaluation_source_sha256": {}}


def validate_sparse_reference(spec: dict[str, Any]) -> dict[str, Any]:
    """Tie the requested capture env/mode to a verified existing eval result."""
    path = Path(spec["reference_eval_json"])
    arrays_path = Path(spec["reference_arrays"])
    meta = json.loads(path.read_text(encoding="utf-8"))
    if meta.get("terrain_set") != "sparse50" or meta.get("envs") != SPARSE_ENV_COUNT:
        raise ValueError("sparse capture reference must be the 64-env sparse50 run")
    fixed = meta.get("fixed_terrain", {})
    geometry = meta.get("terrain_geometry_sha256", {})
    if fixed.get("fixed_level") != spec["fixed_level"] or geometry.get("seed") != SPARSE_GEOMETRY_SEED:
        raise ValueError("sparse capture level or geometry seed differs from reference")
    if meta.get("checkpoint_sha256") != spec.get("checkpoint_sha256"):
        raise ValueError("sparse capture checkpoint SHA differs from the reference evaluation")
    selection = select_sparse_env_pair(path, arrays_path, kind=spec["kind"],
                                       level=spec["fixed_level"])
    if selection["map_mode"] != "probe_prop_only":
        raise ValueError("selection reference must use the map-masked evaluation arrays")
    if selection["col"] != spec["col"]:
        raise ValueError("selected sparse tile column differs from the evaluation result")
    expected_env = selection["crossed_env"] if spec["selection_role"] == "crossed" else selection["fell_env"]
    if expected_env != spec["env_id"]:
        raise ValueError("selected env does not match the derived crossing/fall role")
    tile = next((row for row in fixed.get("tiles", []) if row.get("env") == expected_env), None)
    if not tile or tile.get("kind") != spec["kind"] or tile.get("level") != spec["fixed_level"] or tile.get("col") != spec["col"]:
        raise ValueError("selected env is not on the requested fixed terrain cell")
    source_hashes = meta.get("source_sha256", {})
    root = Path(spec["eval_root"])
    source_paths = {
        "foothold_s2.eval.eval_map_modes": "foothold_s2/eval/eval_map_modes.py",
        "foothold_s2.eval.adapters": "foothold_s2/eval/adapters.py",
        "foothold_s2.eval.fixed_terrain": "foothold_s2/eval/fixed_terrain.py",
        "foothold_s2.eval.geometry_hash": "foothold_s2/eval/geometry_hash.py",
        "foothold_s2.eval.kind_stats": "foothold_s2/eval/kind_stats.py",
        "foothold_s2.terrains.sparse_terrains": "foothold_s2/terrains/sparse_terrains.py",
        "foothold_s2.terrains.columns": "foothold_s2/terrains/columns.py",
        "foothold_s2.terrains.rough_go2_cfg": "foothold_s2/terrains/rough_go2_cfg.py",
    }
    verified_sources = {}
    for module, relative in source_paths.items():
        source = root / relative
        if not source.is_file() or module not in source_hashes:
            raise ValueError(f"sparse evaluation source missing from reference: {module}")
        digest = _sha(source)
        if not digest.startswith(source_hashes[module]):
            raise ValueError(f"sparse evaluation source SHA differs from reference: {module}")
        verified_sources[relative] = digest
    return {"selection": selection, "tile": tile, "reference_checkpoint_sha256": meta["checkpoint_sha256"],
            "evaluation_source_sha256": verified_sources, "reference_json": str(path.resolve()),
            "reference_arrays": str(arrays_path.resolve())}


def configure_sparse_evaluation_config(env_cfg: Any, generator: Any) -> dict[str, Any]:
    """Apply the same 64-env sparse eval switches without changing reset/start ranges."""
    env_cfg.scene.num_envs = SPARSE_ENV_COUNT
    if generator is not None:
        env_cfg.scene.terrain.terrain_generator = generator
    dr_off = []
    for name in ("actuator_gains", "motor_strength", "physics_material", "add_base_mass",
                 "base_com", "push_robot", "base_external_force_torque"):
        if getattr(env_cfg.events, name, None) is not None:
            setattr(env_cfg.events, name, None)
            dr_off.append(name)
    action_delay = getattr(getattr(env_cfg, "actions", None), "joint_pos", None)
    if action_delay is not None and hasattr(action_delay, "max_delay_s"):
        action_delay.max_delay_s = 0.0
        dr_off.append("action_delay")
    curriculum_off = []
    for name in ("terrain_levels", "command_range"):
        if getattr(env_cfg.curriculum, name, None) is not None:
            setattr(env_cfg.curriculum, name, None)
            curriculum_off.append(name)
    env_cfg.commands.base_velocity.resampling_time_range = (LONG_COMMAND_RESAMPLE_S, LONG_COMMAND_RESAMPLE_S)
    return {"mode": "sparse_eval_reference", "dr_off": dr_off,
            "curriculum_off": curriculum_off, "action_delay_ticks": 0,
            "start_ranges_preserved": True, "applied_config": _plain_config(env_cfg)}


def _git_value(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
    if result.returncode:
        raise ValueError("source root git identity could not be verified")
    return result.stdout.strip()


def validate_source_root(root: Path, experiment: str | None = None,
                         source_profile: str | None = None) -> dict[str, str]:
    root = root.resolve()
    source = root / "foothold_s2/eval/record_sol23f.py"
    if source_profile is None:
        if not source.is_file() or _sha(source) != BASE_RECORDER_SHA256:
            raise ValueError("fixed SOL-23f recorder source SHA mismatch")
        checked = {"foothold_s2/eval/record_sol23f.py": _sha(source)}
    elif source_profile == W03_PROFILE:
        if root.as_posix().casefold() != Path(W03_SOURCE_ROOT).as_posix().casefold():
            raise ValueError("W03 source profile root path mismatch")
        if not source.is_file() or _sha(source) != W03_RECORDER_SHA256:
            raise ValueError("W03 fixed recorder source SHA mismatch")
        head = _git_value(root, "rev-parse", "HEAD")
        tracked = subprocess.run(["git", "-C", str(root), "diff", "--quiet", "HEAD", "--"], capture_output=True, check=False)
        if head != W03_SOURCE_HEAD or tracked.returncode:
            raise ValueError("W03 pinned source head or tracked files mismatch")
        checked = {"profile": W03_PROFILE, "git_head": head, "tracked_files_clean": "true",
                   "foothold_s2/eval/record_sol23f.py": _sha(source)}
    elif source_profile == EX35_SOURCE_PROFILE:
        if experiment != "SB":
            raise ValueError("EX-35 source profile is only registered for S-B")
        if root.as_posix().casefold() != Path(EX35_SOURCE_ROOT).as_posix().casefold():
            raise ValueError("EX-35 source profile root path mismatch")
        if not source.is_file() or _sha(source) != EX35_RECORDER_SHA256:
            raise ValueError("EX-35 fixed recorder source SHA mismatch")
        head = _git_value(root, "rev-parse", "HEAD")
        tree = _git_value(root, "rev-parse", "HEAD^{tree}")
        tracked = subprocess.run(["git", "-C", str(root), "diff", "--quiet", "HEAD", "--"],
                                 capture_output=True, check=False)
        staged = subprocess.run(["git", "-C", str(root), "diff", "--cached", "--quiet"],
                                capture_output=True, check=False)
        if head != EX35_SOURCE_HEAD or tree != EX35_SOURCE_TREE or tracked.returncode or staged.returncode:
            raise ValueError("EX-35 pinned source tree identity or tracked files mismatch")
        checked = {"profile": EX35_SOURCE_PROFILE, "git_head": head, "git_tree": tree,
                   "tracked_files_clean": "true",
                   "foothold_s2/eval/record_sol23f.py": _sha(source)}
        for relative, digest in EX35_SOURCE_FILE_SHA256.items():
            path = root / relative
            actual = _sha(path) if path.is_file() else None
            if actual != digest:
                raise ValueError("EX-35 pinned source SHA mismatch: " + relative)
            checked[relative] = actual
    else:
        raise ValueError("unregistered source profile")
    if experiment in ("G0B", "SB"):
        task_name = "g0b_tasks.py" if experiment == "G0B" else "sb_tasks.py"
        task_id = "FootholdS2-Go2-S2-G0B-v0" if experiment == "G0B" else "FootholdS2-Go2-S2-SB-v0"
        task = root / "foothold_s2" / task_name
        if not task.is_file() or task_id not in task.read_text(encoding="utf-8"):
            raise ValueError(f"{experiment} task registration source mismatch")
        checked[str(task.relative_to(root)).replace("\\", "/")] = _sha(task)
        if experiment == "SB":
            adapter = root / "foothold_s2/eval/adapters.py"
            content = adapter.read_text(encoding="utf-8") if adapter.is_file() else ""
            for token in ('"probe_prop_only"', "mask_map_tokens = self.map_mode == \"probe_prop_only\"", "eval_gt"):
                if token not in content:
                    raise ValueError("S-B map-mode adapter contract is missing")
            checked["foothold_s2/eval/adapters.py"] = _sha(adapter)
    return checked


def validate_checkpoint_profile(spec: dict[str, Any], checkpoint: Path) -> dict[str, str] | None:
    if spec.get("source_profile") is None:
        return None
    if spec["source_profile"] == W03_PROFILE:
        digest = _sha(checkpoint.resolve())
        if digest != spec.get("checkpoint_sha256"):
            raise ValueError("W03 checkpoint SHA differs from the selection record")
        return {"profile": W03_PROFILE, "checkpoint": str(checkpoint.resolve()), "checkpoint_sha256": digest}
    if spec["source_profile"] != EX35_SOURCE_PROFILE:
        raise ValueError("unregistered checkpoint source profile")
    checkpoint = checkpoint.resolve()
    if checkpoint.as_posix().casefold() != Path(EX35_CHECKPOINT).as_posix().casefold():
        raise ValueError("EX-35 source profile checkpoint path mismatch")
    digest = _sha(checkpoint)
    if digest != EX35_CHECKPOINT_SHA256:
        raise ValueError("EX-35 source profile checkpoint SHA mismatch")
    return {"profile": EX35_SOURCE_PROFILE, "checkpoint": str(checkpoint),
            "checkpoint_sha256": digest}


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


def step_contract(dt: float, duration_s: float = 12.0, fps: int = 25,
                  commands: Any = None) -> dict[str, Any]:
    active_commands = tuple(COMMANDS if commands is None else commands)
    steps = int(round(duration_s / dt))
    indices = frame_steps(steps, int(round(duration_s * fps)))
    command_rows = []
    start_s = 0.0
    for name, cmd, span in active_commands:
        command_rows.append({"name": name, "target": list(cmd), "start_s": start_s,
                             "duration_s": span})
        start_s += float(span)
    if not math.isclose(start_s, duration_s, abs_tol=1e-6):
        raise ValueError("command spans must sum to capture duration")
    return {
        "duration_s": duration_s, "physics_dt_s": dt, "physics_steps": steps,
        "video_fps": fps, "video_frames": len(indices), "video_sample_step_indices": indices,
        "commands": command_rows,
        "policy_modes": {"latent": "mean", "action": "mean"},
    }


def still_probe_contract(dt: float, at_s: float = 6.0, frame_count: int = 3,
                         fps: int = 25, commands: Any = None) -> dict[str, Any]:
    """Short deterministic physics prefix with a few frames around one timestamp."""
    active = tuple(COMMANDS if commands is None else commands)
    if not math.isfinite(dt) or dt <= 0 or not math.isfinite(at_s) or at_s < 0:
        raise ValueError("still probe time and physics dt must be finite and nonnegative")
    if type(frame_count) is not int or frame_count < 1 or fps < 1:
        raise ValueError("still probe frame count and fps must be positive integers")
    steps_per_frame = 1.0 / (dt * fps)
    if not math.isclose(steps_per_frame, round(steps_per_frame), abs_tol=1e-9):
        raise ValueError("still probe requires an integer physics-step interval per video frame")
    stride = int(round(steps_per_frame))
    first = int(round(at_s / dt))
    indices = [first + i * stride for i in range(frame_count)]
    duration = (indices[-1] + 1) * dt
    rows = []
    start = 0.0
    remaining = duration
    for name, command, span in active:
        if remaining <= 0:
            break
        used = min(float(span), remaining)
        rows.append({"name": name, "target": list(command), "start_s": start,
                     "duration_s": used})
        start += used
        remaining -= used
    if remaining > 1e-9:
        raise ValueError("still probe extends beyond configured commands")
    truncated = tuple((row["name"], tuple(row["target"]), row["duration_s"]) for row in rows)
    return {"duration_s": duration, "physics_dt_s": dt,
            "physics_steps": indices[-1] + 1, "video_fps": fps,
            "video_frames": frame_count, "video_sample_step_indices": indices,
            "commands": rows, "probe": {"sample_center_s": at_s,
                                           "frame_times_s": [i * dt for i in indices]},
            "active_commands": truncated,
            "policy_modes": {"latent": "mean", "action": "mean"}}


def brightness_summary(samples: Any) -> dict[str, float | None]:
    """Summarize per-frame RGB means, leaving empty captures explicitly unmeasured."""
    values = [float(value) for value in samples]
    if not values:
        return {"min_mean_brightness": None, "mean_mean_brightness": None}
    return {"min_mean_brightness": min(values),
            "mean_mean_brightness": sum(values) / len(values)}


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
    parser.add_argument("--scene", choices=("flat", "rough", "sparse"), required=True)
    parser.add_argument("--mp4", required=True)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=int, default=25)
    parser.add_argument("--physics-mode", choices=("fixed", "training"))
    parser.add_argument("--lighting-profile", choices=("inherit", "current_plus_directional", "three_point",
                                                        "dome", "dome_plus_three_point"), default="inherit")
    parser.add_argument("--directional-light-intensity", type=float)
    parser.add_argument("--directional-light-angle-deg", type=float, default=1.0)
    parser.add_argument("--directional-light-azimuth-deg", type=float, default=45.0)
    parser.add_argument("--directional-light-elevation-deg", type=float, default=45.0)
    parser.add_argument("--directional-light-shadows", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--three-point-intensity", type=float)
    parser.add_argument("--three-point-angle-deg", type=float, default=12.0)
    parser.add_argument("--three-point-elevation-deg", type=float, default=45.0)
    parser.add_argument("--three-point-shadows", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dome-intensity", type=float)
    parser.add_argument("--overlay-saturation", type=float, choices=(1.0, 1.25, 1.5), default=1.0,
                        help="HSV saturation multiplier for recorder overlay markers only")
    parser.add_argument("--still-probe-at-s", type=float,
                        help="capture only a few frames around this simulated time; not a seq_video receipt")
    parser.add_argument("--still-probe-frames", type=int, default=3)
    parser.add_argument("--plan-only", action="store_true", help="print CPU plan without importing Kit")
    return parser


def _source_hashes(repo: Path, experiment: str) -> dict[str, str]:
    files = ["foothold_s2/eval/record_sol23f.py", "foothold_s2/eval/adapters.py",
             "foothold_s2/eval/seq_video.py", "foothold_s2/eval/runtime.py",
             "foothold_s2/runners/start_runner.py", "foothold_s2/models/start_perception.py",
             "foothold_s2/x23f_tasks.py"]
    if experiment == "B":
        files += ["foothold_s2/tasks/s2_23f_b_cfg.py", "foothold_s2/tasks/s2_x23_cfg.py"]
    elif experiment in ("G0B", "SB"):
        files += ["foothold_s2/g0b_tasks.py" if experiment == "G0B" else "foothold_s2/sb_tasks.py",
                  "foothold_s2/tasks/s2_g0b_cfg.py" if experiment == "G0B" else "foothold_s2/tasks/s2_sb_cfg.py",
                  "foothold_s2/eval/adapters.py", "foothold_s2/tasks/s2_23f_b_cfg.py",
                  "foothold_s2/tasks/s2_x23_cfg.py"]
    else:
        files += ["foothold_s2/tasks/s2_23f_topdown_cfg.py",
                                          "foothold_s2/tasks/s2_23f_topdown_env.py",
                                          "foothold_s2/terrains/sol23f_topdown.py",
                                          "foothold_s2/terrains/s2_layout.py"]
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


def _w33b_cache_args(existing: str) -> str:
    # Load the adjacent next-run adapter, without changing policy import paths.
    import importlib.util
    path = Path(__file__).resolve().parents[2] / "kit_cache_next.py"
    loader = importlib.util.spec_from_file_location("_w33b_cache_next", path)
    adapter = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(adapter)
    return adapter.with_cache(["--kit_args", existing])[-1].split("=", 1)[1]


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
    full_args.kit_args = _w33b_cache_args(full_args.kit_args)
    full_args.enable_cameras = True
    _app = AppLauncher(full_args).app
    import carb.settings
    print("W33B_CACHE_EFFECTIVE", carb.settings.get_settings().get("/UJITSO/datastore/localCachePath"), flush=True)
    repo = Path(spec["source_root"]).resolve()
    source_gate = validate_source_root(repo, spec["experiment"], spec.get("source_profile"))
    checkpoint_profile = validate_checkpoint_profile(spec, Path(full_args.checkpoint))
    sparse_capture = spec.get("terrain_set") in ("sparse50", W03_FIXED_LEVEL_KINDS)
    fixed64_capture = spec.get("terrain_set") == W03_FIXED_LEVEL_KINDS
    eval_root = Path(spec["eval_root"]).resolve() if sparse_capture else repo
    sys.path.insert(0, str(eval_root))
    if eval_root != repo:
        sys.path.insert(1, str(repo))
    env = None
    container = None
    try:
        import gymnasium as gym
        importlib.import_module("isaaclab_tasks")
        from isaaclab_tasks.utils import load_cfg_from_registry
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        if spec["experiment"] in ("B", "TD"):
            importlib.import_module("foothold_s2.x23f_tasks")
        elif spec["experiment"] == "G0B":
            importlib.import_module("foothold_s2.g0b_tasks")
        else:
            importlib.import_module("foothold_s2.sb_tasks")
        from foothold_s2.eval import adapters, terrain_sets

        task_id = {
            "B": "FootholdS2-Go2-S2-23f-B-v0",
            "TD": "FootholdS2-Go2-S2-23f-TopDown-v0",
            "G0B": "FootholdS2-Go2-S2-G0B-v0",
            "SB": "FootholdS2-Go2-S2-SB-v0",
        }[spec["experiment"]]
        env_cfg = load_cfg_from_registry(task_id, "env_cfg_entry_point")
        agent_cfg = load_cfg_from_registry(task_id, "rsl_rl_cfg_entry_point")
        seed, device = spec["seed"], full_args.device
        env_cfg.seed = seed
        env_cfg.scene.num_envs = SPARSE_ENV_COUNT if sparse_capture else 1
        if not sparse_capture:
            env_cfg.episode_length_s = 14.0
        env_cfg.sim.device = device
        if sparse_capture:
            from foothold_s2.eval import geometry_hash as sparse_geometry_hash
            from foothold_s2.terrains import columns as sparse_columns
            from foothold_s2.terrains import sparse_terrains
            from foothold_s2.terrains.rough_go2_cfg import build_generator, continuous_subterrains
            sparse_terrains.SIDE_TABLE.__init__()
            generator = build_generator(
                {**continuous_subterrains(), **sparse_terrains.sparse_subterrains()},
                sparse_columns.FULL_COLS, seed=sparse_geometry_hash.SPARSE_GEOMETRY_SEED)
            if not fixed64_capture and sparse_geometry_hash.SPARSE_GEOMETRY_SEED != spec["geometry_seed"]:
                raise RuntimeError("sparse terrain geometry seed changed from the eval reference")
            physics_record = configure_sparse_evaluation_config(env_cfg, None if fixed64_capture else generator)
            start_record = ({"yaw_override_rad": None, "source": "continuous evaluation reset (random yaw kept, as in eval_map_modes)", "reset_ranges_preserved": True}
                            if fixed64_capture else {"yaw_override_rad": 0.0, "source": "sparse evaluation reset and quaternion override", "reset_ranges_preserved": True})
            task_selection = {"terrain_set": "sparse50", "fixed_terrain": True,
                              "fixed_level": spec["fixed_level"], "envs": SPARSE_ENV_COUNT,
                              "env_id": spec["env_id"], "kind": spec["kind"], "col": spec["col"],
                              "geometry_seed": spec.get("geometry_seed"), "selection_role": spec["selection_role"]}
            if fixed64_capture:
                task_selection["terrain_set"] = W03_FIXED_LEVEL_KINDS
        else:
            physics_record = configure_physics_mode(env_cfg, spec["physics_mode"])
            start_record = configure_capture_start(env_cfg)
        env_cfg.viewer.resolution = (full_args.width, full_args.height)
        agent_cfg.seed, agent_cfg.device = seed, device
        if sparse_capture:
            pass
        elif spec["experiment"] in ("B", "G0B", "SB"):
            terrain = spec.get("terrain", full_args.scene)
            if terrain != full_args.scene:
                raise ValueError("B terrain in JSON must match seq_video scene argument")
            terrain_type = spec.get("terrain_type")
            if terrain_type:
                generator = terrain_sets.merged_generator([terrain_type], 0.5, seed)
            else:
                generator = terrain_sets.merged_generator(["random_rough"], 0.5, seed)
                generator.sub_terrains["random_rough"].noise_range = (
                    (0.0, 0.003) if terrain == "flat" else (0.01, 0.06))
            env_cfg.scene.terrain.terrain_generator = generator
            env_cfg.scene.terrain.max_init_terrain_level = 0
            env_cfg.curriculum.terrain_levels = None
            task_selection = {"terrain": terrain,
                              "terrain_generator": terrain_type or "random_rough",
                              "terrain_type": terrain_type,
                              "noise_range": (None if terrain_type else
                                              list(generator.sub_terrains["random_rough"].noise_range)),
                              "difficulty": 0.5, "seed": seed,
                              "start_offset_x_m": start_record["offset_x_m"]}
        else:
            generator = env_cfg.scene.terrain.terrain_generator
            generator.seed = seed
            from foothold_s2.sensors.start_obs import AUG
            configure_topdown_evaluation(env_cfg, AUG)
            task_selection = None

        command_cfg = env_cfg.commands.base_velocity
        command_cfg.fixed_cmd = SPARSE_COMMAND[1] if sparse_capture else COMMANDS[0][1]
        command_cfg.resampling_time_range = (LONG_COMMAND_RESAMPLE_S, LONG_COMMAND_RESAMPLE_S)

        gym_env = gym.make(task_id, cfg=env_cfg, render_mode="rgb_array")
        raw = gym_env.unwrapped
        lighting_record = lighting_profile_settings(
            full_args.lighting_profile, intensity=full_args.directional_light_intensity,
            angle_deg=full_args.directional_light_angle_deg,
            azimuth_deg=full_args.directional_light_azimuth_deg,
            elevation_deg=full_args.directional_light_elevation_deg,
            shadows=full_args.directional_light_shadows,
            three_point_intensity=full_args.three_point_intensity,
            three_point_angle_deg=full_args.three_point_angle_deg,
            three_point_elevation_deg=full_args.three_point_elevation_deg,
            three_point_shadows=full_args.three_point_shadows,
            dome_intensity=full_args.dome_intensity)
        lighting_record = apply_lighting_profile(lighting_record)
        if spec["experiment"] == "TD":
            task_selection = _configure_topdown(raw, spec["terrain_type"], spec["level"], seed)
        env = RslRlVecEnvWrapper(gym_env, clip_actions=agent_cfg.clip_actions)
        adapter = adapters.S2Adapter("open")
        if spec["experiment"] == "SB":
            adapter.map_mode = spec["map_mode"]
        built = {"gym_env": gym_env, "raw": raw, "env_cfg": env_cfg, "agent_cfg": agent_cfg,
                 "env": env}
        env, policy, policy_nn, obs = adapter.load_policy(built, full_args.checkpoint)
        runner = policy.runner
        # Do not inherit S2_Z/S2_ACT from a launcher shell: this protocol is mean/mean.
        policy.z_mode, policy.act_mode = spec["z_mode"], spec["act_mode"]
        delay_record = validate_depth_delay(spec["experiment"], int(runner.perception.cfg.depth_delay_ticks))
        saved_gt = bool(runner.perception.cfg.force_gt)
        if spec["experiment"] in ("G0B", "SB"):
            map_input = runner.pcfg.get("map_input", "none")
            if spec["experiment"] == "G0B":
                if map_input != "none" or policy.map_mode is not None:
                    raise RuntimeError("G0B must have no policy map input")
                expected_gt = False
                map_record = {"requested": "none", "effective_use_gt": False,
                              "policy_map_tokens": "absent", "map_input": map_input}
            else:
                if map_input == "none" or policy.map_mode != spec["map_mode"]:
                    raise RuntimeError("S-B checkpoint or adapter map mode mismatch")
                expected_gt = spec["map_mode"] == "eval_gt"
                map_record = {"requested": spec["map_mode"], "effective_use_gt": expected_gt,
                              "policy_map_tokens": "masked" if spec["map_mode"] == "probe_prop_only" else "present",
                              "map_input": map_input}
            assert_map_mode(policy, expected_gt)
        else:
            map_record = apply_map_mode(policy, spec["map_mode"], runner.pcfg.get("map_input", "none"), saved_gt)
            expected_gt = map_record["effective_use_gt"]
        sparse_reference = None
        sparse_assignment = None
        if sparse_capture:
            from foothold_s2.eval import fixed_terrain as sparse_fixed_terrain
            torch.manual_seed(SPARSE_EVAL_SEED)
            env.reset()
            if fixed64_capture:
                level_arg = None if spec.get("map64_levels") is True else spec["fixed_level"]
                sparse_assignment = sparse_fixed_terrain.apply(raw, level_arg)
                env.reset()
                _lv, _ty = sparse_fixed_terrain.fixed_assignment(raw.num_envs, sparse_assignment["rows"], sparse_assignment["cols"], level_arg)
                _cols = raw.scene.terrain.terrain_types.cpu().numpy()
                if int(_cols[spec["env_id"]]) != spec["col"] or int(raw.scene.terrain.terrain_levels[spec["env_id"]].item()) != int(_lv[spec["env_id"]]):
                    raise RuntimeError("selected env does not have the reference fixed64 cell")
                tile = {"env": spec["env_id"], "kind": spec["kind"], "level": int(_lv[spec["env_id"]]), "col": spec["col"]}
            else:
                sparse_assignment = sparse_fixed_terrain.apply_sparse(raw, spec["fixed_level"])
                env.reset()
                tiles = sparse_assignment.get("tiles", [])
                tile = next((row for row in tiles if int(row.get("env", -1)) == spec["env_id"]), None)
                if not tile or tile.get("kind") != spec["kind"] or tile.get("level") != spec["fixed_level"] or tile.get("col") != spec["col"]:
                    raise RuntimeError("selected env does not have the reference sparse fixed cell")
            if int(raw.num_envs) != SPARSE_ENV_COUNT or float(env_cfg.episode_length_s) < 18.0:
                raise RuntimeError("sparse capture env count or episode length cannot cover the evaluation window")
            robot = raw.scene["robot"]
            state = robot.data.root_state_w.clone()
            if not fixed64_capture:
                state[:, 3:7] = torch.tensor([1.0, 0.0, 0.0, 0.0], device=raw.device)
                state[:, 7:] = 0.0
                robot.write_root_pose_to_sim(state[:, :7])
                robot.write_root_velocity_to_sim(state[:, 7:])
            yaw = torch.atan2(2.0 * (robot.data.root_quat_w[:, 0] * robot.data.root_quat_w[:, 3] +
                                     robot.data.root_quat_w[:, 1] * robot.data.root_quat_w[:, 2]),
                              1.0 - 2.0 * (robot.data.root_quat_w[:, 2] ** 2 + robot.data.root_quat_w[:, 3] ** 2))
            if not fixed64_capture and yaw.abs().max().item() > 1.0e-3:
                raise RuntimeError("sparse capture start yaw is not +x")
            sparse_command_term = raw.command_manager.get_term("base_velocity")
            pin_segment_command(command_cfg, sparse_command_term, SPARSE_COMMAND[1])
            sparse_reference = validate_w03_reference(spec) if spec.get("w03_reference") is True else validate_sparse_reference(spec)
            task_selection["fixed_assignment"] = sparse_assignment
            task_selection["selected_tile"] = tile
            task_selection["reference"] = sparse_reference
            start_record["yaw_readback_max_abs_rad"] = float(yaw.abs().max().item())
        else:
            raw.reset()
        policy.reset(torch.ones(env.num_envs, dtype=torch.bool, device=raw.device))
        assert_map_mode(policy, expected_gt)
        obs = env.get_observations()

        # Capture the same observation tick that feeds the policy, including depth,
        # ground truth, reconstructed rough/refined maps and the actual use_gt mask.
        perception = runner.perception
        original_advance = perception._advance
        map_snapshot: dict[str, Any] = {}
        capture_env_id = int(spec["env_id"]) if sparse_capture else 0
        render_visibility_record = {"enabled": False, "reason": "single-environment capture"}
        if sparse_capture and spec.get("hide_others"):
            import omni.usd
            render_visibility_record = hide_nonselected_robot_roots(
                omni.usd.get_context().get_stage(), env_cfg.scene.robot.prim_path,
                capture_env_id, SPARSE_ENV_COUNT, keep_env_ids=(0,))
            render_visibility_record["kept_env_ids"] = [0, capture_env_id]

        def tapped_advance(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map):
            result = original_advance(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map)
            out = result[2]
            def row(values):
                if values is None or not values.numel():
                    return np.empty((0,), dtype=np.float32)
                return values[capture_env_id].reshape(-1).detach().float().cpu().numpy()
            map_snapshot.clear()
            map_snapshot.update({"depth": depth2[capture_env_id, -1].detach().float().cpu().numpy(),
                                 "gt_map": gt_map[capture_env_id].detach().float().cpu().numpy(),
                                 "rough_map": row(out.get("rough")),
                                 "refined_map": row(out.get("refined")),
                                 "use_gt": bool(use_gt[capture_env_id].item()),
                                 "first_after_reset": bool(first[capture_env_id].item())})
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
                termination_snapshot[term_name] = bool(value[capture_env_id].item())
            return done_result

        manager.compute = capture_termination
        robot = raw.scene["robot"]
        target_marker_op = None
        target_marker_record = {"enabled": False, "reason": "single-environment capture"}
        if sparse_capture and not spec.get("hide_others"):
            import omni.usd
            target_marker_op, target_marker_record = define_target_marker(
                omni.usd.get_context().get_stage())
        sensor = raw.scene.sensors["contact_forces"]
        foot_robot_ids, foot_names = robot.find_bodies(".*_foot")
        foot_sensor_ids, sensor_names = sensor.find_bodies(".*_foot")
        if len(foot_robot_ids) != 4 or len(foot_sensor_ids) != 4 or foot_names != sensor_names:
            raise RuntimeError("four matching foot bodies are required")
        command_term = raw.command_manager.get_term("base_velocity")
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from overlay_25e import SceneOverlay, LEGEND
        overlay = SceneOverlay(raw, robot, foot_robot_ids, perception, env_index=capture_env_id,
                               saturation_multiplier=full_args.overlay_saturation)
        overlay_info: list[dict[str, Any]] = []
        step_dt = float(raw.step_dt)
        active_commands = (SPARSE_COMMAND,) if sparse_capture else (WALK_TURN_COMMANDS if spec.get("command_profile") == "walk_turn" else COMMANDS)
        capture_duration = float(spec["duration_s"]) if sparse_capture else 12.0
        if sparse_capture and full_args.fps != 25:
            raise ValueError("sparse eval video uses the fixed 25 fps frame contract")
        if full_args.still_probe_at_s is not None:
            if sparse_capture:
                raise ValueError("still probes are currently limited to standard B/TD/G0B/SB scenes")
            contract = still_probe_contract(step_dt, full_args.still_probe_at_s,
                                            full_args.still_probe_frames, full_args.fps,
                                            active_commands)
            active_commands = contract.pop("active_commands")
            capture_duration = contract["duration_s"]
        else:
            contract = step_contract(step_dt, capture_duration, full_args.fps, active_commands)
        step_count, frame_indices = contract["physics_steps"], set(contract["video_sample_step_indices"])
        if len(frame_indices) != contract["video_frames"]:
            raise RuntimeError("capture frame contract is not distinct")
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
        brightness_samples: list[float] = []
        render_retry_checks: list[dict[str, Any]] = []
        resets = 0
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 15)
            small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 12)
        except OSError:
            font = small = ImageFont.load_default()

        def write_command(command: tuple[float, float, float]) -> None:
            pin_segment_command(command_cfg, command_term, command)

        frame = None
        last_segment = None
        refresh_observation = True
        for _ in range(12):
            raw.render()
        for k in range(step_count):
            now_s = k * step_dt
            starts = contract["commands"]
            seg = next((i for i, item in enumerate(starts)
                        if now_s < item["start_s"] + item["duration_s"]), len(active_commands) - 1)
            name, command, _span = active_commands[seg]
            write_command(command)
            if refresh_observation or seg != last_segment:
                obs = env.get_observations()
                refresh_observation = False
                last_segment = seg
            if k in frame_indices:
                robot_pos = robot.data.root_pos_w[capture_env_id].detach().cpu().numpy()
                if target_marker_op is not None:
                    update_target_marker(target_marker_op, robot_pos,
                                         target_marker_record["height_above_root_m"])
                raw.sim.set_camera_view(eye=(robot_pos[0] - 0.6, robot_pos[1] - 1.6, robot_pos[2] + 0.85),
                                        target=(robot_pos[0] + 0.25, robot_pos[1], robot_pos[2] - 0.05))
                oi = overlay.draw(command, map_snapshot)
                overlay_info.append({"physics_tick": k, **oi})
                frame, retry_checks = render_frame_guarded(raw, robot, command_term, sensor,
                                                           env_index=capture_env_id)
                render_retry_checks.extend({"physics_tick": k, **check} for check in retry_checks)
                if frame.shape[:2] != (full_args.height, full_args.width):
                    frame = np.asarray(Image.fromarray(frame).resize((full_args.width, full_args.height)))
                brightness = float(frame.astype(np.float32).mean())
                brightness_samples.append(brightness)
                rgba = Image.fromarray(frame)
                draw = ImageDraw.Draw(rgba, "RGBA")
                draw.rectangle((0, 0, full_args.width, 26), fill=(0, 0, 0, 150))
                actual = robot.data.root_lin_vel_b[capture_env_id].detach().cpu().numpy()
                wz_now = float(robot.data.root_ang_vel_b[capture_env_id, 2])
                used = "GT" if oi.get("used_gt", True) else "reconstructed"
                draw.text((8, 4), f"{full_args.label} | {name} | t={k * step_dt:.2f}s | cmd vx {command[0]:+.2f} wz {command[2]:+.2f} | actual vx {actual[0]:+.2f} wz {wz_now:+.2f} | policy map: {used}", font=font, fill=(255, 255, 255, 255))
                pixels = np.asarray(rgba.convert("RGB"))
                for packet in stream.encode(av.VideoFrame.from_ndarray(pixels, format="rgb24")):
                    container.mux(packet)
                frame_count += 1

            root_pos_w = robot.data.root_pos_w[capture_env_id].detach().cpu().numpy().copy()
            quat = robot.data.root_quat_w[capture_env_id].detach().cpu().numpy().copy()
            roll = math.atan2(2 * (quat[0] * quat[1] + quat[2] * quat[3]), 1 - 2 * (quat[1] ** 2 + quat[2] ** 2))
            pitch = math.asin(max(-1.0, min(1.0, 2 * (quat[0] * quat[2] - quat[3] * quat[1]))))
            foot_xyz = robot.data.body_pos_w[capture_env_id, foot_robot_ids].detach().cpu().numpy()
            forces = sensor.data.net_forces_w[capture_env_id, foot_sensor_ids].detach()
            contact = (torch.linalg.vector_norm(forces, dim=-1) > 1.0).cpu().numpy()
            overlay.record_step(foot_xyz, contact)
            cmd_now = (command_term.commands if hasattr(command_term, "commands") else command_term.vel_command_b)[capture_env_id, :3].detach().cpu().numpy()
            root_v = robot.data.root_lin_vel_b[capture_env_id].detach().cpu().numpy()
            root_w = robot.data.root_ang_vel_b[capture_env_id].detach().cpu().numpy()
            joint_pos = robot.data.joint_pos[capture_env_id].detach().cpu().numpy().copy()

            with torch.inference_mode():
                actions = policy(obs)
                policy_action = actions[capture_env_id].detach().cpu().numpy().copy()
                if map_snapshot:
                    if spec["map_mode"] == "pred" and map_snapshot["use_gt"]:
                        raise RuntimeError("pred mode consumed GT map on a policy tick")
                    map_rows.append({"t": k * step_dt, **map_snapshot})
                obs, _reward, dones, _extras = env.step(actions)
                done = bool(dones[capture_env_id].item())
                terms = dict(termination_snapshot)
                timed_out = bool(getattr(raw, "reset_time_outs", torch.zeros_like(dones))[capture_env_id].item())
                term = termination_record(done, terms, timed_out)
                # These are the last simulated substep's values, not a per-substep trace.
                # A terminal step may already have reset the articulation.
                if not done:
                    joint_target = robot.data.joint_pos_target[capture_env_id].detach().cpu().numpy().copy()
                    applied_torque = robot.data.applied_torque[capture_env_id].detach().cpu().numpy().copy()
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
        if frame_count != contract["video_frames"]:
            raise RuntimeError(f"frame count {frame_count} != {contract['video_frames']}")
        if spec["map_mode"] in ("pred", "eval_pred", "probe_prop_only", "none") and any(row["use_gt"] for row in map_rows):
            raise RuntimeError("selected map-disabled mode must have zero GT use")
        if spec["map_mode"] == "eval_gt" and map_rows and not all(row["use_gt"] for row in map_rows):
            raise RuntimeError("eval_gt mode must use GT at every perception sample")

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
                            seg_s=np.float64(active_commands[0][2]), foot_z=np.asarray(data["foot_xyz"])[:, :, 2],
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
            map_targets = (0.0, 6.0, 12.0, 17.0) if sparse_capture else (0.0, 3.0, 6.0, 9.0)
            selected = [min(map_rows, key=lambda row: abs(row["t"] - target)) for target in map_targets]
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

        segment_observations = segment_observation_rows(data, active_commands)
        mode_observed = {"map_mode": map_record, "gt_use_count": int(sum(bool(row["use_gt"]) for row in map_rows)),
                         "map_samples": len(map_rows),
                         "gt_use_expected_zero": spec["map_mode"] in ("pred", "eval_pred", "probe_prop_only", "none")}
        source_hashes = _source_hashes(repo, spec["experiment"])
        if sparse_capture and sparse_reference:
            source_hashes.update({"sparse_eval:" + name: digest
                                  for name, digest in sparse_reference["evaluation_source_sha256"].items()})
        metadata = {
            "format": "foothold-sol23f-capture/1", "label": full_args.label,
            "scene": full_args.scene, "experiment": spec["experiment"],
            "source_validation": source_gate, "checkpoint_profile": checkpoint_profile,
            "checkpoint": str(Path(full_args.checkpoint).resolve()),
            "checkpoint_sha256": _sha(Path(full_args.checkpoint)),
            "code_sha256": _sha(Path(__file__).resolve()), "sources_sha256": source_hashes,
            "measurement_recorder": {"format": "sol24i/1", "path": str(Path(__file__).resolve()),
                                     "sha256": _sha(Path(__file__).resolve()),
                                     "overlay_sha256": _sha(Path(__file__).resolve().with_name("overlay_25e.py")),
                                     "base_recorder_sha256": BASE_RECORDER_SHA256,
                                      "measurement_base_sha256": MEASUREMENT_RECORDER_SHA256,
                                     "source_root": str(repo),
                                     "sample_time": "pre-step pose/feet/contact/joints and policy action; terminal flag from step",
                                     "height_definition": "root z minus mean contacting foot-center z; NaN without contact",
                                     "actuator_definition": "nonterminal last simulated substep only; terminal rows NaN"},
            "task_id": task_id, "task_selection": task_selection, "seed": spec["seed"],
            "selected_environment": ({"env_id": capture_env_id, "kind": spec["kind"],
                                      "level": spec["fixed_level"], "col": spec["col"],
                                      "selection_role": spec["selection_role"]} if sparse_capture else None),
            "render_visibility": render_visibility_record
            if sparse_capture else {"enabled": False, "reason": "single-environment capture"},
            "target_robot_marker": target_marker_record,
            "capture_start": start_record,
            "segment_observations": segment_observations,
            "policy_modes": {"latent": spec["z_mode"], "action": spec["act_mode"]},
            "lighting": lighting_record,
            "perception_timing": delay_record,
            "map_modes": mode_observed, "step_contract": contract,
            "physics": {**physics_record, "actual_readback": physics_actual_readback(raw)},
            "segments": [[name, list(command), duration] for name, command, duration in active_commands],
            "frames": frame_count, "fps": full_args.fps, "duration_s": capture_duration,
            **brightness_summary(brightness_samples), "brightness_sample_count": len(brightness_samples),
            "capture_mode": ("still_probe_not_seq_video_receipt" if full_args.still_probe_at_s is not None
                             else "sequence"),
            "resets": resets,
            "render_retry_method": "sim.render then raw.render(recompute=True)",
            "render_retry_checks": render_retry_checks,
            "termination_semantics": "reset is recorded with active termination items; no automatic fall label",
            "map_image": ({"name": map_png.name, "receipt_included": False} if map_rows else None),
            "map_arrays": "aligned by map_t in the feet NPZ; empty for checkpoints without reconstruction maps",
            "overlay_25e": {"legend": LEGEND, "attention_hook": overlay.attn_hook_ok,
                            "saturation_multiplier": overlay.saturation_multiplier,
                            "source_sha256": _sha(Path(__file__).resolve().with_name("overlay_25e.py")),
                            "gt_map_vs_ray_hits_max_abs_m": (max(overlay.gt_check) if overlay.gt_check else None),
                            "frames": overlay_info, "attention_rows_per_step": overlay.attn_rows},
            "map_display": {"height_shape": list(HEIGHT_MAP_SHAPE), "height_scale_m": list(HEIGHT_SCALE_M),
                            "depth_scale_m": list(DEPTH_SCALE_M)},
        }
        _json_atomic(output.with_suffix(".json"), metadata)
        print("SOL23F_CAPTURE", json.dumps({"frames": frame_count, "steps": step_count,
                                             "resets": resets, "map_mode": mode_observed,
                                             "mean_mean_brightness": metadata["mean_mean_brightness"],
                                             "min_mean_brightness": metadata["min_mean_brightness"],
                                             "npz": npz_path.name, "map_png": metadata["map_image"]}), flush=True)
    finally:
        if container is not None:
            container.close()


def segment_observation_rows(data: dict[str, list[Any]], commands: Any = None) -> list[dict[str, Any]]:
    """Measured R17 position and stance-foot height spread for each 3-second segment."""
    import numpy as np
    positions = np.asarray(data["root_pos_w"], dtype=np.float64)
    feet_z = np.asarray(data["foot_xyz"], dtype=np.float64)[:, :, 2]
    contact = np.asarray(data["foot_contact"], dtype=np.bool_)
    segments = np.asarray(data["seg"], dtype=np.int64)
    rows = []
    for index, (name, command, duration) in enumerate(COMMANDS if commands is None else commands):
        mask = segments == index
        if not mask.any():
            raise ValueError(f"segment {name} has no sampled physics steps")
        stance_z = feet_z[mask][contact[mask]]
        selected = positions[mask]
        rows.append({
            "name": name, "command": list(command), "duration_s": duration,
            "position_start_m": selected[0].tolist(), "position_end_m": selected[-1].tolist(),
            "position_min_m": selected.min(axis=0).tolist(), "position_max_m": selected.max(axis=0).tolist(),
            "stance_foot_height_std_m": float(np.std(stance_z)) if stance_z.size else None,
            "stance_samples": int(stance_z.size),
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = _argv_parser()
    # Parse known arguments first so the plan-only path does not import Kit.
    args, _remaining = parser.parse_known_args(argv)
    spec = parse_spec(args.policy)
    source_gate = validate_source_root(Path(spec["source_root"]), spec["experiment"], spec.get("source_profile"))
    checkpoint_profile = validate_checkpoint_profile(spec, Path(args.checkpoint))
    try:
        lighting_plan = lighting_profile_settings(
            args.lighting_profile, intensity=args.directional_light_intensity,
            angle_deg=args.directional_light_angle_deg,
            azimuth_deg=args.directional_light_azimuth_deg,
            elevation_deg=args.directional_light_elevation_deg,
            shadows=args.directional_light_shadows,
            three_point_intensity=args.three_point_intensity,
            three_point_angle_deg=args.three_point_angle_deg,
            three_point_elevation_deg=args.three_point_elevation_deg,
            three_point_shadows=args.three_point_shadows,
            dome_intensity=args.dome_intensity)
    except ValueError as exc:
        parser.error(str(exc))
    sparse_reference = None
    if spec.get("terrain_set") in ("sparse50", W03_FIXED_LEVEL_KINDS):
        if args.scene != ("rough" if spec.get("terrain_set") == W03_FIXED_LEVEL_KINDS else "sparse"):
            parser.error("sparse50 capture requires --scene sparse (fixed64: rough)")
        if args.fps != 25:
            parser.error("sparse50 capture uses 25 fps")
        checkpoint = Path(args.checkpoint)
        if not checkpoint.is_file() or _sha(checkpoint) != spec["checkpoint_sha256"]:
            parser.error("sparse50 checkpoint does not match the evaluation SHA256")
        try:
            sparse_reference = validate_w03_reference(spec) if spec.get("w03_reference") is True else validate_sparse_reference(spec)
        except (OSError, ValueError, KeyError) as exc:
            parser.error(f"sparse50 reference verification failed: {exc}")
    if args.physics_mode is not None:
        if spec.get("terrain_set") in ("sparse50", W03_FIXED_LEVEL_KINDS):
            parser.error("sparse50 physics mode is fixed by the evaluation reference")
        spec["physics_mode"] = args.physics_mode
    if args.still_probe_at_s is None and args.still_probe_frames != 3:
        parser.error("--still-probe-frames requires --still-probe-at-s")
    if args.still_probe_at_s is not None:
        try:
            still_probe_contract(0.02, args.still_probe_at_s, args.still_probe_frames, args.fps)
        except ValueError as exc:
            parser.error(str(exc))
    if args.scene != spec.get("terrain", args.scene) and spec["experiment"] == "B":
        parser.error("B JSON terrain and seq_video scene must match")
    if args.plan_only:
        duration = float(spec.get("duration_s", 12.0))
        commands = (SPARSE_COMMAND,) if spec.get("terrain_set") in ("sparse50", W03_FIXED_LEVEL_KINDS) else COMMANDS
        probe_contract = None
        if args.still_probe_at_s is not None:
            probe_contract = still_probe_contract(0.02, args.still_probe_at_s,
                                                  args.still_probe_frames, args.fps, commands)
            duration = probe_contract["duration_s"]
            commands = probe_contract["active_commands"]
            target_frames = probe_contract["video_frames"]
        else:
            target_frames = int(round(duration * args.fps))
        print(json.dumps({"format": "foothold-sol23f-plan/1", "label": args.label,
                          "scene": args.scene, "spec": spec, "commands": commands,
                          "task_id": {"B": "FootholdS2-Go2-S2-23f-B-v0", "TD": "FootholdS2-Go2-S2-23f-TopDown-v0",
                                      "G0B": "FootholdS2-Go2-S2-G0B-v0", "SB": "FootholdS2-Go2-S2-SB-v0"}[spec["experiment"]],
                          "start_offset_x_m": ROUGH_SAFE_START_X_M,
                          "target_frames": target_frames, "duration_s": duration,
                          "still_probe": (probe_contract["probe"] if probe_contract else None),
                          "map_modes": MAP_MODES_BY_EXPERIMENT[spec["experiment"]],
                           "lighting": lighting_plan,
                          "source_validation": source_gate,
                          "checkpoint_profile": checkpoint_profile,
                          "sparse_reference": sparse_reference,
                          "receipt_consumer": (None if probe_contract else "foothold_s2.eval.seq_video"),
                          "seq_video_receipt_compatible": probe_contract is None}, indent=2))
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
