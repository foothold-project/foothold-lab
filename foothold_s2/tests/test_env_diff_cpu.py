"""환경 차이 확인 (env_diff) · 물리 백엔드 고정 (lab_compat) 의 CPU 시험: 가짜 값으로 식과 거절 조건."""
import sys
import types
from types import SimpleNamespace

import numpy as np
import pytest

from foothold_s2 import lab_compat as lc
from foothold_s2.nav import env_diff as ed


def _err(cmd, n, ticks=60, actual_ratio=None):
    ax = int(np.argmax(np.abs(cmd)))
    e = np.zeros((ticks, 5, n, 3))
    if actual_ratio is not None:
        e[..., ax] = (np.asarray(actual_ratio) * cmd[ax] - cmd[ax])[None, None, :]
    return e


def test_score_case_counts_success_fall_and_stall():
    n = 4
    cmd = (0.2, 0.0, 0.0)
    ratio = np.array([1.0, 1.1, 0.3, 1.0])                       # env 2 는 못 간다
    done = np.array([False, False, False, True])                 # env 3 은 넘어짐
    start = np.zeros((n, 2)); end = np.array([[1.2, 0], [0, 1.3], [0.2, 0], [0, 0]])      # 시작 방향 무작위: +x 가 아니어도 직선 거리로 잰다
    out = ed.score_case(_err(cmd, n, actual_ratio=ratio), done, start, end, cmd)
    assert out["success"] == 2 and out["fell"] == 1 and out["mae_over"] == 1
    assert out["mean_move_m"] == pytest.approx((1.2 + 1.3 + 0.2) / 3) and out["mean_ratio"] == pytest.approx((1.0 + 1.1 + 0.3) / 3)


def test_yaw_and_side_commands_use_their_own_axis():
    n = 2
    out = ed.score_case(_err((0.0, 0.0, 0.5), n, actual_ratio=[1.0, 0.5]), np.zeros(n, bool), np.zeros((n, 2)), np.zeros((n, 2)), (0.0, 0.0, 0.5))
    assert out["success"] == 1
    out = ed.score_case(_err((0.0, -0.2, 0.0), n, actual_ratio=[1.0, 1.0]), np.zeros(n, bool), np.zeros((n, 2)), np.zeros((n, 2)), (0.0, -0.2, 0.0))
    assert out["success"] == 2


def test_verdict_needs_no_fall_and_enough_success():
    ok = {"fwd0.1": {"envs": 10, "success": 9, "fell": 0}, "yaw0.5": {"envs": 10, "success": 9, "fell": 1}}
    v = ed.verdict(ok)
    assert v["per_case_pass"] == {"fwd0.1": True, "yaw0.5": False} and not v["all_pass"]


def test_flat_room_spec_is_a_flat_room_without_primitives():
    spec = ed.flat_room_spec(0)
    assert spec["primitives"] == [] and not np.asarray(spec["tiles"]).any()


class _FakeRaw:
    def __init__(self, manager_name, cfg):
        self.sim = SimpleNamespace(physics_manager=type(manager_name, (), {}))
        self.cfg = SimpleNamespace(sim=SimpleNamespace(physics=cfg))


def test_physics_report_and_refusal_of_newton(monkeypatch):
    monkeypatch.setenv("FOOTHOLD_LAB_MAJOR", "3")
    px = _FakeRaw("PhysxManager", SimpleNamespace(solver_type=1))
    assert lc.require_physx(px) == {"manager": "PhysxManager", "cfg": "SimpleNamespace", "solver_type": 1, "is_physx": True}
    with pytest.raises(RuntimeError, match="not PhysX"):
        lc.require_physx(_FakeRaw("NewtonManager", SimpleNamespace(solver_type=None)))
    monkeypatch.setenv("FOOTHOLD_LAB_MAJOR", "2")
    assert lc.require_physx(SimpleNamespace(cfg=SimpleNamespace(sim=SimpleNamespace())))["is_physx"] is True      # 2.x 는 늘 PhysX


def test_apply_physx_sim_pins_physx_in_3_and_keeps_the_2x_field(monkeypatch):
    class PhysxCfg:
        def __init__(self, gpu_max_rigid_patch_count, solver_type):
            self.gpu_max_rigid_patch_count, self.solver_type = gpu_max_rigid_patch_count, solver_type

    mod = types.ModuleType("isaaclab_physx.physics"); mod.PhysxCfg = PhysxCfg
    pkg = types.ModuleType("isaaclab_physx"); pkg.physics = mod
    monkeypatch.setitem(sys.modules, "isaaclab_physx", pkg); monkeypatch.setitem(sys.modules, "isaaclab_physx.physics", mod)
    monkeypatch.setenv("FOOTHOLD_LAB_MAJOR", "3")
    sim = SimpleNamespace(physics=None)
    lc.apply_physx_sim(sim, 5)
    assert isinstance(sim.physics, PhysxCfg) and sim.physics.gpu_max_rigid_patch_count == 5 and sim.physics.solver_type == 1       # TGS
    monkeypatch.setenv("FOOTHOLD_LAB_MAJOR", "2")
    sim2 = SimpleNamespace(physx=SimpleNamespace(gpu_max_rigid_patch_count=0))
    lc.apply_physx_sim(sim2, 7)
    assert sim2.physx.gpu_max_rigid_patch_count == 7


def test_run_cases_on_a_fake_perfect_follower_passes_every_case_and_calls_the_hook():
    from foothold_s2.nav import command_space as cs
    from foothold_s2.tests.test_nav_env_cpu import PREP, _make

    env, _lower, nav = _make(cs.slots_from_stage_row(PREP, "E1F"), n=3, lag=1.0)
    seen = []
    out = ed.run_cases(nav, on_tick=lambda name, t, s: seen.append((name, t)))
    assert list(out) == [name for name, _ in ed.CASES] and all(v["success"] == 3 and v["fell"] == 0 for v in out.values())
    assert len(seen) == len(ed.CASES) * 60 and ed.verdict(out)["all_pass"]
    assert out["fwd0.2"]["mean_move_m"] == pytest.approx(0.2 * 6.0, rel=0.05)               # 6 초 x 0.2 m/s
