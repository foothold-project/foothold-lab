"""Known-input C1 geometry and role checks. No Kit or GPU starts here."""
from pathlib import Path

import numpy as np
import pytest
import yaml

from foothold_s2.ex42_e1_wide import (_fixed_forward, _endpoint, contract, judge_cells,
                                      kit_commands, off_survival, CONTINUOUS)
from foothold_s2.ex42_e1_wide_plan import (widened_contract, write_evaluation_plan,
                                            validate_evaluation_scope)

ROOT = Path(__file__).resolve().parents[2]


def _plan():
    plan = yaml.safe_load((ROOT / "foothold_s2/curriculum/ex42-prep.yaml").read_text())
    plan["evaluation"]["e1_widened"] = widened_contract(plan)
    return plan


def _side(success=64):
    values = [1.0] * success + [0.0] * (64 - success)
    return {"R": float(np.median(values)), "mae_mps": 0.0, "survival": 64, "envs": 64,
            "per_env_R": values, "per_env_mae_mps": [0.0] * 64,
            "per_env_alive_end": [True] * 64}


def _cells(fixed_success=64, side_success=64):
    fixed = {f"L{level}": {mode: {"fwd1.0": {"success_count": fixed_success,
                                          "survival_count": 64, "valid_count": 64}}
                           for mode in ("eval_gt", "eval_pred", "probe_prop_only")}
             for level in (3, 6, 9)}
    endpoints = {mode: {case: _side(side_success) for case in ("side+0.8", "side-0.8")}
                 for mode in ("eval_gt", "eval_pred", "probe_prop_only")}
    return {"fixed": fixed, "endpoints": endpoints}


def test_c1_roles_are_from_plan_and_l9_stays_record_only():
    plan = _plan()
    assert contract(plan)["fixed_forward_roles"][9] == "record_only_pending_decision"
    cells = _cells(fixed_success=0)
    verdict = judge_cells(cells, plan, cap=5)
    assert verdict["items"]["wide_L3_fwd1.0/eval_gt"]["judgement"] == "FAIL"
    assert verdict["items"]["wide_L6_fwd1.0/eval_gt"]["role"] == "record_only"
    assert verdict["items"]["wide_L9_fwd1.0/eval_gt"]["role"] == "record_only"
    assert verdict["items"]["wide_L3_fwd1.0/probe_prop_only"]["role"] == "record_only"


def test_c1_missing_pred_or_endpoint_cannot_pass():
    plan = _plan()
    cells = _cells()
    assert judge_cells(cells, plan, cap=6)["judgement"] == "PASS"
    del cells["fixed"]["L6"]["eval_pred"]
    assert judge_cells(cells, plan, cap=6)["judgement"] == "HOLD"
    cells = _cells()
    cells["endpoints"]["eval_pred"]["side-0.8"] = _side(0)
    assert judge_cells(cells, plan, cap=6)["judgement"] == "FAIL"
    cells = _cells()
    cells["fixed"]["L3"]["eval_gt"]["fwd1.0"]["valid_count"] = 63
    assert judge_cells(cells, plan, cap=6)["judgement"] == "HOLD"


def test_c1_fixed_forward_uses_each_kind_timing_and_footprint_line(tmp_path):
    steps = 475
    kinds = [CONTINUOUS[i % len(CONTINUOUS)] for i in range(64)]
    x = np.ones((steps, 64), dtype=np.float32) * 3.0
    y = np.zeros_like(x)
    alive = np.ones((steps, 64), dtype=bool)
    # All robots cross on tick 300. The four 300-step kinds must remain failures;
    # the three 475-step kinds may finish their 25-tick settle window.
    x[300:] = 4.0
    path = tmp_path / "env_arrays_eval_gt_fwd1.0.npz"
    np.savez(path, root_x_local_m=x, root_y_local_m=y, alive=alive,
             kind=np.array(kinds), terrain_level=np.full(64, 3),
             terrain_col=np.arange(64) % 23, assignment_sha256="known-assignment", dt=.02,
             alive_end=alive[-1], alive_steps=alive.sum(0))
    rows = {(kind, 3): {"steps": 300 if i < 4 else 475, "dt": .02,
                        "hold_s": .5, "anchors": {"exit_x": 7.5,
                        "exit_bounds_y": [0., 8.]}, "origin_m": [4., 4., 0.]}
            for i, kind in enumerate(CONTINUOUS)}
    y[:] = 0  # local y=0 remains within the tile-wide [0,8] line.
    doc = {"env_arrays": {"eval_gt/fwd1.0": path.name},
           "fixed_terrain": {"assignment_sha256": "known-assignment"},
           "terrain_tiles": [{"env": i, "kind": kind, "level": 3, "column": i % 23}
                             for i, kind in enumerate(kinds)]}
    row = _fixed_forward(tmp_path, doc, "eval_gt", 3, rows)
    assert row["success_count"] == sum(kinds.count(kind) for kind in CONTINUOUS[4:])
    assert row["survival_count"] == 64
    assert row["by_kind"][CONTINUOUS[0]]["success"] == 0
    assert row["by_kind"][CONTINUOUS[4]]["success"] == kinds.count(CONTINUOUS[4])
    doc["terrain_tiles"][0]["column"] = 22
    with pytest.raises(ValueError, match="assignment differs"):
        _fixed_forward(tmp_path, doc, "eval_gt", 3, rows)


def test_c1_command_coverage_and_plan_roles_are_locked(monkeypatch):
    from foothold_s2 import ex42_e1_wide
    plan = _plan()
    monkeypatch.setattr(ex42_e1_wide, "machine_path", lambda _: Path("/tmp/cpu"), raising=False)
    # The command values are locked by the named suites, while roles come from plan.
    assert len(contract(plan)["endpoint_commands"]) == 8
    plan["evaluation"]["e1_widened"]["endpoint_roles"].pop("side-0.8")
    with pytest.raises(ValueError, match="contract differs"):
        contract(plan)


def test_c1_record_only_failures_do_not_block_judged_cells():
    cells = _cells()
    cells["fixed"]["L9"]["eval_gt"]["fwd1.0"]["success_count"] = 0
    cells["endpoints"]["eval_gt"]["spin+0.15"] = {"survival": 0}
    assert judge_cells(cells, _plan(), cap=9)["judgement"] == "PASS"


def test_c1_spin_endpoint_has_no_linear_projection(tmp_path):
    alive = np.ones((300, 64), dtype=bool)
    path = tmp_path / "env_arrays_eval_gt_spin+0.15.npz"
    np.savez(path, alive=alive, dt=.02)
    doc = {"env_arrays": {"eval_gt/spin+0.15": path.name},
           "commands": {"spin+0.15": [0., 0., .15]},
           "modes": {"eval_gt": {"spin+0.15": {"alive_envs_at_end": 64,
                        "per_env": [{"wz_abs_error_mean_alive_radps": .01,
                                     "command_xy_projection_integral_m": None} for _ in range(64)]}}}}
    row = _endpoint(tmp_path, doc, "eval_gt", "spin+0.15")
    assert row["linear_R_median"] is None and row["survival"] == 64
    doc["modes"]["eval_gt"]["spin+0.15"]["per_env"][0]["command_xy_projection_integral_m"] = 0.
    with pytest.raises(ValueError, match="endpoint per-env evidence"):
        _endpoint(tmp_path, doc, "eval_gt", "spin+0.15")


def test_c1_two_gpu_repeat_seeds_have_separate_kit_runtime(monkeypatch, tmp_path):
    import json
    import threading
    from types import SimpleNamespace
    from foothold_s2 import ex42_eval_once
    from foothold_s2 import ex42_e1_v2

    launched = []
    second_started = threading.Event()
    sleeps = []

    def low_command(_checkpoint, root, device, _cfg, *, eval_seed, **_kw):
        out = Path(root) / "e1_v2" / "L0"
        return [("e1_v2_L0", ["python", "-m", "fake", "--out", str(out),
                "--device", device, "--kit_args=--/UJITSO/datastore/localCachePath=/tmp/shared"])]

    def prepare(argv):
        Path(argv[argv.index("--out") + 1]).mkdir(parents=True)

    def child(argv, folder, *, env):
        device = argv[argv.index("--device") + 1]
        out = Path(argv[argv.index("--out") + 1])
        launched.append((device, env, argv))
        if device == "cuda:1":
            second_started.set()
        else:
            assert second_started.wait(timeout=2), "the second GPU never started"
        out.joinpath("map_modes.json").write_text(json.dumps({"run_identity": {
            "device": device, "gpu_uuid": "GPU-" + device[-1] * 32}}))
        return {"state": "done", "rc": 0}

    monkeypatch.setattr(ex42_eval_once, "e1_v2_commands", low_command)
    monkeypatch.setattr(ex42_eval_once, "commands", lambda *_args, **_kw: [])
    monkeypatch.setattr(ex42_e1_v2, "measure_cells", lambda *_args: {"sources": {}})
    got = ex42_eval_once.run_e1_repeat_seeds(
        tmp_path / "model_500.pt", tmp_path, ["cuda:0", "cuda:1"], {},
        seeds=[7, 13], mesh_dir=tmp_path, policy_path=tmp_path / "plan.yaml",
        expected_sha256="a" * 64,
        physical={"cuda:0": {"gpu_uuid": "GPU-" + "0" * 32},
                  "cuda:1": {"gpu_uuid": "GPU-" + "1" * 32}},
        process=SimpleNamespace(prepare_phase_output=prepare, hidden_child=child),
        env={}, sleep=lambda seconds: sleeps.append(seconds))
    assert set(got) == {"e1_v2_L0@cuda:0", "e1_v2_L0@cuda:1"}
    assert sleeps == [30]
    assert {d for d, _, _ in launched} == {"cuda:0", "cuda:1"}
    assert len({e["TMPDIR"] for _, e, _ in launched}) == 2
    assert all(e["TMPDIR"] == e["TEMP"] == e["TMP"] for _, e, _ in launched)
    assert len({next(a for a in argv if a.startswith("--kit_args=")) for _, _, argv in launched}) == 2


def test_c1_kit_commands_match_the_real_eval_parser_and_keep_mode_coverage(tmp_path):
    source = (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text()
    for flag in ("--command-suite", "--fixed-terrain", "--fixed-level", "--mesh-dir",
                 "--modes", "--steps", "--eval-seed", "--ex42-evaluation-plan"):
        assert f'parser.add_argument("{flag}"' in source
    assert '"e1_wide_fixed", "e1_wide_endpoint"' in source
    rows = kit_commands(tmp_path / "model_250.pt", tmp_path / "out", "cuda:1",
                        task="FootholdS2-Go2-S2-SB-v0", plan_path=tmp_path / "plan.yaml",
                        plan=_plan(), mesh_dir=tmp_path / "mesh", seed=42)
    assert [name for name, _ in rows] == ["wide_L3", "wide_L6", "wide_L9", "wide_endpoints"]
    for name, argv in rows:
        assert argv[1:3] == ["-m", "foothold_s2.eval.eval_map_modes"]
        assert argv[argv.index("--modes") + 1] == "eval_gt,eval_pred,probe_prop_only"
        assert argv[argv.index("--command-suite") + 1] == (
            "e1_wide_endpoint" if name == "wide_endpoints" else "e1_wide_fixed")
        assert argv[argv.index("--steps") + 1] == (
            "300" if name == "wide_endpoints" else "475")


def test_c1_derived_evaluation_plan_keeps_training_bytes_and_rejects_other_changes(tmp_path):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    source = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
    source_sha = EX42Plan.load(source).sha256
    destination = tmp_path / "separate" / source.name
    policy = write_evaluation_plan(source, destination, source_sha)
    assert EX42Plan.load(source).sha256 == source_sha
    assert policy.document["evaluation"]["e1_widened"]["off_survival"]["survival_min"] == 60
    assert policy.sha256 != source_sha
    with pytest.raises(ValueError, match="SHA or evaluation scope"):
        write_evaluation_plan(source, tmp_path / "wrong" / source.name, "0" * 64)
    with pytest.raises(ValueError, match="fresh output"):
        write_evaluation_plan(source, destination, source_sha)
    original = destination.read_text()
    destination.write_text(original.replace("window_episodes: 64", "window_episodes: 63", 1))
    with pytest.raises(ValueError, match="differs"):
        validate_evaluation_scope(source, destination)


def test_c1_off_survival_two_boundaries_and_missing_valid_envs():
    plan = _plan()

    def score(survived, valid=64):
        cfg = plan["evaluation"]["e1_widened"]["off_survival"]
        return {"conditions": {"envs": valid},
                "map64": {"probe_prop_only": {case: {"alive_at_end": survived}
                                              for case in cfg["map64_commands"]}},
                "e1_v2_cells": {"low": {f"L{level}": {"probe_prop_only": {
                    case: {"envs": valid, "survival": survived} for case in cfg["low_forward_commands"]}}
                                              for level in cfg["low_forward_levels"]}}}

    assert off_survival(score(64), plan, score(64))["judgement"] == "PASS"
    assert off_survival(score(59), plan, score(64))["judgement"] == "PASS"
    assert off_survival(score(64), plan, score(59))["judgement"] == "PASS"
    assert off_survival(score(59), plan, score(59))["judgement"] == "FAIL"
    assert off_survival(score(64, 63), plan, score(64))["judgement"] == "HOLD"
    assert off_survival(score(64), plan, None)["judgement"] == "HOLD"
