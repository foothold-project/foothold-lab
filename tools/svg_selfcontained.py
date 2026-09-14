# -*- coding: utf-8 -*-
"""도해 SVG 를 «혼자서도 제 색이 나오게» 만든다.

**왜 필요한가.** `<img src="x.svg">` 로 부른 SVG 는 **격리된 문서**다. 페이지의
`--ink` 같은 CSS 변수가 거기까지 안 닿는다. 그러면 `fill="var(--accent)"` 가
풀리지 않아 **초기값인 검정**으로 떨어진다.

실측 (2026-09-13 · 라이브 `research-20260911-eval-protocol-v2`):

    도해 열세 장이 전부 검정
    `var(--accent)` 172곳 · `--rule` 36 · `--rule-2` 31 · `--bad` 30
    게다가 `viewBox` 만 있고 width·height 가 없어 **높이 2px** 로 납작
    파일은 200 으로 멀쩡히 열린다. 그래서 더 안 보였다.

**본문에 넣는 길도 해 봤다.** 색은 살지만 정본 한 장이 167 KB 에서 869 KB 가
되고, 검색 색인에 도해 안 좌표와 글자가 들어가 검색이 흐려지고, 빌드가 10분을
넘겼다. 그래서 **파일 자체를 자립시킨다.**

`<img>` 안의 SVG 도 **자기 `<style>` 은 읽는다.** 거기에 팔레트를 넣으면 된다.
`prefers-color-scheme` 도 듣는다.

**한 가지 한계는 적어 둔다.** 이 방식은 **운영체제 테마**를 따른다. 사이트의
테마 단추로 바꾼 것은 `<img>` 안까지 못 간다. 운영체제가 밝은데 사이트만
어둡게 해 둔 사람은 도해가 밝게 보인다. 검정으로 안 보이는 것보다는 낫고,
이것이 `<img>` 로 부르는 SVG 의 구조적 한계다.
"""
import argparse
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)
DEFAULT_DIR = os.path.join(LAB, 'web', 'assets', 'visual')

MARK = '<!--selfcontained:v1-->'

# `tools/md2site.py` · `web/_build/docs_pages.py` 와 **같은 값**이어야 한다.
# 같은 그림이 두 경로로 나가는데 색이 다르면 어느 쪽이 맞는지 알 수 없다.
LIGHT = {
    '--ink': '#161c26', '--ink-2': '#4a5566', '--ink-3': '#7c8798',
    '--paper': '#f6f5f1', '--paper-2': '#eeece6', '--card': '#ffffff',
    '--rule': '#d9d6cd', '--rule-2': '#efede6', '--dim': '#0e7a6e',
    '--accent': '#0e7a6e', '--accent-soft': '#e0f0ed',
    '--ok': '#0e7a6e', '--ok-soft': '#e0f0ed',
    '--warn': '#a86a08', '--warn-soft': '#fbf0dc',
    '--bad': '#a3342a', '--bad-soft': '#fbe9e7',
    # 2026-09-14. 손그림 도해 4장이 쓰던 색. 값은 사이트 CSS 에서 가져왔다.
    '--dim-ink': '#0b6459', '--ink-soft': '#adb5c1', '--deep': '#112222',
}
DARK = {
    '--ink': '#e9e7e1', '--ink-2': '#adb5c1', '--ink-3': '#7d8693',
    '--paper': '#12161d', '--paper-2': '#191e27', '--card': '#181d26',
    '--rule': '#2b323d', '--rule-2': '#232a35', '--dim': '#3ec7b4',
    '--accent': '#3ec7b4', '--accent-soft': '#11302c',
    '--ok': '#3ec7b4', '--ok-soft': '#11302c',
    '--warn': '#dc9a30', '--warn-soft': '#332710',
    '--bad': '#e56d5e', '--bad-soft': '#331c19',
    '--dim-ink': '#3ec7b4', '--ink-soft': '#4a5566', '--deep': '#0c1117',
}


def _decl(d):
    return ''.join('%s:%s;' % (k, v) for k, v in sorted(d.items()))


def style_block():
    return ('<style>\n'
            ':root{%s}\n'
            '@media(prefers-color-scheme:dark){:root{%s}}\n'
            '</style>\n' % (_decl(LIGHT), _decl(DARK)))


def used_vars(t):
    return set(re.findall(r'var\(\s*(--[a-z0-9-]+)', t, re.I))


def fix(t):
    """반환: (새 내용, 무엇을 했는지). 바꿀 것이 없으면 (None, 사유)."""
    if MARK in t:
        return None, '이미 자립'
    used = used_vars(t)
    if not used:
        return None, '토큰 안 씀'

    unknown = sorted(v for v in used if v not in LIGHT)
    if unknown:
        # 모르는 토큰을 그냥 두면 «그 색만» 검정이 된다. 조용히 넘기지 않는다.
        return None, '모르는 토큰 %s' % ' '.join(unknown)

    m = re.search(r'<svg\b[^>]*>', t)
    if not m:
        return None, 'svg 태그 없음'
    tag = m.group(0)

    # 1. 크기를 준다. viewBox 만 있으면 <img> 안에서 납작해진다.
    if ' width=' not in tag:
        vb = re.search(r'viewBox="[\d.\-]+\s+[\d.\-]+\s+([\d.]+)\s+([\d.]+)"', tag)
        if not vb:
            return None, 'viewBox 없음'
        new_tag = tag[:-1] + ' width="%s" height="%s">' % (vb.group(1), vb.group(2))
        t = t.replace(tag, new_tag, 1)
        tag = new_tag

    # 2. 팔레트를 안에 넣는다.
    t = t.replace(tag, tag + '\n' + MARK + '\n' + style_block(), 1)
    return t, '크기와 팔레트 넣음'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=DEFAULT_DIR)
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()

    if not os.path.isdir(a.dir):
        raise SystemExit('  [!] 폴더가 없습니다: %s' % a.dir)

    done, skip, stuck = [], [], []
    for f in sorted(os.listdir(a.dir)):
        if not f.lower().endswith('.svg'):
            continue
        p = os.path.join(a.dir, f)
        t = io.open(p, encoding='utf-8').read()
        new, why = fix(t)
        if new is None:
            (stuck if why.startswith('모르는') or why.endswith('없음')
             else skip).append((f, why))
            continue
        if a.write:
            io.open(p, 'w', encoding='utf-8', newline='\n').write(new)
        done.append(f)

    print('  자립시킴 %d · 건너뜀 %d · 못한 것 %d' % (len(done), len(skip), len(stuck)))
    for f, why in stuck:
        print('      [!] %s  %s' % (f, why))

    # 조용한 실패를 막는다. 토큰을 쓰는 파일이 있는데 하나도 못 고쳤으면
    # 그것은 «할 일이 없었다» 가 아니라 «안 된 것» 이다.
    tokened = sum(1 for f in os.listdir(a.dir) if f.lower().endswith('.svg')
                  and used_vars(io.open(os.path.join(a.dir, f),
                                        encoding='utf-8').read()))
    if tokened and not done and not any(w == '이미 자립' for _f, w in skip):
        raise SystemExit('  [!] 토큰을 쓰는 SVG 가 %d개인데 하나도 못 고쳤습니다' % tokened)
    if stuck:
        raise SystemExit(1)
    if not a.write:
        print('  (--write 를 주면 씁니다)')


if __name__ == '__main__':
    main()
