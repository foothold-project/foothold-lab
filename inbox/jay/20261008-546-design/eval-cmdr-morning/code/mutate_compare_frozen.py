"""break-the-guard for test_compare_frozen.py: each mutated copy of compare_frozen.py must fail the named checks (16k 3)."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "compare_frozen.py"), encoding="utf-8").read()
M = [
    ("F1 every key treated as bookkeeping", "    if k in BOOK:\n        continue", "    if True:\n        continue", ["C1", "C7", "C10", "C12"]),
    ("F2 held runs pass without a filtered reference", "if held and ref is None:", "if False:", ["C20"]),
    ("F3 the filtered reference count is not checked", "    if ref.get(\"n_valid_runs\") != a.get(\"n_valid_runs\", 0) - len(held):", "    if False:", ["C22"]),
    ("F4 a held run still used is not caught", "out[\"differences\"] += [f\"held run used: {t}\" for t in held if t in man]", "pass", ["C23"]),
    ("F5 a released run not used is not caught", "out[\"differences\"] += [f\"released run not used: {t}\" for t in out[\"released\"] if t not in man]", "pass", ["C24"]),
    ("F6 only the first level compared by key presence", "                diff(x[k], y[k], f\"{path}/{k}\", acc, limit)", "                pass", ["C1", "C7", "C8"]),
]
res = []
for k, (name, a, b, want) in enumerate(M):
    assert SRC.count(a) == 1, name
    p = os.path.join(HERE, f"_mut_compare_frozen_{k}.py")
    open(p, "w", encoding="utf-8").write(SRC.replace(a, b))
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "test_compare_frozen.py")], capture_output=True, text=True,
                           env=dict(os.environ, CF_SCRIPT=p), encoding="utf-8", errors="replace")
    finally:
        os.remove(p)
    failed = [ln.split()[1] for ln in r.stdout.splitlines() if ln.startswith("FAIL ")]
    crashed = "Traceback (most recent call last)" in r.stderr
    caught = r.returncode == 1 and all(w in failed for w in want) and not crashed
    res.append(f"{'CAUGHT' if caught else 'MISSED'} {name}: exit {r.returncode} failed {failed} want {want}{' · CRASH' if crashed else ''}")
print("# test_compare_frozen.py 변이 시험 · 사본 (_mut_compare_frozen_<k>.py) 에서만 바꿔 돌림")
print("\n".join(res))
print("ALL CAUGHT" if all(x.startswith("CAUGHT") for x in res) else "SOME MISSED")
