# -*- coding: utf-8 -*-
"""CE12 1 단계 native 기록의 「수집 성공」 과 「자료 승인」 을 나눠 판정한다 v2 (CPU).

분류: A/평가 · CE12-v1 이식 진단 1 · 기록 검증기
작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 19:03 · v2 20:10 (ASTRA 17d §2.7 · §4) · 10/14 00:49 (ASTRA 17f 4.2 · 4.3 · 4.4)
근거: VERIFY-astra-17d.md §2.6 · §2.7 · §4 · §7 · run_dump.py v2 · compare_native.py · cells.py · adapters.py · _eval/isaac_slot_v3.py 기록 칸 (읽기만)
요지: 수집 성공 (COLLECTED) 은 「이번 attempt 가 관문을 지나 기록을 제자리에 남겼다」 까지다. S0 1 단계 동치 승인 (APPROVED) 은
      수집 성공에 더해 서명 내용 · 요청 (cell · T · N · 명령 시간열) · 금지 override 와 설정 차이 · student 경로 · CPU 재계산 비교 보고서
      (그 보고서가 읽은 NPZ · meta · checkpoint · 설정 · 코드 해시가 지금 파일과 같음) · reset 과 명령 전환 경로가 모두 있어야 한다.
      끝나지 않은 검사는 실패가 아니라 「보류」 (PENDING) 다.
상태: 결함 주입 시험 (test_run_dump.py) 과 변이 (mutate_run_dump.py) 만 거쳤다. 실제 기록에는 아직 안 돌렸다

v1 (19:03) 의 결함 (ASTRA 17d §2.7 재현): 형식만 보고 meta 의 allow_cfg_diff · 관측 설정 차이 · teacher 입력 변경 action 차 · 틀린 steps/cells ·
  signature 누락이 있어도 실패 목록이 [] 였다. stamp 는 없는 signature 를 해시 목록에서 조용히 뺐다.

수집 검사 (C · 모두 통과해야 COLLECTED)
  R1 run.json 의 attempt · which · tag · 체크포인트   R2 시험용 바꿔치기 없음   R3 변환 예상 (cts 1 · v2 0) 이 기록 · 환경 변수 · slot 기록에서 같음
  R4 실행기 종료 0 · 출력 위치 확인 통과
  S1 slot attempt   S2 slot_rc 0   S3 child_rc 0   S4 해제 상태 (cts scene_built · v2 scene_built 또는 exited)
  S5 USD 폴더 수 = 예상   S6 루트 밖 없음   S7 충돌 없음   S8 slot v3 · usd_isolate_run_v3.py · 기록기 · tag · 체크포인트 명령
  S9 assigned 연결 · 변환 수 (미연결 없음 · 흔적만 있는 경우 없음 · assigned 수 = 변환 시도 수 = 예상 · expect_violation 없음 · 거절된 변환 없음)
  S10 격리 상태 (patched_by · usd_isolate_run v3 · 막힌 일 없음 · slot 의 launcher_blocked 없음)
  S11 관문 오류 없음 (registry_error · killed · slot_error)
  G1 guard 0   L1 Traceback 없음   L2 「[CE12-DUMP] done <tag> N 」   N1 npz 형식   N2 signature.json 있음
  M1 meta 체크포인트 경로 · sha256 = 지금 파일   M2 meta model · tag · 시작 시각이 이 attempt 요청 이후
승인 검사 (A · --approve · 수집이 통과해야 의미가 있다)
  A1 signature.json 내용 = 지금 adapter 서명 (v2 는 기록의 런타임 관절 이름으로) · 이름이 npz 와 같음
  A2 요청 (run.json request) = 자료: cells · T · N · cell_index · cell_cmd (cells.py 표) · 요청한 강제 reset 이 그 step · env 에서 일어남
  A3 npz 명령 시간열 = 칸 명령 + 요청한 명령 전환 (모든 step · env)
  A4 금지 override 없음 (allow_cfg_diff · outdir) · 학습 설정 차이 0 (cts: 관측 · 행동 · decimation · v2: env.yaml 과 런타임 같음 · 기준 env.yaml)
  A5 student 경로: cts 는 기록기 자체 검사 (teacher 입력 변경 action 차 0) 와 CPU 재계산 (npz 관측 · critic 을 바꿔도 비트 동일 · policy 를
     바꾸면 변함) · v2 는 ActorCritic 이고 CPU 재계산이 유한
  A6 compare_native --recompute_action 보고서: 없으면 보류 · 상태 pass · 재계산 켬 · 해시 (npz · meta · signature · checkpoint · 설정 · 코드) =
     지금 파일 · T · N 같음
  A7 reset 경로 (reset 이 있고 그 뒤 action 이 1 step 이상 · 아니면 보류)   A8 명령 전환 경로 (전환이 있고 그 뒤 action 이 1 step 이상 ·
     마지막 관측의 전환은 바뀐 명령으로 계산한 action 이 0 개라 보류 · 17f 4.4)
  A9 실행 출처 (17f 4.3): 실행 당시 기록기 · adapter · cells · 실행기 · slot · isolate · guard 의 sha256 (run.json provenance · 옛 칸 ·
     meta) 이 모두 있고 서로 모순이 없고 실행 중 안 바뀌었고, 승인 대상 코드 (--code_bundle 의 SHA256SUMS 또는 지금 파일) 와 같다.
     비교 단계 코드 (compare_native · adapters · cells) 는 A6 에서 따로 본다.
  v2 height miss 수는 보고만 (0 이면 「miss 경로 미확인」 으로 표시 · 평면에서는 늘 0)
stamp: --stamp 는 수집 통과 때 validate_stamp.json (파일이 하나라도 없으면 쓰지 않고 실패). --approve 가 APPROVED 면 approval_stamp.json
  (승인 대상 target: which · tag · attempt · 체크포인트 경로와 sha256 · 실행 출처 · 비교 출처 · 입력 · 보고서 · 설정 · 코드 sha256).
  --check_approval 은 요청의 which · tag · attempt · 체크포인트 (정규화 경로와 sha256) 가 승인 대상과 같고 (17f 4.2 · 다른 모델이면 실패)
  stamp 의 파일이 지금과 같을 때만 STILL VALID.
사용: python validate_dump.py --which cts|v2 --tag T --checkpoint P --attempt A [--stamp] [--approve --compare_report R [--code_bundle S]]
      [--check_approval]
종료 코드: 0 COLLECTED (와 --approve 면 APPROVED) · 1 INVALID 또는 REJECTED 또는 stamp 무효 · 3 PENDING (보류) · 2 인자
"""
import os

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import cells as CL  # noqa: E402

BASE = os.environ.get("CE12_EVAL_ROOT", EVAL).replace("\\", "/")
NATIVE = f"{BASE}/out_ce12/native"
TRACE = "Traceback (most recent call last)"
OBS_DIM = {"cts": {"obs_policy": 450, "obs_single_obs": 45, "obs_critic": 275}, "v2": {"obs_policy": 235}}
MODEL = {"cts": "cts_student", "v2": "v2"}
DUMP_SCRIPT = {"cts": "dump_native_cts.py", "v2": "dump_native_v2.py"}
EXPECT = {"cts": 1, "v2": 0}
EXPECT_ENV = "FOOTHOLD_EXPECT_CONVERSIONS"
SLOT_NAME = "isaac_slot_v3.py"
ISOLATE_NAME = "usd_isolate_run_v3.py"
V2_ENV_YAML = "C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/models/foothold-v2.env.yaml"
PASS, FAIL, PEND = "PASS", "FAIL", "PENDING"


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
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
        return None


def _mods():
    import adapters as A
    import compare_native as C
    return A, C


def cmd_ok(cmd, which, tag, ckpt):
    c = [str(x).replace("\\", "/") for x in (cmd or [])]
    base = [x.rsplit("/", 1)[-1] for x in c]
    if ISOLATE_NAME not in base:
        return f"{ISOLATE_NAME} 없음"
    if DUMP_SCRIPT[which] not in base:
        return f"{DUMP_SCRIPT[which]} 없음"
    if base.index(DUMP_SCRIPT[which]) != base.index(ISOLATE_NAME) + 1:
        return f"{DUMP_SCRIPT[which]} 가 {ISOLATE_NAME} 바로 뒤가 아니다"
    if "--tag" not in c or c.index("--tag") + 1 >= len(c) or c[c.index("--tag") + 1] != tag:
        return "--tag 다름"
    if "--checkpoint" not in c or c.index("--checkpoint") + 1 >= len(c) or not same_path(c[c.index("--checkpoint") + 1], ckpt):
        return "--checkpoint 다름"
    for bad in ("--allow_cfg_diff", "--env_yaml", "--device"):
        if any(x == bad or x.startswith(bad + "=") for x in c):
            return f"금지 옵션 {bad}"
    pos = [i for i, x in enumerate(c) if x == "--outdir"]
    if any(x.startswith("--outdir=") for x in c) or len(pos) != 1 or pos[0] + 1 >= len(c) or c[pos[0] + 1] != NATIVE:
        return "--outdir 가 실행기 값 하나가 아니다"
    return ""


def npz_problem(path, which):
    """N1: 형식. adapters.py 의 열쇠 목록 + 모양 · 폭 · 유한값."""
    if not os.path.isfile(path):
        return "native.npz 없음"
    A, _ = _mods()
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


def files_of(which, tag, attempt):
    f = {"log": f"{NATIVE}/{tag}.log", "guard": f"{NATIVE}/{tag}.guard.json", "slot": f"{NATIVE}/{tag}.slot.json",
         "npz": f"{NATIVE}/{tag}/native.npz", "meta": f"{NATIVE}/{tag}/meta.json", "signature": f"{NATIVE}/{tag}/signature.json",
         "run": f"{NATIVE}/_attempts/{attempt}/run.json"}
    return f


def collect(a):
    """[(id, 상태, 설명)] · 수집 성공 검사."""
    which, tag = a.which, a.tag
    R = []

    def add(name, ok, detail=""):
        R.append((name, PASS if ok else FAIL, "" if ok else detail))

    F = files_of(which, tag, a.attempt)
    run = load_json(F["run"])
    s = load_json(F["slot"]) or {}
    add("R1", run is not None and run.get("attempt") == a.attempt and run.get("which") == which and run.get("tag") == tag
        and same_path(run.get("checkpoint", ""), a.checkpoint),
        f"run.json {None if run is None else {k: run.get(k) for k in ('attempt', 'which', 'tag', 'checkpoint')}}")
    add("R2", run is not None and (not run.get("overrides") or a.allow_overrides), f"overrides {None if run is None else run.get('overrides')}")
    exp = EXPECT[which]
    iso0 = s.get("isolate_state") if isinstance(s.get("isolate_state"), dict) else {}
    ok = run is not None and run.get("expect_conversions") == exp and (run.get("env_set") or {}).get(EXPECT_ENV) == str(exp) \
        and str(s.get("expect_conversions")) == str(exp) and str(iso0.get("expect_conversions", exp)) == str(exp)
    add("R3", ok, f"변환 예상 run {None if run is None else run.get('expect_conversions')} env "
                  f"{None if run is None else (run.get('env_set') or {}).get(EXPECT_ENV)} slot {s.get('expect_conversions')!r} "
                  f"isolate {iso0.get('expect_conversions')!r} (원하는 값 {exp})")
    add("R4", run is not None and run.get("rc") == 0 and run.get("output_problem") == "",
        f"실행기 rc {None if run is None else run.get('rc')} 출력 확인 {None if run is None else run.get('output_problem')!r}")
    add("S1", s.get("attempt") == a.attempt, f"slot attempt {s.get('attempt')!r}")
    add("S2", s.get("slot_rc") == 0, f"slot_rc {s.get('slot_rc')}")
    add("S3", s.get("child_rc") == 0, f"child_rc {s.get('child_rc')}")
    states = ("scene_built",) if which == "cts" else ("scene_built", "exited")
    add("S4", s.get("state_at_release") in states, f"state {s.get('state_at_release')!r} (허용 {states})")
    add("S5", isinstance(s.get("usd_final"), list) and len(s["usd_final"]) == exp, f"usd_final {s.get('usd_final')} (예상 {exp})")
    add("S6", "usd_outside_root" in s and not s["usd_outside_root"] and not s.get("assigned_outside_root"),
        f"usd_outside_root {s.get('usd_outside_root')} assigned_outside_root {s.get('assigned_outside_root')}")
    add("S7", "conflicts" in s and not s["conflicts"], f"conflicts {s.get('conflicts')}")
    why = cmd_ok(s.get("cmd"), which, tag, a.checkpoint)
    rc0 = [str(x).replace("\\", "/").rsplit("/", 1)[-1] for x in ((run or {}).get("cmd") or [])[:2]]
    if not why and s.get("slot_version") != "v3":
        why = f"slot_version {s.get('slot_version')!r}"
    if not why and SLOT_NAME not in rc0:
        why = f"run.json cmd 의 관문이 {SLOT_NAME} 가 아니다 {rc0}"
    add("S8", not why, f"명령: {why}")
    asg = s.get("assigned")
    add("S9", "usd_unassigned" in s and not s["usd_unassigned"] and s.get("hint_without_assigned") is False
        and isinstance(asg, list) and len(asg) == exp and s.get("expect_violation") is False and s.get("conversion_attempts") == exp
        and not s.get("unexpected_refused"),
        f"usd_unassigned {s.get('usd_unassigned')} hint_without_assigned {s.get('hint_without_assigned')} assigned {asg} "
        f"expect_violation {s.get('expect_violation')} conversion_attempts {s.get('conversion_attempts')} "
        f"unexpected_refused {s.get('unexpected_refused')} (예상 {exp})")
    iso = s.get("isolate_state")
    add("S10", isinstance(iso, dict) and bool(iso.get("patched_by")) and iso.get("version") == "v3" and not iso.get("blocked")
        and not s.get("launcher_blocked"), f"isolate_state {iso} launcher_blocked {s.get('launcher_blocked')}")
    add("S11", not s.get("registry_error") and "killed" not in s and "slot_error" not in s,
        f"registry_error {s.get('registry_error')!r} killed {s.get('killed')} slot_error {s.get('slot_error')!r}")
    g = load_json(F["guard"]) or {}
    add("G1", g.get("exit_code") == 0 and g.get("stopped_by_guard") is False, f"guard exit {g.get('exit_code')} stopped {g.get('stopped_by_guard')}")
    try:
        log = open(F["log"], encoding="utf-8", errors="replace").read()
    except FileNotFoundError:
        log = None
    add("L1", log is not None and TRACE not in log, "로그 없음" if log is None else "로그에 Traceback")
    add("L2", log is not None and f"[CE12-DUMP] done {tag} N " in log, "로그에 이 tag 의 [CE12-DUMP] done 줄 없음")
    why = npz_problem(F["npz"], which)
    add("N1", not why, why)
    add("N2", os.path.isfile(F["signature"]), "signature.json 없음")
    meta = load_json(F["meta"])
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
    add("M2", ok, "meta 없음" if meta is None else f"meta model {meta.get('model')!r} tag {(meta.get('args') or {}).get('tag')!r} "
                                                  f"t_start {meta.get('t_start')} 요청 {t0}")
    return R


# ------------------------------------------------------------------------------------------------- 승인
def _sig_now(A, which, d, n_envs):
    if which == "cts":
        ad = A.CTSStudentAdapter.from_source(n_envs)
    else:
        ad = A.V2Adapter.from_env_yaml([str(x) for x in d["obs_joint_names"]], n_envs, [str(x) for x in d["action_joint_names"]])
    sig = ad.signature()
    return json.loads(json.dumps(dict(sig, signature_sha256=A.signature_sha256(sig)), ensure_ascii=False))  # 파일과 같은 JSON 꼴로


def _student_check(A, which, a, d, meta):
    """A5. cts: 기록기 자체 검사 + CPU 재계산 (critic 을 바꿔도 비트 동일 · policy 를 바꾸면 변함). v2: ActorCritic · 유한."""
    import contextlib
    import io
    import torch
    from tensordict import TensorDict
    if which == "cts":
        chk = (meta.get("checks") or {}).get("teacher_input_randomized_max_abs_action_change")
        if chk != 0.0:
            return f"기록기 자체 검사 teacher 입력 변경 action 차 {chk!r} (0.0 이어야)"
        with contextlib.redirect_stdout(io.StringIO()):
            m, _ = A.load_cts_policy_cpu(a.checkpoint, meta.get("agent_yaml"))
        k = 0
        pol, sin, cri = (torch.as_tensor(d[x][k]) for x in ("obs_policy", "obs_single_obs", "obs_critic"))
        g = torch.Generator().manual_seed(17)
        with torch.inference_mode():
            a0 = m.act_inference(TensorDict({"policy": pol, "single_obs": sin, "critic": cri}, batch_size=[pol.shape[0]]))
            a1 = m.act_inference(TensorDict({"policy": pol, "single_obs": sin, "critic": torch.randn(cri.shape, generator=g) * 10.0},
                                            batch_size=[pol.shape[0]]))
            a2 = m.act_inference(TensorDict({"policy": pol + 0.1, "single_obs": sin, "critic": cri}, batch_size=[pol.shape[0]]))
        if not torch.equal(a0, a1):
            return f"CPU 재계산: critic 을 바꾸자 action 이 변함 {float((a0 - a1).abs().max()):.3g}"
        if not float((a2 - a0).abs().max()) > 0:
            return "CPU 재계산: policy 이력을 바꿔도 action 이 그대로 (대조군 실패)"
        return ""
    if meta.get("policy_class") != "ActorCritic":
        return f"v2 policy_class {meta.get('policy_class')!r}"
    with contextlib.redirect_stdout(io.StringIO()):
        m, _ = A.load_v2_policy_cpu(a.checkpoint)
    with torch.inference_mode():
        act = m.act_inference(TensorDict({"policy": torch.as_tensor(d["obs_policy"][0])}, batch_size=[d["obs_policy"].shape[1]]))
    return "" if torch.isfinite(act).all() else "v2 CPU 재계산 action 이 유한하지 않다"


def approve(a, F):
    """[(id, 상태, 설명)] · 자료 승인 검사. 검사 하나가 예외로 끝나면 그 검사만 FAIL."""
    which = a.which
    R = []

    def add(name, status, detail=""):
        R.append((name, status, "" if status == PASS else detail))

    try:
        A, C = _mods()
        d = dict(np.load(F["npz"], allow_pickle=False))
        meta = load_json(F["meta"]) or {}
        run = load_json(F["run"]) or {}
    except Exception as ex:  # noqa: BLE001
        return [(x, FAIL, f"입력을 못 읽음 {type(ex).__name__}: {ex}") for x in A_IDS], {}
    T, N = d["raw_action"].shape[:2]

    def step(name, fn):
        try:
            st, why = fn()
        except Exception as ex:  # noqa: BLE001
            st, why = FAIL, f"{type(ex).__name__}: {ex}"
        add(name, st, why)

    def a1():
        sig = load_json(F["signature"])
        if sig is None:
            return FAIL, "signature.json 없음 또는 JSON 아님"
        now = _sig_now(A, which, d, 1)
        if sig != now:
            diff = sorted(k for k in set(sig) | set(now) if sig.get(k) != now.get(k))
            return FAIL, f"서명이 지금 adapter 와 다름 · 다른 칸 {diff}"
        jn = sig.get("joint_names") or {}
        if jn.get("observation") != [str(x) for x in d["obs_joint_names"]] or jn.get("action") != [str(x) for x in d["action_joint_names"]]:
            return FAIL, "서명의 관절 이름이 npz 와 다름"
        return PASS, ""

    def a2():
        req = run.get("request") or {}
        cells = CL.parse_cells(req.get("cells", ""))
        E = int(req.get("envs_per_cell", 0))
        if T != int(req.get("steps", -1)):
            return FAIL, f"T {T} != 요청 steps {req.get('steps')}"
        if N != len(cells) * E:
            return FAIL, f"N {N} != 요청 {len(cells)} 칸 x {E}"
        if [str(x) for x in d["cell_names"]] != cells:
            return FAIL, f"cell_names {[str(x) for x in d['cell_names']]} != 요청 {cells}"
        if not np.array_equal(d["cell_index"], np.arange(N) // E):
            return FAIL, "cell_index 가 env // envs_per_cell 이 아니다"
        if not np.array_equal(np.asarray(d["cell_cmd"], np.float32), np.asarray([CL.CE12_CELLS[c][1] for c in cells], np.float32)):
            return FAIL, "cell_cmd 가 cells.py 표와 다름"
        why = CL.fixture_problem(T, N, CL.parse_env_list(req.get("reset_envs", "")), int(req.get("reset_step", 0)),
                                 int(req.get("switch_env", -1)), int(req.get("switch_step", 0)), req.get("switch_cell", ""))
        if why:
            return FAIL, f"요청한 reset · 전환이 기록 범위 규칙에 맞지 않다 ({why})"
        envs = CL.parse_env_list(req.get("reset_envs", ""))
        if envs:
            k = int(req["reset_step"]) - 1
            if not (d["reset_after_step"][k, envs].all() and d["time_out"][k, envs].all()):
                return FAIL, f"요청한 강제 reset (step {k} envs {envs}) 이 자료에 없다"
        return PASS, ""

    def a3():
        req = run.get("request") or {}
        exp = np.repeat(np.asarray(d["cell_cmd"], np.float32)[np.asarray(d["cell_index"])][None], T + 1, axis=0)
        if int(req.get("switch_env", -1)) >= 0:
            exp[int(req["switch_step"]):, int(req["switch_env"])] = np.asarray(CL.CE12_CELLS[req["switch_cell"]][1], np.float32)
        bad = np.argwhere(np.any(np.asarray(d["command"], np.float32) != exp, axis=-1))
        if len(bad):
            return FAIL, f"명령 시간열이 요청과 다름 · 첫 (관측 step, env) {bad[0].tolist()} · 개수 {len(bad)}"
        return PASS, ""

    def a4():
        ma = meta.get("args") or {}
        if ma.get("allow_cfg_diff"):
            return FAIL, "meta args allow_cfg_diff 켜짐"
        if not same_path(ma.get("outdir", ""), NATIVE):
            return FAIL, f"meta args outdir {ma.get('outdir')!r}"
        if which == "cts":
            cnt = meta.get("default_cfg_vs_train_yaml_counts")
            if not isinstance(cnt, dict) or any(cnt.get(k) != 0 for k in ("observations", "actions", "decimation")):
                return FAIL, f"학습 설정 차이 {cnt}"
        else:
            cv = meta.get("cfg_vs_env_yaml") or {}
            if not cv or cv.get("terms_runtime") != cv.get("terms_env_yaml") or cv.get("action_runtime") != cv.get("action_env_yaml"):
                return FAIL, "런타임 관측 · 행동 설정이 env.yaml 과 다름 (또는 기록 없음)"
            if not same_path(meta.get("env_yaml", ""), V2_ENV_YAML):
                return FAIL, f"기준 env.yaml 이 아니다 {meta.get('env_yaml')!r}"
        return PASS, ""

    def a5():
        why = _student_check(A, which, a, d, meta)
        return (FAIL, why) if why else (PASS, "")

    def a6():
        if not a.compare_report:
            return PEND, "compare_native --recompute_action 보고서가 아직 없다 (--compare_report)"
        rep = load_json(a.compare_report)
        if rep is None:
            return FAIL, "보고서를 못 읽음"
        if rep.get("status") != "pass":
            return FAIL, f"보고서 상태 {rep.get('status')!r} first {rep.get('first_failure')}"
        names = {c.get("name"): c for c in rep.get("checks", [])}
        if rep.get("recompute_action") is not True or not all(names.get(x, {}).get("ok") for x in
                                                               ("action.recompute_from_adapter_obs", "action.recompute_from_native_obs")):
            return FAIL, "보고서가 --recompute_action 이 아니다 (또는 재계산 칸 없음)"
        if rep.get("model") != MODEL[which] or rep.get("T") != T or rep.get("N") != N:
            return FAIL, f"보고서 model · T · N {rep.get('model')} {rep.get('T')} {rep.get('N')}"
        inp = rep.get("inputs") or {}
        if not same_path(rep.get("npz", ""), F["npz"]) or inp.get("npz_sha256") != sha(F["npz"]):
            return FAIL, "보고서가 읽은 npz 가 지금 파일과 다름 (비교 뒤 바뀜)"
        if inp.get("meta_sha256") != sha(F["meta"]) or inp.get("signature_sha256") != (sha(F["signature"]) if os.path.isfile(F["signature"]) else "없음"):
            return FAIL, "보고서가 읽은 meta · signature 가 지금 파일과 다름"
        if not same_path(rep.get("checkpoint", ""), a.checkpoint) or rep.get("checkpoint_sha256") != sha(a.checkpoint):
            return FAIL, f"보고서의 체크포인트 {rep.get('checkpoint')!r} 가 이 체크포인트와 다름"
        for p, h in (inp.get("config_sha256") or {}).items():
            if not os.path.isfile(p) or sha(p) != h:
                return FAIL, f"보고서가 읽은 설정 {p} 가 지금과 다름"
        need_cfg = [x for x in (((meta.get("train_yaml") or {}).get("path") if isinstance(meta.get("train_yaml"), dict) else None),
                                meta.get("agent_yaml"), meta.get("env_yaml")) if x]
        have = {os.path.normcase(os.path.abspath(p)) for p in (inp.get("config_sha256") or {})}
        if any(os.path.normcase(os.path.abspath(x)) not in have for x in need_cfg):
            return FAIL, f"보고서 설정 해시에 meta 의 설정 파일이 빠짐 {need_cfg}"
        code = inp.get("code_sha256") or {}
        now = {"adapters.py": sha(os.path.join(HERE, "adapters.py")), "compare_native.py": sha(os.path.join(HERE, "compare_native.py")),
               "cells.py": sha(os.path.join(HERE, "cells.py"))}
        if code != now:
            return FAIL, f"보고서를 만든 코드가 지금과 다름 {sorted(k for k in now if code.get(k) != now[k])}"
        return PASS, ""

    cov = C.coverage_of(d)

    def a7():
        if cov["reset_events"] == 0:
            return PEND, "reset 이 한 번도 없다 · reset 뒤 이력 경로 미확인 (--reset_envs · --reset_step)"
        if cov["post_reset_action_steps"] == 0:
            return PEND, "reset 뒤에 action 이 없다 · reset 뒤 행동 경로 미확인"
        return PASS, ""

    def a8():
        if cov["command_switch_events"] == 0:
            return PEND, "명령 전환이 없다 · 그 경로 미확인 (--switch_env · --switch_step · --switch_cell)"
        if cov["post_switch_action_steps"] == 0:
            return PEND, "전환이 마지막 관측에만 있다 · 바뀐 명령으로 계산한 action 0 개 (17f 4.4)"
        return PASS, ""

    def a9():
        why = provenance_problem(a, run, meta)
        return (FAIL, why) if why else (PASS, "")

    for name, fn in (("A1", a1), ("A2", a2), ("A3", a3), ("A4", a4), ("A5", a5), ("A6", a6), ("A7", a7), ("A8", a8), ("A9", a9)):
        step(name, fn)
    return R, cov


A_IDS = ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9")


def _prov_names(which):
    return ("run_dump.py", "cells.py", "isaac_slot_v3.py", "usd_isolate_run_v3.py", "gpu_guard.py", DUMP_SCRIPT[which], "adapters.py")


def run_provenance(run, meta, which):
    """ASTRA 17f 4.3: 실행 당시 코드 해시. ({이름: sha 또는 None}, provenance 와 옛 칸이 서로 다른 이름, 실행 중 바뀐 이름)."""
    prov = {k: (v or {}).get("sha256") for k, v in (run.get("provenance") or {}).items()}
    cap = run.get("capabilities") or {}
    legacy = {"run_dump.py": run.get("run_dump_sha256"), "cells.py": run.get("cells_sha256"), "isaac_slot_v3.py": cap.get("slot_sha256"),
              "usd_isolate_run_v3.py": cap.get("isolate_sha256"), DUMP_SCRIPT[which]: meta.get("script_sha256"),
              "adapters.py": meta.get("adapters_sha256")}
    end = {k: (v or {}).get("sha256") for k, v in (run.get("provenance_end") or {}).items()}
    out, clash, moved = {}, [], []
    for n in _prov_names(which):
        x, y = prov.get(n), legacy.get(n)
        if x and y and x != y:
            clash.append(n)
        out[n] = x or y
        if x and end and end.get(n) != x:
            moved.append(n)
    return out, clash, moved


def _ref_paths(run, which):
    """승인 대상 코드의 경로 (--code_bundle 이 없을 때 지금 파일을 읽는 곳). run.json provenance 의 경로가 있으면 그것."""
    prov = run.get("provenance") or {}
    cap = run.get("capabilities") or {}
    cmd = [str(x).replace("\\", "/") for x in (run.get("cmd") or [])]
    pick = lambda name: next((x for x in cmd if x.rsplit("/", 1)[-1] == name), None)  # noqa: E731
    ref = {"run_dump.py": os.path.join(HERE, "run_dump.py"), "cells.py": os.path.join(HERE, "cells.py"), "adapters.py": os.path.join(HERE, "adapters.py"),
           "isaac_slot_v3.py": cap.get("slot") or pick("isaac_slot_v3.py"), "usd_isolate_run_v3.py": cap.get("isolate") or pick("usd_isolate_run_v3.py"),
           "gpu_guard.py": pick("gpu_guard.py"), DUMP_SCRIPT[which]: pick(DUMP_SCRIPT[which])}
    for n, v in prov.items():
        if isinstance(v, dict) and v.get("path"):
            ref[n] = v["path"]
    return ref


def read_bundle(path):
    """SHA256SUMS 꼴 (<sha256> [*]<경로>) 을 {파일 이름: sha256} 로."""
    out = {}
    for ln in open(path, encoding="utf-8").read().splitlines():
        parts = ln.strip().split(None, 1)
        if len(parts) == 2 and len(parts[0]) == 64:
            out[parts[1].lstrip("*").replace("\\", "/").rsplit("/", 1)[-1]] = parts[0].lower()
    return out


def provenance_problem(a, run, meta):
    """A9: 실행 당시 해시가 모두 기록돼 있고, 서로 모순이 없고, 실행 중에 안 바뀌었고, 승인 대상 코드 (--code_bundle 의 해시 또는
    지금 파일) 와 같아야 한다. 승인 시점 파일을 해시하는 것만으로 과거 실행의 출처가 입증되지는 않는다 (17f 4.3)."""
    got, clash, moved = run_provenance(run, meta, a.which)
    missing = [n for n, h in got.items() if not h]
    if missing:
        return f"실행 당시 해시 기록 없음 {missing} (출처를 이을 수 없다)"
    if clash:
        return f"run.json provenance 와 옛 해시 칸 (run.json · capabilities · meta) 이 서로 다름 {clash}"
    if moved:
        return f"실행 중 코드가 바뀜 {moved}"
    if getattr(a, "code_bundle", ""):
        ref = read_bundle(a.code_bundle)
        absent = [n for n in got if n not in ref]
        if absent:
            return f"승인 대상 묶음 {a.code_bundle} 에 없는 파일 {absent}"
        diff = [n for n, h in got.items() if ref[n] != h]
    else:
        paths = _ref_paths(run, a.which)
        absent = [n for n in got if not paths.get(n) or not os.path.isfile(paths[n])]
        if absent:
            return f"승인 대상 코드 파일이 없다 {absent}"
        diff = [n for n, h in got.items() if sha(paths[n]) != h]
    if diff:
        return f"실행 당시 코드와 승인 대상 코드가 다름 {diff} (기록을 만든 코드가 아니다)"
    return ""


def stamp_files(a, F, approval=False):
    files = dict(F)
    if approval:
        files["compare_report"] = a.compare_report
        files["checkpoint"] = a.checkpoint
        rep = load_json(a.compare_report) or {}
        for i, p in enumerate(sorted((rep.get("inputs") or {}).get("config_sha256") or {})):
            files[f"config_{i}"] = p
        for n in ("adapters.py", "compare_native.py", "cells.py", "validate_dump.py", "run_dump.py", DUMP_SCRIPT[a.which]):
            files[f"code_{n}"] = os.path.join(HERE, n)
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(allow_abbrev=False)
    ap.add_argument("--which", choices=["cts", "v2"], required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--attempt", required=True)
    ap.add_argument("--stamp", action="store_true")
    ap.add_argument("--approve", action="store_true")
    ap.add_argument("--compare_report", default="")
    ap.add_argument("--check_approval", action="store_true")
    ap.add_argument("--code_bundle", default="", help="승인 대상 코드 묶음 (SHA256SUMS 꼴). 없으면 지금 파일과 대조")
    ap.add_argument("--allow_overrides", action="store_true", help="시험 전용")
    a = ap.parse_args(argv)
    F = files_of(a.which, a.tag, a.attempt)
    if a.check_approval:
        st = load_json(f"{NATIVE}/{a.tag}/approval_stamp.json")
        if st is None or st.get("kind") != "approval":
            print(f"APPROVAL INVALID {a.tag}: approval_stamp.json 없음")
            return 1
        tg = st.get("target") or {}
        want = {"which": a.which, "tag": a.tag, "attempt": a.attempt}
        bad = [k for k, v in want.items() if tg.get(k) != v]
        if not os.path.isfile(a.checkpoint) or not same_path(tg.get("checkpoint", ""), a.checkpoint) \
                or tg.get("checkpoint_sha256") != sha(a.checkpoint):
            bad.append("checkpoint")
        if bad:  # 17f 4.2: 다른 모델 · 체크포인트 · tag · attempt 를 물으면 그 승인으로 답하지 않는다
            print(f"APPROVAL INVALID {a.tag}: 승인 당시 대상과 요청이 다름 {bad} (승인 대상 {tg})")
            return 1
        changed = [k for k, (p, h) in st["files"].items() if not os.path.isfile(p) or sha(p) != h]
        if changed:
            print(f"APPROVAL INVALID {a.tag}: 승인 뒤 바뀐 파일 {changed}")
            return 1
        print(f"APPROVAL STILL VALID {a.tag} attempt {a.attempt}")
        return 0
    R = collect(a)
    for name, stt, detail in R:
        print(f"{stt} {name}{'' if stt == PASS else ' ' + detail[:300]}")
    collected = all(x[1] == PASS for x in R)
    print(f"{'COLLECTED' if collected else 'INVALID'} {a.tag} attempt {a.attempt}")
    if collected and a.stamp:
        files = stamp_files(a, F)
        miss = [k for k, p in files.items() if not os.path.isfile(p)]
        if miss:
            print(f"STAMP REFUSED: 파일이 없다 {miss} (해시 목록에서 빼지 않는다)")
            return 1
        json.dump({"kind": "collection", "attempt": a.attempt, "which": a.which, "tag": a.tag, "checks": [x[0] for x in R],
                   "files": {k: [p, sha(p)] for k, p in files.items()}, "validator_sha256": sha(os.path.abspath(__file__)),
                   "t": time.strftime("%Y-%m-%d %H:%M:%S")}, open(f"{NATIVE}/{a.tag}/validate_stamp.json", "w", encoding="utf-8"), indent=1)
    if not a.approve:
        return 0 if collected else 1
    RA, cov = approve(a, F)
    for name, stt, detail in RA:
        print(f"{stt} {name}{'' if stt == PASS else ' ' + detail[:300]}")
    print("coverage " + json.dumps({k: cov.get(k) for k in ("reset_events", "post_reset_action_steps", "command_switch_events",
                                                           "post_switch_action_steps", "ray_miss_count")}, ensure_ascii=False)
          + (" · 미확인 경로 " + ", ".join(cov["unverified_paths"]) if cov["unverified_paths"] else ""))
    if not collected or any(x[1] == FAIL for x in RA):
        print(f"REJECTED {a.tag} attempt {a.attempt}{' (수집 실패)' if not collected else ''}")
        return 1
    if any(x[1] == PEND for x in RA):
        print(f"PENDING {a.tag} attempt {a.attempt}: {[x[0] for x in RA if x[1] == PEND]}")
        return 3
    files = stamp_files(a, F, approval=True)
    miss = [k for k, p in files.items() if not os.path.isfile(p)]
    if miss:
        print(f"REJECTED {a.tag}: 승인 stamp 에 넣을 파일이 없다 {miss}")
        return 1
    run = load_json(F["run"]) or {}
    meta = load_json(F["meta"]) or {}
    rep = load_json(a.compare_report) or {}
    json.dump({"kind": "approval", "attempt": a.attempt, "which": a.which, "tag": a.tag,
               "target": {"which": a.which, "tag": a.tag, "attempt": a.attempt, "checkpoint": os.path.abspath(a.checkpoint).replace("\\", "/"),
                          "checkpoint_sha256": sha(a.checkpoint), "model": MODEL[a.which]},
               "run_provenance": run_provenance(run, meta, a.which)[0],
               "compare_provenance": (rep.get("inputs") or {}).get("code_sha256"),
               "code_bundle": {"path": a.code_bundle, "sha256": sha(a.code_bundle)} if a.code_bundle else None,
               "checks": [x[0] for x in R + RA],
               "coverage": cov, "files": {k: [p, sha(p)] for k, p in files.items()}, "t": time.strftime("%Y-%m-%d %H:%M:%S")},
              open(f"{NATIVE}/{a.tag}/approval_stamp.json", "w", encoding="utf-8"), indent=1)
    print(f"APPROVED {a.tag} attempt {a.attempt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
