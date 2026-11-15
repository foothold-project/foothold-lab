"""break-the-guard for test_post_v9.py: each mutated copy (_mut_post_v9_<k>.py beside the real one) must fail the named checks."""
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

PY = "C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe"
EV = "C:/isaac/ext/go2_rl_robotlab/_eval"
SRC = open(os.path.join(EV, "cmdr_post_v9.py"), encoding="utf-8").read()
M = [
    ("P1 record hashes not compared", 'if rec.get("out_sha256") != h:', 'if False:', ["L1"]),
    ("P2 record attempt not compared", 'if rec.get("attempt") != stp.get("attempt"):', 'if False:', ["L1b"]),
    ("P3 no end check of the files read", '        if now != s0:\n            print(f"INPUT CHANGED during the aggregate: {tag_}/{f_}', '        if False:\n            print(f"INPUT CHANGED during the aggregate: {tag_}/{f_}', ["L2"]),
    ("P4 no stat check around a read", '        if s1 != s2:', '        if False:', ["R1"]),
    ("P5 no hold while the owner re-validates", 'if isinstance(af, dict) and (af.get("state") == "revalidating" or af.get("attempt") != d.get("attempt")):', 'if False:', ["L3", "L3c"]),
    ("P6 origin field ignored", 'stp_.get("origin") or (', '(', ["L4", "G13"]),
    ("P7 hold list ignored", '        if not ok_rel:  # 16i 3', '        if False:  # 16i 3', ["L5"]),
    ("P8 a changed stamp releases the hold", '        if not ok_rel:  # 16i 3', '        if not ok_rel and cur == HOLD[tag].get("stamp_sha256"):  # 16i 3', ["L5b"]),
    ("P9 records looked up across both logs", 'rec = drv.get("rec", {}).get((owner, tag))',
     'rec = next((v for (o_, t_), v in reversed(list(drv.get("rec", {}).items())) if t_ == tag), None)', ["L6"]),
    ("P10 unreadable attempt file of a v3.3+ owner ignored", 'if ver != "3.2" and not isinstance(af, dict):', 'if False:', ["L7"]),
    ("P11 attempt files not compared at the end", '    if (open(p_, "rb").read() if os.path.exists(p_) else None) != raw0:', '    if False:', ["L7b"]),
    ("P13 (16k 4) any release record frees the run", "        ok_rel = not rel_why", "        ok_rel = isinstance(rel, dict)", ["L5e2", "L5f"]),
    ("P14 (16k 4) the held original may be released as the new collection", 'if hashlib.sha256(blobs["driver_stamp.json"]).hexdigest() == entry.get("stamp_sha256") or (held_att and held_att == rel["new_attempt"]):', "if False:", ["L5f"]),
    ("P15 (16k 4) the release does not fix the bytes", '    if now != rel["out_sha256"]:', "    if False:", ["L5i"]),
    ("P16 (16k 4) the evidence file hash is not checked", '    if _sha_file(rel["evidence"]) != rel["evidence_sha256"]:', "    if False:", ["L5h"]),
    ("P17 (16k 4) the evidence content is not checked", '    if not (e.get("comparison_ready") is True and', "    if False and (e.get(\"comparison_ready\") is True and", ["L5h2"]),
    ("P18 (16k 4) a re-validated stamp is accepted without the prev link", ' and stp.get("revalidated_by") and stp.get("prev_stamp_sha256")\n', ' and stp.get("revalidated_by")\n', ["L5g2"]),
    ("P19 (16k 4) a released run that fails auth is not listed as such", '        release_auth_fail.append({"tag": tag, "why": why})', "        pass", ["L5j"]),
    ("P12 hold list not compared at the end", 'if (open(HOLD_P, "rb").read() if os.path.exists(HOLD_P) else None) != HOLD_RAW:', 'if False:', ["L7c"]),
]


def one(k_m):
    k, (name, a, b, want) = k_m
    assert SRC.count(a) == 1, name
    fn = f"_mut_post_v9_{k}.py"
    open(os.path.join(EV, fn), "w", encoding="utf-8").write(SRC.replace(a, b))
    try:
        r = subprocess.run([PY, "test_post_v9.py"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=dict(os.environ, POST_V9=fn), cwd=os.path.dirname(os.path.abspath(__file__)))
    finally:
        os.remove(os.path.join(EV, fn))
    failed = [ln.split()[1] for ln in r.stdout.splitlines() if ln.startswith("FAIL ")]
    crashed = "Traceback (most recent call last)" in r.stderr or "Traceback (most recent call last)" in r.stdout
    caught = r.returncode == 1 and all(w in failed for w in want) and not crashed
    tail = (" · CRASH") if crashed else ""
    return f"{'CAUGHT' if caught else 'MISSED'} {name}: exit {r.returncode} failed {failed} want {want}{tail}"


with ThreadPoolExecutor(3) as ex:
    res = list(ex.map(one, enumerate(M)))
print("# test_post_v9.py 변이 시험 · 사본 (_mut_post_v9_<k>.py) 에서만 바꿔 돌림")
print("\n".join(res))
print("ALL CAUGHT" if all(x.startswith("CAUGHT") for x in res) else "SOME MISSED")
