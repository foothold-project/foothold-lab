"""break-the-guard for test_handover.py: each mutated copy of handover_1400.py must fail the named checks."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "handover_1400.py"), encoding="utf-8").read()
M = [
    ("K1 a valid run's missing files are not a problem", "    if missing_valid:\n        problems.append", "    if False:\n        problems.append", ["H2", "H3"]),
    ("K2 no final re-hash of the originals", "    if changed:\n        problems.append", "    if False:\n        problems.append", ["H5", "H5b"]),
    ("K3 no end process scan", "    if a1:\n", "    if False:\n", ["H6"]),
    ("K4 env_origins.npy not frozen", '"traj.npz", "env_origins.npy", "driver_stamp.json"', '"traj.npz", "driver_stamp.json"', ["H1"]),
    ("K5 stop requests moved even when the freeze failed", "    if not problems:  # 16h 4.2", "    if True:  # 16h 4.2", ["H2"]),
    ("K6 every .stop treated as the drivers' own", 'TARGET_STOPS = [f"{n}.stop" for n in LOGS]', 'TARGET_STOPS = sorted(f for f in os.listdir(OUT) if f.endswith(".stop"))', ["H1b"]),
    ("K7 a stop that changed during the freeze is moved too", "            if sha_or_none(p) != h0:", "            if False:", ["H1d"]),
    ("K8 (16j 9.5) the end scan is not kept", "    scans.append(scan_record(s1, a1))", "    pass", ["H9"]),
    ("K9 argv values kept in the saved scan", 'for x in p["cmdline"] if x.startswith("-") or x.lower().endswith((".py", ".exe"))]', 'for x in p["cmdline"]]', ["H9"]),
]
res = []
for k, (name, a, b, want) in enumerate(M):
    assert SRC.count(a) == 1, name
    p = os.path.join(HERE, f"_mut_handover_{k}.py")
    open(p, "w", encoding="utf-8").write(SRC.replace(a, b))
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "test_handover.py")], capture_output=True, text=True,
                           env=dict(os.environ, HANDOVER_SCRIPT=p), encoding="utf-8", errors="replace")
    finally:
        os.remove(p)
    failed = [ln.split()[1] for ln in r.stdout.splitlines() if ln.startswith("FAIL ")]
    crashed = "Traceback (most recent call last)" in r.stderr
    caught = r.returncode == 1 and all(w in failed for w in want) and not crashed
    res.append(f"{'CAUGHT' if caught else 'MISSED'} {name}: exit {r.returncode} failed {failed} want {want}{' · CRASH' if crashed else ''}")
print("\n".join(res))
print("ALL CAUGHT" if all(x.startswith("CAUGHT") for x in res) else "SOME MISSED")
