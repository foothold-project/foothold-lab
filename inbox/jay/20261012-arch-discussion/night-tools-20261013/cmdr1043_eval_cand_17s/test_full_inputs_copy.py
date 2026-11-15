"""Copy registered source bytes into codexE and test full 1043 input checks."""
import argparse
import json
from pathlib import Path
import shutil
import sys

from s1043_manifest import ROOT, canonical_hash, check_inputs, inside, launch_errors, load, sha256

ap = argparse.ArgumentParser()
ap.add_argument("--run-id", required=True)
a = ap.parse_args()
if not a.run_id.replace("_", "").isalnum():
    raise SystemExit("unsafe run id")
base = ROOT / "fixture_real" / "complete" / a.run_id
if base.exists():
    raise SystemExit("run id exists")
base.mkdir(parents=True)
m = load(ROOT / "cand/manifest_s1043.json")
c = m["contract"]
source_branch = Path("C:/isaac/ext/go2_rl_robotlab/_eval/out_branch")
for name, rec in c["inputs"].items():
    src = Path(rec["path"])
    if source_branch == src or source_branch in src.parents:
        dst = base / "out_branch" / src.relative_to(source_branch)
    else:
        dst = base / "other_inputs" / name / src.name
    if not inside(dst):
        raise SystemExit("copy destination outside codexE")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    rec["path"] = str(dst)
for arm in ("off", "on"):
    stamp_path = Path(c["inputs"][c["branches"][arm]["stamp"]]["path"])
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    for rel in stamp["sha256"]:
        src = source_branch / rel
        dst = base / "out_branch" / rel
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
m["contract_sha256"] = canonical_hash(c)
mp = base / "manifest.json"
mp.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
checks = []
def check(label, expected):
    got = check_inputs(m)
    ok = (not got) if expected is None else any(expected in x for x in got)
    checks.append({"name": label, "ok": ok, "errors": got[:10]})
    print(label, "PASS" if ok else "FAIL", got[:3], flush=True)

check("normal_full_copy", None)
for label, key, expected in (("off_bundle_changed", "off_bundle_json", "input hash off_bundle_json"),
                             ("on_stamp_changed", "on_stamp", "input hash on_stamp"),
                             ("off_result_changed", "off_result", "input hash off_result")):
    p = Path(c["inputs"][key]["path"])
    original = p.read_bytes()
    try:
        p.write_bytes(original + b"x")
        check(label, expected)
    finally:
        p.write_bytes(original)
    check(label + "_restored", None)

approval_path = base / "synthetic_approval.json"
approval = {"approved": True, "experiment": "cmdr_s1042_pair_eval", "train_seed": 1042,
            "contract_sha256": m["contract_sha256"], "stage": "A", "by": "fixture", "approved_at": "fixture"}
approval_path.write_text(json.dumps(approval), encoding="utf-8")
m["execution"]["contract_sha256"] = m["contract_sha256"]
m["execution"]["approval_path"] = str(approval_path)
m["execution"]["approval_sha256"] = sha256(approval_path)
e = launch_errors(m)
ok = "approval contract mismatch" in e
checks.append({"name": "approval_1042_rejected", "ok": ok, "errors": e[:20]})
print("approval_1042_rejected", "PASS" if ok else "FAIL", flush=True)
approval.update(experiment=c["experiment"], train_seed=1043)
approval_path.write_text(json.dumps(approval), encoding="utf-8")
m["execution"]["approval_sha256"] = sha256(approval_path)
e = launch_errors(m)
ok = not any(x.startswith("approval ") for x in e) and any("undecided" in x for x in e)
checks.append({"name": "synthetic_1043_approval_still_blocks_launch", "ok": ok, "errors": e[:20]})
print("synthetic_1043_approval_still_blocks_launch", "PASS" if ok else "FAIL", flush=True)

out = base / "test_results.json"
out.write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("RESULTS", sum(x["ok"] for x in checks), "/", len(checks))
raise SystemExit(0 if all(x["ok"] for x in checks) else 1)
