"""HiPAN 좌표 틀 점검 (G3 83 회: 부목표 끝 거리가 늘어남): teacher 관측의 부목표 칸은 몸 틀 · yaw 부호 · 방 틀 합산 · 보상에 다가가는 길잡이가 있나. CPU · Kit 없음."""
import numpy as np

from foothold_s2.nav import nav_task, rewards_hl, teacher_obs
from foothold_s2.nav.nav_task import room_frame_origin_xy


def _q(yaw):
    return np.array([[np.cos(yaw / 2), 0.0, 0.0, np.sin(yaw / 2)]])


def test_subgoal_observation_is_in_the_body_frame_with_the_left_positive_and_yaw_sign():
    pos, sub = np.array([[5.0, 5.0]]), np.array([[6.0, 5.0]])                 # the subgoal is +1 m on the room +x axis
    for yaw, want in ((0.0, (1.0, 0.0)), (np.pi / 2, (0.0, -1.0)), (-np.pi / 2, (0.0, 1.0)), (np.pi, (-1.0, 0.0))):
        got = teacher_obs.subgoal_in_body(pos, teacher_obs.yaw_from_quat_wxyz(_q(yaw)), sub)[0]
        assert np.allclose(got, want, atol=1e-12), (yaw, got)               # facing +y: a goal on the room +x is on the body right (y < 0)
    sub2 = np.array([[5.0, 6.0]])                                            # +1 m on the room +y: body left when facing +x
    assert np.allclose(teacher_obs.subgoal_in_body(pos, teacher_obs.yaw_from_quat_wxyz(_q(0.0)), sub2)[0], (0.0, 1.0))
    assert np.allclose(teacher_obs.subgoal_in_body(pos, teacher_obs.yaw_from_quat_wxyz(_q(np.pi / 2)), sub2)[0], (1.0, 0.0), atol=1e-12)


def test_room_frame_position_is_the_body_offset_from_the_env_origin_plus_the_start_point_in_the_room_frame():
    pitch = 25.0
    origins = np.array([[3.0 + 2 * pitch, 4.0]])                            # mesh coordinates: row 2, start point (3, 4)
    org = room_frame_origin_xy(origins, [2], pitch)
    assert np.allclose(org, [[3.0, 4.0]])
    pos_local = np.array([[0.5, -0.25, 0.35]])                              # the body moved (+0.5, -0.25) from its env origin
    assert np.allclose(teacher_obs.to_room_frame(pos_local, org)[0, :2], [3.5, 3.75])


def test_the_only_term_that_pays_for_getting_closer_to_the_subgoal_is_r1_inside_0_1_m():
    n = 3
    z = np.zeros
    base = dict(pos_xy=np.array([[2.0, 0.0], [1.0, 0.0], [0.05, 0.0]]), subgoal_xy=np.zeros((n, 2)), v_z=z(n), omega_xy=z((n, 2)), q=z((n, 12)), q0=z(12),
                cmd=z((n, 3)), cmd_prev=z((n, 3)), cmd_prev2=z((n, 3)), actual=z((n, 3)), v_des=np.full(n, 0.5), eta=np.ones(n), limited=z(n, bool), collision=z(n, bool))
    toward = rewards_hl.reward_terms(rewards_hl.HLState(v_xy=np.array([[-0.5, 0.0]] * n), **base))
    away = rewards_hl.reward_terms(rewards_hl.HLState(v_xy=np.array([[0.5, 0.0]] * n), **base))
    for k in toward:
        assert np.allclose(toward[k], away[k]), k                           # no term looks at the direction of motion: toward and away pay the same
    assert list(toward["r1"]) == [0.0, 0.0, 1.0]                            # 2 m and 1 m away: nothing; 0.05 m: 1
