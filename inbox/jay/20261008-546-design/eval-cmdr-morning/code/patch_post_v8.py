"""cmdr_post_v7.py -> cmdr_post_v8.py (lead 10/13, VERIFY-astra-16g 3 / 4 / 5). Anchors exactly once."""
import sys

s = open(sys.argv[1], encoding="utf-8").read()


def rep(old, new):
    global s
    n = s.count(old)
    assert n == 1, f"anchor count {n}: {old[:80]!r}"
    s = s.replace(old, new)


rep('''# Usage: python cmdr_post_v7.py    (CMDR_POST_OUT=<folder> for tests)''', '''# v8 (10/13 13:15, VERIFY-astra-16g 3 / 4 / 5):
#   - a new-format stamp is used only when it is the run its log published: the owner log's last record for that tag
#     is valid and carries the same four output hashes and the same attempt as the stamp (16g 3.1: v7 accepted a newer
#     normal stamp over a log that still published the older run). Records without hashes never vouch for a new stamp.
#   - every file is read between two os.stat calls (inode, size, mtime_ns) and stat-checked again at the end; a change
#     of those attributes during its read or before the end stops the aggregate with exit 3 and nothing written (16g 3.2).
#     This DETECTS stat changes; it does not prove the bytes stayed the same (16i 5.3: a same-size rewrite with the same
#     mtime_ns is not seen). New-format runs are also bound to their published hashes; a frozen bundle is checked against
#     the hand-over manifest. Limit: a writer that replaces only files not yet read is not seen; the evaluator writes
#     meta.json last, and v3.7 moves a run's old folder away before it measures it again, so a run in progress has no stamp.
#   - an owner log whose attempt file says "revalidating", or names another attempt than the log, is being rebuilt by a
#     restarted driver: the aggregate is held (exit 5, nothing written) instead of mixing the old log with new stamps.
#     A v3.3+ owner log without a readable attempt file is held too (16i 5.2). The attempt files and the hold list are
#     read once and compared byte for byte at the end (exit 3 when changed). Records are looked up per owner log (16i 5.1).
#   - inputs_manifest keeps per run: form, origin (the stamp's origin field; "v3.2 legacy stamp" for a legacy stamp),
#     owner log, the record's and the stamp's attempt and the stamp's sha256 besides the four output hashes (16g 3.3 /
#     4). origin_counts sums them; legacy_stamps still counts stamps that are legacy now, not runs of legacy origin.
#   - out/cmdr_post_hold.json {tag: {stamp_sha256, why, released?}} keeps named runs out of every table (res["held"]
#     with the reason) until the entry carries an explicit "released" record (who, why, the new measurement's attempt).
#     A changed stamp alone is NOT a new measurement (v3.7 rewrites stamps when it re-validates); it is listed under
#     hold_candidates (16h 4.3, 16i 3).
#   - schema = "cmdr_post v8".
# Usage: python cmdr_post_v8.py    (CMDR_POST_OUT=<folder> for tests)''')

rep('''    drv["logs"][name] = {"version": ver, "experiment": d.get("experiment"), "runs": len(d.get("runs", [])),
                         "ended": d.get("ended"), "stopped": d.get("stopped")}
''', '''    drv["logs"][name] = {"version": ver, "experiment": d.get("experiment"), "runs": len(d.get("runs", [])),
                         "ended": d.get("ended"), "stopped": d.get("stopped"), "attempt": d.get("attempt")}
    for r_ in d.get("runs", []):  # 16g 3.1 / 16i 5.1: the last record of each tag in THIS log is what this log published
        if isinstance(r_, dict) and r_.get("tag"):
            drv.setdefault("rec", {})[(name, r_["tag"])] = r_
    ap_ = os.path.join(OUT, f"{name}.attempt.json")
    raw_af = open(ap_, "rb").read() if os.path.exists(ap_) else None
    drv.setdefault("sidecar", {})[name] = raw_af  # 16i 5.2: compared again at the end
    try:
        af = json.loads(raw_af.decode("utf-8")) if raw_af is not None else None
    except (json.JSONDecodeError, UnicodeDecodeError):
        af = "broken"
    if ver != "3.2" and not isinstance(af, dict):  # 16i 5.2: a v3.3+ owner without a readable attempt file is not trusted
        print(f"HELD: {name} (v{ver}) has {'no' if af is None else 'an unreadable'} attempt file. Nothing written", file=sys.stderr)
        sys.exit(5)
    if isinstance(af, dict) and (af.get("state") == "revalidating" or af.get("attempt") != d.get("attempt")):
        print(f"HELD: {name} is being rebuilt by attempt {af.get('attempt')} ({af.get('state')}); the log on disk is "
              f"{d.get('attempt')}. Nothing written", file=sys.stderr)
        sys.exit(5)
''')

rep('''def read_run(tag):
    """the stamp and the four output files, each read once (bytes)."""
    b = {}
    for f in ("driver_stamp.json",) + OUT4:
        try:
            with open(os.path.join(OUT, tag, f), "rb") as fh:
                b[f] = fh.read()
        except FileNotFoundError:
            b[f] = None
    return b
''', '''STATS = {}


def _st(p):
    s_ = os.stat(p)
    return (s_.st_ino, s_.st_size, s_.st_mtime_ns)


def read_run(tag):
    """the stamp and the four output files, each read once (bytes) between two stats; the stats are kept for the end check."""
    b, st = {}, {}
    for f in ("driver_stamp.json",) + OUT4:
        p = os.path.join(OUT, tag, f)
        try:
            s1 = _st(p)
            with open(p, "rb") as fh:
                b[f] = fh.read()
            s2 = _st(p)
        except FileNotFoundError:
            b[f], st[f] = None, None
            continue
        if s1 != s2:
            print(f"INPUT CHANGED during the aggregate: {tag}/{f} while it was read; nothing written", file=sys.stderr)
            sys.exit(3)
        st[f] = s2
    STATS[tag] = st
    return b
''')

rep('''        if any(hashlib.sha256(blobs[f]).hexdigest() != h[f] for f in OUT4):
            return "outputs changed after validation", None
        return "", "new"''', '''        if any(hashlib.sha256(blobs[f]).hexdigest() != h[f] for f in OUT4):
            return "outputs changed after validation", None
        rec = drv.get("rec", {}).get((owner, tag))  # 16g 3.1 / 16i 5.1: the run the OWNER log published
        if rec is None:
            return "no run record for this tag in its log", None
        if not rec.get("valid"):
            return "its log's run record is not valid", None
        if rec.get("out_sha256") != h:
            return "stamp hashes differ from its log's run record", None
        if rec.get("attempt") != stp.get("attempt"):
            return "stamp attempt differs from its log's run record", None
        return "", "new"''')

rep('''for tag in valid:
    _, m, rest = tag.split("_", 2)
    blobs = read_run(tag)
    why, form = auth(tag, m, blobs)''', '''HOLD_P = os.path.join(OUT, "cmdr_post_hold.json")
HOLD_RAW = open(HOLD_P, "rb").read() if os.path.exists(HOLD_P) else None  # 16i 5.2: part of the input, compared at the end
HOLD = json.loads(HOLD_RAW.decode("utf-8")) if HOLD_RAW is not None else {}
held, hold_released, hold_candidates = [], [], []
for tag in valid:
    _, m, rest = tag.split("_", 2)
    blobs = read_run(tag)
    if tag in HOLD:
        cur = hashlib.sha256(blobs["driver_stamp.json"]).hexdigest() if blobs["driver_stamp.json"] is not None else None
        rel = HOLD[tag].get("released")
        if not rel:  # 16i 3: held until an explicit release; a changed stamp is not a new measurement by itself
            held.append({"tag": tag, "why": HOLD[tag].get("why"), "held_stamp": HOLD[tag].get("stamp_sha256"), "now_stamp": cur})
            if cur != HOLD[tag].get("stamp_sha256"):
                hold_candidates.append({"tag": tag, "held_stamp": HOLD[tag].get("stamp_sha256"), "now_stamp": cur})
            continue
        hold_released.append({"tag": tag, "released": rel, "held_stamp": HOLD[tag].get("stamp_sha256"), "now_stamp": cur})
    why, form = auth(tag, m, blobs)''')
rep('''    manifest[tag] = {"form": form, **{f: hashlib.sha256(blobs[f]).hexdigest() for f in OUT4}}''',
    '''    stp_ = json.loads(blobs["driver_stamp.json"].decode("utf-8"))
    rec_ = drv.get("rec", {}).get((drv["owner"][tag], tag)) or {}
    manifest[tag] = {"form": form, "origin": stp_.get("origin") or ("v3.2 legacy stamp" if form == "legacy" else "hashed (stamp has no origin field)"),
                     "owner": drv["owner"][tag], "record_attempt": rec_.get("attempt"), "stamp_attempt": stp_.get("attempt"),
                     "stamp_sha256": hashlib.sha256(blobs["driver_stamp.json"]).hexdigest(),
                     **{f: hashlib.sha256(blobs[f]).hexdigest() for f in OUT4}}''')

rep('''res["schema"] = "cmdr_post v7"''', '''res["schema"] = "cmdr_post v8"''')
rep('''res["legacy_tags"] = legacy
''', '''res["legacy_tags"] = legacy
res["held"] = held
res["hold_released"] = hold_released
res["hold_candidates"] = hold_candidates
res["origin_counts"] = {}
for v_ in manifest.values():
    res["origin_counts"][v_["origin"]] = res["origin_counts"].get(v_["origin"], 0) + 1
''')
rep('''        print(f"INPUT CHANGED during the aggregate: {name}; nothing written", file=sys.stderr)
        sys.exit(3)
''', '''        print(f"INPUT CHANGED during the aggregate: {name}; nothing written", file=sys.stderr)
        sys.exit(3)
for tag_, st_ in STATS.items():  # 16g 3.2: every file read is still the file that was read
    for f_, s0 in st_.items():
        try:
            now = _st(os.path.join(OUT, tag_, f_))
        except FileNotFoundError:
            now = None
        if now != s0:
            print(f"INPUT CHANGED during the aggregate: {tag_}/{f_}; nothing written", file=sys.stderr)
            sys.exit(3)
for name_, raw0 in drv.get("sidecar", {}).items():  # 16i 5.2: the attempt files and the hold list are inputs too
    p_ = os.path.join(OUT, f"{name_}.attempt.json")
    if (open(p_, "rb").read() if os.path.exists(p_) else None) != raw0:
        print(f"INPUT CHANGED during the aggregate: {name_}.attempt.json; nothing written", file=sys.stderr)
        sys.exit(3)
if (open(HOLD_P, "rb").read() if os.path.exists(HOLD_P) else None) != HOLD_RAW:
    print("INPUT CHANGED during the aggregate: cmdr_post_hold.json; nothing written", file=sys.stderr)
    sys.exit(3)
''')
rep('''L = ["# CMD-R 표 (자동 생성 · cmdr_post_v6.py)", "",''', '''L = ["# CMD-R 표 (자동 생성 · cmdr_post_v8.py)", "",''')

open(sys.argv[2], "w", encoding="utf-8").write(s)
print("ok", len(s))
