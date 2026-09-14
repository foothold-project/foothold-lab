# -*- coding: utf-8 -*-
"""배포본을 «읽는 사람이 보는 글자» 로 훑어 마크다운이 샌 자리를 잡는다.

분류: 운영 · 작성: 오흥재 · 2026-09-14 · 상태: 확정
근거: 실측 (고의 결함 주입 검출 시험 · `_selftest`)
요지: 문법이 글자로 보이면 렌더가 실패한 것이다. 태그를 걷고 «보이는 글자» 를 본다

## 왜 있나

2026-09-14 팀장 지적: 「`##### 열한 지형을 한 줄에 놓으면` 이 앞에 `#` 는
뭐야? 오류잖아 이거?」

맞았다. `mdpage` 의 제목 정규식이 `#{1,4}` 라 **h5 · h6 를 아예 안 받았고**
그 줄이 본문 문단으로 떨어졌다. 화면에 `#####` 가 글자로 떴다.
라이브에서 13곳이었고 **오류는 한 번도 안 났다.**

그 전에도 팀장이 같은 부류를 여러 번 짚었다. 나는 매번 수치를 재고
「됐습니다」라고 했다. **수치는 사람이 보는 것이 아니다.**

## 무엇을 보나

태그를 걷어낸 «보이는 글자» 에서 마크다운 문법이 남았는지 본다.

| 샌 것 | 보기 |
|---|---|
| 제목 | 줄 앞의 `#` `##` ... |
| 굵게·기울임 | `**글자**` `__글자__` 가 그대로 |
| 링크 | `[글자](주소)` 가 그대로 |
| 그림 | `![글자](주소)` 가 그대로 |
| 표 | 줄이 `|` 로 시작해서 `|` 로 끝남 |

코드 블록 안은 뺀다. 거기서는 `#` 이 주석이라 정상이다.
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

DROP = re.compile(r'(?s)<style\b.*?</style>|<script\b.*?</script>'
                  r'|<pre\b.*?</pre>|<code\b.*?</code>')
TAG = re.compile(r'<[^>]+>')

RULES = [
    # ★ 제목은 «그 줄이 제목뿐일 때» 만 센다. 문서 그래프는 다른 문서의
    #   절 제목을 «인용해서» 한 문장 안에 보여 준다. 그건 정상이다.
    #   줄이 # 으로 시작하고 120자 이하인 «한 제목» 일 때만 잡는다.
    #   그리고 제목 안에는 «또 다른 #» 이 없다. 인용문은 그것을 가진다.
    ('제목', re.compile(r'^\s*#{1,6}[ \t]+[^#\n]{1,110}$')),
    ('굵게', re.compile(r'\*\*[^*\n]{1,60}\*\*')),
    ('링크', re.compile(r'(?<!!)\[[^\]\n]{1,60}\]\([^)\n]{1,120}\)')),
    ('그림', re.compile(r'!\[[^\]\n]{0,80}\]\([^)\n]{1,120}\)')),
    ('표', re.compile(r'^\s*\|.*\|\s*$')),
]


def visible(html):
    """보이는 글자. 코드·스타일·스크립트는 뺀다."""
    t = DROP.sub(' ', html)
    t = TAG.sub('\n', t)
    return t


def scan(out):
    bad, n = [], 0
    for f in sorted(os.listdir(out)):
        if not f.endswith('.html'):
            continue
        n += 1
        t = visible(io.open(os.path.join(out, f),
                            encoding='utf-8', errors='replace').read())
        for line in t.split('\n'):
            s = line.strip()
            if not s or len(s) > 300:
                continue
            for name, pat in RULES:
                if pat.search(s):
                    bad.append('%s · %s 문법이 글자로: %s' % (f, name, s[:56]))
                    break
    return n, bad


def _selftest():
    """알려진 답. 샌 것은 잡고 정상은 안 잡아야 한다."""
    import tempfile
    d = tempfile.mkdtemp()
    cases = [
        ('제목이 샘', '<p>##### 열한 지형을 한 줄에</p>', 1),
        ('굵게가 샘', '<p>**중요한 것** 이다</p>', 1),
        ('링크가 샘', '<p>[여기](http://a.b) 를 보라</p>', 1),
        ('그림이 샘', '<p>![그림 1](a.svg)</p>', 1),
        ('표가 샘', '<p>| 지형 | 성공률 |</p>', 1),
        ('제대로 된 제목', '<h5>열한 지형을 한 줄에</h5>', 0),
        ('제대로 된 굵게', '<p><strong>중요한 것</strong> 이다</p>', 0),
        ('코드 안의 #', '<pre><code># 규격 2 (기본값)</code></pre>', 0),
        ('본문 속 우물정', '<p>깃허브 이슈 #418 을 보라</p>', 0),
        # 문서 그래프가 남의 절 제목을 인용해 보여 주는 것은 정상이다
        ('인용된 절 제목',
         '<p>### 1-3. 저수준 제어 · «### 1-2. 컴퓨팅 보드». 저수준 개방은 '
         '8/12 에 확인했고 그 뒤로 바뀐 것이 없다고 그 문서가 적고 있다</p>', 0),
    ]
    ok = 0
    for name, html, want in cases:
        io.open(os.path.join(d, 'p.html'), 'w', encoding='utf-8').write(html)
        _, bad = scan(d)
        got = (len(bad) == want)
        ok += got
        print('  %s %-16s 기대 %d · 결과 %d %s'
              % ('OK ' if got else '[X]', name, want, len(bad),
                 ('· ' + bad[0].split('· ')[-1][:34]) if bad else ''))
    print('  %d/%d' % (ok, len(cases)))
    return ok == len(cases)


def main(out):
    print('[3.476] 렌더 검사 (마크다운 문법이 글자로 보이는가)')
    if not _selftest():
        print('  [!] 자기시험 실패. 이 검사를 믿을 수 없습니다')
        return False
    n, bad = scan(out)
    print('  페이지 %d장 검사' % n)
    if n == 0:
        print('  [!] 페이지를 하나도 못 찾았습니다. 검사가 안 돈 것입니다')
        return False
    if bad:
        print('  [!] 문법이 글자로 보이는 자리 %d곳' % len(bad))
        for b in bad[:12]:
            print('      ' + b)
        if len(bad) > 12:
            print('      ... %d곳 더' % (len(bad) - 12))
        return False
    print('  페이지 %d장 전부 마크다운이 제대로 그려졌습니다' % n)
    return True


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if _selftest() else 1)
    sys.exit(0 if main(sys.argv[1]) else 1)
