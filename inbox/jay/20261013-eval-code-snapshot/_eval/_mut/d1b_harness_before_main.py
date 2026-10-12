# D1-B harness checks and smoke runs (VERIFY-astra-5.md, harness only; the D1-B main evaluation is NOT run).
#
# One Isaac process, stages run in order and each writes out/<tag>/<stage>.json at once:
#   geom   gap geometry: USD collision mesh vs generator, CPU raycast of every void, collider list,
#          main-evaluation layout and sealed holdout layout generated with the same generator class
#          (no robot on the holdout), local-coordinate manifests, explicit DR/start manifests.
#   g0     G0 wired at the raw height stage (critic height_scan func replaced in this script only),
#          real ObservationManager final block on flat / step / no-hit / injected NaN, -inf, pose, overflow.
#   settle 1 s PD hold at the default pose (action-0 target incl. the injected motor offset) from the D1-B
#          start poses, save, restore through env.reset twice, compare at the PhysX level, replay check.
#   dyn    short teacher rollouts from the restored starts in all 12 validation cells (four encoding /
#          permutation conditions spread over the envs, yaw-rotation envs, forced auto-reset at step 150):
#          ray position, update time, no-hit mask, 187 order against the current root pose every step.
#   fall   simulator smoke of the contactless-fall rules (GT fixed in SCEN below before the run).
#   foot   known-answer foot placements for the risky-touchdown rule.
# Repository files are not modified. Every evaluation-only change is listed in meta.json.
#
# Usage (GPU 1 only): see run_d1b_harness.sh

import argparse
import copy
import hashlib
import json
import math
import os
import subprocess
import sys
import time

import h5py  # noqa: F401
import tensordict  # noqa: F401

from isaaclab.app import AppLauncher

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--checkpoint", required=True)
ap.add_argument("--stages", default="geom,g0,settle,dyn,fall,foot")
ap.add_argument("--episodes", type=int, default=100)
ap.add_argument("--tag", default="d1b_harness")
ap.add_argument("--settle_s", type=float, default=1.0)
ap.add_argument("--cond", default="legacy-normal", choices=["legacy-normal", "legacy-perm2026", "g0plus-normal", "g0plus-perm2026"],
                help="teacher condition of the settle-stage replay (cross-process pairing check)")
ap.add_argument("--settle_diag_s", type=float, default=0.0, help="extra PD-hold seconds after saving, diagnostic only")
ap.add_argument("--settle_kd_scale", type=float, default=1.0, help="diagnostic: damping multiplier during the settle only")
AppLauncher.add_app_launcher_args(ap)
args = ap.parse_args()
args.headless = True
app = AppLauncher(args).app

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
import trimesh  # noqa: E402
from tensordict import TensorDict  # noqa: E402

import isaaclab.terrains as terrain_gen  # noqa: E402
import isaaclab.utils.math as math_utils  # noqa: E402
from isaaclab.envs.mdp.observations import height_scan as il_height_scan  # noqa: E402
from isaaclab.managers import EventTermCfg as EventTerm  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402
from rsl_rl.runners import OnPolicyRunnerCTS  # noqa: E402

import robot_lab.tasks  # noqa: F401,E402
from robot_lab.tasks.go2.env_cfg import Go2EnvCfg  # noqa: E402
from robot_lab.tasks.go2.mdp.terrains import TERRAIN_CFG  # noqa: E402
from robot_lab.tasks.go2.rsl_rl_cfg import MoECTSRunnerCfg  # noqa: E402

sys.path.insert(0, HERE)
import d1b_lib as L  # noqa: E402

OUT = os.path.join(HERE, "out", args.tag)
os.makedirs(OUT, exist_ok=True)
STAGES = args.stages.split(",")
E = args.episodes
DT = L.DT
SEED_VAL, IDS_VAL = 12000, list(range(1000, 1000 + E))
SEED_HO, IDS_HO = 22000, list(range(2000, 2100))
PLATFORM = 3.0
A = PLATFORM / 2
VAL_COLS = [("flat", 0.0), ("gap010", 0.10), ("gap020", 0.20), ("gap030", 0.30)]
SMOKE_COLS = [("step010", None), ("gapwide060", 0.60)]
COLS = VAL_COLS + SMOKE_COLS
DIRS = [0, 45, 90]
CELLS = [(ci, w, al) for ci, (_, w) in enumerate(VAL_COLS) for al in DIRS]
N = len(CELLS) * E
PERM_SEED = 2026


def sha_arr(*arrs):
    h = hashlib.sha256()
    for a in arrs:
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


def smi():
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=index,uuid,memory.used", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=20)
        return r.stdout.strip().splitlines()
    except Exception as ex:  # pragma: no cover
        return [f"nvidia-smi failed: {ex}"]


def dump(name, obj):
    with open(os.path.join(OUT, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    print(f"[D1B] wrote {name}.json", flush=True)


meta = {"args": vars(args), "t_start": time.strftime("%Y-%m-%d %H:%M:%S"), "smi_start": smi(),
        "env_vars": {k: os.environ.get(k) for k in ("CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER")},
        "cells": [{"col": VAL_COLS[c][0], "width": w, "alpha_deg": al} for c, w, al in CELLS], "N": N}


# ---------------------------------------------------------------------------------- config
def height_scan_switch(env, sensor_cfg, offset: float = 0.5):
    """Critic height term for D1-B. Legacy envs: the Isaac Lab formula unchanged. G0 envs: every non-finite
    raw value is replaced by +1 here, BEFORE the manager's single clip(-1,1) and scale 2.5."""
    s = env.scene.sensors[sensor_cfg.name]
    leg = L.legacy_raw_height(s.data.pos_w, s.data.ray_hits_w, offset)
    m = getattr(env, "_d1b_g0", None)
    if m is None:
        return leg
    g0 = L.g0_raw_height(s.data.pos_w, s.data.ray_hits_w, offset)
    return torch.where(m.unsqueeze(1), g0, leg)


def restore_event(env, env_ids):
    """reset_base replacement: write the stored start state and the per-episode reset-mode DR."""
    rob = env.scene["robot"]
    if not hasattr(env, "_d1b_state"):  # wrapper's initial reset, before any D1-B state exists
        root = rob.data.default_root_state[env_ids].clone()
        root[:, :3] += env.scene.env_origins[env_ids]
        rob.write_root_pose_to_sim(root[:, :7], env_ids=env_ids)
        rob.write_root_velocity_to_sim(root[:, 7:], env_ids=env_ids)
        rob.write_joint_state_to_sim(rob.data.default_joint_pos[env_ids], rob.data.default_joint_vel[env_ids], env_ids=env_ids)
        return
    st = env._d1b_state
    rob.write_root_pose_to_sim(st["root_pose"][env_ids], env_ids=env_ids)
    rob.write_root_velocity_to_sim(st["root_vel"][env_ids], env_ids=env_ids)
    rob.write_joint_state_to_sim(st["jpos"][env_ids], st["jvel"][env_ids], env_ids=env_ids)
    if "jtarget" in st:  # frozen rule: PD target = action-0 target (default pose + motor offset), vel/effort targets 0
        rob.set_joint_position_target(st["jtarget"][env_ids], env_ids=env_ids)
        rob.set_joint_velocity_target(torch.zeros_like(st["jtarget"][env_ids]), env_ids=env_ids)
        rob.set_joint_effort_target(torch.zeros_like(st["jtarget"][env_ids]), env_ids=env_ids)
    apply_reset_dr(env, env_ids)


def apply_reset_dr(env, env_ids):
    dr = env._d1b_dr
    rob = env.scene["robot"]
    act = rob.actuators[ACT_NAME]
    act.stiffness[env_ids] = rob.data.default_joint_stiffness[env_ids] * dr["kp"][env_ids]
    act.damping[env_ids] = rob.data.default_joint_damping[env_ids] * dr["kd"][env_ids]
    jt_ = env.action_manager.get_term("joint_pos")
    jt_._offset[env_ids] = dr["off0"][env_ids] + dr["moff"][env_ids]
    for b in (act.positions_delay_buffer, act.velocities_delay_buffer, act.efforts_delay_buffer):
        b.set_time_lag(dr["lag"][env_ids], env_ids)


cfg = Go2EnvCfg()
changes = []
cfg.scene.num_envs = N
cfg.seed = SEED_VAL
cfg.sim.device = "cuda:0"
cfg.observations.policy.enable_corruption = False
cfg.observations.single_obs.enable_corruption = False
changes.append("observation noise off (policy, single_obs); critic has none")
cfg.events.randomize_push_robot = None
for k in ("randomize_rigid_body_mass_base", "randomize_rigid_body_mass_others", "randomize_com_positions",
          "randomize_rigid_body_material", "randomize_actuator_gains", "randomize_motor_zero_offset", "reset_robot_joints"):
    setattr(cfg.events, k, None)
cfg.events.reset_base = EventTerm(func=restore_event, mode="reset", params={})
changes.append("push off; all DR event terms off and replaced by explicit manifest injection (same ranges); "
               "reset_base/reset_robot_joints replaced by restore_event (stored start state + reset-mode DR)")
cfg.curriculum.terrain_levels = None
cfg.curriculum.base_linear_velocity = None
cfg.curriculum.base_height_l2 = None
cfg.episode_length_s = 30.0
changes.append("curriculum off; episode_length_s 30")
cfg.observations.critic.height_scan.func = height_scan_switch
changes.append("critic height_scan func -> height_scan_switch (legacy formula or G0 raw +1 per env); clip/scale unchanged")
rng_cmd = dict(cfg.commands.base_velocity.terrain_max_command_ranges)
for name, _ in COLS:
    rng_cmd.setdefault(name, dict(rng_cmd["gap"]))
cfg.commands.base_velocity.terrain_max_command_ranges = rng_cmd
changes.append("command term: terrain names of the test columns added with the 'gap' ranges (commands are fixed anyway)")


def terrain_cfg(cols, seed, platform):
    tg = copy.deepcopy(TERRAIN_CFG)
    subs = {}
    for name, w in cols:
        if name.endswith("flat"):
            subs[name] = terrain_gen.MeshPlaneTerrainCfg(proportion=1.0)
        elif name.startswith("step"):
            subs[name] = terrain_gen.MeshBoxTerrainCfg(proportion=1.0, box_height_range=(0.10, 0.10), platform_width=platform)
        else:
            subs[name] = terrain_gen.MeshGapTerrainCfg(proportion=1.0, gap_width_range=(w, w), platform_width=platform)
    tg.sub_terrains = subs
    tg.num_rows = 1
    tg.num_cols = len(cols)
    tg.curriculum = True
    tg.difficulty_range = (0.5, 0.5)
    tg.seed = seed
    tg.use_cache = False
    return tg


tg = terrain_cfg(COLS, SEED_VAL, PLATFORM)
cfg.scene.terrain.terrain_generator = tg
cfg.scene.terrain.max_init_terrain_level = None
changes.append(f"terrain: 1 row x {len(COLS)} columns {[c for c, _ in COLS]}, platform {PLATFORM}, widths fixed, "
               f"difficulty recorded 0.5, seed {SEED_VAL}; step010/gapwide060 are smoke-only columns")
meta["eval_changes"] = changes

env = gym.make("RobotLab-Go2-v0", cfg=cfg)
env = RslRlVecEnvWrapper(env, clip_actions=None)
u = env.unwrapped
dev = u.device
robot = u.scene["robot"]
hs = u.scene["height_scanner"]
hs_small = u.scene["height_scanner_small"]
cs = u.scene["contact_forces"]
ter = u.scene.terrain
om = u.observation_manager
jt = u.action_manager.get_term("joint_pos")
ACT_NAME = list(robot.actuators.keys())[0]
act = robot.actuators[ACT_NAME]
meta["smi_after_env"] = smi()
meta["actuators"] = {k: {"class": type(v).__name__, "joint_indices": str(v.joint_indices)} for k, v in robot.actuators.items()}
assert len(robot.actuators) == 1 and act.joint_indices == slice(None), "manifest gain injection assumes one actuator over all joints"

# policy
agent_cfg = MoECTSRunnerCfg()
agent_cfg.device = "cuda:0"
runner = OnPolicyRunnerCTS(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
runner.load(args.checkpoint)
policy = runner.get_inference_policy(device=dev)
pnn = runner.alg.policy
# everything below runs in inference mode (sim buffers created in one mode cannot be updated in place in the other)
_IM = torch.inference_mode()
_IM.__enter__()
h = hashlib.sha256()
with open(args.checkpoint, "rb") as f:
    for b in iter(lambda: f.read(1 << 20), b""):
        h.update(b)
meta["checkpoint_sha256"] = h.hexdigest()

# layout: env e -> cell e // E, episode e % E; every env of a column on row 0 of that column
e_idx = torch.arange(N, device=dev)
cell_of = torch.div(e_idx, E, rounding_mode="floor")
ep_of = e_idx % E
col_of = torch.tensor([CELLS[c][0] for c in range(len(CELLS))], device=dev)[cell_of]
ter.terrain_types[:] = col_of
ter.terrain_levels[:] = 0
ter.env_origins[:] = ter.terrain_origins[0, col_of]
ORG = ter.terrain_origins[0].clone()  # (cols, 3)
meta["terrain_origins_row0"] = ORG.cpu().numpy().round(6).tolist()

# critic layout and permutation (runtime, by term name)
c_names = list(om.active_terms["critic"])
c_dims = [int(np.prod(d)) for d in om.group_obs_term_dim["critic"]]
H_OFF = sum(c_dims[: c_names.index("height_scan")])
H_LEN = c_dims[c_names.index("height_scan")]
PERM = np.random.RandomState(PERM_SEED).permutation(H_LEN)
PERM_T = torch.as_tensor(PERM, device=dev, dtype=torch.long)
meta["critic_layout"] = {"names": c_names, "dims": c_dims, "height_offset": H_OFF, "height_len": H_LEN}
meta["perm"] = {"seed": PERM_SEED, "sha256": sha_arr(PERM.astype(np.int64)), "fixed_points": int((PERM == np.arange(H_LEN)).sum())}

u._d1b_g0 = torch.zeros(N, dtype=torch.bool, device=dev)
u._d1b_perm = torch.zeros(N, dtype=torch.bool, device=dev)


def teacher_mean(o):
    blk = o["critic"][:, H_OFF:H_OFF + H_LEN]
    blk = torch.where(u._d1b_perm.unsqueeze(1), blk[:, PERM_T], blk)
    crit = torch.cat([o["critic"][:, :H_OFF], blk, o["critic"][:, H_OFF + H_LEN:]], dim=-1)
    o2 = o.clone()
    o2["critic"] = crit
    latent = pnn.teacher_encoder(pnn.critic_obs_normalizer(pnn.get_critic_obs(o2)))
    return pnn.actor(torch.cat([latent, pnn.single_obs_normalizer(o2["single_obs"])], dim=-1))


# commands fixed per env
ct = u.command_manager.get_term("base_velocity")
target = torch.zeros(N, 3, device=dev)


def _fixed_resample(env_ids):
    ct.commands[env_ids] = target[env_ids]
    ct.time_left[env_ids] = 1.0e9


ct._resample = _fixed_resample

# bodies, feet, foot colliders from the USD stage
BASE = robot.find_bodies("base")[0][0]
FOOT_NAMES = ["FL_foot", "FR_foot", "RL_foot", "RR_foot"]
FOOT_IDS = [robot.find_bodies(n)[0][0] for n in FOOT_NAMES]
CS_FOOT = [cs.find_bodies(n)[0][0] for n in FOOT_NAMES]
CS_BASE = cs.find_bodies("base")[0][0]
CS_NONFOOT = [i for i, n in enumerate(cs.body_names) if not n.endswith("_foot")]
import omni.usd  # noqa: E402
from pxr import Gf, Usd, UsdGeom, UsdPhysics  # noqa: E402

stage = omni.usd.get_context().get_stage()
foot_col = {}
robot_root = stage.GetPrimAtPath("/World/envs/env_0/Robot")
link_paths = {p.GetName(): p for p in Usd.PrimRange(robot_root, Usd.TraverseInstanceProxies()) if p.HasAPI(UsdPhysics.RigidBodyAPI)}
meta["robot_rigid_bodies_env0"] = sorted(str(p.GetPath()) for p in link_paths.values())
for n in FOOT_NAMES:
    link = link_paths[n]
    lw = UsdGeom.Xformable(link).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    shapes = []
    for p in Usd.PrimRange(link, Usd.TraverseInstanceProxies()):
        if p.HasAPI(UsdPhysics.CollisionAPI):
            pw = UsdGeom.Xformable(p).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            rel = pw * lw.GetInverse()
            ent = {"path": str(p.GetPath()), "type": p.GetTypeName(), "rel_translation": list(rel.ExtractTranslation())}
            if p.IsA(UsdGeom.Sphere):
                sc = Gf.Transform(rel).GetScale()
                ent["radius_attr"] = float(UsdGeom.Sphere(p).GetRadiusAttr().Get())
                ent["scale"] = list(sc)
                ent["radius"] = ent["radius_attr"] * max(sc)
            shapes.append(ent)
    foot_col[n] = shapes
meta["foot_colliders"] = foot_col
sph = [s for n in FOOT_NAMES for s in foot_col[n] if "radius" in s]
assert len(sph) == 4, f"expected one sphere collider per foot, got {foot_col}"
FOOT_R = float(sph[0]["radius"])
assert all(abs(s["radius"] - FOOT_R) < 1e-9 for s in sph)
FOOT_OFF = torch.tensor([s["rel_translation"] for s in sph], device=dev, dtype=torch.float)  # (4,3) in foot frame
meta["foot_radius"] = FOOT_R


def foot_centres(fresh=False):
    """World centre of each foot collision sphere. fresh=True reads PhysX link transforms directly
    (needed after a teleport without a physics step, when robot.data caches are not refreshed)."""
    if fresh:
        lp = robot.root_physx_view.get_link_transforms().clone()
        p = lp[:, FOOT_IDS, :3]
        q = math_utils.convert_quat(lp[:, FOOT_IDS, 3:7], to="wxyz")
    else:
        p = robot.data.body_link_pos_w[:, FOOT_IDS]  # (N,4,3)
        q = robot.data.body_link_quat_w[:, FOOT_IDS]
    return p + math_utils.quat_apply(q, FOOT_OFF.unsqueeze(0).expand(N, 4, 3))


def yaw_of(q):
    w, x, y, z = q[..., 0], q[..., 1], q[..., 2], q[..., 3]
    return torch.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def quat_yaw(yaw):
    z = torch.zeros_like(yaw)
    return math_utils.quat_from_euler_xyz(z, z, yaw)


DEF_Q = robot.data.default_joint_pos.clone()
DR0 = {"off0": jt._offset.clone()}
COM0 = robot.root_physx_view.get_coms().clone()

# ---------------------------------------------------------------------------------- manifests and DR injection
N_SHAPES = int(robot.root_physx_view.max_shapes)
man_val = L.make_manifest(SEED_VAL, IDS_VAL, robot.num_bodies, BASE, N_SHAPES)
man_ho = L.make_manifest(SEED_HO, IDS_HO, robot.num_bodies, BASE, N_SHAPES)
for nm, mm in (("manifest_validation", man_val), ("manifest_holdout_SEALED", man_ho)):
    mm["body_names"] = list(robot.body_names)
    mm["joint_names_articulation"] = list(robot.joint_names)
    mm["joint_names_action_term"] = list(jt._joint_names)
    mm["kp_kd_order"] = "articulation joint order"
    mm["motor_offset_order"] = "action term joint order"
    dump(nm, mm)
meta["manifest_sha256"] = {"validation_rows": L.sha(man_val["rows"]), "holdout_rows": L.sha(man_ho["rows"])}
ROWS = [man_val["rows"][int(ep)] for ep in ep_of.cpu().numpy()]


def inject_startup(rows):
    ids = torch.arange(N, device="cpu")
    dm = robot.data.default_mass.clone().cpu()
    sc = torch.tensor([r["mass_scale"] for r in rows], dtype=torch.float)
    add = torch.tensor([r["base_mass_add"] for r in rows], dtype=torch.float)
    m = dm * sc
    m[:, BASE] = dm[:, BASE] + add
    robot.root_physx_view.set_masses(m, ids)
    inert = robot.data.default_inertia.clone().cpu() * (m / dm)[..., None]
    robot.root_physx_view.set_inertias(inert, ids)
    coms = COM0.clone().cpu()
    coms[:, BASE, :3] += torch.tensor([r["base_com_offset"] for r in rows], dtype=torch.float)
    robot.root_physx_view.set_coms(coms, ids)
    bk = torch.tensor(man_val["buckets"], dtype=torch.float)
    mats = bk[torch.tensor([r["material_bucket"] for r in rows], dtype=torch.long)]
    robot.root_physx_view.set_material_properties(mats, ids)
    rb = {"mass": robot.root_physx_view.get_masses().cpu(), "inertia": robot.root_physx_view.get_inertias().cpu(),
          "com": robot.root_physx_view.get_coms().cpu(), "material": robot.root_physx_view.get_material_properties().cpu()}
    exp = {"mass": m, "inertia": inert, "com": coms, "material": mats}
    return {k: {"max_abs_diff": float((rb[k] - exp[k]).abs().max()), "readback_sha256": sha_arr(rb[k].numpy()),
                "manifest_sha256": sha_arr(exp[k].numpy())} for k in exp}


inj = inject_startup(ROWS)
u._d1b_dr = {
    "kp": torch.tensor([r["kp_scale"] for r in ROWS], device=dev, dtype=torch.float),
    "kd": torch.tensor([r["kd_scale"] for r in ROWS], device=dev, dtype=torch.float),
    "moff": torch.tensor([r["motor_offset"] for r in ROWS], device=dev, dtype=torch.float),
    "lag": torch.tensor([r["delay_lag"] for r in ROWS], device=dev, dtype=torch.int),
    "off0": DR0["off0"],
}
meta["startup_dr_injection"] = inj
meta["default_joint_stiffness_unique"] = torch.unique(robot.data.default_joint_stiffness).cpu().tolist()
meta["default_joint_damping_unique"] = torch.unique(robot.data.default_joint_damping).cpu().tolist()


def reset_dr_check():
    d = u._d1b_dr
    out = {"kp_max_abs": float((act.stiffness - robot.data.default_joint_stiffness * d["kp"]).abs().max()),
           "kd_max_abs": float((act.damping - robot.data.default_joint_damping * d["kd"]).abs().max()),
           "motor_offset_max_abs": float((jt._offset - d["off0"] - d["moff"]).abs().max())}
    for nm_, b in (("pos", act.positions_delay_buffer), ("vel", act.velocities_delay_buffer), ("eff", act.efforts_delay_buffer)):
        out[f"lag_{nm_}_mismatch"] = int((b.time_lags.to(torch.int) != d["lag"]).sum())
    return out


# ---------------------------------------------------------------------------------- placement helpers
def write_state(root_pose, root_vel, jpos, jvel):
    u._d1b_state = {"root_pose": root_pose.clone(), "root_vel": root_vel.clone(), "jpos": jpos.clone(), "jvel": jvel.clone()}


def place_static(root_pose, jpos=None):
    """Teleport without physics (geometry / encoding checks only)."""
    robot.write_root_pose_to_sim(root_pose)
    robot.write_root_velocity_to_sim(torch.zeros(N, 6, device=dev))
    q = DEF_Q if jpos is None else jpos
    robot.write_joint_state_to_sim(q, torch.zeros_like(q))
    u.scene.write_data_to_sim()
    u.sim.forward()
    hs.reset()
    hs_small.reset()


def ground_contact_pose(xy_world, yaw, z_top, clearance=0.002):
    """Root pose with the default joint pose whose lowest foot sphere bottom is `clearance` above z_top."""
    pose = torch.zeros(N, 7, device=dev)
    pose[:, :2] = xy_world
    pose[:, 2] = 0.45 + z_top
    pose[:, 3:7] = quat_yaw(yaw)
    place_static(pose)
    fc = foot_centres(fresh=True)
    bottom = (fc[..., 2] - FOOT_R).min(dim=1).values
    pose[:, 2] += (z_top + clearance) - bottom
    place_static(pose)
    fc = foot_centres(fresh=True)
    return pose, float(((fc[..., 2] - FOOT_R).min(dim=1).values - (z_top + clearance)).abs().max())


def d1b_starts():
    w_e = torch.tensor([CELLS[c][1] for c in range(len(CELLS))], device=dev)[cell_of]
    al = torch.tensor([float(CELLS[c][2]) for c in range(len(CELLS))], device=dev)[cell_of]
    dx = torch.tensor([r["start_dx"] for r in ROWS], device=dev)
    xy = ORG[col_of, :2].clone()
    xy[:, 0] += (A - 0.80) + dx
    yaw = -torch.deg2rad(al)
    cmd = torch.stack([0.30 * torch.cos(torch.deg2rad(al)), 0.30 * torch.sin(torch.deg2rad(al)), torch.zeros_like(al)], 1)
    return xy, yaw, cmd, w_e


T0 = time.time()
dump("meta", meta)

# ================================================================================== stage geom
if "geom" in STAGES:
    g = {}
    # 1 colliders on the stage other than the robots
    cols_found = []
    for p in stage.Traverse():
        sp = str(p.GetPath())
        if p.HasAPI(UsdPhysics.CollisionAPI) and "/Robot" not in sp:
            cols_found.append({"path": sp, "type": p.GetTypeName()})
    g["non_robot_colliders"] = cols_found
    # 2 USD terrain mesh vs a regeneration of the same configuration with the env's generator class
    mp = [p for p in stage.Traverse() if str(p.GetPath()).startswith("/World/ground") and p.IsA(UsdGeom.Mesh)]
    g["ground_meshes"] = [str(p.GetPath()) for p in mp]
    mesh = UsdGeom.Mesh(mp[0])
    pts = np.array(mesh.GetPointsAttr().Get(), dtype=np.float64)
    fvi = np.array(mesh.GetFaceVertexIndicesAttr().Get(), dtype=np.int64).reshape(-1, 3)
    xf = np.array(UsdGeom.Xformable(mp[0]).ComputeLocalToWorldTransform(0.0), dtype=np.float64)
    pts_w = (np.c_[pts, np.ones(len(pts))] @ xf)[:, :3]
    usd_mesh = trimesh.Trimesh(pts_w, fvi, process=False)
    gen_env = tg.class_type(copy.deepcopy(tg))
    gm = gen_env.terrain_mesh

    def canon(mm):
        v = np.round(np.asarray(mm.vertices), 5) + 0.0
        tri = v[np.asarray(mm.faces)].reshape(-1, 9)
        tri = tri[np.lexsort(tri.T[::-1])]
        return sha_arr(np.ascontiguousarray(tri))

    g["usd_mesh_vs_regenerated"] = {"usd_faces": int(len(fvi)), "gen_faces": int(len(gm.faces)),
                                    "usd_canon_sha256": canon(usd_mesh), "gen_canon_sha256": canon(gm),
                                    "origins_max_abs": float(np.abs(gen_env.terrain_origins[0] - ORG.cpu().numpy()).max())}
    g["usd_mesh_vs_regenerated"]["equal"] = g["usd_mesh_vs_regenerated"]["usd_canon_sha256"] == g["usd_mesh_vs_regenerated"]["gen_canon_sha256"]

    # 3 CPU raycast over every void of a layout, plus banks and the tile ring
    def void_scan(mesh_, origins_row0, cols, platform):
        a = platform / 2
        res = []
        for ci, (name, w) in enumerate(cols):
            if w is None:
                continue
            ox, oy = origins_row0[ci, 0], origins_row0[ci, 1]
            s = np.arange(-a - 0.5, a + 0.5 + 1e-9, 0.02)
            pts_ = []
            if w > 0:
                for f in np.linspace(0.02, 0.98, 9):  # across the gap width, away from both walls
                    r_ = a + f * w
                    for t_ in np.arange(-r_, r_ + 1e-9, 0.02):  # all four sides of the ring incl. corners
                        pts_ += [(r_, t_), (-r_, t_), (t_, r_), (t_, -r_)]
            pv = np.array(pts_) if pts_ else np.zeros((0, 2))
            bank = []
            for d_ in (0.005, 0.05, 0.3):
                for t_ in np.arange(-a + 0.01, a - 0.01 + 1e-9, 0.05):
                    bank += [(a - d_, t_), (a + w + d_, t_), (t_, -(a - d_)), (t_, -(a + w + d_))]
            for t_ in np.arange(-4.45, 4.45 + 1e-9, 0.1):
                bank += [(4.45, t_), (-4.45, t_), (t_, 4.45), (t_, -4.45)]
            pb = np.array(bank)
            out = {"col": name, "width": w, "void_points": int(len(pv))}
            if len(pv):
                o_dn = np.c_[pv[:, 0] + ox, pv[:, 1] + oy, np.full(len(pv), 5.0)]
                o_up = np.c_[pv[:, 0] + ox, pv[:, 1] + oy, np.full(len(pv), -50.0)]
                hit_dn = mesh_.ray.intersects_any(o_dn, np.tile([0, 0, -1.0], (len(pv), 1)))
                hit_up = mesh_.ray.intersects_any(o_up, np.tile([0, 0, 1.0], (len(pv), 1)))
                out["void_hit_downward"] = int(hit_dn.sum())
                out["void_hit_upward_from_-50m"] = int(hit_up.sum())
            ob = np.c_[pb[:, 0] + ox, pb[:, 1] + oy, np.full(len(pb), 5.0)]
            loc, ri, _ = mesh_.ray.intersects_location(ob, np.tile([0, 0, -1.0], (len(pb), 1)), multiple_hits=False)
            top = np.full(len(pb), np.nan)
            top[ri] = loc[:, 2]
            out["bank_points"] = int(len(pb))
            out["bank_missing"] = int(np.isnan(top).sum())
            out["bank_top_z_max_abs"] = float(np.nanmax(np.abs(top))) if np.isfinite(top).any() else None
            res.append(out)
        return res

    g["void_scan_usd_env_layout"] = void_scan(usd_mesh, ORG.cpu().numpy(), COLS, PLATFORM)
    # main-evaluation layout (validation columns only) and the sealed holdout layout
    tg_main = terrain_cfg(VAL_COLS, SEED_VAL, PLATFORM)
    gen_main = tg_main.class_type(copy.deepcopy(tg_main))
    g["void_scan_main_layout"] = void_scan(gen_main.terrain_mesh, gen_main.terrain_origins[0], VAL_COLS, PLATFORM)
    HO_COLS = [("hflat", 0.0), ("hgap015", 0.15), ("hgap025", 0.25)]
    tg_ho = terrain_cfg(HO_COLS, SEED_HO, 2.5)
    gen_ho = tg_ho.class_type(copy.deepcopy(tg_ho))
    g["void_scan_holdout_layout_SEALED"] = void_scan(gen_ho.terrain_mesh, gen_ho.terrain_origins[0], HO_COLS, 2.5)
    # 4 local-coordinate tile meshes: validation vs holdout vs seed-only change
    def local_tiles(tgc):
        gen = tgc.class_type(copy.deepcopy(tgc))
        outd = {}
        for name, sub in tgc.sub_terrains.items():
            mm, org = gen._get_terrain_mesh(0.5, sub)
            v = np.asarray(mm.vertices) - np.asarray(org)
            tri = (np.round(v[np.asarray(mm.faces)], 5) + 0.0).reshape(-1, 9)
            tri = tri[np.lexsort(tri.T[::-1])]
            outd[name] = {"sha256": sha_arr(np.ascontiguousarray(tri)), "origin_local": np.asarray(org).round(6).tolist(),
                          "n_faces": int(len(mm.faces))}
        return outd

    lt_val = local_tiles(tg_main)
    lt_ho = local_tiles(tg_ho)
    lt_seed = local_tiles(terrain_cfg(VAL_COLS, SEED_HO, PLATFORM))
    g["local_tiles_validation"] = lt_val
    g["local_tiles_holdout_SEALED"] = lt_ho
    g["local_tiles_validation_params_seed22000"] = lt_seed
    vs = {v["sha256"] for v in lt_val.values()}
    g["holdout_tile_equal_to_any_validation_tile"] = [k for k, v in lt_ho.items() if v["sha256"] in vs]
    g["seed_only_change_gives_identical_tiles"] = all(lt_seed[k]["sha256"] == lt_val[k]["sha256"] for k in lt_val)
    # 5 cell manifests in local coordinates
    g["cells_validation"] = [L.cell_geometry(PLATFORM, w, al) for _, w in VAL_COLS for al in DIRS]
    g["cells_holdout_SEALED"] = [L.cell_geometry(2.5, w, al) for _, w in HO_COLS for al in (-45, -90)]
    keyset = lambda cl: {(c["platform"], c["width"], c["alpha_deg"]) for c in cl}  # noqa: E731
    g["cell_overlap_validation_holdout"] = sorted(keyset(g["cells_validation"]) & keyset(g["cells_holdout_SEALED"]))
    g["start_dx_overlap_count"] = len({round(r["start_dx"], 9) for r in man_val["rows"]} & {round(r["start_dx"], 9) for r in man_ho["rows"]})
    g["holdout_policy_runs"] = 0
    # 6 GPU ray caster over the gap columns: no-hit exactly where the void is (static teleports)
    a = A
    stats = {"rays": 0, "nohit_mismatch": 0, "ambiguous": 0, "bank_z_max_abs": 0.0}
    rs = np.random.default_rng(7)
    for rep in range(6):
        cols_t = torch.as_tensor(rs.integers(1, 4, N), device=dev)
        xy = ORG[cols_t, :2].clone()
        xy[:, 0] += torch.as_tensor(rs.uniform(0.6, 2.4, N), device=dev, dtype=torch.float)
        xy[:, 1] += torch.as_tensor(rs.uniform(-1.0, 1.0, N), device=dev, dtype=torch.float)
        yaw = torch.as_tensor(rs.uniform(-math.pi, math.pi, N), device=dev, dtype=torch.float)
        pose = torch.zeros(N, 7, device=dev)
        pose[:, :2] = xy
        pose[:, 2] = 0.38
        pose[:, 3:7] = quat_yaw(yaw)
        place_static(pose)
        d = hs.data
        st_xy = d.ray_hits_w[..., :2]
        exy = d.pos_w[:, None, :2] + torch.stack([
            torch.cos(yaw)[:, None] * hs.ray_starts[..., 0] - torch.sin(yaw)[:, None] * hs.ray_starts[..., 1],
            torch.sin(yaw)[:, None] * hs.ray_starts[..., 0] + torch.cos(yaw)[:, None] * hs.ray_starts[..., 1]], -1)
        lxy = exy - ORG[cols_t, None, :2]
        w_t = torch.tensor([0.0, 0.10, 0.20, 0.30], device=dev)[cols_t][:, None]
        cheb = torch.maximum(lxy[..., 0].abs(), lxy[..., 1].abs())
        void = (cheb > a + 1e-3) & (cheb < a + w_t - 1e-3)
        bank = (cheb < a - 1e-3) | (cheb > a + w_t + 1e-3)
        amb = ~(void | bank)
        nohit = torch.isposinf(d.ray_hits_w[..., 2])
        stats["rays"] += int(N * hs.num_rays)
        stats["nohit_mismatch"] += int(((nohit != void) & ~amb).sum())
        stats["ambiguous"] += int(amb.sum())
        stats["bank_z_max_abs"] = max(stats["bank_z_max_abs"], float(d.ray_hits_w[..., 2][bank & ~nohit].abs().max()))
        fin = torch.isfinite(d.ray_hits_w[..., 2])
        stats["finite_xy_vs_expected_max_abs"] = max(stats.get("finite_xy_vs_expected_max_abs", 0.0), float((st_xy - exy)[fin].abs().max()))
    g["gpu_raycast_gap_columns"] = stats
    # pattern order: x fastest, 17 x 11 at 0.1 m
    xs = torch.arange(-0.8, 0.8 + 1e-9, 0.1, device=dev)
    ys = torch.arange(-0.5, 0.5 + 1e-9, 0.1, device=dev)
    gx, gy = torch.meshgrid(xs, ys, indexing="xy")
    expp = torch.stack([gx.flatten(), gy.flatten()], 1)
    g["pattern_order_x_fastest_max_abs"] = float((hs.ray_starts[0, :, :2] - expp).abs().max())
    g["pattern_same_for_all_envs"] = bool((hs.ray_starts - hs.ray_starts[0:1]).abs().max() == 0)
    g["ray_start_offset_z"] = float(hs.ray_starts[0, 0, 2])
    np.savez_compressed(os.path.join(OUT, "geom_meshes.npz"), env_vertices=pts_w, env_faces=fvi,
                        holdout_vertices=np.asarray(gen_ho.terrain_mesh.vertices), holdout_faces=np.asarray(gen_ho.terrain_mesh.faces))
    g["wall_s"] = time.time() - T0
    dump("geom", g)

# ================================================================================== stage g0
if "g0" in STAGES:
    r = {}
    # pose sets: 0 flat 0.38 m; 1 step tile edge (half the rays on the 0.10 m box); 2 gap030 lip (no-hit);
    # 3 injected errors on flat (NaN hit, -inf hit, pose NaN, overflow)
    grp = torch.div(e_idx, N // 4, rounding_mode="floor").clamp(max=3)
    pose = torch.zeros(N, 7, device=dev)
    rs = np.random.default_rng(11)
    yaw = torch.as_tensor(rs.uniform(-math.pi, math.pi, N), device=dev, dtype=torch.float)
    col_t = torch.tensor([0, 4, 3, 0], device=dev)[grp]
    pose[:, :2] = ORG[col_t, :2]
    pose[grp == 1, 0] += A  # box edge at x = 1.5
    pose[grp == 2, 0] += A + 0.15
    pose[:, 2] = 0.38
    pose[grp == 1, 2] = 0.38 + 0.10
    pose[:, 3:7] = quat_yaw(yaw)
    pose[grp == 0, 3:7] = quat_yaw(torch.zeros(int((grp == 0).sum()), device=dev))
    place_static(pose)
    with torch.inference_mode():
        d = hs.data
        # inject errors into group 3 (4 sub-kinds by env parity) after the sensor update
        g3 = torch.nonzero(grp == 3).flatten()
        kinds = {"hit_nan": g3[0::4], "hit_neginf": g3[1::4], "pose_nan": g3[2::4], "overflow": g3[3::4]}
        hs._data.ray_hits_w[kinds["hit_nan"], 5, 2] = float("nan")
        hs._data.ray_hits_w[kinds["hit_neginf"], 6, 2] = float("-inf")
        hs._data.pos_w[kinds["pose_nan"], 2] = float("nan")
        hs._data.pos_w[kinds["overflow"], 2] = 3.0e38
        hs._data.ray_hits_w[kinds["overflow"], 7, 2] = -3.0e38
        u._d1b_g0[:] = False
        crit_leg = om.compute_group("critic").clone()
        u._d1b_g0[:] = True
        crit_g0 = om.compute_group("critic").clone()
        pol_g0 = om.compute_group("policy").clone()
        sin_g0 = om.compute_group("single_obs").clone()
        u._d1b_g0[:] = False
        pol_leg = om.compute_group("policy").clone()
        sin_leg = om.compute_group("single_obs").clone()
        # Isaac Lab's own height_scan (unmodified) through the same clip/scale
        orig = (il_height_scan(u, u.observation_manager._group_obs_term_cfgs["critic"][c_names.index("height_scan")].params["sensor_cfg"])
                .clip(-1.0, 1.0) * 2.5)
        bl, bg = crit_leg[:, H_OFF:H_OFF + H_LEN], crit_g0[:, H_OFF:H_OFF + H_LEN]
        masks = L.input_masks(hs.data.pos_w, hs.data.ray_hits_w)
        err_env = torch.zeros(N, dtype=torch.bool, device=dev)
        for k in L.ERROR_KEYS:
            mk = masks[k]
            err_env |= mk if mk.dim() == 1 else mk.any(dim=1)
        nohit = masks["hit_posinf_nohit"]

        def mx(t):
            return float(t.abs().max()) if t.numel() else 0.0

        ok0 = grp == 0
        r["flat_final_legacy_minmax"] = [float(bl[ok0].min()), float(bl[ok0].max())]
        r["flat_final_g0_minmax"] = [float(bg[ok0].min()), float(bg[ok0].max())]
        r["flat_expected"] = -0.30
        r["flat_g0_minus_expected_max_abs"] = mx(bg[ok0] + 0.30)
        ok1 = grp == 1
        vals = torch.unique(torch.round(bg[ok1] * 1e4) / 1e4).cpu().tolist()
        r["step_final_values_g0"] = vals
        r["step_g0_vs_legacy_max_abs"] = mx(bg[ok1] - bl[ok1])
        ok2 = grp == 2
        r["gap_nohit_rays"] = int(nohit[ok2].sum())
        r["gap_nohit_final_legacy_unique"] = torch.unique(bl[ok2][nohit[ok2]]).cpu().tolist()
        r["gap_nohit_final_g0_unique"] = torch.unique(bg[ok2][nohit[ok2]]).cpu().tolist()
        r["gap_finite_g0_vs_legacy_max_abs"] = mx((bg[ok2] - bl[ok2])[~nohit[ok2]])
        fin_all = ~err_env.unsqueeze(1) & ~nohit
        r["all_valid_finite_cells_g0_vs_legacy_bitwise_equal"] = bool(torch.equal(bg[fin_all], bl[fin_all]))
        r["legacy_switch_vs_isaaclab_height_scan_bitwise_equal_valid_envs"] = bool(torch.equal(bl[~err_env], orig[~err_env]))
        r["non_height_critic_g0_vs_legacy_bitwise_equal"] = bool(torch.equal(
            torch.cat([crit_g0[:, :H_OFF], crit_g0[:, H_OFF + H_LEN:]], 1), torch.cat([crit_leg[:, :H_OFF], crit_leg[:, H_OFF + H_LEN:]], 1)))
        r["policy_single_obs_g0_vs_legacy_bitwise_equal"] = bool(torch.equal(pol_g0, pol_leg) and torch.equal(sin_g0, sin_leg))
        r["g0_nonfinite_outputs_valid_envs"] = int((~torch.isfinite(bg[~err_env])).sum())
        r["g0_nonfinite_outputs_error_envs"] = int((~torch.isfinite(bg[err_env])).sum())
        r["legacy_nonfinite_outputs_error_envs"] = int((~torch.isfinite(bl[err_env])).sum())
        inj = {}
        for k, ids in kinds.items():
            row = {"envs": int(len(ids)), "flagged_harness_error": int(err_env[ids].sum())}
            for mk in L.ERROR_KEYS + ("hit_posinf_nohit",):
                t_ = masks[mk][ids]
                row[f"mask_{mk}"] = int((t_ if t_.dim() == 1 else t_.any(dim=1)).sum())
            row["g0_final_at_injected"] = torch.unique(bg[ids][:, {"hit_nan": 5, "hit_neginf": 6, "pose_nan": 5, "overflow": 7}[k]]).cpu().tolist()
            row["legacy_final_at_injected"] = [str(v) for v in torch.unique(bl[ids][:, {"hit_nan": 5, "hit_neginf": 6, "pose_nan": 5, "overflow": 7}[k]]).cpu().tolist()]
            inj[k] = row
        r["injected_errors"] = inj
        r["groups_without_injection_flagged"] = int(err_env[grp < 3].sum())
        # teacher mean path with G0 input, against the module's own act(is_teacher=True)
        u._d1b_g0[:] = True
        o = TensorDict({"policy": pol_g0, "single_obs": sin_g0, "critic": crit_g0}, batch_size=[N])
        sel = ~err_env
        with torch.random.fork_rng(devices=[torch.cuda.current_device()]):
            pnn.act(o, is_teacher=True)
            a_mod = pnn.action_mean.clone()
        u._d1b_perm[:] = False
        a_t = teacher_mean(o)
        r["teacher_mean_vs_module_act_mean_g0_max_abs"] = mx((a_t - a_mod)[sel])
        o_leg = TensorDict({"policy": pol_leg, "single_obs": sin_leg, "critic": crit_leg}, batch_size=[N])
        r["teacher_action_g0_vs_legacy_on_gap_envs_max_abs"] = mx((teacher_mean(o_leg) - a_t)[ok2])
        r["teacher_action_g0_vs_legacy_on_flat_envs_max_abs"] = mx((teacher_mean(o_leg) - a_t)[ok0])
        r["student_action_g0_vs_legacy_max_abs"] = mx(policy(o) - policy(o_leg))
        u._d1b_perm[:] = True
        a_p = teacher_mean(o)
        u._d1b_perm[:] = False
        r["teacher_perm2026_vs_normal_on_gap_envs_max_abs"] = mx((a_p - a_t)[ok2])
        u._d1b_g0[:] = False
    r["wall_s"] = time.time() - T0
    dump("g0", r)

# ================================================================================== stage settle
RESTORE_OK = None
if "settle" in STAGES or any(s in STAGES for s in ("dyn", "fall", "foot")):
    s = {}
    xy, yaw, cmd, w_e = d1b_starts()
    pose, clr = ground_contact_pose(xy, yaw, 0.0)
    s["placement_clearance_error_max_abs"] = clr
    # reset-mode DR for all envs, then 1 s PD hold at the action-0 target (default pose + motor offset)
    apply_reset_dr(u, torch.arange(N, device=dev))
    for b in (act.positions_delay_buffer, act.velocities_delay_buffer, act.efforts_delay_buffer):
        b.reset()
    tgt = DEF_Q.clone()
    tgt[:, jt._joint_ids] = jt._offset
    ts = []
    kd_keep = act.damping.clone()
    act.damping[:] = act.damping * args.settle_kd_scale

    def pd_steps(nsteps, log):
        for i in range(nsteps):
            robot.set_joint_position_target(tgt)
            u.scene.write_data_to_sim()
            u.sim.step(render=False)
            u.scene.update(dt=u.physics_dt)
            if i % 10 == 9:
                d_ = robot.data
                ln = d_.root_com_vel_w[:, :3].norm(dim=1)
                jv_ = d_.joint_vel.abs().amax(dim=1)
                log.append({"t": round(len(log) * 10 * u.physics_dt + 10 * u.physics_dt, 3),
                            "lin_q50_q99_max": [float(ln.median()), float(ln.quantile(0.99)), float(ln.max())],
                            "jvel_q50_max": [float(jv_.median()), float(jv_.max())],
                            "z_q50_min": [float(d_.root_link_pose_w[:, 2].median()), float(d_.root_link_pose_w[:, 2].min())]})

    pd_steps(int(round(args.settle_s / u.physics_dt)), ts)
    act.damping[:] = kd_keep
    s["settle_s"] = args.settle_s
    s["settle_kd_scale"] = args.settle_kd_scale
    s["settle_timeseries"] = ts
    d = robot.data
    settled = {"root_pose": d.root_link_pose_w.clone(), "root_vel": d.root_com_vel_w.clone(),
               "jpos": d.joint_pos.clone(), "jvel": d.joint_vel.clone(),
               "applied_torque": d.applied_torque.clone(), "computed_torque": d.computed_torque.clone()}
    fz = cs.data.net_forces_w[:, CS_FOOT, 2]
    s["settled"] = {"lin_speed_max": float(settled["root_vel"][:, :3].norm(dim=1).max()),
                    "ang_speed_max": float(settled["root_vel"][:, 3:].norm(dim=1).max()),
                    "joint_speed_max": float(settled["jvel"].abs().max()),
                    "base_z_minmax": [float(settled["root_pose"][:, 2].min()), float(settled["root_pose"][:, 2].max())],
                    "tilt_deg_max": float(torch.rad2deg(torch.acos((-d.projected_gravity_b[:, 2]).clamp(-1, 1))).max()),
                    "feet_with_fz_gt_1N_min_per_env": int((fz > 1.0).sum(dim=1).min()),
                    "xy_drift_max": float((settled["root_pose"][:, :2] - pose[:, :2]).norm(dim=1).max()),
                    "yaw_drift_max_rad": float(math_utils.wrap_to_pi(yaw_of(settled["root_pose"][:, 3:7]) - yaw).abs().max())}
    sv = {k: v.cpu().numpy() for k, v in settled.items()}
    np.savez(os.path.join(OUT, "settled_validation.npz"), **sv, cell=cell_of.cpu().numpy(), episode_id=np.array(IDS_VAL)[ep_of.cpu().numpy()])
    s["settled_sha256"] = {k: sha_arr(v) for k, v in sv.items()}
    if args.settle_diag_s > 0:
        ts2 = []
        act.damping[:] = act.damping * args.settle_kd_scale
        pd_steps(int(round(args.settle_diag_s / u.physics_dt)), ts2)
        act.damping[:] = kd_keep
        s["settle_diag_continued"] = ts2
    write_state(settled["root_pose"], settled["root_vel"], settled["jpos"], settled["jvel"])
    u._d1b_state["jtarget"] = tgt.clone()

    def physx_readback():
        v = robot.root_physx_view
        tr = v.get_root_transforms().clone()  # x y z qx qy qz qw
        pose_ = torch.cat([tr[:, :3], tr[:, 6:7], tr[:, 3:6]], 1)
        return {"root_pose": pose_, "root_vel": v.get_root_velocities().clone(),
                "jpos": v.get_dof_positions().clone(), "jvel": v.get_dof_velocities().clone()}

    def restore():
        obs_, _ = u.reset(seed=SEED_VAL)
        rb = physx_readback()
        diff = {k: float((rb[k] - settled[k]).abs().max()) for k in rb}
        hsh = {k: sha_arr(rb[k].cpu().numpy()) for k in rb}
        return TensorDict(obs_, batch_size=[N]), diff, hsh

    target[:] = cmd
    u._d1b_g0[:] = args.cond.startswith("g0plus")
    u._d1b_perm[:] = args.cond.endswith("perm2026")
    s["cond"] = args.cond
    o1, d1, h1 = restore()
    s["restore1_first_obs_sha256"] = {k: sha_arr(o1[k].cpu().numpy()) for k in o1.keys()}
    s["restore1_first_critic_without_height_sha256"] = sha_arr(torch.cat([o1["critic"][:, :H_OFF], o1["critic"][:, H_OFF + H_LEN:]], 1).cpu().numpy())
    s["restore1_max_abs_vs_settled"] = d1
    s["restore1_sha256"] = h1
    s["restore1_hash_equal"] = all(h1[k] == s["settled_sha256"][k] for k in h1)
    s["reset_dr_check"] = reset_dr_check()

    def short_roll(o, k=50):
        tr = []
        with torch.inference_mode():
            for _ in range(k):
                a_ = teacher_mean(o)
                o, _, _, _ = env.step(a_)
                tr.append(torch.cat([robot.data.root_link_pose_w, robot.data.joint_pos], 1).cpu().numpy())
        return np.stack(tr)

    tr1 = short_roll(o1)
    s["replay1_traj_sha256"] = sha_arr(tr1)
    o2, d2, h2 = restore()
    s["restore2_max_abs_vs_settled"] = d2
    s["restore2_sha256"] = h2
    s["restore1_vs_restore2_hash_equal"] = h1 == h2
    s["restore_obs_critic_term_max_abs_1_vs_2"] = {nm_: float((o1["critic"][:, a_:a_ + w_] - o2["critic"][:, a_:a_ + w_]).abs().max())
        for nm_, a_, w_ in zip(c_names, np.cumsum([0] + c_dims[:-1]).tolist(), c_dims)}
    s["restore2_hash_equal"] = all(h2[k] == s["settled_sha256"][k] for k in h2)
    s["restore_obs_equal_1_vs_2"] = {k: bool(torch.equal(o1[k], o2[k])) for k in o1.keys()}
    tr2 = short_roll(o2)
    s["replay_50_steps_bitwise_equal"] = bool(np.array_equal(tr1, tr2))
    s["replay_50_steps_max_abs"] = float(np.abs(tr1 - tr2).max())
    dif = np.abs(tr1 - tr2).reshape(tr1.shape[0], -1).max(axis=1)
    s["replay_first_differing_step"] = int(np.flatnonzero(dif > 0)[0]) + 1 if (dif > 0).any() else None
    s["replay_max_abs_by_step_1_2_5_10_50"] = [float(dif[i]) for i in (0, 1, 4, 9, len(dif) - 1)]
    RESTORE_OK = s["restore1_vs_restore2_hash_equal"]  # state write; the in-process replay is reported separately
    s["restore_ok"] = RESTORE_OK
    s["wall_s"] = time.time() - T0
    dump("settle", s)
    if not RESTORE_OK:
        print("[D1B] restore mismatch: stopping before dyn/fall/foot", flush=True)
        STAGES = [x for x in STAGES if x not in ("dyn", "fall", "foot")]


# ---------------------------------------------------------------------------------- recorder
class Rec:
    def __init__(self, T):
        self.T = T
        self.f = {k: np.zeros((T + 1, N) + sh, np.float32) for k, sh in (
            ("pos", (3,)), ("yaw", ()), ("vel_w", (3,)), ("grav_z", ()), ("foot_c", (4, 3)), ("foot_v", (4, 3)),
            ("foot_fz", (4,)), ("nonfoot_fmax", ()))}
        self.b = {k: np.zeros((T + 1, N), bool) for k in ("base_contact", "local_all_miss", "harness_err", "reset", "nonfinite_state")}
        self.k = 0
        self.pre = None
        self.stale_row0 = None

    def grab(self):
        d = robot.data
        fh = cs.data.net_forces_w_history
        st = {"pos": d.root_link_pose_w[:, :3], "yaw": yaw_of(d.root_link_pose_w[:, 3:7]), "vel_w": d.root_com_vel_w[:, :3],
              "grav_z": d.projected_gravity_b[:, 2], "foot_c": foot_centres(), "foot_v": d.body_link_lin_vel_w[:, FOOT_IDS],
              "foot_fz": cs.data.net_forces_w[:, CS_FOOT, 2],
              "nonfoot_fmax": fh[:, :, CS_NONFOOT].norm(dim=-1).amax(dim=(1, 2)),
              "base_contact": fh[:, :, CS_BASE].norm(dim=-1).amax(dim=1) > 1.0,
              "local_all_miss": torch.isposinf(hs_small.data.ray_hits_w[..., 2]).all(dim=1)}
        m = L.input_masks(hs.data.pos_w, hs.data.ray_hits_w)
        err = torch.zeros(N, dtype=torch.bool, device=dev)
        for k in L.ERROR_KEYS:
            err |= m[k] if m[k].dim() == 1 else m[k].any(dim=1)
        st["harness_err"] = err
        st["nonfinite_state"] = ~(torch.isfinite(d.root_link_pose_w).all(1) & torch.isfinite(d.root_com_vel_w).all(1))
        return {k: v.detach().cpu().numpy() for k, v in st.items()}

    def put(self, j, st, ids=None):
        for k, v in st.items():
            arr = self.f[k] if k in self.f else self.b[k]
            if ids is None:
                arr[j] = v
            else:
                arr[j, ids] = v[ids]

    def pre_reset(self, env_ids):
        self.pre = (env_ids.detach().cpu().numpy().copy(), self.grab())


REC = None
_orig_reset_idx = u._reset_idx


def _hooked_reset_idx(env_ids):
    if REC is not None and len(env_ids) > 0:
        REC.pre_reset(env_ids)
    _orig_reset_idx(env_ids)


u._reset_idx = _hooked_reset_idx


def rollout(o, T, act_fn, per_step=None):
    global REC
    REC = Rec(T)
    REC.put(0, REC.grab())
    with torch.inference_mode():
        for k in range(T):
            a_ = act_fn(o)
            REC.pre = None
            o, _, _, _ = env.step(a_)
            st = REC.grab()
            REC.put(k + 1, st)
            if REC.pre is not None:
                ids, pst = REC.pre
                REC.put(k + 1, pst, ids)   # terminal (pre-reset) state at this sample
                REC.b["reset"][k + 1, ids] = True
            if k == 0:
                REC.stale_row0 = {"base_contact_row0_envs": int(REC.b["base_contact"][0].sum()),
                                  "nonfoot_gt1N_row0_envs": int((REC.f["nonfoot_fmax"][0] > 1.0).sum()),
                                  "foot_fz_row0_differs_from_row1_envs": int((np.abs(REC.f["foot_fz"][0] - REC.f["foot_fz"][1]) > 1.0).any(axis=1).sum())}
                for kk in ("foot_fz", "nonfoot_fmax"):
                    REC.f[kk][0] = REC.f[kk][1]
                REC.b["base_contact"][0] = REC.b["base_contact"][1]
            if per_step is not None:
                per_step(k + 1, o)
    rec, REC = REC, None
    return o, rec


def fall_eval(rec, ids, z_ref):
    """Per env: latched fall from the proposal rules on the samples up to the first reset (inclusive)."""
    out = []
    T = rec.T
    for e in ids:
        rs_ = np.flatnonzero(rec.b["reset"][:, e])
        end = int(rs_[0]) if rs_.size else T
        sl = slice(0, end + 1)
        try:
            r_ = L.gap_fall(rec.f["pos"][sl, e, 2], rec.f["vel_w"][sl, e, 2], z_ref, base_contact=rec.b["base_contact"][sl, e],
                            grav_z=rec.f["grav_z"][sl, e], local_all_miss=rec.b["local_all_miss"][sl, e])
            r_["harness_error"] = bool(rec.b["harness_err"][sl, e].any())
        except L.HarnessError as ex:
            r_ = {"j_fail": -1, "reason": "harness_error", "harness_error": True, "detail": str(ex)}
        r_["reset_at"] = end if rs_.size else None
        below = (rec.f["foot_c"][sl, e, :, 2] < z_ref - 0.05).any(axis=1)
        r_["feet_below_bank_samples"] = int(below.sum())
        r_["feet_below_bank_1s_j"] = L.hold_index(below, L.span_samples(1.0))
        out.append(r_)
    return out


def foot_eval(rec, ids, col_w, col_idx, end_at=None):
    """Per env and foot: touchdowns (2 samples > 1 N), class, margin, risky, slip; tile-local coordinates."""
    res = []
    for e in ids:
        w = col_w[e]
        org = ORG[int(col_idx[e])].cpu().numpy()
        rs_ = np.flatnonzero(rec.b["reset"][:, e])
        end = int(rs_[0]) if rs_.size else rec.T
        if end_at is not None:
            end = min(end, end_at[e])
        evs = []
        for fi in range(4):
            fz = rec.f["foot_fz"][:end + 1, e, fi]
            c = rec.f["foot_c"][:end + 1, e, fi] - org
            td, lo, ini = L.foot_events(fz)
            sl = L.stance_slip(c[:, 0], c[:, 1], td, [x for x in lo if x > td[0]] if td else [], end)
            for n_, j in enumerate(td):
                cls = L.classify_touchdown(c[j, 0], c[j, 1], c[j, 2], A, w, 4.5, FOOT_R)
                mg = float(L.support_margin(c[j, 0], c[j, 1], A, w)) if w > 0 else float("inf")
                evs.append({"foot": FOOT_NAMES[fi], "j": int(j), "x": float(c[j, 0]), "y": float(c[j, 1]), "zc": float(c[j, 2]),
                            "cls": cls, "margin": mg, "risky": bool(L.risky(mg, FOOT_R)) if cls in ("inner", "outer") else None,
                            "vz": float(rec.f["foot_v"][j, e, fi, 2]), "slip": sl[n_] if n_ < len(sl) else None})
        res.append(evs)
    return res


# ================================================================================== stage dyn
if "dyn" in STAGES:
    s = {}
    xy, yaw, cmd, w_e = d1b_starts()
    target[:] = cmd
    rot = (ep_of >= 90)
    target[rot] = torch.tensor([0.0, 0.0, 0.5], device=dev)
    cond = ep_of % 4  # 0 legacy-normal, 1 legacy-perm2026, 2 g0plus-normal, 3 g0plus-perm2026
    u._d1b_g0[:] = cond >= 2
    u._d1b_perm[:] = (cond % 2) == 1
    forced = (ep_of >= 80) & (ep_of < 90)
    T = 300
    o, _ = u.reset(seed=SEED_VAL)
    o = TensorDict(o, batch_size=[N])
    w_col = torch.tensor([w for _, w in VAL_COLS], device=dev)[col_of]
    pattern = hs.ray_starts[..., :2]
    acc = {"steps": 0, "sensor_pos_vs_root_max_abs": 0.0, "ray_xy_vs_root_pose_max_abs": 0.0, "nohit_mismatch": 0,
           "nohit_rays": 0, "ambiguous": 0, "block_vs_expected_max_abs": 0.0, "block_vs_expected_prevpose_max_abs": 0.0,
           "after_forced_reset": {"envs": 0, "block_vs_expected_max_abs": 0.0, "nohit_mismatch": 0, "sensor_pos_vs_root_max_abs": 0.0}}
    prev = {"pos": robot.data.root_link_pose_w.clone()}

    def expected_block(root_pose):
        pos, yw = root_pose[:, :3], yaw_of(root_pose[:, 3:7])
        c_, s_ = torch.cos(yw)[:, None], torch.sin(yw)[:, None]
        ex = pos[:, 0:1] + c_ * pattern[..., 0] - s_ * pattern[..., 1]
        ey = pos[:, 1:2] + s_ * pattern[..., 0] + c_ * pattern[..., 1]
        lx, ly = ex - ORG[col_of, 0:1], ey - ORG[col_of, 1:2]
        cheb = torch.maximum(lx.abs(), ly.abs())
        wv = w_col[:, None]
        void = (cheb > A + 1e-3) & (cheb < A + wv - 1e-3)
        bank = (cheb < A - 1e-3) | (cheb > A + wv + 1e-3)
        raw = (pos[:, 2:3] - 0.0 - 0.5).expand_as(cheb)
        fin = (raw.clamp(-1, 1) * 2.5)
        nh = torch.where(u._d1b_g0[:, None], torch.full_like(fin, 2.5), torch.full_like(fin, -2.5))
        return torch.where(void, nh, fin), void, ~(void | bank), torch.stack([ex, ey], -1)

    def check(k, o_):
        rp = robot.data.root_link_pose_w
        d = hs.data
        exp, void, amb, exy = expected_block(rp)
        blk = o_["critic"][:, H_OFF:H_OFF + H_LEN]
        okm = ~amb
        nh = torch.isposinf(d.ray_hits_w[..., 2])
        fin = torch.isfinite(d.ray_hits_w[..., 2])
        acc["steps"] += 1
        acc["sensor_pos_vs_root_max_abs"] = max(acc["sensor_pos_vs_root_max_abs"], float((d.pos_w - rp[:, :3]).abs().max()))
        acc["ray_xy_vs_root_pose_max_abs"] = max(acc["ray_xy_vs_root_pose_max_abs"], float((d.ray_hits_w[..., :2] - exy)[fin].abs().max()))
        acc["nohit_mismatch"] += int(((nh != void) & okm).sum())
        acc["nohit_rays"] += int(nh.sum())
        acc["ambiguous"] += int(amb.sum())
        acc["block_vs_expected_max_abs"] = max(acc["block_vs_expected_max_abs"], float((blk - exp)[okm].abs().max()))
        expp, _, ambp, _ = expected_block(prev["pos"])
        acc["block_vs_expected_prevpose_max_abs"] = max(acc["block_vs_expected_prevpose_max_abs"], float((blk - expp)[~ambp].abs().max()))
        prev["pos"] = rp.clone()

    # forced auto-reset: time out at step 150 (the env resets inside env.step as in training)
    def act_fn(o_):
        return teacher_mean(o_)

    def per_step2(k, o_):
        if k == 149:
            u.episode_length_buf[forced] = u.max_episode_length - 1
        if k == 150:
            rp = robot.data.root_link_pose_w
            exp, void, amb, _ = expected_block(rp)
            blk = o_["critic"][:, H_OFF:H_OFF + H_LEN]
            fz_ = forced
            acc["after_forced_reset"]["envs"] = int(fz_.sum())
            acc["after_forced_reset"]["reset_flag_set"] = int(torch.as_tensor(REC.b["reset"][150]).sum())
            acc["after_forced_reset"]["block_vs_expected_max_abs"] = float((blk - exp)[fz_][~amb[fz_]].abs().max())
            acc["after_forced_reset"]["sensor_pos_vs_root_max_abs"] = float((hs.data.pos_w - rp[:, :3])[fz_].abs().max())
            acc["after_forced_reset"]["root_vs_restored_start_max_abs"] = float((rp[fz_] - u._d1b_state["root_pose"][fz_]).abs().max())
            nh = torch.isposinf(hs.data.ray_hits_w[..., 2])
            acc["after_forced_reset"]["nohit_mismatch"] = int(((nh != void) & ~amb)[fz_].sum())
        check(k, o_)

    o, rec = rollout(o, T, act_fn, per_step2)
    s["contract"] = acc
    ids_all = list(range(N))
    fe = fall_eval(rec, ids_all, 0.0)
    w_np = w_col.cpu().numpy()
    ft = foot_eval(rec, ids_all, w_np, col_of.cpu().numpy(), end_at=np.where(forced.cpu().numpy(), 150, T))
    # per cell summaries (rotation envs and forced-reset envs separated)
    summ = []
    for c, (ci, w, al) in enumerate(CELLS):
        for role, msk in (("cross", (~rot) & (~forced)), ("rotate", rot), ("forced_reset", forced)):
            ids = torch.nonzero((cell_of == c) & msk).flatten().cpu().tolist()
            if not ids:
                continue
            fl = [fe[i] for i in ids]
            evs = [ev for i in ids for ev in ft[i]]
            cls = {}
            for ev in evs:
                cls[ev["cls"]] = cls.get(ev["cls"], 0) + 1
            outer = [ev for ev in evs if ev["cls"] == "outer"]
            sup = [ev for ev in evs if ev["cls"] in ("inner", "outer")]
            summ.append({"cell": c, "col": VAL_COLS[ci][0], "width": w, "alpha": al, "role": role, "envs": len(ids),
                         "falls": sum(1 for f in fl if f["reason"] not in ("", "harness_error")),
                         "fall_reasons": sorted({f["reason"] for f in fl if f["reason"]}),
                         "harness_error_envs": sum(1 for f in fl if f.get("harness_error")),
                         "all_local_miss_envs": int(rec.b["local_all_miss"][:, ids].any(axis=0).sum()),
                         "touchdowns": len(evs), "td_per_foot_per_s": len(evs) / (4 * len(ids) * T * DT), "td_class": cls,
                         "risky_on_support": sum(1 for ev in sup if ev["risky"]), "support_td": len(sup),
                         "outer_td_x_minus_outer_lip_min": min((ev["x"] - (A + w) for ev in outer), default=None),
                         "zc_minus_r_on_support_minmax": [min((ev["zc"] - FOOT_R for ev in sup), default=None), max((ev["zc"] - FOOT_R for ev in sup), default=None)],
                         "slip_median": float(np.median([ev["slip"] for ev in sup if ev["slip"] is not None])) if sup else None,
                         "x_last_valid_median": float(np.median([rec.f["pos"][int(np.flatnonzero(rec.b["reset"][:, i])[0]) if rec.b["reset"][:, i].any() else T, i, 0] for i in ids]) - ORG[ci, 0].item()),
                         "goal_x_reached_envs": sum(1 for i in ids if (rec.f["pos"][:(int(np.flatnonzero(rec.b["reset"][:, i])[0]) if rec.b["reset"][:, i].any() else T) + 1, i, 0] - ORG[ci, 0].item() >= A + w + 0.80).any())})
    s["cells"] = summ
    s["falls_by_reason"] = {}
    for f in fe:
        s["falls_by_reason"][f["reason"] or "none"] = s["falls_by_reason"].get(f["reason"] or "none", 0) + 1
    # independent end-state label for the crossing envs, for comparison with the detector (not a contract rule)
    lab = []
    for e in range(N):
        if rot[e] or forced[e]:
            continue
        rs_ = np.flatnonzero(rec.b["reset"][:, e])
        end = int(rs_[0]) if rs_.size else T
        zend = float(rec.f["pos"][end, e, 2])
        tilt_end = math.degrees(math.acos(max(-1.0, min(1.0, -float(rec.f["grav_z"][end, e])))))
        gt = "fall" if (zend < 0.10 or tilt_end > 60 or rs_.size) else ("ok" if (zend > 0.20 and tilt_end < 30) else "ambiguous")
        det = fe[e]["reason"] not in ("", "harness_error")
        lab.append((gt, det, fe[e]["reason"], int(cell_of[e])))
    s["crossing_endstate_vs_detector"] = {
        "fall_detected": sum(1 for g_, d_, _, _ in lab if g_ == "fall" and d_), "fall_missed": sum(1 for g_, d_, _, _ in lab if g_ == "fall" and not d_),
        "ok_false_alarm": sum(1 for g_, d_, _, _ in lab if g_ == "ok" and d_), "ok_clear": sum(1 for g_, d_, _, _ in lab if g_ == "ok" and not d_),
        "ambiguous": sum(1 for g_, _, _, _ in lab if g_ == "ambiguous"),
        "missed_cells": sorted({c for g_, d_, _, c in lab if g_ == "fall" and not d_})}
    s["stale_row0"] = rec.stale_row0
    s["crossing_mismatch_details"] = [{"env": e, "cell": c_, "gt_endstate": g_, "detector": rsn, "feet_below_bank_1s_j": fe[e]["feet_below_bank_1s_j"],
                                        "z_end": float(rec.f["pos"][fe[e]["reset_at"] if fe[e]["reset_at"] is not None else T, e, 2])}
                                       for e, (g_, d_, rsn, c_) in zip([e for e in range(N) if not (rot[e] or forced[e])], lab)
                                       if (g_ == "fall" and not d_) or (g_ == "ok" and d_)]
    s["envs_feet_below_bank_1s_without_detection"] = sum(1 for e in range(N) if fe[e]["feet_below_bank_1s_j"] >= 0 and fe[e]["reason"] == "")
    np.savez_compressed(os.path.join(OUT, "dyn_rec.npz"), **rec.f, **rec.b)
    s["wall_s"] = time.time() - T0
    dump("dyn", s)

# ================================================================================== stage fall
# Scenario table. GT is fixed here before the run. 'apriori' = known by construction (checked by the
# validity conditions listed); 'endstate' = fall if base z_end < 0.10 or tilt_end > 60 deg or the env was
# reset by base contact, ok if z_end > 0.20 and tilt_end < 30 deg, otherwise ambiguous (excluded).
SCEN = [
    dict(name="walk_flat_student", col=0, x=A - 0.80, yaw=0.0, vel=None, policy="student", cmd=(0.3, 0, 0), gt="nofall", how="apriori"),
    dict(name="walk_flat_teacher_g0", col=0, x=A - 0.80, yaw=0.0, vel=None, policy="teacher_g0", cmd=(0.3, 0, 0), gt="nofall", how="apriori"),
    dict(name="drop_gapwide060_centre_yaw90", col=5, x=A + 0.30, yaw=math.pi / 2, vel=None, policy="zero", gt="fall", how="apriori"),
    dict(name="drop_beyond_border", col=None, x=None, yaw=0.0, vel=None, policy="zero", gt="fall", how="apriori"),
    dict(name="wedge_gap030_centre_yaw90", col=3, x=A + 0.15, yaw=math.pi / 2, vel=None, policy="zero", gt=None, how="endstate"),
    dict(name="tilted_hang_gap030_front_over_void", col=3, x=A - 0.05, yaw=0.0, vel=None, policy="zero", gt=None, how="endstate"),
    dict(name="jump_flat_vz1.0", col=0, x=0.0, yaw=0.0, vel=(0.0, 0.0, 1.0), policy="zero", gt="nofall", how="apriori_if_upright"),
    dict(name="jump_gap020_vx1.2_vz1.2", col=2, x=A - 0.12, yaw=0.0, vel=(1.2, 0.0, 1.2), policy="zero", gt=None, how="endstate"),
    dict(name="reset_boundary_drop_then_timeout", col=5, x=A + 0.30, yaw=math.pi / 2, vel=None, policy="zero", gt="fall", how="apriori"),
]
if "fall" in STAGES:
    s = {"scenarios": SCEN}
    per = N // len(SCEN)
    sc_of = torch.div(e_idx, per, rounding_mode="floor").clamp(max=len(SCEN) - 1)
    # starts: feet 2 mm above z=0 at the scenario pose (start dx of the episode manifest kept)
    xy = torch.zeros(N, 2, device=dev)
    yw = torch.zeros(N, device=dev)
    cmd_t = torch.zeros(N, 3, device=dev)
    pol = []
    dx = torch.tensor([r["start_dx"] for r in ROWS], device=dev) * 0.0
    for i, sc in enumerate(SCEN):
        m = sc_of == i
        if sc["col"] is None:
            xy[m, 0] = ORG[:, 0].max() + 4.5 + 25.0 + 10.0
            xy[m, 1] = 0.0
        else:
            xy[m] = ORG[sc["col"], :2]
            xy[m, 0] += sc["x"] + dx[m]
        yw[m] = sc["yaw"]
        if "cmd" in sc:
            cmd_t[m] = torch.tensor(sc["cmd"], device=dev)
    pose, clr = ground_contact_pose(xy, yw, 0.0)
    vel = torch.zeros(N, 6, device=dev)
    for i, sc in enumerate(SCEN):
        if sc["vel"] is not None:
            vel[sc_of == i, :3] = torch.tensor(sc["vel"], device=dev)
    # walking scenarios start from the settled D1-B flat state of the same episode (cell 0)
    sv = np.load(os.path.join(OUT, "settled_validation.npz"))
    root_pose = pose.clone()
    jpos = DEF_Q.clone()
    jvel = torch.zeros_like(jpos)
    for i, sc in enumerate(SCEN):
        if sc["policy"] != "zero":
            m = torch.nonzero(sc_of == i).flatten()
            src = (ep_of[m]).cpu().numpy()  # cell 0 rows are env ids 0..E-1
            root_pose[m] = torch.as_tensor(sv["root_pose"][src], device=dev)
            jpos[m] = torch.as_tensor(sv["jpos"][src], device=dev)
            jvel[m] = torch.as_tensor(sv["jvel"][src], device=dev)
    write_state(root_pose, vel, jpos, jvel)
    target[:] = cmd_t
    u._d1b_g0[:] = torch.tensor([sc["policy"] == "teacher_g0" for sc in SCEN], device=dev)[sc_of]
    u._d1b_perm[:] = False
    o, _ = u.reset(seed=SEED_VAL)
    o = TensorDict(o, batch_size=[N])
    s["start_check"] = {"placement_clearance_error_max_abs": clr,
                        "root_vs_requested_max_abs": float((robot.data.root_link_pose_w - root_pose).abs().max())}
    is_st = torch.tensor([sc["policy"] == "student" for sc in SCEN], device=dev)[sc_of]
    is_te = torch.tensor([sc["policy"].startswith("teacher") for sc in SCEN], device=dev)[sc_of]
    rb_ids = torch.nonzero(sc_of == len(SCEN) - 1).flatten()
    T = 150

    def act_fn(o_):
        a_s = policy(o_)
        a_t = teacher_mean(o_)
        z_ = torch.zeros_like(a_s)
        return torch.where(is_st[:, None], a_s, torch.where(is_te[:, None], a_t, z_))

    def per_step(k, o_):
        if k == 39:  # reset-boundary envs: time out at sample 40 (0.80 s), reset onto the flat start
            u.episode_length_buf[rb_ids] = u.max_episode_length - 1
            st = u._d1b_state
            st["root_pose"][rb_ids] = torch.as_tensor(sv["root_pose"][ep_of[rb_ids].cpu().numpy()], device=dev)
            st["root_vel"][rb_ids] = 0.0
            st["jpos"][rb_ids] = torch.as_tensor(sv["jpos"][ep_of[rb_ids].cpu().numpy()], device=dev)
            st["jvel"][rb_ids] = 0.0

    o, rec = rollout(o, T, act_fn, per_step)
    fe = fall_eval(rec, range(N), 0.0)
    rows = []
    for i, sc in enumerate(SCEN):
        ids = torch.nonzero(sc_of == i).flatten().cpu().tolist()
        res = {"name": sc["name"], "envs": len(ids), "gt_rule": sc["how"]}
        tp = fn = fp = tn = amb = invalid = 0
        tdet = []
        details = []
        for e in ids:
            rs_ = np.flatnonzero(rec.b["reset"][:, e])
            end = int(rs_[0]) if rs_.size else T
            zend = float(rec.f["pos"][end, e, 2])
            tilt_end = math.degrees(math.acos(max(-1.0, min(1.0, -float(rec.f["grav_z"][end, e])))))
            if sc["how"] == "endstate" or sc["how"] == "apriori_if_upright":
                if zend < 0.10 or tilt_end > 60 or (rs_.size and rec.b["base_contact"][:end + 1, e].any()):
                    gt = "fall"
                elif zend > 0.20 and tilt_end < 30:
                    gt = "nofall"
                else:
                    gt = "ambiguous"
                if sc["how"] == "apriori_if_upright" and gt != "nofall":
                    invalid += 1
                    continue
            else:
                gt = sc["gt"]
                # validity of the a-priori label
                if sc["name"].startswith("walk") and (rec.b["base_contact"][:, e].any() or rec.f["pos"][:, e, 2].min() < 0.2):
                    invalid += 1
                    continue
                if (sc["name"].startswith("drop") or sc["name"].startswith("reset")) and not (rec.f["nonfoot_fmax"][:26, e].max() < 1.0 and rec.f["foot_fz"][:26, e].max() < 1.0
                                                         and rec.f["pos"][35, e, 2] < -0.5):
                    invalid += 1
                    continue
            det = fe[e]["reason"] not in ("", "harness_error") and 0 <= fe[e]["j_fail"] <= end
            if gt == "ambiguous":
                amb += 1
            elif gt == "fall" and det:
                tp += 1
                tdet.append(fe[e]["j_fail"] * DT)
            elif gt == "fall":
                fn += 1
            elif det:
                fp += 1
            else:
                tn += 1
            if len(details) < 3 or (gt == "fall" and not det) or (gt == "nofall" and det):
                details.append({"env": e, "gt": gt, "detector": fe[e]["reason"], "t_fail": fe[e].get("t_fail"), "z_end": zend,
                                "tilt_end": tilt_end, "z_min": float(rec.f["pos"][:end + 1, e, 2].min()),
                                "all_local_miss_samples": fe[e].get("all_local_miss_count"), "reset_at": fe[e]["reset_at"],
                                "feet_below_bank_samples": fe[e]["feet_below_bank_samples"], "foot_z_end": rec.f["foot_c"][end, e, :, 2].round(3).tolist()})
        zs = [float(rec.f["pos"][fe[e]["reset_at"] if fe[e]["reset_at"] is not None else T, e, 2]) for e in ids]
        res["z_end_minmedmax"] = [min(zs), float(np.median(zs)), max(zs)]
        res["envs_feet_below_bank_1s"] = sum(1 for e in ids if fe[e]["feet_below_bank_1s_j"] >= 0)
        res["detector_reasons"] = sorted({fe[e]["reason"] for e in ids})
        res.update({"tp": tp, "fn": fn, "fp": fp, "tn": tn, "ambiguous": amb, "invalid_label": invalid,
                    "t_detect_minmax": [min(tdet), max(tdet)] if tdet else None, "examples": details})
        if sc["name"].startswith("drop") or sc["name"].startswith("reset"):
            z0 = rec.f["pos"][0, ids, 2]
            # analytic free-fall sample from the recorded start height (continuous time; the sim integrates per 5 ms)
            jj = []
            for z00 in z0:
                tt = np.arange(T + 1) * DT
                zz, vv = z00 - 4.905 * tt ** 2, -9.81 * tt
                jj.append(L.hold_index((zz < -0.10) & (vv < -0.20), 6) * DT)
            res["t_detect_analytic_freefall_minmax"] = [float(min(jj)), float(max(jj))]
        if sc["name"].startswith("reset"):
            pre = [float(rec.f["pos"][40, e, 2]) for e in ids]
            post = [float(robot.data.root_link_pose_w[e, 2]) for e in ids]
            res["reset_flag_at_40"] = int(rec.b["reset"][40, ids].sum())
            res["recorded_z_at_reset_sample_minmax"] = [min(pre), max(pre)]
            res["post_reset_live_z_end_minmax"] = [min(post), max(post)]
            res["latched_j_fail_minmax"] = [min(fe[e]["j_fail"] for e in ids), max(fe[e]["j_fail"] for e in ids)]
            res["outcome_with_goal_after_reset"] = sorted({L.gap_outcome(np.where(np.arange(T + 1) < 41, 1.8, 3.0), np.zeros(T + 1),
                                                                           fe[e]["j_fail"], [45, 45, 45, 45], A, 0.6)["outcome"] for e in ids})
        rows.append(res)
    s["results"] = rows
    s["stale_row0"] = rec.stale_row0
    np.savez_compressed(os.path.join(OUT, "fall_rec.npz"), sc_of=sc_of.cpu().numpy(), **rec.f, **rec.b)
    s["wall_s"] = time.time() - T0
    dump("fall", s)

# ================================================================================== stage foot
if "foot" in STAGES:
    s = {}
    # known placements on gap030 (yaw 0): rear feet on the OUTER bank at designed margin m from the outer lip,
    # or front feet on the INNER platform at margin m from the inner lip. Dropped from 2 cm, PD hold, 1 s.
    DES = [("outer", m) for m in (0.08, 0.045, 0.03, 0.015, -0.03)] + [("inner", m) for m in (0.08, 0.03, -0.03)]
    per = N // len(DES)
    dg = torch.div(e_idx, per, rounding_mode="floor").clamp(max=len(DES) - 1)
    # foot x offsets relative to the base at the default pose, yaw 0
    pose = torch.zeros(N, 7, device=dev)
    pose[:, :2] = ORG[3, :2]
    pose[:, 2] = 0.45
    pose[:, 3] = 1.0
    place_static(pose)
    fc = foot_centres(fresh=True)
    rear_dx = (fc[:, 2:, 0] - pose[:, None, 0]).mean(dim=1)   # RL, RR
    front_dx = (fc[:, :2, 0] - pose[:, None, 0]).mean(dim=1)  # FL, FR
    xy = ORG[3, :2].repeat(N, 1)
    for i, (side, m) in enumerate(DES):
        k = dg == i
        if side == "outer":
            xy[k, 0] += (A + 0.30 + m) - rear_dx[k]
        else:
            xy[k, 0] += (A - m) - front_dx[k]
    pose, clr = ground_contact_pose(xy, torch.zeros(N, device=dev), 0.0, clearance=0.005)
    # test-only neutral robot so the designed foot position is kept until touchdown: no motor offset, no delay,
    # nominal gains, friction 1 / restitution 0 on every shape (the manifests are not changed)
    u._d1b_dr["moff"][:] = 0.0
    u._d1b_dr["lag"][:] = 0
    u._d1b_dr["kp"][:] = 1.0
    u._d1b_dr["kd"][:] = 1.0
    _mats = robot.root_physx_view.get_material_properties()
    _mats[..., 0] = 1.0
    _mats[..., 1] = 1.0
    _mats[..., 2] = 0.0
    robot.root_physx_view.set_material_properties(_mats, torch.arange(N, device="cpu"))
    s["test_only_robot"] = "motor offset 0, delay 0, gains x1, friction 1, restitution 0, feet 5 mm above the top at t=0"
    write_state(pose, torch.zeros(N, 6, device=dev), DEF_Q.clone(), torch.zeros_like(DEF_Q))
    u._d1b_state["jtarget"] = DEF_Q.clone()
    target[:] = 0.0
    u._d1b_g0[:] = False
    o, _ = u.reset(seed=SEED_VAL)
    o = TensorDict(o, batch_size=[N])
    o, rec = rollout(o, 50, lambda o_: torch.zeros(N, 12, device=dev))
    s["stale_row0"] = rec.stale_row0
    w_np = np.full(N, 0.30)
    ft = foot_eval(rec, range(N), w_np, np.full(N, 3))
    rows = []
    for i, (side, m) in enumerate(DES):
        ids = torch.nonzero(dg == i).flatten().cpu().tolist()
        feet = ("RL_foot", "RR_foot") if side == "outer" else ("FL_foot", "FR_foot")
        first = []
        for e in ids:
            ev = [x for x in ft[e] if x["foot"] in feet]
            ev.sort(key=lambda x: x["j"])
            first += [x for x in ev if x["j"] == min(y["j"] for y in ev if y["foot"] == x["foot"])] if ev else []
        expected_risky = (m - FOOT_R) < 0.02
        sup = [x for x in first if x["cls"] in ("inner", "outer")]
        rows.append({"side": side, "designed_margin": m, "expected": "void_or_wall" if m < 0 else ("risky" if expected_risky else "safe"),
                     "envs": len(ids), "first_td_events": len(first), "classes": sorted({x["cls"] for x in first}),
                     "class_counts": {c: sum(1 for x in first if x["cls"] == c) for c in {x["cls"] for x in first}},
                     "margin_minus_designed_max_abs": max((abs(x["margin"] - m) for x in sup), default=None),
                     "margin_minus_designed_median_abs": float(np.median([abs(x["margin"] - m) for x in sup])) if sup else None,
                     "risky_matches_design": sum(1 for x in sup if x["risky"] == expected_risky),
                     "risky_true": sum(1 for x in sup if x["risky"]), "risky_false": sum(1 for x in sup if x["risky"] is False),
                     "feet_without_td": 2 * len(ids) - len(first), "td_time_s_minmax": [min((x["j"] * DT for x in first), default=None), max((x["j"] * DT for x in first), default=None)]})
    s["placement_clearance_error_max_abs"] = clr
    s["results"] = rows
    s["wall_s"] = time.time() - T0
    dump("foot", s)

meta["t_end"] = time.strftime("%Y-%m-%d %H:%M:%S")
meta["smi_end"] = smi()
meta["torch_max_mem_alloc_MiB"] = torch.cuda.max_memory_allocated() / 2 ** 20
meta["wall_s"] = time.time() - T0
dump("meta", meta)
print("[D1B] done", flush=True)
env.close()
app.close()
