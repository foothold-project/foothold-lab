"""break-the-guard for test_validate_branch.py (lead 10/13 evening)."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "validate_branch.py"), encoding="utf-8").read()
M = [
    ("B1 done line not required", '        if f"[BRANCH] done {a.tag}" not in log:', "        if False:", ["V2"]),
    ("B2 Traceback ignored", '        if "Traceback (most recent call last)" in log:', "        if False:", ["V3"]),
    ("B3 args not compared", "            if ra.get(k) != v:", "            if False:", ["V4"]),
    ("B4 checkpoints not required", "            if not os.path.exists(os.path.join(d, f)) or os.path.getsize(os.path.join(d, f)) == 0:", "            if False:", ["V5b"]),
    ("B5 guard exit ignored", '        if g.get("exit_code") != 0 or g.get("stopped_by_guard"):', "        if False:", ["V6"]),
    ("B6 slot conflicts ignored", '        if s.get("slot_rc") != 0 or s.get("conflicts") or len(s.get("usd_final", [])) != 1:', "        if False:", ["V7"]),
    ("B7 reuse by stamp presence only", '            if st.get("sha256") != hashes:', "            if False:", ["V8"]),
    ("B8 stopped-short run accepted", '        if r["final_state"].get("iter_from_counter") != end_it + 1:', "        if False:", ["V9"]),
    ("B9 parent hash not re-checked", '        if r["meta"].get("parent_sha256") != sha(a.parent):', "        if False:", ["V10"]),
]
res = []
for k, (name, a, b, want) in enumerate(M):
    assert SRC.count(a) == 1, name
    p = os.path.join(HERE, f"_mut_vb_{k}.py")
    open(p, "w", encoding="utf-8").write(SRC.replace(a, b))
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "test_validate_branch.py")], capture_output=True, text=True,
                           env=dict(os.environ, VALIDATE_SCRIPT=p), encoding="utf-8", errors="replace", timeout=600)
    finally:
        os.remove(p)
    failed = [ln.split()[1] for ln in r.stdout.splitlines() if ln.startswith("FAIL ")]
    crashed = "Traceback (most recent call last)" in r.stderr
    caught = r.returncode == 1 and all(w in failed for w in want) and not crashed
    res.append(f"{'CAUGHT' if caught else 'MISSED'} {name}: exit {r.returncode} failed {failed} want {want}{' · CRASH' if crashed else ''}")
print("\n".join(res))
print("ALL CAUGHT" if all(x.startswith("CAUGHT") for x in res) else "SOME MISSED")
