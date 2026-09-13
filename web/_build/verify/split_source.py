# -*- coding: utf-8 -*-
"""손 관리 페이지에서 «주입물» 을 걷어내 순수 소스를 만든다 (mai-os#24).

  왜
    brief · index · setup 은 손으로 쓴 원본인데 빌드가 그 파일 «안에» 주입한다.
    그래서 소스와 생성물이 한 파일에 섞였고, 주입물이 쌓여도 아무도 못 봤다
    (빈 CSS 껍데기 77개 · 옛 부트 스크립트 27개).

    소스를 `_src/<이름>.base.html` 로 떼면
      · 손으로 고칠 자리가 하나로 분명해진다
      · 빌드는 매번 소스에서 새로 만들므로 주입물이 쌓일 수 없다
      · 「소스만으로 결과가 재현되는가」를 물을 수 있다

  ★ 이 스크립트는 «한 번만» 도는 이행 도구다. 빌드에 넣지 않는다.
"""
import io
import os
import re
import sys

# 걷어낼 주입물. (이름, 정규식) · 지운 뒤 빌드가 다시 넣는다
DROP = [
    ('전역바',       re.compile(r'<!--gnav:v1-->[\s\S]*?<!--/gnav:v1-->\s*')),
    ('ia-css',      re.compile(r'<style id="ia-css">[\s\S]*?</style>\s*')),
    ('stamp-css',   re.compile(r'<style id="stamp-css">[\s\S]*?</style>\s*')),
    ('판 띠',        re.compile(r'<div class="bstamp"[\s\S]*?</div>\s*')),
    # ★ 2026-09-02. 이 규칙이 본문을 먹을 뻔했다. 볼트의 <!--dark:v1--> 은
    #   짝이 없는 고아라 «다음 </script>» 가 페이지 아래 남의 스크립트였다.
    #   newbadge 가 brief 본문 18,000자를 날린 것과 같은 부류다.
    #   짝이 있으면 짝까지 · 없으면 마커만 뗀다. 순서가 중요하다.
    ('다크 토글(짝)',  re.compile(r'<!--dark:v\d+-->[\s\S]*?<!--/dark:v\d+-->\s*')),
    ('다크 토글(고아)', re.compile(r'<!--dark:v\d+-->\s*')),
    ('라이트 토큰',   re.compile(r'<style>\s*html\[data-theme="light"\]\{[\s\S]*?</style>\s*')),
    ('NEW 배지 CSS', re.compile(r'<style>\s*span\.fh-new\{[\s\S]*?</style>\s*')),
    ('방문 기록',     re.compile(r"<script>\s*\(function\(\)\{\s*var W=7\*86400000[\s\S]*?</script>\s*")),
    ('테마 부트',     re.compile(r'<script(?: id="fh-theme-boot")?>try\{var _t=localStorage'
                                r'[\s\S]*?</script>\s*')),
    ('배지 표식',     re.compile(r'<!--newbadge:v\d+-->\s*')),
    ('빈 껍데기',     re.compile(r'<style[^>]*>\s*(?:@[a-zA-Z-]+[^{};]*\{\s*\}\s*)*\s*</style>\s*')),
]


def strip(t):
    """(순수 소스, 걷어낸 내역)."""
    log = []
    for name, pat in DROP:
        t, n = pat.subn('', t)
        if n:
            log.append((name, n))
    # 주입물을 뺀 자리에 남은 빈 줄을 정리한다
    t = re.sub(r'\n[ \t]*(?:\n[ \t]*){2,}', '\n\n', t)
    return t, log


def _kat():
    """★ 답을 아는 입력. 지울 것만 지우는지 본다."""
    keep = '<style>.mine{color:red}</style><p>본문</p>'
    cases = [
        ('<!--gnav:v1--><nav>x</nav><!--/gnav:v1-->' + keep, keep),
        ('<style id="ia-css">.a{b:c}</style>' + keep, keep),
        ('<style>@media print{}</style>' + keep, keep),
        ('<script id="fh-theme-boot">try{var _t=localStorage.x}catch(e){}</script>' + keep, keep),
        ('<script>try{var _t=localStorage.x}catch(e){}</script>' + keep, keep),
        ('<style>html[data-theme="light"]{--a:1}</style>' + keep, keep),
        ('<style>span.fh-new{display:block}</style>' + keep, keep),
        ('<!--newbadge:v7-->' + keep, keep),
        # 짝이 있는 다크 블록은 통째로
        ('<!--dark:v1--><style>#themeBtn{a:b}</style><script>x</script>'
         '<!--/dark:v1-->' + keep, keep),
        # 짝이 없으면 마커만. 뒤따르는 남의 스크립트를 먹으면 안 된다
        ('<!--dark:v1--><p>본문</p><script>남의것</script>' + keep,
         '<p>본문</p><script>남의것</script>' + keep),
        (keep, keep),                                    # 건드릴 게 없으면 그대로
    ]
    for src, want in cases:
        got, _ = strip(src)
        if got.strip() != want.strip():
            return False, '%r -> %r (기대 %r)' % (src[:50], got[:60], want[:40])
    # 손 CSS 를 지우면 안 된다
    got, _ = strip('<style>:root{--paper:#fff}</style>')
    if ':root' not in got:
        return False, '손 CSS 를 지웠다'
    return True, ''


def main(vault, pages):
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    src_dir = os.path.join(vault, '_src')
    os.makedirs(src_dir, exist_ok=True)
    for page in pages:
        p = os.path.join(vault, page)
        t = io.open(p, encoding='utf-8').read()
        out, log = strip(t)
        base = os.path.join(src_dir, page[:-5] + '.base.html')
        io.open(base, 'w', encoding='utf-8', newline='\n').write(out)
        print('  %s -> _src/%s  %d자 -> %d자' % (page, os.path.basename(base), len(t), len(out)))
        for name, n in log:
            print('       걷어냄 %-12s %d곳' % (name, n))
        # 소스에 주입 흔적이 남았는지 스스로 주장한다 (원칙 2)
        left = [nm for nm, pat in DROP if pat.search(out)]
        if left:
            print('  [!] 아직 남았습니다: %s' % ' · '.join(left))
            return False
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    v = sys.argv[1]
    sys.exit(0 if main(v, sys.argv[2:]) else 1)
