"""mutate_post_v8.py -> mutate_post_v9.py (lead 10/13, VERIFY-astra-16k 4). Every replacement must match exactly once."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(HERE, "mutate_post_v8.py"), encoding="utf-8").read()
R = [
    ('test_post_v8.py: each mutated copy (_mut_post_v8_<k>.py', 'test_post_v9.py: each mutated copy (_mut_post_v9_<k>.py'),
    ('SRC = open(os.path.join(EV, "cmdr_post_v8.py"), encoding="utf-8").read()', 'SRC = open(os.path.join(EV, "cmdr_post_v9.py"), encoding="utf-8").read()'),
    ('''    ("P13 a release frees the run without naming it", 'ok_rel = isinstance(stp0, dict) and stp0.get("attempt") == rec0.get("attempt") == rel["new_attempt"]', 'ok_rel = True', ["L5e"]),\n''',
     '''    ("P13 (16k 4) any release record frees the run", "        ok_rel = not rel_why", "        ok_rel = isinstance(rel, dict)", ["L5e2", "L5f"]),\n'''
     '''    ("P14 (16k 4) the held original may be released as the new collection", 'if hashlib.sha256(blobs["driver_stamp.json"]).hexdigest() == entry.get("stamp_sha256") or (held_att and held_att == rel["new_attempt"]):', "if False:", ["L5f"]),\n'''
     '''    ("P15 (16k 4) the release does not fix the bytes", '    if now != rel["out_sha256"]:', "    if False:", ["L5i"]),\n'''
     '''    ("P16 (16k 4) the evidence file hash is not checked", '    if _sha_file(rel["evidence"]) != rel["evidence_sha256"]:', "    if False:", ["L5h"]),\n'''
     '''    ("P17 (16k 4) the evidence content is not checked", '    if not (e.get("comparison_ready") is True and', "    if False and (e.get(\\"comparison_ready\\") is True and", ["L5h2"]),\n'''
     '''    ("P18 (16k 4) a re-validated stamp is accepted without the prev link", ' and stp.get("revalidated_by") and stp.get("prev_stamp_sha256")\\n', ' and stp.get("revalidated_by")\\n', ["L5g2"]),\n'''
     '''    ("P19 (16k 4) a released run that fails auth is not listed as such", '        release_auth_fail.append({"tag": tag, "why": why})', "        pass", ["L5j"]),\n'''),
    ('fn = f"_mut_post_v8_{k}.py"', 'fn = f"_mut_post_v9_{k}.py"'),
    ('env=dict(os.environ, POST_V8=fn)', 'env=dict(os.environ, POST_V9=fn)'),
    ('[PY, "test_post_v8.py"]', '[PY, "test_post_v9.py"]'),
    ('print("# test_post_v8.py 변이 시험 · 사본 (_mut_post_v8_<k>.py) 에서만 바꿔 돌림")', 'print("# test_post_v9.py 변이 시험 · 사본 (_mut_post_v9_<k>.py) 에서만 바꿔 돌림")'),
]
for a, b in R:
    n = s.count(a)
    if n != 1:
        sys.exit(f"anchor found {n} times: {a[:80]!r}")
    s = s.replace(a, b)
open(os.path.join(HERE, "mutate_post_v9.py"), "w", encoding="utf-8").write(s)
print("wrote mutate_post_v9.py")
