# 실행마다 따로인 USD 변환 폴더로 Isaac 스크립트를 돌린다 (lead · 2026-10-13 저녁 · ASTRA 17b §2.2 · §3 「변환 전에 attempt 별 실제
# 절대 USD 경로를 할당 · 기록」).
# 원리: Isaac Lab AssetConverterBase.__init__ 은 cfg.usd_dir 이 없으면 /tmp/IsaacLab/usd_<날짜>_<시각>_<random.randrange(10000)> 를
#   만든다 (asset_converter_base.py:66~70). 이 실행기는 그 모듈이 import 되는 순간 __init__ 을 감싸, usd_dir 이 없을 때
#   원래와 똑같이 random.randrange(10000) 를 한 번 부른 뒤 (Python random 소비를 원래와 같게 유지) 폴더를
#   <FOOTHOLD_USD_ROOT>/IsaacLab/usd_<날짜>_<시각>_<값> 으로 정한다. 「IsaacLab」 하위 이름을 지켜 기존 로그 정규식과도 맞는다.
#   정한 경로는 변환 전에 <FOOTHOLD_USD_ROOT>/assigned.jsonl 에 한 줄씩 적는다.
#   변환기 · 학습 · 평가 코드는 고치지 않는다.
# 사용: FOOTHOLD_USD_ROOT=<실행별 폴더> python usd_isolate_run.py <스크립트.py> <스크립트 인자 ...>
import importlib.abc
import json
import os
import random
import runpy
import sys
import time
from datetime import datetime

TARGET = "isaaclab.sim.converters.asset_converter_base"
ROOT = os.environ.get("FOOTHOLD_USD_ROOT", "")


def _record(path, cfg):
    os.makedirs(ROOT, exist_ok=True)
    with open(os.path.join(ROOT, "assigned.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "pid": os.getpid(), "usd_dir": path,
                            "asset_path": str(getattr(cfg, "asset_path", "")), "cfg_class": type(cfg).__name__}) + "\n")


def patch(mod):
    C = mod.AssetConverterBase
    if getattr(C, "_foothold_isolated", False):
        return
    orig_init = C.__init__

    def __init__(self, cfg):
        if getattr(cfg, "usd_dir", None) is None:
            tag = datetime.now().strftime("%Y%m%d_%H%M%S")
            r = random.randrange(10000)  # the original's single draw, kept so later Python random use is unchanged
            cfg.usd_dir = os.path.join(ROOT, "IsaacLab", f"usd_{tag}_{r}").replace("\\", "/")
            _record(cfg.usd_dir, cfg)
        orig_init(self, cfg)

    C.__init__ = __init__
    C._foothold_isolated = True
    os.environ["FOOTHOLD_USD_PATCHED"] = "1"


class _Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name != TARGET:
            return None
        for f in sys.meta_path:
            if f is self or not hasattr(f, "find_spec"):
                continue
            spec = f.find_spec(name, path, target)
            if spec is not None:
                break
        else:
            return None
        orig = spec.loader.exec_module

        def exec_module(module):
            orig(module)
            patch(module)

        spec.loader.exec_module = exec_module
        return spec


def main():
    if not ROOT:
        print("STOP: FOOTHOLD_USD_ROOT 가 없다", flush=True)
        sys.exit(2)
    if len(sys.argv) < 2:
        print("STOP: 스크립트가 없다", flush=True)
        sys.exit(2)
    if TARGET in sys.modules:
        patch(sys.modules[TARGET])
    else:
        sys.meta_path.insert(0, _Finder())
    script = os.path.abspath(sys.argv[1])
    sys.argv = [script] + sys.argv[2:]
    sys.path[0] = os.path.dirname(script)
    print(f"[USD-ISOLATE] root {ROOT}", flush=True)
    runpy.run_path(script, run_name="__main__")


if __name__ == "__main__":
    main()
