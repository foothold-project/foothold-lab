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
    # Most tests here cover a stage row without its own `rewards` / `low_forward_fraction` cells (the finished E1,
    # every later stage): the cells of the shipped E1 row are taken off the loaded document. The row cells themselves
    # are tested at the end of the file.
    loaded = EX42Plan.load(PLAN)
    row = next(row for row in loaded.document["stages"] if row["id"] == "E1")
    row.pop("rewards", None)
    row.pop("low_forward_fraction", None)
    return loaded


@pytest.fixture(scope="module")
def source(plan):
    return te.load_ex42_stage_zero_source(plan)


@pytest.fixture()
def view(plan, source):
    return te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E1")


def base(plan):
    return adj.resolve(plan, "E1", None, 0)["commands"]


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
    bad = continuous.command_bad(out["cmd"], out["slot"], out["heading"], torch.zeros(n, dtype=torch.long),
                                 types.SimpleNamespace(stages=[stage]))
    assert not bool(bad.any())


def test_train_start_applies_the_segment_commands_before_the_dry_run_ends():
    text = (ROOT / "foothold_s2" / "scripts" / "train_start.py").read_text(encoding="utf-8")
    call = text.index("EX42_SEGMENT_COMMANDS = _start_segment_commands(")
    block = text[call:text.index("if EX42_SEGMENT_COMMANDS is not None:", call)]
    for piece in ("EX42_STAGE_ZERO_PLAN_VIEW, EX42_STAGE_ZERO_PLAN, EX42_STAGE_ID,",
                  'EX42_STAGE_ZERO_RESUME_PROOF["local_update_origin"] // _interval',
                  'path=os.environ.get("EX42_SEGMENT_ADJUST"), log_dir=EX42_RUN_LOG_DIR,',      # every rank reads the shared records
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


def test_the_approved_limits_themselves_are_reachable(plan, view, tmp_path):
    """decisions.tsv 2026-11-12 14:23: side speed 1.0, side share 0.12 each (forward 0.13), walk 1.5, overlay 0.4, wz 0.8."""
    change = {"ranges__side_vy_abs": [0.1, 1.0], "ranges__walk_vx": [0.3, 1.5], "turn_overlay__fraction": 0.4,
              "turn_overlay__wz_abs": [0.2, 0.8], "shares__forward": 0.13, "shares__side_left": 0.12, "shares__side_right": 0.12}
    record = start(view, plan, tmp_path, 1, document(plan, b1=entry(plan, **change)))
    stage = view.stages[0]
    assert stage.ranges["side_vy_abs"] == (0.1, 1.0) and stage.ranges["walk_vx"] == (0.3, 1.5)
    assert stage.turn_overlay == (0.4, 0.2, 0.8) and (stage.shares["forward"], stage.shares["side_left"]) == (0.13, 0.12)
    assert record["source"] == "adjust_file" and sum(stage.shares.values()) == pytest.approx(1.0)


@pytest.mark.parametrize("change", [
    {"ranges__side_vy_abs": [0.1, 1.1]},              # above the approved side speed
    {"ranges__side_vy_abs": [0.05, 0.8]},             # below the slow floor
    {"ranges__walk_vx": [0.3, 1.6]},
    {"ranges__walk_vx": [0.2, 1.2]},
    {"ranges__forward_vx": [0.1, 1.6]},               # a range the limits do not name may only narrow
    {"ranges__spin_wz_abs": [0.1, 1.5]},
    {"turn_overlay__fraction": 0.45},
    {"turn_overlay__wz_abs": [0.2, 0.9]},
    {"turn_overlay__wz_abs": [0.1, 0.6]},
    {"shares__forward": 0.11, "shares__side_left": 0.13, "shares__side_right": 0.13},   # side share above 0.12
    {"shares__forward": 0.18, "shares__reverse": 0.15},                               # only an upper line is crossed
    {"shares__forward": 0.25, "shares__side_left": 0.06, "shares__side_right": 0.06},
    {"shares__stand": 0.08, "shares__forward": 0.21},                                 # a slot the limits do not name
])
def test_values_outside_the_approved_limits_are_refused(plan, view, tmp_path, change):
    with pytest.raises(ValueError, match="leaves the approved limits"):
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
    (lambda d: d["segments"]["1"].update(rewards={"foot_slip": -0.3}), "rewards needs exactly"),
    (lambda d: d["segments"]["1"].update(note="extra"), "needs decided_at, reason, evidence"),
    (lambda d: d["segments"]["1"].pop("commands"), "needs decided_at, reason, evidence"),
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


def test_a_segment_that_left_no_record_ran_on_plan_values(plan, view, tmp_path):
    """The recorder may reach the run folder after segment 2 started: that segment then ran on the plan row."""
    with pytest.raises(ValueError, match="differs from what segment 1 ran with"):
        start(view, plan, tmp_path, 2, document(plan, b1=entry(plan, **NARROW)))
    assert start(view, plan, tmp_path, 2, document(plan, b2=entry(plan, **NARROW)))["entry"] == 2


def test_the_same_segment_started_again_must_carry_the_same_record(plan, view, tmp_path):
    doc = document(plan, b1=entry(plan, **NARROW))
    first = start(view, plan, tmp_path, 1, doc)
    assert start(view, plan, tmp_path, 1, doc) == first
    with pytest.raises(ValueError, match="already records another command profile"):
        start(view, plan, tmp_path, 1, document(plan, b1=entry(plan, ranges__side_vy_abs=[0.2, 0.6])))


def test_a_stage_without_a_command_profile_takes_no_command_entry(plan, tmp_path):
    stage = object()
    holder = types.SimpleNamespace(stages=[stage])
    # J0 is a row with no `commands` cell (the rows E1F .. E6b carry E1's ranges: test_ex42_later_stage_commands_cpu.py)
    record = adj.start_segment(holder, plan, "J0", boundary_index=1, path=None, log_dir=str(tmp_path), write=True)
    assert record["commands"] is None and record["rewards"]["values"] is None and holder.stages == [stage]
    path = tmp_path / "a.json"
    doc = {**document(plan, b1=entry(plan, **NARROW)), "stage_id": "J0"}
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match=r"may only name boundaries \[\] for commands"):
        adj.start_segment(holder, plan, "J0", boundary_index=1, path=str(path), log_dir=str(tmp_path), write=True)


# ---- reward cells (lead 2026-11-12 21:27): tracking widths and two weights, any boundary, limits outside the plan ----

REWARDS = {"track_lin_vel_std": 0.35, "track_ang_vel_std": 0.4, "feet_air_time": 0.2, "foot_slip": -0.2,
           "zero_yaw": -0.5}       # the plan value here; the zero_yaw tests below move it


def reward_entry(**change):
    return {"decided_at": "2026-11-12T22:10+09:00", "reason": "slow commands stand still", "evidence": "boundary 750 sheet",
            "rewards": {**REWARDS, **change}}


def test_the_shipped_reward_limits_are_the_relayed_lines():
    limits = adj.reward_limits()
    assert limits["cells"] == {"track_lin_vel_std": (0.25, 0.5), "track_ang_vel_std": (0.25, 0.5),
                               "feet_air_time": (0.0, 0.5), "foot_slip": (-0.25, -0.05),
                               "zero_yaw": (-2.0, -0.5)}                  # decisions.tsv 2026-11-13 09:52
    assert len(limits["sha256"]) == 64 and adj.reward_limits("/nowhere/limits.yaml") is None


@pytest.mark.parametrize("text", [
    "schema: ex42-reward-adjust-limits/0\ncells: {}",
    "schema: ex42-reward-adjust-limits/1\ncells: {track_lin_vel_std: [0.25, 0.5]}",
    "schema: ex42-reward-adjust-limits/1\ncells: {track_lin_vel_std: [0.5, 0.25], track_ang_vel_std: [0.25, 0.5], "
    "feet_air_time: [0, 0.5], foot_slip: [-0.25, -0.05], zero_yaw: [-2.0, -0.5]}",
    "schema: ex42-reward-adjust-limits/1\ncells: {track_lin_vel_std: [0.25, 0.5], track_ang_vel_std: [0.25, 0.5], "
    "feet_air_time: [0, 0.5], foot_slip: [-0.25, -0.05]}",                                  # the zero_yaw cell is missing
])
def test_a_malformed_limits_file_is_refused(tmp_path, text):
    path = tmp_path / "limits.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="reward adjust limits need"):
        adj.reward_limits(path)


def test_rewards_may_change_where_the_cap_rises_and_reach_the_stage_and_the_record(plan, view, tmp_path):
    before = dict(view.stages[0].rewards)
    start(view, plan, tmp_path, 1)
    start(view, plan, tmp_path, 2)
    record = start(view, plan, tmp_path, 3, document(plan, b3=reward_entry()))      # boundary 750: commands stay fixed
    stage = view.stages[0]
    assert stage.rewards["foot_slip"] == -0.2 and stage.rewards["feet_air_time"] == 0.2
    assert {k: v for k, v in stage.rewards.items() if k not in ("foot_slip", "feet_air_time")} == \
        {k: v for k, v in before.items() if k not in ("foot_slip", "feet_air_time")}
    assert stage.ranges["side_vy_abs"] == (0.1, 0.8)                                 # the plan command profile
    assert record["source"] == "plan" and record["entry"] is None and record["commands"] == base(plan)
    assert record["rewards"] == {"source": "adjust_file", "entry": 3, "values": REWARDS,
                                 "decided_at": "2026-11-12T22:10+09:00", "reason": "slow commands stand still",
                                 "evidence": "boundary 750 sheet", "limits_sha256": adj.reward_limits()["sha256"]}
    assert json.loads((tmp_path / "segment_commands_b3.json").read_text(encoding="utf-8")) == record


def test_no_entry_leaves_the_plan_rewards(plan, view, tmp_path):
    before = dict(view.stages[0].rewards)
    record = start(view, plan, tmp_path, 1)
    assert view.stages[0].rewards == before and before["foot_slip"] == -0.15 and before["feet_air_time"] == 0.0
    assert record["rewards"]["source"] == "plan" and record["rewards"]["values"] is None


@pytest.mark.parametrize("change", [
    {"track_lin_vel_std": 0.2}, {"track_lin_vel_std": 0.6}, {"track_ang_vel_std": 0.24}, {"track_ang_vel_std": 0.51},
    {"feet_air_time": -0.1}, {"feet_air_time": 0.6}, {"foot_slip": -0.3}, {"foot_slip": -0.04},
    {"zero_yaw": -2.1}, {"zero_yaw": -0.4}, {"zero_yaw": 0.0},
])
def test_rewards_outside_the_limits_are_refused(plan, view, tmp_path, change):
    with pytest.raises(ValueError, match="leaves the approved limits"):
        start(view, plan, tmp_path, 1, document(plan, b1=reward_entry(**change)))
    assert view.stages[0].rewards["foot_slip"] == -0.15


def test_reward_cells_are_exactly_the_registered_ones_and_need_the_limits_file(plan, view, tmp_path):
    for broken in ({**REWARDS, "action_rate": -0.02}, {k: v for k, v in REWARDS.items() if k != "foot_slip"},
                   {k: v for k, v in REWARDS.items() if k != "zero_yaw"}, {**REWARDS, "foot_slip": "low"}):
        doc = document(plan, b1={**reward_entry(), "rewards": broken})
        with pytest.raises(ValueError, match="rewards needs exactly"):
            start(view, plan, tmp_path, 1, doc)
    path = tmp_path / "adjust.json"
    path.write_text(json.dumps(document(plan, b1=reward_entry())), encoding="utf-8")
    with pytest.raises(ValueError, match="no reward adjust limits file"):
        adj.start_segment(view, plan, "E1", boundary_index=1, path=str(path), log_dir=str(tmp_path), write=False,
                          limits_path=tmp_path / "absent.yaml")


def test_commands_and_rewards_are_held_apart_until_a_later_entry_of_their_kind(plan, view, tmp_path):
    doc1 = document(plan, b1=reward_entry())
    start(view, plan, tmp_path, 1, doc1)
    doc2 = {**doc1, "segments": {**doc1["segments"], "2": entry(plan, **NARROW)}}        # commands only at 500
    record = start(view, plan, tmp_path, 2, doc2)
    assert record["entry"] == 2 and record["rewards"]["entry"] == 1 and record["rewards"]["values"] == REWARDS
    doc4 = {**doc2, "segments": {**doc2["segments"], "4": reward_entry(foot_slip=-0.1)}}
    start(view, plan, tmp_path, 3, doc2)
    record = start(view, plan, tmp_path, 4, doc4)
    assert record["entry"] == 2 and view.stages[0].ranges["side_vy_abs"] == (0.1, 0.4)       # commands still from 500
    assert record["rewards"]["entry"] == 4 and view.stages[0].rewards["foot_slip"] == -0.1
    both = {**doc1, "segments": {"1": {**reward_entry(), "commands": entry(plan, **NARROW)["commands"]}}}
    other = tmp_path / "both"
    other.mkdir()
    record = start(view, plan, other, 1, both)                                               # one entry, both kinds
    assert record["entry"] == 1 and record["rewards"]["entry"] == 1


def test_a_later_start_must_reproduce_the_rewards_the_earlier_segments_ran_with(plan, view, tmp_path):
    start(view, plan, tmp_path, 1, document(plan, b1=reward_entry()))
    with pytest.raises(ValueError, match="differs from what segment 1 ran with"):
        start(view, plan, tmp_path, 2, document(plan, b1=reward_entry(foot_slip=-0.1)))
    with pytest.raises(ValueError, match="differs from what segment 1 ran with"):
        start(view, plan, tmp_path, 2)
    assert start(view, plan, tmp_path, 2, document(plan, b1=reward_entry()))["rewards"]["entry"] == 1


def test_a_record_written_before_the_reward_cells_still_counts_and_a_record_can_be_pasted_back(plan, view, tmp_path):
    """The running E1 folder holds segment_commands_b1.json from the earlier code: the overlay as a list, no rewards."""
    record = start(view, plan, tmp_path, 1, document(plan, b1=entry(plan, **NARROW)))
    overlay = record["commands"]["turn_overlay"]
    assert overlay == {"fraction": 0.25, "wz_abs": [0.2, 0.6]}                         # the shape of the input now
    old = {k: v for k, v in record.items() if k != "rewards"}
    old["commands"] = {**record["commands"], "turn_overlay": [overlay["fraction"], *overlay["wz_abs"]]}
    (tmp_path / "segment_commands_b1.json").write_text(json.dumps(old), encoding="utf-8")
    pasted = {**entry(plan), "commands": record["commands"]}                           # lead 21:24: a record's cell, as is
    later = start(view, plan, tmp_path, 2, document(plan, b1=entry(plan, **NARROW), b2=pasted))
    assert later["entry"] == 2 and view.stages[0].ranges["side_vy_abs"] == (0.1, 0.4)
    assert cpc.check({**CLAIMS, "claims": [c for c in CLAIMS["claims"] if c["id"] == ROW]}, CANON,
                     cpc.Sources("E1", run_dir=tmp_path))["rows"][0]["verdict"] == "PASS"   # both shapes are read


def test_a_stage_with_no_adjustable_commands_still_takes_rewards(plan, source, tmp_path):
    holder = te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E1F")
    doc = {"schema": adj.SCHEMA, "stage_id": "E1F", "plan_sha256": plan.sha256, "segments": {"1": reward_entry()}}
    path = tmp_path / "adjust.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    record = adj.start_segment(holder, plan, "E1F", boundary_index=1, path=str(path), log_dir=str(tmp_path), write=True)
    # E1F keeps E1's command ranges (its row carries them) and has no limits cell: commands stay, rewards change
    assert record["commands"]["ranges"]["side_vy_abs"] == [0.1, 0.8] and record["rewards"]["values"] == REWARDS
    assert holder.stages[0].rewards["foot_slip"] == -0.2 and holder.stages[0].ranges["side_vy_abs"] == (0.1, 0.8)


class _Term:
    def __init__(self, weight=0.0, std=None):
        self.weight, self.params = weight, ({"std": std, "command_name": "base_velocity"} if std is not None else {})


def _manager(lin=0.5, ang=0.5, air=0.0, slip=-0.15, yaw=-0.5):
    terms = {"track_lin_vel": _Term(2.0, lin), "track_ang_vel": _Term(1.0, ang),
             "ex41_feet_air_time": _Term(air), "ex41_foot_slip": _Term(slip), "ex41_zero_yaw": _Term(yaw)}
    return types.SimpleNamespace(get_term_cfg=lambda name: terms[name]), terms


def test_the_tracking_widths_go_on_the_env_config_only_when_an_entry_asks(plan, view, tmp_path):
    _, terms = _manager()
    env_cfg = types.SimpleNamespace(rewards=types.SimpleNamespace(track_lin_vel=terms["track_lin_vel"],
                                                                  track_ang_vel=terms["track_ang_vel"]))
    plain = start(view, plan, tmp_path, 1)
    assert adj.apply_reward_params(env_cfg, plain) == {"track_lin_vel_std": {"before": 0.5, "after": 0.5},
                                                      "track_ang_vel_std": {"before": 0.5, "after": 0.5}}
    assert adj.apply_reward_params(env_cfg, None)["track_lin_vel_std"]["after"] == 0.5
    other = tmp_path / "adjusted"
    other.mkdir()
    asked = start(view, plan, other, 1, document(plan, b1=reward_entry()))
    assert adj.apply_reward_params(env_cfg, asked) == {"track_lin_vel_std": {"before": 0.5, "after": 0.35},
                                                      "track_ang_vel_std": {"before": 0.5, "after": 0.4}}
    assert terms["track_lin_vel"].params == {"std": 0.35, "command_name": "base_velocity"} and terms["track_lin_vel"].weight == 2.0


def test_the_live_reward_manager_is_read_back_and_must_carry_what_was_asked(plan, view, tmp_path, monkeypatch):
    monkeypatch.setenv("RANK", "1")
    monkeypatch.setenv("WORLD_SIZE", "2")
    asked = start(view, plan, tmp_path, 3, document(plan, b3=reward_entry()), write=False)
    manager, _ = _manager(lin=0.35, ang=0.4, air=0.2, slip=-0.2)
    env = types.SimpleNamespace(unwrapped=types.SimpleNamespace(reward_manager=manager))
    body = adj.write_reward_readback(env, asked, tmp_path)
    assert body["live"] == REWARDS and body["asked"] == REWARDS and body["source"] == "adjust_file" and body["entry"] == 3
    assert json.loads((tmp_path / "segment_rewards_b3_rank1.json").read_text(encoding="utf-8")) == body
    for wrong in (dict(lin=0.5), dict(ang=0.5), dict(air=0.0), dict(slip=-0.15)):
        manager, _ = _manager(**{**dict(lin=0.35, ang=0.4, air=0.2, slip=-0.2), **wrong})
        with pytest.raises(ValueError, match="the live reward manager carries"):
            adj.reward_readback(types.SimpleNamespace(reward_manager=manager), asked)
    plain = start(view, plan, tmp_path, 0, write=False)
    manager, _ = _manager()
    body = adj.write_reward_readback(types.SimpleNamespace(reward_manager=manager), plain, tmp_path)
    assert body["asked"] is None and body["live"]["foot_slip"] == -0.15 and body["source"] == "plan"
    assert not list(tmp_path.glob("segment_rewards_b0*"))                              # the first segment leaves none


def test_train_start_puts_the_widths_on_the_config_and_reads_the_manager_back_before_the_reset():
    text = (ROOT / "foothold_s2" / "scripts" / "train_start.py").read_text(encoding="utf-8")
    prepared = text.index('print("EX42_STAGE_ZERO_REWARD_CONFIG "')
    applied = text.index("_apply_reward_params(env_cfg, EX42_SEGMENT_COMMANDS)")
    read = text.index("env, EX42_SEGMENT_COMMANDS, EX42_RUN_LOG_DIR), sort_keys=True), flush=True)")
    assert prepared < applied < text.index("ex42_stage_zero_runtime = EX42StageZeroRuntime(") < read
    assert read < text.index("env.reset()", read) and "EX42_SEGMENT_COMMANDS = None" in text


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
    (lambda b: b["commands"]["ranges"].update(side_vy_abs=[0.1, 1.2]), "ranges"),
    (lambda b: b["commands"]["shares"].update(side_left=0.2), "shares"),
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


def test_gate_row_reads_only_the_records_of_its_own_stage(plan, view, tmp_path):
    start(view, plan, tmp_path, 1, document(plan, b1=entry(plan, **NARROW)))
    path = tmp_path / "segment_commands_b1.json"
    body = json.loads(path.read_text(encoding="utf-8"))
    body["commands"]["ranges"]["side_vy_abs"] = [0.1, 1.2]
    body["stage_id"] = "E1F"
    path.write_text(json.dumps(body), encoding="utf-8")
    assert verdict(tmp_path)["verdict"] == "NO_DATA"


def test_the_real_table_still_passes_the_e1_plan_gate():
    assert cpc.launch_gate("E1", PLAN)["passed"] is True


# ---- zero_yaw (decisions.tsv 2026-11-13 09:52): the weight on the yaw rate while the turn command is zero ----

def test_zero_yaw_reaches_the_stage_and_the_record(plan, view, tmp_path):
    before = dict(view.stages[0].rewards)
    assert before["zero_yaw"] == -0.5                                   # the plan value until an entry asks
    start(view, plan, tmp_path, 1)
    entry = reward_entry(track_lin_vel_std=0.5, track_ang_vel_std=0.5, feet_air_time=0.0, foot_slip=-0.15, zero_yaw=-1.0)
    record = start(view, plan, tmp_path, 2, document(plan, b2=entry))
    stage = view.stages[0]
    assert stage.rewards["zero_yaw"] == -1.0
    assert {k: v for k, v in stage.rewards.items() if k != "zero_yaw"} == {k: v for k, v in before.items() if k != "zero_yaw"}
    assert record["rewards"]["values"]["zero_yaw"] == -1.0 and record["rewards"]["entry"] == 2
    again = start(view, plan, tmp_path, 3, document(plan, b2=entry))       # the next segment carries the same file
    assert again["rewards"]["values"]["zero_yaw"] == -1.0 and view.stages[0].rewards["zero_yaw"] == -1.0
    for inside in (-2.0, -0.5):
        start(view, plan, tmp_path, 3, document(plan, b2=entry, b3=reward_entry(zero_yaw=inside)), write=False)
        assert view.stages[0].rewards["zero_yaw"] == inside


def test_the_shipped_zero_yaw_limits_are_the_ledger_row():
    text = adj.REWARD_LIMITS.read_text(encoding="utf-8")
    assert "zero_yaw: [-2.0, -0.5]" in text and "2026-11-13 09:52" in text and "c2032256" in text
    assert "pending" not in text


def test_the_live_zero_yaw_weight_is_read_back(plan, view, tmp_path):
    asked = start(view, plan, tmp_path, 3, document(plan, b3=reward_entry(zero_yaw=-1.5)), write=False)
    manager, _ = _manager(lin=0.35, ang=0.4, air=0.2, slip=-0.2, yaw=-1.5)
    body = adj.reward_readback(types.SimpleNamespace(reward_manager=manager), asked)
    assert body["live"]["zero_yaw"] == -1.5 and body["asked"]["zero_yaw"] == -1.5
    manager, _ = _manager(lin=0.35, ang=0.4, air=0.2, slip=-0.2, yaw=-0.5)           # the env was built with the plan weight
    with pytest.raises(ValueError, match="the live reward manager carries"):
        adj.reward_readback(types.SimpleNamespace(reward_manager=manager), asked)


# ---- the stage row's own reward cells (E1 again from m13250, 2026-11-13): in force from the first update ----

ROW_REWARDS = {"track_lin_vel_std": 0.35, "track_ang_vel_std": 0.5, "feet_air_time": 0.0, "foot_slip": -0.15, "zero_yaw": -1.0}


@pytest.fixture()
def row_plan():
    return EX42Plan.load(PLAN)                                   # the shipped plan, E1 row cell included


def row_view(row_plan):
    source = te.load_ex42_stage_zero_source(row_plan)
    return te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=row_plan,
                                             stage_id="E1")


def test_the_shipped_e1_row_registers_its_reward_cells_inside_the_limits(row_plan):
    assert next(r for r in row_plan.document["stages"] if r["id"] == "E1")["rewards"] == ROW_REWARDS
    assert adj.stage_rewards(row_plan, "E1") == ROW_REWARDS
    assert adj.stage_rewards(row_plan, "E1F") is None and adj.stage_rewards(row_plan, "E0") is None
    limits = adj.reward_limits()["cells"]
    assert all(limits[name][0] <= value <= limits[name][1] for name, value in ROW_REWARDS.items())


def test_the_row_cells_hold_from_the_first_update_and_reach_the_stage_the_env_config_and_the_readback(row_plan, tmp_path):
    view = row_view(row_plan)
    assert view.stages[0].rewards["zero_yaw"] == -0.5             # the source stage, before the row is applied
    record = adj.start_segment(view, row_plan, "E1", boundary_index=0, path=None, log_dir=str(tmp_path), write=True)
    assert record["rewards"] == {"source": "plan", "entry": None, "values": ROW_REWARDS, "decided_at": None, "reason": None,
                                 "evidence": None, "limits_sha256": adj.reward_limits()["sha256"]}
    assert view.stages[0].rewards["zero_yaw"] == -1.0 and view.stages[0].rewards["foot_slip"] == -0.15
    assert not list(tmp_path.glob("segment_commands_b0*"))       # the first segment leaves no record file
    _, terms = _manager()
    env_cfg = types.SimpleNamespace(rewards=types.SimpleNamespace(track_lin_vel=terms["track_lin_vel"],
                                                                  track_ang_vel=terms["track_ang_vel"]))
    assert adj.apply_reward_params(env_cfg, record)["track_lin_vel_std"] == {"before": 0.5, "after": 0.35}
    manager, _ = _manager(lin=0.35, ang=0.5, air=0.0, slip=-0.15, yaw=-1.0)
    assert adj.reward_readback(types.SimpleNamespace(reward_manager=manager), record)["live"] == ROW_REWARDS
    manager, _ = _manager(lin=0.35, ang=0.5, air=0.0, slip=-0.15, yaw=-0.5)      # the env was built on the source weight
    with pytest.raises(ValueError, match="the live reward manager carries"):
        adj.reward_readback(types.SimpleNamespace(reward_manager=manager), record)


def test_later_segments_keep_the_row_cells_until_an_entry_changes_them(row_plan, tmp_path):
    view = row_view(row_plan)
    first = adj.start_segment(view, row_plan, "E1", boundary_index=1, path=None, log_dir=str(tmp_path), write=True)
    assert first["rewards"]["values"] == ROW_REWARDS
    doc = {"schema": adj.SCHEMA, "stage_id": "E1", "plan_sha256": row_plan.sha256,
           "segments": {"2": {"decided_at": "t", "reason": "r", "evidence": "e", "rewards": {**ROW_REWARDS, "zero_yaw": -1.5}}}}
    path = tmp_path / "adjust.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    second = adj.start_segment(row_view(row_plan), row_plan, "E1", boundary_index=2, path=str(path),
                               log_dir=str(tmp_path), write=True)
    assert second["rewards"]["source"] == "adjust_file" and second["rewards"]["values"]["zero_yaw"] == -1.5
    # a start that claims segment 1 ran on other values is refused
    doc["segments"]["1"] = {"decided_at": "t", "reason": "r", "evidence": "e", "rewards": {**ROW_REWARDS, "foot_slip": -0.2}}
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="differs from what segment 1 ran with"):
        adj.start_segment(row_view(row_plan), row_plan, "E1", boundary_index=3, path=str(path), log_dir=str(tmp_path),
                          write=False)


@pytest.mark.parametrize("change, match", [
    ({"zero_yaw": -2.5}, "leaves the approved limits"), ({"track_lin_vel_std": 0.2}, "leaves the approved limits"),
    ({"extra": 1.0}, "rewards needs exactly"), ({"zero_yaw": "low"}, "rewards needs exactly"),
])
def test_a_row_cell_outside_the_limits_or_malformed_stops_the_start(row_plan, tmp_path, change, match):
    row = next(r for r in row_plan.document["stages"] if r["id"] == "E1")
    row["rewards"] = {**ROW_REWARDS, **change}
    with pytest.raises(ValueError, match=match):
        adj.start_segment(row_view(row_plan), row_plan, "E1", boundary_index=0, path=None, log_dir=str(tmp_path),
                          write=False)
    row.pop("rewards")
    with pytest.raises(ValueError, match="rewards needs exactly"):
        row["rewards"] = {k: v for k, v in ROW_REWARDS.items() if k != "zero_yaw"}
        adj.start_segment(row_view(row_plan), row_plan, "E1", boundary_index=0, path=None, log_dir=str(tmp_path),
                          write=False)


# ---- low_forward_fraction (2026-11-13): the share of forward commands drawn from the slow end, a cell outside the plan ----

LOW_NOTE = {"decided_at": "t", "reason": "slow forward commands are rarely drawn", "evidence": "boundary 250 sheet"}


def limits_with_low_forward(tmp_path, fence=(0.2, 0.4)):
    path = tmp_path / "limits_low.yaml"
    path.write_text(adj.REWARD_LIMITS.read_text(encoding="utf-8")
                    + f"command_cells:\n  low_forward_fraction: [{fence[0]}, {fence[1]}]\n", encoding="utf-8")
    return path


def start_low(view, plan, tmp_path, k, value, limits, write=True, **more):
    path = tmp_path / f"adjust_low_{k}.json"
    path.write_text(json.dumps(document(plan, **{f"b{more.pop('at', k)}": {**LOW_NOTE, "low_forward_fraction": value, **more}})),
                    encoding="utf-8")
    return adj.start_segment(view, plan, "E1", boundary_index=k, path=str(path), log_dir=str(tmp_path), write=write,
                             limits_path=limits)


def slow_forward_share(stage, n=400_000):
    import torch
    from foothold_s2.commands import mixed_core as mc
    out = mc.resample_stage(mc.make_generator(11), n, stage, torch.zeros(n))
    forward = out["slot"] == mc.EX39_SLOTS.index("forward")
    return (float((forward & (out["cmd"][:, 0] < 0.3)).float().mean()), float(forward.float().mean()), out)


def limits_without_command_cells(tmp_path):
    text = adj.REWARD_LIMITS.read_text(encoding="utf-8")
    path = tmp_path / "limits_closed.yaml"
    path.write_text(text[:text.index("command_cells:")], encoding="utf-8")
    assert adj.reward_limits(path)["command_cells"] == {}
    return path


def test_the_shipped_limits_open_low_forward_fraction_between_the_source_and_the_approved_value():
    """decisions.tsv 2026-11-13 15:17 (ledger commit a00ab2a8): 0.2 -> 0.4."""
    assert adj.reward_limits()["command_cells"] == {"low_forward_fraction": (0.2, 0.4)}


def test_without_the_command_cell_in_the_limits_file_an_entry_is_refused(plan, view, tmp_path):
    path = tmp_path / "adjust.json"
    path.write_text(json.dumps(document(plan, b1={**LOW_NOTE, "low_forward_fraction": 0.4})), encoding="utf-8")
    with pytest.raises(ValueError, match="no approved limits"):
        adj.start_segment(view, plan, "E1", boundary_index=1, path=str(path), log_dir=str(tmp_path), write=True,
                          limits_path=limits_without_command_cells(tmp_path))
    assert view.stages[0].low_forward_fraction == 0.2 and not list(tmp_path.glob("segment_commands_b*"))


def test_low_forward_fraction_reaches_the_sampler_and_the_record(plan, view, tmp_path):
    import torch
    from foothold_s2.curriculum import continuous
    before, forward_before, _ = slow_forward_share(view.stages[0])
    assert view.stages[0].low_forward_fraction == 0.2 and abs(before - 0.19 * 0.2) < 0.002      # 3.8 % of all commands
    record = start_low(view, plan, tmp_path, 1, 0.4, limits_with_low_forward(tmp_path))
    stage = view.stages[0]
    after, forward_after, out = slow_forward_share(stage)
    assert stage.low_forward_fraction == 0.4 and abs(after - 0.19 * 0.4) < 0.002                # 7.6 %
    assert abs(forward_after - forward_before) < 0.003                                          # the forward share itself stays
    assert record["low_forward_fraction"]["value"] == 0.4 and record["low_forward_fraction"]["entry"] == 1
    assert record["source"] == "plan" and record["commands"] == base(plan)                      # the 13-slot profile is the plan's
    assert json.loads((tmp_path / "segment_commands_b1.json").read_text(encoding="utf-8")) == record
    n = out["cmd"].shape[0]                                                                     # ranges unchanged: the step check holds
    bad = continuous.command_bad(out["cmd"], out["slot"], out["heading"], torch.zeros(n, dtype=torch.long),
                                 types.SimpleNamespace(stages=[stage]))
    assert not bool(bad.any())


def test_a_segment_without_the_cell_keeps_the_old_record_shape(plan, view, tmp_path):
    record = start(view, plan, tmp_path, 1)
    assert "low_forward_fraction" not in record and view.stages[0].low_forward_fraction == 0.2


@pytest.mark.parametrize("value", [0.41, 0.19, -0.1, 1.0, "0.4", None, True])
def test_low_forward_fraction_outside_the_limits_or_not_a_number_is_refused(plan, view, tmp_path, value):
    with pytest.raises(ValueError, match="low_forward_fraction must be a number inside the approved limits"):
        start_low(view, plan, tmp_path, 1, value, limits_with_low_forward(tmp_path))
    assert view.stages[0].low_forward_fraction == 0.2


def test_low_forward_fraction_only_where_commands_may_change(plan, view, tmp_path):
    limits = limits_with_low_forward(tmp_path)
    with pytest.raises(ValueError, match="may only name boundaries"):
        start_low(view, plan, tmp_path, 3, 0.4, limits)
    record = start_low(view, plan, tmp_path, 2, 0.3, limits)
    assert record["low_forward_fraction"]["entry"] == 2


def test_later_segments_keep_it_and_a_start_that_drops_it_is_refused(plan, source, tmp_path):
    limits = limits_with_low_forward(tmp_path)
    fresh = lambda: te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64},   # noqa: E731
                                                      ex42_plan=plan, stage_id="E1")
    start_low(fresh(), plan, tmp_path, 1, 0.4, limits)
    start_low(fresh(), plan, tmp_path, 2, 0.4, limits, at=1)                        # every segment leaves its record
    later = fresh()
    record = start_low(later, plan, tmp_path, 3, 0.4, limits, at=1)                 # segment 3, the entry of boundary 1 holds
    assert later.stages[0].low_forward_fraction == 0.4 and record["low_forward_fraction"]["entry"] == 1
    with pytest.raises(ValueError, match="differs from what segment 1 ran with"):  # the file no longer names it
        adj.start_segment(fresh(), plan, "E1", boundary_index=3, path=None, log_dir=str(tmp_path), write=True,
                          limits_path=limits)


def test_a_limits_file_with_a_bad_command_cell_is_refused(tmp_path):
    for fence in ((0.4, 0.2), (-0.1, 0.4), (0.2, 1.1)):
        with pytest.raises(ValueError, match="command_cells may hold"):
            adj.reward_limits(limits_with_low_forward(tmp_path, fence))
    bad = tmp_path / "other.yaml"
    bad.write_text(adj.REWARD_LIMITS.read_text(encoding="utf-8") + "command_cells:\n  other_cell: [0.1, 0.2]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="command_cells may hold"):
        adj.reward_limits(bad)


# ---- the stage row's own low_forward_fraction (decisions.tsv 2026-11-13 15:17): in force from the first update ----

def test_the_shipped_e1_row_registers_low_forward_fraction_inside_the_limits(row_plan):
    assert next(r for r in row_plan.document["stages"] if r["id"] == "E1")["low_forward_fraction"] == 0.4
    assert adj.stage_low_forward(row_plan, "E1") == 0.4
    assert adj.stage_low_forward(row_plan, "E1F") is None and adj.stage_low_forward(row_plan, "E0") is None


def test_the_row_share_holds_from_the_first_update_and_reaches_the_sampler(row_plan, tmp_path):
    view = row_view(row_plan)
    assert view.stages[0].low_forward_fraction == 0.2                       # the source stage, before the row is applied
    record = adj.start_segment(view, row_plan, "E1", boundary_index=0, path=None, log_dir=str(tmp_path), write=True)
    assert record["low_forward_fraction"] == {"source": "plan", "entry": None, "value": 0.4, "decided_at": None,
                                              "reason": None, "evidence": None,
                                              "limits_sha256": adj.reward_limits()["sha256"]}
    slow, forward, _ = slow_forward_share(view.stages[0])
    assert view.stages[0].low_forward_fraction == 0.4 and abs(slow - 0.19 * 0.4) < 0.002 and abs(forward - 0.19) < 0.003
    assert not list(tmp_path.glob("segment_commands_b0*"))                  # the first segment leaves no record file


def test_the_row_share_stays_in_later_segments_and_in_their_records(row_plan, tmp_path):
    for k in (1, 2, 3):
        view = row_view(row_plan)
        record = adj.start_segment(view, row_plan, "E1", boundary_index=k, path=None, log_dir=str(tmp_path), write=True)
        assert view.stages[0].low_forward_fraction == 0.4 and record["low_forward_fraction"]["source"] == "plan"
        assert json.loads((tmp_path / f"segment_commands_b{k}.json").read_text(encoding="utf-8")) == record


def test_a_row_share_outside_the_limits_or_without_the_limits_cell_is_refused(row_plan, tmp_path):
    import copy as _copy
    from dataclasses import replace
    broken = replace(row_plan, document=_copy.deepcopy(row_plan.document))
    next(r for r in broken.document["stages"] if r["id"] == "E1")["low_forward_fraction"] = 0.5
    with pytest.raises(ValueError, match="E1 plan row low_forward_fraction must be a number inside the approved limits"):
        adj.start_segment(row_view(row_plan), broken, "E1", boundary_index=0, path=None, log_dir=str(tmp_path), write=True)
    with pytest.raises(ValueError, match="no approved limits"):
        adj.start_segment(row_view(row_plan), row_plan, "E1", boundary_index=0, path=None, log_dir=str(tmp_path), write=True,
                          limits_path=limits_without_command_cells(tmp_path))


def test_the_live_objects_keep_the_share(row_plan, tmp_path):
    """E1 has no flag split, so the live sampler draws from the plan view's stage itself. A stage with a flag split
    draws free commands from `CommandShares.free_stage`: the real object must carry the share over."""
    from dataclasses import replace
    from foothold_s2.commands import ex42_shares
    view = row_view(row_plan)
    adj.start_segment(view, row_plan, "E1", boundary_index=0, path=None, log_dir=str(tmp_path), write=True)
    assert view.command_contract is None and view.stages[0].low_forward_fraction == 0.4
    source = te.load_ex42_stage_zero_source(row_plan)
    flagged = te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=row_plan,
                                                stage_id="E1F")
    assert flagged.command_contract is not None and flagged.stages[0].low_forward_fraction == 0.2   # E1F row: no cell
    free = ex42_shares.CommandShares(flagged.command_contract, replace(flagged.stages[0], low_forward_fraction=0.4)).free_stage
    slow, forward, _ = slow_forward_share(free)
    assert free.low_forward_fraction == 0.4 and abs(slow - forward * 0.4) < 0.002
