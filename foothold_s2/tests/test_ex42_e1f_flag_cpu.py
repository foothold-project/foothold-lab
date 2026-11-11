"""Known traces and raw bytes for the E1F flag two-window exit."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
import yaml

from foothold_s2.eval.ex42_flag_cells import contract, read_evidence, score_trace, summarize_repeats
from foothold_s2.ex42_e1f_judge import FlagTwoWindowJudge, judge_e1f


ROOT = Path(__file__).parents[2]
CHECKPOINT_SHA = "c" * 64
PLAN_SHA = "d" * 64


def test_e1f_stage_adapter_is_registered_in_a_fresh_score_process():
    code = ("from foothold_s2.ex42_stage_judges import adapter_for; "
            "p={'stages':[{'id':'E1F','exit_judge':'flag_two_window'}]}; "
            "assert adapter_for(p,'E1F').name == 'flag_two_window'")
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                            env={**os.environ, "CUDA_VISIBLE_DEVICES": ""},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def _plan():
    plan = yaml.safe_load((ROOT / "foothold_s2/curriculum/ex42-prep.yaml").read_text(encoding="utf-8"))
    next(row for row in plan["stages"] if row["id"] == "E1F")["parent"] = {"sha256": CHECKPOINT_SHA}
    return plan


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _trace(count, *, fail_env=None, fall_env=None, dt=.1):
    from foothold_s2.eval.fixed_terrain import fixed_assignment
    steps, n = 120, 64
    targets = np.array([[.5 + j, 0] for j in range(count)], dtype=float)
    flags = np.broadcast_to(targets, (n, count, 2)).copy()
    root = np.zeros((steps, n, 3), dtype=float)
    vel = np.zeros_like(root)
    for t in range(steps):
        root[t, :, 0] = targets[min(t // 10, count - 1), 0]
        vel[t, :, 0] = 0 if t >= (count - 1) * 10 else 1
    if fail_env is not None:
        root[:, fail_env, 0] = -2.0
    alive = np.ones((steps, n), dtype=bool)
    if fall_env is not None:
        alive[-5:, fall_env] = False
    levels, types = fixed_assignment(64, 10, 23)
    return {"root_pos_w": root, "root_vel_w": vel, "alive": alive,
            "flags_w": flags, "dt": np.array(dt), "env_origins_w": np.zeros((64, 3)),
            "terrain_levels": levels, "terrain_types": types}


def _write_round(root, plan, seed, *, fail_env=None,
                 plan_sha=PLAN_SHA, checkpoint_sha=CHECKPOINT_SHA):
    cells = contract(plan)
    root.mkdir(parents=True)
    for count_name, count in (("flag_one", 1), ("flag_four", 4)):
        folder = root / count_name
        folder.mkdir()
        receipt = {"format": "foothold-ex42-flag-eval/1", "state": "done",
                   "plan_sha256": plan_sha, "checkpoint_sha256": checkpoint_sha,
                   "seed": seed, "envs": 64, "count": count_name, "cases": {}}
        for mode in ("eval_gt", "eval_pred", "probe_prop_only"):
            case = f"{count_name}_{mode}"
            spec = cells["case_specs"][case]
            trace = _trace(count, fail_env=fail_env)
            npz = folder / f"{case}.npz"
            np.savez_compressed(npz, **trace)
            raw = folder / f"{case}.json"
            content = {"case_id": case, **spec, **score_trace(trace, spec, cells),
                       "trace_file": str(npz), "trace_sha256": _sha(npz)}
            from foothold_s2.eval.fixed_terrain import assignment_sha256
            content["fixed_terrain"] = {"cols": 23,
                                         "assignment_sha256": assignment_sha256(
                                             trace["terrain_levels"], trace["terrain_types"])}
            raw.write_text(json.dumps(content, sort_keys=True), encoding="utf-8")
            receipt["cases"][case] = {"trace_file": str(npz), "trace_sha256": _sha(npz),
                                      "raw_file": str(raw), "raw_sha256": _sha(raw),
                                      "envs": 64, "valid_count": 64,
                                      "success_count": content["success_count"],
                                      "survival_count": content["survival_count"]}
        (folder / "flag_cells.json").write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")


def _full(tmp_path):
    plan = _plan()
    roots = []
    for i, seed in enumerate((42, 42, 43, 44, 45)):
        root = tmp_path / f"repeat_{i}"
        _write_round(root, plan, seed, fail_env=0 if i == 1 else None)
        roots.append(root)
    summary = summarize_repeats(roots, plan=plan, plan_sha256=PLAN_SHA,
                                checkpoint_sha256=CHECKPOINT_SHA)
    cal = tmp_path / "flag_calibration.json"
    cal.write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")
    plan["evaluation"]["flag_cells"]["calibration"] = {"path": str(cal), "sha256": _sha(cal)}
    current = {}
    for count in ("flag_one", "flag_four"):
        current.update(read_evidence(roots[0] / count, plan=plan, plan_sha256=PLAN_SHA,
                                     checkpoint_sha256=CHECKPOINT_SHA, seed=42, count=count))
    return plan, summary, current, roots


def _judge(monkeypatch, plan, current, *, previous=None):
    monkeypatch.setattr("foothold_s2.ex42_e1f_judge.judge_maintenance",
                        lambda score, baseline, measured: {**score, "judgement": "PASS"})
    return judge_e1f({"flag_cells": current}, {}, {}, plan,
                     previous={"flag_cells": previous} if previous is not None else None)


def test_flag_trace_requires_order_stop_and_survival():
    plan = _plan()
    cells = contract(plan)
    spec = cells["case_specs"]["flag_four_eval_gt"]
    assert score_trace(_trace(4), spec, cells)["success_count"] == 64
    assert score_trace(_trace(4, fail_env=3), spec, cells)["success_count"] == 63
    fall = score_trace(_trace(4, fall_env=3), spec, cells)
    assert fall["survival_count"] == 63 and fall["success_count"] == 63
    late = _trace(4)
    late["root_vel_w"][-4:, :, 0] = .06
    assert score_trace(late, spec, cells)["success_count"] == 64  # earlier 0.5 s still qualifies
    no_stop = _trace(4)
    no_stop["root_vel_w"][:, :, 0] = .06
    assert score_trace(no_stop, spec, cells)["success_count"] == 0
    bad = _trace(4)
    bad["alive"][5, 0] = False
    with pytest.raises(ValueError, match="resurrects"):
        score_trace(bad, spec, cells)
    short = _trace(4)
    short["root_pos_w"] = short["root_pos_w"][:-1]
    short["root_vel_w"] = short["root_vel_w"][:-1]
    short["alive"] = short["alive"][:-1]
    with pytest.raises(ValueError, match="full duration"):
        score_trace(short, spec, cells)


def test_five_repeats_and_two_windows_gate(tmp_path, monkeypatch):
    plan, cal, current, _ = _full(tmp_path)
    assert cal["repeat_width"]["flag_four_eval_gt"]["success_count"] == 1
    passed = _judge(monkeypatch, plan, current, previous=current)
    assert passed["judgement"] == "PASS"
    assert passed["stage_exit"]["items"]["flag_calibration"]["judgement"] == "PASS"
    assert FlagTwoWindowJudge().verify(passed, "PASS", "PASS", plan=plan)["stage_exit"] == passed["stage_exit"]
    assert _judge(monkeypatch, plan, current)["judgement"] == "HOLD"
    missing = dict(current)
    missing.pop("flag_four_eval_pred")
    assert _judge(monkeypatch, plan, missing, previous=current)["judgement"] == "HOLD"
    bad = dict(current)
    raw = Path(bad["flag_one_eval_gt"]["raw_file"])
    raw.write_bytes(raw.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="raw SHA"):
        _judge(monkeypatch, plan, bad, previous=current)


def test_fail_overrides_hold_and_threshold_scales(tmp_path, monkeypatch):
    plan, _cal, current, _ = _full(tmp_path)
    row = current["flag_one_eval_gt"]
    raw = tmp_path / "known_override.json"
    payload = json.loads(Path(row["raw_file"]).read_text(encoding="utf-8"))
    payload["valid_count"] = 48
    payload["success_count"] = 38
    payload["survival_count"] = 45
    raw.write_text(json.dumps(payload), encoding="utf-8")
    altered = copy.deepcopy(current)
    altered["flag_one_eval_gt"].update(valid_count=48, success_count=38,
                                         survival_count=45, raw_file=str(raw), raw_sha256=_sha(raw))
    result = _judge(monkeypatch, plan, altered, previous=current)
    assert result["judgement"] == "FAIL"
    from foothold_s2.ex42_e1f_judge import _flag_window
    check = _flag_window(altered["flag_one_eval_gt"], plan, "flag_one_eval_gt")
    assert (check["success_min"], check["survival_min"], check["judgement"]) == (39, 45, "FAIL")
    payload["valid_count"] = 47
    payload["success_count"] = 47
    payload["survival_count"] = 47
    raw.write_text(json.dumps(payload), encoding="utf-8")
    altered["flag_one_eval_gt"].update(valid_count=47, success_count=47,
                                         survival_count=47, raw_sha256=_sha(raw))
    held = _flag_window(altered["flag_one_eval_gt"], plan, "flag_one_eval_gt")
    assert held["judgement"] == "HOLD" and held["reason"] == "깃발 유효 env 하한 미달"


def test_missing_calibration_and_plan_roles_hold_or_reject(tmp_path, monkeypatch):
    plan, _cal, current, _ = _full(tmp_path)
    plan["evaluation"]["flag_cells"]["calibration"] = {"path": None, "sha256": None}
    held = _judge(monkeypatch, plan, current, previous=current)
    assert held["judgement"] == "HOLD"
    altered = copy.deepcopy(plan)
    altered["evaluation"]["flag_cells"]["case_specs"]["flag_one_probe_prop_only"]["role"] = "judge"
    with pytest.raises(ValueError, match="identity or role"):
        contract(altered)


def test_p1_verify_rejects_a_forged_cell_verdict(tmp_path, monkeypatch):
    plan, _cal, current, _ = _full(tmp_path)
    result = _judge(monkeypatch, plan, current, previous=current)
    forged = copy.deepcopy(result)
    forged["stage_exit"]["items"]["flag_four_eval_pred_current"]["judgement"] = "FAIL"
    forged["stage_exit"]["judgement"] = forged["judgement"] = "FAIL"
    with pytest.raises(ValueError, match="verdict differs from raw"):
        FlagTwoWindowJudge().verify(forged, "FAIL", "PASS", plan=plan)


def test_five_repeat_raw_mutation_cannot_keep_a_pinned_calibration(tmp_path, monkeypatch):
    plan, _cal, current, roots = _full(tmp_path)
    source = roots[1] / "flag_four" / "flag_four_eval_gt.json"
    source.write_bytes(source.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="raw path or SHA"):
        _judge(monkeypatch, plan, current, previous=current)


def test_flag_target_must_match_the_fixed_terrain_origin(tmp_path):
    plan, _cal, _current, roots = _full(tmp_path)
    folder = roots[0] / "flag_one"
    npz = folder / "flag_one_eval_gt.npz"
    with np.load(npz, allow_pickle=False) as data:
        arrays = {key: data[key] for key in data.files}
    arrays["flags_w"][0, 0, 0] += .1
    np.savez_compressed(npz, **arrays)
    raw = folder / "flag_one_eval_gt.json"
    payload = json.loads(raw.read_text(encoding="utf-8"))
    payload["trace_sha256"] = _sha(npz)
    raw.write_text(json.dumps(payload), encoding="utf-8")
    receipt = folder / "flag_cells.json"
    indexed = json.loads(receipt.read_text(encoding="utf-8"))
    indexed["cases"]["flag_one_eval_gt"].update(trace_sha256=_sha(npz), raw_sha256=_sha(raw))
    receipt.write_text(json.dumps(indexed), encoding="utf-8")
    with pytest.raises(ValueError, match="target coordinates"):
        read_evidence(folder, plan=plan, plan_sha256=PLAN_SHA,
                      checkpoint_sha256=CHECKPOINT_SHA, seed=42, count="flag_one")


def test_calibration_cli_reads_all_five_raw_runs(tmp_path):
    from foothold_s2.eval.ex42_flag_calibrate import main

    plan = _plan()
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(yaml.safe_dump(plan), encoding="utf-8")
    checkpoint = tmp_path / "model_1000.pt"
    checkpoint.write_bytes(b"known E1 graduate")
    plan_sha, checkpoint_sha = _sha(plan_path), _sha(checkpoint)
    roots = []
    for i, seed in enumerate((42, 42, 43, 44, 45)):
        root = tmp_path / f"calibration_{i}"
        _write_round(root, plan, seed, plan_sha=plan_sha, checkpoint_sha=checkpoint_sha)
        roots.append(root)
    out = tmp_path / "calibration.json"
    argv = ["--plan", str(plan_path), "--checkpoint", str(checkpoint), "--out", str(out)]
    for root in roots:
        argv += ["--repeat-root", str(root)]
    row = main(argv)
    assert row == json.loads(out.read_text(encoding="utf-8"))
    assert len(row["repeat_receipts"]) == 5
    assert set(row["repeat_width"]) == set(plan["evaluation"]["flag_cells"]["judge_cases"])
    with pytest.raises(ValueError, match="five roots"):
        main(argv[:-2])
