# Record replay videos of full-record CSVs: KINEMATIC REPLAY of the recorded states (no physics is re-computed).
# A one-robot scene with the same terrain generator configuration as the original q_eval run (families, rows,
# difficulty, seed) is built; for every recorded row the base pose and the 12 joint angles are written, kinematics
# are updated, and the viewport camera (following the base) is rendered at 1280 x 720. One frame per 50 Hz row.
# Checks written next to each video: terrain mesh hash vs the original run, replayed foot positions vs the CSV,
# and the height of feet in contact above the terrain at the foot (CPU ray cast on the same mesh).
# Usage (GPU 1, --enable_cameras): python q_video.py --run_tag <q_eval tag> --files a.csv,b.csv [--frames_png]
import argparse
import copy
import hashlib
import json
import os
import sys
import time

import h5py  # noqa: F401
import tensordict  # noqa: F401

from isaaclab.app import AppLauncher

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--run_tag", required=True, help="q_eval run whose meta.json defines the terrain")
ap.add_argument("--full_tag", default=None, help="full-record directory tag (default = run_tag)")
ap.add_argument("--files", default="all", help="comma separated CSV names inside out/full/<full_tag>, or all")
ap.add_argument("--frames_png", default="0,0.25,0.5,0.75,1.0", help="fractions of the episode saved as PNG for checking")
ap.add_argument("--warmup_frames", type=int, default=20)
AppLauncher.add_app_launcher_args(ap)
args = ap.parse_args()
args.headless = True
args.enable_cameras = True
app = AppLauncher(args).app

import gymnasium as gym  # noqa: E402
import imageio  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
import trimesh  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import isaaclab.utils.math as math_utils  # noqa: E402
import robot_lab.tasks  # noqa: F401,E402
from robot_lab.tasks.go2.env_cfg import Go2EnvCfg  # noqa: E402
from robot_lab.tasks.go2.mdp.terrains import TERRAIN_CFG  # noqa: E402

full_tag = args.full_tag or args.run_tag
FD = os.path.join(HERE, "out", "full", full_tag)
VD = os.path.join(HERE, "out", "video", full_tag)
os.makedirs(VD, exist_ok=True)
meta = json.load(open(os.path.join(HERE, "out", args.run_tag, "meta.json"), encoding="utf-8"))
FAMS = meta["families"]
DIFF, SEED = meta["args"]["difficulty"], meta["args"]["eval_seed"]
LABEL = "기록 재생 (운동학 · 물리 재계산 아님)"

cfg = Go2EnvCfg()
cfg.scene.num_envs = 1
cfg.seed = SEED
cfg.sim.device = "cuda:0"
cfg.events.randomize_push_robot = None
cfg.curriculum.terrain_levels = None
cfg.curriculum.base_linear_velocity = None
cfg.curriculum.base_height_l2 = None
tg = copy.deepcopy(TERRAIN_CFG)
tg.sub_terrains = {k: copy.deepcopy(TERRAIN_CFG.sub_terrains[k]) for k in FAMS}
for v in tg.sub_terrains.values():
    v.proportion = 1.0
tg.num_cols = len(FAMS)
tg.num_rows = 10
tg.difficulty_range = (DIFF, DIFF)
tg.curriculum = True
tg.seed = SEED
tg.use_cache = False
cfg.scene.terrain.terrain_generator = tg
cfg.scene.terrain.max_init_terrain_level = None
cfg.viewer.resolution = (1280, 720)
env = gym.make("RobotLab-Go2-v0", cfg=cfg, render_mode="rgb_array")
u = env.unwrapped
u.reset(seed=SEED)
robot = u.scene["robot"]
dev = u.device

# terrain mesh hash, computed exactly as q_eval.py does, and the mesh itself for ground-height checks
import omni.usd  # noqa: E402
from pxr import UsdGeom  # noqa: E402


def sha256_arr(*arrs):
    h = hashlib.sha256()
    for a in arrs:
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


stage = omni.usd.get_context().get_stage()
hs, mesh_tm = [], None
for prim in stage.Traverse():
    if str(prim.GetPath()).startswith("/World/ground") and prim.IsA(UsdGeom.Mesh):
        mesh = UsdGeom.Mesh(prim)
        pts = np.array(mesh.GetPointsAttr().Get(), dtype=np.float32)
        idx = np.array(mesh.GetFaceVertexIndicesAttr().Get(), dtype=np.int64)
        hs.append([str(prim.GetPath()), int(pts.shape[0]), sha256_arr(np.round(pts, 5), idx)])
        xf = np.array(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(0.0), dtype=np.float64)
        mesh_tm = trimesh.Trimesh((np.c_[pts.astype(np.float64), np.ones(len(pts))] @ xf)[:, :3], idx.reshape(-1, 3), process=False)
mesh_equal = [list(x) for x in hs] == [list(x) for x in meta["terrain_mesh"]]
print("[VIDEO] terrain mesh equal to the run:", mesh_equal, flush=True)

jnames_robot = list(robot.joint_names)
FEET = ["FL_foot", "FR_foot", "RL_foot", "RR_foot"]
FIDS = [robot.find_bodies(n)[0][0] for n in FEET]
font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 22)
font_s = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 18)
files = sorted(f for f in os.listdir(FD) if f.endswith(".csv") and f != "episodes_summary.csv") if args.files == "all" else args.files.split(",")
fracs = [float(x) for x in args.frames_png.split(",") if x != ""]
report = []
for fn in files:
    t0 = time.time()
    D = np.genfromtxt(os.path.join(FD, fn), delimiter=",", names=True)
    cols = D.dtype.names
    jn_term = [c[2:-4] for c in cols if c.startswith("q_") and c.endswith("_rad")]
    jmap = [jn_term.index(n) for n in jnames_robot]
    n = len(D)
    key = fn[:-4]
    out_mp4 = os.path.join(VD, f"{key}_kinreplay.mp4")
    w = imageio.get_writer(out_mp4, fps=50, codec="libx264", quality=8, macro_block_size=8)
    fk_err, gap = 0.0, []
    png_rows = sorted({min(n - 1, int(round(f * (n - 1)))) for f in fracs})
    for j in range(n):
        r = D[j]
        pose = torch.tensor([[r["base_x_m"], r["base_y_m"], r["base_z_m"], r["quat_w"], r["quat_x"], r["quat_y"], r["quat_z"]]], device=dev, dtype=torch.float)
        q_term = np.array([r[f"q_{jn}_rad"] for jn in jn_term], dtype=np.float32)
        q = torch.tensor(q_term[jmap], device=dev).unsqueeze(0)
        robot.write_root_pose_to_sim(pose)
        robot.write_root_velocity_to_sim(torch.zeros(1, 6, device=dev))
        robot.write_joint_state_to_sim(q, torch.zeros_like(q))
        u.sim.forward()
        lp = robot.root_physx_view.get_link_transforms()[0, FIDS, :3].cpu().numpy()
        rec = np.array([[r[f"{ft}_x_m"], r[f"{ft}_y_m"], r[f"{ft}_z_m"]] for ft in FEET])
        fk_err = max(fk_err, float(np.abs(lp - rec).max()))
        for i, ft in enumerate(FEET):
            if r[f"{ft}_contact"] > 0.5:
                loc, ri, _ = mesh_tm.ray.intersects_location([[rec[i, 0], rec[i, 1], rec[i, 2] + 5.0]], [[0, 0, -1.0]], multiple_hits=False)
                if len(loc):
                    gap.append(float(rec[i, 2] - loc[0, 2]))
        p = pose[0, :3].cpu().numpy()
        u.sim.set_camera_view(eye=(p[0] - 1.3, p[1] - 1.7, p[2] + 0.75), target=(p[0] + 0.15, p[1], p[2] - 0.1))
        reps = args.warmup_frames if j == 0 else 1
        for _ in range(reps):
            img = u.render()
        im = Image.fromarray(np.asarray(img)[..., :3].astype(np.uint8))
        dr = ImageDraw.Draw(im)
        txt = [f"{LABEL}", f"{full_tag} · {key}", f"t = {r['t_s']:5.2f} s",
               f"명령  vx {r['cmd_vx_mps']:+.2f}  vy {r['cmd_vy_mps']:+.2f} m/s  wz {r['cmd_wz_radps']:+.2f} rad/s",
               f"실제  vx {r['linvel_body_x_mps']:+.2f}  vy {r['linvel_body_y_mps']:+.2f} m/s  wz {r['angvel_body_z_radps']:+.2f} rad/s"]
        dr.rectangle([8, 8, 700, 8 + 30 * len(txt)], fill=(0, 0, 0, 160))
        for k, s in enumerate(txt):
            dr.text((16, 12 + 30 * k), s, font=font if k else font_s, fill=(255, 255, 255))
        frame = np.asarray(im)
        w.append_data(frame)
        if j in png_rows:
            Image.fromarray(frame).save(os.path.join(VD, f"{key}_kinreplay_f{j:04d}.png"))
    w.close()
    g = np.array(gap) if gap else np.array([np.nan])
    rep = {"file": os.path.basename(out_mp4), "source_csv": fn, "frames": n, "fps": 50, "seconds": n / 50.0,
           "replay": "kinematic replay of the recorded states, physics not re-computed", "terrain_mesh_equal_to_run": mesh_equal,
           "replayed_foot_vs_csv_max_abs_m": fk_err, "contact_foot_height_above_terrain_m": {
               "n": int(np.isfinite(g).sum()), "median": float(np.nanmedian(g)), "p01": float(np.nanpercentile(g, 1)),
               "p99": float(np.nanpercentile(g, 99)), "min": float(np.nanmin(g)), "max": float(np.nanmax(g)),
               "frac_within_0.018_0.028": float(np.mean((g >= 0.018) & (g <= 0.028))) if np.isfinite(g).any() else None,
               "n_above_0.028": int(np.sum(g > 0.028)), "n_below_0.018": int(np.sum(g < 0.018)),
               "note": "vertical ray below the foot centre; on stairs a foot touching a riser or edge reads the lower tread"},
           "png_rows": png_rows, "bytes": os.path.getsize(out_mp4), "wall_s": round(time.time() - t0, 1)}
    report.append(rep)
    json.dump(rep, open(os.path.join(VD, f"{key}_kinreplay.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[VIDEO]", json.dumps(rep, ensure_ascii=False), flush=True)
json.dump({"run_tag": args.run_tag, "full_tag": full_tag, "terrain_mesh_equal": mesh_equal, "videos": report},
          open(os.path.join(VD, "videos_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
env.close()
app.close()
