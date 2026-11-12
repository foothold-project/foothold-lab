"""E3 raw material: the exposure receipt is built from the real plan + mesh contract, written atomically, and a consumer
recomputes it. The runtime hooks are checked with a stand-in env (no Kit)."""
from __future__ import annotations

import json
import pathlib
import sys
import types

import pytest
import torch

from foothold_s2 import ex42_exposure_receipt as er
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_training_entry as te

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / "foothold_s2" / "curriculum" / "ex42-prep.yaml"
MESH = pathlib.Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333_flags_E2_1111_v2")   # the mesh the plan pins for E3
PSHA = "a" * 64


class Term:
    def __init__(self, func=None, mode="reset", params=None):
        self.func, self.mode, self.params = func, mode, dict(params or {})


@pytest.fixture(autouse=True)
def isaac_stubs(monkeypatch):
    managers = types.ModuleType("isaaclab.managers")
    managers.EventTermCfg = Term
    utils = types.ModuleType("isaaclab.utils")
    utils.configclass = lambda c: c
    monkeypatch.setitem(sys.modules, "isaaclab", types.ModuleType("isaaclab"))
    monkeypatch.setitem(sys.modules, "isaaclab.managers", managers)
    monkeypatch.setitem(sys.modules, "isaaclab.utils", utils)


def _cfg():
    events = types.SimpleNamespace(
        reset_base=Term(params={"pose_range": {}, "velocity_range": {"x": (0.0, 0.0)}}),
        ex40_push=Term(func=lambda *a: None, mode="interval", params={"velocity_range": {"x": (-1, 1)}}))
    return types.SimpleNamespace(events=events, commands=types.SimpleNamespace(
                                     base_velocity=types.SimpleNamespace(flag_provider=None)),
                                 scene=types.SimpleNamespace(terrain=types.SimpleNamespace(terrain_generator=None)))


def _contract(stage="E3", k=0, outcomes=None):
    return te.prepare_e0_env_cfg(_cfg(), EX42Plan.load(PLAN), MESH, stage_id=stage, boundary_index=k,
                                 ladder_outcomes=outcomes)


need_mesh = pytest.mark.skipif(not MESH.is_dir(), reason="real mesh not on this machine")


@need_mesh
def test_the_receipt_carries_the_real_contract_and_opened_kinds_follow_the_exposure(tmp_path):
    contract = _contract()
    body = er.build_receipt(contract, stage_id="E3", plan_sha256=PSHA, iteration=0, kind="start")
    assert body["columns"] == len(contract["exposure"]) == len(body["column_rows"])
    assert body["mesh_sha256"] == contract["mesh_sha256"] and body["boundary_index"] == 0
    for row, e, cap in zip(body["column_rows"], contract["exposure"], contract["level_caps"]):
        assert (row["exposure"], row["level_cap"], row["open"]) == (e, cap, e > 0)
    assert set(body["opened_kinds"]) == {f"{r['family']}/{r['kind']}" for r in body["column_rows"] if r["open"]}
    assert er.verify_receipt(body) == body["opened_kinds"]
    path = er.write_receipt(tmp_path, body)
    assert path.name == "exposure_receipt_start_0.json" and not list(tmp_path.glob("*.tmp"))
    assert er.verify_receipt(json.loads(path.read_text())) == body["opened_kinds"]


@need_mesh
def test_a_k_ladder_move_changes_the_receipt_and_its_kinds():
    # E3 starts as the E2 end state plus the entry axis D only (lead 2026-11-12 02:00): stepping_stones_low is the one `new`
    # kind of the start block and C/flat is the first kind the K ladder opens.
    flat_pass = {"A/stepping_stones_low": {"first_window_pass": True}}
    first = er.build_receipt(_contract(k=1, outcomes=[flat_pass]), stage_id="E3", plan_sha256=PSHA, iteration=250,
                             kind="boundary")
    later = er.build_receipt(_contract(k=2, outcomes=[flat_pass, {}]), stage_id="E3", plan_sha256=PSHA, iteration=500,
                             kind="boundary")
    held = er.build_receipt(_contract(k=2, outcomes=[{}, {}]), stage_id="E3", plan_sha256=PSHA, iteration=500,
                            kind="boundary")
    assert first["boundary_index"] == 1 and later["boundary_index"] == 2
    assert [(m["kind"], m["grade"]) for m in first["k_ladder_moves"]] == [("A/stepping_stones_low", "current")]
    assert [(m["kind"], m["grade"]) for m in later["k_ladder_moves"]] == [("A/stepping_stones_low", "current"), ("C/flat", "new")]
    assert "C/flat" not in first["opened_kinds"] and "C/flat" in later["opened_kinds"]     # a new kind opens
    assert held["k_ladder_moves"] == [] and "C/flat" not in held["opened_kinds"]           # no evidence = a hold
    assert len({first["sha256"], later["sha256"], held["sha256"]}) == 3


@need_mesh
def test_tampering_is_caught_by_the_recompute():
    body = er.build_receipt(_contract(), stage_id="E3", plan_sha256=PSHA, iteration=0, kind="start")
    cap = json.loads(json.dumps(body)); cap["column_rows"][0]["level_cap"] += 1
    with pytest.raises(ValueError, match="sha256"):
        er.verify_receipt(cap)
    forged = json.loads(json.dumps(body)); row = forged["column_rows"][0]
    row["exposure"] = 0.0 if row["open"] else 1.0                     # exposure flipped, sha refreshed by the forger
    forged["sha256"] = er._sha(forged)
    with pytest.raises(ValueError, match="open flag|opened_kinds"):
        er.verify_receipt(forged)
    forged2 = json.loads(json.dumps(body)); forged2["opened_kinds"] = {}
    forged2["sha256"] = er._sha(forged2)
    with pytest.raises(ValueError, match="opened_kinds"):
        er.verify_receipt(forged2)


@need_mesh
def test_ranks_fold_only_when_they_agree(tmp_path):
    contract = _contract()
    docs = [er.build_receipt(contract, stage_id="E3", plan_sha256=PSHA, iteration=250, kind="boundary",
                             rank=r, world_size=2) for r in (0, 1)]
    assert er.receipt_name("boundary", 250, 1, 2) == "exposure_receipt_250_rank1.json"
    assert er.receipt_name("start", 250, 1, 2) == "exposure_receipt_start_250_rank1.json"
    assert er.fold_ranks(docs)["rank"] == 0
    with pytest.raises(ValueError, match="cover every rank"):
        er.fold_ranks(docs[:1])
    other = json.loads(json.dumps(docs[1])); other["boundary_index"] = 3; other["sha256"] = er._sha(other)
    with pytest.raises(ValueError, match="differ"):
        er.fold_ranks([docs[0], other])


def test_a_contract_with_mismatched_columns_is_refused():
    bad = {"mesh_sha256": "m", "columns": 3, "families": ["A"], "exposure": [1, 1], "level_caps": [0, 0, 0],
           "shares": None, "low_floor": None, "k_ladder": {"boundary_index": 0, "moves": []},
           "column_table": [{"family": "A", "kind": "x"}] * 3}
    with pytest.raises(ValueError, match="differ in length"):
        er.build_receipt(bad, stage_id="E3", plan_sha256=PSHA, iteration=0, kind="start")
    short_caps = {**bad, "exposure": [1, 1, 1], "level_caps": [0, 0]}          # exposure fits, level caps do not
    with pytest.raises(ValueError, match="differ in length"):
        er.build_receipt(short_caps, stage_id="E3", plan_sha256=PSHA, iteration=0, kind="start")
    with pytest.raises(ValueError, match="lacks"):
        er.build_receipt({}, stage_id="E3", plan_sha256=PSHA, iteration=0, kind="start")


# ---- runtime hooks (stand-in env) ---------------------------------------------------------------------------
def _runtime(tmp_path, contract):
    plan = types.SimpleNamespace(stages=[types.SimpleNamespace(name="s")])
    rt = te.EX42StageZeroRuntime(stage_zero_plan=plan, plan_sha256=PSHA, approval_sha256="2" * 64,
                                 parent_sha256="3" * 64, maximum_updates=1750, push_vmax_mps=2.0, stage_id="E1")
    terrain = types.SimpleNamespace(terrain_levels=torch.tensor([0, 1, 2]), terrain_types=torch.tensor([0, 0, 1]),
                                    terrain_origins=torch.zeros(10, 4, 3))
    rt.env = types.SimpleNamespace(num_envs=3, device="cpu", scene=types.SimpleNamespace(terrain=terrain),
                                   _ex42_env_contract=contract)
    rt.runner = types.SimpleNamespace(log_dir=str(tmp_path))
    return rt


@need_mesh
def test_the_runtime_writes_the_start_receipt_once_and_one_per_save_boundary(tmp_path):
    rt = _runtime(tmp_path, _contract(k=2, outcomes=[{}, {}]))
    rt.stage_id = "E3"
    rt.on_update_start(7)                              # a segment continued from update 6
    rt.on_update_start(8)
    assert sorted(p.name for p in tmp_path.glob("exposure_receipt_*")) == ["exposure_receipt_start_6.json"]
    start = json.loads((tmp_path / "exposure_receipt_start_6.json").read_text())
    assert start["kind"] == "start" and start["boundary_index"] == 2 and start["live"]["envs"] == 3
    rt._exposure_receipt(250, "boundary")
    rt._exposure_receipt(500, "boundary")
    got = sorted(p.name for p in tmp_path.glob("exposure_receipt_*"))
    assert got == ["exposure_receipt_250.json", "exposure_receipt_500.json", "exposure_receipt_start_6.json"]
    for name in got:
        er.verify_receipt(json.loads((tmp_path / name).read_text()))


def test_a_failed_receipt_is_reported_and_never_raises(tmp_path, capsys):
    rt = _runtime(tmp_path, {"mesh_sha256": "m"})      # a contract without the needed keys
    rt._exposure_receipt(250, "boundary")
    assert "EX42_EXPOSURE_RECEIPT_FAILED" in capsys.readouterr().out
    assert not list(tmp_path.glob("exposure_receipt_*"))


def test_the_apply_seam_keeps_the_contract_on_the_env_for_the_receipt():
    src = pathlib.Path(te.__file__).read_text(encoding="utf-8")
    assert "env.unwrapped._ex42_env_contract = contract" in src
    assert 'self._exposure_receipt(iteration, "boundary")' in src and 'self._exposure_receipt(update - 1, "start")' in src


@need_mesh
def test_a_continued_segment_start_receipt_does_not_erase_the_boundary_receipt_of_the_same_update(tmp_path):
    """stop-evaluate-continue: boundary 250 ends one process, the next one starts at update 250 (its first update is 251)."""
    contract = _contract()
    first = _runtime(tmp_path, contract); first.stage_id = "E3"
    first._exposure_receipt(250, "boundary")
    boundary = (tmp_path / "exposure_receipt_250.json").read_bytes()
    second = _runtime(tmp_path, contract); second.stage_id = "E3"
    second.on_update_start(251)                         # iteration 250, kind start
    assert (tmp_path / "exposure_receipt_250.json").read_bytes() == boundary
    assert json.loads((tmp_path / "exposure_receipt_start_250.json").read_text())["kind"] == "start"


@need_mesh
def test_an_existing_receipt_is_never_overwritten(tmp_path, capsys):
    body = er.build_receipt(_contract(), stage_id="E3", plan_sha256=PSHA, iteration=250, kind="boundary")
    er.write_receipt(tmp_path, body)
    before = (tmp_path / "exposure_receipt_250.json").read_bytes()
    with pytest.raises(FileExistsError, match="not overwritten"):
        er.write_receipt(tmp_path, {**body, "plan_sha256": "b" * 64})
    assert (tmp_path / "exposure_receipt_250.json").read_bytes() == before and not list(tmp_path.glob("*.tmp"))
    rt = _runtime(tmp_path, _contract()); rt.stage_id = "E3"
    rt._exposure_receipt(250, "boundary")               # the runtime reports it and keeps training
    assert "EX42_EXPOSURE_RECEIPT_FAILED" in capsys.readouterr().out
    assert (tmp_path / "exposure_receipt_250.json").read_bytes() == before


@need_mesh
def test_two_ranks_write_into_one_folder_and_the_boundary_files_fold(tmp_path, monkeypatch):
    contract = _contract()
    for rank in (0, 1):
        monkeypatch.setenv("RANK", str(rank)); monkeypatch.setenv("WORLD_SIZE", "2")
        rt = _runtime(tmp_path, contract); rt.stage_id = "E3"      # both ranks get the same --ex42_log_dir (train_start: output_dir)
        rt.on_update_start(1); rt._exposure_receipt(250, "boundary")
    names = sorted(p.name for p in tmp_path.glob("exposure_receipt_*"))
    assert names == ["exposure_receipt_250_rank0.json", "exposure_receipt_250_rank1.json",
                     "exposure_receipt_start_0_rank0.json", "exposure_receipt_start_0_rank1.json"]
    docs = [json.loads((tmp_path / n).read_text()) for n in names if n.startswith("exposure_receipt_250")]
    assert er.fold_ranks(docs)["world_size"] == 2


# ---- ladder_outcomes: the evidence the k moves came from, replayable by the consumer ----------------------------
# E3 starts as the E2 end state plus the entry axis D only (lead 2026-11-12 02:00): the one `new` kind of the start block is
# A/stepping_stones_low, and C/flat is the first kind the K ladder opens once that kind passed its first window.
LOW_PASS = {"A/stepping_stones_low": {"first_window_pass": True}}


@need_mesh
def test_the_receipt_records_the_ordered_outcomes_the_ladder_really_used_inside_the_sha():
    contract = _contract(k=2, outcomes=[LOW_PASS, {"B/rough": {"target_level_reached": False}}, {"x": {}}])
    body = er.build_receipt(contract, stage_id="E3", plan_sha256=PSHA, iteration=500, kind="boundary")
    assert body["ladder_outcomes"] == [LOW_PASS, {"B/rough": {"target_level_reached": False}}]    # first k only, in order
    swapped = json.loads(json.dumps(body)); swapped["ladder_outcomes"].reverse()
    with pytest.raises(ValueError, match="sha256"):
        er.verify_receipt(swapped)
    assert er.build_receipt(_contract(k=0), stage_id="E3", plan_sha256=PSHA, iteration=0, kind="start")["ladder_outcomes"] == []


@need_mesh
def test_the_consumer_replays_the_k_moves_from_the_plan_and_the_recorded_outcomes():
    plan = EX42Plan.load(PLAN)
    body = er.build_receipt(_contract(k=2, outcomes=[LOW_PASS, {}]), stage_id="E3", plan_sha256=PSHA, iteration=500,
                            kind="boundary")
    assert [m["kind"] for m in er.recompute_from_plan(body, plan)["moves"]] == ["A/stepping_stones_low", "C/flat"]
    fake = json.loads(json.dumps(body)); fake["ladder_outcomes"] = [{}, {}]                  # outcomes changed, sha refreshed
    fake["sha256"] = er._sha(fake)
    with pytest.raises(ValueError, match="differ from the plan replay"):
        er.recompute_from_plan(fake, plan)
    moved = json.loads(json.dumps(body)); moved["k_ladder_moves"] = []                      # moves dropped, sha refreshed
    moved["sha256"] = er._sha(moved)
    with pytest.raises(ValueError, match="k moves differ"):
        er.recompute_from_plan(moved, plan)
    cap = json.loads(json.dumps(body)); cap["column_rows"][0]["level_cap"] += 1            # a careful forger: derived part and sha refreshed
    cap["opened_kinds"] = er.opened_kinds(cap["column_rows"]); cap["sha256"] = er._sha(cap)
    with pytest.raises(ValueError, match="level caps differ"):
        er.recompute_from_plan(cap, plan)


@need_mesh
def test_no_outcomes_is_a_hold_and_the_replay_agrees():
    plan = EX42Plan.load(PLAN)
    body = er.build_receipt(_contract(k=2, outcomes=None), stage_id="E3", plan_sha256=PSHA, iteration=500, kind="boundary")
    assert body["ladder_outcomes"] == [] and er.recompute_from_plan(body, plan)["moves"] == []


def test_outcomes_longer_than_the_boundary_index_or_not_dicts_are_refused():
    base = {"mesh_sha256": "m", "columns": 1, "families": ["A"], "exposure": [1], "level_caps": [0], "shares": None,
            "low_floor": None, "column_table": [{"family": "A", "kind": "x"}]}
    for outcomes in ([{}, {}], ["x"], None):
        contract = {**base, "k_ladder": {"boundary_index": 1, "moves": [], "outcomes": outcomes}}
        with pytest.raises(ValueError, match="outcomes"):
            er.build_receipt(contract, stage_id="E3", plan_sha256=PSHA, iteration=0, kind="start")


@need_mesh
def test_swapping_the_kinds_of_an_open_and_a_closed_column_is_caught_by_the_mesh_column_table():
    plan = EX42Plan.load(PLAN)
    body = er.build_receipt(_contract(k=2, outcomes=[LOW_PASS, {}]), stage_id="E3", plan_sha256=PSHA, iteration=500,
                            kind="boundary")
    rows = body["column_rows"]
    open_i = next(i for i, r in enumerate(rows) if r["open"])
    closed_i = next(i for i, r in enumerate(rows) if not r["open"])
    forged = json.loads(json.dumps(body))
    for key in ("family", "kind"):                                           # swap which kind is open; derived part and sha refreshed
        forged["column_rows"][open_i][key], forged["column_rows"][closed_i][key] = rows[closed_i][key], rows[open_i][key]
    forged["opened_kinds"] = er.opened_kinds(forged["column_rows"]); forged["sha256"] = er._sha(forged)
    assert er.verify_receipt(forged)                                          # the self-consistency check alone accepts it
    with pytest.raises(ValueError, match="differ from the columns of its mesh"):
        er.recompute_from_plan(forged, plan)
    assert er.recompute_from_plan(body, plan)["moves"]                        # the honest receipt still passes
    other = json.loads(json.dumps(body)); other["mesh_sha256"] = "0" * 64; other["sha256"] = er._sha(other)
    with pytest.raises(ValueError, match="mesh_sha256 differs"):
        er.recompute_from_plan(other, plan)
