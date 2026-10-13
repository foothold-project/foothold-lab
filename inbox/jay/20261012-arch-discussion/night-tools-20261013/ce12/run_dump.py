# -*- coding: utf-8 -*-
"""CE12 1 단계 native 기록기 실행기 v2 (lead 가 띄운다 · 이 파일 자체는 GPU 를 쓰지 않고 자식을 띄울 뿐이다).

분류: A/평가 · CE12-v1 이식 진단 1 · 실행기
작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 19:03 · v2 20:10 (ASTRA 17d §2.5 · §2.6 · lead 지시 20:06)
근거: VERIFY-astra-17d.md §2.5 · §2.6 · §3 · §7 · _eval/isaac_slot_v3.py · _eval/usd_isolate_run_v3.py (읽기만) · cells.py
요지: cts 와 v2 모두 isaac_slot v3 -> gpu_guard -> usd_isolate_run v3 -> 기록기. 변환 예상 개수를 cts 1 · v2 0 으로 명시한다.
      기록기 추가 인자는 허용 목록으로만 받고 (등호형 · 축약 · 중복 · 금지 옵션 거절), 끝나면 출력 위치를 직접 확인한다.
상태: 가짜 자식으로만 시험 (test_run_dump.py). 실제 Isaac 실행 0 회

v1 (19:03) 에서 바꾼 것 (ASTRA 17d)
  §2.5 추가 인자가 정확히 「--outdir」 일 때만 거절해서 「--outdir=...」 로 실행기가 정한 출력을 덮을 수 있었다 (rc 0 · 다른 곳에 npz).
       이제 기록기마다 허용 목록 (ALLOWED) 만 받는다. 이름은 정확히 같아야 하고 (argparse 축약 거절), 한 번만, 값은 형식 검사.
       --allow_cfg_diff · --outdir · --tag · --checkpoint · --env_yaml · --device 등 실행기 소유 · 정식 자료 금지 옵션은 어떤 표기로도 거절.
       cells · envs_per_cell · steps 는 늘 명시해서 넘긴다 (요청이 run.json 에 다 남아 validate_dump 가 자료와 대조한다).
       자식이 0 으로 끝나도 <native>/<tag>/ 에 native.npz · meta.json · signature.json 이 있고 meta 의 outdir · tag · checkpoint 가
       실행기가 정한 값과 같아야 한다. 아니면 88 (slot v3 의 89 「변환 예상 위반」 과 겹치지 않게).
  §2.6 v2 를 slot 없이 띄우고 끝난 뒤 assigned.jsonl 을 보던 방식은 버린다 (사후 검사는 공유 쓰기를 막지 못한다).
       v2 도 slot v3 를 거치고, 변환 예상 0 개를 --expect_conversions 0 (slot v3 CLI · 23:30 원본 확인) 과 환경 변수
       FOOTHOLD_EXPECT_CONVERSIONS=0 으로 넘긴다 (slot v3 이 자식 환경에 다시 넣고 usd_isolate_run_v3 가 변환기 진입 즉시 막는다). cts 는 1.
       그 기능이 slot v3 · usd_isolate_run v3 원본에 안 보이면 (이름 검사) v2 는 띄우지 않는다 (종료 2).
       cts 는 예상 1 이 v3 의 기본 규칙 (폴더 정확히 하나) 과 같아서 기능이 없어도 띄운다 (run.json capabilities 에 남김).
  이름: 관문 파일은 아래 SLOT · ISOLATE 상수 하나씩이다. 다른 하위 작업이 이름을 바꾸면 여기만 고친다.

출력 배치 (기본 _eval/out_ce12/native · 이미 있는 것이 하나라도 있으면 거절 · 종료 2)
  <native>/<tag>/ 기록기 결과 · <native>/<tag>.log · .slot.json · .guard.json · <native>/_attempts/<attempt>/run.json · usd/
종료 코드: 0 · 2 (거절 · 인자 · 관문 기능 없음) · 98 (멈춤 파일 · 마감) · slot v3 의 코드 (89 변환 예상 위반 · 90 · 91 · 94~97 · 자식 코드 · 99 guard) ·
  88 (자식은 0 인데 출력 위치 · 내용이 실행기가 정한 것과 다름). slot v3 의 89 는 변환 예상 위반.
사용 (lead):
  PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
  "$PY" ce12/run_dump.py --which cts --checkpoint <E1>/model_20000.pt --tag cts_e1_m20000 [--gpu 1] [--dry_run]
  "$PY" ce12/run_dump.py --which v2 --tag v2_flat
  기록기 인자는 맨 뒤 -- 다음에 허용 목록만 (예: -- --steps 60 --reset_envs 1,5 --reset_step 30 --switch_env 0 --switch_step 40 --switch_cell fwd03)
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
EVAL = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import cells as CL  # noqa: E402

# 시험만 바꾼다 (run.json overrides 에 남고 validate_dump.py 는 --allow_overrides 없이는 거절한다)
OV = {k: os.environ[k] for k in ("CE12_EVAL_ROOT", "CE12_GUARD", "CE12_DUMP_DIR", "CE12_PY_CTS", "CE12_PY_V2", "CE12_SLOT", "CE12_ISOLATE")
      if os.environ.get(k)}
BASE = OV.get("CE12_EVAL_ROOT", EVAL).replace("\\", "/")
PY_CTS = OV.get("CE12_PY_CTS", "C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe")
PY_V2 = OV.get("CE12_PY_V2", "C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe")
PY_TOOLS = "C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe" if not OV else sys.executable
SLOT = OV.get("CE12_SLOT", f"{EVAL}/isaac_slot_v3.py").replace("\\", "/")
ISOLATE = OV.get("CE12_ISOLATE", f"{EVAL}/usd_isolate_run_v3.py").replace("\\", "/")
GUARD = OV.get("CE12_GUARD", f"{EVAL}/gpu_guard.py").replace("\\", "/")
DUMP_DIR = OV.get("CE12_DUMP_DIR", HERE).replace("\\", "/")
NATIVE = f"{BASE}/out_ce12/native"
SCAN = ",".join(f"{BASE}/{d}" for d in ("out_ce12/native", "out_branch", "out_uncr", "out_rand"))
LOCK = f"{BASE}/slot/isaac_convert.lock"
REGISTRY = f"{BASE}/slot/isaac_usd_registry.json"
TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
EXPECT = {"cts": 1, "v2": 0}
EXPECT_ENV = "FOOTHOLD_EXPECT_CONVERSIONS"
SLOT_EXPECT_FLAG = "--expect_conversions"
V2_CKPT = "C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/models/foothold-v2.pt"

# 기록기 추가 인자 허용 목록: 이름 -> 값 형식 ("flag" 는 값 없음). 이 밖의 옵션은 모두 거절.
_INT = re.compile(r"^-?\d{1,6}$")
_FLOAT = re.compile(r"^-?\d{1,6}(\.\d{1,9})?$")
_WORD = re.compile(r"^[A-Za-z0-9_]{1,40}$")
_ENVS = re.compile(r"^\d{1,4}(,\d{1,4}){0,63}$")
COMMON = {"--cells": "cells", "--envs_per_cell": "int", "--steps": "int", "--reset_envs": "envs", "--reset_step": "int",
          "--switch_env": "int", "--switch_step": "int", "--switch_cell": "cell"}
ALLOWED = {
    "cts": dict(COMMON, **{"--family": "word", "--difficulty": "float", "--eval_seed": "int", "--physx_small_buffers": "flag",
                           "--train_yaml": "file", "--agent_yaml": "file"}),
    "v2": dict(COMMON, **{"--seed": "int", "--env_spacing": "float", "--dr_profile": "choice:generalization,command_response",
                          "--spawn_xy_range": "float", "--yaw_range_deg": "float", "--joint_pos_scale": "float"}),
}
FORBIDDEN_WHY = {"--allow_cfg_diff": "정식 자료에서 금지 (설정 차이 관문을 끈다)", "--outdir": "실행기 소유", "--tag": "실행기 소유",
                 "--checkpoint": "실행기 소유", "--env_yaml": "기준 설정을 바꾼다", "--device": "장치는 실행기가 정한다",
                 "--headless": "실행기 소유"}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _value_ok(kind, v):
    if kind == "int":
        return bool(_INT.match(v))
    if kind == "float":
        return bool(_FLOAT.match(v))
    if kind == "word":
        return bool(_WORD.match(v))
    if kind == "envs":
        return bool(_ENVS.match(v))
    if kind == "cell":
        return v in CL.CE12_CELLS
    if kind == "cells":
        try:
            CL.parse_cells(v)
            return True
        except ValueError:
            return False
    if kind == "file":
        return os.path.isfile(v)
    if kind.startswith("choice:"):
        return v in kind[7:].split(",")
    return False


def parse_extra(which, tokens):
    """허용 목록 파싱. (정규화한 {이름: 값 또는 True}, '') 또는 (None, 거절 사유)."""
    allowed = ALLOWED[which]
    out, i = {}, 0
    while i < len(tokens):
        t = tokens[i]
        if not t.startswith("--"):
            return None, f"옵션이 아닌 토큰 {t!r}"
        name, eq, val = t.partition("=")
        if name in FORBIDDEN_WHY:
            return None, f"{name}: {FORBIDDEN_WHY[name]}"
        if name not in allowed:
            return None, f"허용 목록에 없는 옵션 {name!r} (축약 · 다른 이름 거절 · 허용: {sorted(allowed)})"
        if name in out:
            return None, f"{name} 가 두 번 나온다"
        kind = allowed[name]
        if kind == "flag":
            if eq:
                return None, f"{name} 는 값을 받지 않는다"
            out[name] = True
            i += 1
            continue
        if not eq:
            if i + 1 >= len(tokens):
                return None, f"{name} 의 값이 없다"
            val = tokens[i + 1]
            i += 2
        else:
            i += 1
        if val.startswith("--") or not _value_ok(kind, val):
            return None, f"{name} 값 {val!r} 형식이 맞지 않다 ({kind})"
        out[name] = os.path.abspath(val).replace("\\", "/") if kind == "file" else val
    return out, ""


def request_of(which, extra):
    """기록기에 넘길 인자 (늘 명시) 와 run.json 에 남길 요청."""
    req = {"cells": extra.get("--cells", CL.DEFAULT_CELLS), "envs_per_cell": int(extra.get("--envs_per_cell", CL.DEFAULT_ENVS_PER_CELL)),
           "steps": int(extra.get("--steps", CL.DEFAULT_STEPS)), "reset_envs": extra.get("--reset_envs", ""),
           "reset_step": int(extra.get("--reset_step", 0)), "switch_env": int(extra.get("--switch_env", -1)),
           "switch_step": int(extra.get("--switch_step", 0)), "switch_cell": extra.get("--switch_cell", "")}
    cells = CL.parse_cells(req["cells"])
    if not 1 <= req["steps"] <= CL.MAX_STEPS or not 1 <= req["envs_per_cell"] <= 64:
        raise ValueError(f"steps 1..{CL.MAX_STEPS} · envs_per_cell 1..64")
    why = CL.fixture_problem(req["steps"], len(cells) * req["envs_per_cell"], CL.parse_env_list(req["reset_envs"]), req["reset_step"],
                             req["switch_env"], req["switch_step"], req["switch_cell"])
    if why:
        raise ValueError(why)
    args = ["--cells", req["cells"], "--envs_per_cell", str(req["envs_per_cell"]), "--steps", str(req["steps"])]
    for k, v in extra.items():
        if k in ("--cells", "--envs_per_cell", "--steps"):
            continue
        args += [k] if v is True else [k, str(v)]
    req["other"] = {k: v for k, v in extra.items() if k not in ("--cells", "--envs_per_cell", "--steps")}
    return args, req


def capabilities():
    """관문 v3 원본에 변환 예상 기능의 이름이 있는지 (없으면 v2 를 띄우지 않는다)."""
    def txt(p):
        try:
            return open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            return None
    s, i = txt(SLOT), txt(ISOLATE)
    return {"slot": SLOT, "isolate": ISOLATE, "slot_exists": s is not None, "isolate_exists": i is not None,
            "slot_sha256": sha(SLOT) if s is not None else None, "isolate_sha256": sha(ISOLATE) if i is not None else None,
            "slot_expect_flag": bool(s and SLOT_EXPECT_FLAG in s), "slot_expect_env": bool(s and EXPECT_ENV in s),
            "isolate_expect_env": bool(i and EXPECT_ENV in i)}


def paths(tag, attempt):
    att = f"{NATIVE}/_attempts/{attempt}"
    return {"out": f"{NATIVE}/{tag}", "log": f"{NATIVE}/{tag}.log", "slot": f"{NATIVE}/{tag}.slot.json",
            "guard": f"{NATIVE}/{tag}.guard.json", "attempt_dir": att, "run": f"{att}/run.json", "usd": f"{att}/usd"}


def build(a, attempt, dump_args, cap):
    P = paths(a.tag, attempt)
    py = PY_CTS if a.which == "cts" else PY_V2
    dump = [py, ISOLATE, f"{DUMP_DIR}/dump_native_{a.which}.py", "--headless", "--checkpoint", a.checkpoint, "--tag", a.tag,
            "--outdir", NATIVE] + dump_args
    guard = [PY_TOOLS, GUARD, "--gpu", str(a.gpu), "--min_free_mib", str(a.min_free_mib), "--log", P["log"], "--summary", P["guard"], "--"]
    slot = [PY_TOOLS, SLOT, "--watch_log", P["log"], "--record", P["slot"], "--usd_root", P["usd"], "--attempt", attempt,
            "--lock", LOCK, "--registry", REGISTRY, "--scan_dirs", SCAN, "--stop_file", a.stop_file, "--deadline", str(a.deadline)]
    if cap["slot_expect_flag"]:
        slot += [SLOT_EXPECT_FLAG, str(EXPECT[a.which])]
    return slot + ["--"] + guard + dump


def output_problem(a):
    """자식 종료 뒤 실행기가 직접 본다 (validate 에만 맡기지 않는다)."""
    d = f"{NATIVE}/{a.tag}"
    miss = [f for f in ("native.npz", "meta.json", "signature.json") if not os.path.isfile(f"{d}/{f}")]
    if miss:
        return f"{d} 에 {miss} 없음"
    try:
        m = json.load(open(f"{d}/meta.json", encoding="utf-8"))
    except (OSError, ValueError) as ex:
        return f"meta.json 을 못 읽음 {type(ex).__name__}"
    ma = m.get("args") or {}
    same = lambda x, y: os.path.normcase(os.path.abspath(str(x))) == os.path.normcase(os.path.abspath(str(y)))  # noqa: E731
    if not same(ma.get("outdir", ""), NATIVE) or ma.get("tag") != a.tag or not same(m.get("checkpoint", ""), a.checkpoint):
        return f"meta 의 outdir {ma.get('outdir')!r} · tag {ma.get('tag')!r} · checkpoint {m.get('checkpoint')!r} 가 실행기 값과 다름"
    if ma.get("allow_cfg_diff"):
        return "meta args allow_cfg_diff 가 켜져 있다"
    return ""


def main(argv=None):
    ap = argparse.ArgumentParser(description="CE12 native 기록기 실행기", allow_abbrev=False)
    ap.add_argument("--which", choices=["cts", "v2"], required=True)
    ap.add_argument("--checkpoint", default="")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--gpu", type=int, default=1)
    ap.add_argument("--min_free_mib", type=int, default=4096)
    ap.add_argument("--stop_file", default=f"{BASE}/out_ce12/STOP")
    ap.add_argument("--deadline", type=float, default=0.0, help="epoch 초 · 0 이면 없음")
    ap.add_argument("--dry_run", action="store_true")
    ap.add_argument("extra", nargs=argparse.REMAINDER, help="-- 뒤는 기록기 인자 (허용 목록만)")
    a = ap.parse_args(argv)
    tokens = a.extra[1:] if a.extra and a.extra[0] == "--" else a.extra
    if not TAG_RE.match(a.tag):
        print(f"STOP: tag {a.tag!r} 는 영문 · 숫자 · _ . - 만 (경로가 될 수 없다)", flush=True)
        return 2
    if not a.checkpoint:
        if a.which == "v2":
            a.checkpoint = V2_CKPT
        else:
            print("STOP: cts 는 --checkpoint 가 필요하다", flush=True)
            return 2
    a.checkpoint = os.path.abspath(a.checkpoint).replace("\\", "/")
    if not os.path.isfile(a.checkpoint):
        print(f"STOP: 체크포인트가 없다 {a.checkpoint}", flush=True)
        return 2
    extra, why = parse_extra(a.which, tokens)
    if extra is None:
        print(f"STOP: 기록기 인자 거절 · {why}", flush=True)
        return 2
    try:
        dump_args, req = request_of(a.which, extra)
    except ValueError as ex:
        print(f"STOP: 기록 범위 · {ex}", flush=True)
        return 2
    cap = capabilities()
    if not cap["slot_exists"] or not cap["isolate_exists"]:
        print(f"STOP: 관문 파일이 없다 {SLOT} · {ISOLATE}", flush=True)
        return 2
    if EXPECT[a.which] == 0 and not ((cap["slot_expect_flag"] or cap["slot_expect_env"]) and cap["isolate_expect_env"]):
        print(f"STOP: v2 는 변환 예상 0 모드가 필요한데 관문 v3 에 아직 없다 ({EXPECT_ENV} · {SLOT_EXPECT_FLAG} 이름이 원본에 안 보임) · "
              f"slot flag {cap['slot_expect_flag']} env {cap['slot_expect_env']} · isolate env {cap['isolate_expect_env']}", flush=True)
        return 2
    attempt = f"{a.tag}-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
    P = paths(a.tag, attempt)
    taken = [P[k] for k in ("out", "log", "slot", "guard") if os.path.exists(P[k])]
    if taken:
        print(f"STOP: 이미 있다 (덮어쓰지 않는다 · 옮긴 뒤 다시): {taken}", flush=True)
        return 2
    cmd = build(a, attempt, dump_args, cap)
    env = dict(os.environ, CUDA_DEVICE_ORDER="PCI_BUS_ID", CUDA_VISIBLE_DEVICES=str(a.gpu), OMNI_KIT_ACCEPT_EULA="YES",
               PYTHONUNBUFFERED="1", **{EXPECT_ENV: str(EXPECT[a.which])})
    rec = {"tool": "ce12/run_dump.py", "version": "v2", "which": a.which, "tag": a.tag, "attempt": attempt, "checkpoint": a.checkpoint,
           "gpu": a.gpu, "min_free_mib": a.min_free_mib, "stop_file": a.stop_file, "deadline": a.deadline, "paths": P, "cmd": cmd,
           "request": req, "expect_conversions": EXPECT[a.which], "capabilities": cap,
           "env_set": {k: env[k] for k in ("CUDA_DEVICE_ORDER", "CUDA_VISIBLE_DEVICES", "OMNI_KIT_ACCEPT_EULA", "PYTHONUNBUFFERED", EXPECT_ENV)},
           "overrides": OV, "run_dump_sha256": sha(os.path.abspath(__file__)), "cells_sha256": sha(f"{HERE}/cells.py"),
           "t_request": time.strftime("%Y-%m-%d %H:%M:%S"), "t_request_epoch": time.time()}
    if a.dry_run:
        print("[CE12-RUN] dry_run attempt", attempt)
        print(json.dumps({"paths": P, "cmd": cmd, "env_set": rec["env_set"], "request": req, "capabilities": cap}, ensure_ascii=False, indent=1))
        return 0
    why = ("stop file" if a.stop_file and os.path.exists(a.stop_file) else
           "deadline" if a.deadline and time.time() > a.deadline else "")
    os.makedirs(P["attempt_dir"], exist_ok=False)

    def finish(rc, **kw):
        rec.update(kw, rc=rc, t_end=time.strftime("%Y-%m-%d %H:%M:%S"))
        with open(P["run"], "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
        print(f"[CE12-RUN] {a.which} tag {a.tag} attempt {attempt} rc {rc}", flush=True)
        return rc

    if why:
        return finish(98, state=f"not launched ({why})")
    with open(P["run"], "w", encoding="utf-8") as f:
        json.dump(dict(rec, state="launched"), f, ensure_ascii=False, indent=1)
    print(f"[CE12-RUN] start {a.which} tag {a.tag} attempt {attempt}", flush=True)
    rc = subprocess.run(cmd, cwd=EVAL, env=env).returncode
    if rc != 0:
        return finish(rc, child_rc=rc, state="exited")
    prob = output_problem(a)
    if prob:
        return finish(88, child_rc=rc, state="exited", output_problem=prob)
    return finish(0, child_rc=rc, state="exited", output_problem="")


if __name__ == "__main__":
    sys.exit(main())
