# Mutation check of the CPU tests: each mutation breaks one gate in a COPY of rand_scenes (sibling folder
# _eval/_mut_rand_scenes_<k>, removed afterwards; the real files are never edited), runs the tests that should notice,
# and reports CAUGHT (at least one of them fails) or MISSED. A pattern that is not found exactly once is NOT APPLIED (a failure).
#   python mutate_rand_scenes.py [name filter ...]   -> _eval/out_rand/_cpu_tests/mutations_<stamp>.json
# Revised 2026-10-13 for ASTRA 17d (common-boundary stops, pairing, record joins, push linkage, gate v3, wording, settle).
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.dirname(HERE)
T_VAL = "test_validate_attempt_mutations"
T_FLOW = "test_driver_flow_retry_and_records"
T_CX = "test_astra17d_counterexamples_not_rc0"
T_STOP = "test_driver_protective_stops_at_the_common_boundary"
T_DRY = "test_driver_dry_run_and_paths"
T_REAL = "test_real_isaac_slot_v3_accepts_our_args"
T_REC = "test_record_checks_csv_npz_and_meaning"
T_CROSS = "test_cross_checks_refuse_empty_unequal_and_repeat_mismatch"
_TRUE_TESTS = {"fingerprint_complete": [T_VAL, T_CX], "terrain_complete": [T_VAL, T_CX]}


def true_cond(name, cond):
    """Mutation: the validator check `name` always passes (`True or <cond>`)."""
    return (f"M {name} always passes", "rand_lib.py", f'add("{name}", {cond},', f'add("{name}", True or {cond},',
            _TRUE_TESTS.get(name, [T_VAL]))


MUTATIONS = [
    # frame gate
    ("M01 dark threshold 0", "rand_gate.py", "DARK, FLAT, BLUE = 20.0, 6.0, 0.35", "DARK, FLAT, BLUE = 0.0, 6.0, 0.35", ["test_frame_check_known"]),
    ("M02 no re-render loop", "rand_gate.py", "while not ok and tries < max_rerender:", "while False:", ["test_capture_with_gate_retry_loop"]),
    ("M03 web copy frames not gated", "rand_gate.py", '    if aw["bad"]:\n        bad.append', '    if False:\n        bad.append',
     ["test_publish_accepts_clean_and_refuses_defects"]),
    ("M04 faststart not checked", "rand_gate.py", "    if not fs:\n", "    if False:\n", ["test_publish_accepts_clean_and_refuses_defects"]),
    ("M05 master not gated", "rand_gate.py", 'if am["bad"] or (expect_master_frames', 'if False and (expect_master_frames',
     ["test_publish_accepts_clean_and_refuses_defects"]),
    # log and push basics
    ("M06 Traceback ignored", "rand_lib.py", '"Traceback (most recent call last)" not in log', "True", [T_VAL, T_FLOW]),
    ("M07 any done line accepted", "rand_lib.py", 'dones == [(expect["scene"], expect["attempt_id"])]', "len(dones) >= 1", [T_VAL, T_FLOW]),
    ("M08 interval reset off by one step", "rand_lib.py", "            t = f32(interval_s)\n", "            t = f32(interval_s + step_dt)\n",
     ["test_predict_fire_states_vs_event_manager_arithmetic"]),
    ("M09 heading rotation sign", "rand_lib.py", "return [c * vx - s * vy,", "return [c * vx + s * vy,", ["test_to_world_rotation"]),
    ("M10 range check off", "rand_lib.py", "if world6[i] < lo - tol or world6[i] > hi + tol:", "if False:", ["test_range_checks", T_VAL]),
    ("M11 combine priority ignored", "rand_lib.py", "mode = ma if COMBINE_PRIORITY[ma] >= COMBINE_PRIORITY[mb] else mb", "mode = ma",
     ["test_effective_friction"]),
    ("M12 smoke sky failure assumed", "rand_driver.py", 'failed_as_expected = (not s3["validation"]["ok"] and', "failed_as_expected = True or (",
     ["test_driver_stops_when_smoke_gate_does_not_refuse"]),
    ("M13 no retry", "rand_driver.py", "for k in range(1, tries + 1):", "for k in range(1, 2):", [T_FLOW]),
    ("M14 overlay strip in the 3D area", "rand_overlay.py", "dr.rectangle([8, 622, W - 8, 712]", "dr.rectangle([8, 560, W - 8, 712]",
     ["test_overlay_layout_and_gate_interaction"]),
    ("M15 handover path allowed", "rand_lib.py", 'if "/handover" in n or ', "if ", [T_DRY]),
    ("M17 material tolerance 1.0", "rand_lib.py", 'abs(mt.get(f"{k}_min", -9) - fr[k]) <= 1e-6 and abs(mt.get(f"{k}_max", -9) - fr[k]) <= 1e-6',
     'abs(mt.get(f"{k}_min", -9) - fr[k]) <= 1.0 and abs(mt.get(f"{k}_max", -9) - fr[k]) <= 1.0', [T_VAL]),
    # 17d 2.1: common-boundary stops
    ("M20 guard stop not at the boundary", "rand_driver.py", 'if rec["guard_stopped"] or 99 in codes:', "if False:", [T_STOP, T_CX]),
    ("M21 gate codes not at the boundary", "rand_driver.py", "stop_code = next((c for c in STOP_CODES if c in codes), None)", "stop_code = None", [T_STOP]),
    ("M22 free memory not checked before launch", "rand_driver.py", "if free is not None and free < self.a.min_free_mib:", "if False:", [T_STOP]),
    ("M23 driver ignores the stop file", "rand_driver.py", "if self.a.stop_file and os.path.exists(self.a.stop_file):", "if False:",
     ["test_driver_stop_file_deadline_and_slot98"]),
    ("M24 driver ignores the deadline", "rand_driver.py", "if self.a.deadline and time.time() > self.a.deadline:", "if False:",
     ["test_driver_stop_file_deadline_and_slot98"]),
    ("M25 code 89 not a stop", "rand_driver.py", ',\n              89: "conversion attempt beyond the expected one, or the isolation runner blocked something"}',
     "}", [T_STOP]),
    # 17d 2.2: pairing
    ("M26 pairing does not reach the rc", "rand_driver.py", 'rc = 4 if failed else (6 if (cross["pairing"]["applicable"] and not cross["pairing"]["valid"]) else 0)',
     "rc = 4 if failed else 0", [T_CX]),
    ("M27 empty fingerprints equal", "rand_driver.py", "equal = bool(fps) and complete and all(v == ref for v in fps.values())",
     "equal = all(v == ref for v in fps.values())", [T_CROSS]),
    ("M28 terrain not compared", "rand_driver.py", "t_equal = t_valid and len(", "t_equal = True or len(", [T_CX]),
    ("M29 repeated reference not required", "rand_driver.py",
     '                reasons.append(f"the reference scene differs between two processes (max {md})")\n', "                pass\n", [T_CROSS]),
    ("M30 base vs push compared after the push", "rand_driver.py", 'j0 = int(ev[0]["state_j"])\n', 'j0 = int(ev[0]["state_j"]) + 50\n', [T_FLOW, T_CX]),
    ("M31 NaN equals NaN again", "rand_lib.py",
     "            if na.any() or nb.any() or not (np.isfinite(a).all() and np.isfinite(b).all()):\n                return float(\"inf\")\n",
     "            if False:\n                return float(\"inf\")\n", ["test_compare_rows_nan_is_not_equal"]),
    true_cond("fingerprint_complete", "not fpp"),
    true_cond("terrain_complete", "not tp"),
    # 17d 2.3: record joins
    ("M34 judgement columns may be NaN", "rand_lib.py", 'P["judge_finite_before_fall"] = bool(jn >= jf)', 'P["judge_finite_before_fall"] = True', [T_REC, T_CX]),
    ("M35 CSV and NPZ not joined", "rand_lib.py", 'P["csv_equals_npz"] = bool(same_nan and (err <= 0).all())', 'P["csv_equals_npz"] = True', [T_REC, T_VAL]),
    ("M36 contact flags not binary-checked", "rand_lib.py", '"binary_flags": all(np.isin(col[c][w], (0.0, 1.0)).all() for c in BINARY_COLUMNS),',
     '"binary_flags": True,', [T_REC, T_VAL]),
    ("M37 quaternion not checked", "rand_lib.py", '"unit_quaternion": bool((np.abs(q - 1.0) <= 1e-3).all()),', '"unit_quaternion": True,', [T_REC]),
    ("M38 fall not recomputed", "rand_lib.py", 'P["fall_matches_result"] = (bool(', 'P["fall_matches_result"] = True or (bool(', [T_REC, T_VAL]),
    ("M39 probe NaN not separated", "rand_lib.py", 'P["probe_columns"] = bool(np.isnan(pr).all())', 'P["probe_columns"] = True', [T_REC]),
    ("M40 NaN markers not checked", "rand_lib.py", 'P["nan_markers"] = bool(np.array_equal(', 'P["nan_markers"] = True or bool(np.array_equal(', [T_REC]),
    # 17d 2.4: pushes against the frozen schedule, request bundle
    ("M41 direction not recomputed", "rand_lib.py", "if max(abs(a - b) for a, b in zip(w_req, w)) > 1e-6:", "if False:", [T_VAL, T_CX]),
    ("M42 request and order not checked", "rand_lib.py",
     'if any(abs(float(req.get(key, float("nan"))) - schedule[k][key]) > 1e-12 for key in PUSH_KEYS) or e.get("frame") != frame:', "if False:", [T_VAL]),
    ("M43 after - before not checked", "rand_lib.py", "if max(abs((a - b) - m) for a, b, m in zip(va, vb, wm)) > 1e-6:", "if False:", [T_VAL]),
    ("M44 record push rows not checked", "rand_lib.py",
     '            P["record_rows"].append(f"event {k}: record row {j} {r} != index {k} delta {expect_row}")\n', "            pass\n", [T_VAL]),
    true_cond("train_yaml_is_request", 'res.get("train_yaml_sha256") == expect["train_yaml_sha256"]'),
    true_cond("train_contract_kept", "not tcp"),
    true_cond("eval_env_is_training", "not evp"),
    ("M48 probe flag not in the request", "rand_lib.py", '    same["friction_probe"] = (res.get("friction_probe"), expect["probe"])\n', "", [T_VAL]),
    # lead 20:06: gate v3 record, one conversion expected
    true_cond("slot_version", 'slot.get("slot_version") == SLOT_VERSION'),
    true_cond("slot_attempt_is_this_attempt", 'slot.get("attempt") == expect["attempt_id"]'),
    true_cond("slot_rc_zero", 'slot.get("slot_rc") == 0'),
    true_cond("slot_child_rc_zero", 'slot.get("child_rc") == 0'),
    true_cond("slot_scene_built", 'slot.get("state_at_release") == "scene_built"'),
    true_cond("slot_expect_one_conversion", 'slot.get("expect_conversions") == str(EXPECTED_CONVERSIONS) and slot.get("expect_violation", None) is False'),
    ("M slot_expected_conversions always passes", "rand_lib.py", 'add("slot_expected_conversions", isinstance(fin, list)',
     'add("slot_expected_conversions", True or isinstance(fin, list)', [T_VAL]),
    true_cond("slot_usd_inside_root", 'slot.get("usd_outside_root", None) == [] and slot.get("assigned_outside_root", None) == []'),
    ("M slot_usd_assigned always passes", "rand_lib.py", 'add("slot_usd_assigned", slot.get("usd_unassigned", None) == []',
     'add("slot_usd_assigned", True or slot.get("usd_unassigned", None) == []', [T_VAL]),
    true_cond("slot_no_conflicts", '"conflicts" in slot and not slot["conflicts"]'),
    true_cond("slot_registry_ok", 'slot.get("registry_error", None) == ""'),
    true_cond("slot_not_killed", '"killed" not in slot and "slot_error" not in slot'),
    true_cond("slot_usd_root_is_this_attempt", 'slot.get("usd_root") == root'),
    ("M slot_cmd_isolated always passes", "rand_lib.py", 'add("slot_cmd_isolated", any(', 'add("slot_cmd_isolated", True or any(', [T_VAL]),
    true_cond("usd_isolate_patched", 'bool(iso.get("patched_by")) and iso.get("version") == SLOT_VERSION and iso.get("blocked", None) == []'),
    ("M62 gate v2 script", "rand_lib.py", 'SLOT_SCRIPT = os.path.join(EVAL, "isaac_slot_v3.py")', 'SLOT_SCRIPT = os.path.join(EVAL, "isaac_slot.py")', [T_DRY]),
    ("M63 command without the isolation runner", "rand_lib.py", 'py, ISOLATE_SCRIPT, os.path.join(HERE, "q_rand.py")]', 'py, os.path.join(HERE, "q_rand.py")]', [T_DRY]),
    ("M64 command without --usd_root / --attempt", "rand_lib.py", '            "--usd_root", usd_root, "--attempt", attempt_id,\n', "", [T_DRY, T_REAL]),
    ("M65 scan only out_rand", "rand_lib.py", 'return ",".join([OUT_RAND, os.path.join(EVAL, "out_branch"), os.path.join(EVAL, "out_uncr")])',
     "return OUT_RAND", [T_DRY]),
    ("M66 stop file and deadline not passed", "rand_lib.py",
     '            "--scan_dirs", scan_dirs(), "--stop_file", stop_file, "--deadline", repr(float(deadline)),\n',
     '            "--scan_dirs", scan_dirs(),\n', [T_DRY, T_REAL]),
    ("M67 expected conversions not passed", "rand_lib.py", '            "--expect_conversions", str(EXPECTED_CONVERSIONS), "--",\n', '            "--",\n',
     [T_DRY]),
    # 17d 5: wording and the low-friction default
    ("M68 same-start claim burned in", "q_rand.py", '· 사전 정한 1판 (결과로 고르지 않음) · "', '· 같은 출발 · 사전 정한 1판 (결과로 고르지 않음) · "',
     ["test_no_forbidden_text"]),
    ("M69 feet-only wording", "q_rand.py", '마찰 · 로봇 모든 shape 재질', '마찰 · 로봇 발 재질', ["test_no_forbidden_text"]),
    ("M70 low friction default back to 0.2", "rand_driver.py", 'ap.add_argument("--fric_low", type=float, default=0.0,',
     'ap.add_argument("--fric_low", type=float, default=0.2,', [T_DRY]),
    # 17d 7: settle time
    ("M71 settle not censored at the next push", "rand_lib.py",
     'cands = [(n, "end of record")] + [(j, "next push") for j in pushes if j > j0][:1]', 'cands = [(n, "end of record")]',
     ["test_push_response_censored_and_timestamp_span"]),
    ("M72 settle hold by sample count", "rand_lib.py", "if t[k] - t[start] >= settle_hold_s - 1e-9:", "if k - start >= 12:",
     ["test_push_response_censored_and_timestamp_span"]),
]


def main():
    stamp = time.strftime("%Y%m%d-%H%M%S")
    only = sys.argv[1:]
    out = []
    for k, (name, fn, old, new, tests) in enumerate(MUTATIONS, 1):
        if only and not any(o in name for o in only):
            continue
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
                print(f"{out[-1]['result']:8s} {name}", flush=True)
                continue
            open(p, "w", encoding="utf-8").write(src.replace(old, new))
            r = subprocess.run([sys.executable, os.path.join(cp, "test_rand_scenes.py")] + tests, cwd=cp,
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            fails = [ln for ln in r.stdout.splitlines() if ln.startswith("FAIL ")]
            ran = [ln for ln in r.stdout.splitlines() if ln.startswith(("PASS ", "FAIL "))]
            res = "CAUGHT" if fails else ("MISSED" if ran else f"NO TEST RAN (rc {r.returncode})")
            out.append({"mutation": name, "file": fn, "tests": tests, "result": res, "failing": [f[:300] for f in fails],
                        "stderr_tail": r.stderr[-300:] if not ran else ""})
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
