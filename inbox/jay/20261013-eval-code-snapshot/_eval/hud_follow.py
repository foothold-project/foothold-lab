# Follows the label renders: whenever a tag's label run has finished (a "LABEL <tag> ... EXIT 0" line in
# out/label_*.log), runs hud_make.py for the items of that tag that have no HUD yet. Stops when out/hud_follow.stop
# exists. Usage: python hud_follow.py [--batch1] [--workers 10]
import argparse
import glob
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--batch1", action="store_true")
ap.add_argument("--workers", type=int, default=10)
a = ap.parse_args()
done = set()
while not os.path.exists(os.path.join(HERE, "out", "hud_follow.stop")):
    fin = set()
    for lg in glob.glob(os.path.join(HERE, "out", "label_*.log")):
        for line in open(lg, encoding="utf-8", errors="replace"):
            m = re.match(r"LABEL (\S+) files \d+ EXIT 0", line)
            if m:
                fin.add(m.group(1))
    new = sorted(fin - done)
    if new:
        cmd = [sys.executable, "hud_make.py", "--list", "out/hud_sel.json", "--tags", ",".join(new), "--workers", str(a.workers),
               "--stills", "0.1,0.45,0.55,0.9", "--report", "out/hud_report.json"] + (["--batch1"] if a.batch1 else [])
        rc = subprocess.run(cmd, cwd=HERE).returncode
        print(f"HUD {','.join(new)} EXIT {rc} {time.strftime('%H:%M:%S')}", flush=True)
        if rc == 0:
            done |= set(new)
    time.sleep(20)
print("HUD FOLLOW STOPPED", flush=True)
