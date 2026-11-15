"""mutate_post_v9.py -> mutate_post_v10.py (lead 10/13, VERIFY-astra-16l). Every replacement must match exactly once."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(HERE, "mutate_post_v9.py"), encoding="utf-8").read()
P14_V9 = s[s.index('    ("P14 (16k 4)'):s.index('    ("P15 (16k 4)')]
P16_P18_V9 = s[s.index('    ("P16 (16k 4)'):s.index('    ("P19 (16k 4)')]
R = [
    ('test_post_v9.py: each mutated copy (_mut_post_v9_<k>.py', 'test_post_v10.py: each mutated copy (_mut_post_v10_<k>.py'),
    ('SRC = open(os.path.join(EV, "cmdr_post_v9.py"), encoding="utf-8").read()', 'SRC = open(os.path.join(EV, "cmdr_post_v10.py"), encoding="utf-8").read()'),
    (P14_V9,
     '''    ("P14 (16k 4) the held original may be released as the new collection", '            or held_att in (rel["new_attempt"], stp.get("attempt"), rec.get("attempt"))):', "            or False):", ["L5f"]),\n'''),
    (P16_P18_V9,
     '''    ("P16 (16k 4) the evidence file hash is not checked", '    if sha_e is None or sha_e != rel["evidence_sha256"]:', "    if False:", ["L5h"]),\n'''
     '''    ("P17 (16k 4) the evidence content is not checked", '    if not (isinstance(e, dict) and e.get("comparison_ready") is True and', "    if False and (isinstance(e, dict) and e.get(\\"comparison_ready\\") is True and", ["L5h2"]),\n'''
     '''    ("P18 (16l 3.1) a stamp naming another collection is accepted", '    if stp.get("attempt") != rel["new_attempt"] or rec.get("attempt") != rel["new_attempt"]:  # 16l 3.1: no exception', "    if False:", ["L5g2"]),\n'''
     '''    ("P20 (16l 3.3) the release dependencies are not hashed again at the end", "for p_, h_ in DEP_SEEN.items():  # 16l 3.3", "for p_, h_ in {}.items():  # 16l 3.3", ["L5m", "L5m2"]),\n'''
     '''    ("P21 (16l 3.4) a named hold list that is missing counts as no holds", 'if (os.environ.get("CMDR_POST_HOLD") or BUNDLE) and (HOLD_RAW is None', "if False and (HOLD_RAW is None", ["L5k", "L5k2"]),\n'''
     '''    ("P22 (16l 5.3) the bundle's evidence copy is not read", '    ep = os.path.join(BUNDLE, "evidence", tag + ".json") if BUNDLE else rel["evidence"]', '    ep = rel["evidence"]', ["L5l"]),\n'''),
    ('fn = f"_mut_post_v9_{k}.py"', 'fn = f"_mut_post_v10_{k}.py"'),
    ('env=dict(os.environ, POST_V9=fn)', 'env=dict(os.environ, POST_V10=fn)'),
    ('[PY, "test_post_v9.py"]', '[PY, "test_post_v10.py"]'),
    ('print("# test_post_v9.py 변이 시험 · 사본 (_mut_post_v9_<k>.py) 에서만 바꿔 돌림")', 'print("# test_post_v10.py 변이 시험 · 사본 (_mut_post_v10_<k>.py) 에서만 바꿔 돌림")'),
]
for a, b in R:
    n = s.count(a)
    if n != 1:
        sys.exit(f"anchor found {n} times: {a[:80]!r}")
    s = s.replace(a, b)
open(os.path.join(HERE, "mutate_post_v10.py"), "w", encoding="utf-8").write(s)
print("wrote mutate_post_v10.py")
