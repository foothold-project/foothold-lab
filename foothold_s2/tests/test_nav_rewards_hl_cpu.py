import numpy as np
import pytest

from foothold_s2.nav import rewards_hl as rw


def _state(n=1, **kw):
    z = lambda *shape: np.zeros(shape)
    base = dict(pos_xy=z(n, 2), subgoal_xy=np.full((n, 2), 5.0), v_xy=z(n, 2), v_z=z(n), omega_xy=z(n, 2),
                q=z(n, 12), q0=z(12), cmd=z(n, 3), cmd_prev=z(n, 3), cmd_prev2=z(n, 3), actual=z(n, 3),
                v_des=np.full(n, 0.6), eta=np.ones(n), limited=np.zeros(n, bool), collision=np.zeros(n, bool))
    base.update(kw)
    return rw.HLState(**base)


def test_weights_are_table_ii():
    assert rw.WEIGHTS == {"r1": 5.0, "r2": 0.5, "r3": 0.25, "r4": -0.1, "r5": -0.1, "r6": -0.2, "r7": -0.1, "r8": -0.04,
                          "r9": -2.5, "r10": -2.5}


def test_r1_arrival_within_a_tenth_of_a_metre_hand_values():
    near = _state(pos_xy=np.array([[4.95, 5.0]]), subgoal_xy=np.array([[5.0, 5.0]]))         # 0.05 m -> 5.0
    far = _state(pos_xy=np.array([[4.8, 5.0]]), subgoal_xy=np.array([[5.0, 5.0]]))           # 0.2 m -> 0
    assert rw.reward_total(near)[1]["r1"][0] == 5.0 and rw.reward_total(far)[1]["r1"][0] == 0.0
    for d, want in ((0.08, 5.0), (0.12, 0.0)):                                                # 문턱 0.1 양쪽
        s = _state(pos_xy=np.array([[5.0 - d, 5.0]]), subgoal_xy=np.array([[5.0, 5.0]]))
        assert rw.reward_total(s)[1]["r1"][0] == want


def test_r2_counts_the_visit_then_one_over_sqrt():
    g = rw.VisitGrid(2)
    p = np.array([[1.2, 1.2], [3.2, 3.2]])
    eta = [g.visit(p) for _ in range(4)]
    assert [e[0] for e in eta] == [1, 2, 3, 4]
    s = _state(2, eta=eta[3])
    assert np.allclose(rw.reward_terms(s)["r2"], 1 / np.sqrt(4))
    assert np.isclose(rw.reward_total(_state(1, eta=np.array([1.0])))[1]["r2"][0], 0.5)       # 첫 방문 0.5 x 1
    assert np.isclose(rw.reward_total(_state(1, eta=np.array([4.0])))[1]["r2"][0], 0.25)       # 4 번째 0.5 x 1/2


def test_visit_grid_cells_are_half_metre_and_reset_clears_only_the_named_env():
    g = rw.VisitGrid(2)
    g.visit(np.array([[1.0, 1.0], [1.0, 1.0]]))
    assert g.visit(np.array([[1.4, 1.4], [3.0, 3.0]])).tolist() == [2.0, 1.0]                  # 0.5 m 칸 (1.0~1.5) 은 같은 칸
    assert g.visit(np.array([[1.6, 1.6], [3.0, 3.0]]))[0] == 1.0                              # 다음 칸
    g.reset([0])
    assert g.visit(np.array([[1.0, 1.0], [1.0, 1.0]])).tolist() == [1.0, 2.0]
    assert g.visit(np.array([[-3.0, 25.0]] * 2)).tolist() == [1.0, 1.0]                      # 방 밖은 가장자리 칸


def test_r3_is_one_at_the_desired_speed_and_decays_with_a_0_3_scale():
    at = _state(v_xy=np.array([[0.6, 0.0]]))
    off = _state(v_xy=np.array([[0.3, 0.0]]))                                                # |0.6 - 0.3| / 0.3 = 1
    assert np.isclose(rw.reward_total(at)[1]["r3"][0], 0.25)
    assert np.isclose(rw.reward_total(off)[1]["r3"][0], 0.25 * np.exp(-1.0))
    assert np.isclose(rw.reward_terms(_state(v_xy=np.array([[0.3, 0.4]]), v_des=np.array([0.5])))["r3"][0], 1.0)   # 속력은 xy 노름


def test_r4_r5_command_rate_and_smoothness_hand_values():
    c0, c1, c2 = np.array([[0.0, 0.0, 0.0]]), np.array([[0.4, 0.0, 0.0]]), np.array([[1.0, 0.0, 0.2]])
    t = rw.reward_terms(_state(cmd=c2, cmd_prev=c1, cmd_prev2=c0))
    assert np.isclose(t["r4"][0], 0.6 ** 2 + 0.2 ** 2)                                         # |c2 - c1|^2
    assert np.isclose(t["r5"][0], (1.0 - 0.8) ** 2 + 0.2 ** 2)                                 # |c2 - 2 c1 + c0|^2


def test_r6_uses_three_columns_without_the_pose_switch_and_five_with_it():
    cmd = np.array([[0.5, 0.1, 0.2, 0.05, 0.1]])
    act = np.array([[0.4, 0.1, 0.0, 0.0, 0.0]])
    s = _state(cmd=cmd, cmd_prev=cmd, cmd_prev2=cmd, actual=act)
    assert np.isclose(rw.reward_terms(s, False)["r6"][0], 0.1 ** 2 + 0.2 ** 2)
    assert np.isclose(rw.reward_terms(s, True)["r6"][0], 0.1 ** 2 + 0.2 ** 2 + 0.05 ** 2 + 0.1 ** 2)
    with pytest.raises(ValueError):
        rw.reward_terms(_state(), True)                                                         # 3 칸 상태로 자세 켬은 거절


def test_r7_r8_body_motion_and_default_pose_hand_values():
    s = _state(v_z=np.array([0.3]), omega_xy=np.array([[0.2, 0.1]]), q=np.full((1, 12), 0.1), q0=np.zeros(12))
    t = rw.reward_terms(s)
    assert np.isclose(t["r7"][0], 0.09 + 0.04 + 0.01) and np.isclose(t["r8"][0], 12 * 0.01)


def test_r9_r10_indicators_and_the_weighted_total_for_a_fixed_state():
    s = _state(pos_xy=np.array([[5.0, 5.0]]), v_xy=np.array([[0.6, 0.0]]), eta=np.array([1.0]),
               limited=np.array([True]), collision=np.array([True]))
    total, terms = rw.reward_total(s)
    assert terms["r9"][0] == -2.5 and terms["r10"][0] == -2.5
    assert np.isclose(total[0], 5.0 + 0.5 + 0.25 - 2.5 - 2.5)                                  # r1 r2 r3 r9 r10 만 0 이 아님


def test_v_des_is_drawn_in_the_plan_range_and_weights_must_be_complete():
    v = rw.sample_v_des(np.random.default_rng(0), 4000)
    assert 0.3 <= v.min() and v.max() <= 1.0 and abs(v.mean() - 0.65) < 0.02
    with pytest.raises(ValueError):
        rw.reward_total(_state(), weights={"r1": 1.0})
