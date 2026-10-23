"""명령 생성기 L0 (14 §9 · 3.2 절). 학습과 같은 torch 함수를 CPU 에서 부른다. 답을 아는 입력 + negative control."""

import math

import pytest
import torch

from foothold_s2.commands import mixed_core as mc

P = mc.CommandParams()
PI = math.pi


def gen(seed=7):
    return mc.make_generator(seed)


def approx(x, **kw):
    return pytest.approx(x, **kw)


# ---------------------------------------------------------------- (a) 자유 속도 분포


def test_free_velocity_keep_rates_and_signs_1000_samples():
    # 14 §9 는 1,000 표본 +-0.03 이다. 0.5 비율의 표준오차가 0.016 이라 0.03 은 1.9 시그마(우연히 6 % 실패)라서
    # 1,000 표본은 +-0.05(3 시그마)로, 정밀 확인은 아래 20만 표본 시험이 맡는다.
    cmd = mc.sample_free(gen(1), 1000, P)
    for col, keep in ((0, 0.9), (1, 0.75), (2, 0.5)):
        rate = float((cmd[:, col] != 0.0).float().mean())
        assert abs(rate - keep) <= 0.05, (col, rate)
    for col in (0, 1, 2):
        nz = cmd[cmd[:, col] != 0.0, col]
        assert abs(float((nz > 0).float().mean()) - 0.5) <= 0.06


def test_free_velocity_magnitude_is_uniform_0_to_1_1000_samples():
    cmd = mc.sample_free(gen(2), 1000, P)
    mag = cmd[cmd[:, 0] != 0.0, 0].abs()
    assert abs(float((mag < 0.5).float().mean()) - 0.5) <= 0.05
    assert float(mag.max()) <= 1.0 and float(mag.min()) >= 0.0
    assert float((mag < 0.3).float().mean()) > 0.2          # 저속 0~0.5 가 실제로 나온다 (J-F)


def test_free_velocity_large_sample_precision():
    cmd = mc.sample_free(gen(3), 200_000, P)
    mag = cmd[cmd[:, 1] != 0.0, 1].abs()
    assert abs(float((mag < 0.5).float().mean()) - 0.5) < 0.005
    assert abs(float((cmd[:, 1] != 0.0).float().mean()) - 0.75) < 0.005
    assert float(cmd[:, 2].abs().max()) <= 2.0


def test_negative_control_vmax_changes_the_distribution():
    cmd = mc.sample_free(gen(4), 50_000, P, vmax_x=1.5)
    mag = cmd[cmd[:, 0] != 0.0, 0].abs()
    assert float(mag.max()) > 1.4 and abs(float((mag < 0.75).float().mean()) - 0.5) < 0.01
    base = mc.sample_free(gen(4), 50_000, P)[:, 0].abs()
    base = base[base > 0]
    assert abs(float((base < 0.75).float().mean()) - 0.75) < 0.01


# ---------------------------------------------------------------- (b) env 비율 표 (14 §3.2)


def _mean(x):
    return float(x.float().mean())


def test_mode_ratios_after_1000_iterations_match_table():
    out = mc.resample_free_modes(gen(5), 400_000, P, iteration=2000)
    stand, spin, heading = _mean(out["stand"]), _mean(out["spin"]), _mean(out["heading"])
    free = 1 - stand - spin - heading
    assert abs(stand - 0.10) < 0.004
    assert abs(spin - 0.18) < 0.004
    assert abs(heading - 0.30) < 0.004
    assert abs(free - 0.42) < 0.004


def test_mode_ratios_before_1000_iterations_have_no_spin():
    out = mc.resample_free_modes(gen(6), 400_000, P, iteration=500)
    assert float(out["spin"].sum()) == 0.0
    assert abs(_mean(out["stand"]) - 0.10) < 0.004
    assert abs(_mean(out["heading"]) - 0.30) < 0.004
    assert abs((1 - _mean(out["stand"]) - _mean(out["heading"])) - 0.60) < 0.004


def test_flags_are_exclusive_and_stand_wins():
    out = mc.resample_free_modes(gen(8), 100_000, P, iteration=2000)
    assert not bool((out["stand"] & out["spin"]).any())
    assert not bool((out["stand"] & out["heading"]).any())
    assert not bool((out["spin"] & out["heading"]).any())
    assert bool((out["cmd"][out["stand"]] == 0.0).all())
    spin = out["cmd"][out["spin"]]
    assert bool((spin[:, :2] == 0.0).all()) and float(spin[:, 2].abs().max()) <= 2.0


def test_continuous_group_totals_match_the_table_for_env_split():
    # 이어진 지형 env 전체: 깃발 20 % + 자유 속도 80 % (정지 8 · 회전 14.4 · heading 24 · 자유 wz 33.6)
    n = 500_000
    flag = torch.arange(n) % 5 == 0
    out = mc.resample_free_modes(gen(9), n, P, iteration=2000)
    free = ~flag
    labels = mc.mode_labels(flag, out["stand"] & free, out["spin"] & free, out["heading"] & free)
    total = 0.0
    for name, want in (("flag", 0.20), ("stand", 0.08), ("spin", 0.144), ("heading", 0.24), ("free_wz", 0.336)):
        share = _mean(labels == mc.MODES.index(name))
        total += share
        assert abs(share - want) < 0.004, name
    assert abs(total - 1.0) < 1e-6


def test_heading_flag_off_negative_control_gives_free_wz():
    p = mc.CommandParams(heading_flag_after=0.0, heading_flag_before=0.0)
    out = mc.resample_free_modes(gen(10), 100_000, p, iteration=2000)
    assert int(out["heading"].sum()) == 0
    rows = ~(out["stand"] | out["spin"])
    wz = out["cmd"][rows, 2]
    wz = wz[wz != 0.0]
    assert abs(_mean(wz.abs() < 1.0) - 0.5) < 0.01        # 자유 wz 는 U[-2, 2]


# ---------------------------------------------------------------- heading 식 (14 §9 L0)


def test_heading_formula_hand_values():
    assert float(mc.heading_wz(PI / 2, 0.0)) == approx(0.785398, abs=1e-5)
    assert float(mc.heading_wz(-PI + 0.1, PI - 0.1)) == approx(0.1, abs=1e-5)     # wrap 오차 0.2
    assert float(mc.heading_wz(PI, 0.0)) == approx(PI / 2, abs=1e-5)              # 자름 +-2 는 안 걸림
    assert abs(float(mc.heading_wz(PI, 0.0))) < 2.0


def test_heading_applies_only_to_flagged_envs_and_stand_wins():
    cmd = torch.tensor([[0.5, 0.0, 0.3], [0.5, 0.0, 0.3], [0.0, 0.0, 0.0]])
    heading = torch.tensor([True, False, True])
    stand = torch.tensor([False, False, True])
    out = mc.apply_heading(cmd, heading, stand, torch.full((3,), PI / 2), torch.zeros(3), P)
    assert float(out[0, 2]) == approx(PI / 4, abs=1e-5)
    assert float(out[1, 2]) == approx(0.3, abs=1e-6)        # heading 이 아니면 자유 wz 그대로
    assert bool((out[2] == 0.0).all())                       # 정지 우선
    assert bool((out[:, :2] == cmd[:, :2]).all())


def test_heading_wz_stays_within_157_in_the_sampled_distribution():
    r = mc.resample_free_modes(gen(11), 100_000, P, iteration=2000)
    yaw = mc._u(gen(12), (100_000,), -PI, PI)
    wz = mc.heading_wz(r["psi_star"], yaw)
    assert float(wz.abs().max()) <= PI / 2 + 1e-5


def test_wrap_to_pi_matches_isaac_lab_rule():
    w = mc.wrap_to_pi(torch.tensor([PI, -PI, 3 * PI, -3 * PI, 0.0, 2 * PI]))
    assert w[0] == approx(PI, abs=1e-6) and w[1] == approx(-PI, abs=1e-6)
    assert float(w[2]) == approx(PI, abs=1e-5) and float(w[3]) == approx(-PI, abs=1e-5)
    assert float(w[4]) == 0.0 and abs(float(w[5])) < 1e-5


# ---------------------------------------------------------------- 깃발 (14 §9 L0)


def _two_flags(n=1):
    flags = torch.tensor([[1.0, 0.0], [2.0, 1.0]]).repeat(n, 1, 1)
    st = mc.FlagState.new(flags)
    st.v[:] = 0.5
    return st


def _step(st, pos, yaw=0.0, dt=0.02, params=P):
    pos = torch.as_tensor(pos, dtype=torch.float32).reshape(-1, 2)
    yaw = torch.as_tensor(yaw, dtype=torch.float32).reshape(-1) * torch.ones(len(pos))
    return mc.flag_step(st, pos, yaw, dt, params)


def test_flag_command_toward_first_flag_then_next_flag_at_45_degrees():
    st = _two_flags()
    cmd = _step(st, [0.0, 0.0])
    assert cmd[0].tolist() == approx([0.5, 0.0, 0.0], abs=1e-6)
    cmd = _step(st, [1.0, 0.0])                       # 첫 깃발 0.5 m 안
    assert int(st.idx[0]) == 1
    assert cmd[0, :2].tolist() == approx([0.35355339, 0.35355339], abs=1e-6)
    assert float(cmd[0, 2]) == approx(PI / 4, abs=1e-6)


def test_flag_negative_control_empty_flag_list_gives_zero():
    st = mc.FlagState.new(torch.zeros(1, 2, 2), n_flags=torch.tensor([0]))
    st.v[:] = 0.8
    assert _step(st, [0.0, 0.0])[0].tolist() == [0.0, 0.0, 0.0]


def test_flag_rotated_body_frame():
    st = mc.FlagState.new(torch.tensor([[[0.0, 1.0], [0.0, 2.0]]]))
    st.v[:] = 1.0
    cmd = _step(st, [0.0, 0.0], yaw=PI / 2)
    assert cmd[0].tolist() == approx([1.0, 0.0, 0.0], abs=1e-6)


def test_last_flag_holds_zero_for_at_least_two_seconds():
    st = _two_flags()
    _step(st, [1.0, 0.0])
    cmd = _step(st, [2.0, 1.0])
    assert bool((cmd == 0.0).all()) and float(st.hold_left[0]) == approx(2.0 - 0.02, abs=1e-5)
    for _ in range(50):
        cmd = _step(st, [2.0, 1.0])
        assert bool((cmd == 0.0).all())
    assert float(st.hold_left[0]) == approx(0.98, abs=1e-4)


def test_flag_speed_below_threshold_becomes_in_place_spin():
    st = _two_flags()
    st.v[:] = 0.2
    st.spin_wz[:] = -0.9
    assert _step(st, [0.0, 0.0])[0].tolist() == approx([0.0, 0.0, -0.9], abs=1e-6)


def test_flag_resample_statistics_1000_samples():
    n = 1000
    st = mc.FlagState.new(torch.tensor([[3.0, 0.0], [6.0, 0.0]]).repeat(n, 1, 1))
    mc.flag_resample(st, torch.arange(n), gen(13), P)
    cmd = mc.flag_step(st, torch.zeros(n, 2), torch.zeros(n), 0.02, P)
    spin = cmd[:, 0] == 0.0
    assert abs(_mean(spin) - 0.3) <= 0.05                  # v < 0.3 의 확률 (1,000 표본 3 시그마)
    assert float(cmd[spin, 2].abs().max()) <= 1.2
    assert bool((cmd[spin, 1] == 0.0).all())
    assert float(cmd[~spin, 2].abs().max()) <= 1.0
    speed = torch.hypot(cmd[~spin, 0], cmd[~spin, 1])
    assert float(speed.max()) <= 1.0 + 1e-6 and float(speed.min()) >= 0.3 - 1e-6


def test_flag_spin_probability_large_sample():
    n = 100_000
    st = mc.FlagState.new(torch.tensor([[3.0, 0.0], [6.0, 0.0]]).repeat(n, 1, 1))
    mc.flag_resample(st, torch.arange(n), gen(16), P)
    assert abs(_mean(st.v < 0.3) - 0.3) < 0.005


def test_backoff_after_a_passed_flag_gives_negative_forward_and_returns():
    p = mc.CommandParams(backoff_prob=1.0)
    st = _two_flags()
    _step(st, [1.0, 0.0], params=p)                         # 첫 깃발 통과
    mc.flag_resample(st, torch.tensor([0]), gen(14), p)     # 재추출에서 물러나기 켜짐
    assert float(st.backoff_left[0]) == approx(2.0)
    st.v[:] = 0.5
    cmd = _step(st, [1.5, 0.0], params=p)
    assert float(cmd[0, 0]) == approx(-float(st.backoff_v[0]), abs=1e-6)
    assert -0.3 - 1e-6 <= float(cmd[0, 0]) <= -0.1 + 1e-6
    assert abs(float(cmd[0, 1])) < 1e-6 and float(cmd[0, 2]) == 0.0
    for _ in range(100):                                    # 2 s 뒤 전진 깃발 방향으로 복귀
        cmd = _step(st, [1.5, 0.0], params=p)
    assert float(st.backoff_left[0]) == 0.0
    cmd = _step(st, [1.5, 0.0], params=p)                   # 물러나기가 끝난 다음 스텝부터 전진 깃발 쪽
    assert float(cmd[0, 0]) > 0.0


def test_backoff_negative_control_no_passed_flag_never_turns_on():
    p = mc.CommandParams(backoff_prob=1.0)
    st = _two_flags()
    mc.flag_resample(st, torch.tensor([0]), gen(15), p)
    assert float(st.backoff_left[0]) == 0.0


def test_flag_state_reset_clears_progress_and_swaps_flags():
    st = _two_flags(2)
    _step(st, [[1.0, 0.0], [0.0, 0.0]])
    assert int(st.idx[0]) == 1
    new_flags = torch.tensor([[[9.0, 9.0], [10.0, 9.0]]])
    st.reset(torch.tensor([0]), flags=new_flags)
    assert int(st.idx[0]) == 0 and int(st.passed[0]) == 0
    assert st.flags[0, 0].tolist() == [9.0, 9.0]


def test_straight_flag_line_is_four_flags_one_meter_apart_and_inside_the_tile():
    f = mc.straight_flag_line(torch.tensor([10.0, -3.0]))
    assert f.shape == (4, 2)
    assert f.flatten().tolist() == approx([10.5, -3, 11.5, -3, 12.5, -3, 13.5, -3], abs=1e-6)
    assert float((f[:, 0] - 10.0).max()) == approx(3.5) and float((f[:, 0] - 10.0).min()) > 0   # 경계(+4 m)에서 0.5 m 안쪽, 앞쪽만
    old = mc.straight_flag_line(torch.tensor([0.0, 0.0]), first=1.0)     # 예전 배치는 네 번째가 경계 위
    assert float(old[:, 0].max()) == approx(4.0)


def test_flag_speed_range_curriculum_needs_tracking_and_median_level_and_caps_at_1_5():
    c = mc.RangeCurriculum()
    assert not c.update_flag(0.9, 0.9, 4.9)                  # 레벨 중앙값 미달
    assert not c.update_flag(0.79, 0.9, 7.0)                 # 추종 미달
    assert c.update_flag(0.8, 0.8, 5.0) and c.flag_vmax == approx(1.25)
    assert c.update_flag(0.9, 0.9, 6.0) and c.flag_vmax == approx(1.5)
    assert not c.update_flag(0.9, 0.9, 9.0) and c.flag_vmax == approx(1.5)    # 상한
    assert c.vmax_x == approx(1.0)                           # 자유 속도 상한은 따로


def test_flag_vmax_is_in_the_saved_state_and_survives_a_resume():
    c = mc.RangeCurriculum()
    c.update_flag(0.9, 0.9, 6.0)
    saved = dict(vars(c))                                    # start_runner._env_state 가 하는 것과 같다
    d = mc.RangeCurriculum()
    for k, v in saved.items():
        setattr(d, k, v)
    assert d.flag_vmax == approx(1.25)


# ---------------------------------------------------------------- 범위 커리큘럼 · 노출 로그


def test_range_curriculum_expands_in_quarter_steps_up_to_caps():
    c = mc.RangeCurriculum()
    assert not c.update(0.79, 0.9)
    assert c.update(0.8, 0.8, iteration=10)
    assert (c.vmax_x, c.vmax_y) == (1.25, 1.0)          # vy 는 1.0 까지
    assert c.update(0.9, 0.9) and c.vmax_x == 1.5
    assert not c.update(0.9, 0.9) and c.vmax_x == 1.5   # 상한
    assert c.history[0] == {"iteration": 10, "vmax_x": 1.25, "vmax_y": 1.0}


def test_direction_bins_and_exposure_log():
    cmd = torch.tensor([[0.5, 0, 0], [-0.5, 0, 0], [0, 0.5, 0], [0, -0.5, 0], [0, 0, 1.0], [0, 0, 0],
                        [0.3, 0.4, 0]])
    names = [mc.DIRECTIONS[i] for i in mc.direction_bin(cmd).tolist()]
    assert names == ["front", "back", "left", "right", "spin", "zero", "left"]
    log = mc.ExposureLog()
    modes = torch.tensor([mc.MODES.index(m) for m in ("flag", "stand", "spin", "heading", "free_wz", "free_wz",
                                                      "free_wz")])
    log.add(modes, cmd, 0.02)
    snap = log.snapshot()
    assert sum(snap["mode_ratio"].values()) == approx(1.0)
    assert snap["direction_ratio"]["spin"] == approx(1 / 7)
    assert snap["mode_ratio"]["free_wz"] == approx(3 / 7)


def test_start_mode_command_distribution_is_the_start_paper_one():
    """G0-start (lead 10/21): vx U[0,1.5] · vy 0 · vx < 0.3 이면 vx = 0 · wz U[-1.2,1.2], 그 밖은 wz 0. 0.3 미만 가지 비율 약 20 %."""
    import torch
    from foothold_s2.commands import mixed_core as mc

    gen = mc.make_generator(0)
    params = mc.CommandParams(start_mode=True)
    out = mc.resample_free_modes(gen, 200000, params, iteration=0)
    cmd, spin = out["cmd"], out["spin"]
    assert float(cmd[:, 1].abs().max()) == 0.0                                                 # vy 는 항상 0
    assert abs(float(spin.float().mean()) - 0.3 / 1.5) < 0.01                                  # 제자리 회전 가지 ≈ 20 %
    assert float(cmd[spin][:, 0].abs().max()) == 0.0 and float(cmd[spin][:, 2].abs().max()) <= 1.2 + 1e-6
    assert float(cmd[spin][:, 2].abs().mean()) > 0.55 and float(cmd[spin][:, 2].abs().mean()) < 0.65     # U[-1.2,1.2] 의 |wz| 평균 0.6
    assert float(cmd[~spin][:, 2].abs().max()) == 0.0                                          # 전진 중 yaw 없음 (원문에 없음)
    assert float(cmd[~spin][:, 0].min()) >= 0.3 and float(cmd[~spin][:, 0].max()) <= 1.5
    assert not bool(out["stand"].any()) and not bool(out["heading"].any())
    default = mc.resample_free_modes(mc.make_generator(0), 1000, mc.CommandParams(), iteration=0)
    assert float(default["cmd"][:, 1].abs().max()) > 0.0                                       # 기본(열린) 생성기는 그대로: vy 가 있다
