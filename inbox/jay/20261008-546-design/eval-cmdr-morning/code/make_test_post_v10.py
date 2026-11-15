"""test_post_v9.py -> test_post_v10.py (lead 10/13, VERIFY-astra-16l 3.1 / 3.3 / 3.4 / 5.3). Every replacement must match exactly once."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(HERE, "test_post_v9.py"), encoding="utf-8").read()
s = s.replace('"""Known-answer tests for cmdr_post_v9.py (v8 tests + 16k 4 release binding)',
              '"""Known-answer tests for cmdr_post_v10.py (v8 tests + 16k 4 release binding + 16l 3 / 5.3)', 1)

G_START = s.index("    # re-validated later by another v3.7 instance")
G_END = s.index('    open(ev_n, "a").write(" ")\n')
NEW_G = '''    # re-validated later by another v3.7 instance: it KEEPS the collection attempt and names itself in revalidated_by,
    # with a link to the previous stamp (driver v3.7 1224, 1241-1247); the record is reused with the same attempt
    sp_n = os.path.join(d_n, "driver_stamp.json")
    st_keep = open(sp_n, "rb").read()
    st_ = json.loads(st_keep)
    st_.update(revalidated_by="NEXT", prev_stamp_sha256=hashlib.sha256(st_keep).hexdigest(), revalidated_at="later")
    json.dump(st_, open(sp_n, "w"))
    LD.recs["cmdr_eval_driver"].append({"tag": t_on, "valid": True, "reused": True, "attempt": "NEW-j9", "out_sha256": hn})
    LD.go()
    check("L5g (16l 3.1) the released run re-validated the v3.7 way (same collection attempt, revalidated_by, new stamp bytes): still released",
          (LD.rc, LD.res["held"], [r["tag"] for r in LD.res["hold_released"]], LD.res["auth_fail"]), (0, [], [t_on], []))
    # 16l 3.2: the held original re-validated (its own attempt kept), outputs equal to the approved ones, release names NEW
    st_o = json.loads(st_keep)
    st_o.update(attempt=att_old, revalidated_by="NEXT", prev_stamp_sha256=hs, revalidated_at="later")
    json.dump(st_o, open(sp_n, "w"))
    LD.recs["cmdr_eval_driver"].append({"tag": t_on, "valid": True, "reused": True, "attempt": att_old, "out_sha256": hn})
    LD.go()
    check("L5g2 (16l 3.2) the held original re-validated (its attempt, the approved bytes) under a release naming the new collection: held",
          (LD.rc, [(h["tag"], h.get("release_why", "")[:20]) for h in LD.res["held"]], LD.res["hold_released"]), (0, [(t_on, "the stamp or the own")], []))
    open(sp_n, "wb").write(st_keep)
    LD.recs["cmdr_eval_driver"].pop()
    LD.recs["cmdr_eval_driver"].pop()
'''

J_END = s.index("    # L6 (16i 5.1) records are looked up in the owner log only\n")
NEW_K = '''    # 16l 3.4 / 5.3 / 3.3: back to a valid release, then the named hold list, the bundle copies and a dependency change
    st_["pins"] = PINS
    json.dump(st_, open(os.path.join(d_n, "driver_stamp.json"), "w"))
    LD.go()
    check("L5k0 control after L5j: released again", (LD.rc, [r["tag"] for r in LD.res["hold_released"]]), (0, [t_on]))
    os.remove(os.path.join(LD.out, "cmdr_post.json"))
    LD.go(env_extra={"CMDR_POST_HOLD": os.path.join(LD.out, "H-TYPO", "cmdr_post_hold.json")})
    check("L5k (16l 3.4) a named hold list that is missing: exit 6, nothing written", (LD.rc, os.path.exists(os.path.join(LD.out, "cmdr_post.json"))), (6, False))
    LD.go(env_extra={"CMDR_POST_HOLD": hp_, "CMDR_POST_HOLD_SHA256": "0" * 64})
    check("L5k2 a named hold list that is not the expected bytes: exit 6, nothing written", (LD.rc, os.path.exists(os.path.join(LD.out, "cmdr_post.json"))), (6, False))
    BUN = os.path.join(LD.out, "BUNDLE")
    os.makedirs(os.path.join(BUN, "held_stamps"))
    os.makedirs(os.path.join(BUN, "evidence"))
    shutil.copy(os.path.join(LD.out, "H0", "stamps", t_on + ".json"), os.path.join(BUN, "held_stamps", t_on + ".json"))
    shutil.copy(ev_2, os.path.join(BUN, "evidence", t_on + ".json"))
    hb = json.load(open(hp_))
    hb[t_on]["released"]["evidence"] = os.path.join(LD.out, "no_such_dir", "ev.json")  # only the bundle copy exists
    json.dump(hb, open(os.path.join(BUN, "cmdr_post_hold.json"), "w"))
    LD.go(env_extra={"CMDR_POST_BUNDLE": BUN})
    check("L5l (16l 5.3) the bundle's hold list, held stamp and evidence copies are read (the work-tree evidence path is gone): released, deps from the bundle",
          (LD.rc, [r["tag"] for r in LD.res["hold_released"]] if LD.rc == 0 else None,
           sorted(os.path.relpath(p_, BUN) for p_ in LD.res.get("release_deps_sha256", {})) if LD.rc == 0 else None),
          (0, [t_on], [os.path.join("evidence", t_on + ".json"), os.path.join("held_stamps", t_on + ".json")]))
    os.remove(os.path.join(LD.out, "cmdr_post.json"))
    LD.go(env_extra={"CMDR_POST_BUNDLE": os.path.join(LD.out, "NO_BUNDLE")})
    check("L5l2 a named bundle without a hold list: exit 6, nothing written", (LD.rc, os.path.exists(os.path.join(LD.out, "cmdr_post.json"))), (6, False))
    good_ev = open(ev_2, "rb").read()

    def ev_flip():
        open(ev_2, "wb").write(good_ev + b" ")
    code = run_hooked(LD.out, ev_2, ev_flip)
    open(ev_2, "wb").write(good_ev)
    check("L5m (16l 3.3) the evidence replaced right after it was read: exit 3, nothing written",
          (code, os.path.exists(os.path.join(LD.out, "cmdr_post.json"))), (3, False))
    held_copy = os.path.join(LD.out, "H0", "stamps", t_on + ".json")
    good_h = open(held_copy, "rb").read()

    def h_flip():
        open(held_copy, "wb").write(good_h + b" ")
    code = run_hooked(LD.out, held_copy, h_flip)
    open(held_copy, "wb").write(good_h)
    check("L5m2 (16l 3.3) the held original stamp copy replaced right after it was read: exit 3, nothing written",
          (code, os.path.exists(os.path.join(LD.out, "cmdr_post.json"))), (3, False))

'''
R = [
    ('POST = os.environ.get("POST_V9", "cmdr_post_v9.py")', 'POST = os.environ.get("POST_V10", "cmdr_post_v10.py")'),
    ('("cmdr_post v9", ', '("cmdr_post v10", '),
    ('json.dump(dict(v6, schema="cmdr_post v9", release_auth_fail=[])', 'json.dump(dict(v6, schema="cmdr_post v10", release_auth_fail=[])'),
    ('    def go(self, extra_logs=None):\n', '    def go(self, extra_logs=None, env_extra=None):\n'),
    ('        env = dict(os.environ, CMDR_POST_OUT=self.out, CMDR_POST_DEST=self.out, KMP_DUPLICATE_LIB_OK="TRUE", CUDA_VISIBLE_DEVICES="")\n',
     '        env = dict(os.environ, CMDR_POST_OUT=self.out, CMDR_POST_DEST=self.out, KMP_DUPLICATE_LIB_OK="TRUE", CUDA_VISIBLE_DEVICES="")\n'
     '        env.update(env_extra or {})\n'),
]
s = s[:G_START] + NEW_G + s[G_END:J_END] + NEW_K + s[J_END:]
for a, b in R:
    n = s.count(a)
    if n != 1:
        sys.exit(f"anchor found {n} times: {a[:70]!r}")
    s = s.replace(a, b)
open(os.path.join(HERE, "test_post_v10.py"), "w", encoding="utf-8").write(s)
print("wrote test_post_v10.py")
