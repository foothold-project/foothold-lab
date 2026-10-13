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
    ("K8 (16j 9.5) the end scan is not kept", "    scans.append(scan_record(s1, old, t1))", "    scans.append(dict(scans[0]))", ["H9"]),
    ("K9 argv values kept in the saved scan", '        d["argv_readable"] = c is not None', '        d["argv"] = c\n        d["argv_readable"] = c is not None', ["H9"]),
    ("K10 (16k 6) --headless=false taken as --headless", 'd["headless_exact"] = bool(c) and "--headless" in c', 'd["headless_exact"] = bool(c) and any(x.startswith("--headless") for x in c)', ["H10"]),
    ("K11 (16k 6) non-python processes dropped from the record", "    rows = [facts(p) for p in snap]", '    rows = [facts(p) for p in snap if (p.get("name") or "").lower().startswith(("python", "kit"))]', ["H10"]),
    ("K12 (16k 7.2) the hold list is not part of the bundle", '    if os.path.exists(os.path.join(OUT, "cmdr_post_hold.json")):  # 16k 7.2', "    if False:  # 16k 7.2", ["H11"]),  # H11b is now also caught by the 16l 5.2 appearance check
    ("K13 (16l 5.2) a hold list that appears is not checked", '    if sha_or_none(os.path.join(OUT, "cmdr_post_hold.json")) != hold0 and "cmdr_post_hold.json" not in changed:', "    if False:", ["H12"]),
    ("K14 (16l 5.3) evidence not copied into the bundle", '                shutil.copy2(rel["evidence"], os.path.join(H, "evidence", t + ".json"))', "                pass", ["H13"]),
    ("K15 (16l 5.3) evidence bytes not checked against the release", '            if sha_or_none(rel["evidence"]) != rel.get("evidence_sha256"):', "            if False:", ["H13b"]),
    ("K16 (16l 5.3) release dependencies not re-checked at the end", "    changed += [f\"release dependency {d['from']}\" for d in deps.values() if sha_or_none(d[\"from\"]) != d[\"sha256\"]]", "    pass", ["H13c"]),
    ("K17 (16l 5.3) the held original stamp is not found by its hash", '        if sha_or_none(src) != e.get("stamp_sha256"):', "        if not os.path.exists(src):", ["H13d"]),
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
