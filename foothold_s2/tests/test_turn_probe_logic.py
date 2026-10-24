"""우회전 원인 분리 판정(turn_probe_logic) 시험: 알려진 한계값 입력 검산 + 반례. CPU 만."""

import subprocess
from pathlib import Path

import numpy as np
import pytest

from foothold_s2.eval import turn_probe_logic as L

T, J = 1600, 12                      # 8 s x 200 Hz
HARD = np.tile(np.array([[-1.0, 1.0]]), (J, 1))
EFF = np.full(J, 23.5)
LIM = {"effort_limit": EFF, "saturation_effort": EFF, "velocity_limit": np.full(J, 30.0)}
SOFT = np.tile(np.array([[-0.9, 0.9]]), (J, 1))


def _base():
    q = np.zeros((T, J))
    return {"q": q, "qd": np.zeros((T, J)), "limits": LIM, "soft": SOFT, "target": q + 0.0, "hard": HARD, "computed": np.zeros((T, J)), "applied": np.zeros((T, J)),
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


@pytest.mark.parametrize("effort", [1.0e9, 23.5])
def test_reviewer_case_clipped_40_to_23_5_is_support_whatever_effort_limit_is_given(effort):
    a = _base()
    a["computed"][:, 4], a["applied"][:, 4] = 40.0, 23.5      # 8 s 정체, 계산 40, 적용 23.5 (reviewer 합성 입력)
    a["limits"] = {**LIM, "effort_limit": np.full(J, effort)}
    r = L.judge(a, 1.2)

    assert r["actuator"]["verdict"] == "지지" and r["actuator"]["joints"] == [4] and r["posture"]["verdict"] == "보류"
    assert r["actuator"]["curve_used"] is (effort < 1e6)


def test_reviewer_case_speed_dependent_clip_to_20_is_support():
    a = _base()
    a["qd"][:, 6] = 10.0                                      # 빠르게 도는 관절: 곡선 상한 = 23.5 x (1 - 10/30) = 15.67
    a["computed"][:, 6], a["applied"][:, 6] = 40.0, 15.0
    r = L.judge(a, 1.2)["actuator"]

    assert r["verdict"] == "지지" and 6 in r["joints"]
    b = _base()
    b["qd"][:, 6] = 10.0                                      # 계산도 적용도 15.5(곡선 15.67 의 98 % 이상): 잘림 없이 곡선 위
    b["computed"][:, 6] = b["applied"][:, 6] = 15.5
    rb = L.judge(b, 1.2)["actuator"]

    assert rb["verdict"] == "지지" and rb["at_dc_curve_fraction"][6] == 1.0 and rb["clipped_fraction"][6] == 0.0
    c = _base()
    c["qd"][:, 6] = 10.0
    c["computed"][:, 6] = c["applied"][:, 6] = 10.0           # 곡선 아래, 잘림 없음
    assert L.judge(c, 1.2)["actuator"]["verdict"] == "반증"


def test_dc_envelope_matches_the_training_clip_function():
    torch = pytest.importorskip("torch")
    from foothold_s2.robots import go2_params as gp

    qd = np.linspace(-40, 40, 81)[:, None]
    eff = np.full((81, 1), 1.0e3)                            # 큰 요청 -> 상한/하한으로 잘린다
    bot, top = L.dc_envelope(qd, [gp.CALF["effort_limit"]], [gp.CALF["saturation_effort"]], [gp.CALF["velocity_limit"]])
    up = gp.dc_motor_clip(torch.tensor(eff), torch.tensor(qd), gp.CALF["effort_limit"], gp.CALF["saturation_effort"], gp.CALF["velocity_limit"]).numpy()
    dn = gp.dc_motor_clip(torch.tensor(-eff), torch.tensor(qd), gp.CALF["effort_limit"], gp.CALF["saturation_effort"], gp.CALF["velocity_limit"]).numpy()

    assert np.allclose(top, up, atol=1e-4) and np.allclose(bot, dn, atol=1e-4)


def test_default_effort_limit_without_clipping_cannot_judge_the_curve_and_says_so():
    a = _base()
    a["limits"] = {**LIM, "effort_limit": np.full(J, 1.0e9)}
    r = L.judge(a, 1.2)["actuator"]

    assert r["curve_used"] is False and r["verdict"] == "미확인" and "곡선 근처" in r["note"]    # 곡선을 못 쓰고 잘림도 없으면 반증이 아니다


def test_missing_inputs_are_unconfirmed_not_negative():
    a = _base()
    a["computed"] = None
    a["applied"] = None

    assert L.judge(a, 1.2)["actuator"]["verdict"] == "미확인"
    assert L.judge(a, 1.2)["posture"]["verdict"] == "미확인"
    assert L.joint_limit(None, None, None, np.zeros(3, bool))["verdict"] == "미확인"
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
    assert L.judge(b, 1.2)["posture"]["verdict"] == "해당 없음"   # 돌고 있으면 정체가 없어 자세 가설은 판정 대상이 아니다(반증이 아님)
    b2 = _base()
    b2["wz"][:] = 1.2
    b2["wz"][:600] = 0.0                                           # 3 s/8 s = 37.5 % 만 정체
    assert L.judge(b2, 1.2)["posture"]["verdict"] == "해당 없음" and L.judge(b2, 1.2)["posture"]["stall_fraction"] == pytest.approx(600 / T)
    c = _base()
    c["q"][:, 3], c["target"][:, 3] = 0.98, 1.3

    assert L.judge(c, 1.2)["posture"]["verdict"] == "보류"   # 다른 가설이 지지이면 보류
    d = _base()
    d["target"] = d["target"] + 0.3 * np.sin(np.linspace(0, 40, T))[:, None]

    assert L.judge(d, 1.2)["posture"]["verdict"] == "보류"   # 정체인데 목표는 움직인다: 자세 평평 아님


def test_order_pair_is_per_context_and_needs_both_measurements():
    assert L.order_pair(0.9, None)["verdict"] == "미확인" and L.order_pair(float("nan"), 0.1)["verdict"] == "미확인"
    assert L.order_pair(0.8, 0.1)["verdict"] == "지지" and L.order_pair(0.12, 0.1)["verdict"] == "반증"
    assert L.order_pair(0.1, 0.8)["verdict"] == "반증"                 # 독립이 더 나쁘면 순서 영향이 아니다
    assert L.side_asymmetry(0.9, 0.1) == pytest.approx(0.8)


def test_soft_limit_is_judged_separately_from_hard():
    a = _base()
    a["q"][:, 2], a["target"][:, 2] = 0.88, 0.95             # soft 상한 0.9 근처에서 목표가 soft 밖, hard(1.0) 안
    r = L.judge(a, 1.2)["joint_limit"]

    assert r["verdict"] == "반증" and r["soft"]["verdict"] == "지지" and r["soft"]["joints"] == [2]


def test_thresholds_and_blob_sha_are_available_for_the_result_file():
    th = L.thresholds()

    assert th["SUSTAIN_S"] == 0.5 and th["POSTURE_MIN_STALL_FRACTION"] == 0.5 and "EFFORT_LIMIT_SENTINEL" in th and len(th) >= 10
    git = subprocess.run(["git", "hash-object", L.__file__], capture_output=True, text=True, cwd=str(Path(L.__file__).parent)).stdout.strip()

    assert L.module_blob_sha() == git


def test_thresholds_are_the_registered_values():
    assert (L.HZ, L.SUSTAIN_S, L.LIMIT_MARGIN_RAD, L.SATURATION_FRAC, L.CONTACT_FORCE_N, L.STALL_FRAC, L.ORDER_GAP) == (200.0, 0.5, 0.05, 0.98, 1.0, 0.1, 0.25)
