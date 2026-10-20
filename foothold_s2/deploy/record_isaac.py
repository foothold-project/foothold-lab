"""Isaac 쪽 «정답» 기록 (Kit 에서 한 번 돌린다). 정책 노드의 관측 조립 · 순열 시험이 이것과 1e-5 로 맞아야 한다.

산출: testdata/s1blind_record.npz (step 마다 관측 495 와 그 재료), params/deploy.yaml, exported/policy.onnx(+ 원본 출력 기록).
사용: python -m foothold_s2.deploy.record_isaac --headless --device cuda:1 --checkpoint <model.pt> --out foothold_s2/deploy
"""

import argparse
import os
import sys

import tensordict  # noqa: F401
import torch

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--checkpoint", required=True)
parser.add_argument("--out", required=True)
parser.add_argument("--steps", type=int, default=60)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app

import numpy as np  # noqa: E402
import yaml  # noqa: E402
from isaaclab.envs import ManagerBasedRLEnv  # noqa: E402

from foothold_s2.deploy import sdk_joints  # noqa: E402
from foothold_s2.tasks.s1_env_cfg import FootholdS1aBlindEnvCfg  # noqa: E402


def main():
    cfg = FootholdS1aBlindEnvCfg()
    cfg.scene.num_envs = 8
    cfg.sim.device = args.device
    cfg.observations.policy.enable_corruption = False
    cfg.actions.joint_pos.max_delay_s = 0.0
    env = ManagerBasedRLEnv(cfg)
    asset = env.scene["robot"]
    term = env.command_manager.get_term("base_velocity")
    names = list(asset.data.joint_names)
    rec = {k: [] for k in ("obs", "q", "dq", "quat", "ang_vel_b", "cmd", "last_action", "fresh")}

    def record(obs_policy, fresh):
        rec["obs"].append(obs_policy.cpu().numpy())
        rec["q"].append(asset.data.joint_pos.cpu().numpy())
        rec["dq"].append(asset.data.joint_vel.cpu().numpy())
        rec["quat"].append(asset.data.root_quat_w.cpu().numpy())
        rec["ang_vel_b"].append(asset.data.root_ang_vel_b.cpu().numpy())
        rec["cmd"].append(term.command.cpu().numpy())
        rec["last_action"].append(env.action_manager.action.cpu().numpy())
        rec["fresh"].append(fresh.cpu().numpy())

    obs, _ = env.reset()
    record(obs["policy"], torch.ones(env.num_envs, dtype=torch.bool, device=env.device))      # 리셋 직후 (이력은 이 값으로 채워짐)
    gen = torch.Generator(device=env.device).manual_seed(3)

    for _ in range(args.steps):
        act = 0.3 * torch.randn(env.num_envs, 12, device=env.device, generator=gen)
        obs, _, _, _, _ = env.step(act)
        record(obs["policy"], env.episode_length_buf <= 0)       # 중간에 리셋된 env 는 이력이 새 값으로 채워진다

    out = {k: np.stack(v) for k, v in rec.items()}
    out["joint_names"] = np.array(names)
    out["default_joint_pos"] = asset.data.default_joint_pos[0].cpu().numpy()
    os.makedirs(os.path.join(args.out, "testdata"), exist_ok=True)
    np.savez_compressed(os.path.join(args.out, "testdata", "s1blind_record.npz"), **out)

    # deploy.yaml (공식 export_deploy_cfg 와 같은 칸 이름)
    sdk = sdk_joints.SDK_JOINT_NAMES
    joint_ids_map = [names.index(n) for n in sdk]
    stiffness = np.zeros(12)
    damping = np.zeros(12)
    stiffness[joint_ids_map] = asset.data.default_joint_stiffness[0].cpu().numpy()
    damping[joint_ids_map] = asset.data.default_joint_damping[0].cpu().numpy()
    deploy = {
        "joint_names_isaac": names, "joint_names_sdk": list(sdk), "joint_ids_map": joint_ids_map,
        "step_dt": float(env.step_dt), "stiffness": stiffness.tolist(), "damping": damping.tolist(),
        "default_joint_pos": asset.data.default_joint_pos[0].cpu().numpy().tolist(),
        "actions": {"JointPositionAction": {"scale": 0.25, "offset": asset.data.default_joint_pos[0].cpu().numpy().tolist()}},
        "observations": {"policy": {"history_length": 11, "terms": ["base_ang_vel", "projected_gravity", "velocity_commands",
                                                                  "joint_pos_rel", "joint_vel_rel", "last_action"],
                                     "flatten": "per_term", "history_order": "oldest_first"}},
        "commands": {"base_velocity": {"ranges": {"lin_vel_x": [-1.5, 1.5], "lin_vel_y": [-1.0, 1.0], "ang_vel_z": [-2.0, 2.0]}}},
    }
    os.makedirs(os.path.join(args.out, "params"), exist_ok=True)
    with open(os.path.join(args.out, "params", "deploy.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(deploy, f, allow_unicode=True, sort_keys=False)

    print("[RECORD] joint order (isaac):", names)
    print("[RECORD] obs shape", out["obs"].shape, "fresh steps", int(out["fresh"].sum()))
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
