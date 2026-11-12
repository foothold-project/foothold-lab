"""E4 / E5 named-kind exit consumer: targets, recount gates and the per-cell exchange watch. Real plan, stood-in raw readers."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
import yaml

from foothold_s2 import ex42_late_stage_judge as late
from foothold_s2.eval import ex42_late_stage_kinds as kinds
from foothold_s2.ex42_score import ROOT

PLAN = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
PASS = {"eval_gt": {"judgement": "PASS"}, "eval_pred": {"judgement": "PASS"}}
FAIL = {"eval_gt": {"judgement": "FAIL"}, "eval_pred": {"judgement": "PASS"}}


def _plan():
    return yaml.safe_load(PLAN.read_text(encoding="utf-8"))


def test_e4_targets_come_from_the_plan_and_raise_slope_to_level_six():
    t = kinds.level_targets(_plan(), "E4")
    assert t[("E", "slope_steep")] == t[("E", "slope_steep_inv")] == 6
    assert t[("B", "climb_up")] == 3 and t[("E", "stairs_high")] == 3
    assert t[("A", "stepping_stones_low")] == 5                       # the E3 cap is kept, not lowered to the E4 floor
    assert any(f == "A" and v == 9 for (f, _), v in t.items())        # continuous kinds stay at their own cap


def test_e5_targets_keep_the_current_cap_and_do_not_raise_it():
    t5, t4 = kinds.level_targets(_plan(), "E5"), kinds.level_targets(_plan(), "E4")
    assert t5 and all(t5[k] <= t4.get(k, 99) for k in t5 if k in t4)
    assert kinds.spec_for(_plan(), "E5")["E5"]["min_level"] == 0


def test_inventory_marks_unopened_and_too_low_targets_and_refuses_unknown_kinds():
    plan = _plan()
    full = {f"{f}/{k}": v for (f, k), v in kinds.level_targets(plan, "E4").items()}
    ok = kinds.target_inventory(plan, "E4", full)
    assert ok["missing_targets"] == [] and ok["opened_cells"]
    low = dict(full, **{"E/slope_steep": 5})
    assert [m["kind"] for m in kinds.target_inventory(plan, "E4", low)["missing_targets"]] == ["slope_steep"]
    gone = {k: v for k, v in full.items() if k != "B/climb_up"}
    assert [m["kind"] for m in kinds.target_inventory(plan, "E4", gone)["missing_targets"]] == ["climb_up"]
    with pytest.raises(ValueError, match="outside the declared target set"):
        kinds.target_inventory(plan, "E4", dict(full, **{"Z/made_up": 1}))


def test_cells_are_l0_l5_and_cap_and_continuous_a_uses_the_global_flag_source():
    inv = kinds.target_inventory(_plan(), "E4", {"A/stepping_stones_low": 5, "B/climb_up": 3})
    got = {(c["family"], c["kind"], c["level"]): c["flag_source"] for c in inv["opened_cells"]}
    assert set(got) == {("A", "stepping_stones_low", 0), ("A", "stepping_stones_low", 5),
                        ("B", "climb_up", 0), ("B", "climb_up", 3)}
    assert set(got.values()) == {"kind_flag_four"}
    cont = next(k for (f, k) in kinds.level_targets(_plan(), "E4") if f == "A" and k != "stepping_stones_low"
                and k != "stepping_stones_high")
    inv = kinds.target_inventory(_plan(), "E4", {f"A/{cont}": 9})
    assert {c["flag_source"] for c in inv["opened_cells"]} == {"global_flag_cells"}


def _setup(monkeypatch, tmp_path, *, stage="E4", opened=None, exposure=True, exposure_mesh="b" * 64):
    import foothold_s2.ex42_learned_cells_evidence as evidence
    evaluation = tmp_path / "m500"
    (evaluation / f"kind_cells_{stage.lower()}").mkdir(parents=True)
    monkeypatch.setattr(evidence, "read_stage_exposure", lambda *_a, **_k: (
        {"opened_kinds": opened or {}, "mesh_sha256": exposure_mesh, "receipts": []} if exposure else None))
    score = {"stage_id": stage, "checkpoint_sha256": "a" * 64, "checkpoint": str(tmp_path / "model_500.pt"),
             "execution_plan_sha256": "c" * 64, "maintenance_source_sha256": "d" * 64, "conditions": {"eval_seed": 42}}
    mesh = {"mesh_sha256": "b" * 64, "column_family": ["B"], "columns": ["climb_up"]}
    return _plan(), evaluation, score, mesh


def _all_open(stage="E4"):
    return {f"{f}/{k}": v for (f, k), v in kinds.level_targets(_plan(), stage).items()}


def test_without_a_stage_exposure_receipt_it_holds_and_reads_no_raw(monkeypatch, tmp_path):
    plan, ev, score, mesh = _setup(monkeypatch, tmp_path, exposure=False)
    monkeypatch.setattr(kinds, "read_e3_window", lambda *_a, **_k: pytest.fail("raw window must not be read"))
    r = kinds.recount(score, plan=plan, evaluation=ev, mesh=mesh, stage_id="E4")
    assert r["judgement"] == "HOLD" and r["exposure_found"] is False and "cells" not in r


def test_a_training_mesh_that_differs_from_the_evaluation_mesh_is_refused(monkeypatch, tmp_path):
    plan, ev, score, mesh = _setup(monkeypatch, tmp_path, opened=_all_open(), exposure_mesh="e" * 64)
    with pytest.raises(ValueError, match="training and evaluation mesh differ"):
        kinds.recount(score, plan=plan, evaluation=ev, mesh=mesh, stage_id="E4")


def test_all_cells_passing_but_a_target_unopened_is_still_hold(monkeypatch, tmp_path):
    opened = dict(_all_open(), **{"E/slope_steep": 3})
    plan, ev, score, mesh = _setup(monkeypatch, tmp_path, opened=opened)
    (ev / "flag_cells" / "flag_four").mkdir(parents=True)
    (ev / "flag_cells" / "flag_four" / "flag_cells.json").write_text("{}")
    monkeypatch.setattr(kinds, "read_e3_window", lambda *_a, **_k: {"B/climb_up/L0": PASS})
    r = kinds.recount(score, plan=plan, evaluation=ev, mesh=mesh, stage_id="E4")
    assert r["inventory"]["missing_targets"] and r["judgement"] == "HOLD"


def test_every_target_open_and_every_cell_passing_is_pass_and_a_failing_cell_fails(monkeypatch, tmp_path):
    plan, ev, score, mesh = _setup(monkeypatch, tmp_path, opened=_all_open())
    (ev / "flag_cells" / "flag_four").mkdir(parents=True)
    (ev / "flag_cells" / "flag_four" / "flag_cells.json").write_text("{}")
    seen = {}
    monkeypatch.setattr(kinds, "read_e3_window", lambda *_a, **k: seen.update(k) or {"B/climb_up/L0": PASS})
    assert kinds.recount(score, plan=plan, evaluation=ev, mesh=mesh, stage_id="E4")["judgement"] == "PASS"
    assert seen["stage_id"] == "E4"                                   # the reader is asked for the late stage, not E3
    monkeypatch.setattr(kinds, "read_e3_window", lambda *_a, **_k: {"B/climb_up/L0": PASS, "B/gap/L3": FAIL})
    assert kinds.recount(score, plan=plan, evaluation=ev, mesh=mesh, stage_id="E4")["judgement"] == "FAIL"


def test_missing_global_flag_receipt_holds_for_continuous_kinds(monkeypatch, tmp_path):
    plan, ev, score, mesh = _setup(monkeypatch, tmp_path, opened=_all_open())
    monkeypatch.setattr(kinds, "read_e3_window", lambda *_a, **_k: pytest.fail("raw window must not be read"))
    r = kinds.recount(score, plan=plan, evaluation=ev, mesh=mesh, stage_id="E4")
    assert r["judgement"] == "HOLD" and "flag_four" in r["reason"]


def test_child_failure_marker_is_hold_and_a_forged_marker_is_refused(monkeypatch, tmp_path):
    plan, ev, score, mesh = _setup(monkeypatch, tmp_path, opened=_all_open())
    marker = ev / "kind_cells_e4" / "child_failures.json"
    marker.write_text(json.dumps({"format": "foothold-ex42-e4-child-failures/1",
                                  "checkpoint_sha256": "a" * 64, "reason": "Kit died"}))
    r = kinds.recount(score, plan=plan, evaluation=ev, mesh=mesh, stage_id="E4")
    assert r["judgement"] == "HOLD" and r["reason"] == "Kit died"
    marker.write_text(json.dumps({"format": "foothold-ex42-e4-child-failures/1",
                                  "checkpoint_sha256": "9" * 64, "reason": "x"}))
    with pytest.raises(ValueError, match="marker differs"):
        kinds.recount(score, plan=plan, evaluation=ev, mesh=mesh, stage_id="E4")


def test_stage_identity_must_match():
    with pytest.raises(ValueError):
        kinds.folder_name("E3")


def test_registered_kind_passes_follow_the_raw_cells_only():
    prev = {"cells": {"B/gap/L0": PASS, "B/gap/L3": FAIL, "B/beam/L0": FAIL}}
    assert kinds.passed_kinds(prev) == {("B", "gap"): True, ("B", "beam"): False}
    assert kinds.passed_kinds(None) == {}


# ---- judge level: the shared APIs are called with raw-derived inputs, per cell -------------------------------------
def _ctx(tmp_path, stage="E4"):
    return SimpleNamespace(stage_id=stage, plan=_plan(), checkpoint=tmp_path / "model_500.pt", evaluation=tmp_path / "m500")


def _source(cells_now, cells_old, learned=32):
    items = {k: {"role": "judge", "judgement": "PASS"} for k in ("exposure", "kind_current", "kind_previous", "level_targets")}
    return {"items": items, "cells_now": cells_now, "cells_previous": cells_old,
            "registered_kind_passes": {("B", "gap"): True}, "learned_cells_min": learned}


def _gates(monkeypatch, tmp_path, source, *, prior=object(), plan_sha="c" * 64, compare=None):
    import foothold_s2.ex42_exchange_watch as watch
    import foothold_s2.ex42_learned_cells_evidence as evidence
    calls = {}
    monkeypatch.setattr(late, "common_inputs", lambda *a: source)
    monkeypatch.setattr(evidence, "judge_two_boundaries", lambda *a, **k: calls.update(learned=k) or
                        {"role": "judge", "judgement": "PASS"})
    monkeypatch.setattr(watch, "compare", compare or (lambda *a, **k: calls.setdefault("cmp", []).append(k) or
                                                      {"role": "judge", "judgement": "PASS"}))
    current = {"execution_plan_sha256": plan_sha}
    return late.common_gates(_ctx(tmp_path), current, prior, baseline={}, measured={}), calls


def test_gates_compare_every_shared_cell_and_use_the_registered_threshold(monkeypatch, tmp_path):
    out, calls = _gates(monkeypatch, tmp_path, _source({"B/gap/L0": PASS, "B/gap/L3": PASS}, {"B/gap/L0": PASS, "B/gap/L3": PASS}))
    assert out["exchange_watch"]["judgement"] == "PASS" and len(calls["cmp"]) == 2
    assert calls["cmp"][0]["kind_score_key"] == "late_kind" and calls["learned"]["min_episodes"] == 32
    assert calls["learned"]["registered_kind_passes"] == {("B", "gap"): True}


def test_no_previous_cell_to_compare_is_hold_not_pass(monkeypatch, tmp_path):
    out, _ = _gates(monkeypatch, tmp_path, _source({"B/gap/L0": PASS}, {}))
    assert out["exchange_watch"]["judgement"] == "HOLD"
    out, _ = _gates(monkeypatch, tmp_path, _source({"B/gap/L0": PASS}, {"B/gap/L0": PASS}), prior=None)
    assert out["exchange_watch"]["judgement"] == "HOLD"


def test_one_failing_cell_comparison_is_not_averaged_away(monkeypatch, tmp_path):
    seq = iter(["PASS", "HOLD"])
    out, _ = _gates(monkeypatch, tmp_path, _source({"a/b/L0": PASS, "a/b/L3": PASS}, {"a/b/L0": PASS, "a/b/L3": PASS}),
                    compare=lambda *a, **k: {"role": "judge", "judgement": next(seq)})
    assert out["exchange_watch"]["judgement"] == "HOLD"


@pytest.mark.parametrize("sha,learned", [(None, 32), ("", 32), ("c" * 64, 16), ("c" * 64, None)])
def test_missing_plan_sha_or_wrong_threshold_holds(monkeypatch, tmp_path, sha, learned):
    out, calls = _gates(monkeypatch, tmp_path, _source({}, {}, learned=learned), plan_sha=sha)
    assert out["learned_cells"]["judgement"] == "HOLD" and "learned" not in calls


def test_common_inputs_builds_the_four_items_from_the_recount(monkeypatch, tmp_path):
    import foothold_s2.ex42_e3_judge as e3
    mesh = {"mesh_sha256": "b" * 64}
    monkeypatch.setattr(e3, "_mesh", lambda *_a: mesh)
    now = {"judgement": "PASS", "exposure_found": True, "inventory": {"missing_targets": []},
           "cells": {"B/gap/L0": PASS}, "evaluation": str(tmp_path / "m500" / "kind_cells_e4")}
    old = {"judgement": "HOLD", "cells": {"B/gap/L0": PASS}}
    seq = iter([now, old])
    monkeypatch.setattr(kinds, "recount", lambda *_a, **_k: next(seq))
    current = {}
    prior = {"late_kind": {"evaluation": str(tmp_path / "m250" / "kind_cells_e4")}}
    src = late.common_inputs(_ctx(tmp_path), current, prior)
    assert {k: v["judgement"] for k, v in src["items"].items()} == {
        "exposure": "PASS", "level_targets": "PASS", "kind_current": "PASS", "kind_previous": "HOLD"}
    assert current["late_kind"]["evaluation"] == now["evaluation"] and src["learned_cells_min"] == 32


def test_missing_exposure_or_target_or_previous_each_hold_their_own_item(monkeypatch, tmp_path):
    import foothold_s2.ex42_e3_judge as e3
    monkeypatch.setattr(e3, "_mesh", lambda *_a: {"mesh_sha256": "b" * 64})
    now = {"judgement": "HOLD", "exposure_found": False, "reason": "no receipt", "evaluation": "x"}
    monkeypatch.setattr(kinds, "recount", lambda *_a, **_k: now)
    src = late.common_inputs(_ctx(tmp_path), {}, None)
    assert {k: v["judgement"] for k, v in src["items"].items()} == {
        "exposure": "HOLD", "level_targets": "HOLD", "kind_current": "HOLD", "kind_previous": "HOLD"}
    now.update(exposure_found=True, judgement="PASS", inventory={"missing_targets": [{"kind": "x"}]})
    src = late.common_inputs(_ctx(tmp_path), {}, None)
    assert src["items"]["level_targets"]["judgement"] == "HOLD" and src["items"]["exposure"]["judgement"] == "PASS"


def test_prior_mesh_that_differs_is_refused(monkeypatch, tmp_path):
    import foothold_s2.ex42_e3_judge as e3
    meshes = iter([{"mesh_sha256": "b" * 64}, {"mesh_sha256": "c" * 64}])
    monkeypatch.setattr(e3, "_mesh", lambda *_a: next(meshes))
    monkeypatch.setattr(kinds, "recount", lambda *_a, **_k: {"judgement": "PASS", "evaluation": "x"})
    with pytest.raises(ValueError, match="mesh differ"):
        late.common_inputs(_ctx(tmp_path), {}, {"late_kind": {"evaluation": str(tmp_path / "m250" / "kind_cells_e4")}})
