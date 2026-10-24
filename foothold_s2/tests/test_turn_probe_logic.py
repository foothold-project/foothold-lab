"""우회전 원인 분리 판정(turn_probe_logic) 시험: 알려진 한계값 입력 검산 + 반례. CPU 만."""

import numpy as np
import pytest

from foothold_s2.eval import turn_probe_logic as L

T, J = 1600, 12                      # 8 s x 200 Hz
HARD = np.tile(np.array([[-1.0, 1.0]]), (J, 1))
EFF = np.full(J, 23.5)


def _base():
    q = np.zeros((T, J))
    return {"q": q, "target": q + 0.0, "hard": HARD, "computed": np.zeros((T, J)), "applied": np.zeros((T, J)), "effort_limit": EFF,
            "force": np.zeros((T, 5)), "kinds": ["foot", "foot", "calf", "thigh", "base"], "wz": np.full(T, 0.0), "alive": np.ones(T, bool)}


def test_longest_run():
    m = np.array([[0, 1, 1, 0, 1, 1, 1, 0], [1, 1, 1, 1, 1, 1, 1, 1], [0] * 8])

    assert longest_run_list(m) == [3, 8, 0]


def longest_run_list(m):
    return L.longest_run(m).tolist()


def test_joint_at_known_limit_is_flagged_only_when_target_is_outside_and_sustained():
    a = _base()
    a["q"][:, 3] = 0.98                                     # 상한 1.0 에서 0.02 (margin 0.05 안)
    a["target"][:, 3] = 1.3                                 # 목표는 한계 밖
    r = L.judge(a, 1.2)["joint_limit"]

    assert r["verdict"] == "지지" and r["joints"] == [3]
    b = _base()
    b["q"][:, 3] = 0.98                                     # 한계 근처이지만 목표는 한계 안: 외형만으로 한계라 하지 않는다
    b["target"][:, 3] = 0.99

    assert L.judge(b, 1.2)["joint_limit"]["verdict"] == "반증"
    c = _base()
    c["q"][:, 3] = 0.5
    c["target"][:, 3] = 1.3                                 # 목표만 밖, q 는 멀다: 반증

    assert L.judge(c, 1.2)["joint_limit"]["verdict"] == "반증"


def test_short_limit_touch_is_not_sustained():
    a = _base()
    a["q"][:90, 2] = 0.98
    a["target"][:90, 2] = 1.3                                # 0.45 s < 0.5 s

    assert L.judge(a, 1.2)["joint_limit"]["verdict"] == "반증"
    a["q"][:100, 2] = 0.98
    a["target"][:100, 2] = 1.3                               # 정확히 0.5 s

    assert L.judge(a, 1.2)["joint_limit"]["verdict"] == "지지"


def test_limit_pressing_while_the_robot_turns_is_not_a_cause():
    a = _base()
    a["q"][:, 3] = 0.98
    a["target"][:, 3] = 1.3
    a["wz"][:] = 1.2                                         # 명령대로 돌고 있다: 정체가 아님

    assert L.judge(a, 1.2)["joint_limit"]["verdict"] == "반증"


def test_actuator_saturation_and_clip_are_measured_over_time_not_from_the_last_substep():
    a = _base()
    a["applied"][200:500, 5] = 23.5                          # 1.5 s 포화
    a["computed"][200:500, 5] = 40.0
    r = L.judge(a, 1.2)["actuator"]

    assert r["verdict"] == "지지" and r["joints"] == [5] and r["clipped_fraction"][5] == pytest.approx(300 / T)
    b = _base()
    b["applied"][-1, 5] = 23.5                               # 마지막 substep 하나만 포화
    b["computed"][-1, 5] = 40.0

    assert L.judge(b, 1.2)["actuator"]["verdict"] == "반증"


def test_missing_inputs_are_unconfirmed_not_negative():
    a = _base()
    a["computed"] = None
    a["applied"] = None

    assert L.judge(a, 1.2)["actuator"]["verdict"] == "미확인"
    assert L.judge(a, 1.2)["posture"]["verdict"] == "미확인"
    b = _base()
    b["force"] = None

    assert L.judge(b, 1.2)["foot_support"]["verdict"] == "미확인"
    c = _base()
    c["hard"] = None

    assert L.judge(c, 1.2)["joint_limit"]["verdict"] == "미확인"


def test_non_foot_contact_during_stall_is_flagged_but_foot_contact_is_not():
    a = _base()
    a["force"][100:400, 2] = 30.0                            # calf 접촉 1.5 s, 정체 중
    r = L.judge(a, 1.2)["foot_support"]

    assert r["verdict"] == "지지" and r["links"] == ["calf#2"]
    b = _base()
    b["force"][:, 0] = 60.0                                  # 발 접촉은 정상 지지

    assert L.judge(b, 1.2)["foot_support"]["verdict"] == "반증"


def test_posture_requires_all_other_hypotheses_cleared_and_flat_target():
    a = _base()                                              # 한계 · 포화 · 접촉 없음, 정체, 목표 평평
    r = L.judge(a, 1.2)

    assert r["posture"]["verdict"] == "지지" and r["stall_fraction"] == 1.0
    b = _base()
    b["wz"][:] = 1.2
    assert L.judge(b, 1.2)["posture"]["verdict"] == "반증"   # 돌고 있으면 자세 문제 아님
    c = _base()
    c["q"][:, 3], c["target"][:, 3] = 0.98, 1.3

    assert L.judge(c, 1.2)["posture"]["verdict"] == "보류"   # 다른 가설이 지지이면 보류
    d = _base()
    d["target"] = d["target"] + 0.3 * np.sin(np.linspace(0, 40, T))[:, None]

    assert L.judge(d, 1.2)["posture"]["verdict"] == "보류"   # 정체인데 목표는 움직인다: 자세 평평 아님


def test_order_needs_both_measurements_and_detects_recovery_when_independent():
    assert L.order({"left": 0.9, "right": 0.1}, None)["verdict"] == "미확인"
    r = L.order({"left": 0.9, "right": 0.8}, {"left": 0.9, "right": 0.1})

    assert r["verdict"] == "지지" and r["right_recovers_when_independent"]
    assert L.order({"left": 0.9, "right": 0.12}, {"left": 0.9, "right": 0.1})["verdict"] == "반증"
    assert L.side_asymmetry(0.9, 0.1) == pytest.approx(0.8)


def test_thresholds_are_the_registered_values():
    assert (L.HZ, L.SUSTAIN_S, L.LIMIT_MARGIN_RAD, L.SATURATION_FRAC, L.CONTACT_FORCE_N, L.STALL_FRAC, L.ORDER_GAP) == (200.0, 0.5, 0.05, 0.98, 1.0, 0.1, 0.25)
