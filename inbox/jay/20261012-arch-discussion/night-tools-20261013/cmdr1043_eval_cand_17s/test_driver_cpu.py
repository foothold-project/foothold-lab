"""No-child CLI checks for the 1043 A driver."""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from s1043_manifest import ROOT, assert_isolated, inside, load, sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", args.run_id):
        raise ValueError("unsafe run id")
    print("sys.executable", sys.executable)
    print("candidate.__file__", __file__)
    print("candidate.sha256", sha256(__file__))
    path = ROOT / "cand/cmdr_eval_driver_s1043.py"
    manifest_path = ROOT / "cand/manifest_s1043.json"
    out = ROOT / "cand/reports" / f"driver_cpu_{args.run_id}.json"
    if not inside(out) or out.exists():
        raise RuntimeError("report path not new and isolated")
    m = load(manifest_path)
    print("ISOLATION", assert_isolated(m))
    expected_python = Path(m["contract"]["runtime"]["python"]).resolve()
    if Path(sys.executable).resolve() != expected_python:
        raise RuntimeError("환경 불일치")
    h = sha256(path)
    base = [sys.executable, "-B", str(path), "--manifest", str(manifest_path), "--expect_self_sha", h]
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1")
    cases = []
    for name, tail, rc in (("A_plan", ["--cpu_plan"], 0), ("B_refuse", ["--plan", "B"], 8),
                           ("remeasure_refuse", ["--plan", "remeasure"], 8),
                           ("self_hash_refuse", ["--expect_self_sha", "0" * 64, "--cpu_plan"], 3)):
        cmd = base + tail
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        row = {"name": name, "rc": p.returncode, "expected_rc": rc, "ok": p.returncode == rc,
               "stdout": p.stdout[-2000:], "stderr": p.stderr[-2000:]}
        if name == "A_plan" and p.returncode == 0:
            plan = json.loads(p.stdout.splitlines()[-1])
            row["count"] = plan["A_count"]
            row["unique_tags"] = len(set(plan["A_tags"]))
            row["ok"] &= plan["A_count"] == row["unique_tags"] == 45 and plan["B_remaining"] == 510
        cases.append(row)
    old_argv = sys.argv
    try:
        sys.argv = [str(path), "--manifest", str(manifest_path), "--expect_self_sha", h]
        spec = importlib.util.spec_from_file_location("driver_candidate", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.argv = old_argv
    parent = module.q("q_eval_cmdr.py", "cq_p20000_flat_stop03_on_s1000",
                      module.MODELS["p20000"][0], "flat", "stop03", 100, True, 1000)
    branch = module.q("q_eval_cmdr.py", "cq_off24000_flat_stop03_on_s1000",
                      module.MODELS["off24000"][0], "flat", "stop03", 100, True, 1000)
    q_ok = (parent[parent.index("--outdir") + 1] == m["contract"]["paths"]["data"] and
            branch[branch.index("--outdir") + 1] == m["contract"]["paths"]["data"] and
            "--train_yaml" not in parent and branch[branch.index("--train_yaml") + 1] ==
            m["contract"]["inputs"]["parent_env_yaml"]["path"])
    cases.append({"name": "q_outdir_and_roles", "ok": q_ok, "rc": 0 if q_ok else 1, "expected_rc": 0})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for case in cases:
        print(case["name"], "PASS" if case["ok"] else "FAIL", "rc", case["rc"])
    return 0 if all(case["ok"] for case in cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
