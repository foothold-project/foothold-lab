"""EX42_LEVEL_SPREAD_KINDS (planner BOUNDARY-E2R2-M250-PREP 17-5 · lead 1121 03:07): 이어 받을 때 그 열 env 의 시작 수준을 0..상한에 고르게. CPU · Isaac 없음.
꺼져 있으면 시작 배치 · 영수증이 옛 것과 같아야 한다. 켜짐 시험은 실제 E2 plan 행 (rf 의 plan · 215757 m250 과 같은 열 배치) · 빔 메시 · 실제 부모 env_state
(215757 model_250) 를 실제 entry (prepare_e0_env_cfg → apply_e0_exposure) 에 넣는다."""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import numpy as np
import pytest
import torch

from foothold_s2.terrains import ex42_exposure as ex

PLAN = Path(os.environ.get("EX42_SPREAD_TEST_PLAN", "/home/jay/data/foothold/sonnet_beam_mesh_1119/rf_m250/ex42-prep.yaml"))
MESH = Path("/mnt/win-d/mai/data/foothold/sonnet_beam_mesh_1119/b2m_rpy_lv")
PARENT = Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261120_193344_r2/main/EX-42-B-E2_20261120_215757/model_250.pt")
needs_real = pytest.mark.skipif(not (PLAN.is_file() and (MESH / "terrain_mesh.npz").is_file() and PARENT.is_file()),
                                reason="rf plan, beam mesh or parent checkpoint not on this machine")
BEAMS = (35, 36, 37, 38, 39)


class Term:
    def __init__(self, func=None, mode="reset", params=None, weight=0.0):
        self.func, self.mode, self.params, self.weight = func, mode, dict(params or {}), weight


def _push(env, env_ids, velocity_range):
    pass


@pytest.fixture
def isaac_stubs(monkeypatch):
    managers = types.ModuleType("isaaclab.managers")
    managers.EventTermCfg = Term
    utils = types.ModuleType("isaaclab.utils")
    utils.configclass = lambda c: c
    monkeypatch.setitem(sys.modules, "isaaclab", types.ModuleType("isaaclab"))
    monkeypatch.setitem(sys.modules, "isaaclab.managers", managers)
    monkeypatch.setitem(sys.modules, "isaaclab.utils", utils)


def _cfg():
    events = types.SimpleNamespace(reset_base=Term(params={"pose_range": {}, "velocity_range": {"x": (0.0, 0.0)}}),
                                   ex40_push=Term(func=_push, mode="interval", params={"velocity_range": {"x": (-1, 1)}}))
    rewards = types.SimpleNamespace(track_lin_vel=Term(params={"std": 0.7}), foot_edge=Term())
    return types.SimpleNamespace(events=events, scene=types.SimpleNamespace(terrain=types.SimpleNamespace(terrain_generator=None)), rewards=rewards,
                                 terminations=types.SimpleNamespace(foot_below_ground=Term()),
                                 commands=types.SimpleNamespace(base_velocity=types.SimpleNamespace(flag_provider=None)))


def _installed_update():
    def update(self, env_ids, move_up, move_down):
        self.terrain_levels[env_ids] += 1 * move_up - 1 * move_down
        self.terrain_levels[env_ids] = torch.clamp(self.terrain_levels[env_ids], min=0)
        self.env_origins[env_ids] = self.terrain_origins[self.terrain_levels[env_ids], self.terrain_types[env_ids]]
    return update


def _env(n=3072):
    origins = np.load(MESH / "terrain_mesh.npz", allow_pickle=False)["origins"]
    t = types.SimpleNamespace(terrain_origins=torch.as_tensor(origins, dtype=torch.float32), max_terrain_level=origins.shape[0],
                              terrain_levels=torch.zeros(n, dtype=torch.long), terrain_types=torch.zeros(n, dtype=torch.long), env_origins=torch.zeros(n, 3))
    t.update_env_origins = types.MethodType(_installed_update(), t)
    rm = types.SimpleNamespace(get_term_cfg=lambda name: types.SimpleNamespace(weight=-1.0))      # the live reward manager has the plan's foot_edge weight
    return types.SimpleNamespace(unwrapped=types.SimpleNamespace(scene=types.SimpleNamespace(terrain=t), device="cpu", reward_manager=rm))


def _start(monkeypatch, spread):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.scripts import ex42_training_entry as te
    monkeypatch.delenv("EX42_LEVEL_SPREAD_KINDS", raising=False)
    if spread is not None:
        monkeypatch.setenv("EX42_LEVEL_SPREAD_KINDS", spread)
    contract = te.prepare_e0_env_cfg(_cfg(), EX42Plan.load(PLAN), MESH, stage_id="E2")
    state = torch.load(PARENT, map_location="cpu", weights_only=False)["env_state"]
    env = _env(len(state["terrain_levels"]))
    receipt = te.apply_e0_exposure(env, contract, state, parent_same_mesh=True)
    return env.unwrapped.scene.terrain, receipt, state, contract


def _hist(t, cols):
    on = torch.isin(t.terrain_types, torch.tensor(cols))
    return torch.bincount(t.terrain_levels[on], minlength=10).tolist()


@needs_real
def test_off_restores_the_parent_placement_exactly(monkeypatch, isaac_stubs):
    t, receipt, state, _ = _start(monkeypatch, None)
    assert "level_spread" not in receipt and receipt["start"] == "parent_env_state"
    assert torch.equal(t.terrain_types, state["terrain_types"].long())
    caps = torch.as_tensor(receipt["level_caps"])
    assert torch.equal(t.terrain_levels, torch.minimum(state["terrain_levels"].long(), caps[t.terrain_types]))


@needs_real
def test_on_spreads_the_beam_envs_over_l0_l1_l2_and_leaves_every_other_env_as_it_was(monkeypatch, isaac_stubs):
    off, _, _, _ = _start(monkeypatch, None)
    on, receipt, state, contract = _start(monkeypatch, "A/balance_beams")
    assert receipt["level_caps"][35] == 2                                    # rf plan: A/balance_beams start cap 2
    h = _hist(on, BEAMS)
    n = sum(h)
    assert sum(h[3:]) == 0 and all(abs(h[k] - n / 3) <= 1 for k in range(3))      # L0 : L1 : L2 about 1/3 each, nothing above the cap
    beams = torch.isin(on.terrain_types, torch.tensor(BEAMS))
    assert torch.equal(on.terrain_types, off.terrain_types)                 # no column changes
    assert torch.equal(on.terrain_levels[~beams], off.terrain_levels[~beams])   # every other column bit for bit
    assert torch.equal(on.env_origins, on.terrain_origins[on.terrain_levels, on.terrain_types])
    s = receipt["level_spread"]
    assert s["columns"] == list(BEAMS) and s["envs"] == n and s["after"] == {str(k): h[k] for k in range(3)}
    assert s["before"] == {str(k): v for k, v in enumerate(_hist(off, BEAMS)) if v}
    # later moves are the curriculum's: a promotion from L2 is cut at the cap, a demotion goes down
    ids = torch.nonzero(beams & (on.terrain_levels == 2)).flatten()[:4]
    on.update_env_origins(ids, torch.ones(4, dtype=torch.bool), torch.zeros(4, dtype=torch.bool))
    assert bool((on.terrain_levels[ids] == 2).all())
    on.update_env_origins(ids, torch.zeros(4, dtype=torch.bool), torch.ones(4, dtype=torch.bool))
    assert bool((on.terrain_levels[ids] == 1).all())


@needs_real
def test_bad_names_and_zero_exposure_columns_refuse(monkeypatch, isaac_stubs):
    for bad in ("A/nothing", "balance_beams", "A/balance_beams,A/balance_beams"):
        with pytest.raises(ValueError, match="EX42_LEVEL_SPREAD_KINDS"):
            _start(monkeypatch, bad)
    with pytest.raises(ValueError, match="exposure 0"):
        _start(monkeypatch, "A/stepping_stones_high")


def test_spread_is_deterministic_and_draws_no_random_number():
    t = types.SimpleNamespace(terrain_origins=torch.zeros(10, 4, 3), terrain_levels=torch.zeros(12, dtype=torch.long),
                              terrain_types=torch.tensor([1, 0] * 6), env_origins=torch.zeros(12, 3))
    cap = torch.tensor([5, 2, 5, 5])
    state = torch.random.get_rng_state()
    r = ex.spread_start_levels(t, cap, (1,), lambda ids: None)
    assert torch.equal(torch.random.get_rng_state(), state)
    assert t.terrain_levels[t.terrain_types == 1].tolist() == [0, 1, 2, 0, 1, 2] and bool((t.terrain_levels[t.terrain_types == 0] == 0).all())
    assert r == {"columns": [1], "envs": 6, "before": {"0": 6}, "after": {"0": 2, "1": 2, "2": 2}}


# ---- EX42_EDGE_PENALTY_OFF_KINDS (planner 18 · lead 1121 03:21): A 틈 열만 발 가장자리 벌점 끔 ------------------------------------------------

GAPS = (45, 46, 47)


def _tables():
    from foothold_s2.terrains.ex42_edge_masks import EdgeTables, load_edge_masks
    return EdgeTables(load_edge_masks(str(MESH / "terrain_mesh.npz")), 76, "cpu")


def _feet_on_masks(t, cols, n_per=64, seed=0):
    """각 열 · 줄의 inner/outer 칸 가운데에 발 하나를 둔 (N, 1, 2) 좌표와 그 줄 · 열."""
    g = torch.Generator().manual_seed(seed)
    feet, rows, ts = [], [], []
    fam = int(round(t.shift[1].item() * 2 / t.tile[1]))
    for col in cols:
        k = int(t.col_to_k[col])
        for r in range(t.inner.shape[0]):
            cells = torch.nonzero(t.inner[r, k] | t.outer[r, k])
            if len(cells) == 0:
                continue
            for i in torch.randint(len(cells), (n_per,), generator=g):
                c = cells[int(i)]
                feet.append([-t.tile[0] * t.inner.shape[0] / 2.0 + t.tile[0] * r + (c[0].item() + 0.5) * t.res,
                             -t.tile[1] * fam / 2.0 + t.tile[1] * col + (c[1].item() + 0.5) * t.res])
                rows.append(r); ts.append(col)
    return torch.tensor(feet, dtype=torch.float32)[:, None, :], torch.tensor(rows), torch.tensor(ts)


needs_masks = pytest.mark.skipif(not (MESH / "terrain_mesh.npz").is_file(), reason="beam mesh not on this machine")


@needs_masks
def test_edge_off_reads_zero_on_the_gap_columns_and_every_other_column_is_unchanged():
    t = _tables()
    masked = [int(c) for c in (t.col_to_k >= 0).nonzero().flatten()]
    assert set(GAPS) <= set(masked)                                          # the beam mesh has A/gaps edge masks (verifier: A gap edge on)
    feet, rows, cols = _feet_on_masks(t, masked)
    contact = torch.ones(len(feet), 1, dtype=torch.bool)
    before = t.penalty(feet, contact, rows, cols)
    gap = torch.isin(cols, torch.tensor(GAPS))
    assert int((before[gap] != 0).sum()) > 100                               # the term was on there
    check = t.drop_columns(GAPS)
    after = t.penalty(feet, contact, rows, cols)
    assert check["columns"] == list(GAPS) and all(v > 0 for v in check["inner_before"]) and check["inner_after"] == [0.0, 0.0, 0.0]
    assert bool((after[gap] == 0).all())                                    # on: those columns read 0
    assert torch.equal(after[~gap], before[~gap])                           # every other column bit for bit
    on = torch.isin(cols, torch.tensor(GAPS))
    assert int((on & (after != 0)).sum()) == 0                               # the first-update count EX42_EDGE_PENALTY_OFF ... off_on_env_steps=0


@needs_masks
def test_edge_off_refuses_a_column_without_a_mask():
    t = _tables()
    free = int((t.col_to_k < 0).nonzero().flatten()[0])
    with pytest.raises(ValueError, match="no edge mask"):
        t.drop_columns((free,))


def test_edge_off_switch_reads_the_table_and_is_off_by_default():
    from foothold_s2 import ex42_gap_switches as gs
    from foothold_s2.terrains.ex42_column_reset import build_column_table
    table = build_column_table(["A"] * 50 + ["B"] * 12 + ["C"] * 7 + ["D"] * 3 + ["E"] * 4)
    sw = gs.read_switches(table, {})
    assert gs.receipt(sw) == {} and not gs.any_on(sw) and sw["edge_off_columns"] == ()
    sw = gs.read_switches(table, {gs.ENV_EDGE_OFF: "A/gaps"})
    assert sw["edge_off_columns"] == GAPS and gs.receipt(sw) == {"gap_switches": {"edge_penalty_off_kinds": ["A/gaps"]}}
    with pytest.raises(ValueError, match="same kinds"):
        gs.read_switches(table, {gs.ENV_EDGE_OFF: "A/gaps", gs.ENV_EDGE: "A/gaps"})


@needs_real
def test_entry_on_drops_the_gap_columns_from_the_live_tables_and_off_keeps_them(monkeypatch, isaac_stubs):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.scripts import ex42_training_entry as te
    for on in (False, True):
        monkeypatch.delenv("EX42_LEVEL_SPREAD_KINDS", raising=False)
        monkeypatch.delenv("EX42_EDGE_PENALTY_OFF_KINDS", raising=False)
        if on:
            monkeypatch.setenv("EX42_EDGE_PENALTY_OFF_KINDS", "A/gaps")
        contract = te.prepare_e0_env_cfg(_cfg(), EX42Plan.load(PLAN), MESH, stage_id="E2")
        env = _env(64)
        got = te.attach_edge_tables(env.unwrapped, contract)
        k = env.unwrapped.ex42_edge_tables.col_to_k
        if on:
            assert contract["gap_switches"] == {"edge_penalty_off_kinds": ["A/gaps"]}
            assert [int(k[c]) for c in GAPS] == [-1, -1, -1] and got["self_check"]["edge_penalty_off"]["inner_after"] == [0.0, 0.0, 0.0]
            assert int((k >= 0).sum()) == base_masked - 3
        else:
            assert "gap_switches" not in contract and "edge_penalty_off" not in got["self_check"]
            assert all(int(k[c]) >= 0 for c in GAPS)
            base_masked = int((k >= 0).sum())


def test_first_update_line_and_live_count_are_wired():
    import ast
    root = Path(__file__).resolve().parents[1]
    src = (root / "rewards" / "start_rewards.py").read_text(encoding="utf-8")
    assert '"_ex42_edge_off_acc"' in src and "on & (value != 0)" in src
    runner = (root / "runners" / "start_runner.py").read_text(encoding="utf-8")
    assert "EX42_EDGE_PENALTY_OFF it=%d kinds=%s off_env_steps=%d off_on_env_steps=%d off_on_frac=%.6f steps=%d" in runner
    ast.parse(src); ast.parse(runner)
