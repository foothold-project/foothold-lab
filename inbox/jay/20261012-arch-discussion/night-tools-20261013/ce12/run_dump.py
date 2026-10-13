# -*- coding: utf-8 -*-
"""CE12 1 단계 native 기록기 실행기 (lead 가 띄운다 · 이 파일 자체는 GPU 를 쓰지 않고 자식을 띄울 뿐이다).

분류: A/평가 · CE12-v1 이식 진단 1 · 실행기
작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 19:03
근거: lead 지시 10/13 19:03 · _eval/isaac_slot.py v2 (--usd_root · --attempt 필수) · _eval/usd_isolate_run.py v2 · _eval/gpu_guard.py ·
      _eval/unseen_driver_cmdr.py run_one (같은 순서 · 같은 환경 변수) · IsaacLab 변환기 사용처 (아래 v2 근거) · 모두 읽기만
요지: cts 는 isaac_slot -> gpu_guard -> usd_isolate_run -> dump_native_cts.py. v2 는 URDF 변환이 없어 isaac_slot 이 95 를 내므로
      slot 없이 gpu_guard -> usd_isolate_run -> dump_native_v2.py 로 띄우고, 끝난 뒤 변환이 정말 없었는지 확인한다.
상태: 가짜 자식 (실제 isaac_slot.py · usd_isolate_run.py + 가짜 guard · 가짜 기록기) 으로만 시험. 실제 Isaac 실행 0 회

출력 배치 (기본 _eval/out_ce12/native · 이미 있는 것이 하나라도 있으면 거절 · 종료 2)
  <native>/<tag>/                    기록기 결과 (native.npz · meta.json · signature.json) · 검증 stamp 도 여기
  <native>/<tag>.log                 감시 로그 (gpu_guard 가 자식 출력을 씀). isaac_slot 의 --scan_dirs 가 <native> 의 *.log 를 훑으므로 여기 둔다
  <native>/<tag>.slot.json           isaac_slot 기록 (cts 만)
  <native>/<tag>.guard.json          gpu_guard 요약
  <native>/_attempts/<attempt>/run.json   이 실행기의 기록 (명령 · 시각 · 종료 코드 · v2 격리 확인)
  <native>/_attempts/<attempt>/usd/  이 시도 전용 USD 루트 (FOOTHOLD_USD_ROOT)
  attempt 이름은 <tag>-<YYYYmmdd-HHMMSS>-<pid>

v2 를 slot 없이 띄우는 근거 (코드 읽기 · 10/13 19:0x)
  1. Isaac Lab 에서 변환기 (AssetConverterBase 자식) 를 만드는 곳은 spawn_from_urdf (sim/spawners/from_files/from_files.py:118 UrdfConverter)
     와 spawn_from_mjcf (같은 파일 :160 MjcfConverter) 둘뿐이다 (isaaclab · isaaclab_assets · isaaclab_tasks 전체 grep). MeshConverter 를
     만드는 spawner 는 없다.
  2. v2 기록기의 장면: robot = UNITREE_GO2_CFG (isaaclab_assets/robots/unitree.py:140-142 UsdFileCfg · go2.usd · spawn_from_usd) ·
     terrain_type "plane" (terrain_importer.py:108 · :223 GroundPlaneCfg · from_files_cfg.py:206 USD 파일) · DomeLight · RayCaster ·
     ContactSensor (velocity_env_cfg.py MySceneCfg). velocity 과제 폴더에 UrdfFileCfg · MjcfFileCfg 사용 없음.
     학습 기록 models/foothold-v2.env.yaml 의 robot spawn 도 spawn_from_usd.
  3. 그래서 v2 실행에는 IsaacLab.usd_* 폴더가 생기지 않고 isaac_slot 은 자식 종료 0 이어도 95 를 낸다 (isaac_slot.py 「폴더 하나」 규칙).
  이 근거가 틀렸을 때를 위해 실행 뒤 확인한다: <usd>/isolate_state.json 이 없거나 patched_by 가 비면 92 (격리가 안 걸렸다),
  <usd>/assigned.jsonl 에 줄이 있거나 로그에 IsaacLab.usd_ 가 보이면 93 (변환이 일어났다). 둘 다 validate_dump.py 가 다시 본다.
  v2 는 변환 잠금 (isaac_convert.lock) 을 잡지 않는다. 변환이 없으므로 잠금이 막을 공유 쓰기가 없다 (위 근거가 맞을 때).

종료 코드: 0 · 2 (거절 · 인자) · 98 (멈춤 파일 · 마감) · cts 는 isaac_slot 의 코드 (94~97 · 자식 코드) · v2 는 gpu_guard 의 코드
  (99 = guard 정지 · 자식 코드) 또는 92 · 93.
사용 (lead):
  PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
  "$PY" ce12/run_dump.py --which cts --checkpoint <E1>/model_20000.pt --tag cts_e1_m20000 [--gpu 1] [--dry_run]
  "$PY" ce12/run_dump.py --which v2 --tag v2_flat
  기록기에 더 줄 인자는 맨 뒤 -- 다음에 (예: -- --train_yaml <E1>/params/env.yaml --agent_yaml <E1>/params/agent.yaml)
  끝나면 출력된 attempt 로: "$PY" ce12/validate_dump.py --which cts --tag cts_e1_m20000 --checkpoint ... --attempt <attempt> --stamp
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
# 시험만 바꾼다 (run.json overrides 에 남고 validate_dump.py 는 --allow_overrides 없이는 거절한다)
OV = {k: os.environ[k] for k in ("CE12_EVAL_ROOT", "CE12_GUARD", "CE12_DUMP_DIR", "CE12_PY_CTS", "CE12_PY_V2") if os.environ.get(k)}
BASE = OV.get("CE12_EVAL_ROOT", EVAL).replace("\\", "/")
PY_CTS = OV.get("CE12_PY_CTS", "C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe")
PY_V2 = OV.get("CE12_PY_V2", "C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe")
PY_TOOLS = "C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe" if not OV else sys.executable
SLOT = os.path.join(EVAL, "isaac_slot.py").replace("\\", "/")
ISOLATE = os.path.join(EVAL, "usd_isolate_run.py").replace("\\", "/")
GUARD = OV.get("CE12_GUARD", os.path.join(EVAL, "gpu_guard.py")).replace("\\", "/")
DUMP_DIR = OV.get("CE12_DUMP_DIR", HERE).replace("\\", "/")
NATIVE = f"{BASE}/out_ce12/native"
SCAN = ",".join(f"{BASE}/{d}" for d in ("out_ce12/native", "out_branch", "out_uncr", "out_rand"))
LOCK = f"{BASE}/slot/isaac_convert.lock"
REGISTRY = f"{BASE}/slot/isaac_usd_registry.json"
TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
USD_RE = re.compile(r"IsaacLab.usd_(\d{8}_\d{6}_\d+)")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def paths(tag, attempt):
    att = f"{NATIVE}/_attempts/{attempt}"
    return {"out": f"{NATIVE}/{tag}", "log": f"{NATIVE}/{tag}.log", "slot": f"{NATIVE}/{tag}.slot.json",
            "guard": f"{NATIVE}/{tag}.guard.json", "attempt_dir": att, "run": f"{att}/run.json", "usd": f"{att}/usd"}


def build(a, attempt, extra):
    P = paths(a.tag, attempt)
    if a.which == "cts":
        dump = [PY_CTS, ISOLATE, f"{DUMP_DIR}/dump_native_cts.py", "--headless", "--checkpoint", a.checkpoint, "--tag", a.tag,
                "--outdir", NATIVE] + extra
        guard = [PY_TOOLS, GUARD, "--gpu", str(a.gpu), "--min_free_mib", str(a.min_free_mib), "--log", P["log"], "--summary", P["guard"], "--"]
        slot = [PY_TOOLS, SLOT, "--watch_log", P["log"], "--record", P["slot"], "--usd_root", P["usd"], "--attempt", attempt,
                "--lock", LOCK, "--registry", REGISTRY, "--scan_dirs", SCAN, "--stop_file", a.stop_file, "--deadline", str(a.deadline), "--"]
        return slot + guard + dump, {}
    dump = [PY_V2, ISOLATE, f"{DUMP_DIR}/dump_native_v2.py", "--headless", "--checkpoint", a.checkpoint, "--tag", a.tag,
            "--outdir", NATIVE] + extra
    guard = [PY_TOOLS, GUARD, "--gpu", str(a.gpu), "--min_free_mib", str(a.min_free_mib), "--log", P["log"], "--summary", P["guard"], "--"]
    return guard + dump, {"FOOTHOLD_USD_ROOT": P["usd"]}


def v2_isolation(P):
    """v2 실행 뒤: 격리가 걸렸는지 (isolate_state.json) · 변환이 일어났는지 (assigned.jsonl · 로그의 IsaacLab.usd_)."""
    st_p = f"{P['usd']}/isolate_state.json"
    try:
        st = json.load(open(st_p, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        st = None
    asg_p = f"{P['usd']}/assigned.jsonl"
    lines = [x for x in open(asg_p, encoding="utf-8").read().splitlines() if x.strip()] if os.path.exists(asg_p) else []
    try:
        log = open(P["log"], encoding="utf-8", errors="replace").read()
    except FileNotFoundError:
        log = ""
    return {"isolate_state": st, "patched_by": (st or {}).get("patched_by", ""), "assigned_lines": len(lines),
            "log_usd_folders": sorted(set(USD_RE.findall(log)))}


def main(argv=None):
    ap = argparse.ArgumentParser(description="CE12 native 기록기 실행기")
    ap.add_argument("--which", choices=["cts", "v2"], required=True)
    ap.add_argument("--checkpoint", default="")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--gpu", type=int, default=1)
    ap.add_argument("--min_free_mib", type=int, default=4096)
    ap.add_argument("--stop_file", default=f"{BASE}/out_ce12/STOP")
    ap.add_argument("--deadline", type=float, default=0.0, help="epoch 초 · 0 이면 없음")
    ap.add_argument("--dry_run", action="store_true")
    ap.add_argument("extra", nargs=argparse.REMAINDER, help="-- 뒤는 기록기에 그대로")
    a = ap.parse_args(argv)
    extra = a.extra[1:] if a.extra and a.extra[0] == "--" else a.extra
    if not TAG_RE.match(a.tag):
        print(f"STOP: tag {a.tag!r} 는 영문 · 숫자 · _ . - 만 (경로가 될 수 없다)", flush=True)
        return 2
    if not a.checkpoint:
        if a.which == "v2":
            a.checkpoint = "C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/models/foothold-v2.pt"
        else:
            print("STOP: cts 는 --checkpoint 가 필요하다", flush=True)
            return 2
    a.checkpoint = os.path.abspath(a.checkpoint).replace("\\", "/")
    if not os.path.isfile(a.checkpoint):
        print(f"STOP: 체크포인트가 없다 {a.checkpoint}", flush=True)
        return 2
    for x in extra:
        if x in ("--tag", "--outdir", "--checkpoint"):
            print(f"STOP: 기록기 인자 {x} 는 실행기가 정한다", flush=True)
            return 2
    attempt = f"{a.tag}-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
    P = paths(a.tag, attempt)
    taken = [P[k] for k in ("out", "log", "slot", "guard") if os.path.exists(P[k])]
    if taken:
        print(f"STOP: 이미 있다 (덮어쓰지 않는다 · 옮긴 뒤 다시): {taken}", flush=True)
        return 2
    cmd, env_add = build(a, attempt, extra)
    env = dict(os.environ, CUDA_DEVICE_ORDER="PCI_BUS_ID", CUDA_VISIBLE_DEVICES=str(a.gpu), OMNI_KIT_ACCEPT_EULA="YES",
               PYTHONUNBUFFERED="1", **env_add)
    rec = {"tool": "ce12/run_dump.py", "which": a.which, "tag": a.tag, "attempt": attempt, "checkpoint": a.checkpoint,
           "gpu": a.gpu, "min_free_mib": a.min_free_mib, "stop_file": a.stop_file, "deadline": a.deadline, "paths": P, "cmd": cmd,
           "env_set": {k: env[k] for k in ("CUDA_DEVICE_ORDER", "CUDA_VISIBLE_DEVICES", "OMNI_KIT_ACCEPT_EULA", "PYTHONUNBUFFERED")} | env_add,
           "slot": a.which == "cts", "overrides": OV, "run_dump_sha256": sha(os.path.abspath(__file__)),
           "t_request": time.strftime("%Y-%m-%d %H:%M:%S"), "t_request_epoch": time.time()}
    if a.dry_run:
        print("[CE12-RUN] dry_run attempt", attempt)
        print(json.dumps({"paths": P, "cmd": cmd, "env_set": rec["env_set"]}, ensure_ascii=False, indent=1))
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
    if a.which == "cts":
        return finish(rc, child_rc=rc, state="exited")
    iso = v2_isolation(P)
    out = rc
    if rc == 0 and (iso["isolate_state"] is None or not iso["patched_by"]):
        out = 92
    elif rc == 0 and (iso["assigned_lines"] or iso["log_usd_folders"]):
        out = 93
    return finish(out, child_rc=rc, state="exited", v2_isolation=iso)


if __name__ == "__main__":
    sys.exit(main())
