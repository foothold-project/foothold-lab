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
#   - every file is read between two os.stat calls (inode, size, mtime_ns) and checked again at the end; a file that
#     changed during its read or before the end stops the aggregate with exit 3 and nothing written (16g 3.2: a legacy
#     run's files replaced after its meta was read). Limit: a writer that replaces only files not yet read and never
#     touches one already read is not seen; the evaluator writes meta.json last, and v3.7 moves a run's old folder away
#     before it measures it again, so a run in progress has no stamp.
#   - an owner log whose attempt file says "revalidating", or names another attempt than the log, is being rebuilt by a
#     restarted driver: the aggregate is held (exit 5, nothing written) instead of mixing the old log with new stamps.
#   - inputs_manifest keeps per run: form, origin (the stamp's origin field; "v3.2 legacy stamp" for a legacy stamp),
#     owner log, the record's and the stamp's attempt and the stamp's sha256 besides the four output hashes (16g 3.3 /
#     4). origin_counts sums them; legacy_stamps still counts stamps that are legacy now, not runs of legacy origin.
#   - out/cmdr_post_hold.json {tag: {stamp_sha256, why}} keeps named runs out of every table while their stamp is the
#     held one (res["held"] with the reason); a run measured again has a new stamp and is used again (res["hold_released"])
#     (16h 4.3: the 11:38 stand run that shared its USD folder must not stand in the frozen tables as checked).
#   - schema = "cmdr_post v8".
# Usage: python cmdr_post_v8.py    (CMDR_POST_OUT=<folder> for tests)''')

rep('''    drv["logs"][name] = {"version": ver, "experiment": d.get("experiment"), "runs": len(d.get("runs", [])),
                         "ended": d.get("ended"), "stopped": d.get("stopped")}
''', '''    drv["logs"][name] = {"version": ver, "experiment": d.get("experiment"), "runs": len(d.get("runs", [])),
                         "ended": d.get("ended"), "stopped": d.get("stopped"), "attempt": d.get("attempt")}
    for r_ in d.get("runs", []):  # 16g 3.1: the last record of each tag is what this log published
        if isinstance(r_, dict) and r_.get("tag"):
            drv.setdefault("rec", {})[r_["tag"]] = r_
    try:
        af = json.load(open(os.path.join(OUT, f"{name}.attempt.json"), encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        af = None
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
        rec = drv.get("rec", {}).get(tag)  # 16g 3.1: the stamp must be the run its log published
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
    why, form = auth(tag, m, blobs)''', '''HOLD = {}  # 16h 4.3: out/cmdr_post_hold.json {tag: {"stamp_sha256", "why"}}: a run kept out of the tables on purpose
if os.path.exists(os.path.join(OUT, "cmdr_post_hold.json")):
    HOLD = json.load(open(os.path.join(OUT, "cmdr_post_hold.json"), encoding="utf-8"))
held, hold_released = [], []
for tag in valid:
    _, m, rest = tag.split("_", 2)
    blobs = read_run(tag)
    if tag in HOLD:
        cur = hashlib.sha256(blobs["driver_stamp.json"]).hexdigest() if blobs["driver_stamp.json"] is not None else None
        if cur == HOLD[tag].get("stamp_sha256"):  # the very run that was held: out of the tables, reason kept
            held.append({"tag": tag, "why": HOLD[tag].get("why"), "stamp_sha256": cur})
            continue
        hold_released.append({"tag": tag, "held_stamp": HOLD[tag].get("stamp_sha256"), "now_stamp": cur})  # measured again
    why, form = auth(tag, m, blobs)''')
rep('''    manifest[tag] = {"form": form, **{f: hashlib.sha256(blobs[f]).hexdigest() for f in OUT4}}''',
    '''    stp_ = json.loads(blobs["driver_stamp.json"].decode("utf-8"))
    rec_ = drv.get("rec", {}).get(tag) or {}
    manifest[tag] = {"form": form, "origin": stp_.get("origin") or ("v3.2 legacy stamp" if form == "legacy" else "hashed (stamp has no origin field)"),
                     "owner": drv["owner"][tag], "record_attempt": rec_.get("attempt"), "stamp_attempt": stp_.get("attempt"),
                     "stamp_sha256": hashlib.sha256(blobs["driver_stamp.json"]).hexdigest(),
                     **{f: hashlib.sha256(blobs[f]).hexdigest() for f in OUT4}}''')

rep('''res["schema"] = "cmdr_post v7"''', '''res["schema"] = "cmdr_post v8"''')
rep('''res["legacy_tags"] = legacy
''', '''res["legacy_tags"] = legacy
res["held"] = held
res["hold_released"] = hold_released
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
''')
rep('''L = ["# CMD-R 표 (자동 생성 · cmdr_post_v6.py)", "",''', '''L = ["# CMD-R 표 (자동 생성 · cmdr_post_v8.py)", "",''')

open(sys.argv[2], "w", encoding="utf-8").write(s)
print("ok", len(s))
