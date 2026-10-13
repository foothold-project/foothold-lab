"""cmdr_post_v8.py -> cmdr_post_v9.py (lead 10/13, VERIFY-astra-16k 4 / 7.2). Every replacement must match exactly once."""
import os
import sys

EV = sys.argv[1] if len(sys.argv) > 1 else "C:/isaac/ext/go2_rl_robotlab/_eval"
s = open(os.path.join(EV, "cmdr_post_v8.py"), encoding="utf-8").read()

R = [
    ('#   - schema = "cmdr_post v8".\n# Usage: python cmdr_post_v8.py    (CMDR_POST_OUT=<folder> for tests)\n',
     '#   - schema = "cmdr_post v8".\n'
     '# v9 (10/13 15:30, VERIFY-astra-16k 4 / 7.2):\n'
     '#   - a release frees a held run only when it names the new collection by its attempt AND its four output hashes and points\n'
     '#     at saved evidence (a compare_stand result for that attempt and those hashes), the bytes on disk are those, the stamp\n'
     '#     and the owner record vouch for them, and the named collection is not the held original (whose stamp copy is found\n'
     '#     in the hand-over folder by the held stamp hash). Re-validation later (owner record reused) keeps the release only\n'
     '#     while the stamp still names that collection and the bytes are unchanged. Otherwise the run stays held with the reason.\n'
     '#   - a released run that then fails authentication is listed under release_auth_fail as well as auth_fail (16k 4).\n'
     '#   - CMDR_POST_HOLD=<file> reads the hold list from a frozen bundle copy instead of out/ (16k 7.2).\n'
     '#   - schema = "cmdr_post v9".\n'
     '# Usage: python cmdr_post_v9.py    (CMDR_POST_OUT=<folder> for tests)\n'),
    ('HOLD_P = os.path.join(OUT, "cmdr_post_hold.json")\n',
     'HOLD_P = os.environ.get("CMDR_POST_HOLD", os.path.join(OUT, "cmdr_post_hold.json"))\n'),
    ('held, hold_released, hold_candidates = [], [], []\n',
     'held, hold_released, hold_candidates, release_auth_fail = [], [], [], []\n'
     'REL_KEYS = ("by", "why", "new_attempt", "out_sha256", "evidence", "evidence_sha256")\n'
     '\n'
     '\n'
     'def _sha_file(p):\n'
     '    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None\n'
     '\n'
     '\n'
     'def release_check(tag, rel, blobs, entry):\n'
     '    """16k 4: "" when the release names a valid new collection that is on disk now, else the reason (the run stays held)."""\n'
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
     '    if stp.get("attempt") != rel["new_attempt"] or rec.get("attempt") != rel["new_attempt"]:\n'
     '        # a later v3.7 re-validation rewrites the stamp with its own attempt and links the previous stamp (driver v3.7\n'
     '        # 1241-1247); the release holds while the bytes are still the approved ones (checked above)\n'
     '        if not (rec.get("reused") is True and stp.get("revalidated_by") and stp.get("prev_stamp_sha256")\n'
     '                and rec.get("attempt") == stp.get("attempt")):\n'
     '            return "the stamp or the owner record names another collection than the released one"\n'
     '    hp = os.path.join(OUT, entry.get("handover") or "_no_handover_", "stamps", tag + ".json")\n'
     '    if not entry.get("handover") or _sha_file(hp) != entry.get("stamp_sha256"):\n'
     '        return "the held original\'s stamp copy is not found in the hand-over folder by the held hash"\n'
     '    held_att = (json.load(open(hp, encoding="utf-8")) or {}).get("attempt")\n'
     '    if hashlib.sha256(blobs["driver_stamp.json"]).hexdigest() == entry.get("stamp_sha256") or (held_att and held_att == rel["new_attempt"]):\n'
     '        return "the released collection is the held original"\n'
     '    if _sha_file(rel["evidence"]) != rel["evidence_sha256"]:\n'
     '        return "the evidence file is missing or changed"\n'
     '    try:\n'
     '        e = json.load(open(rel["evidence"], encoding="utf-8"))\n'
     '    except (OSError, json.JSONDecodeError):\n'
     '        return "the evidence file is unreadable"\n'
     '    if not (e.get("comparison_ready") is True and e.get("new_run_valid") is True and not e.get("changed_while_reading")\n'
     '            and e.get("new_attempt") == rel["new_attempt"] and e.get("new_out_sha256") == rel["out_sha256"]):\n'
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
     '        rel = HOLD[tag].get("released")\n'
     '        rel_why = release_check(tag, rel, blobs, HOLD[tag]) if isinstance(rel, dict) else ("no release record" if not rel else "release is not a record")\n'
     '        ok_rel = not rel_why  # 16k 4: bound to the new collection\'s attempt, bytes and evidence, never the held original\n'),
    ('                         "release_rejected": bool(rel)})\n',
     '                         "release_rejected": bool(rel), "release_why": rel_why})\n'),
    ('    if pending_release and not why:  # written only once the released run passed authentication (16j 5.3)\n'
     '        hold_released.append(pending_release)\n',
     '    if pending_release and not why:  # written only once the released run passed authentication (16j 5.3)\n'
     '        hold_released.append(pending_release)\n'
     '    if pending_release and why:  # 16k 4: counted with the holds as well as with the auth failures\n'
     '        release_auth_fail.append({"tag": tag, "why": why})\n'),
    ('res["schema"] = "cmdr_post v8"\n', 'res["schema"] = "cmdr_post v9"\nres["release_auth_fail"] = release_auth_fail\n'),
]
for a, b in R:
    n = s.count(a)
    if n != 1:
        sys.exit(f"anchor found {n} times: {a[:70]!r}")
    s = s.replace(a, b)
open(os.path.join(EV, "cmdr_post_v9.py"), "w", encoding="utf-8").write(s)
print("wrote", os.path.join(EV, "cmdr_post_v9.py"))
