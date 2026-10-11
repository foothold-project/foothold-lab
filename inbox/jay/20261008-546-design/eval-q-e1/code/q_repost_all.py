# Re-run q_post on every saved trajectory (CPU only, no simulation), after backing up the
# previous episodes.csv / cells.json to out/_bak_v1/<tag>/. Then check that every column and
# key that existed before is unchanged. Usage: python q_repost_all.py [--skip tag,...]
import csv, glob, json, os, shutil, sys
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out")
sys.path.insert(0, HERE)
import q_post  # noqa: E402

def tags():
    t = []
    for p in sorted(glob.glob(os.path.join(OUT, "*", "traj.npz"))):
        tag = os.path.basename(os.path.dirname(p))
        if tag.startswith("_"):
            continue
        z = __import__("numpy").load(p)
        if "cmd_a" not in z.files:   # pre-restructure run, not post-processable
            continue
        t.append(tag)
    return t

def work(tag):
    d = os.path.join(OUT, tag); b = os.path.join(OUT, "_bak_v1", tag)
    os.makedirs(b, exist_ok=True)
    for f in ("episodes.csv", "cells.json"):
        if os.path.exists(os.path.join(d, f)) and not os.path.exists(os.path.join(b, f)):
            shutil.copy2(os.path.join(d, f), os.path.join(b, f))
    q_post.postprocess(d)
    # regression: every old column / key unchanged
    old = list(csv.DictReader(open(os.path.join(b, "episodes.csv"), encoding="utf-8")))
    new = list(csv.DictReader(open(os.path.join(d, "episodes.csv"), encoding="utf-8")))
    bad = 0
    if len(old) != len(new):
        return tag, "row count differs"
    for ro, rn in zip(old, new):
        for k, v in ro.items():
            if rn.get(k) != v:
                bad += 1
    co = json.load(open(os.path.join(b, "cells.json"), encoding="utf-8"))
    cn = json.load(open(os.path.join(d, "cells.json"), encoding="utf-8"))
    badc = sum(1 for x, y in zip(co, cn) for k in x if json.dumps(x[k]) != json.dumps(y.get(k)))
    return tag, f"episodes old-field mismatches {bad} | cells old-key mismatches {badc} | new cols {len(new[0]) - len(old[0])}"

if __name__ == "__main__":
    skip = set(sys.argv[2].split(",")) if len(sys.argv) > 2 and sys.argv[1] == "--skip" else set()
    only = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--only" else None  # substring filter
    T = [t for t in tags() if t not in skip and (only is None or only in t)]
    print("tags", len(T))
    with Pool(16) as p:
        for tag, msg in p.imap_unordered(work, T):
            print(tag, msg, flush=True)
