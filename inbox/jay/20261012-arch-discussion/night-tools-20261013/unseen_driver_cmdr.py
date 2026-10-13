# CMD-R 미경험 지형 회귀 진단 (lead · 2026-10-13 저녁 · GPU 1 · 학습 없음) · v2 (ASTRA 17 §5.2 · §6 반영).
#   물음: CMD-R 갈래 학습 (시드 1042 · 24000) 이 부모 E1 20000 의 미경험 지형 능력을 바꿨나. 1042 한 학습 시드의 조건부
#         회귀 자료이며, 학습 시드 반복이나 v2 공통 비교를 대신하지 않는다.
#   대상 (manifest MODELS): 부모 E1 20000 · off 24000 · on 24000. 셋 다 같은 평가기 q_eval_cmdr.py 로 새로 잰다
#         (예전 un_e1_m20000_* 는 q_eval.py · --full_record 로 잰 것이라 섞지 않는다. 부모 새 값과 예전 값의 일치 여부는
#         재현 확인으로만 기록한다).
#   출력: 새 루트 _eval/out_uncr/ 에만 쓴다 (로그 · guard · slot · 결과 · 상태 · 집계). --full_record 를 쓰지 않는다
#         (full_record.py 는 출력 폴더를 _eval/out/full 로 고정해 쓰기 때문). 기존 _eval/out 과 동결 폴더에는 쓰지 않는다.
#   Isaac 실행은 모두 isaac_slot.py (변환 구간 OS 잠금 · USD 폴더 하나 · 다른 로그와 겹침 없음) → gpu_guard.py 를 거친다.
#   단계: diag (7 칸 × 셋 = 21 실행) → 통과하면 full (10 종 × fwd05 · fwd03 · fwd10 × 셋, diag 와 겹치는 칸은 재사용).
#   판정 표기: crossed = 「낙상 전 몸통의 장애물 구간 끝 통과」 (UNSEEN-E12 정의). 네 발 도착 · 명령 준수 · 안전 통과가 아니다.
# 사용: python unseen_driver_cmdr.py [--stages diag,full,post]
import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
ROOT = os.path.join(HERE, "out_uncr")
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
EPISODES = 100
ENV = dict(os.environ, CUDA_DEVICE_ORDER="PCI_BUS_ID", CUDA_VISIBLE_DEVICES="1", OMNI_KIT_ACCEPT_EULA="YES", PYTHONUNBUFFERED="1")
ATTEMPT = f"g1-{os.getpid()}-{time.strftime('%m%d%H%M%S')}"
SLOT = os.path.join(HERE, "slot")
LOG = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "version": "cmdr-2", "attempt": ATTEMPT, "root": ROOT, "models": MODELS,
       "runs": [], "skipped": [], "stages": {}, "failures": []}


def save():
    p = os.path.join(ROOT, "driver.json")
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


def fail(stage, what):
    LOG["failures"].append({"stage": stage, "what": what, "t": time.strftime("%H:%M:%S")})
    say(f"FAIL {stage}: {what}")
    save()


def keep_attempt(*names):
    for n in names:
        full = os.path.join(ROOT, n)
        if os.path.exists(full):
            d = os.path.join(ROOT, "attempts")
            os.makedirs(d, exist_ok=True)
            stamp_ = time.strftime("%Y%m%d-%H%M%S", time.localtime(os.path.getmtime(full)))
            shutil.move(full, os.path.join(d, f"{n}.{stamp_}"))


def py_traceback(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "Traceback (most recent call last)" in f.read()
    except FileNotFoundError:
        return False


def guarded(tag, cmd, tries=4, wait_s=300):
    rc = None
    for k in range(1, tries + 1):
        keep_attempt(f"{tag}.log", f"{tag}.guard.json", f"{tag}.slot.json")
        t0 = time.time()
        rc = subprocess.run([PY, "isaac_slot.py", "--watch_log", os.path.join(ROOT, f"{tag}.log"), "--record", os.path.join(ROOT, f"{tag}.slot.json"),
                             "--lock", os.path.join(SLOT, "isaac_convert.lock"), "--registry", os.path.join(SLOT, "isaac_usd_registry.json"),
                             "--scan_dirs", ",".join([ROOT, BR]), "--",
                             PY, "gpu_guard.py", "--gpu", "1", "--min_free_mib", "4096", "--log", os.path.join(ROOT, f"{tag}.log"),
                             "--summary", os.path.join(ROOT, f"{tag}.guard.json"), "--"] + cmd, cwd=HERE, env=ENV).returncode
        say(f"RUN {tag} try {k} EXIT {rc} {time.time() - t0:.0f}s")
        if rc == 0 and py_traceback(os.path.join(ROOT, f"{tag}.log")):
            say(f"  {tag}: exit 0 but a Python Traceback is in the log; counted as error 1")
            rc = 1
        if rc == 0:
            return 0, k
        if rc == 99:
            say(f"GUARD STOP {tag}: free < 4096 MiB on GPU 1, waiting {wait_s}s")
            time.sleep(wait_s)
        elif rc == 96:
            say(f"USD folder conflict {tag}: retry after 60 s with a new conversion")
            time.sleep(60)
        else:
            time.sleep(30)
    return rc, tries


def tag_of(m, fam, cell):
    return f"uncr_{m}_{fam}_{cell}"


def validate_run(m, fam, cell, tag):
    d = os.path.join(ROOT, tag)
    spec = MODELS[m]
    try:
        g = json.load(open(os.path.join(ROOT, f"{tag}.guard.json"), encoding="utf-8"))
        if g.get("exit_code") != 0 or g.get("stopped_by_guard"):
            return f"guard exit {g.get('exit_code')} stopped {g.get('stopped_by_guard')}"
        s = json.load(open(os.path.join(ROOT, f"{tag}.slot.json"), encoding="utf-8"))
        if s.get("slot_rc") != 0 or s.get("conflicts") or len(s.get("usd_final", [])) != 1:
            return f"slot rc {s.get('slot_rc')} usd {s.get('usd_final')} conflicts {s.get('conflicts')}"
        log = open(os.path.join(ROOT, f"{tag}.log"), encoding="utf-8", errors="replace").read()
        if "Traceback (most recent call last)" in log:
            return "Python Traceback in log"
        if f"[Q-EVAL] done {tag} N {EPISODES} " not in log:
            return "log has no completion line for this tag and N"
        meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
        a = meta["args"]
        want = {"terrain_set": "unseen10", "families": fam, "cells": cell, "episodes": EPISODES, "eval_seed": 1000, "obs_noise": False,
                "full_record": False, "policy": "student", "difficulty": 0.5}
        for k, v in want.items():
            if a.get(k) != v:
                return f"arg {k}={a.get(k)!r} want {v!r}"
        if os.path.normcase(os.path.abspath(a.get("checkpoint", ""))) != os.path.normcase(os.path.abspath(spec["ckpt"])):
            return f"checkpoint {a.get('checkpoint')!r}"
        if os.path.normcase(os.path.abspath(a.get("outdir", ""))) != os.path.normcase(os.path.abspath(ROOT)):
            return f"outdir {a.get('outdir')!r}"
        if meta.get("checkpoint_sha256") != sha(spec["ckpt"]):
            return "checkpoint sha256"
        if meta.get("loaded_iter") != spec["iter"]:
            return f"loaded_iter {meta.get('loaded_iter')}"
        if spec["yaml"]:
            src = meta.get("train_yaml_source") or {}
            if os.path.normcase(os.path.abspath(src.get("train_yaml", ""))) != os.path.normcase(os.path.abspath(spec["yaml"])):
                return "train_yaml_source"
        if meta.get("N") != EPISODES:
            return f"N {meta.get('N')}"
        c = json.load(open(os.path.join(d, "cells.json"), encoding="utf-8"))
        if len(c) != 1 or c[0].get("n") != EPISODES:
            return "cells.json n"
        rows = list(csv.DictReader(open(os.path.join(d, "episodes.csv"), encoding="utf-8")))
        if sorted(int(r["episode"]) for r in rows) != list(range(EPISODES)) or any(r["family"] != fam or r["cell"] != cell for r in rows):
            return "episodes.csv ids / family / cell"
        for f in ("traj.npz", "env_origins.npy"):
            if not os.path.exists(os.path.join(d, f)):
                return f"missing {f}"
    except Exception as ex:  # noqa: BLE001
        return f"unreadable: {type(ex).__name__}: {ex}"
    return ""


def outhash(tag):
    d = os.path.join(ROOT, tag)
    return {f: sha(os.path.join(d, f)) for f in ("meta.json", "cells.json", "episodes.csv", "traj.npz", "env_origins.npy")}


def reusable(m, fam, cell, tag):
    p = os.path.join(ROOT, tag, "driver_stamp.json")
    if not os.path.exists(p):
        return False
    try:
        if json.load(open(p, encoding="utf-8")).get("out_sha256") != outhash(tag):
            return False
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    return validate_run(m, fam, cell, tag) == ""


def run_set(stage, cells):
    for spec in MODELS.values():
        assert os.path.exists(spec["ckpt"]), spec["ckpt"]
    for fam, cell in cells:
        for m in ("par", "off", "on"):
            tag = tag_of(m, fam, cell)
            if reusable(m, fam, cell, tag):
                LOG["runs"].append({"stage": stage, "tag": tag, "reused": True, "valid": True})
                continue
            spec = MODELS[m]
            cmd = [PY, "q_eval_cmdr.py", "--headless", "--tag", tag, "--policy", "student", "--checkpoint", spec["ckpt"],
                   "--terrain_set", "unseen10", "--families", fam, "--cells", cell, "--episodes", str(EPISODES), "--outdir", ROOT]
            if spec["yaml"]:
                cmd += ["--train_yaml", spec["yaml"]]
            rc, k = guarded(tag, cmd)
            why = validate_run(m, fam, cell, tag) if rc == 0 else f"exit {rc}"
            LOG["runs"].append({"stage": stage, "tag": tag, "rc": rc, "tries": k, "valid": not why, "why": why, "attempt": ATTEMPT})
            if why:
                LOG["skipped"].append(tag)
                fail(stage, f"{tag}: {why}")
            else:
                json.dump({"attempt": ATTEMPT, "out_sha256": outhash(tag), "t": time.strftime("%Y-%m-%d %H:%M:%S")},
                          open(os.path.join(ROOT, tag, "driver_stamp.json"), "w", encoding="utf-8"), indent=1)
            save()


def cell_stats(d):
    """UNSEEN-E12 와 같은 정의: crossed = 낙상 전 (fall_t 로 자름) 몸통 x 가 장애물 구간 끝을 넘음."""
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    fam = meta["args"]["families"]
    ze = meta["obstacle_zone_m"][fam][1]
    tr = np.load(os.path.join(d, "traj.npz"))["traj"]
    org = np.load(os.path.join(d, "env_origins.npy"))
    n = surv = cross = alive_cross = 0
    for r in csv.DictReader(open(os.path.join(d, "episodes.csv"), encoding="utf-8")):
        e = int(r["env"])
        s = r["survived"] == "True"
        j = tr.shape[0] - 1 if s else max(0, int(round(float(r["fall_t"]) / 0.02)) - 1)
        c = bool(np.nanmax(tr[: j + 1, e, 0] - org[e, 0]) >= ze)
        n += 1
        surv += s
        cross += c
        alive_cross += c and s
    return {"n": n, "surv": surv, "cross": cross, "alive_cross": alive_cross, "zone_end": round(ze, 3)}


def stage_post(cells):
    rows = []
    for fam, cell in cells:
        row = {"terrain": fam, "cell": cell}
        ok = True
        for m in ("par", "off", "on"):
            tag = tag_of(m, fam, cell)
            if validate_run(m, fam, cell, tag):
                ok = False
                continue
            x = cell_stats(os.path.join(ROOT, tag))
            row.update({f"{m}_{k}": v for k, v in x.items()})
        old = os.path.join(HERE, "out", f"un_e1_m20000_{fam}_{cell}")
        if ok and os.path.exists(os.path.join(old, "cells.json")):
            o = cell_stats(old)
            row["par_old_cross"], row["par_old_surv"] = o["cross"], o["surv"]
            row["par_reproduces_old"] = (o["cross"], o["surv"]) == (row["par_cross"], row["par_surv"])
        row["complete"] = ok
        rows.append(row)
    path = os.path.join(ROOT, "UNCR-cells.csv")
    keys = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("terrain", "cell"), k))
    with open(path + ".tmp", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    os.replace(path + ".tmp", path)
    LOG["stages"]["post"] = {"rows": len(rows), "complete": sum(r["complete"] for r in rows)}
    say(f"POST rows {len(rows)} complete {LOG['stages']['post']['complete']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="diag,full,post")
    a = ap.parse_args()
    st = a.stages.split(",")
    os.makedirs(ROOT, exist_ok=True)
    os.makedirs(SLOT, exist_ok=True)
    say(f"START attempt {ATTEMPT} stages {st} root {ROOT}")
    save()
    if "diag" in st:
        run_set("diag", DIAG)
        diag_bad = [t for t in LOG["skipped"]]
        LOG["stages"]["diag"] = {"invalid": diag_bad}
        if diag_bad:
            fail("diag", f"{len(diag_bad)} invalid runs; full stage not started")
            st = [s for s in st if s != "full"]
    if "full" in st:
        run_set("full", FULL)
    if "post" in st:
        stage_post(DIAG + [c for c in FULL if c not in DIAG] if "full" in st else DIAG)
    LOG["finished" if not LOG["failures"] else "incomplete"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save()
    say("END " + ("finished" if not LOG["failures"] else f"incomplete {len(LOG['failures'])}"))
    sys.exit(0 if not LOG["failures"] else 1)


if __name__ == "__main__":
    main()
