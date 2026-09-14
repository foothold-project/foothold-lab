# -*- coding: utf-8 -*-
"""도해의 선 굵기를 «한 벌» 로 맞춘다.

분류: 운영 · 작성: 오흥재 · 2026-09-14 · 상태: 확정
근거: 실측 (도해 15장의 stroke-width 전수 · 적용 전후 개수 대조)

## 왜 있나

2026-09-13 에 팀장이 프로토콜 페이지를 보고 「border 다름」을 지적했다.
재어 보니 도해 15장에 선 굵기가 **11가지** 쓰이고 있었다.

    1 · 1.5 · 1.6 · 1.7 · 1.8 · 2 · 2.2 · 2.6 · 2.8 · 3.4 · 6

같은 역할(가는 선 · 보통 · 강조)인데 도해마다 값이 다르다. `curves` 계열은
1.7 / 2.2 / 2.8 을 쓰고 `fig01` 계열은 1.8 / 2.6 / 3.4 를 쓴다. 나란히 놓이면
테두리 굵기가 제각각으로 보인다. 0.1 차이(1.5 와 1.6)는 눈으로 구분도 안 되니
«뜻이 있는 차이» 가 아니라 만든 시점이 다른 흔적이다.

## 무엇만 바꾸나

**역할이 같은 두 벌을 하나로 모으는 것만 한다.** 굵기를 새로 디자인하지 않는다.

    1.2 · 1.4 · 1.5 · 1.7 · 1.8  ->  1.6    가는 선
    2.2 · 2.4                    ->  2      보통
    2.6 · 3 · 3.2 · 3.4          ->  2.8    강조

`1` (격자·눈금) 과 `6` (fig06 의 굵은 띠) 은 건드리지 않는다.

## 자리가 셋이다 (이걸 찾는 데 세 번 걸렸다)

    deliverables/plan/assets/   ← 제안서 도해의 «원본»
    web/assets/                 ← 빌드가 위에서 복사해 온 것
    docs/assets/visual/         ← 연구 문서 도해의 원본

빌드가 첫째에서 둘째로 복사하므로 **둘째만 고치면 다음 빌드에 되돌아간다.**
실제로 두 번 그랬다. 관문이 두 번 다 세웠고 그제야 첫째를 찾았다.

    python tools/svg_strokes.py --write        # 세 자리를 전부 돈다


★ 그리고 처음엔 `eval-v2*` 만 보고 다섯 가지만 옮기려 했다. 관문이 「한 벌에
없는 굵기가 남았다」고 서서 알았다. 같은 폴더에 `eval-harness-*` 계열이 더
있고 거기 1.2 · 1.4 · 2.4 · 3 · 3.2 가 쓰인다. **고정 목록으로 훑으면 나중에
생긴 것을 통째로 건너뛴다.** 그래서 이 도구는 폴더를 전수로 돈다.

## 어떻게 확인하나

바꾼 뒤 **개수가 보존되는지** 센다. 1.7 이 22개였으면 1.8 이 22개 늘어야 한다.
줄거나 늘면 다른 것을 건드린 것이다.
"""
import io
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

# 한 벌은 다섯이다. 실제로 가장 많이 쓰인 값을 대표로 삼았다.
#
#   1      격자 · 눈금 · 보조선      (67개로 최다)
#   1.6    가는 선                  (1.2 33 · 1.6 11 · 1.4 8 · 1.5 2 를 모음)
#   2      보통 선                  (2 35 · 2.2 23 · 2.4 2 를 모음)
#   2.8    강조                     (3.4 24 · 2.8 22 · 3 1 · 3.2 4 를 모음)
#   6      fig06 의 굵은 띠         (한 도해 안에서만 쓰는 특수값)
#
# 1.7·1.8 은 「가는 선」 무리로 내린다. 0.1~0.2 차이는 눈으로 구분이 안 되고
# 도해마다 값이 갈린 흔적일 뿐이다.
MAP = {'1.2': '1.6', '1.4': '1.6', '1.5': '1.6', '1.7': '1.6', '1.8': '1.6',
       '2.2': '2', '2.4': '2',
       '2.6': '2.8', '3': '2.8', '3.2': '2.8', '3.4': '2.8'}
KEEP = {'1', '1.6', '2', '2.8', '6'}
PAT = re.compile(r'stroke-width="([\d.]+)"')


def widths(text):
    return Counter(PAT.findall(text))


def apply(text):
    return PAT.sub(lambda m: 'stroke-width="%s"' % MAP.get(m.group(1), m.group(1)),
                   text)


def _selftest():
    src = ('<line stroke-width="1.7"/><line stroke-width="2.2"/>'
           '<line stroke-width="3.4"/><line stroke-width="1"/>'
           '<line stroke-width="6"/><rect stroke-width="1.8"/>')
    got = widths(apply(src))
    want = Counter({'1.6': 2, '2': 1, '2.8': 1, '1': 1, '6': 1})
    if got != want:
        return False, '%s (기대 %s)' % (dict(got), dict(want))
    # 굵기 말고는 아무것도 안 바뀌어야 한다
    if apply('<text x="1.7">1.7</text>') != '<text x="1.7">1.7</text>':
        return False, '굵기가 아닌 1.7 을 건드렸다'
    return True, '2칸'


def main(root, write):
    ok, why = _selftest()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    # ★ **어디를 도는지 찍는다.** 상대 경로로 부르면 부른 사람이 생각한 곳과
    #   다른 곳을 돌 수 있다. 실제로 그랬다. `'web/assets'` 로 불렀는데 그 셸의
    #   현재 폴더가 달라 엉뚱한 데를 훑고 「17장 손댐」이라 보고했다. 정작
    #   고쳐야 할 넷은 안 건드렸고 나는 «됐다» 고 읽었다 (2026-09-14).
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        print('  [!] 폴더가 없습니다: %s' % root)
        return False
    print('  자기시험 통과 (%s) · 대상 %s' % (why, root))

    before, after, touched = Counter(), Counter(), 0
    for dirpath, _d, files in os.walk(root):
        for f in sorted(files):
            if not f.endswith('.svg'):
                continue
            p = os.path.join(dirpath, f)
            t = io.open(p, encoding='utf-8').read()
            b = widths(t)
            if not (set(b) & set(MAP)):
                before.update(b)
                after.update(b)
                continue
            n = apply(t)
            before.update(b)
            after.update(widths(n))
            touched += 1
            if write:
                io.open(p, 'w', encoding='utf-8', newline='\n').write(n)

    moved = sum(before[k] for k in MAP)
    gained = sum(after[v] - before[v] for v in set(MAP.values()))
    print('  도해 %d장 손댐 · 옮긴 선 %d개 · 받은 쪽 증가 %d개'
          % (touched, moved, gained))
    if moved != gained:
        print('  [!] 개수가 안 맞습니다. 다른 것을 건드렸습니다')
        return False
    if sum(before.values()) != sum(after.values()):
        print('  [!] 전체 선 수가 달라졌습니다')
        return False
    left = sorted(set(after) - KEEP, key=float)
    print('  남은 굵기 %d가지: %s'
          % (len(after), ' · '.join(sorted(after, key=float))))
    if left:
        print('  [!] 한 벌에 없는 굵기가 남았습니다: %s' % left)
        return False
    if not write:
        print('  (--write 를 주면 씁니다)')
    return True


if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__))
    lab = os.path.dirname(here)
    # 세 자리를 전부 돈다. 하나만 돌면 다음 빌드에 되돌아간다.
    roots = [os.path.join(lab, 'deliverables', 'plan', 'assets'),
             os.path.join(lab, 'web', 'assets'),
             os.path.join(lab, 'docs', 'assets')]
    ok = True
    for r in roots:
        if os.path.isdir(r):
            ok = main(r, '--write' in sys.argv) and ok
    sys.exit(0 if ok else 1)
