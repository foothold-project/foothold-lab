"""EX-42 M map-off branch: fixed-level cells, entry, publication, boundaries, return, hand-off wiring. CPU only.

Fixtures are built inside the tests from the real plan and approvals (copies in tmp_path): the plan's M contract lists
the approved sources there, which the real plan leaves empty."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest
import yaml

from foothold_s2 import ex42_late_exit_judges as late
from foothold_s2 import ex42_map_off_branch as mob
from foothold_s2 import ex42_stage_handoff as handoff
from foothold_s2.commands.ex42_shares import read_contract
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.eval import ex42_map_off_cells as cells

REAL = Path(__file__).resolve().parents[1] / "curriculum"
SHA = "b" * 64
MESH = "c" * 64


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _records(alive: int):
    return [{"env": i, "alive": i < alive} for i in range(64)]


def _raw(gt=64, off=58, *, levels=("L3", "L6", "L9")):
    return {level: {"eval_gt": _records(gt), "map_off": _records(off)} for level in levels}


def _build(raw, checkpoint=SHA, stage="E4", iteration=500, plan_sha="d" * 64):
    return cells.build_cells(raw, checkpoint_sha256=checkpoint, plan_sha256=plan_sha, mesh_sha256=MESH,
                             stage_id=stage, boundary_iteration=iteration)


def _write(folder, row) -> Path:
    return cells.write_cells(folder, row)


@pytest.fixture
def world(tmp_path):
    """A template curriculum folder whose M contract approves E1F and E4, each source row carrying a parent pin."""
    template = tmp_path / "template"
    shutil.copytree(REAL, template, ignore=shutil.ignore_patterns("__pycache__", "*.py"))
    doc = yaml.safe_load((template / "ex42-prep.yaml").read_text(encoding="utf-8"))
    for row in doc["stages"]:
        if row["id"] == "M":
            row["authorization_contract"]["source_stage_ids"] = ["E1F", "E4"]
        if row["id"] in ("E1F", "E4"):
            row["parent"] = {"source_stage_id": "E1", "cumulative_update": 1000}
    (template / "ex42-prep.yaml").write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return SimpleNamespace(tmp=tmp_path, template=template, plan=template / "ex42-prep.yaml",
                           approvals=template / "ex42-approvals.yaml", doc=doc)


def _enter(world, source="E4", gap=7, **kw):
    world.count = getattr(world, "count", 0) + 1
    folder = world.tmp / f"b_{source}_{gap}_{world.count}"
    cells_path = _write(folder, _build(_raw(64, 64 - gap), stage=source, plan_sha=EX42Plan.load(world.plan).sha256))
    args = dict(plan_path=world.plan, approvals_path=world.approvals, source_stage_id=source, cells_path=cells_path,
                checkpoint_sha256=SHA, source_iteration=500, changed_axes=[], budget_limit=20000, budget_used=3000,
                out=world.tmp / f"M_{source}_{gap}_{world.count}")
    args.update(kw)
    return mob.publish_entry(**args)


# ---- fixed-level raw -> cells file --------------------------------------------------------------------------------------
@pytest.mark.parametrize("off,expected", [(58, "PASS"), (57, "FAIL"), (64, "PASS")])
def test_gt64_with_off58_passes_and_off57_fails_through_the_written_file(tmp_path, off, expected):
    path = _write(tmp_path, _build(_raw(64, off)))
    row = json.loads(path.read_text())                                    # the judge reads the file back, not the dict
    assert late.mapoff_window(row)["judgement"] == expected


@pytest.mark.parametrize("break_raw", [
    lambda raw: raw.pop("L9"),                                            # a level missing
    lambda raw: raw.update(L12=raw["L9"]),                                # a level that is not fixed
    lambda raw: raw["L6"].pop("map_off"),                                 # a mode missing
    lambda raw: raw["L6"]["map_off"].pop(),                               # 63 envs
    lambda raw: raw["L6"]["map_off"].__setitem__(5, {"env": 4, "alive": True}),   # duplicate env id
    lambda raw: raw["L3"]["eval_gt"].__setitem__(2, {"env": 2, "alive": 1}),      # not a real bool
    lambda raw: raw["L3"]["eval_gt"].__setitem__(2, {"env": 2, "alive": True, "x": float("nan")}),
    lambda raw: raw["L3"]["eval_gt"].__setitem__(2, {"env": 99, "alive": True}),
])
def test_cells_builder_refuses_missing_duplicate_wrong_size_and_nan(break_raw):
    raw = _raw()
    break_raw(raw)
    with pytest.raises(ValueError):
        _build(raw)


def test_cells_file_counts_must_match_its_raw_and_checkpoint(tmp_path):
    path = _write(tmp_path, _build(_raw(64, 58)))
    row = json.loads(path.read_text())
    row["levels"]["L3"]["map_off_alive"] = 64                              # counts edited, raw untouched
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError):
        cells.read_cells(path, checkpoint_sha256=SHA)
    with pytest.raises(ValueError):
        late.mapoff_window(row)                                            # the judge recounts producer files too
    path2 = _write(tmp_path / "two", _build(_raw()))
    with pytest.raises(ValueError):
        cells.read_cells(path2, checkpoint_sha256="e" * 64)                # another saved checkpoint
    assert cells.read_cells(tmp_path / "none.json", checkpoint_sha256=SHA) is None


# ---- entry ----------------------------------------------------------------------------------------------------------
def test_real_plan_approves_no_source_so_every_entry_is_refused(tmp_path):
    doc = yaml.safe_load((REAL / "ex42-prep.yaml").read_text(encoding="utf-8"))
    assert mob.approved_sources(doc) == []
    with pytest.raises(ValueError, match="not approved"):
        mob.entry_decision(doc, "E4", tmp_path / "x.json", checkpoint_sha256=SHA, changed_axes=[])


@pytest.mark.parametrize("gap,axes,action,state", [
    (7, [], "enter", "map_off_below_gt"), (6, [], "no_entry", "map_off_within_limit"),
    (7, ["terrain_exposure"], "no_entry", "other_axis_changed"), (7, ["map_off_probability"], "enter", "map_off_below_gt"),
    (7, None, "hold", "axis_change_unknown")])
def test_entry_condition_truth_table(world, gap, axes, action, state):
    path = _write(world.tmp / "c", _build(_raw(64, 64 - gap)))
    got = mob.entry_decision(world.doc, "E4", path, checkpoint_sha256=SHA, changed_axes=axes)
    assert (got["action"], got["state"]) == (action, state)


def test_one_low_level_is_enough_and_missing_or_foreign_evidence_is_never_an_entry(world):
    raw = _raw(64, 64)
    raw["L9"]["map_off"] = _records(50)
    path = _write(world.tmp / "c", _build(raw, stage="E1F"))
    one = mob.entry_decision(world.doc, "E1F", path, checkpoint_sha256=SHA, changed_axes=[])
    assert one["gaps_envs"] == {"L3": 0, "L6": 0, "L9": 14} and one["action"] == "enter"     # one level, not all three
    missing = mob.entry_decision(world.doc, "E4", world.tmp / "none.json", checkpoint_sha256=SHA, changed_axes=[])
    foreign = mob.entry_decision(world.doc, "E4", path, checkpoint_sha256="f" * 64, changed_axes=[])
    wrong_stage = mob.entry_decision(world.doc, "E1F", path, checkpoint_sha256=SHA, changed_axes=[], plan_sha256="1" * 64)
    assert [x["action"] for x in (missing, foreign, wrong_stage)] == ["hold"] * 3
    with pytest.raises(ValueError, match="not approved"):
        mob.entry_decision(world.doc, "E2", path, checkpoint_sha256=SHA, changed_axes=[])


# ---- publication: two real source shapes ---------------------------------------------------------------------------
@pytest.mark.parametrize("source", ["E1F", "E4"])
def test_entry_pair_keeps_the_sources_commands_shares_terrain_and_loads(world, source):
    made = _enter(world, source)
    plan = EX42Plan.load(made["plan"])
    row = next(r for r in plan.document["stages"] if r["id"] == "M")
    origin = next(r for r in world.doc["stages"] if r["id"] == source)
    assert row["enabled"] is True and row["p_map_off"]["continuous"] == 0.3
    assert row["commands"] == origin["commands"] and row["shares"] == origin["shares"]
    assert row["terrain"]["exposure_at_M"] == origin["terrain"][f"exposure_at_{source}"]       # not M's placeholder
    assert row["terrain"].get("k_ladder") == origin["terrain"].get("k_ladder")
    assert row["parent"]["sha256"] == SHA and row["parent"]["cumulative_update"] == 1500
    assert row["branch_origin"]["stage_id"] == source
    assert read_contract(plan, "M")["shares"] == origin["shares"]                              # the real consumer accepts it
    cell = yaml.safe_load(Path(made["approvals"]).read_text())["stage_m_authorization"]
    assert cell["scope"]["maximum_updates"] == 500 and cell["scope"]["later_stages_authorized"] is False
    assert cell["prerequisites"]["branch_origin_stage_id"] == source == cell["prerequisites"]["return_stage_id"]
    assert cell["prerequisites"]["entry_condition_receipt_sha256"] == made["entry"]["cells_sha256"]
    transition = json.loads((Path(made["folder"]) / mob.TRANSITION).read_text())
    assert transition["budget"]["reserved"] == 1000 and transition["budget"]["m_counts_toward_source_maximum"] is False
    assert transition["plan_sha256"] == _sha(Path(made["plan"]).read_bytes())


def test_entry_publication_refuses_unmet_condition_unapproved_source_budget_and_second_try(world):
    made = _enter(world, "E4")
    with pytest.raises(FileExistsError):                                    # the same boundary again: one pair only
        _enter(world, "E4", out=made["folder"])
    with pytest.raises(ValueError, match="not met"):
        _enter(world, "E1F", gap=6)
    with pytest.raises(ValueError, match="not met"):
        _enter(world, "E1F", gap=7, changed_axes=["terrain_exposure"], out=world.tmp / "o2")
    with pytest.raises(ValueError, match="not approved"):
        _enter(world, "E2", out=world.tmp / "o3")
    with pytest.raises(ValueError, match="budget"):
        _enter(world, "E4", gap=7, budget_used=19500, out=world.tmp / "o4")
    broken = yaml.safe_load(world.approvals.read_text())
    broken["stage_m_authorization"]["approved"] = False
    other = world.tmp / "approvals_unapproved.yaml"
    other.write_text(yaml.safe_dump(broken, sort_keys=False, allow_unicode=True))
    with pytest.raises(ValueError, match="approval cell"):
        _enter(world, "E4", approvals_path=other, out=world.tmp / "o5")
    widened = yaml.safe_load(world.approvals.read_text())
    widened["stage_m_authorization"]["scope"]["maximum_updates"] = 900
    other.write_text(yaml.safe_dump(widened, sort_keys=False, allow_unicode=True))
    with pytest.raises(ValueError, match="approval cell"):
        _enter(world, "E4", approvals_path=other, out=world.tmp / "o6")


def test_a_source_without_commands_or_terrain_is_refused_rather_than_borrowed_from_m(world):
    doc = deepcopy(world.doc)
    next(r for r in doc["stages"] if r["id"] == "E4")["terrain"].pop("exposure_at_E4")
    with pytest.raises(ValueError, match="nothing to inherit"):
        mob.pin_source(doc, "E4")


# ---- M boundaries ----------------------------------------------------------------------------------------------------
def _run(world, source="E4"):
    made = _enter(world, source)
    run = world.tmp / f"run_{source}"
    run.mkdir()
    return SimpleNamespace(made=made, plan=Path(made["plan"]), p1=run / "p1_score.json", n=[0],
                           out=lambda: world.tmp / f"ret_{source}_{len(list(world.tmp.glob('ret_*')))}")


def _boundary(world, r, it, verdict, **kw):
    kw.setdefault("return_out", r.out())
    return mob.decide_m_boundary(r.plan, r.p1, it, verdict, **kw)


def test_pass_returns_to_the_entry_stage_with_p_map_off_kept_and_nothing_counted_on_the_source(world):
    r = _run(world, "E1F")
    got = _boundary(world, r, 250, "PASS")
    assert (got["action"], got["target_stage"], got["return_to"], got["m_state"]) == ("launch", "E1F", "E1F", "m_exit_pass")
    assert got["p_map_off"] == 0.3 and got["source_windows_counted_after_return"] == 0
    assert got["required_new_windows_after_return"] == 2 and got["notification_required"] is False
    assert got["budget"] == {"m_updates": 250, "ex42_budget_used_after": 3250, "source_stage_updates_counted": 500,
                             "m_updates_count_toward_source_maximum": False, "m_updates_count_toward_ex42_budget": True}
    back = yaml.safe_load(Path(got["plan"]).read_text())
    row = next(x for x in back["stages"] if x["id"] == "E1F")
    assert row["p_map_off"]["continuous"] == 0.3 and row["window_floor"]["required_new_windows"] == 2
    assert next(x for x in back["stages"] if x["id"] == "M")["enabled"] is False        # M is not left switched on
    assert row["commands"] == next(x for x in world.doc["stages"] if x["id"] == "E1F")["commands"]


def test_hold_continues_then_extends_once_then_exhausts_with_a_notice_and_still_returns(world):
    r = _run(world)
    sent = []
    assert _boundary(world, r, 250, "HOLD")["segment_end"] == 500
    ext = _boundary(world, r, 500, "FAIL")
    assert (ext["action"], ext["state"], ext["segment_end"]) == ("continue", "m_extension", 750)
    assert _boundary(world, r, 750, "HOLD")["segment_end"] == 1000
    last = _boundary(world, r, 1000, "HOLD", notify=sent.append)
    assert last["action"] == "launch" and last["state"] == "m_exhausted_return_to_source" and last["target_stage"] == "E4"
    assert last["notification_required"] is True and last["notified"] is True and len(sent) == 1
    assert last["budget"]["ex42_budget_used_after"] == 4000 and last["budget"]["m_updates"] == 1000


def test_a_failing_notice_is_reported_not_hidden_and_the_return_still_happens(world):
    r = _run(world)
    _boundary(world, r, 250, "HOLD"), _boundary(world, r, 500, "HOLD"), _boundary(world, r, 750, "HOLD")

    def broken(_message):
        raise OSError("channel down")
    last = _boundary(world, r, 1000, "HOLD", notify=broken)
    assert last["action"] == "launch" and last["notified"] is False and "channel down" in last["notify_error"]
    assert last["notification_required"] is True
    r2 = _run(world, "E1F")
    for step in (250, 500, 750):
        _boundary(world, r2, step, "HOLD")
    assert _boundary(world, r2, 1000, "HOLD")["notified"] is False             # no channel at all is the same


def test_a_repeated_boundary_or_a_boundary_after_the_return_counts_nothing_twice(world):
    r = _run(world)
    first = _boundary(world, r, 250, "PASS")
    again = mob.decide_m_boundary(r.plan, r.p1, 250, "PASS")                   # no return_out: nothing is published again
    assert again["duplicate"] is True and again["plan"] == first["plan"] and again["budget"] == first["budget"]
    later = mob.decide_m_boundary(r.plan, r.p1, 500, "HOLD")
    assert later["duplicate"] is True and later["action"] == "launch"
    state = json.loads((r.p1.parent / mob.STATE_FILE).read_text())
    assert state["status"] == "returned" and state["last_boundary"] == 250


def test_resume_reads_the_saved_state_and_never_goes_backwards_or_off_the_interval(world):
    r = _run(world)
    _boundary(world, r, 250, "HOLD")
    _boundary(world, r, 500, "HOLD")                                           # extension taken here
    assert json.loads((r.p1.parent / mob.STATE_FILE).read_text())["extension_used"] is True
    with pytest.raises(ValueError, match="backwards"):
        mob.decide_m_boundary(r.plan, r.p1, 250, "HOLD")
    for bad in (0, 125, 1250, -250, "250"):
        with pytest.raises(ValueError):
            mob.decide_m_boundary(r.plan, r.p1, bad, "HOLD")
    with pytest.raises(ValueError, match="invalid"):
        mob.decide_m_boundary(r.plan, r.p1, 750, "MAYBE")


def test_a_return_publication_cannot_run_when_the_source_plan_changed_after_entry(world):
    r = _run(world)
    doc = yaml.safe_load(world.plan.read_text())
    doc["training_budget"]["note_changed"] = True
    world.plan.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
    with pytest.raises(ValueError, match="changed after M was entered"):
        _boundary(world, r, 250, "PASS")


# ---- the two new windows after a return ----------------------------------------------------------------------------
def _ctx(tmp_path, row, plan_sha, receipt_sha):
    evaluation = tmp_path / "m750"
    previous = tmp_path / "m500"
    previous.mkdir(parents=True, exist_ok=True)
    evaluation.mkdir(parents=True, exist_ok=True)
    if receipt_sha is not None:
        (previous / "p1_score.json").write_text(json.dumps({"plan_sha256": receipt_sha}))
    checkpoint = tmp_path / "model_750.pt"
    return SimpleNamespace(stage_id="E4", checkpoint=checkpoint, evaluation=evaluation, plan_path=tmp_path / "plan.yaml",
                           plan={"evaluation": {"interval_updates": 250}, "stages": [row]}, digest=lambda p: plan_sha)


@pytest.mark.parametrize("floor,receipt,expected", [
    (True, "p" * 64, True), (True, "q" * 64, False), (True, None, False), (False, "q" * 64, True)])
def test_windows_measured_before_the_return_do_not_count(tmp_path, floor, receipt, expected):
    row = {"id": "E4", **({"window_floor": {"after_m_iteration": 250}} if floor else {})}
    judge = late.E6aPostureTwoWindowJudge()
    judge.stage_id = "E4"
    assert judge._counts_after_return(_ctx(tmp_path, row, "p" * 64, receipt)) is expected


@pytest.mark.parametrize("floor,receipt,verdict", [
    (True, "old" + "0" * 61, "HOLD"), (True, "p" * 64, "PASS"), (False, "old" + "0" * 61, "PASS")])
def test_the_floor_reaches_the_exit_judgement(tmp_path, monkeypatch, floor, receipt, verdict):
    """The two windows of the exit judge: a window measured under the pre-M plan leaves the exit at HOLD."""
    from foothold_s2 import ex42_e0_judge
    monkeypatch.setattr(late, "previous_window", lambda ctx: {"checkpoint_sha256": SHA})
    monkeypatch.setattr(ex42_e0_judge, "load_baseline", lambda *a, **k: {})
    monkeypatch.setattr(ex42_e0_judge, "judge", lambda *a, **k: {"judgement": "PASS"})

    class Judge(late._LateJudge):
        name, stage_id, item = "floor_probe", "E4", "probe"

        def window_item(self, folder, ctx, score):
            return {"role": "judge", "judgement": "PASS"}
    row = {"id": "E4", **({"window_floor": {"after_m_iteration": 250}} if floor else {})}
    ctx = _ctx(tmp_path, row, "p" * 64, receipt)
    ctx.plan["assumptions_pending_lead"] = {"q4_two_window_range": {"value": {"measured": {}}}}
    ctx.cfg, ctx.root = {"baseline": {"sha256": "x"}}, tmp_path
    assert Judge().judge(ctx, {})["stage_exit"]["judgement"] == verdict


# ---- hand-off wiring -----------------------------------------------------------------------------------------------
def _boundary_files(world, source, iteration, judgment, gap=7):
    run = world.tmp / f"hand_{source}_{iteration}_{judgment}_{gap}"
    run.mkdir()
    checkpoint = run / f"model_{iteration}.pt"
    checkpoint.write_bytes(b"weights-" + source.encode())
    sha = _sha(checkpoint.read_bytes())
    (run / "manifest.json").write_text(json.dumps({"checkpoints": {checkpoint.name: sha}, "progress": {"completed_updates": iteration}}))
    p1 = run / "p1_score.json"
    p1.write_text(json.dumps({"judgment": judgment, "checkpoint_sha256": sha, "state": "complete", "stage_id": source,
                              "checkpoint_iteration": iteration}))
    plan_sha = EX42Plan.load(world.plan).sha256
    path = _write(run / "ev", _build(_raw(64, 64 - gap), checkpoint=sha, stage=source, iteration=iteration, plan_sha=plan_sha))
    return run, p1, checkpoint, sha, path


def _publisher(world, sha):
    def branch(*, plan_path, approvals_path, source_stage_id, cells_path, checkpoint_sha256, source_iteration,
               changed_axes, parent_manifest, gate_receipt):
        return mob.publish_entry(plan_path=plan_path, approvals_path=approvals_path, source_stage_id=source_stage_id,
                                 cells_path=cells_path, checkpoint_sha256=checkpoint_sha256,
                                 source_iteration=source_iteration, changed_axes=changed_axes, budget_limit=20000,
                                 budget_used=2000, out=world.tmp / f"M_hand_{source_iteration}_{sha[:6]}")
    return branch


@pytest.mark.parametrize("source", ["E1F", "E4"])
def test_a_source_boundary_with_low_map_off_survival_launches_m(world, source):
    iteration = 500
    run, p1, _ckpt, sha, cells_path = _boundary_files(world, source, iteration, "HOLD")
    got = handoff.decide_next_stage(world.plan, world.approvals, source, iteration, p1, run / "manifest.json",
                                    branch=_publisher(world, sha), map_off_cells=cells_path)
    assert (got["action"], got["target_stage"], got["state"]) == ("launch", "M", "map_off_branch_authorized")
    assert got["authorization"]["kind"] == "map_off_branch_entry" and got["authorization"]["source_stage_id"] == source
    assert yaml.safe_load(Path(got["plan"]).read_text())["stages"][[r["id"] for r in world.doc["stages"]].index("M")]["enabled"]


def test_the_branch_is_not_entered_when_survival_is_fine_the_source_passes_or_nothing_is_wired(world):
    run, p1, _c, sha, ok = _boundary_files(world, "E4", 500, "HOLD", gap=6)
    got = handoff.decide_next_stage(world.plan, world.approvals, "E4", 500, p1, run / "manifest.json",
                                    branch=_publisher(world, sha), map_off_cells=ok)
    assert got["state"] != "map_off_branch_authorized" and got["map_off_entry"]["state"] == "map_off_within_limit"
    run, p1, _c, sha, low = _boundary_files(world, "E4", 500, "PASS")        # a passing boundary changes the next axes
    got = handoff.decide_next_stage(world.plan, world.approvals, "E4", 500, p1, run / "manifest.json",
                                    branch=_publisher(world, sha), map_off_cells=low)
    assert got["state"] != "map_off_branch_authorized" and got["map_off_entry"]["state"] == "other_axis_changed"
    run, p1, _c, sha, low = _boundary_files(world, "E4", 750, "HOLD")
    for wired in ({"branch": None, "map_off_cells": low}, {"branch": _publisher(world, sha), "map_off_cells": None}):
        got = handoff.decide_next_stage(world.plan, world.approvals, "E4", 750, p1, run / "manifest.json", **wired)
        assert got is None or got["state"] != "map_off_branch_authorized"


def test_an_entry_the_publisher_refuses_is_a_notice_not_a_launch(world):
    run, p1, _c, sha, low = _boundary_files(world, "E4", 500, "HOLD")

    def refuse(**_kw):
        raise ValueError("budget cannot hold M")
    got = handoff.decide_next_stage(world.plan, world.approvals, "E4", 500, p1, run / "manifest.json",
                                    branch=refuse, map_off_cells=low)
    assert got["action"] == "notify" and got["state"] == "map_off_branch_not_authorized" and "budget" in got["reason"]


def test_the_running_m_stage_returns_through_the_same_hand_off(world):
    made = _enter(world, "E4")
    run, p1, ckpt, sha, _ = _boundary_files(world, "M", 250, "PASS")
    out_root = world.tmp / "out_root"
    got = handoff.decide_next_stage(made["plan"], made["approvals"], "M", 250, p1, run / "manifest.json", out_root=out_root)
    assert (got["action"], got["target_stage"], got["next_stage_id"], got["m_state"]) == ("launch", "E4", "E4", "m_exit_pass")
    assert Path(got["plan"]).is_file() and got["gate_sha256"] == _sha(p1.read_bytes())
    run2, p2, _c2, _s2, _ = _boundary_files(world, "M", 250, "HOLD", gap=0)
    cont = handoff.decide_next_stage(_enter(world, "E1F", gap=8)["plan"], made["approvals"], "M", 250, p2,
                                     run2 / "manifest.json", out_root=out_root)
    assert (cont["action"], cont["target_stage"], cont["segment_end"]) == ("continue", "M", 500)
    assert cont["resume_checkpoint"].endswith("model_250.pt")
    assert handoff.decide_next_stage(made["plan"], made["approvals"], "M", 250, p2, run2 / "manifest.json")["state"] == \
        "m_decision_failed"                                                  # no out root: refused, never guessed


def test_branch_from_env_is_off_without_an_out_root_and_the_launcher_accepts_the_return(world, tmp_path):
    assert mob.branch_from_env({}) is None and callable(mob.branch_from_env({"EX42_MATERIALIZE_OUT_ROOT": str(tmp_path)}))
    made = _enter(world, "E4")
    run, p1, ckpt, sha, _ = _boundary_files(world, "M", 250, "PASS")
    decision = handoff.decide_next_stage(made["plan"], made["approvals"], "M", 250, p1, run / "manifest.json",
                                         out_root=world.tmp / "o")
    script = tmp_path / "launcher.sh"
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o755)
    seen = {}

    def popen(argv, env, **_kw):
        seen.update(env)
        return SimpleNamespace(pid=4242)
    record = handoff.start_launcher(decision, script, run, parent_manifest=run / "manifest.json", parent_checkpoint=ckpt,
                                    gate_receipt=p1, popen=popen)
    assert record["target_stage"] == "E4" and seen["EX42_AUTO_TARGET_STAGE"] == "E4" and seen["EX42_AUTO_PLAN"] == decision["plan"]
