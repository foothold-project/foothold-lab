"""break-the-guard for test_isaac_slot.py: each mutated copy of isaac_slot.py must fail the named checks (lead 10/13)."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "isaac_slot.py"), encoding="utf-8").read()
M = [
    ("S1 lock released right after launch (no wait for the scene line)", "        if CONVERT_DONE in read(a.watch_log):", "        if True:", ["T2"]),
    ("S2 registry conflicts ignored", "            if k in reg and reg[k] != me:", "            if False:", ["T3b"]),
    ("S2b other logs not scanned", "        for k, v in other_logs_naming(set(folders), dirs, a.watch_log).items():", "        for k, v in {}.items():", ["T3c"]),
    ("S3 an old log is not moved aside", "    if os.path.exists(a.watch_log):  # 5", "    if False:  # 5", ["T7"]),
    ("S4 the one-USD-folder check dropped", "    elif rc == 0 and len(final) != 1:", "    elif False:", ["T5", "T5b"]),
    ("S5 the conversion time limit ignored", "        if time.time() - t_hold > a.convert_timeout_s:", "        if False:", ["T6"]),
]
res = []
for k, (name, a, b, want) in enumerate(M):
    assert SRC.count(a) == 1, name
    p = os.path.join(HERE, f"_mut_slot_{k}.py")
    open(p, "w", encoding="utf-8").write(SRC.replace(a, b))
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "test_isaac_slot.py")], capture_output=True, text=True,
                           env=dict(os.environ, ISAAC_SLOT_SCRIPT=p), encoding="utf-8", errors="replace", timeout=900)
    finally:
        os.remove(p)
    failed = [ln.split()[1] for ln in r.stdout.splitlines() if ln.startswith("FAIL ")]
    crashed = "Traceback (most recent call last)" in r.stderr
    caught = r.returncode == 1 and all(w in failed for w in want) and not crashed
    res.append(f"{'CAUGHT' if caught else 'MISSED'} {name}: exit {r.returncode} failed {failed} want {want}{' · CRASH' if crashed else ''}")
print("\n".join(res))
print("ALL CAUGHT" if all(x.startswith("CAUGHT") for x in res) else "SOME MISSED")
