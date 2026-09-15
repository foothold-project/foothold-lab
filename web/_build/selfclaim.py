# -*- coding: utf-8 -*-
"""자기 참조 사실 자동 집계 (SITE-REVIEW-20260824 §6-2).

  문제: 외부 사실은 claims.py 가 지키는데, **우리 자신에 대한 사실**
  (현 단계 · 안건 수 · 덱 장수 · 팀 인원)은 아무도 검증하지 않았다.
  손으로 쓴 숫자라 문서가 늘 때마다 어긋났고, 실제로 이렇게 틀려 있었다.

    index 「덱 (10장)」   vs  pitch.html 실제 12장
    index 「안건 5건」    vs  plan.html 「🔶 6건」 (PLAN.md §5 = D1~D6)
    index 「현 단계 W1 · 환경 구성」  08-12 이후 미갱신

  팀원·멘토가 이 페이지를 신뢰 기준으로 삼는 순간 틀린 방향으로 안내된다.

  방법: 손으로 쓰지 않는다. 원천에서 세고, 표지 블록을 다시 만든다.
    덱 장수  <- pitch.html 의 slide 섹션 수
    안건 수  <- 04_plan/PLAN.md §5 표의 D 행 수
    단계     <- 오늘 날짜와 마일스톤 표
    팀 인원  <- index 푸터의 이름 나열

  마커로 감싸 몇 번 돌려도 결과가 같다.
"""
import datetime
import io
import os
import re
import sys
import buildtime

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)                       # 05_deliverables
PROJ = __import__('roots').proj()                  # 02_team · 04_plan 이 있는 곳

A, B = '<!--status:v1-->', '<!--/status:v1-->'

# ★ 2026-09-02 (mai-os#24). «슬롯» 은 소유 마커와 다른 표식이다.
#   슬롯 = 손 관리 소스가 «여기에 넣어라» 고 선언하는 자리. 계산 결과는 없다.
#   소유 마커(A/B) = 생성물에만 있는 것. 소스에 있으면 오염이다.
#   관문은 이 둘을 반대로 판정한다. 소스에 슬롯은 합법 · 소유 마커는 불법.
SLOT = '<!--slot:status-->'

# 일정 앵커. 여기가 유일 원본이다. 바꾸려면 이 표만 고친다.
#   9/30 은 8/20 회의에서 「아마 10월 초」 언급이 나왔으나 공식 공지 전이라
#   현행 가정을 유지한다(회의록 20260820 §확정 6).
MILESTONES = [
    ('2026-09-04', '기획 발표', '두 트랙 기획 확정'),
    ('2026-09-30', '중간 발표', '시뮬 RL · 일반화 벤치마크'),
    ('2026-12-11', '최종 발표', '실기 자율주행 · 통합'),
]
START = '2026-08-06'        # 첫 멘토 미팅. 기간 계산의 시작점


def _d(s):
    return datetime.date(*map(int, s.split('-')))


def count_slides(pitch):
    """★ class="slide" 정확일치로 세면 안 된다. 추가 클래스가 붙은 장을 놓친다.
    실제로 그렇게 세어 12장을 10장으로 읽었다(2026-08-26)."""
    return len(re.findall(r'<section[^>]*\bclass="[^"]*\bslide\b', pitch))


def count_agenda(plan_md):
    """PLAN.md §5 결정 안건 표의 D 행 수."""
    sec = re.search(r'^##\s*5\..*?$(.*?)^##\s', plan_md, re.M | re.S)
    body = sec.group(1) if sec else plan_md
    return len(re.findall(r'^\|\s*D\d+\s*\|', body, re.M))


def facts(today=None):
    today = today or buildtime.today()
    pitch = io.open(os.path.join(VAULT, 'pitch.html'), encoding='utf-8').read()
    plan_md = io.open(os.path.join(PROJ, '04_plan', 'PLAN.md'), encoding='utf-8').read()

    nxt = next((m for m in MILESTONES if _d(m[0]) >= today), MILESTONES[-1])
    prev = [m for m in MILESTONES if _d(m[0]) < today]
    stage = ('%s 준비' % nxt[1], nxt[2])
    weeks = ((today - _d(START)).days // 7) + 1
    total = ((_d(MILESTONES[-1][0]) - _d(START)).days // 7) + 1
    dday = (_d(nxt[0]) - today).days
    return {
        'slides': count_slides(pitch),
        'agenda': count_agenda(plan_md),
        'week': weeks, 'total_weeks': total,
        'stage': stage[0], 'stage_sub': stage[1],
        'next_label': nxt[1], 'next_date': nxt[0], 'dday': dday,
        'done': len(prev),
    }


def block(f):
    st = ('<div class="st"><div class="k">%s</div>'
          '<div class="v">%s<small>%s</small></div></div>')
    stc = ('<div class="st" style="border-left-color:%s"><div class="k">%s</div>'
           '<div class="v">%s<small>%s</small></div></div>')
    md = _d(f['next_date'])
    items = (
        st % ('기간', '%d주차' % f['week'], '전체 %d주 · 2026.08 ~ 12' % f['total_weeks']),
        st % ('현 단계', f['stage'], f['stage_sub']),
        stc % ('var(--dim)', '다음 마일스톤',
               # ★ 2026-09-16. 같은 이유로 여기도 살린다.
               (('<span class="dd-live" data-due="%s">D-%d</span>'
                 % (md.isoformat(), f['dday'])) if f['dday'] >= 0 else '지남'),
               '%d/%d %s' % (md.month, md.day, f['next_label'])),
        stc % ('var(--note)', '미결 안건', '%d건' % f['agenda'],
               '설계도 5절 · 팀이 정할 것'),
    )
    return '%s\n<div class="status">\n  %s\n</div>\n%s' % (A, '\n  '.join(items), B)


def apply(idx_path, f):
    """표지의 상태 블록과 덱 장수를 원천 값으로 맞춘다. 바뀐 것을 돌려준다."""
    t = io.open(idx_path, encoding='utf-8').read()
    changed = []

    if SLOT in t:
        # 슬롯이 있으면 첫 빌드부터 여기서 만든다. 소스에 값을 되돌리지 않는다
        t2 = t.replace(SLOT, block(f), 1)
    elif A in t:
        t2 = re.sub(re.escape(A) + r'.*?' + re.escape(B), block(f), t, flags=re.S)
    else:
        # ★ 첫 삽입. `</div>` 로 끝을 잡으면 안 된다. 안쪽 .st 들이 먼저 닫혀서
        #   너무 일찍 끊기고 옛 블록 잔해가 남는다(2026-08-26 실제로 그랬다).
        #   블록 «다음에 오는 것»(footer)을 기준으로 끝을 잡는다.
        m = re.search(r'<div class="status">.*?</div>\s*(?=\n\s*<footer)', t, re.S)
        if not m:
            print('  [!] 표지에서 상태 블록을 못 찾았습니다 (status div + footer 기준)')
            return None
        t2 = t[:m.start()] + block(f) + '\n' + t[m.end():]
    if t2 != t:
        changed.append('현재 상태 블록')
        t = t2

    def deck(m):
        if int(m.group(1)) != f['slides']:
            changed.append('덱 %s장 -> %d장' % (m.group(1), f['slides']))
        return '덱 (%d장)' % f['slides']
    t = re.sub(r'덱 \((\d+)장\)', deck, t)

    # ★ 사후 조건. 치환이 반쯤 되면 옛 칸이 남아 «두 개의 진실»이 생긴다.
    #   블록은 하나, 칸은 정확히 넷이어야 한다.
    # ★ 세는 패턴에 주의. `class="st` 는 `class="status"` 에도 걸린다.
    #   접두사로 세다가 4를 5로 읽었다(2026-08-26). 경계를 명시한다.
    ST = re.compile(r'<div class="st[">]')
    if t.count(A) != 1:
        print('  [!] 상태 블록 마커가 %d개입니다 (1개여야)' % t.count(A))
        return None
    seg = t.split(A, 1)[1].split(B, 1)[0]
    if len(ST.findall(seg)) != 4:
        print('  [!] 상태 칸이 %d개입니다 (4개여야). 옛 블록 잔해 의심'
              % len(ST.findall(seg)))
        return None
    after = t.split(B, 1)[1].split('<footer', 1)[0]
    if ST.search(after):
        print('  [!] 블록 «뒤»에 상태 칸이 %d개 남아 있습니다. 치환이 일찍 끊겼습니다'
              % len(ST.findall(after)))
        return None

    io.open(idx_path, 'w', encoding='utf-8', newline='\n').write(t)
    return changed


def contradictions(f):
    """다른 페이지가 같은 사실을 다르게 말하는가. 여기서 걸러야 배포가 안 나간다."""
    out = []
    p = os.path.join(VAULT, 'plan.html')
    if os.path.exists(p):
        t = io.open(p, encoding='utf-8').read()
        m = re.search(r'🔶\s*(\d+)\s*건', t)
        if m and int(m.group(1)) != f['agenda']:
            out.append('plan.html 「%s건」 vs PLAN.md §5 %d건' % (m.group(1), f['agenda']))
    idx = io.open(os.path.join(VAULT, 'index.html'), encoding='utf-8').read()
    for n in re.findall(r'덱 \((\d+)장\)', idx):
        if int(n) != f['slides']:
            out.append('index 덱 「%s장」 vs pitch 실제 %d장' % (n, f['slides']))
    return out


def _kat():
    """★ 세는 방법이 맞는지 답을 아는 입력으로 먼저 본다 (커널 원칙 1)."""
    s = ('<section class="slide">a</section>'
         '<section class="slide dark">b</section>'
         '<section class="cover slide">c</section>'
         '<div class="slide">not a section</div>')
    if count_slides(s) != 3:
        return False, 'slide 세기 오류: %d (3이어야)' % count_slides(s)
    md = ('## 5. 안건\n\n| # | 안건 |\n|---|---|\n| D1 | a |\n| D2 | b |\n'
          '\n## 6. 다음\n\n| D9 | 세면 안 되는 것 |\n')
    if count_agenda(md) != 2:
        return False, '안건 세기 오류: %d (2여야)' % count_agenda(md)
    return True, ''


def main():
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why); return False
    f = facts()
    ch = apply(os.path.join(VAULT, 'index.html'), f)
    if ch is None:
        return False
    print('  자가검증 통과 · 덱 %d장 · 미결 안건 %d건 · %d주차 · 다음 %s D-%d'
          % (f['slides'], f['agenda'], f['week'], f['next_label'], f['dday']))
    for c in ch:
        print('  갱신: %s' % c)
    bad = contradictions(f)
    for b in bad:
        print('  ★ 상충: %s' % b)
    if bad:
        return False
    print('  페이지 간 상충 없음')
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main() else 1)
