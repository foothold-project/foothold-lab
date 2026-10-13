"""break-the-guard for test_validate_branch.py v2 (lead 10/13 evening)."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "validate_branch.py"), encoding="utf-8").read()
M = [
    ("B1 done line not required", '        if f"[BRANCH] done {a.tag}" not in log:', "        if False:", ["V2"]),
    ("B2 Traceback ignored", '        if "Traceback (most recent call last)" in log:', "        if False:", ["V3"]),
    ("B2b root reference failure ignored", "        if ROOT_REF in log:", "        if False:", ["V3b"]),
    ("B3 args not compared", "            if ra.get(k) != v:", "            if False:", ["V4"]),
    ("B4 checkpoint not opened", '            why = ckpt_check(os.path.join(d, f), it, by[f].get("model_sha"))',
     '            why = "" if os.path.getsize(os.path.join(d, f)) else "empty"', ["V5b", "V5c"]),
    ("B4b iter in the checkpoint not compared", '    if ck.get("iter") != want_iter:', "    if False:", ["V5d"]),
    ("B5 guard exit ignored", '        if g.get("exit_code") != 0 or g.get("stopped_by_guard"):', "        if False:", ["V6"]),
    ("B6 slot conflicts ignored", '        if len(s.get("usd_final", [])) != 1 or s.get("usd_outside_root") or s.get("conflicts"):', "        if False:", ["V7"]),
    ("B6b slot child exit ignored", '        if s.get("slot_rc") != 0 or s.get("child_rc") != 0 or s.get("state_at_release") != "scene_built":',
     '        if s.get("slot_rc") != 0:', ["V7b"]),
    ("B6c launcher not required", '        if not any(x.endswith("usd_isolate_run.py") for x in cmd) or not any(x.endswith("branch_run.py") for x in cmd):',
     "        if False:", ["V7c"]),
    ("B6d attempt not compared", '        if s.get("attempt") != attempt:', "        if False:", ["V7d"]),
    ("B6e stale results accepted", '        if time.mktime(time.strptime(r["meta"]["t_start"], "%Y-%m-%d %H:%M:%S")) < a.since - 1:', "        if False:", ["V7f"]),
    ("B7 reuse by stamp presence only", '        if not why and st.get("sha256") != hashes:', "        if False:", ["V8"]),
    ("B8 stopped-short run accepted", '        if r["final_state"].get("iter_from_counter") != end_it + 1:', "        if False:", ["V9"]),
    ("B9 parent hash not re-checked", '        if r["meta"].get("parent_sha256") != psha:', "        if False:", ["V10"]),
    ("B10 save file name not checked",
     '        if not saves or saves[-1].get("where") != f"save it={end_it} last=True" or saves[-1].get("file") != f"model_{end_it}.pt":',
     '        if not saves or saves[-1].get("where") != f"save it={end_it} last=True":', ["V11"]),
    ("B11 bundle not required", '        for f in ("bundle.json", "bundle.npz"):\n            if not os.path.exists(os.path.join(d, f)):',
     '        for f in ("bundle.json", "bundle.npz"):\n            if False:', ["V12"]),
    ("B12 attempt optional", "    if not a.attempt:\n        print", "    if False:\n        print", ["V13"]),
]
res = []
for k, (name, a, b, want) in enumerate(M):
    if SRC.count(a) != 1:
        res.append(f"BAD-ANCHOR {name}: count {SRC.count(a)}")
        continue
    p = os.path.join(HERE, f"_mut_vb_{k}.py")
    open(p, "w", encoding="utf-8").write(SRC.replace(a, b))
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "test_validate_branch.py")], capture_output=True, text=True,
                           env=dict(os.environ, VALIDATE_SCRIPT=p), encoding="utf-8", errors="replace", timeout=1200)
    finally:
        os.remove(p)
    failed = [ln.split()[1] for ln in r.stdout.splitlines() if ln.startswith("FAIL ")]
    crashed = "Traceback (most recent call last)" in r.stderr
    caught = r.returncode == 1 and all(w in failed for w in want) and not crashed
    res.append(f"{'CAUGHT' if caught else 'MISSED'} {name}: exit {r.returncode} failed {failed} want {want}{' · CRASH' if crashed else ''}")
print("\n".join(res))
print("ALL CAUGHT" if all(x.startswith("CAUGHT") for x in res) else "SOME MISSED")
