# CMD-R 미경험 진단 수집본 재검사기 v2 (lead 하위 작업 · 2026-10-14 새벽 · CPU 만 · ASTRA 17e §3.1 · §3.4 · §5.3 반영).
#   v1 (uncr_revalidate.py) 은 ASTRA 17e 가 해시로 고정해 검사한 판이라 고치지 않고 이 새 파일을 만들었다. v1 의 검사는 모두 그대로 두고 더했다.
#   v1 결함 (17e) 과 v2:
#     - §3.1 등록 명령과 실제 저장 명령을 대조하지 않았다. v2 는 cell 마다 고정 명령 · 종류 · 기간 · 전환 규칙 (CELL_CONTRACT, q_eval_cmdr.py
#       :92~105 ALL_CELLS 를 옮겨 고정한 표) 을 meta 의 cell 과 대조하고, traj.npz 의 cmd_a · cmd_b · sw · cmd_hist · act_abs_mean 의
#       모양 · dtype · 유한성 · 값을 본다. cmd_hist 는 필수 키다. 상태 j 의 명령은 q_eval_cmdr.py:598~618 그대로
#       「j-1 >= sw 이면 cmd_b 아니면 cmd_a」 (j = 0 은 cmd_a) 여야 한다 (q_post.py:38 과 같은 규칙). heading-hold · spawn_offset ·
#       height_perm_seed · fingerprint_only 같은 이 평가에서 꺼져 있어야 하는 인자와 meta heading_hold 도 본다. checks_run 0 이라는
#       자기 보고는 이 검사를 대신하지 않는다.
#     - §3.4 frozen_ok 가 코드를 포함하지 않았다. v2 는 판정에 쓰는 코드 (이 파일 · q_post.py · q_metrics.py) 를 바이트로 읽어 그 바이트를
#       실행하고 (q_post 가 import 하는 q_metrics 도 그 바이트 모듈로 묶음), 적재 해시를 입력과 같은 재대조 목록에 넣는다. 끝에 파일이
#       적재 해시와 다르면 frozen_ok False. 캐시된 모듈은 검사 시작마다 지금 파일 해시와 대조해 다르면 다시 적재한다.
#     - §5.3 수집 코드 출처: stamp 의 코드를 역할 (eval · metrics · guard · post · slot · isolate) 로 읽는다. eval · metrics · guard 는 세
#       실행이 같아야 하고 면제하지 않는다. slot · isolate 는 등록한 두 값 (ASTRA 가 검토한 v2 판 · 새로 등록한 v3 판) 사이의 교체만
#       허용하고 그 밖의 값은 짝 불일치다. post 가 stamp 에 없는 옛 실행은 「출처 미확인」 이며 있는 값끼리만 같아야 한다.
#       slot 기록은 v2 · v3 형식을 둘 다 읽고, stamp 의 wrapper 와 기록 형식 · 실행기 이름이 서로 맞아야 한다. v3 기록은 v2 registry 가
#       아닌 별도 registry (isaac_usd_registry_v3.json) 를 써야 한다 (§5.4 혼합 운용).
#     - 짝 비교에 쓰는 자료 (지문 · env_origins 해시 · traj[0] 해시 · 역할별 코드) 를 공개 결과에 남겨, 두 루트의 실행을 한 칸으로 묶는
#       드라이버 (v5) 도 cell_verdict 로 같은 규칙을 쓴다. traj[0] 은 허용 오차 대신 바이트 해시가 같아야 한다.
#   묶음 해시 (bundle) 는 v1 과 같은 정의 (루트 · 실행 입력 파일 · 체크포인트 · yaml) 라서 같은 자료면 v1 보고와 같은 값이 나온다.
#   판정 코드 해시는 묶음에 넣지 않고 judge_code 와 frozen_ok 로 따로 적는다.
#   판정 (실행): invalid 기록 결함 · 측정 무효 / hold 측정은 있으나 사람이 봐야 함 / valid. 칸: valid · hold · invalid · incomplete.
#   이유 문자열은 [코드] 로 시작한다. 새 코드: [cmd-contract] [cmd-array] [cmd-time] [action] [eval-args] [terrain-src].
# 사용: python uncr_revalidate_v3.py [--root out_uncr] [--out_base out_uncr_v6/reval] [--no_write]
#   종료 코드: 0 diag 7 칸 모두 valid · 1 아님 · 2 검사 중 입력이나 판정 코드가 바뀜.
import argparse
import ctypes
import csv
import gc
import glob
import hashlib
import io
import json
import math
import os
import platform
import re
import shutil
import sys
import tempfile
import time
import types
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SELF = "uncr_revalidate_v3.py"
VERSION = "uncr-reval-3"
DEFAULT_ROOT = os.path.join(HERE, "out_uncr")
DEFAULT_OUT = os.path.join(HERE, "out_uncr_v6", "reval")
RECOMPUTE_BASE = os.environ.get("UNCR_V6_WORK", os.path.join(HERE, "out_uncr_v6", "_recompute"))
with open(os.path.abspath(__file__), "rb") as _fh:
    SELF_SHA_AT_LOAD = hashlib.sha256(_fh.read()).hexdigest()

# collection contract: the values of unseen_driver_cmdr.py v3 lines 36~48, with absolute paths (a copy of this file elsewhere reads the same)
E1 = "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192"
TRAIN_YAML = f"{E1}/params/env.yaml"
BR = "C:/isaac/ext/go2_rl_robotlab/_eval/out/branch"
MODELS = {"par": {"ckpt": f"{E1}/model_20000.pt", "iter": 20000, "yaml": ""},
          "off": {"ckpt": f"{BR}/cmdr_s1042_off_u4000/model_24000.pt", "iter": 24000, "yaml": TRAIN_YAML},
          "on": {"ckpt": f"{BR}/cmdr_s1042_on_u4000/model_24000.pt", "iter": 24000, "yaml": TRAIN_YAML}}
TERRAINS = ["discrete_obstacles", "wave", "stepping_stones", "gap", "pit", "rails", "star", "floating_ring", "repeated_boxes", "repeated_cylinders"]
DIAG = [("gap", "fwd05"), ("stepping_stones", "fwd05"), ("floating_ring", "fwd05"), ("rails", "fwd05"), ("wave", "fwd05"),
        ("gap", "back03"), ("discrete_obstacles", "back03")]
FULL = [(t, c) for c in ("fwd05", "fwd03", "fwd10") for t in TERRAINS]
MANIFEST = DIAG + [c for c in FULL if c not in DIAG]
EPISODES, EVAL_SEED, DIFF = 100, 1000, 0.5
WANT_ARGS = {"terrain_set": "unseen10", "episodes": EPISODES, "eval_seed": EVAL_SEED, "obs_noise": False, "full_record": False,
             "policy": "student", "difficulty": DIFF}
# 17e 3.1: arguments that must be off in this fixed evaluation (q_eval_cmdr.py:35, 51~60) and the meta record of heading hold (:583)
OFF_ARGS = {"heading_hold": 0.0, "spawn_offset": "", "height_perm_seed": -1, "fingerprint_only": False}
META_HEADING_HOLD = {"K": 0.0, "clip": 0.5, "envs": 0}
# 17e 3.1: the fixed cells, copied from q_eval_cmdr.py:92~105 ALL_CELLS (only the cells this driver uses)
CELL_CONTRACT = {
    "fwd03": {"name": "fwd03", "kind": "lin", "cmd": [0.3, 0.0, 0.0], "duration_s": 20.0, "switch_s": None, "src": "Q"},
    "fwd05": {"name": "fwd05", "kind": "lin", "cmd": [0.5, 0.0, 0.0], "duration_s": 20.0, "switch_s": None, "src": "LEAD_TEMP"},
    "fwd10": {"name": "fwd10", "kind": "lin", "cmd": [1.0, 0.0, 0.0], "duration_s": 20.0, "switch_s": None, "src": "LEAD_TEMP_UNSEEN"},
    "back03": {"name": "back03", "kind": "lin", "cmd": [-0.3, 0.0, 0.0], "duration_s": 20.0, "switch_s": None, "src": "Q"},
}
NO_SWITCH = 10 ** 9                                                        # q_eval_cmdr.py:344
TERRAIN_SRC_SHA = "0009e1e11850191bb875e316038a08ae85308226e27d6a748fe474aa1301eed4"  # generalization_env_cfg.py in all 23 reviewed runs
DT = 0.02                                                                  # q_metrics.DT
SPAWN_ROWS = 8                                                             # q_eval_cmdr.py:112
RESET_XY_M = 0.5                                                           # q_eval_cmdr.py:244~246 reset_base xy +-0.5 m
NCH = 12
CHANNELS = {0: "root_pos_w x", 1: "root_pos_w y", 2: "root_pos_w z", 3: "heading_w", 4: "root_lin_vel_b x", 5: "root_lin_vel_b y",
            6: "root_lin_vel_b z", 7: "root_ang_vel_b x", 8: "root_ang_vel_b y", 9: "root_ang_vel_b z", 10: "projected_gravity_b z",
            11: "base z minus nanmean of height_scanner_small ray hit z (NaN when no ray hits)"}
REQUIRED_CH = tuple(range(11))
GROUND_CH = 11
# 17e 5.3: collection code by role. eval · metrics · guard are never exempted; slot · isolate may differ only by the registered replacement.
ROLES = {"eval": ("q_eval_cmdr.py",), "metrics": ("q_metrics.py",), "guard": ("gpu_guard.py",), "post": ("q_post.py",),
         "slot": ("isaac_slot.py", "isaac_slot_v3.py"), "isolate": ("usd_isolate_run.py", "usd_isolate_run_v3.py")}
FIXED_ROLES = ("eval", "metrics", "guard")
APPROVED_V2_CODE = {  # ASTRA 17e §7 (the reviewed collection of the 23 runs)
    "q_eval_cmdr.py": "24aeaf6358ef79096911e3dcb220212ac715775012da96bf14e438c331dba4bc",
    "q_metrics.py": "c9930f8d327efd04df51440da519fefab2585490ae45b4a6ffbd39466138a794",
    "gpu_guard.py": "7fabec30704830a410878e4244190a4e62c60f3828ad5908fbf9ee264c30cbd4",
    "isaac_slot.py": "90ae613b0e7e791fa24bf82866eb0a0285eafe5cd10f0e201ba2f5af9fa19c47",
    "usd_isolate_run.py": "366a3c13aac3499e711ea717441ae7e3da67871302b5c6e432b1cbc20ea0a87f"}
REGISTERED_V3_WRAPPERS = {  # README-slot-isolate-v3.md files as of 2026-10-13 20:10 (to be reviewed by ASTRA 17f)
    "isaac_slot_v3.py": "974919b0717b684fb9f0a57a0282aeb5a0b321f4bc7d4131aedcc461e2d3945a",
    "usd_isolate_run_v3.py": "30dc2ea930f400948474b11c648aa389ff495d2a1bd764b4b9b984b931d11efb"}
REGISTERED_POST = {"q_post.py": "f90aaa97a50c5347111298b913d7bb948e58f0d1ce3af09808739cfcae1e26dd"}  # reproduces the 23 runs' bytes
WRAPPER_ALLOWED = {"slot": {("isaac_slot.py", APPROVED_V2_CODE["isaac_slot.py"]), ("isaac_slot_v3.py", REGISTERED_V3_WRAPPERS["isaac_slot_v3.py"])},
                   "isolate": {("usd_isolate_run.py", APPROVED_V2_CODE["usd_isolate_run.py"]),
                               ("usd_isolate_run_v3.py", REGISTERED_V3_WRAPPERS["usd_isolate_run_v3.py"])}}
DATA_CODE = tuple(f for fs in ROLES.values() for f in fs)
NOTE_CODE = ("unseen_driver_cmdr.py", "unseen_driver_cmdr_v4.py", "unseen_driver_cmdr_v5.py", "unseen_driver_cmdr_v6.py",
             "uncr_revalidate.py", SELF)
V3_REGISTRY_NAME = "isaac_usd_registry_v3.json"
JUDGE = {SELF: os.path.abspath(__file__), "q_post.py": os.path.join(HERE, "q_post.py"), "q_metrics.py": os.path.join(HERE, "q_metrics.py")}
PAIR_KEYS = ("terrain_mesh", "terrain_origins_sha256", "pairing_sha256", "pairing_sha256_ext")
PAIRING_REQ = ("init_root_pose", "init_joint_pos", "body_masses", "joint_stiffness")          # q_eval_cmdr.py:420~425
EXT_REQ = ("com", "material_static_dynamic_restitution", "motor_zero_offset")                 # q_eval_cmdr.py:432~454
HEX64 = re.compile(r"[0-9a-f]{64}")
EMPTY_SHA = hashlib.sha256(b"").hexdigest()
RUN_FILES = ("meta.json", "cells.json", "episodes.csv", "traj.npz", "env_origins.npy")
SIDE_FILES = (".log", ".guard.json", ".slot.json")
STAMP = "driver_stamp.json"
TAG_RX = re.compile(r"uncr_(par|off|on)_([a-z_]+)_((?:fwd|back)\d\d)")
USD_RX = re.compile(r"([^\s@\"'<>|=]*?)[/\\]IsaacLab[/\\]usd_(\d{8}_\d{6}_\d+)")
CSV_NEED = ("family", "cell", "episode", "env", "survived", "fall_reason", "fall_t", "span_survived", "span_fall_reason", "span_fall_t")
NPZ_NEED = ("traj", "term", "cel", "fam", "epi", "cmd_a", "cmd_b", "sw", "act_abs_mean", "cmd_hist")
ROBOT_ROOT_FAIL = "</World/envs/env_0/Robot>: Unresolved reference"
WINDOW_DOC = ("per episode: states 0..J (J = round(duration_s / DT) = 1000) when it survived, else 0..j_fall-1 where j_fall is the later of "
              "fall_t and span_fall_t (episodes.csv) divided by DT; j_fall must not come after the first term flag and equals it for base_contact")
CMD_TIME_DOC = "cmd_hist[j] = cmd_b if j-1 >= sw else cmd_a (q_eval_cmdr.py:580, 611, 612; q_post.py:38)"


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


EXPECTED_ENV = {
    "executable": "C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe",
    "python_version": "3.11.15 | packaged by Anaconda, Inc. | (main, Jun 11 2026, 15:12:53) [MSC v.1942 64 bit (AMD64)]",
    "numpy_version": "1.26.0",
    "numpy_file": "C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/Lib/site-packages/numpy/__init__.py",
    "blas_name": "openblas64",
    "blas_version": "0.3.23.dev",
    "openblas_kernel": "Cooperlake",
    "OPENBLAS_CORETYPE": None,
    "MKL_CBWR": None,
    "MKL_ENABLE_INSTRUCTIONS": None,
    "cpu_name": "AMD64 Family 25 Model 24 Stepping 1, AuthenticAMD",
    "q_post_sha256": "f90aaa97a50c5347111298b913d7bb948e58f0d1ce3af09808739cfcae1e26dd",
    "q_metrics_sha256": "c9930f8d327efd04df51440da519fefab2585490ae45b4a6ffbd39466138a794",
}


class UnsupportedEnvironment(RuntimeError):
    pass


def environment_fingerprint():
    config = np.show_config(mode="dicts")
    blas = config.get("Build Dependencies", {}).get("blas", {})
    kernel = None
    libs = glob.glob(os.path.join(os.path.dirname(np.__file__), "..", "numpy.libs", "*openblas*"))
    for path in sorted(libs):
        lib = ctypes.CDLL(path)
        for symbol in ("openblas_get_corename64_", "openblas_get_corename"):
            try:
                fun = getattr(lib, symbol)
            except AttributeError:
                continue
            fun.restype = ctypes.c_char_p
            kernel = fun().decode("ascii")
            break
        if kernel:
            break
    return {"executable": sys.executable, "python_version": sys.version, "numpy_version": np.__version__,
            "numpy_file": np.__file__, "blas_name": blas.get("name"), "blas_version": blas.get("version"),
            "blas_config": config, "openblas_kernel": kernel, "cpu_name": platform.processor(),
            "OPENBLAS_CORETYPE": os.environ.get("OPENBLAS_CORETYPE"), "MKL_CBWR": os.environ.get("MKL_CBWR"),
            "MKL_ENABLE_INSTRUCTIONS": os.environ.get("MKL_ENABLE_INSTRUCTIONS"),
            "q_post_sha256": sha_file(os.path.join(HERE, "q_post.py")),
            "q_metrics_sha256": sha_file(os.path.join(HERE, "q_metrics.py"))}


def environment_differences(observed, expected=EXPECTED_ENV):
    path_keys = {"executable", "numpy_file"}
    return [key for key, want in expected.items()
            if (norm(observed.get(key)) if key in path_keys and observed.get(key) else observed.get(key))
            != (norm(want) if key in path_keys else want)]


def ensure_supported_environment():
    fingerprint = environment_fingerprint()
    different = environment_differences(fingerprint)
    if different:
        raise UnsupportedEnvironment("[post-env] 다른 칸: " + ", ".join(different))
    return fingerprint


def is_hash(v):
    return isinstance(v, str) and HEX64.fullmatch(v) is not None and v != EMPTY_SHA


def canon(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


class Reader:
    """Every input is read once as bytes; its hash and its parse use the same bytes. recheck() hashes every file again, including the
    judgement code registered with code()."""

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

    def code(self, name, path, sha_loaded):
        self.ext["code:" + name] = {"path": path, "sha256": sha_loaded}

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
                out.append(k if k.startswith("code:") else "ext:" + k)
        return sorted(out)


_JUDGE = {}


def _module_from_bytes(path, modname):
    with open(path, "rb") as f:
        b = f.read()
    m = types.ModuleType(modname)
    m.__file__ = path
    exec(compile(b, path, "exec"), m.__dict__)  # noqa: S102  the bytes just hashed are the bytes that run
    return m, sha_bytes(b)


def judge_modules():
    """q_metrics and q_post loaded from bytes whose hash is kept; loaded again whenever a file on disk differs from the loaded bytes
    (17e 3.4: a cached module must equal the frozen code of this check). Returns (q_post module, {name: sha loaded}, reloaded)."""
    now = {n: sha_file(JUDGE[n]) for n in ("q_metrics.py", "q_post.py")}
    reloaded = False
    if not _JUDGE or any(_JUDGE["sha"][n] != now[n] for n in now):
        qm, s_qm = _module_from_bytes(JUDGE["q_metrics.py"], "q_metrics")
        prev = sys.modules.get("q_metrics")
        sys.modules["q_metrics"] = qm  # q_post's own `import q_metrics as Q` binds these bytes
        try:
            qp, s_qp = _module_from_bytes(JUDGE["q_post.py"], "q_post_for_reval")
        finally:
            if prev is None:
                sys.modules.pop("q_metrics", None)
            else:
                sys.modules["q_metrics"] = prev
        if qp.Q is not qm:
            raise RuntimeError("q_post did not bind the q_metrics bytes loaded for this check")
        _JUDGE.update(qp=qp, sha={"q_metrics.py": s_qm, "q_post.py": s_qp})
        reloaded = True
    return _JUDGE["qp"], dict(_JUDGE["sha"]), reloaded


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


def roles_of(code):
    """{role: [file, sha] or None} from a stamp's code_sha256; a role naming two files is returned as 'ambiguous'."""
    out = {}
    for role, files in ROLES.items():
        have = [f for f in files if f in code]
        out[role] = [have[0], code[have[0]]] if len(have) == 1 else (None if not have else "ambiguous")
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


def check_run(root, tag, rd, ckpt_sha, yaml_sha, code_now, qp, require_stamp=True, attempt_prefix=None):
    res = {"tag": tag, "root": norm(root), "verdict": "invalid", "invalid": [], "hold": [], "notes": []}
    bad, hold, note = res["invalid"].append, res["hold"].append, res["notes"].append
    before = set(rd.inputs)

    def done():
        res["inputs"] = {k: rd.inputs[k] for k in sorted(set(rd.inputs) - before)}
        res["verdict"] = "invalid" if res["invalid"] else "hold" if res["hold"] else "valid"
        return res

    mt = TAG_RX.fullmatch(tag)
    if not mt or mt.group(2) not in TERRAINS or mt.group(3) not in CELL_CONTRACT:
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
        _check_body(root, tag, m, fam, cell, spec, b, rd, ckpt_sha, yaml_sha, code_now, qp, require_stamp, attempt_prefix, res, bad, hold, note)
    except Exception as ex:  # noqa: BLE001
        bad(f"[unreadable] {type(ex).__name__}: {str(ex)[:200]}")
    return done()


def _check_slot(root, tag, s, st, attempt_prefix, rd, res, bad, note):
    """slot record (v2 or v3 form), USD isolation records and the wrapper the stamp names."""
    v3 = s.get("slot_version") == "v3"
    res["slot_version"] = "v3" if v3 else "v2"
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
    iso_name = "usd_isolate_run_v3.py" if v3 else "usd_isolate_run.py"
    cmd = [str(x).replace("\\", "/") for x in s.get("cmd", [])]
    if not any(x.endswith("/" + iso_name) or x == iso_name for x in cmd) or not any(x.endswith("q_eval_cmdr.py") for x in cmd) \
            or "--tag" not in cmd or cmd[cmd.index("--tag") + 1] != tag:
        bad(f"[slot] cmd is not {iso_name} q_eval_cmdr.py --tag <this tag> ({'v3' if v3 else 'v2'} slot record)")
    if v3:
        if s.get("expect_conversions") != "1" or s.get("usd_unassigned") or s.get("assigned_outside_root") or s.get("expect_violation") \
                or s.get("registry_error") or s.get("hint_without_assigned") or s.get("launcher_blocked") or s.get("unexpected_refused") \
                or s.get("killed"):
            bad("[slot] v3 record shows a protection event (expect / unassigned / outside / registry / blocked / killed)")
        if os.path.basename(str(s.get("registry") or "")) != V3_REGISTRY_NAME:
            bad(f"[slot] v3 slot used registry {s.get('registry')!r}, not the separate {V3_REGISTRY_NAME} (17e 5.4)")
    usd_root = norm(s.get("usd_root") or "")
    res["usd_root"] = usd_root
    if not usd_root.startswith(norm(root) + "/usd/") or usd_root.rsplit("/", 1)[-1] != os.path.normcase(f"{tag}-{att}"):
        bad(f"[usd-path] slot usd_root is not <root>/usd/<tag>-<attempt>: {usd_root}")
    dirs_asg = set()
    try:
        lines = [json.loads(x) for x in rd.read(os.path.join(usd_root, "assigned.jsonl")).decode("utf-8").splitlines() if x.strip()]
    except FileNotFoundError:
        lines = []
    if not lines:
        bad("[usd-path] no assigned.jsonl record in the run's USD root")
    for r in lines:
        ud = norm(r.get("usd_dir") or "") if r.get("usd_dir") else ""
        kind = r.get("kind")
        if kind not in (None, "assigned", "explicit_inside") or not ud.startswith(usd_root + "/isaaclab/usd_") or not r.get("patched_by"):
            bad(f"[usd-path] assigned line {kind or 'v2'} {ud} {r.get('patched_by')!r} is not an assignment inside the run's root")
        dirs_asg.add(ud)
    res["usd_assigned"] = sorted(dirs_asg)
    ist = os.path.join(usd_root, "isolate_state.json")
    if os.path.exists(ist):
        iso = json.loads(rd.read(ist).decode("utf-8"))
        res["isolate_patched_by"] = iso.get("patched_by")
        if iso.get("blocked"):
            bad(f"[usd-path] isolate_state blocked {str(iso.get('blocked'))[:120]}")
    elif v3:
        bad("[usd-path] no isolate_state.json for a v3 run")
    else:
        note("no isolate_state.json in the run's USD root")
    return usd_root, dirs_asg, v3


def _check_body(root, tag, m, fam, cell, spec, b, rd, ckpt_sha, yaml_sha, code_now, qp, require_stamp, attempt_prefix, res, bad, hold, note):
    d = os.path.join(root, tag)
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
        roles = roles_of(code)
        res["roles"] = roles
        miss = [r for r in ROLES if r != "post" and not isinstance(roles[r], list)]
        if miss:
            bad(f"[stamp-code] stamp lacks one collection file per role: {miss}")
        res["q_post"] = {"in_stamp": "q_post.py" in code,
                         "provenance": ("stamp 기록: " + code["q_post.py"]) if "q_post.py" in code else
                         "출처 미확인: 수집 stamp 에 q_post.py 해시가 없음 (지금 q_post 로 다시 만든 결과와의 바이트 대조만 아래에 적음)",
                         "sha256_now": code_now.get("q_post.py")}
        res["attempt"] = st.get("attempt")
        res["stamp_t"] = st.get("t")
    elif require_stamp:
        bad("[stamp-missing] no driver_stamp.json")
    s = json.loads(b[".slot.json"].decode("utf-8"))
    usd_root, dirs_asg, v3 = _check_slot(root, tag, s, st, attempt_prefix, rd, res, bad, note)
    if st is not None and isinstance(res.get("roles", {}).get("slot"), list) and isinstance(res["roles"].get("isolate"), list):
        want_w = ("isaac_slot_v3.py", "usd_isolate_run_v3.py") if v3 else ("isaac_slot.py", "usd_isolate_run.py")
        if (res["roles"]["slot"][0], res["roles"]["isolate"][0]) != want_w:
            bad(f"[stamp-code] stamp wrappers {res['roles']['slot'][0]} / {res['roles']['isolate'][0]} do not match the "
                f"{'v3' if v3 else 'v2'} slot record")
    g = json.loads(b[".guard.json"].decode("utf-8"))
    if g.get("exit_code") != 0 or g.get("stopped_by_guard"):
        bad(f"[guard] exit {g.get('exit_code')} stopped {g.get('stopped_by_guard')}")
    log = b[".log"].decode("utf-8", errors="replace")
    if "Traceback (most recent call last)" in log or ROBOT_ROOT_FAIL in log:
        bad("[log] Traceback or robot root reference failure")
    if f"[Q-EVAL] done {tag} N {EPISODES} " not in log or "Time taken for scene creation" not in log:
        bad("[log] no scene line or no completion line for this tag and N")
    found = USD_RX.findall(log)
    outside = sorted({norm(p) if p else "<none>" for p, _ in found} - {usd_root})
    if not found:
        bad("[usd-path] the log names no USD folder")
    if outside:
        bad(f"[usd-path] the log names USD paths outside this run's root: {outside[:3]}")
    dirs_log = {f"{usd_root}/isaaclab/usd_{k}" for _, k in found}
    final = {norm(x) if v3 else f"{usd_root}/isaaclab/usd_{x}" for x in (s.get("usd_final") or [])}
    if found and not (dirs_log == final == dirs_asg):
        bad(f"[usd-path] USD folders differ: log {sorted(dirs_log)} slot {sorted(final)} assigned {sorted(dirs_asg)}")
    unres = sum(1 for ln in log.splitlines() if "Unresolved reference" in ln)
    if unres:
        note(f"{unres} unresolved reference lines in the log (not the robot root; visual assets not approved by this check)")
    meta = json.loads(b["meta.json"].decode("utf-8"))
    a = meta.get("args") or {}
    want = dict(WANT_ARGS, families=fam, cells=cell, tag=tag)
    for k, v in want.items():
        if a.get(k) != v:
            bad(f"[args] {k}={a.get(k)!r} want {v!r}")
    for k, v in OFF_ARGS.items():
        if a.get(k) != v:
            bad(f"[eval-args] {k}={a.get(k)!r} must be {v!r} in this evaluation")
    if meta.get("heading_hold") != META_HEADING_HOLD or "spawn_offset" in meta:
        bad(f"[eval-args] meta heading_hold {meta.get('heading_hold')!r} / spawn_offset present {'spawn_offset' in meta}")
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
    if (meta.get("terrain_set") or {}).get("source_sha256") != TERRAIN_SRC_SHA:
        bad(f"[terrain-src] unseen10 generator source {str((meta.get('terrain_set') or {}).get('source_sha256'))[:12]} is not the reviewed one")
    cr, cp = meta.get("checks_run") or {}, meta.get("checks_pre") or {}
    if cr.get("nonfinite_action_or_obs_count") != 0:
        bad(f"[checks] nonfinite action or obs {cr.get('nonfinite_action_or_obs_count')}")
    if cr.get("obs_single_cmd_vs_target_max_abs") != 0.0 or cr.get("obs_history_latest_cmd_vs_target_max_abs") != 0.0:
        bad("[checks] command did not reach the observation exactly")
    if cp.get("manual_student_path_vs_act_inference_max_abs") != 0.0 or cp.get("teacher_input_randomized_max_abs_action_change") != 0.0:
        bad("[checks] checks_pre: student path or teacher independence")
    cc = CELL_CONTRACT[cell]
    T = int(round(cc["duration_s"] / DT))
    N = EPISODES
    cl = meta.get("cells") or []
    if meta.get("N") != N or meta.get("T_steps") != T or meta.get("families") != [fam] or len(cl) != 1:
        bad(f"[meta] N {meta.get('N')} T_steps {meta.get('T_steps')} families {meta.get('families')} cells {len(cl)}")
        return
    if canon(cl[0]) != canon(cc):
        bad(f"[cmd-contract] meta cell {canon(cl[0])[:160]} is not the fixed cell {canon(cc)}")
    oz = (meta.get("obstacle_zone_m") or {}).get(fam)
    if not (isinstance(oz, list) and len(oz) == 3 and isinstance(oz[1], (int, float)) and math.isfinite(oz[1]) and oz[1] > 0):
        bad(f"[meta] obstacle_zone_m[{fam}] {oz!r}")
        return
    ze = float(oz[1])
    for x in fp_problems(meta):
        bad("[fp-form] " + x)
    res["fp"] = {k: canon(meta.get(k)) for k in PAIR_KEYS}
    res["fp_raw"] = {k: meta.get(k) for k in PAIR_KEYS}
    c = json.loads(b["cells.json"].decode("utf-8"))
    if not (isinstance(c, list) and len(c) == 1 and c[0].get("n") == N and c[0].get("family") == fam and c[0].get("cell") == cell):
        bad("[cells] cells.json is not one row of this family / cell with n 100")
    with np.load(io.BytesIO(b["traj.npz"]), allow_pickle=False) as z:
        miss = [k for k in NPZ_NEED if k not in z.files]
        if miss:
            bad(f"[traj-shape] traj.npz lacks {miss}")
            return
        tr, term, epi, fa, ce = z["traj"], z["term"], z["epi"], z["fam"], z["cel"]
        ca, cb, sw, ch, act = z["cmd_a"], z["cmd_b"], z["sw"], z["cmd_hist"], z["act_abs_mean"]
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
    # --- 17e 3.1: the stored commands against the fixed contract, and the state-action time rule
    want_a = np.array(cc["cmd"], np.float32)
    want_b = np.zeros(3, np.float32) if cc["kind"] == "stop" else want_a
    want_sw = NO_SWITCH if cc["switch_s"] is None else int(round(cc["switch_s"] / DT))
    arr_bad = []
    for name, x, shp in (("cmd_a", ca, (N, 3)), ("cmd_b", cb, (N, 3)), ("cmd_hist", ch, (T + 1, N, 3))):
        if x.shape != shp or x.dtype != np.float32 or not np.isfinite(x).all():
            arr_bad.append(f"{name} {x.shape} {x.dtype} finite {bool(np.isfinite(x).all()) if x.dtype.kind == 'f' else '?'}")
    if sw.shape != (N,) or sw.dtype.kind not in "iu":
        arr_bad.append(f"sw {sw.shape} {sw.dtype}")
    if arr_bad:
        bad(f"[cmd-array] {arr_bad}")
        return
    vals = []
    if not (ca == want_a).all():
        vals.append(f"cmd_a max abs diff {float(np.abs(ca - want_a).max()):.3g} from {cc['cmd']}")
    if not (cb == want_b).all():
        vals.append(f"cmd_b max abs diff {float(np.abs(cb - want_b).max()):.3g}")
    if not (sw == want_sw).all():
        vals.append(f"sw {sorted(set(sw.tolist()))[:3]} want {want_sw}")
    if vals:
        bad(f"[cmd-array] stored commands are not the fixed cell: {vals}")
        return
    jj = np.arange(T + 1)[:, None]
    want_h = np.where(((jj - 1) >= sw[None, :])[..., None], cb[None, :, :], ca[None, :, :])
    if not (ch == want_h).all():
        jbad = np.argwhere((ch != want_h).any(axis=2))[0]
        bad(f"[cmd-time] cmd_hist differs from the time rule ({CMD_TIME_DOC}) first at state {int(jbad[0])} env {int(jbad[1])}")
        return
    if act.shape != (N,) or act.dtype.kind != "f" or not np.isfinite(act).all() or not (act > 0).all():
        bad(f"[action] act_abs_mean {act.shape} {act.dtype}: finite and > 0 for every env is required")
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
    res["traj0_sha256"] = sha_bytes(np.ascontiguousarray(tr[0]).tobytes())
    res["origins_sha256"] = sha_bytes(b["env_origins.npy"])
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
        nf = ~np.isfinite(tr[:jw + 1, e, 0:11])
        if nf.any() and first_bad is None:
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
            c_ = bool(np.max(tr[:jc + 1, e, 0] - org[e, 0]) >= ze)
            n += 1
            surv += s_n50
            cross += c_
            alive_cross += c_ and s_n50
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
    os.makedirs(RECOMPUTE_BASE, exist_ok=True)
    td = tempfile.mkdtemp(prefix="uncr_reval3_post_", dir=RECOMPUTE_BASE)
    eq, err = {}, ""
    try:
        for f in ("meta.json", "traj.npz"):
            with open(os.path.join(td, f), "wb") as fh:
                fh.write(b[f])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            qp.postprocess(td)
        for f in ("episodes.csv", "cells.json"):
            with open(os.path.join(td, f), "rb") as fh:
                eq[f] = fh.read() == b[f]
    except Exception as ex:  # noqa: BLE001  (q_post keeps traj.npz open on an exception; the handle is freed below)
        err = f"{type(ex).__name__}: {str(ex)[:160]}"
    gc.collect()
    res.setdefault("q_post", {})["recompute_folder"] = td
    res.setdefault("q_post", {})["recompute_equal"] = eq
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


def pair_check(rs):
    """17b 2.4 · 17e 5.3: three runs of one cell (any roots). Returns (diff list, notes)."""
    diff, notes = [], []
    for k in PAIR_KEYS:
        if len({r["fp"][k] for r in rs}) != 1:
            v0 = rs[0]["fp_raw"][k]
            if isinstance(v0, dict):
                diff += [f"{k}.{kk}" for kk in sorted(v0) if len({canon((r["fp_raw"][k] or {}).get(kk)) for r in rs}) != 1] or [k]
            else:
                diff.append(k)
    if len({r["origins_sha256"] for r in rs}) != 1:
        diff.append("env_origins.npy")
    if len({r["traj0_sha256"] for r in rs}) != 1:
        diff.append("traj[0] bytes")
    for role in FIXED_ROLES:
        vals = [canon((r.get("roles") or {}).get(role)) for r in rs]
        if len(set(vals)) != 1 or "null" in vals:
            diff.append(f"collection code {role} ({ROLES[role][0]})")
    post = [(r.get("model"), (r.get("roles") or {}).get("post")) for r in rs]
    known = {canon(v) for _, v in post if v}
    if len(known) > 1:
        diff.append("collection code post (q_post.py)")
    if any(not v for _, v in post):
        notes.append(f"q_post provenance unknown for {[mm for mm, v in post if not v]} (old stamps)")
    for role in ("slot", "isolate"):
        vals = [(r.get("roles") or {}).get(role) for r in rs]
        badw = [v for v in vals if not isinstance(v, list) or tuple(v) not in WRAPPER_ALLOWED[role]]
        if badw:
            diff.append(f"unregistered {role} wrapper {badw[:2]}")
        elif len({tuple(v) for v in vals}) > 1:
            notes.append(f"{role} wrapper differs between the runs: registered replacement {sorted({v[0] for v in vals})}")
    return diff, notes


def cell_verdict(fam, cell, trio):
    """trio: {model: public run result or None}. The same rule for one root (revalidate) and for runs taken from two roots (v5 post)."""
    key = f"{fam}/{cell}"
    present = [m for m in MODELS if trio.get(m)]
    missing = [m for m in MODELS if m not in present]
    inv = [m for m in present if trio[m]["verdict"] == "invalid"]
    hol = [m for m in present if trio[m]["verdict"] == "hold"]
    reasons, diff, notes, pair_ok = [], [], [], None
    if inv:
        reasons += [f"invalid run {m}: {'; '.join(trio[m]['invalid'])[:300]}" for m in inv]
    if missing:
        reasons.append(f"[missing] runs not collected: {missing}")
    if not inv and not missing:
        diff, notes = pair_check([trio[m] for m in MODELS])
        pair_ok = not diff
        if diff:
            reasons.append(f"[pair] the three runs are not a recorded pair: {diff}")
        if hol:
            reasons += [f"hold run {m}: {'; '.join(trio[m]['hold'])[:300]}" for m in hol]
    verdict = "invalid" if inv else "incomplete" if missing else "hold" if (hol or not pair_ok) else "valid"
    return {"cell": key, "verdict": verdict, "reasons": reasons, "notes": notes, "pair_ok": pair_ok, "pair_diff": diff, "in_diag": (fam, cell) in DIAG,
            "runs": {m: (trio[m]["verdict"] if trio.get(m) else "missing") for m in MODELS},
            "sources": {m: trio[m].get("root") for m in present},
            "stats": {m: trio[m].get("stats") for m in present} if verdict == "valid" else {}}


def _count(vals, keys):
    return {k: sum(1 for v in vals if v == k) for k in keys}


def _code_now():
    out = {}
    for f in DATA_CODE + NOTE_CODE:
        p = os.path.join(HERE, f)
        out[f] = sha_file(p) if os.path.exists(p) else None
    return out


def begin(root):
    """A Reader with the checkpoints, the yaml and the judgement code registered (code at its loaded hash)."""
    rd = Reader(root)
    ckpt_sha = {m: rd.ext_sha(f"ckpt:{m}", spec["ckpt"]) for m, spec in MODELS.items()}
    yaml_sha = rd.ext_sha("train_yaml", TRAIN_YAML)
    qp, loaded, reloaded = judge_modules()
    rd.code(SELF, JUDGE[SELF], SELF_SHA_AT_LOAD)
    for n in ("q_post.py", "q_metrics.py"):
        rd.code(n, JUDGE[n], loaded[n])
    judge = {SELF: {"path": JUDGE[SELF].replace("\\", "/"), "sha256_loaded": SELF_SHA_AT_LOAD},
             **{n: {"path": JUDGE[n].replace("\\", "/"), "sha256_loaded": loaded[n], "reloaded_for_this_check": reloaded} for n in loaded}}
    return rd, ckpt_sha, yaml_sha, qp, judge


def check_one(root, tag, require_stamp=True, attempt_prefix=None):
    """one run with its own frozen recheck (the v5 driver's per-run check)."""
    rd, ckpt_sha, yaml_sha, qp, _ = begin(root)
    r = check_run(root, tag, rd, ckpt_sha, yaml_sha, _code_now(), qp, require_stamp=require_stamp, attempt_prefix=attempt_prefix)
    ch = rd.recheck()
    if ch:
        r["invalid"].append(f"[frozen] input or judgement code changed during the check: {ch[:5]}")
        r["verdict"] = "invalid"
    return r


def revalidate(root=DEFAULT_ROOT, tags=None, check_environment=True):
    environment = ensure_supported_environment() if check_environment else environment_fingerprint()
    t = time.strftime("%Y-%m-%d %H:%M:%S")
    rd, ckpt_sha, yaml_sha, qp, judge = begin(root)
    code_now = _code_now()
    tags = find_tags(root) if tags is None else list(tags)
    runs = {tg: check_run(root, tg, rd, ckpt_sha, yaml_sha, code_now, qp) for tg in tags}
    changed = rd.recheck()
    code_changed = [k for k in changed if k.startswith("code:")]
    for r in runs.values():
        hit = [k for k in changed if k in r.get("inputs", {}) or k.startswith("ext:") or k.startswith("code:")]
        if hit:
            r["invalid"].append(f"[frozen] input or judgement code changed during the check: {hit[:5]}")
            r["verdict"] = "invalid"
    for k in judge:
        judge[k]["sha256_at_end"] = sha_file(JUDGE[k]) if os.path.exists(JUDGE[k]) else None
    groups = sorted({(r["family"], r["cell"]) for r in runs.values() if "family" in r})
    cells = {f"{fam}/{cell}": cell_verdict(fam, cell, {m: runs.get(f"uncr_{m}_{fam}_{cell}") for m in MODELS}) for fam, cell in groups}
    diag_keys = [f"{f}/{c}" for f, c in DIAG]
    diag_runs = [r["verdict"] for r in runs.values() if (r.get("family"), r.get("cell")) in DIAG]
    counts = {"runs": _count([r["verdict"] for r in runs.values()], ("valid", "hold", "invalid")),
              "diag_runs": _count(diag_runs, ("valid", "hold", "invalid")),
              "cells": _count([c["verdict"] for c in cells.values()], ("valid", "hold", "invalid", "incomplete")),
              "diag_cells": _count([cells[k]["verdict"] if k in cells else "missing" for k in diag_keys],
                                   ("valid", "hold", "invalid", "incomplete", "missing"))}
    data_ext = {k: v["sha256"] for k, v in rd.ext.items() if not k.startswith("code:")}
    bundle = {"root": norm(root), "inputs": rd.inputs, "external": data_ext}
    return {"kind": "uncr_revalidate", "version": VERSION, "environment": environment,
            "t": t, "t_end": time.strftime("%Y-%m-%d %H:%M:%S"), "root": norm(root),
            "revalidator": {"path": JUDGE[SELF].replace("\\", "/"), "sha256": SELF_SHA_AT_LOAD}, "judge_code": judge,
            "code_now": code_now, "channels": CHANNELS, "required_channels": list(REQUIRED_CH), "ground_channel": GROUND_CH,
            "judgement_window": WINDOW_DOC, "cell_contract": CELL_CONTRACT, "command_time_rule": CMD_TIME_DOC, "off_args": OFF_ARGS,
            "wrapper_registration": {k: sorted(list(x) for x in v) for k, v in WRAPPER_ALLOWED.items()},
            "classes": {"invalid": "record defect or invalid measurement", "hold": "measured, needs a person (see reasons)",
                        "valid": "all checks passed; channel 11 NaN after the window is allowed and counted",
                        "incomplete": "cell lacks one of par / off / on", "missing": "no run of the cell"},
            "models": {m: {"ckpt": spec["ckpt"], "sha256_now": ckpt_sha[m]} for m, spec in MODELS.items()},
            "train_yaml": {"path": TRAIN_YAML, "sha256_now": yaml_sha},
            "runs": runs, "cells": cells, "diag_cells_missing": [k for k in diag_keys if k not in cells], "counts": counts,
            "inputs_sha256": dict(sorted(rd.inputs.items())), "external_sha256": {k: v for k, v in sorted(rd.ext.items()) if not k.startswith("code:")},
            "bundle_sha256": sha_bytes(canon(bundle).encode()), "frozen_ok": not changed, "changed_during_check": changed,
            "code_changed_during_check": code_changed}


def write_report(rep, out_base=DEFAULT_OUT, name="revalidate.json"):
    root, ob = rep["root"], norm(out_base)
    if ob == root or ob.startswith(root + "/"):
        raise ValueError(f"refusing to write inside the input root {root}")
    base = os.path.join(out_base, time.strftime("%Y%m%d-%H%M%S"))
    d, k = base, 1
    while os.path.exists(d):
        d = f"{base}-{k}"
        k += 1
    os.makedirs(d)
    p = os.path.join(d, name)
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
    try:
        rep = revalidate(a.root)
    except UnsupportedEnvironment as ex:
        print(str(ex))
        sys.exit(3)
    for k in sorted(rep["cells"], key=lambda k: (not rep["cells"][k]["in_diag"], k)):
        c = rep["cells"][k]
        print(f"{'DIAG' if c['in_diag'] else 'full'} {k:28s} {c['verdict']:10s} runs {c['runs']} stats "
              f"{ {m: (s['surv'], s['cross']) for m, s in c['stats'].items() if s} }")
        for x in c["reasons"] + c["notes"]:
            print("    ", x[:300])
    print("counts", json.dumps(rep["counts"]))
    print("bundle", rep["bundle_sha256"], "frozen_ok", rep["frozen_ok"], "inputs", len(rep["inputs_sha256"]),
          "judge", {k: v["sha256_loaded"][:12] for k, v in rep["judge_code"].items()})
    if not a.no_write:
        print("report", write_report(rep, a.out_base))
    if not rep["frozen_ok"]:
        sys.exit(2)
    sys.exit(0 if rep["counts"]["diag_cells"]["valid"] == len(DIAG) else 1)


if __name__ == "__main__":
    main()
