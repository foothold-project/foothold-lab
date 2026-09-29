"""복원 USD 위 Go2 정책별 보행 계측.

분류: 실험
작성: 오흥재 지시 Codex · 2026-09-16 20:00
근거: WORKER-06-go2.md · sim/eval/record_terrain_demo.py · probe_height_scan.py
요지: 표준 ManagerBasedRLEnv 안에서 A/B 정책을 로드하고 종료 전 상태를 기록한다.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
os.environ["OMNI_KIT_ACCEPT_EULA"] = "YES"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
START = time.perf_counter()
START_ISO = dt.datetime.now().astimezone().isoformat()
OUT = None


def stamp(name, **values):
    row = {"time": dt.datetime.now().astimezone().isoformat(), "pid": os.getpid(),
           "stage": name, **values}
    print(json.dumps(row, ensure_ascii=False), flush=True)
    if OUT is not None:
        with (OUT / "stages.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


stamp("imports_begin")
# Windows Kit startup requires this order, as in record_terrain_demo.py.
import torch
from tensordict import TensorDict  # noqa: F401
import rsl_rl.runners
from isaaclab.app import AppLauncher

p = argparse.ArgumentParser()
p.add_argument("--policy", choices=("A", "B"), required=True)
p.add_argument("--smoke", action="store_true")
p.add_argument("--video", action="store_true")
AppLauncher.add_app_launcher_args(p)
args = p.parse_args()
args.headless = True
args.enable_cameras = args.video
OUT = ROOT / "_out" / "go2" / ("smoke_A" if args.smoke else args.policy)
OUT.mkdir(parents=True, exist_ok=True)
write_json(OUT / "process.json", {"pid": os.getpid(), "started_at": START_ISO, "argv": sys.argv,
                                 "device": args.device, "smoke": args.smoke})
CHECKPOINT = (Path("C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt")
              if args.policy == "A" else REPO / "models" / "foothold-v1.pt")
summary = {"policy": args.policy, "status": "started", "started_at": START_ISO,
           "checkpoint": str(CHECKPOINT), "checkpoint_sha256": sha(CHECKPOINT), "device": args.device,
           "smoke": args.smoke, "video_status": "영상 미수행", "video_reason": "연기 시험 또는 --video 없음",
           "fall_count": None, "scan_finite_ratio_mean": None}
write_json(OUT / "summary.json", summary)
stamp("checkpoint_read_begin")
checkpoint_data = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
state = checkpoint_data["model_state_dict"]
actor_layers = {k: list(v.shape) for k, v in state.items() if "actor" in k and k.endswith("weight") and v.ndim == 2}
first_actor_key = next(k for k in actor_layers if k.endswith("0.weight"))
input_dim = actor_layers[first_actor_key][1]
summary.update(checkpoint_input_dim=input_dim, checkpoint_actor_layers=actor_layers)
write_json(OUT / "summary.json", summary)
stamp("checkpoint_read_end", checkpoint_input_dim=input_dim, actor_layers=actor_layers)
del checkpoint_data, state
stamp("app_launcher_begin")
app = AppLauncher(args).app
stamp("app_launcher_end")


def main():
    import numpy as np
    from scipy.interpolate import RegularGridInterpolator
    from rsl_rl.runners import OnPolicyRunner
    from isaaclab.envs import ManagerBasedRLEnv
    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
    import isaaclab_tasks  # noqa: F401
    from isaaclab_tasks.utils import load_cfg_from_registry
    from isaaclab_tasks.manager_based.locomotion.velocity.config.go2.rough_env_cfg import UnitreeGo2RoughEnvCfg
    from isaaclab.utils.math import euler_xyz_from_quat
    sys.path.insert(0, str(REPO / "sim" / "eval"))

    stats_path = ROOT / "_out" / "mesh" / "ground_stats.json"
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    # ground_stats.json records grid metadata and this companion array artifact.
    # Both are already mesh coordinates: applying world_to_mesh again would be wrong.
    grid_path = stats_path.with_name("grid_audit.npz")
    grid = np.load(grid_path)
    xs, ys, heights = grid["x_m"], grid["y_m"], grid["height_final_m"].copy()
    heights[grid["empty_mask"]] = np.nan
    assert list(heights.shape) == stats["grid"]["shape_yx"]
    assert np.allclose(np.diff(xs), stats["grid"]["cell_m"])
    gx, gy = np.meshgrid(xs, ys)
    center = heights[(gx * gx + gy * gy <= 1.0) & np.isfinite(heights)]
    ground_median = float(np.median(center))
    interp = RegularGridInterpolator((ys, xs), heights, bounds_error=False, fill_value=np.nan)

    cfg = UnitreeGo2RoughEnvCfg()
    agent = load_cfg_from_registry("Isaac-Velocity-Rough-Unitree-Go2-v0", "rsl_rl_cfg_entry_point")
    cfg.seed = agent.seed = 42
    cfg.sim.device = agent.device = args.device
    cfg.scene.num_envs = 1 if args.smoke else 4
    # InteractiveScene overwrites terrain.env_spacing from scene.env_spacing.
    cfg.scene.env_spacing = 1.0
    terrain = cfg.scene.terrain
    terrain.terrain_type = "usd"
    terrain.usd_path = str(stats_path.with_name("ground.usd"))
    terrain.prim_path = "/World/ground"
    terrain.terrain_generator = None
    terrain.env_spacing = 1.0
    cfg.curriculum.terrain_levels = None
    cfg.observations.policy.enable_corruption = False
    cfg.scene.height_scanner.mesh_prim_paths = ["/World/ground"]
    cmd = cfg.commands.base_velocity
    cmd.ranges.lin_vel_x = (0.5, 0.5)
    cmd.ranges.lin_vel_y = (0.0, 0.0)
    cmd.ranges.ang_vel_z = (0.0, 0.0)
    cmd.heading_command = False
    cmd.rel_heading_envs = 0.0
    cmd.rel_standing_envs = 0.0  # Every environment receives the requested 0.5 m/s.
    cfg.episode_length_s = 12.0
    pos = cfg.scene.robot.init_state.pos
    cfg.scene.robot.init_state.pos = (pos[0], pos[1], ground_median + 0.42)
    cfg.events.reset_base.params["pose_range"]["x"] = (-0.3, 0.3)
    cfg.events.reset_base.params["pose_range"]["y"] = (-0.3, 0.3)
    # Leave default yaw and other randomization unchanged, as required by section 1.
    if args.policy == "B":
        from gap_observations import height_scan_with_gap
        cfg.observations.policy.height_scan.func = height_scan_with_gap
        cfg.observations.policy.height_scan.params.update(offset=0.5, miss_value=1.0)
    cfg.viewer.resolution = (1280, 720)
    cfg.viewer.origin_type = "world"
    cfg.viewer.eye = (0.0, -3.0 / math.sqrt(2), 3.0 / math.sqrt(2))
    cfg.viewer.lookat = (0.0, 0.0, 0.0)
    summary["settings"] = {
        "num_envs": cfg.scene.num_envs, "terrain_type": terrain.terrain_type,
        "usd_path": terrain.usd_path, "prim_path": terrain.prim_path, "terrain_generator": None,
        "env_spacing": terrain.env_spacing, "scene_env_spacing": cfg.scene.env_spacing,
        "curriculum_terrain_levels": None,
        "observation_corruption": False, "scanner_mesh_paths": cfg.scene.height_scanner.mesh_prim_paths,
        "velocity_command": [0.5, 0, 0], "heading_command": False, "rel_standing_envs": 0,
        "episode_length_s": cfg.episode_length_s, "duration_s": 2.0 if args.smoke else 12.0,
        "ground_center_radius_m": 1.0, "ground_median_m": ground_median,
        "spawn_z_m": cfg.scene.robot.init_state.pos[2], "reset_pose_range": cfg.events.reset_base.params["pose_range"],
        "height_func": cfg.observations.policy.height_scan.func.__name__,
        "height_offset": cfg.observations.policy.height_scan.params.get("offset", 0.5),
        "miss_value": 1.0 if args.policy == "B" else None,
        "height_clip": cfg.observations.policy.height_scan.clip,
        "seed": cfg.seed, "camera_eye": cfg.viewer.eye, "camera_target": cfg.viewer.lookat,
        "grid_source": str(grid_path), "grid_sha256": sha(grid_path),
        "ground_stats_sha256": sha(stats_path), "usd_sha256": sha(Path(terrain.usd_path)),
        "coordinate_note": "USD and grid are already mesh coordinates; world_to_mesh not applied twice"}
    write_json(OUT / "summary.json", summary)
    stamp("environment_create_begin", settings=summary["settings"])
    raw = ManagerBasedRLEnv(cfg=cfg, render_mode="rgb_array" if args.video else None)
    stamp("environment_create_end")
    stamp("wrapper_begin")
    env = RslRlVecEnvWrapper(raw, clip_actions=agent.clip_actions)
    stamp("wrapper_end")
    stamp("reset_begin")
    obs, _ = env.reset()
    stamp("reset_end")
    obs_dim = int(obs["policy"].shape[-1])
    summary["observation_dim"] = obs_dim
    summary["env_origins"] = raw.scene.env_origins.cpu().tolist()
    if not args.smoke:
        origins = raw.scene.env_origins.cpu().numpy()
        for axis in (0, 1):
            unique = np.unique(origins[:, axis])
            if len(unique) != 2 or not np.allclose(np.diff(unique), 1.0):
                raise RuntimeError(f"Environment spacing mismatch: {origins.tolist()}")
    write_json(OUT / "summary.json", summary)
    stamp("dimension_check", observation_dim=obs_dim, checkpoint_input_dim=input_dim)
    if obs_dim != input_dim:
        raise RuntimeError(f"호환 실패: observation={obs_dim}, checkpoint={input_dim}")
    stamp("runner_load_begin")
    runner = OnPolicyRunner(env, agent.to_dict(), log_dir=None, device=agent.device)
    runner.load(str(CHECKPOINT))
    policy = runner.get_inference_policy(device=raw.device)
    summary["loaded"] = True
    stamp("runner_load_end")

    robot = raw.scene["robot"]
    foot_ids = [robot.find_bodies(prefix + "_foot")[0][0] for prefix in ("FL", "FR", "RL", "RR")]
    term_names = raw.observation_manager._group_obs_term_names["policy"]
    term_dims = raw.observation_manager.group_obs_term_dim["policy"]
    scan_index = term_names.index("height_scan")
    scan_start = sum(int(np.prod(d)) for d in term_dims[:scan_index])
    scan_end = scan_start + int(np.prod(term_dims[scan_index]))
    sensor = raw.scene.sensors["height_scanner"]
    stamp("initial_scan", finite=torch.isfinite(sensor.data.ray_hits_w[..., 2]).sum(dim=1).tolist(),
          rays=int(sensor.data.ray_hits_w.shape[1]), scan_vector_slice=[scan_start, scan_end])
    summary["scan_vector_slice"] = [scan_start, scan_end]
    original_compute = raw.termination_manager.compute
    snapshot = {}

    def capture_before_reset():
        result = original_compute()
        snapshot["position"] = robot.data.root_pos_w.detach().cpu().numpy().copy()
        angles = euler_xyz_from_quat(robot.data.root_quat_w)
        snapshot["roll"] = ((angles[0] + torch.pi) % (2 * torch.pi) - torch.pi).cpu().numpy()
        snapshot["pitch"] = ((angles[1] + torch.pi) % (2 * torch.pi) - torch.pi).cpu().numpy()
        snapshot["feet"] = robot.data.body_pos_w[:, foot_ids, :].detach().cpu().numpy().copy()
        snapshot["fell"] = raw.termination_manager.get_term("base_contact").cpu().numpy().copy()
        snapshot["done"] = result.cpu().numpy().copy()
        snapshot["timeout"] = raw.termination_manager.time_outs.cpu().numpy().copy()
        hits = sensor.data.ray_hits_w[..., 2]
        pre = sensor.data.pos_w[:, 2, None] - hits - 0.5
        snapshot["finite"] = (torch.isfinite(hits) & torch.isfinite(pre)).sum(dim=1).cpu().numpy()
        # Read the observation vector before automatic reset destroys terminal state.
        vector = raw.observation_manager.compute(update_history=False)["policy"]
        snapshot["scan"] = vector[:, scan_start:scan_end].detach().cpu().numpy().copy()
        snapshot["commands"] = raw.command_manager.get_command("base_velocity").cpu().numpy().copy()
        return result

    raw.termination_manager.compute = capture_before_reset
    writer = None
    video_frames = 0
    if args.video:
        try:
            stamp("video_setup_begin")
            import imageio.v2 as imageio
            raw.sim.set_camera_view(eye=cfg.viewer.eye, target=cfg.viewer.lookat)
            for _ in range(8):
                raw.render()
            writer = imageio.get_writer(str(OUT / "run.mp4"), fps=30, codec="libx264",
                                        macro_block_size=8, pixelformat="yuv420p")
            summary["video_reason"] = None
            stamp("video_setup_end")
        except Exception:
            summary["video_reason"] = traceback.format_exc()
            stamp("video_unperformed", error=summary["video_reason"])
    duration = summary["settings"]["duration_s"]
    count = round(duration / raw.step_dt)
    episode_ids = np.zeros(cfg.scene.num_envs, dtype=int)
    start_x = robot.data.root_pos_w[:, 0].cpu().numpy().copy()
    episode_starts = np.zeros(cfg.scene.num_envs)
    episode_samples = np.zeros(cfg.scene.num_envs, dtype=int)
    episodes, rows = [], []
    columns = ["t", "env", "episode", "episode_t", "base_x", "base_y", "base_z", "base_roll", "base_pitch",
               "fell", "done", "timeout", "foot_pen_FL", "foot_pen_FR", "foot_pen_RL", "foot_pen_RR",
               "scan_finite", "scan_rays", "scan_min", "scan_max", "scan_median", "scan_seen_finite",
               "scan_miss_replaced", "progress_x", "command_vx", "command_vy", "command_wz"]
    stamp("policy_loop_begin", steps=count, step_dt=raw.step_dt)
    with (OUT / "trace.csv").open("w", encoding="utf-8", newline="") as f:
        csv_writer = csv.DictWriter(f, fieldnames=columns)
        csv_writer.writeheader()
        for step in range(count):
            with torch.inference_mode():
                actions = policy(obs)
                if not torch.isfinite(actions).all():
                    raise RuntimeError("Non-finite policy actions")
                obs, _, _, _ = env.step(actions)
            t = (step + 1) * raw.step_dt
            feet = snapshot["feet"]
            ground = interp(feet[..., [1, 0]].reshape(-1, 2)).reshape(cfg.scene.num_envs, 4)
            pen = feet[..., 2] - ground - 0.02
            episode_samples += 1
            for e in range(cfg.scene.num_envs):
                scan = snapshot["scan"][e]
                finite_scan = scan[np.isfinite(scan)]
                row = dict(t=t, env=e, episode=int(episode_ids[e]), episode_t=t-episode_starts[e],
                           base_x=float(snapshot["position"][e, 0]), base_y=float(snapshot["position"][e, 1]),
                           base_z=float(snapshot["position"][e, 2]), base_roll=float(snapshot["roll"][e]),
                           base_pitch=float(snapshot["pitch"][e]), fell=int(snapshot["fell"][e]),
                           done=int(snapshot["done"][e]), timeout=int(snapshot["timeout"][e]),
                           scan_finite=int(snapshot["finite"][e]), scan_rays=len(scan),
                           scan_min=float(finite_scan.min()) if finite_scan.size else float("nan"),
                           scan_max=float(finite_scan.max()) if finite_scan.size else float("nan"),
                           scan_median=float(np.median(finite_scan)) if finite_scan.size else float("nan"),
                           scan_seen_finite=int(finite_scan.size),
                           scan_miss_replaced=len(scan)-int(snapshot["finite"][e]) if args.policy == "B" else 0,
                           progress_x=float(snapshot["position"][e, 0]-start_x[e]),
                           command_vx=float(snapshot["commands"][e, 0]),
                           command_vy=float(snapshot["commands"][e, 1]), command_wz=float(snapshot["commands"][e, 2]))
                row.update({"foot_pen_" + name: float(pen[e, j]) for j, name in enumerate(("FL", "FR", "RL", "RR"))})
                csv_writer.writerow(row)
                rows.append(row)
                if snapshot["done"][e] or step == count-1:
                    episodes.append({"env": e, "episode": int(episode_ids[e]), "fell": bool(snapshot["fell"][e]),
                                     "fall_time_s": t if snapshot["fell"][e] else None,
                                     "end_reason": "base_contact" if snapshot["fell"][e] else
                                     ("timeout" if snapshot["timeout"][e] else "window_end_censored"),
                                     "duration_s": t-episode_starts[e], "samples": int(episode_samples[e]),
                                     "progress_x_m": row["progress_x"]})
                    episode_ids[e] += 1
                    start_x[e] = float(robot.data.root_pos_w[e, 0])
                    episode_starts[e] = t
                    episode_samples[e] = 0
            f.flush()
            if writer is not None and video_frames < round(t * 30 + 1e-8):
                try:
                    frame = raw.render()
                    if frame is None or frame.shape[:2] != (720, 1280):
                        raise RuntimeError(f"Unexpected rendered image: {None if frame is None else frame.shape}")
                    writer.append_data(frame)
                    video_frames += 1
                except Exception:
                    summary["video_reason"] = traceback.format_exc()
                    writer.close()
                    writer = None
                    stamp("video_unperformed", error=summary["video_reason"])
            if step == 0 or (step+1) % 25 == 0:
                stamp("policy_step", step=step+1, t=t, video_frames=video_frames)
    if writer is not None:
        stamp("video_close_begin")
        writer.close()
        summary["video_status"] = "완료" if video_frames == round(duration*30) else "영상 미수행"
        summary["video_path"] = str(OUT / "run.mp4")
        stamp("video_close_end", frames=video_frames)
    pens = np.array([[r["foot_pen_" + name] for name in ("FL", "FR", "RL", "RR")] for r in rows])
    evaluable = np.all(np.isfinite(pens), axis=1)
    candidate = np.any(pens < -0.01, axis=1)
    measured_pens = pens[np.isfinite(pens)]
    summary.update(status="completed", inference=True, steps=count, trace_rows=len(rows),
                   episode_count=len(episodes), completed_episode_count=sum(e["end_reason"] != "window_end_censored" for e in episodes),
                   episodes=episodes, fall_count=sum(e["fell"] for e in episodes),
                   progress_x_mean_m=float(np.mean([e["progress_x_m"] for e in episodes])),
                   foot_pen_proxy="발 링크 원점 z - 격자 보간 지면 z - 0.02 m. 실제 접촉점이 아닌 대리 지표.",
                   foot_pen_tolerance_m=0.01, foot_pen_steps=int(candidate.sum()),
                   foot_pen_step_ratio=float(candidate.mean()), foot_pen_all_feet_evaluable_rows=int(evaluable.sum()),
                   foot_pen_missing_rows=int((~evaluable).sum()),
                   foot_pen_max_depth_m=float(max(0, -measured_pens.min())) if measured_pens.size else None,
                   scan_finite_ratio_mean=float(np.mean([r["scan_finite"]/r["scan_rays"] for r in rows])),
                   scan_seen_finite_ratio_mean=float(np.mean([r["scan_seen_finite"]/r["scan_rays"] for r in rows])),
                   video_frames=video_frames, video_fps=30, video_resolution=[1280,720],
                   ended_at=dt.datetime.now().astimezone().isoformat(), wall_seconds=time.perf_counter()-START)
    write_json(OUT / "summary.json", summary)
    stamp("measurement_complete", fall_count=summary["fall_count"], scan_finite_ratio_mean=summary["scan_finite_ratio_mean"])
    stamp("environment_close_begin")
    env.close()
    stamp("environment_close_end")


try:
    main()
except BaseException:
    summary.update(status="failed", error=traceback.format_exc(), ended_at=dt.datetime.now().astimezone().isoformat(),
                   wall_seconds=time.perf_counter()-START)
    write_json(OUT / "summary.json", summary)
    stamp("failed", error=summary["error"])
    raise
finally:
    stamp("app_close_begin")
    app.close()
    stamp("app_close_end")
