"""handover_1400.py: VERIFY-astra-16l 5.2 / 5.3 (lead 10/13 16:08). Every replacement must match exactly once."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
p = os.path.join(HERE, "handover_1400.py")
s = open(p, encoding="utf-8").read()
R = [
    ('    stops0 = {f: sha(os.path.join(OUT, f)) for f in TARGET_STOPS if os.path.exists(os.path.join(OUT, f))}\n',
     '    stops0 = {f: sha(os.path.join(OUT, f)) for f in TARGET_STOPS if os.path.exists(os.path.join(OUT, f))}\n'
     '    hold0 = sha_or_none(os.path.join(OUT, "cmdr_post_hold.json"))  # 16l 5.2: absent at the start is recorded too\n'),
    ('        copies["cmdr_post_hold.json"] = sha(os.path.join(OUT, "cmdr_post_hold.json"))\n',
     '        copies["cmdr_post_hold.json"] = sha(os.path.join(OUT, "cmdr_post_hold.json"))\n'
     '    # 16l 5.3: what a release depends on travels with the bundle: the held original\'s stamp and the release evidence\n'
     '    deps = {}\n'
     '    hold_copy = os.path.join(H, "cmdr_post_hold.json")\n'
     '    try:\n'
     '        hold_obj = json.loads(open(hold_copy, "rb").read().decode("utf-8")) if os.path.exists(hold_copy) else {}\n'
     '    except (UnicodeDecodeError, json.JSONDecodeError):\n'
     '        hold_obj = None\n'
     '        problems.append({"hold list unreadable": "cmdr_post_hold.json"})\n'
     '    for t, e in (hold_obj or {}).items():\n'
     '        if not isinstance(e, dict):\n'
     '            problems.append({"hold entry not a record": t})\n'
     '            continue\n'
     '        src = os.path.join(OUT, e.get("handover") or "_no_handover_", "stamps", t + ".json")\n'
     '        if sha_or_none(src) != e.get("stamp_sha256"):\n'
     '            problems.append({"held original stamp not found by its hash": t})\n'
     '        else:\n'
     '            os.makedirs(os.path.join(H, "held_stamps"), exist_ok=True)\n'
     '            shutil.copy2(src, os.path.join(H, "held_stamps", t + ".json"))\n'
     '            deps[f"held_stamps/{t}.json"] = {"from": src, "sha256": e["stamp_sha256"]}\n'
     '        rel = e.get("released")\n'
     '        if isinstance(rel, dict) and rel.get("evidence"):\n'
     '            if sha_or_none(rel["evidence"]) != rel.get("evidence_sha256"):\n'
     '                problems.append({"release evidence missing or not the recorded bytes": t})\n'
     '            else:\n'
     '                os.makedirs(os.path.join(H, "evidence"), exist_ok=True)\n'
     '                shutil.copy2(rel["evidence"], os.path.join(H, "evidence", t + ".json"))\n'
     '                deps[f"evidence/{t}.json"] = {"from": rel["evidence"], "sha256": rel["evidence_sha256"]}\n'
     '    for rel_p, d in deps.items():\n'
     '        if sha_or_none(os.path.join(H, rel_p)) != d["sha256"]:\n'
     '            problems.append({"dependency copy differs": rel_p})\n'),
    ('    man["copies_sha256"] = copies\n', '    man["copies_sha256"] = copies\n    man["release_deps"] = deps\n'),
    ('    changed = [f for f, h in copies.items() if sha_or_none(os.path.join(OUT, f)) != h]\n',
     '    changed = [f for f, h in copies.items() if sha_or_none(os.path.join(OUT, f)) != h]\n'
     '    if sha_or_none(os.path.join(OUT, "cmdr_post_hold.json")) != hold0 and "cmdr_post_hold.json" not in changed:\n'
     '        changed.append("cmdr_post_hold.json (appeared, changed or disappeared)")\n'
     '    changed += [f"release dependency {d[\'from\']}" for d in deps.values() if sha_or_none(d["from"]) != d["sha256"]]\n'),
]
for a, b in R:
    n = s.count(a)
    if n != 1:
        sys.exit(f"anchor found {n} times: {a[:70]!r}")
    s = s.replace(a, b)
open(p, "w", encoding="utf-8").write(s)
print("patched")
