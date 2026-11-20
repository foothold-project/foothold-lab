"""E2 v1 stage exit by map gain in two consecutive boundaries (mapgain_two_boundary_e2). CPU only, no Kit."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from foothold_s2 import ex42_mapgain_exit as mx
from foothold_s2.ex42_stage_judges import ADAPTERS, adapter_for, aggregate

PLAN = Path(__file__).resolve().parents[1] / "curriculum/ex42-prep.yaml"
SOURCE_V1 = Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_record/e2_handoff_20261120_170553_v1/materialized_E2")
MESH = Path("/mnt/win-d/mai/data/foothold/sonnet_beam_mesh_1119/b2m_rpy_lv")


def _plan():
    return yaml.safe_load(PLAN.read_text(encoding="utf-8-sig"))


def _row(verdict, level=5):
    return {"verdict": verdict, "level": level, "first_window_pass": verdict in ("graduate", "ceiling")}


def _boundary(folder: Path, iteration: int, verdicts: dict, *, ck: bytes | None = None):
    """eval/scores/m<iteration>/ with the outcome file, its meta and the model file next to eval/ (the run folder)."""
    scores = folder / f"m{iteration}"
    scores.mkdir(parents=True)
    data = ck if ck is not None else f"model {iteration}".encode()
    (folder.parent.parent / f"model_{iteration}.pt").write_bytes(f"model {iteration}".encode())
    (scores / "mapgain_outcomes.json").write_text(json.dumps(verdicts), encoding="utf-8")
    (scores / "mapgain_meta.json").write_text(json.dumps({"format": "foothold-ex42-mapgain-meta/1", "checkpoint_sha256": hashlib.sha256(data).hexdigest()}), encoding="utf-8")
    return scores


def test_the_judged_kinds_are_the_single_kind_rules_above_the_hold_floor_and_the_end_level_is_5():
    plan = _plan()
    assert mx.judged_kinds(plan) == ["A/gaps", "B/gap", "C/gap", "B/beam", "A/balance_beams", "C/box"] and mx.end_level(plan) == 5
    plan["stages"][[r["id"] for r in plan["stages"]].index("E2")]["terrain"]["exposure_at_E2"]["positive"][1]["share"] = 0.03     # A/gaps at the floor: graduated, left to maintenance
    assert "A/gaps" not in mx.judged_kinds(plan)


@pytest.mark.parametrize("row,state", [(_row("graduate"), "PASS"), (_row("ceiling"), "PASS"), (_row("graduate", 3), "HOLD"), (_row("not_yet"), "FAIL"),
                                       (_row("undecidable"), "HOLD"), (_row("incomplete"), "HOLD"), (None, "HOLD")])
def test_a_kind_passes_a_boundary_only_by_graduating_at_the_end_level(row, state):
    assert mx.kind_state(row, 5)["judgement"] == state


def test_two_consecutive_boundaries_are_needed_and_one_pass_is_hold():
    kinds = ["A/gaps", "C/box"]
    both = mx.kind_items(kinds, {k: _row("graduate") for k in kinds}, {k: _row("ceiling") for k in kinds}, 5)
    assert aggregate(i["judgement"] for i in both.values()) == "PASS"
    one = mx.kind_items(kinds, {k: _row("graduate") for k in kinds}, None, 5)
    assert aggregate(i["judgement"] for i in one.values()) == "HOLD"
    broke = mx.kind_items(kinds, {k: _row("graduate") for k in kinds}, {"A/gaps": _row("not_yet"), "C/box": _row("graduate")}, 5)
    assert aggregate(i["judgement"] for i in broke.values()) == "FAIL"


def test_the_outcomes_are_tied_to_the_checkpoint_and_the_previous_boundary_is_one_interval_back(tmp_path):
    scores = tmp_path / "eval" / "scores"
    scores.mkdir(parents=True)
    now = _boundary(scores, 500, {"A/gaps": _row("graduate")})
    _boundary(scores, 250, {"A/gaps": _row("ceiling")})
    ck = tmp_path / "model_500.pt"
    got, old = mx.read_pair(now, ck, 250)
    assert got["A/gaps"]["verdict"] == "graduate" and old["A/gaps"]["verdict"] == "ceiling"
    assert mx.read_pair(scores / "m250", tmp_path / "model_250.pt", 250)[1] is None          # first window: no previous
    ck.write_bytes(b"another model")
    with pytest.raises(ValueError, match="another checkpoint"):
        mx.read_outcomes(now, ck)
    (now / "mapgain_meta.json").unlink()
    with pytest.raises(ValueError, match="no mapgain_meta"):
        mx.read_outcomes(now, ck)
    assert mx.read_outcomes(tmp_path / "nothing", ck) is None


def test_the_adapter_is_registered_and_a_plan_naming_it_resolves():
    assert ADAPTERS[mx.NAME].name == "mapgain_two_boundary_e2"
    plan = _plan()
    next(r for r in plan["stages"] if r["id"] == "E2")["exit_judge"] = mx.NAME
    assert adapter_for(plan, "E2") is ADAPTERS[mx.NAME]
    assert adapter_for(_plan(), "E2").name == "kind_two_window_e2"                    # the shipped plan is unchanged


def _verify_fixture(tmp_path, monkeypatch, verdict_now="graduate", verdict_old="ceiling"):
    from foothold_s2 import ex42_stage_judges
    monkeypatch.setattr(ex42_stage_judges, "_map39_cell_check", lambda *_: "PASS")
    plan = _plan()
    kinds = mx.judged_kinds(plan)
    scores = tmp_path / "eval" / "scores"
    scores.mkdir(parents=True)
    now = _boundary(scores, 500, {k: _row(verdict_now) for k in kinds})
    _boundary(scores, 250, {k: _row(verdict_old) for k in kinds})
    ck = tmp_path / "model_500.pt"
    a, b = mx.read_pair(now, ck, 250)
    items = {"maintenance_current": {"role": "judge", "judgement": "PASS"}, "maintenance_previous": {"role": "judge", "judgement": "PASS"},
             "learned_cells": {"role": "judge", "judgement": "PASS"}, **mx.kind_items(kinds, a, b, 5)}
    verdict = aggregate(i["judgement"] for i in items.values())
    score = {"stage_id": "E2", "checkpoint": str(ck), "stage_exit": {"adapter": mx.NAME, "judgement": verdict, "windows": 2, "items": items},
             "mapgain_exit": {"evaluation": str(now), "judged_kinds": kinds, "end_level": 5, "now": a, "previous": b}}
    return plan, score, verdict


def test_p1_verify_accepts_the_honest_exit_and_each_forgery_is_refused(tmp_path, monkeypatch):
    plan, score, verdict = _verify_fixture(tmp_path, monkeypatch)
    assert verdict == "PASS"
    assert ADAPTERS[mx.NAME].verify(score, "PASS", "PASS", plan=plan) == {"stage_exit": score["stage_exit"]}
    forged = json.loads(json.dumps(score)); forged["stage_exit"]["items"]["A/gaps/L5/mapgain_previous"]["judgement"] = "FAIL"
    with pytest.raises(ValueError, match="aggregate|recount"):
        ADAPTERS[mx.NAME].verify(forged, "PASS", "PASS", plan=plan)
    edited = json.loads(json.dumps(score)); edited["mapgain_exit"]["now"]["A/gaps"]["verdict"] = "ceiling"
    with pytest.raises(ValueError, match="differ from the files"):
        ADAPTERS[mx.NAME].verify(edited, "PASS", "PASS", plan=plan)
    short = json.loads(json.dumps(score)); del short["stage_exit"]["items"]["C/box/L5/mapgain_current"]
    with pytest.raises(ValueError, match="aggregate"):
        ADAPTERS[mx.NAME].verify(short, "PASS", "PASS", plan=plan)
    lied = json.loads(json.dumps(score)); lied["stage_exit"]["items"]["learned_cells"]["judgement"] = "HOLD"
    with pytest.raises(ValueError):
        ADAPTERS[mx.NAME].verify(lied, "PASS", "PASS", plan=plan)


def test_p1_verify_refuses_a_pass_claimed_over_a_failed_window(tmp_path, monkeypatch):
    plan, score, verdict = _verify_fixture(tmp_path, monkeypatch, verdict_old="not_yet")
    assert verdict == "FAIL"
    assert ADAPTERS[mx.NAME].verify(score, "FAIL", "PASS", plan=plan)
    with pytest.raises(ValueError, match="aggregate"):
        ADAPTERS[mx.NAME].verify(score, "PASS", "PASS", plan=plan)


def test_the_boundary_judge_writes_the_meta_the_exit_reads(tmp_path):
    import numpy as np
    from foothold_s2.tools import ex42_v1_mapgain_boundary as J
    root = tmp_path / "runs"
    for sp in J.SPEEDS:
        for seed in (42, 43, 44):
            for inp, suffix in J.SUFFIX_OF.items():
                d = root / f"C_box_L5_v{sp}_s{seed}_{suffix}"
                d.mkdir(parents=True, exist_ok=True)
                (d / "DONE").write_text("")
                alive = np.ones(64, bool) if inp != "flat" else np.zeros(64, bool)
                np.savez(d / f"env_arrays_{J.MODE_OF[inp]}_x.npz", alive_end=alive, root_x_local_m=np.zeros((5, 64)))
    ck = tmp_path / "model_500.pt"; ck.write_bytes(b"ck500")
    out = tmp_path / "eval" / "scores" / "m500"
    assert J.main(["--root", str(root), "--kinds", "C/box=5", "--mesh-dir", str(tmp_path), "--boundary", "2", "--out", str(out), "--checkpoint", str(ck)]) == 0
    assert json.loads((out / "mapgain_meta.json").read_text())["checkpoint_sha256"] == hashlib.sha256(b"ck500").hexdigest()
    assert mx.read_outcomes(out, ck)["C/box"]["verdict"] == "graduate"


needs_v1 = pytest.mark.skipif(not (SOURCE_V1 / "ex42-prep.yaml").is_file() or not (MESH / "terrain_manifest.json").is_file(), reason="E2 v1 folder not on this machine")


@needs_v1
def test_the_reentry_draft_switches_the_exit_judge_and_the_e3_entry_gate_together(tmp_path):
    from foothold_s2.curriculum.ex42_prep import EX42Plan, authorization_validators
    from foothold_s2.tools import ex42_e2_reentry_draft as rd
    from foothold_s2.tests.test_ex42_e2_reentry_cpu import _fake_run
    run, sha = _fake_run(tmp_path, 250)
    record = rd.draft(SOURCE_V1, run, 250, MESH, tmp_path / "d", keep_mesh=True, exit_judge=mx.NAME)
    plan = EX42Plan.load(tmp_path / "d" / "ex42-prep.yaml")
    assert adapter_for(plan.document, "E2").name == mx.NAME
    e3 = next(r for r in plan.document["stages"] if r["id"] == "E3")
    assert e3["authorization_contract"]["entry_gate_adapter"] == mx.NAME
    approvals = yaml.safe_load((tmp_path / "d" / "ex42-approvals.yaml").read_text(encoding="utf-8-sig"))
    assert approvals["stage_e2_authorization"]["later_stage_entry_gate_adapter"] == mx.NAME
    assert authorization_validators(plan)["E2"](tmp_path / "d" / "ex42-approvals.yaml", sha)["scope"]["parent_sha256"] == sha
    assert record["exit_judge"]["E2.exit_judge"][1] == mx.NAME and record["exit_judge"]["E2.exit_judge"][0] == "kind_two_window_e2"
    with pytest.raises(ValueError, match="not a registered adapter"):
        rd.draft(SOURCE_V1, run, 250, MESH, tmp_path / "bad", keep_mesh=True, exit_judge="typo_judge")
    assert not (tmp_path / "bad").exists()
