"""L ① · C-1 음성 클라이언트 상태 기계 단위 시험 (가짜 시계 · 가짜 서버 메시지 · 네트워크 없음).

각 경계에서 기대 결과와 「음성 때문에 나간 제어 프레임 수」 (take · release · cmd · posture · unlock · action) 를 센다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voice_client as V  # noqa: E402

R = '11111111-1111-4111-8111-111111111111'
L1 = '22222222-2222-4222-8222-222222222222'


class Clock:
    def __init__(self):
        self.t, self.w = 100.0, 1_000_000

    def now(self):
        return self.t

    def wall(self):
        return self.w

    def go(self, s):
        self.t += s
        self.w += int(s * 1000)


def rig(session_s=60):
    c = Clock()
    n = iter(range(1, 10_000))
    s = V.VoiceSession(R, session_s, now=c.now, wall_ms=c.wall, ids=lambda: f'f{next(n)}')
    return c, s


def lease(holder=None, lease_id=None):
    return dict(t='lease', robot=R, holder=holder, lease_id=lease_id, since=None)


def state(c, posture='STANDING', res=None, latched=True):
    return dict(t='state', robot=R, connection='ONLINE', posture=dict(state=posture, mode=1 if posture == 'STANDING' else 5),
                posture_result=res, latched=latched, applied=[0, 0, 0])


def reply(fid, ok=True, code=None):
    return dict(t='reply', id=fid, ok=ok, **({} if ok else dict(error=dict(code=code))))


def intent(c, action='stand_down', **kw):
    return dict(dict(id=f'i{c.w}{action}', intent=action, robot=R, issued_at=c.w, ttl_ms=2000), **kw)


def held(c, s):
    s.open()
    take = s.on_message(lease(None))
    assert [f['t'] for f in take] == ['lease.take']
    s.on_message(reply(take[0]['id']))
    s.on_message(state(c))
    s.on_message(lease(dict(holder_type='USER', user=dict(id='u', display_name='v')), L1))
    assert s.phase == 'held' and s.gate
    return take


# ── 1. 누가 이미 쥐고 있으면 받지 않음 ──
def test_human_holds_no_take():
    c, s = rig()
    s.open()
    out = s.on_message(lease(dict(holder_type='USER', user=dict(id='h', display_name='사람'))))
    assert out == [] and s.phase == 'closed' and s.why == 'held_by_user'
    assert s.counts == dict(take=0, release=0, cmd=0, posture=0, unlock=0, action=0)


def test_run_holds_no_take():
    c, s = rig()
    s.open()
    s.on_message(lease(dict(holder_type='RUN', user=None)))
    assert s.phase == 'closed' and s.why == 'held_by_run' and s.counts['take'] == 0


def test_transfer_in_progress_server_refuses_take():
    c, s = rig()
    s.open()
    take = s.on_message(lease(None))                       # 비어 보였지만 서버엔 넘기는 중
    s.on_message(reply(take[0]['id'], ok=False, code='LEASE_HELD'))
    assert s.phase == 'closed' and s.why == 'take_refused_lease_held'
    assert s.counts['take'] == 1 and s.counts['posture'] == 0 and s.counts['cmd'] == 0


# ── 2. 받을 때 ──
def test_stop_confirm_failed_no_posture():
    c, s = rig()
    s.open()
    take = s.on_message(lease(None))
    s.on_message(reply(take[0]['id']))
    s.on_message(dict(t='lease.result', robot=R, request_id=None, result='CANCELED', error='STOP_CONFIRM_FAILED'))
    assert s.phase == 'closed' and s.why == 'take_stop_confirm_failed'
    assert s.submit(intent(c)) == [] and s.counts['posture'] == 0


def test_take_timeout_closes():
    c, s = rig()
    s.open()
    s.on_message(lease(None))
    c.go(V.TAKE_WAIT_S + .1); s.health()
    s.on_tick()
    assert s.phase == 'closing' and s.why == 'take_timeout' and not s.gate and s.counts['posture'] == 0
    c.go(V.CLOSE_WAIT_S + .1)
    s.on_tick()
    assert s.phase == 'closed' and s.must_disconnect


def test_intent_heard_before_grant_is_not_replayed():
    c, s = rig()
    s.open()
    s.on_message(lease(None))
    early = intent(c)                                        # 받기 전에 들은 말
    assert s.submit(early) == []
    c.go(.5)
    s.on_message(state(c))
    s.on_message(lease(dict(holder_type='USER'), L1))
    again = dict(early, id='i-early-copy')                    # 같은 시각 (받기 전) 의 말을 받은 뒤 넣어도
    assert s.submit(again) == []
    assert [r['why'] for r in s.rows if r['kind'] == 'intent_rejected'] == ['not_held', 'before_grant']
    assert s.counts['posture'] == 0


# ── 3. 정상 · 한 건씩 · 결과로만 완료 ──
def test_stand_down_then_up_same_session():
    c, s = rig()
    held(c, s)
    c.go(.1); s.on_message(state(c))
    out = s.submit(intent(c))
    assert [f['t'] for f in out] == ['posture'] and out[0]['action'] == 'stand_down' and out[0]['lease_id'] == L1
    rid = out[0]['id']
    assert s.submit(intent(c, 'stand_up', id='other')) == []            # 한 건씩 (busy)
    s.on_message(reply(rid))
    s.on_message(state(c, 'STANDING', dict(request_id=rid, action='stand_down', status='SUCCEEDED', code='CONFIRMED')))
    assert not s.pending['done']                                           # 성공 결과여도 아직 서 있음 → 완료 아님
    s.on_message(state(c, 'LYING', dict(request_id=rid, action='stand_down', status='SUCCEEDED', code='CONFIRMED')))
    assert s.pending['result'] == 'CONFIRMED'
    c.go(.2); s.on_message(state(c, 'LYING'))
    out = s.submit(intent(c, 'stand_up'))
    rid2 = out[0]['id']
    assert rid2 != rid
    s.on_message(reply(rid2))
    s.on_message(state(c, 'STANDING', dict(request_id=rid2, action='stand_down', status='SUCCEEDED', code='CONFIRMED')))
    assert not s.pending['done']                                           # 같은 번호 · 다른 동작 → 아님
    s.on_message(state(c, 'STANDING', dict(request_id=rid2, action='stand_up', status='SUCCEEDED', code='CONFIRMED')))
    assert [r['action'] for r in s.rows if r['kind'] == 'confirmed'] == ['stand_down', 'stand_up']
    assert s.counts['posture'] == 2 and s.counts['unlock'] == 0 and s.counts['action'] == 0


def test_rejects_wrong_intent_expired_duplicate_stale():
    c, s = rig()
    held(c, s)
    c.go(.1); s.on_message(state(c))
    assert s.submit(intent(c, 'sit_down')) == []
    old = intent(c); c.go(2.5); s.on_message(state(c))
    assert s.submit(old) == []
    dup = intent(c)
    assert len(s.submit(dup)) == 1
    s.pending['done'] = True
    assert s.submit(dup) == []
    c.go(1.5)                                                               # 화면 상태가 1 s 넘게 안 옴
    assert s.submit(intent(c)) == []
    whys = [r['why'] for r in s.rows if r['kind'] == 'intent_rejected']
    assert whys == ['wrong_intent', 'expired', 'duplicate', 'stale']


def test_heartbeat_zero_only_with_increasing_seq():
    c, s = rig()
    held(c, s)
    frames = []
    for _ in range(35):
        c.go(.1)
        s.on_message(state(c))
        frames += s.on_tick()
    cmds = [f for f in frames if f['t'] == 'cmd']
    assert len(cmds) in (3, 4) and all(f['axes'] == [0, 0, 0] for f in cmds)
    assert [f['seq'] for f in cmds] == list(range(1, len(cmds) + 1))
    assert s.counts['unlock'] == 0 and s.counts['action'] == 0


# ── 4. 결과 불명 · 연결 · 조종권 잃음 ──
def test_result_unknown_closes_without_retry():
    c, s = rig()
    held(c, s)
    c.go(.1); s.on_message(state(c))
    rid = s.submit(intent(c))[0]['id']
    s.on_message(reply(rid))
    out = []
    for _ in range(int(V.RESULT_WAIT_S * 10) + 5):
        c.go(.1)
        out += s.on_message(state(c))
        s.health()
        out += s.on_tick()
    assert s.pending['unknown'] and s.why == 'result_unknown'
    assert [f['t'] for f in out if f['t'] in ('posture', 'lease.take')] == []        # 재요청 · 재취득 없음
    assert [f['t'] for f in out if f['t'] == 'lease.release'] == ['lease.release']


def test_disconnect_after_send_is_unknown_and_no_retake():
    c, s = rig()
    held(c, s)
    c.go(.1); s.on_message(state(c))
    s.submit(intent(c))
    s.on_disconnect()
    assert s.phase == 'closed' and s.why == 'connection_lost' and s.pending['unknown']
    assert s.on_tick() == [] and s.submit(intent(c, id='x')) == []


def test_lease_lost_closes_and_never_retakes():
    c, s = rig()
    held(c, s)
    s.on_message(lease(None))                                              # 만료 · 회수
    assert s.phase == 'closed' and s.why == 'lease_lost'
    c.go(5)
    assert s.on_tick() == [] and s.counts['take'] == 1


# ── 5. 닫기 · 사람에게 넘기기 ──
def test_handover_close_gate_first_wait_pending_then_release():
    c, s = rig()
    held(c, s)
    c.go(.1); s.on_message(state(c))
    rid = s.submit(intent(c))[0]['id']
    s.on_message(reply(rid))
    out = s.close('handover')
    assert out == [] and not s.gate and s.phase == 'closing'              # 보낸 요청 결과 전에는 반납 안 함
    assert s.submit(intent(c, 'stand_up', id='late')) == []
    rel = s.on_message(state(c, 'LYING', dict(request_id=rid, action='stand_down', status='SUCCEEDED', code='CONFIRMED')))
    assert [f['t'] for f in rel] == ['lease.release']
    s.on_message(reply(rel[0]['id']))
    assert s.phase == 'closed' and s.lease is None and s.why == 'handover'
    c.go(5)
    assert s.on_tick() == [] and s.counts['take'] == 1                     # 다시 잡지 않음


def test_session_expiry_and_recognizer_silence():
    c, s = rig(session_s=3)
    held(c, s)
    out = []
    for _ in range(40):
        c.go(.1); out += s.on_message(state(c)); s.health(); out += s.on_tick()
    assert s.why == 'session_expired' and [f['t'] for f in out].count('lease.release') == 1
    c2, s2 = rig()
    held(c2, s2)
    out2 = []
    for _ in range(60):
        c2.go(.1); out2 += s2.on_message(state(c2)); out2 += s2.on_tick()        # 건강 신호 없음
    assert s2.why == 'recognizer_silent' and [f['t'] for f in out2].count('lease.release') == 1


def test_grant_arriving_after_close_is_released_without_gate():
    c, s = rig()
    s.open()
    s.on_message(lease(None))
    s.close('user_close')
    out = s.on_message(lease(dict(holder_type='USER'), L1))
    assert [f['t'] for f in out] == ['lease.release'] and not s.gate and s.counts['posture'] == 0


def test_server_refused_posture_closes_request_only():
    c, s = rig()
    held(c, s)
    c.go(.1); s.on_message(state(c))
    rid = s.submit(intent(c))[0]['id']
    s.on_message(reply(rid, ok=False, code='POSTURE_NOT_ALLOWED'))
    assert s.pending['done'] and s.pending['refused'] == 'POSTURE_NOT_ALLOWED' and s.phase == 'held'
    assert s.counts['posture'] == 1


# ── Codex 판정 (11-25 「보완」) 재현을 회귀로 ──
import asyncio  # noqa: E402
import json  # noqa: E402
import types  # noqa: E402

import pytest  # noqa: E402


def test_R1_session_expiry_enforced_at_submit_before_tick():
    c, s = rig(session_s=3)
    held(c, s)
    c.go(3.1)
    out = s.submit(intent(c))                     # 상태 · 건강 신호 · 주기 점검 어느 것도 오기 전에 바로 의도
    assert [f['t'] for f in out if f['t'] == 'posture'] == [] and s.why == 'session_expired'
    assert [f['t'] for f in out] == ['lease.release']


def test_R1_recognizer_silence_enforced_at_submit():
    c, s = rig()
    held(c, s)
    c.go(5.1); s.on_message(state(c))
    out = s.submit(intent(c))
    assert s.counts['posture'] == 0 and s.why == 'recognizer_silent'


def test_R1_result_after_deadline_is_unknown_not_confirmed():
    c, s = rig()
    held(c, s)
    c.go(.1); s.on_message(state(c))
    rid = s.submit(intent(c))[0]['id']
    s.on_message(reply(rid))
    c.go(V.RESULT_WAIT_S + .1); s.health()
    s.on_message(state(c, 'LYING', dict(request_id=rid, action='stand_down', status='SUCCEEDED', code='CONFIRMED')))
    assert s.pending.get('unknown') and s.pending.get('result') is None
    assert [r for r in s.rows if r['kind'] == 'confirmed'] == []


def test_R1_session_s_must_be_finite_positive():
    for bad in (0, -1, float('inf'), float('nan'), True, '60'):
        with pytest.raises(ValueError):
            V.VoiceSession(R, bad)


def test_R2_offline_state_closes_and_blocks_new_intent():
    c, s = rig()
    held(c, s)
    out = s.on_message(dict(state(c), connection='OFFLINE'))
    assert s.phase in ('closing', 'closed') and not s.gate and s.why == 'robot_offline'
    assert [f['t'] for f in out] == ['lease.release']
    assert s.submit(intent(c)) == [] and s.counts['posture'] == 0


def test_R2_offline_old_result_not_read_as_confirmed():
    c, s = rig()
    held(c, s)
    c.go(.1); s.on_message(state(c))
    rid = s.submit(intent(c))[0]['id']
    s.on_message(reply(rid))
    s.on_message(dict(state(c, 'LYING', dict(request_id=rid, action='stand_down', status='SUCCEEDED', code='CONFIRMED')), connection='OFFLINE'))
    assert [r for r in s.rows if r['kind'] == 'confirmed'] == []


def test_R3_subscribe_without_snapshot_ends():
    c, s = rig()
    s.open()
    for _ in range(int(V.SUB_WAIT_S * 10) + 1):
        c.go(.1); s.health()
    s.on_tick()
    assert s.phase == 'closed' and s.why == 'subscribe_timeout' and s.must_disconnect and s.counts['take'] == 0


def test_R3_close_while_taking_without_notice_ends():
    c, s = rig()
    s.open(); s.on_message(lease(None)); s.close('user_close')
    c.go(V.CLOSE_WAIT_S + .1)
    s.on_tick()
    assert s.phase == 'closed' and s.why == 'user_close' and s.must_disconnect and not s.gate
    assert [r['why'] for r in s.rows if r['kind'] == 'close_unconfirmed'] == ['close_wait_timeout']


def test_R3_release_without_reply_is_unconfirmed():
    c, s = rig()
    held(c, s)
    rel = s.close('demo')
    assert [f['t'] for f in rel] == ['lease.release']
    c.go(V.RELEASE_WAIT_S + .1)
    s.on_tick()
    assert s.phase == 'closed' and s.must_disconnect
    assert [r['why'] for r in s.rows if r['kind'] == 'close_unconfirmed'] == ['release_unconfirmed']


class FakeWS:
    def __init__(self, incoming):
        self.incoming, self.sent, self.closed = list(incoming), [], False

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    async def close(self):
        self.closed = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        while not self.incoming or self.closed:
            await asyncio.sleep(.01)
        return self.incoming.pop(0)


def fake_websockets(ws, calls):
    mod = types.ModuleType('websockets')

    class ConnectionClosed(Exception):
        pass

    class Conn:
        async def __aenter__(self):
            return ws

        async def __aexit__(self, *a):
            ws.closed = True

    def connect(url, **kw):
        calls.append(url)
        return Conn()
    mod.connect, mod.ConnectionClosed = connect, ConnectionClosed
    return mod


@pytest.mark.parametrize('url', ['ws://example.com/api/v1/ws', 'ws://127.0.0.1/api/v1/ws', 'ws://127.0.0.1:0/api/v1/ws',
                                 'wss://127.0.0.1:8810/api/v1/ws', 'ws://u@127.0.0.1:8810/api/v1/ws',
                                 'ws://127.0.0.1:8810/api/v1/ws?x=1', 'ws://127.0.0.1:8810/other', 'ws://localhost:8810/api/v1/ws'])
def test_R4_runner_rejects_non_loopback_before_network(monkeypatch, url):
    calls = []
    monkeypatch.setitem(sys.modules, 'websockets', fake_websockets(FakeWS([]), calls))
    s = V.VoiceSession(R, 60)
    with pytest.raises(ValueError):
        asyncio.run(V.run_session(s, url, 'tok', asyncio.Queue()))
    assert calls == []


def test_R4_login_rejects_non_loopback_before_network(monkeypatch):
    import urllib.request
    hit = []
    monkeypatch.setattr(urllib.request, 'urlopen', lambda *a, **k: hit.append(a))
    for base in ('http://example.com:8810', 'https://127.0.0.1:8810', 'http://127.0.0.1'):
        with pytest.raises(SystemExit):
            V.app_login(base, 'u', 'p')
    assert hit == []


def test_R5_broken_message_after_grant_closes_gate(monkeypatch):
    msgs = [json.dumps(lease(None))]
    ws = FakeWS(msgs)
    calls = []
    monkeypatch.setitem(sys.modules, 'websockets', fake_websockets(ws, calls))
    s = V.VoiceSession(R, 60)

    async def main():
        q = asyncio.Queue()
        task = asyncio.create_task(V.run_session(s, 'ws://127.0.0.1:8810/api/v1/ws', 'tok', q))
        for _ in range(100):
            await asyncio.sleep(.02)
            take = next((f for f in ws.sent if f['t'] == 'lease.take'), None)
            if take:
                break
        ws.incoming += [json.dumps(reply(take['id'])), json.dumps(dict(state(None), _x=1)),
                        json.dumps(lease(dict(holder_type='USER'), L1))]
        for _ in range(100):
            await asyncio.sleep(.02)
            if s.phase == 'held':
                break
        assert s.phase == 'held' and s.gate
        ws.incoming.append('{broken json')
        await task
    with pytest.raises(json.JSONDecodeError):
        asyncio.run(main())
    assert s.phase == 'closed' and not s.gate and s.why == 'runner_error'


# ── Codex 재판정 (11-25 「보완」 2 차) 재현을 회귀로 ──
def test_S1_handover_does_not_reuse_subscribe_deadline():
    c, s = rig()
    held(c, s)
    for _ in range(20):
        c.go(.5); s.health()                                               # 구독 기한 (5 s) 훨씬 지남 · 인식기는 살아 있음
    s.on_message(state(c))
    rid = s.submit(intent(c))[0]['id']
    s.on_message(reply(rid))
    s.close('handover')
    c.go(.2); s.health()
    s.on_tick()
    assert s.phase == 'closing' and not s.must_disconnect                  # 바로 끝나지 않고 결과를 기다림
    rel = s.on_message(state(c, 'LYING', dict(request_id=rid, action='stand_down', status='SUCCEEDED', code='CONFIRMED')))
    assert [f['t'] for f in rel] == ['lease.release'] and [r['kind'] for r in s.rows].count('confirmed') == 1


def test_S1_late_result_after_closed_is_not_confirmed():
    c, s = rig()
    held(c, s)
    c.go(.1); s.on_message(state(c))
    rid = s.submit(intent(c))[0]['id']
    s.on_message(reply(rid))
    s.close('handover')
    for _ in range(int((V.RESULT_WAIT_S + V.RELEASE_WAIT_S) * 10) + 5):
        c.go(.1); s.on_tick()
    assert s.phase == 'closed' and s.pending['unknown']
    s.on_message(state(c, 'LYING', dict(request_id=rid, action='stand_down', status='SUCCEEDED', code='CONFIRMED')))
    assert [r for r in s.rows if r['kind'] == 'confirmed'] == []
    assert [r['kind'] for r in s.rows].count('late_result_ignored') == 1


def test_S1_release_then_disconnect_keeps_reason_and_marks_unconfirmed():
    c, s = rig()
    held(c, s)
    assert [f['t'] for f in s.close('handover')] == ['lease.release']
    s.on_disconnect()
    assert s.why == 'handover' and s.release_unconfirmed
    assert [r['why'] for r in s.rows if r['kind'] == 'close_unconfirmed'] == ['release_unconfirmed']


def test_S2_take_deadline_enforced_before_grant_message():
    c, s = rig()
    s.open(); s.on_message(lease(None))
    c.go(V.TAKE_WAIT_S + .1)
    s.on_message(state(c))
    out = s.on_message(lease(dict(holder_type='USER'), L1))              # 기한 뒤 grant
    assert s.phase != 'held' and not s.gate and [f['t'] for f in out] == ['lease.release']
    assert s.submit(intent(c)) == [] and s.counts['posture'] == 0


def test_S2_late_health_does_not_erase_silence():
    c, s = rig()
    held(c, s)
    c.go(V.HEALTH_WAIT_S + .1)
    s.health(); s.on_message(state(c))
    assert s.submit(intent(c)) == [] and s.counts['posture'] == 0 and s.why == 'recognizer_silent'


def test_S2_session_expired_before_grant_does_not_revive():
    c, s = rig(session_s=1)
    s.open(); s.on_message(lease(None))
    c.go(1.2); s.health()
    s.on_message(lease(dict(holder_type='USER'), L1))
    assert s.phase != 'held' and not s.gate and s.why == 'session_expired'


class FailFirstSend(FakeWS):
    async def send(self, raw):
        raise RuntimeError('send failed')


def test_S3_first_send_error_closes_session(monkeypatch):
    ws = FailFirstSend([])
    monkeypatch.setitem(sys.modules, 'websockets', fake_websockets(ws, []))
    s = V.VoiceSession(R, 60)
    with pytest.raises(RuntimeError):
        asyncio.run(V.run_session(s, 'ws://127.0.0.1:8810/api/v1/ws', 'tok', asyncio.Queue()))
    assert s.phase == 'closed' and not s.gate


# ── T. 반납 관측 · 반납 접수 답 순서 (11-25 시연에서 재현된 오분류 보완) ──
OTHER_R = '33333333-3333-4333-8333-333333333333'


def _closing(c, s):
    held(c, s)
    rel = s.close('demo')
    assert [f['t'] for f in rel] == ['lease.release'] and s.phase == 'closing' and not s.gate
    return rel[0]['id']


def _kinds(s, k):
    return [r for r in s.rows if r['kind'] == k]


def _after_close_quiet(c, s):
    """닫힌 뒤: 게이트 닫힘 · 종결 1 회 · 재반납 / 재취득 / 추가 posture 없음"""
    assert s.phase == 'closed' and not s.gate and s.lease is None
    assert len(_kinds(s, 'closed')) == 1
    c.go(V.CLOSE_WAIT_S + V.RELEASE_WAIT_S + 1)
    assert s.on_tick() == []
    assert s.submit(intent(c, id='after')) == []
    assert (s.counts['take'], s.counts['release'], s.counts['posture']) == (1, 1, 0)


def test_T1_broadcast_then_reply():
    c, s = rig()
    rid = _closing(c, s)
    s.on_message(lease(None))                                              # 서버: 이 로봇 조종권 없음 (먼저 옴)
    assert s.phase == 'closed' and s.why == 'demo' and not s.release_unconfirmed
    assert _kinds(s, 'close_unconfirmed') == [] and len(_kinds(s, 'release_observed')) == 1
    assert _kinds(s, 'release_reply_ok') == []                             # 답을 받은 것으로 지어내지 않음
    assert _kinds(s, 'closed')[0]['basis'] == 'holder_null_broadcast'
    s.on_message(reply(rid))                                               # 접수 답은 뒤에 따로
    assert len(_kinds(s, 'release_reply_ok')) == 1 and s.release_reply is True
    _after_close_quiet(c, s)


def test_T2_reply_then_broadcast():
    c, s = rig()
    rid = _closing(c, s)
    s.on_message(reply(rid))
    assert s.phase == 'closed' and _kinds(s, 'closed')[0]['basis'] == 'release_reply_ok'
    s.on_message(lease(None))
    assert len(_kinds(s, 'release_observed')) == 1 and len(_kinds(s, 'release_reply_ok')) == 1
    assert _kinds(s, 'close_unconfirmed') == [] and not s.release_unconfirmed
    _after_close_quiet(c, s)


def test_T3_duplicate_broadcast_counts_once():
    c, s = rig()
    _closing(c, s)
    s.on_message(lease(None)); s.on_message(lease(None)); s.on_message(lease(None))
    assert len(_kinds(s, 'release_observed')) == 1
    _after_close_quiet(c, s)


def test_T4_other_holder_or_other_robot_is_not_release():
    # 다른 주인 알림 (lease_id 는 그 연결에 숨겨짐) → 정상 반납으로 치지 않음
    c, s = rig()
    _closing(c, s)
    s.on_message(lease(dict(holder_type='USER', user=dict(id='x', display_name='y')), None))
    assert s.phase == 'closed' and s.release_unconfirmed and _kinds(s, 'release_observed') == []
    assert [r['why'] for r in _kinds(s, 'close_unconfirmed')] == ['release_unconfirmed']
    # 다른 로봇의 「조종권 없음」 → 무시 · 기한 뒤 확인 못 함
    c, s = rig()
    _closing(c, s)
    s.on_message(dict(lease(None), robot=OTHER_R))
    assert s.phase == 'closing' and _kinds(s, 'release_observed') == []
    # holder 항목이 빠진 이상 형식 → 정상 반납으로 치지 않음
    bad = lease(None); del bad['holder']
    s.on_message(bad)
    assert _kinds(s, 'release_observed') == [] and s.release_unconfirmed


def test_T5_neither_arrives_is_still_unconfirmed():
    c, s = rig()
    _closing(c, s)
    c.go(V.RELEASE_WAIT_S + .1)
    s.on_tick()
    assert s.phase == 'closed' and s.must_disconnect and s.release_unconfirmed
    assert _kinds(s, 'release_observed') == [] and _kinds(s, 'release_reply_ok') == []
    assert [r['why'] for r in _kinds(s, 'close_unconfirmed')] == ['release_unconfirmed']


def test_T6_real_loss_before_release_stays_lease_lost():
    c, s = rig()
    held(c, s)
    s.on_message(lease(None))                                              # 반납 보내기 전 회수 = 상실
    assert s.phase == 'closed' and s.why == 'lease_lost' and not s.release_sent
    assert _kinds(s, 'release_observed') == [] and s.counts['release'] == 0
    c.go(5)
    assert s.on_tick() == [] and s.counts['take'] == 1
