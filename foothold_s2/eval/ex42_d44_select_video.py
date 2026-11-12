"""EX-42 D44 selected-env video: the 64-env D44 case, unchanged, filming one env.

Copy of ex42_d44_eval (integration HEAD) for one case. Physics, commands and scoring
are the evaluator's; additionally one chosen env is rendered (others hidden) and the
run is compared with a reference per_env JSON (fidelity check). Original docstring:

EX-42 E1 D44 landing cells on 64 independent copies of the pinned tile.

This Kit child is launched only after the prep plan contains a D44 case and
timing contract. It writes per-step NPZ and per-case JSON, then a combined
receipt. No cell is inferred from map64 or from another checkpoint.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import traceback
from pathlib import Path

import h5py  # noqa: F401
import tensordict  # noqa: F401
import torch
import rsl_rl.runners  # noqa: F401
import yaml
from isaaclab.app import AppLauncher

from foothold_s2.eval.ex42_d44_cells import (TRACE_FORMAT, RECEIPT_FORMAT, contract, summarize,
                                             restart_command, top_latch_mask)
from foothold_s2.eval.ex42_eval_tile_mesh import preflight_replicas, source_tile


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--task", default="FootholdS2-Go2-S2-SB-v0")
parser.add_argument("--checkpoint", type=Path, required=True)
parser.add_argument("--plan", type=Path, required=True)
parser.add_argument("--mesh-dir", type=Path, required=True)
parser.add_argument("--replica-dir", type=Path, required=True)
parser.add_argument("--expected-replica-sha256", required=True)
parser.add_argument("--envs", type=int, default=64)
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--out", type=Path, required=True)
parser.add_argument("--case-id", required=True)
parser.add_argument("--film-env", type=int, required=True)
parser.add_argument("--reference-json", type=Path, required=True)
parser.add_argument("--no-video", action="store_true")
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
args.enable_cameras = not args.no_video
if args.envs != 64 or args.seed < 0 or not args.checkpoint.is_file() or args.out.exists():
    parser.error("D44 requires a fresh output, pinned checkpoint, seed and 64 envs")
plan_bytes = args.plan.read_bytes()
plan = yaml.safe_load(plan_bytes.decode("utf-8-sig"))
settings = contract(plan)
from foothold_s2.eval import ex42_friction
friction_policy = ex42_friction.load_policy(args.plan)
# prep pins /home/jay/data/... while the evaluator passes the resolved /mnt/win-d/... path (11/11 m250); compare both resolved
if (not settings["source_mesh_dir"] or Path(settings["source_mesh_dir"]).resolve() != args.mesh_dir.resolve()
        or not settings["source_mesh_sha256"]):
    parser.error("D44 prep must pin the one-tile source directory and mesh SHA")
source, tile = source_tile(args.mesh_dir)
if source["mesh_sha256"] != settings["source_mesh_sha256"]:
    parser.error("D44 source tile SHA differs from prep")
replica = preflight_replicas(args.mesh_dir, args.replica_dir, anchor="landing_center",
                             expected_mesh_sha256=args.expected_replica_sha256)
app = AppLauncher(args).app

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
import isaaclab_tasks  # noqa: E402,F401
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402
from isaaclab_tasks.utils import load_cfg_from_registry  # noqa: E402

import foothold_s2.sb_tasks  # noqa: E402,F401
from foothold_s2.eval import adapters, ex41_eval_loader, map_mode_cells, run_identity  # noqa: E402
from foothold_s2.eval.ex42_eval_tile_mesh import assign_independent_env_origins  # noqa: E402
from foothold_s2.terrains.ex42_mesh_mount import mesh_file_generator_cfg  # noqa: E402


FEET = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")


def _indices(robot, sensor):
    body, sensing = list(robot.body_names), list(sensor.body_names)
    if any(body.count(name) != 1 or sensing.count(name) != 1 for name in FEET):
        raise RuntimeError("D44 requires four uniquely named robot and sensor feet")
    return [body.index(name) for name in FEET], [sensing.index(name) for name in FEET]


def _configure():
    env_cfg = load_cfg_from_registry(args.task, "env_cfg_entry_point")
    agent_cfg = load_cfg_from_registry(args.task, "rsl_rl_cfg_entry_point")
    env_cfg.scene.num_envs = args.envs
    if not args.no_video:
        env_cfg.viewer.resolution = (1280, 720)
    env_cfg.seed = agent_cfg.seed = args.seed
    env_cfg.sim.device = agent_cfg.device = args.device
    env_cfg.scene.terrain.terrain_type = "generator"
    env_cfg.scene.terrain.terrain_generator = mesh_file_generator_cfg(
        args.replica_dir / "terrain_mesh.npz", replica["mesh_sha256"])
    env_cfg.scene.terrain.max_init_terrain_level = 7
    env_cfg.observations.policy.enable_corruption = False
    from foothold_s2.sensors import start_obs
    start_obs.AUG.enabled = False
    disabled = adapters.disable_eval_randomization(env_cfg)
    for name in ("terrain_levels", "command_range"):
        if hasattr(env_cfg.curriculum, name):
            setattr(env_cfg.curriculum, name, None)
    env_cfg.events.reset_base.params["pose_range"] = {
        "x": (0.0, 0.0), "y": (0.0, 0.0), "yaw": (0.0, 0.0)}
    env_cfg.events.reset_robot_joints.params["position_range"] = (1.0, 1.0)
    env_cfg.events.reset_robot_joints.params["velocity_range"] = (0.0, 0.0)
    command_cfg = env_cfg.commands.base_velocity
    command_cfg.resampling_time_range = (1.0e9, 1.0e9)
    command_cfg.dynamic_flags = False
    command_cfg.flag_stride = 0
    if hasattr(env_cfg.actions.joint_pos, "max_delay_s"):
        env_cfg.actions.joint_pos.max_delay_s = 0.0
    ex42_friction.configure(env_cfg, friction_policy)
    return env_cfg, agent_cfg, disabled


def _steps(seconds, dt):
    value = round(seconds / dt)
    if value < 1 or abs(value * dt - seconds) > dt / 2:
        raise ValueError("D44 timing does not align with policy dt")
    return value


class Film:
    """One selected env, rendered while all 64 envs run exactly as the evaluator runs them."""

    def __init__(self, raw, annotator, path):
        import av
        from foothold_s2.eval.ex42_d44_video import WIDTH, HEIGHT, FPS
        self.raw, self.annotator, self.path = raw, annotator, path
        self.raw_path = path.with_name(path.stem + ".raw.mp4")
        self.writer = av.open(str(self.raw_path), mode="w")
        self.stream = self.writer.add_stream("libx264", rate=FPS)
        self.stream.width, self.stream.height, self.stream.pix_fmt = WIDTH, HEIGHT, "yuv420p"
        self.stream.options = {"crf": "20", "preset": "medium"}
        self.screen, self.robots, self.active = [], [], True
        self.intrinsics = None
        self.capture_dir = path.with_name(path.stem + "_capture")
        self.capture_dir.mkdir(parents=True, exist_ok=False)
        self.clean = av.open(str(self.capture_dir / "review.mp4"), mode="w")
        self.clean_stream = self.clean.add_stream("libx264", rate=FPS)
        self.clean_stream.width, self.clean_stream.height, self.clean_stream.pix_fmt = WIDTH, HEIGHT, "yuv420p"
        self.clean_stream.options = {"crf": "18", "preset": "medium"}
        self.rows = {key: [] for key in ("t", "seg", "foot_pos_w", "foot_contact", "root_pos_w", "root_quat_w",
                                        "roll", "pitch", "vx", "vy", "wz", "command", "done", "time_out",
                                        "map_use_gt", "gt_map", "refined_map")}
        self.snap, self.overlay, self.overlay_info, self.frame_ticks = {}, None, [], []

    def tick(self, k, dt, seg, foot_pos, contact, root, quat, vel, wz, command, done, map_snap):
        import numpy as np
        w, x, y, z = (float(v) for v in quat)
        roll = float(np.arctan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)))
        pitch = float(np.arcsin(np.clip(2 * (w * y - z * x), -1.0, 1.0)))
        for key, value in (("t", k * dt), ("seg", seg), ("foot_pos_w", foot_pos), ("foot_contact", contact),
                           ("root_pos_w", root), ("root_quat_w", quat), ("roll", roll), ("pitch", pitch),
                           ("vx", float(vel[0])), ("vy", float(vel[1])), ("wz", float(wz)),
                           ("command", command), ("done", bool(done)), ("time_out", False),
                           ("map_use_gt", bool(map_snap.get("use_gt", False))),
                           ("gt_map", map_snap.get("gt_map", np.empty((0,), np.float32)).reshape(-1)),
                           ("refined_map", map_snap.get("refined_map", np.empty((0,), np.float32)).reshape(-1))):
            self.rows[key].append(np.asarray(value))

    def frame(self, env_id, root, hud_lines, expected_static=False, command=(0.0, 0.0, 0.0)):
        import av
        import numpy as np
        import torch
        from PIL import Image, ImageDraw, ImageFont
        from foothold_s2.eval.c_layer_frame_audit import project_world_point
        from foothold_s2.eval.c_layer_segmentation import robot_pixel_evidence, require_single_visible_robot
        from foothold_s2.eval.video25.record_c_layer import follow_camera_pose
        from foothold_s2.eval.ex42_d44_video import WIDTH, HEIGHT
        raw = self.raw
        eye, target = follow_camera_pose(root)
        raw.sim.set_camera_view(eye=eye, target=target)
        if self.overlay is not None:
            self.overlay_info.append({"frame": len(self.screen), **self.overlay.draw(command, self.snap)})
        before = (int(raw.common_step_counter), raw.scene["robot"].data.root_pos_w.detach().cpu().clone())
        for _ in range(2 if self.screen else 8):   # first frame: camera move and annotator need a few renders to settle
            raw.sim.render()
        image = np.ascontiguousarray(raw.render(recompute=True))[..., :3]
        after = (int(raw.common_step_counter), raw.scene["robot"].data.root_pos_w.detach().cpu())
        if before[0] != after[0] or not torch.equal(before[1], after[1]):
            raise RuntimeError("D44 rendering advanced physics")
        if image.shape[:2] != (HEIGHT, WIDTH) or float(image.astype(np.float32).mean()) <= 10.0:
            raise RuntimeError("D44 render frame dimension or brightness invalid")
        projection = project_world_point(root, eye, target, width=WIDTH, height=HEIGHT,
                                         focal_length_mm=self.intrinsics[0],
                                         horizontal_aperture_mm=self.intrinsics[1])
        self.screen.append({"root_center_px": projection,
            "root_in_frame": 0 <= projection[0] < WIDTH and 0 <= projection[1] < HEIGHT,
            "expected_static": bool(expected_static), "camera_eye_w": eye, "camera_target_w": target,
            "focal_length_mm": self.intrinsics[0], "horizontal_aperture_mm": self.intrinsics[1]})
        pixels = robot_pixel_evidence(self.annotator.get_data(), selected_env=env_id,
                                      env_count=args.envs, height=HEIGHT, width=WIDTH)
        require_single_visible_robot(pixels)
        self.robots.append(pixels)
        for packet in self.clean_stream.encode(av.VideoFrame.from_ndarray(image, format="rgb24")):
            self.clean.mux(packet)
        pil = Image.fromarray(image)
        draw = ImageDraw.Draw(pil, "RGBA")
        draw.rectangle((0, 0, WIDTH, 59), fill=(0, 0, 0, 190))
        for i, line in enumerate(hud_lines):
            draw.text((10, 4 + 17 * i), line, font=ImageFont.load_default(), fill=(255, 255, 255, 255))
        for packet in self.stream.encode(av.VideoFrame.from_ndarray(np.asarray(pil.convert("RGB")), format="rgb24")):
            self.writer.mux(packet)

    def close(self):
        try:
            for packet in self.stream.encode():
                self.writer.mux(packet)
        finally:
            self.writer.close()
            for packet in self.clean_stream.encode():
                self.clean.mux(packet)
            self.clean.close()
            self.annotator.detach()


def _run_cell(env, raw, robot, sensor, body_ids, sensor_ids, term, runner, case_id, spec, dt,
              checkpoint_preparation, film=None):
    n = args.envs
    env.reset()
    terrain = raw.scene.terrain
    expected = torch.arange(n, device=raw.device)
    if (not torch.equal(terrain.terrain_levels, expected.div(8, rounding_mode="floor"))
            or not torch.equal(terrain.terrain_types, expected.remainder(8))):
        raise RuntimeError("D44 terrain assignment changed during reset")
    state = robot.data.root_state_w.clone()
    local_anchor = tile["anchors_local_m"]["landing_center"]
    if spec["task"] == "stop_restart":
        approach = tile["anchors_local_m"]["approach"]
        shift = torch.tensor([approach[i] - local_anchor[i] for i in range(3)], device=raw.device)
        state[:, :3] += shift
    state[:, 7:] = 0
    robot.write_root_pose_to_sim(state[:, :7])
    robot.write_root_velocity_to_sim(state[:, 7:])
    obs = env.get_observations()
    if checkpoint_preparation["checkpoint_pose_commands"]:
        ex41_eval_loader.verify_ex41_pose_observation(obs)
    map_mode_cells.disable_heading_for_fixed_eval(term)
    policy = adapters.S2Policy(runner, n, z_mode="mean", act_mode="mean", map_mode=spec["map_mode"])
    policy.reset(torch.ones(n, dtype=torch.bool, device=raw.device))
    if bool(policy.pstate.use_gt.any()) != (spec["map_mode"] == "eval_gt"):
        raise RuntimeError("D44 requested map mode differs from policy input")
    t = settings["timing"]
    settle = _steps(t["settle_s"], dt)
    approach = _steps(t["approach_limit_s"], dt)
    stop = _steps(t["stop_s"], dt)
    restart = _steps(t["restart_limit_s"], dt)
    turn = _steps(settings["turn_seconds"], dt)
    total = settle + (turn if spec["task"].startswith("turn_") else approach + stop + restart)
    rows = {key: [] for key in ("root_pos_w", "root_quat_w", "foot_pos_w", "contact",
                                "body_vel_b", "alive", "phase_id", "cmd_post")}
    alive = torch.ones(n, dtype=torch.bool, device=raw.device)
    entered = torch.zeros(n, dtype=torch.bool, device=raw.device)
    top_latched = torch.zeros(n, dtype=torch.bool, device=raw.device)
    top_latched_at = np.full(n, -1, dtype=np.int32)
    offset = (raw.scene.env_origins - torch.tensor(local_anchor, device=raw.device)).detach().cpu().numpy()
    for k in range(total):
        phase = 0 if k < settle else (1 if spec["task"].startswith("turn_") else
                1 if k < settle + approach else 2 if k < settle + approach + stop else 3)
        phase_ids = torch.full((n,), phase, dtype=torch.int16, device=raw.device)
        if phase == 3:
            phase_np, restart_vx = restart_command(top_latched.detach().cpu().numpy(),
                                                   settings["restart_vx_mps"])
            phase_ids = torch.as_tensor(phase_np, device=raw.device)
        term.vel_command_b[:, :3] = 0.0
        if phase == 1 and spec["task"].startswith("turn_"):
            term.vel_command_b[:, 2] = settings["turn_rate_radps"] * (1 if spec["task"] == "turn_left" else -1)
        elif phase == 1:
            term.vel_command_b[~entered, 0] = settings["approach_vx_mps"]
        elif phase == 3:
            term.vel_command_b[:, 0] = torch.as_tensor(restart_vx, device=raw.device)
        term.stand.copy_(torch.linalg.norm(term.vel_command_b[:, :3], dim=1) == 0)
        map_mode_cells.assert_heading_off_for_fixed_eval(term)
        if bool(term.is_flag_env.any()):
            raise RuntimeError("D44 fixed command evaluation contains a flag environment")
        requested = term.vel_command_b[:, :3].clone()
        action = policy(obs)
        obs, _reward, done, _extras = env.step(action)
        active = alive & ~done.bool()
        if bool(active.any()) and not torch.allclose(
                term.vel_command_b[active, :3], requested[active], atol=1e-5, rtol=0):
            raise RuntimeError("D44 command changed during the policy step")
        policy.reset(done)
        alive &= ~done.bool()
        if checkpoint_preparation["checkpoint_pose_commands"]:
            ex41_eval_loader.verify_ex41_pose_observation(obs)
        if phase == 1 and spec["task"] == "stop_restart":
            local_x = robot.data.root_pos_w[:, 0] - torch.as_tensor(offset[:, 0], device=raw.device)
            band = tile["anchors_local_m"]["stop_band_x"]
            entered |= (local_x >= band[0]) & (local_x <= band[1]) & alive
        if phase == 3 and spec["task"] == "stop_restart":
            local_root = robot.data.root_pos_w.detach().cpu().numpy() - offset
            local_feet = robot.data.body_pos_w[:, body_ids].detach().cpu().numpy() - offset[:, None, :]
            candidate = top_latch_mask(local_root[:, :2], local_feet[:, :, 0],
                                       alive.detach().cpu().numpy(),
                                       tile["anchors_local_m"]["landing_bounds_xy"])
            newly = candidate & ~top_latched.detach().cpu().numpy()
            top_latched_at[newly] = k
            top_latched |= torch.as_tensor(candidate, dtype=torch.bool, device=raw.device)
        force = torch.linalg.vector_norm(sensor.data.net_forces_w[:, sensor_ids], dim=-1)
        data = robot.data
        rows["root_pos_w"].append(data.root_pos_w.detach().cpu().numpy().copy())
        rows["root_quat_w"].append(data.root_quat_w.detach().cpu().numpy().copy())
        rows["foot_pos_w"].append(data.body_pos_w[:, body_ids].detach().cpu().numpy().copy())
        rows["contact"].append((force > 1.0).detach().cpu().numpy().copy())
        rows["body_vel_b"].append(data.root_lin_vel_b.detach().cpu().numpy().copy())
        rows["alive"].append(alive.detach().cpu().numpy().copy())
        rows["phase_id"].append(phase_ids.detach().cpu().numpy().copy())
        rows["cmd_post"].append(term.vel_command_b[:, :3].detach().cpu().numpy().copy())
        if film is not None:
            e = args.film_env
            root_e = data.root_pos_w[e].detach().cpu().numpy().copy()
            vel_e, wz_e = data.root_lin_vel_b[e].detach().cpu().numpy().copy(), float(data.root_ang_vel_b[e, 2])
            cmd_e = requested[e].detach().cpu().numpy().copy()
            film.tick(k, dt, int(phase), data.body_pos_w[e, body_ids].detach().cpu().numpy().copy(),
                      (force[e] > 1.0).detach().cpu().numpy().copy(), root_e,
                      data.root_quat_w[e].detach().cpu().numpy().copy(), vel_e, wz_e, cmd_e,
                      bool(done[e]), film.snap)
            if k % round(1.0 / (25 * dt)) == 0:
                film.frame_ticks.append(k)
                local_x_e = float(root_e[0] - offset[e, 0])
                film.frame(e, root_e, [
                    f"{case_id} | env {e} | phase {phase} | t={k * dt:.2f}s | alive={bool(alive[e])}",
                    f"cmd vx={cmd_e[0]:+.2f} wz={cmd_e[2]:+.2f} | actual vx={vel_e[0]:+.2f} wz={wz_e:+.2f}",
                    f"local_x={local_x_e:+.2f} m | feet contact={int((force[e] > 1.0).sum())}/4"],
                           expected_static=(spec["task"] == "stop_restart" and not bool(np.any(cmd_e != 0.0))),
                           command=tuple(float(v) for v in cmd_e))
    trace = {key: np.stack(value) for key, value in rows.items()}
    trace.update(trace_format=np.asarray(TRACE_FORMAT), top_latched_at=top_latched_at,
                 tile_offset_w=offset, approach_entered=entered.detach().cpu().numpy(), dt=np.asarray(dt),
                 case_id=np.asarray(case_id), map_mode=np.asarray(spec["map_mode"]))
    return trace


def write_capture_and_compose(film, spec, case_id, picked, dt, checkpoint_sha, mesh_sha):
    """25e capture folder (review.mp4/json/feet.npz/done) from the filmed env, then rule 4 composition."""
    import numpy as np
    from foothold_s2.eval import video_style
    from foothold_s2.eval.video25 import compose_25e_v2style10 as composer
    cap = film.capture_dir
    steps = len(film.rows["t"])
    sample = film.frame_ticks
    frames = len(sample)
    duration = steps * dt
    if abs(duration * 25 - frames) > 1e-6 or sample != list(range(0, steps, round(1.0 / (25 * dt)))):
        raise RuntimeError("D44 capture frames do not tile the recorded physics steps")
    t = settings["timing"]
    if spec["task"].startswith("turn_"):
        names = [("settle", (0.0, 0.0, 0.0), settings["timing"]["settle_s"]),
                 (spec["task"], (0.0, 0.0, settings["turn_rate_radps"] * (1 if spec["task"] == "turn_left" else -1)),
                  settings["turn_seconds"])]
    else:
        names = [("settle", (0.0, 0.0, 0.0), t["settle_s"]),
                 ("approach_to_stop_band", (settings["approach_vx_mps"], 0.0, 0.0), t["approach_limit_s"]),
                 ("stop_band_hold", (0.0, 0.0, 0.0), t["stop_s"]),
                 ("restart_to_top", (settings["restart_vx_mps"], 0.0, 0.0), t["restart_limit_s"])]
    commands, start = [], 0.0
    for name, target, span in names:
        commands.append({"name": name, "target": list(target), "start_s": start, "duration_s": float(span)})
        start += float(span)
    if abs(start - duration) > 1e-6:
        raise RuntimeError("D44 command spans differ from recorded duration")
    arrays = {k: np.stack(v) for k, v in film.rows.items() if k not in ("gt_map", "refined_map")}
    for key in ("gt_map", "refined_map"):
        sizes = {row.size for row in film.rows[key]}
        arrays[key] = (np.stack(film.rows[key]).astype(np.float32) if len(sizes) == 1 and 0 not in sizes
                       else np.empty((0,), np.float32))
    arrays["body_height_foot_center_m"] = (arrays["root_pos_w"][:, 2] - arrays["foot_pos_w"][:, :, 2].mean(axis=1)).astype(np.float32)
    arrays["seg"] = arrays["seg"].astype(np.int8)
    arrays["dt"] = np.float64(dt)
    np.savez_compressed(cap / "review_feet.npz", **arrays)
    style = {"style_id": video_style.STYLE_ID, "approved": True, "allow_unapproved": False,
             "values": dict(video_style.APPROVED_STYLE), "approved_values": dict(video_style.APPROVED_STYLE)}
    meta = {"label": "D44", "scene": f"D44 {spec['task']} env {args.film_env}",
            "task_selection": {"terrain_type": "D44 eval_stairs_landing_016", "selected_tile": {"level": 0}},
            "selected_environment": {"env_id": args.film_env, "kind": spec["task"], "level": 0, "col": 0,
                                     "selection_role": "D44 per_env " + str(picked.get("reason"))},
            "map_modes": {"map_mode": {"requested": spec["map_mode"]}},
            "step_contract": {"duration_s": duration, "physics_dt_s": dt, "physics_steps": steps,
                              "video_fps": 25, "video_frames": frames, "video_sample_step_indices": sample,
                              "commands": commands, "policy_modes": {"latent": "mean", "action": "mean"}},
            "camera_screen_projection": film.screen, "robot_instance_evidence": film.robots,
            "overlay_25e": {"legend": film.legend, "scene_foot_scan_visible": False,
                            "attention_hook": film.overlay.attn_hook_ok,
                            "saturation_multiplier": film.overlay.saturation_multiplier,
                            "frames": film.overlay_info, "attention_rows_per_step": film.overlay.attn_rows},
            "style": style, "lighting": film.style["lighting"], "checkpoint_sha256": checkpoint_sha,
            "mesh_sha256": mesh_sha, "per_env_row": picked, "case_id": case_id}
    (cap / "review.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (cap / "review.done").write_text("done\n", encoding="utf-8")
    ok = bool(picked.get("success"))
    out = film.path.with_name(film.path.stem + "_v34D168.mp4")
    question = ("정지 밴드에서 멈춘 뒤 다시 출발해 윗 단에 네 발로 올라서는가"
                if spec["task"] == "stop_restart" else "제자리 회전 6초 동안 발판 위에서 도는가")
    extra = f"env {args.film_env} · {'성공' if ok else '실패'} {picked.get('reason')} · 64환경 판정과 일치"
    return composer.render(cap, "seq", "1x", out, question=question, extra_line=extra,
                           extra_color=(200, 235, 200) if ok else (150, 150, 255))


def main():
    env = None
    phase = "configure"
    try:
        print("D44_PHASE", phase, flush=True)
        env_cfg, agent_cfg, disabled = _configure()
        phase = "checkpoint"
        print("D44_PHASE", phase, flush=True)
        checkpoint_state, checkpoint_preparation = ex41_eval_loader.load_checkpoint_for_eval(
            env_cfg, args.checkpoint)
        phase = "gym_make"
        print("D44_PHASE", phase, flush=True)
        env = RslRlVecEnvWrapper(
            gym.make(args.task, cfg=env_cfg, **({} if args.no_video else {"render_mode": "rgb_array"})),
            clip_actions=agent_cfg.clip_actions)
        raw = env.unwrapped
        ex42_friction.install_and_verify(raw, friction_policy)
        film = None
        if not args.no_video:
            import omni.usd
            import omni.replicator.core as rep
            from pxr import UsdGeom
            from foothold_s2.eval import video_style
            from foothold_s2.eval.ex42_d44_video import prepare_render_product
            style = video_style.APPROVED_STYLE
            lighting = video_style.apply_lighting_profile(video_style.lighting_profile_settings(
                style["lighting_profile"], dome_intensity=style["dome_intensity"],
                three_point_intensity=style["three_point_intensity"],
                three_point_angle_deg=style["three_point_angle_deg"],
                three_point_elevation_deg=style["three_point_elevation_deg"],
                three_point_shadows=style["three_point_shadows"]))
            hidden = video_style.hide_nonselected_robot_roots(
                omni.usd.get_context().get_stage(), env_cfg.scene.robot.prim_path,
                args.film_env, args.envs)
            from foothold_s2.eval.c_layer_segmentation import ensure_only_selected_visible
            hidden["visibility_check"] = ensure_only_selected_visible(
                omni.usd.get_context().get_stage(), hidden["visible_robot_root"],
                hidden["hidden_robot_roots"], UsdGeom.Imageable)
            product = prepare_render_product(raw)
            annotator = rep.AnnotatorRegistry.get_annotator(
                "instance_id_segmentation_fast", init_params={"colorize": False}, device="cpu")
            annotator.attach([product])
            cam = UsdGeom.Camera(omni.usd.get_context().get_stage().GetPrimAtPath("/OmniverseKit_Persp"))
            args.out.mkdir(parents=True, exist_ok=False)
            film = Film(raw, annotator, args.out / f"{args.case_id}_env{args.film_env}.mp4")
            film.intrinsics = (float(cam.GetFocalLengthAttr().Get()), float(cam.GetHorizontalApertureAttr().Get()))
            film.style = {"style_id": video_style.STYLE_ID, "values": style, "lighting": lighting,
                          "hidden_robot_roots": len(hidden["hidden_robot_roots"])}
        assign_independent_env_origins(raw)
        robot, sensor = raw.scene["robot"], raw.scene["contact_forces"]
        body_ids, sensor_ids = _indices(robot, sensor)
        term = raw.command_manager.get_term("base_velocity")
        dt = float(raw.step_dt)
        runner, _saved = adapters.load_s2_runner(env, agent_cfg.to_dict(), args.checkpoint,
                                                 args.device, checkpoint_state=checkpoint_state)
        if film is not None:
            import numpy as _np
            from foothold_s2.eval.video25.overlay_25e import SceneOverlay, LEGEND
            perception = runner.perception
            original_advance = perception._advance
            film_env = args.film_env

            def tapped_advance(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map):
                result = original_advance(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map)
                out = result[2]

                def row(values):
                    if values is None or not values.numel():
                        return _np.empty((0,), dtype=_np.float32)
                    return values[film_env].reshape(-1).detach().float().cpu().numpy()
                film.snap.clear()
                film.snap.update({"depth": depth2[film_env, -1].detach().float().cpu().numpy(),
                                  "gt_map": gt_map[film_env].detach().float().cpu().numpy(),
                                  "rough_map": row(out.get("rough")), "refined_map": row(out.get("refined")),
                                  "use_gt": bool(use_gt[film_env].item()),
                                  "first_after_reset": bool(first[film_env].item())})
                return result
            perception._advance = tapped_advance
            foot_ids_r, _foot_names = robot.find_bodies(".*_foot")
            # The attention hook turns off torch's MHA fastpath, which changes the policy's numerics and
            # breaks bit-faithful replay of the evaluator; the overlay gets a perception without `ie`.
            film.overlay = SceneOverlay(raw, robot, foot_ids_r, type("NoAttention", (), {})(), env_index=film_env,
                                        saturation_multiplier=film.style["values"]["overlay_saturation"])
            film.legend = LEGEND
        checkpoint_sha = hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
        args.out.mkdir(parents=True, exist_ok=True)
        cases = {}
        order = [*settings["judge_cases"], *settings["record_cases"]]
        if args.case_id not in order:
            raise ValueError("--case-id is not a D44 case of this plan")
        # The evaluator runs its cases in one process, in this order; state carries over, so a
        # faithful run replays the earlier cases (not filmed) before the filmed one.
        for case_id in order[:order.index(args.case_id) + 1]:
            spec = settings["case_specs"][case_id]
            if case_id != args.case_id:
                _run_cell(env, raw, robot, sensor, body_ids, sensor_ids, term, runner,
                          case_id, spec, dt, checkpoint_preparation)
                print("D44_PRIOR_CASE_REPLAYED", case_id, flush=True)
                continue
            try:
                trace = _run_cell(env, raw, robot, sensor, body_ids, sensor_ids, term, runner,
                                  case_id, spec, dt, checkpoint_preparation, film=film)
            finally:
                if film is not None:
                    film.close()
            scored = summarize(trace, spec=spec, anchors=tile["anchors_local_m"], settings=settings, dt=dt)
            reference = json.loads(args.reference_json.read_text(encoding="utf-8"))["per_env"]
            keys = ("success", "reason")
            diffs = [e for e in range(args.envs)
                     if any(scored["per_env"][e].get(k) != reference[e].get(k) for k in keys)]
            fidelity = {"reference_json": str(args.reference_json),
                        "reference_sha256": hashlib.sha256(args.reference_json.read_bytes()).hexdigest(),
                        "compared_envs": args.envs, "different_envs": diffs,
                        "same": not diffs, "keys": list(keys)}
            print("D44_FIDELITY", json.dumps(fidelity), flush=True)
            picked = scored["per_env"][args.film_env]
            print("D44_FILM_ENV", args.film_env, picked.get("success"), picked.get("reason"), flush=True)
            if film is not None and not diffs:
                from foothold_s2.eval.ex42_d44_video import (_overlay_result, command_order, FPS, WIDTH, HEIGHT,
                                                             sha256_file)
                from foothold_s2.eval.c_layer_frame_audit import audit_video
                final = film.path
                _overlay_result(film.raw_path, final, case_id=f"{case_id} env {args.film_env}",
                                start_position="approach" if spec["task"] == "stop_restart" else "landing_center",
                                sequence=command_order(spec["task"]), success=bool(picked.get("success")),
                                failure_reasons=[str(picked.get("reason"))])
                audit = audit_video(final, expected=len(film.screen), width=WIDTH, height=HEIGHT,
                                    screen_evidence=film.screen, robot_instance_evidence=film.robots)
                film.raw_path.unlink()
                receipt = {"schema": "foothold-ex42-d44-select-video/1", "case_id": case_id,
                           "film_env": args.film_env, "envs": args.envs, "per_env_row": picked,
                           "fidelity": fidelity, "frames": audit["frames"], "frame_audit": audit,
                           "video": str(final), "video_sha256": sha256_file(final),
                           "checkpoint": str(args.checkpoint.resolve()), "style": film.style,
                           "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
                           "screen_evidence": film.screen, "robot_instance_evidence": film.robots}
                final.with_suffix(".json").write_text(json.dumps(receipt, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                print("D44_SELECT_VIDEO_DONE", final, audit["pass"], flush=True)
                composed = write_capture_and_compose(film, spec, case_id, picked, dt, hashlib.sha256(
                    args.checkpoint.read_bytes()).hexdigest(), replica["mesh_sha256"])
                print("D44_COMPOSED", composed["output"], composed["frames"], composed["video_rule_version"], flush=True)
            raw_file = args.out / f"{case_id}.npz"
            np.savez_compressed(raw_file, **trace)
            row = {"case_id": case_id, "task": spec["task"], "map_mode": spec["map_mode"],
                   "role": spec["role"], **scored,
                   "trace_file": str(raw_file),
                   "trace_sha256": hashlib.sha256(raw_file.read_bytes()).hexdigest()}
            case_file = args.out / f"{case_id}.json"
            case_file.write_text(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
            cases[case_id] = {key: row[key] for key in ("case_id", "task", "map_mode", "role",
                "envs", "valid_count", "success_count", "survival_count", "trace_file", "trace_sha256")}
            cases[case_id].update(raw_file=str(case_file), raw_sha256=hashlib.sha256(case_file.read_bytes()).hexdigest())
            print("D44_CASE_DONE", case_id, scored["valid_count"], scored["success_count"],
                  scored["survival_count"], flush=True)
        result = {"format": RECEIPT_FORMAT, "state": "done",
                  "checkpoint": str(args.checkpoint.resolve()), "checkpoint_sha256": checkpoint_sha,
                  "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(), "source_mesh_sha256": source["mesh_sha256"],
                  "replica_mesh_sha256": replica["mesh_sha256"], "seed": args.seed, "envs": args.envs,
                  "dt": dt, "dr_disabled": disabled,
                  "run_identity": run_identity.safe_collect(args.device, checkpoint_sha, eval_seed=args.seed),
                  "checkpoint_preparation": checkpoint_preparation, "cases": cases}
        result["evaluation_friction"] = ex42_friction.verify(raw, friction_policy)
        (args.out / "d44_cells.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print("D44_EVAL_DONE", args.out, flush=True)
        if not (args.out / "d44_cells.json").is_file():
            raise RuntimeError("D44 child returned without its result receipt")
    except BaseException as exc:
        print("D44_FAILED", phase, repr(exc), file=sys.stderr, flush=True)
        traceback.print_exc()
        # Isaac Kit's close path can turn an uncaught child exception into rc 0.
        # A failed evaluation must never look like a successful empty receipt.
        os._exit(1)
    finally:
        if env is not None:
            env.close()
        app.close()


if __name__ == "__main__":
    main()
