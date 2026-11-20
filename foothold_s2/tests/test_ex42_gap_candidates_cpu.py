"""E2 틈 처방 후보 둘 (verifier REPORT-START-GAP-E2-1121 의 1 · 2 · lead 1121 02:53). CPU · Isaac 없음 (isaaclab 은 가짜 모듈).

후보 1  EX42_TRACK_LIN_MIN_FWD_KINDS=A/gaps : 그 열 env 중 전진 명령 (cmd_x > 0) 만 선속도 추종 x 성분을 START 포화식 (S:151 · W:86) 으로.
후보 2  EX42_GAP_FWD_CMD_KINDS=A/gaps       : 그 열 env 의 명령을 START 분포 (S:225~233) 로 (vx U[0, 전진 상한] · vy 0 · vx < 0.3 은 제자리 돌기).
둘 다 기본 꺼짐이고, 꺼져 있으면 식 · 명령 · 영수증이 옛 것과 같아야 한다. 켜짐 시험은 실제 E2 plan 행 (215757 의 r2sp_m100 plan) 과 실제 빔 메시로 한다.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest
import torch

from foothold_s2 import ex42_gap_switches as gs

E2_PLAN = Path("/home/jay/data/foothold/sonnet_beam_mesh_1119/r2sp_m100/ex42-prep.yaml")
MESH = Path("/mnt/win-d/mai/data/foothold/sonnet_beam_mesh_1119/b2m_rpy_lv")
needs_real = pytest.mark.skipif(not (E2_PLAN.is_file() and (MESH / "terrain_mesh.npz").is_file()), reason="E2 plan or beam mesh not on this machine")
GAP_COLS = (45, 46, 47)


class Term:                                    # EventTermCfg / RewardTermCfg 대역 (func · mode · params · weight)
    def __init__(self, func=None, mode="reset", params=None, weight=0.0):
        self.func, self.mode, self.params, self.weight = func, mode, dict(params or {}), weight


def _orig_track(*a, **k):
    raise AssertionError("not called")


def _inner_push(env, env_ids, velocity_range):
    pass


@pytest.fixture
def isaac_stubs(monkeypatch):
    managers = types.ModuleType("isaaclab.managers")
    managers.EventTermCfg = Term
    managers.SceneEntityCfg = lambda name, **k: types.SimpleNamespace(name=name, **k)
    utils = types.ModuleType("isaaclab.utils")
    utils.configclass = lambda c: c
    pkg = types.ModuleType("isaaclab")
    monkeypatch.setitem(sys.modules, "isaaclab", pkg)
    monkeypatch.setitem(sys.modules, "isaaclab.managers", managers)
    monkeypatch.setitem(sys.modules, "isaaclab.utils", utils)


def _env_cfg():
    events = types.SimpleNamespace(
        reset_base=Term(params={"pose_range": {}, "velocity_range": {"x": (0.0, 0.0)}}),
        ex40_push=Term(func=_inner_push, mode="interval", params={"velocity_range": {"x": (-1, 1)}}))
    terrain = types.SimpleNamespace(terrain_generator=None)
    rewards = types.SimpleNamespace(track_lin_vel=Term(func=_orig_track, params={"command_name": "base_velocity", "std": 0.5 ** 0.5}, weight=2.0), foot_edge=Term(weight=0.0))
    terms = types.SimpleNamespace(foot_below_ground=Term(params={"margin": 0.25}))
    commands = types.SimpleNamespace(base_velocity=types.SimpleNamespace(flag_provider=None))
    return types.SimpleNamespace(events=events, scene=types.SimpleNamespace(terrain=terrain), rewards=rewards, terminations=terms, commands=commands)


FAKE_FWD = object()


def _fake_rewards(monkeypatch):
    """start_rewards 는 Kit 안에서만 import 된다 (isaaclab 전체). entry 가 고르는 함수 이름만 대역으로 본다 · 함수 몸통은 소스 대조 시험이 본다."""
    import foothold_s2.rewards as pkg
    fake = types.ModuleType("foothold_s2.rewards.start_rewards")
    fake.track_lin_vel_min_fwd_on_columns = FAKE_FWD
    fake.track_lin_vel_min_on_columns = object()
    monkeypatch.setitem(sys.modules, "foothold_s2.rewards.start_rewards", fake)
    monkeypatch.setattr(pkg, "start_rewards", fake, raising=False)


def _prepare(monkeypatch, env):
    _fake_rewards(monkeypatch)
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.scripts import ex42_training_entry as te
    for k in (gs.ENV_EDGE, gs.ENV_MIN, gs.ENV_PLANE, gs.ENV_MIN_FWD):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    cfg = _env_cfg()
    receipt = te.prepare_e0_env_cfg(cfg, EX42Plan.load(E2_PLAN), MESH, stage_id="E2")
    return cfg, receipt


# ---- 후보 1: 식 ----------------------------------------------------------------------------------------------------------------------------

def test_fwd_saturation_forgives_forward_overspeed_on_listed_forward_envs_only():
    std = 0.5 ** 0.5
    cmd = torch.tensor([[1.0, 0.0], [1.0, 0.0], [-0.5, 0.0], [0.0, 0.4], [1.0, 0.0], [0.6, 0.2]])
    vel = torch.tensor([[1.4, 0.0], [0.6, 0.0], [-0.9, 0.0], [0.0, 0.8], [1.4, 0.0], [0.9, 0.5]])
    col = torch.tensor([True, True, True, True, False, True])
    out = gs.track_lin_fwd_saturated(vel, cmd, std, col)
    exact = torch.exp(-torch.sum((cmd - vel) ** 2, dim=-1) / std ** 2)
    assert float(out[0]) == pytest.approx(1.0)                                   # 전진 과속 무벌점
    assert float(out[1]) == pytest.approx(float(exact[1]))                       # 모자라면 같은 벌점
    assert float(out[2]) == pytest.approx(float(exact[2])) and float(out[2]) < 1  # 후진 명령은 정확 추종 (뒤로 과속도 벌점)
    assert float(out[3]) == pytest.approx(float(exact[3])) and float(out[3]) < 1  # 옆 명령 (cmd_x 0) 은 정확 추종
    assert float(out[4]) == pytest.approx(float(exact[4])) and float(out[4]) < 1  # 열 밖은 정확 추종
    assert float(out[5]) == pytest.approx(float(torch.exp(torch.tensor(-(0.3 ** 2) / std ** 2))))   # 대각 전진: x 과속 무벌점 · y 는 정확
    assert torch.equal(gs.track_lin_fwd_saturated(vel, cmd, std, torch.zeros(6, dtype=torch.bool)), exact)


def test_fwd_saturation_does_not_forgive_lateral_drift_the_componentwise_min_does():
    """성분별 min (EX42_TRACK_LIN_MIN_KINDS) 은 vy 명령 0 에서 왼쪽 쏠림 (vy > 0) 을 무벌점으로 둔다. 이 후보는 y 를 정확 추종으로 둬서 막는다."""
    std = 0.5 ** 0.5
    cmd, vel, on = torch.tensor([[0.8, 0.0]]), torch.tensor([[0.8, 0.3]]), torch.tensor([True])
    assert float(gs.track_lin_mixed(vel, cmd, std, on)[0]) == pytest.approx(1.0)
    assert float(gs.track_lin_fwd_saturated(vel, cmd, std, on)[0]) < 0.9


def test_both_tracking_switches_together_are_refused_and_the_receipt_names_the_new_one():
    from foothold_s2.terrains.ex42_column_reset import build_column_table
    table = build_column_table(["A"] * 50 + ["B"] * 12 + ["C"] * 7 + ["D"] * 3 + ["E"] * 4)
    with pytest.raises(ValueError, match="set one"):
        gs.read_switches(table, {gs.ENV_MIN: "A/gaps", gs.ENV_MIN_FWD: "A/gaps"})
    sw = gs.read_switches(table, {gs.ENV_MIN_FWD: "A/gaps"})
    assert sw["min_fwd_columns"] == GAP_COLS and gs.receipt(sw) == {"gap_switches": {"track_lin_min_fwd_kinds": ["A/gaps"]}}
    assert gs.receipt(gs.read_switches(table, {})) == {}


def test_the_reward_function_reads_the_columns_and_calls_the_tested_formula():
    """start_rewards 의 항 함수가 시험한 식 (track_lin_fwd_saturated) 과 열 마스크를 부른다: 소스 AST 로 대조 (식을 두 곳에 쓰지 않음)."""
    import ast
    src = (Path(__file__).resolve().parents[1] / "rewards" / "start_rewards.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "track_lin_vel_min_fwd_on_columns")
    called = {getattr(c.func, "id", getattr(c.func, "attr", "")) for c in ast.walk(fn) if isinstance(c, ast.Call)}
    assert {"track_lin_fwd_saturated", "column_env_mask"} <= called and [a.arg for a in fn.args.args][:4] == ["env", "command_name", "std", "min_fwd_columns"]


# ---- 후보 1: 실제 entry (E2 plan 행 · 빔 메시) ----------------------------------------------------------------------------------------------

@needs_real
def test_entry_on_puts_the_fwd_function_on_the_gap_columns_only(monkeypatch, isaac_stubs):
    cfg, receipt = _prepare(monkeypatch, {gs.ENV_MIN_FWD: "A/gaps"})
    assert cfg.rewards.track_lin_vel.func is FAKE_FWD
    assert cfg.rewards.track_lin_vel.params["min_fwd_columns"] == list(GAP_COLS)
    assert cfg.rewards.track_lin_vel.params["std"] == 0.5 ** 0.5 and cfg.rewards.track_lin_vel.weight == 2.0   # 항 이름 · std · 가중치 그대로
    assert receipt["gap_switches"] == {"track_lin_min_fwd_kinds": ["A/gaps"]}
    assert "plane_columns" not in cfg.terminations.foot_below_ground.params                                   # 종료는 안 건드림


@needs_real
def test_entry_off_leaves_the_term_and_the_receipt_as_before(monkeypatch, isaac_stubs):
    cfg, receipt = _prepare(monkeypatch, {})
    assert cfg.rewards.track_lin_vel.func is _orig_track and set(cfg.rewards.track_lin_vel.params) == {"command_name", "std"}
    assert "gap_switches" not in receipt


# ---- 후보 2: 명령 (실제 명령 항 · 실제 sampler) ----------------------------------------------------------------------------------------------

N = 3072


def _term(monkeypatch, kinds):
    from foothold_s2.tests.test_ex42_flag_command_contract_cpu import e1f_term
    monkeypatch.delenv("EX42_STONE_FWD_FLOOR", raising=False)
    monkeypatch.delenv("EX42_STONE_FWD_FLOOR_KINDS", raising=False)
    command, runtime, _ = e1f_term(monkeypatch, {}, n=N)
    if kinds:
        from dataclasses import replace
        runtime.plan.stages = [replace(s, gap_forward_kinds=tuple(kinds.split(","))) for s in runtime.plan.stages]
    raw = command._env
    base = raw._ex42_column_table[0]
    raw._ex42_column_table = [base, {"family": "A", "kind": "gaps"}, {"family": "B", "kind": "gap"}, {"family": "A", "kind": "balance_beams"},
                              {"family": "A", "kind": "stepping_stones_low"}]
    runtime.command_allocation.column_continuous = torch.tensor([True] + [False] * 4)
    raw.scene.terrain.terrain_types = (torch.arange(N) % 5).long()
    return command, runtime


def _draw(command):
    command.time_left[:] = 4.0
    command.gen.manual_seed(7)
    command._resample_command(torch.arange(N))
    return command.vel_command_b.clone(), command.slot_current.clone(), command.is_flag_env.clone()


def test_gap_envs_take_the_start_command_and_every_other_env_is_bit_for_bit_unchanged(monkeypatch):
    on, run_on = _term(monkeypatch, "A/gaps")
    cmd_on, slot_on, flag_on = _draw(on)
    off, _ = _term(monkeypatch, "")
    cmd_off, slot_off, flag_off = _draw(off)
    cols = on._env.scene.terrain.terrain_types
    gap = (cols == 1) & ~flag_on
    top = run_on.plan.stages[0].ranges["forward_vx"][1]
    assert torch.equal(flag_on, flag_off) and int(gap.sum()) > 500
    go, turn = gap & (slot_on == 0), gap & ((slot_on == 3) | (slot_on == 4))
    assert torch.equal(go | turn, gap)                                              # 틈 열은 전진 아니면 제자리 돌기뿐 (뒤 · 옆 · 정지 없음)
    assert float(cmd_on[go, 0].min()) >= 0.3 and float(cmd_on[go, 0].max()) <= top and bool((cmd_on[go, 1:] == 0).all())
    assert bool((cmd_on[turn, :2] == 0).all()) and float(cmd_on[turn, 2].abs().max()) <= 1.2 and int(turn.sum()) > 0
    share = int(turn.sum()) / int(gap.sum())
    assert abs(share - 0.3 / top) < 0.05                                            # vx < 0.3 이 제자리 돌기로 (U[0, top] 의 몫)
    assert torch.equal(cmd_on[~gap], cmd_off[~gap]) and torch.equal(slot_on[~gap], slot_off[~gap])   # 다른 열 (B 틈 · 평균대 · 징검돌 · 연속) 비트 그대로
    s = on.gap_forward_summary()
    assert s[0] == ("A/gaps",) and s[1] == int((cols == 1).sum()) and s[3] == int(go.sum()) and s[4] == int(turn.sum()) and s[5] == 0


def test_off_the_sampler_is_the_old_one_and_the_summary_is_none(monkeypatch):
    from foothold_s2.commands import mixed_core as mc
    off, run = _term(monkeypatch, "")
    assert off.gap_forward_summary() is None
    stage = run.plan.stages[0]
    a = mc.resample_stage(mc.make_generator(3), 512, stage, torch.zeros(512))
    b = mc.resample_stage(mc.make_generator(3), 512, stage, torch.zeros(512), None, torch.ones(512, dtype=torch.bool))   # 칸이 꺼져 있으면 마스크를 줘도 그대로
    assert all(torch.equal(a[k], b[k]) for k in a)


def test_a_kind_not_in_the_table_is_an_error_not_a_silent_off(monkeypatch):
    command, _ = _term(monkeypatch, "A/gaps,D/nothing")
    with pytest.raises(ValueError, match="not in the column table"):
        command._resample_command(torch.arange(8))


@needs_real
def test_entry_reads_the_env_into_the_e2_stage_and_refuses_bad_values(monkeypatch):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.scripts import ex42_training_entry as te
    plan = EX42Plan.load(E2_PLAN)
    source = te.load_ex42_stage_zero_source(plan)
    for k in ("EX42_STONE_FWD_FLOOR", "EX42_STONE_FWD_FLOOR_KINDS"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.delenv("EX42_GAP_FWD_CMD_KINDS", raising=False)
    view = te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E2")
    assert view.stages[0].gap_forward_kinds == ()
    monkeypatch.setenv("EX42_GAP_FWD_CMD_KINDS", "A/gaps")
    view = te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E2")
    assert view.stages[0].gap_forward_kinds == ("A/gaps",)
    for bad in ("A/gaps,A/gaps", "gaps", "a/gaps"):
        monkeypatch.setenv("EX42_GAP_FWD_CMD_KINDS", bad)
        with pytest.raises(ValueError, match="EX42_GAP_FWD_CMD_KINDS"):
            te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E2")
