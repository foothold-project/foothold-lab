"""break-the-guard for test_post_v10.py: each mutated copy (_mut_post_v10_<k>.py beside the real one) must fail the named checks."""
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

PY = "C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe"
EV = "C:/isaac/ext/go2_rl_robotlab/_eval"
SRC = open(os.path.join(EV, "cmdr_post_v10.py"), encoding="utf-8").read()
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
    ("P14 (16k 4) the held original may be released as the new collection", '            or held_att in (rel["new_attempt"], stp.get("attempt"), rec.get("attempt"))):', "            or False):", ["L5f"]),
    ("P15 (16k 4) the release does not fix the bytes", '    if now != rel["out_sha256"]:', "    if False:", ["L5i"]),
    ("P16 (16k 4) the evidence file hash is not checked", '    if sha_e is None or sha_e != rel["evidence_sha256"]:', "    if False:", ["L5h"]),
    ("P17 (16k 4) the evidence content is not checked", '    if not (isinstance(e, dict) and e.get("comparison_ready") is True and', "    if False and (isinstance(e, dict) and e.get(\"comparison_ready\") is True and", ["L5h2"]),
    ("P18 (16l 3.1) a stamp naming another collection is accepted", '    if stp.get("attempt") != rel["new_attempt"] or rec.get("attempt") != rel["new_attempt"]:  # 16l 3.1: no exception', "    if False:", ["L5g2"]),
    ("P20 (16l 3.3) the release dependencies are not hashed again at the end", "for p_, h_ in DEP_SEEN.items():  # 16l 3.3", "for p_, h_ in {}.items():  # 16l 3.3", ["L5m", "L5m2"]),
    ("P21 (16l 3.4) a named hold list that is missing counts as no holds", 'if (os.environ.get("CMDR_POST_HOLD") or BUNDLE) and (HOLD_RAW is None', "if False and (HOLD_RAW is None", ["L5k", "L5k2"]),
    ("P22 (16l 5.3) the bundle's evidence copy is not read", '    ep = os.path.join(BUNDLE, "evidence", tag + ".json") if BUNDLE else rel["evidence"]', '    ep = rel["evidence"]', ["L5l"]),
    ("P19 (16k 4) a released run that fails auth is not listed as such", '        release_auth_fail.append({"tag": tag, "why": why})', "        pass", ["L5j"]),
    ("P12 hold list not compared at the end", 'if (open(HOLD_P, "rb").read() if os.path.exists(HOLD_P) else None) != HOLD_RAW:', 'if False:', ["L7c"]),
]


def one(k_m):
    k, (name, a, b, want) = k_m
    assert SRC.count(a) == 1, name
    fn = f"_mut_post_v10_{k}.py"
    open(os.path.join(EV, fn), "w", encoding="utf-8").write(SRC.replace(a, b))
    try:
        r = subprocess.run([PY, "test_post_v10.py"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=dict(os.environ, POST_V10=fn), cwd=os.path.dirname(os.path.abspath(__file__)))
    finally:
        os.remove(os.path.join(EV, fn))
    failed = [ln.split()[1] for ln in r.stdout.splitlines() if ln.startswith("FAIL ")]
    crashed = "Traceback (most recent call last)" in r.stderr or "Traceback (most recent call last)" in r.stdout
    caught = r.returncode == 1 and all(w in failed for w in want) and not crashed
    tail = (" · CRASH") if crashed else ""
    return f"{'CAUGHT' if caught else 'MISSED'} {name}: exit {r.returncode} failed {failed} want {want}{tail}"


with ThreadPoolExecutor(3) as ex:
    res = list(ex.map(one, enumerate(M)))
print("# test_post_v10.py 변이 시험 · 사본 (_mut_post_v10_<k>.py) 에서만 바꿔 돌림")
print("\n".join(res))
print("ALL CAUGHT" if all(x.startswith("CAUGHT") for x in res) else "SOME MISSED")
