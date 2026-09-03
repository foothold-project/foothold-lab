"""평지 Go2 대군을 지정 대열과 카메라로 촬영한다. #99 발표 자산."""
import argparse, hashlib, json, math, os, statistics, sys, time

# Windows Kit 기동 전 필수 import 순서.
import torch
from tensordict import TensorDict  # noqa: F401
import rsl_rl.runners  # noqa: F401
from isaaclab.app import AppLauncher

p = argparse.ArgumentParser()
p.add_argument("--checkpoint", required=True); p.add_argument("--output_dir", required=True)
p.add_argument("--cut", required=True, choices=("A", "B"))
p.add_argument("--view", required=True, choices=("chase", "topdown", "front", "dolly", "aisle", "macro", "hero"))
p.add_argument("--num_envs", type=int, required=True); p.add_argument("--columns", type=int, required=True)
p.add_argument("--rows", type=int, required=True); p.add_argument("--spacing", type=float, required=True)
p.add_argument("--width", type=int, default=1920); p.add_argument("--height", type=int, default=1080)
p.add_argument("--crf", type=int, default=20); p.add_argument("--preset", default="slow")
p.add_argument("--warmup_frames", type=int, default=8); p.add_argument("--seed", type=int, default=42)
p.add_argument("--eval_duration", type=float, default=20.0); p.add_argument("--command_vx", type=float, default=1.0)
p.add_argument("--spawn_xy_range", type=float, default=0.10)
p.add_argument("--yaw_range_deg", type=float, default=5.0); p.add_argument("--joint_pos_scale", type=float, default=0.05)
AppLauncher.add_app_launcher_args(p)
args, _ = p.parse_known_args(); args.enable_cameras = True
if args.num_envs != args.columns * args.rows: p.error("num_envs must equal columns * rows")

STARTED = time.perf_counter(); app = AppLauncher(args).app
import imageio.v2 as imageio
import numpy as np
from rsl_rl.runners import OnPolicyRunner
import isaaclab.sim as sim_utils
from isaaclab.envs import ManagerBasedRLEnv
from isaaclab.utils.assets import retrieve_file_path
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
import isaaclab_tasks  # noqa: F401
from isaaclab_tasks.utils import load_cfg_from_registry
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
from generalization_env_cfg import UnitreeGo2GeneralizationEnvCfg

TASK = "Isaac-Velocity-Rough-Unitree-Go2-v0"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1048576), b""): h.update(block)
    return h.hexdigest()


def configure(cfg, agent):
    cfg.seed = agent.seed = args.seed; cfg.scene.num_envs = args.num_envs
    cfg.scene.terrain.terrain_type = "plane"; cfg.scene.terrain.terrain_generator = None
    cfg.scene.terrain.env_spacing = args.spacing; cfg.episode_length_s = args.eval_duration
    cfg.curriculum.terrain_levels = None; cfg.observations.policy.enable_corruption = False
    cmd = cfg.commands.base_velocity
    cmd.ranges.lin_vel_x = (args.command_vx, args.command_vx); cmd.ranges.lin_vel_y = (0.0, 0.0)
    cmd.ranges.ang_vel_z = (0.0, 0.0); cmd.heading_command = False
    cmd.rel_heading_envs = 0.0; cmd.rel_standing_envs = 0.0; cmd.debug_vis = False
    for name in ("push_robot", "base_external_force_torque", "add_base_mass", "base_com"):
        if hasattr(cfg.events, name): setattr(cfg.events, name, None)
    yaw = math.radians(args.yaw_range_deg)
    cfg.events.reset_base.params["pose_range"] = {"x": (-args.spawn_xy_range, args.spawn_xy_range), "y": (-args.spawn_xy_range, args.spawn_xy_range), "yaw": (-yaw, yaw)}
    cfg.events.reset_base.params["velocity_range"] = {k: (0.0, 0.0) for k in ("x", "y", "z", "roll", "pitch", "yaw")}
    cfg.events.reset_robot_joints.params["position_range"] = (1.0 - args.joint_pos_scale, 1.0 + args.joint_pos_scale)
    cfg.events.reset_robot_joints.params["velocity_range"] = (0.0, 0.0)
    cfg.viewer.resolution = (args.width, args.height); cfg.viewer.origin_type = "world"
    if getattr(args, "device", None): cfg.sim.device = agent.device = args.device


def origins(device):
    row = torch.arange(args.rows, device=device, dtype=torch.float32)
    col = torch.arange(args.columns, device=device, dtype=torch.float32)
    rr, cc = torch.meshgrid(row, col, indexing="ij")
    out = torch.zeros((args.num_envs, 3), device=device)
    out[:, 0] = (-(rr - (args.rows - 1) / 2) * args.spacing).flatten()
    out[:, 1] = ((cc - (args.columns - 1) / 2) * args.spacing).flatten()
    return out


def camera():
    depth = (args.rows - 1) * args.spacing; width = (args.columns - 1) * args.spacing
    rear, front = -depth / 2, depth / 2; finish = front + args.eval_duration * args.command_vx
    if args.view == "chase": eye, target = (rear - 15, 0, 3), (rear + 18, 0, 0.45)
    elif args.view == "front": eye, target = (finish + 40, 0, 2), (front + 8, 0, 0.45)
    elif args.view == "topdown":
        vfov = 2 * math.atan(math.tan(math.radians(30)) * args.height / args.width)
        height = max((width + 8) / (2 * math.tan(math.radians(30))), (depth + 28) / (2 * math.tan(vfov / 2)), 12)
        eye, target = (9, 0, height), (10, 0, 0)
    else: eye, target = camera_at(0.0)
    return {"view": args.view, "eye_m": list(eye), "target_m": list(target), "horizontal_fov_deg": 60.0}


def camera_at(s):
    depth = (args.rows - 1) * args.spacing; width = (args.columns - 1) * args.spacing
    rear, front = -depth / 2, depth / 2; finish = front + args.eval_duration * args.command_vx
    vfov = 2 * math.atan(math.tan(math.radians(30)) * args.height / args.width)
    top_h = max((width + 8) / (2 * math.tan(math.radians(30))), (depth + 28) / (2 * math.tan(vfov / 2)), 12)
    lerp = lambda a, b: a + (b - a) * s
    if args.view == "dolly":
        eye = (lerp(rear - 8.0, 9.0), 0.0, 0.5 * (top_h / 0.5) ** s)
        target = (lerp(rear + 10.0, 10.0), 0.0, lerp(0.4, 0.0))
    elif args.view in ("aisle", "macro"):
        x0 = rear + 1.5 * args.spacing; cx = x0 + args.command_vx * args.eval_duration * s
        if args.view == "aisle": eye, target = (cx, 0.0, 0.45), (cx + 15.0, 0.0, 0.35)
        else: eye, target = (cx, 0.0, 0.22), (cx + 3.0, 0.0, 0.18)
    else:
        eye = (finish + 6.0, 0.0, 0.6)
        target = (lerp(front + 4.0, finish), 0.0, 0.45)
    return eye, target


def gate(width):
    cfg = sim_utils.CuboidCfg(size=(0.16, width + 8, 0.016), visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.95, 0.18, 0.04), emissive_color=(0.95, 0.18, 0.04), roughness=0.9))
    cfg.func("/World/ArmyGate10m", cfg, translation=(10.0, 0.0, 0.008))


def main():
    os.makedirs(args.output_dir, exist_ok=True); previews = os.path.join(args.output_dir, "previews"); os.makedirs(previews, exist_ok=True)
    cfg = UnitreeGo2GeneralizationEnvCfg(); agent = load_cfg_from_registry(TASK, "rsl_rl_cfg_entry_point"); configure(cfg, agent)
    env_started = time.perf_counter(); raw = ManagerBasedRLEnv(cfg=cfg, render_mode="rgb_array")
    expected = origins(raw.device); raw.scene.terrain.env_origins[:] = expected; raw.reset(); env_ready = time.perf_counter()
    err = float(torch.max(torch.abs(raw.scene.env_origins.detach().cpu() - expected.cpu())).item())
    if err > 1e-6: raise RuntimeError(f"env_origins mismatch: {err}")
    width = (args.columns - 1) * args.spacing; depth = (args.rows - 1) * args.spacing
    gate(width); cam = camera()
    moving_camera = args.view in ("dolly", "aisle", "macro", "hero")
    if not moving_camera: raw.sim.set_camera_view(eye=cam["eye_m"], target=cam["target_m"])
    env = RslRlVecEnvWrapper(raw, clip_actions=agent.clip_actions); checkpoint = retrieve_file_path(args.checkpoint)
    runner = OnPolicyRunner(env, agent.to_dict(), log_dir=None, device=agent.device); runner.load(checkpoint)
    policy = runner.get_inference_policy(device=raw.device); policy_nn = runner.alg.policy; obs = env.get_observations()
    policy_ready = time.perf_counter()
    for _ in range(args.warmup_frames): raw.render()
    warmup_done = time.perf_counter(); fps = int(round(1 / raw.step_dt)); count = int(round(args.eval_duration * fps))
    stem = f"flat_army_{args.cut}_{args.num_envs}_{args.view}"; video = os.path.join(args.output_dir, stem + ".mp4")
    writer = imageio.get_writer(video, fps=fps, codec="libx264", quality=None, macro_block_size=8, pixelformat="yuv420p", output_params=["-crf", str(args.crf), "-preset", args.preset])
    if moving_camera: preview_indices = (0, 250, 500, 750, count - 1)
    else: preview_indices = (0, max(0, count // 2 - 1), count - 1)
    renders, steps = [], []; saved = {}; rec_start = time.perf_counter()
    try:
        t = time.perf_counter()
        if moving_camera:
            eye, target = camera_at(0.0); raw.sim.set_camera_view(eye=eye, target=target)
        frame = np.ascontiguousarray(raw.render()); writer.append_data(frame); renders.append(time.perf_counter() - t)
        name = f"{args.cut}_{args.view}_frame0000.png"; imageio.imwrite(os.path.join(previews, name), frame); saved["0"] = name
        for i in range(1, count):
            t = time.perf_counter()
            with torch.inference_mode(): actions = policy(obs); obs, _, dones, _ = env.step(actions); policy_nn.reset(dones)
            steps.append(time.perf_counter() - t); t = time.perf_counter()
            if moving_camera:
                eye, target = camera_at(i / (count - 1)); raw.sim.set_camera_view(eye=eye, target=target)
            frame = np.ascontiguousarray(raw.render()); writer.append_data(frame); renders.append(time.perf_counter() - t)
            if i in preview_indices:
                name = f"{args.cut}_{args.view}_frame{i:04d}.png"; imageio.imwrite(os.path.join(previews, name), frame); saved[str(i)] = name
            if (i + 1) % 50 == 0: print(f"[{args.cut}/{args.view}] {i + 1}/{count} elapsed={time.perf_counter() - rec_start:.1f}s", flush=True)
    finally: writer.close()
    rec_end = time.perf_counter(); check = {"status": "pending external av inspection", "preview_frames": saved}
    data = {"argv": sys.argv, "cut": args.cut, "video": os.path.basename(video), "bytes": os.path.getsize(video), "num_envs": args.num_envs, "formation": {"columns": args.columns, "rows": args.rows}, "formation_extent_m": {"width": width, "depth": depth}, "spacing_m": args.spacing, "camera": cam, "gate_line": {"progress_m": 10.0, "visible": True}, "resolution": [args.width, args.height], "fps": fps, "frames": count, "video_duration_s": count / fps, "seed": args.seed, "command_vx_mps": args.command_vx, "eval_duration_s": args.eval_duration, "spawn_xy_range_m": args.spawn_xy_range, "yaw_range_deg": args.yaw_range_deg, "joint_pos_scale": args.joint_pos_scale, "policy_checkpoint": checkpoint, "policy_sha256": sha256(checkpoint), "env_origins_max_error_m": err, "encoding": {"codec": "libx264", "crf": args.crf, "preset": args.preset}, "timing_s": {"app_and_imports": env_started - STARTED, "environment_creation_and_reset": env_ready - env_started, "policy_load": policy_ready - env_ready, "render_warmup": warmup_done - policy_ready, "recording_total": rec_end - rec_start, "render_per_frame_mean": statistics.mean(renders), "render_per_frame_median": statistics.median(renders), "simulation_step_mean": statistics.mean(steps), "process_total": rec_end - STARTED}, "frame_inspection": check}
    with open(os.path.join(args.output_dir, stem + ".json"), "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
    print(json.dumps(data, ensure_ascii=False, indent=2), flush=True); env.close()


if __name__ == "__main__":
    try: main()
    finally: app.close()
