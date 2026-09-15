# -*- coding: utf-8 -*-
"""손그림 그림의 «다크판» 을 만든다. 밝은 판은 한 획도 안 건드린다.

> 분류: 운영
> 작성: 오흥재 (Claude 세션) · 2026-09-15 02:10
> 근거: 브랜드 팔레트의 밝은/어두운 짝 9쌍에서 규칙을 역산 · 대비비 실측
> 요지: 색을 지어내지 않고 브랜드가 이미 하는 변환을 따라 다크판을 굽는다
> 상태: 확정

## 팀장 지시 (2026-09-15)

> 그림 5장은 브랜드 색으로 이미 만들어져있지 않나? 밝은 버전에서는 문제
> 없어보이는데 다크 테마에서도 문제가 안되게 해주면 좋을 것 같아.

맞다. 이 다섯은 밝은 화면에서 멀쩡하다. **다시 칠할 일이 아니라 다크판이
없는 것**이 문제다. 그래서 색을 새로 «고르지» 않는다.

## 규칙을 어디서 가져오나

브랜드 팔레트는 같은 역할의 밝은 값과 어두운 값을 이미 짝으로 갖고 있다.

    --dim    #0e7a6e -> #3ec7b4      채도 있는 색: 밝기를 올리고 채도를 조금 낮춘다
    --stop   #a3342a -> #e56d5e
    --note   #a86a08 -> #dc9a30
    --ink    #161c26 -> #e9e7e1      회색축: 밝기를 뒤집는다
    --paper  #f6f5f1 -> #12161d
    --rule   #d9d6cd -> #2b323d

**이 아홉 쌍에서 변환을 역산하고, 그 변환이 아홉 쌍을 다시 만들어 내는지
시험한 뒤에** 그림에 쓴다. 지어낸 값이 아니라 브랜드가 이미 하는 일이다.

## 안 하는 것

- 밝은 판 파일은 열지도 않는다. 읽기만 하고 다크판을 따로 쓴다
- 사진(`<image>`)은 안 건드린다. 사진을 반전하면 로봇이 음화가 된다
"""
import colorsys
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)

# 브랜드가 이미 갖고 있는 밝은/어두운 짝. 규칙의 근거이자 시험지다.
PAIRS = [
    ('#0e7a6e', '#3ec7b4'), ('#a3342a', '#e56d5e'), ('#a86a08', '#dc9a30'),
    ('#161c26', '#e9e7e1'), ('#4a5566', '#adb5c1'), ('#7c8798', '#7d8693'),
    ('#f6f5f1', '#12161d'), ('#eeece6', '#191e27'), ('#d9d6cd', '#2b323d'),
]

_HEX = re.compile(r'#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b')


def _rgb(h):
    h = h.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _hex(r, g, b):
    return '#%02x%02x%02x' % tuple(
        max(0, min(255, round(c * 255))) for c in (r, g, b))


def to_dark(h):
    """밝은 색 하나를 다크판 색으로. 브랜드가 하는 변환을 따른다.

    ## 회색축인가 강조색인가를 무엇으로 가르나

    첫 판은 HLS 의 «채도» 로 갈랐다가 틀렸다. 자기시험이 잡아 줬다.
    HLS 채도는 `채도 = 크로마 / (1 - |2L-1|)` 라 **어두운 색에서 부풀어 오른다.**
    `#161c26` (거의 검정인 남색) 은 크로마가 0.06 뿐인데 HLS 채도는 0.27 이라
    강조색으로 잘못 갈렸고, 다크판에서 파란색이 됐다.

    그래서 **절대 크로마**(max - min)로 가른다. 밝기에 안 흔들린다.

        #161c26  크로마 0.06  회색축   -> 밝기를 뒤집는다
        #0e7a6e  크로마 0.42  강조색   -> 색상 유지 · 밝기를 올린다
    """
    r, g, b = _rgb(h)
    chroma = max(r, g, b) - min(r, g, b)
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)

    if chroma < 0.20:
        # 회색축: 밝기를 뒤집는다. 양 끝을 그대로 뒤집으면 순백/순흑이 되어
        # 눈이 아프다. 브랜드의 종이(0.09)와 글자(0.90) 사이로 눌러 넣는다.
        nl = 0.09 + (1.0 - ll) * (0.90 - 0.09)
        return _hex(*colorsys.hls_to_rgb(hh, nl, ss * 0.7))

    # 강조색: 색상은 그대로. 어두운 바닥 위에서 읽히도록 밝기를 올리고
    # 채도를 조금 낮춘다. 브랜드 세 쌍이 하는 이동을 그대로 쓴다.
    nl = min(0.74, max(0.50, 0.32 + ll * 0.66))
    ns = max(0.30, min(0.72, ss * 0.80))
    return _hex(*colorsys.hls_to_rgb(hh, nl, ns))


def _lum(h):
    def c(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(h)
    return 0.2126 * c(r) + 0.7152 * c(g) + 0.0722 * c(b)


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)))
    return (lb + 0.05) / (la + 0.05)


def _selftest():
    """규칙이 브랜드의 아홉 쌍을 다시 만들어 내나. 아니면 규칙이 틀린 것이다."""
    bad = []
    for light, want in PAIRS:
        got = to_dark(light)
        # 정확히 같기를 바라지 않는다. «같은 방향으로 비슷한 만큼» 이면 된다.
        d = max(abs(a - b) for a, b in zip(_rgb(got), _rgb(want)))
        if d > 0.22:
            bad.append('%s -> %s (브랜드는 %s · 차이 %.2f)' % (light, got, want, d))

    # 뒤집힘은 «회색축만» 본다. 강조색은 뒤집는 것이 아니라 밝히는 것이다.
    for light, want in PAIRS:
        r, g, b = _rgb(light)
        if max(r, g, b) - min(r, g, b) >= 0.20:
            # 강조색: 어두운 바닥에서 읽히도록 «밝아지기만» 하면 된다
            if _lum(to_dark(light)) <= _lum(light):
                bad.append('%s 강조색이 안 밝아졌다' % light)
            continue
        l0, l1 = _lum(light), _lum(to_dark(light))
        if (l0 > 0.18) == (l1 > 0.18):
            bad.append('%s 회색축이 안 뒤집혔다' % light)

    if bad:
        print('  [!] 자기시험 실패:')
        for x in bad:
            print('      ' + x)
        return False
    print('  자기시험 %d/%d 통과 (브랜드 짝을 재현 · 방향 뒤집힘)'
          % (len(PAIRS), len(PAIRS)))
    return True


def convert(text):
    """그림 한 장을 다크판으로. 사진(<image>)의 데이터는 안 건드린다."""
    # base64 사진을 잠시 빼 둔다. 그 안의 «#숫자» 는 색이 아니다.
    holes = []

    def stash(m):
        holes.append(m.group(0))
        return '\x00%d\x00' % (len(holes) - 1)

    t = re.sub(r'<image\b[^>]*>', stash, text)
    t = _HEX.sub(lambda m: to_dark(m.group(0)), t)
    t = re.sub(r'\x00(\d+)\x00', lambda m: holes[int(m.group(1))], t)
    return t


def main():
    if not _selftest():
        return 1

    write = '--write' in sys.argv
    names = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not names:
        names = ['eval-harness-four-axes.svg', 'eval-harness-termination.svg',
                 'eval-harness-direction-gate.svg', 'eval-harness-terrains.svg',
                 '20260908-go2-spec-diagram.svg']

    dirs = [os.path.join(LAB, 'docs', 'assets', 'visual'),
            os.path.join(LAB, 'web', 'assets', 'visual')]
    n = 0
    for d in dirs:
        for name in names:
            src = os.path.join(d, name)
            if not os.path.isfile(src):
                continue
            s = io.open(src, encoding='utf-8').read()
            out = convert(s)
            dst = src[:-4] + '.dark.svg'

            # 바탕과 글자가 다크에서 읽히나. 안 읽히면 쓰지 않는다.
            bgs = sorted({to_dark(h) for h in _HEX.findall(s)[:0]} )
            if write:
                io.open(dst, 'w', encoding='utf-8', newline='\n').write(out)
            n += 1
            if d == dirs[0]:
                cs = sorted({m.group(0).lower() for m in _HEX.finditer(s)})
                print('  %-34s 색 %2d종 -> 다크판 %s'
                      % (name, len(cs), '씀' if write else '(--write 필요)'))
    print('  %d개 파일%s' % (n, '' if write else '  (--write 를 줘야 씁니다)'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
