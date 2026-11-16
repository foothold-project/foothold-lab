"""v29-11: the E1F plan row carries the four low-speed devices E1 trains with (lead 2026-11-15 22:46, planner work table 22:45)."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.ex42_live_adjust import limits_from_plan, read_request
from foothold_s2.rewards.ex42_slow_track import configure_from_plan
from foothold_s2.scripts import ex42_stage_launcher as L
from foothold_s2.tests.test_ex42_stage_launcher_cpu import _env

PLAN = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml"


def _rows():
    plan = EX42Plan.load(PLAN)
    by = {r["id"]: r for r in plan.document["stages"]}
    return plan, by["E1"], by["E1F"]


def test_the_e1f_row_has_the_e1_live_blocks_and_only_the_start_weight_differs():
    plan, e1, e1f = _rows()
    # E1F new composition (2026-11-16): the only difference is the low_side_fraction fence in command_limits (the limits file stays byte for byte)
    # and (2026-11-16 15:20) the two reward fences the row widens: slow_track_sigma [0.35, 0.5] and slow_progress [0.0, 0.6] (E1's are [0.5, 0.5] and the file's)
    e1f_live = {**e1f["live_adjustment"], "command_limits": dict(e1f["live_adjustment"]["command_limits"]),
                "extra_reward_limits": dict(e1f["live_adjustment"]["extra_reward_limits"])}
    assert e1f_live["command_limits"].pop("low_side_fraction") == [0.0, 0.5]
    assert e1f_live["extra_reward_limits"].pop("slow_track_sigma") == [0.35, 0.5]
    assert e1f_live["extra_reward_limits"].pop("slow_progress") == [0.0, 0.6]
    e1_live = {**e1["live_adjustment"], "extra_reward_limits": dict(e1["live_adjustment"]["extra_reward_limits"])}
    assert e1_live["extra_reward_limits"].pop("slow_track_sigma") == [0.5, 0.5] and "slow_progress" not in e1_live["extra_reward_limits"]
    assert e1f_live == e1_live
    assert {k: v for k, v in e1f["live_monitor"].items() if k != "initial_slow_track_weight"} == \
        {k: v for k, v in e1["live_monitor"].items() if k != "initial_slow_track_weight"}
    assert e1["live_monitor"]["initial_slow_track_weight"] == 0.2 and e1f["live_monitor"]["initial_slow_track_weight"] == 0.3
    assert e1f["slow_track_heading"] is True and e1f["low_forward_fraction"] == 0.5
    assert e1f["live_adjustment"]["runtime_start"] == {"policy_std_cap": 0.0}          # the code refuses a non-zero start from the plan


def test_the_slow_track_term_starts_at_the_e1f_weight_with_heading_envs_counted():
    _, _, e1f = _rows()

    class Term:
        def __init__(self, *, func, weight, params):
            self.func, self.weight, self.params = func, weight, params

    env_cfg = SimpleNamespace(rewards=SimpleNamespace())
    assert configure_from_plan(env_cfg, e1f, Term) == {"weight": 0.3, "include_heading": True}


def test_the_e1f_limits_load_and_an_e1f_adjust_file_with_the_std_cap_is_read_at_update_1():
    plan, _, e1f = _rows()
    limits = limits_from_plan(e1f["live_adjustment"])
    assert limits["runtime"]["policy_std_cap"] == (0.0, 2.0) and limits["commands"]["low_forward_fraction"] == (0.2, 0.5)
    sha = plan.sha256 if hasattr(plan, "sha256") else None
    assert sha is not None and len(sha) == 64
    doc = {"schema": "ex42-update-adjust/1", "stage_id": "E1F", "plan_sha256": sha,
           "changes": {"1": {"decided_by": "test", "decided_at": "2026-11-15 22:46", "evidence": "test",
                             "runtime": {"policy_std_cap": 0.48}}}}
    raw = json.dumps(doc).encode()
    entry, parsed = read_request(raw, stage_id="E1F", plan_sha256=sha, iteration=1, limits=limits)
    assert parsed["runtime"] == {"policy_std_cap": 0.48}
    assert read_request(raw, stage_id="E1F", plan_sha256=sha, iteration=2, limits=limits) is None
    with pytest.raises(ValueError, match="identity differs"):                            # the file is bound to the stage and to this plan
        read_request(raw, stage_id="E1", plan_sha256=sha, iteration=1, limits=limits)
    with pytest.raises(ValueError, match="identity differs"):
        read_request(raw, stage_id="E1F", plan_sha256="0" * 64, iteration=1, limits=limits)
    with pytest.raises(ValueError, match="outside approved limit"):
        read_request(raw.replace(b"0.48", b"2.5"), stage_id="E1F", plan_sha256=sha, iteration=1, limits=limits)


def test_the_launcher_hands_ex42_update_adjust_on_to_the_stage_it_starts_and_drops_only_the_segment_adjust(tmp_path):
    # E1F is not in the raw plan's stage table (materialize adds it), so the environment hand-over is shown on E1; the code path is the same for every stage
    env = {**_env(tmp_path), "EX42_UPDATE_ADJUST": "/adj/update-adjust-e1f.json", "EX42_SEGMENT_ADJUST": "/adj/segment.json"}
    _, child, _ = L.build(env, now=0)
    assert child["EX42_UPDATE_ADJUST"] == "/adj/update-adjust-e1f.json"
    assert "EX42_SEGMENT_ADJUST" not in child                                           # belongs to the stage that is running, never to a fresh start
    cont = {**_env(tmp_path, action="continue"), "EX42_UPDATE_ADJUST": "/adj/u.json", "EX42_SEGMENT_ADJUST": "/adj/s.json"}
    _, child, _ = L.build(cont)
    assert child["EX42_UPDATE_ADJUST"] == "/adj/u.json" and child["EX42_SEGMENT_ADJUST"] == "/adj/s.json"
