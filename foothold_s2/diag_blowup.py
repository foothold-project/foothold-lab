"""발산 원인 진단 (lead 10/21): D2-s43 model_1100.pt 에서 같은 설정으로 이어 돌며, 스텝 보상이 -100 아래로 떨어지는 env 의 직전 50 스텝을 저장한다. 종료 없는 진단 모드(발산해도 계속 돈다).

사용: python -m foothold_s2.diag_blowup --task FootholdS2-Go2-S1a-diag-D2-v0 --headless --device cuda:0 --seed 43 --num_envs 4096 --blow_ckpt <model_1100.pt> --blow_iters 60 --blow_out <폴더>
"""

import argparse
import os
import sys
import traceback

import h5py  # noqa: F401
import tensordict  # noqa: F401
import torch
import rsl_rl.runners  # noqa: F401

from isaaclab.app import AppLauncher

ISAACLAB = os.environ.get("ISAACLAB_PATH", "C:/isaac/IsaacLab")
sys.path.insert(0, os.path.join(ISAACLAB, "scripts", "reinforcement_learning", "rsl_rl"))
import cli_args  # noqa: E402  isort: skip

parser = argparse.ArgumentParser(description="S1-a 학습 (S1Runner)")
parser.add_argument("--num_envs", type=int, default=None)
parser.add_argument("--task", type=str, required=True)
parser.add_argument("--agent", type=str, default="rsl_rl_cfg_entry_point")
parser.add_argument("--seed", type=int, default=None)
parser.add_argument("--max_iterations", type=int, default=None)
parser.add_argument("--blow_ckpt", required=True)
parser.add_argument("--blow_iters", type=int, default=60)
parser.add_argument("--blow_out", required=True)
parser.add_argument("--blow_threshold", type=float, default=-100.0)
parser.add_argument("--stage_transfer", action="store_true",
                    help="S1-a -> S1-b: 가중치 · optimizer · iteration · 명령 상한만 옮기고 지형 칸은 새로(열 배치가 다르다). 이 단계의 반복 수는 이어 시작한 회차부터 0")
parser.add_argument("--load_experiment", type=str, default=None, help="이어 받을 체크포인트의 실험 폴더(기본: 이 실행의 experiment_name)")
cli_args.add_rsl_rl_args(parser)
AppLauncher.add_app_launcher_args(parser)
args_cli, hydra_args = parser.parse_known_args()
sys.argv = [sys.argv[0]] + hydra_args
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import importlib.metadata as metadata  # noqa: E402
from datetime import datetime  # noqa: E402

import gymnasium as gym  # noqa: E402
from isaaclab.utils.io import dump_yaml  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402

import isaaclab_tasks  # noqa: E402,F401
from isaaclab_tasks.utils import get_checkpoint_path  # noqa: E402
from isaaclab_tasks.utils.hydra import hydra_task_config  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
import foothold_s2.tasks  # noqa: E402,F401
from foothold_s2.robots import go2_params as gp  # noqa: E402
from foothold_s2.runners.status import write_status  # noqa: E402
from foothold_s2.s1_runner import STAGE_TRANSFER_KEYS, S1Runner  # noqa: E402
from foothold_s2.tasks.robot_mass import log_robot_mass  # noqa: E402

RSL_RL_PIN = "3.1.2"


class StopDiag(Exception):
    pass


def install_recorder(raw, out_dir, threshold, runner, history=50, max_events=3):
    """env.step 을 감싸 매 스텝 항별 보상 · 관절 · 접촉 · 자세 · 명령을 고리 버퍼에 쌓고, 스텝 보상이 임계 아래인 env 가 처음 나오면 그 env 의 직전 `history` 스텝을 저장한다."""
    import json

    robot = raw.scene["robot"]
    sensor = raw.scene["contact_forces"]
    foot_ids, _ = sensor.find_bodies(".*_foot")
    n = raw.num_envs
    dev = raw.device
    terms = list(raw.reward_manager.active_terms)
    width = 1 + len(terms) + 12 * 4 + 4 + 1 + 3 + 3 + 3 + 3 + 12
    ring = torch.zeros(history, n, width, device=dev)
    state = {"k": 0, "events": [], "min_by_step": [], "pre": []}
    cmd_term = raw.command_manager.get_term("base_velocity")
    original_step = raw.step
    os.makedirs(out_dir, exist_ok=True)

    def names():
        out = ["reward"] + ["r_" + t for t in terms]
        out += ["jvel_%d" % i for i in range(12)] + ["torque_%d" % i for i in range(12)] + ["jacc_%d" % i for i in range(12)]
        out += ["jpos_%d" % i for i in range(12)] + ["foot_force_%d" % i for i in range(4)] + ["root_z"]
        out += ["grav_%d" % i for i in range(3)] + ["lin_vel_b_%d" % i for i in range(3)] + ["ang_vel_b_%d" % i for i in range(3)]
        out += ["cmd_%d" % i for i in range(3)] + ["action_%d" % i for i in range(12)]
        return out

    def step(actions):
        result = original_step(actions)
        rew = raw.reward_buf.clone()
        row = torch.cat([rew[:, None], raw.reward_manager._step_reward, robot.data.joint_vel, robot.data.applied_torque, robot.data.joint_acc,
                         robot.data.joint_pos, sensor.data.net_forces_w[:, foot_ids, :].norm(dim=-1), robot.data.root_pos_w[:, 2:3],
                         robot.data.projected_gravity_b, robot.data.root_lin_vel_b, robot.data.root_ang_vel_b, cmd_term.command[:, :3], actions], dim=1)
        ring[state["k"] % history] = row
        state["k"] += 1
        worst, who = rew.min(dim=0)
        state["min_by_step"].append([state["k"], float(worst), int(who), float(robot.data.joint_vel.abs().max()),
                                     float(robot.data.applied_torque.abs().max()), bool(torch.isnan(robot.data.joint_vel).any())])

        if float(worst) < -20.0 and len(state["pre"]) < 40:
            state["pre"].append({"k": state["k"], "reward": float(worst), "env": int(who), "terrain_type": int(raw.scene.terrain.terrain_types[who]),
                                 "level": int(raw.scene.terrain.terrain_levels[who])})

        if float(worst) < threshold:
            idx = int(who)
            order = [(state["k"] - history + i) % history for i in range(history)] if state["k"] >= history else list(range(state["k"]))
            rows = ring[order][:, idx, :].cpu().tolist()
            state["events"].append({"step_k": state["k"], "iteration": int(runner.current_learning_iteration), "env": idx, "reward": float(worst),
                                    "terrain_type": int(raw.scene.terrain.terrain_types[idx]), "terrain_level": int(raw.scene.terrain.terrain_levels[idx]),
                                    "columns": names(), "last_steps": rows})
            print("[DIAG] 사건 %d: iteration %s env %d reward %.1f 지형 열 %d 레벨 %d" % (
                len(state["events"]), runner.current_learning_iteration, idx, float(worst), int(raw.scene.terrain.terrain_types[idx]),
                int(raw.scene.terrain.terrain_levels[idx])), flush=True)

            if len(state["events"]) >= max_events:
                finish("events")
                raise StopDiag()

        return result

    def finish(reason):
        with open(os.path.join(out_dir, "blowup.json"), "w", encoding="utf-8") as handle:
            json.dump({"reason": reason, "threshold": threshold, "events": state["events"], "pre_events_below_-20": state["pre"],
                       "min_reward_by_step_tail": state["min_by_step"][-3000:], "terms": terms}, handle)

    raw.step = step

    return {"finish": finish}


@hydra_task_config(args_cli.task, args_cli.agent)
def main(env_cfg, agent_cfg):
    installed = metadata.version("rsl-rl-lib")

    if installed != RSL_RL_PIN:
        raise RuntimeError(f"rsl-rl-lib {installed} 은 계약 {RSL_RL_PIN} 이 아니다 (환경: {sys.prefix})")

    agent_cfg = cli_args.update_rsl_rl_cfg(agent_cfg, args_cli)
    env_cfg.scene.num_envs = args_cli.num_envs if args_cli.num_envs is not None else env_cfg.scene.num_envs
    total = args_cli.max_iterations if args_cli.max_iterations is not None else agent_cfg.max_iterations
    env_cfg.seed = agent_cfg.seed
    env_cfg.sim.device = args_cli.device if args_cli.device is not None else env_cfg.sim.device

    log_root = os.path.abspath(os.path.join("logs", "rsl_rl", agent_cfg.experiment_name))
    log_dir = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    if agent_cfg.run_name:
        log_dir += f"_{agent_cfg.run_name}"

    log_dir = os.path.join(log_root, log_dir)
    env_cfg.log_dir = log_dir
    os.environ["TRAIN_START_STATUS_DIR"] = log_dir
    write_status(log_dir, {"state": "starting", "log_dir": log_dir, "task": args_cli.task})

    load_root = os.path.abspath(os.path.join("logs", "rsl_rl", args_cli.load_experiment)) if args_cli.load_experiment else log_root
    resume_path = get_checkpoint_path(load_root, agent_cfg.load_run, agent_cfg.load_checkpoint) if agent_cfg.resume else None
    env = gym.make(args_cli.task, cfg=env_cfg)
    log_robot_mass(env, "S1 train " + args_cli.task)
    print("[종료 조건] fbg_margin %s m (foot_below_ground)" % gp.TERMINATION["foot_below_ground_m"], flush=True)
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)
    train_cfg = agent_cfg.to_dict()
    runner = S1Runner(env, train_cfg, log_dir=log_dir, device=agent_cfg.device)
    runner.add_git_repo_to_log(__file__)

    resume_path = args_cli.blow_ckpt
    print(f"[INFO] 진단: 체크포인트 {resume_path} 에서 이어 감", flush=True)
    runner.load(resume_path)
    recorder = install_recorder(env.unwrapped, args_cli.blow_out, args_cli.blow_threshold, runner)

    dump_yaml(os.path.join(log_dir, "params", "env.yaml"), env_cfg)
    dump_yaml(os.path.join(log_dir, "params", "agent.yaml"), agent_cfg)
    start = runner.current_learning_iteration + (1 if resume_path else 0)
    remaining = args_cli.blow_iters
    print(f"[INFO] 목표 {total} 회, 시작 {start}, 남은 {remaining}", flush=True)
    try:
        runner.learn(num_learning_iterations=remaining, init_at_random_ep_len=True)
    except StopDiag:
        print("[DIAG] 사건 수집 끝, 중단", flush=True)
    except BaseException:
        recorder["finish"]("exception")
        raise

    recorder["finish"]("done")


if __name__ == "__main__":
    # rl 의 train_start.py 와 같은 규칙: 결과를 기록한 뒤 env.close()/app.close() 를 부르지 않고 os._exit (close 가 멈춘 적 있음).
    torch.backends.cudnn.deterministic = False
    code = 0

    try:
        main()
    except SystemExit as e:
        code = 0 if e.code in (None, 0) else 1
    except BaseException:
        write_status(os.environ.get("TRAIN_START_STATUS_DIR"), {"state": "failed", "traceback": traceback.format_exc()})
        code = 1

    sys.stdout.flush()
    os._exit(code)
