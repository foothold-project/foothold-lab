# -*- coding: utf-8 -*-
"""AME-2 v1~v6 보고서(docs/research/20261007-ame2-go2-v1-v6.md) 그림 일곱 장과 자료 CSV.
  python _out/tools/ame2_figs.py
산출: docs/assets/visual/ame2-*.svg (+ .dark.svg 는 tools/svg_theme.write_pair 로)
      docs/assets/eval/ame2-v14-2000-by-task.csv · ame2-versions.csv
숫자 출처: RunPod limseokheon/ame2_go2 reports/ (보고서 본문과 같은 값 · 손으로 옮김).
Wilson 95 % 는 여기서 계산한다."""
import math, os, sys, csv
from pathlib import Path
LAB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LAB / 'tools'))
import svg_selfcontained as SC  # noqa: E402
import svg_theme  # noqa: E402

VIS = LAB / 'docs' / 'assets' / 'visual'
DAT = LAB / 'docs' / 'assets' / 'eval'
SANS = 'IBM Plex Sans KR, Malgun Gothic, sans-serif'
MONO = 'IBM Plex Mono, Consolas, monospace'


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


class Fig:
    def __init__(self, name, w, h, label):
        self.name, self.w, self.h, self.label, self.o = name, w, h, label, []

    def t(self, x, y, s, size=12, fill='--ink', anchor='start', weight=400, mono=False):
        self.o.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="var({fill})" text-anchor="{anchor}" '
                      f'font-weight="{weight}" font-family="{MONO if mono else SANS}">{esc(s)}</text>')

    def r(self, x, y, w, h, fill='--card', stroke='--rule', rx=6, dash=False, sw=1.2):
        d = ' stroke-dasharray="5 4"' if dash else ''
        st = f' stroke="var({stroke})" stroke-width="{sw}"' if stroke else ''
        self.o.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="var({fill})"{st}{d}/>')

    def l(self, x1, y1, x2, y2, stroke='--ink-3', sw=1.4, arrow=False, dash=False):
        a = ' marker-end="url(#ar)"' if arrow else ''
        d = ' stroke-dasharray="5 4"' if dash else ''
        self.o.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="var({stroke})" stroke-width="{sw}"{a}{d}/>')

    def c(self, x, y, rad, fill='--accent', stroke=None):
        st = f' stroke="var({stroke})" stroke-width="1.5"' if stroke else ''
        self.o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad}" fill="var({fill})"{st}/>')

    def save(self):
        head = (f'<svg viewBox="-20 -20 {self.w + 40} {self.h + 40}" xmlns="http://www.w3.org/2000/svg" '
                f'style="max-width:100%;height:auto;display:block" role="img" aria-label="{esc(self.label)}" '
                f'width="{self.w}" height="{self.h}">\n<!--selfcontained:v1-->\n'
                f'<style>\n:root{{{SC._decl(SC.LIGHT)}}}\n</style>\n'
                '<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
                '<path d="M 0 0 L 10 5 L 0 10 z" fill="var(--ink-3)"/></marker></defs>\n'
                f'<title>{esc(self.label)}</title>\n')
        p = VIS / f'{self.name}.svg'
        p.write_text(head + '\n'.join(self.o) + '\n</svg>\n', encoding='utf-8', newline='\n')
        svg_theme.write_pair(str(p))
        return p


def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0, c - h), min(1, c + h)


# ---------------------------------------------------------------- 1. 대응 타임라인
def fig_timeline():
    f = Fig('ame2-timeline', 900, 470, 'AME-2 내부 실험 판과 석헌 서사 v1~v6 의 대응')
    f.t(0, 14, '석헌의 v1~v6 사이에는 서사에 안 나온 판이 13개 있다', 15, weight=700)
    f.t(0, 34, '색칠한 칸 = 서사에 나온 판 · 점선 칸 = 서사에 없는 판(대부분 실패 진단) · 결과는 그 판 보고서의 값', 11.5, '--ink-2')
    cols = [
        ('9/24', '험지 · 500회', [('A baseline', '험지 0/120', 0), ('B flat_mirror', '험지 0/120', 0), ('C progress', '험지 26/120', 1)]),
        ('9/27~9/28', '험지 이어서 · 평지 시작', [('C 1000회', '0.5 m 도달 75/400', 2), ('restore_v1', 'smoke 2회만', 0),
                                           ('flat_goal_v1', '결과 폴더 삭제', 0), ('flat_goal_v2', '각 과제 0/50', 0)]),
        ('9/29', '평지 · 0 을 깨려는 시도', [('v3 guard', '도착 0/120', 0), ('v4 probe', '도착 0/320', 0), ('v5 limits', '도착 0/320', 0),
                                     ('v6 heading', '도착 0/320', 0), ('v7 3:3:2:2', '전부 0', 3), ('v8 보상·제어', '정지 80/80', 4)]),
        ('9/30', '이동 비중 올림', [('v9 raw cost', '정지 53/80', 0), ('v10 2차 차분', '284회 폐기', 0), ('v11 49:49:2', '364/1040', 5)]),
        ('10/6', '정밀 도착 · 20초', [('v12 보행 주기', '31회 취소', 0), ('v13 1000회', '810/1040', 6)]),
        ('10/6~10/7', '이어 2000회 · 둘로 가름', [('v14 control', '850/1040', 7), ('v14 candidate', '885/1040', 7), ('v15 공개 코드', '학습 중 2466/5000', 0)]),
    ]
    tag = {1: '서사 v1', 2: '서사 v1', 3: '서사 v2', 4: '서사 v3', 5: '서사 v4', 6: '서사 v5', 7: '서사 v6'}
    cw, gap, y0 = 140, 12, 62
    for i, (d, sub, chips) in enumerate(cols):
        x = i * (cw + gap)
        f.r(x, y0, cw, 40, '--paper-2', None, rx=6)
        f.t(x + cw / 2, y0 + 17, d, 13, anchor='middle', weight=700)
        f.t(x + cw / 2, y0 + 33, sub, 10.5, '--ink-2', anchor='middle')
        for j, (nm, res, k) in enumerate(chips):
            y = y0 + 52 + j * 58
            if k:
                f.r(x, y, cw, 50, '--accent-soft', '--accent', sw=1.6)
            else:
                f.r(x, y, cw, 50, '--card', '--ink-soft', dash=True)
            f.t(x + 9, y + 18, nm, 12, '--ink', weight=600)
            f.t(x + 9, y + 37, res, 11, '--ink-2' if not k else '--dim-ink', mono=any(ch.isdigit() for ch in res))
            if k:
                f.t(x + cw - 8, y + 18, tag[k], 10, '--dim-ink', anchor='end', weight=700)
    f.l(0, 448, 900, 448, '--rule', 1)
    f.t(0, 466, '판정 규약이 판마다 다르다: 9/24~9/28 험지는 0.5 m 도달 · v7~v11 은 8초 마감 · v13~v14 는 15초 마감 20초 에피소드. 숫자를 한 줄로 잇지 말 것', 11, '--warn')
    return f.save()


# ---------------------------------------------------------------- 2. 완성 시스템 중 된 것
def fig_system():
    f = Fig('ame2-system-status', 900, 330, 'AME-2 완성 시스템 셋 중 무엇이 만들어졌나')
    f.t(0, 14, 'AME-2 완성 시스템에는 학습 결과가 셋 필요하다 · 지금 있는 것은 teacher 하나(평지)', 15, weight=700)
    f.t(0, 34, '근거: docs/AME2_Go2_Implementation_Plan_ko.md 1절 · docs/AME2_RESUME_ko.md · reports/public_go2_v15_20261007/HANDOFF_ko.txt', 11, '--ink-3', mono=True)
    boxes = [
        ('teacher', '정답 높이지도 + 몸 상태 + 목표', ['목표 자세 도달 정책 (PPO)', '평지 2000회까지 · 시드 1개', '논문 예산 80,000회의 2.5 %'], 'ok', '만듦 · 평지만'),
        ('Mapper', '깊이 카메라 2대 → 국소 격자', ['가려진 지형 높이·불확실성 예측', '센서·격자 검사만 (9/22~9/23)', '학습 안 함'], 'bad', '안 함'),
        ('student', 'Mapper 지도 누적 + 상태 20프레임', ['teacher 행동과 지도 표현 증류', '실제 로봇에 올라가는 정책', '학습 안 함'], 'bad', '안 함'),
        ('실기·sim2sim', 'Go2 실기 · MuJoCo 등', ['다른 시뮬레이터로 옮겨 재기', '실제 Go2 에서 재기', '산출물 없음'], 'bad', '없음'),
    ]
    bw, gap, y = 200, 33, 60
    for i, (nm, inp, lines, st, chip) in enumerate(boxes):
        x = i * (bw + gap)
        soft = '--ok-soft' if st == 'ok' else '--bad-soft'
        f.r(x, y, bw, 168, '--card', '--ok' if st == 'ok' else '--rule', sw=1.6 if st == 'ok' else 1.2, dash=st != 'ok')
        f.t(x + 12, y + 26, nm, 15, weight=700)
        cwid = 22 + 11 * len(chip)
        f.r(x + bw - 10 - cwid, y + 11, cwid, 22, soft, None, rx=11)
        f.t(x + bw - 10 - cwid / 2, y + 26, chip, 11, '--ok' if st == 'ok' else '--bad', anchor='middle', weight=700)
        f.t(x + 12, y + 50, inp, 11, '--ink-2')
        f.l(x + 12, y + 62, x + bw - 12, y + 62, '--rule-2', 1)
        for j, s in enumerate(lines):
            f.t(x + 12, y + 86 + j * 24, s, 11.5, '--ink')
        if i < 3:
            f.l(x + bw + 3, y + 84, x + bw + gap - 4, y + 84, '--ink-3', 1.4, arrow=True)
    y2 = 252
    f.r(0, y2, 900, 62, '--warn-soft', None, rx=8)
    f.t(14, y2 + 24, '10/7 새로 도는 것 · 내부 v15', 13, '--warn', weight=700)
    f.t(14, y2 + 46, '공개 leggedrobotics/ame2_minimal 의 teacher 를 Go2 로 옮겨 12종 험지에서 학습 중 (1024 환경 · 21:18 기준 2466/5000회). v14 와 구조가 달라 결과를 그대로 잇지 못한다', 11.5, '--ink')
    return f.save()


# ---------------------------------------------------------------- 3. teacher 신경망
def fig_net():
    f = Fig('ame2-teacher-net', 900, 400, 'AME-2 teacher 의 actor 와 critic 구조')
    f.t(0, 14, 'teacher actor 는 지도 351점에 attention 을 건다 · critic 은 정답 정보로 MoE 16개', 15, weight=700)
    f.t(0, 34, '근거: experiments/ame2_flat_recovery_v14_candidate_20261006/bootstrap/teacher_network.py · policy_observations.py · 은닉 크기와 ELU 는 논문 미공개라 구현 선택', 11, '--ink-3', mono=True)
    def box(x, y, w, h, a, b=None, fill='--card', stroke='--rule'):
        f.r(x, y, w, h, fill, stroke)
        f.t(x + w / 2, y + (h / 2 + 4 if not b else h / 2 - 3), a, 12, anchor='middle', weight=600)
        if b:
            f.t(x + w / 2, y + h / 2 + 14, b, 10.5, '--ink-2', anchor='middle', mono=True)
    f.t(0, 66, 'actor (정책) · 입력 1,102', 12.5, '--accent', weight=700)
    box(0, 80, 150, 50, '몸 상태 45 + 목표 4', '[dx, dy, sin, cos]', '--accent-soft', '--accent')
    box(0, 150, 150, 50, '지도 27×13×3', '351점 · 6 cm 격자', '--accent-soft', '--accent')
    box(190, 80, 150, 50, '상태 encoder', 'MLP 49→128→64')
    box(190, 150, 150, 50, '점별 특징', 'MLP + CNN → 96')
    box(380, 150, 150, 50, '전역 특징', 'max pool → 64')
    box(380, 80, 150, 50, 'query 96', '상태 64 + 전역 64')
    box(570, 110, 150, 60, 'multi-head attention', '32 head · 96차원', '--warn-soft', '--warn')
    box(760, 80, 140, 50, 'decoder', '224→512→256→128')
    box(760, 150, 140, 50, '관절 12개 목표', '× 0.25 rad')
    f.l(150, 105, 188, 105, arrow=True); f.l(150, 175, 188, 175, arrow=True)
    f.l(340, 175, 378, 175, arrow=True); f.l(340, 105, 378, 105, arrow=True)
    f.l(455, 150, 455, 132, arrow=True)
    f.l(530, 105, 568, 130, arrow=True); f.l(530, 175, 568, 150, arrow=True)
    f.l(720, 140, 758, 112, arrow=True); f.l(830, 130, 830, 148, arrow=True)
    f.t(560, 218, '국소 96 + 전역 64 = 지도 표현 160 → 상태 64 와 합쳐 224', 11, '--ink-2')
    y = 250
    f.t(0, y, 'critic (가치) · 입력 420 · 학습 때만 쓰는 정답 정보', 12.5, '--ink-2', weight=700)
    box(0, y + 14, 270, 54, '몸 45 + 목표 5 + 정답 높이 351 + 접촉 19', '목표 5 = x · y · sin · cos · 남은 시간', '--paper-2', '--rule')
    box(300, y + 14, 230, 54, 'expert 16개', '각 420→256→256→128→1')
    box(300, y + 82, 230, 46, 'softmax gate', '420→128→128→16')
    box(580, y + 40, 140, 54, '가치 V', '가중합')
    f.l(270, y + 41, 298, y + 41, arrow=True); f.l(270, y + 52, 298, y + 104, arrow=True)
    f.l(530, y + 41, 578, y + 62, arrow=True); f.l(530, y + 104, 578, y + 74, arrow=True)
    f.t(760, y + 32, '제어', 12, '--ink', weight=700)
    for j, s in enumerate(['물리 400 Hz · 정책 50 Hz', '목표각 기본 자세 ±0.5 rad', '변화 4 rad/s 이하', '출력 배율 이동 0.8 · 근처 0.4']):
        f.t(760, y + 54 + j * 20, s, 10.5, '--ink-2')
    return f.save()


# ---------------------------------------------------------------- 4. v14 2000회 과제별
V14 = [  # 과제, 분모, control, candidate
    ('가까운 정면', 20, 13, 20), ('move 1.0 · 1.5 m', 160, 139, 160), ('move 2.5 m', 80, 55, 52), ('move 4.0 m', 80, 48, 21),
    ('pose', 320, 231, 259), ('turn', 280, 272, 276), ('stand', 80, 80, 80), ('sequence', 40, 25, 37), ('합계', 1040, 850, 885)]


def fig_v14():
    f = Fig('ame2-v14-2000', 900, 545, 'v14 2000회 control 대 candidate 과제별 성공률')
    f.t(0, 14, '2000회: candidate 가 합계에서 앞서지만 4 m 이동은 크게 뒤진다', 15, weight=700)
    f.t(0, 34, '막대 = 성공률 · 가는 선 = Wilson 95 % (평가 1040판 기준 · 학습 시드는 갈래당 1개) · 근거 reports/flat_recovery_v14_20261006/comparison_2000.json', 11, '--ink-2')
    x0, bw, y0, rh = 170, 560, 74, 47
    f.r(x0 - 4, 48, 14, 10, '--ink-3', None, rx=2); f.t(x0 + 16, 57, 'control (v5 설정 유지)', 11, '--ink-2')
    f.r(x0 + 186, 48, 14, 10, '--accent', None, rx=2); f.t(x0 + 206, 57, 'candidate (v6 수정군 · 정면 30 % + 1500회 거리 승급)', 11, '--ink-2')
    for p in (0, 25, 50, 75, 100):
        x = x0 + bw * p / 100
        f.l(x, y0 - 6, x, y0 + rh * len(V14) - 6, '--rule-2', 1)
        f.t(x, y0 + rh * len(V14) + 8, f'{p} %', 10, '--ink-3', anchor='middle', mono=True)
    for i, (nm, n, a, b) in enumerate(V14):
        y = y0 + i * rh
        last = nm == '합계'
        if last:
            f.l(0, y - 8, 900, y - 8, '--rule', 1)
        f.t(0, y + 13, nm, 12.5, weight=700 if last else 500)
        f.t(0, y + 29, f'n = {n}', 10, '--ink-3', mono=True)
        for k, (v, col) in enumerate(((a, '--ink-3'), (b, '--accent'))):
            yy = y + k * 17
            f.r(x0, yy, bw * v / n, 13, col, None, rx=2)
            lo, hi = wilson(v, n)
            f.l(x0 + bw * lo, yy + 6.5, x0 + bw * hi, yy + 6.5, '--ink', 1.1)
            f.t(x0 + bw + 14, yy + 11, f'{v}/{n}', 11, '--ink' if k else '--ink-2', mono=True, weight=700 if k else 400)
            f.t(x0 + bw + 84, yy + 11, f'{100 * v / n:.1f} %', 11, '--ink-2', mono=True)
    f.t(0, 538, '「가까운 정면」은 move 안의 부분집합(거리 ≤ 1.5 m · 0°) 이라 합계에 따로 더하지 않는다 · 물리 실패 control 154 · candidate 70', 11, '--ink-2')
    return f.save()


# ---------------------------------------------------------------- 5. 1500 → 2000
def fig_1500():
    f = Fig('ame2-v14-1500-2000', 900, 330, 'v14 1500회와 2000회 사이에 갈린 것')
    f.t(0, 14, '1500회에는 합계가 813 으로 같았다 · 차이는 거리 승급 뒤 500회에서 생겼다', 15, weight=700)
    f.t(0, 34, '1500→2000 구간은 candidate 만 학습 거리 1~2.5 m (control 은 1~1.5 m) · 근거 comparison_1500.json · comparison_2000.json · candidate/curriculum_decision_1500.json', 11, '--ink-2')
    panels = [('합계 성공', 1040, (813, 850), (813, 885), (780, 900)), ('sequence 성공', 40, (33, 25), (17, 37), (10, 40)),
              ('물리 실패 (적을수록 좋음)', 1040, (139, 154), (156, 70), (50, 170))]
    pw, gap, top, ph = 270, 45, 78, 190
    for i, (nm, n, c, k, (lo, hi)) in enumerate(panels):
        x = i * (pw + gap)
        f.r(x, top - 22, pw, ph + 70, '--card', '--rule')
        f.t(x + 14, top, nm, 13, weight=700)
        f.t(x + pw - 14, top, f'/ {n}', 11, '--ink-3', anchor='end', mono=True)
        X1, X2 = x + 60, x + pw - 70
        Y = lambda v: top + 30 + ph * (1 - (v - lo) / (hi - lo)) * 0.82
        f.l(X1, top + 22, X1, top + ph + 12, '--rule', 1); f.l(X2, top + 22, X2, top + ph + 12, '--rule', 1)
        f.t(X1, top + ph + 30, '1500회', 11, '--ink-2', anchor='middle'); f.t(X2, top + ph + 30, '2000회', 11, '--ink-2', anchor='middle')
        for (a, b), col, nmb in ((c, '--ink-3', 'control'), (k, '--accent', 'candidate')):
            f.l(X1, Y(a), X2, Y(b), col, 2.4)
            f.c(X1, Y(a), 4.5, col); f.c(X2, Y(b), 4.5, col)
            f.t(X2 + 10, Y(b) + 4, f'{b}', 12, col if col == '--accent' else '--ink-2', mono=True, weight=700)
        same = c[0] == k[0]
        if same:
            f.t(X1 - 10, Y(c[0]) + 4, f'{c[0]}', 12, '--ink', anchor='end', mono=True, weight=700)
        else:
            for (a, _), col in ((c, '--ink-2'), (k, '--dim-ink')):
                f.t(X1 - 10, Y(a) + 4, f'{a}', 12, col, anchor='end', mono=True)
    f.t(0, 326, '회색 control · 청록 candidate · 학습 시드가 갈래당 1개라 「1500회 동률 → 2000회 차이」가 학습 경로 변동인지 처치 효과인지 가를 수 없다', 11, '--warn')
    return f.save()


# ---------------------------------------------------------------- 6. 같은 잣대 v11 → v13
def fig_ruler():
    f = Fig('ame2-same-ruler', 900, 390, '같은 20초 잣대로 다시 잰 v11 과 v13')
    f.t(0, 14, '서사 v4→v5 의 큰 도약은 보상 · 학습량 · 마감 세 가지가 함께 바뀐 결과다', 15, weight=700)
    f.t(0, 34, '세 모델을 모두 20초 판정으로 다시 잰 값 · 근거 reports/flat_precise_arrival_v13_20261006/REPORT_ko.txt', 11, '--ink-2')
    tasks = [('move', 320), ('pose', 320), ('turn', 280), ('stand', 80), ('sequence', 40)]
    models = [('v11 · 500회 (서사 v4)', [38, 23, 224, 80, 0], 365, '--ink-soft'), ('v13 · 500회 (보상만 바꿈)', [54, 87, 170, 80, 0], 391, '--ink-3'),
              ('v13 · 1000회 (서사 v5)', [186, 239, 277, 80, 28], 810, '--accent')]
    x0, gw, bh, base = 40, 168, 190, 320
    for g, (tn, n) in enumerate(tasks):
        gx = x0 + g * gw
        for m, (mn, vals, tot, col) in enumerate(models):
            v = vals[g]; h = bh * v / n; bx = gx + m * 40
            f.r(bx, base - h, 32, max(h, 1.5), col, None, rx=2)
            f.t(bx + 16, base - h - 6, f'{v}', 10.5, '--ink-2', anchor='middle', mono=True)
        f.t(gx + 56, base + 18, tn, 12, anchor='middle', weight=600)
        f.t(gx + 56, base + 34, f'/ {n}', 10, '--ink-3', anchor='middle', mono=True)
    f.l(x0 - 6, base, x0 + 5 * gw - 30, base, '--rule', 1)
    for m, (mn, vals, tot, col) in enumerate(models):
        x = m * 300
        f.r(x, 56, 14, 10, col, None, rx=2)
        f.t(x + 20, 66, mn, 11.5, '--ink-2')
        f.t(x + 20, 86, f'합계 {tot}/1040', 11.5, '--ink', mono=True, weight=700)
    f.t(0, 382, '석헌이 쓴 v4 숫자(37 · 23 · 224)는 8초 판정이다. 20초로 다시 재면 38 · 23 · 224 · v13 500회는 turn 이 224 → 170 으로 내려갔다', 11, '--warn')
    return f.save()


# ---------------------------------------------------------------- 7. Nav2 와 붙이는 자리
def fig_iface():
    f = Fig('ame2-nav2-interface', 900, 380, 'AME-2 의 목표 자세 명령과 Nav2 속도 명령 사이')
    f.t(0, 14, 'AME-2 는 속도가 아니라 「어디에 어느 방향으로 서라」를 받는다', 15, weight=700)
    f.t(0, 34, '근거: 보고서 2.2 · 10.2절 · docs/AME2_HiPAN_Integration_Review_ko.md 3절 · docs/AME2_PGCL_Navigation_Spec_ko.md (9/22 설계 · 실행 전)', 11, '--ink-3', mono=True)
    def box(x, y, w, h, a, b=None, fill='--card', stroke='--rule', dash=False):
        f.r(x, y, w, h, fill, stroke, dash=dash)
        f.t(x + w / 2, y + (h / 2 + 4 if not b else h / 2 - 3), a, 12, anchor='middle', weight=600)
        if b:
            f.t(x + w / 2, y + h / 2 + 14, b, 10.5, '--ink-2', anchor='middle', mono=True)
    y = 60
    f.t(0, y, '지금 우리 foothold 계열', 12.5, '--accent', weight=700)
    box(0, y + 12, 170, 48, 'Nav2 planner', '전역 경로')
    box(220, y + 12, 170, 48, 'Nav2 controller', 'cmd_vel')
    box(440, y + 12, 220, 48, 'foothold 정책', 'lin_vel_x · ang_vel_z', '--accent-soft', '--accent')
    f.l(170, y + 36, 218, y + 36, arrow=True); f.l(390, y + 36, 438, y + 36, arrow=True)
    f.t(680, y + 41, '명령 모양이 그대로 맞는다', 11.5, '--ok')
    y = 150
    f.t(0, y, 'AME-2 를 붙이려면 (둘 다 아직 안 해 봄 · 추정)', 12.5, '--warn', weight=700)
    box(0, y + 12, 170, 48, 'Nav2 planner', '전역 경로')
    box(220, y + 12, 170, 48, '(가) 앞쪽 지점 고르기', 'controller 우회', '--card', '--warn', dash=True)
    box(440, y + 12, 220, 48, 'AME-2 정책', '[dx, dy, sin ψ, cos ψ]', '--warn-soft', '--warn')
    f.l(170, y + 36, 218, y + 36, arrow=True); f.l(390, y + 36, 438, y + 36, arrow=True)
    box(220, y + 76, 170, 48, '(나) cmd_vel × Δt', '→ 목표 자세', '--card', '--bad', dash=True)
    f.l(390, y + 100, 438, y + 60, arrow=True)
    f.t(680, y + 30, '(가) 경로 지점 추종형', 11.5, '--ink-2')
    f.t(680, y + 98, '(나) 속도·도착 시점을 강제 못 함', 11.5, '--bad')
    f.t(680, y + 116, '0.3 m 목표는 도착·정지 영역에 들어감', 11, '--ink-2')
    y = 300
    f.r(0, y, 900, 64, '--paper-2', None, rx=8)
    f.t(14, y + 24, '석헌 쪽 상위 설계 (HiPAN 검토 B 안 · PGCL)', 12.5, weight=700)
    f.t(14, y + 46, '상위 정책이 10 Hz 로 다음 목표 [dx, dy, dyaw] 를 내고 하위는 고정한 AME student 가 걷는다. student 가 아직 없어서 지금 바로는 못 돈다', 11.5, '--ink-2')
    return f.save()


def data():
    DAT.mkdir(parents=True, exist_ok=True)
    with open(DAT / 'ame2-v14-2000-by-task.csv', 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.writer(fh); w.writerow(['task', 'n', 'control_success', 'candidate_success', 'control_wilson95_lo', 'control_wilson95_hi', 'candidate_wilson95_lo', 'candidate_wilson95_hi'])
        for nm, n, a, b in V14:
            w.writerow([nm, n, a, b, *[f'{x:.4f}' for x in (*wilson(a, n), *wilson(b, n))]])
    rows = [
        ('서사 v1', 'experiment C (progress)', '9/24~9/28', '험지 0.5 m 도달 · 500회 44/400 → 1000회 75/400', 'reports/teacher_500_vs_1000_same_env_20260928/comparison_report_ko.md'),
        ('서사 v2', 'ame2_flat_goal_v7_fresh_3322', '9/29', 'move 0/320 · pose 0/320 · turn 0/280 · stand 0/80 (보정 판정 20/80) · sequence 0/40', 'reports/flat_fresh_3322_20260929/'),
        ('서사 v3', 'ame2_flat_goal_v8_reward_control', '9/29~9/30', 'stand 80/80 · 나머지 0', 'reports/flat_reward_control_v8_20260929/'),
        ('서사 v4', 'ame2_flat_goal_v11_move_focus', '9/30', '364/1040 (8초 판정) · 20초 재채점 365', 'reports/flat_move_focus_v11_20260930/'),
        ('서사 v5', 'ame2_flat_precise_arrival_v13_20261006', '10/6', '810/1040', 'reports/flat_precise_arrival_v13_20261006/'),
        ('서사 v6 (v5 설정 유지)', 'ame2_flat_recovery_v14_control_20261006', '10/6~10/7', '1500회 813 · 2000회 850/1040', 'reports/flat_recovery_v14_20261006/'),
        ('서사 v6 (수정군)', 'ame2_flat_recovery_v14_candidate_20261006', '10/6~10/7', '1500회 813 · 2000회 885/1040', 'reports/flat_recovery_v14_20261006/'),
    ]
    with open(DAT / 'ame2-versions.csv', 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.writer(fh); w.writerow(['narrative', 'internal_experiment', 'date_kst', 'result', 'source_on_volume']); w.writerows(rows)


if __name__ == '__main__':
    for fn in (fig_timeline, fig_system, fig_net, fig_v14, fig_1500, fig_ruler, fig_iface):
        print(fn().name)
    data(); print('csv ok')
