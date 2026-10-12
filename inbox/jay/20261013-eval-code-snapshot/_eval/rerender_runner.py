# Re-renders the videos moved to out/_bad/ (frame defects), GPU 1, one renderer at a time, every process under
# gpu_guard.py. q_video.py now checks every frame (black / flat / sky / robot window) and re-renders a failing frame;
# when a frame still fails it stops without writing that video. A tag is then retried (new process) for the files
# still missing, at most --tries times. Usage: python rerender_runner.py --what label|record [--tries 3]
import argparse
import glob
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
ap = argparse.ArgumentParser()
ap.add_argument("--what", choices=["label", "record"], required=True)
ap.add_argument("--tries", type=int, default=3)
a = ap.parse_args()
moved = json.load(open(os.path.join(HERE, "out", "_bad", "moved.json"), encoding="utf-8"))
pairs = moved["web_items"] if a.what == "label" else moved["record_items"]
root = "video_hud_src" if a.what == "label" else "video"
todo = {}
for tag, key in pairs:
    todo.setdefault(tag, []).append(key)
env = dict(os.environ, CUDA_DEVICE_ORDER="PCI_BUS_ID", CUDA_VISIBLE_DEVICES="1", OMNI_KIT_ACCEPT_EULA="YES", PYTHONUNBUFFERED="1")
for tag in sorted(todo):
    for attempt in range(1, a.tries + 1):
        left = [k for k in todo[tag] if not os.path.exists(os.path.join(HERE, "out", root, tag, k + "_kinreplay.mp4"))]
        if not left:
            break
        t0 = time.time()
        cmd = [PY, "gpu_guard.py", "--gpu", "1", "--log", f"out/{root}/{tag}.rerender{attempt}.log", "--summary", f"out/{root}/{tag}.rerender{attempt}.guard.json",
               "--", PY, "q_video.py", "--run_tag", tag, "--files", ",".join(k + ".csv" for k in left), "--out_root", root, "--sim_device", "cpu"]
        if a.what == "label":
            cmd += ["--overlay", "label"]
        rc = subprocess.run(cmd, cwd=HERE, env=env).returncode
        print(f"RERENDER {a.what} {tag} try {attempt} files {len(left)} EXIT {rc} {time.time() - t0:.0f}s {time.strftime('%H:%M:%S')}", flush=True)
        if rc == 99:
            print(f"STOP: guard stopped {tag}", flush=True)
            sys.exit(99)
    left = [k for k in todo[tag] if not os.path.exists(os.path.join(HERE, "out", root, tag, k + "_kinreplay.mp4"))]
    if left:
        print(f"FAILED {a.what} {tag}: {len(left)} still missing after {a.tries} tries: {left}", flush=True)
    # rebuild the tag's videos_report.json from the per-video JSON files (an aborted process does not write it)
    vd = os.path.join(HERE, "out", root, tag)
    rp = os.path.join(vd, "videos_report.json")
    old = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else {"run_tag": tag, "full_tag": tag}
    vids = [json.load(open(p, encoding="utf-8")) for p in sorted(glob.glob(os.path.join(vd, "*_kinreplay.json")))]
    old["videos"] = vids
    old["terrain_mesh_equal"] = all(v["terrain_mesh_equal_to_run"] for v in vids)
    json.dump(old, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"RERENDER {a.what} DONE", flush=True)
