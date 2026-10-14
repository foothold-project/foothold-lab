"""CPU-only end-to-end post, driver plan, frozen-input and mutation checks."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from s1043_manifest import ROOT, canonical_hash, sha256

ap = argparse.ArgumentParser()
ap.add_argument("--run-id", required=True)
a = ap.parse_args()
if not a.run_id.replace("_", "").isalnum():
    raise SystemExit("unsafe run id")
root = ROOT / "fixture_synth" / a.run_id
if root.exists():
    raise SystemExit("run id already exists")
env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", PYTHONDONTWRITEBYTECODE="1")
PY = sys.executable
post = ROOT / "cand/cmdr_post_s1043.py"
driver = ROOT / "cand/cmdr_eval_driver_s1043.py"
frozen = ROOT / "cand/frozen_exec_s1043.py"
results = []

def cmd(parts, envx=None):
    return subprocess.run([PY, "-B", *map(str, parts)], cwd=ROOT, env=env if envx is None else envx,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")

def note(name, got, want, detail=""):
    ok = got == want
    results.append({"name": name, "got": got, "want": want, "ok": ok, "detail": detail[:350]})
    print(name, "PASS" if ok else "FAIL", "got", got, "want", want, flush=True)

made = cmd([ROOT / "cand/make_synth_a.py", "--id", a.run_id])
if made.returncode:
    raise SystemExit(made.stderr)
base = root

def run_post(folder, script=post):
    return cmd([script, "--manifest", folder / "manifest.json", "--expect_self_sha", sha256(script), "--cpu_fixture"])

normal = run_post(base)
normal_obj = json.loads((base / "reports/cmdr_post.json").read_text(encoding="utf-8")) if normal.returncode == 0 else {}
normal_good = (normal.returncode == 0 and normal_obj.get("n_valid_runs") == 45 and
               normal_obj.get("a_complete") is True and
               normal_obj.get("target_verdict", {}).get("24000", {}).get("verdict") == "개선" and
               normal_obj.get("target_verdict", {}).get("24000", {}).get("mean_pp") == 10.0 and
               normal_obj.get("regression_coverage", {}).get("measured") == 3 and
               (base / "reports/CMDR-tables.md").exists())
note("normal_post_45_exact10", normal_good, True, normal.stderr)

reference = cmd([ROOT / "cand/make_v10_reference.py", "--fixture", a.run_id])
if reference.returncode:
    raise SystemExit(reference.stderr)
old_env = dict(env, CMDR_POST_OUT=str(base / "v10_data"), CMDR_POST_DEST=str(base / "v10_reports"))
legacy = cmd(["C:/isaac/ext/go2_rl_robotlab/_eval/cmdr_post_v10.py"], old_env)
old_obj = json.loads((base / "v10_reports/cmdr_post.json").read_text(encoding="utf-8")) if legacy.returncode == 0 else {}
keys = ("targets", "startup", "cells", "holm", "completion", "target_verdict",
        "regression_24000", "regression_coverage", "contract_24000", "n_valid_runs")
note("v10_same_logic_10_fields", legacy.returncode == 0 and all(normal_obj[k] == old_obj[k] for k in keys), True, legacy.stderr)

def variant(label):
    folder = root / "variants" / label
    folder.mkdir(parents=True)
    shutil.copytree(base / "data", folder / "data")
    (folder / "reports").mkdir()
    m = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    for k, original_path in list(m["contract"]["paths"].items()):
        m["contract"]["paths"][k] = str(folder / k / Path(original_path).name) if k in (
            "registry", "convert_lock", "run_lease", "stop", "compare_report") else str(folder / k)
    m["contract_sha256"] = canonical_hash(m["contract"])
    mp = folder / "manifest.json"
    mp.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    logp = folder / "data/s1043A_base.json"
    log = json.loads(logp.read_text(encoding="utf-8"))
    log["contract_sha256"] = m["contract_sha256"]
    log["pins"]["manifest_s1043.json"] = sha256(mp)
    for rec in log["runs"]:
        tag = rec["tag"]
        run = folder / "data" / tag
        meta = json.loads((run / "meta.json").read_text(encoding="utf-8"))
        meta["args"]["outdir"] = str(folder / "data")
        (run / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        stp = json.loads((run / "driver_stamp.json").read_text(encoding="utf-8"))
        stp["contract_sha256"] = m["contract_sha256"]
        stp["pins"] = log["pins"]
        rec["out_sha256"] = {f: sha256(run / f) for f in ("meta.json", "cells.json", "episodes.csv", "traj.npz")}
        stp["out_sha256"] = rec["out_sha256"]
        (run / "driver_stamp.json").write_text(json.dumps(stp, ensure_ascii=False), encoding="utf-8")
    logp.write_text(json.dumps(log, ensure_ascii=False), encoding="utf-8")
    return folder

def edit_json(path, fn):
    obj = json.loads(path.read_text(encoding="utf-8"))
    fn(obj)
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")

def first(folder, model="on24000", cell="stop03", seed=1000):
    return folder / "data" / f"cq_{model}_flat_{cell}_on_s{seed}"

def resign(folder, run):
    tag = run.name
    logp = folder / "data/s1043A_base.json"
    log = json.loads(logp.read_text(encoding="utf-8"))
    hashes = {f: sha256(run / f) for f in ("meta.json", "cells.json", "episodes.csv", "traj.npz")}
    rec = next(r for r in log["runs"] if r["tag"] == tag)
    rec["out_sha256"] = hashes
    logp.write_text(json.dumps(log, ensure_ascii=False), encoding="utf-8")
    edit_json(run / "driver_stamp.json", lambda x: x.update(out_sha256=hashes))

def negative(label, mutate, keyword=None):
    folder = variant(label)
    mutate(folder)
    r = run_post(folder)
    no_output = not any((folder / "reports").iterdir())
    got = r.returncode != 0 and no_output and (keyword is None or keyword in (r.stderr + r.stdout))
    note(label, got, True, f"rc={r.returncode}; " + r.stderr + r.stdout)
    return folder

negative("log_1042", lambda f: edit_json(f / "data/s1043A_base.json", lambda x: x.update(experiment="cmdr_s1042_pair_eval")), "identity")
negative("stamp_1042", lambda f: edit_json(first(f) / "driver_stamp.json", lambda x: x.update(experiment="cmdr_s1042_pair_eval")), "stamp 1043")
def model_1042(f):
    run = first(f)
    edit_json(run / "meta.json", lambda x: x["args"].update(checkpoint="C:/isaac/old1042/model_24000.pt"))
    resign(f, run)
negative("model_1042", model_1042, "meta evaluator")
def on_only(f):
    p = f / "data/s1043A_base.json"
    def op(x):
        x["runs"] = [r for r in x["runs"] if not r["tag"].startswith("cq_p20000_")]
        x["matrix"] = {k: v for k, v in x["matrix"].items() if not k.startswith("cq_p20000_")}
    edit_json(p, op)
negative("on_only_complete", on_only, "45")
negative("parent_hash", lambda f: edit_json(f / "data/s1043A_base.json", lambda x: x["ckpt"]["p20000"].update(sha256="0" * 64)), "checkpoint")
def output_root(f):
    run = first(f)
    edit_json(run / "meta.json", lambda x: x["args"].update(outdir="C:/isaac/ext/go2_rl_robotlab/_eval/out"))
    resign(f, run)
output_bad = negative("output_root_revert", output_root, "meta evaluator")
def device_bad(f):
    run = first(f)
    edit_json(run / "meta.json", lambda x: x["devices"].update(torch_cuda0_uuid="wrong-uuid"))
    resign(f, run)
device_fixture = negative("gpu_0_uuid_1", device_bad, "UUID")
def pair_bad(f):
    run = first(f)
    edit_json(run / "meta.json", lambda x: x["pairing_sha256"].update(init_root_pose="different"))
    resign(f, run)
pair_fixture = negative("pair_fingerprint", pair_bad, "fingerprint")
def duplicate_tag(f):
    edit_json(f / "data/s1043A_base.json", lambda x: x["runs"].append(dict(x["runs"][0])))
negative("duplicate_tag", duplicate_tag, "duplicate")
def edit_episodes(f, mode):
    run = first(f)
    p = run / "episodes.csv"
    rows = list(csv.DictReader(io.StringIO(p.read_text(encoding="utf-8"))))
    if mode == "missing":
        rows.pop()
    else:
        rows[-1]["episode"] = "98"
    out = io.StringIO(newline="")
    w = csv.DictWriter(out, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(rows)
    p.write_text(out.getvalue(), encoding="utf-8")
    resign(f, run)
negative("missing_episode", lambda f: edit_episodes(f, "missing"), "episode ids")
episode_fixture = negative("duplicate_episode", lambda f: edit_episodes(f, "duplicate"), "episode ids")
negative("attempt_revalidating", lambda f: edit_json(f / "data/s1043A_base.attempt.json", lambda x: x.update(state="revalidating")), "attempt")
legacy_env = dict(env, CMDR_POST_HOLD=str(base / "old1042_hold.json"))
legacy_cmd = [post, "--manifest", base / "manifest.json", "--expect_self_sha", sha256(post), "--cpu_fixture"]
legacy_run = cmd(legacy_cmd, legacy_env)
note("legacy_hold_override_refused", legacy_run.returncode != 0 and "legacy post environment override refused" in legacy_run.stderr, True,
     f"rc={legacy_run.returncode}; " + legacy_run.stderr)
def pin_bad(f):
    p = f / "data/s1043A_base.json"
    edit_json(p, lambda x: x["pins"].update(**{"q_eval_cmdr.py": "0" * 64}))
    for tag in json.loads(p.read_text(encoding="utf-8"))["matrix"]:
        edit_json(f / "data" / tag / "driver_stamp.json", lambda x: x["pins"].update(**{"q_eval_cmdr.py": "0" * 64}))
pin_fixture = negative("pin_mismatch", pin_bad, "pins")
def output_byte_bad(f):
    p = first(f) / "episodes.csv"
    p.write_text(p.read_text(encoding="utf-8").replace("0.1", "0.2", 1), encoding="utf-8")
hash_fixture = negative("output_byte_change", output_byte_bad, "output hash")

def rewrite_csv_pass(f, cell, seed, remove):
    run = first(f, cell=cell, seed=seed)
    p = run / "episodes.csv"
    rows = list(csv.DictReader(io.StringIO(p.read_text(encoding="utf-8"))))
    for i in remove:
        for col in ("span_q2_pass", "span_q1a_pass", "span_q1_pass", "q2_pass", "q1a_pass", "q1_pass"):
            rows[i][col] = "False"
    out = io.StringIO(newline="")
    w = csv.DictWriter(out, fieldnames=rows[0].keys())
    w.writeheader(); w.writerows(rows)
    p.write_text(out.getvalue(), encoding="utf-8")
    resign(f, run)

f933 = variant("known_9_9333")
rewrite_csv_pass(f933, "fwd02", 1004, [59])
r933 = run_post(f933)
j933 = json.loads((f933 / "reports/cmdr_post.json").read_text(encoding="utf-8")) if r933.returncode == 0 else {}
v933 = j933.get("target_verdict", {}).get("24000", {})
note("known_9_9333_fails", r933.returncode == 0 and v933.get("verdict") == "개선 아님" and 9.93 < v933.get("mean_pp", 0) < 9.94, True, r933.stderr)

fzero = variant("known_lower_zero")
for seed in range(1000, 1005):
    rewrite_csv_pass(fzero, "stop03", seed, range(50, 60))
rzero = run_post(fzero)
jzero = json.loads((fzero / "reports/cmdr_post.json").read_text(encoding="utf-8")) if rzero.returncode == 0 else {}
vzero = jzero.get("target_verdict", {}).get("24000", {})
note("known_one_lower_zero_fails", rzero.returncode == 0 and vzero.get("verdict") == "개선 아님" and not vzero.get("all_low_above_0"), True, rzero.stderr)

def run_driver(manifest, extra):
    return cmd([driver, "--manifest", manifest, "--expect_self_sha", sha256(driver), *extra])
normal_plan = run_driver(ROOT / "cand/manifest_s1043.json", ["--cpu_plan"])
note("driver_A_plan_45", normal_plan.returncode == 0 and '"A_count": 45' in normal_plan.stdout, True, normal_plan.stderr)
for plan in ("B", "remeasure"):
    r = run_driver(ROOT / "cand/manifest_s1043.json", ["--cpu_plan", "--plan", plan])
    note("driver_" + plan + "_blocked", r.returncode == 8, True, r.stderr + r.stdout)
actual = run_driver(ROOT / "cand/manifest_s1043.json", [])
note("undecided_launch_blocked", actual.returncode == 4 and "undecided" in actual.stdout, True, actual.stderr + actual.stdout)

for label, mutate in (("v2_registry", lambda c: c["device"].update(slot="v2")),
                      ("separate_convert_lock", lambda c: c["device"].update(convert_lock="separate"))):
    folder = variant(label)
    mp = folder / "manifest.json"
    mm = json.loads(mp.read_text(encoding="utf-8"))
    mutate(mm["contract"])
    mm["contract_sha256"] = canonical_hash(mm["contract"])
    mp.write_text(json.dumps(mm, ensure_ascii=False), encoding="utf-8")
    r = run_driver(mp, ["--cpu_plan"])
    note(label, r.returncode == 4, True, r.stderr + r.stdout)

fmp = root / "frozen_manifest.json"
fm = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
finput = root / "frozen_input.txt"
finput.write_text("frozen", encoding="utf-8")
fm["contract"]["fixture_inputs"] = {"sample": {"path": str(finput), "sha256": sha256(finput)}}
fm["contract_sha256"] = canonical_hash(fm["contract"])
fmp.write_text(json.dumps(fm, ensure_ascii=False), encoding="utf-8")
def frozen_run():
    return cmd([frozen, "--manifest", fmp, "--checkpoint_label", "p20000", "--expect_self_sha", sha256(frozen), "--cpu_fixture"])
fr = frozen_run()
note("frozen_input_normal", fr.returncode == 0 and "READY_CPU_NO_CHILD" in fr.stdout, True, fr.stderr + fr.stdout)
finput.write_text("changed", encoding="utf-8")
fr = frozen_run()
note("slot_wait_input_change_blocked", fr.returncode == 92 and "fixture input changed" in fr.stderr, True, fr.stderr + fr.stdout)

mutants = (
    ("device_guard", device_fixture, 'raise ValueError("device index or UUID")', "pass"),
    ("pair_guard", pair_fixture, 'raise ValueError("pair fingerprint mismatch")', "pass"),
    ("episode_guard", episode_fixture, 'raise ValueError(f"{tag}: episode ids are not 0..99")', "pass"),
    ("path_guard", output_bad, 'raise ValueError("meta evaluator contract")', "pass"),
    ("hash_guard", hash_fixture, 'return "output hash mismatch"', 'return ""'),
    ("pin_guard", pin_fixture, 'raise SystemExit("A log pins mismatch")', "pass"),
)
source = post.read_text(encoding="utf-8")
for label, bad_fixture, needle, replacement in mutants:
    mutant = ROOT / "cand" / f"mutant_{a.run_id}_{label}.py"
    if source.count(needle) != 1:
        note("mutant_" + label, "patch failed", "CAUGHT")
        continue
    mutant.write_text(source.replace(needle, replacement, 1), encoding="utf-8")
    good_run = run_post(base, mutant)
    bad_run = run_post(bad_fixture, mutant)
    caught = normal_good and good_run.returncode == 0 and bad_run.returncode == 0
    note("mutant_" + label, "CAUGHT" if caught else "NOT_CAUGHT", "CAUGHT", good_run.stderr + bad_run.stderr)

out = root / "test_results.json"
out.write_text(json.dumps({"normal_first": normal_good, "tests": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("RESULTS", sum(x["ok"] for x in results), "/", len(results), "at", out)
raise SystemExit(0 if all(x["ok"] for x in results) else 1)
