# -*- coding: utf-8 -*-
"""자산(assets) 주소에 내용 해시를 붙인다. 안 붙이면 고쳐도 아무도 못 본다.

★ 2026-08-27 팀장 지적: "도식화 그림은 왜 안 바뀌었나?"

  파일은 제대로 바뀌어 있었다. 파인튜닝 계획 도식은 5갈래로 다시 그려
  배포까지 나갔고, 배포본을 열어 세어 보면 갈래가 다섯이다.
  **그런데 화면에는 옛 그림이 나왔다.**

  원인은 `vercel.json` 이다.

      "source": "/assets/(.*)"
      "Cache-Control": "public, max-age=31536000, immutable"

  `immutable` 은 브라우저에게 **「이 주소의 내용은 절대 안 바뀐다」**고 하는
  약속이다. 그 약속을 받은 브라우저는 새로고침을 해도 다시 안 물어본다.
  그런데 우리는 **같은 이름 위에 계속 덮어쓴다.** 약속을 우리가 어기고 있었다.

  그래서 지금까지 «자산을 고친 모든 작업»은 새로 온 사람에게만 보였다.
  이미 한 번 본 사람(= 팀원 전부)에게는 옛 것이 1년간 남는다.

해법
  파일 이름은 그대로 두고 **주소 뒤에 내용 해시를 붙인다.**
      assets/visual/finetune-plan-flow.svg?v=028f81ea
  내용이 바뀌면 해시가 바뀌고, 해시가 바뀌면 **주소가 다른 파일**이 된다.
  브라우저는 처음 보는 주소라 새로 받는다. `immutable` 약속도 그대로 지켜진다
  (그 주소의 내용은 정말로 안 바뀌니까).

  캐시 규칙을 푸는 방법도 있지만 그건 폰트·PDF 뷰어처럼 **진짜 안 바뀌는
  것들까지** 매번 다시 받게 만든다. 주소를 바꾸는 쪽이 옳다.
"""
import hashlib
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# ★ 주소는 «주소 자리»에서만 고친다. 본문 글자는 건드리지 않는다.
#
#   처음에는 「assets/ 로 시작하고 확장자로 끝나는 문자열」을 통째로 찾았다.
#   두 가지가 바로 걸렸다.
#     1) `<pre>` 안의 설명글 `docs/assets/video/eval_lv0/3/6/9.mp4` 를
#        진짜 파일로 착각했다. 그건 lv0·lv3·lv6·lv9 를 줄여 쓴 «말»이다.
#     2) `search-index.json` 을 `search-index.js` 로 잘랐다.
#        확장자 후보를 `js|mjs|json` 순으로 적어서 짧은 `js` 가 먼저 맞았다.
#        (정규식 대안은 «가장 긴 것»이 아니라 «먼저 적은 것»이 이긴다)
#   둘 다 「주소 자리에서만 본다」로 한 번에 사라진다. 개별 예외가 아니라
#   자리로 막는 것이 옳다 (커널 2-2: 실수는 부류로 막는다).
_SLOT = re.compile(r'(?P<pre>(?:href|src)="|url\()'
                   r'(?P<path>(?:\.\./)*assets/[^"\')>]+?)'
                   r'(?:\?v=[0-9a-f]{8})?'
                   r'(?P<post>"|\))')

# 해시를 붙이지 않는 것. 코드가 이름으로 찾아 쓰는 파일들이라
# 주소를 바꾸면 오히려 깨진다.
SKIP = ('assets/secure/',        # 자료실이 manifest 를 보고 직접 fetch 한다
        'assets/search-index.json',   # 검색 스크립트가 고정 이름으로 부른다
        'assets/vendor/')        # pdf.js 워커가 제 짝을 상대경로로 찾는다


def _sha(p):
    return hashlib.sha256(io.open(p, 'rb').read()).hexdigest()[:8]


def _paths(t):
    return [m.group('path') for m in _SLOT.finditer(t)]


def _kat(site):
    """★ 답을 아는 입력으로 먼저 시험한다.

    ★ 아래 넷째·다섯째는 «실제로 나를 문 것»이다. 처음 판은 둘 다 통과시켰고
      빌드가 「가리키는데 파일이 없음」으로 잡아 줬다. 그 두 입력을 여기 박는다.
    """
    one = _paths('<img src="assets/visual/a.svg">')
    if one != ['assets/visual/a.svg']:
        return False, '평범한 자산 주소를 못 찾음: %r' % one

    again = _paths('<img src="assets/visual/a.svg?v=deadbeef">')
    if again != ['assets/visual/a.svg']:
        return False, '이미 붙은 해시를 못 떼어냄: %r' % again

    if _paths('<a href="setup.html">'):
        return False, '자산이 아닌 주소를 자산으로 봄'

    if _paths('url(../assets/brand/x.png)') != ['../assets/brand/x.png']:
        return False, '상위 경로(../) 자산을 못 찾음'

    # 4) 확장자 대안 순서 사고: json 을 js 로 자르지 않는가
    j = _paths('<script src="assets/search-index.json">')
    if j != ['assets/search-index.json']:
        return False, 'json 을 %r 로 잘랐다 (대안 순서 문제)' % j

    # 5) 본문 글자 사고: <pre> 안의 설명글을 주소로 보지 않는가
    prose = '<pre>곡선 그림 3종 docs/assets/video/eval_lv0/3/6/9.mp4 난이도별</pre>'
    if _paths(prose):
        return False, '본문 글자를 주소로 봄: %r' % _paths(prose)

    return True, ''


def main(site):
    ok, why = _kat(site)
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False

    cache = {}
    missing = set()

    def _fix(m):
        ref = m.group('path')
        bare = re.sub(r'^(\.\./)+', '', ref)
        keep = m.group('pre') + ref + m.group('post')
        if any(bare.startswith(x) for x in SKIP):
            return keep                         # 해시 없이 그대로 (기존 ?v= 는 뗀다)
        p = os.path.join(site, bare.replace('/', os.sep))
        if p not in cache:
            cache[p] = _sha(p) if os.path.isfile(p) else None
        h = cache[p]
        if h is None:
            missing.add(bare)
            return keep
        return '%s%s?v=%s%s' % (m.group('pre'), ref, h, m.group('post'))

    n_pages, n_refs = 0, 0
    for dirpath, dirnames, names in os.walk(site):
        dirnames[:] = [d for d in dirnames if d not in ('assets', '_build', '.git')]
        for f in sorted(names):
            if not f.endswith('.html'):
                continue
            p = os.path.join(dirpath, f)
            t = io.open(p, encoding='utf-8', newline=None).read()
            new = _SLOT.sub(_fix, t)
            n_refs += len(_paths(t))
            if new != t:
                io.open(p, 'w', encoding='utf-8', newline='\n').write(new)
            n_pages += 1

    stamped = sum(1 for v in cache.values() if v)
    print('  자가검증 통과 · 페이지 %d개 · 자산 주소 %d곳 · 파일 %d종에 해시'
          % (n_pages, n_refs, stamped))

    # ★ 조용한 실패 방지: 가리키는데 없는 자산은 알린다.
    #   해시를 못 붙이는 것보다 «파일이 없다»가 더 큰 문제다.
    if missing:
        for b in sorted(missing)[:10]:
            print('  ★ 가리키는데 파일이 없음: %s' % b)
        print('  없는 자산 %d종' % len(missing))
        return False
    if stamped == 0:
        print('  [!] 한 곳도 해시를 못 붙였습니다. 자산을 못 찾고 있습니다.')
        return False
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.path.insert(0, HERE)
    import linkcheck
    sys.exit(0 if main(linkcheck._site()) else 1)
