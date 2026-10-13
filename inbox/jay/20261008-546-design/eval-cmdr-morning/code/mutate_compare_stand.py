"""break-the-guard for test_compare_stand.py: each mutated copy of compare_stand.py must fail the named checks (16j 5.2)."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "compare_stand.py"), encoding="utf-8").read()
M = [
    ("C1 disk bytes not compared with the stamp", 'and st["out_sha256"] == now4 and rec.get("out_sha256") == now4', "", ["S2"]),
    ("C2 owner matrix and pair failure not checked", '"owner matrix valid, no pair failure": base.get("matrix", {}).get(TAG) == "valid"', '"owner matrix valid, no pair failure": True or base.get("matrix", {}).get(TAG) == "valid"', ["S4"]),
    ("C3 preserved original not tied to the hand-over", 'res["old_equals_handover"] = bool(man_run) and all(', 'res["old_equals_handover"] = True or all(', ["S5"]),
    ("C4 an incomplete new run is read anyway", "if len(old) != 1 or missing_new:", "if len(old) != 1:", ["S6"]),
    ("C5 a reused record counts as a new measurement", 'rec.get("reused") is False', 'rec.get("reused") in (False, True)', ["S7"]),
    ("C6 no re-check after reading", "if changed:\n", "if False:\n", ["S8", "S9"]),
]
res = []
for k, (name, a, b, want) in enumerate(M):
    assert SRC.count(a) == 1, name
    p = os.path.join(HERE, f"_mut_compare_stand_{k}.py")
    open(p, "w", encoding="utf-8").write(SRC.replace(a, b))
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "test_compare_stand.py")], capture_output=True, text=True,
                           env=dict(os.environ, COMPARE_SCRIPT=p), encoding="utf-8", errors="replace")
    finally:
        os.remove(p)
    failed = [ln.split()[1] for ln in r.stdout.splitlines() if ln.startswith("FAIL ")]
    crashed = "Traceback (most recent call last)" in r.stderr
    caught = r.returncode == 1 and all(w in failed for w in want) and not crashed
    res.append(f"{'CAUGHT' if caught else 'MISSED'} {name}: exit {r.returncode} failed {failed} want {want}{' · CRASH' if crashed else ''}")
print("# test_compare_stand.py 변이 시험 · 사본 (_mut_compare_stand_<k>.py) 에서만 바꿔 돌림")
print("\n".join(res))
print("ALL CAUGHT" if all(x.startswith("CAUGHT") for x in res) else "SOME MISSED")
