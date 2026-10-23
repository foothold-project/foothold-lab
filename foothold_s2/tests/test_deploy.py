"""정책 노드 L0 (DDS 없이): 관측 조립 · 관절 순열 · 행동 스케일 · 명령 정리기 · STOP 래치 · deadman · ONNX.

Isaac 정답은 `deploy/testdata/s1blind_record.npz` (record_isaac.py 가 Kit 에서 기록).
"""

import os
import sys

import numpy as np
import pytest
import yaml

from foothold_s2.deploy import command_filter as cf
from foothold_s2.deploy import obs as dobs
from foothold_s2.deploy import safety as sf
from foothold_s2.deploy import sdk_joints as sj

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORD = os.path.join(HERE, "deploy", "testdata", "s1blind_record.npz")
DEPLOY = os.path.join(HERE, "deploy", "params", "deploy.yaml")
CKPT = os.environ.get("S1_BLIND_CKPT", os.path.join(os.path.dirname(HERE), "logs", "rsl_rl", "foothold_s1a",
                                                      "2026-10-20_11-35-41", "model_9.pt"))
PYLIB = os.environ.get("S2_PYLIB", "C:/Users/AI-WS01/s2_lab/pylib")


@pytest.fixture(scope="module")
def rec():
    return np.load(RECORD)


def replay(rec, env, to_sdk_and_back=False, wrong_perm=False):
    names = list(rec["joint_names"])
    asm = dobs.ObsAssembler(rec["default_joint_pos"])
    out = []

    for t in range(rec["obs"].shape[0]):
        q, dq, la = rec["q"][t, env], rec["dq"][t, env], rec["last_action"][t, env]

        if to_sdk_and_back:                                       # 실기 경로: SDK 순서로 받아 Isaac 순서로 되돌림
            q = sj.sdk_vec_to_isaac(sj.isaac_vec_to_sdk(q, names), names)
            dq = sj.sdk_vec_to_isaac(sj.isaac_vec_to_sdk(dq, names), names)

        if wrong_perm:                                            # negative control: 왼 · 오른쪽 hip 을 맞바꿈
            q = q.copy()
            q[[0, 1]] = q[[1, 0]]

        out.append(asm.step(q, dq, rec["quat"][t, env], rec["ang_vel_b"][t, env], rec["cmd"][t, env], la))

    return np.stack(out)


def test_obs_assembly_matches_isaac_to_1e5_for_every_env_and_step_including_reset_fill(rec):
    for env in range(rec["obs"].shape[1]):
        mine = replay(rec, env)
        assert mine.shape == (rec["obs"].shape[0], 495)
        assert np.abs(mine - rec["obs"][:, env]).max() < 1e-5, env


def test_obs_assembly_through_sdk_order_round_trip_is_identical(rec):
    a, b = replay(rec, 0), replay(rec, 0, to_sdk_and_back=True)
    assert np.array_equal(a, b)


def test_negative_control_wrong_joint_permutation_breaks_the_match(rec):
    bad = replay(rec, 0, wrong_perm=True)
    assert np.abs(bad - rec["obs"][:, 0]).max() > 1e-3


def test_obs_layout_is_per_term_history_oldest_first(rec):
    o = rec["obs"][30, 2]
    assert np.allclose(o[:33].reshape(11, 3)[-1], rec["ang_vel_b"][30, 2])
    assert np.allclose(o[:33].reshape(11, 3)[-2], rec["ang_vel_b"][29, 2])
    assert np.allclose(o[99:231].reshape(11, 12)[-1], rec["q"][30, 2] - rec["default_joint_pos"], atol=1e-6)


def test_gravity_from_quaternion_hand_values():
    assert np.allclose(dobs.projected_gravity([1, 0, 0, 0]), [0, 0, -1])
    s = np.sqrt(0.5)                                  # x 축 90도 회전: 몸 y 축이 위를 향함 -> 중력은 몸 -y
    assert np.allclose(dobs.projected_gravity([s, s, 0, 0]), [0, -1, 0], atol=1e-6)
    assert np.allclose(dobs.projected_gravity([s, 0, s, 0]), [-1, 0, 0], atol=1e-6) or \
        np.allclose(dobs.projected_gravity([s, 0, s, 0]), [1, 0, 0], atol=1e-6)


def test_joint_permutation_is_identity_and_names_map_correctly():
    isaac = ["FL_hip_joint", "FR_hip_joint", "RL_hip_joint", "RR_hip_joint", "FL_thigh_joint", "FR_thigh_joint",
             "RL_thigh_joint", "RR_thigh_joint", "FL_calf_joint", "FR_calf_joint", "RL_calf_joint", "RR_calf_joint"]
    x = np.arange(12.0)
    assert np.array_equal(sj.sdk_vec_to_isaac(sj.isaac_vec_to_sdk(x, isaac), isaac), x)
    sdk = sj.isaac_vec_to_sdk(np.array(isaac), isaac)
    assert list(sdk) == list(sj.SDK_JOINT_NAMES)                      # 번호 i 가 SDK 이름 i
    assert sj.SDK_JOINT_NAMES[0] == "FR_hip_joint" and sj.SDK_JOINT_NAMES[3] == "FL_hip_joint"
    with pytest.raises(ValueError):
        sj.permutation(isaac[:-1] + ["XX_calf_joint"])


def test_deploy_yaml_is_consistent_with_the_record(rec):
    d = yaml.safe_load(open(DEPLOY, encoding="utf-8"))
    assert d["joint_names_isaac"] == list(rec["joint_names"])
    assert d["joint_names_sdk"] == list(sj.SDK_JOINT_NAMES)
    assert [d["joint_names_isaac"][i] for i in d["joint_ids_map"]] == list(sj.SDK_JOINT_NAMES)
    assert np.allclose(d["default_joint_pos"], rec["default_joint_pos"])
    assert d["actions"]["JointPositionAction"]["scale"] == 0.25
    assert d["observations"]["policy"]["history_length"] == 11
    assert abs(d["step_dt"] - 0.02) < 1e-9
    assert set(d["stiffness"]) == {25.0} and set(d["damping"]) == {0.5}


def test_action_to_target_scale(rec):
    default = rec["default_joint_pos"]
    assert np.allclose(default + 0.25 * np.zeros(12), default)
    a = np.linspace(-1, 1, 12)
    assert np.allclose(default + 0.25 * a, default + a * 0.25)
    assert abs((default + 0.25 * a - default)[11] - 0.25) < 1e-12


# ------------------------------------------------------------------ 명령 정리기


def run_filter(cmds, cls, dt=0.02):
    f = cf.CommandFilter()
    outs = [f.step(c, cls, dt) for c in cmds]

    return f, outs


def test_continuous_class_only_clips_to_training_range():
    _, o = run_filter([(2.0, 1.5, 3.0), (-2.0, -1.5, -3.0), (0.5, 0.2, 0.1)], cf.CONTINUOUS)
    assert o[0] == (1.5, 1.0, 2.0) and o[1] == (-1.5, -1.0, -2.0) and o[2] == (0.5, 0.2, 0.1)


def test_sparse_lateral_and_back_and_rotation_limits():
    f = cf.CommandFilter()
    assert f.step((0.5, 0.5, 2.0), cf.SPARSE, 0.02) == (0.5, 0.2, 1.0)          # 이동 중 wz ±1.0
    assert "sparse_range" in f.warnings
    f.reset()
    assert f.step((0.1, 0.0, 2.0), cf.SPARSE, 0.02) == (0.1, 0.0, 1.2)          # 제자리 wz ±1.2
    f.reset()
    assert f.step((-0.31, 0.0, 0.0), cf.SPARSE, 0.02)[0] == pytest.approx(-0.3)   # 후진 상한
    f.reset()
    assert f.step((1.4, 0.0, 0.0), cf.SPARSE, 0.02)[0] == 1.0


def test_sparse_back_time_and_distance_limits_and_reset_on_forward_or_stop():
    f = cf.CommandFilter()
    outs = [f.step((-0.3, 0.0, 0.0), cf.SPARSE, 0.02)[0] for _ in range(100)]      # 정확히 2.00 s
    assert all(v == pytest.approx(-0.3) for v in outs)
    assert f.step((-0.3, 0.0, 0.0), cf.SPARSE, 0.02)[0] == 0.0                     # 2.02 s, 0.606 m
    assert "back_limit" in f.warnings
    assert f.step((0.0, 0.0, 0.0), cf.SPARSE, 0.02)[0] == 0.0                      # 정지가 세기를 비움
    assert f.step((-0.3, 0.0, 0.0), cf.SPARSE, 0.02)[0] == pytest.approx(-0.3)
    f2 = cf.CommandFilter()
    for _ in range(50):
        f2.step((-0.3, 0.0, 0.0), cf.SPARSE, 0.02)
    f2.step((0.2, 0.0, 0.0), cf.SPARSE, 0.02)                                       # 전진 명령도 비움
    assert f2.back_time == 0.0 and f2.back_dist == 0.0


def test_sparse_distance_rule_binds_when_time_alone_would_not():
    p = cf.FilterParams(back_max_s=10.0, back_max_m=0.6)
    f = cf.CommandFilter(p)
    outs = [f.step((-0.3, 0.0, 0.0), cf.SPARSE, 0.02)[0] for _ in range(103)]
    assert outs[99] == pytest.approx(-0.3) and outs[101] == 0.0


def test_unknown_class_is_an_error():
    with pytest.raises(ValueError):
        cf.CommandFilter().step((0, 0, 0), "grass", 0.02)


# ------------------------------------------------------------------ 안전 상태기계


def standing_machine(now=0.0):
    m = sf.SafetyMachine()
    m.request_stand(now)
    m.heartbeat(now + sf.FIXSTAND_S)          # 서는 동안에도 하트비트는 계속 온다
    m.tick(now + sf.FIXSTAND_S)
    assert m.state == sf.POLICY

    return m


def test_stand_sequence_and_failed_stand_returns_to_passive():
    m = sf.SafetyMachine()
    assert m.state == sf.PASSIVE and m.filter_command((1, 0, 0), 0.0) == (0.0, 0.0, 0.0)
    m.request_stand(0.0)
    assert m.state == sf.FIXSTAND
    m.tick(1.0)
    assert m.state == sf.FIXSTAND
    m.tick(2.0, posture_ok=False)
    assert m.state == sf.PASSIVE


def test_deadman_zeroes_the_command_after_0_3_s_and_recovers_when_commands_resume():
    m = standing_machine(10.0)
    t = 12.0
    m.command_received(t)
    m.heartbeat(t)
    assert m.filter_command((0.5, 0, 0), t + 0.29) == (0.5, 0.0, 0.0)
    assert m.filter_command((0.5, 0, 0), t + 0.31) == (0.0, 0.0, 0.0)
    m.command_received(t + 0.4)
    assert m.filter_command((0.5, 0, 0), t + 0.41) == (0.5, 0.0, 0.0)


def test_heartbeat_loss_latches_stop_and_nothing_resumes_automatically():
    m = standing_machine(0.0)
    m.command_received(2.0)
    m.heartbeat(2.0)
    m.tick(2.9)
    assert m.state == sf.POLICY
    m.tick(3.05)                                       # 1.05 s 끊김
    assert m.state == sf.HOLD and m.latched
    m.heartbeat(3.1)
    m.command_received(3.1)
    m.tick(10.0)
    assert m.state == sf.HOLD                          # 신호가 돌아와도 자동 재개 없음
    assert m.filter_command((1.0, 0, 0), 10.0) == (0.0, 0.0, 0.0)
    m.release(11.0)
    assert m.state == sf.POLICY and not m.latched
    assert m.filter_command((1.0, 0, 0), 11.05) == (1.0, 0.0, 0.0)


def test_stop_input_and_posture_failure_latch_and_release_needs_a_human():
    m = standing_machine(0.0)
    m.heartbeat(2.0)
    m.command_received(2.0)
    m.stop(2.5)
    assert m.state == sf.HOLD and m.filter_command((1, 0, 0), 2.5) == (0.0, 0.0, 0.0)
    m.release(3.0)
    m.heartbeat(3.0)
    m.tick(3.1, posture_ok=False)
    assert m.state == sf.HOLD
    m2 = sf.SafetyMachine()
    m2.release(1.0)                                    # 래치가 없으면 해제는 아무 일도 안 한다
    assert m2.state == sf.PASSIVE


def test_unstable_hold_goes_to_sport_if_available_and_damp_only_on_flat():
    def held():
        m = standing_machine(0.0)
        m.heartbeat(2.0)
        m.stop(2.0)
        return m

    m = held()
    m.tick(3.0, hold_stable=False)
    m.tick(3.0 + sf.HOLD_UNSTABLE_S - 0.1, hold_stable=False)
    assert m.state == sf.HOLD
    m.tick(3.0 + sf.HOLD_UNSTABLE_S + 0.1, hold_stable=False, sport_available=True)
    assert m.state == sf.SPORT
    m = held()
    m.tick(3.0, hold_stable=False)
    m.tick(40.0, hold_stable=False, flat_terrain=False)                    # 평지가 아니면 힘을 빼지 않는다
    assert m.state == sf.HOLD
    m.tick(41.0, hold_stable=False, flat_terrain=True)
    assert m.state == sf.DAMP


def test_clock_driven_deadman_and_heartbeat_fire_at_the_documented_times_within_0_1_s():
    m = standing_machine(0.0)
    t0 = 2.0
    m.command_received(t0)
    m.heartbeat(t0)
    first_dead = next(t0 + k * 0.01 for k in range(200) if m.deadman_tripped(t0 + k * 0.01))
    assert abs(first_dead - (t0 + sf.DEADMAN_S)) < 0.1

    def hb_time():
        for k in range(300):
            m.tick(t0 + k * 0.01)

            if m.state == sf.HOLD:
                return t0 + k * 0.01

    assert abs(hb_time() - (t0 + sf.HEARTBEAT_S)) < 0.1


# ------------------------------------------------------------------ ONNX


def _ort():
    sys.path.append(PYLIB)

    try:
        import onnxruntime as ort                    # noqa: F401
        import onnx                                  # noqa: F401
    except Exception:                                # onnx 는 protobuf 판이 맞아야 한다 (PYLIB 의 onnx 1.18 + ort)
        return None

    return ort


def test_onnx_export_matches_the_checkpoint_to_1e5_on_recorded_observations(rec, tmp_path):
    torch = pytest.importorskip("torch")
    ort = _ort()

    if ort is None or not os.path.exists(CKPT):
        pytest.skip("onnxruntime/onnx(%s) 또는 체크포인트(%s) 없음: 이 시험은 «미확인» 으로 남는다" % (PYLIB, CKPT))

    from foothold_s2.deploy import export

    path = str(tmp_path / "policy.onnx")
    net = export.export_onnx(CKPT, path)
    sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    x = rec["obs"].reshape(-1, 495)[:200].astype(np.float32)
    y = sess.run(None, {"obs": x})[0]
    ref = net(torch.as_tensor(x)).detach().numpy()
    assert y.shape == (200, 12) and np.abs(y - ref).max() < 1e-5
    # 서로 다른 입력은 다른 출력(상수 그래프가 아님)
    assert np.abs(y[0] - y[100]).max() > 1e-4
