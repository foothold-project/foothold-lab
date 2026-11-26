"""L 시연 · 「들은 음성 명령」 알림 통로 (읽기 전용 · 127.0.0.1 만 · 화면 표시용).

음성 시연이 들은 문장 · 보낸 요청 · 결과를 SSE 로 흘려보낸다. 화면은 받아서 안내 줄에 띄우기만 한다
(이 통로로 로봇에 무엇을 보내지 않음 · 화면도 이 내용으로 로봇에 요청하지 않음).
GET /voice-heard/events  (Origin 이 있으면 허용 목록만 · 없으면 받음 — 같은 출처를 검증한 것이 아님)
범위: 합성 wav 전용 · 읽기 전용 · loopback 노트북 시연. 실기용 인증 · 개인 발화 보호 장치가 아니다.
"""
import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ALLOWED_ORIGINS = {'http://127.0.0.1:5180'}


class HeardFeed:
    def __init__(self, port):
        self.port, self.subs, self.lock = port, [], threading.Lock()
        feed = self

        class H(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *a):
                pass

            def do_GET(self):
                origin = self.headers.get('Origin')
                if self.path != '/voice-heard/events' or (origin is not None and origin not in ALLOWED_ORIGINS):
                    self.send_response(404 if self.path != '/voice-heard/events' else 403)
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                q = queue.Queue(maxsize=200)
                with feed.lock:
                    feed.subs.append(q)
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                try:
                    self.wfile.write(b': open\n\n'); self.wfile.flush()
                    while True:
                        try:
                            ev = q.get(timeout=5)
                            self.wfile.write(b'data: ' + json.dumps(ev, ensure_ascii=False).encode() + b'\n\n')
                        except queue.Empty:
                            self.wfile.write(b': ping\n\n')
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    with feed.lock:
                        if q in feed.subs:
                            feed.subs.remove(q)

        self.server = ThreadingHTTPServer(('127.0.0.1', port), H)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def publish(self, ev):
        with self.lock:
            subs = list(self.subs)
        for q in subs:
            try:
                q.put_nowait(ev)
            except queue.Full:
                pass

    def close(self):
        self.server.shutdown()
        self.server.server_close()
