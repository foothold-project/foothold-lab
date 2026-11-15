# Renders the label-strip replay videos (q_video.py --overlay label, PhysX on CPU, renderer on GPU 1) for the HUD
# selection, one q_video process per tag, each under gpu_guard.py (200 ms, stop below 4096 MiB free, exit 99).
# Usage: python label_runner.py --sel out/hud_sel.json [--batch1] [--part 0/1] [--tags a,b]
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
BATCH1_FAMS = ("flat", "stairs_up")


def batch1(it):
    tag = it["tag"]
    if tag.endswith("_offplat"):
        return it["file"].startswith("stairs_up_")
    return any(tag.endswith("_" + f) for f in BATCH1_FAMS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sel", default=os.path.join(HERE, "out", "hud_sel.json"))
    ap.add_argument("--batch1", action="store_true")
    ap.add_argument("--part", default="0/1")
    ap.add_argument("--tags", default="")
    a = ap.parse_args()
    items = json.load(open(a.sel, encoding="utf-8"))
    if a.batch1:
        items = [x for x in items if batch1(x)]
    if a.tags:
        items = [x for x in items if x["tag"] in a.tags.split(",")]
    todo = {}
    for x in items:
        if not os.path.exists(x["video"]):
            todo.setdefault(x["tag"], []).append(x["file"])
    k, n = (int(v) for v in a.part.split("/"))
    tags = sorted(todo)[k::n]
    env = dict(os.environ, CUDA_DEVICE_ORDER="PCI_BUS_ID", CUDA_VISIBLE_DEVICES="1", OMNI_KIT_ACCEPT_EULA="YES", PYTHONUNBUFFERED="1")
    os.makedirs(os.path.join(HERE, "out", "video_hud_src"), exist_ok=True)
    for tag in tags:
        run_tag = tag
        t0 = time.time()
        cmd = [PY, "gpu_guard.py", "--gpu", "1", "--log", f"out/video_hud_src/{tag}.log", "--summary", f"out/video_hud_src/{tag}.guard.json",
               "--", PY, "q_video.py", "--run_tag", run_tag, "--files", ",".join(todo[tag]), "--overlay", "label",
               "--out_root", "video_hud_src", "--sim_device", "cpu"]
        rc = subprocess.run(cmd, cwd=HERE, env=env).returncode
        print(f"LABEL {tag} files {len(todo[tag])} EXIT {rc} {time.time() - t0:.0f}s {time.strftime('%H:%M:%S')}", flush=True)
        if rc == 99:
            print(f"STOP: guard stopped {tag}", flush=True)
            sys.exit(99)
        if rc != 0:
            print(f"STOP: {tag} failed", flush=True)
            sys.exit(4)
    print("LABEL DONE", flush=True)


if __name__ == "__main__":
    main()
