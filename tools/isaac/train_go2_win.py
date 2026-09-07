# Windows 우회: Isaac Sim Kit 로드 전에 "네이티브 확장을 가진" 패키지를 선점 import
# Kit 이 자기 DLL 을 먼저 올리면 뒤늦은 import 가 엔트리포인트 불일치로 죽는다.
#   - tensordict : access violation 0xC0000005
#   - h5py       : entrypoint not found 0xC0000139
import torch                       # noqa
from tensordict import TensorDict  # noqa
import rsl_rl.runners              # noqa
import h5py                        # noqa
import runpy, sys, os
SCRIPT = os.path.join("scripts", "reinforcement_learning", "rsl_rl", "train.py")
sys.path.insert(0, os.path.dirname(os.path.abspath(SCRIPT)))   # cli_args 를 찾게
sys.argv = [SCRIPT] + sys.argv[1:]
runpy.run_path(SCRIPT, run_name="__main__")
