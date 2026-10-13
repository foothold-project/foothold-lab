# CMD-R 미경험 지형 회귀 진단 v3 (lead · 2026-10-13 저녁 · GPU 1 · 학습 없음 · ASTRA 17 §5.2 · 17b §2.4 · §2.5 반영).
#   물음: CMD-R 갈래 학습 (시드 1042 · 24000) 이 부모 E1 20000 의 미경험 지형 능력을 바꿨나. 1042 한 학습 시드의 조건부 회귀
#         자료이며, 학습 시드 반복 · v2 공통 비교 · 1043 평가를 대신하지 않는다.
#   대상: 부모 E1 20000 · off 24000 · on 24000. 셋 다 q_eval_cmdr.py · 같은 명시 인자 (평가 시드 1000 · 난이도 0.5 · noise 끔 · student ·
#         100 판). 예전 un_e1_m20000_* (q_eval.py · full_record) 와는 「통과 · 생존 개수 일치」 만 별도 열로 적는다 (실행 재현 주장 아님).
#   출력: _eval/out_uncr/ 에만 쓴다. --full_record 를 쓰지 않는다. Isaac 은 isaac_slot.py (실행별 USD 루트 · attempt · 멈춤 파일)
#         → gpu_guard.py → usd_isolate_run.py → q_eval_cmdr.py 순서로만 띄운다.
#   v2 결함 (17b) 과 v3:
#     - 유효성: 형식 외에 checks_run (명령 전달 오차 0 · nonfinite 0) · checks_pre (student 경로 = act_inference · teacher 입력 무관) ·
#       traj.npz · env_origins.npy 를 열어 shape · 유한값 · episodes 의 env 범위를 본다. slot 기록의 attempt · 자식 종료 · 루트 밖 USD 없음.
#     - 짝: 칸마다 셋의 terrain_mesh · terrain_origins_sha256 · pairing_sha256 · pairing_sha256_ext 를 대조해 pair_ok 와 다른 항목을
#       남긴다. 짝이 안 맞으면 개별 통계는 남기되 짝 비교로 표시하지 않는다.
#     - diag 와 full 을 나눴다. 기본 단계는 diag,post 이고 full 은 명시해야 하며, diag_gate.json (diag 21 실행 모두 유효 · 7 칸 모두
#       pair_ok) 이 있어야 시작한다.
#     - 재시도는 결과 폴더까지 attempts/<tag>.<시각>/ 로 옮겨 보존한다. stamp 는 결과 · 로그 · guard · slot · 실행 코드 해시를 묶는다.
#     - post 는 고정 manifest (diag 7 칸 + full 30 칸) 를 늘 다 적고, 요청한 단계의 칸이 비거나 무효면 실패로 전파한다 (exit 1).
#     - 멈춤: _eval/out_uncr/STOP 이 생기면 다음 실행을 띄우지 않는다.
#   판정 표기: crossed = 「낙상 전 몸통의 장애물 구간 끝 통과」. 네 발 도착 · 명령 준수 · 안전 통과가 아니다.
# 사용: python unseen_driver_cmdr.py [--stages diag,post | full,post | post]
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
ROOT = os.environ.get("UNCR_ROOT", os.path.join(HERE, "out_uncr"))
STOPF = os.path.join(ROOT, "STOP")
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
CODE = ["q_eval_cmdr.py", "q_metrics.py", "isaac_slot.py", "usd_isolate_run.py", "gpu_guard.py", "unseen_driver_cmdr.py"]
PAIR_KEYS = ("terrain_mesh", "terrain_origins_sha256", "pairing_sha256", "pairing_sha256_ext")
ENV = dict(os.environ, CUDA_DEVICE_ORDER="PCI_BUS_ID", CUDA_VISIBLE_DEVICES="1", OMNI_KIT_ACCEPT_EULA="YES", PYTHONUNBUFFERED="1")
ATTEMPT = f"g1-{os.getpid()}-{time.strftime('%m%d%H%M%S')}"
SLOT = os.path.join(HERE, "slot")
LOG = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "version": "cmdr-3", "attempt": ATTEMPT, "root": ROOT, "models": MODELS,
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


def code_sha():
    return {f: sha(os.path.join(HERE, f)) for f in CODE}


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
                             "--scan_dirs", ",".join([ROOT, BR]), "--stop_file", STOPF, "--",
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


def validate_run(m, fam, cell, tag, att_prefix=None):
    d = os.path.join(ROOT, tag)
    spec = MODELS[m]
    try:
        s = json.load(open(os.path.join(ROOT, f"{tag}.slot.json"), encoding="utf-8"))
        if att_prefix and not str(s.get("attempt", "")).startswith(att_prefix):
            return f"slot attempt {s.get('attempt')!r}"
        if s.get("slot_rc") != 0 or s.get("child_rc") != 0 or s.get("state_at_release") != "scene_built":
            return f"slot rc {s.get('slot_rc')} child {s.get('child_rc')} state {s.get('state_at_release')}"
        if len(s.get("usd_final", [])) != 1 or s.get("usd_outside_root") or s.get("conflicts"):
            return f"slot usd {s.get('usd_final')} outside {s.get('usd_outside_root')} conflicts {s.get('conflicts')}"
        if not any(str(x).replace("\\", "/").endswith("usd_isolate_run.py") for x in s.get("cmd", [])):
            return "slot cmd without usd_isolate_run.py"
        g = json.load(open(os.path.join(ROOT, f"{tag}.guard.json"), encoding="utf-8"))
        if g.get("exit_code") != 0 or g.get("stopped_by_guard"):
            return f"guard exit {g.get('exit_code')} stopped {g.get('stopped_by_guard')}"
        log = open(os.path.join(ROOT, f"{tag}.log"), encoding="utf-8", errors="replace").read()
        if "Traceback (most recent call last)" in log or "</World/envs/env_0/Robot>: Unresolved reference" in log:
            return "Traceback or robot root reference failure in log"
        if f"[Q-EVAL] done {tag} N {EPISODES} " not in log:
            return "log has no completion line for this tag and N"
        meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
        a = meta["args"]
        want = {"terrain_set": "unseen10", "families": fam, "cells": cell, "episodes": EPISODES, "eval_seed": EVAL_SEED, "obs_noise": False,
                "full_record": False, "policy": "student", "difficulty": DIFF}
        for k, v in want.items():
            if a.get(k) != v:
                return f"arg {k}={a.get(k)!r} want {v!r}"
        if os.path.normcase(os.path.abspath(a.get("checkpoint", ""))) != os.path.normcase(os.path.abspath(spec["ckpt"])):
            return f"checkpoint {a.get('checkpoint')!r}"
        if os.path.normcase(os.path.abspath(a.get("outdir", ""))) != os.path.normcase(os.path.abspath(ROOT)):
            return f"outdir {a.get('outdir')!r}"
        if meta.get("checkpoint_sha256") != sha(spec["ckpt"]) or meta.get("loaded_iter") != spec["iter"]:
            return "checkpoint sha256 or loaded_iter"
        if spec["yaml"] and os.path.normcase(os.path.abspath((meta.get("train_yaml_source") or {}).get("train_yaml", ""))) != os.path.normcase(os.path.abspath(spec["yaml"])):
            return "train_yaml_source"
        cr, cp = meta.get("checks_run") or {}, meta.get("checks_pre") or {}
        if cr.get("nonfinite_action_or_obs_count") != 0:
            return f"nonfinite {cr.get('nonfinite_action_or_obs_count')}"
        if cr.get("obs_single_cmd_vs_target_max_abs") != 0.0 or cr.get("obs_history_latest_cmd_vs_target_max_abs") != 0.0:
            return "command did not reach the observation exactly"
        if cp.get("manual_student_path_vs_act_inference_max_abs") != 0.0 or cp.get("teacher_input_randomized_max_abs_action_change") != 0.0:
            return "checks_pre: student path or teacher independence"
        if meta.get("N") != EPISODES:
            return f"N {meta.get('N')}"
        c = json.load(open(os.path.join(d, "cells.json"), encoding="utf-8"))
        if len(c) != 1 or c[0].get("n") != EPISODES:
            return "cells.json n"
        rows = list(csv.DictReader(open(os.path.join(d, "episodes.csv"), encoding="utf-8")))
        if sorted(int(r["episode"]) for r in rows) != list(range(EPISODES)) or any(r["family"] != fam or r["cell"] != cell for r in rows):
            return "episodes.csv ids / family / cell"
        tr = np.load(os.path.join(d, "traj.npz"))["traj"]
        org = np.load(os.path.join(d, "env_origins.npy"))
        if tr.ndim != 3 or tr.shape[1] != org.shape[0] or tr.shape[2] < 3 or org.shape[1] != 3 or not np.isfinite(org).all():
            return f"traj / origins shape {tr.shape} {org.shape}"
        if max(int(r["env"]) for r in rows) >= tr.shape[1]:
            return "episodes env index out of range"
    except Exception as ex:  # noqa: BLE001
        return f"unreadable: {type(ex).__name__}: {ex}"
    return ""


def outhash(tag):
    d = os.path.join(ROOT, tag)
    h = {f: sha(os.path.join(d, f)) for f in ("meta.json", "cells.json", "episodes.csv", "traj.npz", "env_origins.npy")}
    h.update({e: sha(os.path.join(ROOT, f"{tag}{e}")) for e in (".log", ".guard.json", ".slot.json")})
    return h


def reusable(m, fam, cell, tag):
    p = os.path.join(ROOT, tag, "driver_stamp.json")
    try:
        st = json.load(open(p, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    try:
        if st.get("out_sha256") != outhash(tag) or st.get("code_sha256") != code_sha():
            return False
    except FileNotFoundError:
        return False
    return validate_run(m, fam, cell, tag, st.get("attempt")) == ""


def run_set(stage, cells):
    for spec in MODELS.values():
        assert os.path.exists(spec["ckpt"]), spec["ckpt"]
    for fam, cell in cells:
        for m in ("par", "off", "on"):
            tag = tag_of(m, fam, cell)
            if os.path.exists(STOPF):
                fail(stage, "stop file: not launching the rest")
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
            why = validate_run(m, fam, cell, tag, att) if rc == 0 else f"exit {rc}"
            LOG["runs"].append({"stage": stage, "tag": tag, "rc": rc, "tries": k, "valid": not why, "why": why, "attempt": att})
            if why:
                LOG["skipped"].append(tag)
                fail(stage, f"{tag}: {why}")
            else:
                s = json.load(open(os.path.join(ROOT, f"{tag}.slot.json"), encoding="utf-8"))
                json.dump({"attempt": s.get("attempt"), "out_sha256": outhash(tag), "code_sha256": code_sha(), "t": time.strftime("%Y-%m-%d %H:%M:%S")},
                          open(os.path.join(ROOT, tag, "driver_stamp.json"), "w", encoding="utf-8"), indent=1)
            save()


def cell_stats(d):
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


def pair_check(fam, cell):
    """17b 2.4: the three runs of a cell must share the evaluator's own fingerprints to be read as pairs."""
    metas = {m: json.load(open(os.path.join(ROOT, tag_of(m, fam, cell), "meta.json"), encoding="utf-8")) for m in ("par", "off", "on")}
    diff = []
    for k in PAIR_KEYS:
        vals = [json.dumps(metas[m].get(k), sort_keys=True) for m in ("par", "off", "on")]
        if metas["par"].get(k) is None or len(set(vals)) != 1:
            if isinstance(metas["par"].get(k), dict):
                diff += [f"{k}.{kk}" for kk in metas["par"][k] if len({json.dumps((metas[m].get(k) or {}).get(kk)) for m in ("par", "off", "on")}) != 1] or [k]
            else:
                diff.append(k)
    return not diff, diff


def stage_post(requested):
    rows, bad = [], []
    for fam, cell in MANIFEST:
        row = {"terrain": fam, "cell": cell, "in_diag": (fam, cell) in DIAG}
        ok = True
        for m in ("par", "off", "on"):
            tag = tag_of(m, fam, cell)
            if not reusable(m, fam, cell, tag):
                ok = False
                row[f"{m}_state"] = "missing or invalid"
                continue
            row.update({f"{m}_{k}": v for k, v in cell_stats(os.path.join(ROOT, tag)).items()})
        if ok:
            row["pair_ok"], dk = pair_check(fam, cell)
            row["pair_diff"] = " ".join(dk)
            old = os.path.join(HERE, "out", f"un_e1_m20000_{fam}_{cell}")
            if os.path.exists(os.path.join(old, "cells.json")):
                o = cell_stats(old)
                row["par_old_cross"], row["par_old_surv"] = o["cross"], o["surv"]
                row["par_counts_match_old"] = (o["cross"], o["surv"]) == (row["par_cross"], row["par_surv"])
        row["complete"] = ok
        rows.append(row)
        if (fam, cell) in requested and not ok:
            bad.append(f"{fam}/{cell}")
    path = os.path.join(ROOT, "UNCR-cells.csv")
    keys = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("terrain", "cell", "in_diag", "complete", "pair_ok"), k))
    with open(path + ".tmp", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    os.replace(path + ".tmp", path)
    diag_rows = [r for r in rows if r["in_diag"]]
    gate = {"diag_runs_valid": all(r["complete"] for r in diag_rows), "diag_pair_ok": all(r.get("pair_ok") for r in diag_rows),
            "t": time.strftime("%Y-%m-%d %H:%M:%S"), "attempt": ATTEMPT}
    json.dump(gate, open(os.path.join(ROOT, "diag_gate.json"), "w", encoding="utf-8"), indent=1)
    LOG["stages"]["post"] = {"rows": len(rows), "complete": sum(r["complete"] for r in rows), "requested_incomplete": bad, "diag_gate": gate}
    if bad:
        fail("post", f"requested cells incomplete: {bad[:6]}")
    say(f"POST rows {len(rows)} complete {LOG['stages']['post']['complete']} requested incomplete {len(bad)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="diag,post")
    a = ap.parse_args()
    st = a.stages.split(",")
    os.makedirs(ROOT, exist_ok=True)
    os.makedirs(SLOT, exist_ok=True)
    say(f"START attempt {ATTEMPT} stages {st} root {ROOT}")
    save()
    requested = set()
    if "diag" in st:
        run_set("diag", DIAG)
        requested |= set(DIAG)
    if "full" in st:
        try:
            gate = json.load(open(os.path.join(ROOT, "diag_gate.json"), encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            gate = {}
        if not (gate.get("diag_runs_valid") and gate.get("diag_pair_ok")):
            fail("full", f"diag gate not passed ({gate}); full not started")
        else:
            run_set("full", FULL)
            requested |= set(FULL)
    if "post" in st:
        stage_post(requested)
    LOG["finished" if not LOG["failures"] else "incomplete"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save()
    say("END " + ("finished" if not LOG["failures"] else f"incomplete {len(LOG['failures'])}"))
    sys.exit(0 if not LOG["failures"] else 1)


if __name__ == "__main__":
    main()
