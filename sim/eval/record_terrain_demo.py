"""평지 Go2 대군을 지정 대열과 카메라로 촬영한다. 런칭 영상 A 재료 렌더.

record_flat_army.py 에서 갈라져 나왔다. 추가한 것은 카메라 뷰 여덟 개와
지형 인자, 감속 경사다. NVIDIA rough 체크포인트로 평지에서 굴린다.
평가 데이터가 아니라 영상 소재용이다.

뷰
  horizon    지평선에서 대군이 다가온다 (카메라 고정, horizon_dist 로 거리)
  firststep  대열 앞 빈 자리에서 다리가 들어온다 (개미 샷)
  belowfoot  발밑에서 올려다본다
  legs       대열 안쪽 다리 높이 (decel_start 로 감속 정지)
  column     일렬 종대 (column_origins CSV)
  orbit      선회 (dense_origins CSV 로 조밀하게)
  retreat    정지 대군 위를 뒤로 빠진다 (grid_origins CSV)
  climb      14 m 에서 929 m 까지 끝까지 가속 상승, 워드마크로 착지
  prelude    정지 대열 낮은 부감

원점 CSV
  column_origins_256   256 대 한 줄 (일렬 종대)
  dense_origins_4096   64x64 간격 1.2 m (조밀 선회)
  grid_origins_4096    128x32 진행축 긴 격자 (끝없는 대열)
"""
import argparse, csv, hashlib, json, math, os, statistics, sys, time

# Windows Kit 기동 전 필수 import 순서.
ORIGINAL_ARGV = list(sys.argv)
prelaunch_argv = [sys.argv[0]]
skip_next = False
for token in sys.argv[1:]:
    if skip_next:
        skip_next = False
    elif token in ("--view", "--hfov", "--gate", "--origins_csv"):
        skip_next = True
    elif not token.startswith("--view=") and not token.startswith("--hfov=") and not token.startswith("--gate=") and not token.startswith("--origins_csv="):
        prelaunch_argv.append(token)
sys.argv[:] = prelaunch_argv
import torch
from tensordict import TensorDict  # noqa: F401
import rsl_rl.runners  # noqa: F401
from isaaclab.app import AppLauncher
sys.argv[:] = ORIGINAL_ARGV

p = argparse.ArgumentParser()
p.add_argument("--checkpoint", required=True); p.add_argument("--output_dir", required=True)
p.add_argument("--terrain", default="plane")
p.add_argument("--horizon_dist", type=float, default=180.0)
p.add_argument("--decel_start", type=float, default=-1.0, help="이 초부터 감속을 시작한다")
p.add_argument("--decel_secs", type=float, default=2.0, help="감속에 걸리는 시간")
p.add_argument("--terrain_rows", type=int, default=8)
p.add_argument("--terrain_cols", type=int, default=8)
p.add_argument("--cut", required=True, choices=("A", "B", "F"))
p.add_argument("--view", required=True, choices=("chase", "topdown", "front", "dolly", "aisle", "macro", "hero", "lead", "foot", "side", "orbit", "rise", "underfoot", "formation", "climb", "horizon", "legs", "firststep", "belowfoot", "column", "prelude", "retreat"))
p.add_argument("--num_envs", type=int, required=True); p.add_argument("--columns", type=int, required=True)
p.add_argument("--rows", type=int, required=True); p.add_argument("--spacing", type=float, required=True)
p.add_argument("--width", type=int, default=1920); p.add_argument("--height", type=int, default=1080)
p.add_argument("--crf", type=int, default=20); p.add_argument("--preset", default="slow")
p.add_argument("--warmup_frames", type=int, default=8); p.add_argument("--seed", type=int, default=42)
p.add_argument("--eval_duration", type=float, default=20.0); p.add_argument("--command_vx", type=float, default=1.0)
p.add_argument("--spawn_xy_range", type=float, default=0.10)
p.add_argument("--yaw_range_deg", type=float, default=5.0); p.add_argument("--joint_pos_scale", type=float, default=0.05)
p.add_argument("--hfov", dest="camera_hfov", type=float, default=60.0)
p.add_argument("--gate", dest="gate_mode", choices=("on", "off"), default="on")
p.add_argument("--origins_csv", default="")
AppLauncher.add_app_launcher_args(p)
args, _ = p.parse_known_args(); args.enable_cameras = True
if args.num_envs != args.columns * args.rows: p.error("num_envs must equal columns * rows")
VIEW = args.view; CAMERA_HFOV = args.camera_hfov; GATE_MODE = args.gate_mode; ORIGINS_CSV = args.origins_csv
del args.view, args.camera_hfov, args.gate_mode, args.origins_csv
launcher_argv = [sys.argv[0]]
skip_next = False
for token in sys.argv[1:]:
    if skip_next:
        skip_next = False
    elif token in ("--view", "--hfov", "--gate", "--origins_csv"):
        skip_next = True
    elif not token.startswith("--view=") and not token.startswith("--hfov=") and not token.startswith("--gate=") and not token.startswith("--origins_csv="):
        launcher_argv.append(token)
sys.argv[:] = launcher_argv

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
    if args.terrain == "plane":
        cfg.scene.terrain.terrain_type = "plane"; cfg.scene.terrain.terrain_generator = None
    else:
        cfg.scene.terrain.terrain_type = "generator"
        tg = cfg.scene.terrain.terrain_generator
        if args.terrain != "all":
            keep = {k: v for k, v in tg.sub_terrains.items() if k == args.terrain}
            if not keep:
                raise SystemExit("모르는 지형: " + args.terrain + " / 가능: " + ",".join(tg.sub_terrains))
            for v in keep.values(): v.proportion = 1.0
            tg.sub_terrains = keep
        tg.num_rows = args.terrain_rows; tg.num_cols = args.terrain_cols
        tg.curriculum = False
    cfg.scene.terrain.env_spacing = args.spacing; cfg.episode_length_s = args.eval_duration
    cfg.curriculum.terrain_levels = None; cfg.observations.policy.enable_corruption = False
    cmd = cfg.commands.base_velocity
    cmd.ranges.lin_vel_x = (args.command_vx, args.command_vx); cmd.ranges.lin_vel_y = (0.0, 0.0)
    globals()["_CMD"] = cmd
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
    if ORIGINS_CSV:
        with open(ORIGINS_CSV, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if len(rows) != args.num_envs:
            raise RuntimeError(f"origins CSV row count mismatch: expected={args.num_envs}, actual={len(rows)}")
        try:
            xy = [[float(row["x_m"]), float(row["y_m"])] for row in rows]
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("origins CSV must contain numeric x_m,y_m columns") from exc
        out = torch.zeros((args.num_envs, 3), device=device)
        out[:, :2] = torch.tensor(xy, device=device, dtype=torch.float32)
        return out
    row = torch.arange(args.rows, device=device, dtype=torch.float32)
    col = torch.arange(args.columns, device=device, dtype=torch.float32)
    rr, cc = torch.meshgrid(row, col, indexing="ij")
    out = torch.zeros((args.num_envs, 3), device=device)
    out[:, 0] = (-(rr - (args.rows - 1) / 2) * args.spacing).flatten()
    out[:, 1] = ((cc - (args.columns - 1) / 2) * args.spacing).flatten()
    return out


TERRAIN_BOX = None


def camera():
    if TERRAIN_BOX is not None:
        x0,x1,y0,y1,z = TERRAIN_BOX
        cx,cy = (x0+x1)/2,(y0+y1)/2
        span = max(x1-x0, y1-y0)
        if VIEW == "topdown":
            return {"view":VIEW,"eye_m":[cx-1,cy,z+span*1.1],"target_m":[cx,cy,z],"horizontal_fov_deg":None}
        if VIEW == "front":
            return {"view":VIEW,"eye_m":[x1+span*0.35,cy,z+1.6],"target_m":[cx,cy,z+0.35],"horizontal_fov_deg":None}
        return {"view":VIEW,"eye_m":[cx,y0-span*0.45,z+1.1],"target_m":[cx,cy,z+0.35],"horizontal_fov_deg":None}
    depth = (args.rows - 1) * args.spacing; width = (args.columns - 1) * args.spacing
    rear, front = -depth / 2, depth / 2; finish = front + args.eval_duration * args.command_vx
    if VIEW == "column":
        # 일렬 종대. 줄 옆 낮은 자리에서 줄을 따라 멀리 본다.
        eye = (front - 8.0, 2.4, 0.55)
        target = (front - 40.0, 0.0, 0.5)
        return {"view": VIEW, "eye_m": list(eye), "target_m": list(target), "horizontal_fov_deg": None}
    if VIEW == "prelude":
        # 멈춘 대열 위 낮은 부감. 끝 자세가 climb 의 시작 자세와 같다.
        eye = (-70.0, 0.0, 10.0)
        target = (0.0, 0.0, 0.8)
        return {"view": VIEW, "eye_m": list(eye), "target_m": list(target), "horizontal_fov_deg": None}
    if VIEW == "firststep":
        # 대열 앞의 빈 자리. 지면에 붙인다. 다리가 걸어 들어온다.
        # 바닥을 내려다본다. 지평선이 안 보여서 화면이 빈다.
        eye = (front + 11.0, 0.0, 0.62)
        target = (front + 5.5, 0.0, 0.0)
        return {"view": VIEW, "eye_m": list(eye), "target_m": list(target), "horizontal_fov_deg": None}
    if VIEW == "belowfoot":
        # 발밑. 몸통보다 낮게 두고 살짝 올려다본다.
        eye = (front - 4.0, 0.0, 0.13)
        target = (front - 12.0, 0.0, 0.62)
        return {"view": VIEW, "eye_m": list(eye), "target_m": list(target), "horizontal_fov_deg": None}
    if VIEW == "legs":
        # 다리 높이. 여러 마리의 다리가 한 화면에.
        # 대열 안쪽. 몇 미터 앞의 다리만 화면에 든다.
        eye = (front + args.horizon_dist, 0.0, 0.26)
        target = (front + args.horizon_dist - 5.0, 0.0, 0.34)
        return {"view": VIEW, "eye_m": list(eye), "target_m": list(target), "horizontal_fov_deg": None}
    if VIEW == "horizon":
        # 카메라는 거의 고정. 커지는 것은 그들이 다가와서다.
        eye = (front + args.horizon_dist, 0.0, 1.7)
        target = (front, 0.0, 0.75)
    elif VIEW == "formation": eye, target = (-1.0, 0.0, 927.988), (0.0, 0.0, 0.0)
    elif VIEW == "chase": eye, target = (rear - 15, 0, 3), (rear + 18, 0, 0.45)
    elif VIEW == "front": eye, target = (finish + 40, 0, 2), (front + 8, 0, 0.45)
    elif VIEW == "topdown":
        vfov = 2 * math.atan(math.tan(math.radians(30)) * args.height / args.width)
        height = max((width + 8) / (2 * math.tan(math.radians(30))), (depth + 28) / (2 * math.tan(vfov / 2)), 12)
        eye, target = (9, 0, height), (10, 0, 0)
    else: eye, target = camera_at(0.0)
    return {"view": VIEW, "eye_m": list(eye), "target_m": list(target), "horizontal_fov_deg": None}


def camera_at(s):
    depth = (args.rows - 1) * args.spacing; width = (args.columns - 1) * args.spacing
    rear, front = -depth / 2, depth / 2; finish = front + args.eval_duration * args.command_vx
    vfov = 2 * math.atan(math.tan(math.radians(30)) * args.height / args.width)
    top_h = max((width + 8) / (2 * math.tan(math.radians(30))), (depth + 28) / (2 * math.tan(vfov / 2)), 12)
    lerp = lambda a, b: a + (b - a) * s
    if VIEW == "climb":
        # 등속이 아니라 가속. 뒤로 갈수록 더 많이 드러난다.
        a = s ** 2.6                         # 끝까지 가속. 감속 구간을 없앤다
        # 400 m 에서 멈춘다. 928 m 는 글자가 얼룩이 되는 높이다.
        h = 14.0 + (929.0 - 14.0) * a
        back = -70.0 + (-1.0 + 70.0) * a
        eye = (back, 0.0, h)
        tgt = (0.0, 0.0, 0.0) if a > 0.15 else (0.0, 0.0, 0.9 * (1 - a / 0.15))
        return eye, tgt
    if VIEW == "retreat":
        # 정지 대군 위를 뒤로 빠지며 오른다. 빠질수록 끝없는 대열이 드러난다.
        a = s ** 1.5
        back = -8.0 - (55.0 - 8.0) * a
        h = 2.0 + (22.0 - 2.0) * a
        return (back, 0.0, h), (back + 30.0, 0.0, 0.6)
    if VIEW == "dolly":
        eye = (lerp(rear - 8.0, 9.0), 0.0, 0.5 * (top_h / 0.5) ** s)
        target = (lerp(rear + 10.0, 10.0), 0.0, lerp(0.4, 0.0))
    elif VIEW in ("aisle", "macro"):
        x0 = rear + 1.5 * args.spacing; cx = x0 + args.command_vx * args.eval_duration * s
        if VIEW == "aisle": eye, target = (cx, 0.0, 0.45), (cx + 15.0, 0.0, 0.35)
        else: eye, target = (cx, 0.0, 0.22), (cx + 3.0, 0.0, 0.18)
    elif VIEW == "lead":
        lx = front + 7.0 + args.command_vx * args.eval_duration * s
        eye, target = (lx, 0.0, 0.55), (lx - 14.0, 0.0, 0.40)
    elif VIEW == "foot":
        x0 = rear + 1.5 * args.spacing; cx = x0 + args.command_vx * args.eval_duration * s
        eye, target = (cx, 0.0, 0.13), (cx + 3.0, 1.25, 0.20)
    elif VIEW == "side":
        eye, target = (5.0, 0.0, 0.30), (5.0, 14.0, 0.28)
    elif VIEW == "orbit":
        x0 = rear + 1.5 * args.spacing; cx = x0 + args.command_vx * args.eval_duration * s
        th = math.radians(-60.0 + 120.0 * s)
        eye = (cx + 7.0 * math.cos(th), 7.0 * math.sin(th), 1.1)
        target = (cx, 0.0, 0.35)
    elif VIEW == "rise":
        eye, target = (10.0, 0.0, 1.2 * (top_h / 1.2) ** s), (10.0, 0.0, 0.0)
    elif VIEW == "underfoot":
        eye, target = (25.0, 0.0, 0.07), (5.0, 0.0, 0.40)
    else:
        eye = (finish + 6.0, 0.0, 0.6)
        target = (lerp(front + 4.0, finish), 0.0, 0.45)
    return eye, target


def gate(width):
    cfg = sim_utils.CuboidCfg(size=(0.16, width + 8, 0.016), visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.95, 0.18, 0.04), emissive_color=(0.95, 0.18, 0.04), roughness=0.9))
    cfg.func("/World/ArmyGate10m", cfg, translation=(10.0, 0.0, 0.008))


def read_hfov():
    import omni.usd
    from pxr import UsdGeom

    stage = omni.usd.get_context().get_stage()
    cam = UsdGeom.Camera(stage.GetPrimAtPath("/OmniverseKit_Persp"))
    ha = float(cam.GetHorizontalApertureAttr().Get())
    fl = float(cam.GetFocalLengthAttr().Get())
    return math.degrees(2.0 * math.atan(ha / (2.0 * fl))), ha, fl


def set_hfov(deg):
    import omni.usd
    from pxr import UsdGeom

    stage = omni.usd.get_context().get_stage()
    prim = stage.GetPrimAtPath("/OmniverseKit_Persp")
    cam = UsdGeom.Camera(prim) if prim.IsValid() else UsdGeom.Camera.Define(stage, "/OmniverseKit_Persp")
    ha = float(cam.GetHorizontalApertureAttr().Get())
    omni.usd.set_prop_val(cam.GetFocalLengthAttr(), ha / (2.0 * math.tan(math.radians(deg) / 2.0)))
    measured, measured_ha, measured_fl = read_hfov()
    if abs(measured - deg) > 0.1:
        raise RuntimeError(f"horizontal FOV mismatch: requested={deg}, measured={measured}")
    return measured, measured_ha, measured_fl


def initialize_camera(sim, eye, target):
    sim.set_camera_view(eye=eye, target=target)
    if CAMERA_HFOV != 60.0:
        from omni.kit.viewport.utility import get_active_viewport

        viewport = get_active_viewport()
        updates_enabled = viewport.updates_enabled
        viewport.updates_enabled = False
        try: set_hfov(CAMERA_HFOV)
        finally: viewport.updates_enabled = updates_enabled


def main():
    os.makedirs(args.output_dir, exist_ok=True); previews = os.path.join(args.output_dir, "previews"); os.makedirs(previews, exist_ok=True)
    cfg = UnitreeGo2GeneralizationEnvCfg(); agent = load_cfg_from_registry(TASK, "rsl_rl_cfg_entry_point"); configure(cfg, agent)
    env_started = time.perf_counter(); raw = ManagerBasedRLEnv(cfg=cfg, render_mode="rgb_array")
    if args.terrain == "plane":
        expected = origins(raw.device); raw.scene.terrain.env_origins[:] = expected; raw.reset()
        err = float(torch.max(torch.abs(raw.scene.env_origins.detach().cpu() - expected.cpu())).item())
        if err > 1e-6: raise RuntimeError(f"env_origins mismatch: {err}")
    else:
        raw.reset(); expected = raw.scene.env_origins.detach().clone(); err = 0.0
        o = expected.detach().cpu()
        global TERRAIN_BOX
        TERRAIN_BOX = (float(o[:,0].min()), float(o[:,0].max()),
                       float(o[:,1].min()), float(o[:,1].max()), float(o[:,2].mean()))
        print(f"[지형] {args.terrain} · x {TERRAIN_BOX[0]:.1f}~{TERRAIN_BOX[1]:.1f} y {TERRAIN_BOX[2]:.1f}~{TERRAIN_BOX[3]:.1f} z {TERRAIN_BOX[4]:.2f}", flush=True)
    env_ready = time.perf_counter()
    if ORIGINS_CSV:
        expected_cpu = expected.detach().cpu()
        depth = float((expected_cpu[:, 0].max() - expected_cpu[:, 0].min()).item())
        width = float((expected_cpu[:, 1].max() - expected_cpu[:, 1].min()).item())
    else:
        width = (args.columns - 1) * args.spacing; depth = (args.rows - 1) * args.spacing
    if GATE_MODE == "on": gate(width)
    cam = camera()
    moving_camera = VIEW in ("dolly", "aisle", "macro", "hero", "lead", "foot", "orbit", "rise", "climb", "retreat")
    if not moving_camera: initialize_camera(raw.sim, cam["eye_m"], cam["target_m"])
    env = RslRlVecEnvWrapper(raw, clip_actions=agent.clip_actions); checkpoint = retrieve_file_path(args.checkpoint)
    runner = OnPolicyRunner(env, agent.to_dict(), log_dir=None, device=agent.device); runner.load(checkpoint)
    policy = runner.get_inference_policy(device=raw.device); policy_nn = runner.alg.policy; obs = env.get_observations()
    policy_ready = time.perf_counter()
    for _ in range(args.warmup_frames): raw.render()
    warmup_done = time.perf_counter(); fps = int(round(1 / raw.step_dt)); count = int(round(args.eval_duration * fps))
    stem = f"flat_army_{args.cut}_{args.num_envs}_{VIEW}"; video = os.path.join(args.output_dir, stem + ".mp4")
    writer = imageio.get_writer(video, fps=fps, codec="libx264", quality=None, macro_block_size=8, pixelformat="yuv420p", output_params=["-crf", str(args.crf), "-preset", args.preset])
    if VIEW == "formation": preview_indices = (0, 50, 150, 500, count - 1)
    elif moving_camera or VIEW in ("side", "underfoot"): preview_indices = (0, 250, 500, 750, count - 1)
    else: preview_indices = (0, max(0, count // 2 - 1), count - 1)
    renders, steps = [], []; saved = {}; rec_start = time.perf_counter()
    try:
        t = time.perf_counter()
        if moving_camera:
            eye, target = camera_at(0.0); initialize_camera(raw.sim, eye, target)
        frame = np.ascontiguousarray(raw.render()); writer.append_data(frame); renders.append(time.perf_counter() - t)
        initial_hfov, horizontal_aperture, focal_length = read_hfov()
        if abs(initial_hfov - CAMERA_HFOV) > 0.1:
            raise RuntimeError(f"initial horizontal FOV mismatch: requested={CAMERA_HFOV}, measured={initial_hfov}")
        name = f"{args.cut}_{VIEW}_frame0000.png"; imageio.imwrite(os.path.join(previews, name), frame); saved["0"] = name
        for i in range(1, count):
            t = time.perf_counter()
            if args.decel_start >= 0:
                tt = i / fps
                if tt <= args.decel_start:
                    v = args.command_vx
                elif tt >= args.decel_start + args.decel_secs:
                    v = 0.0
                else:
                    u = (tt - args.decel_start) / args.decel_secs
                    v = args.command_vx * (1.0 - u) ** 2      # 부드럽게 멎는다
                cm = raw.command_manager.get_command("base_velocity")
                cm[:, 0] = v
            with torch.inference_mode(): actions = policy(obs); obs, _, dones, _ = env.step(actions); policy_nn.reset(dones)
            steps.append(time.perf_counter() - t); t = time.perf_counter()
            if moving_camera:
                eye, target = camera_at(i / (count - 1)); raw.sim.set_camera_view(eye=eye, target=target)
            frame = np.ascontiguousarray(raw.render()); writer.append_data(frame); renders.append(time.perf_counter() - t)
            if i in preview_indices:
                name = f"{args.cut}_{VIEW}_frame{i:04d}.png"; imageio.imwrite(os.path.join(previews, name), frame); saved[str(i)] = name
            if (i + 1) % 50 == 0: print(f"[{args.cut}/{VIEW}] {i + 1}/{count} elapsed={time.perf_counter() - rec_start:.1f}s", flush=True)
    finally: writer.close()
    rec_end = time.perf_counter(); final_hfov, final_ha, final_fl = read_hfov()
    if abs(final_hfov - CAMERA_HFOV) > 0.1: raise RuntimeError(f"final horizontal FOV mismatch: requested={CAMERA_HFOV}, measured={final_hfov}")
    cam["horizontal_fov_deg"] = initial_hfov
    cam["horizontal_aperture"] = horizontal_aperture; cam["focal_length"] = focal_length
    cam["final_horizontal_fov_deg"] = final_hfov; cam["final_horizontal_aperture"] = final_ha; cam["final_focal_length"] = final_fl
    check = {"status": "pending external av inspection", "preview_frames": saved}
    formation = {"columns": args.columns, "rows": args.rows}
    if ORIGINS_CSV: formation = {"origins_csv": ORIGINS_CSV, "rows": args.num_envs}
    data = {"argv": ORIGINAL_ARGV, "cut": args.cut, "video": os.path.basename(video), "bytes": os.path.getsize(video), "num_envs": args.num_envs, "formation": formation, "formation_extent_m": {"width": width, "depth": depth}, "spacing_m": args.spacing, "camera": cam, "gate_line": {"progress_m": 10.0, "visible": GATE_MODE == "on"}, "resolution": [args.width, args.height], "fps": fps, "frames": count, "video_duration_s": count / fps, "seed": args.seed, "command_vx_mps": args.command_vx, "eval_duration_s": args.eval_duration, "spawn_xy_range_m": args.spawn_xy_range, "yaw_range_deg": args.yaw_range_deg, "joint_pos_scale": args.joint_pos_scale, "policy_checkpoint": checkpoint, "policy_sha256": sha256(checkpoint), "env_origins_max_error_m": err, "encoding": {"codec": "libx264", "crf": args.crf, "preset": args.preset}, "timing_s": {"app_and_imports": env_started - STARTED, "environment_creation_and_reset": env_ready - env_started, "policy_load": policy_ready - env_ready, "render_warmup": warmup_done - policy_ready, "recording_total": rec_end - rec_start, "render_per_frame_mean": statistics.mean(renders), "render_per_frame_median": statistics.median(renders), "simulation_step_mean": statistics.mean(steps), "process_total": rec_end - STARTED}, "frame_inspection": check}
    with open(os.path.join(args.output_dir, stem + ".json"), "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
    print(json.dumps(data, ensure_ascii=False, indent=2), flush=True); env.close()


if __name__ == "__main__":
    try: main()
    finally: app.close()
