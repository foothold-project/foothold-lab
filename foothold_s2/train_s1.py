"""S1-a 학습 실행기. 설치 `scripts/reinforcement_learning/rsl_rl/train.py` 를 그대로 돌리되, Kit 이 뜬 뒤 우리 task 를 등록한다.

사용: python -m foothold_s2.train_s1 --task FootholdS2-Go2-S1a-scan-v0 --headless --device cuda:0 --max_iterations 10
Windows Kit 제약(CLAUDE 메모리): AppLauncher 전에 h5py · torch · tensordict · rsl_rl.runners 를 먼저 불러야 한다.
"""

import os
import sys

import h5py  # noqa: F401
import torch  # noqa: F401
import tensordict  # noqa: F401
import rsl_rl.runners  # noqa: F401

ISAACLAB = os.environ.get("ISAACLAB_DIR", "C:/isaac/IsaacLab")
TRAIN = os.path.join(ISAACLAB, "scripts", "reinforcement_learning", "rsl_rl", "train.py")
MARK = "import isaaclab_tasks  # noqa: F401"


def main():
    src = open(TRAIN, encoding="utf-8").read()

    if MARK not in src:
        raise SystemExit(f"설치 train.py 에 표지 줄이 없다: {MARK}")

    src = src.replace(MARK, MARK + "\nimport foothold_s2.tasks  # noqa: F401", 1)
    sys.path.insert(0, os.path.dirname(TRAIN))
    sys.path.insert(0, os.getcwd())
    sys.argv[0] = TRAIN
    exec(compile(src, TRAIN, "exec"), {"__name__": "__main__", "__file__": TRAIN})


if __name__ == "__main__":
    main()
