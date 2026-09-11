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
p.add_argument("--trace_csv", type=str, default="",
               help="프레임별 계측을 이 자리에 적는다. HUD 를 나중에 얹을 때 쓴다. 안 주면 아무 일도 안 한다.")
p.add_argument("--gate_m", type=float, default=3.0,
               help="HUD 가 그리는 통과선. 평가 하네스의 --min_progress_m 과 맞춘다.")
p.add_argument("--max_lateral_drift", type=float, default=0.75,
               help="HUD 가 그리는 좌우 이탈 문턱. 평가 하네스와 맞춘다.")
p.add_argument("--max_velocity_mae", type=float, default=0.25,
               help="HUD 가 그리는 속도 오차 문턱. 평가 하네스와 맞춘다.")
# 평가 하네스와 «같은 규격» 을 기본으로 쓴다. 영상과 성적표가 어긋나면 안 된다.
p.add_argument("--gap_aware_scan", action="store_true",
               help="(지금은 기본값이라 아무 일도 안 한다. 옛 명령과의 호환용)")
p.add_argument("--legacy_miss_scan", action="store_true",
               help="**결함 규격 1** 로 되돌린다. eval_spec_version=1 로 찍힌 영상을 재현할 때만 쓴다.")
p.add_argument("--difficulty", type=float, default=None,
               help="지형 난이도를 한 값으로 못 박는다. 안 주면 설정 그대로 둔다(예전 동작).")
p.add_argument("--horizon_dist", type=float, default=180.0)
p.add_argument("--decel_start", type=float, default=-1.0, help="이 초부터 감속을 시작한다")
p.add_argument("--decel_secs", type=float, default=2.0, help="감속에 걸리는 시간")
p.add_argument("--terrain_rows", type=int, default=8)
p.add_argument("--terrain_cols", type=int, default=8)
p.add_argument("--cut", required=True, choices=("A", "B", "F"))
p.add_argument("--view", required=True, choices=("chase", "topdown", "front", "dolly", "aisle", "macro", "hero", "lead", "foot", "side", "orbit", "rise", "underfoot", "formation", "climb", "horizon", "legs", "firststep", "belowfoot", "column", "prelude", "retreat",
                              "track_side", "track_q", "track_top", "track_foot", "track_high"))
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
import terrains
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
        if args.difficulty is not None:
            raise SystemExit("평지에는 난이도가 없다. --difficulty 를 빼거나 지형을 고른다.")
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
        # curriculum 이 꺼져 있으면 IsaacLab 은 difficulty_range 에서 타일마다
        # uniform 으로 뽑는다 (terrain_generator.py:229 실측). 범위를 (d, d) 로
        # 좁혀야 모든 타일이 정확히 d 가 된다. num_rows 는 건드릴 필요가 없다.
        globals()["_DIFFICULTY_RANGE"] = terrains.pin_difficulty(tg, args.difficulty)
    # **영상과 성적표가 같은 눈을 써야 한다.** 평가를 새 규격으로 재면서 렌더만
    # 옛 관측으로 두면, 화면에서는 로봇이 틈을 장애물로 보고 표에는 넘는 것으로
    # 나온다. 팀원이 둘을 나란히 놓고 헷갈린다.
    #   구현은 generalization_env_cfg.apply_gap_aware_scan 한 자리에만 둔다.
    globals()["_MISS_VALUE"] = None
    globals()["_SPEC_VERSION"] = 1 if args.legacy_miss_scan else 2
    if not args.legacy_miss_scan:
        from generalization_env_cfg import apply_gap_aware_scan
        globals()["_MISS_VALUE"] = apply_gap_aware_scan(cfg)

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
    # track_* 는 «로봇의 지금 자리»를 읽어 카메라를 둔다. 나머지는 대형 좌표를 쓴다.
    TRACK_VIEWS = ('track_side', 'track_q', 'track_top', 'track_foot', 'track_high')
    moving_camera = VIEW in ("dolly", "aisle", "macro", "hero", "lead", "foot", "orbit", "rise", "climb", "retreat") or VIEW in TRACK_VIEWS
    if not moving_camera: initialize_camera(raw.sim, cam["eye_m"], cam["target_m"])
    env = RslRlVecEnvWrapper(raw, clip_actions=agent.clip_actions); checkpoint = retrieve_file_path(args.checkpoint)
    runner = OnPolicyRunner(env, agent.to_dict(), log_dir=None, device=agent.device); runner.load(checkpoint)
    policy = runner.get_inference_policy(device=raw.device); policy_nn = runner.alg.policy; obs = env.get_observations()
    policy_ready = time.perf_counter()
    for _ in range(args.warmup_frames): raw.render()
    warmup_done = time.perf_counter(); fps = int(round(1 / raw.step_dt)); count = int(round(args.eval_duration * fps))
    stem = f"flat_army_{args.cut}_{args.num_envs}_{VIEW}"; video = os.path.join(args.output_dir, stem + ".mp4")

    # **찍을 수 없는 길이면 writer 를 열기 «전»에 멈춘다.**
    #
    # 열고 나서 멈추면 0장짜리 mp4 가 남는다. 파일이 있으니 성공처럼 보이고,
    # 뒤에 도는 HUD 패스가 그것을 집어 든다. trace 도 최소 2줄을 요구하므로
    # 여기서 같은 문턱으로 막는다 `확인됨` (2026-09-11 검증 · 6차에서 지적).
    if count < 2:
        raise RuntimeError(
            "찍을 프레임이 %d 장이다. --eval_duration %.4f 초에 %d fps 면 너무 짧다. "
            "최소 2장이 필요하다." % (count, args.eval_duration, fps))

    writer = imageio.get_writer(video, fps=fps, codec="libx264", quality=None, macro_block_size=8, pixelformat="yuv420p", output_params=["-crf", str(args.crf), "-preset", args.preset])
    # **count 를 넘는 자리를 넣지 않는다.** 짧은 컷에서 500 을 넣으면 그 장이 안 나온다
    # `확인됨` (2026-09-11 검증 · count=300 인데 500 이 들어 있었다).
    if VIEW == "formation":
        preview_indices = tuple(sorted({i for i in (0, 50, 150, 500, count - 1)
                                        if 0 <= i < max(count, 1)}))
    elif moving_camera or VIEW in ("side", "underfoot"):
        # **count 를 넘는 자리를 넣지 않는다.** 짧은 컷에서 미리보기가 한 장만 나온다.
        preview_indices = tuple(sorted({0, count // 4, count // 2,
                                        3 * count // 4, count - 1}))
    else: preview_indices = (0, max(0, count // 2 - 1), count - 1)
    # trace 를 적을 것인가. 안 주면 None 이라 아래가 전부 건너뛴다.
    trace_rows = [] if args.trace_csv else None
    foot_ids = None
    robot = raw.scene["robot"]

    if trace_rows is not None:
        # 발 body 넷을 FL · FR · RL · RR 순서로 집는다. 못 집으면 그 열만 비운다.
        # **0 으로 채우지 않는다.** 0 은 「쟀는데 0」이라는 뜻이 된다.
        try:
            found, foot_names = robot.find_bodies(".*_foot")
        except Exception as error:  # noqa: BLE001
            found, foot_names = [], []
            print("[WARN] 발 body 조회 실패: %s" % error, flush=True)
        if len(found) == 4:
            order = {"FL": 0, "FR": 1, "RL": 2, "RR": 3}
            slots = [None, None, None, None]
            for body_id, body_name in zip(found, foot_names):
                slot = order.get(body_name.split("_")[0].upper())
                if slot is not None:
                    slots[slot] = body_id
            if all(v is not None for v in slots):
                foot_ids = slots
        if foot_ids is None:
            print("[WARN] 발 body 를 못 집었습니다. 발 높이 열은 빈 칸으로 둡니다.", flush=True)
        else:
            print("[PASS] 발 body %s -> FL/FR/RL/RR 자리 %s" % (foot_names, foot_ids), flush=True)

        # 출발 자세. 전방축·측면축을 여기서 못 박아야 fwd_m · lat_m 이 뜻을 갖는다.
        TRACE_ENV = 0
        trace_start_pos = robot.data.root_pos_w[TRACE_ENV, :2].clone()
        _q = robot.data.root_quat_w[TRACE_ENV]
        _w, _x, _y, _z = (float(_q[0]), float(_q[1]), float(_q[2]), float(_q[3]))
        _yaw = math.atan2(2.0 * (_w * _z + _x * _y), 1.0 - 2.0 * (_y * _y + _z * _z))
        trace_fwd = (math.cos(_yaw), math.sin(_yaw))
        trace_lat = (-trace_fwd[1], trace_fwd[0])

    def trace_row(frame_index, dt_s):
        """프레임 한 장에 대응하는 계측 한 줄. 프레임을 찍는 «그 자리»에서 부른다."""
        e = TRACE_ENV
        q = robot.data.root_quat_w[e]
        w, x, y, z = (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
        roll = math.degrees(math.atan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y)))
        pitch = math.degrees(math.asin(max(-1.0, min(1.0, 2.0 * (w * y - z * x)))))

        # **출발 축에서 얼마나 틀어졌나.** 예전에는 roll·pitch 만 적고 yaw 를
        # 안 적었다. 그래서 「카메라가 왜 도느냐」를 물었을 때 원자료로 답할
        # 수가 없었다 (2026-09-11 · 팀장 지적).
        #
        # 세계 좌표 yaw 를 그대로 쓰지 않고 **출발 축 기준**으로 적는다.
        # 화면에서 「돌았다」는 것은 출발선 대비 틀어진 정도지 세계 좌표계의
        # 절대 각이 아니다. 부호는 왼쪽이 양수다.
        yaw_w = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
        yaw_rel = math.degrees(math.atan2(
            math.sin(yaw_w) * trace_fwd[0] - math.cos(yaw_w) * trace_fwd[1],
            math.cos(yaw_w) * trace_fwd[0] + math.sin(yaw_w) * trace_fwd[1]))

        v = robot.data.root_lin_vel_b[e]
        vx, vy = float(v[0]), float(v[1])

        here = robot.data.root_pos_w[e, :2]
        dx = float(here[0] - trace_start_pos[0])
        dy = float(here[1] - trace_start_pos[1])
        fwd_m = dx * trace_fwd[0] + dy * trace_fwd[1]
        lat_m = dx * trace_lat[0] + dy * trace_lat[1]

        # **설정이 아니라 지금 실제로 주고 있는 명령을 읽는다.** `--decel_start` 로
        # 감속하는 동안 설정은 그대로라서, 설정을 읽으면 영상 위 숫자만 조용히 틀린다.
        try:
            cmd_vx = float(raw.command_manager.get_command("base_velocity")[e, 0])
        except Exception:  # noqa: BLE001
            cmd_vx = float(_CMD.ranges.lin_vel_x[0]) if _CMD is not None else args.command_vx

        row = {
            "frame": frame_index,
            "t_s": round(frame_index * dt_s, 6),
            "cmd_vx_mps": cmd_vx,
            "vx_mps": vx,
            "vy_mps": vy,
            "speed_mps": math.hypot(vx, vy),
            "vel_err_mps": abs(vx - cmd_vx),
            "fwd_m": fwd_m,
            "lat_m": lat_m,
            "base_z_m": float(robot.data.root_pos_w[e, 2]),
            "pitch_deg": pitch,
            "roll_deg": roll,
            "yaw_deg": yaw_rel,
        }
        if foot_ids is not None:
            for name, body_id in zip(("fl", "fr", "rl", "rr"), foot_ids):
                row["foot_z_%s_m" % name] = float(robot.data.body_pos_w[e, body_id, 2])
        return row

    # **카메라 방향은 출발 자세에 못 박는다.**
    #
    # 예전에는 매 프레임 로봇의 «지금» yaw 를 다시 읽어 전방축을 만들었다.
    # 그래서 로봇이 몸을 틀 때마다 카메라가 z 축으로 같이 돌았고, 화면에서는
    # 지형이 통째로 도는 것처럼 보였다 `확인됨` (2026-09-11 · 팀장 지적 ·
    # stepping_stones 앞쪽 비스듬 1.0 m/s). 발 디딜 곳을 찾느라 몸을 가장 많이
    # 비트는 지형에서 가장 심하게 돌았다. 하필 발자리를 봐야 하는 지형이다.
    #
    # 돌 이유가 없다. 명령은 `ang_vel_z = (0, 0)` 에 `heading_command = False`
    # 라 «돌아라» 라고 시킨 적이 없고, 지형도 직선이다. 화면에서 도는 것은
    # 의도가 아니라 자세 흔들림이고, 카메라가 그걸 따라갈 까닭이 없다.
    # yaw 추출식은 roll·pitch 가 클수록 오염되므로 흔들림은 실제보다 커진다.
    #
    # 자리(px·py·pz)는 계속 따라간다. **방향만** 고정한다.
    _cam_axis = []

    def camera_axis():
        """출발 때 한 번 정하고 그대로 쓰는 전방축·측면축."""
        if not _cam_axis:
            q0 = raw.scene["robot"].data.root_quat_w[0]
            w, x, y, z = (float(q0[0]), float(q0[1]), float(q0[2]), float(q0[3]))
            yaw0 = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
            _cam_axis.append((math.cos(yaw0), math.sin(yaw0)))
            print("[PASS] 카메라 축 고정 · 출발 yaw %+.2f도 · 이후 안 돈다"
                  % math.degrees(yaw0), flush=True)
        fx, fy = _cam_axis[0]
        return fx, fy, -fy, fx

    def camera_track():
        """로봇의 지금 «자리» 와 출발 때 고정한 «방향» 에서 카메라 자리를 만든다.

        **대형 좌표를 쓰지 않는다.** 한 마리를 찍을 때 기존 시점이 로봇을
        놓치는 이유가 그것이다 `확인됨` (2026-09-11 · orbit 은 점, macro 는 빈 바닥).
        """
        e = 0
        p = raw.scene["robot"].data.root_pos_w[e]
        px, py, pz = float(p[0]), float(p[1]), float(p[2])
        fx, fy, lx, ly = camera_axis()   # 고정축. 로봇이 몸을 틀어도 화면은 안 돈다

        if VIEW == "track_side":
            # 옆에서. 다리 높이와 장애물 단면이 같이 보인다.
            eye = (px - 0.20 * fx + 2.85 * lx, py - 0.20 * fy + 2.85 * ly, pz + 0.26)
            target = (px + 0.30 * fx, py + 0.30 * fy, pz - 0.08)
        elif VIEW == "track_q":
            # 뒤 비스듬히 위에서. 두루 쓴다.
            eye = (px - 2.5 * fx + 1.55 * lx, py - 2.5 * fy + 1.55 * ly, pz + 1.25)
            target = (px + 1.1 * fx, py + 1.1 * fy, pz - 0.14)
        elif VIEW == "track_top":
            # 바로 위에서. 발이 어디를 디디는지 보인다.
            #
            # **로봇 방향을 쓰지 않는다.** 시선이 거의 수직이면 카메라의 좌우
            # 기울기가 정해지지 않는데, 앞쪽 오프셋까지 로봇 방향으로 잡으면
            # 로봇이 조금만 틀어도 화면이 통째로 돈다 `확인됨` (2026-09-11).
            # 세계 축을 쓰고 오프셋을 키워 시선을 안정시킨다.
            eye = (px, py, pz + 4.0)
            target = (px + 0.45, py, 0.0)
        elif VIEW == "track_high":
            # **앞쪽 비스듬 · «낮은» 각에서 로봇을 마주 본다.**
            #
            # 이름은 track_high 지만 각도는 낮다. 이유가 있다.
            #
            # 몸통이 네 다리 «가운데» 에 있어서, 어느 한 시점으로 넷을 다 볼 수 없다.
            # 위에서 보면 넷 다 가리고(track_top), 앞 45도로 내려봐도 뒷다리 둘이
            # 몸통에 가린다 `확인됨` (2026-09-11 · 팀장 지적 두 번).
            #
            # **각을 낮추면 다리가 바닥과 하늘을 배경으로 실루엣이 되어 몸통 밖으로
            # 벌어져 보인다.** 그래서 카메라 높이를 로봇 몸통(0.42 m)보다 조금만
            # 위인 1.02 m 에 두고, 옆으로 40도쯤 비껴 선다. 비껴 서야 뒷다리가
            # 몸통 윤곽 바깥으로 나온다.
            #
            # 높이를 로봇에 붙이지 않고 «세계 좌표» 로 못 박는다. 로봇이 구덩이에
            # 빠지거나 턱을 오를 때 카메라가 같이 오르내리면 지형이 안 보인다.
            eye = (px + 1.62 * fx + 1.36 * lx, py + 1.62 * fy + 1.36 * ly, 1.02)
            target = (px - 0.20 * fx, py - 0.20 * fy, pz - 0.10)
        else:  # track_foot
            # 앞발 높이에서 앞을 본다. 착지 순간이 크게 보인다.
            eye = (px + 1.75 * fx + 0.72 * lx, py + 1.75 * fy + 0.72 * ly, 0.20)
            target = (px + 0.15 * fx, py + 0.15 * fy, 0.12)
        return eye, target

    renders, steps = [], []; saved = {}; rec_start = time.perf_counter()
    try:
        t = time.perf_counter()
        if moving_camera:
            eye, target = camera_track() if VIEW in TRACK_VIEWS else camera_at(0.0)
            initialize_camera(raw.sim, eye, target)
        # **0프레임도 trace 를 적는다.** 이 render 는 루프 «밖» 이라 빠뜨리기 쉽다.
        # 빠뜨리면 프레임 수와 trace 줄 수가 하나 어긋나고, HUD 를 얹었을 때
        # 모든 숫자가 한 칸씩 밀린다 `확인됨` (2026-09-11 · 300프레임에 299줄).
        if trace_rows is not None:
            trace_rows.append(trace_row(0, 1.0 / capture_fps))
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
                eye, target = (camera_track() if VIEW in TRACK_VIEWS
                               else camera_at(i / (count - 1)))
                raw.sim.set_camera_view(eye=eye, target=target)
            # **trace 는 프레임을 찍기 «직전»에 적는다.** 그래야 줄 번호 = 프레임 번호다.
            if trace_rows is not None:
                trace_rows.append(trace_row(len(trace_rows), 1.0 / fps))
            frame = np.ascontiguousarray(raw.render()); writer.append_data(frame); renders.append(time.perf_counter() - t)
            if i in preview_indices:
                name = f"{args.cut}_{VIEW}_frame{i:04d}.png"; imageio.imwrite(os.path.join(previews, name), frame); saved[str(i)] = name
            if (i + 1) % 50 == 0: print(f"[{args.cut}/{VIEW}] {i + 1}/{count} elapsed={time.perf_counter() - rec_start:.1f}s", flush=True)
    finally: writer.close()

    # **파일을 열어 직접 센다.** writer 를 닫은 «뒤» 다.
    #
    # `len(renders)` 는 인코더에 «건넨» 장수이지 파일에 «들어간» 장수가 아니다.
    # 그것을 결과로 받아들이면 인코더가 흘린 장을 못 잡는다 `확인됨`
    # (2026-09-11 검증 · 6차에서 지적).
    #
    # 메타데이터의 장수도 안 믿는다. 컨테이너 머리말은 실제로 쓰인 것과 다를
    # 수 있다. 끝까지 디코딩해서 센다. 300장에 1초 안쪽이다.
    encoded = 0
    with imageio.get_reader(video) as probe:
        for _ in probe:
            encoded += 1
    print("[PASS] 파일에 실제로 들어간 프레임 %d 장" % encoded, flush=True)

    # trace 를 적는다. **빈 것을 조용히 쓰지 않는다.**
    if trace_rows is not None:
        if len(trace_rows) < 2:
            raise RuntimeError("trace 줄이 %d 개다. 녹화가 안 돌았다." % len(trace_rows))
        # **조용한 어긋남을 막는다.** 줄 수가 프레임 수와 다르면 HUD 가 밀린다.
        if len(trace_rows) != encoded:
            raise RuntimeError(
                "trace 줄 %d 개가 «파일을 열어 센» 프레임 %d 장과 다르다. "
                "HUD 를 얹으면 숫자가 밀린다." % (len(trace_rows), encoded))

    if encoded != count:
        raise RuntimeError(
            "파일에 프레임이 %d 장 들어갔는데 %d 장을 찍으려 했다. "
            "녹화가 중간에 끊겼거나 인코더가 흘렸다." % (encoded, count))

    if trace_rows is not None:
        from overlay import trace as trace_mod
        # **읽는 쪽이 요구하는 메타를 다 채운다.** fps 와 command_vx_mps 가 없으면
        # overlay/render.py 가 KeyError 로 죽는다 (trace.py:121·134).
        trace_mod.write(args.trace_csv,
                        {"command_vx_mps": float(args.command_vx),
                         # **찍은 주기**를 적는다. 담긴 영상의 fps 가 아니다.
                         # 슬로우모션이면 둘이 다르고, `t_s` 는 찍은 주기를
                         # 따라야 시뮬레이션 시각이 맞는다.
                         "fps": capture_fps,
                         "dt_s": round(1.0 / capture_fps, 6),
                         "slowmo": _ACTION_REPEAT,
                         "eval_duration_s": float(args.eval_duration),
                         "frames_recorded": len(trace_rows),
                         "gate_m": float(args.gate_m),
                         "max_lateral_drift_m": float(args.max_lateral_drift),
                         "max_velocity_mae_mps": float(args.max_velocity_mae),
                         "terrain": args.terrain,
                         "difficulty": args.difficulty,
                         "eval_spec_version": globals().get("_SPEC_VERSION"),
                         "policy_checkpoint": os.path.basename(args.checkpoint),
                         # **제목을 직접 적는다.** 안 적으면 HUD 가 env_id·episode 로
                         # 만들려다 «?» 로 떨어지고, 그 글자가 굽힌 서체에 없어
                         # 두부가 찍힌다 `확인됨` (2026-09-11 · gap-side 첫 컷).
                         "title": "%s · d%.1f · %.1f m/s · %s" % (
                             args.terrain,
                             args.difficulty if args.difficulty is not None else -1.0,
                             args.command_vx,
                             os.path.splitext(os.path.basename(args.checkpoint))[0])},
                        trace_rows)
        print("[PASS] trace %d 줄 -> %s" % (len(trace_rows), args.trace_csv), flush=True)
    rec_end = time.perf_counter(); final_hfov, final_ha, final_fl = read_hfov()
    if abs(final_hfov - CAMERA_HFOV) > 0.1: raise RuntimeError(f"final horizontal FOV mismatch: requested={CAMERA_HFOV}, measured={final_hfov}")
    cam["horizontal_fov_deg"] = initial_hfov
    cam["horizontal_aperture"] = horizontal_aperture; cam["focal_length"] = focal_length
    cam["final_horizontal_fov_deg"] = final_hfov; cam["final_horizontal_aperture"] = final_ha; cam["final_focal_length"] = final_fl
    check = {"status": "pending external av inspection", "preview_frames": saved}
    formation = {"columns": args.columns, "rows": args.rows}
    if ORIGINS_CSV: formation = {"origins_csv": ORIGINS_CSV, "rows": args.num_envs}
    data = {"argv": ORIGINAL_ARGV, "cut": args.cut, "terrain": args.terrain,
            "difficulty_range": globals().get("_DIFFICULTY_RANGE"), "eval_spec_version": globals().get("_SPEC_VERSION"), "trace_csv": args.trace_csv or None, "gap_aware_scan": not bool(args.legacy_miss_scan),
            "height_scan_miss_value": globals().get("_MISS_VALUE"), "video": os.path.basename(video), "bytes": os.path.getsize(video), "num_envs": args.num_envs, "formation": formation, "formation_extent_m": {"width": width, "depth": depth}, "spacing_m": args.spacing, "camera": cam, "gate_line": {"progress_m": 10.0, "visible": GATE_MODE == "on"}, "resolution": [args.width, args.height], "fps": fps, "frames": count, "video_duration_s": count / fps, "seed": args.seed, "command_vx_mps": args.command_vx, "eval_duration_s": args.eval_duration, "spawn_xy_range_m": args.spawn_xy_range, "yaw_range_deg": args.yaw_range_deg, "joint_pos_scale": args.joint_pos_scale, "policy_checkpoint": checkpoint, "policy_sha256": sha256(checkpoint), "env_origins_max_error_m": err, "encoding": {"codec": "libx264", "crf": args.crf, "preset": args.preset}, "timing_s": {"app_and_imports": env_started - STARTED, "environment_creation_and_reset": env_ready - env_started, "policy_load": policy_ready - env_ready, "render_warmup": warmup_done - policy_ready, "recording_total": rec_end - rec_start, "render_per_frame_mean": statistics.mean(renders), "render_per_frame_median": statistics.median(renders), "simulation_step_mean": statistics.mean(steps), "process_total": rec_end - STARTED}, "frame_inspection": check}
    with open(os.path.join(args.output_dir, stem + ".json"), "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
    print(json.dumps(data, ensure_ascii=False, indent=2), flush=True); env.close()


if __name__ == "__main__":
    try: main()
    finally: app.close()
