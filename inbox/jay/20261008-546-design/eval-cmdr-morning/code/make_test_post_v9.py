"""test_post_v8.py -> test_post_v9.py (lead 10/13, VERIFY-astra-16k 4). Every replacement must match exactly once."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
s = open(os.path.join(HERE, "test_post_v8.py"), encoding="utf-8").read()
s = s.replace('"""Known-answer tests for cmdr_post_v8.py', '"""Known-answer tests for cmdr_post_v9.py (v8 tests + 16k 4 release binding)', 1)

A_REL = s[s.index("    # a real new measurement: new outputs, a stamp and a published record with the new attempt\n"):
          s.index("    # L6 (16i 5.1) records are looked up in the owner log only\n")]

NEW_REL = '''    # 16k 4: a release must name the new collection (attempt + four output hashes) and saved evidence for it
    def evidence(name, attempt, hashes, **over):
        e = {"comparison_ready": True, "new_run_valid": True, "new_attempt": attempt, "new_out_sha256": hashes}
        e.update(over)
        p_ = os.path.join(LD.out, name)
        json.dump(e, open(p_, "w"))
        return p_, hashlib.sha256(open(p_, "rb").read()).hexdigest()
    d_n = os.path.join(LD.out, t_on)
    h_old = {f_: hashlib.sha256(open(os.path.join(d_n, f_), "rb").read()).hexdigest() for f_ in OUT4}
    att_old = json.load(open(os.path.join(LD.out, "H0", "stamps", t_on + ".json"))).get("attempt")
    ev_o, evs_o = evidence("ev_orig.json", att_old, h_old)
    hj[t_on]["released"] = {"by": "lead", "why": "보류 원본 확인", "new_attempt": att_old, "out_sha256": h_old, "evidence": ev_o, "evidence_sha256": evs_o}
    json.dump(hj, open(hp_, "w"))
    LD.go()
    check("L5f (16k 4) a complete-looking release that names the held original itself: still held (not a new collection)",
          (LD.rc, [(h["tag"], h.get("release_why", "")[:40]) for h in LD.res["held"]], LD.res["hold_released"]),
          (0, [(t_on, "the released collection is the held orig")], []))
    # a real new measurement: new outputs, a stamp and a published record with the new attempt
    open(os.path.join(d_n, "episodes.csv"), "a", newline="").write("")
    rows_n = list(csv.DictReader(open(os.path.join(d_n, "episodes.csv"), encoding="utf-8")))
    rows_n[0]["mae_vx"] = "0.0123"
    with open(os.path.join(d_n, "episodes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(rows_n[0].keys()))
        w.writeheader()
        w.writerows(rows_n)
    hn = {f_: hashlib.sha256(open(os.path.join(d_n, f_), "rb").read()).hexdigest() for f_ in OUT4}
    json.dump({"pins": PINS, "ckpt_sha256": CKPT["on24000"], "stamp_version": "3.7", "out_sha256": hn, "attempt": "NEW-j9"},
              open(os.path.join(d_n, "driver_stamp.json"), "w"))
    LD.recs["cmdr_eval_driver"].append({"tag": t_on, "valid": True, "reused": False, "attempt": "NEW-j9", "out_sha256": hn})
    hj[t_on]["released"] = {"by": "lead", "why": "새 측정 확인", "new_attempt": "NEW-j9"}
    json.dump(hj, open(hp_, "w"))
    LD.go()
    check("L5e2 (16k 4) the v8-style release (attempt only, no hashes or evidence) of a real new collection: still held, reason given",
          (LD.rc, [(h["tag"], "lacks" in h.get("release_why", "")) for h in LD.res["held"]], LD.res["hold_released"]), (0, [(t_on, True)], []))
    ev_n, evs_n = evidence("ev_new.json", "NEW-j9", hn)
    good_rel = {"by": "lead", "why": "새 측정 확인", "new_attempt": "NEW-j9", "out_sha256": hn, "evidence": ev_n, "evidence_sha256": evs_n}
    hj[t_on]["released"] = dict(good_rel)
    json.dump(hj, open(hp_, "w"))
    LD.go()
    check("L5c a release naming the new collection, its hashes and its evidence: used again, the release record kept",
          (LD.rc, LD.res["held"], [(r["tag"], r["released"]["new_attempt"]) for r in LD.res["hold_released"]], "wave/fwd03/on" in LD.res["regression_24000"]),
          (0, [], [(t_on, "NEW-j9")], True))
    # re-validated later by another v3.7 instance: it rewrites the stamp with its own attempt and a link to the previous stamp
    # (cmdr_eval_driver_v37.py 1241-1247) and records reused with that attempt; the bytes stay the approved ones
    sp_n = os.path.join(d_n, "driver_stamp.json")
    st_keep = open(sp_n, "rb").read()
    st_ = json.loads(st_keep)
    st_.update(attempt="LATER-j1", revalidated_by="LATER", prev_stamp_sha256=hashlib.sha256(st_keep).hexdigest(), revalidated_at="later")
    json.dump(st_, open(sp_n, "w"))
    LD.recs["cmdr_eval_driver"].append({"tag": t_on, "valid": True, "reused": True, "attempt": "LATER-j1", "out_sha256": hn})
    LD.go()
    check("L5g (16k 4) the released run re-validated later (stamp rewritten with the new attempt and a prev link, bytes unchanged): still released",
          (LD.rc, LD.res["held"], [r["tag"] for r in LD.res["hold_released"]], LD.res["auth_fail"]), (0, [], [t_on], []))
    st_.pop("prev_stamp_sha256")
    json.dump(st_, open(sp_n, "w"))
    LD.go()
    check("L5g2 a stamp naming another attempt without the re-validation link: held",
          (LD.rc, [(h["tag"], h.get("release_why", "")[:20]) for h in LD.res["held"]]), (0, [(t_on, "the stamp or the own")]))
    open(sp_n, "wb").write(st_keep)
    LD.recs["cmdr_eval_driver"].pop()
    open(ev_n, "a").write(" ")
    LD.go()
    check("L5h (16k 4) the evidence file changed after the release: held again",
          (LD.rc, [(h["tag"], h.get("release_why")) for h in LD.res["held"]]), (0, [(t_on, "the evidence file is missing or changed")]))
    ev_n, evs_n = evidence("ev_new.json", "NEW-j9", hn)
    ev_b, evs_b = evidence("ev_bad.json", "NEW-j9", hn, comparison_ready=False)
    hj[t_on]["released"] = dict(good_rel, evidence=ev_b, evidence_sha256=evs_b)
    json.dump(hj, open(hp_, "w"))
    LD.go()
    check("L5h2 evidence that does not show a ready comparison: held",
          (LD.rc, [(h["tag"], h.get("release_why", "")[:17]) for h in LD.res["held"]]), (0, [(t_on, "the evidence does")]))
    hj[t_on]["released"] = dict(good_rel, evidence=ev_n, evidence_sha256=evs_n)
    json.dump(hj, open(hp_, "w"))
    # same attempt, outputs + stamp + record all re-signed with new hashes (16k 4 last case)
    rows_n[0]["mae_vx"] = "0.0456"
    with open(os.path.join(d_n, "episodes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(rows_n[0].keys()))
        w.writeheader()
        w.writerows(rows_n)
    hn2 = {f_: hashlib.sha256(open(os.path.join(d_n, f_), "rb").read()).hexdigest() for f_ in OUT4}
    json.dump({"pins": PINS, "ckpt_sha256": CKPT["on24000"], "stamp_version": "3.7", "out_sha256": hn2, "attempt": "NEW-j9"},
              open(os.path.join(d_n, "driver_stamp.json"), "w"))
    LD.recs["cmdr_eval_driver"].append({"tag": t_on, "valid": True, "reused": False, "attempt": "NEW-j9", "out_sha256": hn2})
    LD.go()
    check("L5i (16k 4) same attempt but outputs, stamp and record re-signed with other hashes: held (the release fixed the bytes)",
          (LD.rc, [(h["tag"], h.get("release_why")) for h in LD.res["held"]]), (0, [(t_on, "the output bytes on disk are not the released ones")]))
    hj[t_on]["released"] = dict(good_rel, out_sha256=hn2)
    ev_2, evs_2 = evidence("ev_2.json", "NEW-j9", hn2)
    hj[t_on]["released"].update(evidence=ev_2, evidence_sha256=evs_2)
    json.dump(hj, open(hp_, "w"))
    st_ = json.load(open(os.path.join(d_n, "driver_stamp.json")))
    st_["pins"] = {"other": "pins"}
    json.dump(st_, open(os.path.join(d_n, "driver_stamp.json"), "w"))
    hs2 = {f_: hashlib.sha256(open(os.path.join(d_n, f_), "rb").read()).hexdigest() for f_ in OUT4}
    LD.go()
    check("L5j (16k 4) a valid release whose run then fails authentication: out of the tables, in auth_fail AND release_auth_fail",
          (LD.rc, [x["tag"] for x in LD.res["auth_fail"]], [x["tag"] for x in LD.res["release_auth_fail"]], "wave/fwd03/on" in LD.res["regression_24000"]),
          (0, [t_on], [t_on], False))

'''
R = [
    ('POST = os.environ.get("POST_V8", "cmdr_post_v8.py")', 'POST = os.environ.get("POST_V9", "cmdr_post_v9.py")'),
    ('("cmdr_post v8", ', '("cmdr_post v9", '),
    ('    json.dump({t_on: {"stamp_sha256": hs, "why": "USD 임시 폴더 공유 의심 (11:38) · 다시 재는 중"}}, open(os.path.join(LD.out, "cmdr_post_hold.json"), "w"))\n',
     '    os.makedirs(os.path.join(LD.out, "H0", "stamps"))  # 16k 4: the hand-over keeps the held original\'s stamp\n'
     '    shutil.copy(os.path.join(LD.out, t_on, "driver_stamp.json"), os.path.join(LD.out, "H0", "stamps", t_on + ".json"))\n'
     '    json.dump({t_on: {"stamp_sha256": hs, "why": "USD 임시 폴더 공유 의심 (11:38) · 다시 재는 중", "handover": "H0"}}, open(os.path.join(LD.out, "cmdr_post_hold.json"), "w"))\n'),
    (A_REL, NEW_REL),
    ('    g3 = FC.build(post_path=os.path.join(r6, "cmdr_post.json"), summary_path=summ)\n',
     '    g3v8 = FC.build(post_path=os.path.join(r6, "cmdr_post.json"), summary_path=summ)\n'
     '    check("G3b the frozen v8 aggregate is refused by the v9 page layer", "집계 판 불일치" in g3v8["cmdr_status"], True)\n'
     '    # the page-layer rendering checks below need a real-sized aggregate: the frozen v8 tables relabelled v9 (tables are\n'
     '    # computed the same way in v8 and v9; only the release rule differs). Provenance is not tested here.\n'
     '    p9 = os.path.join(ROOT, "frozen_as_v9.json")\n'
     '    json.dump(dict(v6, schema="cmdr_post v9", release_auth_fail=[]), open(p9, "w", encoding="utf-8"), ensure_ascii=False)\n'
     '    g3 = FC.build(post_path=p9, summary_path=summ)\n'),
]
for a, b in R:
    n = s.count(a)
    if n != 1:
        sys.exit(f"anchor found {n} times: {a[:70]!r}")
    s = s.replace(a, b)
if "\nimport shutil\n" not in s:
    s = s.replace("\nimport json\n", "\nimport json\nimport shutil\n", 1)
open(os.path.join(HERE, "test_post_v9.py"), "w", encoding="utf-8").write(s)
print("wrote test_post_v9.py")
