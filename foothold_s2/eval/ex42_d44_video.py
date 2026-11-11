"""Record the approved EX-42 D44 eval_gt and eval_pred cases.

The capture uses one environment on the pinned single evaluation tile.  It is
deliberately a separate Kit child from ex42_d44_eval, so it can be scheduled
after the boundary chain and cannot contend with its evaluator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import traceback

from foothold_s2.eval.ex41_eval_loader import verify_ex41_pose_observation

SCHEMA = "foothold-ex42-d44-video/1"
VIDEO_CASES = ("turn_left_eval_gt", "turn_left_eval_pred",
               "turn_right_eval_gt", "turn_right_eval_pred",
               "stop_restart_eval_gt", "stop_restart_eval_pred")
WIDTH, HEIGHT, FPS = 1280, 720, 25
RENDER_WARMUP_FRAMES = 12


def command_order(task: str) -> tuple[str, ...]:
    if task == "turn_left":
        return ("turn_left_6s",)
    if task == "turn_right":
        return ("turn_right_6s",)
    if task == "stop_restart":
        return ("approach_to_stop_band", "stop_band_hold_2s", "restart_to_top")
    raise ValueError("unknown D44 task")


def command_for_tick(*, task: str, tick: int, settle: int, approach: int,
                     stop: int, turn_rate: float, approach_speed: float,
                     restart_speed: float, stop_band: tuple[float, float],
                     local_x: float, entered: bool) -> tuple[str, tuple[float, float, float], bool]:
    """Pure command schedule for the specifically approved D44 video tasks."""
    if tick < settle:
        return "settle", (0.0, 0.0, 0.0), entered
    if task in ("turn_left", "turn_right"):
        sign = 1.0 if task == "turn_left" else -1.0
        return "landing_turn", (0.0, 0.0, sign * turn_rate), entered
    if task != "stop_restart":
        raise ValueError("unknown D44 task")
    if tick < settle + approach:
        entered = entered or stop_band[0] <= local_x <= stop_band[1]
        command = (0.0, 0.0, 0.0) if entered else (approach_speed, 0.0, 0.0)
        return "approach", command, entered
    if tick < settle + approach + stop:
        return "stop_band_hold", (0.0, 0.0, 0.0), entered
    return "restart_to_top", (restart_speed, 0.0, 0.0), entered


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def build_plan(*, checkpoint: str | Path, plan_path: str | Path,
               output_dir: str | Path, mesh_dir: str | Path,
               expected_checkpoint_sha256: str | None = None) -> dict:
    """CPU-only preflight. Requires the actual m1000 checkpoint and pinned D44 mesh."""
    import yaml
    from foothold_s2.eval.ex42_d44_cells import contract
    from foothold_s2.eval.ex42_eval_tile_mesh import source_tile

    ckpt, plan_file, out, mesh = (Path(checkpoint).resolve(strict=True),
                                  Path(plan_path).resolve(strict=True),
                                  Path(output_dir).resolve(), Path(mesh_dir).resolve(strict=True))
    if ckpt.name != "model_1000.pt":
        raise ValueError("D44 video is pinned to the m1000 checkpoint file")
    ckpt_sha = sha256_file(ckpt)
    if expected_checkpoint_sha256 is not None and ckpt_sha != expected_checkpoint_sha256:
        raise ValueError("m1000 checkpoint SHA differs from the requested SHA")
    plan_bytes = plan_file.read_bytes()
    settings = contract(yaml.safe_load(plan_bytes.decode("utf-8-sig")))
    source_manifest, _ = source_tile(mesh)
    if (mesh != Path(settings["source_mesh_dir"]).resolve(strict=True)
            or source_manifest["mesh_sha256"] != settings["source_mesh_sha256"]):
        raise ValueError("D44 video mesh differs from the evaluation plan")
    if out.exists():
        raise FileExistsError("D44 video output directory must be new")
    selected = {name: settings["case_specs"].get(name) for name in VIDEO_CASES}
    expected = {}
    for name in VIDEO_CASES:
        task, mode = name.rsplit("_eval_", maxsplit=1)
        expected[name] = {"task": task, "map_mode": "eval_" + mode, "role": "judge"}
    if any(spec != expected[name] for name, spec in selected.items()):
        raise ValueError("D44 video case mapping differs from the approved plan")
    timings = settings["timing"]
    durations = {name: (settings["turn_seconds"] if name.startswith("turn_") else
                        timings["approach_limit_s"] + timings["stop_s"]
                        + timings["restart_limit_s"]) for name in VIDEO_CASES}
    return {"schema": SCHEMA, "checkpoint": str(ckpt), "checkpoint_sha256": ckpt_sha,
            "checkpoint_iteration_required": 1000, "plan": str(plan_file),
            "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(), "mesh_dir": str(mesh),
            "mesh_sha256": source_manifest["mesh_sha256"], "seed": 42, "envs": 1,
            "map_modes": sorted({settings["case_specs"][name]["map_mode"] for name in VIDEO_CASES}),
            "cases": list(VIDEO_CASES), "durations_s": durations,
            "video": {"width": WIDTH, "height": HEIGHT, "fps": FPS},
            "output_dir": str(out), "command_order": {
                name: list(command_order(settings["case_specs"][name]["task"]))
                for name in VIDEO_CASES},
            "capture_backend": "foothold_s2.eval.ex42_d44_video"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--mesh-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--expected-checkpoint-sha256", required=True)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--execute", action="store_true")
    return parser


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                    sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _steps(seconds: float, dt: float) -> int:
    count = round(seconds / dt)
    if count < 1 or abs(count * dt - seconds) > dt / 2:
        raise ValueError("D44 video timing does not align with policy dt")
    return count


def make_capture_env(gym, task_id: str, env_cfg):
    """Create the same RGB-backed viewport used by the approved recorder."""
    env_cfg.viewer.resolution = (WIDTH, HEIGHT)
    return gym.make(task_id, cfg=env_cfg, render_mode="rgb_array")


def prepare_render_product(raw):
    """Warm the lazy Isaac Lab RGB annotator before consumers attach masks."""
    for _ in range(RENDER_WARMUP_FRAMES):
        raw.render()
    product = getattr(raw, "_render_product", None)
    if product is None:
        raise RuntimeError("D44 RGB render product was not created during viewport warmup")
    return product


def _one_case(env, raw, robot, sensor, sensor_ids, term, policy, obs, *,
              case_id: str, settings: dict, anchors: dict, dt: float,
              tile_origin, foot_ids, output: Path, camera,
              checkpoint_sha: str, plan_sha: str) -> dict:
    import av
    import numpy as np
    import torch
    from PIL import Image, ImageDraw, ImageFont
    from foothold_s2.eval.c_layer_frame_audit import audit_video, project_world_point
    from foothold_s2.eval.c_layer_segmentation import (
        robot_pixel_evidence, require_single_visible_robot)
    from foothold_s2.eval.video25.record_c_layer import follow_camera_pose

    task = settings["case_specs"][case_id]["task"]
    map_mode = settings["case_specs"][case_id]["map_mode"]
    timing = settings["timing"]
    env.reset()
    tile_origin = torch.as_tensor(tile_origin, device=raw.device)
    local_anchor = anchors["landing_center"] if task.startswith("turn_") else anchors["approach"]
    state = robot.data.root_state_w.clone()
    shift = torch.as_tensor(local_anchor, dtype=state.dtype, device=state.device) - torch.as_tensor(
        anchors["landing_center"], dtype=state.dtype, device=state.device)
    state[0, :3] += shift
    state[0, 7:] = 0
    robot.write_root_pose_to_sim(state[:, :7])
    robot.write_root_velocity_to_sim(state[:, 7:])
    obs = env.get_observations()
    verify_ex41_pose_observation(obs)
    policy.reset(torch.ones(1, dtype=torch.bool, device=raw.device))
    # The approved video tasks start directly at their task anchor: turns are
    # six seconds of in-place rotation; stop/restart begins with approach.
    settle = 0
    if task.startswith("turn_"):
        approach = stop = restart = 0
        turn = _steps(settings["turn_seconds"], dt)
        total = turn
    else:
        approach = _steps(timing["approach_limit_s"], dt)
        stop = _steps(timing["stop_s"], dt)
        restart = _steps(timing["restart_limit_s"], dt)
        turn = 0
        total = settle + approach + stop + restart
    steps_per_frame = round(1.0 / (FPS * dt))
    if abs(steps_per_frame * dt * FPS - 1.0) > 1e-6:
        raise ValueError("D44 frame cadence cannot provide distinct 25fps frames")
    stop_band = anchors["stop_band_x"]
    arrays = {key: [] for key in ("root", "quat", "feet", "contact", "vel", "wz",
                                  "alive", "phase", "command")}
    annotator = None
    try:
        import omni.replicator.core as rep
        render_product = prepare_render_product(raw)
        annotator = rep.AnnotatorRegistry.get_annotator(
            "instance_id_segmentation_fast", init_params={"colorize": False}, device="cpu")
        annotator.attach([render_product])
    except Exception as exc:
        raise RuntimeError("D44 video requires per-frame robot instance evidence") from exc
    raw_path = output.with_name(output.stem + ".raw.mp4")
    if output.exists() or raw_path.exists():
        raise FileExistsError(output)
    writer = av.open(str(raw_path), mode="w")
    stream = writer.add_stream("libx264", rate=FPS)
    stream.width, stream.height, stream.pix_fmt = WIDTH, HEIGHT, "yuv420p"
    stream.options = {"crf": "20", "preset": "medium"}
    screen_evidence, robot_evidence = [], []
    entered = False
    try:
        for tick in range(total):
            local_x = float(robot.data.root_pos_w[0, 0] - tile_origin[0])
            phase, command, entered = command_for_tick(
                task=task, tick=tick, settle=settle, approach=approach, stop=stop,
                turn_rate=settings["turn_rate_radps"], approach_speed=settings["approach_vx_mps"],
                restart_speed=settings["restart_vx_mps"], stop_band=tuple(stop_band),
                local_x=local_x, entered=entered)
            term.vel_command_b[:, :3] = torch.as_tensor(command, device=raw.device)
            term.stand.copy_(math.isclose(float(np.linalg.norm(command)), 0.0))
            requested = term.vel_command_b[:, :3].clone()
            obs, _reward, done, _extras = env.step(policy(obs))
            if not torch.allclose(term.vel_command_b[:, :3], requested, atol=1e-6, rtol=0):
                raise RuntimeError("D44 video command changed during the policy step")
            policy.reset(done)
            force = torch.linalg.vector_norm(sensor.data.net_forces_w[:, sensor_ids], dim=-1)
            contact = force > 1.0
            root_now = robot.data.root_pos_w[0].detach().cpu().numpy().copy()
            quat_now = robot.data.root_quat_w[0].detach().cpu().numpy().copy()
            feet_now = robot.data.body_pos_w[0, foot_ids].detach().cpu().numpy().copy()
            vel_now = robot.data.root_lin_vel_b[0].detach().cpu().numpy().copy()
            wz_now = float(robot.data.root_ang_vel_b[0, 2])
            arrays["root"].append(root_now); arrays["quat"].append(quat_now)
            arrays["feet"].append(feet_now); arrays["contact"].append(contact[0].detach().cpu().numpy().copy())
            arrays["vel"].append(vel_now); arrays["wz"].append(wz_now)
            arrays["alive"].append(not bool(done[0]))
            arrays["phase"].append(phase); arrays["command"].append(command)
            if tick % steps_per_frame == 0 or bool(done[0]):
                eye, target = follow_camera_pose(root_now)
                raw.sim.set_camera_view(eye=eye, target=target)
                before_render = (int(raw.common_step_counter),
                                 robot.data.root_pos_w[0].detach().cpu().clone(),
                                 term.vel_command_b[0, :3].detach().cpu().clone())
                for _ in range(2):
                    raw.sim.render()
                frame = np.ascontiguousarray(raw.render(recompute=True))[..., :3]
                after_render = (int(raw.common_step_counter),
                                 robot.data.root_pos_w[0].detach().cpu(),
                                 term.vel_command_b[0, :3].detach().cpu())
                if (before_render[0] != after_render[0]
                        or not torch.equal(before_render[1], after_render[1])
                        or not torch.equal(before_render[2], after_render[2])):
                    raise RuntimeError("D44 rendering advanced physics or changed the command")
                if frame.shape[:2] != (HEIGHT, WIDTH):
                    raise RuntimeError(f"D44 viewport dimensions differ: {frame.shape[:2]}")
                if float(frame.astype(np.float32).mean()) <= 10.0:
                    raise RuntimeError("D44 render produced a dark frame")
                camera_projection = project_world_point(root_now, eye, target, width=WIDTH, height=HEIGHT,
                                                        focal_length_mm=camera[0], horizontal_aperture_mm=camera[1])
                screen_evidence.append({"root_center_px": camera_projection,
                    "root_in_frame": 0 <= camera_projection[0] < WIDTH and 0 <= camera_projection[1] < HEIGHT,
                    "expected_static": (task == "stop_restart" and command == (0.0, 0.0, 0.0)),
                    "camera_eye_w": eye, "camera_target_w": target,
                    "focal_length_mm": camera[0], "horizontal_aperture_mm": camera[1]})
                packet = annotator.get_data()
                pixels = robot_pixel_evidence(packet, selected_env=0, env_count=1, height=HEIGHT, width=WIDTH)
                require_single_visible_robot(pixels)
                robot_evidence.append(pixels)
                rgba = Image.fromarray(frame)
                draw = ImageDraw.Draw(rgba, "RGBA")
                draw.rectangle((0, 0, WIDTH, 59), fill=(0, 0, 0, 190))
                draw.text((10, 4), f"{case_id} | {phase} | t={tick * dt:.2f}s",
                          font=ImageFont.load_default(), fill=(255, 255, 255, 255))
                draw.text((10, 21), f"cmd vx={command[0]:+.2f} wz={command[2]:+.2f} | actual vx={vel_now[0]:+.2f} wz={wz_now:+.2f}",
                          font=ImageFont.load_default(), fill=(255, 255, 255, 255))
                local_x_now = float(robot.data.root_pos_w[0, 0] - tile_origin[0])
                contacts = int(contact[0].sum().item())
                speed_xy = float(np.linalg.norm(vel_now[:2]))
                status = stop_restart_hud(task=task if phase == "stop_band_hold" else "other",
                    local_x=local_x_now, stop_band=stop_band, foot_contacts=contacts,
                    speed_xy=speed_xy, stop_speed=timing["stop_speed_mps"])
                draw.text((10, 38), status,
                          font=ImageFont.load_default(), fill=(255, 255, 255, 255))
                frame = np.asarray(rgba.convert("RGB"))
                for packet_frame in stream.encode(av.VideoFrame.from_ndarray(frame, format="rgb24")):
                    writer.mux(packet_frame)
            if bool(done[0]):
                break
        for packet_frame in stream.encode():
            writer.mux(packet_frame)
    finally:
        writer.close()
        annotator.detach()
    result = judge_one(arrays, task=task, anchors=anchors, settings=settings, dt=dt,
                       tile_origin=tile_origin.detach().cpu().numpy())
    start_position = "landing_center" if task.startswith("turn_") else "approach"
    _overlay_result(raw_path, output, case_id=case_id, start_position=start_position,
                    sequence=command_order(task), success=result["success"],
                    failure_reasons=result["failure_reasons"])
    audit = audit_video(output, expected=len(screen_evidence), width=WIDTH, height=HEIGHT,
                        screen_evidence=screen_evidence, robot_instance_evidence=robot_evidence)
    if audit["pass"] is not True:
        raise RuntimeError("D44 full-frame audit failed: " + ",".join(audit.get("issues", [])))
    receipt = {"schema": SCHEMA, "state": "done", "case_id": case_id, "task": task,
        "map_mode": map_mode, "start_position": "landing_center" if task.startswith("turn_") else "approach",
        "command_order": list(command_order(task)),
        "command_trace": summarize_commands(arrays),
        "checkpoint_sha256": checkpoint_sha, "plan_sha256": plan_sha,
        "envs": 1, "dt_s": dt, "fps": FPS, "frames": audit["frames"],
        "duration_s": audit["frames"] / FPS, "success": result["success"],
        "failure_reasons": result["failure_reasons"], "video": str(output),
        "video_sha256": sha256_file(output), "frame_audit": audit,
        "screen_evidence": screen_evidence, "robot_instance_evidence": robot_evidence}
    _write_json(output.with_suffix(".json"), receipt)
    raw_path.unlink()
    return receipt


def judge_one(data: dict, *, task: str, anchors: dict, settings: dict, dt: float,
              tile_origin) -> dict:
    """One-env equivalent of the D44 scorer; outcomes are recorded, never used to select a clip."""
    import numpy as np
    root = np.asarray(data["root"], dtype=np.float64)
    feet = np.asarray(data["feet"], dtype=np.float64)
    contact = np.asarray(data["contact"], dtype=bool)
    velocity = np.asarray(data["vel"], dtype=np.float64)
    alive = np.asarray(data["alive"], dtype=bool)
    phases = np.asarray(data["phase"], dtype=str)
    quat = np.asarray(data["quat"], dtype=np.float64)
    reasons = []
    origin = np.asarray(tile_origin, dtype=np.float64)
    local = root - origin[None]
    local_feet = feet - origin[None, None]
    if not alive[-1]:
        reasons.append("robot_terminated")
    if task.startswith("turn_"):
        w, x, y, z = np.moveaxis(quat, -1, 0)
        yaw = np.unwrap(np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))
        turn = phases == "landing_turn"
        sign = 1 if task == "turn_left" else -1
        yaw_delta = sign * float(yaw[turn][-1] - yaw[turn][0]) if turn.any() else 0.0
        platform = anchors["landing_bounds_xy"]
        landed = ((local[:, 0] >= platform[0]) & (local[:, 0] <= platform[1])
                  & (local[:, 1] >= platform[2]) & (local[:, 1] <= platform[3])
                  & contact.any(axis=-1) & np.all(~contact | (local_feet[:, :, 2] >=
                    anchors["landing_center"][2] - settings["timing"]["foot_below_top_m"]), axis=-1))
        if not turn.any() or not np.all(landed[turn]):
            reasons.append("not_on_landing_during_turn")
        if yaw_delta < settings["turn_seconds"] * settings["turn_rate_radps"] * settings["turn_success_fraction"]:
            reasons.append("turn_angle_below_threshold")
    else:
        timing = settings["timing"]
        band = anchors["stop_band_x"]
        in_band = (local[:, 0] >= band[0]) & (local[:, 0] <= band[1])
        approach = phases == "approach"
        stop = phases == "stop_band_hold"
        restart = phases == "restart_to_top"
        approached = bool(np.any(in_band[approach]))
        if not approached:
            reasons.append("approach_timeout")
        speed = np.linalg.norm(velocity[:, :2], axis=-1) <= timing["stop_speed_mps"]
        stop_ok = _has_run(stop & in_band & speed, math.ceil(timing["stop_hold_s"] / dt))
        if not stop_ok:
            reasons.append("stop_band_hold_not_met")
        bounds = anchors["landing_bounds_xy"]
        platform = ((local[:, 0] >= bounds[0]) & (local[:, 0] <= bounds[1])
                    & (local[:, 1] >= bounds[2]) & (local[:, 1] <= bounds[3])
                    & contact.all(axis=-1)
                    & np.all(~contact | (local_feet[:, :, 2] >= anchors["landing_center"][2]
                                         - timing["foot_below_top_m"]), axis=-1))
        top_ok = _has_run(restart & platform, math.ceil(timing["top_hold_s"] / dt))
        if not top_ok:
            reasons.append("landing_hold_not_met")
    return {"success": not reasons, "failure_reasons": reasons}


def _has_run(mask, minimum: int) -> bool:
    count = 0
    for value in mask:
        count = count + 1 if bool(value) else 0
        if count >= minimum:
            return True
    return False


def summarize_commands(data: dict) -> list[dict]:
    """Compact actual/requested command readback grouped by contiguous phase."""
    import numpy as np
    phases = list(data["phase"])
    commands = np.asarray(data["command"], dtype=np.float64)
    actual = np.asarray(data["vel"], dtype=np.float64)
    wz = np.asarray(data["wz"], dtype=np.float64)
    rows = []
    start = 0
    while start < len(phases):
        end = start + 1
        while (end < len(phases) and phases[end] == phases[start]
               and np.array_equal(commands[end], commands[start])):
            end += 1
        rows.append({"phase": phases[start], "steps": end - start,
                     "requested_vx_mps": float(commands[start, 0]),
                     "requested_wz_radps": float(commands[start, 2]),
                     "actual_vx_mean_mps": float(actual[start:end, 0].mean()),
                     "actual_vx_min_mps": float(actual[start:end, 0].min()),
                     "actual_vx_max_mps": float(actual[start:end, 0].max()),
                     "actual_wz_mean_radps": float(wz[start:end].mean())})
        start = end
    return rows


def stop_restart_hud(*, task: str, local_x: float, stop_band: tuple[float, float],
                     foot_contacts: int, speed_xy: float, stop_speed: float) -> str:
    in_band = stop_band[0] <= local_x <= stop_band[1]
    band = ("in" if in_band else "out") if task == "stop_restart" else "n/a"
    stopped = ("yes" if speed_xy <= stop_speed else "no") if task == "stop_restart" else "n/a"
    return (f"stop-band={band} | stopped={stopped} | feet contact={foot_contacts}/4 "
            f"| speed_xy={speed_xy:.3f} m/s")


def _overlay_result(source: Path, destination: Path, *, case_id: str, start_position: str,
                    sequence: tuple[str, ...], success: bool,
                    failure_reasons: list[str]) -> None:
    import av
    from PIL import Image, ImageDraw, ImageFont
    reader = av.open(str(source), mode="r")
    writer = av.open(str(destination), mode="w")
    stream = writer.add_stream("libx264", rate=FPS)
    stream.width, stream.height, stream.pix_fmt = WIDTH, HEIGHT, "yuv420p"
    stream.options = {"crf": "20", "preset": "medium"}
    try:
        font = ImageFont.load_default()
        for packet in reader.decode(video=0):
            frame = Image.fromarray(packet.to_ndarray(format="rgb24"))
            draw = ImageDraw.Draw(frame, "RGBA")
            draw.rectangle((0, HEIGHT - 48, WIDTH, HEIGHT), fill=(0, 0, 0, 205))
            draw.text((10, HEIGHT - 45), f"{case_id} | start={start_position} | {' > '.join(sequence)}",
                      font=font, fill=(255, 255, 255, 255))
            marker = "PASS" if success else "FAIL: " + ",".join(failure_reasons)
            draw.text((10, HEIGHT - 25), marker, font=font,
                      fill=(80, 255, 80, 255) if success else (255, 100, 100, 255))
            for encoded in stream.encode(av.VideoFrame.from_ndarray(__import__("numpy").asarray(frame), format="rgb24")):
                writer.mux(encoded)
        for encoded in stream.encode():
            writer.mux(encoded)
    finally:
        reader.close(); writer.close()


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    if argv is None:
        initial, _ = parser.parse_known_args()
    else:
        initial, _ = parser.parse_known_args(argv)
    if initial.plan_only:
        args = parser.parse_args(argv)
        plan = build_plan(checkpoint=args.checkpoint, plan_path=args.plan, output_dir=args.out,
                          mesh_dir=args.mesh_dir, expected_checkpoint_sha256=args.expected_checkpoint_sha256)
        print(json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    if not initial.execute:
        parser.error("use --plan-only for CPU preflight or --execute for Kit capture")
    from isaaclab.app import AppLauncher
    AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args(argv)
    # Isaac Sim requires camera rendering to be enabled explicitly for headless captures.
    args.enable_cameras = True
    app = AppLauncher(args).app
    if app is None:
        raise RuntimeError("Kit failed to start")
    env = None
    try:
        plan_doc = build_plan(checkpoint=args.checkpoint, plan_path=args.plan, output_dir=args.out,
                              mesh_dir=args.mesh_dir, expected_checkpoint_sha256=args.expected_checkpoint_sha256)
        import yaml
        import torch
        import gymnasium as gym
        import importlib
        importlib.import_module("isaaclab_tasks")
        from isaaclab_tasks.utils import load_cfg_from_registry
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        from foothold_s2.eval.ex42_d44_cells import contract
        from foothold_s2.eval.ex42_eval_tile_mesh import source_tile
        from foothold_s2.eval import adapters, ex41_eval_loader, map_mode_cells
        from foothold_s2.terrains.ex42_mesh_mount import mesh_file_generator_cfg
        importlib.import_module("foothold_s2.sb_tasks")

        plan_bytes = Path(args.plan).read_bytes()
        document = yaml.safe_load(plan_bytes.decode("utf-8-sig"))
        settings = contract(document)
        source_manifest, tile = source_tile(Path(args.mesh_dir))
        env_cfg = load_cfg_from_registry("FootholdS2-Go2-S2-SB-v0", "env_cfg_entry_point")
        agent_cfg = load_cfg_from_registry("FootholdS2-Go2-S2-SB-v0", "rsl_rl_cfg_entry_point")
        env_cfg.scene.num_envs = 1; env_cfg.seed = agent_cfg.seed = 42
        env_cfg.sim.device = agent_cfg.device = args.device
        env_cfg.scene.terrain.terrain_type = "generator"
        env_cfg.scene.terrain.terrain_generator = mesh_file_generator_cfg(
            Path(args.mesh_dir) / "terrain_mesh.npz", source_manifest["mesh_sha256"],
            single_tile_size=tile["tile_size_m"])
        env_cfg.scene.terrain.max_init_terrain_level = 0
        env_cfg.observations.policy.enable_corruption = False
        from foothold_s2.sensors import start_obs
        start_obs.AUG.enabled = False
        adapters.disable_eval_randomization(env_cfg)
        for key in ("terrain_levels", "command_range"):
            if hasattr(env_cfg.curriculum, key): setattr(env_cfg.curriculum, key, None)
        env_cfg.commands.base_velocity.resampling_time_range = (1.0e9, 1.0e9)
        env_cfg.commands.base_velocity.dynamic_flags = False
        env_cfg.commands.base_velocity.flag_stride = 0
        env_cfg.events.reset_base.params["pose_range"] = {"x": (0., 0.), "y": (0., 0.), "yaw": (0., 0.)}
        env_cfg.events.reset_robot_joints.params["position_range"] = (1., 1.)
        env_cfg.events.reset_robot_joints.params["velocity_range"] = (0., 0.)
        if hasattr(env_cfg.actions.joint_pos, "max_delay_s"):
            env_cfg.actions.joint_pos.max_delay_s = 0.
        checkpoint_state, checkpoint_preparation = ex41_eval_loader.load_checkpoint_for_eval(
            env_cfg, Path(args.checkpoint))
        if int(checkpoint_state.get("iter", -1)) != 1000:
            raise ValueError("D44 capture checkpoint is not m1000 by embedded iteration")
        env = RslRlVecEnvWrapper(make_capture_env(gym, "FootholdS2-Go2-S2-SB-v0", env_cfg),
                                 clip_actions=agent_cfg.clip_actions)
        raw = env.unwrapped
        terrain = raw.scene.terrain
        if terrain.terrain_origins.shape != (1, 1, 3):
            raise RuntimeError("single-env D44 renderer did not mount exactly one tile")
        tile_origin = terrain.terrain_origins[0, 0].detach().clone()
        terrain.terrain_levels.fill_(0); terrain.terrain_types.fill_(0)
        landing = torch.as_tensor(tile["anchors_local_m"]["landing_center"],
                                  dtype=terrain.env_origins.dtype, device=terrain.env_origins.device)
        terrain.env_origins.copy_((tile_origin + landing).reshape(1, 3))
        if int(raw.num_envs) != 1 or not torch.equal(raw.scene.env_origins, terrain.env_origins):
            raise RuntimeError("D44 renderer environment count or tile assignment differs")
        robot, sensor = raw.scene["robot"], raw.scene["contact_forces"]
        feet = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")
        foot_ids = [robot.body_names.index(name) for name in feet]
        sensor_ids = [sensor.body_names.index(name) for name in feet]
        term = raw.command_manager.get_term("base_velocity")
        map_mode_cells.disable_heading_for_fixed_eval(term)
        runner, _ = adapters.load_s2_runner(env, agent_cfg.to_dict(), Path(args.checkpoint),
            args.device, checkpoint_state=checkpoint_state)
        obs = env.get_observations()
        ex41_eval_loader.verify_ex41_pose_observation(obs)
        import omni.usd
        from pxr import UsdGeom
        camera_prim = omni.usd.get_context().get_stage().GetPrimAtPath("/OmniverseKit_Persp")
        if not camera_prim.IsValid() or not camera_prim.IsA(UsdGeom.Camera):
            raise RuntimeError("D44 viewport camera is unavailable")
        camera_obj = UsdGeom.Camera(camera_prim)
        intrinsics = (float(camera_obj.GetFocalLengthAttr().Get()),
                      float(camera_obj.GetHorizontalApertureAttr().Get()))
        out_dir = Path(args.out).resolve(); out_dir.mkdir(parents=True, exist_ok=False)
        outputs = {}
        for case_id in VIDEO_CASES:
            map_mode = settings["case_specs"][case_id]["map_mode"]
            policy = adapters.S2Policy(runner, 1, z_mode="mean", act_mode="mean", map_mode=map_mode)
            expected_gt = map_mode == "eval_gt"
            if bool(policy.pstate.use_gt.all()) != expected_gt:
                raise RuntimeError(f"D44 {map_mode} capture selected the wrong map input")
            target = out_dir / f"D44-{case_id}-m1000.mp4"
            outputs[case_id] = _one_case(env, raw, robot, sensor, sensor_ids, term, policy, obs,
                case_id=case_id, settings=settings, anchors=tile["anchors_local_m"],
                dt=float(raw.step_dt), tile_origin=tile_origin, foot_ids=foot_ids,
                output=target, camera=intrinsics, checkpoint_sha=plan_doc["checkpoint_sha256"],
                plan_sha=plan_doc["plan_sha256"])
        top = {"schema": SCHEMA, "state": "done", "checkpoint": str(Path(args.checkpoint).resolve()),
               "checkpoint_sha256": plan_doc["checkpoint_sha256"], "plan_sha256": plan_doc["plan_sha256"],
               "mesh_sha256": plan_doc["mesh_sha256"], "seed": 42, "envs": 1,
               "checkpoint_preparation": checkpoint_preparation, "videos": outputs}
        _write_json(out_dir / "d44_video_receipt.json", top)
        print("D44_VIDEO_DONE", out_dir, flush=True)
    except BaseException as exc:
        print("D44_VIDEO_FAILED", repr(exc), file=sys.stderr, flush=True)
        traceback.print_exc()
        return 1
    finally:
        if env is not None:
            env.close()
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
