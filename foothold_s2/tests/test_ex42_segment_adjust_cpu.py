"""E1 segment command adjustment (CG E.2 E1 "구간 명령 조정", v0.17l): a file outside the plan changes the command
profile at boundaries 1 and 2 only, inside the approved values, and every started segment leaves a record."""
from __future__ import annotations

import copy
import json
import types
from pathlib import Path

import pytest
import yaml

from foothold_s2 import ex42_canon_params_check as cpc
from foothold_s2.commands import ex42_segment_adjust as adj
from foothold_s2.commands import ex42_shares
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_training_entry as te

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "foothold_s2" / "curriculum" / "ex42-prep.yaml"


@pytest.fixture(scope="module")
def plan():
    return EX42Plan.load(PLAN)


@pytest.fixture(scope="module")
def source(plan):
    return te.load_ex42_stage_zero_source(plan)


@pytest.fixture()
def view(plan, source):
    return te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E1")


def base(plan):
    return adj.resolve(plan, "E1", None, 0)[0]


def entry(plan, **change):
    commands = copy.deepcopy(next(s for s in plan.document["stages"] if s["id"] == "E1")["commands"])
    for key, value in change.items():
        group, name = key.split("__")
        if group == "turn_overlay":
            commands[group][name] = value
        else:
            commands[group][name] = value
    return {"decided_at": "2026-11-12T16:10+09:00", "reason": "side step progress below the rule", "evidence": "boundary 250 sheet",
            "commands": commands}


def document(plan, **segments):
    return {"schema": adj.SCHEMA, "stage_id": "E1", "plan_sha256": plan.sha256,
            "segments": {key.lstrip("b"): value for key, value in segments.items()}}


def start(view, plan, tmp_path, k, doc=None, write=True):
    path = None
    if doc is not None:
        path = tmp_path / f"adjust_{k}.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
    return adj.start_segment(view, plan, "E1", boundary_index=k, path=str(path) if path else None, log_dir=str(tmp_path), write=write)


NARROW = {"ranges__side_vy_abs": [0.1, 0.4]}


def test_e1_may_adjust_at_boundaries_one_and_two_only(plan):
    assert adj.adjustable_boundaries(plan, "E1") == (1, 2)
    assert adj.adjustable_boundaries(plan, "E1F") == ()


def test_no_file_keeps_the_plan_profile_and_records_it(plan, view, tmp_path):
    record = start(view, plan, tmp_path, 1)
    assert record["source"] == "plan" and record["entry"] is None and record["commands"] == base(plan)
    assert view.stages[0].ranges["side_vy_abs"] == (0.1, 0.8)
    assert json.loads((tmp_path / "segment_commands_b1.json").read_text(encoding="utf-8")) == record


def test_first_segment_and_dry_run_leave_no_record(plan, view, tmp_path):
    assert start(view, plan, tmp_path, 0)["source"] == "plan"
    start(view, plan, tmp_path, 1, document(plan, b1=entry(plan, **NARROW)), write=False)
    assert list(tmp_path.glob("segment_commands_b*.json")) == []


def test_adjustment_reaches_the_stage_and_the_record(plan, view, tmp_path):
    change = {**NARROW, "shares__forward": 0.21, "shares__side_left": 0.08, "shares__side_right": 0.08,
              "turn_overlay__fraction": 0.1, "turn_overlay__wz_abs": [0.3, 0.5]}
    record = start(view, plan, tmp_path, 1, document(plan, b1=entry(plan, **change)))
    stage = view.stages[0]
    assert stage.ranges["side_vy_abs"] == (0.1, 0.4) and stage.turn_overlay == (0.1, 0.3, 0.5)
    assert stage.shares["forward"] == 0.21 and stage.shares["side_left"] == 0.08 and sum(stage.shares.values()) == pytest.approx(1.0)
    assert record["source"] == "adjust_file" and record["entry"] == 1 and len(record["file_sha256"]) == 64
    assert record["reason"] and record["decided_at"] and record["evidence"]
    assert record["commands"]["ranges"]["side_vy_abs"] == [0.1, 0.4]


def test_the_sampler_and_the_step_check_use_the_adjusted_profile(plan, view, tmp_path):
    import torch
    from foothold_s2.commands import mixed_core as mc
    from foothold_s2.curriculum import continuous
    change = {**NARROW, "shares__forward": 0.23, "shares__side_left": 0.07, "shares__side_right": 0.07,
              "turn_overlay__wz_abs": [0.3, 0.5]}
    start(view, plan, tmp_path, 2, document(plan, b2=entry(plan, **change)))
    stage, n = view.stages[0], 200_000
    out = mc.resample_stage(mc.make_generator(7), n, stage, torch.zeros(n))
    slot = {name: i for i, name in enumerate(mc.EX39_SLOTS)}
    side = torch.isin(out["slot"], torch.tensor([slot["side_left"], slot["side_right"]]))
    vy = out["cmd"][side, 1].abs()
    assert 0.1 <= float(vy.min()) and 0.38 < float(vy.max()) <= 0.4                    # the plan row went to 0.8
    assert abs(float(side.float().mean()) - 0.14) < 0.004                              # 0.07 + 0.07, the plan row has 0.18
    turned = side & (out["cmd"][:, 2].abs() > 0)
    assert 0.3 <= float(out["cmd"][turned, 2].abs().min()) and float(out["cmd"][turned, 2].abs().max()) <= 0.5
    assert not bool(continuous.command_bad(stage, out["slot"], out["cmd"]).any())


def test_train_start_applies_the_segment_commands_before_the_dry_run_ends():
    text = (ROOT / "foothold_s2" / "scripts" / "train_start.py").read_text(encoding="utf-8")
    call = text.index("EX42_SEGMENT_COMMANDS = _start_segment_commands(")
    block = text[call:text.index("if EX42_SEGMENT_COMMANDS is not None:", call)]
    for piece in ("EX42_STAGE_ZERO_PLAN_VIEW, EX42_STAGE_ZERO_PLAN, EX42_STAGE_ID,",
                  'EX42_STAGE_ZERO_RESUME_PROOF["local_update_origin"] // _interval',
                  'path=os.environ.get("EX42_SEGMENT_ADJUST"), log_dir=_pre_args.ex42_log_dir,',
                  'write=not _e_dry_run and os.environ.get("RANK", "0") == "0")'):
        assert piece in block
    made = text.index("EX42_STAGE_ZERO_PLAN_VIEW = make_ex42_stage_zero_plan_view(")
    dry_end = text.index('print(f"EX42_STAGE_{EX42_STAGE_ID}_SEGMENT "')
    assert made < text.index("EX42_STAGE_ZERO_RESUME_PROOF = validate_ex42_stage_zero_resume(", made) < call < dry_end
    assert dry_end < text.index("attach_runtime(env.unwrapped, EX42_STAGE_ZERO_PLAN_VIEW, log_dir)")


def test_later_segments_keep_the_last_adjustment(plan, view, tmp_path):
    doc1 = document(plan, b1=entry(plan, **NARROW))
    start(view, plan, tmp_path, 1, doc1)
    doc2 = document(plan, b1=entry(plan, **NARROW), b2=entry(plan, ranges__side_vy_abs=[0.2, 0.5]))
    start(view, plan, tmp_path, 2, doc2)
    for k in (3, 4, 5, 6):                      # the cap-raising segments: no new entry, the segment-3 values stay
        record = start(view, plan, tmp_path, k, doc2)
        assert record["entry"] == 2 and view.stages[0].ranges["side_vy_abs"] == (0.2, 0.5)


@pytest.mark.parametrize("change", [
    {"ranges__side_vy_abs": [0.1, 1.0]},              # above the approved side speed
    {"ranges__side_vy_abs": [0.05, 0.8]},             # below the approved floor
    {"ranges__walk_vx": [0.3, 1.3]},
    {"turn_overlay__fraction": 0.3},                  # more than the approved quarter
    {"turn_overlay__wz_abs": [0.2, 0.7]},
    {"turn_overlay__wz_abs": [0.1, 0.6]},
    {"shares__forward": 0.17, "shares__side_left": 0.10, "shares__side_right": 0.10},   # side share above the approved 0.09
    {"shares__forward": 0.25, "shares__side_left": 0.06, "shares__side_right": 0.06},
    {"shares__stand": 0.08, "shares__forward": 0.21},                                 # a slot the approval did not move
])
def test_values_outside_the_approved_ones_are_refused(plan, view, tmp_path, change):
    with pytest.raises(ValueError, match="leaves the approved"):
        start(view, plan, tmp_path, 1, document(plan, b1=entry(plan, **change)))
    assert view.stages[0].ranges["side_vy_abs"] == (0.1, 0.8) and list(tmp_path.glob("segment_commands_b*.json")) == []


@pytest.mark.parametrize("key", ["0", "3", "4", "6"])
def test_no_adjustment_at_the_first_segment_or_where_the_cap_rises(plan, view, tmp_path, key):
    doc = document(plan, **{"b" + key: entry(plan, **NARROW)})
    with pytest.raises(ValueError, match="may only name boundaries"):
        start(view, plan, tmp_path, 6, doc)


def test_an_entry_for_a_boundary_not_reached_is_refused(plan, view, tmp_path):
    doc = document(plan, b1=entry(plan, **NARROW), b2=entry(plan, **NARROW))
    with pytest.raises(ValueError, match="before the run reached it"):
        start(view, plan, tmp_path, 1, doc)


@pytest.mark.parametrize("mutate, match", [
    (lambda d: d.update(stage_id="E1F"), "another stage or plan"),
    (lambda d: d.update(plan_sha256="0" * 64), "another stage or plan"),
    (lambda d: d.update(schema="ex42-segment-adjust/0"), "needs exactly schema"),
    (lambda d: d.update(note="extra"), "needs exactly schema"),
    (lambda d: d["segments"]["1"].update(reason="  "), "needs decided_at, reason, evidence"),
    (lambda d: d["segments"]["1"].pop("evidence"), "needs decided_at, reason, evidence"),
    (lambda d: d["segments"]["1"].update(rewards={"foot_slip": -0.3}), "needs decided_at, reason, evidence"),
    (lambda d: d["segments"]["1"]["commands"].update(rewards={"foot_slip": -0.3}), "needs exactly shares, ranges and turn_overlay"),
    (lambda d: d.update(segments={}), "may only name boundaries"),
])
def test_only_the_three_command_cells_with_a_written_reason(plan, view, tmp_path, mutate, match):
    doc = document(plan, b1=entry(plan, **NARROW))
    mutate(doc)
    with pytest.raises(ValueError, match=match):
        start(view, plan, tmp_path, 1, doc)


def test_a_later_start_must_reproduce_what_the_earlier_segments_ran_with(plan, view, tmp_path):
    start(view, plan, tmp_path, 1, document(plan, b1=entry(plan, **NARROW)))
    rewritten = document(plan, b1=entry(plan, ranges__side_vy_abs=[0.3, 0.8]))
    with pytest.raises(ValueError, match="differs from what segment 1 ran with"):
        start(view, plan, tmp_path, 2, rewritten)
    with pytest.raises(ValueError, match="differs from what segment 1 ran with"):
        start(view, plan, tmp_path, 2)                       # dropping the file would silently go back to the plan values
    assert not (tmp_path / "segment_commands_b2.json").exists()


def test_a_segment_that_ran_on_plan_values_cannot_be_given_an_entry_afterwards(plan, view, tmp_path):
    start(view, plan, tmp_path, 1)
    with pytest.raises(ValueError, match="differs from what segment 1 ran with"):
        start(view, plan, tmp_path, 2, document(plan, b1=entry(plan, **NARROW)))
    assert start(view, plan, tmp_path, 2, document(plan, b2=entry(plan, **NARROW)))["entry"] == 2


def test_the_same_segment_started_again_must_carry_the_same_record(plan, view, tmp_path):
    doc = document(plan, b1=entry(plan, **NARROW))
    first = start(view, plan, tmp_path, 1, doc)
    assert start(view, plan, tmp_path, 1, doc) == first
    with pytest.raises(ValueError, match="already records another command profile"):
        start(view, plan, tmp_path, 1, document(plan, b1=entry(plan, ranges__side_vy_abs=[0.2, 0.6])))


def test_a_stage_without_a_command_profile_takes_no_file(plan, tmp_path):
    holder = types.SimpleNamespace(stages=[object()])
    assert adj.start_segment(holder, plan, "E1F", boundary_index=1, path=None, log_dir=str(tmp_path), write=True) is None
    path = tmp_path / "a.json"
    path.write_text(json.dumps(document(plan, b1=entry(plan, **NARROW))), encoding="utf-8")
    with pytest.raises(ValueError, match="no command profile to adjust"):
        adj.start_segment(holder, plan, "E1F", boundary_index=1, path=str(path), log_dir=str(tmp_path), write=True)


def test_stage_commands_and_the_adjustment_share_one_validator(plan):
    cell = next(s for s in plan.document["stages"] if s["id"] == "E1")["commands"]
    assert ex42_shares.validate_commands(plan, cell, "E1") == ex42_shares.stage_commands(plan, "E1")


# ---- the gate table reads the records ----

CLAIMS = yaml.safe_load((ROOT / "foothold_s2" / "curriculum" / "ex42-canon-claims.yaml").read_text(encoding="utf-8"))
CANON = (ROOT / CLAIMS["canon"]["path"]).read_text(encoding="utf-8")
ROW = "E1.segment_command_adjustment"


def verdict(folder):
    claims = {**CLAIMS, "claims": [c for c in CLAIMS["claims"] if c["id"] == ROW]}
    return cpc.check(claims, CANON, cpc.Sources("E1", run_dir=folder))["rows"][0]


def test_gate_row_passes_on_records_inside_the_canon(plan, view, tmp_path):
    start(view, plan, tmp_path, 1, document(plan, b1=entry(plan, **NARROW)))
    start(view, plan, tmp_path, 2, document(plan, b1=entry(plan, **NARROW)))
    row = verdict(tmp_path)
    assert row["verdict"] == "PASS" and row["seen"] == [(1, "adjust_file", 1), (2, "adjust_file", 1)]


def test_gate_row_has_no_data_without_records_and_skips_in_plan_mode(tmp_path):
    assert verdict(tmp_path)["verdict"] == "NO_DATA"
    claims = {**CLAIMS, "claims": [c for c in CLAIMS["claims"] if c["id"] == ROW]}
    assert cpc.check(claims, CANON, cpc.Sources("E1", plan=PLAN))["rows"][0]["verdict"] == "SKIP"


@pytest.mark.parametrize("damage, text", [
    (lambda b: b["commands"]["ranges"].update(side_vy_abs=[0.1, 1.0]), "ranges"),
    (lambda b: b["commands"]["shares"].update(side_left=0.12), "shares"),
    (lambda b: b["commands"].update(turn_overlay=[0.5, 0.2, 0.6]), "turn overlay"),
    (lambda b: b.update(entry=3), "adjusted at boundary 3"),
])
def test_gate_row_fails_on_a_record_outside_the_canon(plan, view, tmp_path, damage, text):
    start(view, plan, tmp_path, 1, document(plan, b1=entry(plan, **NARROW)))
    path = tmp_path / "segment_commands_b1.json"
    body = json.loads(path.read_text(encoding="utf-8"))
    damage(body)
    path.write_text(json.dumps(body), encoding="utf-8")
    row = verdict(tmp_path)
    assert row["verdict"] == "FAIL" and text in row["detail"]


def test_the_real_table_still_passes_the_e1_plan_gate():
    assert cpc.launch_gate("E1", PLAN)["passed"] is True
