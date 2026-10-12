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
# Usage: python unseen_driver.py [--stages eval,post,videos,audit]
import argparse
import csv
import glob
import json
import os
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
ENV = dict(os.environ, CUDA_DEVICE_ORDER="PCI_BUS_ID", CUDA_VISIBLE_DEVICES="1", OMNI_KIT_ACCEPT_EULA="YES", PYTHONUNBUFFERED="1")
LOG = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "runs": [], "skipped": [], "videos": [], "stages": {}}


def save():
    json.dump(LOG, open(os.path.join(OUT, "unseen_driver.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def say(s):
    print(f"{time.strftime('%H:%M:%S')} {s}", flush=True)


def guarded(name, cmd, log_path, summary_path, tries=4, wait_s=300):
    for k in range(1, tries + 1):
        t0 = time.time()
        rc = subprocess.run([PY, "gpu_guard.py", "--gpu", "1", "--min_free_mib", "4096", "--log", log_path, "--summary", summary_path, "--"] + cmd,
                            cwd=HERE, env=ENV).returncode
        say(f"RUN {name} try {k} EXIT {rc} {time.time() - t0:.0f}s")
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


def stage_eval():
    for run, it, fam, cell, tag in tags():
        if os.path.exists(os.path.join(OUT, tag, "cells.json")):
            continue
        cmd = [PY, "q_eval.py", "--headless", "--tag", tag, "--policy", "student", "--checkpoint", f"{E[run]}/model_{it}.pt",
               "--terrain_set", "unseen10", "--families", fam, "--cells", cell, "--episodes", "100", "--full_record"]
        rc, k = guarded(tag, cmd, f"out/{tag}.log", f"out/{tag}.guard.json")
        LOG["runs"].append({"tag": tag, "rc": rc, "tries": k})
        if rc != 0:
            LOG["skipped"].append(tag)
        save()


def stage_post():
    r = subprocess.run([PY, "unseen_post.py"], cwd=HERE, capture_output=True, text=True)
    say("POST " + (r.stdout.strip() or r.stderr[-400:]))


def selection():
    items = []
    for run, it, fam, cell, tag in tags():
        sp = os.path.join(OUT, "full", tag, "episodes_summary.csv")
        if not os.path.exists(sp):
            continue
        rows = list(csv.DictReader(open(sp, encoding="utf-8")))
        for lab in ("first_success", "first_failure"):
            hit = next((r for r in rows if lab in r["labels"]), None)
            if not hit:
                continue
            key = hit["file"][:-4]
            items.append({"key": f"{tag}/{key}", "tag": tag, "file": hit["file"], "pick": lab, "run": run, "model": it, "terrain": fam, "cell": cell,
                          "video": os.path.join(OUT, "video_hud_src", tag, key + "_kinreplay.mp4"),
                          "parquet": os.path.join(OUT, "legacy", tag, "timeseries", key + ".parquet"),
                          "hud": os.path.join(OUT, "video_hud", tag, key + "_kinreplay_hud.mp4"),
                          "web": os.path.join(OUT, "web", tag, key + "_kinreplay_hud_web.mp4"),
                          "title": f"{run} {it} {SHORT.get(fam, fam)} {cell} ep{int(hit['episode'])}"})
    json.dump(items, open(os.path.join(OUT, "unseen_sel.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return items


def stage_videos():
    items = selection()
    by = {}
    for x in items:
        by.setdefault(x["tag"], []).append(x)
    for tag, xs in by.items():
        for attempt in range(1, 4):
            left = [x["file"] for x in xs if not os.path.exists(x["video"])]
            if not left:
                break
            cmd = [PY, "q_video.py", "--run_tag", tag, "--files", ",".join(left), "--overlay", "label", "--out_root", "video_hud_src", "--sim_device", "cpu"]
            rc, _ = guarded(f"video {tag}", cmd, f"out/video_hud_src/{tag}.log", f"out/video_hud_src/{tag}.guard.json", tries=4)
        left = [x["file"] for x in xs if not os.path.exists(x["video"])]
        LOG["videos"].append({"tag": tag, "requested": len(xs), "missing": left})
        r = subprocess.run([PY, "fr_to_legacy.py", "--tag", tag], cwd=HERE, capture_output=True, text=True)
        if r.returncode != 0:
            say(f"CONVERT FAILED {tag}: {r.stderr[-300:]}")
        save()
    r = subprocess.run([PY, "hud_make.py", "--list", "out/unseen_sel.json", "--workers", "12", "--stills", "0.1,0.45,0.55,0.9",
                        "--report", "out/unseen_hud_report.json"], cwd=HERE, capture_output=True, text=True)
    LOG["stages"]["hud_make_rc"] = r.returncode
    say(f"HUD rc {r.returncode} {r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ''}")
    save()


def stage_audit():
    items = json.load(open(os.path.join(OUT, "unseen_sel.json"), encoding="utf-8"))
    files = [x[k] for x in items for k in ("video", "hud", "web") if os.path.exists(x[k])]
    lst = os.path.join(OUT, "unseen_audit_files.txt")
    open(lst, "w", encoding="utf-8").write("\n".join(files))
    sys.path.insert(0, HERE)
    import frame_audit
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(16) as ex:
        res = list(ex.map(frame_audit.audit, files, [0] * len(files)))
    json.dump(res, open(os.path.join(OUT, "unseen_frame_audit.json"), "w", encoding="utf-8"), indent=1)
    bad = [x["file"] for x in res if x["bad"]]
    LOG["stages"]["audit"] = {"files": len(res), "bad": bad}
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
    say(f"AUDIT files {len(res)} bad {len(bad)} web {sum(1 for r in rows if r['web'])}/{len(rows)}")
    save()


ap = argparse.ArgumentParser()
ap.add_argument("--stages", default="eval,post,videos,audit")
a = ap.parse_args()
for st in a.stages.split(","):
    say(f"STAGE {st}")
    {"eval": stage_eval, "post": stage_post, "videos": stage_videos, "audit": stage_audit}[st]()
LOG["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
save()
say("UNSEEN DRIVER DONE")
