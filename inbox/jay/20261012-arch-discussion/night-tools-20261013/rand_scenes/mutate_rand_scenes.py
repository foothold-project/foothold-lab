# Mutation check of the CPU tests: each mutation breaks one gate in a COPY of rand_scenes (sibling folder
# _eval/_mut_rand_scenes_<k>, removed afterwards; the real files are never edited), runs the tests that should notice,
# and reports CAUGHT (at least one of them fails) or MISSED.
#   python mutate_rand_scenes.py   -> _eval/out_rand/_cpu_tests/mutations_<stamp>.json
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.dirname(HERE)
MUTATIONS = [
    ("M01 dark threshold 0", "rand_gate.py", "DARK, FLAT, BLUE = 20.0, 6.0, 0.35", "DARK, FLAT, BLUE = 0.0, 6.0, 0.35",
     ["test_frame_check_known"]),
    ("M02 no re-render loop", "rand_gate.py", "while not ok and tries < max_rerender:", "while False:",
     ["test_capture_with_gate_retry_loop"]),
    ("M03 web copy frames not gated", "rand_gate.py", "    if aw[\"bad\"]:\n        bad.append", "    if False:\n        bad.append",
     ["test_publish_accepts_clean_and_refuses_defects"]),
    ("M04 faststart not checked", "rand_gate.py", "    if not fs:\n", "    if False:\n",
     ["test_publish_accepts_clean_and_refuses_defects"]),
    ("M05 master not gated", "rand_gate.py", "if am[\"bad\"] or (expect_master_frames", "if False and (expect_master_frames",
     ["test_publish_accepts_clean_and_refuses_defects"]),
    ("M06 Traceback ignored", "rand_lib.py", "\"Traceback (most recent call last)\" not in log", "True",
     ["test_validate_attempt_mutations", "test_driver_flow_retry_and_records"]),
    ("M07 any done line accepted", "rand_lib.py", "dones == [(expect[\"scene\"], expect[\"attempt_id\"])]", "len(dones) >= 1",
     ["test_validate_attempt_mutations", "test_driver_flow_retry_and_records"]),
    ("M08 interval reset off by one step", "rand_lib.py", "            t = f32(interval_s)\n", "            t = f32(interval_s + step_dt)\n",
     ["test_predict_fire_states_vs_event_manager_arithmetic"]),
    ("M09 heading rotation sign", "rand_lib.py", "return [c * vx - s * vy,", "return [c * vx + s * vy,",
     ["test_to_world_rotation"]),
    ("M10 range check off", "rand_lib.py", "if world6[i] < lo - tol or world6[i] > hi + tol:", "if False:",
     ["test_range_checks", "test_validate_attempt_mutations"]),
    ("M11 combine priority ignored", "rand_lib.py", "mode = ma if COMBINE_PRIORITY[ma] >= COMBINE_PRIORITY[mb] else mb", "mode = ma",
     ["test_effective_friction"]),
    ("M12 smoke sky failure assumed", "rand_driver.py", "failed_as_expected = (not s3[\"validation\"][\"ok\"] and", "failed_as_expected = True or (",
     ["test_driver_stops_when_smoke_gate_does_not_refuse"]),
    ("M13 no retry", "rand_driver.py", "for k in range(1, tries + 1):", "for k in range(1, 2):",
     ["test_driver_flow_retry_and_records"]),
    ("M14 overlay strip in the 3D area", "rand_overlay.py", "dr.rectangle([8, 622, W - 8, 712]", "dr.rectangle([8, 560, W - 8, 712]",
     ["test_overlay_layout_and_gate_interaction"]),
    ("M15 handover path allowed", "rand_lib.py", "if \"/handover\" in n or ", "if ",
     ["test_driver_dry_run_and_paths"]),
    ("M16 NaN core columns allowed", "rand_lib.py", "out[\"core_finite\"] = bool(all(np.isfinite(col[c]).all() for c in CORE_FINITE))",
     "out[\"core_finite\"] = True", ["test_record_roundtrip_and_checks"]),
    ("M17 material tolerance 1.0", "rand_lib.py", "abs(mt.get(f\"{k}_min\", -9) - fr[k]) <= 1e-6 and abs(mt.get(f\"{k}_max\", -9) - fr[k]) <= 1e-6",
     "abs(mt.get(f\"{k}_min\", -9) - fr[k]) <= 1.0 and abs(mt.get(f\"{k}_max\", -9) - fr[k]) <= 1.0", ["test_validate_attempt_mutations"]),
    ("M18 guard stop not stopping", "rand_driver.py", "            if rec[\"guard_stopped\"]:\n", "            if False:\n",
     ["test_driver_stops_on_gpu_guard"]),
    ("M19 base vs push compared after the push", "rand_driver.py", "j0 = ev[0][\"state_j\"]\n", "j0 = ev[0][\"state_j\"] + 50\n",
     ["test_driver_flow_retry_and_records"]),
    # isaac_slot v2 contract (lead 10/13 19:02)
    ("M20 slot attempt id not checked", "rand_lib.py", "add(\"slot_attempt_is_this_attempt\", slot.get(\"attempt\") == expect[\"attempt_id\"],",
     "add(\"slot_attempt_is_this_attempt\", True,", ["test_validate_attempt_mutations"]),
    ("M21 slot rc not checked", "rand_lib.py", "add(\"slot_rc_zero\", slot.get(\"slot_rc\") == 0,", "add(\"slot_rc_zero\", True,",
     ["test_validate_attempt_mutations", "test_real_isaac_slot_accepts_our_args"]),
    ("M22 child rc not checked", "rand_lib.py", "add(\"slot_child_rc_zero\", slot.get(\"child_rc\") == 0,", "add(\"slot_child_rc_zero\", True,",
     ["test_validate_attempt_mutations"]),
    ("M23 scene_built not checked", "rand_lib.py", "add(\"slot_scene_built\", slot.get(\"state_at_release\") == \"scene_built\",",
     "add(\"slot_scene_built\", True,", ["test_validate_attempt_mutations"]),
    ("M24 USD folder count not checked", "rand_lib.py", "add(\"slot_one_usd_folder\", isinstance(", "add(\"slot_one_usd_folder\", True or isinstance(",
     ["test_validate_attempt_mutations"]),
    ("M25 USD outside the root allowed", "rand_lib.py", "add(\"slot_usd_inside_root\", slot.get(\"usd_outside_root\", None) == [],",
     "add(\"slot_usd_inside_root\", True,", ["test_validate_attempt_mutations", "test_real_isaac_slot_accepts_our_args"]),
    ("M26 conflicts allowed", "rand_lib.py", "add(\"slot_no_conflicts\", \"conflicts\" in slot and not slot[\"conflicts\"],",
     "add(\"slot_no_conflicts\", True,", ["test_validate_attempt_mutations"]),
    ("M27 USD root of another attempt allowed", "rand_lib.py", "add(\"slot_usd_root_is_this_attempt\", slot.get(\"usd_root\") == _norm(expect[\"usd_root\"]),",
     "add(\"slot_usd_root_is_this_attempt\", True,", ["test_validate_attempt_mutations"]),
    ("M28 isolation runner not required in cmd", "rand_lib.py", "add(\"slot_cmd_isolated\", any(", "add(\"slot_cmd_isolated\", True or any(",
     ["test_validate_attempt_mutations"]),
    ("M29 isolate_state not checked", "rand_lib.py", "add(\"usd_isolate_patched\", bool(iso.get(\"patched_by\")),", "add(\"usd_isolate_patched\", True,",
     ["test_validate_attempt_mutations"]),
    ("M30 command without usd_isolate_run", "rand_lib.py", "py, os.path.join(EVAL, \"usd_isolate_run.py\"), os.path.join(HERE, \"q_rand.py\")]",
     "py, os.path.join(HERE, \"q_rand.py\")]", ["test_driver_dry_run_and_paths"]),
    ("M31 command without --usd_root / --attempt", "rand_lib.py", "            \"--usd_root\", usd_root, \"--attempt\", attempt_id,\n", "",
     ["test_driver_dry_run_and_paths", "test_real_isaac_slot_accepts_our_args"]),
    ("M32 scan only out_rand", "rand_lib.py", "return \",\".join([OUT_RAND, os.path.join(EVAL, \"out_branch\"), os.path.join(EVAL, \"out_uncr\")])",
     "return OUT_RAND", ["test_driver_dry_run_and_paths"]),
    ("M33 stop file and deadline not passed to isaac_slot", "rand_lib.py",
     "\"--scan_dirs\", scan_dirs(), \"--stop_file\", stop_file, \"--deadline\", repr(float(deadline)), \"--\",",
     "\"--scan_dirs\", scan_dirs(), \"--\",", ["test_driver_dry_run_and_paths", "test_real_isaac_slot_accepts_our_args"]),
    ("M34 driver ignores the stop file", "rand_driver.py", "if self.a.stop_file and os.path.exists(self.a.stop_file):", "if False:",
     ["test_driver_stop_file_deadline_and_slot98"]),
    ("M35 driver ignores the deadline", "rand_driver.py", "if self.a.deadline and time.time() > self.a.deadline:", "if False:",
     ["test_driver_stop_file_deadline_and_slot98"]),
    ("M36 driver retries after isaac_slot 98", "rand_driver.py", "if rec[\"rc\"] == 98:", "if False:",
     ["test_driver_stop_file_deadline_and_slot98"]),
]


def main():
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = []
    for k, (name, fn, old, new, tests) in enumerate(MUTATIONS, 1):
        cp = os.path.join(EVAL, f"_mut_rand_scenes_{k:02d}")
        if os.path.exists(cp):
            shutil.rmtree(cp)
        shutil.copytree(HERE, cp, ignore=shutil.ignore_patterns("__pycache__"))
        try:
            p = os.path.join(cp, fn)
            src = open(p, encoding="utf-8").read()
            n = src.count(old)
            if n != 1:
                out.append({"mutation": name, "result": f"NOT APPLIED (pattern found {n} times)"})
                continue
            open(p, "w", encoding="utf-8").write(src.replace(old, new))
            r = subprocess.run([sys.executable, os.path.join(cp, "test_rand_scenes.py")] + tests, cwd=cp,
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            fails = [ln for ln in r.stdout.splitlines() if ln.startswith("FAIL ")]
            out.append({"mutation": name, "file": fn, "tests": tests, "result": "CAUGHT" if fails else "MISSED",
                        "failing": [f[:200] for f in fails]})
        finally:
            shutil.rmtree(cp, ignore_errors=True)
        print(f"{out[-1]['result']:8s} {name}", flush=True)
    rp = os.path.join(EVAL, "out_rand", "_cpu_tests", f"mutations_{stamp}.json")
    os.makedirs(os.path.dirname(rp), exist_ok=True)
    json.dump(out, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    caught = sum(1 for x in out if x["result"] == "CAUGHT")
    print(json.dumps({"caught": caught, "total": len(out), "report": rp}))
    return 0 if caught == len(out) else 1


if __name__ == "__main__":
    sys.exit(main())
