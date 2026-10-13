# -*- coding: utf-8 -*-
"""CE12 1 단계 native 기록이 「이번 시도에서」 제대로 끝났는지 검증하고, 통과하면 stamp 를 남긴다 (CPU).

분류: A/평가 · CE12-v1 이식 진단 1 · 기록 검증기
작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 19:03
근거: lead 지시 10/13 19:03 · branch/validate_branch.py · unseen_driver_cmdr.py validate_run 과 같은 slot · guard · 로그 규칙 (읽기만) ·
      run_dump.py 출력 배치 · adapters.py DUMP_COMMON · DUMP_CTS · DUMP_V2
요지: 검사마다 이름을 붙여 모두 돌리고 (첫 실패에서 멈추지 않는다) 실패한 이름을 모두 보고한다. 하나라도 실패면 INVALID.
상태: 결함 주입 시험 (test_run_dump.py) 과 변이 (mutate_run_dump.py) 만 거쳤다. 실제 기록에는 아직 안 돌렸다

검사 (cts)
  R1 run.json: <native>/_attempts/<attempt>/run.json 이 있고 attempt · which · tag · checkpoint 가 인자와 같다
  R2 시험용 바꿔치기 없음 (run.json overrides 가 비었다 · --allow_overrides 는 시험 전용)
  S1 slot attempt 가 --attempt 와 같다          S2 slot_rc 0          S3 child_rc 0          S4 state_at_release scene_built
  S5 usd_final 정확히 하나                      S6 usd_outside_root 없음                    S7 conflicts 없음
  S8 slot cmd 에 usd_isolate_run.py · dump_native_cts.py · --tag <tag> · --checkpoint <체크포인트>
  G1 guard exit_code 0 · guard 정지 아님
  L1 로그에 Traceback 없음                      L2 로그에 「[CE12-DUMP] done <tag> N 」
  N1 <native>/<tag>/native.npz 가 있고 형식이 맞다 (열쇠 · 모양 · 관측 폭 · 유한값 · model)
  M1 meta 의 체크포인트 경로가 같고 sha256 이 지금 파일과 같다
  M2 meta 의 model · tag 가 맞고 t_start 가 이 시도의 요청 시각 이후 (예전 결과를 새 시도로 받지 않는다)
검사 (v2 · slot 없이 띄운다 · run_dump.py 머리의 근거)
  S1~S8 대신: V1 run rc 0 · child_rc 0      V2 <usd>/isolate_state.json 이 있고 patched_by 가 있다 (격리가 걸렸다)
  V3 <usd>/assigned.jsonl 이 없거나 비었다 (변환 없음)    V4 로그에 IsaacLab.usd_ 없음 (변환 없음)
  V5 run cmd 에 usd_isolate_run.py · dump_native_v2.py · --tag <tag> · --checkpoint <체크포인트>
  R1 · R2 · G1 · L1 · L2 · N1 · M1 · M2 는 같다.
stamp (--stamp · 모두 통과일 때만): <native>/<tag>/validate_stamp.json 에 attempt 와 파일 sha256 (npz · meta · signature · 로그 · guard ·
  slot 또는 run · isolate_state).
사용: python validate_dump.py --which cts|v2 --tag T --checkpoint P --attempt A [--stamp]
종료 코드: 0 VALID · 1 INVALID · 2 인자
"""
import os

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.dirname(HERE)
BASE = os.environ.get("CE12_EVAL_ROOT", EVAL).replace("\\", "/")
NATIVE = f"{BASE}/out_ce12/native"
TRACE = "Traceback (most recent call last)"
OBS_DIM = {"cts": {"obs_policy": 450, "obs_single_obs": 45, "obs_critic": 275}, "v2": {"obs_policy": 235}}
MODEL = {"cts": "cts_student", "v2": "v2"}
DUMP_SCRIPT = {"cts": "dump_native_cts.py", "v2": "dump_native_v2.py"}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def same_path(x, y):
    return os.path.normcase(os.path.abspath(str(x))) == os.path.normcase(os.path.abspath(str(y)))


def load_json(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def cmd_ok(cmd, which, tag, ckpt):
    c = [str(x).replace("\\", "/") for x in (cmd or [])]
    if not any(x.endswith("/usd_isolate_run.py") or x == "usd_isolate_run.py" for x in c):
        return "usd_isolate_run.py 없음"
    if not any(x.endswith("/" + DUMP_SCRIPT[which]) or x == DUMP_SCRIPT[which] for x in c):
        return f"{DUMP_SCRIPT[which]} 없음"
    if "--tag" not in c or c.index("--tag") + 1 >= len(c) or c[c.index("--tag") + 1] != tag:
        return "--tag 다름"
    if "--checkpoint" not in c or c.index("--checkpoint") + 1 >= len(c) or not same_path(c[c.index("--checkpoint") + 1], ckpt):
        return "--checkpoint 다름"
    return ""


def npz_problem(path, which):
    """N1: 형식. adapters.py 의 열쇠 목록 + 모양 · 폭 · 유한값."""
    if not os.path.isfile(path):
        return "native.npz 없음"
    sys.path.insert(0, HERE)
    import adapters as A
    try:
        d = dict(np.load(path, allow_pickle=False))
    except Exception as ex:  # noqa: BLE001
        return f"npz 를 못 읽음 {type(ex).__name__}"
    model = MODEL[which]
    miss = A.check_dump_keys(d, model)
    if miss:
        return f"빠진 열쇠 {miss}"
    if str(d["model"]) != model:
        return f"model {d['model']} != {model}"
    T, N = d["raw_action"].shape[:2]
    J = len(d["art_joint_names"])
    if T < 1 or N < 1:
        return "T 또는 N 이 0"
    want = {k: (T + 1, N, s) for k, s in (("root_pos_w", 3), ("root_quat_w", 4), ("lin_vel_b", 3), ("ang_vel_b", 3),
                                          ("projected_gravity_b", 3), ("command", 3), ("joint_pos", J), ("joint_vel", J),
                                          ("last_action", 12))}
    want.update({k: (T, N, 12) for k in ("raw_action", "action_offset", "joint_target")})
    want.update({k: (T, N) for k in ("reset_after_step", "terminated", "time_out")})
    want.update({k: (T + 1, N, w) for k, w in OBS_DIM[which].items()})
    want.update({"default_joint_pos": (N, J), "default_joint_vel": (N, J), "cell_index": (N,)})
    if which == "v2":
        want["height_sensor_pos_w"] = (T + 1, N, 3)
        want["ray_hits_w"] = (T + 1, N, 187, 3)
        want["ray_starts_local"] = (187, 3)
    for k, s in want.items():
        if tuple(d[k].shape) != s:
            return f"{k} 모양 {tuple(d[k].shape)} != {s}"
    if len(d["obs_joint_names"]) != 12 or len(d["action_joint_names"]) != 12:
        return "관절 이름 목록이 12 개가 아니다"
    for k, v in d.items():
        if k == "ray_hits_w" or v.dtype.kind != "f":
            continue
        if not np.isfinite(v).all():
            return f"{k} 에 유한하지 않은 값"
    return ""


def check(a):
    """[(이름, 통과, 설명)] 과 stamp 용 파일 목록."""
    which, tag = a.which, a.tag
    R = []

    def add(name, ok, detail=""):
        R.append((name, bool(ok), "" if ok else detail))

    att_dir = f"{NATIVE}/_attempts/{a.attempt}"
    run = load_json(f"{att_dir}/run.json")
    add("R1", run is not None and run.get("attempt") == a.attempt and run.get("which") == which and run.get("tag") == tag
        and same_path(run.get("checkpoint", ""), a.checkpoint), f"run.json {None if run is None else {k: run.get(k) for k in ('attempt', 'which', 'tag', 'checkpoint')}}")
    add("R2", run is not None and (not run.get("overrides") or a.allow_overrides), f"overrides {None if run is None else run.get('overrides')}")
    files = {"log": f"{NATIVE}/{tag}.log", "guard": f"{NATIVE}/{tag}.guard.json", "npz": f"{NATIVE}/{tag}/native.npz",
             "meta": f"{NATIVE}/{tag}/meta.json", "signature": f"{NATIVE}/{tag}/signature.json", "run": f"{att_dir}/run.json"}
    if which == "cts":
        s = load_json(f"{NATIVE}/{tag}.slot.json") or {}
        files["slot"] = f"{NATIVE}/{tag}.slot.json"
        add("S1", s.get("attempt") == a.attempt, f"slot attempt {s.get('attempt')!r}")
        add("S2", s.get("slot_rc") == 0, f"slot_rc {s.get('slot_rc')}")
        add("S3", s.get("child_rc") == 0, f"child_rc {s.get('child_rc')}")
        add("S4", s.get("state_at_release") == "scene_built", f"state {s.get('state_at_release')!r}")
        add("S5", isinstance(s.get("usd_final"), list) and len(s["usd_final"]) == 1, f"usd_final {s.get('usd_final')}")
        add("S6", "usd_outside_root" in s and not s["usd_outside_root"], f"usd_outside_root {s.get('usd_outside_root')}")
        add("S7", "conflicts" in s and not s["conflicts"], f"conflicts {s.get('conflicts')}")
        why = cmd_ok(s.get("cmd"), which, tag, a.checkpoint)
        add("S8", not why, f"slot cmd: {why}")
    else:
        usd = (run or {}).get("paths", {}).get("usd", f"{att_dir}/usd")
        add("V1", run is not None and run.get("rc") == 0 and run.get("child_rc") == 0,
            f"run rc {None if run is None else run.get('rc')} child_rc {None if run is None else run.get('child_rc')}")
        st = load_json(f"{usd}/isolate_state.json")
        add("V2", st is not None and bool(st.get("patched_by")), f"isolate_state {st}")
        if st is not None:
            files["isolate_state"] = f"{usd}/isolate_state.json"
        asg = f"{usd}/assigned.jsonl"
        n_asg = len([x for x in open(asg, encoding="utf-8").read().splitlines() if x.strip()]) if os.path.exists(asg) else 0
        add("V3", n_asg == 0, f"assigned.jsonl {n_asg} 줄 (변환이 일어났다)")
        why = cmd_ok((run or {}).get("cmd"), which, tag, a.checkpoint)
        add("V5", not why, f"run cmd: {why}")
    g = load_json(files["guard"]) or {}
    add("G1", g.get("exit_code") == 0 and g.get("stopped_by_guard") is False, f"guard exit {g.get('exit_code')} stopped {g.get('stopped_by_guard')}")
    try:
        log = open(files["log"], encoding="utf-8", errors="replace").read()
    except FileNotFoundError:
        log = None
    add("L1", log is not None and TRACE not in log, "로그 없음" if log is None else "로그에 Traceback")
    add("L2", log is not None and f"[CE12-DUMP] done {tag} N " in log, "로그에 이 tag 의 [CE12-DUMP] done 줄 없음")
    if which == "v2":
        import re
        found = sorted(set(re.findall(r"IsaacLab.usd_(\d{8}_\d{6}_\d+)", log or "")))
        add("V4", log is not None and not found, f"로그의 USD 변환 폴더 {found}")
    why = npz_problem(files["npz"], which)
    add("N1", not why, why)
    meta = load_json(files["meta"])
    ok = meta is not None and same_path(meta.get("checkpoint", ""), a.checkpoint) and os.path.isfile(a.checkpoint) \
        and meta.get("checkpoint_sha256") == sha(a.checkpoint)
    add("M1", ok, "meta 없음" if meta is None else f"meta checkpoint {meta.get('checkpoint')!r} sha {str(meta.get('checkpoint_sha256'))[:12]}")
    t0 = (run or {}).get("t_request_epoch")
    try:
        ts = time.mktime(time.strptime(meta["t_start"], "%Y-%m-%d %H:%M:%S")) if meta else None
    except (KeyError, ValueError, TypeError):
        ts = None
    ok = meta is not None and meta.get("model") == MODEL[which] and (meta.get("args") or {}).get("tag") == tag \
        and t0 is not None and ts is not None and ts >= t0 - 1
    add("M2", ok, "meta 없음" if meta is None else f"meta model {meta.get('model')!r} tag {(meta.get('args') or {}).get('tag')!r} t_start {meta.get('t_start')} 요청 {t0}")
    return R, files


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", choices=["cts", "v2"], required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--attempt", required=True)
    ap.add_argument("--stamp", action="store_true")
    ap.add_argument("--allow_overrides", action="store_true", help="시험 전용")
    a = ap.parse_args(argv)
    R, files = check(a)
    bad = [r for r in R if not r[1]]
    for name, ok, detail in R:
        print(f"{'PASS' if ok else 'FAIL'} {name}{'' if ok else ' ' + detail[:300]}")
    if bad:
        print(f"INVALID {a.tag} attempt {a.attempt}: {[r[0] for r in bad]}")
        return 1
    if a.stamp:
        st = {"attempt": a.attempt, "which": a.which, "tag": a.tag, "checkpoint": a.checkpoint, "checks": [r[0] for r in R],
              "sha256": {k: sha(v) for k, v in files.items() if os.path.isfile(v)}, "validator_sha256": sha(os.path.abspath(__file__)),
              "t": time.strftime("%Y-%m-%d %H:%M:%S")}
        with open(f"{NATIVE}/{a.tag}/validate_stamp.json", "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=1)
    print(f"VALID {a.tag} attempt {a.attempt}{' (stamp)' if a.stamp else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
