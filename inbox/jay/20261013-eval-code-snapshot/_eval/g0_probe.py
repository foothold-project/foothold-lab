# G0 GPU probe: shoot the real height_scanner rays over every tile of the 8 training terrains plus two
# evaluation-only columns (Isaac Lab mesh "gap", height-field "stepping_stones"; training config is not
# changed), and along lines that run past the terrain border. Robots are teleported (no physics step,
# no policy). For every pose: ray hits from the RayCaster, the legacy height block from the real
# ObservationManager (critic group), and the G0 encoding of the same hits. Saves the collision mesh
# for the CPU classification in g0_classify.py.
#
# Usage: set CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 OMNI_KIT_ACCEPT_EULA=YES
#        python g0_probe.py --headless

import argparse
import copy
import json
import os
import sys
import time

import h5py  # noqa: F401
import tensordict  # noqa: F401

from isaaclab.app import AppLauncher

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--envs", type=int, default=1000)
ap.add_argument("--spacing", type=float, default=0.5)
ap.add_argument("--seed", type=int, default=1000)
ap.add_argument("--tag", default="g0_probe")
AppLauncher.add_app_launcher_args(ap)
args = ap.parse_args()
args.headless = True
app = AppLauncher(args).app

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402

import robot_lab.tasks  # noqa: F401,E402
from robot_lab.tasks.go2.env_cfg import Go2EnvCfg  # noqa: E402
from robot_lab.tasks.go2.mdp.terrains import TERRAIN_CFG  # noqa: E402

sys.path.insert(0, HERE)
import g0_encoding as G  # noqa: E402

OUT = os.path.join(HERE, "out", args.tag)
os.makedirs(OUT, exist_ok=True)
TRAIN = ["flat", "wave", "slope_up", "slope_down", "rough_slope", "stairs_up", "stairs_down", "obstacles"]
EVAL_ONLY = ["gap", "stepping_stones"]
FAMS = TRAIN + EVAL_ONLY


def smi():
    import subprocess
    r = subprocess.run(["nvidia-smi", "--query-gpu=index,uuid,memory.used", "--format=csv,noheader"],
                       capture_output=True, text=True)
    return r.stdout.strip().splitlines()


meta = {"args": vars(args), "families": FAMS, "eval_only_columns": EVAL_ONLY, "smi_start": smi(),
        "env_vars": {k: os.environ.get(k) for k in ("CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER")}}

cfg = Go2EnvCfg()
cfg.scene.num_envs = args.envs
cfg.seed = args.seed
cfg.sim.device = "cuda:0"
cfg.observations.policy.enable_corruption = False
cfg.observations.single_obs.enable_corruption = False
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
tg.curriculum = True
tg.difficulty_range = (0.0, 1.0)  # row r has difficulty in [r/10, (r+1)/10)
tg.seed = args.seed
tg.use_cache = False
cfg.scene.terrain.terrain_generator = tg
meta["terrain"] = {"rows": tg.num_rows, "cols": tg.num_cols, "size": list(tg.size), "border_width": tg.border_width,
                   "gap_width_range": list(TERRAIN_CFG.sub_terrains["gap"].gap_width_range),
                   "gap_platform_width": TERRAIN_CFG.sub_terrains["gap"].platform_width,
                   "stepping_stones_holes_depth": TERRAIN_CFG.sub_terrains["stepping_stones"].holes_depth}

env = gym.make("RobotLab-Go2-v0", cfg=cfg)
u = env.unwrapped
u.reset(seed=args.seed)
dev = u.device
robot = u.scene["robot"]
hs = u.scene["height_scanner"]
ter = u.scene.terrain
meta["smi_after_env"] = smi()
meta["torch_cuda0_uuid"] = str(torch.cuda.get_device_properties(0).uuid)
meta["device"] = str(dev)

# critic layout (height block position) from the manager
om = u.observation_manager
names = list(om.active_terms["critic"])
dims = [int(np.prod(d)) for d in om.group_obs_term_dim["critic"]]
h_off = sum(dims[: names.index("height_scan")])
h_len = dims[names.index("height_scan")]
meta["height_block"] = [h_off, h_len]
term_cfg = om._group_obs_term_cfgs["critic"][names.index("height_scan")]
meta["height_term"] = {"func": f"{term_cfg.func.__module__}.{term_cfg.func.__name__}", "clip": list(term_cfg.clip),
                       "scale": term_cfg.scale, "params": {k: str(v) for k, v in term_cfg.params.items()}}
meta["raycaster"] = {"offset_pos": list(hs.cfg.offset.pos), "ray_alignment": hs.cfg.ray_alignment,
                     "max_distance": hs.cfg.max_distance, "mesh_prim_paths": list(hs.cfg.mesh_prim_paths),
                     "num_rays": int(hs.num_rays)}

# ---- poses -------------------------------------------------------------------------
origins = ter.terrain_origins.cpu().numpy()  # (rows, cols, 3)
R, Cn = origins.shape[:2]
half = tg.size[0] / 2.0
offs = np.arange(-half + args.spacing / 2, half, args.spacing)
poses = []  # x, y, row, col  (row/col = -1 for the outside lines)
for r in range(R):
    for c in range(Cn):
        ox, oy = origins[r, c, 0], origins[r, c, 1]
        for dx in offs:
            for dy in offs:
                poses.append((ox + dx, oy + dy, r, c))
gx = (R * tg.size[0]) / 2.0
gy = (Cn * tg.size[1]) / 2.0
cx, cy = origins[..., 0].mean(), origins[..., 1].mean()
ext = tg.border_width + 10.0
for x in np.arange(cx - gx - ext, cx + gx + ext + 1e-9, args.spacing):
    poses.append((x, cy, -1, -1))
for y in np.arange(cy - gy - ext, cy + gy + ext + 1e-9, args.spacing):
    poses.append((cx, y, -1, -1))
poses = np.array(poses, dtype=np.float64)
P = poses.shape[0]
meta["n_poses"] = int(P)
meta["grid_extent_xy"] = [float(cx - gx), float(cx + gx), float(cy - gy), float(cy + gy)]
print(f"[G0] poses {P}, rays per pose {hs.num_rays}")

N = args.envs
nr = int(hs.num_rays)
hit_z_all = np.zeros((P, nr), np.float32)
ray_xy_all = np.zeros((P, nr, 2), np.float32)
legacy_all = np.zeros((P, nr), np.float32)
g0_all = np.zeros((P, nr), np.float32)
base_z_all = np.zeros(P, np.float32)
mine_vs_pipeline = 0.0
default_q = robot.data.default_joint_pos.clone()
center_ray = int(np.argmin(np.linalg.norm(hs.ray_starts[0, :, :2].cpu().numpy(), axis=1)))


def place(xyz):
    pose = torch.zeros(N, 7, device=dev)
    pose[:, :3] = xyz
    pose[:, 3] = 1.0  # identity quaternion (w, x, y, z): yaw 0
    robot.write_root_pose_to_sim(pose)
    robot.write_root_velocity_to_sim(torch.zeros(N, 6, device=dev))
    robot.write_joint_state_to_sim(default_q, torch.zeros_like(default_q))
    u.scene.write_data_to_sim()
    u.sim.forward()
    hs.reset()  # mark outdated so the next .data access re-casts at the new pose


t0 = time.time()
with torch.inference_mode():
    for b0 in range(0, P, N):
        b = poses[b0:b0 + N]
        n = b.shape[0]
        xyz = torch.zeros(N, 3, device=dev)
        xyz[:n, 0] = torch.as_tensor(b[:, 0], device=dev, dtype=torch.float)
        xyz[:n, 1] = torch.as_tensor(b[:, 1], device=dev, dtype=torch.float)
        xyz[:n, 2] = 1.0
        if n < N:  # park the unused envs at the first pose of the batch
            xyz[n:] = xyz[0]
        place(xyz)
        hz = hs.data.ray_hits_w[..., 2].clone()
        # base 0.38 m above the ground under the centre ray (or the highest finite hit; 0.38 if none)
        cz = hz[:, center_ray]
        fin = torch.where(torch.isfinite(hz), hz, torch.full_like(hz, -1e9)).max(dim=1).values
        gz = torch.where(torch.isfinite(cz), cz, torch.where(fin > -1e8, fin, torch.zeros_like(fin)))
        xyz[:, 2] = gz + 0.38
        place(xyz)
        crit = om.compute_group("critic")  # real pipeline: height_scan -> clip -> scale
        leg = crit[:, h_off:h_off + h_len]
        d = hs.data
        hz = d.ray_hits_w[..., 2]
        mine = G.legacy_encode(d.pos_w[:, 2], hz)
        both_nan = torch.isnan(mine) & torch.isnan(leg)
        mine_vs_pipeline = max(mine_vs_pipeline, float(torch.where(both_nan, torch.zeros_like(leg), (mine - leg).abs()).max()))
        hit_z_all[b0:b0 + n] = hz[:n].cpu().numpy()
        ray_xy_all[b0:b0 + n] = d.ray_hits_w[:n, :, :2].cpu().numpy()  # inf for misses; replaced below
        starts = hs._ray_starts_w[:n, :, :2].cpu().numpy()
        ray_xy_all[b0:b0 + n] = starts  # vertical rays: the ray x,y is the start x,y
        legacy_all[b0:b0 + n] = leg[:n].cpu().numpy()
        g0_all[b0:b0 + n] = G.g0_encode(d.pos_w[:n, 2], hz[:n]).cpu().numpy()
        base_z_all[b0:b0 + n] = d.pos_w[:n, 2].cpu().numpy()
meta["probe_wall_s"] = time.time() - t0
meta["my_legacy_formula_vs_pipeline_max_abs"] = mine_vs_pipeline
meta["ray_directions_unique"] = np.unique(hs.ray_directions[0].cpu().numpy().round(6), axis=0).tolist()
meta["smi_end"] = smi()

# collision mesh actually used by the ray caster (USD points with the prim world transform)
import omni.usd  # noqa: E402
from pxr import UsdGeom  # noqa: E402

stage = omni.usd.get_context().get_stage()
mp = None
for prim in stage.Traverse():
    if str(prim.GetPath()).startswith("/World/ground") and prim.IsA(UsdGeom.Mesh):
        mp = prim
        break
mesh = UsdGeom.Mesh(mp)
pts = np.array(mesh.GetPointsAttr().Get(), dtype=np.float64)
fvi = np.array(mesh.GetFaceVertexIndicesAttr().Get(), dtype=np.int64)
fvc = np.array(mesh.GetFaceVertexCountsAttr().Get(), dtype=np.int64)
xf = np.array(UsdGeom.Xformable(mp).ComputeLocalToWorldTransform(0.0), dtype=np.float64)  # row-vector convention
pts_w = np.c_[pts, np.ones(len(pts))] @ xf
meta["mesh"] = {"prim": str(mp.GetPath()), "n_points": int(len(pts)), "faces_all_triangles": bool((fvc == 3).all()),
                "n_faces": int(len(fvc)), "local_to_world_is_identity": bool(np.allclose(xf, np.eye(4)))}
np.savez_compressed(os.path.join(OUT, "mesh.npz"), vertices=pts_w[:, :3], faces=fvi.reshape(-1, 3))
np.savez_compressed(os.path.join(OUT, "rays.npz"), poses=poses, hit_z=hit_z_all, ray_xy=ray_xy_all,
                    legacy=legacy_all, g0=g0_all, base_z=base_z_all, origins=origins)
json.dump(meta, open(os.path.join(OUT, "meta.json"), "w"), indent=1, default=str)
cause = G.classify(torch.as_tensor(hit_z_all)).numpy()
print("[G0] done", P, "poses; inf", int((cause == 1).sum()), "nan", int((cause == 2).sum()),
      "| my legacy vs pipeline", mine_vs_pipeline)
env.close()
app.close()
