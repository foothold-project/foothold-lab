"""A3 CPU suite: A2 normal tests + 17x tests + watchdog tests, then every code-mutant set, then a clean-folder import
of the frozen bundle. Run it from a COPY of the frozen folder with --frozen <frozen folder> so the frozen bytes are
never written. Exit 0 only if everything ran and passed."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
NORMAL = (
    "test_s2_scene_a2.py", "test_s2_connect_a2.py", "test_s2_connect_17v.py", "test_s2_17v_core.py",
    "test_s2_sensor_tracker_17v.py", "test_s2_capture_journal_a2.py", "test_s2_device_binding_a2.py",
    "test_s2_stage0_contract_a2.py", "test_s2_job_owner.py", "test_s2_job_object_os.py",
    "test_s2_resource_lease.py", "test_s2_zero_supervisor.py",
    "test_s2_capture_to_check_a3.py", "test_s2_prelaunch_competing_a3.py", "test_s2_hard_watchdog.py",
    "test_s2_a32.py", "test_s2_a33.py",
)
MUTANT_SETS = (  # (label, isolated script and expected caught)
    ("a_mutants", "test_s2_step4_mutants.py", 5),
    ("a2_mutants", "test_s2_a2_mutants.py", 6),
)


def isolated_command(path: Path, *args: str):
    code = ("import runpy,sys;from pathlib import Path;"
            "p=Path(sys.argv[1]);sys.path.insert(0,str(p.parent));"
            "sys.argv=[str(p),*sys.argv[2:]];runpy.run_path(str(p),run_name='__main__')")
    return [sys.executable, "-I", "-B", "-c", code, str(path), *args]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    p.add_argument("--frozen", required=True, type=Path)
    a = p.parse_args()
    if not a.run_id.replace("_", "").isalnum():
        raise ValueError("simple run id required")
    root = HERE / "evidence_s2_step4a3" / a.run_id
    root.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = "-1"
    env["KMP_DUPLICATE_LIB_OK"] = "TRUE"  # fixture children only; never the live launcher
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    results = []
    ok = True
    for name in NORMAL:
        t = time.monotonic()
        proc = subprocess.run(isolated_command(HERE / name), cwd=HERE, env=env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
        (root / (name + ".log")).write_text(proc.stdout, encoding="utf-8")
        item = {"name": name, "exit_code": proc.returncode, "seconds": round(time.monotonic() - t, 2),
                "passes": sum(l.startswith("PASS ") for l in proc.stdout.splitlines())}
        results.append(item)
        print(name, item["exit_code"], item["passes"], flush=True)
        if proc.returncode:
            ok = False
            break
    if ok:
        for label, script, expected in MUTANT_SETS:
            out = root / label
            t = time.monotonic()
            proc = subprocess.run(isolated_command(HERE / script, "--out", str(out)), cwd=HERE, env=env,
                                  text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
            (root / (label + ".log")).write_text(proc.stdout, encoding="utf-8")
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8")) if (out / "summary.json").is_file() else {}
            item = {"name": label, "exit_code": proc.returncode, "seconds": round(time.monotonic() - t, 2),
                    "caught": summary.get("caught", 0), "total": summary.get("total", 0), "expected": expected}
            results.append(item)
            print(label, item["exit_code"], item["caught"], "/", item["total"], flush=True)
            if proc.returncode or item["caught"] != expected or item["total"] != expected:
                ok = False
                break
    if ok:
        for label, script in (("a3_mutants", "test_s2_a3_mutants.py"), ("watchdog_mutants", "test_s2_hard_watchdog_mutants.py"),
                              ("a32_mutants", "test_s2_a32_mutants.py")):
            t = time.monotonic()
            menv = dict(env, S2_A3_MUT_OUT=str(root / (label + ".json")), S2_A32_MUT_OUT=str(root / (label + ".json")))
            proc = subprocess.run(isolated_command(HERE / script), cwd=HERE, env=menv, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
            (root / (label + ".log")).write_text(proc.stdout, encoding="utf-8")
            last = [l for l in proc.stdout.splitlines() if l.startswith("SUMMARY")]
            item = {"name": label, "exit_code": proc.returncode, "seconds": round(time.monotonic() - t, 2),
                    "summary_line": last[-1] if last else None}
            results.append(item)
            print(label, item["exit_code"], item["summary_line"], flush=True)
            if proc.returncode:
                ok = False
                break
    if ok:
        bundle = a.frozen.resolve()
        clean = Path(tempfile.mkdtemp(prefix="s2_a3_run_clean_"))
        for source in bundle.iterdir():
            if source.is_file():
                shutil.copy2(source, clean / source.name)
        lines = [l for l in (bundle / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
        def parts(line):
            digest, name = line.split(None, 1)
            return digest, name.strip().lstrip("*")
        matched = all((clean / parts(l)[1]).is_file() and hashlib.sha256(
            (clean / parts(l)[1]).read_bytes()).hexdigest() == parts(l)[0] for l in lines)
        code = ("import importlib,json,pathlib,sys;p=pathlib.Path(sys.argv[1]).resolve();sys.path.insert(0,str(p));"
                "from s2_stage0_contract_a2 import REQUIRED_BUNDLE;names=[x[:-3] for x in REQUIRED_BUNDLE if x.endswith('.py')];"
                "mods=[importlib.import_module(x) for x in names];assert all(pathlib.Path(x.__file__).resolve().parent==p for x in mods);"
                "print(json.dumps({'imported':len(mods)}))")
        isolated = env.copy()
        isolated.pop("PYTHONPATH", None)
        proc = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(clean)], cwd=clean, env=isolated, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        (root / "frozen_clean_import.log").write_text(proc.stdout, encoding="utf-8")
        imported = json.loads(proc.stdout.strip().splitlines()[-1])["imported"] if proc.returncode == 0 else 0
        item = {"name": "frozen_clean_import", "exit_code": proc.returncode if matched else 1, "hashes_match": matched,
                "lines": len(lines), "imported": imported}
        results.append(item)
        print(item["name"], item["exit_code"], imported, "hashes", matched, "lines", len(lines), flush=True)
        ok = item["exit_code"] == 0 and imported == 22
    summary = {"run_id": a.run_id, "complete": ok, "results": results}
    (root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
