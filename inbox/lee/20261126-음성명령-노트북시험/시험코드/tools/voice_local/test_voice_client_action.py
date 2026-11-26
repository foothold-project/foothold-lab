"""L · 음성 action 요청 · SDK 접수 경로 시험 (11-25 Codex 판정 반영 · 가짜 시계 · 네트워크 없음).

- 명시적 action_profile 에서만 sit_down → Sit · sit_rise → RiseSit (기본 posture 전용 L 은 그대로).
- 접수 = SUCCEEDED + SDK_ACCEPTED + sdk_code 0 · robot · request_id · SDK 이름 모두 일치. 물리 완료로 쓰지 않음.
- 세션당 action 한 건 · 접수 뒤에도 다음 의도 거부 · 세션 끝나면 「진행 상태 모름」 만 기록.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voice_client as V  # noqa: E402
from test_voice_client_l1 import R, Clock, held, intent, reply, state, lease  # noqa: E402

OTHER_R = '33333333-3333-4333-8333-333333333333'


def rig(profile=True, session_s=60):
    c = Clock()
    n = iter(range(1, 10_000))
    s = V.VoiceSession(R, session_s, now=c.now, wall_ms=c.wall, ids=lambda: f'f{next(n)}', action_profile=profile)
    return c, s


def ares(rid, action='Sit', status='SUCCEEDED', code='SDK_ACCEPTED', sdk_code=0):
    return dict(request_id=rid, action=action, status=status, code=code, sdk_code=sdk_code, mode=None, enabled=None)


def st(c, posture='STANDING', ar=None, robot=R, applied=(0, 0, 0)):
    m = state(c, posture)
    m.update(action_result=ar, robot=robot, applied=list(applied))
    return m


def kinds(s, k):
    return [r for r in s.rows if r['kind'] == k]


def sent_sit(c, s, action='sit_down'):
    held(c, s)
    out = s.submit(intent(c, action))
    assert len(out) == 1 and out[0]['t'] == 'action'
    return out[0]


def test_A1_default_profile_keeps_posture_only():
    c, s = rig(profile=False)
    held(c, s)
    assert s.submit(intent(c, 'sit_down')) == [] and s.submit(intent(c, 'sit_rise')) == []
    assert [r['why'] for r in kinds(s, 'intent_rejected')] == ['wrong_intent', 'wrong_intent']
    assert s.counts['action'] == 0
    assert s.submit(intent(c, 'stand_down'))[0]['t'] == 'posture'      # 기존 경로 그대로


def test_A2_sit_request_frame_and_sdk_accept_only():
    c, s = rig()
    f = sent_sit(c, s)
    assert (f['action'], f['params'], f['confirmed'], f['lease_id'], f['robot']) == ('Sit', {}, False, f['lease_id'], R)
    assert f['lease_id'] and s.counts == dict(take=1, release=0, cmd=0, posture=0, unlock=0, action=1)
    s.on_message(reply(f['id']))
    assert len(kinds(s, 'action_accepted_by_server')) == 1 and kinds(s, 'sdk_accepted') == []   # 서버 답 ≠ 접수
    s.on_message(st(c, ar=ares(f['id'], status='RUNNING', code='STARTED', sdk_code=None)))
    assert kinds(s, 'sdk_accepted') == []                                                      # RUNNING ≠ 접수
    s.on_message(st(c, ar=ares(f['id'])))
    acc = kinds(s, 'sdk_accepted')
    assert len(acc) == 1 and acc[0]['physical'] == 'unverified' and acc[0]['posture'] == 'STANDING'
    assert kinds(s, 'confirmed') == [] and s.action_unresolved
    # 접수 뒤에도 다음 의도 거부 (자세 · action 모두) · 재요청 없음
    c.go(.1); s.on_message(st(c))
    assert s.submit(intent(c, 'stand_down')) == [] and s.submit(intent(c, 'sit_rise', id='x2')) == []
    assert [r['why'] for r in kinds(s, 'intent_rejected')] == ['action_once', 'action_once']
    assert s.counts['action'] == 1 and s.counts['posture'] == 0


def test_A3_mismatched_results_do_not_count():
    c, s = rig()
    f = sent_sit(c, s)
    s.on_message(reply(f['id']))
    s.on_message(st(c, ar=ares('other-id')))                     # 다른 번호
    s.on_message(st(c, ar=ares(f['id'], action='RiseSit')))      # 다른 SDK 이름
    s.on_message(st(c, ar=ares(f['id']), robot=OTHER_R))         # 다른 로봇
    m = st(c); m['posture_result'] = dict(request_id=f['id'], action='stand_down', status='SUCCEEDED', code='CONFIRMED', sdk_code=0)
    s.on_message(m)                                              # 자세 결과 칸 (요청 종류 다름)
    assert kinds(s, 'sdk_accepted') == [] and kinds(s, 'ended') == [] and not s.pending['done']


def test_A4_success_without_exact_acceptance_is_not_accepted():
    for code, sdk in (('OTHER', 0), ('SDK_ACCEPTED', 3104), ('SDK_ACCEPTED', None), ('SDK_ACCEPTED', True)):
        c, s = rig()
        f = sent_sit(c, s)
        s.on_message(reply(f['id']))
        s.on_message(st(c, ar=ares(f['id'], code=code, sdk_code=sdk)))
        assert kinds(s, 'sdk_accepted') == [] and kinds(s, 'ended') == [] and not s.action_unresolved
        assert len(kinds(s, 'unexpected_result')) == 1             # 거절 · 실패와 구분되는 예상 밖 형식


def test_A5_rejected_or_failed_no_retry_and_no_more_intents():
    for status, code in (('REJECTED', 'MOVING'), ('FAILED', 'TIMEOUT')):
        c, s = rig()
        f = sent_sit(c, s)
        s.on_message(reply(f['id']))
        s.on_message(st(c, ar=ares(f['id'], status=status, code=code, sdk_code=3104 if status == 'FAILED' else None)))
        assert kinds(s, 'ended')[0]['result'] == f'{status}/{code}'
        c.go(.1); s.on_message(st(c))
        assert s.submit(intent(c, 'sit_down', id='again')) == []
        assert kinds(s, 'intent_rejected')[-1]['why'] == 'action_once' and s.counts['action'] == 1


def test_A6_server_refusal_no_retry():
    c, s = rig()
    f = sent_sit(c, s)
    s.on_message(reply(f['id'], ok=False, code='ACTION_MOVING'))
    assert s.pending['refused'] == 'ACTION_MOVING' and kinds(s, 'action_accepted_by_server') == []
    c.go(.1); s.on_message(st(c))
    assert s.submit(intent(c, 'sit_down', id='again')) == [] and s.counts['action'] == 1


def test_A7_no_result_is_unknown_and_closes():
    c, s = rig()
    f = sent_sit(c, s)
    s.on_message(reply(f['id']))
    c.go(V.RESULT_WAIT_S + .1)
    out = s.on_tick()
    assert [r['why'] for r in kinds(s, 'pending_unknown')] == ['result_timeout']
    assert s.why == 'result_unknown' and any(x['t'] == 'lease.release' for x in out)
    assert kinds(s, 'sdk_accepted') == [] and s.counts['action'] == 1


def test_A8_sit_precheck_uses_observable_state_only():
    c, s = rig()
    held(c, s)
    s.on_message(st(c, posture='LYING'))
    assert s.submit(intent(c, 'sit_down')) == [] and kinds(s, 'intent_rejected')[-1]['why'] == 'not_standing'
    s.on_message(st(c, applied=(.2, 0, 0)))
    assert s.submit(intent(c, 'sit_down', id='m')) == [] and kinds(s, 'intent_rejected')[-1]['why'] == 'moving'
    assert s.counts['action'] == 0 and not s.action_used          # 사전 검사 거절은 한 건으로 세지 않음


def test_A9_rise_sit_is_independent_trial_start_unverified():
    c, s = rig()
    f = sent_sit(c, s, 'sit_rise')
    assert f['action'] == 'RiseSit' and f['params'] == {} and f['confirmed'] is False
    assert kinds(s, 'intent_accepted')[0]['start_posture'] == 'unverified'
    s.on_message(reply(f['id']))
    s.on_message(st(c, ar=ares(f['id'], action='RiseSit')))
    assert len(kinds(s, 'sdk_accepted')) == 1 and kinds(s, 'confirmed') == []   # 서 있음 확인으로 바꾸지 않음


def _accepted(c, s):
    f = sent_sit(c, s)
    s.on_message(reply(f['id']))
    s.on_message(st(c, ar=ares(f['id'])))
    assert s.action_unresolved
    return f


def test_A10_end_after_accept_records_unknown_progress_only():
    # 운영자 닫기: 기존 순서 (게이트 닫기 → 반납) · 진행 상태 모름 한 번
    c, s = rig()
    _accepted(c, s)
    out = s.close('operator_close')
    assert [x['t'] for x in out] == ['lease.release'] and not s.gate
    u = kinds(s, 'action_unresolved_at_end')
    assert len(u) == 1 and u[0]['why'] == 'operator_close' and u[0]['action'] == 'sit_down'
    s.on_message(lease(None))
    assert s.phase == 'closed' and len(kinds(s, 'action_unresolved_at_end')) == 1
    # 세션 만료 · 건강 신호 상실 · 조종권 상실 · 연결 단절
    for go, why in ((lambda c, s: (c.go(61), s.on_tick()), 'session_expired'),
                    (lambda c, s: (c.go(V.HEALTH_WAIT_S + .1), s.on_tick()), 'recognizer_silent'),
                    (lambda c, s: s.on_message(lease(dict(holder_type='USER', user=None), 'other-lease')), 'lease_lost'),
                    (lambda c, s: s.on_disconnect(), 'connection_lost')):
        c, s = rig()
        _accepted(c, s)
        go(c, s)
        u = kinds(s, 'action_unresolved_at_end')
        assert len(u) == 1 and u[0]['why'] == why, (why, u)
        assert kinds(s, 'confirmed') == [] and s.counts['action'] == 1 and s.counts['take'] == 1


def test_A11_late_result_after_close_logged_once():
    c, s = rig()
    f = sent_sit(c, s)
    s.on_disconnect()
    for _ in range(3):
        s.on_message(st(c, ar=ares(f['id'])))
    late = kinds(s, 'late_result_ignored')
    assert len(late) == 1 and late[0]['code'] == 'SDK_ACCEPTED' and kinds(s, 'sdk_accepted') == []


def test_A12_one_frame_even_if_two_intents_before_reply():
    # Codex 보완 1: 한 건 선점은 프레임 만들기 직전 · 서버 답 전에 두 의도가 와도 프레임 1 건
    c, s = rig()
    f = sent_sit(c, s)
    assert s.submit(intent(c, 'sit_rise', id='q2')) == [] and s.submit(intent(c, 'stand_down', id='q3')) == []
    assert s.counts['action'] == 1 and s.counts['posture'] == 0 and s.action_used


def test_A13_late_accept_after_unknown_does_not_revive():
    # Codex 보완 2: 기한 넘어 UNKNOWN 된 요청에 뒤늦은 SDK_ACCEPTED 가 와도 성공으로 되살리지 않음
    c, s = rig(session_s=600)
    f = sent_sit(c, s)
    s.on_message(reply(f['id']))
    s.on_message(st(c, ar=ares('other-id')))                  # 불일치 결과는 기한을 갱신하지 않음
    c.go(V.RESULT_WAIT_S + .1)
    s.on_tick()
    assert [r['why'] for r in kinds(s, 'pending_unknown')] == ['result_timeout']
    s.on_message(st(c, ar=ares(f['id'])))
    assert kinds(s, 'sdk_accepted') == [] and not s.action_unresolved


def test_A14_unresolved_mark_survives_release_and_result_closure():
    # Codex 보완 3: 결과 종결 (SDK 접수) 과 실행 미확인은 별개 · 반납 관측은 완료/취소 증거 아님
    c, s = rig()
    _accepted(c, s)
    assert s.pending['done'] and s.pending['result'] == 'SDK_ACCEPTED' and s.action_unresolved
    rel = s.close('operator_close')                            # 결과 종결 뒤라 기존 순서대로 바로 반납 (물리 완료는 기다리지 않음)
    s.on_message(reply(rel[0]['id'])); s.on_message(lease(None))
    assert s.phase == 'closed' and s.action_unresolved
    assert not any(r['kind'] in ('confirmed', 'action_done', 'action_canceled') for r in s.rows)


def test_A15_accept_arrives_while_closing():
    # Codex 보완 꼭 1: 서버 답 뒤 닫기 → 닫는 중 SDK 접수 → 미확인 종료 한 번 · 그 뒤 반납 (방송 먼저 / reply 먼저)
    for order in ('broadcast_first', 'reply_first'):
        c, s = rig()
        f = sent_sit(c, s)
        s.on_message(reply(f['id']))
        assert s.close('operator_close') == [] and s.phase == 'closing'          # 결과 기다림 (반납 아직)
        out = s.on_message(st(c, ar=ares(f['id'])))
        assert len(kinds(s, 'sdk_accepted')) == 1 and [x['t'] for x in out] == ['lease.release']
        u = kinds(s, 'action_unresolved_at_end')
        assert len(u) == 1 and u[0]['why'] == 'operator_close'
        msgs = [lease(None), reply(out[0]['id'])] if order == 'broadcast_first' else [reply(out[0]['id']), lease(None)]
        for m in msgs:
            s.on_message(m)
        assert s.phase == 'closed' and len(kinds(s, 'action_unresolved_at_end')) == 1 and s.action_unresolved
        s.on_message(st(c, ar=ares(f['id'])))                                    # 닫힌 뒤 같은 결과: 되살리지 않음
        assert len(kinds(s, 'sdk_accepted')) == 1


def test_A16_close_before_server_reply_then_reply_and_accept():
    # 서버 답을 기다리는 동안 닫기 → 답 · 접수 도착
    c, s = rig()
    f = sent_sit(c, s)
    assert s.close('operator_close') == [] and s.phase == 'closing'
    assert s.on_message(reply(f['id'])) == []
    out = s.on_message(st(c, ar=ares(f['id'])))
    assert [x['t'] for x in out] == ['lease.release']
    assert len(kinds(s, 'action_unresolved_at_end')) == 1 and kinds(s, 'action_unresolved_at_end')[0]['why'] == 'operator_close'
    # 닫는 중 거절이면 미확인 표식 없음 (접수 안 됨)
    c, s = rig()
    f = sent_sit(c, s)
    s.close('operator_close'); s.on_message(reply(f['id']))
    s.on_message(st(c, ar=ares(f['id'], status='REJECTED', code='MOVING', sdk_code=None)))
    assert kinds(s, 'action_unresolved_at_end') == [] and not s.action_unresolved and s.release_sent
