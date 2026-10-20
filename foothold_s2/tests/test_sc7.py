"""SC-7 L0: 깃발 속도 커리큘럼 갱신 · 벌점 켜짐 비율 기록 · 추종식 A/B 키."""

import ast
import os

import pytest
import torch

from foothold_s2.commands import mixed_core as mc
from foothold_s2.curriculum import terrain_levels_mixed as tlm
from foothold_s2.rewards import core, penalty_log

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def acc(lin, ang, n):
    a = tlm._Acc()
    a.add(lin * n, ang * n, n)

    return a


def test_apply_range_update_raises_free_and_flag_limits_independently():
    rc = mc.RangeCurriculum()
    up = tlm.apply_range_update(rc, acc(0.9, 0.9, 10), acc(0.9, 0.9, 10), 1, flag_median_level=3.0)
    assert up == (True, False) and rc.vmax_x == pytest.approx(1.25) and rc.flag_vmax == pytest.approx(1.0)
    up = tlm.apply_range_update(rc, acc(0.5, 0.9, 10), acc(0.85, 0.85, 10), 2, flag_median_level=5.0)
    assert up == (False, True) and rc.vmax_x == pytest.approx(1.25) and rc.flag_vmax == pytest.approx(1.25)


def test_apply_range_update_with_no_episodes_changes_nothing_and_resets_accumulators():
    rc = mc.RangeCurriculum()
    a, b = acc(0.9, 0.9, 4), tlm._Acc()
    assert tlm.apply_range_update(rc, a, b, 1, 9.0) == (True, False)
    assert a.n == 0 and b.n == 0


def test_penalty_log_reports_the_previous_iterations_mean_fraction():
    log = penalty_log.PenaltyLog()
    assert log.roll(0)["collision"] == 0.0
    for v in ([1.0, 0.0, 0.0, 0.0], [1.0, 1.0, 0.0, 0.0]):                 # 켜짐 비율 0.25 · 0.5 -> 평균 0.375
        log.add("collision", torch.tensor(v))
        log.add("stumble", torch.zeros(4))
    out = log.roll(1)
    assert out["collision"] == pytest.approx(0.375) and out["stumble"] == 0.0 and out["foot_edge"] == 0.0
    log.add("collision", torch.ones(4))
    assert log.roll(1)["collision"] == pytest.approx(0.375)               # 같은 반복 안에서는 값이 안 바뀐다
    assert log.roll(2)["collision"] == pytest.approx(1.0)


def test_penalty_activation_curriculum_term_shape():
    env = type("E", (), {})()
    env.common_step_counter = 48
    assert penalty_log.penalty_activation(env, None) == {"collision": 0.0, "stumble": 0.0, "foot_edge": 0.0}
    penalty_log.record(env, "foot_edge", torch.tensor([0.0, -1.5]))
    env.common_step_counter = 72
    assert penalty_log.penalty_activation(env, None)["foot_edge"] == pytest.approx(0.5)


def test_tracking_forms_a_and_b_differ_on_slow_reverse_and_match_on_forward_error():
    cmd, v = torch.tensor([[-0.5, 0.0]]), torch.tensor([[-0.2, 0.0]])
    a, b = core.track_lin_min_form(v, cmd), core.track_lin_exact(v, cmd)
    assert float(a) == pytest.approx(1.0) and float(b) < 0.75


def test_env_cfg_exposes_the_a_b_key_and_a_form_function_exists():
    src = open(os.path.join(PKG, "tasks", "s1_env_cfg.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    fields = {n.target.id: n.value.value for n in ast.walk(tree)
              if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and isinstance(n.value, ast.Constant)}
    assert fields.get("track_lin_form") == "B"                             # 기본은 B(정확 추종)
    assert "track_lin_vel_min_form" in src and "A 또는 B" in src
    rew = open(os.path.join(PKG, "rewards", "start_rewards.py"), encoding="utf-8").read()
    assert "def track_lin_vel_min_form" in rew and "func=collision_term" in rew
