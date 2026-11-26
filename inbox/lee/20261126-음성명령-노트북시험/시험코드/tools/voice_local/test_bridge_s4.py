"""S4 · 로컬 음성 브리지 시험 (127.0.0.1 임시 포트 · 팀 서버 · Go2 없음).

앞부분은 가짜 받아쓰기로 브리지 규칙 (소비자 하나 · 폐기 · 만료 · 입력 상한 · 출처 · 토큰) 을 보고,
뒷부분은 실제 Vosk + 11-23 판정 규칙으로 합성 wav 6 개를 넣어 의도가 stand down · stand up 에서만 나오는지 본다
(stand up · don't stand up wav 는 11-25 추가 · 끝 무음 1.15 초로 다시 만든 개발용 시험 파일).
합성 wav (Kokoro af_heart) 는 사람 목소리가 아니다. 이 결과는 작동 확인이며 인식률 · 부정문 방어 합격이 아니다.
"""
import http.client
import json
import os
import threading
import time

import pytest

import bridge as B

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = os.path.expanduser('~/Desktop/foothold/1차 검토/26.11/26.11.23/2_음성인식_사람목소리시험_실기준비/시험코드')
MODEL = os.path.expanduser('~/foothold-voice/model_dl/vosk-model-small-en-us-0.15')
ORIGIN = 'http://127.0.0.1:5180'
ROBOT = '11111111-1111-4111-8111-111111111111'


class FakeListener:
    """wav 이름별로 정해 둔 판정을 내는 가짜 (Vosk 없이 규칙만 본다)"""
    script = {}

    def __init__(self):
        self.done = False

    def feed(self, b):
        if self.done:
            return None
        self.done = True
        return FakeListener.current


def start(tmp_path, factory=None, ttl_ms=B.TTL_MS):
    log = tmp_path / 'log.jsonl'
    br = B.Bridge(ROBOT, factory or FakeListener, str(log), [ORIGIN], 'tok', ttl_ms=ttl_ms)
    srv = B.ThreadingHTTPServer(('127.0.0.1', 0), B.make_handler(br))
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return br, srv, srv.server_address[1], log


def stop(br, srv):
    br.closing.set(); srv.shutdown(); srv.server_close()


def req(port, method, path, body=None, headers=None):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    h = {'host': '127.0.0.1:%d' % port, **(headers or {})}
    raw = json.dumps(body).encode() if body is not None else None
    if raw is not None:
        h['content-type'] = 'application/json'
    c.request(method, path, body=raw, headers=h)
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, (json.loads(data) if data else None)


class SSE:
    def __init__(self, port, origin=ORIGIN):
        self.c = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        self.c.request('GET', '/voice-local/events', headers={'host': '127.0.0.1:%d' % port, 'origin': origin})
        self.r = self.c.getresponse()
        self.session = self._session() if self.r.status == 200 else None

    def _session(self):
        name = None
        while True:
            line = self.r.fp.readline().decode()
            if line.startswith('event: '):
                name = line[7:].strip()
            elif line.startswith('data: ') and name == 'session':
                return json.loads(line[6:])

    def log(self, port, row, token=None):
        return req(port, 'POST', '/voice-local/log', row, {'origin': ORIGIN, 'x-voice-log-token': token or self.session['log_token']})

    def next_event(self):
        while True:
            line = self.r.fp.readline().decode()
            if line.startswith('data: '):
                return json.loads(line[6:])

    def close(self):
        self.r.close(); self.c.close()   # 응답까지 닫아야 소켓이 실제로 닫힌다


def say(port, sample, token='tok'):
    return req(port, 'POST', '/voice-local/say', {'sample': sample}, {'x-voice-token': token})


def rows(log):
    return [json.loads(x) for x in open(log, encoding='utf-8')] if os.path.exists(log) else []


def wait_for(cond, s=2.0):
    end = time.time() + s
    while time.time() < end:
        if cond():
            return True
        time.sleep(.02)
    return False


TRIGGER = dict(kind='trigger', phrase='foothold stand down', heard='foothold stand down')


def test_s4_open_sse_still_serves_say_and_log_and_delivers_once(tmp_path):
    FakeListener.current = TRIGGER
    br, srv, port, log = start(tmp_path)
    try:
        sse = SSE(port)
        assert sse.r.status == 200
        code, out = say(port, 'foothold_stand_down')            # SSE 가 열린 채로 say 처리
        assert code == 200 and out['delivery'] == 'queued'
        got = sse.next_event()
        assert got == out['intent'] and got['robot'] == ROBOT and got['intent'] == 'stand_down' and got['ttl_ms'] == 2000
        assert got['issued_at'] == out['captured_ms']            # 넣은 시각 (인식 뒤 새로 찍지 않음)
        assert sse.session['robot'] == ROBOT and len(sse.session['log_token']) == 32
        code, _ = sse.log(port, {'kind': 'accepted', 'intent': got['id']})
        assert code == 200
        assert wait_for(lambda: any(r['kind'] == 'bridge_sent' for r in rows(log)))
        assert [r['screen']['kind'] for r in rows(log) if r['kind'] == 'screen'] == ['accepted']
        sse.close()
    finally:
        stop(br, srv)


def test_s4_second_consumer_rejected_first_kept(tmp_path):
    FakeListener.current = TRIGGER
    br, srv, port, log = start(tmp_path)
    try:
        first = SSE(port)
        second = SSE(port)
        assert first.r.status == 200 and second.r.status == 409
        _, out = say(port, 'foothold_stand_down')
        assert out['delivery'] == 'queued' and first.next_event()['id'] == out['intent']['id']
        first.close()
    finally:
        stop(br, srv)


def test_s4_no_consumer_drops_and_no_replay_after_connect(tmp_path):
    FakeListener.current = TRIGGER
    br, srv, port, log = start(tmp_path)
    try:
        _, out = say(port, 'foothold_stand_down')
        assert out['delivery'] == 'no_consumer'
        sse = SSE(port)
        _, out2 = say(port, 'foothold_stand_down')
        assert sse.next_event()['id'] == out2['intent']['id']   # 앞 의도는 재생되지 않고 새 것만
        sse.close()
    finally:
        stop(br, srv)


def test_s4_disconnected_consumer_pending_is_dropped(tmp_path):
    FakeListener.current = TRIGGER
    br, srv, port, log = start(tmp_path)
    try:
        sse = SSE(port)
        sse.close()
        assert wait_for(lambda: any(r['kind'] == 'sse_closed' for r in rows(log)) or br.consumer is not None)
        # 끊긴 뒤 들어온 의도: 소비자가 정리됐으면 no_consumer, 정리 전이면 큐에 들어갔다가 끊김 처리에서 버려짐
        _, out = say(port, 'foothold_stand_down')
        assert out['delivery'] in ('no_consumer', 'queued')
        assert wait_for(lambda: br.consumer is None, 8)
        assert not any(r['kind'] == 'bridge_sent' for r in rows(log))
    finally:
        stop(br, srv)


def test_s4_expired_intent_is_not_sent(tmp_path):
    FakeListener.current = TRIGGER
    br, srv, port, log = start(tmp_path, ttl_ms=0)              # 바로 만료
    try:
        sse = SSE(port)
        _, out = say(port, 'foothold_stand_down')
        assert out['delivery'] == 'expired'
        assert not any(r['kind'] == 'bridge_sent' for r in rows(log))
        sse.close()
    finally:
        stop(br, srv)


@pytest.mark.parametrize('sample,why', [('../etc/passwd', 'sample_name'), ('/tmp/x', 'sample_name'), ('Foothold', 'sample_name'),
                                        ('no_such_sample', 'sample_missing_or_large')])
def test_s4_say_only_known_samples(tmp_path, sample, why):
    br, srv, port, log = start(tmp_path)
    try:
        assert say(port, sample) == (400, {'ok': False, 'why': why})
    finally:
        stop(br, srv)


def test_s4_bad_format_wav_rejected(tmp_path):
    import wave
    samples = tmp_path / 'samples'; samples.mkdir()
    with wave.open(str(samples / 'stereo.wav'), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b'\0' * 64)
    br, srv, port, log = start(tmp_path)
    br.samples = str(samples)
    try:
        assert say(port, 'stereo') == (400, {'ok': False, 'why': 'sample_format'})
    finally:
        stop(br, srv)


def test_s4_token_origin_host_and_body_limits(tmp_path):
    br, srv, port, log = start(tmp_path)
    try:
        assert say(port, 'foothold_stand_down', token='wrong')[0] == 403
        assert SSE(port, origin='http://evil.example').r.status == 403
        assert req(port, 'POST', '/voice-local/log', {'kind': 'x'}, {'origin': ORIGIN, 'x-voice-log-token': 'x'})[0] == 403   # 연결 전
        sse = SSE(port)
        lt = sse.session['log_token']
        assert say(port, 'foothold_stand_down', token=lt)[0] == 403                       # 기록 토큰으로 의도 못 만듦
        assert sse.log(port, {'kind': 'x'}, token='tok')[0] == 403                          # say 토큰으로 기록 못 함
        assert req(port, 'POST', '/voice-local/log', {'kind': 'x'}, {'origin': 'http://evil.example', 'x-voice-log-token': lt})[0] == 403
        assert req(port, 'POST', '/voice-local/log', {'kind': 'x'}, {'x-voice-log-token': lt})[0] == 403   # Origin 없음
        assert sse.log(port, {'kind': 'x' * 5000})[0] == 400
        assert sse.log(port, {'kind': 'ok'})[0] == 200
        assert req(port, 'GET', '/voice-local/health', headers={'host': 'evil.example'})[0] == 421
        assert not any(lt in json.dumps(r) or 'tok' == r.get('token') for r in rows(log))   # 토큰 값은 기록에 안 남김
        sse.close()
        assert wait_for(lambda: br.consumer is None, 3)
        assert sse.log(port, {'kind': 'after'}, token=lt)[0] == 403                         # 끊기면 기록 토큰 폐기
    finally:
        stop(br, srv)


def test_s4_consumer_changed_during_recognition_is_not_forwarded(tmp_path):
    first_closed = threading.Event()

    class Slow(FakeListener):
        def feed(self, b):
            first_closed.wait(3)
            return super().feed(b)
    FakeListener.current = TRIGGER
    br, srv, port, log = start(tmp_path, factory=Slow)
    try:
        a = SSE(port)
        out = {}
        t = threading.Thread(target=lambda: out.update(r=say(port, 'foothold_stand_down')))
        t.start()
        time.sleep(.2)
        a.close()
        assert wait_for(lambda: br.consumer is None, 3)
        b = SSE(port)                       # 인식 도중 새 화면이 붙음
        first_closed.set(); t.join(5)
        assert out['r'][1]['delivery'] == 'consumer_changed'
        assert not any(r['kind'] == 'bridge_sent' for r in rows(log))
        b.close()
    finally:
        stop(br, srv)


def test_s4_log_write_failure_is_visible(tmp_path):
    br, srv, port, log = start(tmp_path)
    br.log_path = str(tmp_path / 'no_dir' / 'log.jsonl')         # 쓸 수 없는 곳
    try:
        sse = SSE(port)
        code, out = sse.log(port, {'kind': 'x'})
        assert code == 500 and out['why'] == 'write_failed'
        sse.close()
    finally:
        stop(br, srv)


# ── 실제 Vosk + 11-23 판정 규칙 (합성 wav · 작동 확인만) ──
@pytest.mark.parametrize('sample,expect_intent', [('foothold_stand_down', 'stand_down'), ('foothold_dont_stand_down', None),
                                                  ('foothold_sit_down', None), ('ordinary_sentence', None),
                                                  ('foothold_stand_up', 'stand_up'), ('foothold_dont_stand_up', None)])   # (나)
def test_s4_real_vosk_only_stand_down_or_up_makes_intent(tmp_path, sample, expect_intent):
    if not os.path.isdir(MODEL) or not os.path.isdir(RULES):
        pytest.skip('Vosk 모델 · 11-23 규칙 없음')
    factory = B.vosk_listener_factory(MODEL, RULES)
    br, srv, port, log = start(tmp_path, factory=factory)
    try:
        code, out = say(port, sample)
        got = out['intent']['intent'] if out['intent'] else None
        print('\n[S4 Vosk] %s → 들은 것 %s · 의도 %s' % (sample, out['heard'], got or '없음'))
        assert code == 200 and got == expect_intent
    finally:
        stop(br, srv)


# ── 판정 보완 3 · 4 ──
class RawSSE(SSE):
    def __init__(self, port, headers):
        self.c = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        self.c.request('GET', '/voice-local/events', headers={'host': '127.0.0.1:%d' % port, **headers})
        self.r = self.c.getresponse()
        self.session = self._session() if self.r.status == 200 else None


@pytest.mark.parametrize('headers,code', [
    ({'referer': ORIGIN + '/', 'sec-fetch-site': 'same-origin'}, 200),            # 같은 출처 GET (Origin 없음)
    ({'referer': ORIGIN + '/', 'sec-fetch-site': 'cross-site'}, 403),
    ({'referer': ORIGIN + '/'}, 403),
    ({'sec-fetch-site': 'same-origin'}, 403),
    ({'referer': 'http://evil.example/', 'sec-fetch-site': 'same-origin'}, 403),
    ({'origin': 'http://evil.example', 'referer': ORIGIN + '/', 'sec-fetch-site': 'same-origin'}, 403),   # Origin 있으면 그것만 본다
    ({'origin': ORIGIN}, 200),
])
def test_s4_events_same_origin_fallback(tmp_path, headers, code):
    br, srv, port, log = start(tmp_path)
    try:
        s = RawSSE(port, headers)
        assert s.r.status == code
        if code == 200:
            assert s.session['robot'] == ROBOT
            assert req(port, 'POST', '/voice-local/log', {'kind': 'x'}, {'x-voice-log-token': s.session['log_token']})[0] == 403   # log 는 여전히 Origin 필수
        s.close()
    finally:
        stop(br, srv)


@pytest.mark.parametrize('url', ['ws://127.0.0.1:8810@example.com/api/v1/agent/ws', 'ws://user@127.0.0.1:8810/api/v1/agent/ws',
                                 'ws://127.0.0.1/api/v1/agent/ws', 'wss://127.0.0.1:8810/api/v1/agent/ws', 'ws://localhost:8810/api/v1/agent/ws',
                                 'ws://127.0.0.1:8810/other', 'ws://127.0.0.1:8810/api/v1/agent/ws?x=1', 'ws://127.0.0.1:99999/api/v1/agent/ws',
                                 'ws://127.0.0.2:8810/api/v1/agent/ws'])
def test_s5_agent_url_rejected_before_token(tmp_path, url):
    import subprocess, sys as _sys
    r = subprocess.run([_sys.executable, os.path.join(HERE, 's5_agent.py'), '--url', url, '--token-file', str(tmp_path / 'none'),
                        '--log', str(tmp_path / 'a.jsonl')], capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and 'loopback 서버 고정 경로만 허용' in r.stderr
    assert not (tmp_path / 'a.jsonl').exists()


def test_s5_agent_good_url_passes_check(tmp_path):
    import subprocess, sys as _sys
    r = subprocess.run([_sys.executable, os.path.join(HERE, 's5_agent.py'), '--url', 'ws://127.0.0.1:8810/api/v1/agent/ws',
                        '--token-file', str(tmp_path / 'none'), '--log', str(tmp_path / 'a.jsonl')], capture_output=True, text=True, timeout=60)
    assert 'loopback 서버 고정 경로만 허용' not in r.stderr and 'FileNotFoundError' in r.stderr   # 검사 통과 → 다음 단계 (토큰 파일 없음) 에서 멈춤
