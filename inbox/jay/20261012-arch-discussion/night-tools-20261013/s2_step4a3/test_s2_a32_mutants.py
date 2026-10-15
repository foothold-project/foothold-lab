"""A3.2 code mutants. Each case: copy bundle, apply ONE text replacement, run test_s2_a32.py.
CAUGHT only if the unmodified copy passes the script first and the mutant's FIRST 'FAIL <label>' equals the wanted label."""
from __future__ import annotations
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
PY = sys.executable
T = "test_s2_a32.py"
CK, EC, DG, PR = "s2_connect_check_17v.py", "s2_env_config_17v.py", "s2_connect_diag_17v.py", "s2_mesh_probe_a2.py"
TS_OLD = 'hold("sensor_timestamp",np.any((ts_diff<0)&~reset_at) or np.any((ts_diff>=0)&reset_at))'
CASES = (
 ("clock_check_reverted_to_any_negative", CK, TS_OLD, 'hold("sensor_timestamp",np.any(ts_diff<0))',
  T, "A32 fixture (clock rewinds exactly at the step-128 reset) passes", "the intended reset would HOLD again"),
 ("clock_rewind_allowed_anywhere", CK, TS_OLD, 'hold("sensor_timestamp",False or np.any((ts_diff>=0)&reset_at))',
  T, "A32 clock rewind without an episode change -> sensor_timestamp", "a clock that rewinds with no reset passes"),
 ("clock_rewind_not_required_at_reset", CK, TS_OLD, 'hold("sensor_timestamp",np.any((ts_diff<0)&~reset_at))',
  T, "A32 reset without a clock rewind -> sensor_timestamp", "a reset the sensor never saw passes"),
 ("boundary_threshold_changed", CK, "return yaw, expected, oracle_z, oracle_finite, oracle_edge, oracle_edge<=boundary_exclusion_m",
  "return yaw, expected, oracle_z, oracle_finite, oracle_edge, oracle_edge<=0.0",
  T, "A32 fixture (clock rewinds exactly at the step-128 reset) passes", "the shared boundary formula drifts from the fixture's"),
 ("gravity_left_on", EC, "        rigid.disable_gravity=True", "        rigid.disable_gravity=False",
  T, "A32 eight_case cfg: gravity off for the robot", "the diagnostic robot falls again"),
 ("base_contact_termination_kept", EC, "        cfg.terminations.base_contact=None", "        pass",
  T, "A32 eight_case cfg: base_contact termination removed, time_out kept", "contact resets come back"),
 ("fixed_pose_flag_always_true", DG, "def fixed_pose_ok(arrays,tolerance=.002):\n    return bool(",
  "def fixed_pose_ok(arrays,tolerance=.002):\n    return True or bool(",
  T, "A32 fixed_pose_ok false when the pose moves 5 cm in warmup", "a moving robot is certified fixed"),
 ("mesh_flag_always_true", DG, 'mesh_collision_verified=evidence["kind"]=="observed_collision_mesh")',
  "mesh_collision_verified=True)",
  T, "A32 unverified evidence leaves mesh_collision_verified false and the checker HOLDs", "unverified collision evidence is certified"),
 ("collision_z_not_checked", PR, ' and cmp["hit_z_bad"] == 0', "",
  T, "A32 collision disagrees when the RayCaster plane is 5 cm higher", "a 5 cm height disagreement is accepted"),
 ("mesh_faces_not_compared", PR, "equal = bool(np.array_equal(ui.astype(np.int64), wi.astype(np.int64)))", "equal = True",
  T, "A32 different face order disagrees", "different triangle order is accepted"),
 ("evidence_kind_always_observed", PR, '"kind": "observed_collision_mesh" if not reasons else "unverified_collision_mesh"',
  '"kind": "observed_collision_mesh"',
  T, "A32 evidence is unverified when: mesh disagrees", "any probe result is certified observed"),
 ("occluded_rays_compared", PR, "comparable = (status != 2) & ~edge", "comparable = ~edge",
  T, "A32 occluded rays do not break agreement", "robot-occluded rays count as a disagreement"),
 ("boundary_rays_compared", PR, "comparable = (status != 2) & ~edge", "comparable = (status != 2)",
  T, "A32 boundary rays are skipped, not compared", "edge rays are compared"),
 ("min_rays_zero", PR, "MIN_COMPARED_RAYS = 1000", "MIN_COMPARED_RAYS = 0",
  T, "A32 too few compared rays cannot count as observed", "50 rays count as observed"),
 ("robot_hits_treated_as_terrain", PR, "        if path.startswith(terrain_prefix):", "        if True:",
  T, "A32 a ray the robot occludes is counted as occluded, not compared", "robot collider hits count as terrain"),
)
def run_test(d: Path, script: str):
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", KMP_DUPLICATE_LIB_OK="TRUE", PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([PY, "-B", "-u", str(d / script)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=300, cwd=str(d), env=env)
    fails = [l[5:].strip() for l in (p.stdout or "").splitlines() if l.startswith("FAIL ")]
    return p.returncode, fails
def main():
    only = sys.argv[1:]
    ignore = shutil.ignore_patterns("evidence*", "__pycache__", "mutants_*")
    results = []
    caught = 0
    for name, src, old, new, script, want, meaning in CASES:
        if only and name not in only: continue
        base = Path(tempfile.mkdtemp(prefix="s2_a32m_", dir=HERE.parent))
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
    out = os.environ.get("S2_A32_MUT_OUT")
    if out: Path(out).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.exit(0 if caught == len(results) else 1)
main()
