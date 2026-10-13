# CMD-R 미경험 지형 회귀 진단 v4 (lead 하위 작업 · 2026-10-13 밤 · GPU 1 · 학습 없음 · ASTRA 17c §2.4 P1 셋 · §4 · §5 · §6 반영).
#   v3 (unseen_driver_cmdr.py) 는 수집에 쓴 코드라 고치지 않고, 이 사본을 고쳤다. 물음 · 대상 · 평가 인자 · 출력 루트 (_eval/out_uncr) ·
#   실행 폴더 이름 · stamp 키 (attempt · out_sha256 · code_sha256 · t) 는 v3 과 같아 v3 이 모은 실행을 그대로 다시 쓸 수 있다.
#   다시 쓰는 것은 uncr_revalidate.py 재검사가 valid 인 실행뿐이다.
#   물음 · 대상은 v3 머리말 그대로: 1042 한 학습 시드의 조건부 회귀 자료이며, 학습 시드 반복 · v2 공통 비교 · 1043 평가를 대신하지 않는다.
#   v3 결함 (17c) 과 v4:
#     - P1 post 단독 거짓 완료: v3 은 requested 를 실행한 단계에서만 채웠다. v4 는 --manifest diag|full|all (기본 diag = 고정 수집 계약)
#       을 post 단독에도 적용한다. 빈 루트에서 post 를 부르면 diag 7 칸이 없으므로 실패한다 (exit 1). 칸 상태는 valid · hold · invalid ·
#       incomplete · missing 으로 나누고, 요청 칸은 없음 · 일부 · 무효 · 보류 · 짝 불일치를 따로 적는다.
#     - P1 궤적 · 지문 검사 부족: 실행 판정은 uncr_revalidate.py (채널 · 판정 구간 · 지문 형식 · env 대응 · USD 격리 기록) 가 한다.
#       통과 · 생존 집계도 재검사가 읽은 동결 바이트에서 나오며 np.nanmax 를 쓰지 않는다 (판정 구간 유한값이 확인된 뒤에만 센다).
#     - P1 오래된 full 관문: diag_gate.json 의 불리언을 읽지 않는다. full 은 --reval <revalidate.json> 을 받아, 지금 루트를 다시 재검사한
#       묶음 해시가 그 파일과 같고 · 재검사기 코드가 같고 · diag 7 칸이 둘 다에서 valid 이고 · diag 실행의 수집 코드와 체크포인트가
#       지금 동결본과 같을 때만 시작한다. 통과한 관문은 이 attempt 이름으로 full_gate_v4.json 에 적는다 (어느 실행도 이 파일을 근거로
#       읽지 않는다. 기록일 뿐).
#     - §5 출처: CODE 에 q_post.py · uncr_revalidate.py · 이 파일을 넣었다. 시작 때 코드 · 입력 (체크포인트 · 학습 yaml · 갈래 bundle ·
#       lab 지형 설정 두 파일) 해시를 동결하고, 실행마다 띄우기 전 · 끝난 뒤, 그리고 드라이버가 끝날 때 다시 대조한다.
#       새 stamp 의 code_sha256 은 실행 뒤 파일 상태가 아니라 동결본이다 (띄우기 전 · 끝난 뒤 둘 다 같음을 확인한 뒤에만 적는다).
#       v3 stamp (q_post 해시 없음) 의 실행은 재검사 보고에 「출처 미확인」 으로 남고, 수집 코드 다섯은 동결본과 같아야 재사용한다.
#     - §4: isaac_slot 의 --scan_dirs 에 out_branch (1043 학습 출력) 를 더했다.
#   v3 의 기록을 덮어쓰지 않는다: driver.json · diag_gate.json · UNCR-cells.csv 대신 driver_v4.json · post_v4.json · UNCR-cells-v4.csv ·
#   full_gate_v4.json 에 쓴다. post 가 쓴 재검사 결과는 out_uncr_reval/<시각>/revalidate.json.
#   판정 표기: crossed = 「낙상 전 몸통의 장애물 구간 끝 통과」. 네 발 도착 · 명령 준수 · 안전 통과가 아니다.
# 사용: python unseen_driver_cmdr_v4.py [--stages diag,post] [--stages post --manifest diag|full|all]
#                                      [--stages full,post --reval out_uncr_reval/<시각>/revalidate.json]
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

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
ROOT = os.environ.get("UNCR_ROOT", os.path.join(HERE, "out_uncr"))
STOPF = os.path.join(ROOT, "STOP")
REVAL_BASE = os.environ.get("UNCR_REVAL_ROOT", os.path.join(HERE, "out_uncr_reval"))
RV_PATH = os.path.abspath(os.environ.get("UNCR_REVAL_SCRIPT", os.path.join(HERE, "uncr_revalidate.py")))
_spec = importlib.util.spec_from_file_location("uncr_revalidate", RV_PATH)
RV = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RV)
E1, TRAIN_YAML, BR = RV.E1, RV.TRAIN_YAML, RV.BR
BR_NEW = os.path.join(HERE, "out_branch")
MODELS, TERRAINS, DIAG, FULL, MANIFEST = RV.MODELS, RV.TERRAINS, RV.DIAG, RV.FULL, RV.MANIFEST
EPISODES, EVAL_SEED, DIFF = RV.EPISODES, RV.EVAL_SEED, RV.DIFF
CODE_FILES = {f: os.path.join(HERE, f) for f in ("q_eval_cmdr.py", "q_metrics.py", "q_post.py", "isaac_slot.py", "usd_isolate_run.py",
                                                  "gpu_guard.py")}
CODE_FILES["uncr_revalidate.py"] = RV_PATH
CODE_FILES["unseen_driver_cmdr_v4.py"] = os.path.abspath(__file__)
CODE = list(CODE_FILES)
COLLECT_CODE, POST_CODE = RV.COLLECT_CODE, RV.POST_CODE
LAB_EVAL = "C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/sim/eval"
INPUT_FILES = {f"ckpt:{m}": s["ckpt"] for m, s in MODELS.items()}
INPUT_FILES["train_yaml"] = TRAIN_YAML
for _m in ("off", "on"):
    for _f in ("bundle.json", "bundle.npz"):
        INPUT_FILES[f"{_f}:{_m}"] = os.path.join(BR, f"cmdr_s1042_{_m}_u4000", _f)
INPUT_FILES["lab:generalization_env_cfg.py"] = f"{LAB_EVAL}/generalization_env_cfg.py"
INPUT_FILES["lab:terrains.py"] = f"{LAB_EVAL}/terrains.py"
ENV = dict(os.environ, CUDA_DEVICE_ORDER="PCI_BUS_ID", CUDA_VISIBLE_DEVICES="1", OMNI_KIT_ACCEPT_EULA="YES", PYTHONUNBUFFERED="1")
ATTEMPT = f"g1-{os.getpid()}-{time.strftime('%m%d%H%M%S')}"
SLOT = os.environ.get("UNCR_SLOT", os.path.join(HERE, "slot"))
LOG = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "version": "cmdr-4", "attempt": ATTEMPT, "root": ROOT, "models": MODELS,
       "revalidator": RV_PATH, "runs": [], "skipped": [], "stages": {}, "failures": []}
FROZEN = {"code": {}, "inputs": {}}


def save():
    p = os.path.join(ROOT, "driver_v4.json")
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


def code_sha():
    return {f: sha(p) for f, p in CODE_FILES.items()}


def inputs_sha():
    return {k: (sha(p) if os.path.exists(p) else None) for k, p in INPUT_FILES.items()}


def freeze():
    """17c 5: code and input manifest frozen at the start; compared again before and after every run and at the end."""
    FROZEN["code"] = code_sha()
    FROZEN["inputs"] = inputs_sha()


def frozen_now():
    c, i = code_sha(), inputs_sha()
    diff = [k for k in c if c[k] != FROZEN["code"].get(k)] + [k for k in i if i[k] != FROZEN["inputs"].get(k)]
    return not diff, diff


def fail(stage, what):
    LOG["failures"].append({"stage": stage, "what": what, "t": time.strftime("%H:%M:%S")})
    say(f"FAIL {stage}: {what}")
    save()


def keep_attempt(tag):
    """17b 2.5: the whole earlier attempt (result folder, log, guard, slot) moves to attempts/<tag>.<time>/."""
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


def run_one(tag, cmd, att, tries=3):
    rc = None
    for k in range(1, tries + 1):
        if os.path.exists(STOPF):
            return 98, k
        keep_attempt(tag)
        t0 = time.time()
        rc = subprocess.run([PY, "isaac_slot.py", "--watch_log", os.path.join(ROOT, f"{tag}.log"), "--record", os.path.join(ROOT, f"{tag}.slot.json"),
                             "--attempt", f"{att}-try{k}", "--usd_root", os.path.join(ROOT, "usd", f"{tag}-{att}-try{k}"),
                             "--lock", os.path.join(SLOT, "isaac_convert.lock"), "--registry", os.path.join(SLOT, "isaac_usd_registry.json"),
                             "--scan_dirs", ",".join([ROOT, BR, BR_NEW]), "--stop_file", STOPF, "--",
                             PY, "gpu_guard.py", "--gpu", "1", "--min_free_mib", "4096", "--log", os.path.join(ROOT, f"{tag}.log"),
                             "--summary", os.path.join(ROOT, f"{tag}.guard.json"), "--", PY, "usd_isolate_run.py"] + cmd, cwd=HERE, env=ENV).returncode
        say(f"RUN {tag} try {k} EXIT {rc} {time.time() - t0:.0f}s")
        if rc == 0:
            return 0, k
        if rc == 98:
            return rc, k
        time.sleep(300 if rc == 99 else 60 if rc == 96 else 30)
    return rc, tries


def tag_of(m, fam, cell):
    return f"uncr_{m}_{fam}_{cell}"


def outhash(tag):
    d = os.path.join(ROOT, tag)
    h = {f: sha(os.path.join(d, f)) for f in ("meta.json", "cells.json", "episodes.csv", "traj.npz", "env_origins.npy")}
    h.update({e: sha(os.path.join(ROOT, f"{tag}{e}")) for e in (".log", ".guard.json", ".slot.json")})
    return h


def check_alone(tag, require_stamp=True, attempt_prefix=None):
    rd = RV.Reader(ROOT)
    ck = {m: rd.ext_sha(f"ckpt:{m}", s["ckpt"]) for m, s in MODELS.items()}
    ys = rd.ext_sha("train_yaml", TRAIN_YAML)
    now = {f: (sha(os.path.join(HERE, f)) if os.path.exists(os.path.join(HERE, f)) else None) for f in RV.DATA_CODE + RV.NOTE_CODE}
    r = RV.check_run(ROOT, tag, rd, ck, ys, now, require_stamp=require_stamp, attempt_prefix=attempt_prefix)
    ch = rd.recheck()
    if ch:
        r["invalid"].append(f"[frozen] input changed during the check: {ch[:5]}")
        r["verdict"] = "invalid"
    return r


def reusable(m, fam, cell, tag):
    """v3-compatible stamp, collection code equal to the frozen code now, and the revalidation of the run valid."""
    try:
        with open(os.path.join(ROOT, tag, "driver_stamp.json"), encoding="utf-8") as f:
            st = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    code = st.get("code_sha256") or {}
    if any(code.get(f) != FROZEN["code"].get(f) for f in COLLECT_CODE):
        return False
    if POST_CODE in code and code[POST_CODE] != FROZEN["code"].get(POST_CODE):
        return False
    return check_alone(tag, True, st.get("attempt"))["verdict"] == "valid"


def write_stamp(tag):
    with open(os.path.join(ROOT, f"{tag}.slot.json"), encoding="utf-8") as f:
        s = json.load(f)
    st = {"attempt": s.get("attempt"), "out_sha256": outhash(tag), "code_sha256": dict(FROZEN["code"]), "t": time.strftime("%Y-%m-%d %H:%M:%S"),
          "driver_version": "cmdr-4", "inputs_sha256": dict(FROZEN["inputs"]),
          "code_checked": "code and inputs equal to the driver start before the launch and after the run"}
    p = os.path.join(ROOT, tag, "driver_stamp.json")
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1)
    os.replace(p + ".tmp", p)


def run_set(stage, cells):
    for spec in MODELS.values():
        assert os.path.exists(spec["ckpt"]), spec["ckpt"]
    for fam, cell in cells:
        for m in ("par", "off", "on"):
            tag = tag_of(m, fam, cell)
            if os.path.exists(STOPF):
                fail(stage, "stop file: not launching the rest")
                return
            ok, diff = frozen_now()
            if not ok:
                fail(stage, f"code or inputs changed since the driver start: {diff}; not launching the rest")
                return
            if reusable(m, fam, cell, tag):
                LOG["runs"].append({"stage": stage, "tag": tag, "reused": True, "valid": True})
                continue
            spec = MODELS[m]
            cmd = ["q_eval_cmdr.py", "--headless", "--tag", tag, "--policy", "student", "--checkpoint", spec["ckpt"], "--terrain_set", "unseen10",
                   "--families", fam, "--cells", cell, "--episodes", str(EPISODES), "--eval_seed", str(EVAL_SEED), "--difficulty", str(DIFF),
                   "--outdir", ROOT]
            if spec["yaml"]:
                cmd += ["--train_yaml", spec["yaml"]]
            att = f"{ATTEMPT}-{tag}"
            rc, k = run_one(tag, cmd, att)
            ok, diff = frozen_now()
            entry = {"stage": stage, "tag": tag, "rc": rc, "tries": k, "attempt": att}
            if rc != 0:
                why = f"exit {rc}"
            elif not ok:
                why = f"code or inputs changed during the run: {diff}"
            else:
                r = check_alone(tag, require_stamp=False, attempt_prefix=att)
                why = "" if r["verdict"] in ("valid", "hold") else "invalid: " + "; ".join(r["invalid"])[:400]
            if not why:
                write_stamp(tag)
                r = check_alone(tag, require_stamp=True, attempt_prefix=att)
                entry.update(verdict=r["verdict"], hold=r["hold"], invalid=r["invalid"])
                if r["verdict"] == "invalid":
                    why = "invalid after stamping: " + "; ".join(r["invalid"])[:400]
            entry.update(valid=not why and entry.get("verdict") == "valid", why=why)
            LOG["runs"].append(entry)
            if why:
                LOG["skipped"].append(tag)
                fail(stage, f"{tag}: {why}")
            save()
            if not ok:
                return


def old_counts(d):
    """information only: the old q_eval.py run of the parent (v3 cell_stats, np.nanmax, as before). Not a validity input."""
    with open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    fam = meta["args"]["families"]
    ze = meta["obstacle_zone_m"][fam][1]
    with np.load(os.path.join(d, "traj.npz")) as z:
        tr = z["traj"]
    org = np.load(os.path.join(d, "env_origins.npy"))
    surv = cross = 0
    with open(os.path.join(d, "episodes.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        e = int(r["env"])
        s = r["survived"] == "True"
        j = tr.shape[0] - 1 if s else max(0, int(round(float(r["fall_t"]) / 0.02)) - 1)
        surv += s
        cross += bool(np.nanmax(tr[: j + 1, e, 0] - org[e, 0]) >= ze)
    return cross, surv


def full_gate(reval_path):
    """17c 2.4 P1: full starts only on a revalidation bound to the data, code and checkpoints of now."""
    if not reval_path:
        return False, "no --reval: full needs the revalidate.json of this root made by uncr_revalidate.py and reviewed", None
    try:
        with open(reval_path, encoding="utf-8") as f:
            rv = json.load(f)
    except (OSError, json.JSONDecodeError) as ex:
        return False, f"--reval unreadable: {ex}", None
    if rv.get("kind") != "uncr_revalidate" or rv.get("version") != RV.VERSION:
        return False, f"--reval is not a {RV.VERSION} revalidation", None
    if RV.norm(rv.get("root") or "") != RV.norm(ROOT):
        return False, f"--reval is for root {rv.get('root')!r}, not {ROOT!r}", None
    if (rv.get("revalidator") or {}).get("sha256") != FROZEN["code"].get("uncr_revalidate.py"):
        return False, "--reval was made by other revalidator code", None
    if not rv.get("frozen_ok"):
        return False, "--reval saw its inputs change during the check", None
    fresh = RV.revalidate(ROOT)
    if not fresh["frozen_ok"]:
        return False, f"inputs changed during the gate revalidation: {fresh['changed_during_check'][:5]}", None
    if fresh["bundle_sha256"] != rv.get("bundle_sha256"):
        return False, (f"bundle {fresh['bundle_sha256'][:12]} now differs from --reval {str(rv.get('bundle_sha256'))[:12]}: the runs changed "
                       "since that revalidation, or it was made for other attempts"), None
    for fam, cell in DIAG:
        k = f"{fam}/{cell}"
        a = ((rv.get("cells") or {}).get(k) or {}).get("verdict")
        b = (fresh["cells"].get(k) or {}).get("verdict")
        if a != "valid" or b != "valid":
            return False, f"diag cell {k} is not valid (reviewed {a}, now {b})", None
    atts = {}
    for fam, cell in DIAG:
        for m in ("par", "off", "on"):
            r = fresh["runs"][tag_of(m, fam, cell)]
            code = r.get("code_at_collection") or {}
            diff = [f for f in COLLECT_CODE if code.get(f) != FROZEN["code"].get(f)]
            if POST_CODE in code and code[POST_CODE] != FROZEN["code"].get(POST_CODE):
                diff.append(POST_CODE)
            if diff:
                return False, f"{r['tag']} was collected with other code than now: {diff}", None
            atts[r["tag"]] = r.get("attempt")
    for m in MODELS:
        if fresh["models"][m]["sha256_now"] != FROZEN["inputs"].get(f"ckpt:{m}"):
            return False, f"checkpoint {m} differs from the frozen input", None
    gate = {"attempt": ATTEMPT, "t": time.strftime("%Y-%m-%d %H:%M:%S"), "reval_path": os.path.abspath(reval_path), "reval_file_sha256": sha(reval_path),
            "reval_t": rv.get("t"), "bundle_sha256": fresh["bundle_sha256"], "code_sha256": dict(FROZEN["code"]),
            "inputs_sha256": dict(FROZEN["inputs"]), "diag_attempts": atts}
    return True, "", gate


def stage_post(requested):
    rep = RV.revalidate(ROOT)
    try:
        rpath = RV.write_report(rep, REVAL_BASE)
    except (OSError, ValueError) as ex:
        rpath = ""
        fail("post", f"revalidation report not written: {ex}")
    rows = []
    cats = {k: [] for k in ("missing", "incomplete", "invalid", "hold", "unpaired")}
    for fam, cell in MANIFEST:
        key = f"{fam}/{cell}"
        c = rep["cells"].get(key)
        state = c["verdict"] if c else "missing"
        row = {"terrain": fam, "cell": cell, "in_diag": (fam, cell) in DIAG, "requested": (fam, cell) in requested, "state": state,
               "complete": state == "valid", "pair_ok": c.get("pair_ok") if c else None,
               "pair_diff": " ".join(c.get("pair_diff") or []) if c else "", "why": " | ".join(c.get("reasons") or [])[:400] if c else ""}
        for m in ("par", "off", "on"):
            r = rep["runs"].get(tag_of(m, fam, cell))
            row[f"{m}_verdict"] = r["verdict"] if r else "missing"
            if r and r["verdict"] in ("valid", "hold") and r.get("stats"):
                row.update({f"{m}_{k}": v for k, v in r["stats"].items()})
        if state == "valid":
            old = os.path.join(HERE, "out", f"un_e1_m20000_{fam}_{cell}")
            if os.path.exists(os.path.join(old, "cells.json")):
                oc, osv = old_counts(old)
                row["par_old_cross"], row["par_old_surv"] = oc, osv
                row["par_counts_match_old"] = (oc, osv) == (row["par_cross"], row["par_surv"])
        rows.append(row)
        if row["requested"] and state != "valid":
            cats["unpaired" if (state == "hold" and c and c.get("pair_ok") is False) else state].append(key)
    path = os.path.join(ROOT, "UNCR-cells-v4.csv")
    keys = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("terrain", "cell", "in_diag", "requested", "state", "complete", "pair_ok"), k))
    with open(path + ".tmp", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    os.replace(path + ".tmp", path)
    post = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "attempt": ATTEMPT, "requested": sorted(f"{f}/{c}" for f, c in requested),
            "reval": rpath, "bundle_sha256": rep["bundle_sha256"], "frozen_ok": rep["frozen_ok"], "rows": len(rows),
            "complete": sum(r["complete"] for r in rows), "counts": rep["counts"]}
    post.update({f"requested_{k}": v for k, v in cats.items()})
    p = os.path.join(ROOT, "post_v4.json")
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(post, f, ensure_ascii=False, indent=1)
    os.replace(p + ".tmp", p)
    LOG["stages"]["post"] = post
    if not rep["frozen_ok"]:
        fail("post", f"inputs changed during the revalidation: {rep['changed_during_check'][:5]}")
    bad = {k: v for k, v in cats.items() if v}
    if bad:
        fail("post", "requested cells not valid: " + "; ".join(f"{k} {v[:6]}" for k, v in bad.items()))
    say(f"POST rows {len(rows)} valid {post['complete']} requested not valid {sum(len(v) for v in cats.values())} reval {rpath}")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="diag,post")
    ap.add_argument("--manifest", choices=("diag", "full", "all"), default="diag",
                    help="cells post must find valid, also when post runs alone (default diag: the fixed collection contract)")
    ap.add_argument("--reval", default="", help="full: revalidate.json of this root made by uncr_revalidate.py and reviewed")
    a = ap.parse_args()
    st = [s for s in a.stages.split(",") if s]
    os.makedirs(ROOT, exist_ok=True)
    freeze()
    LOG.update(stages_requested=st, manifest=a.manifest, reval_arg=a.reval, code_sha256_start=FROZEN["code"],
               inputs_sha256_start=FROZEN["inputs"])
    say(f"START attempt {ATTEMPT} stages {st} manifest {a.manifest} root {ROOT}")
    save()
    unknown = [s for s in st if s not in ("diag", "full", "post")]
    if unknown or not st:
        fail("args", f"stages {st}: unknown {unknown}")
    else:
        requested = set({"diag": DIAG, "full": FULL, "all": MANIFEST}[a.manifest])
        if "diag" in st:
            os.makedirs(SLOT, exist_ok=True)
            run_set("diag", DIAG)
            requested |= set(DIAG)
        if "full" in st:
            requested |= set(FULL)
            ok, why, gate = full_gate(a.reval)
            if not ok:
                fail("full", f"gate not passed: {why}; full not started")
            else:
                LOG["full_gate"] = gate
                p = os.path.join(ROOT, "full_gate_v4.json")
                with open(p + ".tmp", "w", encoding="utf-8") as f:
                    json.dump(gate, f, ensure_ascii=False, indent=1)
                os.replace(p + ".tmp", p)
                os.makedirs(SLOT, exist_ok=True)
                run_set("full", FULL)
        if "post" in st:
            stage_post(requested)
    ok, diff = frozen_now()
    LOG["code_and_inputs_unchanged_at_end"] = ok
    if not ok:
        fail("end", f"code or inputs changed during this driver run: {diff}")
    LOG["finished" if not LOG["failures"] else "incomplete"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save()
    say("END " + ("finished" if not LOG["failures"] else f"incomplete {len(LOG['failures'])}"))
    sys.exit(0 if not LOG["failures"] else 1)


if __name__ == "__main__":
    main()
