"""W04 깃발 평가: 답을 아는 입력(손으로 계산한 거리 · 각도 · 틱 번호)으로 R04-1 · R04-4 · R04-6 값을 확인한다. Kit 없이 돈다."""

import math

import numpy as np
import pytest
import torch

from foothold_s2.eval import flag_eval as FE


def _t(v, dtype=torch.float32):
    return torch.as_tensor(v, dtype=dtype)


def test_command_hand_values():
    pos = _t([[0.0, 0.0]] * 4)
    yaw = _t([0.0, 0.0, 0.0, math.pi / 2])
    tgt = _t([[1.0, 0.0], [0.0, 1.0], [-1.0, -0.001], [1.0, 0.0]])
    vx, vy, wz, ang = FE.command_from_target(pos, yaw, tgt, torch.ones(4, dtype=torch.bool))
    assert vx.tolist() == pytest.approx([0.6] * 4) and vy.tolist() == [0.0] * 4
    assert ang[0].item() == pytest.approx(0.0, abs=1e-6)                       # 정면 -> 각 0 -> wz 0
    assert wz[0].item() == pytest.approx(0.0, abs=1e-6)
    assert ang[1].item() == pytest.approx(math.pi / 2, abs=1e-6) and wz[1].item() == pytest.approx(1.0)       # 왼쪽 90 도 -> clip 1.0
    assert wz[2].item() == pytest.approx(-1.0)                                  # 거의 뒤(오른쪽으로 도는 쪽) -> clip -1.0
    assert ang[3].item() == pytest.approx(-math.pi / 2, abs=1e-6) and wz[3].item() == pytest.approx(-1.0)     # 몸이 +y 를 보고 깃발은 +x -> 오른쪽으로 90 도


def test_command_small_angle_is_not_clipped_and_no_target_is_zero():
    pos, yaw = _t([[0.0, 0.0], [0.0, 0.0]]), _t([0.0, 0.0])
    tgt = _t([[math.cos(0.3), math.sin(0.3)], [1.0, 0.0]])
    vx, vy, wz, ang = FE.command_from_target(pos, yaw, tgt, torch.tensor([True, False]))
    assert wz[0].item() == pytest.approx(0.3, abs=1e-6) and vx[0].item() == pytest.approx(0.6)
    assert vx[1].item() == 0.0 and wz[1].item() == 0.0                         # 목표 없음 -> 세 칸 0


def _tracker(flags, n=1, steps=20):
    f = np.repeat(np.asarray(flags, dtype=np.float32)[None], n, axis=0)
    return FE.FlagTracker(f, "cpu", num_steps=steps)


def test_reach_radius_is_inclusive_and_order_is_sequential():
    tr = _tracker([[0.5, 0.0], [1.5, 0.0], [2.5, 0.0]])
    yaw = _t([0.0])
    c0 = tr.step(0, _t([[0.0, 0.0]]), yaw)                                     # 거리 정확히 0.5 -> 첫 깃발에 닿음(경계 포함), 목표는 둘째
    assert tr.reach_step.tolist() == [[0, -1, -1]] and tr.idx.item() == 1
    assert c0[0, 0].item() == pytest.approx(0.6)
    tr.step(1, _t([[0.9999, 0.0]]), yaw)                                       # 둘째까지 거리 0.5001 -> 아직
    assert tr.idx.item() == 1
    tr.step(2, _t([[1.0, 0.0]]), yaw)                                          # 거리 0.5 -> 닿음
    assert tr.reach_step.tolist() == [[0, 2, -1]] and tr.idx.item() == 2
    tr.step(3, _t([[3.0, 0.0]]), yaw)                                          # 셋째 닿음 -> 전부 닿음
    assert tr.idx.item() == 3 and tr.reach_step.tolist() == [[0, 2, 3]]
    c = tr.step(4, _t([[3.0, 0.0]]), yaw)
    assert c.tolist() == [[0.0, 0.0, 0.0]]                                     # 마지막 깃발 뒤 정지 명령
    assert tr.target_series[:5, 0].tolist() == [1, 1, 2, 3, 3]                 # 틱마다 현재 목표 번호


def test_two_flags_reached_in_one_tick():
    tr = _tracker([[0.5, 0.0], [0.9, 0.0], [5.0, 0.0]])
    tr.step(7, _t([[0.7, 0.0]]), _t([0.0]))
    assert tr.reach_step.tolist() == [[7, 7, -1]] and tr.idx.item() == 2


def test_inactive_env_gets_zero_command_and_keeps_state():
    tr = _tracker([[0.5, 0.0]], n=2)
    c = tr.step(0, _t([[0.0, 0.0], [0.0, 0.0]]), _t([0.0, 0.0]), active=torch.tensor([True, False]))
    assert tr.reach_step.tolist() == [[0], [-1]]
    assert c[1].tolist() == [0.0, 0.0, 0.0]


def test_new_episode_resets_only_masked_envs():
    tr = _tracker([[0.5, 0.0], [5.0, 0.0]], n=2)
    tr.step(0, _t([[0.0, 0.0], [0.0, 0.0]]), _t([0.0, 0.0]))
    tr.note_fall(1, _t([0.2, 0.2]), torch.tensor([True, True]))
    tr.new_episode(torch.tensor([True, False]))
    assert tr.idx.tolist() == [0, 1] and tr.reach_step[0].tolist() == [-1, -1] and tr.reach_step[1].tolist() == [0, -1]
    assert tr.fall_step.tolist() == [-1, 1]


def test_fall_threshold_is_strict_and_first_tick_only():
    tr = _tracker([[0.5, 0.0]], n=3)
    act = torch.ones(3, dtype=torch.bool)
    tr.note_fall(4, _t([0.25, 0.2499, 0.30]), act)
    assert tr.fall_step.tolist() == [-1, 4, -1]                                # 0.25 는 낙하가 아님(< 0.25)
    tr.note_fall(5, _t([0.10, 0.10, 0.10]), act)
    assert tr.fall_step.tolist() == [5, 4, 5]                                  # 첫 틱만 남는다
    tr.note_fall(6, _t([0.0, 0.0, 0.0]), torch.zeros(3, dtype=torch.bool))
    assert tr.fall_step.tolist() == [5, 4, 5]                                  # 비활성 env 는 안 본다


def test_gauges_hand_values():
    d, a = FE.gauges([0.0, 0.0], 0.0, [3.0, 4.0])
    assert d == pytest.approx(5.0) and a == pytest.approx(math.degrees(math.atan2(4, 3)))        # 5 m, 53.13 도
    d, a = FE.gauges([1.0, 1.0], math.pi / 2, [1.0, 3.0])                      # 몸이 +y, 깃발도 +y 2 m
    assert d == pytest.approx(2.0) and a == pytest.approx(0.0, abs=1e-9)
    d, a = FE.gauges([0.0, 0.0], 0.0, [0.0, -2.0])                             # 오른쪽 90 도 -> -90
    assert d == pytest.approx(2.0) and a == pytest.approx(-90.0)


def test_judge_hand_cases():
    dt = 0.02
    reach = np.array([[0, 5, 10, 30], [0, 8, -1, -1], [-1, -1, -1, -1], [0, 4, 9, 20]])
    fall = np.array([-1, 40, -1, 25])
    j = FE.judge(reach, fall, np.array([300, 40, 300, 300]), 300, dt)
    assert j["flag_reached_n"].tolist() == [4, 2, 0, 4]
    assert j["flag_last_reached"].tolist() == [True, False, False, True]
    assert j["flag_last_reach_time_s"][0] == pytest.approx(0.6) and np.isnan(j["flag_last_reach_time_s"][1])
    assert j["flag_fall"].tolist() == [False, True, False, True]
    assert j["flag_fell_before_last"].tolist() == [False, True, False, False]    # 3번 env: 마지막 깃발(틱 20)에 닿은 뒤(틱 25) 넘어짐 -> 도달 전 낙하 아님
    assert j["flag_fall_time_s"][1] == pytest.approx(0.8)
    assert bool(j["flag_order_ok"]) and int(j["flag_count"]) == 4
    assert j["flag_reach_time_s"][1].tolist()[:2] == pytest.approx([0.0, 0.16]) and np.isnan(j["flag_reach_time_s"][1, 2])


def test_judge_flags_a_broken_order():
    j = FE.judge(np.array([[-1, 3, -1]]), np.array([-1]), np.array([10]), 10, 0.02)          # 둘째만 닿음 = 순서 위반
    assert not bool(j["flag_order_ok"])
    j2 = FE.judge(np.array([[5, 3, -1]]), np.array([-1]), np.array([10]), 10, 0.02)           # 틱 번호가 줄어듦
    assert not bool(j2["flag_order_ok"])


def test_continuous_layout():
    f = FE.continuous_env_flags(3)
    assert f.shape == (3, 4, 2)
    assert f[0, :, 0].tolist() == [0.5, 1.5, 2.5, 3.5] and f[:, :, 1].sum() == 0.0


@pytest.mark.parametrize("kind,diff", [("gaps", 0.55), ("stepping_stones_high", 0.95), ("stepping_beams", 0.35), ("balance_beams", 0.75), ("stepping_stones_low", 0.15)])
def test_sparse_flags_sit_on_support_and_pit_floor_is_the_depth(kind, diff):
    from foothold_s2.eval import start_sheet as ss
    from foothold_s2.terrains import sparse_terrains as st

    tile = st.build_tile(kind, diff)
    start_kind, randomness, _g = st.KINDS[kind]
    rng = np.random.default_rng(st.seed_of(kind, diff))
    geom = ss.generate(start_kind, st.level_of(diff), rng, randomness=randomness) if randomness is not None else ss.generate(start_kind, st.level_of(diff), rng)
    assert float(np.asarray(tile.boxes)[:, 5].min()) == pytest.approx(-geom.depth, abs=1e-9)          # 구덩이 바닥 윗면 = -depth (깃발 배치가 쓰는 값)
    fl = FE.sparse_flags_rel(tile)
    assert fl.shape == (FE.SPARSE_COUNT, 2)
    grid = st.height_grid(tile.boxes, res=0.05)
    floor_top = -geom.depth

    for (rx, ry) in fl:                                                         # 모든 깃발이 구덩이 바닥이 아닌 윗면 위
        x, y = rx + FE.SPARSE_START_X, ry + FE.SPARSE_START_Y
        assert grid[int(x / 0.05), int(y / 0.05)] > floor_top + 0.1

    xs = fl[:, 0] + FE.SPARSE_START_X
    assert xs[-1] == pytest.approx(FE.SPARSE_GOAL_PLATFORM_X, abs=0.61)                  # 마지막은 도착 단 근처
    assert np.all(np.diff(xs) > 0.2)                                           # 앞에서 뒤로 차례로


def test_sparse_env_flags_share_cells():
    from foothold_s2.terrains import sparse_terrains as st

    tile_a, tile_b = st.build_tile("gaps", 0.55), st.build_tile("balance_beams", 0.55)
    cells = {(5, 3): tile_a, (5, 4): tile_b}
    tiles = [{"env": 0, "kind": "gaps", "level": 5, "col": 3}, {"env": 1, "kind": "balance_beams", "level": 5, "col": 4}, {"env": 2, "kind": "gaps", "level": 5, "col": 3}]
    out = FE.sparse_env_flags(tiles, cells)
    assert out.shape == (3, FE.SPARSE_COUNT, 2) and np.array_equal(out[0], out[2])


def test_tracker_follows_flags_in_a_toy_world():
    """질점 시뮬: 몸이 명령대로 움직인다(vx 를 몸 방향으로, wz 로 회전). 연속 4 깃발이 차례로 닿고 마지막 뒤 멈춘다."""
    tr = FE.FlagTracker(FE.continuous_env_flags(1), "cpu", num_steps=400)
    pos, yaw = torch.tensor([[0.0, 0.0]]), torch.tensor([0.0])

    for k in range(400):
        cmd = tr.step(k, pos, yaw)
        yaw = yaw + cmd[:, 2] * 0.02
        pos = pos + torch.stack([torch.cos(yaw), torch.sin(yaw)], -1) * cmd[:, :1] * 0.02

    assert tr.idx.item() == 4 and (tr.reach_step >= 0).all()
    assert tr.reach_step[0, 0].item() == 0                                      # 출발점이 첫 깃발 0.5 m 안 -> 틱 0
    assert abs(pos[0, 0].item() - 3.0) < 0.1                                    # 마지막 깃발(3.5)의 0.5 m 안(x 3.0)에서 닿는 순간 멈춤


def test_z_fall_can_be_disabled_for_continuous_terrain_and_termination_still_counts():
    """연속 지형: 원점 기준 z 가 내리막에서 0.25 m 아래여도 서 있는 env 는 낙하가 아니다(예행 8 env 중 5 가 오검출). 종료 조건만 낙하."""
    tr = FE.FlagTracker(FE.continuous_env_flags(2), "cpu", z_fall=False)
    act = torch.ones(2, dtype=torch.bool)
    tr.note_fall(3, _t([0.10, 0.10]), act)
    assert tr.fall_step.tolist() == [-1, -1]
    tr.note_done(5, torch.tensor([True, False]), act)
    assert tr.fall_step.tolist() == [5, -1] and tr.fall_kind.tolist() == [2, 0]


def test_first_event_wins_between_z_and_termination():
    tr = FE.FlagTracker(FE.continuous_env_flags(1), "cpu", z_fall=True)
    act = torch.ones(1, dtype=torch.bool)
    tr.note_fall(4, _t([0.2]), act)
    tr.note_done(6, torch.tensor([True]), act)
    assert tr.fall_step.tolist() == [4] and tr.fall_kind.tolist() == [1]
    tr2 = FE.FlagTracker(FE.continuous_env_flags(1), "cpu", z_fall=True)
    tr2.note_done(2, torch.tensor([True]), act)
    tr2.note_fall(3, _t([0.1]), act)
    assert tr2.fall_step.tolist() == [2] and tr2.fall_kind.tolist() == [2]
