"""E1 exit option: stop-restart landing cases recorded only, rescored on CPU from the Kit traces.

The plan here is the real curriculum file. Only the Kit artifacts (traces, receipts) and the
map/stand/axis scorer are stand-ins, because those need Isaac output.
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pytest
import yaml

from foothold_s2 import ex42_d44_reissue as reissue
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.eval import ex42_d44_cells

CURRICULUM = Path(__file__).resolve().parents[1] / "curriculum"
STOP = ("stop_restart_eval_gt", "stop_restart_eval_pred")
TURNS = ["turn_left_eval_gt", "turn_left_eval_pred", "turn_right_eval_gt", "turn_right_eval_pred"]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _put(path, row):
    path.write_text(json.dumps(row), encoding="utf-8")


def _landing(document):
    return document["evaluation"]["paper_cells"]["stairs_landing"]


def _real_plan(tmp_path):
    folder = tmp_path / "curriculum"
    shutil.copytree(CURRICULUM, folder, ignore=shutil.ignore_patterns("*.py", "__pycache__"))
    return EX42Plan.load(folder / "ex42-prep.yaml")


def test_contract_lets_a_map_on_case_be_recorded_but_never_a_map_off_case_judge():
    document = yaml.safe_load((CURRICULUM / "ex42-prep.yaml").read_text(encoding="utf-8"))
    assert list(ex42_d44_cells.contract(document)["judge_cases"]) == [*TURNS, *STOP]
    landing = _landing(document)
    recorded = copy.deepcopy(document)
    row = _landing(recorded)
    row["judge_cases"] = list(TURNS)
    row["record_cases"] = [*landing["record_cases"], *STOP]
    for name in STOP:
        row["case_specs"][name]["role"] = "record_only"
    settings = ex42_d44_cells.contract(recorded)
    assert list(settings["judge_cases"]) == TURNS and set(STOP) <= set(settings["record_cases"])
    # the list and the per-case role must still agree
    stale = copy.deepcopy(recorded)
    _landing(stale)["case_specs"][STOP[0]]["role"] = "judge"
    with pytest.raises(ValueError, match="invalid task, mode or role"):
        ex42_d44_cells.contract(stale)
    # a map-off case as a judge stays refused
    blind = copy.deepcopy(document)
    row = _landing(blind)
    name = "stop_restart_probe_prop_only"
    row["judge_cases"].append(name)
    row["record_cases"].remove(name)
    row["case_specs"][name]["role"] = "judge"
    with pytest.raises(ValueError, match="map mode and judgment role differ"):
        ex42_d44_cells.contract(blind)
    # an empty judge list is not a contract
    empty = copy.deepcopy(recorded)
    row = _landing(empty)
    row["record_cases"] += row["judge_cases"]
    for name in row["judge_cases"]:
        row["case_specs"][name]["role"] = "record_only"
    row["judge_cases"] = []
    with pytest.raises(ValueError, match="case list or timing contract missing"):
        ex42_d44_cells.contract(empty)


def test_derived_plan_differs_from_the_run_plan_only_in_the_two_landing_roles(tmp_path):
    plan = _real_plan(tmp_path)
    policy = reissue.write_demoted_plan(plan, tmp_path / "out" / "evaluation_plan" / "ex42-prep.yaml", STOP)
    before = plan.path.read_text(encoding="utf-8").splitlines()
    after = policy.path.read_text(encoding="utf-8").splitlines()
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert len(before) == len(after) and len(changed) == 4
    assert all("judge_cases" in before[i] or "record_cases" in before[i] or "stop_restart_eval_" in before[i]
               for i in changed)
    assert policy.sha256 != plan.sha256
    assert reissue.demoted_cases(plan, policy) == STOP
    assert _landing(policy.document)["judge_cases"] == TURNS
    # every data file the plan refers to travels with it, so the policy loads on its own
    assert {p.name for p in policy.path.parent.iterdir()} == {
        p.name for p in plan.path.parent.iterdir() if p.suffix in (".yaml", ".yml", ".json")}


@pytest.mark.parametrize("record, message", [
    ((), "must name distinct current landing judge"),
    (("stop_restart_eval_gt", "stop_restart_eval_gt"), "must name distinct current landing judge"),
    (("stop_restart_probe_prop_only",), "must name distinct current landing judge"),
    (("unknown_case",), "must name distinct current landing judge"),
    (tuple([*TURNS, *STOP]), "case list or timing contract missing"),
])
def test_record_request_must_name_current_judges_and_leave_one(tmp_path, record, message):
    plan = _real_plan(tmp_path)
    with pytest.raises(ValueError, match=message):
        reissue.write_demoted_plan(plan, tmp_path / "out" / "p" / "ex42-prep.yaml", record)


def test_evaluation_plan_with_any_other_difference_is_refused(tmp_path):
    plan = _real_plan(tmp_path)
    policy = reissue.write_demoted_plan(plan, tmp_path / "a" / "ex42-prep.yaml", STOP)
    with pytest.raises(ValueError, match="only move landing judge cases"):
        reissue.demoted_cases(plan, plan)                       # nothing moved
    with pytest.raises(ValueError, match="only move landing judge cases"):
        reissue.demoted_cases(policy, plan)                     # a record promoted to judge
    text = policy.path.read_text(encoding="utf-8")
    for old, new in (("stop_hold_s: 1.0", "stop_hold_s: 0.9"), ("valid_min: 48", "valid_min: 40"),
                     ("interval_updates: 250", "interval_updates: 500")):
        assert old in text
        policy.path.write_text(text.replace(old, new, 1), encoding="utf-8")
        with pytest.raises(ValueError, match="outside landing case roles"):
            reissue.demoted_cases(plan, EX42Plan.load(policy.path))
    policy.path.write_text(text, encoding="utf-8")
    assert reissue.demoted_cases(plan, EX42Plan.load(policy.path)) == STOP


def _boundary(run, iteration, plan, *, kit_plan_sha256=None):
    source = run / "eval" / "scores" / f"m{iteration}"
    d44 = source / "d44"
    d44.mkdir(parents=True)
    checkpoint = run / f"model_{iteration}.pt"
    checkpoint.write_bytes(f"checkpoint {iteration}".encode())
    for name in reissue.OTHER_EVIDENCE:
        (source / name).mkdir()
    settings = ex42_d44_cells.contract(plan.document)
    indexed = {}
    for case_id, spec in settings["case_specs"].items():
        trace = d44 / f"{case_id}.npz"
        count = 130 if spec["task"] == "stop_restart" else 70
        phases = np.ones((count, 64), dtype=np.int16)
        phases[:10] = 0
        commands = np.zeros((count, 64, 3), dtype=np.float32)
        if spec["task"] == "stop_restart":
            phases[50:70] = 2
            phases[70:] = 3
            commands[70:, :, 0] = 1.0
        np.savez_compressed(
            trace, root_pos_w=np.zeros((count, 64, 3), dtype=np.float32),
            root_quat_w=np.tile(np.array([1, 0, 0, 0], dtype=np.float32), (count, 64, 1)),
            foot_pos_w=np.zeros((count, 64, 4, 3), dtype=np.float32),
            contact=np.zeros((count, 64, 4), dtype=bool), alive=np.ones((count, 64), dtype=bool),
            body_vel_b=np.zeros((count, 64, 3), dtype=np.float32), phase_id=phases, cmd_post=commands,
            top_latched_at=np.full(64, -1, dtype=np.int32),
            trace_format=np.asarray(ex42_d44_cells.TRACE_FORMAT),
            tile_offset_w=np.zeros((64, 3), dtype=np.float32), dt=np.asarray(.1))
        row = {"case_id": case_id, **spec, "trace_file": str(trace), "trace_sha256": _sha(trace)}
        _put(d44 / f"{case_id}.json", row)
        indexed[case_id] = {"raw_sha256": _sha(d44 / f"{case_id}.json"), "trace_sha256": _sha(trace)}
    kit_plan = plan.sha256 if kit_plan_sha256 is None else kit_plan_sha256
    _put(d44 / "d44_cells.json", {
        "format": ex42_d44_cells.RECEIPT_FORMAT, "state": "done", "checkpoint_sha256": _sha(checkpoint),
        "source_mesh_sha256": settings["source_mesh_sha256"], "plan_sha256": kit_plan, "seed": 42,
        "envs": 64, "cases": indexed})
    _put(source / "eval_receipt.json", {
        "state": "done", "checkpoint": str(checkpoint), "checkpoint_sha256": _sha(checkpoint), "eval_seed": 42,
        "evaluation_plan": {"path": str(plan.path), "sha256": kit_plan},
        "steps": {"d44": {"state": "done"}}, "ex42_mesh": {"mesh_sha256": "b" * 64}})


def _run(tmp_path, monkeypatch, iterations=(250, 500), **kit):
    plan = _real_plan(tmp_path)
    run = tmp_path / "run"
    for iteration in iterations:
        _boundary(run, iteration, plan, **kit)
    anchors = {"landing_center": [4., 4., 1.44], "landing_bounds_xy": [3.4, 4.6, 3.4, 4.6],
               "stop_band_x": [1.6, 1.9]}
    tile = ({"mesh_sha256": _landing(plan.document)["source_mesh_sha256"]}, {"anchors_local_m": anchors})
    from foothold_s2.eval import ex42_eval_tile_mesh
    monkeypatch.setattr(reissue, "source_tile", lambda _: tile)
    monkeypatch.setattr(ex42_eval_tile_mesh, "source_tile", lambda _: tile)
    monkeypatch.setattr(reissue, "manifest_checkpoint_sha",
                        lambda path: (_sha(path), int(Path(path).stem.split("_")[1])))
    seen = []

    def measure(checkpoint, output, **kwargs):
        seen.append((Path(output).name, Path(kwargs["evaluation_plan_path"])))
        return {"checkpoint_sha256": _sha(checkpoint), "judgement": "PASS"}

    def p1(score, *, iteration, plan_path, evaluation_plan_path, **_):
        assert Path(plan_path) == plan.path                      # the gate stays bound to the run plan
        return {"judgment": "HOLD" if iteration == iterations[0] else "PASS",
                "evaluation_plan": {"path": str(evaluation_plan_path), "sha256": _sha(evaluation_plan_path)}}

    monkeypatch.setattr(reissue, "measure", measure)
    monkeypatch.setattr(reissue, "p1_score_from_measure", p1)
    return run, plan, seen


def _windows(run, plan, out, **kwargs):
    kwargs.setdefault("record", STOP)
    kwargs.setdefault("iterations", (250, 500))
    return reissue.reissue_windows(run, out, p1_plan=plan.path,
                                   approvals=plan.path.parent / "ex42-approvals.yaml", **kwargs)


def test_two_windows_are_rescored_from_the_original_traces_under_the_derived_plan(tmp_path, monkeypatch):
    run, plan, seen = _run(tmp_path, monkeypatch)
    before = {p: _sha(p) for p in run.rglob("*") if p.is_file()}
    out = tmp_path / "derived"
    receipt = _windows(run, plan, out)
    policy = EX42Plan.load(out / "evaluation_plan" / "ex42-prep.yaml")
    assert receipt["state"] == "complete" and receipt["judgment"] == "PASS"
    assert receipt["plan_sha256"] == plan.sha256 and receipt["evaluation_plan"]["sha256"] == policy.sha256
    assert receipt["recorded_cases"] == list(STOP)
    assert [row["iteration"] for row in receipt["completed"]] == [250, 500]
    assert receipt["p1_score"] == str(out / "m500" / "p1_score.json")
    assert seen == [("m250", policy.path), ("m500", policy.path)]
    assert reissue._read(out / "role_reissue_receipt.json") == receipt
    for iteration in (250, 500):
        folder = out / f"m{iteration}"
        kit = reissue._read(folder / "d44" / "d44_cells.json")
        assert kit["plan_sha256"] == policy.sha256
        assert kit["cpu_reissue"]["original_kit_plan_sha256"] == plan.sha256
        assert kit["cpu_reissue"]["original_kit_receipt_sha256"] == _sha(
            run / "eval" / "scores" / f"m{iteration}" / "d44" / "d44_cells.json")
        for name in STOP:
            assert reissue._read(folder / "d44" / f"{name}.json")["role"] == "record_only"
            assert (folder / "d44" / f"{name}.npz").resolve() == (
                run / "eval" / "scores" / f"m{iteration}" / "d44" / f"{name}.npz").resolve()
        judged = ex42_d44_cells.read_evidence(
            folder / "d44", plan=policy.document, plan_sha256=policy.sha256,
            checkpoint_sha256=_sha(run / f"model_{iteration}.pt"), seed=42)
        assert list(judged) == TURNS                             # the judge sees four cells, not six
        with pytest.raises(ValueError, match="conditions or coverage differ"):
            ex42_d44_cells.read_evidence(                        # and the derived folder is not run-plan evidence
                folder / "d44", plan=plan.document, plan_sha256=plan.sha256,
                checkpoint_sha256=_sha(run / f"model_{iteration}.pt"), seed=42)
        assert reissue._read(folder / "eval_receipt.json")["evaluation_plan"]["sha256"] == policy.sha256
    assert {p: _sha(p) for p in run.rglob("*") if p.is_file()} == before      # the live run is untouched


def test_window_reissue_refusals_leave_no_output(tmp_path, monkeypatch):
    run, plan, _ = _run(tmp_path, monkeypatch)
    out = tmp_path / "refused"
    for kwargs, message in (
            ({"iterations": (250, 750)}, "consecutive boundaries"),
            ({"iterations": (500, 250)}, "consecutive boundaries"),
            ({"iterations": (100, 350)}, "consecutive boundaries"),
            ({"iterations": ()}, "consecutive boundaries"),
            ({"iterations": (500, 750)}, "No such file|m750"),
            ({"expected_scorer_sha256": "0" * 64}, "scorer SHA differs"),
            ({"record": ("turn_left_probe_prop_only",)}, "must name distinct current landing judge")):
        with pytest.raises((ValueError, OSError), match=message):
            _windows(run, plan, out, **kwargs)
        assert not out.exists()
    with pytest.raises(ValueError, match="outside the live run"):
        _windows(run, plan, run / "eval" / "inside")
    (tmp_path / "taken").mkdir()
    with pytest.raises(ValueError, match="fresh output root"):
        _windows(run, plan, tmp_path / "taken")
    trace = run / "eval" / "scores" / "m500" / "d44" / "turn_left_eval_gt.npz"
    trace.write_bytes(trace.read_bytes() + b"x")
    with pytest.raises(ValueError, match="raw SHA"):
        _windows(run, plan, out)
    assert not out.exists()


def test_originals_must_be_kit_evidence_of_the_run_plan(tmp_path, monkeypatch):
    run, plan, _ = _run(tmp_path, monkeypatch, kit_plan_sha256="c" * 64)
    with pytest.raises(ValueError, match="original Kit or P1 identity incomplete"):
        _windows(run, plan, tmp_path / "other-plan")
    assert not (tmp_path / "other-plan").exists()


def test_command_line_takes_exactly_one_of_plan_and_record_cases(tmp_path, monkeypatch, capsys):
    run, plan, _ = _run(tmp_path, monkeypatch)
    scorer = _sha(Path(ex42_d44_cells.__file__))
    common = ["--run", str(run), "--p1-plan", str(plan.path),
              "--approvals", str(plan.path.parent / "ex42-approvals.yaml"),
              "--expected-scorer-sha256", scorer, "--iterations", "250,500"]
    for extra in ([], ["--record-cases", ",".join(STOP), "--evaluation-plan", str(plan.path)]):
        with pytest.raises(SystemExit) as stop:
            reissue.main([*common, "--out", str(tmp_path / "cli-bad"), *extra])
        assert stop.value.code == 5 and "exactly one" in capsys.readouterr().err
        assert not (tmp_path / "cli-bad").exists()
    assert reissue.main([*common, "--out", str(tmp_path / "cli"), "--record-cases", ",".join(STOP)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["judgment"] == "PASS" and printed["recorded_cases"] == list(STOP)
