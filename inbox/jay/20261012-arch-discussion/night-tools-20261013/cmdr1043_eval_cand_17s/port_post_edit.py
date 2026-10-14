"""One-time source transformation from the preserved post v10 copy."""
from pathlib import Path

p = Path(__file__).with_name("cmdr_post_s1043.py")
s = p.read_text(encoding="utf-8")

def replace_span(start, end, new):
    global s
    a = s.index(start)
    b = s.index(end, a)
    s = s[:a] + new + s[b:]

replace_span('LOGS = ["cmdr_eval_driver", "cmdr_eval_driver_g0"]', '\n\nSTATS = {}', '''LOGS = ["s1043A_base"]
EXPERIMENT = CONTRACT["experiment"]
OUT4 = ("meta.json", "cells.json", "episodes.csv", "traj.npz")
expected = {"cq_" + "_".join(map(str, j[:-1])) + "_s" + str(j[-1]): tuple(j)
            for j in CONTRACT["plan"]["A"]}
if len(expected) != 45:
    raise SystemExit("A plan must contain 45 unique tags")
name = LOGS[0]
p_log = Path(OUT) / (name + ".json")
raw_log = p_log.read_bytes()
d = json.loads(raw_log.decode("utf-8"))
if (d.get("version") != "1043-A1" or d.get("experiment") != EXPERIMENT or
        d.get("contract_sha256") != MANIFEST["contract_sha256"] or d.get("stage") != "A"):
    raise SystemExit("1043 A log identity mismatch")
if d.get("pair_fail") or d.get("skipped") or d.get("not_run") or d.get("not_valid"):
    raise SystemExit("A log has failures or missing runs")
if not d.get("complete") or not d.get("ended") or d.get("end_kind") != "complete":
    raise SystemExit("A log incomplete")
if d.get("matrix") != {t: "valid" for t in expected}:
    raise SystemExit("A matrix must contain exactly 45 valid tags")
records = d.get("runs")
if not isinstance(records, list) or len(records) != 45 or [r.get("tag") for r in records] != list(dict.fromkeys(r.get("tag") for r in records)):
    raise SystemExit("A records missing or duplicate")
if {r.get("tag") for r in records} != set(expected) or not all(r.get("valid") and r.get("attempt") for r in records):
    raise SystemExit("A run records invalid")
expected_pins = {k.removeprefix("source_").removeprefix("config_"): v["sha256"]
                 for k, v in CONTRACT["inputs"].items() if k.startswith(("source_", "config_"))}
for filename in ("s1043_manifest.py", "cmdr_bundle_compare_s1043.py", "cmdr_eval_driver_s1043.py",
                 "cmdr_post_s1043.py", "frozen_exec_s1043.py"):
    expected_pins[filename] = sha256(Path(HERE) / filename)
expected_pins["manifest_s1043.json"] = sha256(args.manifest)
if d.get("pins") != expected_pins:
    raise SystemExit("A log pins mismatch")
expected_ckpt = {"p20000": "parent_model", "off22000": "off_model_22000",
                 "on22000": "on_model_22000", "off24000": "off_model_24000", "on24000": "on_model_24000"}
for model in ("p20000", "off24000", "on24000"):
    rec = (d.get("ckpt") or {}).get(model)
    if not isinstance(rec, dict) or rec.get("sha256") != CONTRACT["inputs"][expected_ckpt[model]]["sha256"]:
        raise SystemExit("A checkpoint mismatch: " + model)
p_attempt = Path(OUT) / (name + ".attempt.json")
raw_attempt = p_attempt.read_bytes()
attempt = json.loads(raw_attempt.decode("utf-8"))
if attempt.get("attempt") != d.get("attempt") or attempt.get("state") != "ended":
    raise SystemExit("A attempt mismatch or rebuilding")
drv = {"matrix": d["matrix"], "pair_fail": [], "skipped": [], "owner": {t: name for t in expected},
       "log_pins": {name: d["pins"]}, "log_ckpt": {name: {m: v.get("sha256") for m, v in d["ckpt"].items()}},
       "rec": {(name, r["tag"]): r for r in records}, "inputs": {name: hashlib.sha256(raw_log).hexdigest()},
       "sidecar": {name: raw_attempt},
       "logs": {name: {"version": d["version"], "experiment": EXPERIMENT,
                       "runs": len(records), "ended": d["ended"], "attempt": d["attempt"]}}}
valid = sorted(expected)
''')

replace_span('def auth(tag, m, blobs):', '\n\ndef paired(xs, ys):', '''def auth(tag, m, blobs):
    if any(blobs[f] is None for f in ("driver_stamp.json",) + OUT4):
        return "stamp or output missing"
    try:
        stp = json.loads(blobs["driver_stamp.json"].decode("utf-8"))
    except (ValueError, UnicodeError):
        return "stamp unreadable"
    if not isinstance(stp, dict) or stp.get("stamp_version") != "1043-A1":
        return "legacy or wrong stamp version"
    if (stp.get("experiment") != EXPERIMENT or stp.get("contract_sha256") != MANIFEST["contract_sha256"] or
            stp.get("stage") != "A" or stp.get("origin") != "hashed-at-collection"):
        return "stamp 1043 identity mismatch"
    if stp.get("pins") != drv["log_pins"][name]:
        return "stamp pins mismatch"
    want = drv["log_ckpt"][name].get(m)
    if not want or stp.get("ckpt_sha256") != want:
        return "stamp checkpoint mismatch"
    hashes = stp.get("out_sha256")
    if not isinstance(hashes, dict) or set(hashes) != set(OUT4):
        return "stamp output hashes missing"
    if hashes != {f: hashlib.sha256(blobs[f]).hexdigest() for f in OUT4}:
        return "output hash mismatch"
    rec = drv["rec"].get((name, tag))
    if not rec or not rec.get("valid") or rec.get("out_sha256") != hashes:
        return "owner record mismatch"
    if not stp.get("attempt") or rec.get("attempt") != stp["attempt"]:
        return "collection attempt mismatch"
    return ""


R = {}
manifest = {}
for tag in valid:
    m, fam, cell, noise, seed = expected[tag]
    blobs = read_run(tag)
    why = auth(tag, m, blobs)
    if why:
        raise SystemExit(f"A authentication rejected: {tag}: {why}")
    parsed = load(tag, blobs)
    if parsed["cell"] != cell:
        raise SystemExit(f"A cell mismatch: {tag}")
    R[(m, fam, cell, noise, seed)] = parsed
    stp = json.loads(blobs["driver_stamp.json"].decode("utf-8"))
    rec = drv["rec"][(name, tag)]
    manifest[tag] = {"form": "new", "origin": stp["origin"], "owner": name,
                     "record_attempt": rec["attempt"], "stamp_attempt": stp["attempt"],
                     "stamp_sha256": hashlib.sha256(blobs["driver_stamp.json"]).hexdigest(),
                     **{f: hashlib.sha256(blobs[f]).hexdigest() for f in OUT4}}
if len(R) != 45:
    raise SystemExit("A requires 45 valid unique runs")
''')

replace_span('res["schema"] = "cmdr_post v10"', 'res["origin_counts"] = {}', '''res["schema"] = "cmdr_post_s1043 A1"
res["contract_sha256"] = MANIFEST["contract_sha256"]
res["experiment"] = EXPERIMENT
res["train_seed"] = 1043
res["stage"] = "A"
res["claim"] = CONTRACT["reporting"]["claim"]
res["a_complete"] = len(R) == 45
res["auth_fail"] = []
res["legacy_stamps"] = 0
res["legacy_tags"] = []
''')
replace_span('for name in LOGS:  # 16e 3.2:', 'res["driver_logs"] = drv["logs"]', '''for name in LOGS:
    p = os.path.join(OUT, f"{name}.json")
    if hashlib.sha256(Path(p).read_bytes()).hexdigest() != drv["inputs"][name]:
        raise SystemExit("INPUT CHANGED: driver log")
for tag_, st_ in STATS.items():
    for f_, s0 in st_.items():
        if _st(os.path.join(OUT, tag_, f_)) != s0:
            raise SystemExit("INPUT CHANGED: run file")
for name_, raw0 in drv["sidecar"].items():
    if (Path(OUT) / f"{name_}.attempt.json").read_bytes() != raw0:
        raise SystemExit("INPUT CHANGED: attempt")
''')
s = s.replace('json.dump(res, open(os.path.join(DEST, "cmdr_post.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)',
'''json_bytes = (json.dumps(res, ensure_ascii=False, indent=1, default=float) + "\\n").encode("utf-8")''')
s = s.replace('L = ["# CMD-R 표 (자동 생성 · cmdr_post_v8.py)", "",',
'''L = ["# CMD-R 표 (자동 생성 · cmdr_post_s1043.py)", "",
     CONTRACT["reporting"]["claim"], "",''')
s = s.replace('open(os.path.join(DEST, "CMDR-tables.md"), "w", encoding="utf-8").write("\\n".join(L) + "\\n")',
'''table_bytes = ("\\n".join(L) + "\\n").encode("utf-8")
Path(DEST).mkdir(parents=True, exist_ok=True)
for filename, content in (("cmdr_post.json", json_bytes), ("CMDR-tables.md", table_bytes)):
    target = Path(DEST) / filename
    with tempfile.NamedTemporaryFile(dir=DEST, prefix=filename + ".", suffix=".tmp", delete=False) as f:
        f.write(content)
        temp = Path(f.name)
    os.replace(temp, target)''')
p.write_text(s, encoding="utf-8")
