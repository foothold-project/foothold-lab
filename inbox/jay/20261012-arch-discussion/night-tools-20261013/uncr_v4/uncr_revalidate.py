# CMD-R 미경험 진단 수집본 재검사기 v1 (lead 하위 작업 · 2026-10-13 밤 · CPU 만 · ASTRA 17c §2.4 P1 · §5 · §6 「수정한 CPU 검증기로
# 동결 묶음 재검사」). 수집 코드 (unseen_driver_cmdr.py v3 · q_eval_cmdr.py · q_post.py · q_metrics.py) 는 고치지 않고 읽기만 한다.
#   입력: out_uncr 의 실행 폴더 (<tag>/ · <tag>.log · .guard.json · .slot.json · usd/<tag>-<attempt>/assigned.jsonl). 읽기만 한다.
#   출력: out_uncr_reval/<시각>/revalidate.json 에만 쓴다. 입력 루트 안에는 쓰지 않는다 (write_report 가 거부).
#         q_post 재계산은 시스템 임시 폴더에서 하고 지운다.
#   동결: 입력 파일마다 바이트를 한 번 읽어 그 바이트로 해시와 해석을 같이 한다. 끝에 모든 입력을 다시 해시해 대조한다.
#   채널 (q_eval_cmdr.py:566~575 snap · 559~563 ground_z): traj 는 [T_steps+1, N, 12].
#     0~2 root_pos_w · 3 heading_w · 4~6 root_lin_vel_b · 7~9 root_ang_vel_b · 10 projected_gravity_b z ·
#     11 몸통 z 에서 height_scanner_small ray hit z 의 nanmean 을 뺀 값 (ray 가 하나도 안 맞으면 NaN).
#   판정 구간 (episode 마다): 상태 0 부터, 살아남았으면 J = round(20 s / 0.02) = 1000 까지, 낙상했으면 낙상 상태 직전까지.
#     낙상 상태는 episodes.csv 의 fall_t (n50) 와 span_fall_t 중 늦은 쪽 (두 시간 정의의 합집합). term 과 대조한다.
#   판정 (실행):
#     invalid: 기록 결함 · 측정 무효. 파일 없음 · stamp 이후 변경 · slot · guard · log · USD 격리 기록 · 평가 인자 · 체크포인트 ·
#              checks_run · checks_pre · traj 모양 · term · epi · fam · cel · env 대응 (음수 · 중복 · 범위 · 시작 위치) · term 과
#              episode 대응 · 판정 구간의 필수 채널 0~10 비유한 · 지문 형식 · 검사 중 입력 변경.
#     hold: 측정은 있으나 사람이 봐야 한다. 판정 구간 안의 채널 11 NaN (below_support 규칙을 그 표본에서 못 봄) · 판정 구간 뒤
#           필수 채널 비유한 · stamp 의 수집 코드와 지금 파일이 다름 · 지금 q_post 로 다시 만든 episodes.csv · cells.json 이 저장본과 다름 ·
#           학습 yaml 해시가 수집 때와 다름.
#     valid: 위 둘에 해당 없음. 판정 구간 뒤 채널 11 NaN 은 허용하고 따로 센다 (ASTRA 17c §1 · uncr_on_gap_fwd05 env 50 NaN 193).
#   판정 (칸): 셋 (par · off · on) 이 다 있고 다 valid 이고, 지문 네 항목 · env_origins.npy · traj[0] · 수집 코드 해시가 셋 사이 같아야
#     valid. invalid 실행이 있으면 invalid · 빠진 실행이 있으면 incomplete · 짝이 다르거나 hold 실행이 있으면 hold.
#   출처: stamp 의 code_sha256 은 수집 당시 기록을 그대로 적고 (덮어쓰지 않음) 지금 파일 해시를 옆에 적는다. q_post.py 는 v3 stamp 에
#     없으므로 「출처 미확인」 으로 적고, 지금 q_post 로 다시 만든 결과와의 바이트 대조를 따로 적는다 (등가 확인이지 출처 증명이 아님).
#   이유 문자열은 [코드] 로 시작한다 (시험 · 변이 시험이 코드로 대조).
# 사용: python uncr_revalidate.py [--root out_uncr] [--out_base out_uncr_reval] [--no_write]
#   종료 코드: 0 diag 7 칸 모두 valid · 1 아님 · 2 검사 중 입력이 바뀜.
import argparse
import csv
import gc
import hashlib
import importlib.util
import io
import json
import math
import os
import re
import shutil
import sys
import tempfile
import time
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = "uncr-reval-1"
DEFAULT_ROOT = os.path.join(HERE, "out_uncr")
DEFAULT_OUT = os.path.join(HERE, "out_uncr_reval")

# collection contract: the same values as unseen_driver_cmdr.py v3 lines 36~48
E1 = "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192"
TRAIN_YAML = f"{E1}/params/env.yaml"
BR = os.path.join(HERE, "out", "branch")
MODELS = {"par": {"ckpt": f"{E1}/model_20000.pt", "iter": 20000, "yaml": ""},
          "off": {"ckpt": os.path.join(BR, "cmdr_s1042_off_u4000", "model_24000.pt").replace("\\", "/"), "iter": 24000, "yaml": TRAIN_YAML},
          "on": {"ckpt": os.path.join(BR, "cmdr_s1042_on_u4000", "model_24000.pt").replace("\\", "/"), "iter": 24000, "yaml": TRAIN_YAML}}
TERRAINS = ["discrete_obstacles", "wave", "stepping_stones", "gap", "pit", "rails", "star", "floating_ring", "repeated_boxes", "repeated_cylinders"]
DIAG = [("gap", "fwd05"), ("stepping_stones", "fwd05"), ("floating_ring", "fwd05"), ("rails", "fwd05"), ("wave", "fwd05"),
        ("gap", "back03"), ("discrete_obstacles", "back03")]
FULL = [(t, c) for c in ("fwd05", "fwd03", "fwd10") for t in TERRAINS]
MANIFEST = DIAG + [c for c in FULL if c not in DIAG]
EPISODES, EVAL_SEED, DIFF = 100, 1000, 0.5
WANT_ARGS = {"terrain_set": "unseen10", "episodes": EPISODES, "eval_seed": EVAL_SEED, "obs_noise": False, "full_record": False,
             "policy": "student", "difficulty": DIFF}
DT = 0.02                                                                  # q_metrics.DT
CELL_S = {"fwd03": 20.0, "fwd05": 20.0, "fwd10": 20.0, "back03": 20.0}   # q_eval_cmdr.py:97~100 duration_s
SPAWN_ROWS = 8                                                             # q_eval_cmdr.py:112
RESET_XY_M = 0.5                                                           # q_eval_cmdr.py:244~246 reset_base xy +-0.5 m
NCH = 12
CHANNELS = {0: "root_pos_w x", 1: "root_pos_w y", 2: "root_pos_w z", 3: "heading_w", 4: "root_lin_vel_b x", 5: "root_lin_vel_b y",
            6: "root_lin_vel_b z", 7: "root_ang_vel_b x", 8: "root_ang_vel_b y", 9: "root_ang_vel_b z", 10: "projected_gravity_b z",
            11: "base z minus nanmean of height_scanner_small ray hit z (NaN when no ray hits)"}
REQUIRED_CH = tuple(range(11))
GROUND_CH = 11
COLLECT_CODE = ("q_eval_cmdr.py", "q_metrics.py", "isaac_slot.py", "usd_isolate_run.py", "gpu_guard.py")
POST_CODE = "q_post.py"
DATA_CODE = COLLECT_CODE + (POST_CODE,)
NOTE_CODE = ("unseen_driver_cmdr.py", "unseen_driver_cmdr_v4.py", "uncr_revalidate.py")
PAIR_KEYS = ("terrain_mesh", "terrain_origins_sha256", "pairing_sha256", "pairing_sha256_ext")
PAIRING_REQ = ("init_root_pose", "init_joint_pos", "body_masses", "joint_stiffness")          # q_eval_cmdr.py:420~425
EXT_REQ = ("com", "material_static_dynamic_restitution", "motor_zero_offset")                 # q_eval_cmdr.py:432~454
HEX64 = re.compile(r"[0-9a-f]{64}")
EMPTY_SHA = hashlib.sha256(b"").hexdigest()   # sha256_arr of an empty array
RUN_FILES = ("meta.json", "cells.json", "episodes.csv", "traj.npz", "env_origins.npy")
SIDE_FILES = (".log", ".guard.json", ".slot.json")
STAMP = "driver_stamp.json"
TRAJ0_TOL = 1e-5
TAG_RX = re.compile(r"uncr_(par|off|on)_([a-z_]+)_((?:fwd|back)\d\d)")
USD_RX = re.compile(r"([^\s@\"'<>|=]*?)[/\\]IsaacLab[/\\]usd_(\d{8}_\d{6}_\d+)")
CSV_NEED = ("family", "cell", "episode", "env", "survived", "fall_reason", "fall_t", "span_survived", "span_fall_reason", "span_fall_t")
NPZ_NEED = ("traj", "term", "cel", "fam", "epi", "cmd_a", "cmd_b", "sw", "act_abs_mean")
WINDOW_DOC = ("per episode: states 0..J (J = round(duration_s / DT) = 1000) when it survived, else 0..j_fall-1 where j_fall is the later of "
              "fall_t and span_fall_t (episodes.csv) divided by DT; j_fall must not come after the first term flag and equals it for base_contact")


def norm(p):
    return os.path.normcase(os.path.abspath(p)).replace("\\", "/")


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def is_hash(v):
    return isinstance(v, str) and HEX64.fullmatch(v) is not None and v != EMPTY_SHA


def canon(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


class Reader:
    """Every input is read once as bytes; its hash and its parse use the same bytes. recheck() hashes every file again."""

    def __init__(self, root):
        self.root = norm(root)
        self.inputs = {}
        self.paths = {}
        self.ext = {}

    def key(self, path):
        p = norm(path)
        return p[len(self.root) + 1:] if p.startswith(self.root + "/") else "abs:" + p

    def read(self, path):
        with open(path, "rb") as f:
            b = f.read()
        k = self.key(path)
        self.inputs[k] = sha_bytes(b)
        self.paths[k] = path
        return b

    def ext_sha(self, name, path):
        try:
            s = sha_file(path)
        except OSError:
            s = None
        self.ext[name] = {"path": path, "sha256": s}
        return s

    def recheck(self):
        out = []
        for k, p in self.paths.items():
            try:
                s = sha_file(p)
            except OSError:
                s = None
            if s != self.inputs[k]:
                out.append(k)
        for k, v in self.ext.items():
            try:
                s = sha_file(v["path"])
            except OSError:
                s = None
            if s != v["sha256"]:
                out.append("ext:" + k)
        return sorted(out)


_QPOST = {}


def q_post_module():
    if "m" not in _QPOST:
        p = os.path.join(HERE, "q_post.py")
        spec = importlib.util.spec_from_file_location("q_post_for_reval", p)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _QPOST["m"] = m
        _QPOST["sha256_at_load"] = sha_file(p)
    return _QPOST["m"]


def fp_problems(meta):
    """17c 2.4: the fingerprints must have the evaluator's own form before they are compared."""
    out = []
    tm = meta.get("terrain_mesh")
    if not isinstance(tm, list) or not tm:
        out.append(f"terrain_mesh is not a non-empty mesh list: {str(tm)[:60]!r}")
    else:
        for x in tm:
            if not (isinstance(x, list) and len(x) == 3 and isinstance(x[0], str) and x[0].startswith("/World/ground")
                    and isinstance(x[1], int) and not isinstance(x[1], bool) and x[1] > 0 and is_hash(x[2])):
                out.append(f"terrain_mesh entry malformed: {str(x)[:80]!r}")
    if not is_hash(meta.get("terrain_origins_sha256")):
        out.append(f"terrain_origins_sha256 is not a 64-hex hash of data: {str(meta.get('terrain_origins_sha256'))[:70]!r}")
    for k, req in (("pairing_sha256", PAIRING_REQ), ("pairing_sha256_ext", EXT_REQ)):
        d = meta.get(k)
        if not isinstance(d, dict) or not d:
            out.append(f"{k} is empty or not a dict: {str(d)[:40]!r}")
            continue
        miss = [r for r in req if r not in d]
        if k == "pairing_sha256_ext":
            for suf in ("_stiffness", "_damping"):
                if not any(str(x).startswith("actuator_") and str(x).endswith(suf) for x in d):
                    miss.append(f"actuator_*{suf}")
        if miss:
            out.append(f"{k} missing keys {miss}")
        badv = [x for x, v in d.items() if not is_hash(v)]
        if badv:
            out.append(f"{k} values are not 64-hex hashes of data: {badv[:6]}")
    return out


def _fall_j(sv, ft):
    if sv == "True":
        return None
    v = float(ft)
    if not math.isfinite(v):
        raise ValueError(f"fall_t {ft!r}")
    j = int(round(v / DT))
    if abs(j * DT - v) > 1e-6:
        raise ValueError(f"fall_t {ft!r} is not on the {DT} s grid")
    return j


def check_run(root, tag, rd, ckpt_sha, yaml_sha, code_now, require_stamp=True, attempt_prefix=None):
    res = {"tag": tag, "verdict": "invalid", "invalid": [], "hold": [], "notes": []}
    bad, hold, note = res["invalid"].append, res["hold"].append, res["notes"].append
    before = set(rd.inputs)

    def done():
        res["inputs"] = {k: rd.inputs[k] for k in sorted(set(rd.inputs) - before)}
        res["verdict"] = "invalid" if res["invalid"] else "hold" if res["hold"] else "valid"
        return res

    mt = TAG_RX.fullmatch(tag)
    if not mt or mt.group(2) not in TERRAINS or mt.group(3) not in CELL_S:
        bad(f"[tag] not a run name of this driver: {tag}")
        return done()
    m, fam, cell = mt.group(1), mt.group(2), mt.group(3)
    res.update(model=m, family=fam, cell=cell)
    spec = MODELS[m]
    d = os.path.join(root, tag)
    try:
        b = {}
        for f in RUN_FILES:
            b[f] = rd.read(os.path.join(d, f))
        for e in SIDE_FILES:
            b[e] = rd.read(os.path.join(root, f"{tag}{e}"))
    except FileNotFoundError as ex:
        bad(f"[missing] {ex.filename}")
        return done()
    try:
        _check_body(root, tag, m, fam, cell, spec, b, rd, ckpt_sha, yaml_sha, code_now, require_stamp, attempt_prefix, res, bad, hold, note)
    except Exception as ex:  # noqa: BLE001
        bad(f"[unreadable] {type(ex).__name__}: {str(ex)[:200]}")
    return done()


def _check_body(root, tag, m, fam, cell, spec, b, rd, ckpt_sha, yaml_sha, code_now, require_stamp, attempt_prefix, res, bad, hold, note):
    d = os.path.join(root, tag)
    # --- stamp: out hashes against the frozen bytes; collection code recorded as it was, next to the files now
    st = None
    sp = os.path.join(d, STAMP)
    if os.path.exists(sp):
        st = json.loads(rd.read(sp).decode("utf-8"))
        want = {f: sha_bytes(b[f]) for f in RUN_FILES}
        want.update({e: sha_bytes(b[e]) for e in SIDE_FILES})
        got = st.get("out_sha256") or {}
        diff = [k for k in want if got.get(k) != want[k]]
        if diff:
            bad(f"[stamp-out] files differ from the stamp (changed after it): {diff}")
        code = st.get("code_sha256") or {}
        res["code_at_collection"] = code
        res["code_now"] = {f: code_now.get(f) for f in sorted(set(code) | set(DATA_CODE))}
        changed = [f for f in DATA_CODE if f in code and code[f] != code_now.get(f)]
        if changed:
            hold(f"[stamp-code] collection code differs from the files now: {changed}")
        other = [f for f in code if f not in DATA_CODE and code[f] != code_now.get(f)]
        if other:
            note(f"driver or checker code differs from the files now (not data code): {other}")
        if not all(f in code for f in COLLECT_CODE):
            bad(f"[stamp-code] stamp lacks collection code hashes: {[f for f in COLLECT_CODE if f not in code]}")
        res["q_post"] = {"in_stamp": POST_CODE in code,
                         "provenance": ("stamp 기록: " + code[POST_CODE]) if POST_CODE in code else
                         "출처 미확인: 수집 stamp 에 q_post.py 해시가 없음 (지금 q_post 로 다시 만든 결과와의 바이트 대조만 아래에 적음)",
                         "sha256_now": code_now.get(POST_CODE)}
        res["attempt"] = st.get("attempt")
        res["stamp_t"] = st.get("t")
    elif require_stamp:
        bad("[stamp-missing] no driver_stamp.json")
    # --- slot, guard, log, USD isolation records
    s = json.loads(b[".slot.json"].decode("utf-8"))
    att = s.get("attempt", "")
    res["slot_attempt"] = att
    if st is not None and st.get("attempt") != att:
        bad(f"[slot] slot attempt {att!r} is not the stamp attempt {st.get('attempt')!r}")
    if attempt_prefix and not str(att).startswith(attempt_prefix):
        bad(f"[slot] slot attempt {att!r} is not of {attempt_prefix!r}")
    if s.get("slot_rc") != 0 or s.get("child_rc") != 0 or s.get("state_at_release") != "scene_built":
        bad(f"[slot] rc {s.get('slot_rc')} child {s.get('child_rc')} state {s.get('state_at_release')}")
    if not isinstance(s.get("usd_final"), list) or len(s["usd_final"]) != 1 or s.get("usd_outside_root") or s.get("conflicts"):
        bad(f"[slot] usd {s.get('usd_final')} outside {s.get('usd_outside_root')} conflicts {s.get('conflicts')}")
    cmd = [str(x).replace("\\", "/") for x in s.get("cmd", [])]
    if not any(x.endswith("usd_isolate_run.py") for x in cmd) or not any(x.endswith("q_eval_cmdr.py") for x in cmd) \
            or "--tag" not in cmd or cmd[cmd.index("--tag") + 1] != tag:
        bad("[slot] cmd is not usd_isolate_run.py q_eval_cmdr.py --tag <this tag>")
    usd_root = norm(s.get("usd_root") or "")
    res["usd_root"] = usd_root
    if not usd_root.startswith(norm(root) + "/usd/") or usd_root.rsplit("/", 1)[-1] != os.path.normcase(f"{tag}-{att}"):
        bad(f"[usd-path] slot usd_root is not <root>/usd/<tag>-<attempt>: {usd_root}")
    keys_asg = set()
    try:
        lines = [json.loads(x) for x in rd.read(os.path.join(usd_root, "assigned.jsonl")).decode("utf-8").splitlines() if x.strip()]
    except FileNotFoundError:
        lines = []
    if not lines:
        bad("[usd-path] no assigned.jsonl record in the run's USD root")
    for r in lines:
        ud = norm(r.get("usd_dir") or "")
        if not ud.startswith(usd_root + "/isaaclab/usd_") or not r.get("patched_by"):
            bad(f"[usd-path] assigned usd_dir outside the run's root or not patched: {ud} {r.get('patched_by')!r}")
        keys_asg.add(ud.rsplit("/usd_", 1)[-1])
    res["usd_assigned"] = sorted(norm(r.get("usd_dir") or "") for r in lines)
    ist = os.path.join(usd_root, "isolate_state.json")
    if os.path.exists(ist):
        res["isolate_patched_by"] = json.loads(rd.read(ist).decode("utf-8")).get("patched_by")
    else:
        note("no isolate_state.json in the run's USD root")
    g = json.loads(b[".guard.json"].decode("utf-8"))
    if g.get("exit_code") != 0 or g.get("stopped_by_guard"):
        bad(f"[guard] exit {g.get('exit_code')} stopped {g.get('stopped_by_guard')}")
    log = b[".log"].decode("utf-8", errors="replace")
    if "Traceback (most recent call last)" in log or "</World/envs/env_0/Robot>: Unresolved reference" in log:
        bad("[log] Traceback or robot root reference failure")
    if f"[Q-EVAL] done {tag} N {EPISODES} " not in log or "Time taken for scene creation" not in log:
        bad("[log] no scene line or no completion line for this tag and N")
    found = USD_RX.findall(log)
    outside = sorted({norm(p) if p else "<none>" for p, _ in found} - {usd_root})
    if not found:
        bad("[usd-path] the log names no USD folder")
    if outside:
        bad(f"[usd-path] the log names USD paths outside this run's root: {outside[:3]}")
    keys_log = {k for _, k in found}
    if found and not (keys_log == set(s.get("usd_final") or []) == keys_asg):
        bad(f"[usd-path] USD folders differ: log {sorted(keys_log)} slot {s.get('usd_final')} assigned {sorted(keys_asg)}")
    unres = sum(1 for ln in log.splitlines() if "Unresolved reference" in ln)
    if unres:
        note(f"{unres} unresolved reference lines in the log (not the robot root; visual assets not approved by this check)")
    # --- meta: evaluation arguments, checkpoint, checks
    meta = json.loads(b["meta.json"].decode("utf-8"))
    a = meta.get("args") or {}
    want = dict(WANT_ARGS, families=fam, cells=cell, tag=tag)
    for k, v in want.items():
        if a.get(k) != v:
            bad(f"[args] {k}={a.get(k)!r} want {v!r}")
    if norm(a.get("checkpoint") or "") != norm(spec["ckpt"]):
        bad(f"[args] checkpoint {a.get('checkpoint')!r}")
    if norm(a.get("outdir") or "") != norm(root):
        bad(f"[args] outdir {a.get('outdir')!r}")
    if ckpt_sha.get(m) is None or meta.get("checkpoint_sha256") != ckpt_sha.get(m) or meta.get("loaded_iter") != spec["iter"]:
        bad(f"[ckpt] checkpoint_sha256 / loaded_iter differ from the checkpoint file now ({meta.get('loaded_iter')})")
    if spec["yaml"]:
        ys = meta.get("train_yaml_source") or {}
        if norm(ys.get("train_yaml") or "") != norm(spec["yaml"]):
            bad("[args] train_yaml_source")
        elif ys.get("train_yaml_sha256") != yaml_sha:
            hold("[yaml] train yaml sha256 differs from the file now")
    cr, cp = meta.get("checks_run") or {}, meta.get("checks_pre") or {}
    if cr.get("nonfinite_action_or_obs_count") != 0:
        bad(f"[checks] nonfinite action or obs {cr.get('nonfinite_action_or_obs_count')}")
    if cr.get("obs_single_cmd_vs_target_max_abs") != 0.0 or cr.get("obs_history_latest_cmd_vs_target_max_abs") != 0.0:
        bad("[checks] command did not reach the observation exactly")
    if cp.get("manual_student_path_vs_act_inference_max_abs") != 0.0 or cp.get("teacher_input_randomized_max_abs_action_change") != 0.0:
        bad("[checks] checks_pre: student path or teacher independence")
    T = int(round(CELL_S[cell] / DT))
    N = EPISODES
    cl = meta.get("cells") or []
    if meta.get("N") != N or meta.get("T_steps") != T or meta.get("families") != [fam] or len(cl) != 1 or cl[0].get("name") != cell \
            or cl[0].get("duration_s") != CELL_S[cell]:
        bad(f"[meta] N {meta.get('N')} T_steps {meta.get('T_steps')} families {meta.get('families')} cells {[c.get('name') for c in cl]}")
    oz = (meta.get("obstacle_zone_m") or {}).get(fam)
    if not (isinstance(oz, list) and len(oz) == 3 and isinstance(oz[1], (int, float)) and math.isfinite(oz[1]) and oz[1] > 0):
        bad(f"[meta] obstacle_zone_m[{fam}] {oz!r}")
        return
    ze = float(oz[1])
    fpp = fp_problems(meta)
    for x in fpp:
        bad("[fp-form] " + x)
    res["_fp"] = {k: canon(meta.get(k)) for k in PAIR_KEYS}
    res["_fp_raw"] = {k: meta.get(k) for k in PAIR_KEYS}
    c = json.loads(b["cells.json"].decode("utf-8"))
    if not (isinstance(c, list) and len(c) == 1 and c[0].get("n") == N and c[0].get("family") == fam and c[0].get("cell") == cell):
        bad("[cells] cells.json is not one row of this family / cell with n 100")
    # --- arrays
    with np.load(io.BytesIO(b["traj.npz"]), allow_pickle=False) as z:
        miss = [k for k in NPZ_NEED if k not in z.files]
        if miss:
            bad(f"[traj-shape] traj.npz lacks {miss}")
            return
        tr, term, epi, fa, ce = z["traj"], z["term"], z["epi"], z["fam"], z["cel"]
    if tr.shape != (T + 1, N, NCH) or tr.dtype != np.float32:
        bad(f"[traj-shape] traj {tr.shape} {tr.dtype}, want {(T + 1, N, NCH)} float32")
        return
    if term.shape != (T + 1, N) or term.dtype != np.bool_ or term[0].any():
        bad(f"[term] term {term.shape} {term.dtype} or set at state 0")
        return
    if any(x.shape != (N,) or x.dtype.kind not in "iu" for x in (epi, fa, ce)):
        bad("[env-map] epi / fam / cel shape or type")
        return
    if (fa != 0).any() or (ce != 0).any() or not np.array_equal(epi, np.arange(N) % EPISODES):
        bad("[env-map] fam / cel / epi are not this one family / cell / episode order")
        return
    org = np.load(io.BytesIO(b["env_origins.npy"]), allow_pickle=False)
    if org.shape != (N, 3) or not np.isfinite(org).all():
        bad(f"[env-map] env_origins {org.shape} or nonfinite")
        return
    for k in range(SPAWN_ROWS):
        rows_k = org[epi % SPAWN_ROWS == k]
        if rows_k.size and not (rows_k == rows_k[0]).all():
            bad(f"[env-map] env_origins differ inside start row {k}")
            return
    t0 = tr[0, :, 0:2]
    fin = np.isfinite(t0).all(axis=1)  # a nonfinite start is left to the judgement window check below (state 0 is always in it)
    dxy = float(np.abs(t0[fin] - org[fin, 0:2]).max()) if fin.any() else 0.0
    if dxy > RESET_XY_M + 0.01:
        bad(f"[env-map] traj start is {dxy:.3f} m from its env origin (reset range {RESET_XY_M} m)")
    res["_traj0"] = tr[0].copy()
    res["_origins_sha"] = sha_bytes(b["env_origins.npy"])
    # --- episodes.csv: env correspondence
    rows = list(csv.DictReader(io.StringIO(b["episodes.csv"].decode("utf-8"))))
    if not rows or any(k not in rows[0] for k in CSV_NEED):
        bad(f"[csv] episodes.csv columns lack {[k for k in CSV_NEED if not rows or k not in rows[0]]}")
        return
    envs = [int(r["env"]) for r in rows]
    neg = [e for e in envs if e < 0]
    if neg:
        bad(f"[env-negative] negative env index {neg[:5]}")
    if len(rows) != N or sorted(envs) != list(range(N)):
        bad(f"[env-set] episodes.csv env column is not 0..{N - 1} once each ({len(rows)} rows)")
    if res["invalid"]:
        return
    for r, e in zip(rows, envs):
        if int(r["episode"]) != int(epi[e]) or r["family"] != fam or r["cell"] != cell:
            bad(f"[env-episode] env {e}: episode {r['episode']} family {r['family']} cell {r['cell']}")
            return
    # --- term vs episode, judgement window, channels
    J = T
    n = surv = cross = alive_cross = 0
    g_after, g_after_envs, g_in, g_in_envs, req_after = 0, [], 0, [], 0
    first_bad = None
    for r, e in zip(rows, envs):
        tt = np.nonzero(term[1:J + 1, e])[0]
        first = int(tt[0]) + 1 if tt.size else None
        ends = []
        for sv, ft, why in ((r["survived"], r["fall_t"], r["fall_reason"]), (r["span_survived"], r["span_fall_t"], r["span_fall_reason"])):
            if sv not in ("True", "False"):
                bad(f"[term-episode] env {e}: survived {sv!r}")
                return
            jf = _fall_j(sv, ft)
            if jf is None:
                if first is not None:
                    bad(f"[term-episode] env {e} is marked survived but term is set at state {first}")
                    return
                ends.append(J)
                continue
            if not 0 <= jf <= J or (first is not None and jf > first) or (why == "base_contact" and jf != first):
                bad(f"[term-episode] env {e}: fall state {jf} ({why}) vs first term {first}")
                return
            ends.append(jf - 1)
        jw = max(max(ends), 0)  # state 0 is always read (crossing uses it even for a fall at state 0)
        reqw = tr[:jw + 1, e, 0:11]
        nf = ~np.isfinite(reqw)
        if nf.any():
            if first_bad is None:
                j0, c0 = map(int, np.argwhere(nf)[0])
                first_bad = (e, j0, c0, int(nf.sum()))
        gi = int((~np.isfinite(tr[:jw + 1, e, GROUND_CH])).sum())
        if gi:
            g_in += gi
            g_in_envs.append(e)
        ga = int((~np.isfinite(tr[jw + 1:, e, GROUND_CH])).sum())
        if ga:
            g_after += ga
            g_after_envs.append(e)
        req_after += int((~np.isfinite(tr[jw + 1:, e, 0:11])).sum())
        s_n50 = r["survived"] == "True"
        jc = J if s_n50 else max(0, int(round(float(r["fall_t"]) / DT)) - 1)
        if not nf.any():
            cc = bool(np.max(tr[:jc + 1, e, 0] - org[e, 0]) >= ze)
            n += 1
            surv += s_n50
            cross += cc
            alive_cross += cc and s_n50
    if first_bad:
        e, j0, c0, cnt = first_bad
        bad(f"[window-required] required channel nonfinite inside the judgement window: first env {e} state {j0} channel {c0} "
            f"({CHANNELS[c0]}), {cnt} values in that env")
        return
    if g_in:
        hold(f"[ground-in-window] channel 11 NaN inside the judgement window: {g_in} values, envs {g_in_envs[:10]} "
             "(below_support cannot be judged at those states)")
    if req_after:
        hold(f"[after-window-required] required channels nonfinite after the judgement window: {req_after} values")
    res["nan"] = {"ground_ch11_after_window": g_after, "ground_ch11_after_window_envs": g_after_envs,
                  "ground_ch11_in_window": g_in, "required_after_window": req_after}
    res["stats"] = {"n": n, "surv": surv, "cross": cross, "alive_cross": alive_cross, "zone_end": round(ze, 3)}
    # --- post-processing re-run with the q_post on disk now, on the frozen bytes
    td = tempfile.mkdtemp(prefix="uncr_reval_post_")
    eq, err = {}, ""
    try:
        for f in ("meta.json", "traj.npz"):
            with open(os.path.join(td, f), "wb") as fh:
                fh.write(b[f])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            q_post_module().postprocess(td)
        for f in ("episodes.csv", "cells.json"):
            with open(os.path.join(td, f), "rb") as fh:
                eq[f] = fh.read() == b[f]
    except Exception as ex:  # noqa: BLE001  (q_post keeps traj.npz open on an exception; the handle is freed below)
        err = f"{type(ex).__name__}: {str(ex)[:160]}"
    gc.collect()
    shutil.rmtree(td, ignore_errors=True)
    res.setdefault("q_post", {})["recompute_equal"] = eq
    res["q_post"]["sha256_used"] = _QPOST.get("sha256_at_load")
    if err:
        hold(f"[post-recompute] q_post on disk now fails on the frozen bytes: {err}")
    elif not all(eq.values()):
        hold(f"[post-recompute] q_post on disk now gives other bytes for {[f for f, v in eq.items() if not v]}")


def find_tags(root):
    if not os.path.isdir(root):
        return []
    names = set()
    for n in os.listdir(root):
        p = os.path.join(root, n)
        if os.path.isdir(p) and TAG_RX.fullmatch(n):
            names.add(n)
        for ext in SIDE_FILES:
            if n.endswith(ext) and TAG_RX.fullmatch(n[: -len(ext)]):
                names.add(n[: -len(ext)])
    return sorted(names)


def traj0_diff(a, b):
    """max abs difference of two initial states; NaN at the same place counts as equal, NaN on one side as infinite."""
    na, nb = np.isnan(a), np.isnan(b)
    if a.shape != b.shape or (na != nb).any():
        return float("inf")
    d = np.abs(np.where(na, 0.0, a) - np.where(nb, 0.0, b))
    return float(d.max()) if d.size else 0.0


def cell_verdict(fam, cell, runs):
    key = f"{fam}/{cell}"
    trio = {m: runs.get(f"uncr_{m}_{fam}_{cell}") for m in MODELS}
    present = [m for m, r in trio.items() if r]
    missing = [m for m in MODELS if m not in present]
    inv = [m for m in present if trio[m]["verdict"] == "invalid"]
    hol = [m for m in present if trio[m]["verdict"] == "hold"]
    reasons, diff, pair_ok = [], [], None
    if inv:
        reasons += [f"invalid run {m}: {'; '.join(trio[m]['invalid'])[:300]}" for m in inv]
    if missing:
        reasons.append(f"[missing] runs not collected: {missing}")
    if not inv and not missing:
        rs = [trio[m] for m in MODELS]
        for k in PAIR_KEYS:
            if len({r["_fp"][k] for r in rs}) != 1:
                v0 = rs[0]["_fp_raw"][k]
                if isinstance(v0, dict):
                    diff += [f"{k}.{kk}" for kk in sorted(v0) if len({canon((r["_fp_raw"][k] or {}).get(kk)) for r in rs}) != 1] or [k]
                else:
                    diff.append(k)
        if len({r["_origins_sha"] for r in rs}) != 1:
            diff.append("env_origins.npy")
        t0 = max(traj0_diff(r["_traj0"], rs[0]["_traj0"]) for r in rs)
        if not t0 <= TRAJ0_TOL:
            diff.append(f"traj[0] max abs diff {t0:.3g}")
        for f in DATA_CODE:
            if len({(r.get("code_at_collection") or {}).get(f) for r in rs}) != 1:
                diff.append(f"collection code {f}")
        pair_ok = not diff
        if diff:
            reasons.append(f"[pair] the three runs are not a recorded pair: {diff}")
        if hol:
            reasons += [f"hold run {m}: {'; '.join(trio[m]['hold'])[:300]}" for m in hol]
    verdict = "invalid" if inv else "incomplete" if missing else "hold" if (hol or not pair_ok) else "valid"
    return {"cell": key, "verdict": verdict, "reasons": reasons, "pair_ok": pair_ok, "pair_diff": diff, "in_diag": (fam, cell) in DIAG,
            "runs": {m: (trio[m]["verdict"] if trio[m] else "missing") for m in MODELS},
            "stats": {m: trio[m].get("stats") for m in present}}


def _count(vals, keys):
    return {k: sum(1 for v in vals if v == k) for k in keys}


def revalidate(root=DEFAULT_ROOT, tags=None):
    rd = Reader(root)
    t = time.strftime("%Y-%m-%d %H:%M:%S")
    ckpt_sha = {m: rd.ext_sha(f"ckpt:{m}", spec["ckpt"]) for m, spec in MODELS.items()}
    yaml_sha = rd.ext_sha("train_yaml", TRAIN_YAML)
    code_now = {}
    for f in DATA_CODE + NOTE_CODE:
        p = os.path.join(HERE, f)
        code_now[f] = sha_file(p) if os.path.exists(p) else None
    tags = find_tags(root) if tags is None else list(tags)
    runs = {tg: check_run(root, tg, rd, ckpt_sha, yaml_sha, code_now) for tg in tags}
    changed = rd.recheck()
    for r in runs.values():
        hit = [k for k in changed if k in r.get("inputs", {}) or k.startswith("ext:")]
        if hit:
            r["invalid"].append(f"[frozen] input changed during the check: {hit[:5]}")
            r["verdict"] = "invalid"
    groups = sorted({(r["family"], r["cell"]) for r in runs.values() if "family" in r})
    cells = {f"{fam}/{cell}": cell_verdict(fam, cell, runs) for fam, cell in groups}
    for r in runs.values():
        for k in [k for k in r if k.startswith("_")]:
            del r[k]
    diag_keys = [f"{f}/{c}" for f, c in DIAG]
    diag_runs = [r["verdict"] for r in runs.values() if (r.get("family"), r.get("cell")) in DIAG]
    counts = {"runs": _count([r["verdict"] for r in runs.values()], ("valid", "hold", "invalid")),
              "diag_runs": _count(diag_runs, ("valid", "hold", "invalid")),
              "cells": _count([c["verdict"] for c in cells.values()], ("valid", "hold", "invalid", "incomplete")),
              "diag_cells": _count([cells[k]["verdict"] if k in cells else "missing" for k in diag_keys],
                                   ("valid", "hold", "invalid", "incomplete", "missing"))}
    bundle = {"root": norm(root), "inputs": rd.inputs, "external": {k: v["sha256"] for k, v in rd.ext.items()}}
    me = os.path.abspath(__file__)
    return {"kind": "uncr_revalidate", "version": VERSION, "t": t, "t_end": time.strftime("%Y-%m-%d %H:%M:%S"), "root": norm(root),
            "revalidator": {"path": me.replace("\\", "/"), "sha256": sha_file(me)},
            "code_now": code_now, "channels": CHANNELS, "required_channels": list(REQUIRED_CH), "ground_channel": GROUND_CH,
            "judgement_window": WINDOW_DOC,
            "classes": {"invalid": "record defect or invalid measurement", "hold": "measured, needs a person (see reasons)",
                        "valid": "all checks passed; channel 11 NaN after the window is allowed and counted",
                        "incomplete": "cell lacks one of par / off / on", "missing": "no run of the cell"},
            "models": {m: {"ckpt": spec["ckpt"], "sha256_now": ckpt_sha[m]} for m, spec in MODELS.items()},
            "train_yaml": {"path": TRAIN_YAML, "sha256_now": yaml_sha},
            "runs": runs, "cells": cells, "diag_cells_missing": [k for k in diag_keys if k not in cells], "counts": counts,
            "inputs_sha256": dict(sorted(rd.inputs.items())), "external_sha256": {k: v for k, v in sorted(rd.ext.items())},
            "bundle_sha256": sha_bytes(canon(bundle).encode()), "frozen_ok": not changed, "changed_during_check": changed}


def write_report(rep, out_base=DEFAULT_OUT):
    root, ob = rep["root"], norm(out_base)
    if ob == root or ob.startswith(root + "/"):
        raise ValueError(f"refusing to write inside the input root {root}")
    base = os.path.join(out_base, time.strftime("%Y%m%d-%H%M%S"))
    d, k = base, 1
    while os.path.exists(d):
        d = f"{base}-{k}"
        k += 1
    os.makedirs(d)
    p = os.path.join(d, "revalidate.json")
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    os.replace(p + ".tmp", p)
    return p


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--out_base", default=DEFAULT_OUT)
    ap.add_argument("--no_write", action="store_true")
    a = ap.parse_args()
    rep = revalidate(a.root)
    for k in sorted(rep["cells"], key=lambda k: (not rep["cells"][k]["in_diag"], k)):
        c = rep["cells"][k]
        print(f"{'DIAG' if c['in_diag'] else 'full'} {k:28s} {c['verdict']:10s} runs {c['runs']} stats {c['stats']}")
        for x in c["reasons"]:
            print("    ", x[:300])
    for tg, r in rep["runs"].items():
        if r.get("notes") or r.get("nan", {}).get("ground_ch11_after_window"):
            print(f"  note {tg}: nan {r.get('nan')} notes {[x[:120] for x in r['notes']]}")
    print("counts", json.dumps(rep["counts"]))
    print("bundle", rep["bundle_sha256"], "frozen_ok", rep["frozen_ok"], "inputs", len(rep["inputs_sha256"]))
    if not a.no_write:
        print("report", write_report(rep, a.out_base))
    if not rep["frozen_ok"]:
        sys.exit(2)
    sys.exit(0 if rep["counts"]["diag_cells"]["valid"] == len(DIAG) else 1)


if __name__ == "__main__":
    main()
