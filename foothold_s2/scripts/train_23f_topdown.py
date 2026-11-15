"""SOL-23f START-TopDown 전용 진입점. 논문 유래와 우리 선택은 보고서에 분리한다."""

import runpy
import sys
from pathlib import Path


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    sys.argv = [sys.argv[0], "--task", "FootholdS2-Go2-S2-23f-TopDown-v0", "--variant", "TopDown", *sys.argv[1:]]
    runpy.run_module("foothold_s2.scripts.train_sol23f_common", run_name="__main__")
