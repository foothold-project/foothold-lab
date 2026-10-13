# One randomization scene of the E1 student: same checkpoint, same command, same start; one disturbance per run.
#   kind none     : no disturbance (reference)
#   kind push     : the training push term (push_by_setting_velocity semantics: add a delta to root_vel_w, interval from
#                   the run's env.yaml, 4 s) with FIXED deltas instead of random ones (--push, item k = k-th firing),
#                   every world component checked against the training velocity_range when applied
#   kind friction : the training material term (robot bodies, startup) with a FIXED value instead of 64 random buckets;
#                   the ground keeps its trained material. Robot values are read back from PhysX, the ground and the
#                   combine modes from the USD stage, the contact value is computed with the PhysX combine rule, and with
#                   --friction_probe a foot-vs-ground contact sensor records friction / normal force in the run.
# Every scene uses the same deterministic material and push terms (no random draws), so all random draws (mass, COM,
# gains, motor offset, delays) and the start are identical across scenes; the driver checks the fingerprints.
# Physics and rendering in one process: two envs for MoECTS, only student env 0 is judged; the viewport camera follows its base, one frame per 50 Hz state, every
# frame through the frame gate (re-render up to --max_rerender, then stop, no video). The illegal_contact termination is
# off so the robot is not reset after a fall: the fall is recorded with the Q rule (base contact > 1 N, the training
# termination, computed with the training function each step) and the run continues for the video.
# Output (all under --outdir, which must be inside _eval/out_rand): meta.json · record.csv · traj.npz · pushes.json ·
# <scene>_master.mp4 (50 fps) · <scene>_web.mp4 (30 fps, 720p, h264, faststart) · stills/ · result.json · fail.json
# The run ends with "[RAND] done scene=<scene> attempt=<id>" on success; on any error "[RAND] FAIL ..." and exit 3.
# Usage (through rand_driver.py: isaac_slot_v3.py -> gpu_guard.py on GPU 1 -> usd_isolate_run_v3.py -> this script):
#   FOOTHOLD_USD_ROOT=<attempt>/usd python usd_isolate_run_v3.py q_rand.py --scene base --kind none --attempt_id X --outdir <attempt>
import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
import traceback

import h5py  # noqa: F401  (Windows DLL preload, as scripts/rsl_rl/play.py)
import tensordict  # noqa: F401

from isaaclab.app import AppLauncher

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import rand_gate as RG  # noqa: E402
import rand_lib as RL  # noqa: E402
import rand_overlay as RO  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--scene", required=True)
ap.add_argument("--kind", choices=["none", "push", "friction"], required=True)
ap.add_argument("--attempt_id", required=True)
ap.add_argument("--outdir", required=True)
ap.add_argument("--checkpoint", default=RL.CKPT_DEFAULT)
ap.add_argument("--train_yaml", default=RL.TRAIN_YAML_DEFAULT)
ap.add_argument("--cmd", default="0.5,0.0,0.0", help="vx,vy,wz fixed for the whole run")
ap.add_argument("--duration_s", type=float, default=20.0)
ap.add_argument("--eval_seed", type=int, default=1000)
ap.add_argument("--push", default="", help="kind push: 'vy=+0.4;vy=-0.4;...' item k at the k-th firing of the push interval")
ap.add_argument("--push_frame", choices=["heading", "world"], default="heading")
ap.add_argument("--friction", default="1.0,1.0", help="robot body static,dynamic friction (all shapes)")
ap.add_argument("--restitution", type=float, default=0.0)
ap.add_argument("--start_row", type=int, default=0)
ap.add_argument("--sim_device", default="cuda:0")
ap.add_argument("--physx_small_buffers", action="store_true")
ap.add_argument("--obs_noise", action="store_true", help="keep training observation noise (default off, as q_eval)")
ap.add_argument("--friction_probe", action="store_true", help="extra foot contact sensor vs the ground with friction forces")
ap.add_argument("--no_video", action="store_true")
ap.add_argument("--warmup_frames", type=int, default=20)
ap.add_argument("--max_rerender", type=int, default=12)
ap.add_argument("--test_inject", default="", help="gate test only: black_once:J | sky_once:J | sky_always:J (state J)")
ap.add_argument("--cam_eye", default="-1.3,-1.7,0.75", help="camera eye offset from the base [m] (q_video.py)")
ap.add_argument("--cam_target", default="0.15,0.0,-0.1", help="camera target offset from the base [m] (q_video.py)")
AppLauncher.add_app_launcher_args(ap)
args = ap.parse_args()
args.headless = True
args.enable_cameras = not args.no_video

# --- checks before Isaac starts ---------------------------------------------------------------------------------------------
RL.check_out_path(args.outdir)
os.makedirs(args.outdir, exist_ok=True)
DR = RL.load_train_dr(args.train_yaml)
SCHED = RL.parse_push_schedule(args.push)
FS, FD = (float(x) for x in args.friction.split(","))
CMD = [float(x) for x in args.cmd.split(",")]
assert len(CMD) == 3
if args.kind == "push":
    assert SCHED and any(not d["none"] for d in SCHED), "kind push needs --push"
    pv = RL.plan_violations(SCHED, DR["push_velocity_range"], args.push_frame)
    assert not pv, f"push schedule outside the training range for some heading: {pv}"
else:
    assert not SCHED, "--push only with kind push"
if args.kind != "friction":
    assert (FS, FD) == (1.0, 1.0), "only kind friction changes the robot friction (others use 1.0, 1.0)"
lo_s, hi_s = DR["material_static_range"]
lo_d, hi_d = DR["material_dynamic_range"]
lo_r, hi_r = DR["material_restitution_range"]
assert lo_s <= FS <= hi_s and lo_d <= FD <= hi_d and lo_r <= args.restitution <= hi_r, "friction outside the training range"
assert FD <= FS or not DR["material_make_consistent"], "dynamic > static (training make_consistent=True)"
if args.test_inject:
    _k, _j = args.test_inject.split(":")
    assert _k in ("black_once", "sky_once", "sky_always") and int(_j) >= 0
T = int(round(args.duration_s / RL.DT))
OUT = args.outdir
T0 = time.time()
HANDLES = {"writer": None}  # the open video writer, closed by the failure path before the partial file is moved

app_launcher = AppLauncher(args)
simulation_app = app_launcher.app


def smi():
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=index,uuid,memory.used,memory.total,utilization.gpu",
                            "--format=csv,noheader"], capture_output=True, text=True, timeout=20)
        return r.stdout.strip().splitlines()
    except Exception as e:  # pragma: no cover
        return [f"nvidia-smi failed: {e}"]


def dict_diff(a, b, path=""):
    """Same as q_eval_cmdr.py."""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append(f"{path}/{k}: only in {'train' if k in a else 'eval'}")
            else:
                out += dict_diff(a[k], b[k], f"{path}/{k}")
    elif isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            out.append(f"{path}: len {len(a)} vs {len(b)}")
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                out += dict_diff(x, y, f"{path}[{i}]")
    else:
        if isinstance(a, float) and isinstance(b, float):
            if not (a == b or (math.isnan(a) and math.isnan(b))):
                out.append(f"{path}: {a} vs {b}")
        elif a != b:
            out.append(f"{path}: {a!r} vs {b!r}")
    return out


def wjson(name, obj):
    p = os.path.join(OUT, name)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)
    os.replace(p + ".tmp", p)


def main():
    import copy

    import gymnasium as gym
    import imageio
    import numpy as np
    import torch
    import yaml
    from tensordict import TensorDict

    import isaaclab.utils.math as math_utils
    from isaaclab.envs.mdp.terminations import illegal_contact
    from isaaclab.managers import EventTermCfg as EventTerm
    from isaaclab.managers import SceneEntityCfg
    from isaaclab.sensors import ContactSensorCfg
    from isaaclab.utils.dict import class_to_dict
    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
    from rsl_rl.runners import OnPolicyRunnerCTS

    import robot_lab.tasks  # noqa: F401  (registers RobotLab-Go2-v0)
    from robot_lab.tasks.go2.env_cfg import Go2EnvCfg
    from robot_lab.tasks.go2.mdp.terrains import TERRAIN_CFG
    from robot_lab.tasks.go2.rsl_rl_cfg import MoECTSRunnerCfg

    def sha_arr(*arrs):
        h = hashlib.sha256()
        for a in arrs:
            h.update(np.ascontiguousarray(a).tobytes())
        return h.hexdigest()

    meta = {"args": vars(args), "T_steps": T, "dt": RL.DT, "train_dr": DR, "push_schedule": SCHED,
            "env_vars": {k: os.environ.get(k) for k in ("CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER", "OMNI_KIT_ACCEPT_EULA",
                                                         "FOOTHOLD_USD_ROOT", "FOOTHOLD_USD_PATCHED")},
            "smi_start": smi(), "t_start": time.strftime("%Y-%m-%d %H:%M:%S"),
            "code_sha256": {os.path.basename(p): RL.sha256_file(p) for p in
                            [os.path.join(HERE, f) for f in ("q_rand.py", "rand_lib.py", "rand_gate.py", "rand_overlay.py")] +
                            [os.path.join(EVAL, f) for f in ("frame_audit.py", "q_metrics.py")] +
                            [p for p in (RL.SLOT_SCRIPT, RL.ISOLATE_SCRIPT) if os.path.exists(p)]},
            "checkpoint": args.checkpoint, "checkpoint_sha256": RL.sha256_file(args.checkpoint),
            "train_yaml": args.train_yaml, "train_yaml_sha256": RL.sha256_file(args.train_yaml)}

    # --- deterministic event terms (same in every scene) -------------------------------------------------------------------
    PUSH_LOG = []

    def push_fixed(env, env_ids, schedule, frame, vel_range, asset_cfg):
        """Training push_by_setting_velocity with a fixed delta: root_vel_w += delta, written with
        write_root_velocity_to_sim. Called by the event manager at the training interval (inside env.step, after the
        physics and the resets, before the observation). Item k of the schedule at the k-th firing."""
        env_ids = env_ids[env_ids == 0]  # only the judged student can fire or advance the schedule
        if len(env_ids) == 0:
            return
        asset = env.scene[asset_cfg.name]
        k = len(PUSH_LOG)
        j = int(env.episode_length_buf[env_ids][0])
        e = {"index": k, "state_j": j, "t_s": j * RL.DT, "common_step": int(env.common_step_counter), "applied": False}
        if k < len(schedule) and not schedule[k]["none"]:
            hd = float(asset.data.heading_w[env_ids][0])
            w = RL.to_world(schedule[k], hd, frame)
            viol = RL.range_violations(w, vel_range)
            if viol:
                raise RuntimeError(f"push {k} outside the training velocity_range at heading {hd}: {viol}")
            before = asset.data.root_vel_w[env_ids].clone()
            vel = before + torch.tensor([w], device=asset.device, dtype=before.dtype)
            asset.write_root_velocity_to_sim(vel, env_ids=env_ids)
            after = asset.data.root_vel_w[env_ids].clone()
            e.update(applied=True, request=schedule[k], frame=frame, heading_rad=hd, dv_world_requested=w,
                     vel_w_before=before[0].tolist(), vel_w_after=after[0].tolist(),
                     dv_world_measured=(after - before)[0].tolist())
        PUSH_LOG.append(e)

    def set_material_fixed(env, env_ids, static, dynamic, restitution, asset_cfg):
        """Training randomize_rigid_body_material with one fixed value on every shape of the robot (startup)."""
        asset = env.scene[asset_cfg.name]
        m = asset.root_physx_view.get_material_properties()
        m[..., 0] = static
        m[..., 1] = dynamic
        m[..., 2] = restitution
        asset.root_physx_view.set_material_properties(m, torch.arange(env.scene.num_envs, device="cpu"))

    def reset_root_q(env, env_ids, pose_range, asset_cfg=SceneEntityCfg("robot")):
        """q_eval_cmdr.py reset: pose offset from pose_range, yaw from env._q_yaw, zero velocity."""
        asset = env.scene[asset_cfg.name]
        root = asset.data.default_root_state[env_ids].clone()
        r = torch.tensor([pose_range.get(k, (0.0, 0.0)) for k in ("x", "y", "z")], device=asset.device)
        s = math_utils.sample_uniform(r[:, 0], r[:, 1], (len(env_ids), 3), device=asset.device)
        pos = root[:, :3] + env.scene.env_origins[env_ids] + s
        yaw_all = getattr(env, "_q_yaw", None)
        yaw = torch.zeros(len(env_ids), device=asset.device) if yaw_all is None else yaw_all[env_ids]
        z = torch.zeros_like(yaw)
        quat = math_utils.quat_mul(root[:, 3:7], math_utils.quat_from_euler_xyz(z, z, yaw))
        asset.write_root_pose_to_sim(torch.cat([pos, quat], dim=-1), env_ids=env_ids)
        asset.write_root_velocity_to_sim(torch.zeros(len(env_ids), 6, device=asset.device), env_ids=env_ids)

    # --- env config ----------------------------------------------------------------------------------------------------------
    env_cfg = Go2EnvCfg()
    train_view = class_to_dict(env_cfg)
    with open(args.train_yaml, "r", encoding="utf-8") as f:
        train_yaml = yaml.load(f, Loader=yaml.UnsafeLoader)
    diffs = {k: dict_diff(train_yaml.get(k), train_view.get(k), k) for k in ["observations", "actions", "decimation", "sim", "events", "terminations"]}
    diffs["scene/robot"] = dict_diff(train_yaml["scene"]["robot"], train_view["scene"]["robot"], "scene/robot")
    meta["default_cfg_vs_train_yaml_counts"] = {k: len(v) for k, v in diffs.items()}
    meta["default_cfg_vs_train_yaml"] = {k: v[:20] for k, v in diffs.items()}

    changes = []
    env_cfg.scene.num_envs = 2  # MoECTS needs env 1 as teacher; env 0 remains the only judged student
    env_cfg.seed = args.eval_seed
    env_cfg.sim.device = args.sim_device
    if args.physx_small_buffers:
        env_cfg.sim.physx.gpu_max_rigid_patch_count = 2 ** 17
        env_cfg.sim.physx.gpu_collision_stack_size = 64 * 1024 * 1024
        changes.append("physx buffers reduced (rigid patches 2^17, collision stack 64 MiB)")
    if not args.obs_noise:
        env_cfg.observations.policy.enable_corruption = False
        env_cfg.observations.single_obs.enable_corruption = False
        changes.append("observation noise off for policy and single_obs (as q_eval)")
    env_cfg.events.randomize_push_robot = EventTerm(
        func=push_fixed, mode="interval", interval_range_s=tuple(DR["push_interval_s"]), is_global_time=DR["push_is_global_time"],
        params={"schedule": SCHED, "frame": args.push_frame, "vel_range": DR["push_velocity_range"], "asset_cfg": SceneEntityCfg("robot")})
    changes.append(f"push: training interval {DR['push_interval_s']} s, fixed deltas {[RL.describe_push(d, args.push_frame) for d in SCHED]} instead of uniform draws")
    env_cfg.events.randomize_rigid_body_material = EventTerm(
        func=set_material_fixed, mode="startup",
        params={"static": FS, "dynamic": FD, "restitution": args.restitution, "asset_cfg": SceneEntityCfg("robot", body_names=".*")})
    changes.append(f"robot material: fixed static {FS} dynamic {FD} restitution {args.restitution} on every shape instead of 64 random buckets")
    env_cfg.events.reset_robot_joints.params["position_range"] = (1.0, 1.0)
    changes.append("reset joints at the default pose, scale (1,1) (as q_eval)")
    env_cfg.events.reset_base = EventTerm(func=reset_root_q, mode="reset",
                                          params={"pose_range": {"x": (0.0, 0.0), "y": (0.0, 0.0), "z": (0.0, 0.0)}})
    changes.append("reset_base: fixed start at the tile origin + default root pose, yaw 0 (command +x), velocity 0")
    env_cfg.curriculum.terrain_levels = None
    env_cfg.curriculum.base_linear_velocity = None
    env_cfg.curriculum.base_height_l2 = None
    changes.append("all curriculum terms off")
    env_cfg.episode_length_s = args.duration_s + 10.0
    changes.append(f"episode_length_s {env_cfg.episode_length_s} (no time_out inside the run)")
    term_cfg = env_cfg.terminations.illegal_contact
    BASE_THRESH = float(term_cfg.params["threshold"])
    BASE_SENSOR = copy.deepcopy(term_cfg.params["sensor_cfg"])
    env_cfg.terminations.illegal_contact = None
    changes.append(f"illegal_contact termination off (no reset at a fall); the same function (threshold {BASE_THRESH} N) is evaluated every step and recorded")
    tg = copy.deepcopy(TERRAIN_CFG)
    tg.sub_terrains = {"flat": copy.deepcopy(TERRAIN_CFG.sub_terrains["flat"])}
    tg.sub_terrains["flat"].proportion = 1.0
    tg.num_cols = 1
    tg.num_rows = 10
    tg.difficulty_range = (0.5, 0.5)
    tg.curriculum = True
    tg.seed = args.eval_seed
    tg.use_cache = False
    env_cfg.scene.terrain.terrain_generator = tg
    env_cfg.scene.terrain.max_init_terrain_level = None
    changes.append(f"terrain: flat only (training flat family), 10 rows, seed {args.eval_seed}, student start row {args.start_row}, teacher row {(args.start_row + 5) % tg.num_rows}")
    if args.friction_probe:
        env_cfg.scene.foot_probe = ContactSensorCfg(
            prim_path="{ENV_REGEX_NS}/Robot/.*_foot", update_period=0.0, history_length=0, track_air_time=False,
            filter_prim_paths_expr=["/World/ground/terrain/mesh"], track_friction_forces=True, max_contact_data_count_per_prim=8)
        changes.append("friction probe: extra contact sensor on the feet filtered against /World/ground/terrain/mesh with friction forces (reporting only)")
    env_cfg.viewer.resolution = (1280, 720)
    meta["eval_changes"] = changes
    meta["base_contact_rule"] = {"threshold_N": BASE_THRESH, "sensor": BASE_SENSOR.name, "body_names": BASE_SENSOR.body_names}
    # training contract (ASTRA 17d 2.4): the evaluation config AS BUILT against the training env.yaml, full lists. The driver
    # accepts only the differences this tool makes on purpose (rand_lib.allowed_train_diff_paths).
    try:
        eval_view = class_to_dict(env_cfg)
        tc = {g: dict_diff(train_yaml.get(g), eval_view.get(g), g) for g in ("observations", "actions", "decimation", "sim")}
        tc["scene/robot"] = dict_diff(train_yaml["scene"]["robot"], eval_view["scene"]["robot"], "scene/robot")
        meta["train_contract"] = {"diffs": tc, "compared": "evaluation config as built vs the training env.yaml",
                                  "obs_noise": bool(args.obs_noise), "physx_small_buffers": bool(args.physx_small_buffers),
                                  "sim_device": args.sim_device}
    except Exception as ex:  # noqa: BLE001  recorded; the driver refuses an attempt without a contract
        meta["train_contract"] = {"error": f"{type(ex).__name__}: {ex}"}

    env = gym.make("RobotLab-Go2-v0", cfg=env_cfg, render_mode=None if args.no_video else "rgb_array")
    env = RslRlVecEnvWrapper(env, clip_actions=None)
    u = env.unwrapped
    dev = u.device
    robot = u.scene["robot"]
    meta["smi_after_env"] = smi()

    agent_cfg = MoECTSRunnerCfg()
    agent_cfg.device = args.sim_device
    runner = OnPolicyRunnerCTS(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    runner.load(args.checkpoint)
    meta["loaded_iter"] = int(runner.current_learning_iteration)
    policy = runner.get_inference_policy(device=dev)
    pnn = runner.alg.policy
    meta["policy_class"] = type(pnn).__name__
    meta["inference_fn"] = f"{type(pnn).__name__}.{policy.__name__}"
    meta["devices"] = {"env_device": str(dev), "sim_device": str(u.sim.device), "runner_device": str(runner.device)}
    _jt = u.action_manager.get_term("joint_pos")
    _sc = _jt._scale
    if hasattr(_sc, "cpu"):
        _sc = _sc.detach().cpu().numpy()
        _sc = (_sc[0] if _sc.ndim == 2 else _sc).tolist()
    else:
        _sc = [float(_sc)] * len(_jt._joint_names)
    meta["eval_env"] = {"num_envs": int(u.num_envs), "judged_env_id": 0, "teacher_env_id": 1,
                        "physics_dt": float(u.physics_dt), "step_dt": float(u.step_dt), "decimation": int(u.cfg.decimation),
                        "action_joint_names": [str(x) for x in _jt._joint_names], "action_scale": [float(x) for x in _sc],
                        "source": "the env as built (ManagerBasedRLEnv physics_dt, step_dt, action term joints and scale)"}
    if torch.cuda.is_available():
        meta["devices"]["torch_cuda0_name"] = torch.cuda.get_device_properties(0).name
        meta["devices"]["torch_cuda0_uuid"] = str(getattr(torch.cuda.get_device_properties(0), "uuid", ""))

    # --- start: tile, command, seeded reset ----------------------------------------------------------------------------------
    ter = u.scene.terrain
    ter.terrain_types[:] = 0
    ter.terrain_levels[:] = args.start_row
    ter.terrain_levels[1] = (args.start_row + 5) % tg.num_rows  # keep the unjudged teacher away from env 0's camera
    ter.env_origins[:] = ter.terrain_origins[ter.terrain_levels, ter.terrain_types]
    meta["eval_env"]["teacher_terrain_row"] = int(ter.terrain_levels[1])
    u._q_yaw = torch.zeros(u.num_envs, device=dev)
    ct = u.command_manager.get_term("base_velocity")
    target = torch.tensor([CMD], device=dev, dtype=torch.float).repeat(u.num_envs, 1)

    def _fixed_resample(env_ids):
        ct.commands[env_ids] = target[env_ids]
        ct.time_left[env_ids] = 1.0e9

    ct._resample = _fixed_resample
    obs_buf, _ = u.reset(seed=args.eval_seed)
    obs = TensorDict(obs_buf, batch_size=[u.num_envs])
    PUSH_LOG.clear()

    # --- fingerprint of the start and of every random draw (must be equal across scenes) --------------------------------------
    fp = {"init_root_pose": sha_arr(np.round(robot.data.root_state_w[0:1, :7].cpu().numpy(), 6)),
          "init_joint_pos": sha_arr(np.round(robot.data.joint_pos[0:1].cpu().numpy(), 6)),
          "body_masses": sha_arr(np.round(robot.root_physx_view.get_masses()[0:1].cpu().numpy(), 6)),
          "com": sha_arr(np.round(robot.root_physx_view.get_coms()[0:1].cpu().numpy(), 6))}
    for name, act in robot.actuators.items():
        fp[f"actuator_{name}_stiffness"] = sha_arr(np.round(act.stiffness[0:1].cpu().numpy(), 6))
        fp[f"actuator_{name}_damping"] = sha_arr(np.round(act.damping[0:1].cpu().numpy(), 6))
        if hasattr(act, "positions_delay_buffer"):
            fp[f"actuator_{name}_delay_lags"] = sha_arr(act.positions_delay_buffer.time_lags[0:1].cpu().numpy().astype(np.int64))
    jt = u.action_manager.get_term("joint_pos")
    off = jt._offset.cpu().numpy() if hasattr(jt._offset, "cpu") else np.asarray(jt._offset)
    fp["motor_zero_offset"] = sha_arr(np.round(off[0:1] if off.ndim > 1 else off, 6))
    meta["start"] = {"root_state_w": robot.data.root_state_w[0].cpu().numpy().round(6).tolist(),
                     "env_origin": ter.env_origins[0].cpu().numpy().round(6).tolist()}

    # --- material read back: PhysX (robot shapes), USD (ground, robot bindings, scene default) ---------------------------------
    mats = robot.root_physx_view.get_material_properties()[0:1].cpu().numpy()
    mrb = {"robot_tensor": {"n_shapes": int(mats.shape[1]),
                            "static_min": float(mats[..., 0].min()), "static_max": float(mats[..., 0].max()),
                            "dynamic_min": float(mats[..., 1].min()), "dynamic_max": float(mats[..., 1].max()),
                            "restitution_min": float(mats[..., 2].min()), "restitution_max": float(mats[..., 2].max()),
                            "source": "robot.root_physx_view.get_material_properties() after the startup term"}}
    fp["robot_material"] = sha_arr(np.round(mats, 6))
    import omni.usd
    from pxr import Usd, UsdGeom, UsdPhysics, UsdShade

    stage = omni.usd.get_context().get_stage()

    def mat_attrs(mprim):
        out = {"path": str(mprim.GetPath())}
        for key, name in (("static_friction", "physics:staticFriction"), ("dynamic_friction", "physics:dynamicFriction"),
                          ("restitution", "physics:restitution"), ("friction_combine_mode", "physxMaterial:frictionCombineMode"),
                          ("restitution_combine_mode", "physxMaterial:restitutionCombineMode")):
            a = mprim.GetAttribute(name)
            out[key] = a.Get() if a and a.IsValid() else None
            out[key + "_authored"] = bool(a and a.IsValid() and a.HasAuthoredValue())
        for k in ("friction_combine_mode", "restitution_combine_mode"):
            if out[k] is not None:
                out[k] = str(out[k])
        return out

    def bound_physics_material(prim):
        try:
            m, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial("physics")
            return m.GetPrim() if m and m.GetPrim().IsValid() else None
        except Exception:  # pragma: no cover
            return None

    try:
        gprim = stage.GetPrimAtPath("/World/ground/terrain/mesh")
        gm = bound_physics_material(gprim) if gprim.IsValid() else None
        mrb["ground_usd"] = mat_attrs(gm) if gm is not None else {"error": "no physics material bound to /World/ground/terrain/mesh"}
    except Exception as ex:  # pragma: no cover
        mrb["ground_usd"] = {"error": repr(ex)}
    try:
        sprim = stage.GetPrimAtPath(env_cfg.sim.physics_prim_path)
        sm = bound_physics_material(sprim)
        mrb["scene_default_usd"] = mat_attrs(sm) if sm is not None else {"error": "no default material bound to the physics scene"}
    except Exception as ex:  # pragma: no cover
        mrb["scene_default_usd"] = {"error": repr(ex)}
    try:
        rprim = stage.GetPrimAtPath("/World/envs/env_0/Robot")
        colliders, bound = 0, {}
        for p in Usd.PrimRange(rprim, Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)):
            if p.HasAPI(UsdPhysics.CollisionAPI):
                colliders += 1
                m = bound_physics_material(p)
                key = str(m.GetPath()) if m is not None else "(none: scene default material)"
                bound[key] = bound.get(key, 0) + 1
        mrb["robot_usd_bindings"] = {"colliders": colliders, "bound": bound,
                                     "materials": {k: mat_attrs(stage.GetPrimAtPath(k)) for k in bound if not k.startswith("(none")}}
    except Exception as ex:  # pragma: no cover
        mrb["robot_usd_bindings"] = {"error": repr(ex)}
    g = mrb.get("ground_usd", {})
    sd = mrb.get("scene_default_usd", {})
    rb = mrb.get("robot_usd_bindings", {}).get("materials", {})
    modes = {v.get("friction_combine_mode") or "average" for v in rb.values()}
    if any(k.startswith("(none") for k in mrb.get("robot_usd_bindings", {}).get("bound", {})) or not modes:
        modes.add(sd.get("friction_combine_mode") or "average")
    robot_mode_usd = sorted(modes)
    g_mode = g.get("friction_combine_mode") or "average"
    if g.get("static_friction") is not None:
        eff = {m: RL.effective_friction({"static": FS, "dynamic": FD},
                                        {"static": float(g["static_friction"]), "dynamic": float(g["dynamic_friction"])}, m, g_mode)
               for m in robot_mode_usd}
    else:
        eff = {}
    mrb["effective"] = {"robot_combine_mode_usd": robot_mode_usd, "ground_combine_mode": g_mode, "by_robot_mode": eff,
                        "note": "robot values are written per shape by the PhysX tensor API; the combine mode of those runtime "
                                "materials is not exposed by the tensor API (unconfirmed, PhysX default average assumed). "
                                "Contact value = PhysX combine rule on the robot value and the ground USD value."}
    meta["material_readback"] = mrb
    meta["fingerprint"] = fp

    # terrain meshes (ASTRA 17d 2.2): local geometry hash (as q_eval) AND the world transform and a hash of the world-space
    # points, so a moved collision mesh with the same local points does not count as the same terrain
    hs = []
    for prim in stage.Traverse():
        if str(prim.GetPath()).startswith("/World/ground") and prim.IsA(UsdGeom.Mesh):
            mesh = UsdGeom.Mesh(prim)
            pts = np.array(mesh.GetPointsAttr().Get(), dtype=np.float32)
            idx = np.array(mesh.GetFaceVertexIndicesAttr().Get(), dtype=np.int64)
            cnt = np.array(mesh.GetFaceVertexCountsAttr().Get(), dtype=np.int64)
            xf = np.array(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default()), dtype=np.float64)
            wpts = (np.c_[pts.astype(np.float64), np.ones(len(pts))] @ xf)[:, :3]  # USD row-vector convention (as q_video.py)
            hs.append({"path": str(prim.GetPath()), "points": int(pts.shape[0]), "faces": int(cnt.shape[0]),
                       "geom_sha256": sha_arr(np.round(pts, 5), idx), "xform_world": np.round(xf, 6).flatten().tolist(),
                       "world_sha256": sha_arr(np.round(wpts, 4), idx, cnt)})
    meta["terrain_mesh"] = hs

    # --- student path checks (q_eval_cmdr.py) ---------------------------------------------------------------------------------
    gen = torch.Generator(device=dev)
    gen.manual_seed(12345)  # separate generator, env RNG untouched
    checks = {}
    with torch.inference_mode():
        a0 = policy(obs)
        o1 = obs.clone()
        o1["critic"] = torch.randn(o1["critic"].shape, generator=gen, device=dev) * 10.0
        checks["teacher_input_randomized_max_abs_action_change"] = float((policy(o1) - a0)[0:1].abs().max())
        lat, _ = pnn.student_moe_encoder(pnn.actor_obs_normalizer(obs["policy"]))
        a_manual = pnn.actor(torch.cat([lat, pnn.single_obs_normalizer(obs["single_obs"])], dim=-1))
        checks["manual_student_path_vs_act_inference_max_abs"] = float((a_manual - a0)[0:1].abs().max())
    meta["checks_pre"] = checks
    wjson("meta.json", meta)

    # --- rollout -------------------------------------------------------------------------------------------------------------
    col = {c: i for i, c in enumerate(RL.COLUMNS)}
    rows = np.full((T + 1, len(RL.COLUMNS)), np.nan, dtype=np.float64)
    fid = [robot.find_bodies(n)[0][0] for n in RL.FEET]
    cs = u.scene["contact_forces"]
    fid_cs = [cs.find_bodies(n)[0][0] for n in RL.FEET]
    BASE_SENSOR.resolve(u.scene)
    probe = u.scene["foot_probe"] if args.friction_probe else None
    fid_pr = [probe.find_bodies(n)[0][0] for n in RL.FEET] if probe is not None else None
    hs_small = u.scene["height_scanner_small"]
    cos60 = math.cos(math.radians(60.0))
    tilt_hold = int(round(0.2 / RL.DT))
    state = {"tilt_run": 0, "fall_j": None, "fall_reason": "", "fall_onset_j": None}
    fires_pred = RL.predict_fire_states(DR["push_interval_s"][0], RL.DT, T)
    sched_t = [j * RL.DT for k, j in enumerate(fires_pred) if k < len(SCHED) and not SCHED[k]["none"]]
    REASON_KO = {"base_contact": "몸통 접촉", "tilt60": "60도 넘게 0.2 s 기울어짐", "below_support": "지지면 아래"}

    def snap(j, act_abs):
        d = robot.data
        r = rows[j]
        r[col["step"]] = j
        r[col["t_s"]] = j * RL.DT
        pos = d.root_pos_w[0].cpu().numpy()
        r[col["base_x_m"]:col["base_z_w_m"] + 1] = pos
        r[col["quat_w"]:col["quat_z"] + 1] = d.root_quat_w[0].cpu().numpy()
        r[col["heading_rad"]] = float(d.heading_w[0])
        r[col["linvel_world_x_mps"]:col["linvel_world_z_mps"] + 1] = d.root_lin_vel_w[0].cpu().numpy()
        r[col["linvel_body_x_mps"]:col["linvel_body_z_mps"] + 1] = d.root_lin_vel_b[0].cpu().numpy()
        r[col["angvel_body_x_radps"]:col["angvel_body_z_radps"] + 1] = d.root_ang_vel_b[0].cpu().numpy()
        gz = float(d.projected_gravity_b[0, 2])
        r[col["gravity_body_z"]] = gz
        z = hs_small.data.ray_hits_w[0, :, 2]
        z = torch.where(torch.isfinite(z), z, torch.nan)
        ground = float(torch.nanmean(z))
        r[col["ground_z_m"]] = ground
        hag = float(pos[2]) - ground
        r[col["base_height_above_ground_m"]] = hag
        r[col["cmd_vx_mps"]:col["cmd_wz_radps"] + 1] = target[0].cpu().numpy()
        bc = bool(illegal_contact(u, BASE_THRESH, BASE_SENSOR)[0]) if j > 0 else False
        r[col["base_contact"]] = int(bc)
        # online fall (display only; the result uses q_metrics.fall_index on the whole record)
        state["tilt_run"] = state["tilt_run"] + 1 if (-gz < cos60) else 0
        if state["fall_j"] is None:
            why = "base_contact" if bc else ("tilt60" if state["tilt_run"] >= tilt_hold else ("below_support" if hag < 0 else ""))
            if why:
                state["fall_j"], state["fall_reason"] = j, why
                state["fall_onset_j"] = j - tilt_hold + 1 if why == "tilt60" else j
        r[col["fall_online"]] = int(state["fall_j"] is not None)
        r[col["push_index"]] = -1
        for e in PUSH_LOG:
            if e["applied"] and e["state_j"] == j:
                r[col["push_index"]] = e["index"]
                w = e["dv_world_requested"]
                r[col["push_dv_world_x_mps"]], r[col["push_dv_world_y_mps"]] = w[0], w[1]
                r[col["push_dw_world_x_radps"]], r[col["push_dw_world_y_radps"]], r[col["push_dw_world_z_radps"]] = w[3], w[4], w[5]
        fw = cs.data.net_forces_w[0, fid_cs]  # (4, 3) world, last physics substep
        fn = fw.norm(dim=-1).cpu().numpy()
        sp = d.body_lin_vel_w[0, fid, :2].norm(dim=-1).cpu().numpy()
        for i, ft in enumerate(RL.FEET):
            r[col[f"{ft}_contact"]] = int(fn[i] > 1.0)
            r[col[f"{ft}_normal_force_N"]] = fn[i]
            r[col[f"{ft}_speed_xy_mps"]] = sp[i]
        if probe is not None:
            nf = probe.data.force_matrix_w[0, fid_pr].reshape(4, -1, 3).sum(dim=1).norm(dim=-1).cpu().numpy()
            ff = probe.data.friction_forces_w[0, fid_pr].reshape(4, -1, 3).sum(dim=1).norm(dim=-1).cpu().numpy()
            for i, ft in enumerate(RL.FEET):
                r[col[f"{ft}_probe_normal_N"]] = nf[i]
                r[col[f"{ft}_probe_friction_N"]] = ff[i]
        r[col["action_abs_mean"]] = act_abs
        return pos

    # --- video --------------------------------------------------------------------------------------------------------------
    video = not args.no_video
    eye_off = np.array([float(x) for x in args.cam_eye.split(",")])
    tgt_off = np.array([float(x) for x in args.cam_target.split(",")])
    inj_kind, inj_j = (args.test_inject.split(":")[0], int(args.test_inject.split(":")[1])) if args.test_inject else ("", -1)
    rerenders = []
    stills = []
    writer = None
    HFOV = None
    master = os.path.join(OUT, f"{args.scene}_master.mp4")
    web = os.path.join(OUT, f"{args.scene}_web.mp4")
    if video:
        os.makedirs(os.path.join(OUT, "stills"), exist_ok=True)
        cam = stage.GetPrimAtPath(env_cfg.viewer.cam_prim_path)
        HFOV = 2.0 * math.atan(float(cam.GetAttribute("horizontalAperture").Get()) / (2.0 * float(cam.GetAttribute("focalLength").Get())))
        meta["camera"] = {"hfov_deg": math.degrees(HFOV), "eye_offset": eye_off.tolist(), "target_offset": tgt_off.tolist(),
                          "follow": "fixed offset from the base position every state (q_video.py)"}
        writer = imageio.get_writer(master, fps=50, codec="libx264", quality=8, macro_block_size=8)
        HANDLES["writer"] = writer
    # Burned-in text (ASTRA 17d 2.2 · 5): no pairing claim ("같은 출발 · 교란만 다름") in the frames, because the cross-scene
    # checks run only after every scene; the page may add it when summary.json says the pairing is valid. The material is the
    # robot's EVERY shape (not only the feet) and the contact value is a calculation under the average assumption.
    run_line = (f"E1 student · model_{meta['loaded_iter']} · 평지 · 시드 {args.eval_seed} · 사전 정한 1판 (결과로 고르지 않음) · "
                f"관측 잡음 {'켬' if args.obs_noise else '끔'}")

    def _num(v):
        return float(v) if v is not None else float("nan")

    gs, gd = _num(g.get("static_friction")), _num(g.get("dynamic_friction"))
    if args.kind == "none":
        scene_line, scene_color = "기준 · 교란 없음", RO.WHITE
    elif args.kind == "push":
        scene_line = "밀기 · 학습 범위 안 고정값 · " + RO.push_series_ko(SCHED, args.push_frame)
        scene_color = RO.ORANGE
    else:
        scene_line = (f"{'낮은' if FS < 1.0 else '높은'} 마찰 · 로봇 모든 shape 재질 {FS:.2f} / {FD:.2f} "
                      f"(로봇 쪽 학습 범위 {lo_s:g}~{hi_s:g})")
        scene_color = RO.CYAN
    e0 = next(iter(eff.values()), None)
    fric_line = (f"재질: 로봇 모든 shape {FS:.2f} / {FD:.2f} · 바닥 {gs:.2f} / {gd:.2f} · 접촉 "
                 + (f"{e0['static']:.2f} / {e0['dynamic']:.2f} ({g_mode} 가정 · 런타임 결합 미확인)" if e0 else "미확인"))
    stills_at = {0: "t00", T // 2: "mid", T: "end"}
    for k, jf in enumerate(fires_pred):
        if k < len(SCHED) and not SCHED[k]["none"] and jf + 10 <= T:
            stills_at[jf + 10] = f"push{k + 1}_plus0.2s"

    def frame_for(j, pos):
        p = pos.astype(float)
        eye, tgt = p + eye_off, p + tgt_off
        inj_here = (j == inj_j)

        def render(tries):
            u.sim.set_camera_view(eye=tuple(eye), target=tuple(tgt))
            if inj_here and (inj_kind == "sky_always" or (inj_kind == "sky_once" and tries == 0)):
                u.sim.set_camera_view(eye=tuple(eye), target=(eye[0] + 0.01, eye[1], eye[2] + 10.0))
            n = args.warmup_frames if (j == 0 and tries == 0) else 1
            img = None
            for _ in range(n):
                img = u.render()
            a = np.asarray(img)[..., :3]
            if inj_here and inj_kind == "black_once" and tries == 0:
                a = np.zeros_like(a)
            return a

        uv = RG.project(eye, tgt, p, 1280, 720, HFOV)
        arr = RG.capture_with_gate(render, uv, args.max_rerender, j, rerenders)
        last = [e for e in PUSH_LOG if e["applied"] and e["state_j"] <= j]
        arrow = None
        if last and (j - last[-1]["state_j"]) * RL.DT < RO.MARK_S:
            e = last[-1]
            arrow = RO.arrow_px(RG.project, eye, tgt, p, e["dv_world_requested"][:2], 1280, 720, HFOV)
            bottom, bcol = (f"밀기 #{e['index'] + 1} · {e['t_s']:.2f} s · {RO.push_label_ko(e['request'], e['frame'])} · "
                            f"세계 속도 변화 ({e['dv_world_measured'][0]:+.2f}, {e['dv_world_measured'][1]:+.2f}) m/s"), RO.ORANGE
        elif args.kind == "friction":
            bottom, bcol = fric_line, RO.CYAN
        elif args.kind == "push":
            bottom, bcol = (f"밀기 예정 {' · '.join(f'{t:.2f}' for t in sched_t)} s (학습 간격 설정 "
                            f"{DR['push_interval_s'][0]:g} s 의 실제 step) · 재질 로봇 모든 shape {FS:.2f} · 바닥 {gs:.2f}"), RO.WHITE
        else:
            bottom, bcol = f"교란 없음 · 재질 로봇 모든 shape {FS:.2f} · 바닥 {gs:.2f}", RO.WHITE
        r = rows[j]
        if state["fall_j"] is not None:
            status, scol = (f"넘어짐 감지 {state['fall_j'] * RL.DT:.2f} s ({REASON_KO[state['fall_reason']]}) · "
                            f"이후는 참고 화면 (판정 밖)"), RO.RED
        else:
            status, scol = "넘어짐 없음", RO.WHITE
        info = {"run_line": run_line, "scene_line": scene_line, "scene_color": scene_color, "t_s": j * RL.DT,
                "cmd": CMD, "vel": (r[col["linvel_body_x_mps"]], r[col["linvel_body_y_mps"]], r[col["angvel_body_z_radps"]]),
                "status": status, "status_color": scol, "bottom_line": bottom, "bottom_color": bcol,
                "duration_s": args.duration_s, "ticks_sched": sched_t,
                "ticks_applied": [e["t_s"] for e in PUSH_LOG if e["applied"] and e["state_j"] <= j],
                "fall_t": None if state["fall_j"] is None else state["fall_j"] * RL.DT, "arrow": arrow}
        fr = RO.draw_overlay(arr, info)
        writer.append_data(fr)
        if j in stills_at or (state["fall_j"] == j):
            from PIL import Image
            name = f"stills/{args.scene}_{stills_at.get(j, 'fall')}_j{j:04d}.png"
            Image.fromarray(fr).save(os.path.join(OUT, name))
            stills.append(name)

    cmd_err_single = cmd_err_hist = 0.0
    nonfinite = 0
    t_roll = time.time()
    smi_mid = None
    with torch.inference_mode():
        pos = snap(0, float("nan"))
        if video:
            frame_for(0, pos)
        for k in range(T):
            cmd_err_single = max(cmd_err_single, float((obs["single_obs"][0:1, 6:9] - target[0:1]).abs().max()))
            cmd_err_hist = max(cmd_err_hist, float((obs["policy"][0:1, 87:90] - target[0:1]).abs().max()))
            act = policy(obs)
            nonfinite += int((~torch.isfinite(act[0:1])).sum()) + int((~torch.isfinite(obs["policy"][0:1])).sum())
            ct.commands[:] = target
            obs, _, _, _ = env.step(act)
            pos = snap(k + 1, float(act[0].abs().mean()))
            if video:
                frame_for(k + 1, pos)
            if k == T // 2:
                smi_mid = smi()
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    meta["rollout_wall_s"] = time.time() - t_roll
    meta["smi_mid"] = smi_mid
    meta["torch_max_mem_alloc_MiB"] = torch.cuda.max_memory_allocated() / 2 ** 20 if torch.cuda.is_available() else None
    checks_run = {"obs_single_cmd_vs_target_max_abs": cmd_err_single, "obs_history_latest_cmd_vs_target_max_abs": cmd_err_hist,
                  "nonfinite_action_or_obs_count": nonfinite}
    meta["checks_run"] = checks_run
    if writer is not None:
        writer.close()
        HANDLES["writer"] = None

    # --- records -------------------------------------------------------------------------------------------------------------
    RL.write_record(os.path.join(OUT, "record.csv"), rows)
    np.savez(os.path.join(OUT, "traj.npz"), rows=rows, columns=np.array(RL.COLUMNS))
    wjson("pushes.json", PUSH_LOG)
    c = {name: rows[:, i] for i, name in enumerate(RL.COLUMNS)}
    fall = RL.fall_summary(c["base_contact"] > 0.5, c["gravity_body_z"], c["base_height_above_ground_m"])
    fall["online_j"], fall["online_reason"], fall["online_onset_j"] = state["fall_j"], state["fall_reason"], state["fall_onset_j"]
    stats = {"walk": RL.walk_summary(c, fall["j"]), "push_response": RL.push_response(c, PUSH_LOG, fall["j"])}
    meta["smi_end"] = smi()
    wjson("meta.json", meta)

    # --- videos: gate every frame of master and web copy --------------------------------------------------------------------
    vinfo = {}
    if video:
        vinfo = {"master": os.path.basename(master), "web": os.path.basename(web), "frames_master": T + 1,
                 "rerendered_frames": len({x[0] for x in rerenders}), "rerender_calls": len(rerenders),
                 "rerenders": [list(x) for x in rerenders[:200]], "max_rerender": args.max_rerender,
                 "test_inject": args.test_inject, "stills": stills}
        vinfo.update(RG.publish(master, web, os.path.join(OUT, "rejected"), expect_master_frames=T + 1))
    result = {"schema": RL.RESULT_SCHEMA, "attempt_id": args.attempt_id, "scene": args.scene, "kind": args.kind,
              "checkpoint": args.checkpoint, "checkpoint_sha256": meta["checkpoint_sha256"], "loaded_iter": meta["loaded_iter"],
              "train_yaml_sha256": meta["train_yaml_sha256"], "cmd": CMD, "duration_s": args.duration_s, "T_steps": T,
              "eval_seed": args.eval_seed, "sim_device": args.sim_device, "obs_noise": bool(args.obs_noise),
              "friction_probe": bool(args.friction_probe),
              "friction_requested": {"static": FS, "dynamic": FD, "restitution": args.restitution},
              "material_readback": mrb, "fingerprint": fp, "terrain_mesh": hs,
              "eval_env": meta.get("eval_env"), "train_contract": meta.get("train_contract"),
              "push": {"schedule": SCHED, "frame": args.push_frame, "interval_s": DR["push_interval_s"],
                       "velocity_range": DR["push_velocity_range"], "events": PUSH_LOG, "predicted_fire_states": fires_pred},
              "fall": fall, "stats": stats, "checks_pre": checks, "checks_run": checks_run, "video": vinfo,
              "files": {"record_csv": "record.csv", "traj_npz": "traj.npz", "meta_json": "meta.json", "pushes_json": "pushes.json"},
              "code_sha256": meta["code_sha256"], "t_start": meta["t_start"], "t_end": time.strftime("%Y-%m-%d %H:%M:%S"),
              "wall_s": round(time.time() - T0, 1), "rollout_wall_s": round(meta["rollout_wall_s"], 1),
              "torch_max_mem_alloc_MiB": meta["torch_max_mem_alloc_MiB"], "smi": {"start": meta["smi_start"], "mid": smi_mid, "end": meta["smi_end"]},
              "statement_scope": "one predefined episode under this disturbance setting; not a robustness or randomization-range verification"}
    wjson("result.json", result)
    print(f"[RAND] fall {json.dumps({k: fall[k] for k in ('fell', 't_s', 'reason')})} pushes_applied "
          f"{sum(1 for e in PUSH_LOG if e['applied'])} rerender_calls {len(rerenders)}", flush=True)
    print(f"[RAND] done scene={args.scene} attempt={args.attempt_id}", flush=True)
    return env


if __name__ == "__main__":
    _env = None
    try:
        _env = main()
    except BaseException as ex:  # noqa: BLE001  (any error: record, print, hard exit so Kit cannot turn it into exit 0)
        print(f"[RAND] FAIL {type(ex).__name__}: {str(ex)[:500]}", flush=True)
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        moved = []
        try:
            if HANDLES["writer"] is not None:
                HANDLES["writer"].close()  # release the file (ffmpeg holds it open on Windows)
        except Exception:  # pragma: no cover
            pass
        try:  # a partial or ungated video must not stay where a finished one would be
            for _n in (f"{args.scene}_master.mp4", f"{args.scene}_web.mp4"):
                _p = os.path.join(OUT, _n)
                if os.path.exists(_p):
                    os.makedirs(os.path.join(OUT, "rejected"), exist_ok=True)
                    os.replace(_p, os.path.join(OUT, "rejected", _n + ".failed"))
                    moved.append(_n)
        except Exception:  # pragma: no cover
            pass
        try:
            wjson("fail.json", {"attempt_id": args.attempt_id, "scene": args.scene, "error": f"{type(ex).__name__}: {ex}",
                                "traceback": traceback.format_exc(), "moved_videos": moved,
                                "t": time.strftime("%Y-%m-%d %H:%M:%S")})
        except Exception:  # pragma: no cover
            pass
        os._exit(3)
    try:
        _env.close()
    finally:
        simulation_app.close()
