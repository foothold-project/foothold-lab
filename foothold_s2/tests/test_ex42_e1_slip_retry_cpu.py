"""The E1 foot_slip retry cell: the finished E1 (EX-42-B-E1_20261111_114505, foot_slip 0.0) is the control and the
retry differs from it by that one reward weight (CPU only, nothing starts)."""
from __future__ import annotations

import copy
import pathlib
import sys
import types
from dataclasses import replace

import pytest
import yaml

from foothold_s2.curriculum.ex42_prep import EX42Plan, validate_stage_e1_authorization
from foothold_s2.scripts import ex42_training_entry as entry
from foothold_s2.tools import ex42_make_e1_slip_retry as maker

ROOT = pathlib.Path(__file__).resolve().parents[2]
CUR = ROOT / "foothold_s2" / "curriculum"
BASE_PLAN, BASE_APPROVALS = CUR / maker.BASE_PLAN, CUR / maker.BASE_APPROVALS
RETRY_PLAN, RETRY_APPROVALS = CUR / maker.RETRY_PLAN, CUR / maker.RETRY_APPROVALS
CONTROL_ENV = pathlib.Path("/home/jay/data/foothold/s2_lab/ex42_main_20261111_114505/main/EX-42-B-E1_20261111_114505/params/env.yaml")
needs_control = pytest.mark.skipif(not CONTROL_ENV.is_file(), reason="the finished E1 run is not on this machine")
E0_RUN = pathlib.Path("/home/jay/data/foothold/s2_lab/ex42_main_20261111_072218/main/EX-42-B-E0_20261111_072218")
needs_e0 = pytest.mark.skipif(not (E0_RUN / "model_250.pt").is_file(), reason="the E0 run is not on this machine")


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8-sig"))


def _diff(a, b, path=""):
    """Every dotted path whose value differs (lists are compared whole, by index when they have the same length)."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for key in sorted(set(a) | set(b), key=str):
            out += _diff(a.get(key, "<absent>"), b.get(key, "<absent>"), f"{path}.{key}" if path else str(key))
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += _diff(x, y, f"{path}[{i}]")
        return out
    return [] if a == b else [path]


def test_the_committed_retry_files_are_what_the_tool_builds_from_the_shipped_pair():
    plan_text, approvals_text = maker.build()
    assert RETRY_PLAN.read_text(encoding="utf-8") == plan_text
    assert RETRY_APPROVALS.read_text(encoding="utf-8") == approvals_text        # a prep change needs the tool run again


def test_the_retry_plan_differs_from_the_shipped_plan_by_the_one_reward_and_its_bookkeeping_only():
    changed = _diff(_load(BASE_PLAN), _load(RETRY_PLAN))
    assert sorted(changed) == sorted([
        "approval_file", "stage_zero.approval_sha256",
        "stages[1].reward_overrides", "stages[1].retry_of"]), changed
    row = next(r for r in _load(RETRY_PLAN)["stages"] if r["id"] == "E1")
    assert row["reward_overrides"] == {"foot_slip": -0.25} and row["retry_of"]["control_run"] == "EX-42-B-E1_20261111_114505"
    base_row = next(r for r in _load(BASE_PLAN)["stages"] if r["id"] == "E1")
    assert row["parent"] == base_row["parent"] and row["parent"]["sha256"] == entry.E1_PARENT_SHA256
    assert (row["parent"]["cumulative_update"], row["parent"]["manifest_local_update"]) == (13250, 250)


def test_the_retry_approvals_differ_from_the_shipped_ones_in_the_closed_e1_cell_only():
    changed = _diff(_load(BASE_APPROVALS), _load(RETRY_APPROVALS))
    assert changed and all(p.startswith("stage_e1_authorization.") for p in changed), changed
    cell = _load(RETRY_APPROVALS)["stage_e1_authorization"]
    assert cell["approved"] is False and cell["decision_id"] is None and cell["approver"] is None
    assert cell["scope"] == _load(BASE_APPROVALS)["stage_e1_authorization"]["scope"]       # same parent, same bounds
    plan = EX42Plan.load(RETRY_PLAN)
    with pytest.raises(ValueError, match="authorization is missing"):
        validate_stage_e1_authorization(plan, RETRY_APPROVALS, entry.E1_PARENT_SHA256)    # nothing can start before the cell is filled
    assert _load(RETRY_PLAN)["stage_zero"]["approval_sha256"] == __import__("hashlib").sha256(RETRY_APPROVALS.read_bytes()).hexdigest()


def test_the_retry_plan_loads_and_its_stage_table_is_the_shipped_one():
    retry, base = EX42Plan.load(RETRY_PLAN), EX42Plan.load(BASE_PLAN)
    assert retry.reward_overrides("E1") == {"foot_slip": -0.25} and base.reward_overrides("E1") == {}
    assert all(retry.reward_overrides(s) == {} for s in retry.runtime_stage_ids if s != "E1")
    assert entry.e_stage_table(retry.document["stages"]) == entry.e_stage_table(base.document["stages"])
    assert retry.sha256 != base.sha256 and retry.runtime_stage_ids == base.runtime_stage_ids


@pytest.mark.parametrize("edit,match", [
    (lambda r: r.update(reward_overrides={"foot_slip": -0.25, "swing": -0.5}), "only a foot_slip"),
    (lambda r: r.update(reward_overrides={"swing": -0.5}), "only a foot_slip"),
    (lambda r: r.update(reward_overrides={"foot_slip": 0.25}), "only a foot_slip"),
    (lambda r: r.update(reward_overrides={"foot_slip": float("nan")}), "only a foot_slip"),
    (lambda r: r.update(reward_overrides={"foot_slip": -1.5}), "only a foot_slip"),
    (lambda r: r.pop("retry_of"), "retry_of"),
    (lambda r: r.update(retry_of={"control_run": ""}), "retry_of")])
def test_a_reward_override_without_its_control_or_with_more_than_the_one_weight_is_refused(tmp_path, edit, match):
    doc = _load(RETRY_PLAN)
    edit(next(r for r in doc["stages"] if r["id"] == "E1"))
    for source in CUR.iterdir():
        if source.is_file():
            (tmp_path / source.name).write_bytes(source.read_bytes())
    (tmp_path / RETRY_PLAN.name).write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        EX42Plan.load(tmp_path / RETRY_PLAN.name)


def _view(plan, overrides):
    from foothold_s2.curriculum.continuous import load_plan
    source = load_plan(plan.path.parent / plan.document["stage_zero"]["source"]["path"], arm="B")
    stage = next(r for r in source.stages if r.id == "T0_prime")
    return source, stage, entry.make_ex42_stage_zero_plan_view(source, stage, {"parent_sha256": entry.E1_PARENT_SHA256},
                                                               parent_update=250, reward_overrides=overrides)


def test_the_plan_view_changes_the_foot_slip_weight_and_no_other_weight():
    retry, base = EX42Plan.load(RETRY_PLAN), EX42Plan.load(BASE_PLAN)
    _, stage, shipped = _view(base, base.reward_overrides("E1"))
    _, _, changed = _view(retry, retry.reward_overrides("E1"))
    assert shipped.stages[0].rewards == stage.rewards and stage.rewards["foot_slip"] == 0.0
    assert {k for k in stage.rewards if changed.stages[0].rewards[k] != stage.rewards[k]} == {"foot_slip"}
    assert changed.stages[0].rewards["foot_slip"] == -0.25 and set(changed.stages[0].rewards) == set(stage.rewards)
    assert changed.stages[0] is not stage and stage.rewards["foot_slip"] == 0.0           # the shared EX-41 stage is not mutated
    with pytest.raises(ValueError, match="does not have"):
        _view(retry, {"no_such_weight": -1.0})


def _registered_rewards(view, monkeypatch):
    """The real w86_runtime.prepare_env_cfg on a stand-in env cfg (Isaac Lab is not importable without Kit)."""
    from foothold_s2.rewards import w86_runtime
    managers = types.ModuleType("isaaclab.managers")
    for name in ("RewardTermCfg", "TerminationTermCfg", "EventTermCfg"):
        setattr(managers, name, lambda **kw: types.SimpleNamespace(**kw))
    monkeypatch.setitem(sys.modules, "isaaclab", types.ModuleType("isaaclab"))
    monkeypatch.setitem(sys.modules, "isaaclab.managers", managers)
    term = lambda w: types.SimpleNamespace(weight=w)                                              # noqa: E731
    cfg = types.SimpleNamespace(
        rewards=types.SimpleNamespace(collision=term(-10.0), action_smoothness=term(-0.01), joint_power=term(-2e-5),
                                      stumble=term(-1.0)),
        terminations=types.SimpleNamespace(), events=types.SimpleNamespace())
    w86_runtime.prepare_env_cfg(cfg, view)
    return {name: getattr(term, "weight") for name, term in vars(cfg.rewards).items()}


def test_the_registered_reward_weights_of_the_retry_differ_from_the_shipped_ones_in_foot_slip_only(monkeypatch):
    retry, base = EX42Plan.load(RETRY_PLAN), EX42Plan.load(BASE_PLAN)
    shipped = _registered_rewards(_view(base, base.reward_overrides("E1"))[2], monkeypatch)
    changed = _registered_rewards(_view(retry, retry.reward_overrides("E1"))[2], monkeypatch)
    assert set(shipped) == set(changed) and shipped["ex41_foot_slip"] == 0.0
    assert {k for k in changed if changed[k] != shipped[k]} == {"ex41_foot_slip"} and changed["ex41_foot_slip"] == -0.25


class _Loose(yaml.SafeLoader):
    pass


_Loose.add_multi_constructor("tag:yaml.org,2002:python/", lambda loader, suffix, node: (
    loader.construct_sequence(node, deep=True) if isinstance(node, yaml.SequenceNode) else
    loader.construct_mapping(node, deep=True) if isinstance(node, yaml.MappingNode) else loader.construct_scalar(node)))


@needs_control
def test_the_retry_rewards_equal_the_finished_e1_runs_env_yaml_key_by_key_except_foot_slip(monkeypatch):
    control = yaml.load(CONTROL_ENV.read_text(encoding="utf-8"), Loader=_Loose)["rewards"]
    retry = EX42Plan.load(RETRY_PLAN)
    built = _registered_rewards(_view(retry, retry.reward_overrides("E1"))[2], monkeypatch)
    ran = {name: spec["weight"] for name, spec in control.items()}
    assert ran["ex41_foot_slip"] == 0.0                                                         # the control ran without the penalty
    # every term this code path registers or sets is compared with what the control run really had
    assert set(built) <= set(ran), sorted(set(built) - set(ran))
    assert {k for k in built if built[k] != ran[k]} == {"ex41_foot_slip"}
    assert built["ex41_foot_slip"] == -0.25


@needs_e0
def test_the_control_run_directory_is_never_reused_and_a_closed_cell_starts_nothing(tmp_path):
    from foothold_s2.tests.test_ex42_e1_entry_cpu import _cli
    parent = E0_RUN / "model_250.pt"
    args = _cli(tmp_path, parent, plan_path=RETRY_PLAN, approvals_path=RETRY_APPROVALS)
    with pytest.raises(ValueError, match="authorization is missing"):
        entry.validate_ex42_stage_e_cli(**args)
    cell = _load(RETRY_APPROVALS)
    cell["stage_e1_authorization"].update(approved=True, decision_id="test-only", approved_at="2026-11-12T00:00+09:00", approver="test")
    cell["stage_e1_authorization"]["decision_source"] = {"commit": "0" * 40}
    opened = tmp_path / "opened.yaml"
    opened.write_text(yaml.safe_dump(cell, sort_keys=False, allow_unicode=True), encoding="utf-8")
    existing = tmp_path / "finished_e1_run"
    existing.mkdir()                                                                            # stands in for the control run directory
    with pytest.raises(ValueError, match="output must be new"):
        entry.validate_ex42_stage_e_cli(**(args | {"approvals_path": opened, "log_dir": existing}))


def test_train_start_gives_the_plan_view_the_stages_reward_overrides():
    source = (ROOT / "foothold_s2" / "scripts" / "train_start.py").read_text(encoding="utf-8")
    assert "reward_overrides=EX42_STAGE_ZERO_PLAN.reward_overrides(EX42_STAGE_ID)" in source
    assert source.index("reward_overrides=EX42_STAGE_ZERO_PLAN.reward_overrides") < source.index("prepare_ex41_env_cfg(")
