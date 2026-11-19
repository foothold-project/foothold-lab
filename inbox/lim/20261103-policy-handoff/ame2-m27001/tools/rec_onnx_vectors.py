"""AME-2 app handoff (2026-11-03): record real teacher observations for the ONNX parity check.

Builds the training task (Ame2-Go2-Gaze-NoGapStones5) with 2 robots, puts robot 0 on a flat tile
(the rough column with slope and roughness set to 0) and robot 1 on a stair_up tile, and
records STEPS control steps of (teacher_prop, teacher_mapping, policy action) per robot.
Observation noise is switched off (deployment-like inputs). The env cfg actually used is dumped
to env_record.yaml before the env is built (diff it against params/env.yaml).

  cd <ame2_spd> ; go2/scripts/run.sh py /root/onnx1103/rec_onnx_vectors.py --headless
      --checkpoint <model.pt> --out_dir /root/onnx1103/rec agent.actor.crop_x=12 ...
"""

import argparse
import hashlib
import json
import os
import sys

from isaaclab.app import AppLauncher

sys.path.append(os.path.join(os.getcwd(), "go2", "scripts", "rsl_rl"))
import cli_args  # isort: skip

parser = argparse.ArgumentParser()
parser.add_argument("--task", type=str, default="Ame2-Go2-Gaze-NoGapStones5")
parser.add_argument("--agent", type=str, default="rsl_rl_cfg_entry_point")
parser.add_argument("--out_dir", type=str, required=True)
parser.add_argument("--steps", type=int, default=200)
parser.add_argument("--stair_level", type=int, default=5)
cli_args.add_rsl_rl_args(parser)
AppLauncher.add_app_launcher_args(parser)
args, hydra_args = parser.parse_known_args()
sys.argv = [sys.argv[0]] + hydra_args
app = AppLauncher(args).app

import gymnasium as gym
import numpy as np
import torch

from rsl_rl.runners import OnPolicyRunner

from isaaclab.utils.io import dump_yaml
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
from isaaclab_tasks.utils.hydra import hydra_task_config

import ame2_go2.tasks  # noqa: F401
from ame2_go2.provenance import code_id
from ame2_go2.tasks.mdp.events import _go2_column_terrain_names
from ame2_go2.tasks.mdp.observations import ame2_joint_pos_rel


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


@hydra_task_config(args.task, args.agent)
def main(env_cfg, agent_cfg):
    agent_cfg = cli_args.update_rsl_rl_cfg(agent_cfg, args)
    os.makedirs(args.out_dir, exist_ok=True)
    env_cfg.seed = agent_cfg.seed
    env_cfg.scene.num_envs = 2
    gen = env_cfg.scene.terrain.terrain_generator
    gen.sub_terrains["rough"].max_slope_deg = 0.0      # flat tile
    gen.sub_terrains["rough"].max_roughness_m = 0.0
    env_cfg.curriculum.terrain_levels = None            # keep the chosen tiles at reset
    env_cfg.curriculum.teacher_mapping_noise = None     # observation noise off (deployment-like inputs)
    env_cfg.observations.teacher_mapping.teacher_mapping.params["custom_noise"] = [0.0, 0.0, 0.0]
    env_cfg.observations.teacher_prop.enable_corruption = False
    env_cfg.scene.height_scanner.drift_range = (0.0, 0.0)
    dump_yaml(os.path.join(args.out_dir, "env_record.yaml"), env_cfg)
    dump_yaml(os.path.join(args.out_dir, "agent_record.yaml"), agent_cfg)

    env = RslRlVecEnvWrapper(gym.make(args.task, cfg=env_cfg), clip_actions=agent_cfg.clip_actions)
    u = env.unwrapped
    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    runner.load(args.checkpoint)
    policy = runner.get_inference_policy(device=u.device)
    model = runner.alg.get_policy()

    terrain = u.scene.terrain
    names = _go2_column_terrain_names(terrain.cfg.terrain_generator)
    col_flat, col_stair = names.index("rough"), names.index("stair_up")
    terrain.terrain_types[:] = torch.tensor([col_flat, col_stair], device=u.device)
    terrain.terrain_levels[:] = torch.tensor([0, args.stair_level], device=u.device)
    terrain.env_origins[:] = terrain.terrain_origins[terrain.terrain_levels, terrain.terrain_types]
    env.reset()
    obs = env.get_observations()

    robot = u.scene["robot"]
    term = u.action_manager.get_term("joint_pos")
    q0 = robot.data.default_joint_pos.clone()
    sensor = u.scene["height_scanner"]
    n, T = 2, args.steps
    keys = ("prop", "mapping", "action", "gaze_r", "target_q", "joint_pos", "lin_vel_b", "ang_vel_b", "gravity_b", "done", "a_prev")
    rec = {k: [] for k in keys}
    a_prev = torch.zeros(n, 12, device=u.device)
    with torch.inference_mode():
        for t in range(T):
            act = policy(obs)
            rec["prop"].append(obs["teacher_prop"].float().cpu().numpy())
            rec["mapping"].append(obs["teacher_mapping"].float().cpu().numpy())
            rec["action"].append(act.float().cpu().numpy())
            rec["gaze_r"].append(model._last_gaze_r.float().cpu().numpy())
            rec["joint_pos"].append((robot.data.joint_pos - q0).cpu().numpy())
            rec["lin_vel_b"].append(robot.data.root_lin_vel_b.cpu().numpy())
            rec["ang_vel_b"].append(robot.data.root_ang_vel_b.cpu().numpy())
            rec["gravity_b"].append(robot.data.projected_gravity_b.cpu().numpy())
            rec["a_prev"].append(a_prev.cpu().numpy())
            obs, _, dones, _ = env.step(act)
            rec["target_q"].append(term.processed_actions.cpu().numpy())
            rec["done"].append(dones.cpu().numpy().astype(bool))
            a_prev = torch.where(dones.bool().unsqueeze(1), torch.zeros_like(act), act)
    R = {k: np.stack(v, axis=1) for k, v in rec.items()}  # (n, T, ...)

    # checks of the observation layout against the robot state (noise is off, so these should be ~0)
    P = R["prop"]
    chk = {
        "prop_lin_vel_vs_state": float(np.abs(P[..., 0:3] - R["lin_vel_b"]).max()),
        "prop_ang_vel_vs_state": float(np.abs(P[..., 3:6] - R["ang_vel_b"]).max()),
        "prop_gravity_vs_state": float(np.abs(P[..., 6:9] - R["gravity_b"]).max()),
        "prop_joint_pos_rel_vs_state": float(np.abs(P[..., 9:21] - R["joint_pos"]).max()),
        "prop_last_action_vs_clip50_prev_action": float(np.abs(P[..., 33:45] - np.clip(R["a_prev"], -50, 50)).max()),
        "target_q_vs_q0_plus_0p25a": float(np.abs(R["target_q"] - (q0.cpu().numpy()[:, None, :] + 0.25 * R["action"])).max()),
    }
    gx, gy = R["mapping"][0, 0, :, 0, 0], R["mapping"][0, 0, 0, :, 1]
    chk["map_x_const_over_y"] = float(np.abs(R["mapping"][..., 0] - gx[None, None, :, None]).max())
    chk["map_y_const_over_x"] = float(np.abs(R["mapping"][..., 1] - gy[None, None, None, :]).max())

    # save the recording first (the pose test below must not be able to lose it)
    for i, tag in enumerate(("flat", "stairs")):
        np.savez(os.path.join(args.out_dir, f"rec_{tag}.npz"), **{k: v[i] for k, v in R.items()}, meta=json.dumps({"checks": chk}))
    print("REC_SAVED_RAW", flush=True)

    # default-pose test: joints exactly at the default, zero velocity; action 0 -> target = default
    # (inside inference mode: the env buffers became inference tensors in the recording loop)
    with torch.inference_mode():
        env.reset()
        robot.write_joint_state_to_sim(q0, torch.zeros_like(q0))
        rel = ame2_joint_pos_rel(u).clone()
        prop_now = u.observation_manager.compute_group("teacher_prop").clone()
        term.process_actions(torch.zeros(n, 12, device=u.device))
    pose = {
        "joint_pos_rel_max_abs": float(rel.abs().max()),
        "prop_joint_pos_rel_max_abs": float(prop_now[:, 9:21].abs().max()),
        "pass_joint_pos_rel_lt_0p05": bool(rel.abs().max() < 0.05 and prop_now[:, 9:21].abs().max() < 0.05),
        "action0_target_minus_default_max_abs": float((term.processed_actions - q0).abs().max()),
        "default_joint_pos": q0[0].cpu().tolist(),
        "robot_joint_names": list(robot.joint_names),
        "action_term_joint_names": list(term._joint_names),
        "action_scale": float(term.cfg.scale),
        "use_default_offset": bool(term.cfg.use_default_offset),
    }

    meta = {
        "checkpoint": os.path.abspath(args.checkpoint), "checkpoint_sha256": sha256(args.checkpoint), "code_id": code_id(),
        "task": args.task, "hydra_args": hydra_args, "steps": T, "step_dt": float(u.step_dt), "physics_dt": float(u.physics_dt),
        "decimation": int(u.cfg.decimation), "terrain_columns": {"flat": col_flat, "stairs": col_stair},
        "terrain_levels": {"flat": 0, "stairs": args.stair_level}, "map_grid_x": gx.tolist(), "map_grid_y": gy.tolist(),
        "sensor_offset": list(sensor.cfg.offset.pos), "changes_from_training_cfg": [
            "scene.num_envs=2", "rough sub-terrain max_slope_deg=0 max_roughness_m=0 (flat tile)", "curriculum.terrain_levels=None",
            "curriculum.teacher_mapping_noise=None", "teacher_mapping custom_noise=[0,0,0]", "teacher_prop.enable_corruption=False",
            "height_scanner.drift_range=(0,0)"],
        "checks": chk, "default_pose_test": pose,
        "resets_in_recording": {"flat": int(R["done"][0].sum()), "stairs": int(R["done"][1].sum())},
    }
    for i, tag in enumerate(("flat", "stairs")):
        np.savez(os.path.join(args.out_dir, f"rec_{tag}.npz"), **{k: v[i] for k, v in R.items()}, meta=json.dumps(meta))
    with open(os.path.join(args.out_dir, "rec_meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print("REC_CHECKS", json.dumps(chk), flush=True)
    print("REC_POSE", json.dumps({k: v for k, v in pose.items() if "names" not in k}), flush=True)
    print("REC_DONE", args.out_dir, flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
