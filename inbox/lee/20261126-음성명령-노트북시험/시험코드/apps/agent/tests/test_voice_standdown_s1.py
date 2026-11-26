"""S1 · 로컬 음성 → 엎드리기 연동 시험 (에이전트 단계 · 실기 · SDK · DDS · 네트워크 · 음성 없음).

팀 자세 시험 (test_go2_posture.py) 의 장치 구성을 그대로 쓰고, SDK 자리에
가짜 Go2 장치 모형 (voice_fake_go2.py) 을 꽂는다. 측정값은 시험이 손으로 넣지 않고
가짜 장치가 자기 상태에서 만들어 낸다. 「foothold stand down」 은 시나리오 이름일 뿐
이 단계에 음성 입력은 없다.

범위 (Codex 11-24 판정):
  - 고정 시계 · 수동 drain · tick 순서 시험이다. 「박자」 는 가짜 장치의 tick 순서이지
    실제 초 · 주기 · 지연이 아니다.
  - loop_step() 은 go2_direct/server.py 주행 고리의 consume → healthy 비교 → feedback_lost
    조건식을 복제한 것이다. 실제 server.run / setup.run 의 스케줄 · 출력 스레드 · 통신은
    실행하지 않는다 (S5 에서 본다). 「feedback_lost 1 회」 는 이 복제 조건식의 관찰이다.
  - 자세 완료 (posture_result CONFIRMED) 와 현재 세대의 정지 확인 (stop_ref) 은 별개다.
"""
from foothold_agent.go2_direct.feedback import Feedback
from foothold_agent.go2_direct.server import DriveSession, ServerSink
from foothold_agent.go2_direct.sink import Go2Sink
from foothold_agent.link.client import Client, Settings
from test_go2_direct import Clock
from test_setup_pairing import SERIAL
from voice_fake_go2 import FakeGo2Device


def rig(unlock=True, **device_options):
    clock, device = Clock(), FakeGo2Device(**device_options)
    clock.value = 1000.
    normal, emergency = device.client('normal'), device.client('emergency')
    feedback = Feedback(SERIAL, now=clock)
    sink = Go2Sink(normal, emergency, now=clock, offline_test_mode=True)
    feedback.sink = sink
    session = DriveSession(feedback, now=clock)
    client = Client(session, ServerSink(sink, session), Settings('ws://127.0.0.1/ws', 'fake-token'))
    client._emit(session.connect())
    trace, health = [], dict(healthy=False)

    def evaluate(publish=True):
        """한 박자. publish=False 면 새 표본 없이 평가만 한다 (센서 끊김 표현)."""
        if publish:
            low, sport = device.tick()
            feedback.lowstate(low)
            feedback.sportmodestate(sport)
        ready = feedback.consume(client)
        lost = health['healthy'] and not ready
        if lost:
            client._emit(session.feedback_lost())
        health['healthy'] = ready
        sink.drain()
        state = session._state()
        trace.append(dict(tick=device.tick_count, published=publish, ready=ready, feedback_lost=lost,
                          posture=state['posture']['state'], mode=state['posture']['mode'],
                          result=(state['posture_result'] or {}).get('code'),
                          status=(state['posture_result'] or {}).get('status'),
                          latched=bool(session.core.latch), stop_ref=state.get('stop_ref'),
                          stop_gen=session.core.stop_gen,
                          sink_gen=sink.generation, confirmed_gen=sink._confirmed_generation))
        return state

    def frame(t, **values):
        client._emit(session.receive(dict(t=t, **values)))

    evaluate()
    frame('lease', lease_id='fake-lease', holder_type='USER')
    evaluate()
    if unlock:
        frame('unlock', lease_id='fake-lease', stop_gen=session.core.stop_gen)
        evaluate()
    normal.calls.clear(); emergency.calls.clear(); device.log.clear()
    return clock, device, sink, session, (normal, emergency), evaluate, frame, trace


def ask_stand_down(frame, request_id='voice-1'):
    frame('posture', request_id=request_id, lease_id='fake-lease', action='stand_down')


def print_trace(title, device, trace):
    print('\n[%s]' % title)
    for tick, event in device.log:
        print('  박자 %d · 장치 %s' % (tick, event))
    for row in trace:
        print('  박자 %(tick)d%(new)s · 판정 %(posture)s (mode %(mode)s) · 준비 %(ready)s · '
              '결과 %(status)s/%(result)s · 잠금 %(latched)s · feedback_lost %(feedback_lost)s · '
              'stop_gen %(stop_gen)s · sink 세대 %(sink_gen)s · 정지 확인 세대 %(confirmed_gen)s'
              % dict(row, new='' if row['published'] else ' (새 표본 없음)'))


def standdown_preceded_by_stopmove_once(calls):
    names = [name for name, _ in calls]
    assert names.count('StandDown') == 1
    index = names.index('StandDown')
    assert index > 0 and names[index - 1] == 'StopMove'


def no_nonzero_move(*clients):
    assert not any(name == 'Move' and any(v) for c in clients for name, v in c.calls)


def test_s1_stand_down_reaches_measured_lying_and_confirmed():
    _, device, sink, session, (normal, emergency), step, frame, trace = rig()
    assert step()['posture']['state'] == 'STANDING'
    assert not session.core.latch                       # 요청 전 잠금 풀림
    ask_stand_down(frame)
    assert session.core.latch                           # 요청이 잠금을 건다
    assert sink.posture_result['status'] == 'RUNNING'
    sink.drain()
    standdown_preceded_by_stopmove_once(normal.calls)
    assert session._state()['posture']['state'] == 'STANDING'   # 수락 순간엔 아직 서 있음
    for _ in range(4):
        step()
    print_trace('S1 정상 · 시나리오 foothold stand down', device, trace)
    lying = [row for row in trace if row['posture'] == 'LYING']
    first = lying[0]
    assert first['ready'] is False and first['feedback_lost'] is True
    assert sum(row['feedback_lost'] for row in trace) == 1      # 복제 고리 조건식의 관찰
    assert all(row['latched'] for row in lying)                  # 잠금 유지 (해제는 성공 조건 아님)
    assert lying[-1]['status'] == 'SUCCEEDED' and lying[-1]['result'] == 'CONFIRMED'
    assert sink.posture_result == dict(request_id='voice-1', action='stand_down',
                                       status='SUCCEEDED', code='CONFIRMED', sdk_code=0)
    no_nonzero_move(normal, emergency)


def test_s1_accept_without_change_stays_standing_and_running():
    _, device, sink, session, (normal, emergency), step, frame, trace = rig(accept_without_change=True)
    step()
    ask_stand_down(frame)
    sink.drain()
    standdown_preceded_by_stopmove_once(normal.calls)
    for _ in range(5):
        state = step()
    print_trace('S1 부정 · 수락만 · 자세 안 바뀜', device, trace)
    assert state['posture']['state'] == 'STANDING'
    assert (state['posture_result']['status'], state['posture_result']['code']) == ('RUNNING', 'STARTED')


def test_s1_stopmove_rejected_never_reaches_standdown():
    _, device, sink, session, (normal, emergency), step, frame, trace = rig(stopmove_code=3104)
    step()
    ask_stand_down(frame)
    sink.drain()
    for _ in range(3):
        state = step()
    print_trace('S1 부정 · StopMove 거절', device, trace)
    assert ('StandDown', ()) not in normal.calls
    assert state['posture']['state'] == 'STANDING'
    assert (state['posture_result']['status'], state['posture_result']['code']) == ('REJECTED', 'ROBOT_SLOW')


def test_s1_sdk_acceptance_alone_does_not_complete():
    """SDK 수락 뒤 새 측정 없이 drain 만 반복 → 완료 아님 (세대 · 신선도 검사는 아래 두 시험)."""
    _, device, sink, session, (normal, emergency), step, frame, trace = rig()
    step()
    ask_stand_down(frame)
    sink.drain(); sink.drain(); sink.drain()
    print_trace('S1 부정 · SDK 수락만 · 새 측정 없음', device, trace)
    assert ('StandDown', ()) in normal.calls
    assert sink.posture_result['status'] == 'RUNNING'


def test_s1_stale_sensor_after_lying_becomes_unknown():
    clock, device, sink, session, clients, step, frame, trace = rig()
    step()
    ask_stand_down(frame)
    sink.drain()
    for _ in range(3):
        step()
    assert trace[-1]['posture'] == 'LYING'
    clock.value += .25                                   # 신선도 한계 0.20 초를 넘김 · 새 표본 없음
    state = step(publish=False)
    print_trace('S1 경계 · 엎드린 뒤 센서 끊김', device, trace)
    assert state['posture']['state'] == 'UNKNOWN'
    assert trace[-1]['ready'] is False


def test_s1_feedback_lost_needs_new_samples_for_stop_confirmation():
    _, device, sink, session, clients, step, frame, trace = rig()
    step()
    ask_stand_down(frame)
    sink.drain()
    for _ in range(3):
        step()
        if trace[-1]['feedback_lost']:
            break
    step(publish=False)                 # 대조: 새 표본 없이 평가 → 확인 안 생김
    no_sample = trace[-1]
    step()                              # 새 표본
    print_trace('S1 경계 · feedback_lost 뒤 정지 확인', device, trace)
    assert no_sample['confirmed_gen'] is None
    lost_at = next(i for i, row in enumerate(trace) if row['feedback_lost'])
    before, at = trace[lost_at - 1], trace[lost_at]
    after = next(row for row in trace[lost_at + 1:] if row['published'])
    # feedback_lost 박자: sink 세대가 바뀌고 이전 세대의 정지 확인은 버려짐 (베끼지 않음)
    assert at['sink_gen'] != before['sink_gen'] and at['confirmed_gen'] is None
    # 다음 박자: 새 표본이 새 세대의 정지 확인을 다시 만든다 (자세 완료 CONFIRMED 와는 별개 칸)
    assert after['published'] and after['confirmed_gen'] == at['sink_gen']
    assert after['confirmed_gen'] == after['sink_gen']
    # 참고: 이 rig 에서는 서버 STOP 참조 프레임을 주입하지 않아 stop_ref 가 0 이며, 이를 세대별 정지 확인의 근거로 사용하지 않는다.
    # 범위: sink 의 확인 상태 관찰이며 서버 조종권 부여 · 잠금 해제까지 검증한 것은 아니다.


def test_s1_stand_up_from_lying_while_locked_reaches_measured_standing():
    """(가) 엎드림 (잠금) → 잠금 해제는 팀 규칙대로 거부 → 잠금인 채 일어서기 요청 → 다음 박자에 서 있는 값 → STANDING · CONFIRMED"""
    _, device, sink, session, (normal, emergency), step, frame, trace = rig()
    step()
    ask_stand_down(frame)
    for _ in range(4):
        step()
    assert session._state()['posture']['state'] == 'LYING' and session.core.latch
    frame('unlock', lease_id='fake-lease', stop_gen=session.core.stop_gen)
    for _ in range(2):
        step()
    unlocked = not session.core.latch
    normal.calls.clear()
    frame('posture', request_id='voice-2', lease_id='fake-lease', action='stand_up')
    sink.drain()
    for _ in range(4):
        state = step()
    print_trace('S1 (가) · 엎드림 → 잠금 해제 거부 → 잠금인 채 일어서기', device, trace)
    assert not unlocked                                  # 엎드린 상태에선 해제 거부 (팀 규칙 · policy_not_running)
    assert [n for n, _ in normal.calls].count('StandUp') == 1
    assert state['posture']['state'] == 'STANDING'
    assert sink.posture_result['request_id'] == 'voice-2' and sink.posture_result['action'] == 'stand_up'
    assert (sink.posture_result['status'], sink.posture_result['code']) == ('SUCCEEDED', 'CONFIRMED')
    no_nonzero_move(normal, emergency)
