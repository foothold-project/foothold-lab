# -*- coding: utf-8 -*-
"""어느 페이지에도 안 걸린 도해를 잡는다.

> 분류: 운영
> 작성: 오흥재 (Claude 세션) · 2026-09-14 23:10
> 근거: 실측 (배포본 141장을 훑어 참조를 셈)
> 요지: 새 고아가 생기면 배포를 세운다. 오늘의 7장은 명부에 유예로 담는다
> 상태: 확정

## 왜

도해를 만들어 두고 페이지에서 안 쓰면 아무 오류도 안 난다. 그래서 계속 쌓인다.
2026-09-14 에 재니 7장이 그랬다. 둘은 내가 다른 자리로 옮긴 흔적이다.

site 세션 제안: 「목록으로 두지 말고 관문으로」. 목록은 늘어나기만 하고 아무도
안 읽는다. 명부(`orphan_figs.txt`)에 오늘의 7장을 적고, **새로 생기면 세운다.**
명부가 줄어드는 것은 통과다. 그 줄 수가 남은 일의 크기다.

## 안 세는 것

테마 짝(`x.dark.svg`)은 HTML 에 안 나온다. 토글이 브라우저에서 갈아끼우기
때문이다. 밝은 쪽이 걸려 있으면 짝도 걸린 것으로 본다.

## 관문 자신을 먼저 시험한다

`_selftest()` 가 가짜 사이트를 만들어, 걸린 것/안 걸린 것/짝/글자로만 적힌
이름을 구별하는지 본다. 「파일 이름이 글자로 적힌 것을 참조로 세는」 실수를
전에 했다 (다이제스트 재료 때문에 고아가 0장으로 나왔다).
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, 'orphan_figs.txt')

# `src`/`href` 속성 «안» 의 것만 센다. 본문에 글자로 적힌 이름은 참조가 아니다.
_REF = re.compile(r'(?:src|href)="[^"?]*?([\w.-]+\.svg)')
_STRIP = re.compile(r'(?s)<style\b.*?</style>|<script\b.*?</script>')


def referenced(site):
    ref = set()
    for root, _dirs, files in os.walk(site):
        if os.sep + '.' in root:
            continue
        for f in files:
            if not f.endswith('.html'):
                continue
            t = _STRIP.sub(' ', io.open(os.path.join(root, f),
                                        encoding='utf-8', errors='ignore').read())
            ref |= set(_REF.findall(t))
    # 밝은 쪽이 걸렸으면 테마 짝도 걸린 것이다
    ref |= {f[:-4] + '.dark.svg' for f in set(ref)
            if f.endswith('.svg') and not f.endswith('.dark.svg')}
    return ref


def orphans(site, visual_rel=os.path.join('assets', 'visual')):
    vis = os.path.join(site, visual_rel)
    if not os.path.isdir(vis):
        return None
    ref = referenced(site)
    return sorted(f for f in os.listdir(vis)
                  if f.endswith('.svg') and not f.endswith('.dark.svg')
                  and f not in ref)


def allowed():
    if not os.path.isfile(LEDGER):
        return set()
    return {l.strip() for l in io.open(LEDGER, encoding='utf-8')
            if l.strip() and not l.startswith('#')}


def _selftest(tmp=None):
    import shutil
    import tempfile
    root = tmp or tempfile.mkdtemp(prefix='orphan-')
    vis = os.path.join(root, 'assets', 'visual')
    os.makedirs(vis, exist_ok=True)
    try:
        for n in ('used.svg', 'used.dark.svg', 'lonely.svg',
                  'only-as-text.svg'):
            io.open(os.path.join(vis, n), 'w', encoding='utf-8').write('<svg/>')
        io.open(os.path.join(root, 'p.html'), 'w', encoding='utf-8').write(
            '<img src="assets/visual/used.svg?v=1">'
            '<p>only-as-text.svg 라는 파일이 있습니다</p>'
            '<style>.x{background:url(lonely.svg)}</style>')
        got = orphans(root)
        want = ['lonely.svg', 'only-as-text.svg']
        bad = []
        if got != want:
            bad.append('기대 %s · 결과 %s' % (want, got))
        # 짝이 고아로 안 잡히는지
        if 'used.dark.svg' in (got or []):
            bad.append('테마 짝을 고아로 셌다')
        if bad:
            print('  [!] 자기시험 실패: %s' % ' · '.join(bad))
            return False
        print('  자기시험 3/3 통과 (짝 제외 · 글자로만 적힌 이름 구별 · CSS url 제외)')
        return True
    finally:
        if not tmp:
            shutil.rmtree(root, ignore_errors=True)


def check(site):
    got = orphans(site)
    if got is None:
        print('  [!] 도해 폴더가 없다')
        return False
    ok_list = allowed()
    new = [f for f in got if f not in ok_list]
    gone = sorted(ok_list - set(got))
    print('  고아 %d장 · 명부 %d장 · 명부에 없는 새 고아 %d장'
          % (len(got), len(ok_list), len(new)))
    if gone:
        print('     명부에서 지워도 되는 것 %d장: %s'
              % (len(gone), ', '.join(gone[:5])))
    if new:
        print('     [X] 새로 생긴 고아: %s' % ', '.join(new))
        print('         쓰거나 지우거나, 까닭을 적고 tools/orphan_figs.txt 에 넣습니다')
    return not new


if __name__ == '__main__':
    site = (sys.argv[1] if len(sys.argv) > 1 else
            os.path.join(HERE, '..', '..', 'foothold-site'))
    if not _selftest():
        raise SystemExit(1)
    raise SystemExit(0 if check(os.path.abspath(site)) else 1)
