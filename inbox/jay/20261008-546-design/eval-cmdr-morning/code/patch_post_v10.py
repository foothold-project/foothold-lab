"""cmdr_post_v8.py -> cmdr_post_v10.py (lead 10/13, VERIFY-astra-16k 4 / 7.2 and VERIFY-astra-16l 3.1 / 3.3 / 3.4 / 5.3).
v9 (patch_post_v9.py) stays as the version 16l reviewed; v10 is built from v8 again. Every replacement must match exactly once."""
import os
import sys

EV = sys.argv[1] if len(sys.argv) > 1 else "C:/isaac/ext/go2_rl_robotlab/_eval"
s = open(os.path.join(EV, "cmdr_post_v8.py"), encoding="utf-8").read()

R = [
    ('#   - schema = "cmdr_post v8".\n# Usage: python cmdr_post_v8.py    (CMDR_POST_OUT=<folder> for tests)\n',
     '#   - schema = "cmdr_post v8".\n'
     '# v10 (10/13 16:15, VERIFY-astra-16k 4 / 7.2 and 16l 3.1 / 3.3 / 3.4 / 5.3; v9 was the 16l draft):\n'
     '#   - a release frees a held run only when it names the new collection by its attempt AND its four output hashes and points\n'
     '#     at saved evidence (a compare_stand result for that attempt and those hashes); the bytes on disk are those; the stamp\n'
     '#     and the owner record vouch for them AND both name that collection attempt (v3.7 keeps the collection attempt when\n'
     '#     it re-validates and names the checker in revalidated_by, driver 1224: no exception for another attempt, 16l 3.1);\n'
     '#     and the collection is not the held original (whose stamp copy is found by the held stamp hash).\n'
     '#   - the held original stamp and the evidence are each read once: the hash and the parse come from the same bytes, and\n'
     '#     both are hashed again at the end like the other inputs (16l 3.3).\n'
     '#   - CMDR_POST_BUNDLE=<frozen hand-over folder> reads the hold list, the held original stamps and the evidence from the\n'
     '#     copies the freeze made (cmdr_post_hold.json, held_stamps/<tag>.json, evidence/<tag>.json; 16l 5.3).\n'
     '#     CMDR_POST_HOLD=<file> names the hold list alone. A named hold list must exist, parse to a record and, when\n'
     '#     CMDR_POST_HOLD_SHA256 is given, have those bytes; otherwise exit 6 and nothing is written (16l 3.4).\n'
     '#   - a released run that then fails authentication is listed under release_auth_fail as well as auth_fail (16k 4).\n'
     '#   - schema = "cmdr_post v10".\n'
     '# Usage: python cmdr_post_v10.py    (CMDR_POST_OUT=<folder> for tests)\n'),
    ('HOLD_P = os.path.join(OUT, "cmdr_post_hold.json")\n'
     'HOLD_RAW = open(HOLD_P, "rb").read() if os.path.exists(HOLD_P) else None  # 16i 5.2: part of the input, compared at the end\n'
     'HOLD = json.loads(HOLD_RAW.decode("utf-8")) if HOLD_RAW is not None else {}\n',
     'BUNDLE = os.environ.get("CMDR_POST_BUNDLE")  # 16l 5.3: the frozen hand-over folder holding the release dependencies\n'
     'HOLD_P = os.environ.get("CMDR_POST_HOLD") or (os.path.join(BUNDLE, "cmdr_post_hold.json") if BUNDLE else os.path.join(OUT, "cmdr_post_hold.json"))\n'
     'HOLD_RAW = open(HOLD_P, "rb").read() if os.path.exists(HOLD_P) else None  # 16i 5.2: part of the input, compared at the end\n'
     'try:\n'
     '    HOLD = json.loads(HOLD_RAW.decode("utf-8")) if HOLD_RAW is not None else {}\n'
     'except (UnicodeDecodeError, json.JSONDecodeError):\n'
     '    HOLD = None\n'
     'if (os.environ.get("CMDR_POST_HOLD") or BUNDLE) and (HOLD_RAW is None or not isinstance(HOLD, dict) or (\n'
     '        os.environ.get("CMDR_POST_HOLD_SHA256") and hashlib.sha256(HOLD_RAW).hexdigest() != os.environ["CMDR_POST_HOLD_SHA256"])):\n'
     '    print(f"HOLD LIST NOT USABLE: {HOLD_P} (missing, unreadable, not a record or not the expected bytes); nothing written", file=sys.stderr)\n'
     '    sys.exit(6)  # 16l 3.4: a named hold list that is not there is never "no holds"\n'
     'if not isinstance(HOLD, dict):\n'
     '    print(f"HOLD LIST NOT USABLE: {HOLD_P}; nothing written", file=sys.stderr)\n'
     '    sys.exit(6)\n'),
    ('held, hold_released, hold_candidates = [], [], []\n',
     'held, hold_released, hold_candidates, release_auth_fail = [], [], [], []\n'
     'REL_KEYS = ("by", "why", "new_attempt", "out_sha256", "evidence", "evidence_sha256")\n'
     'DEP_SEEN = {}  # 16l 3.3: dependency file -> hash of the bytes read; compared again at the end\n'
     '\n'
     '\n'
     'def _read_dep(p):\n'
     '    """the bytes of a release dependency, read once; the hash and the parse both come from them (16l 3.3)"""\n'
     '    try:\n'
     '        raw = open(p, "rb").read()\n'
     '    except OSError:\n'
     '        DEP_SEEN.setdefault(p, None)\n'
     '        return None, None\n'
     '    DEP_SEEN[p] = hashlib.sha256(raw).hexdigest()\n'
     '    return raw, DEP_SEEN[p]\n'
     '\n'
     '\n'
     'def release_check(tag, rel, blobs, entry):\n'
     '    """16k 4 / 16l 3: "" when the release names a valid new collection that is on disk now, else the reason (stays held)."""\n'
     '    miss = [k for k in REL_KEYS if not rel.get(k)]\n'
     '    if miss:\n'
     '        return f"release record lacks {miss}"\n'
     '    if not isinstance(rel["out_sha256"], dict) or sorted(rel["out_sha256"]) != sorted(OUT4):\n'
     '        return "release out_sha256 must name the four output files"\n'
     '    now = {f: hashlib.sha256(blobs[f]).hexdigest() if blobs.get(f) is not None else None for f in OUT4}\n'
     '    if now != rel["out_sha256"]:\n'
     '        return "the output bytes on disk are not the released ones"\n'
     '    try:\n'
     '        stp = json.loads(blobs["driver_stamp.json"].decode("utf-8"))\n'
     '    except (AttributeError, json.JSONDecodeError, UnicodeDecodeError):\n'
     '        return "stamp unreadable"\n'
     '    rec = drv.get("rec", {}).get((drv["owner"][tag], tag)) or {}\n'
     '    if not isinstance(stp, dict) or stp.get("out_sha256") != now or rec.get("out_sha256") != now:\n'
     '        return "the stamp or the owner record does not vouch for the released bytes"\n'
     '    if stp.get("attempt") != rel["new_attempt"] or rec.get("attempt") != rel["new_attempt"]:  # 16l 3.1: no exception\n'
     '        return "the stamp or the owner record names another collection than the released one"\n'
     '    hp = (os.path.join(BUNDLE, "held_stamps", tag + ".json") if BUNDLE\n'
     '          else os.path.join(OUT, entry.get("handover") or "_no_handover_", "stamps", tag + ".json"))\n'
     '    raw_h, sha_h = _read_dep(hp)\n'
     '    if sha_h is None or sha_h != entry.get("stamp_sha256"):\n'
     '        return "the held original\'s stamp copy is not found by the held hash"\n'
     '    try:\n'
     '        held_att = (json.loads(raw_h.decode("utf-8")) or {}).get("attempt")\n'
     '    except (AttributeError, json.JSONDecodeError, UnicodeDecodeError):\n'
     '        return "the held original\'s stamp copy is unreadable"\n'
     '    if (hashlib.sha256(blobs["driver_stamp.json"]).hexdigest() == entry.get("stamp_sha256")\n'
     '            or held_att in (rel["new_attempt"], stp.get("attempt"), rec.get("attempt"))):\n'
     '        return "the released collection is the held original"\n'
     '    ep = os.path.join(BUNDLE, "evidence", tag + ".json") if BUNDLE else rel["evidence"]\n'
     '    raw_e, sha_e = _read_dep(ep)\n'
     '    if sha_e is None or sha_e != rel["evidence_sha256"]:\n'
     '        return "the evidence file is missing or changed"\n'
     '    try:\n'
     '        e = json.loads(raw_e.decode("utf-8"))\n'
     '    except (UnicodeDecodeError, json.JSONDecodeError):\n'
     '        return "the evidence file is unreadable"\n'
     '    if not (isinstance(e, dict) and e.get("comparison_ready") is True and e.get("new_run_valid") is True\n'
     '            and not e.get("changed_while_reading") and e.get("new_attempt") == rel["new_attempt"]\n'
     '            and e.get("new_out_sha256") == rel["out_sha256"]):\n'
     '        return "the evidence does not show a valid new collection with this attempt and these hashes"\n'
     '    return ""\n'),
    ('        rel = HOLD[tag].get("released")\n'
     '        ok_rel = False  # 16j 5.3: a release names the new measurement; it frees the run only if that IS the run on disk\n'
     '        if isinstance(rel, dict) and all(rel.get(k) for k in ("by", "why", "new_attempt")):\n'
     '            try:\n'
     '                stp0 = json.loads(blobs["driver_stamp.json"].decode("utf-8")) if blobs["driver_stamp.json"] is not None else {}\n'
     '            except (json.JSONDecodeError, UnicodeDecodeError):\n'
     '                stp0 = {}\n'
     '            rec0 = drv.get("rec", {}).get((drv["owner"][tag], tag)) or {}\n'
     '            ok_rel = isinstance(stp0, dict) and stp0.get("attempt") == rec0.get("attempt") == rel["new_attempt"]\n',
     '        rel = HOLD[tag].get("released") if isinstance(HOLD[tag], dict) else None\n'
     '        rel_why = release_check(tag, rel, blobs, HOLD[tag]) if isinstance(rel, dict) else ("no release record" if not rel else "release is not a record")\n'
     '        ok_rel = not rel_why  # 16k 4 / 16l 3: bound to the collection attempt, its bytes and its evidence\n'),
    ('                         "release_rejected": bool(rel)})\n',
     '                         "release_rejected": bool(rel), "release_why": rel_why})\n'),
    ('    if pending_release and not why:  # written only once the released run passed authentication (16j 5.3)\n'
     '        hold_released.append(pending_release)\n',
     '    if pending_release and not why:  # written only once the released run passed authentication (16j 5.3)\n'
     '        hold_released.append(pending_release)\n'
     '    if pending_release and why:  # 16k 4: counted with the holds as well as with the auth failures\n'
     '        release_auth_fail.append({"tag": tag, "why": why})\n'),
    ('if (open(HOLD_P, "rb").read() if os.path.exists(HOLD_P) else None) != HOLD_RAW:\n'
     '    print("INPUT CHANGED during the aggregate: cmdr_post_hold.json; nothing written", file=sys.stderr)\n'
     '    sys.exit(3)\n',
     'if (open(HOLD_P, "rb").read() if os.path.exists(HOLD_P) else None) != HOLD_RAW:\n'
     '    print("INPUT CHANGED during the aggregate: cmdr_post_hold.json; nothing written", file=sys.stderr)\n'
     '    sys.exit(3)\n'
     'for p_, h_ in DEP_SEEN.items():  # 16l 3.3: the held original stamps and the evidence are inputs too\n'
     '    if (hashlib.sha256(open(p_, "rb").read()).hexdigest() if os.path.exists(p_) else None) != h_:\n'
     '        print(f"INPUT CHANGED during the aggregate: {p_}; nothing written", file=sys.stderr)\n'
     '        sys.exit(3)\n'),
    ('res["schema"] = "cmdr_post v8"\n',
     'res["schema"] = "cmdr_post v10"\nres["release_auth_fail"] = release_auth_fail\n'
     'res["release_deps_sha256"] = dict(DEP_SEEN)\nres["hold_list"] = {"path": HOLD_P, "sha256": hashlib.sha256(HOLD_RAW).hexdigest() if HOLD_RAW is not None else None}\n'),
]
for a, b in R:
    n = s.count(a)
    if n != 1:
        sys.exit(f"anchor found {n} times: {a[:70]!r}")
    s = s.replace(a, b)
open(os.path.join(EV, "cmdr_post_v10.py"), "w", encoding="utf-8").write(s)
print("wrote", os.path.join(EV, "cmdr_post_v10.py"))
