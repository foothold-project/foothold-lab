"""break-the-guard for test_v37.py: each mutation must make the test fail (exit 1) at the named checks."""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
PY = "C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe"
SRC = open("C:/isaac/ext/go2_rl_robotlab/_eval/cmdr_eval_driver_v37.py", encoding="utf-8").read()
M = [
 ("M1 no gate in the slot wait", '        gate(where, ck)\n        f = open(os.path.join(OUT, CONVERT_LOCK), "a+b")', '        f = open(os.path.join(OUT, CONVERT_LOCK), "a+b")', ["18a", "18b", "18c", "18d"]),
 ("M2 no gate with the slot held", '            gate(f"{name} try {k} launch", ck)  # with the slot held, right before the child starts', '            pass', ["18e"]),
 ("M3 slot released at once", '    t0 = time.time()\n    lp = os.path.join(OUT, f"{name}.log")\n', '    return "marker", 0.0\n', ["20a"]),
 ("M4 unreadable argv not foreign", "            out.append(f\"unknown:{p['pid']}\")", '            pass', ["21"]),
 ("M5 parent create time not checked", 'or par["create_time"] > cur["create_time"]:', 'or False:', ["21"]),
 ("M6 root reference only on a non-zero exit", 'if rc != 99 and root_ref_failed(name):', 'if rc not in (0, 99) and root_ref_failed(name):', ["19a", "19b"]),
 ("M7 shared folder not checked", '    if others:\n', '    if False:\n', ["22b", "22d", "23"]),
 ("M8 stop / deadline exits are errors", '"incomplete" if code in (2, 7) else "error"', '"error"', ["25a", "25b"]),
 ("M9 earlier result not preserved", 'moved = preserve_result(tag)  # (z)', 'moved = None', ["24b"]),
 ("M10 lines after the scene line not checked", '    if any(USD_RE.search(x) or IMPORTER in x for x in L[mk + 1:]):', '    if False:', ["22e"]),
 ("M11 kit not foreign", '        if name.startswith("kit") or name.startswith("isaac-sim"):', '        if False:', ["21"]),
 ("M12 validate without usd_check", '        why = usd_check(tag)  # (y)\n        if why:\n            return why\n', '', ["11g"]),
 ("M13 attempts names may be replaced", '    while os.path.exists(q_):', '    while False:', ["19b"]),
 ("M14 ppid asked per process", '    for pr in psutil.process_iter(["pid", "name", "cmdline"]):\n        try:\n            d = dict(pr.info)', '    for pr in psutil.process_iter(["pid", "name", "cmdline", "ppid"]):\n        try:\n            d = dict(pr.info)', ["26"]),
 ("M15 legacy origin not named", '"legacy-origin revalidated" if "stamp_version" not in prev else "hashed-at-collection"', '"hashed-at-collection"', ["27a"]),
 ("M16 origin upgraded on a later reuse", 'prev.get("origin") or (', '(', ["27b"]),
]
def one(m):
    name, a, b, want = m
    assert SRC.count(a) == 1, name
    env = dict(os.environ, V37_MUTATE=json.dumps([[a, b]]))
    r = subprocess.run([PY, "test_v37.py"], capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
    failed = [l.split()[1] for l in r.stdout.splitlines() if l.startswith("FAIL ")]
    crashed = "Traceback (most recent call last)" in r.stderr
    caught = r.returncode == 1 and all(w in failed for w in want) and not crashed
    tail = (" · CRASH " + r.stderr.strip().splitlines()[-1][:120]) if crashed else ""
    return f"{'CAUGHT' if caught else 'MISSED'} {name}: exit {r.returncode} failed {failed} want {want}{tail}"
with ThreadPoolExecutor(4) as ex:
    res = list(ex.map(one, M))
print("\n".join(res))
print("ALL CAUGHT" if all(x.startswith("CAUGHT") for x in res) else "SOME MISSED")
