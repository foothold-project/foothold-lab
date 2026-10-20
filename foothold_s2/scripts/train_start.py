"""START 전용 학습 진입점 (12 §8 · 13 §6 · 18 §5.1).

설치 Isaac Lab `scripts/reinforcement_learning/rsl_rl/train.py` 는 198~203 행에서 OnPolicyRunner · DistillationRunner 말고는
거부한다. 그래서 그 파일의 흐름(앱 실행 · hydra cfg · per-process --num_envs(119 행) · rank 별 device · seed(137~143 행))을
옮기고 runner 만 StartRunner 로 바꾼다. task 등록(`FootholdS2-Go2-S2-v0`)은 lead 의 tasks 쪽이 한다.

실행 예(실행하지 않음 · Linux 두 장):
    python -m torch.distributed.run --nnodes=1 --nproc_per_node=2 foothold_s2/scripts/train_start.py \
        --task=FootholdS2-Go2-S2-v0 --num_envs=1536 --headless --distributed
"""

from __future__ import annotations

import argparse
import os
import sys

# tensordict 의 C 확장은 Kit 이 뜬 뒤 처음 불러오면 이 기기에서 access violation 으로 죽는다(10/20 start_gate 실측 두 번).
import tensordict  # noqa: F401,E402
import torch  # noqa: E402

from isaaclab.app import AppLauncher  # noqa: E402

ISAAC_RSL = os.path.join(os.environ.get("ISAACLAB_PATH", "C:/isaac/IsaacLab"), "scripts", "reinforcement_learning", "rsl_rl")
sys.path.insert(0, ISAAC_RSL)
import cli_args  # noqa: E402  isort: skip

parser = argparse.ArgumentParser(description="START 학습 (StartRunner)")
parser.add_argument("--num_envs", type=int, default=None)
parser.add_argument("--task", type=str, required=True)
parser.add_argument("--agent", type=str, default="rsl_rl_cfg_entry_point")
parser.add_argument("--seed", type=int, default=None)
parser.add_argument("--max_iterations", type=int, default=None)
parser.add_argument("--distributed", action="store_true", default=False)
parser.add_argument("--map_input", type=str, default=None, help="reconstruction(G1 · G3) · none(G0)")
parser.add_argument("--force_gt", action="store_true", default=False, help="G0-gt")
cli_args.add_rsl_rl_args(parser)
AppLauncher.add_app_launcher_args(parser)
args_cli, hydra_args = parser.parse_known_args()
sys.argv = [sys.argv[0]] + hydra_args
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import importlib.metadata as metadata  # noqa: E402
import json  # noqa: E402
import traceback  # noqa: E402
from datetime import datetime  # noqa: E402

import gymnasium as gym  # noqa: E402
from isaaclab.utils.io import dump_yaml  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402

import isaaclab_tasks  # noqa: E402,F401
from isaaclab_tasks.utils import get_checkpoint_path  # noqa: E402
from isaaclab_tasks.utils.hydra import hydra_task_config  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
import foothold_s2.tasks  # noqa: E402,F401  (lead 의 gym 등록)
from foothold_s2.runners.start_runner import StartRunner  # noqa: E402

RSL_RL_PIN = "3.1.2"  # Isaac Lab setup.py 49 행 · 18 §5.1: 환경 이름 없이 버전을 추정하지 않는다


@hydra_task_config(args_cli.task, args_cli.agent)
def main(env_cfg, agent_cfg):
    installed = metadata.version("rsl-rl-lib")
    if installed != RSL_RL_PIN:
        raise RuntimeError(f"rsl-rl-lib {installed} 은 계약 {RSL_RL_PIN} 이 아니다 (환경: {sys.prefix})")
    agent_cfg = cli_args.update_rsl_rl_cfg(agent_cfg, args_cli)
    env_cfg.scene.num_envs = args_cli.num_envs if args_cli.num_envs is not None else env_cfg.scene.num_envs  # per-process
    agent_cfg.max_iterations = args_cli.max_iterations if args_cli.max_iterations is not None else agent_cfg.max_iterations
    env_cfg.seed = agent_cfg.seed
    env_cfg.sim.device = args_cli.device if args_cli.device is not None else env_cfg.sim.device
    if args_cli.distributed:
        env_cfg.sim.device = f"cuda:{app_launcher.local_rank}"
        agent_cfg.device = f"cuda:{app_launcher.local_rank}"
        seed = agent_cfg.seed + app_launcher.local_rank
        env_cfg.seed = seed
        agent_cfg.seed = seed

    log_root = os.path.abspath(os.path.join("logs", "rsl_rl", agent_cfg.experiment_name))
    log_dir = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if agent_cfg.run_name:
        log_dir += f"_{agent_cfg.run_name}"
    log_dir = os.path.join(log_root, log_dir)
    env_cfg.log_dir = log_dir

    env = gym.make(args_cli.task, cfg=env_cfg)
    resume_path = get_checkpoint_path(log_root, agent_cfg.load_run, agent_cfg.load_checkpoint) if agent_cfg.resume else None
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

    train_cfg = agent_cfg.to_dict()
    pc = dict(train_cfg.get("perception", {}) or {})
    if args_cli.map_input:
        pc["map_input"] = args_cli.map_input
    if args_cli.force_gt:
        pc["force_gt"] = True
    train_cfg["perception"] = pc
    runner = StartRunner(env, train_cfg, log_dir=log_dir, device=agent_cfg.device)
    runner.add_git_repo_to_log(__file__)
    if resume_path:
        print(f"[INFO] START 체크포인트에서 이어 감: {resume_path}")
        runner.load(resume_path)
    dump_yaml(os.path.join(log_dir, "params", "env.yaml"), env_cfg)
    dump_yaml(os.path.join(log_dir, "params", "agent.yaml"), train_cfg)
    runner.learn(num_learning_iterations=agent_cfg.max_iterations, init_at_random_ep_len=True)
    write_status(log_dir, {"done": True, "iter": runner.current_learning_iteration, "log_dir": log_dir})


def write_status(log_dir: str | None, payload: dict) -> None:
    """끝남 · 실패를 파일로 남긴다. 실행 규칙: 판정은 이 파일과 로그로 하고 종료 코드만 믿지 않는다."""
    path = os.path.join(log_dir or ".", "train_start_status.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload["time"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("TRAIN_START_STATUS", json.dumps(payload, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    # 실행 규칙 (10/20 start_gate 실측: app.close() 가 결과 기록 뒤 멈춘다):
    # 체크포인트 · 상태 파일을 쓴 뒤 env.close() · app.close() 를 부르지 않고 os._exit 로 끝낸다.
    # 예외면 traceback 을 상태 파일에 쓰고 코드 1 로 끝낸다(Isaac 은 예외 뒤에도 0 을 낼 수 있다).
    torch.backends.cudnn.deterministic = False
    code = 0
    try:
        main()
    except SystemExit as e:  # hydra 가 정상 끝에 SystemExit(0) 을 낼 수 있다
        code = 0 if e.code in (None, 0) else 1
    except BaseException:
        write_status(os.environ.get("TRAIN_START_STATUS_DIR"), {"done": False, "traceback": traceback.format_exc()})
        code = 1
    sys.stdout.flush()
    os._exit(code)
