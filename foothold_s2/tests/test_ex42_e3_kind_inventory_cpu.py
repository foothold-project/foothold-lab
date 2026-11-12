"""Known-input checks for the CG E3 five START kinds and opened level cells."""
from pathlib import Path

import pytest
import yaml

from foothold_s2.eval.ex42_stage_kind_bundle import e3_target_inventory, read_e3_window
from foothold_s2 import ex42_eval_once
from foothold_s2.ex42_stage_judges import adapter_for


PLAN = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml"


def test_e3_inventory_has_five_start_kinds_and_only_opened_representative_levels():
    plan = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    result = e3_target_inventory(plan, {"A/stepping_stones_low": 6, "B/rough": 3})
    assert len(result["targets"]) == 20
    assert {row["kind"] for row in result["targets"] if row["family"] == "A"
            and row["level"] == 5} == {
                "stepping_stones_low", "stepping_stones_high", "balance_beams",
                "stepping_beams", "gaps"}
    assert result["opened_cells"] == [
        {"family": "A", "kind": "stepping_stones_low", "level": n, "flag_source": "kind_flag_four"} for n in (0, 5, 6)
    ] + [{"family": "B", "kind": "rough", "level": n, "flag_source": "kind_flag_four"} for n in (0, 3)]
    assert len(result["missing_targets"]) == 18


def test_e3_inventory_rejects_an_unapproved_kind_and_a_missing_start_kind():
    plan = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="outside approved"):
        e3_target_inventory(plan, {"B/beam": 0})
    plan["evaluation"]["e3_kind_exit"]["start_kinds"].remove("gaps")
    with pytest.raises(ValueError, match="target list"):
        e3_target_inventory(plan, {})


def test_e3_child_commands_use_actual_kind_and_both_raw_subcells(monkeypatch):
    plan = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    assert adapter_for(plan, "E3").name == "kind_two_window_e3"
    monkeypatch.setattr(ex42_eval_once, "machine_path", lambda name: Path("/tmp/python") if name == "conda_python" else Path("/tmp/cache"))
    cells = e3_target_inventory(plan, {"A/stepping_stones_low": 6})["opened_cells"]
    commands = ex42_eval_once.e3_kind_kit_commands(
        "/tmp/model_250.pt", "/tmp/out", "cuda:1", task="task",
        plan_path="/tmp/plan", mesh_dir="/tmp/mesh", mesh_sha256="a" * 64,
        seed=42, window_index=1, cells=cells)
    assert len(commands) == 6
    assert all(argv[argv.index("--device") + 1] == "cuda:1" for _, argv in commands)
    assert all("--kind-level" in argv or argv[argv.index("--level") + 1] in {"0", "5", "6"}
               for _, argv in commands)
    assert all("--execute" in argv for name, argv in commands if name.endswith("_forward"))
    assert all(argv[argv.index("--count") + 1] == "flag_four"
               for name, argv in commands if name.endswith("_flag_four"))


def test_e3_raw_window_requires_exact_opened_cell_set(monkeypatch, tmp_path):
    import foothold_s2.eval.ex42_stage_kind_bundle as module
    plan = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    inventory = e3_target_inventory(plan, {"B/rough": 3})
    folder = tmp_path / "kind_cells_e3"
    (folder / "B" / "rough" / "L0").mkdir(parents=True)
    calls = []
    monkeypatch.setattr(module, "read_stage_kind_bundle", lambda path, **kwargs: calls.append(path) or
                        {"eval_gt": {"judgement": "PASS"}})
    with pytest.raises(ValueError, match="coverage"):
        read_e3_window(folder, inventory=inventory, plan=plan,
                       plan_sha256="a" * 64, mesh={}, checkpoint_sha256="b" * 64, seed=42)
    (folder / "B" / "rough" / "L3").mkdir()
    result = read_e3_window(folder, inventory=inventory, plan=plan,
                            plan_sha256="a" * 64, mesh={}, checkpoint_sha256="b" * 64, seed=42)
    assert len(result) == len(calls) == 2
    (folder / "B" / "rough" / "L4").mkdir()
    with pytest.raises(ValueError, match="coverage"):
        read_e3_window(folder, inventory=inventory, plan=plan,
                       plan_sha256="a" * 64, mesh={}, checkpoint_sha256="b" * 64, seed=42)


def test_e3_child_failure_is_a_scored_hold_and_tampered_marker_is_rejected(tmp_path):
    import json
    from foothold_s2.ex42_e3_judge import recount

    evaluation = tmp_path / "m250"
    folder = evaluation / "kind_cells_e3"
    folder.mkdir(parents=True)
    marker = folder / "child_failures.json"
    row = {"format": "foothold-ex42-e3-child-failures/1",
           "checkpoint_sha256": "a" * 64, "reason": "missing Kit trace"}
    marker.write_text(json.dumps(row), encoding="utf-8")
    score = {"stage_id": "E3", "checkpoint_sha256": "a" * 64}
    result = recount(score, plan={}, evaluation=evaluation, mesh={"mesh_sha256": "b" * 64})
    assert result["judgement"] == "HOLD" and result["child_failure"]["sha256"]
    row["checkpoint_sha256"] = "c" * 64
    marker.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError, match="marker differs"):
        recount(score, plan={}, evaluation=evaluation, mesh={"mesh_sha256": "b" * 64})


def test_e3_missing_retained_children_stay_hold_without_inventing_raw(tmp_path):
    from foothold_s2.ex42_e3_judge import _retained

    score = {}
    assert _retained(score, evaluation=tmp_path, plan={}, plan_sha256="a" * 64,
                     checkpoint_sha256="b" * 64, seed=42) == ["d44", "flag_one", "flag_four"]
    assert "d44_cells" not in score and "flag_cells" not in score


def test_continuous_kinds_take_the_global_flag_source_and_get_no_kind_flag_child(monkeypatch):
    plan = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    family = plan["evaluation"]["e3_kind_exit"]["continuous_family"]
    continuous = list(next(row for row in plan["stages"] if row["id"] == "E0")["terrain"]["kind_task"]["continuous"])
    opened = {f"{family}/{kind}": 9 for kind in continuous}
    opened["B/rough"] = 3
    cells = e3_target_inventory(plan, opened)["opened_cells"]
    shared = [cell for cell in cells if cell["flag_source"] == "global_flag_cells"]
    assert len(shared) == 21 and {cell["kind"] for cell in shared} == set(continuous)      # seven kinds x L0, L5, cap
    assert [cell["flag_source"] for cell in cells if cell["family"] == "B"] == ["kind_flag_four"] * 2
    monkeypatch.setattr(ex42_eval_once, "machine_path",
                        lambda name: Path("/tmp/python") if name == "conda_python" else Path("/tmp/cache"))
    names = [name for name, _ in ex42_eval_once.e3_kind_kit_commands(
        "/tmp/model_250.pt", "/tmp/out", "cuda:1", task="task", plan_path="/tmp/plan", mesh_dir="/tmp/mesh",
        mesh_sha256="a" * 64, seed=42, window_index=1, cells=cells)]
    assert sum(name.endswith("_forward") for name in names) == len(cells) == 23
    assert [name for name in names if name.endswith("_flag_four")] == ["e3_B_rough_L0_flag_four", "e3_B_rough_L3_flag_four"]


def test_e3_recount_holds_without_the_global_flag_receipt_and_names_the_sources(monkeypatch, tmp_path):
    import foothold_s2.ex42_e3_judge as judge
    import foothold_s2.ex42_learned_cells_evidence as evidence

    plan = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    evaluation = tmp_path / "m250"
    (evaluation / "kind_cells_e3").mkdir(parents=True)
    opened = {"A/pyramid_stairs": 5, "B/rough": 3}
    monkeypatch.setattr(evidence, "read_stage_exposure",
                        lambda *_args, **_kwargs: {"opened_kinds": opened, "mesh_sha256": "b" * 64, "receipts": []})
    score = {"stage_id": "E3", "checkpoint_sha256": "a" * 64, "checkpoint": str(tmp_path / "model_250.pt"),
             "execution_plan_sha256": "c" * 64, "maintenance_source_sha256": "d" * 64, "conditions": {"eval_seed": 42}}
    mesh = {"mesh_sha256": "b" * 64, "column_family": ["A", "B"], "columns": ["pyramid_stairs", "rough"]}
    monkeypatch.setattr(judge, "read_e3_window", lambda *_args, **_kwargs: pytest.fail("no raw window may be read"))
    held = judge.recount(score, plan=plan, evaluation=evaluation, mesh=mesh)
    assert held["judgement"] == "HOLD" and "전역 깃발" in held["reason"] and "cells" not in held
    receipt = evaluation / "flag_cells" / "flag_four"
    receipt.mkdir(parents=True)
    (receipt / "flag_cells.json").write_text("{}", encoding="utf-8")
    seen = {}
    monkeypatch.setattr(judge, "read_e3_window",
                        lambda _folder, **kwargs: seen.update(kwargs) or
                        {"A/pyramid_stairs/L0": {"eval_gt": {"judgement": "PASS"}, "eval_pred": {"judgement": "PASS"}}})
    result = judge.recount(score, plan=plan, evaluation=evaluation, mesh=mesh)
    assert seen["global_flag_dir"] == receipt and result["flag_sources"] == ["global_flag_cells", "kind_flag_four"]


def _recount_setup(monkeypatch, tmp_path, *, opened, exposure_mesh="b" * 64, exposure=True):
    import foothold_s2.ex42_e3_judge as judge
    import foothold_s2.ex42_learned_cells_evidence as evidence

    plan = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    evaluation = tmp_path / "m250"
    (evaluation / "kind_cells_e3").mkdir(parents=True)
    monkeypatch.setattr(evidence, "read_stage_exposure",
                        lambda *_a, **_k: {"opened_kinds": opened, "mesh_sha256": exposure_mesh, "receipts": []}
                        if exposure else None)
    score = {"stage_id": "E3", "checkpoint_sha256": "a" * 64, "checkpoint": str(tmp_path / "model_250.pt"),
             "execution_plan_sha256": "c" * 64, "maintenance_source_sha256": "d" * 64, "conditions": {"eval_seed": 42}}
    mesh = {"mesh_sha256": "b" * 64, "column_family": ["B"], "columns": ["rough"]}
    return judge, plan, evaluation, score, mesh


def test_e3_recount_never_passes_while_targets_are_unopened(monkeypatch, tmp_path):
    judge, plan, evaluation, score, mesh = _recount_setup(monkeypatch, tmp_path, opened={"B/rough": 3})
    passing = {"eval_gt": {"judgement": "PASS"}, "eval_pred": {"judgement": "PASS"}}
    monkeypatch.setattr(judge, "read_e3_window", lambda *_a, **_k: {"B/rough/L0": passing, "B/rough/L3": passing})
    result = judge.recount(score, plan=plan, evaluation=evaluation, mesh=mesh)
    assert result["inventory"]["missing_targets"] and result["judgement"] == "HOLD"


def test_e3_recount_holds_without_a_training_exposure_receipt_and_reads_no_raw(monkeypatch, tmp_path):
    judge, plan, evaluation, score, mesh = _recount_setup(monkeypatch, tmp_path, opened={}, exposure=False)
    monkeypatch.setattr(judge, "read_e3_window", lambda *_a, **_k: pytest.fail("raw window must not be read"))
    result = judge.recount(score, plan=plan, evaluation=evaluation, mesh=mesh)
    assert result["judgement"] == "HOLD" and "노출 영수증" in result["reason"] and "cells" not in result


def test_e3_recount_refuses_a_training_mesh_that_differs_from_the_evaluation_mesh(monkeypatch, tmp_path):
    judge, plan, evaluation, score, mesh = _recount_setup(monkeypatch, tmp_path, opened={"B/rough": 3},
                                                          exposure_mesh="e" * 64)
    monkeypatch.setattr(judge, "read_e3_window", lambda *_a, **_k: pytest.fail("raw window must not be read"))
    with pytest.raises(ValueError, match="training and evaluation mesh differ"):
        judge.recount(score, plan=plan, evaluation=evaluation, mesh=mesh)


def _share_receipt(folder, plan, *, iteration=250, rank=0, world_size=2, flag=0.15, continuous=(850, 150),
                   stage_id="E3", plan_sha="p" * 64):
    import json
    boundary = next(r for r in plan["stages"] if r["id"] == "E3")["command_allocation_boundary"]["shares"]
    shares = dict(boundary) if flag == 0.15 else dict(next(r for r in plan["stages"] if r["id"] == "E3")["shares"])
    total = sum(continuous)
    doc = {"format": "ex42-command-shares/1", "stage_id": stage_id, "iteration": iteration, "rank": rank,
           "world_size": world_size, "plan_sha256": plan_sha, "configured": {"shares": shares},
           "count_origin_update": 0,
           "cumulative": {"reset_modes": {
               "continuous": {"total": total, "counts": {"free": continuous[0], "flag": continuous[1]}},
               "all": {"total": total * 2, "counts": {"free": continuous[0] * 2, "flag": continuous[1]}}}}}
    (folder / f"command_shares_{iteration}_rank{rank}.json").write_text(json.dumps(doc), encoding="utf-8")


def test_flag_share_consumes_both_rank_receipts_after_the_c_boundary(tmp_path):
    from foothold_s2.ex42_e3_judge import flag_share

    plan = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    model = tmp_path / "model_250.pt"
    kwargs = dict(plan=plan, plan_sha256="p" * 64)
    assert flag_share(model, **kwargs)["judgement"] == "HOLD"                 # no receipt, nothing invented
    _share_receipt(tmp_path, plan, rank=0)
    assert flag_share(model, **kwargs)["judgement"] == "HOLD"                 # one rank is not both ranks
    _share_receipt(tmp_path, plan, rank=1)
    item = flag_share(model, **kwargs)
    assert item["judgement"] == "PASS" and item["iteration"] == 250 and len(item["ranks"]) == 2
    assert item["ranks"][0]["all_resets"] == 2000 and item["expected"] == 0.15
    (tmp_path / "command_shares_250_rank1.json").unlink()
    _share_receipt(tmp_path, plan, rank=1, continuous=(700, 300))              # 30 % flag: far outside 4 sigma
    assert flag_share(model, **kwargs)["judgement"] == "HOLD"


def test_flag_share_ignores_receipts_before_the_boundary_other_stage_plan_or_after_the_checkpoint(tmp_path):
    from foothold_s2.ex42_e3_judge import flag_share

    plan = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    model = tmp_path / "model_250.pt"
    for rank in (0, 1):
        _share_receipt(tmp_path, plan, rank=rank, flag=0.10, continuous=(900, 100))    # E3 start vector, flag 0.10
    _share_receipt(tmp_path, plan, rank=0, iteration=500)
    _share_receipt(tmp_path, plan, rank=1, iteration=500)                              # later than model_250
    assert flag_share(model, plan=plan, plan_sha256="p" * 64)["judgement"] == "HOLD"
    for rank in (0, 1):
        _share_receipt(tmp_path, plan, rank=rank, iteration=100, stage_id="E2")
    assert flag_share(model, plan=plan, plan_sha256="p" * 64)["judgement"] == "HOLD"
    for rank in (0, 1):
        _share_receipt(tmp_path, plan, rank=rank, iteration=200)
    assert flag_share(model, plan=plan, plan_sha256="x" * 64)["judgement"] == "HOLD"   # another plan
    assert flag_share(model, plan=plan, plan_sha256="p" * 64)["iteration"] == 200
