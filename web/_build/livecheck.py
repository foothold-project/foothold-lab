# -*- coding: utf-8 -*-
"""민 것이 «라이브에 실제로 올라갔는가» 를 확인한다. 배포 뒤에 돌린다.

  python _build/livecheck.py                  마지막 커밋이 바꾼 페이지
  python _build/livecheck.py --commit HEAD~2  그 커밋이 바꾼 페이지

★ 2026-09-09. 오늘 하루에 이 확인을 손으로 여섯 번 했다. 두 번 하면 자동화를
  검토하라는 것이 이 저장소의 규칙이다.

  그리고 손으로 하면 틀린다. 오늘 실제로 겪은 것들이다.
    · `curl` 이 308 스텁 15바이트를 받아 왔는데 «없다» 고 읽을 뻔했다 (-L 누락)
    · 배포가 아직 안 돈 순간에 404 를 보고 «안 올라갔다» 고 할 뻔했다
    · 브라우저 캐시가 옛 색인을 줘서 «고쳤는데 안 고쳐진» 것처럼 보였다

무엇을 보나 (대리 신호가 아니라 결과를 본다)
  ① 그 주소가 200 인가            · 308 리다이렉트를 따라간 «뒤» 의 응답
  ② 라이브 바이트가 내 것과 같은가 · 「배포됐다」의 유일한 증거다
  ③ 새 페이지가 색인에 있는가      · 열리는 것과 찾히는 것은 다르다

  ②를 보는 이유: 배포는 «비동기» 다. push 직후에는 옛 판이 200 으로 응답한다.
  200 만 보면 「올라갔다」고 말하게 된다. 그것이 오늘 하루의 실패 부류다.
"""
import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import quote

SITE = 'https://foothold-project.vercel.app'
STAMP = re.compile(rb'<!--stamp:v1-->.*?<!--/stamp:v1-->', re.S)


def _fetch(url, timeout=25):
    """(갈래, 상태, 본문). 리다이렉트를 «따라간 뒤» 를 본다.

    ★ 2026-09-09. 처음에는 실패를 전부 «상태 0» 하나로 냈다. 그래서 내 도구가
      한글 주소를 못 만들어 죽은 것을 「그 페이지가 라이브에 없다」로 읽었다.
      **도구의 실패와 대상의 실패는 다른 사실이다.** 넷을 갈라 적는다.

        없음     404 · 410. 대상이 없다
        답이다름  그 밖의 HTTP 상태. 서버가 다른 답을 했다
        못감     연결·시간초과. 내가 거기까지 못 갔다 (망 · 프록시)
        내결함   요청을 «만들다» 죽었다. 내 도구가 틀렸다
    """
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'foothold-livecheck',
            'Cache-Control': 'no-cache'})
    except Exception as e:
        return '내결함', 0, str(e).encode('utf-8', 'replace')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 'ok', r.status, r.read()
    except urllib.error.HTTPError as e:
        return ('없음' if e.code in (404, 410) else '답이다름'), e.code, b''
    except (UnicodeError, ValueError) as e:
        return '내결함', 0, str(e).encode('utf-8', 'replace')
    except Exception as e:
        return '못감', 0, str(e).encode('utf-8', 'replace')


def _norm(b):
    """빌드 도장을 뺀 바이트. 도장은 배포마다 달라 비교에 못 쓴다."""
    return STAMP.sub(b' ', b)


def changed_pages(site_dir, commit):
    r = subprocess.run(['git', '-C', site_dir, 'show', '--name-only',
                        '--format=', commit],
                       capture_output=True, text=True, encoding='utf-8')
    if r.returncode != 0:
        return None
    out = []
    for line in (r.stdout or '').split('\n'):
        f = line.strip()
        if f.endswith('.html') and os.path.isfile(os.path.join(site_dir, f)):
            out.append(f)
    return sorted(out)


def url_for(f):
    """cleanUrls 규칙. index.html 은 폴더 주소가 된다.

    ★ 한글 파일 이름을 «반드시» 퍼센트 인코딩한다. 안 하면 urllib 이
      UnicodeEncodeError 로 죽고, 그것을 「사이트가 응답 안 함」 으로 읽게 된다.
      실측 2026-09-09: 이 도구를 만든 첫 판이 그래서 멀쩡한 페이지 셋을
      «안 올라감» 으로 보고했다. 도구의 실패를 대상의 실패로 읽는 부류다.
    """
    if f == 'index.html':
        return SITE + '/'
    if f.endswith('/index.html'):
        path = f[:-len('/index.html')]
    else:
        path = f[:-len('.html')]
    return SITE + '/' + quote(path, safe='/')


def _kat():
    if url_for('index.html') != SITE + '/':
        return False, '홈 주소를 못 만듦'
    if url_for('team-meang/index.html') != SITE + '/team-meang':
        return False, '하위 폴더 주소를 못 만듦'
    if url_for('a.html') != SITE + '/a':
        return False, '.html 을 안 뗌'
    if '%' not in url_for('research-직진성-외부표준.html'):
        return False, '한글 주소를 퍼센트 인코딩 안 함 (urllib 이 죽는다)'
    if _norm(b'x<!--stamp:v1-->A<!--/stamp:v1-->y') != b'x y':
        return False, '도장을 못 걷어냄'
    # ★ 실패 갈래를 «가르는가». 넷이 같은 얼굴로 나오면 다음 사람이 또
    #   도구의 실패를 대상의 실패로 읽는다.
    if _fetch('http://127.0.0.1:9/nowhere', timeout=5)[0] != '못감':
        return False, '연결 실패를 «못감» 으로 안 부름'
    # 인코딩 안 된 주소가 여기까지 오면 «내 도구가 틀린 것» 이다.
    # 「그 페이지가 없다」 로 읽으면 안 된다. 오늘 실제로 그럴 뻔했다.
    if _fetch('http://127.0.0.1:9/한글', timeout=5)[0] != '내결함':
        return False, '인코딩 안 된 주소를 «내결함» 으로 안 부름'
    if _fetch('그건주소가아니다', timeout=5)[0] != '내결함':
        return False, '주소가 아닌 것을 «내결함» 으로 안 부름'
    return True, ''


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', default=os.path.join(
        os.path.expanduser('~'), 'Desktop', 'jay', '인공지능사관학교',
        'foothold-site'))
    ap.add_argument('--commit', default='HEAD')
    ap.add_argument('--wait', type=int, default=300, help='최대 대기 초')
    a = ap.parse_args(argv)

    ok, why = _kat()
    if not ok:
        print('[!] 자기시험 실패: %s' % why)
        return 1

    files = changed_pages(a.site, a.commit)
    if files is None:
        print('[!] %s 에서 커밋을 못 읽었습니다' % a.site)
        return 1
    if not files:
        print('그 커밋이 바꾼 HTML 이 없습니다. 확인할 것이 없습니다')
        return 0
    print('%s 가 바꾼 페이지 %d장' % (a.commit, len(files)))

    local = {}
    for f in files:
        local[f] = hashlib.sha256(
            _norm(io.open(os.path.join(a.site, f), 'rb').read())).hexdigest()

    deadline = time.time() + a.wait
    pending = list(files)
    bad = {}
    round_no = 0
    while pending and time.time() < deadline:
        round_no += 1
        still = []
        for f in pending:
            kind, st, body = _fetch(url_for(f))
            if kind == '내결함':
                print('  [!] 이 도구가 %s 의 주소를 못 다뤘습니다: %s'
                      % (f, body.decode('utf-8', 'replace')[:120]))
                print('      대상의 결함이 아닙니다. 도구를 고쳐야 합니다.')
                return 1
            if kind != 'ok' or st != 200:
                still.append(f)
                bad[f] = {'없음': '라이브에 없음 (404)',
                          '못감': '거기까지 못 감 (망·시간초과)',
                          '답이다름': 'HTTP %s' % st}.get(kind, 'HTTP %s' % st)
                continue
            if hashlib.sha256(_norm(body)).hexdigest() != local[f]:
                still.append(f)
                bad[f] = '라이브가 아직 옛 판'
                continue
            bad.pop(f, None)
        pending = still
        if pending:
            print('  %d회차 · 아직 %d장 (%s)'
                  % (round_no, len(pending), pending[0]))
            time.sleep(15)

    for f in files:
        mark = '올라감' if f not in pending else ('★ ' + bad.get(f, '?'))
        print('  %-52s %s' % (url_for(f).replace(SITE, ''), mark))

    if pending:
        print('[!] %d장이 %d초 안에 안 올라갔습니다' % (len(pending), a.wait))
        return 1

    # ③ 열리는 것과 «찾히는 것» 은 다르다.
    kind, st, raw = _fetch(SITE + '/assets/search-index.json', timeout=60)
    if kind != 'ok' or st != 200:
        print('[!] 색인을 못 받았습니다 · %s (HTTP %s)' % (kind, st))
        return 1
    idx = json.loads(raw.decode('utf-8'))
    have = {e['p'] for e in idx}
    missing = [f for f in files if f not in have]
    print('  라이브 색인 %d레코드 · 이번 페이지 %d장 중 색인에 있는 것 %d장'
          % (len(idx), len(files), len(files) - len(missing)))
    if missing:
        print('[!] 열리지만 검색에는 없습니다: %s' % ' · '.join(missing[:6]))
        return 1
    print('전부 올라갔고 전부 검색됩니다')
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
