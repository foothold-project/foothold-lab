"""E3 to E5 named-kind exit: the real plan rows, the real exposure receipts (real mesh), the raw Kit reader stubbed as in the E2 tests."""
from __future__ import annotations

import hashlib
import json
import pathlib

import pytest

from foothold_s2 import ex42_kind_stage_judge as ks
from foothold_s2.curriculum.ex42_prep import EX42Plan, entry_gate_adapter_ready
from foothold_s2.ex42_stage_judges import adapter_for, aggregate
from foothold_s2.tests import test_ex42_exposure_receipt_cpu as rt
from foothold_s2.tests.test_ex42_exposure_receipt_cpu import isaac_stubs  # noqa: F401  (autouse fixture of the receipt tests)

PLAN = rt.PLAN
need_mesh = rt.need_mesh
PSHA = rt.PSHA
LOW_PASS = rt.LOW_PASS


_LEGACY = []


def _real_plan():
    return EX42Plan.load(PLAN)


def _plan():
    """The plan with E3's one-kind K ladder put back (stepping_stones_low `new`, C/flat next): CG v0.18 draft E.12 opens E3's bundle in the start
    block and keeps `k_ladder.order: []`, so the machinery tests below run on this synthetic plan; the real rows are tested on `_real_plan()`."""
    if not _LEGACY:
        import tempfile
        _LEGACY.append(rt._ladder_plan(pathlib.Path(tempfile.mkdtemp(prefix="ex42-legacy-ladder-"))))
    return _LEGACY[0]


def _cell(valid, success, survival):
    return {"valid_count": valid, "success_count": success, "survival_count": survival}


def _score(cell, valid_min=24):
    return ks.score_kind(cell, valid_min_each=valid_min, success_min=52, survival_min=60, envs=32)


def test_the_three_stages_have_registered_judges_and_the_next_entry_resolves():
    plan = _real_plan()
    for stage in ("E3", "E4", "E5"):
        assert adapter_for(plan.document, stage).name == f"kind_two_window_{stage.lower()}"
    rows = {r["id"]: r for r in plan.document["stages"]}
    for target in ("E4", "E5", "E6a"):
        row = rows[target]
        assert entry_gate_adapter_ready(plan, row, row["authorization_contract"]), target


def test_the_stage_kind_lists_come_from_the_real_rows_and_never_name_a_continuous_kind():
    plan = _real_plan().document
    e3, e4, e5 = (ks.required_kinds(plan, s) for s in ("E3", "E4", "E5"))
    # CG v0.18 draft E.12: the judged kinds are the stage's NEW bundle (the maintenance table keeps the earlier ones at 0.03)
    assert e3 == ["B/pallets", "A/stepping_beams", "A/stepping_stones_low"]
    assert e4 == ["B/stones", "A/stepping_stones_high"]
    assert len(e5) == 14 and set(e5) == {"A/gaps", "B/gap", "C/gap", "B/beam", "A/balance_beams", "B/pallets", "A/stepping_beams",
                                           "A/stepping_stones_low", "B/stones", "A/stepping_stones_high",
                                           "E/stairs_high", "C/box", "B/climb_down", "E/stairs_high_inv"}
    assert not any(k in e3 for k in ("A/continuous",))
    spec = ks._spec(plan)
    assert spec["envs_per_kind"] == 32 and spec["valid_min_each"] == 24


def test_a_kind_cell_is_scored_with_the_promotion_counts_scaled_to_its_valid_envs():
    assert _score(_cell(32, 26, 30))["judgement"] == "PASS"            # ceil(52*32/64) = 26, ceil(60*32/64) = 30
    assert _score(_cell(32, 25, 30))["judgement"] == "FAIL"
    assert _score(_cell(32, 26, 29))["judgement"] == "FAIL"
    assert _score(_cell(23, 23, 23))["judgement"] == "HOLD"            # fewer than 24 valid envs is never judged
    assert _score(_cell(24, 20, 23))["judgement"] == "PASS"            # ceil(52*24/64) = 20, ceil(60*24/64) = 23
    assert _score(_cell(24, 19, 23))["judgement"] == "FAIL" and _score(_cell(24, 20, 22))["judgement"] == "FAIL"   # rounded up, not down
    for bad in (_cell(33, 0, 0), _cell(32, 33, 33), _cell(-1, 0, 0)):
        with pytest.raises(ValueError):
            ks.score_kind(bad, valid_min_each=24, success_min=52, survival_min=60, envs=32)


def test_optional_balance_beam_survival_gate_is_scored_and_receipted(monkeypatch):
    monkeypatch.delenv(ks.SURVIVAL_FINISH_ENV, raising=False)
    assert ks.survival_finish_x_from_env() is None
    old = _score(_cell(32, 32, 18))
    assert old["judgement"] == "FAIL" and "survival_finish_x_m" not in old
    monkeypatch.setenv(ks.SURVIVAL_FINISH_ENV, "6.8")
    assert ks.survival_finish_x_from_env() == 6.8
    cell = {**_cell(32, 32, 32), "survival_finish_x_m": 6.8,
            "survival_finish_reclassified_count": 14}
    scored = _score(cell)
    assert scored["judgement"] == "PASS"
    assert scored["survival_finish_reclassified_count"] == 14
    assert scored["survival_finish_x_m"] == 6.8
    for raw in ("0", "12.1", "nan", "inf", "wrong"):
        monkeypatch.setenv(ks.SURVIVAL_FINISH_ENV, raw)
        with pytest.raises(ValueError, match=ks.SURVIVAL_FINISH_ENV):
            ks.survival_finish_x_from_env()


def test_finish_survival_gate_only_reaches_balance_beams_and_never_mixes_windows(monkeypatch, tmp_path):
    calls = []
    def read_cell(_folder, **kwargs):
        calls.append((kwargs["kind"], kwargs["survival_finish_x_m"]))
        return _cell(32, 32, 32)
    monkeypatch.setattr(ks, "read_start_kind_cell", read_cell)
    kinds = {"A/balance_beams": 4, "B/rough": 1}
    rows = ks.read_kind_modes(tmp_path, kinds, plan=_real_plan().document,
                              mesh={}, checkpoint_sha256="a" * 64, seed=42,
                              survival_finish_x_m=6.8)
    assert len(calls) == 6
    assert calls == [("balance_beams", 6.8)] * 3 + [("rough", None)] * 3
    assert rows["A/balance_beams"]["eval_gt"]["judgement"] == "PASS"
    assert ks.checked_previous({"kind_stage": {}}, evaluation=tmp_path, plan={},
                               plan_sha256="p", mesh={}, seed=42,
                               survival_finish_x_m=6.8) is None


def test_optional_survival_finish_evaluation_receipt_is_explicit():
    from foothold_s2.ex42_eval_once import kind_survival_finish_receipt
    assert kind_survival_finish_receipt({"kind_stage": {}}) is None
    score = {"kind_stage": {"survival_finish_x_m": 6.8, "modes": {"A/balance_beams": {
        "eval_gt": {"survival_finish_reclassified_count": 14},
        "eval_pred": {"survival_finish_reclassified_count": 10}}}}}
    assert kind_survival_finish_receipt(score) == {"x_m": 6.8,
                                                   "reclassified_by_mode": {"eval_gt": 14, "eval_pred": 10}}


def _bundle(levels, verdicts):
    """{kind: {level, eval_gt, eval_pred, probe}} with the given judgement per kind (PASS or FAIL) for both judged modes."""
    out = {}
    for kind, level in levels.items():
        good = verdicts[kind] == "PASS"
        cell = _score(_cell(32, 28 if good else 10, 31 if good else 20))
        out[kind] = {"level": level, "eval_gt": {**cell, "role": "judge"}, "eval_pred": {**cell, "role": "judge"},
                     "probe_prop_only": {**cell, "role": "record_only"}}
    return out


def _verdict(items):
    return aggregate(item["judgement"] for item in items.values() if item["role"] == "judge")


def test_the_exit_aggregates_over_every_open_kind_and_needs_the_previous_window_and_the_whole_ladder():
    levels = {"A/stepping_stones_low": 1, "C/flat": 0}
    done = ks.ladder_item(list(levels), levels)
    both = _bundle(levels, {k: "PASS" for k in levels})
    assert _verdict(ks.stage_items(levels, both, both, done)) == "PASS"
    one_fail = _bundle(levels, {"A/stepping_stones_low": "PASS", "C/flat": "FAIL"})
    assert _verdict(ks.stage_items(levels, one_fail, both, done)) == "FAIL"
    assert _verdict(ks.stage_items(levels, both, one_fail, done)) == "FAIL"        # previous window of one kind failed
    assert _verdict(ks.stage_items(levels, both, None, done)) == "HOLD"            # no previous window at all
    assert _verdict(ks.stage_items(levels, both, {"C/flat": both["C/flat"]}, done)) == "HOLD"   # one kind without it
    raised = {"A/stepping_stones_low": {**both["A/stepping_stones_low"], "level": 2}, "C/flat": both["C/flat"]}
    assert _verdict(ks.stage_items(levels, both, raised, done)) == "HOLD"          # previous window at another level
    pending = ks.ladder_item(["A/stepping_stones_low", "C/flat", "B/rough"], levels)
    assert pending["judgement"] == "HOLD" and pending["pending"] == ["B/rough"]
    assert _verdict(ks.stage_items(levels, both, both, pending)) == "HOLD"          # ladder not finished
    record = ks.stage_items(levels, one_fail, both, done)["C/flat/L0/probe_prop_only_current"]
    assert record["role"] == "record_only"                                         # recorded, never judged


def test_the_ladder_evidence_follows_the_judgement_of_each_kind():
    levels = {"A/stepping_stones_low": 1, "C/flat": 0}
    both = _bundle(levels, {k: "PASS" for k in levels})
    bad = _bundle(levels, {"A/stepping_stones_low": "PASS", "C/flat": "FAIL"})
    assert ks.ladder_outcomes(levels, both, None) == {"A/stepping_stones_low": {"first_window_pass": True, "target_level_reached": False},
                                                      "C/flat": {"first_window_pass": True, "target_level_reached": False}}
    assert ks.ladder_outcomes(levels, both, both)["C/flat"] == {"first_window_pass": True, "target_level_reached": True}
    assert ks.ladder_outcomes(levels, bad, both)["C/flat"] == {"first_window_pass": False, "target_level_reached": False}
    assert ks.ladder_outcomes(levels, both, bad)["C/flat"] == {"first_window_pass": True, "target_level_reached": False}


def _write_boundary_receipts(folder, stage, k, outcomes, iteration):
    body = rt.er.build_receipt(rt._contract(stage=stage, k=k, outcomes=outcomes, plan=_plan()), stage_id=stage, plan_sha256=PSHA,
                               iteration=iteration, kind="boundary")
    rt.er.write_receipt(folder, body)
    return body


@need_mesh
def test_the_opened_kinds_are_the_plan_replay_of_the_receipt_and_a_forged_receipt_opens_nothing(tmp_path):
    plan = _plan().document
    body = _write_boundary_receipts(tmp_path, "E3", 2, [LOW_PASS, {}], 500)
    checkpoint = tmp_path / "model_500.pt"
    opened = ks.opened_kinds(checkpoint, stage_id="E3", plan_sha256=PSHA, plan=plan)
    assert opened == body["opened_kinds"] and "C/flat" in opened and "B/rough" not in opened
    required = ks.required_kinds(plan, "E3")
    assert ks.ladder_item(required, opened)["judgement"] == "HOLD"
    with pytest.raises(ValueError, match="identity"):
        ks.opened_kinds(checkpoint, stage_id="E3", plan_sha256="b" * 64, plan=plan)
    forged = tmp_path / "forged"
    forged.mkdir()
    fake = json.loads(json.dumps(body))
    fake["ladder_outcomes"] = [{}, {}]                       # evidence that opens nothing, sha refreshed by the forger
    fake["sha256"] = rt.er._sha(fake)
    (forged / "exposure_receipt_500.json").write_text(json.dumps(fake))
    with pytest.raises(ValueError, match="differ from the plan replay"):
        ks.opened_kinds(forged / "model_500.pt", stage_id="E3", plan_sha256=PSHA, plan=plan)
    with pytest.raises(ValueError, match="missing"):
        ks.opened_kinds(tmp_path / "model_750.pt", stage_id="E3", plan_sha256=PSHA, plan=plan)


def _learned_boundary(folder, iteration, table, cells):
    body = {"format": "foothold-ex42-learned-cells/1", "stage_id": "E3", "plan_sha256": PSHA,
            "window": {"from_it": iteration - 250, "to_it": iteration}, "rank": 0, "world_size": 1,
            "axes": {"level_bands": [[0, 2], [3, 5], [6, 9]],
                     "groups": ["forward", "reverse", "side_left", "side_right", "turn_left", "turn_right", "stand", "flag"],
                     "modes": ["map_on_adaptive", "map_off"], "columns": len(table)},
            "columns": table, "cells": cells, "total": sum(c[-1] for c in cells), "episodes_counted_once": True}
    body["sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    (folder / f"learned_cells_{iteration}.json").write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")


@need_mesh
def test_learned_cells_registers_the_kinds_the_boundary_exposure_opened_in_any_family(tmp_path):
    from foothold_s2.ex42_learned_cells_evidence import judge_two_boundaries
    plan = _plan().document
    body = _write_boundary_receipts(tmp_path, "E3", 2, [LOW_PASS, {}], 500)
    _write_boundary_receipts(tmp_path, "E3", 1, [LOW_PASS], 250)
    table = [{"family": r["family"], "kind": r["kind"]} for r in body["column_rows"]]
    (tmp_path / "params").mkdir()
    (tmp_path / "params" / "agent.yaml").write_text("perception:\n  p_map_off: 0\n")
    for iteration in (250, 500):
        _learned_boundary(tmp_path, iteration, table, [[0, 0, "forward", "map_on_adaptive", 1]])
    checkpoint = tmp_path / "model_500.pt"

    def pending_kinds(named):
        result = judge_two_boundaries(checkpoint, stage_id="E3", plan=plan, plan_sha256=PSHA, interval=250,
                                      min_episodes=32, previous_kind_pass=False, named_kinds=named)
        return {(r[0], r[1]) for r in result["pending"]}

    assert ("C", "flat") not in pending_kinds({})                       # opened, but no previous passing window: not registered yet
    assert ("C", "flat") in pending_kinds({("C", "flat"): True})         # a non-A kind registers once its window passed
    assert ("A", "stepping_stones_low") in pending_kinds({("A", "stepping_stones_low"): True})
    assert ("B", "rough") not in pending_kinds({("B", "rough"): True})   # the ladder has not opened it: it has no exposure
    with pytest.raises(ValueError, match="threshold invalid"):
        judge_two_boundaries(checkpoint, stage_id="E3", plan=plan, plan_sha256=PSHA, interval=250, min_episodes=32,
                             previous_kind_pass=False)                   # E3 without its kind list
    # E2 takes its bundle kind list like the later stages since CG v0.18 draft E.12 (the one-kind None path is retired)


def test_the_exchange_watch_compares_the_kind_cells_it_is_given_by_name():
    from foothold_s2.ex42_exchange_watch import compare
    measured = {"survival_drop_envs": 2, "error_rise_vx_vy_mps": 0.1, "error_rise_wz_radps": 0.1}
    now = {"conditions": {"eval_seed": 42}, "score_config_sha256": "s", "stage_id": "E3", "kind_stage": {"mesh_sha256": "m"}}
    old = json.loads(json.dumps(now))

    def watch(newer, older):
        result = compare(now, old, measured=measured, baseline={}, kind_now={"eval_gt": {"C/flat": newer}},
                         kind_previous={"eval_gt": {"C/flat": older}}, kind_key="kind_stage", subcells=("C/flat",))
        return [v["cell"] for v in result["violations"]]

    assert watch(_cell(32, 26, 30), _cell(32, 26, 30)) == []
    assert watch(_cell(32, 20, 30), _cell(32, 26, 30)) == ["kind/eval_gt/C/flat/success_count"]
    assert "kind_stage" not in compare(now, {**old, "kind_stage": {"mesh_sha256": "other"}}, measured=measured, baseline={},
                                       kind_now={}, kind_previous=None, kind_key="kind_stage", subcells=())["missing"]


def test_the_e2_exchange_watch_default_still_reads_the_e2_keys():
    from foothold_s2.ex42_exchange_watch import compare
    now = {"conditions": {"eval_seed": 42}, "score_config_sha256": "s", "stage_id": "E2", "e2_kind": {"mesh_sha256": "m"}}
    other = {**now, "e2_kind": {"mesh_sha256": "x"}}
    assert compare(now, other, measured={}, baseline={}, kind_now={}, kind_previous=None)["missing"] == ["identity"]


def test_a_registered_kind_counts_a_straight_line_travel_and_an_unregistered_one_is_hold(tmp_path):
    spec = ks._spec(_plan().document)
    assert ks.finish_anchor({}, family="A", kind="gaps", level=0, completion=spec["completion"]) is None
    anchor = ks.finish_anchor({}, family="C", kind="flat", level=0, completion=spec["completion"])
    assert anchor["travel_m"] == 3.5 and ks.finish_anchor({}, family="B", kind="rough", level=0, completion=spec["completion"])["travel_m"] == 4.0
    assert ks.finish_anchor({}, family="E", kind="slope_steep", level=0, completion=spec["completion"])["center_max_m"] == 3.85
    for hold in ("no_such_kind",):                                    # a kind the plan does not register
        with pytest.raises(KeyError):
            ks.finish_anchor({}, family="B", kind=hold, level=0, completion=spec["completion"])


def test_travel_is_a_straight_line_displacement_so_a_random_reset_heading_does_not_matter():
    import numpy as np
    from foothold_s2.eval.ex42_kind_completion import score_last_support
    steps, envs, dt = 100, 4, 0.02
    t = np.arange(steps)[:, None] * 0.05
    angle = np.array([0.0, 1.5, 3.1, -2.0])[None, :]                # four reset headings
    x = 10.0 + t * np.cos(angle) + 0 * t
    y = 3.0 + t * np.sin(angle) + 0 * t
    alive = np.ones((steps, envs), dtype=bool)
    alive[40:, 3] = False                                            # one env falls before it has gone 3.5 m (it is at 2 m)
    trace = {"root_x_local_m": x, "root_y_local_m": y, "alive": alive, "dt": dt}
    got = score_last_support(trace, travel_m=3.5, settle_s=0.5, envs=envs)
    assert [row["success"] for row in got["per_env"]] == [True, True, True, False]
    assert score_last_support(trace, finish_x_m=12.0, settle_s=0.5, envs=envs)["success_count"] == 1     # a map-forward line misses the rotated envs
    with pytest.raises(ValueError, match="exactly one"):
        score_last_support(trace, finish_x_m=1.0, travel_m=1.0, settle_s=0.5, envs=envs)


def test_a_kind_without_a_registered_rule_gets_hold_cells_in_the_raw_reader(monkeypatch):
    calls = []
    monkeypatch.setattr(ks, "read_start_kind_cell", lambda *a, **k: calls.append(k["family"] + "/" + k["kind"]) or _cell(32, 30, 32))
    plan = _plan().document
    out = ks.read_kind_modes(pathlib.Path("/none"), {"B/no_such_kind": 0, "C/flat": 0}, plan=plan, mesh={}, checkpoint_sha256="c" * 64, seed=42)
    assert out["B/no_such_kind"]["eval_gt"]["judgement"] == "HOLD" and out["B/no_such_kind"]["probe_prop_only"]["role"] == "record_only"
    assert calls == ["C/flat"] * 3                                    # the registered kind was read in all three modes


def test_a_contract_that_differs_from_the_registered_one_is_refused():
    plan = json.loads(json.dumps(_plan().document))
    plan["evaluation"]["kind_stage_cells"]["completion"]["B/rough"]["rule"] = "last_support"
    with pytest.raises(ValueError, match="completion rule invalid"):
        ks._spec(plan)
    plan = json.loads(json.dumps(_plan().document))
    plan["evaluation"]["kind_stage_cells"]["completion"]["C/flat"]["m"] = 99
    with pytest.raises(ValueError, match="completion rule invalid"):
        ks._spec(plan)
    plan = json.loads(json.dumps(_plan().document))
    plan["evaluation"]["kind_stage_cells"]["envs_per_kind"] = 128
    with pytest.raises(ValueError, match="contract differs"):
        ks._spec(plan)


def _verify_fixture(tmp_path, monkeypatch, *, required=None, old_passes=True):
    """A P1 score for E3 at m500 over the real receipt (low + flat open), the raw Kit reader and the previous-window lookup stubbed."""
    from foothold_s2.eval import ex42_mesh_eval
    from foothold_s2 import ex42_e1_judge, ex42_stage_judges
    plan = _plan().document
    body = _write_boundary_receipts(tmp_path, "E3", 2, [LOW_PASS, {}], 500)
    opened = dict(body["opened_kinds"])
    if required is not None:
        monkeypatch.setattr(ks, "required_kinds", lambda *_: required)
    levels = {k: opened[k] for k in ks.required_kinds(plan, "E3") if k in opened}      # every named kind that is open (the bundle and the ladder's flat)
    run = tmp_path / "m500"
    (run / "map64").mkdir(parents=True)
    (run / "kind_cells").mkdir()
    (run / "map64" / "map_modes.json").write_text(json.dumps({"ex42_mesh": {"manifest": "/x/mesh_manifest.json", "mesh_sha256": "b" * 64}}))
    monkeypatch.setattr(ex42_mesh_eval, "preflight", lambda _p: {"mesh_sha256": "b" * 64})
    now = _bundle(levels, {k: "PASS" for k in levels})
    old = _bundle(levels, {k: "PASS" if old_passes else "FAIL" for k in levels})
    monkeypatch.setattr(ks, "read_kind_modes", lambda folder, kinds, **kw: now if kw["checkpoint_sha256"] == "c" * 64 else old)
    monkeypatch.setattr(ex42_e1_judge, "previous_e1_score", lambda *a, **k: {"checkpoint": str(tmp_path / "model_250.pt"), "checkpoint_sha256": "d" * 64})
    monkeypatch.setattr(ks, "checked_previous", lambda *a, **k: old)
    monkeypatch.setattr(ex42_stage_judges, "_map39_cell_check", lambda *_: "PASS")
    req = ks.required_kinds(plan, "E3")
    items = {"maintenance_current": {"role": "judge", "judgement": "PASS"}, "maintenance_previous": {"role": "judge", "judgement": "PASS"},
             "learned_cells": {"role": "judge", "judgement": "PASS"}, "exchange_watch": {"role": "judge", "judgement": "PASS"},
             **ks.stage_items(levels, now, old, ks.ladder_item(req, opened))}
    verdict = _verdict(items)
    score = {"stage_id": "E3", "checkpoint": str(tmp_path / "model_500.pt"), "checkpoint_sha256": "c" * 64,
             "execution_plan_sha256": PSHA, "maintenance_source_sha256": PSHA, "score_config_sha256": "s", "conditions": {"eval_seed": 42},
             "stage_exit": {"adapter": "kind_two_window_e3", "judgement": verdict, "windows": 2, "items": items},
             "kind_stage": {"modes": now, "previous_modes": old, "mesh_sha256": "b" * 64, "evaluation": str(run / "kind_cells"),
                            "opened_kinds": opened}}
    return plan, score, verdict


@need_mesh
def test_p1_verify_accepts_the_honest_exit_and_each_forgery_is_refused(tmp_path, monkeypatch):
    plan, score, verdict = _verify_fixture(tmp_path, monkeypatch, required=["A/stepping_stones_low", "C/flat"])
    assert verdict == "PASS"
    adapter = adapter_for(plan, "E3")
    assert adapter.verify(score, "PASS", "PASS", plan=plan) == {"stage_exit": score["stage_exit"]}

    def forged(mutate, match):
        copy = json.loads(json.dumps(score))
        mutate(copy)
        with pytest.raises(ValueError, match=match):
            adapter.verify(copy, "PASS", "PASS", plan=plan)

    forged(lambda s: s["stage_exit"]["items"]["learned_cells"].update(judgement="HOLD"), "aggregate stage exit differs")
    forged(lambda s: s["stage_exit"]["items"].pop("C/flat/L0/eval_gt_previous"), "aggregate stage exit differs")
    forged(lambda s: s["stage_exit"]["items"]["C/flat/L0/eval_pred_current"].update(success_count=0), "differ from the recount")
    forged(lambda s: s["kind_stage"]["modes"]["C/flat"]["eval_gt"].update(judgement="PASS", success_count=1), "kind score differs from raw")
    forged(lambda s: s["kind_stage"].update(previous_modes=None), "previous window differs")
    forged(lambda s: s["kind_stage"]["opened_kinds"].update({"B/rough": 0}), "opened kinds differ")
    forged(lambda s: s["kind_stage"].update(mesh_sha256="e" * 64), "mesh identity differs")


@need_mesh
def test_p1_verify_refuses_a_pass_while_the_ladder_is_not_finished_or_a_window_failed(tmp_path, monkeypatch):
    plan, score, verdict = _verify_fixture(tmp_path, monkeypatch)            # the E3 list of the legacy-ladder plan names the bundle, the earlier kinds, C/flat and B/rough; B/rough stays closed
    assert verdict == "HOLD" and score["stage_exit"]["items"]["kind_ladder"]["judgement"] == "HOLD"
    adapter = adapter_for(plan, "E3")
    assert adapter.verify(score, "HOLD", "PASS", plan=plan)
    with pytest.raises(ValueError, match="aggregate stage exit differs"):
        adapter.verify(score, "PASS", "PASS", plan=plan)
    plan2, failed, verdict2 = _verify_fixture(tmp_path / "second", monkeypatch, required=["A/stepping_stones_low", "C/flat"], old_passes=False) \
        if (tmp_path / "second").mkdir() is None else (None, None, None)
    assert verdict2 == "FAIL"
    assert adapter.verify(failed, "FAIL", "PASS", plan=plan2)


def test_a_failed_kind_child_is_hold_with_the_marker_sha_and_the_other_kinds_are_still_read(monkeypatch, tmp_path):
    folder = tmp_path / "kind_cells"
    folder.mkdir()
    marker = {"format": "foothold-ex42-kind-stage-child-failures/1", "stage_id": "E3", "checkpoint_sha256": "c" * 64,
              "failures": {"C/flat": "ValueError: boom"}}
    (folder / "child_failures.json").write_text(json.dumps(marker))
    monkeypatch.setattr(ks, "read_start_kind_cell", lambda *a, **k: _cell(32, 30, 32))
    out = ks.read_kind_modes(folder, {"C/flat": 0, "C/discrete_grid": 0}, plan=_plan().document, mesh={}, checkpoint_sha256="c" * 64, seed=42)
    assert out["C/flat"]["eval_gt"]["judgement"] == "HOLD" and out["C/flat"]["eval_gt"]["child_failure"]["sha256"]
    assert out["C/discrete_grid"]["eval_gt"]["judgement"] == "PASS"
    marker["checkpoint_sha256"] = "d" * 64
    (folder / "child_failures.json").write_text(json.dumps(marker))
    with pytest.raises(ValueError, match="marker identity"):
        ks.read_kind_modes(folder, {"C/flat": 0}, plan=_plan().document, mesh={}, checkpoint_sha256="c" * 64, seed=42)


def test_the_stage_evaluation_commands_are_one_child_per_open_kind_at_its_cap_with_the_plan_env_count():
    from foothold_s2 import ex42_eval_once as once
    plan = _plan()
    kinds = {"A/stepping_stones_low": 1, "C/flat": 0}
    commands = once.kind_stage_kit_commands("/x/model_500.pt", "/x/m500", "cuda:0", task="T", plan_path=plan.path, plan=plan.document,
                                            mesh_dir="/x/mesh", seed=42, kinds=kinds)
    assert [name for name, _ in commands] == ["kind_stage_A__stepping_stones_low", "kind_stage_C__flat"]
    for (name, argv), (kind, level) in zip(commands, sorted(kinds.items())):
        family, kname = kind.split("/")
        at = lambda flag: argv[argv.index(flag) + 1]
        assert (at("--envs"), at("--fixed-level"), at("--ex42-kind-family"), at("--ex42-kind-name")) == ("32", str(level), family, kname)
        assert at("--out") == f"/x/m500/kind_cells/{kind.replace('/', '__')}" and at("--commands") == "fwd1.0" and at("--steps") == "600"
    e2 = once.e2_kind_kit_commands("/x/model_500.pt", "/x/m500", "cuda:0", task="T", plan_path=plan.path, plan=plan.document,
                                   mesh_dir="/x/mesh", mesh_sha256="m" * 64, seed=42)
    assert e2[0][1][e2[0][1].index("--envs") + 1] == "64"                  # E2 keeps its 64-env cells


def test_the_ladder_evidence_list_has_one_entry_per_boundary_and_pads_a_missing_one(tmp_path):
    out = {"C/flat": {"first_window_pass": True, "target_level_reached": False}}
    for iteration in (250, 500, 750):
        folder = tmp_path / f"m{iteration}"
        if iteration != 500:                                        # the 500 boundary left no evidence (its evaluation failed)
            ks.write_ladder_evidence(tmp_path / f"model_{iteration}.pt", folder, 250, out if iteration == 750 else {"A/x": {}})
    assert json.loads((tmp_path / "m250" / "ladder_outcomes_list.json").read_text()) == [{"A/x": {}}]
    assert json.loads((tmp_path / "m750" / "ladder_outcomes_list.json").read_text()) == [{"A/x": {}}, {}, out]


def test_a_continued_stage_segment_gets_the_ladder_evidence_file_or_is_refused(tmp_path, monkeypatch):
    from foothold_s2.scripts import ex42_stage_launcher as L
    from foothold_s2.tests.test_ex42_stage_launcher_cpu import _env

    # the shipped template plan pins no parent for E3 (a materialized plan does); the stage table lookups are the only stub
    monkeypatch.setattr(L, "_stage_updates", lambda stage, plan: 1000)
    monkeypatch.setattr(L, "_stage_caps", lambda stage, plan: [1000])
    env = _env(tmp_path, action="continue", stage="E3")
    Path = pathlib.Path
    run = Path(env["EX42_AUTO_RESUME_CHECKPOINT"]).parent
    env["EX42_AUTO_RESUME_CHECKPOINT"] = str(run / "model_500.pt")      # two boundaries passed (interval 250)
    env["EX42_AUTO_SEGMENT_END"] = "750"
    with pytest.raises(L.LaunchRefused, match="missing or unreadable"):
        L.build(env)
    listing = run / "eval" / "scores" / "m500" / "ladder_outcomes_list.json"
    listing.parent.mkdir(parents=True)
    listing.write_text(json.dumps([{}]))
    with pytest.raises(L.LaunchRefused, match="one evidence entry per boundary"):
        L.build(env)
    listing.write_text(json.dumps([{}, {"C/flat": {"first_window_pass": True}}]))
    _, child, _ = L.build(env)
    assert child["EX42_LADDER_OUTCOMES"] == str(listing)
    (tmp_path / "e1").mkdir()
    stage_one = _env(tmp_path / "e1", action="continue", stage="E1")
    assert "EX42_LADDER_OUTCOMES" not in L.build(stage_one)[1]            # only E3 to E5 carry the ladder evidence


def test_center_max_counts_the_ring_distance_from_the_cell_origin_in_any_heading_and_splits_the_failures():
    import numpy as np
    from foothold_s2.eval.ex42_kind_completion import score_last_support
    steps, envs = 100, 4
    t = np.arange(steps)[:, None] * 0.05
    x = np.stack([t[:, 0], 0 * t[:, 0], -t[:, 0], 0.4 + 0 * t[:, 0]], axis=1)      # +x, stays, -x, near the start
    y = np.stack([0 * t[:, 0], 0 * t[:, 0], 0.0 * t[:, 0], 0.4 * t[:, 0]], axis=1)
    x[:, 1] = 0.01 * t[:, 0]
    alive = np.ones((steps, envs), dtype=bool)
    alive[30:, 3] = False                                            # env 3 falls, env 1 only dawdles
    trace = {"root_x_local_m": x, "root_y_local_m": y, "alive": alive, "dt": 0.02}
    got = score_last_support(trace, center_max_m=3.5, settle_s=0.5, envs=envs)
    assert [r["success"] for r in got["per_env"]] == [True, False, True, False]
    assert (got["fell_before_reach_count"], got["timeout_count"]) == (1, 1)


def test_the_approved_exit_gate_of_e3_to_e5_is_exactly_the_design_block_without_a_completion_line():
    import yaml
    doc = yaml.safe_load((pathlib.Path(__file__).resolve().parents[1] / "curriculum" / "ex42-approvals.yaml").read_text(encoding="utf-8"))
    want = {"cells": "opened_kinds_at_level_cap", "success_min": 52, "survival_min": 60, "windows": 2, "learned_cells_min": 32,
            "learned_cells_min_grade": "assumption", "exchange_learning_watch": True, "maintenance_table": "pass"}
    for stage in ("e3", "e4", "e5"):
        assert doc[f"stage_{stage}_authorization"]["exit_gate"] == want       # the pass rule per kind lives in the plan only


def test_an_approved_exit_gate_that_differs_from_the_plan_promotion_is_named_and_the_real_ones_agree():
    import yaml
    plan = _plan().document
    doc = yaml.safe_load((pathlib.Path(__file__).resolve().parents[1] / "curriculum" / "ex42-approvals.yaml").read_text(encoding="utf-8"))
    for stage in ("e3", "e4", "e5"):
        gate = doc[f"stage_{stage}_authorization"]["exit_gate"]
        assert ks.exit_gate_mismatch(plan, gate) == []
        for key, other in (("success_min", 51), ("survival_min", 59), ("windows", 3)):
            assert ks.exit_gate_mismatch(plan, {**gate, key: other}) == [key]
        gate_without = {k: v for k, v in gate.items() if k != "windows"}
        assert ks.exit_gate_mismatch(plan, gate_without) == ["windows"]       # an absent key is a difference, not a pass


def test_a_differing_gate_turns_the_learned_cells_item_hold_and_the_exit_aggregate_with_it():
    learned = {"role": "judge", "judgement": "PASS"}
    assert ks.gate_checked(learned, []) is learned
    held = ks.gate_checked(learned, ["windows"])
    assert held["judgement"] == "HOLD" and held["exit_gate_mismatch"] == ["windows"] and learned["judgement"] == "PASS"
    assert aggregate(i["judgement"] for i in (held, {"judgement": "PASS"})) == "HOLD"


def test_climb_and_gap_of_b_are_x_based_cells_that_start_facing_plus_x_and_only_they_get_the_option():
    from foothold_s2 import ex42_eval_once as once
    plan = _plan()
    completion = plan.document["evaluation"]["kind_stage_cells"]["completion"]
    assert {k: (v["rule"], v["m"], v.get("start_yaw_zero")) for k, v in completion.items() if k in ("B/climb_up", "B/climb_down", "B/gap")} == {
        "B/climb_up": ("forward_x", 4.5, True), "B/climb_down": ("forward_x", 4.5, True), "B/gap": ("forward_x", 5.4, True)}
    assert [k for k, v in completion.items() if v.get("start_yaw_zero")] == ["B/climb_up", "B/climb_down", "B/gap"]
    gap = ks.finish_anchor({}, family="B", kind="gap", level=3, completion=completion)
    assert gap["start_yaw_zero"] is True and gap["forward_x_m"] == 5.4 and "travel_m" not in gap
    assert "start_yaw_zero" not in ks.finish_anchor({}, family="B", kind="rough", level=3, completion=completion)
    kinds = {"B/climb_up": 1, "B/gap": 1, "B/rough": 1, "C/flat": 0}
    commands = once.kind_stage_kit_commands("/x/model_500.pt", "/x/m500", "cuda:0", task="T", plan_path=plan.path, plan=plan.document,
                                            mesh_dir="/x/mesh", seed=42, kinds=kinds)
    assert {name: "--start-yaw-zero" in argv for name, argv in commands} == {
        "kind_stage_B__climb_up": True, "kind_stage_B__gap": True, "kind_stage_B__rough": False, "kind_stage_C__flat": False}


def test_a_start_yaw_zero_mark_other_than_true_is_an_invalid_completion_rule():
    import copy
    doc = copy.deepcopy(_plan().document)
    doc["evaluation"]["kind_stage_cells"]["completion"]["B/gap"]["start_yaw_zero"] = False
    with pytest.raises(ValueError, match="completion rule invalid"):
        ks._spec(doc)


def test_the_raw_reader_asks_the_cell_validator_for_the_yaw_record_only_when_the_anchor_carries_the_mark(monkeypatch, tmp_path):
    from foothold_s2.eval import ex42_kind_completion as kc
    from foothold_s2.eval import ex42_mesh_eval as me
    asked = []

    def stop(*args, **kwargs):
        asked.append(kwargs["start_yaw_zero"])
        raise RuntimeError("stop after the validator")

    monkeypatch.setattr(me, "validate_kind_cell", stop)
    modes = {m: {"fwd1.0": {}} for m in ("eval_gt", "eval_pred", "probe_prop_only")}
    (tmp_path / "map_modes.json").write_text(json.dumps({
        "checkpoint_sha256": "c" * 64, "eval_seed": 42, "envs": 32, "ex42_mesh": {"mesh_sha256": "m"}, "modes": modes,
        "env_arrays": {f"{m}/fwd1.0": f"env_arrays_{m}_fwd1.0.npz" for m in modes}}))
    for anchor in ({"travel_m": 4.5, "start_yaw_zero": True}, {"travel_m": 4.0}):
        with pytest.raises(RuntimeError, match="stop after"):
            kc.read_start_kind_cell(tmp_path, mesh={"mesh_sha256": "m"}, checkpoint_sha256="c" * 64, seed=42, family="B",
                                    kind="gap", level=1, mode="eval_gt", seconds=12, settle_s=0.5, envs=32, anchor=anchor)
    assert asked == [True, False]


def test_forward_x_counts_only_the_plus_x_displacement_so_walking_sideways_or_back_does_not_pass():
    import numpy as np
    from foothold_s2.eval.ex42_kind_completion import score_last_support
    steps, envs, dt = 100, 4, 0.02
    t = np.arange(steps)[:, None] * 0.08                             # 7.9 m in 100 steps (the 4.5 m line is reached with the settle window left)
    x = 2.0 + t * np.array([1.0, 0.0, -1.0, 0.0])[None, :]           # +x, sideways (y), backward, standing
    y = 6.0 + t * np.array([0.0, 1.0, 0.0, 0.0])[None, :]
    trace = {"root_x_local_m": x, "root_y_local_m": y, "alive": np.ones((steps, envs), dtype=bool), "dt": dt}
    got = score_last_support(trace, forward_x_m=4.5, settle_s=0.5, envs=envs)
    assert [row["success"] for row in got["per_env"]] == [True, False, False, False]
    assert score_last_support(trace, travel_m=4.5, settle_s=0.5, envs=envs)["success_count"] == 3     # the straight-line rule would pass three
    with pytest.raises(ValueError, match="exactly one"):
        score_last_support(trace, forward_x_m=1.0, travel_m=1.0, settle_s=0.5, envs=envs)


def test_a_forward_x_rule_without_the_plus_x_start_mark_is_an_invalid_completion_rule():
    import copy
    doc = copy.deepcopy(_plan().document)
    del doc["evaluation"]["kind_stage_cells"]["completion"]["B/gap"]["start_yaw_zero"]
    with pytest.raises(ValueError, match="completion rule invalid"):
        ks._spec(doc)


def test_each_anchor_of_the_plan_reaches_its_own_arrival_rule_through_the_reader_helper():
    import numpy as np
    from foothold_s2.eval.ex42_kind_completion import score_with_anchor
    steps, envs = 100, 2
    t = np.arange(steps)[:, None] * 0.08
    trace = {"root_x_local_m": 2.0 + 0 * t + np.zeros((1, envs)), "root_y_local_m": 6.0 + t * np.array([[1.0, 0.0]]),
             "alive": np.ones((steps, envs), dtype=bool), "dt": 0.02}
    trace["root_x_local_m"] = 2.0 + t * np.array([[0.0, 1.0]])         # env 0 walks along y, env 1 along +x
    completion = _plan().document["evaluation"]["kind_stage_cells"]["completion"]
    by = {kind: [r["success"] for r in score_with_anchor(trace, ks.finish_anchor({}, family="B", kind=kind, level=1, completion=completion),
                                                        settle_s=0.5, envs=envs)["per_env"]] for kind in ("gap", "rough")}
    assert by["gap"] == [False, True]             # forward_x: only the +x walker
    assert by["rough"] == [True, True]            # travel: both walkers


def _run_the_real_judge(tmp_path, monkeypatch, survival_min):
    """judge() end to end on CPU: everything that reads Kit files or training receipts is stubbed to PASS, the approvals file is a
    real file next to the plan with the given survival_min; returns (score the judge made, kwargs judge_two_boundaries got)."""
    from types import SimpleNamespace
    import yaml
    from foothold_s2 import ex42_e0_judge, ex42_exchange_watch, ex42_learned_cells_evidence
    plan, score, _ = _verify_fixture(tmp_path, monkeypatch, required=["A/stepping_stones_low", "C/flat"])
    kinds = score["kind_stage"]["opened_kinds"]
    kinds = {k: kinds[k] for k in ("A/stepping_stones_low", "C/flat")}
    gate = {"success_min": 52, "survival_min": survival_min, "windows": 2, "learned_cells_min": 32}
    (tmp_path / plan["approval_file"]).write_text(yaml.safe_dump({"stage_e3_authorization": {"approved": True, "exit_gate": gate}}))
    seen = {}
    monkeypatch.setattr(ex42_e0_judge, "load_baseline", lambda *a, **k: {})
    monkeypatch.setattr(ex42_e0_judge, "judge", lambda *a, **k: {"judgement": "PASS", "execution_plan_sha256": PSHA})
    monkeypatch.setattr(ks, "previous_window", lambda ctx: {"stage_id": "E3"})
    monkeypatch.setattr(ks, "opened_kinds", lambda *a, **k: kinds)
    monkeypatch.setattr(ks, "write_ladder_evidence", lambda *a, **k: None)
    monkeypatch.setattr(ex42_exchange_watch, "compare", lambda *a, **k: {"role": "judge", "judgement": "PASS"})

    def learned(*args, **kwargs):
        seen.update(kwargs)
        return {"role": "judge", "judgement": "PASS"}

    monkeypatch.setattr(ex42_learned_cells_evidence, "judge_two_boundaries", learned)
    run = tmp_path / "m500"
    ctx = SimpleNamespace(plan=plan, plan_path=tmp_path / "plan.yaml", evaluation=run, checkpoint=tmp_path / "model_500.pt",
                          checkpoint_sha="c" * 64, seed=42, digest=lambda _p: PSHA, root=tmp_path, cfg={"baseline": {"sha256": "z" * 64}})
    got = ks.KindStageTwoWindowJudge("E3").judge(ctx, {"execution_plan_sha256": PSHA, "judgement": "PASS"})
    return got, seen


@need_mesh
def test_the_real_judge_holds_on_an_approved_gate_that_differs_from_the_plan_and_passes_with_the_same_gate(tmp_path, monkeypatch):
    for survival_min, want, mismatch in ((59, "HOLD", ["survival_min"]), (60, "PASS", None)):
        folder = tmp_path / f"s{survival_min}"
        folder.mkdir()
        got, seen = _run_the_real_judge(folder, monkeypatch, survival_min)
        learned = got["stage_exit"]["items"]["learned_cells"]
        assert got["judgement"] == want and got["stage_exit"]["judgement"] == want
        assert learned["judgement"] == want and learned.get("exit_gate_mismatch") == mismatch
        assert seen["min_episodes"] == 32 and seen["stage_id"] == "E3"                     # the approved learned_cells_min still reaches the evidence judge
        assert set(seen["named_kinds"]) == {("A", "stepping_stones_low"), ("C", "flat")}   # the named-kind wiring is covered by the same run
