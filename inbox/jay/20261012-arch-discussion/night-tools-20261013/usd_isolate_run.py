# 실행마다 따로인 USD 변환 폴더로 Isaac 스크립트를 돌린다 v2 (lead · 2026-10-13 저녁 · ASTRA 17b §2.2 · §3 「변환 전에 attempt 별 실제
# 절대 USD 경로를 할당 · 기록」).
# 원리: Isaac Lab AssetConverterBase.__init__ 은 cfg.usd_dir 이 없으면 /tmp/IsaacLab/usd_<날짜>_<시각>_<random.randrange(10000)> 를
#   만든다 (asset_converter_base.py:66~70). 이 실행기는 그 모듈이 올라온 뒤 __init__ 을 감싸, usd_dir 이 없을 때
#   원래와 똑같이 random.randrange(10000) 를 한 번 부른 뒤 (Python random 소비를 원래와 같게 유지) 폴더를
#   <FOOTHOLD_USD_ROOT>/IsaacLab/usd_<날짜>_<시각>_<값> 으로 정한다. 「IsaacLab」 하위 이름을 지켜 기존 로그 정규식과도 맞는다.
#   정한 경로는 변환 전에 <FOOTHOLD_USD_ROOT>/assigned.jsonl 에 한 줄씩 적는다.
#   변환기 · 학습 · 평가 코드는 고치지 않는다.
# v1 결함 (10/13 18:51 실제 gate 실행 · GPU 0): sys.meta_path 맨 앞에 넣은 finder 가 Isaac (Kit) 안에서는 불리지 않았다.
#   USD 는 공용 /tmp/IsaacLab/usd_20261013_185115_9514 로 갔고 assigned.jsonl 이 없었다 (isaac_slot 이 94 로 막음).
#   CPU 시험은 가짜 패키지를 보통 경로로 import 해서 이 차이를 못 봤다.
# v2: 세 겹으로 감싼다.
#   1. loader: 표준 .py · .pyc 적재가 모두 지나는 importlib 의 _LoaderBasics.exec_module 을 감싸, 어느 finder 가 찾았든
#      대상 모듈 본문이 끝나는 순간 감싼다 (첫 변환 전 틈 없음). 주 경로.
#   2. finder: v1 그대로 (표준 loader 가 아닐 때를 위해).
#   3. audit hook (sys.addaudithook): 위 둘이 다 못 한 경우, 대상 모듈이 올라온 뒤 처음 오는 감사 사건 (import · open 등) 때 감싼다.
#      이 길은 「import 직후 아무 사건 없이 바로 변환」 하면 늦는다 (CPU 시험 U7 v2 초안에서 확인). 그때는 isaac_slot 이 94 로 막는다.
#   어느 길로 감쌌는지 (loader · finder · audit:<사건>) 를 로그 줄 「[USD-ISOLATE] patched via ...」 와 <root>/isolate_state.json 에 남긴다.
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
_STATE = {"patched_by": "", "busy": False}


def _record(path, cfg):
    os.makedirs(ROOT, exist_ok=True)
    with open(os.path.join(ROOT, "assigned.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "pid": os.getpid(), "usd_dir": path,
                            "asset_path": str(getattr(cfg, "asset_path", "")), "cfg_class": type(cfg).__name__,
                            "patched_by": _STATE["patched_by"]}) + "\n")


def patch(mod, how):
    C = getattr(mod, "AssetConverterBase", None)
    if C is None:  # the module is still running its body; a later event will try again
        return False
    if getattr(C, "_foothold_isolated", False):
        return True
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
    _STATE["patched_by"] = how
    os.environ["FOOTHOLD_USD_PATCHED"] = how
    os.makedirs(ROOT, exist_ok=True)
    with open(os.path.join(ROOT, "isolate_state.json"), "w", encoding="utf-8") as f:
        json.dump({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "pid": os.getpid(), "patched_by": how,
                   "meta_path": [type(x).__module__ + "." + type(x).__name__ for x in sys.meta_path]}, f, indent=1)
    print(f"[USD-ISOLATE] patched via {how}", flush=True)
    return True


def _audit(event, args):
    if _STATE["patched_by"] or _STATE["busy"]:
        return
    m = sys.modules.get(TARGET)
    if m is None:
        return
    _STATE["busy"] = True
    try:
        patch(m, f"audit:{event}")
    except Exception as ex:  # noqa: BLE001  never break the host; isaac_slot still checks the folder (94)
        print(f"[USD-ISOLATE] patch failed {type(ex).__name__}: {ex}", flush=True)
    finally:
        _STATE["busy"] = False


def _wrap_loader_class():
    """Every standard .py/.pyc load ends in _LoaderBasics.exec_module whichever finder found the file (Kit's included),
    so the target is patched the moment its body finishes, with no gap before the first conversion."""
    import importlib._bootstrap_external as be
    orig = be._LoaderBasics.exec_module
    if getattr(orig, "_foothold", False):
        return

    def exec_module(self, module):
        orig(self, module)
        if not _STATE["patched_by"] and getattr(module, "__name__", "") == TARGET:
            patch(module, "loader")

    exec_module._foothold = True
    be._LoaderBasics.exec_module = exec_module


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
            if not _STATE["patched_by"]:
                patch(module, "finder")

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
        patch(sys.modules[TARGET], "already_loaded")
    else:
        _wrap_loader_class()
        sys.meta_path.insert(0, _Finder())
        sys.addaudithook(_audit)
    script = os.path.abspath(sys.argv[1])
    sys.argv = [script] + sys.argv[2:]
    sys.path[0] = os.path.dirname(script)
    print(f"[USD-ISOLATE] root {ROOT}", flush=True)
    runpy.run_path(script, run_name="__main__")


if __name__ == "__main__":
    main()
