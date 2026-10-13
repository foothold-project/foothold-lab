"""break-the-guard for test_isaac_slot.py v2: each mutated copy of isaac_slot.py must fail the named checks (lead 10/13)."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "isaac_slot.py"), encoding="utf-8").read()
M = [
    ("S1 lock released right after launch", "        if CONVERT_DONE in text and USD_RE.search(text):", "        if True:", ["T2"]),
    ("S1b released at the scene line without knowing the folder (17b 2.2)", "        if CONVERT_DONE in text and USD_RE.search(text):", "        if CONVERT_DONE in text:", ["T8"]),
    ("S2 registry conflicts ignored", "        if k in reg and reg[k] != me:", "        if False:", ["T3b"]),
    ("S2b other logs not scanned", '    for d in [d for d in a.scan_dirs.split(",") if d]:', "    for d in []:", ["T3c"]),
    ("S3 an old log is not moved aside", "    if os.path.exists(a.watch_log):  # 5", "    if False:  # 5", ["T7"]),
    ("S4 the one-USD-folder check dropped", "    if rc == 0 and len(final) != 1:", "    if False:", ["T5", "T5b"]),
    ("S5 the conversion time limit ignored", "        if time.time() - t_hold > a.convert_timeout_s:", "        if False:", ["T6"]),
    ("S6 a folder outside this run's root accepted", "    if rc == 0 and outside:", "    if False:", ["T9"]),
    ("S7 stop file and deadline ignored while waiting", '    if a.stop_file and os.path.exists(a.stop_file):\n        return "stop file"', "    if False:\n        return \"stop file\"", ["T10", "T12"]),
    ("S7b deadline ignored", "    if a.deadline and time.time() > a.deadline:", "    if False:", ["T11"]),
    ("S8 the child does not get its own USD root", "    env = dict(os.environ, FOOTHOLD_USD_ROOT=root)", "    env = dict(os.environ)", ["T13"]),
]
res = []
for k, (name, a, b, want) in enumerate(M):
    assert SRC.count(a) == 1, name
    p = os.path.join(HERE, f"_mut_slot_{k}.py")
    open(p, "w", encoding="utf-8").write(SRC.replace(a, b))
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "test_isaac_slot.py")], capture_output=True, text=True,
                           env=dict(os.environ, ISAAC_SLOT_SCRIPT=p), encoding="utf-8", errors="replace", timeout=900)
        out = r.stdout
        rcode = r.returncode
    except subprocess.TimeoutExpired as ex:
        out, rcode = (ex.stdout or b"").decode("utf-8", "replace") if isinstance(ex.stdout, bytes) else (ex.stdout or ""), "timeout"
    finally:
        os.remove(p)
    failed = [ln.split()[1] for ln in out.splitlines() if ln.startswith("FAIL ")]
    caught = (rcode == 1 and all(w in failed for w in want)) or rcode == "timeout"
    res.append(f"{'CAUGHT' if caught else 'MISSED'} {name}: exit {rcode} failed {failed} want {want}")
print("\n".join(res))
print("ALL CAUGHT" if all(x.startswith("CAUGHT") for x in res) else "SOME MISSED")
