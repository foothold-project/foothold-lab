"""A3 code mutants (17x fixes). Each case: copy bundle, apply ONE text replacement, run ONE test script.
CAUGHT only if the unmodified copy passes that same script first and the mutant's FIRST 'FAIL <label>' equals the wanted label."""
from __future__ import annotations
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
PY = sys.executable
CASES = (
 ("device_uuid_compare_removed", "s2_device_binding_a2.py",
  "    if normalize_uuid(raw)!=normalize_uuid(expected_uuid):raise DeviceHold(\"torch_uuid_mismatch\")",
  "    pass",
  "test_s2_device_binding_a2.py", "other_gpu_uuid_rejected",
  "child GPU identity mismatch is no longer rejected"),
 ("stage_failure_not_recorded", "s2_connect_diag_17v.py",
  "            journal.stage_failure(step,stage,repr(ex),getattr(provider,\"emergency_raw\",None))",
  "            pass",
  "test_s2_capture_journal_a2.py", "step_failure_note_exists",
  "failures outside map derivation lose their stage note and emergency raw"),
 ("ray_index_not_collapsed", "s2_connect_diag_17v.py",
  "        out[\"ray_index\"]=index[0]",
  "        pass",
  "test_s2_capture_to_check_a3.py", "capture_shapes_match_fixture",
  "collector hands the checker a (256,187) ray_index again"),
 ("scene_step_height_precheck_removed", "s2_stage0_contract_a2.py",
  "        if abs(options[\"step_height_m\"]-ans[\"step\"][\"top_z_m\"])>1e-9 or abs(",
  "        if False or abs(",
  "test_s2_stage0_contract_a2.py", "step_height_manifest_differs_from_answer_rejected",
  "prelaunch no longer rejects a step height that differs from the answer scene"),
 ("usd_root_env_not_passed", "s2_zero_supervisor.py",
  "            env[\"FOOTHOLD_USD_ROOT\"]=str(manifest[\"usd_root\"])",
  "            pass",
  "test_s2_stage0_contract_a2.py", "usd_isolation_env_and_wrapper_reach_child",
  "the isolated USD root is not given to the child"),
 ("nested_output_counted_twice", "s2_zero_supervisor.py",
  "    return [p for i,p in enumerate(resolved)\n            if not any(j!=i and (q==p and j<i or q!=p and q in p.parents) for j,q in enumerate(resolved))]",
  "    return resolved",
  "test_s2_stage0_contract_a2.py", "non_overlapping_counts_nested_once",
  "nested output roots are counted twice in the disk budget"),
 ("python_isaac_scan_removed", "s2_stage0_prelaunch.py",
  "            if name.startswith(\"python\"):",
  "            if False:",
  "test_s2_prelaunch_competing_a3.py", "python_branch_run_found",
  "python-launched Isaac tools are no longer seen as competing processes"),
)
def run_test(d: Path, script: str):
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", KMP_DUPLICATE_LIB_OK="TRUE", PYTHONDONTWRITEBYTECODE="1")
    isolated = ("import runpy,sys;from pathlib import Path;d=Path(sys.argv[1]);"
                "sys.path.insert(0,str(d));runpy.run_path(str(d/sys.argv[2]),run_name='__main__')")
    p = subprocess.run([PY, "-I", "-B", "-u", "-c", isolated, str(d), script],
                       capture_output=True, text=True, timeout=300, cwd=str(d), env=env)
    fails = [l[5:].strip() for l in p.stdout.splitlines() if l.startswith("FAIL ")]
    return p.returncode, fails
def main():
    only = sys.argv[1:]
    ignore = shutil.ignore_patterns("evidence*", "__pycache__", "mutants_*")
    results = []
    caught = 0
    for name, src, old, new, script, want, meaning in CASES:
        if only and name not in only: continue
        base = Path(tempfile.mkdtemp(prefix="s2_a3m_", dir=HERE.parent))
        d = base / "b"
        shutil.copytree(HERE, d, ignore=ignore)
        rc0, f0 = run_test(d, script)
        text = (d / src).read_text(encoding="utf-8")
        assert text.count(old) == 1, (name, text.count(old))
        (d / src).write_text(text.replace(old, new), encoding="utf-8")
        rc1, f1 = run_test(d, script)
        ok = rc0 == 0 and not f0 and rc1 != 0 and bool(f1) and f1[0] == want
        caught += bool(ok)
        print("%s %s baseline_rc=%s want=[%s] first_fail=[%s] mutant_rc=%s" % ("CAUGHT" if ok else "NOT_CAUGHT", name, rc0, want, f1[0] if f1 else None, rc1), flush=True)
        results.append({"name": name, "source": src, "test": script, "want": want, "first_fail": f1[0] if f1 else None,
                        "baseline_rc": rc0, "mutant_rc": rc1, "meaning": meaning, "caught": bool(ok)})
        shutil.rmtree(base, ignore_errors=True)
    print("SUMMARY %d/%d CAUGHT" % (caught, len(results)))
    out = os.environ.get("S2_A3_MUT_OUT")
    if out: Path(out).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.exit(0 if caught == len(results) else 1)
main()
