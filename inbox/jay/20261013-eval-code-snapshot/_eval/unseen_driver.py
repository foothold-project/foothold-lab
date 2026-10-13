# Overnight driver for UNSEEN-E12 (2026-10-12 night, GPU 1 only, no training).
#   eval   : q_eval --terrain_set unseen10, one terrain x one cell x 100 episodes per run (100 envs; 1,100 do not fit
#            GPU 1), --full_record, student path, noise off, difficulty 0.5, eval seed 1000 (E1 and E2 paired)
#            models: E1 / E2 x model_20000 (fwd05, fwd03) and model_20499 (fwd05, fwd03, fwd10)
#   post   : unseen_post.py (survival, Q1, Q3, crossed)
#   videos : first success / first failure per run: label-strip replay (q_video, frame gate) -> lab-format parquet
#            (fr_to_legacy) -> HUD + web copy (hud_make, frame gate)
#   audit  : frame_audit on every new video, every frame; web list
# Every GPU 1 process runs under gpu_guard.py --gpu 1 --min_free_mib 4096. A run stopped by the guard (exit 99) is
# retried after 5 min (display GPU load changes), at most 4 times, then skipped and listed in out/unseen_driver.json.
# v2 (lead, 10/13 10:07, VERIFY-astra-15 9.3; v1 kept as unseen_driver_v1.py). v1 counted a run as done when the
# process exited 0 or cells.json existed, ignored the post-process return code, reused a video because the file
# existed, and audited only the files that existed. v2:
#   - exit 0 is not success: a Python traceback in the log is error 1 (Isaac Kit exits 0 after an uncaught exception),
#     and validate_run() checks the guard summary, the evaluator's own completion line for this tag and N, the meta
#     args against this run's contract, the checkpoint sha256, cells.json / episodes.csv (100 episodes, ids 0..99) and
#     the full record summary (each written representative episode exists and agrees with episodes.csv on survival).
#   - a finished run is reused only when its stamp (out/<tag>/driver_stamp.json) still matches the output hashes and
#     validate_run() passes again; runs from v1 have no stamp and are validated and stamped now.
#   - every attempt keeps its log: an earlier log / guard summary of the same name is moved to out/attempts/ first.
#   - post: non-zero exit or an UNSEEN-cells.csv without exactly one row per planned tag stops the driver (incomplete).
#   - videos: each of the 144 selected episodes needs a replay, a HUD and a web copy that decode to exactly the source
#     episode's row count (ffprobe -count_frames); a failed fr_to_legacy / hud_make is a failure, not a log line.
#   - audit: the expected set is every selected episode x (replay, HUD, web); a missing file is a failure.
#   - "finished" is written only when every stage passed; otherwise "incomplete" lists why and the exit code is 1.
# Usage: python unseen_driver.py [--stages eval,post,videos,audit]
import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
OUT = os.path.join(HERE, "out")
E = {"E1": "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192",
     "E2": "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-11_12-39-32_e2_seed43_n8192"}
TERRAINS = ["discrete_obstacles", "wave", "stepping_stones", "gap", "pit", "rails", "star", "floating_ring", "repeated_boxes", "repeated_cylinders"]
SHORT = {"discrete_obstacles": "disc_obst", "stepping_stones": "step_stones", "floating_ring": "float_ring",
         "repeated_boxes": "rep_boxes", "repeated_cylinders": "rep_cyl"}
CELLS = {"20000": ["fwd05", "fwd03"], "20499": ["fwd05", "fwd03", "fwd10"]}
EPISODES = 100
ENV = dict(os.environ, CUDA_DEVICE_ORDER="PCI_BUS_ID", CUDA_VISIBLE_DEVICES="1", OMNI_KIT_ACCEPT_EULA="YES", PYTHONUNBUFFERED="1")
ATTEMPT = f"g1-{os.getpid()}-{time.strftime('%m%d%H%M%S')}"
OUT_FILES = ("meta.json", "cells.json", "episodes.csv")
LOG = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "version": "2", "attempt": ATTEMPT, "runs": [], "skipped": [], "videos": [],
       "stages": {}, "failures": []}


def save():
    p = os.path.join(OUT, "unseen_driver.json")
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


def keep_attempt(*paths):
    """Move an earlier attempt's log / guard summary aside so a retry does not overwrite its failure record."""
    for p in paths:
        full = os.path.join(HERE, p)
        if os.path.exists(full):
            d = os.path.join(OUT, "attempts")
            os.makedirs(d, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(os.path.getmtime(full)))
            shutil.move(full, os.path.join(d, f"{os.path.basename(full)}.{stamp}"))


def py_traceback(log_path):
    try:
        with open(os.path.join(HERE, log_path), encoding="utf-8", errors="replace") as f:
            return "Traceback (most recent call last)" in f.read()
    except FileNotFoundError:
        return False


def guarded(name, cmd, log_path, summary_path, tries=4, wait_s=300):
    rc = None
    for k in range(1, tries + 1):
        keep_attempt(log_path, summary_path)
        t0 = time.time()
        rc = subprocess.run([PY, "gpu_guard.py", "--gpu", "1", "--min_free_mib", "4096", "--log", log_path, "--summary", summary_path, "--"] + cmd,
                            cwd=HERE, env=ENV).returncode
        say(f"RUN {name} try {k} EXIT {rc} {time.time() - t0:.0f}s")
        if rc == 0 and py_traceback(log_path):
            say(f"  {name}: exit 0 but a Python Traceback is in the log; counted as error 1")
            rc = 1
        if rc == 0:
            return 0, k
        if rc == 99:
            say(f"GUARD STOP {name}: free < 4096 MiB on GPU 1, waiting {wait_s}s")
            time.sleep(wait_s)
        else:
            time.sleep(30)
    return rc, tries


def tags():
    out = []
    for cell in ("fwd05", "fwd03", "fwd10"):
        for it in ("20499", "20000"):
            if cell not in CELLS[it]:
                continue
            for run in ("E1", "E2"):
                for fam in TERRAINS:
                    out.append((run, it, fam, cell, f"un_{run.lower()}_m{it}_{fam}_{cell}"))
    return out


def validate_run(run, it, fam, cell, tag):
    """'' if out/<tag> is a complete, correct result for exactly this run, else the reason."""
    d = os.path.join(OUT, tag)
    ckpt = f"{E[run]}/model_{it}.pt"
    try:
        g = json.load(open(os.path.join(OUT, f"{tag}.guard.json"), encoding="utf-8"))
        if g.get("exit_code") != 0 or g.get("stopped_by_guard"):
            return f"guard exit {g.get('exit_code')} stopped {g.get('stopped_by_guard')}"
        log = open(os.path.join(OUT, f"{tag}.log"), encoding="utf-8", errors="replace").read()
        if "Traceback (most recent call last)" in log:
            return "Python Traceback in log"
        if f"[Q-EVAL] done {tag} N {EPISODES} " not in log:
            return "log has no completion line for this tag and N"
        m = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
        a = m["args"]
        want = {"terrain_set": "unseen10", "families": fam, "cells": cell, "episodes": EPISODES, "eval_seed": 1000, "obs_noise": False,
                "full_record": True, "policy": "student", "difficulty": 0.5, "checkpoint": ckpt}
        for k, v in want.items():
            if a.get(k) != v:
                return f"arg {k}={a.get(k)!r} want {v!r}"
        if m.get("checkpoint_sha256") != sha(ckpt):
            return "checkpoint sha256"
        if m.get("N") != EPISODES:
            return f"N {m.get('N')}"
        c = json.load(open(os.path.join(d, "cells.json"), encoding="utf-8"))
        if len(c) != 1 or c[0].get("n") != EPISODES:
            return "cells.json n"
        rows = list(csv.DictReader(open(os.path.join(d, "episodes.csv"), encoding="utf-8")))
        if sorted(int(r["episode"]) for r in rows) != list(range(EPISODES)) or any(r["family"] != fam or r["cell"] != cell for r in rows):
            return "episodes.csv ids / family / cell"
        # the full record keeps only representative episodes (first success / failure, median MAE): one summary row per
        # written file (out/full/<tag>/SCHEMA.md). Each row must name a file that exists, an episode of this run, and
        # agree with episodes.csv on survival.
        fs = list(csv.DictReader(open(os.path.join(OUT, "full", tag, "episodes_summary.csv"), encoding="utf-8")))
        surv = {int(r["episode"]): r["survived"] for r in rows}
        if not fs:
            return "full record summary empty"
        for r in fs:
            if not os.path.exists(os.path.join(OUT, "full", tag, r["file"])):
                return f"full record file missing {r['file']}"
            e = int(r["episode"])
            if e not in surv or r["survived"] != surv[e]:
                return f"full record episode {e} does not match episodes.csv"
    except Exception as ex:  # noqa: BLE001
        return f"unreadable: {type(ex).__name__}: {ex}"
    return ""


def outhash(tag):
    return {f: sha(os.path.join(OUT, tag, f)) for f in OUT_FILES} | {"full_summary": sha(os.path.join(OUT, "full", tag, "episodes_summary.csv"))}


def reusable(spec):
    tag = spec[-1]
    p = os.path.join(OUT, tag, "driver_stamp.json")
    if os.path.exists(p):
        try:
            if json.load(open(p, encoding="utf-8")).get("out_sha256") != outhash(tag):
                return False
        except FileNotFoundError:
            return False
    elif not os.path.exists(os.path.join(OUT, tag, "cells.json")):
        return False
    return validate_run(*spec) == ""


def stamp(tag, attempt):
    json.dump({"attempt": attempt, "out_sha256": outhash(tag), "t": time.strftime("%Y-%m-%d %H:%M:%S")},
              open(os.path.join(OUT, tag, "driver_stamp.json"), "w", encoding="utf-8"), indent=1)


def stage_eval():
    for spec in tags():
        run, it, fam, cell, tag = spec
        if reusable(spec):
            old = os.path.join(OUT, tag, "driver_stamp.json")
            stamp(tag, json.load(open(old, encoding="utf-8")).get("attempt") if os.path.exists(old) else "v1")
            LOG["runs"].append({"tag": tag, "reused": True, "valid": True})
            continue
        cmd = [PY, "q_eval.py", "--headless", "--tag", tag, "--policy", "student", "--checkpoint", f"{E[run]}/model_{it}.pt",
               "--terrain_set", "unseen10", "--families", fam, "--cells", cell, "--episodes", str(EPISODES), "--full_record"]
        rc, k = guarded(tag, cmd, f"out/{tag}.log", f"out/{tag}.guard.json")
        why = validate_run(*spec) if rc == 0 else f"exit {rc}"
        LOG["runs"].append({"tag": tag, "rc": rc, "tries": k, "valid": not why, "why": why, "attempt": ATTEMPT})
        if why:
            LOG["skipped"].append(tag)
            fail("eval", f"{tag}: {why}")
        else:
            stamp(tag, ATTEMPT)
        save()


def stage_post():
    r = subprocess.run([PY, "unseen_post.py"], cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace")
    say("POST " + (r.stdout.strip()[-400:] or r.stderr[-400:]))
    LOG["stages"]["post_rc"] = r.returncode
    if r.returncode != 0:
        fail("post", f"unseen_post.py exit {r.returncode}: {(r.stderr or '')[-300:]}")
        return
    rows = list(csv.DictReader(open(os.path.join(OUT, "UNSEEN-cells.csv"), encoding="utf-8")))
    have = sorted(r["tag"] for r in rows)
    want = sorted(t for *_, t in tags())
    if have != want:
        fail("post", f"UNSEEN-cells.csv rows {len(have)} want {len(want)} · missing {sorted(set(want) - set(have))[:5]} · extra {sorted(set(have) - set(want))[:5]}")


def selection():
    items = []
    for run, it, fam, cell, tag in tags():
        sp = os.path.join(OUT, "full", tag, "episodes_summary.csv")
        if not os.path.exists(sp):
            fail("videos", f"{tag}: no full record summary")
            continue
        rows = list(csv.DictReader(open(sp, encoding="utf-8")))
        for lab in ("first_success", "first_failure"):
            hit = next((r for r in rows if lab in r["labels"]), None)
            if not hit:
                continue  # a run with no success (or no failure) has nothing to pick: not a failure
            key = hit["file"][:-4]
            items.append({"key": f"{tag}/{key}", "tag": tag, "file": hit["file"], "pick": lab, "run": run, "model": it, "terrain": fam, "cell": cell,
                          "rows": int(hit["rows"]),
                          "video": os.path.join(OUT, "video_hud_src", tag, key + "_kinreplay.mp4"),
                          "parquet": os.path.join(OUT, "legacy", tag, "timeseries", key + ".parquet"),
                          "hud": os.path.join(OUT, "video_hud", tag, key + "_kinreplay_hud.mp4"),
                          "web": os.path.join(OUT, "web", tag, key + "_kinreplay_hud_web.mp4"),
                          "title": f"{run} {it} {SHORT.get(fam, fam)} {cell} ep{int(hit['episode'])}"})
    json.dump(items, open(os.path.join(OUT, "unseen_sel.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return items


def frames(path):
    """decoded frame count, or -1 if the file is missing or does not decode."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return -1
    r = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    try:
        return int(r.stdout.strip().split(",")[0]) if r.returncode == 0 else -1
    except ValueError:
        return -1


def video_ok(x, k):
    return frames(x[k]) == x["rows"]


def stage_videos():
    items = selection()
    by = {}
    for x in items:
        by.setdefault(x["tag"], []).append(x)
    for tag, xs in by.items():
        for attempt in range(1, 4):
            left = [x["file"] for x in xs if not video_ok(x, "video")]
            if not left:
                break
            cmd = [PY, "q_video.py", "--run_tag", tag, "--files", ",".join(left), "--overlay", "label", "--out_root", "video_hud_src", "--sim_device", "cpu"]
            guarded(f"video {tag}", cmd, f"out/video_hud_src/{tag}.log", f"out/video_hud_src/{tag}.guard.json", tries=4)
        left = [x["file"] for x in xs if not video_ok(x, "video")]
        LOG["videos"].append({"tag": tag, "requested": len(xs), "missing_or_wrong_frames": left})
        if left:
            fail("videos", f"{tag}: replay missing or frame count != source rows: {left}")
        r = subprocess.run([PY, "fr_to_legacy.py", "--tag", tag], cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            fail("videos", f"fr_to_legacy {tag} exit {r.returncode}: {(r.stderr or '')[-300:]}")
        save()
    r = subprocess.run([PY, "hud_make.py", "--list", "out/unseen_sel.json", "--workers", "12", "--stills", "0.1,0.45,0.55,0.9",
                        "--report", "out/unseen_hud_report.json"], cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace")
    LOG["stages"]["hud_make_rc"] = r.returncode
    say(f"HUD rc {r.returncode} {r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ''}")
    if r.returncode != 0:
        fail("videos", f"hud_make exit {r.returncode}: {(r.stderr or '')[-300:]}")
    bad = [f"{x['key']} {k}" for x in items for k in ("hud", "web") if not video_ok(x, k)]
    if bad:
        fail("videos", f"HUD / web missing or frame count != source rows: {len(bad)} · {bad[:6]}")
    save()


def stage_audit():
    items = json.load(open(os.path.join(OUT, "unseen_sel.json"), encoding="utf-8"))
    expected = [x[k] for x in items for k in ("video", "hud", "web")]
    missing = [f for f in expected if not os.path.exists(f)]
    files = [f for f in expected if os.path.exists(f)]
    lst = os.path.join(OUT, "unseen_audit_files.txt")
    open(lst, "w", encoding="utf-8").write("\n".join(files))
    sys.path.insert(0, HERE)
    import frame_audit
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(16) as ex:
        res = list(ex.map(frame_audit.audit, files, [0] * len(files)))
    json.dump(res, open(os.path.join(OUT, "unseen_frame_audit.json"), "w", encoding="utf-8"), indent=1)
    bad = [x["file"] for x in res if x["bad"]]
    LOG["stages"]["audit"] = {"expected": len(expected), "audited": len(res), "missing": missing, "bad": bad}
    if missing or bad:
        fail("audit", f"expected {len(expected)} · missing {len(missing)} · bad frames in {len(bad)}")
    rows = []
    for x in items:
        vj = x["video"][:-4] + ".json"
        q = json.load(open(vj, encoding="utf-8")).get("q_line", "") if os.path.exists(vj) else ""
        rows.append({"run": x["run"], "model": x["model"], "terrain": x["terrain"], "cell": x["cell"], "pick": x["pick"], "title": x["title"],
                     "q_line": q, "web": os.path.relpath(x["web"], HERE).replace("\\", "/") if os.path.exists(x["web"]) else "",
                     "web_bytes": os.path.getsize(x["web"]) if os.path.exists(x["web"]) else ""})
    with open(os.path.join(OUT, "unseen_web_list.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    say(f"AUDIT expected {len(expected)} missing {len(missing)} bad {len(bad)} web {sum(1 for r in rows if r['web'])}/{len(rows)}")
    save()


if __name__ == "__main__":  # the audit stage uses a process pool: on Windows (spawn) the children re-import this file
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="eval,post,videos,audit")
    a = ap.parse_args()
    for st in a.stages.split(","):
        say(f"STAGE {st}")
        {"eval": stage_eval, "post": stage_post, "videos": stage_videos, "audit": stage_audit}[st]()
    if LOG["failures"]:
        LOG["incomplete"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save()
        say(f"UNSEEN DRIVER INCOMPLETE · {len(LOG['failures'])} failures")
        sys.exit(1)
    LOG["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save()
    say("UNSEEN DRIVER DONE")
