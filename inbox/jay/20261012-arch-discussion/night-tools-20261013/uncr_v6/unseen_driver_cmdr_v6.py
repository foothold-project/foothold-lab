# CMD-R 미경험 지형 회귀 진단 v5 (lead 하위 작업 · 2026-10-14 새벽 · GPU 1 · 학습 없음 · ASTRA 17e §3.1 ~ §3.4 · §5 · §6 반영).
#   v4 (unseen_driver_cmdr_v4.py) 와 재검사기 v1 은 ASTRA 17e 가 해시로 고정해 검사한 판이라 고치지 않고 이 새 파일을 만들었다.
#   물음 · 대상 · 평가 인자는 v3 · v4 와 같다 (1042 한 학습 시드의 조건부 회귀 자료. 학습 시드 반복 · v2 공통 비교 · 1043 평가를 대신하지 않는다).
#   옛 묶음과 새 수집을 나눈다:
#     - 옛 묶음 (_eval/out_uncr, 23 실행, v2 slot · v2 실행기로 수집) 은 읽기만 한다. 승인 근거는 ASTRA 17e §4 가 검토한 재검사 보고
#       (out_uncr_reval/20261013-201422/revalidate.json, 파일 sha256 · 묶음 sha256 을 OLD_APPROVED 에 고정) 이다. v5 는 그 루트에 아무것도
#       쓰지 않고 (stamp · post · gate 포함), 재검사기 v2 로 다시 읽어 묶음 해시가 승인값과 같을 때만 diag 7 칸으로 쓴다.
#     - 새 수집은 _eval/out_uncr_v6 에 쓴다. 실행 관문은 isaac_slot_v3.py --expect_conversions 1 · usd_isolate_run_v3.py.
#   §5.3 출처: 「검토한 옛 묶음 승인」 (OLD_APPROVED) 과 「새 실행 코드 manifest」 (시작 때 동결하는 CODE · INPUTS) 를 따로 고정한다.
#     새 manifest 는 등록값 (REGISTERED_CODE · REGISTERED_INPUTS) 과 같아야 full 을 띄운다. 등록값에서 평가 (q_eval_cmdr) · 지표 (q_metrics) ·
#     guard · q_post · 체크포인트 · 학습 yaml · lab 지형 설정은 옛 묶음과 같은 값이고, 다른 것은 wrapper 둘 (slot · isolate) 의 v2 → v3
#     교체뿐이다 (재검사기 v2 의 WRAPPER_ALLOWED 에 그 두 쌍만 등록). 정책 · 평가 · 지형 코드 차이는 면제하지 않는다.
#   §3.1 명령 계약은 재검사기 v2 가 본다 (cell 고정 명령 · cmd_a · cmd_b · sw · cmd_hist 시간 대응 · action 요약 · 꺼져 있어야 할 인자).
#   §3.2 실패 분류 (일반 rc != 0 하나로 다루지 않음):
#     stop      98 (멈춤 파일 · 마감): 띄우지 않고 끝.
#     protection 89 · 90 · 91 · 94 · 95 · 96 · 97 · 로그의 로봇 루트 물리 참조 실패 · slot 기록 없음 또는 v3 아님 · 새 실행 재검사의 [usd-path] [slot]:
#               재시도하지 않고 첫 발생에서 전체 확대를 멈춘다. 실패 attempt 는 그 자리에 두고 HALT_v6.json 을 쓴다. 사람이 읽고 지우기 전에는
#               다음 full 을 띄우지 않는다.
#     gpu       99 이고 guard 요약이 stopped_by_guard: GPU_RETRIES 번까지만 다시 띄운다. 다시 띄우기 전 (그리고 매 기동 전) GPU 1 여유가
#               GPU_FREE_NEED_MIB 이상이어야 하며, GPU_WAIT_S 안에 안 되면 멈춘다.
#     child     그 밖의 rc != 0: 재시도하지 않고 이 단계를 멈춘다 (HALT 는 쓰지 않음).
#     data      rc 0 인데 새 실행 재검사가 invalid (보호 이유가 아닌 것): 이 단계를 멈춘다. hold 는 stamp 를 남기고 계속한다 (post 는 성공으로 닫지 않음).
#   §3.3 동결: 시작 때 CODE · INPUTS 를 동결하고, 매 자식 기동 직전 · 종료 직후 같은 계약으로 대조한다. 바뀌었으면 다음 자식을 띄우지 않는다.
#     재시도 사이 기다림은 1 초 단위로 STOP · HALT · 마감을 본다.
#   §5.4 혼합 운용: v3 slot 에는 별도 registry (slot/isaac_usd_registry_v3.json) 를 넘긴다. v2 registry (slot/isaac_usd_registry.json) 는
#     읽기만 해서 그 안에 적힌 로그들의 폴더를 --scan_dirs 에 더하고, out_branch (GPU 0 학습 출력) · 옛 out/branch · 옛 out_uncr 도 넣어
#     로그 경로 대조로 겹침을 찾게 한다. v2 참가자의 잠금 밖 쓰기는 v2 파일만 바꾸므로 v3 기록을 지울 수 없다.
#   §5.6 사람의 검토: full 은 --reval (재검사기 v2 의 옛 루트 보고) 과 --approval (검토자가 쓴 승인 파일) 둘 다 있어야 한다. 승인 파일은
#     reval 파일 해시 · 옛 묶음 해시 · 새 코드 manifest 해시 · 재사용 선택 · 새 실행 수 · decision approve · by 를 담아야 하고 지금 값과 같아야
#     한다 (파일을 읽었다는 증거는 아니고, 승인이 무엇에 대한 것인지를 묶는다). --stages manifest 가 그 값과 빈 틀을 적는다.
#   §6: discrete_obstacles/fwd05 의 옛 par · off 두 실행 재사용은 --reuse_partial yes 로만 (기본 no · 새 실행 75 건, yes 이면 73 건).
#     부분 칸은 완성 비교로 내지 않는다 (post 표에 valid 가 아닌 칸의 수치를 싣지 않음).
#   멈춤: out_uncr_v6/STOP (그리고 --stop_file). 옛 out_uncr/STOP 은 v4 용이라 보지 않는다.
#   판정 표기: crossed = 「낙상 전 몸통의 장애물 구간 끝 통과」. 네 발 도착 · 명령 준수 · 안전 통과가 아니다.
# 사용: python unseen_driver_cmdr_v6.py --stages manifest
#       python unseen_driver_cmdr_v6.py --stages full,post --reval <재검사 v2 보고> --approval <승인 파일> [--reuse_partial no|yes]
#       python unseen_driver_cmdr_v6.py --stages post [--manifest diag|full|all] [--reuse_partial no|yes]
import argparse
import csv
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
OLD_ROOT = os.environ.get("UNCR_V6_OLD_ROOT", os.path.join(HERE, "out_uncr"))
ROOT = os.environ.get("UNCR_V6_ROOT", os.path.join(HERE, "out_uncr_v6"))
REVAL_BASE = os.environ.get("UNCR_V6_REVAL_ROOT", os.path.join(ROOT, "reval"))
SLOT = os.environ.get("UNCR_V6_SLOT", os.path.join(HERE, "slot"))
LOCK = os.path.join(SLOT, "isaac_convert.lock")
REG_V3 = os.path.join(SLOT, "isaac_usd_registry_v3.json")
REG_V2 = os.path.join(SLOT, "isaac_usd_registry.json")  # read only
STOPF = os.path.join(ROOT, "STOP")
HALTF = os.path.join(ROOT, "HALT_v6.json")
RV_PATH = os.path.abspath(os.environ.get("UNCR_REVAL3_SCRIPT", os.path.join(HERE, "uncr_revalidate_v3.py")))
_spec = importlib.util.spec_from_file_location("uncr_revalidate_v3", RV_PATH)
RV = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RV)
E1, TRAIN_YAML, BR = RV.E1, RV.TRAIN_YAML, RV.BR
BR_NEW = os.path.join(HERE, "out_branch")
MODELS, TERRAINS, DIAG, FULL, MANIFEST = RV.MODELS, RV.TERRAINS, RV.DIAG, RV.FULL, RV.MANIFEST
EPISODES, EVAL_SEED, DIFF = RV.EPISODES, RV.EVAL_SEED, RV.DIFF
DO_FWD05 = ("discrete_obstacles", "fwd05")
OLD_APPROVED = {"report": os.path.join(HERE, "out_uncr_reval", "20261013-201422", "revalidate.json"),
                "report_sha256": "5d2421fe1283a82f416ed863abc0e85753896c1840dfc2fba34243329a4e526f",
                "bundle_sha256": "e55975172405901a0178a8e2bd3541ce7e13b118d0a9ab723fb6028d69ef2b58",
                "review": "VERIFY-astra-17e.md §4 (23 runs, diag 7 cells valid, descriptive statistics only)"}
REGISTERED_CODE = {f: RV.APPROVED_V2_CODE[f] for f in ("q_eval_cmdr.py", "q_metrics.py", "gpu_guard.py")}
REGISTERED_CODE.update(RV.REGISTERED_POST)
REGISTERED_CODE.update(RV.REGISTERED_V3_WRAPPERS)
LAB_EVAL = "C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/sim/eval"
REGISTERED_INPUTS = {"ckpt:par": "c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8",
                     "ckpt:off": "77c2fb648348dab5704d35fb94a6128ae2789b6ebb5470042b76e2548a6e86c1",
                     "ckpt:on": "9d26717c70061ef3a3de33a6e3cc040596682ccc9e650b45cc36b9a1a02c8b25",
                     "train_yaml": "2ee0009fd7564decacd75db4b292cfe9c6e6256d4db244ecaa68f3f122aeb75c",
                     "lab:generalization_env_cfg.py": RV.TERRAIN_SRC_SHA,
                     "lab:terrains.py": "3e0d47185f110a5fb6aa3550ba61ea7edd0fa1e89bd6a275f9377fae283a72ae"}
CODE_FILES = {f: os.path.join(HERE, f) for f in REGISTERED_CODE}
CODE_FILES["uncr_revalidate_v3.py"] = RV_PATH
CODE_FILES["unseen_driver_cmdr_v6.py"] = os.path.abspath(__file__)
for _name in ("test_uncr_v6.py", "mutate_uncr_v6.py", "frozen_exec.py"):
    CODE_FILES[_name] = os.path.join(HERE, _name)
INPUT_FILES = {f"ckpt:{m}": s["ckpt"] for m, s in MODELS.items()}
INPUT_FILES["train_yaml"] = TRAIN_YAML
for _m in ("off", "on"):
    for _f in ("bundle.json", "bundle.npz"):
        INPUT_FILES[f"{_f}:{_m}"] = os.path.join(BR, f"cmdr_s1042_{_m}_u4000", _f)
INPUT_FILES["lab:generalization_env_cfg.py"] = f"{LAB_EVAL}/generalization_env_cfg.py"
INPUT_FILES["lab:terrains.py"] = f"{LAB_EVAL}/terrains.py"
PROTECTION_RC = {89: "conversion attempts past the expected count or the launcher blocked one", 90: "the gate could not finish (registry or gate error)",
                 91: "assigned.jsonl and the log are not connected", 94: "USD folder outside the run root or unresolvable",
                 95: "USD folder count differs from the expected one", 96: "another run uses the same absolute USD folder",
                 97: "no scene line within the conversion limit", 92: "frozen_exec found changed code, input, or manifest"}
PROTECTION_REASONS = ("[usd-path]", "[slot]")
GPU_RETRIES = 2
GPU_FREE_NEED_MIB = 4096 + 2048
GPU_WAIT_S = 600
RETRY_WAIT_S = 120
SLEEP_STEP = 1.0
ENV = dict(os.environ, CUDA_DEVICE_ORDER="PCI_BUS_ID", CUDA_VISIBLE_DEVICES="1", OMNI_KIT_ACCEPT_EULA="YES", PYTHONUNBUFFERED="1")
ATTEMPT = f"g1-{os.getpid()}-{time.strftime('%m%d%H%M%S')}"
LOG = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "version": "cmdr-6", "attempt": ATTEMPT, "root": ROOT, "old_root": OLD_ROOT,
       "models": MODELS, "revalidator": RV_PATH, "runs": [], "skipped": [], "stages": {}, "failures": []}
FROZEN = {"code": {}, "inputs": {}}
OPT = {"deadline": 0.0, "stop_files": [STOPF]}


def save():
    os.makedirs(ROOT, exist_ok=True)
    p = os.path.join(ROOT, "driver_v6.json")
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(LOG, f, ensure_ascii=False, indent=1)
    os.replace(p + ".tmp", p)


def say(s):
    print(f"{time.strftime('%H:%M:%S')} {s}", flush=True)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sha_or_none(p):
    try:
        return sha(p)
    except OSError:
        return None


for _name in ("unseen_driver_cmdr_v6.py", "uncr_revalidate_v3.py", "test_uncr_v6.py", "mutate_uncr_v6.py", "frozen_exec.py"):
    REGISTERED_CODE[_name] = sha_or_none(CODE_FILES[_name])


def code_sha():
    return {f: sha_or_none(p) for f, p in CODE_FILES.items()}


def inputs_sha():
    return {k: sha_or_none(p) for k, p in INPUT_FILES.items()}


def freeze():
    FROZEN["code"] = code_sha()
    FROZEN["inputs"] = inputs_sha()


def frozen_now():
    c, i = code_sha(), inputs_sha()
    diff = [k for k in c if c[k] != FROZEN["code"].get(k)] + [k for k in i if i[k] != FROZEN["inputs"].get(k)]
    return not diff, diff


def manifest_sha():
    return hashlib.sha256(RV.canon({"code": FROZEN["code"], "inputs": FROZEN["inputs"]}).encode()).hexdigest()


def registration():
    """17e 5.3: the frozen new-execution manifest against the registered values (old approved code and inputs, plus only the v3 wrappers)."""
    diff = [f for f, s in REGISTERED_CODE.items() if not s or FROZEN["code"].get(f) != s]
    diff += [k for k, s in REGISTERED_INPUTS.items() if FROZEN["inputs"].get(k) != s]
    return not diff, diff


def fail(stage, what):
    LOG["failures"].append({"stage": stage, "what": what, "t": time.strftime("%H:%M:%S")})
    say(f"FAIL {stage}: {what}")
    save()


def halt_reason():
    for f in OPT["stop_files"]:
        if f and os.path.exists(f):
            return f"stop file {f}"
    if os.path.exists(HALTF):
        return "HALT_v6.json (a protection failure is recorded)"
    if OPT["deadline"] and time.time() > OPT["deadline"]:
        return "deadline"
    return ""


def _sleep(s):
    time.sleep(s)


def wait(seconds):
    """17e 3.3: a wait that answers STOP · HALT · deadline every SLEEP_STEP seconds. Returns the reason it stopped, or ''."""
    for _ in range(max(1, int(seconds / SLEEP_STEP))):
        why = halt_reason()
        if why:
            return why
        _sleep(SLEEP_STEP)
    return halt_reason()


def gpu_free_mib():
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits", "-i", "1"], capture_output=True,
                           text=True, timeout=30)
        return int(r.stdout.strip().splitlines()[0])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


def gpu_ready():
    """the condition before every launch (and so before a GPU retry): GPU 1 free memory >= GPU_FREE_NEED_MIB within GPU_WAIT_S."""
    for _ in range(max(1, int(GPU_WAIT_S / 30))):
        free = gpu_free_mib()
        if free is not None and free >= GPU_FREE_NEED_MIB:
            return True, ""
        why = wait(30)
        if why:
            return False, why
    return False, f"GPU 1 free memory {gpu_free_mib()} MiB stayed below {GPU_FREE_NEED_MIB} MiB for {GPU_WAIT_S} s"


def keep_attempt(tag):
    items = [tag, f"{tag}.log", f"{tag}.guard.json", f"{tag}.slot.json"]
    if not any(os.path.exists(os.path.join(ROOT, n)) for n in items):
        return
    dst = os.path.join(ROOT, "attempts", f"{tag}.{time.strftime('%Y%m%d-%H%M%S')}")
    os.makedirs(dst, exist_ok=True)
    for n in items:
        src = os.path.join(ROOT, n)
        if os.path.exists(src):
            shutil.move(src, os.path.join(dst, n))
            if os.path.exists(src):
                raise RuntimeError(f"could not move {src}")


def v2_registry_dirs():
    """17e 5.4: the v2 registry is only read; the folders of the logs it names are added to the scan."""
    try:
        with open(REG_V2, encoding="utf-8") as f:
            reg = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(reg, dict):
        return []
    return sorted({os.path.dirname(str(v)) for v in reg.values() if isinstance(v, str) and v})


def scan_dirs():
    out = []
    for d in [ROOT, OLD_ROOT, BR, BR_NEW] + v2_registry_dirs():
        if RV.norm(d) not in [RV.norm(x) for x in out]:
            out.append(d)
    return out


def slot_argv(tag, cmd, att, k):
    return [PY, "isaac_slot_v3.py", "--watch_log", os.path.join(ROOT, f"{tag}.log"), "--record", os.path.join(ROOT, f"{tag}.slot.json"),
            "--attempt", f"{att}-try{k}", "--usd_root", os.path.join(ROOT, "usd", f"{tag}-{att}-try{k}"), "--lock", LOCK, "--registry", REG_V3,
            "--scan_dirs", ",".join(scan_dirs()), "--stop_file", STOPF, "--deadline", str(OPT["deadline"]), "--expect_conversions", "1", "--",
            PY, "frozen_exec.py", "--manifest", os.path.join(ROOT, "manifest_v6.json"), "--expected-sha", manifest_sha(), "--",
            PY, "gpu_guard.py", "--gpu", "1", "--min_free_mib", "4096", "--log", os.path.join(ROOT, f"{tag}.log"),
            "--summary", os.path.join(ROOT, f"{tag}.guard.json"), "--", PY, "usd_isolate_run_v3.py"] + cmd


def _read_json(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def classify(tag, rc):
    """17e 3.2: (class, why) for one finished launch."""
    if rc == 98:
        return "stop", "slot did not launch (stop file or deadline)"
    try:
        with open(os.path.join(ROOT, f"{tag}.log"), encoding="utf-8", errors="replace") as f:
            log = f.read()
    except OSError:
        log = ""
    if RV.ROBOT_ROOT_FAIL in log:
        return "protection", "robot root physics reference failure in the log"
    if rc in PROTECTION_RC:
        return "protection", f"slot {rc}: {PROTECTION_RC[rc]}"
    rec = _read_json(os.path.join(ROOT, f"{tag}.slot.json"))
    if not isinstance(rec, dict) or rec.get("slot_version") != "v3":
        return "protection", "no v3 slot record for this launch"
    if rc == 0:
        if rec.get("killed") or rec.get("usd_unassigned") or rec.get("launcher_blocked") or rec.get("usd_outside_root"):
            return "protection", "the v3 slot record shows a protection event"
        return "ok", ""
    if rc == 99 and (_read_json(os.path.join(ROOT, f"{tag}.guard.json")) or {}).get("stopped_by_guard"):
        return "gpu", "gpu_guard stopped the run: GPU 1 free memory under the floor"
    return "child", f"child exit {rc}"


def run_one(tag, cmd, att):
    gpu_retries, k = 0, 0
    while True:
        k += 1
        why = halt_reason()
        if why:
            return {"cls": "stop", "rc": 98, "tries": k - 1, "why": why}
        ok, diff = frozen_now()
        if not ok:
            return {"cls": "frozen", "rc": None, "tries": k - 1, "why": f"code or inputs changed before launch {k}: {diff}"}
        ok, why = gpu_ready()
        if not ok:
            return {"cls": "gpu_precondition", "rc": None, "tries": k - 1, "why": why}
        keep_attempt(tag)
        why = halt_reason()
        if why:
            return {"cls": "stop", "rc": 98, "tries": k - 1, "why": why}
        ok, diff = frozen_now()
        if not ok:
            return {"cls": "frozen", "rc": None, "tries": k - 1, "why": f"code or inputs changed after GPU wait before launch {k}: {diff}"}
        t0 = time.time()
        rc = subprocess.run(slot_argv(tag, cmd, att, k), cwd=HERE, env=ENV).returncode
        say(f"RUN {tag} try {k} EXIT {rc} {time.time() - t0:.0f}s")
        ok, diff = frozen_now()
        if not ok:
            return {"cls": "frozen", "rc": rc, "tries": k, "why": f"code or inputs changed while launch {k} ran: {diff}"}
        cls, why = classify(tag, rc)
        if cls == "gpu" and gpu_retries < GPU_RETRIES:
            gpu_retries += 1
            w = wait(RETRY_WAIT_S)
            if w:
                return {"cls": "stop", "rc": rc, "tries": k, "why": f"while waiting to retry: {w}"}
            continue
        return {"cls": cls, "rc": rc, "tries": k, "why": why}


def halt(tag, res):
    info = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "attempt": ATTEMPT, "tag": tag, "class": res.get("cls"), "rc": res.get("rc"),
            "why": res.get("why"), "kept_in_place": [os.path.join(ROOT, n) for n in (tag, f"{tag}.log", f"{tag}.slot.json", f"{tag}.guard.json")
                                                      if os.path.exists(os.path.join(ROOT, n))] + [os.path.join(ROOT, "usd")],
            "next": "a person reads the attempt, decides the cause, and removes this file before any further full"}
    with open(HALTF + ".tmp", "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    os.replace(HALTF + ".tmp", HALTF)
    fail("protection", f"{tag}: {res.get('why')} (rc {res.get('rc')}); HALT_v6.json written, no retry, no further launch")


def tag_of(m, fam, cell):
    return f"uncr_{m}_{fam}_{cell}"


def source_of(fam, cell, m, reuse):
    if (fam, cell) in DIAG:
        return "old"
    if (fam, cell) == DO_FWD05 and m in ("par", "off") and reuse:
        return "old"
    return "new"


def plan_full(reuse):
    return [(fam, cell, m) for fam, cell in FULL if (fam, cell) not in DIAG for m in ("par", "off", "on") if source_of(fam, cell, m, reuse) == "new"]


def outhash(tag):
    d = os.path.join(ROOT, tag)
    h = {f: sha(os.path.join(d, f)) for f in ("meta.json", "cells.json", "episodes.csv", "traj.npz", "env_origins.npy")}
    h.update({e: sha(os.path.join(ROOT, f"{tag}{e}")) for e in (".log", ".guard.json", ".slot.json")})
    return h


def write_stamp(tag):
    s = _read_json(os.path.join(ROOT, f"{tag}.slot.json")) or {}
    st = {"attempt": s.get("attempt"), "out_sha256": outhash(tag), "code_sha256": dict(FROZEN["code"]), "t": time.strftime("%Y-%m-%d %H:%M:%S"),
          "driver_version": "cmdr-6", "inputs_sha256": dict(FROZEN["inputs"]), "manifest_sha256": manifest_sha(), "registry": REG_V3,
          "environment": RV.ensure_supported_environment(),
          "code_checked": "code and inputs equal to the driver start right before and right after every launch"}
    p = os.path.join(ROOT, tag, "driver_stamp.json")
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1)
    os.replace(p + ".tmp", p)


def reusable_new(tag):
    st = _read_json(os.path.join(ROOT, tag, "driver_stamp.json"))
    if not isinstance(st, dict):
        return False
    code = st.get("code_sha256") or {}
    if any(code.get(f) != FROZEN["code"].get(f) for f in REGISTERED_CODE):
        return False
    return RV.check_one(ROOT, tag, True, st.get("attempt"))["verdict"] == "valid"


def run_set(plan):
    """new runs only (out_uncr_v6). Returns False when the stage stopped."""
    for spec in MODELS.values():
        assert os.path.exists(spec["ckpt"]), spec["ckpt"]
    os.makedirs(ROOT, exist_ok=True)
    for fam, cell, m in plan:
        tag = tag_of(m, fam, cell)
        why = halt_reason()
        if why:
            fail("full", f"not launching the rest: {why}")
            return False
        ok, diff = frozen_now()
        if not ok:
            fail("full", f"code or inputs changed since the driver start: {diff}; not launching the rest")
            return False
        if reusable_new(tag):
            LOG["runs"].append({"stage": "full", "tag": tag, "reused": True, "valid": True})
            continue
        spec = MODELS[m]
        cmd = ["q_eval_cmdr.py", "--headless", "--tag", tag, "--policy", "student", "--checkpoint", spec["ckpt"], "--terrain_set", "unseen10",
               "--families", fam, "--cells", cell, "--episodes", str(EPISODES), "--eval_seed", str(EVAL_SEED), "--difficulty", str(DIFF),
               "--outdir", ROOT]
        if spec["yaml"]:
            cmd += ["--train_yaml", spec["yaml"]]
        att = f"{ATTEMPT}-{tag}"
        res = run_one(tag, cmd, att)
        entry = {"stage": "full", "tag": tag, "attempt": att, **res}
        LOG["runs"].append(entry)
        if res["cls"] == "protection":
            halt(tag, res)
            return False
        if res["cls"] != "ok":
            LOG["skipped"].append(tag)
            fail("full", f"{tag}: {res['cls']}: {res['why']} (rc {res['rc']}, launches {res['tries']}); stage stopped")
            return False
        r = RV.check_one(ROOT, tag, require_stamp=False, attempt_prefix=att)
        if r["verdict"] == "invalid":
            prot = [x for x in r["invalid"] if x.startswith(PROTECTION_REASONS)]
            entry.update(verdict="invalid", invalid=r["invalid"])
            if prot:
                halt(tag, {"cls": "protection", "rc": 0, "why": "revalidation of the new run: " + "; ".join(prot)[:400]})
            else:
                fail("full", f"{tag}: data invalid: {'; '.join(r['invalid'])[:400]}; stage stopped")
            return False
        write_stamp(tag)
        r = RV.check_one(ROOT, tag, require_stamp=True, attempt_prefix=att)
        entry.update(verdict=r["verdict"], hold=r["hold"], invalid=r["invalid"])
        if r["verdict"] == "invalid":
            fail("full", f"{tag}: invalid after stamping: {'; '.join(r['invalid'])[:400]}; stage stopped")
            return False
        save()
    return True


def old_bundle(fresh=None):
    """the reviewed old bundle (17e 5.3): the approved report file intact, and the old root read now gives the approved bundle hash.
    Returns (ok, why, fresh report)."""
    if sha_or_none(OLD_APPROVED["report"]) != OLD_APPROVED["report_sha256"]:
        return False, f"the approved report {OLD_APPROVED['report']} is missing or changed", fresh
    fresh = fresh or RV.revalidate(OLD_ROOT)
    if not fresh["frozen_ok"]:
        return False, f"old root inputs or judgement code changed during its revalidation: {fresh['changed_during_check'][:5]}", fresh
    if fresh["bundle_sha256"] != OLD_APPROVED["bundle_sha256"]:
        return False, f"old root bundle {fresh['bundle_sha256'][:12]} is not the approved {OLD_APPROVED['bundle_sha256'][:12]}", fresh
    return True, "", fresh


def full_gate(reval_path, approval_path, reuse):
    """17e 3.1 · 5.3 · 5.6: full starts only on (1) the registered manifest, (2) a v2 revalidation of the old root equal to the approved
    bundle with 7 valid diag cells collected by the approved v2 code, and (3) an approval file bound to these hashes and this scope."""
    if os.path.exists(HALTF):
        return False, "HALT_v6.json exists (protection failure not cleared)", None
    ok, diff = registration()
    if not ok:
        return False, f"new execution manifest differs from the registered values: {diff} (not exempted)", None
    if not reval_path or not approval_path:
        return False, "full needs --reval (uncr_revalidate_v3 report of the old root) and --approval (the reviewer's file)", None
    rv = _read_json(reval_path)
    if not isinstance(rv, dict) or rv.get("kind") != "uncr_revalidate" or rv.get("version") != RV.VERSION:
        return False, f"--reval is not a {RV.VERSION} report", None
    if RV.norm(rv.get("root") or "") != RV.norm(OLD_ROOT):
        return False, f"--reval is for {rv.get('root')!r}, not the old root {OLD_ROOT!r}", None
    judge = rv.get("judge_code") or {}
    if (rv.get("revalidator") or {}).get("sha256") != FROZEN["code"].get("uncr_revalidate_v3.py") \
            or any((judge.get(f) or {}).get("sha256_loaded") != FROZEN["code"].get(f) for f in ("q_post.py", "q_metrics.py")):
        return False, "--reval was made by other judgement code (revalidator / q_post / q_metrics)", None
    if not rv.get("frozen_ok"):
        return False, "--reval saw its inputs or judgement code change during the check", None
    ok, why, fresh = old_bundle()
    if not ok:
        return False, why, None
    if fresh["bundle_sha256"] != rv.get("bundle_sha256"):
        return False, "--reval bundle is not the old root now", None
    for fam, cell in DIAG:
        k = f"{fam}/{cell}"
        a, b = ((rv.get("cells") or {}).get(k) or {}).get("verdict"), (fresh["cells"].get(k) or {}).get("verdict")
        if a != "valid" or b != "valid":
            return False, f"diag cell {k} is not valid (reviewed {a}, now {b})", None
    for fam, cell in DIAG + ([DO_FWD05] if reuse else []):
        for m in ("par", "off", "on"):
            if source_of(fam, cell, m, reuse) != "old":
                continue
            r = fresh["runs"].get(tag_of(m, fam, cell)) or {}
            if r.get("verdict") != "valid":
                return False, f"old run {tag_of(m, fam, cell)} is {r.get('verdict')}", None
            roles = r.get("roles") or {}
            want = {"eval": "q_eval_cmdr.py", "metrics": "q_metrics.py", "guard": "gpu_guard.py", "slot": "isaac_slot.py", "isolate": "usd_isolate_run.py"}
            wrong = [ro for ro, f in want.items() if roles.get(ro) != [f, RV.APPROVED_V2_CODE[f]]]
            if wrong:
                return False, f"old run {r.get('tag')} was not collected with the approved v2 code: {wrong}", None
    ap = _read_json(approval_path)
    plan = plan_full(reuse)
    want_ap = {"kind": "uncr_v6_full_approval", "decision": "approve", "reval_sha256": sha_or_none(reval_path),
               "old_bundle_sha256": fresh["bundle_sha256"], "code_manifest_sha256": manifest_sha(), "reuse_partial": "yes" if reuse else "no",
               "new_runs": len(plan)}
    if not isinstance(ap, dict):
        return False, "--approval unreadable", None
    wrong = [k for k, v in want_ap.items() if ap.get(k) != v]
    if wrong or not str(ap.get("by") or "").strip():
        return False, f"--approval does not approve this: {wrong or ['by']}", None
    gate = {"attempt": ATTEMPT, "t": time.strftime("%Y-%m-%d %H:%M:%S"), "reval": os.path.abspath(reval_path), "approval": os.path.abspath(approval_path),
            "approval_sha256": sha_or_none(approval_path), "approved_by": ap.get("by"), **{k: v for k, v in want_ap.items() if k != "kind"},
            "old_approved": OLD_APPROVED, "planned": [tag_of(m, f, c) for f, c, m in plan]}
    return True, "", gate


def stage_manifest(reuse):
    ok, diff = registration()
    plan = plan_full(reuse)
    info = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "attempt": ATTEMPT, "code_sha256": FROZEN["code"], "inputs_sha256": FROZEN["inputs"],
            "code_paths": CODE_FILES, "input_paths": INPUT_FILES, "environment": RV.environment_fingerprint(),
            "code_manifest_sha256": manifest_sha(), "registered_ok": ok, "registered_diff": diff, "registered_code": REGISTERED_CODE,
            "registered_inputs": REGISTERED_INPUTS, "wrapper_registration": {k: sorted(list(x) for x in v) for k, v in RV.WRAPPER_ALLOWED.items()},
            "old_approved": OLD_APPROVED, "reuse_partial": "yes" if reuse else "no", "new_runs": len(plan),
            "new_runs_if_reuse_no": len(plan_full(False)), "new_runs_if_reuse_yes": len(plan_full(True)),
            "approval_template": {"kind": "uncr_v6_full_approval", "decision": "pending", "by": "", "t": "",
                                  "reval_sha256": "<sha256 of the uncr_revalidate_v3 report of the old root you read>",
                                  "old_bundle_sha256": OLD_APPROVED["bundle_sha256"], "code_manifest_sha256": manifest_sha(),
                                  "reuse_partial": "yes" if reuse else "no", "new_runs": len(plan)}}
    p = os.path.join(ROOT, "manifest_v6.json")
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    os.replace(p + ".tmp", p)
    LOG["stages"]["manifest"] = {k: info[k] for k in ("code_manifest_sha256", "registered_ok", "registered_diff", "new_runs")}
    if not ok:
        fail("manifest", f"new execution manifest differs from the registered values: {diff}")
    say(f"MANIFEST {manifest_sha()} registered {ok} new runs {len(plan)} -> {p}")


def stage_post(requested, reuse):
    old_ok, old_why, old_rep = old_bundle()
    if old_rep is None:
        old_rep = RV.revalidate(OLD_ROOT)
    new_rep = RV.revalidate(ROOT)
    paths = {}
    for name, rep in (("old", old_rep), ("new", new_rep)):
        try:
            paths[name] = RV.write_report(rep, REVAL_BASE, name=f"revalidate_v6_{name}.json")
        except (OSError, ValueError) as ex:
            fail("post", f"{name} revalidation report not written: {ex}")
    rows = []
    cats = {k: [] for k in ("missing", "incomplete", "invalid", "hold", "unpaired")}
    for fam, cell in MANIFEST:
        key = f"{fam}/{cell}"
        trio, src = {}, {}
        for m in ("par", "off", "on"):
            src[m] = source_of(fam, cell, m, reuse)
            trio[m] = (old_rep if src[m] == "old" else new_rep)["runs"].get(tag_of(m, fam, cell))
        c = RV.cell_verdict(fam, cell, trio) if any(trio.values()) else None
        state = c["verdict"] if c else "missing"
        why = " | ".join((c or {}).get("reasons") or [])
        if c and "old" in src.values() and not old_ok and any(trio[m] for m in trio if src[m] == "old"):
            state, why = "invalid", f"old bundle not the approved one: {old_why} | {why}"
        row = {"terrain": fam, "cell": cell, "in_diag": (fam, cell) in DIAG, "requested": (fam, cell) in requested, "state": state,
               "complete": state == "valid", "pair_ok": c.get("pair_ok") if c else None, "pair_diff": " ".join((c or {}).get("pair_diff") or []),
               "notes": " | ".join((c or {}).get("notes") or []), "why": why[:400], "sources": " ".join(f"{m}:{src[m]}" for m in src)}
        for m in ("par", "off", "on"):
            row[f"{m}_verdict"] = trio[m]["verdict"] if trio[m] else "missing"
        if state == "valid":  # 17e 6: numbers only for complete, paired, valid cells
            for m in ("par", "off", "on"):
                row.update({f"{m}_{k}": v for k, v in c["stats"][m].items()})
        rows.append(row)
        if row["requested"] and state != "valid":
            cats["unpaired" if (state == "hold" and c and c.get("pair_ok") is False) else state].append(key)
    path = os.path.join(ROOT, "UNCR-cells-v6.csv")
    keys = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("terrain", "cell", "in_diag", "requested", "state", "complete", "pair_ok"), k))
    with open(path + ".tmp", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    os.replace(path + ".tmp", path)
    post = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "attempt": ATTEMPT, "requested": sorted(f"{f}/{c}" for f, c in requested),
            "reuse_partial": "yes" if reuse else "no", "reval": paths, "old_bundle_ok": old_ok, "old_bundle_why": old_why,
            "old_bundle_sha256": old_rep["bundle_sha256"], "new_bundle_sha256": new_rep["bundle_sha256"],
            "frozen_ok": bool(old_rep["frozen_ok"] and new_rep["frozen_ok"]), "rows": len(rows), "complete": sum(r["complete"] for r in rows)}
    post.update({f"requested_{k}": v for k, v in cats.items()})
    p = os.path.join(ROOT, "post_v6.json")
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(post, f, ensure_ascii=False, indent=1)
    os.replace(p + ".tmp", p)
    LOG["stages"]["post"] = post
    if not post["frozen_ok"]:
        fail("post", "inputs or judgement code changed during a revalidation")
    bad = {k: v for k, v in cats.items() if v}
    if bad:
        fail("post", "requested cells not valid: " + "; ".join(f"{k} {v[:6]}" for k, v in bad.items()))
    say(f"POST rows {len(rows)} valid {post['complete']} requested not valid {sum(len(v) for v in cats.values())} old bundle ok {old_ok}")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="post")
    ap.add_argument("--manifest", choices=("diag", "full", "all"), default="diag",
                    help="cells post must find valid, also when post runs alone (default diag: the fixed collection contract)")
    ap.add_argument("--reval", default="", help="full: uncr_revalidate_v3 report of the old root (out_uncr)")
    ap.add_argument("--approval", default="", help="full: the reviewer's approval file (see --stages manifest)")
    ap.add_argument("--reuse_partial", choices=("no", "yes"), default="no",
                    help="reuse the old par / off runs of discrete_obstacles/fwd05 (default no: 75 new runs; yes: 73)")
    ap.add_argument("--deadline", type=float, default=0.0, help="epoch seconds; no launch after it, and waits stop at it")
    ap.add_argument("--stop_file", default="")
    a = ap.parse_args()
    st = [s for s in a.stages.split(",") if s]
    reuse = a.reuse_partial == "yes"
    OPT["deadline"] = a.deadline
    if a.stop_file:
        OPT["stop_files"].append(a.stop_file)
    try:
        environment = RV.ensure_supported_environment() if any(s in ("full", "post") for s in st) else RV.environment_fingerprint()
    except RV.UnsupportedEnvironment as ex:
        print(str(ex), flush=True)
        sys.exit(3)
    os.makedirs(ROOT, exist_ok=True)
    freeze()
    reg_ok, reg_diff = registration()
    LOG.update(stages_requested=st, manifest=a.manifest, reval_arg=a.reval, approval_arg=a.approval, reuse_partial=a.reuse_partial,
               code_sha256_start=FROZEN["code"], inputs_sha256_start=FROZEN["inputs"], code_manifest_sha256=manifest_sha(),
               registered_ok=reg_ok, registered_diff=reg_diff, v2_registry_sha256_start=sha_or_none(REG_V2),
               environment=environment)
    say(f"START attempt {ATTEMPT} stages {st} root {ROOT} old {OLD_ROOT} reuse_partial {a.reuse_partial} registered {reg_ok}")
    save()
    unknown = [s for s in st if s not in ("manifest", "full", "post")]
    if unknown or not st:
        fail("args", f"stages {st}: unknown {unknown} (v5 does not re-collect diag: it is the approved old bundle)")
    else:
        requested = set({"diag": DIAG, "full": FULL, "all": MANIFEST}[a.manifest])
        if "manifest" in st:
            stage_manifest(reuse)
        if "full" in st:
            requested |= set(FULL)
            ok, why, gate = full_gate(a.reval, a.approval, reuse)
            if not ok:
                fail("full", f"gate not passed: {why}; full not started")
            else:
                LOG["full_gate"] = gate
                p = os.path.join(ROOT, "full_gate_v6.json")
                with open(p + ".tmp", "w", encoding="utf-8") as f:
                    json.dump(gate, f, ensure_ascii=False, indent=1)
                os.replace(p + ".tmp", p)
                run_set(plan_full(reuse))
        if "post" in st:
            stage_post(requested, reuse)
    ok, diff = frozen_now()
    LOG["code_and_inputs_unchanged_at_end"] = ok
    LOG["v2_registry_sha256_end"] = sha_or_none(REG_V2)
    if not ok:
        fail("end", f"code or inputs changed during this driver run: {diff}")
    LOG["finished" if not LOG["failures"] else "incomplete"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save()
    say("END " + ("finished" if not LOG["failures"] else f"incomplete {len(LOG['failures'])}"))
    sys.exit(0 if not LOG["failures"] else 1)


if __name__ == "__main__":
    main()
