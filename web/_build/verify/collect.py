# -*- coding: utf-8 -*-
"""브라우저가 잰 계산 스타일을 파일로 받는다 (mai-os#24).

  왜 서버로 받나
    스냅샷은 요소 수백 개 x 속성 25개다. 대화로 옮기면 잘리거나 옮겨 적다 틀린다.
    브라우저가 직접 디스크에 쓰게 한다 (원칙 3).

  ★ 2026-09-02 독립 검수가 잡은 결함 · 경로 탈출
    전에는 `self.path.strip('/').replace('..','')` 뒤에 그대로 join 했다.
    Windows 절대경로 이름을 주면 join 이 출력 폴더를 **벗어난다.**
      /C:/Windows/Temp/evil  ->  C:/Windows/Temp/evil.json
    구분자·드라이브·탈출을 지우는 것으로는 못 막는다. 그래서 이제는
    «허용하는 이름 모양» 만 받고, 만든 경로가 출력 뿌리 안인지 다시 확인한다.

  ★ 함께 잡은 것 · 인증 없는 wildcard CORS
    아무 페이지나 이 포트에 쓸 수 있었다. 이제 토큰과 출처를 확인한다.
    토큰은 실행할 때 화면에 찍는다. 채취기에 `window.__SNAP_TOKEN` 으로 넣는다.

  이 서버는 «검증 도구» 다. 기능을 늘리지 않는다.
"""
import io
import ipaddress
import json
import os
import re
import secrets
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'snap')

# 받아들이는 이름. 이 모양이 아니면 거부한다 (드라이브·구분자·점 두 개가 애초에 못 들어온다)
NAME_OK = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')
MAX_BODY = 8 * 1024 * 1024        # 8MB. 스냅샷 하나는 실측 수백 KB

ALLOW_SCHEME = ('http', 'https')
ALLOW_HOST = ('localhost',)       # 이 이름 «자체» 만. 하위 도메인은 남의 것이다
ALLOW_PORT = range(1, 65536)      # 어느 포트에서 산출물을 띄울지는 그때그때 다르다

TOKEN = os.environ.get('SNAP_TOKEN') or secrets.token_urlsafe(16)


def origin_ok(origin):
    """이 출처를 믿을 수 있나. 접두사 비교가 아니라 «파싱해서» 본다.

    ★ 2026-09-02 독립 검수 2차 지적. 전에는 o.startswith('http://localhost') 였다.
      그러면 아래가 전부 통과한다. 전부 남의 서버다.
        http://localhost.evil.example      (하위 도메인이 아니라 완전히 다른 이름)
        http://127.0.0.1.evil.example
        http://localhost@evil.example      (@ 앞은 userinfo 다. 진짜 host 는 뒤)
      접두사는 문자열이 어디서 끝나는지 모른다. 그래서 host 를 «정확히» 견준다.

    None(출처 없음)은 통과시킨다. 브라우저가 아닌 곳에서 온 요청이고,
    그 경우는 토큰이 막는다. 토큰 검증은 이 함수와 무관하게 늘 돈다.
    """
    if origin is None:
        return True
    if origin == 'null':           # 샌드박스 iframe 등. 누구인지 알 수 없다
        return False
    try:
        u = urlsplit(origin)
    except ValueError:
        return False
    if u.scheme not in ALLOW_SCHEME:
        return False
    # 출처(Origin)는 scheme://host[:port] 뿐이다. 경로·질의·조각·userinfo 가 붙으면 위조다
    if u.path or u.query or u.fragment or u.username or u.password:
        return False
    host = u.hostname               # urlsplit 이 userinfo 와 포트를 이미 떼어 준다
    if not host:
        return False
    try:
        if u.port is not None and u.port not in ALLOW_PORT:
            return False
    except ValueError:
        return False
    if host in ALLOW_HOST:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False                # 이름이면 허용 목록에 «정확히» 있어야 한다


def safe_path(url_path, out=None):
    """URL 경로에서 안전한 저장 위치. 못 만들면 None.

    ★ 두 겹으로 본다.
      ① 이름 모양이 허용 목록에 맞는가
      ② 만들어진 절대경로가 정말 출력 뿌리 «안» 인가
    ①만으로는 부족하다는 것이 이번 결함의 교훈이다. 실제 경로를 다시 센다.
    """
    out = os.path.abspath(out or OUT)
    # ★ lstrip('/') 은 앞 슬래시를 «여러 개» 벗긴다. //evil 이 evil 로 통과했다
    #   (자기시험이 잡았다). 정확히 하나만 벗기고 나머지는 이름 규칙에 맡긴다.
    u = url_path or ''
    if not u.startswith('/'):
        return None
    name = u[1:]
    if '?' in name or '#' in name:
        return None
    if not NAME_OK.match(name):
        return None
    p = os.path.abspath(os.path.join(out, name + '.json'))
    root = out.rstrip(os.sep) + os.sep
    if not p.startswith(root):
        return None
    if os.path.dirname(p) != out.rstrip(os.sep):
        return None
    return p


class H(BaseHTTPRequestHandler):
    out_dir = None                 # main 이 정한다

    def _origin_ok(self):
        return origin_ok(self.headers.get('Origin'))

    def _cors(self):
        o = self.headers.get('Origin')
        if o and self._origin_ok():
            self.send_header('Access-Control-Allow-Origin', o)
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Snap-Token')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Vary', 'Origin')

    def _deny(self, code, why):
        self.send_response(code); self._cors()
        self.send_header('Content-Type', 'text/plain; charset=utf-8'); self.end_headers()
        self.wfile.write(('거부: %s' % why).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_POST(self):
        if not self._origin_ok():
            return self._deny(403, '허용하지 않는 출처')
        if self.headers.get('X-Snap-Token', '') != TOKEN:
            return self._deny(403, '토큰 불일치')
        try:
            n = int(self.headers.get('Content-Length', 0))
        except ValueError:
            return self._deny(400, '길이 없음')
        if n <= 0 or n > MAX_BODY:
            return self._deny(413, '본문 크기 %d' % n)
        p = safe_path(self.path, self.out_dir)
        if p is None:
            return self._deny(400, '이름이 허용 모양이 아님')
        raw = self.rfile.read(n)
        try:
            obj = json.loads(raw.decode('utf-8'))
        except Exception as e:
            return self._deny(400, 'JSON 이 아님 (%s)' % type(e).__name__)
        if not isinstance(obj, dict) or 'meta' not in obj or 'el' not in obj:
            return self._deny(400, '스냅샷 모양이 아님')
        io.open(p, 'w', encoding='utf-8').write(json.dumps(obj, ensure_ascii=False))
        self.send_response(200); self._cors()
        self.send_header('Content-Type', 'text/plain; charset=utf-8'); self.end_headers()
        self.wfile.write(('saved %s %d bytes' % (os.path.basename(p), len(raw))).encode())

    def log_message(self, *a):
        pass


def _kat():
    """★ 답을 아는 입력. 경로 탈출을 정말 막는지 «격리 폴더» 에서 본다."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        good = ['/snap', '/idx-after-d', '/pure_index.m', '/a']
        bad = ['/C:/Windows/Temp/evil', '/..%5Cevil', '/../evil', '/sub/dir/x',
               '/' + chr(92) + 'evil', '//evil', '/', '', '/.hidden', '/' + 'x' * 200,
               '/evil' + chr(0), '/C:evil', '/\\\\server\\share\\x']
        for u in good:
            p = safe_path(u, d)
            if p is None:
                return False, '성한 이름을 거부함: %r' % u
            if os.path.dirname(os.path.abspath(p)) != os.path.abspath(d):
                return False, '성한 이름이 밖으로 나감: %r -> %r' % (u, p)
        for u in bad:
            p = safe_path(u, d)
            if p is not None:
                return False, '위험한 이름을 통과시킴: %r -> %r' % (u, p)
        # 악성 요청 뒤에도 폴더가 비어 있어야 한다 (쓰기가 아예 없었다는 뜻)
        if os.listdir(d):
            return False, '격리 폴더에 파일이 생김'

    # ★ 출처 판정. 접두사 비교가 통과시키던 «혼동 출처» 를 반례로 고정한다
    good_origin = [
        None,                                  # 출처 없음. 토큰이 막는다
        'http://127.0.0.1:8834', 'http://127.0.0.1', 'https://127.0.0.1:8080',
        'http://localhost:8835', 'http://localhost',
        'http://[::1]:8834',                   # IPv6 되돌이
        'http://127.0.0.2:8000',               # 127/8 전체가 되돌이다
    ]
    bad_origin = [
        'http://localhost.evil.example',       # 접두사 비교가 통과시켰다
        'http://localhost.evil.example:8834',
        'http://127.0.0.1.evil.example',
        'http://localhost@evil.example',       # @ 앞은 userinfo 다
        'http://127.0.0.1@evil.example',
        'http://evil.example',
        'http://notlocalhost',
        'http://localhosts',
        'https://localhost.attacker.test',
        'file://localhost',                    # scheme 이 허용 밖
        'javascript:http://localhost',
        'null',                                # 샌드박스 iframe. 누구인지 모른다
        'http://localhost/path',               # 출처에 경로가 붙을 수 없다
        'http://localhost?x=1',
        'http://localhost#f',
        'http://127.0.0.1:99999',              # 포트가 범위 밖
        'http://',
        '',
        'localhost:8834',                      # scheme 이 없다
        'http://0x7f000001',                   # 16진 표기는 이름으로 읽힌다. 허용 목록에 없다
    ]
    for o in good_origin:
        if not origin_ok(o):
            return False, '성한 출처를 거부함: %r' % (o,)
    for o in bad_origin:
        if origin_ok(o):
            return False, '혼동 출처를 통과시킴: %r' % (o,)
    return True, ''


def main(port=8824, out=None):
    global OUT
    OUT = os.path.abspath(out or OUT)
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    os.makedirs(OUT, exist_ok=True)       # ★ 부수효과는 여기서만. import 로는 안 만든다
    H.out_dir = OUT
    print('수집기 · http://127.0.0.1:%d · 저장 %s' % (port, OUT))
    print('토큰 · 브라우저에서  window.__SNAP_TOKEN = %r' % TOKEN)
    HTTPServer(('127.0.0.1', port), H).serve_forever()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if '--selftest' in sys.argv:
        ok, why = _kat()
        print('수집기 자기시험 %s%s' % ('통과' if ok else '실패', '' if ok else ': ' + why))
        sys.exit(0 if ok else 1)
    main()
