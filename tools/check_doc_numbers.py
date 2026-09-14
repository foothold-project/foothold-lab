# -*- coding: utf-8 -*-
"""문서에 손으로 옮겨 적은 «숫자» 가 실측과 같은가.

분류: 운영 · 작성: 오흥재 · 2026-09-14 · 상태: 확정
근거: 실측 (고의 오류 13종 주입 검출 시험 · `--selftest`)

## 왜 있나

문서에 표를 쓸 때 숫자는 사람이 옮긴다. 옮기다 틀려도 **아무 데서도 소리가
안 난다.** 표는 멀쩡해 보이고 빌드도 통과한다. 읽는 사람은 그 숫자를 믿는다.

2026-09-14 발행 전 검증에서 실제로 그 일이 있었다. `rails` 의 생존 85% ·
평균 전진 2.64 m 는 **평가 규격 1** 의 값인데 정본 표에 규격 2 결과인 것처럼
실려 있었다. 정본 원자료를 다시 집계하니 82% · 2.70 m 였다.

그래서 표를 다시 파싱해 **두 곳과 값으로 대조한다.**

  · `gallery/v1/manifest.json`                 종합 성공률 (평가 144칸)
  · `maindata-v1/.../generalization_raw.csv`   축별 통과율 · 종료 사유 · 전진

둘이 서로 어긋나는 것도 결함으로 센다.

문자열을 찾는 관문은 조작한 보고서 5종을 다 통과시킨 적이 있다 (2026-09-12).
이 관문은 **재측정**이다.

## 늘리는 법

원장이나 원자료에서 온 숫자를 표로 싣는 문서가 늘면 여기에 붙인다.
**표의 모양이 아니라 값으로 비교하는 것**만 지킨다.
"""
import csv
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)
SITE = os.path.join(os.path.dirname(LAB), 'foothold-site')
DOC = os.path.join(LAB, 'docs', 'research',
                   'generalization-benchmark-10-terrains.md')
RAW = os.path.join(LAB, 'sim', 'eval', 'results', 'maindata-v1')


def load_manifest():
    p = os.path.join(SITE, 'gallery', 'v1', 'manifest.json')
    return json.load(io.open(p, encoding='utf-8'))


def rate(evals, terrain, model, speed):
    for e in evals:
        if (e['terrain'] == terrain and e['model'] == model
                and abs(e['speed_mps'] - speed) < 1e-9):
            return e['success_rate']
    return None


def _T(x):
    return str(x).strip().lower() in ('true', '1', 'yes')


def axes(model, group, speed):
    """원자료에서 축별 통과율·평균 전진·종료 사유를 «다시 센다»."""
    p = os.path.join(RAW, model, group, 'd0.5', 'v' + speed,
                     'generalization_raw.csv')
    if not os.path.isfile(p):
        return {}
    rows = list(csv.DictReader(io.open(p, encoding='utf-8')))
    out = {}
    for t in sorted({r['terrain'] for r in rows}):
        w = [r for r in rows if r['terrain'] == t]
        n = len(w)
        out[t] = {
            '생존': sum(1 for r in w if _T(r['survival_success'])) * 100 // n,
            '전진': sum(1 for r in w if _T(r['progress_success'])) * 100 // n,
            '속도추종': sum(1 for r in w if _T(r['tracking_success'])) * 100 // n,
            '방향': sum(1 for r in w if _T(r['direction_success'])) * 100 // n,
            '종합': sum(1 for r in w if _T(r['overall_success'])) * 100 // n,
            '평균전진': sum(float(r['forward_progress_m']) for r in w) / n,
            '몸통접촉': sum(1 for r in w
                        if r['termination_reason'] == 'base_contact'),
            '시간만료': sum(1 for r in w
                        if r['termination_reason'] == 'timeout'),
            'n': n,
        }
    return out


def num(s):
    s = (s or '').strip().replace('**', '').replace('%', '')
    s = s.replace('m', '').strip()
    try:
        return float(s)
    except ValueError:
        return None


def check(text, man, ax, bad):
    """반환: 대조한 칸 수."""
    ev = man['evaluations']
    sets = man['terrain_sets']
    n = 0

    # ── §2 본표: 지형 | 생존 | 전진 | 속도추종 | 방향 | 종합 | 평균전진 | 판정
    sec = text.split('### 2-1.')[0]
    seen2 = set()
    row = re.compile(r'^\|\s*([a-z_]+)\s*\|([^|]+)\|([^|]+)\|([^|]+)\|'
                     r'([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|', re.M)
    for m in row.finditer(sec):
        t = m.group(1)
        seen2.add(t)
        want = ax.get(t)
        if not want:
            bad.append('§2 %s: 원자료에 없음' % t)
            continue
        for i, key in enumerate(['생존', '전진', '속도추종', '방향', '종합']):
            got = num(m.group(2 + i))
            n += 1
            if got != want[key]:
                bad.append('§2 %s %s 문서 %s · 원자료 %s'
                           % (t, key, got, want[key]))
        got = num(m.group(7))
        n += 1
        if got is None or abs(got - want['평균전진']) > 0.005:
            bad.append('§2 %s 평균전진 문서 %s · 원자료 %.2f'
                       % (t, got, want['평균전진']))
        n += 1
        if ('통과' in m.group(8)) != (want['종합'] >= 50):
            bad.append('§2 %s 판정 «%s» 인데 종합 %d%%'
                       % (t, m.group(8).strip(), want['종합']))
        # 원장과 원자료가 서로 맞는가
        n += 1
        r = rate(ev, t, 'baseline', 1.0)
        if r is None or abs(r - want['종합']) > 0.5:
            bad.append('§2 %s: 원장 %s · 원자료 %d%% 가 서로 다릅니다'
                       % (t, r, want['종합']))

    n += 1
    if seen2 != set(sets['unseen10']):
        bad.append('§2 지형 목록이 미경험 10종과 다릅니다: 빠짐 %s · 남음 %s'
                   % (sorted(set(sets['unseen10']) - seen2),
                      sorted(seen2 - set(sets['unseen10']))))

    # ── §2-2 속도 곡선 (종합 성공률)
    #   ★ 이 절에는 표가 «둘» 이다. 앞이 속도 곡선, 뒤가 1.5 m/s 축별이다.
    #     처음엔 나누지 않아 뒤 표를 앞 표로 읽고 거짓 경보 4건이 났다.
    #     처음엔 본문 문장으로 잘랐다. 그런데 그 문장을 고치자 나누기가 깨져
    #     거짓 경보 4건이 또 났다. **글이 아니라 표의 머리줄로 가른다.**
    #     머리줄은 열 구성이라 글보다 잘 안 바뀐다.
    part = text.split('### 2-2.')[1].split('### 2-3.')[0]
    HEAD15 = '| 지형 | 생존 | 전진 | 속도추종 | 방향 | 종합 |'
    if HEAD15 in part:
        sec2, sec15 = part.split(HEAD15, 1)
        sec15 = HEAD15 + sec15
    else:
        sec2, sec15 = part, ''
        bad.append('§2-2 의 1.5 m/s 축별 표를 못 찾았습니다 (머리줄이 바뀌었나)')
    r3 = re.compile(r'^\|\s*([a-z_]+)\s*\|([^|]+)\|([^|]+)\|([^|]+)\|', re.M)
    for m in r3.finditer(sec2):
        t = m.group(1)
        for i, sp in enumerate((0.5, 1.0, 1.5)):
            got = num(m.group(2 + i))
            want = rate(ev, t, 'baseline', sp)
            n += 1
            if want is None:
                bad.append('§2-2 %s %s m/s: 원장에 없음' % (t, sp))
            elif got != want:
                bad.append('§2-2 %s %s m/s 문서 %s · 원장 %s'
                           % (t, sp, got, want))

    # ── §2-2 뒤쪽: 1.5 m/s 축별 표 (원자료 v1.5 로 대조)
    ax15 = axes('baseline', 'unseen10', '1.5')
    r5 = re.compile(r'^\|\s*([a-z_]+)\s*\|([^|]+)\|([^|]+)\|([^|]+)\|'
                    r'([^|]+)\|([^|]+)\|', re.M)
    seen15 = set()
    for m in r5.finditer(sec15):
        t = m.group(1)
        seen15.add(t)
        w = ax15.get(t)
        if not w:
            bad.append('§2-2(1.5) %s: 원자료에 없음' % t)
            continue
        for i, key in enumerate(['생존', '전진', '속도추종', '방향', '종합']):
            got = num(m.group(2 + i))
            n += 1
            if got != w[key]:
                bad.append('§2-2(1.5) %s %s 문서 %s · 원자료 %s'
                           % (t, key, got, w[key]))
    n += 1
    pass5 = {t for t in sets['unseen10'] if ax.get(t, {}).get('종합', 0) >= 50}
    if seen15 and seen15 != pass5:
        bad.append('§2-2(1.5) 지형 목록이 통과 5종과 다릅니다: %s'
                   % sorted(seen15 ^ pass5))

    # ── §2-3 rails 갈래 표 (전진 통과 46 중 속도 추종 탈락 38 …)
    if 'rails' in ax:
        p = os.path.join(RAW, 'baseline', 'unseen10', 'd0.5', 'v1',
                         'generalization_raw.csv')
        w = [r for r in csv.DictReader(io.open(p, encoding='utf-8'))
             if r['terrain'] == 'rails']
        ok_ = [r for r in w if _T(r['progress_success'])]
        want = {
            '전진축에서 탈락': len(w) - len(ok_),
            '전진축 통과': len(ok_),
            '그중 종합 성공': sum(1 for r in ok_ if _T(r['overall_success'])),
            '그중 속도 추종에서 탈락':
                sum(1 for r in ok_ if not _T(r['tracking_success'])),
            '그 38 개 중 방향에서도 탈락':
                sum(1 for r in ok_ if not _T(r['tracking_success'])
                    and not _T(r['direction_success'])),
        }
        for label, v in want.items():
            m = re.search(r'\|[^|]*%s\s*\|\s*\*{0,2}(\d+)\*{0,2}\s*\|'
                          % re.escape(label), text)
            n += 1
            if not m:
                bad.append('§2-3 «%s» 줄을 못 찾음' % label)
            elif int(m.group(1)) != v:
                bad.append('§2-3 %s 문서 %s · 원자료 %d'
                           % (label, m.group(1), v))

    # ── §2-3 rails 정본 열
    rails = ax.get('rails') or {}
    if rails:
        for label, key, conv in [('생존율', '생존', lambda v: float(v)),
                                 ('평균 전진', '평균전진',
                                  lambda v: round(v, 2))]:
            m = re.search(r'\|\s*%s\s*\|[^|]*\|\s*\*\*([^*|]+)\*\*\s*\|'
                          % re.escape(label), text)
            n += 1
            if not m:
                bad.append('§2-3 «%s» 줄을 못 찾음' % label)
            elif num(m.group(1)) != conv(rails[key]):
                bad.append('§2-3 %s 문서 %s · 원자료 %s'
                           % (label, num(m.group(1)), conv(rails[key])))
        m = re.search(r'timeout (\d+) · base_contact (\d+)', text)
        n += 1
        if not m:
            bad.append('§2-3 종료 사유 줄을 못 찾음')
        elif (int(m.group(1)), int(m.group(2))) != (rails['시간만료'],
                                                    rails['몸통접촉']):
            bad.append('§2-3 종료 사유 문서 %s/%s · 원자료 %d/%d'
                       % (m.group(1), m.group(2),
                          rails['시간만료'], rails['몸통접촉']))

    # ── §3 실패 모양 표: 지형 | 생존 | 몸통접촉 | 시간만료 | 모양
    sec3 = text.split('## 3.')[1].split('## 4.')[0]
    r4 = re.compile(r'^\|\s*([a-z_]+)\s*\|([^|]+)\|([^|]+)\|([^|]+)\|', re.M)
    seen3 = set()
    for m in r4.finditer(sec3):
        t = m.group(1)
        seen3.add(t)
        w = ax.get(t)
        if not w:
            bad.append('§3 %s: 원자료에 없음' % t)
            continue
        for i, key in enumerate(['생존', '몸통접촉', '시간만료']):
            got = num(m.group(2 + i))
            n += 1
            if got != w[key]:
                bad.append('§3 %s %s 문서 %s · 원자료 %s' % (t, key, got, w[key]))
    n += 1
    fail = {t for t in sets['unseen10'] if ax.get(t, {}).get('종합', 0) < 50}
    if seen3 != fail:
        bad.append('§3 실패 지형 목록이 실측과 다릅니다: %s'
                   % sorted(fail ^ seen3))

    # ── §5 학습 분포 안
    sec5 = text.split('## 5.')[1].split('## 6.')[0]
    seen5 = set()
    for m in re.finditer(r'^\|\s*([a-z_]+)\s*\|([^|]+)\|', sec5, re.M):
        t, got = m.group(1), num(m.group(2))
        want = rate(ev, t, 'baseline', 1.0)
        n += 1
        seen5.add(t)
        if want is None:
            bad.append('§5 %s: 원장에 없음' % t)
        elif got != want:
            bad.append('§5 %s 문서 %s · 원장 %s' % (t, got, want))
    n += 1
    if seen5 != set(sets['rough6']):
        bad.append('§5 지형 목록이 기존 6종과 다릅니다: 빠짐 %s'
                   % sorted(set(sets['rough6']) - seen5))

    # ── 제목의 주장이 실측과 같은가
    n += 1
    pas = sum(1 for t in sets['unseen10'] if ax.get(t, {}).get('종합', 0) >= 50)
    if pas != 5:
        bad.append('제목은 5종 통과인데 실측에서는 %d종입니다' % pas)

    # ── 실패 5종의 «최고» 성공률을 본문이 바르게 적었나
    #   처음 판에서 pit 7% 라 적었는데 실제로는 rails 8% 였다.
    n += 1
    best = max(((t, sp, rate(ev, t, 'baseline', sp))
                for t in fail for sp in (0.5, 1.0, 1.5)),
               key=lambda x: x[2] if x[2] is not None else -1)
    m = re.search(r'가장 높은 값이 (\S+) 의 ([\d.]+) m/s (\d+)%', text)
    if not m:
        bad.append('실패 5종 최고값 문장을 못 찾음')
    elif (m.group(1), float(m.group(2)), float(m.group(3))) != (
            best[0], best[1], best[2]):
        bad.append('실패 5종 최고 문서 «%s %s m/s %s%%» · 실측 «%s %s m/s %s%%»'
                   % (m.group(1), m.group(2), m.group(3), best[0],
                      best[1], best[2]))

    # ── 금지된 글자
    n += 1
    if '—' in text:
        bad.append('em dash 가 %d개 있습니다' % text.count('—'))
    return n


CASES = [
    ('축 값 하나', '| rails | 82% | 46%', '| rails | 85% | 46%'),
    ('평균 전진', '| 2.70 m | 실패 |', '| 2.64 m | 실패 |'),
    ('속도 곡선 한 칸', '| star | 86% | **100%** | 62% |',
     '| star | 86% | **100%** | 72% |'),
    ('rails 정본 생존율', '| **82%** |', '| **85%** |'),
    ('종료 사유', 'timeout 82 · base_contact 18',
     'timeout 85 · base_contact 15'),
    ('실패 유형 표', '| stepping_stones | 15% | 85 | 15 |',
     '| stepping_stones | 42% | 85 | 15 |'),
    ('§5 한 칸', '| boxes | 34% |', '| boxes | 44% |'),
    ('지형 하나 빠뜨림',
     '| wave | 100% | 100% | 100% | 100% | **100%** | 5.48 m | 통과 |\n', ''),
    ('실패 5종 최고값', 'rails 의 1.0 m/s 8% 다', 'pit 의 0.5 m/s 7% 다'),
    ('em dash', '결과는 절반이다', '결과는 절반이다 — 그렇다'),
    ('1.5 축별 한 칸', '| star | 100% | 100% | **62%** | 100% | 62% |',
     '| star | 100% | 100% | **52%** | 100% | 62% |'),
    ('rails 갈래 한 칸', '| · 그중 속도 추종에서 탈락 | 38 |',
     '| · 그중 속도 추종에서 탈락 | 30 |'),
    ('전진축 탈락 수', '| 전진축에서 탈락 | **54** |',
     '| 전진축에서 탈락 | **44** |'),
]


def selftest():
    """알려진 답. 숫자를 하나 틀리게 만들면 잡아야 한다."""
    man = load_manifest()
    ax = axes('baseline', 'unseen10', '1')
    t = io.open(DOC, encoding='utf-8').read()
    okc = 0
    for name, old, new in CASES:
        s = t.replace(old, new, 1)
        if s == t:
            print('  [!] %-18s 주입 실패 (대상 없음)' % name)
            continue
        b = []
        check(s, man, ax, b)
        if b:
            okc += 1
            print('  잡음    %-18s %s' % (name, b[0][:56]))
        else:
            print('  [X]놓침 %-18s' % name)
    print('  %d/%d' % (okc, len(CASES)))
    return okc == len(CASES)


def main():
    man = load_manifest()
    ax = axes('baseline', 'unseen10', '1')
    if not ax:
        print('  [!] 원자료를 못 읽었습니다. 통과로 안 읽습니다')
        return 1
    t = io.open(DOC, encoding='utf-8').read()
    bad = []
    n = check(t, man, ax, bad)
    print('  대조 %d칸 (원장 + 원자료 %d 에피소드)'
          % (n, sum(v['n'] for v in ax.values())))
    if bad:
        print('  [!] 어긋난 것 %d건' % len(bad))
        for b in bad[:20]:
            print('      ' + b)
        return 1
    if n < 60:
        print('  [!] 대조한 칸이 너무 적습니다. 표를 못 읽은 것입니다')
        return 1
    print('  문서의 숫자가 실측과 전부 일치합니다')
    return 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    sys.exit(main())
