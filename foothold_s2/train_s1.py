"""S1-a 학습 실행기 (isaac311 · rsl-rl-lib 3.1.2). 설치 `scripts/reinforcement_learning/rsl_rl/train.py` 의 흐름 + S1Runner.

사용: python -m foothold_s2.train_s1 --task FootholdS2-Go2-S1a-scan-v0 --headless --device cuda:0 --max_iterations 6000
이어 학습: 끝에 --resume --load_run <폴더> --checkpoint latest.pt  (max_iterations 는 «전체 목표 회차» 로 읽고 남은 회차만 돈다)
Windows Kit 제약: AppLauncher 전에 h5py · torch · tensordict · rsl_rl.runners 를 먼저 불러야 한다.
판정은 종료 코드가 아니라 로그 디렉터리의 `train_start_status.json` 과 run.log 로 한다 (Isaac 은 예외 뒤에도 0 을 낸다).
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
    print("[action 클립] clip_actions %s" % agent_cfg.clip_actions, flush=True)
    print("[종료 조건] fbg_margin %s m (foot_below_ground)" % gp.TERMINATION["foot_below_ground_m"], flush=True)
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)
    train_cfg = agent_cfg.to_dict()
    runner = S1Runner(env, train_cfg, log_dir=log_dir, device=agent_cfg.device)
    runner.add_git_repo_to_log(__file__)

    if resume_path:
        print(f"[INFO] S1 체크포인트에서 이어 감: {resume_path}", flush=True)
        runner.load(resume_path, env_keys=STAGE_TRANSFER_KEYS if args_cli.stage_transfer else None)

        if args_cli.stage_transfer:                      # p_advance 의 T 를 이 단계의 반복 수(0 부터)로 센다
            env.unwrapped.stage_iteration_offset = runner.current_learning_iteration + 1
            print("[INFO] 단계 전이: stage_iteration_offset =", env.unwrapped.stage_iteration_offset, flush=True)
            rc = runner._command_term().range_curriculum                 # 평가 기록 카드용: 이어 받은 명령 상한 값 (lead 요청)
            print("[S1b 시작 명령 상한] vmax_x=%s vmax_y=%s flag_vmax=%s 이어 받은 회차=%s" % (rc.vmax_x, rc.vmax_y, rc.flag_vmax,
                                                                                runner.current_learning_iteration), flush=True)

    dump_yaml(os.path.join(log_dir, "params", "env.yaml"), env_cfg)
    dump_yaml(os.path.join(log_dir, "params", "agent.yaml"), agent_cfg)
    start = runner.current_learning_iteration + (1 if resume_path else 0)
    remaining = max(0, total - start)
    print(f"[INFO] 목표 {total} 회, 시작 {start}, 남은 {remaining}", flush=True)
    runner.learn(num_learning_iterations=remaining, init_at_random_ep_len=True)


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
