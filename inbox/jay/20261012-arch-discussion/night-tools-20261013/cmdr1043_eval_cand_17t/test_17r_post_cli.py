"""Reauthenticate copied 45-run synthetic A data for the updated post CLI."""
import csv
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from s1043_manifest import CANDIDATE_FILES, canonical_hash, sha256


def check(label, ok):
    print(("PASS" if ok else "FAIL"), label, flush=True)
    if not ok:
        raise AssertionError(label)


def fixture(kind):
    source = ROOT / "fixture_synth/integrated_2"
    dest = ROOT / "fixture_17r_post" / f"{kind}_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
    shutil.copytree(source / "data", dest / "data")
    old = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    template = json.loads((HERE / "manifest_s1043.json").read_text(encoding="utf-8"))
    c = old["contract"]
    c["evaluation"] = template["contract"]["evaluation"]
    c["deployment"] = template["contract"]["deployment"]
    c["startup_tests"] = template["contract"]["startup_tests"]
    c["diagnostic"] = template["contract"]["diagnostic"]
    c["device"].update(gpu_index=1, gpu_uuid="GPU-fixture-uuid", CUDA_VISIBLE_DEVICES="1", child_logical_cuda=0)
    for key, value in c["paths"].items():
        c["paths"][key] = str(dest / Path(value).relative_to(source))
    old["contract_sha256"] = canonical_hash(c)
    old["execution"] = template["execution"]
    old["execution"]["contract_sha256"] = old["contract_sha256"]
    manifest = dest / "manifest.json"
    manifest.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
    data = dest / "data"
    dpath = data / "s1043A_base.json"
    d = json.loads(dpath.read_text(encoding="utf-8"))
    pins = {k.removeprefix("source_").removeprefix("config_"): v["sha256"] for k, v in c["inputs"].items()
            if k.startswith(("source_", "config_"))}
    pins.update({name: sha256(HERE / name) for name in CANDIDATE_FILES})
    pins["manifest_s1043.json"] = sha256(manifest)
    d["pins"] = pins
    d["contract_sha256"] = old["contract_sha256"]
    mutate_tag = "cq_off24000_flat_fwd01_on_s1000"
    for rec in d["runs"]:
        tag = rec["tag"]
        folder = data / tag
        meta_file = folder / "meta.json"
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        meta["args"]["outdir"] = str(data)
        meta["args"]["physics_gpu"] = 0
        meta["args"]["active_gpu"] = 0
        meta["devices"]["torch_cuda0_uuid"] = "GPU-fixture-uuid"
        meta_file.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        if kind == "nan" and tag == mutate_tag:
            ep = folder / "episodes.csv"
            rows = list(csv.DictReader(io.StringIO(ep.read_text(encoding="utf-8"))))
            rows[0]["mae_vx"] = "nan"
            buf = io.StringIO(newline="")
            writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
            ep.write_text(buf.getvalue(), encoding="utf-8")
        hashes = {name: sha256(folder / name) for name in ("meta.json", "cells.json", "episodes.csv", "traj.npz")}
        rec["out_sha256"] = hashes
        stamp_file = folder / "driver_stamp.json"
        stamp = json.loads(stamp_file.read_text(encoding="utf-8"))
        stamp["pins"] = pins
        stamp["contract_sha256"] = old["contract_sha256"]
        stamp["out_sha256"] = hashes
        stamp_file.write_text(json.dumps(stamp, ensure_ascii=False), encoding="utf-8")
    dpath.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return dest, manifest


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1"
    post = HERE / "cmdr_post_s1043.py"
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1")
    normal, manifest = fixture("normal")
    cmd = [sys.executable, "-B", str(post), "--manifest", str(manifest),
           "--expect_self_sha", sha256(post), "--cpu_fixture"]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=90)
    if r.returncode:
        print("NORMAL_POST_FAILURE", r.stdout, r.stderr, flush=True)
    check("post physical1 logical0 normal CLI", r.returncode == 0)
    result = json.loads((normal / "reports/cmdr_post.json").read_text(encoding="utf-8"))
    check("post normal 45 valid", result["n_valid_runs"] == 45 and result["a_complete"] is True)
    nan, manifest = fixture("nan")
    cmd[cmd.index("--manifest") + 1] = str(manifest)
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=90)
    check("post NaN MAE CLI invalid", r.returncode != 0 and "entire run invalid" in (r.stdout + r.stderr))
    check("post NaN no false 45 report", not (nan / "reports/cmdr_post.json").exists())


if __name__ == "__main__":
    main()
