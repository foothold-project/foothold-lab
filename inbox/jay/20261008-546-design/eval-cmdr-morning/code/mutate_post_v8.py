"""break-the-guard for test_post_v8.py: each mutated copy (_mut_post_v8_<k>.py beside the real one) must fail the named checks."""
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

PY = "C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe"
EV = "C:/isaac/ext/go2_rl_robotlab/_eval"
SRC = open(os.path.join(EV, "cmdr_post_v8.py"), encoding="utf-8").read()
M = [
    ("P1 record hashes not compared", 'if rec.get("out_sha256") != h:', 'if False:', ["L1"]),
    ("P2 record attempt not compared", 'if rec.get("attempt") != stp.get("attempt"):', 'if False:', ["L1b"]),
    ("P3 no end check of the files read", '        if now != s0:\n            print(f"INPUT CHANGED during the aggregate: {tag_}/{f_}', '        if False:\n            print(f"INPUT CHANGED during the aggregate: {tag_}/{f_}', ["L2"]),
    ("P4 no stat check around a read", '        if s1 != s2:', '        if False:', ["R1"]),
    ("P5 no hold while the owner re-validates", 'if isinstance(af, dict) and (af.get("state") == "revalidating" or af.get("attempt") != d.get("attempt")):', 'if False:', ["L3", "L3c"]),
    ("P6 origin field ignored", 'stp_.get("origin") or (', '(', ["L4", "G13"]),
]


def one(k_m):
    k, (name, a, b, want) = k_m
    assert SRC.count(a) == 1, name
    fn = f"_mut_post_v8_{k}.py"
    open(os.path.join(EV, fn), "w", encoding="utf-8").write(SRC.replace(a, b))
    try:
        r = subprocess.run([PY, "test_post_v8.py"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=dict(os.environ, POST_V8=fn), cwd=os.path.dirname(os.path.abspath(__file__)))
    finally:
        os.remove(os.path.join(EV, fn))
    failed = [ln.split()[1] for ln in r.stdout.splitlines() if ln.startswith("FAIL ")]
    crashed = "Traceback (most recent call last)" in r.stderr or "Traceback (most recent call last)" in r.stdout
    caught = r.returncode == 1 and all(w in failed for w in want) and not crashed
    tail = (" · CRASH") if crashed else ""
    return f"{'CAUGHT' if caught else 'MISSED'} {name}: exit {r.returncode} failed {failed} want {want}{tail}"


with ThreadPoolExecutor(3) as ex:
    res = list(ex.map(one, enumerate(M)))
print("# test_post_v8.py 변이 시험 · 사본 (_mut_post_v8_<k>.py) 에서만 바꿔 돌림")
print("\n".join(res))
print("ALL CAUGHT" if all(x.startswith("CAUGHT") for x in res) else "SOME MISSED")
