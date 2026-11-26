#!/usr/bin/env python3
"""로컬 음성 → 엎드리기 · 일어서기 연동 시험용 브리지 (S4 · 가짜 Go2 장치 시험 전용 · 같은 노트북 loopback 만).

하는 일
  - 알려진 시험 wav (samples/ 안 이름만) 를 Vosk 로 받아쓰고, 11-23 판정 규칙 (hey_foothold_1123.Listener ·
    CMD_REPLY · CMD_REJECT) 으로 「foothold stand down」 · 「foothold stand up」 을 알아들었을 때만 의도 하나를 만든다.
  - 의도 {id uuid · intent stand_down | stand_up · robot (시작 때 고정) · issued_at (wav 를 넣은 시각 ms) · ttl_ms 2000} 를
    지금 연결된 화면 하나 (SSE) 에 한 번 보낸다. 연결이 없거나 끊겼거나 기한이 지났으면 버린다 (재전송 · 과거 이벤트 재생 없음).
  - 화면이 보낸 관찰 기록을 JSONL 로 남긴다 (실패하면 500 으로 드러냄).
하지 않는 일
  - 팀 서버 · 에이전트 · Go2 에 아무것도 보내지 않는다. 의도를 받은 화면이 자기 조종권으로 기존 자세 요청을 보낸다.
  - 임의 파일 경로를 열지 않는다. 0.0.0.0 에 열지 않는다. CORS 허용 헤더를 내지 않는다.

경로
  GET  /voice-local/events   SSE · 소비자 하나 (두 번째는 409) · Origin 이 허용 목록일 때만
  POST /voice-local/log      화면 기록 (JSON 한 줄 · 4 KB 상한) · Origin 허용 목록일 때만
  POST /voice-local/say      {"sample": "<samples 안 이름>"} · 시작 때 만든 토큰 헤더 X-Voice-Token 필수 (CLI 전용)
  GET  /voice-local/health   상태
실행: python3 bridge.py --robot <로봇 UUID> [--port 8821] [--origin http://127.0.0.1:5180]
      (Vosk 가 든 venv · 모델 · 11-23 규칙 위치는 인자로)
"""
import argparse
import json
import os
import queue
import select
import socket
import re
import secrets
import sys
import threading
import time
import uuid
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, 'samples')
INTENT_PHRASES = {'foothold stand down': 'stand_down', 'foothold stand up': 'stand_up'}   # (나) 두 의도 · 나머지 명령은 의도 없음
INTENT_PHRASE = 'foothold stand down'                                                     # 이전 이름 (시험 호환)
TTL_MS = 2000
MAX_WAV_BYTES = 2_000_000          # 16 kHz · 16 bit · 1 채널 기준 약 60 초
MAX_WAV_SECONDS = 10.0
MAX_LOG_BYTES = 4096
SSE_PING_S = 5.0
SSE_POLL_S = 0.5
NAME_RE = re.compile(r'^[a-z0-9_]{1,64}$')


def now_ms():
    return int(time.time() * 1000)


class Bridge:
    def __init__(self, robot, listener_factory, log_path, origins, token, ttl_ms=TTL_MS, samples=SAMPLES):
        self.robot, self.listener_factory, self.log_path = robot, listener_factory, log_path
        self.origins, self.token, self.ttl_ms, self.samples = set(origins), token, ttl_ms, samples
        self.lock = threading.Lock()
        self.consumer = None            # 지금 연결된 SSE 의 큐 하나
        self.log_token = None           # 그 연결 전용 기록 토큰 (say 에는 쓸 수 없음 · 끊기면 버림)
        self.recognizing = threading.Lock()
        self.closing = threading.Event()

    # ── 기록 ──
    def record(self, row):
        line = json.dumps(dict(row, bridge_ms=now_ms()), ensure_ascii=False)
        with self.lock, open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

    def note(self, row):
        """브리지 자체 기록: 실패해도 동작은 계속 (경고만 · 화면 기록 실패는 500 으로 따로 알림)"""
        try:
            self.record(row)
        except OSError as e:
            print('[bridge] 기록 실패 %s · %s' % (type(e).__name__, row.get('kind')), file=sys.stderr, flush=True)

    # ── SSE 소비자 ──
    def attach(self):
        with self.lock:
            if self.consumer is not None:
                return None
            self.consumer = queue.Queue(maxsize=8)
            self.log_token = secrets.token_hex(16)
            return self.consumer, self.log_token

    def detach(self, q):
        with self.lock:
            if self.consumer is q:
                self.consumer = None
                self.log_token = None

    def deliver(self, intent, bound):
        """받아쓰기 시작 때 연결돼 있던 화면 (bound) 에만 한 번. 없거나 바뀌었거나 기한이 지났으면 버린다"""
        if now_ms() - intent['issued_at'] >= intent['ttl_ms']:
            return 'expired'
        with self.lock:
            q = self.consumer
        if q is None or bound is None:
            return 'no_consumer'
        if q is not bound:
            return 'consumer_changed'
        try:
            q.put_nowait(intent)
        except queue.Full:
            return 'consumer_full'
        return 'queued'

    # ── 받아쓰기 ──
    def read_sample(self, name):
        if not isinstance(name, str) or not NAME_RE.match(name):
            raise ValueError('sample_name')
        path = os.path.join(self.samples, name + '.wav')
        if not os.path.isfile(path) or os.path.getsize(path) > MAX_WAV_BYTES:
            raise ValueError('sample_missing_or_large')
        with wave.open(path) as w:
            if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, 16000):
                raise ValueError('sample_format')
            if w.getnframes() / 16000 > MAX_WAV_SECONDS:
                raise ValueError('sample_long')
            return w.readframes(w.getnframes())

    def say(self, name):
        """wav 하나 → 판정들 → stand down · stand up 이면 의도 하나 (그 wav 에서 처음 허용 명령만 · 복합 발화 검증 아님)"""
        captured = now_ms()                       # 넣은 (수집) 시각. 느린 인식 뒤 새로 찍지 않는다
        with self.lock:
            bound = self.consumer                 # 이 시각에 연결된 화면에만 넘긴다
        if not self.recognizing.acquire(blocking=False):
            return dict(ok=False, why='busy')
        try:
            data = self.read_sample(name)
            listener, results = self.listener_factory(), []
            for i in range(0, len(data), 4000):
                r = listener.feed(data[i:i + 4000])
                if r and r.get('kind') != 'empty':
                    results.append(r)
        finally:
            self.recognizing.release()
        heard = [dict(kind=r['kind'], phrase=r.get('phrase') or r.get('grammar'), heard=r.get('heard')) for r in results]
        hit = next((r for r in results if r.get('kind') == 'trigger' and r.get('phrase') in INTENT_PHRASES), None)
        out = dict(ok=True, sample=name, heard=heard, captured_ms=captured, recognized_ms=now_ms())
        if hit is None:
            out['intent'] = None
            self.note(dict(kind='bridge_no_intent', **out))
            return out
        intent = dict(id=str(uuid.uuid4()), intent=INTENT_PHRASES[hit['phrase']], robot=self.robot, issued_at=captured, ttl_ms=self.ttl_ms)
        out['intent'] = intent
        out['delivery'] = self.deliver(intent, bound)
        self.note(dict(kind='bridge_intent', **out))
        return out


def make_handler(bridge):
    class H(BaseHTTPRequestHandler):
        server_version = 'voice-local-bridge'
        protocol_version = 'HTTP/1.1'

        def log_message(self, *a):
            pass

        def _send(self, code, body):
            raw = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('content-type', 'application/json; charset=utf-8')
            self.send_header('content-length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _peer_closed(self):
            """화면이 연결을 닫았나 (읽을 것이 있는데 0 바이트 = 닫힘). 쓰기 성공만으로는 전달을 알 수 없다"""
            try:
                ready, _, _ = select.select([self.connection], [], [], 0)
                return bool(ready) and self.connection.recv(1, socket.MSG_PEEK) == b''
            except OSError:
                return True

        def _host_ok(self):
            host = self.headers.get('host', '')
            return host.split(':')[0] in ('127.0.0.1', 'localhost')

        def _origin_ok(self):
            return self.headers.get('origin') in bridge.origins

        def _events_origin_ok(self):
            """SSE GET 전용: 같은 출처 GET 은 Origin 이 없을 수 있다 (Fetch 명세).
            Origin 이 있으면 허용 목록과 정확히 같아야 하고, 없으면 Referer 출처가 허용 목록이고
            Sec-Fetch-Site 가 same-origin 일 때만 받는다. 다른 · 모르는 출처는 거부"""
            origin = self.headers.get('origin')
            if origin is not None:
                return origin in bridge.origins
            ref = urlsplit(self.headers.get('referer', ''))
            ref_origin = '%s://%s' % (ref.scheme, ref.netloc) if ref.scheme and ref.netloc else None
            return ref_origin in bridge.origins and self.headers.get('sec-fetch-site') == 'same-origin'

        def _body(self, limit):
            n = int(self.headers.get('content-length') or 0)
            if n <= 0 or n > limit:
                raise ValueError('body_size')
            return json.loads(self.rfile.read(n))

        def do_GET(self):
            if not self._host_ok():
                return self._send(421, dict(ok=False, why='host'))
            if self.path == '/voice-local/health':
                with bridge.lock:
                    busy = bridge.consumer is not None
                return self._send(200, dict(ok=True, robot=bridge.robot, consumer=busy))
            if self.path != '/voice-local/events':
                return self._send(404, dict(ok=False))
            if not self._events_origin_ok():
                return self._send(403, dict(ok=False, why='origin'))
            got = bridge.attach()
            if got is None:
                return self._send(409, dict(ok=False, why='consumer_exists'))
            q, log_token = got
            bridge.note(dict(kind='sse_open'))
            try:
                self.send_response(200)
                self.send_header('content-type', 'text/event-stream')
                self.send_header('cache-control', 'no-store')
                self.end_headers()
                session = json.dumps(dict(log_token=log_token, robot=bridge.robot))
                self.wfile.write(('event: session\ndata: %s\n\n' % session).encode()); self.wfile.flush()   # 의도와 구분되는 제어 이벤트
                last_ping = time.monotonic()
                while not bridge.closing.is_set():
                    if self._peer_closed():
                        break
                    try:
                        intent = q.get(timeout=SSE_POLL_S)
                    except queue.Empty:
                        if time.monotonic() - last_ping >= SSE_PING_S:
                            self.wfile.write(b': ping\n\n'); self.wfile.flush(); last_ping = time.monotonic()
                        continue
                    if now_ms() - intent['issued_at'] >= intent['ttl_ms']:
                        bridge.note(dict(kind='bridge_drop_expired', intent=intent['id']))
                        continue
                    if self._peer_closed():                  # 보내기 직전에도 끊김 확인 (줄이는 것일 뿐 경합은 남는다)
                        bridge.note(dict(kind='bridge_drop_disconnected', intent=intent['id']))
                        break
                    self.wfile.write(('data: %s\n\n' % json.dumps(intent)).encode()); self.wfile.flush()
                    bridge.note(dict(kind='bridge_sent', intent=intent['id']))   # 로컬 SSE 쓰기 · flush 완료일 뿐 브라우저 수신 증거 아님
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                bridge.detach(q)
                while not q.empty():          # 끊긴 소비자의 미전송 의도는 버린다
                    bridge.note(dict(kind='bridge_drop_disconnected', intent=q.get_nowait()['id']))
                bridge.note(dict(kind='sse_closed'))
            self.close_connection = True

        def do_POST(self):
            if not self._host_ok():
                return self._send(421, dict(ok=False, why='host'))
            try:
                if self.path == '/voice-local/log':
                    if not self._origin_ok():
                        return self._send(403, dict(ok=False, why='origin'))
                    with bridge.lock:
                        current = bridge.log_token
                    if current is None or not secrets.compare_digest(self.headers.get('x-voice-log-token', ''), current):
                        return self._send(403, dict(ok=False, why='log_token'))
                    row = self._body(MAX_LOG_BYTES)
                    if not isinstance(row, dict) or not isinstance(row.get('kind'), str):
                        return self._send(400, dict(ok=False, why='row'))
                    try:
                        bridge.record(dict(screen=row, kind='screen'))
                    except OSError as e:
                        return self._send(500, dict(ok=False, why='write_failed', detail=type(e).__name__))
                    return self._send(200, dict(ok=True))
                if self.path == '/voice-local/say':
                    if not secrets.compare_digest(self.headers.get('x-voice-token', ''), bridge.token):
                        return self._send(403, dict(ok=False, why='token'))
                    req = self._body(512)
                    try:
                        return self._send(200, bridge.say(req.get('sample')))
                    except ValueError as e:
                        return self._send(400, dict(ok=False, why=str(e)))
                return self._send(404, dict(ok=False))
            except (ValueError, json.JSONDecodeError):
                return self._send(400, dict(ok=False, why='body'))
    return H


def vosk_listener_factory(model_dir, rule_dir):
    sys.path.insert(0, rule_dir)
    import hey_foothold_1123 as R
    from vosk import Model, SetLogLevel
    SetLogLevel(-1)
    model = Model(model_dir)
    return lambda: R.Listener(model, R.CMD_REPLY, R.CMD_REJECT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--robot', required=True)
    ap.add_argument('--port', type=int, default=8821)
    ap.add_argument('--origin', action='append', default=None)
    ap.add_argument('--model', default=os.path.expanduser('~/foothold-voice/model_dl/vosk-model-small-en-us-0.15'))
    ap.add_argument('--rules', required=True, help='hey_foothold_1123.py 가 있는 폴더 (11-23 시험코드)')
    ap.add_argument('--log', default=os.path.join(HERE, 'logs', 'voice_local.jsonl'))
    ap.add_argument('--token-file', default=os.path.join(HERE, 'logs', 'say.token'))
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.log), exist_ok=True)
    token = secrets.token_hex(16)
    fd = os.open(a.token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)   # 만들 때부터 0600
    with os.fdopen(fd, 'w') as f:
        f.write(token)
    bridge = Bridge(a.robot, vosk_listener_factory(a.model, a.rules), a.log, a.origin or ['http://127.0.0.1:5180'], token)
    srv = ThreadingHTTPServer(('127.0.0.1', a.port), make_handler(bridge))
    srv.daemon_threads = True
    bridge.note(dict(kind='bridge_start', robot=a.robot, port=a.port))
    print('[bridge] 127.0.0.1:%d · robot %s · 기록 %s · 토큰 파일 %s' % (a.port, a.robot, a.log, a.token_file), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        bridge.closing.set()
        srv.server_close()
        bridge.note(dict(kind='bridge_stop'))


if __name__ == '__main__':
    main()
