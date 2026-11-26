"""PR478 판 (84dac3c2) 검산 전용 · 일회용 · 커밋 안 함.

앉음 (mode 10) 에서 앉은 자세에서 일어서기 (RiseSit) 요청이 어떻게 처리되는지 가짜 장치로 확인한다.
앉음 값 (mode 10 · 몸 높이 0.24 m) 은 PR478 시험 (test_go2_resting_stop.py) 의 가정값을 그대로 쓴다 (실측 아님).
"""
from test_go2_actions import send
from test_go2_posture import rig


def _rig_at(mode, height, **values):
    clock, sink, normal, emergency, session, client, measured, frame = rig(mode)
    measured(mode, body_height=height, **values)
    sink.drain()
    normal.calls.clear(); emergency.calls.clear()
    for name in ('Sit', 'RiseSit'):          # 팀 test_go2_actions 처럼 가짜 SDK 자리에 메서드를 넣음 (반환 0)
        setattr(normal, name, (lambda n: lambda *a: (normal.calls.append((n, a)), 0)[1])(name))
    return sink, normal, emergency, measured, frame


def test_1_sitting_still_risesit_standing_required():
    sink, normal, emergency, measured, frame = _rig_at(10, .24)
    send(frame, 'RiseSit')
    sink.drain()
    print('1', sink.actions.result, normal.calls, emergency.calls)
    assert sink.actions.result['code'] == 'STANDING_REQUIRED'
    assert ('RiseSit', ()) not in normal.calls


def test_2_sitting_not_still_moving_first():
    sink, normal, emergency, measured, frame = _rig_at(10, .24, velocity=(.3, 0., 0.))
    send(frame, 'RiseSit')
    sink.drain()
    print('2', sink.actions.result, normal.calls, emergency.calls)
    assert sink.actions.result['code'] == 'MOVING'
    assert ('RiseSit', ()) not in normal.calls


def test_3_sitting_still_sit_again_standing_required():
    sink, normal, emergency, measured, frame = _rig_at(10, .24)
    send(frame, 'Sit')
    sink.drain()
    print('3', sink.actions.result, normal.calls, emergency.calls)
    assert sink.actions.result['code'] == 'STANDING_REQUIRED'
    assert ('Sit', ()) not in normal.calls


def test_4_lying_still_risesit_standing_required():
    sink, normal, emergency, measured, frame = _rig_at(5, .10)
    send(frame, 'RiseSit')
    sink.drain()
    print('4', sink.actions.result, normal.calls, emergency.calls)
    assert sink.actions.result['code'] == 'STANDING_REQUIRED'
    assert ('RiseSit', ()) not in normal.calls


def test_5_standing_still_risesit_accepted():
    sink, normal, emergency, measured, frame = _rig_at(1, .30)
    send(frame, 'RiseSit')
    sink.drain()
    print('5', sink.actions.result, normal.calls, emergency.calls)
    assert sink.actions.result['code'] == 'SDK_ACCEPTED' and sink.actions.result['status'] == 'SUCCEEDED'
    assert normal.calls.count(('RiseSit', ())) == 1
