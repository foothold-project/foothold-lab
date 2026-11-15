"""A3.2 code mutants. Each case: copy bundle, apply ONE text replacement, run test_s2_a32.py.
CAUGHT only if the unmodified copy passes the script first and the mutant's FIRST 'FAIL <label>' equals the wanted label."""
from __future__ import annotations
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
PY = sys.executable
T = "test_s2_a32.py"
CK, EC, DG, PR = "s2_connect_check_17v.py", "s2_env_config_17v.py", "s2_connect_diag_17v.py", "s2_mesh_probe_a2.py"
CLOCK_OLD = ('''    hold("sensor_timestamp",np.any(np.abs(ts_diff[~scheduled]-CONTROL_DT_S)>CLOCK_TOL_S) or
         np.any(ts_diff[scheduled]>=0) or np.any(np.abs(clock[RESET_STEP]-CONTROL_DT_S)>CLOCK_TOL_S))''')
CASES = (
 ("clock_any_negative_only", CK, CLOCK_OLD, '    hold("sensor_timestamp",np.any(ts_diff<0))',
  T, "A32 scheduled reset: fixture passes", "the intended step-128 reset would HOLD (attempt-3 checker)"),
 ("clock_regress_allowed", CK, 'np.any(np.abs(ts_diff[~scheduled]-CONTROL_DT_S)>CLOCK_TOL_S) or\n         np.any(ts_diff[scheduled]>=0)',
  'np.any(ts_diff[~scheduled]>CONTROL_DT_S+CLOCK_TOL_S) or\n         np.any(ts_diff[scheduled]>=0)',
  T, "A32 same-episode clock regress -> sensor_timestamp", "a clock that runs backwards outside the scheduled reset passes"),
 ("clock_stall_allowed", CK, 'np.any(np.abs(ts_diff[~scheduled]-CONTROL_DT_S)>CLOCK_TOL_S) or',
  'np.any(ts_diff[~scheduled]<0) or',
  T, "A32 same-episode clock stall (constant time) -> sensor_timestamp", "a stalled clock passes"),
 ("clock_after_reset_unchecked", CK, ' or np.any(np.abs(clock[RESET_STEP]-CONTROL_DT_S)>CLOCK_TOL_S))', ')',
  T, "A32 clock after the reset not at one control step -> sensor_timestamp", "any restart time after the reset passes"),
 ("episode_plus_one_relaxed", CK, 'a["episode_ids"][RESET_STEP]-a["episode_ids"][RESET_STEP-1] == 1',
  'a["episode_ids"][RESET_STEP]-a["episode_ids"][RESET_STEP-1] >= 1',
  T, "A32 episode jumps by 2 at the scheduled reset -> stale_packet", "episode +2 at the scheduled reset passes"),
 ("termination_not_checked", CK, 'hold("unscheduled_termination", np.any(np.asarray(a["termination"]) != 0) or np.any(np.asarray(a["timeout"]) != 0))',
  'hold("unscheduled_termination", False)',
  T, "A32 an unscheduled termination with a real reset is its own HOLD", "automatic resets are not separately flagged"),
 ("timeout_not_checked", CK, ' or np.any(np.asarray(a["timeout"]) != 0))', ')',
  T, "A32 a timeout flag -> unscheduled_termination", "timeouts are not flagged"),
 ("reset_marker_not_checked", CK, 'hold("reset_marker", not np.array_equal(', 'hold("reset_marker", False and not np.array_equal(',
  T, "A32 scheduled reset with no reset marker -> reset_marker", "a reset without a marker passes"),
 ("ray_start_xy_not_checked", CK, 'hold("ray_start_xy", np.max(', 'hold("ray_start_xy", False and np.max(',
  T, "A32 ray start XY 1 cm off the analysis XY -> ray_start_xy", "ray start frame is not compared with the analysis XY"),
 ("ray_direction_not_checked", CK, 'hold("ray_direction", np.max(', 'hold("ray_direction", False and np.max(',
  T, "A32 tilted ray direction -> ray_direction", "a tilted ray passes"),
 ("ray_start_height_not_checked", CK, 'hold("ray_start_height", np.any(', 'hold("ray_start_height", False and np.any(',
  T, "A32 rays that start below the terrain surface -> ray_start_height", "rays under the ground pass (the gap_90 fall)"),
 ("boundary_threshold_changed", CK, "return yaw, expected, oracle_z, oracle_finite, oracle_edge, oracle_edge<=boundary_exclusion_m",
  "return yaw, expected, oracle_z, oracle_finite, oracle_edge, oracle_edge<=0.0",
  T, "A32 scheduled reset: fixture passes", "the shared boundary formula drifts from the fixture's"),
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
 ("scope_not_required_by_checker", CK, 'mesh.get("scope")!="sampled_collision_response" or mesh.get("branches_ok") is not True or', '',
  T, "A32 evidence without the sampled-scope statement is refused by the checker", "the checker accepts evidence without scope and branch result"),
 ("asset_digest_invented", DG, 'return ""\n\n\ndef versions_snapshot', 'return "0"*64\n\n\ndef versions_snapshot',
  T, "A32 asset digest of an unreachable https reference is empty, not invented", "a made-up asset digest satisfies the checker"),
 ("mesh_faces_not_compared", PR, "equal = bool(np.array_equal(ui.astype(np.int64), wi.astype(np.int64)))", "equal = True",
  T, "A32 different face order disagrees", "different triangle order is accepted"),
 ("evidence_kind_always_observed", PR, '"kind": "observed_collision_mesh" if not reasons else "unverified_collision_mesh"',
  '"kind": "observed_collision_mesh"',
  T, "A32 evidence is unverified when: mesh disagrees", "any probe result is certified observed"),
 ("occluded_holes_pass", PR, 'row["satisfied"] = bool(nonboundary >= MIN_BRANCH_PLANNED and row["compared"] >= MIN_BRANCH_COMPARED_FRACTION * nonboundary',
  'row["satisfied"] = bool(nonboundary >= MIN_BRANCH_PLANNED and row["compared"] >= 0',
  T, "A32 branches: every hole ray occluded -> not ok (the occluded-holes counterexample)", "a branch with no compared ray counts as satisfied"),
 ("oracle_not_used", PR, 'om = comp & ((st == ST_TERRAIN) != ofin[:, env])', 'om = comp & False',
  T, "A32 branches: PhysX finds ground in a hole -> not ok, counted as oracle and hit/miss mismatch", "the known scene is not an expected answer"),
 ("missing_branch_ignored", PR, 'branches_ok": bool(not missing_required and not unsatisfied and not any_failure)',
  'branches_ok": bool(not unsatisfied and not any_failure)',
  T, "A32 branches: a scene sample that never looks into a hole -> missing_required, not ok", "a branch never exercised passes"),
 ("boundary_rays_compared", PR, "nb = in_branch & ~boundary", "nb = in_branch",
  T, "A32 branches: boundary rays are skipped, and a branch left with too few rays is not satisfied", "edge rays are compared"),
 ("robot_hits_treated_as_terrain", PR, "            if path.startswith(terrain_prefix):", "            if True:",
  T, "A32 physx: a ray the robot collider takes is occluded, not a ground sample", "robot collider hits count as terrain"),
 ("physx_errors_not_recorded", PR, "            status[i] = ST_ERROR\n", "            status[i] = ST_MISS\n",
  T, "A32 physx: a failing query is recorded per ray and the loop goes on", "a failed query reads as a miss"),
 ("time_budget_ignored", PR, "        if self.spent_s > PHYSX_TIME_BUDGET_S:", "        if False:",
  T, "A32 PhysxSampler stops at its time budget and says so", "PhysX sampling can run past its time budget"),
 ("sampler_ignores_step_list", PR, "        if step not in self.steps or self.raycast is None:", "        if self.raycast is None:",
  T, "A32 PhysxSampler records only the pre-registered steps", "PhysX is fired at steps that were not pre-registered"),
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
