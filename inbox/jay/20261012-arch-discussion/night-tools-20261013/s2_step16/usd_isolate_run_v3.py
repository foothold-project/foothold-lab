# 실행마다 따로인 USD 변환 폴더로 Isaac 스크립트를 돌린다 v3 (lead 세션 · Claude 하위 작업 작성 · 2026-10-13 밤 · ASTRA 17c §3 반영).
# v2 (usd_isolate_run.py) 는 고치지 않고 둔다.
# v2 결함 (17c 재현):
#   - cfg.usd_dir 를 영구로 바꿨다. 같은 cfg 로 변환기를 두 번 만들면 두 번째가 명시 경로 재사용이 되어 경로가 같고 randrange 가 한 번 줄었다
#     (seed 7: 원래 다음 random 0.3948234964231735 · v2 0.9478653606090632). 원래 코드보다 먼저 random 을 뽑아 asset 검사 실패 경로에서도 소비했다.
#   - cfg.usd_dir 가 명시돼 있으면 루트 밖이라도 그대로 쓰고 assigned 에 남기지 않았다.
#   - 표준이 아닌 loader 로 올라온 뒤 다른 감사 사건 없이 바로 변환하면 감싸기가 늦어 공용 폴더로 갔다 (patched_by=audit:os.mkdir 기록은 첫 경로 선택 뒤).
# v3:
#   1. cfg 를 건드리지 않는다. AssetConverterBase 에 데이터 descriptor 「_usd_dir」 를 얹어, 원래 __init__ 이 기본 분기에서
#      「.../IsaacLab/usd_<날짜>_<시각>_<값>」 을 대입하는 순간 같은 이름으로 <루트>/IsaacLab/usd_<날짜>_<시각>_<값> 로 바꿔 둔다.
#      randrange 는 원래 코드가 원래 자리 (cfg.validate · asset 검사 뒤) 에서 변환마다 한 번씩 부른다. 같은 cfg 두 번이면 두 번 뽑고 두 경로가 다르다.
#      바꾼 경로는 폴더를 만들기 전에 <루트>/assigned.jsonl 에 한 줄 (kind assigned) 로 적는다. 기본 분기 값이 그 모양이 아니면 예외로 멈춘다.
#   2. cfg.usd_dir 명시: 루트 안이면 그대로 쓰고 kind explicit_inside 로 적는다. 루트 밖이면 kind explicit_outside_refused 로 적고 예외로 멈춘다
#      (허용 목록 없음. 미리 변환한 USD 를 읽기 전용으로 쓰려면 변환기를 거치지 말고 USD 를 직접 읽게 한다).
#   3. 감싸기 전 변환 차단: 감사 hook 이 모든 os.mkdir 사건에서 (a) 호출 스택에 asset_converter_base.py 의 __init__ 이 있는데 바로 위 호출자가
#      이 실행기의 감싼 __init__ 이 아니면 (b) 또는 만들려는 폴더가 「IsaacLab/usd_<날짜>_<시각>_<값>」 인데 루트 밖이면, 그 mkdir 을
#      예외 (UsdIsolationError) 로 막는다. 기반 __init__ 의 첫 쓰기는 os.makedirs 이므로 공용 폴더에 아무것도 만들기 전에 멈춘다.
#      막은 일은 isolate_state.json 의 blocked 와 로그 줄 「[USD-ISOLATE] BLOCKED ...」 에 남긴다.
#   4. 감싸는 길은 v2 와 같다: loader (importlib _LoaderBasics.exec_module) · finder · 감사 사건 (늦은 감싸기). 대상 모듈이 다시 올라와
#      새 클래스가 생겨도 그 클래스를 감싼다.
#   5. 지형 cache (terrain_generator.py 의 cache_dir) 는 가로채지 않는다. TerrainGenerator 가 use_cache=True 로 만들어지면 경고만
#      isolate_state.json 의 warnings 와 로그 줄 「[USD-ISOLATE] WARNING ...」 에 남긴다.
#   6. (ASTRA 17d 2.6) 예상 변환 개수 FOOTHOLD_EXPECT_CONVERSIONS = 0 | 1 | any (없으면 any = v2 와 같음). 감싼 __init__ 에 들어오는 순간
#      시도 수를 세어, 0 이면 첫 번째를, 1 이면 두 번째를 random · 폴더 생성 · 변환 전에 예외로 막고 assigned.jsonl 에
#      kind refused_unexpected_conversion 줄 (usd_dir null) 을 남긴다. isaac_slot_v3 가 --expect_conversions 값을 자식에게 넘긴다.
#      감싸지 못한 변환 (3 의 경우) 은 이 셈에 들어오지 않고 3 의 mkdir 차단으로 멈춘다.
# 사용: [FOOTHOLD_EXPECT_CONVERSIONS=0|1|any] FOOTHOLD_USD_ROOT=<실행별 폴더> python usd_isolate_run_v3.py <스크립트.py> <스크립트 인자 ...>
#      (v2 와 같은 꼴)
import importlib.abc
import json
import os
import re
import runpy
import sys
import threading
import time
import uuid

TARGET = "isaaclab.sim.converters.asset_converter_base"
TERRAIN = "isaaclab.terrains.terrain_generator"
BASE_SUFFIX = "isaaclab/sim/converters/asset_converter_base.py"
DEFAULT_RE = re.compile(r"^(?:.*[/\\])?IsaacLab[/\\]+usd_(\d{8}_\d{6}_\d+)$", re.I)
_STATE = {"patched_by": "", "terrain_patched_by": "", "blocked": [], "warnings": [], "patched": [], "wrap_code": None, "conversions": 0, "conversion_successes": 0}
_CTX = {}
_TL = threading.local()  # per-thread re-entry guard for the audit hook
_BASE_CODE = {}


def _busy():
    return getattr(_TL, "busy", False)


class UsdIsolationError(RuntimeError):
    pass


def _canon(p):
    s = str(p).strip().replace("\\", "/")
    if not s:
        return None
    return os.path.normcase(os.path.normpath(os.path.abspath(s))).replace("\\", "/").rstrip("/")


ROOT = _canon(os.environ.get("FOOTHOLD_USD_ROOT", "")) or ""
# ASTRA 17d 2.6: how many converter runs this process may start. 0 = none (the first is refused at entry), 1 = one (the second is
# refused at entry), any = not limited (the default when the variable is absent, as in v2). isaac_slot_v3 sets it for its child.
EXPECT = (os.environ.get("FOOTHOLD_EXPECT_CONVERSIONS", "") or "any").strip().lower()
CAP = int(os.environ.get("FOOTHOLD_CONVERSION_CAP", "0"))


def _under_root(c):
    return bool(ROOT) and c is not None and (c == ROOT or c.startswith(ROOT + "/"))


def _save_state():
    os.makedirs(ROOT, exist_ok=True)
    path = os.path.join(ROOT, "isolate_state.json")
    tmp = f"{path}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "pid": os.getpid(), "version": "v3", "root": ROOT,
                   "expect_conversions": EXPECT, "conversions": _STATE["conversions"],
                   "conversion_successes": _STATE["conversion_successes"], "conversion_cap": CAP,
                   "patched_by": _STATE["patched_by"], "patched": _STATE["patched"], "terrain_patched_by": _STATE["terrain_patched_by"],
                   "blocked": _STATE["blocked"], "warnings": _STATE["warnings"],
                   "meta_path": [type(x).__module__ + "." + type(x).__name__ for x in sys.meta_path]}, f, indent=1)
    os.replace(tmp, path)


def _record(path, cfg, kind, original, extra=None):
    os.makedirs(ROOT, exist_ok=True)
    with open(os.path.join(ROOT, "assigned.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "pid": os.getpid(), "usd_dir": path,
                            "asset_path": str(getattr(cfg, "asset_path", "")), "cfg_class": type(cfg).__name__,
                            "patched_by": _STATE["patched_by"], "kind": kind, "original": original, "version": "v3",
                            "case_arm": os.environ.get("FOOTHOLD_S2_EVAL_CASE_ARM"), **(extra or {})}) + "\n")


def _block(why, path):
    _STATE["blocked"].append({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "why": why, "path": str(path)})
    was = _busy()
    _TL.busy = True
    try:
        _save_state()
        print(f"[USD-ISOLATE] BLOCKED {why}: {path}", flush=True)
    except Exception:  # noqa: BLE001  the block itself must still happen
        pass
    finally:
        _TL.busy = was
    raise UsdIsolationError(f"[USD-ISOLATE] {why}: {path} (attempt root {ROOT})")


def _warn(item):
    _STATE["warnings"].append(dict(item, t=time.strftime("%Y-%m-%d %H:%M:%S")))
    was = _busy()
    _TL.busy = True
    try:
        _save_state()
        print(f"[USD-ISOLATE] WARNING {json.dumps(item, ensure_ascii=False)}", flush=True)
    except Exception:  # noqa: BLE001
        pass
    finally:
        _TL.busy = was


def _get_usd_dir(self):
    try:
        return self.__dict__["_usd_dir"]
    except KeyError:
        raise AttributeError("_usd_dir") from None


def _set_usd_dir(self, value):
    ctx = _CTX.get(id(self))
    m = DEFAULT_RE.match(str(value))
    if ctx is not None and ctx["mode"] == "default" and ctx["path"] is None:
        if not m:
            _block("the converter's default USD folder has an unexpected form; refusing to guess", value)
        new = f"{ROOT}/IsaacLab/usd_{m.group(1)}"
        _record(new, ctx["cfg"], "assigned", str(value), {"n": ctx["n"]})
        ctx["path"] = new
        value = new
    elif ctx is None and m and not _under_root(_canon(value)):
        _block("a default USD folder set outside a wrapped converter __init__", value)
    self.__dict__["_usd_dir"] = value


def _del_usd_dir(self):
    self.__dict__.pop("_usd_dir", None)


def patch(mod, how):
    C = getattr(mod, "AssetConverterBase", None)
    if C is None:  # the module is still running its body; a later event will try again
        return False
    if C.__dict__.get("_foothold_isolated", False):
        return True
    orig_init = C.__init__

    def __init__(self, cfg):
        _STATE["conversions"] += 1
        n = _STATE["conversions"]
        ud = getattr(cfg, "usd_dir", None)
        if CAP and n > CAP:
            _record(None, cfg, "refused_conversion_cap", None if ud is None else str(ud), {"n": n, "cap": CAP})
            _block(f"converter entry {n} exceeds hard cap {CAP}", getattr(cfg, "asset_path", "?"))
        if EXPECT == "0" or (EXPECT == "1" and n > 1):  # 17d 2.6: refused at entry, before the draw, any folder and any conversion
            _record(None, cfg, "refused_unexpected_conversion", None if ud is None else str(ud), {"n": n, "expect": EXPECT})
            _block(f"converter run {n} was not expected (FOOTHOLD_EXPECT_CONVERSIONS={EXPECT})", getattr(cfg, "asset_path", "?"))
        ctx = {"cfg": cfg, "path": None, "mode": "default", "n": n}
        if ud is not None:
            c = _canon(ud)
            if _under_root(c):
                ctx["mode"] = "explicit_inside"
                _record(c, cfg, "explicit_inside", str(ud), {"n": n})
            else:
                _record(c or str(ud), cfg, "explicit_outside_refused", str(ud))
                _block("cfg.usd_dir is outside the attempt root (refused; no allow list)", ud)
        _CTX[id(self)] = ctx
        try:
            orig_init(self, cfg)
            _STATE["conversion_successes"] += 1
            _save_state()
        finally:
            _CTX.pop(id(self), None)
        if ctx["mode"] == "default" and ctx["path"] is None:
            _block("the converter finished without the default USD folder being redirected", self.__dict__.get("_usd_dir", "?"))

    C.__init__ = __init__
    C._usd_dir = property(_get_usd_dir, _set_usd_dir, _del_usd_dir)
    C._foothold_isolated = True
    _STATE["wrap_code"] = __init__.__code__
    _STATE["patched"].append(how)
    if not _STATE["patched_by"]:
        _STATE["patched_by"] = how
    os.environ["FOOTHOLD_USD_PATCHED"] = _STATE["patched_by"]
    was = _busy()
    _TL.busy = True
    try:
        _save_state()
    finally:
        _TL.busy = was
    print(f"[USD-ISOLATE] patched via {how}", flush=True)
    return True


def patch_terrain(mod, how):
    G = getattr(mod, "TerrainGenerator", None)
    if G is None:
        return False
    if G.__dict__.get("_foothold_cache_watch", False):
        return True
    orig = G.__init__

    def __init__(self, cfg, *args, **kwargs):
        try:
            if getattr(cfg, "use_cache", False):
                cd = str(getattr(cfg, "cache_dir", ""))
                _warn({"what": "terrain cache in use; this launcher does not isolate it", "cache_dir": cd,
                       "cache_dir_under_root": _under_root(_canon(cd)), "seed": getattr(cfg, "seed", None)})
        except Exception:  # noqa: BLE001  a warning must never break terrain generation
            pass
        return orig(self, cfg, *args, **kwargs)

    G.__init__ = __init__
    G._foothold_cache_watch = True
    if not _STATE["terrain_patched_by"]:
        _STATE["terrain_patched_by"] = how
    return True


def _is_base_init(code):
    r = _BASE_CODE.get(code)
    if r is None:
        r = code.co_name == "__init__" and code.co_filename.replace("\\", "/").lower().endswith(BASE_SUFFIX)
        _BASE_CODE[code] = r
    return r


def _check_mkdir(path):
    f = sys._getframe(1)
    while f is not None:
        if _is_base_init(f.f_code):
            if f.f_back is None or f.f_back.f_code is not _STATE["wrap_code"]:
                _block("AssetConverterBase.__init__ ran without the isolation wrapper (loaded before it could be wrapped)", path)
            break
        f = f.f_back
    s = str(path)
    if "usd_" in s.lower() and DEFAULT_RE.match(s) and not _under_root(_canon(s)):
        _block("a USD conversion folder outside the attempt root", path)


def _late_patch(event):
    m = sys.modules.get(TARGET)
    if m is not None and not _STATE["patched_by"]:
        patch(m, f"audit:{event}")
    t = sys.modules.get(TERRAIN)
    if t is not None and not _STATE["terrain_patched_by"]:
        patch_terrain(t, f"audit:{event}")


def _audit(event, args):
    if _busy():
        return
    _TL.busy = True
    try:
        if not (_STATE["patched_by"] and _STATE["terrain_patched_by"]):
            try:
                _late_patch(event)
            except Exception as ex:  # noqa: BLE001  never break the host on a patch attempt
                print(f"[USD-ISOLATE] patch failed {type(ex).__name__}: {ex}", flush=True)
        if event == "os.mkdir":
            _check_mkdir(args[0])
    finally:
        _TL.busy = False


def _wrap_loader_class():
    """Every standard .py/.pyc load ends in _LoaderBasics.exec_module whichever finder found the file (Kit's included)."""
    import importlib._bootstrap_external as be
    orig = be._LoaderBasics.exec_module
    if getattr(orig, "_foothold", False):
        return

    def exec_module(self, module):
        orig(self, module)
        name = getattr(module, "__name__", "")
        if name == TARGET:
            patch(module, "loader")
        elif name == TERRAIN:
            patch_terrain(module, "loader")

    exec_module._foothold = True
    be._LoaderBasics.exec_module = exec_module


class _Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name not in (TARGET, TERRAIN):
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
            if name == TARGET:
                patch(module, "finder")
            else:
                patch_terrain(module, "finder")

        spec.loader.exec_module = exec_module
        return spec


def main():
    if not ROOT:
        print("STOP: FOOTHOLD_USD_ROOT 가 없다", flush=True)
        sys.exit(2)
    if EXPECT not in ("0", "1", "any"):
        print(f"STOP: FOOTHOLD_EXPECT_CONVERSIONS={EXPECT!r} 는 0 · 1 · any 가 아니다", flush=True)
        sys.exit(2)
    if len(sys.argv) < 2:
        print("STOP: 스크립트가 없다", flush=True)
        sys.exit(2)
    if TARGET in sys.modules:
        patch(sys.modules[TARGET], "already_loaded")
    if TERRAIN in sys.modules:
        patch_terrain(sys.modules[TERRAIN], "already_loaded")
    _wrap_loader_class()
    sys.meta_path.insert(0, _Finder())
    sys.addaudithook(_audit)
    script = os.path.abspath(sys.argv[1])
    sys.argv = [script] + sys.argv[2:]
    sys.path[0] = os.path.dirname(script)
    print(f"[USD-ISOLATE] root {ROOT} (v3) expect_conversions {EXPECT}", flush=True)
    runpy.run_path(script, run_name="__main__")


if __name__ == "__main__":
    main()
