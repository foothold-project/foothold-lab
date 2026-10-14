"""CPU CLI tests. Every input is a copy under codexE."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import re
from pathlib import Path

from s1043_manifest import ROOT, assert_isolated, inside, load, sha256

MANIFEST = ROOT / "cand/manifest_s1043.json"
COMPARE = ROOT / "cand/cmdr_bundle_compare_s1043.py"
SRC = ROOT / "fixture_real"
CASES = None
OUT = ROOT / "cand/reports/bundle_compare.json"
RESULTS = None
EXPECTED_COMPARE_SHA = "548aae46e52948cfe998d4cc4ad193781b887105a29b850f24f5d94c08bd8f95"


def compare_case(name, edit=None, expected_rc=0, expected_problem=None):
    here = CASES / name
    off, on = here / "off", here / "on"
    if here.exists():
        raise RuntimeError(f"case directory already exists: {here}")
    for arm, dst in (("off", off), ("on", on)):
        dst.mkdir(parents=True)
        for fn in ("bundle.json", "bundle.npz"):
            shutil.copy2(SRC / arm / fn, dst / fn)
    if edit:
        edit(off, on)
    cmd = [sys.executable, "-B", str(COMPARE), "--manifest", str(MANIFEST), "--off", str(off),
           "--on", str(on), "--out", str(OUT), "--expect_self_sha", EXPECTED_COMPARE_SHA]
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1")
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    report = json.loads(OUT.read_text(encoding="utf-8")) if OUT.is_file() else {}
    problems = report.get("problems", [])
    ok = p.returncode == expected_rc and (expected_problem is None or any(expected_problem in x for x in problems))
    return {"name": name, "ok": ok, "rc": p.returncode, "expected_rc": expected_rc,
            "problems": problems, "stdout": p.stdout[-2000:], "stderr": p.stderr[-2000:]}


def json_edit(path, fun):
    obj = json.loads(path.read_text(encoding="utf-8"))
    fun(obj)
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def main():
    global CASES, RESULTS
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", args.run_id):
        raise ValueError("run-id must be a short safe name")
    CASES = ROOT / "cand/work/stage1_cases" / args.run_id
    RESULTS = ROOT / "cand/reports" / f"stage1_results_{args.run_id}.json"
    print("sys.executable", sys.executable)
    print("candidate.__file__", __file__)
    print("candidate.sha256", sha256(__file__))
    expected_python = Path("C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe").resolve()
    if Path(sys.executable).resolve() != expected_python or not inside(__file__):
        raise RuntimeError("환경 불일치")
    m = load(MANIFEST)
    if sha256(COMPARE) != EXPECTED_COMPARE_SHA:
        raise RuntimeError("환경 불일치: comparator sha256")
    print("ISOLATION", assert_isolated(m))
    for path in (CASES, OUT, RESULTS, SRC):
        if not inside(path):
            raise RuntimeError(f"isolation failure {path}")
    if CASES.exists():
        raise RuntimeError("stage1 already run; preserve earlier evidence and use a new case root")
    CASES.mkdir(parents=True)
    results = [compare_case("normal", expected_rc=0)]
    results.append(compare_case("seed_1042", lambda off, on: json_edit(off / "bundle.json", lambda j: j["meta"]["args"].update(seed=1042)),
                                expected_rc=1, expected_problem="args.seed"))
    results.append(compare_case("parent_hash", lambda off, on: json_edit(on / "bundle.json", lambda j: j["meta"].update(parent_sha256="0" * 64)),
                                expected_rc=1, expected_problem="parent hash mismatch"))
    results.append(compare_case("one_arm_bytes", lambda off, on: (on / "bundle.npz").write_bytes((on / "bundle.npz").read_bytes() + b"x"),
                                expected_rc=1, expected_problem="bundle.npz differs"))
    results.append(compare_case("normal_final", expected_rc=0))
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for row in results:
        print(row["name"], "PASS" if row["ok"] else "FAIL", "rc", row["rc"], "problems", len(row["problems"]))
    return 0 if all(row["ok"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
