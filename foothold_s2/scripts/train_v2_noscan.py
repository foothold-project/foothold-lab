"""EX-24 학습 진입점 (SONNET-X23): v2 를 돌린 그 학습 스크립트(Isaac Lab scripts/reinforcement_learning/rsl_rl/train.py, 표준 rsl_rl OnPolicyRunner)를 그대로 실행한다.

설치본 train.py 는 한 글자도 고치지 않고 runpy 로 실행하고, 그 전에 우리 task(FootholdS2-Go2-S2-X24-v0)만 gym 에 등록한다(foothold_s2.x24_tasks 는 gymnasium 만 import 하므로
Kit 이 뜨기 전에 불러도 안전하다). Windows Kit 제약(10/20 실측): AppLauncher 전에 h5py · torch · tensordict · rsl_rl.runners 를 먼저 불러야 한다.

    python foothold_s2/scripts/train_v2_noscan.py --task FootholdS2-Go2-S2-X24-v0 --headless --device cuda:N --num_envs 4096 --seed 42 --max_iterations 1501 --run_name ex24-v2-noscan agent.device=cuda:N
"""

import os
import runpy
import sys

import h5py  # noqa: F401
import tensordict  # noqa: F401
import torch  # noqa: F401
import rsl_rl.runners  # noqa: F401

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import foothold_s2.x24_tasks  # noqa: E402,F401

TRAIN = os.path.join(os.environ.get("ISAACLAB_PATH", "C:/isaac/IsaacLab"), "scripts", "reinforcement_learning", "rsl_rl", "train.py")

if __name__ == "__main__":
    runpy.run_path(TRAIN, run_name="__main__")
