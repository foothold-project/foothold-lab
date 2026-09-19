# -*- coding: utf-8 -*-
"""학습이 가르친 명령 범위와 평가가 재는 범위를 맞대어 본다 (#443).

> 분류: 운영
> 작성: 오흥재 (Claude 세션) · 2026-09-19 10:40
> 근거: `models/*.env.yaml` 학습 시각 저장본 · 갤러리 매니페스트의 평가 칸 ·
>       #428 의 17항목 감사
> 요지: 평가점이 «전부» 학습 범위 안에 있으면 그 평가는 명령 범위 한계를
>       구조적으로 못 드러낸다. 그 상태로 배포하지 않는다
> 상태: 확정

## 왜 만드나

`#428` 의 사고는 「바꾼 것을 안 적었다」로 끝나지 않는다. 구조는 이렇다.

    학습이 가르친 명령 범위   =  전진 0.5 ~ 1.5 m/s 뿐
    평가가 재는 명령 범위     =  전진 0.5 · 1.0 · 1.5 m/s
    그런데 이 둘을 맞대어 보는 자리가 «어디에도 없었다»

그래서 양쪽 다 자기 기준으로는 멀쩡했다. 954칸을 돌리고도 「정지 · 저속 · 회전 ·
횡이동을 한 번도 안 가르쳤다」가 성적표에 안 나타났다.

**평가가 모델의 한계를 표현할 수 없으면, 그 평가는 한계가 없다고 말하는 것과
같다.**

## 판정

「범위 밖 평가점을 최소 한 점 포함」이 아니라 **「범위 밖이 하나도 없으면
막는다」** 이다. 한 점은 우연히 들어갈 수도 우연히 빠질 수도 있다.

## 「아직 없다」를 조용히 통과시키지 않는다

학습 범위를 못 찾으면 **통과가 아니라 «대조 못 함» 으로 소리 낸다.** 다만 그것
하나로 배포를 막지는 않는다. 막으면 새 평가를 돌리기 전까지 아무것도 못 낸다.
대신 무엇을 해야 읽히는지 화면에 적는다.
"""
import glob
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)

# 학습 쪽에서 볼 축. 오늘은 전진 속도 하나지만 축을 늘릴 수 있게 표로 둔다.
#   이름 · env.yaml 의 키 · 평가 칸에서 그 축에 해당하는 필드
AXES = [('전진 속도', 'lin_vel_x', 'speed_mps')]


def train_range_from_env_yaml(path, key):
    """`models/*.env.yaml` 에서 명령 범위를 읽는다.

    이 파일은 **학습 시각에 직렬화돼 `.pt` 와 함께 저장된** 것이다. 소스 파일과
    달리 「그때 실제로 그 값으로 돌았나」를 말해 준다 (#428 에서 이것으로 확인).

    `!!python/tuple` 꼬리표가 있어 SafeLoader 로 못 읽는다. 값만 필요하므로
    줄을 훑는다. 객체를 만들지 않는다.
    """
    try:
        lines = io.open(path, encoding='utf-8', errors='ignore').read().split('\n')
    except OSError:
        return None
    for i, ln in enumerate(lines):
        if not re.match(r'^\s*%s:\s*(!!python/tuple)?\s*$' % re.escape(key), ln):
            continue
        vals = []
        for j in range(i + 1, min(i + 4, len(lines))):
            m = re.match(r'^\s*-\s*(-?\d+(?:\.\d+)?)\s*$', lines[j])
            if not m:
                break
            vals.append(float(m.group(1)))
        if len(vals) == 2:
            return (vals[0], vals[1])
    return None


def eval_points(manifest, field):
    """평가가 실제로 잰 점들. 매니페스트의 칸에서 뽑는다."""
    out = set()
    for e in (manifest.get('evaluations') or []):
        v = e.get(field)
        if isinstance(v, (int, float)):
            out.add(float(v))
    return sorted(out)


def judge(lo, hi, points):
    """범위 밖 점이 하나도 없으면 막는다."""
    outside = [p for p in points if p < lo or p > hi]
    return outside


def check(train_rng, points, axis):
    if train_rng is None:
        return ('미확인',
                '%s · 학습 범위를 못 읽었습니다. 대조하지 못했습니다' % axis)
    lo, hi = train_rng
    if not points:
        return ('미확인', '%s · 평가점이 없습니다' % axis)
    outside = judge(lo, hi, points)
    if outside:
        return ('통과',
                '%s · 학습 %.2f ~ %.2f · 평가 %s · 범위 밖 %s'
                % (axis, lo, hi, points, outside))
    return ('막힘',
            '%s · 학습 %.2f ~ %.2f · 평가 %s · **범위 밖이 하나도 없습니다**'
            % (axis, lo, hi, points))


def _selftest():
    """결함을 «심어» 본다. 관문이 빈 채로 도는 것을 막는다.

    ★ 2026-09-14 에 「자기시험이 4/4 통과했는데 늘 나던 오류에 업힌 것」을
      겪었다. 그래서 두 방향을 다 넣는다. 막아야 할 것은 막고, 통과시켜야
      할 것은 통과시키는지.
    """
    cases = [
        # (학습 범위, 평가점, 기대)
        ((0.5, 1.5), [0.5, 1.0, 1.5], '막힘'),      # 지금 우리 상태
        ((0.5, 1.5), [0.0, 0.5, 1.0, 1.5], '통과'),  # 정지를 넣으면 통과
        ((0.5, 1.5), [0.5, 1.0, 1.5, 2.0], '통과'),  # 위로 나가도 통과
        ((-1.0, 1.0), [0.5, 1.0], '막힘'),           # NVIDIA 기본값 안이면 막힘
        (None, [0.5], '미확인'),                      # 못 읽으면 조용히 통과 금지
        ((0.5, 1.5), [], '미확인'),                   # 평가점이 없어도 마찬가지
    ]
    bad = []
    for rng, pts, want in cases:
        got, _ = check(rng, pts, '시험')
        if got != want:
            bad.append('%s · %s -> %s (기대 %s)' % (rng, pts, got, want))
    if bad:
        for b in bad:
            print('  [X] 자기시험 실패 · %s' % b)
        return False
    print('  자기시험 %d/%d 통과 (막아야 할 것 · 통과시킬 것 · 못 읽는 것)'
          % (len(cases), len(cases)))
    return True


def main():
    if not _selftest():
        return 1

    mpath = os.path.join(LAB, 'web', 'gallery', 'v1', 'manifest.json')
    if not os.path.isfile(mpath):
        alt = os.path.join(os.path.dirname(LAB), 'foothold-site',
                           'gallery', 'v1', 'manifest.json')
        mpath = alt if os.path.isfile(alt) else None
    if not mpath:
        print('  [!] 갤러리 매니페스트를 못 찾았습니다. 대조하지 못했습니다')
        return 0
    man = json.load(io.open(mpath, encoding='utf-8'))
    main_model = man.get('main_model') or 'foothold-v1'

    env = os.path.join(LAB, 'models', '%s.env.yaml' % main_model)
    if not os.path.isfile(env):
        cand = glob.glob(os.path.join(LAB, 'models', '*.env.yaml'))
        env = cand[0] if cand else None

    print('  모델 %s · 학습 설정 %s'
          % (main_model, os.path.basename(env) if env else '없음'))

    worst, lines = '통과', []
    for axis, ykey, efield in AXES:
        rng = train_range_from_env_yaml(env, ykey) if env else None
        pts = eval_points(man, efield)
        verdict, msg = check(rng, pts, axis)
        lines.append((verdict, msg))
        if verdict == '막힘':
            worst = '막힘'
        elif verdict == '미확인' and worst != '막힘':
            worst = '미확인'

    for v, m in lines:
        print('  %-6s %s' % (v, m))

    if worst == '막힘':
        print()
        print('  [!] 평가가 학습 범위 «밖» 을 하나도 재지 않습니다.')
        print('      이 상태의 성적표는 명령 범위 한계를 구조적으로 못 드러냅니다.')
        print('      고치는 법은 둘입니다.')
        print('        1. 평가에 범위 밖 점을 넣는다 (정지 0.0 · 저속 0.25 등)')
        print('        2. 성적표에 «이 범위 안에서만 쟀다» 를 명시한다')
        print('      2 는 이미 종합보고서 05절에 넣었습니다. 1 이 남았습니다.')
        return 1
    if worst == '미확인':
        print()
        print('  [!] 대조하지 못했습니다. 통과로 세지 마십시오.')
        print('      평가를 한 번 더 돌리면 run_manifest 에 training_env_cfg 가')
        print('      들어가고 그때부터 자동으로 읽힙니다 (PR #440).')
        return 0
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
