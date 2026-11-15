"""CPU-only startup, reset, USD identity and flat deployment checks."""
import copy
import ast
import csv
import io
import json
import math
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import time
import numpy as np

HERE = Path(__file__).parent
ROOT = HERE.parent
RUN_ROOT = ROOT / "fixture_17r_c" / f"run_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
sys.path.insert(0, str(HERE))
from s1043_manifest import CANDIDATE_FILES, canonical_hash, check_inputs, sha256
from frozen_exec_s1043 import command_errors
from test_17r_b import make


def check(label, condition):
    print(("PASS" if condition else "FAIL"), label, flush=True)
    if not condition:
        raise AssertionError(label)


def driver_namespace(manifest):
    path = HERE / "cmdr_eval_driver_s1043.py"
    old = sys.argv
    try:
        sys.argv = [str(path), "--manifest", str(manifest), "--expect_self_sha", sha256(path), "--cpu_plan"]
        return runpy.run_path(str(path), run_name="cpu_contract_probe")
    finally:
        sys.argv = old


def startup_checks():
    m, _ = make(0)
    m["execution"]["stage"] = "A"
    c = m["contract"]
    ns = driver_namespace(HERE / "manifest_s1043.json")
    for suffix, spec in c["startup_tests"]["suffixes"].items():
        tag = f"cq_test_deadbeef_g0t123456p123_{suffix}"
        ck = spec["checkpoint"]
        model = c["parent"]["path"] if ck == "p20000" else c["inputs"][f"{'off' if ck.startswith('off') else 'on'}_model_{ck[-5:]}"]["path"]
        cells = ",".join(c["startup_tests"]["smoke_cells"]) if spec["cells"] == "all_11" else spec["cells"]
        bad_yaml = {"other_run": c["startup_tests"]["other_run_yaml"],
                    "sibling": c["inputs"]["parent_agent_yaml"]["path"]}.get(spec["yaml"])
        q = ns["q"](spec["evaluator"], tag, model, "flat", cells, spec["episodes"], True, 1000,
                    train_yaml=bad_yaml, small=spec["small"])
        data = Path(c["paths"]["data"])
        cmd = [c["runtime"]["python"], c["inputs"]["source_gpu_guard.py"]["path"], "--gpu", "0",
               "--min_free_mib", "4096", "--log", str(data / f"{tag}.log"),
               "--summary", str(data / f"{tag}.guard.json"), "--",
               c["runtime"]["python"], c["inputs"]["source_usd_isolate_run_v3.py"]["path"]] + q[1:]
        check("startup " + suffix, command_errors(m, ck, cmd) == [])
        check("startup duplicate " + suffix, bool(command_errors(m, ck, cmd + ["--episodes", "999"])))
    bad = copy.deepcopy(m)
    bad["contract"]["evaluation"]["reset"]["origin_xy_m"] = [-9, 9]
    check("reset XY mutation", "reset contract differs from pinned q" in check_inputs(bad, require_files=False))
    check("smoke source registered", ns["tests"].__globals__["CONTRACT"]["inputs"]["source_q_eval.py"]["path"] != str(HERE / "q_eval.py"))
    out = RUN_ROOT / "usd"
    out.mkdir(parents=True, exist_ok=True)
    ns["usd_index"].__globals__["OUT"] = str(out)
    ns["usd_index"].__globals__["USD_IDX"].clear()
    suffix = "usd_20261014_001833_9514"
    for tag, attempt in (("one", "attemptA"), ("two", "attemptB")):
        (out / f"{tag}.log").write_text(f"C:/tmp/{attempt}/IsaacLab/{suffix}/go2.usd\n[INFO]: Time taken for scene creation\n", encoding="utf-8")
    check("USD full path differs", len(ns["usd_index"]()) == 2)
    check("USD distinct roots accepted", ns["usd_check"]("one") == "" and ns["usd_check"]("two") == "")
    other = copy.deepcopy(m)
    other_root = RUN_ROOT / "other_writer"
    other_root.mkdir(parents=True, exist_ok=True)
    other["contract"]["paths"]["data"] = str(other_root)
    other["contract_sha256"] = canonical_hash(other["contract"])
    other_manifest = other_root / "manifest.json"
    other_manifest.write_text(json.dumps(other), encoding="utf-8")
    proc = {"pid": 98765, "name": "python.exe", "cmdline": [sys.executable, str(HERE / "cmdr_eval_driver_s1043.py"),
            "--manifest", str(other_manifest), "--log", "same"]}
    check("other writer root distinct", ns["driver_writers"]("same", procs=[proc]) == [])
    proc_equal = dict(proc, cmdline=[sys.executable, str(HERE / "cmdr_eval_driver_s1043.py"),
                                     "--manifest=" + str(other_manifest), "--log=same"])
    check("other writer root equals syntax", ns["driver_writers"]("same", procs=[proc_equal]) == [])


def flat_checks():
    flat = RUN_ROOT / "flat_bundle"
    flat.mkdir(parents=True, exist_ok=True)
    for name in CANDIDATE_FILES:
        shutil.copy2(HERE / name, flat / name)
    m = json.loads((HERE / "manifest_s1043.json").read_text(encoding="utf-8"))
    c = m["contract"]
    c["deployment"]["candidate_dir"] = str(flat)
    c["deployment"]["write_root"] = str(ROOT)
    paths = c["paths"]
    for key in paths:
        if key in ("registry", "convert_lock", "run_lease", "compare_report"):
            paths[key] = str(flat / Path(paths[key]).name)
        else:
            paths[key] = str(flat / key)
    probe = flat / "probe.txt"
    probe.write_text("cpu fixture\n", encoding="utf-8")
    c["fixture_inputs"] = {"probe": {"path": str(probe), "sha256": sha256(probe)}}
    m["contract_sha256"] = canonical_hash(c)
    m["execution"]["contract_sha256"] = m["contract_sha256"]
    manifest = flat / "manifest.json"
    manifest.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    py = c["runtime"]["python"]
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1")
    cmd = [py, "-B", str(flat / "frozen_exec_s1043.py"), "--manifest", str(manifest),
           "--checkpoint_label", "p20000", "--expect_self_sha", sha256(flat / "frozen_exec_s1043.py"), "--cpu_fixture"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=30)
    if r.returncode:
        print("FLAT FROZEN FAILURE", r.returncode, r.stdout, r.stderr, flush=True)
    check("flat frozen CLI", r.returncode == 0 and "READY_CPU_NO_CHILD" in r.stdout)
    cmd = [py, "-B", str(flat / "cmdr_eval_driver_s1043.py"), "--manifest", str(manifest),
           "--expect_self_sha", sha256(flat / "cmdr_eval_driver_s1043.py"), "--cpu_plan"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=30)
    if r.returncode:
        print("FLAT DRIVER FAILURE", r.returncode, r.stdout, r.stderr, flush=True)
    check("flat driver CLI", r.returncode == 0 and '"A_count": 45' in r.stdout)
    check("flat bundle has no cand child", not (flat / "cand").exists())
    malformed = json.loads(manifest.read_text(encoding="utf-8"))
    malformed["contract"]["deployment"]["candidate_dir"] = str(HERE)
    malformed["contract_sha256"] = canonical_hash(malformed["contract"])
    malformed["execution"]["contract_sha256"] = malformed["contract_sha256"]
    malformed_path = flat / "manifest_wrong_layout.json"
    malformed_path.write_text(json.dumps(malformed), encoding="utf-8")
    cmd[cmd.index("--manifest") + 1] = str(malformed_path)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=30)
    check("flat wrong layout refused", r.returncode != 0)


def mae_checks():
    source = (HERE / "cmdr_post_s1043.py").read_text(encoding="utf-8")
    function = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "load")
    scope = {"csv": csv, "io": io, "math": math, "np": np,
             "CONTRACT": {"evaluation": {"mae_missing_policy": "invalidate_entire_run"}},
             "startup": lambda z: [], "main_col": lambda cell: "span_q2_pass", "ref_col": lambda cell: "q2_pass"}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(HERE / "cmdr_post_s1043.py"), "exec"), scope)
    rows = [{"episode": str(i), "cell": "stop03", "mae_vx": "0.1", "mae_vy": "0.2", "mae_wz": "0.3",
             "span_q2_pass": "True", "q2_pass": "True", "span_survived": "True"} for i in range(100)]
    def blobs():
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
        binary = io.BytesIO()
        np.savez(binary, marker=np.zeros(1))
        return {"episodes.csv": buf.getvalue().encode(), "traj.npz": binary.getvalue()}
    check("finite MAE valid", scope["load"]("finite", blobs())["mae_n"] == {"vx": 100, "vy": 100, "wz": 100})
    rows[12]["mae_vx"] = "nan"
    try:
        scope["load"]("nonfinite", blobs())
    except ValueError as exc:
        check("nonfinite MAE invalid run", "entire run invalid" in str(exc))
    else:
        check("nonfinite MAE invalid run", False)


if __name__ == "__main__":
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1"
    startup_checks()
    flat_checks()
    mae_checks()
