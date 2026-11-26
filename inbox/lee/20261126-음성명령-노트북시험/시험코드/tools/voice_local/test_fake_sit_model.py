"""가짜 Go2 앉음 가정 모형 (sit_model) 회귀 · 기본값 보존 (11-25 A/B/C) · Codex 경계."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s5_agent as A  # noqa: E402

F = A._fake


def sample(d):
    low, sport = d.tick()
    return sport.mode, round(sport.body_height, 2), [round(x, 2) for x in low.imu_state.rpy]


def test_default_records_only():
    d = F.FakeGo2Device()
    c = d.client('normal')
    assert c.Sit() == 0 and c.RiseSit() == 0
    assert sample(d) == (0, .30, [0., 0., 0.]) and sample(d) == (0, .30, [0., 0., 0.])
    assert [m for m, _ in c.calls] == ['Sit', 'RiseSit']


def test_sit_model_transitions_next_tick_consistently():
    d = F.FakeGo2Device(sit_model=True)
    c = d.client('normal')
    assert sample(d) == (0, .30, [0., 0., 0.])
    assert c.Sit() == 0
    assert d.pose['mode'] == 0                                   # 부른 순간엔 그대로 · 다음 tick 에 한꺼번에
    assert sample(d) == (10, .24, [0., .52, 0.])
    assert sample(d) == (10, .24, [0., .52, 0.])
    assert c.RiseSit() == 0
    assert sample(d) == (1, .30, [0., 0., 0.])


def test_no_call_no_transition():
    # 거절된 요청은 메서드가 불리지 않음 → 전이 0
    d = F.FakeGo2Device(sit_model=True)
    for _ in range(5):
        assert sample(d) == (0, .30, [0., 0., 0.])
    d.client('normal').StopMove(); d.client('emergency').Move(0., 0., 0.)
    assert sample(d) == (0, .30, [0., 0., 0.])


def test_accept_without_change_keeps_pose():
    d = F.FakeGo2Device(sit_model=True, accept_without_change=True)
    d.client('normal').Sit()
    assert sample(d) == (0, .30, [0., 0., 0.])


def test_code_origin_points_to_selected_repo():
    o = A.code_origin()
    assert o['fake_device'] == A.FAKE_PATH
    assert all(f.startswith(A.AGENT_REPO + os.sep) for f in o['files'].values())
