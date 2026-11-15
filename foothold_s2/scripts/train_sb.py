"""EX-33 S-B 진입점: SOL-23f 공통 학습 실행기에 SB 변형으로 들어간다(B 와 같은 실행기 · 마감 · 영수증)."""

import runpy
import sys
from pathlib import Path


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    sys.argv = [sys.argv[0], "--task", "FootholdS2-Go2-S2-SB-v0", "--variant", "SB", *sys.argv[1:]]
    runpy.run_module("foothold_s2.scripts.train_sol23f_common", run_name="__main__")
