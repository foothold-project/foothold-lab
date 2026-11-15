"""SOL-23f B 전용 진입점. EX23 대조는 기존 실행 자료를 사용한다."""

import runpy
import sys
from pathlib import Path


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    sys.argv = [sys.argv[0], "--task", "FootholdS2-Go2-S2-23f-B-v0", "--variant", "B", *sys.argv[1:]]
    runpy.run_module("foothold_s2.scripts.train_sol23f_common", run_name="__main__")
