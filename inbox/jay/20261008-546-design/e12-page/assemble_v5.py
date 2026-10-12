# -*- coding: utf-8 -*-
"""page.html 4판 → 5판 조립 (lead · 10/13 아침). 원본은 page_v4.html 로 남긴다.
새 절: night · unseen · rg · cmdr · next · app (조각 v5_*.html · 숫자는 facts5_*.py 가 build 때 채움).
고치는 문구: ASTRA 13 (model_20000 경계 · 명령 확대는 원인으로 쓰지 않음) · 다음 실험 순서 (ASTRA 9 · 11 반영)."""
import io
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, 'page.html')
if not os.path.exists(os.path.join(HERE, 'page_v4.html')):
    shutil.copy2(P, os.path.join(HERE, 'page_v4.html'))
s = io.open(os.path.join(HERE, 'page_v4.html'), encoding='utf-8').read()
rd = lambda n: io.open(os.path.join(HERE, n), encoding='utf-8').read()


def rep(old, new, count=1):
    global s
    assert s.count(old) == count, ('찾는 문구 수가 다르다', old[:80], s.count(old))
    s = s.replace(old, new)


# ---------- 1. CSS ----------
rep('.quad{grid-template-columns:repeat(4,minmax(0,1fr))!important}',
    '''.quad{grid-template-columns:repeat(4,minmax(0,1fr))!important}
/* 5판 */
.vmode #night,.vmode #unseen,.vmode #rg,.vmode #cmdr,.vmode #next,.vmode #app{display:none}
.urow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:10px 0 14px}
@media (max-width:1100px){.urow{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:600px){.urow{grid-template-columns:1fr}}
.sub2{color:var(--ink-3);font-size:12px;font-weight:400}
table.def.unseen td{font-family:var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap}
table.def.unseen th[scope="row"]{white-space:nowrap;color:var(--ink);font-size:13.5px;font-weight:500}
table.def.unseen th[scope="row"] .sub2{display:block}
table.def.night td:first-child{font-family:var(--sans);font-weight:600;font-size:14px;white-space:nowrap}
table.def.night td:nth-child(3){color:var(--ink-2);font-size:13.5px;min-width:15em}
table.def.night td:nth-child(4){font-size:13.5px;min-width:12em}
table.def.night{min-width:900px}
.split .tbl table.def.wrap td:not(:first-child){white-space:normal}
.split .tbl table.def.wrap td:first-child,.split .tbl table.def.wrap th{white-space:nowrap}
.urow .tile .tag{flex:none}
.urow .tile .th{flex-wrap:wrap}
.superseded{margin:6px 0 10px;padding:8px 12px;background:var(--note-soft);color:var(--note-ink);border-radius:6px;font-size:13.5px}''')

# ---------- 2. 머리 ----------
rep('<div class="kicker">FOOTHOLD · 시뮬 RL · 2026-10-12</div>', '<div class="kicker">FOOTHOLD · 시뮬 RL · 2026-10-13 아침</div>')
rep('결론이 아니라 <b>중간 정리</b> 입니다.</p>',
    '결론이 아니라 <b>중간 정리</b> 입니다. 5판은 밤사이 결과 (v2 의 미경험 지형 10 종 · 다른 물리 엔진 시험 · CMD-R 진행) 와 다음 실험 계획을 위에 더했습니다.</p>')
rep('<span class="num">model_20000</span> = 명령 상한 0.5 m/s 로 학습한 끝 · <span class="num">model_20499</span> = 상한을 1.0 m/s 로 넓힌 뒤 500 iteration',
    '<span class="num">model_20000</span> = 대부분 명령 상한 0.5 m/s 로 학습 · 상한을 1.0 m/s 로 넓힌 첫 학습 한 번 포함 · <span class="num">model_20499</span> = 그 뒤 499 iteration')
rep('<dt>작성</dt><dd>오흥재 (lead 세션 · Claude 실행) · 2026-10-12</dd>',
    '<dt>작성</dt><dd>오흥재 (lead 세션 · Claude 실행) · 2026-10-12 · 5판 2026-10-13</dd>')
rep('v2 모델 카드 <code>models/foothold-v2.json</code>. 이 페이지의 숫자는 생성 스크립트가 원자료에서 읽어 넣었습니다</dd>',
    'v2 모델 카드 <code>models/foothold-v2.json</code> · 미경험 지형 <code>un_*</code> 100 실행 · RoboGauge 원출력 7 개 · CMD-R 학습 · 평가 로그 · ASTRA 검증 7 ~ 14. 이 페이지의 숫자는 생성 스크립트가 원자료에서 읽어 넣었습니다</dd>')
rep('<dt>요지</dt><dd>걷기 통과 · 멈추기 약점 · 20499 하락은 명령 범위를 넓힌 직후 · 지형을 보지 않아 gap · 징검다리는 아직 못 배움</dd>',
    '<dt>요지</dt><dd>걷기 통과 · 멈추기 약점 · 20499 는 명령 범위를 넓힌 직후 하락 (원인 미확인) · v2 미경험 지형에서 gap · 징검다리는 기준선에 거의 · 전혀 못 닿음 (원인 미확인) · 다른 엔진 시험은 20499 가 높아 두 시험이 다른 능력을 잼 · 다음은 같은 시험지부터</dd>')
rep('<dt>상태</dt><dd>4판 (10/12 밤) · 중간 정리 · v2 와 비교 · 쉬운 설명 추가 · 판정 기준 (Q) 은 lead 임시 조건이며 팀장 확정 전 · 학습은 Linux 이전까지 멈춤</dd>',
    '<dt>상태</dt><dd>5판 (10/13 아침) · 밤사이 결과 · CMD-R 은 진행 중 (최종 24,000 비교는 낮에 갱신) · 판정 기준 (Q) 은 lead 임시 조건 · ASTRA 14 로 미경험 지형 해석 고침</dd>')

# ---------- 3. 중간 정리 ----------
rep('<li><b>20,499 가 20,000 보다 나쁜 것은 명령 범위를 두 배로 넓힌 직후이기 때문으로 보입니다</b> (추정 · <a href="#drop">아래</a>).</li>',
    '<li><b>20,499 는 20,000 보다 우리 시험에서 나쁩니다.</b> 명령 범위를 두 배로 넓힌 직후에 나빠졌지만, 범위를 넓힌 것이 원인인지는 아직 모릅니다 (<a href="#drop">아래</a>). 다른 물리 엔진 시험에서는 반대로 20,499 가 높습니다 (<a href="#rg">위</a>).</li>')
rep('<li><b>gap · 징검다리는 이 실험으로는 못 배웁니다.</b> 배포하는 student 가 지형을 보지 않고, 학습 지형에 그 둘이 0 % 입니다 (<a href="#gap">아래</a>).</li>',
    '<li><b>gap · 징검다리에 약합니다.</b> 지금 student 는 높이 지도를 받지 않고, 두 지형을 학습한 비율도 0 % 입니다. v2 의 미경험 지형 시험에서 0.5 m/s 이하 gap 기준선 도달은 0 ~ 4 %, 징검다리는 0 % 였습니다 (<a href="#unseen">위</a>). 지도가 없어서인지 · 학습 지형 때문인지 · 다른 조건 때문인지는 아직 나누지 않았습니다.</li>')
rep('<li>20,499 의 하락이 학습을 더 하면 회복되는지. 저장소 기본 학습 길이는 300,000 iteration 인데 우리는 20,500 에서 멈췄습니다.</li>',
    '<li>20,499 의 하락이 학습을 더 하면 회복되는지. 밤에 E1 20,000 에서 4,000 iteration 이어 학습한 CMD-R 「안 고친」 갈래가 첫 관찰입니다 (<a href="#cmdr">위</a>).</li>')
rep('<li>다음 학습 순서 (팀장 결정): gap 을 학습 지형에 넣기 → student 에게 지형 지도 주기 → 마지막에 AME-2. Linux 로 옮긴 뒤 돌립니다.</li>',
    '<li>다음 순서 (팀장 확인 전): 같은 시험지 → Linux 이전 → 「지도를 주면 달라지나」 한 시드 예비 (<a href="#next">위</a>).</li>')

# ---------- 4. 새 절 (중간 정리 바로 뒤) ----------
i = s.index('<section id="why">')
new = ''.join(rd(n).strip('\n') + '\n\n' for n in ('v5_night.html', 'v5_unseen.html', 'v5_rg.html', 'v5_cmdr.html', 'v5_next.html', 'v5_app.html'))
s = s[:i] + new + s[i:]

# ---------- 5. 20499 절 (ASTRA 13) ----------
rep('20,000 까지 정책은 바로 그 범위만 연습했고, 20,000 부터는 1.0 m/s 까지 빠른 명령을 연습하기 시작했습니다.',
    '20,000 앞까지의 학습은 대부분 그 범위에서 했고, 20,000 부터 1.0 m/s 까지 빠른 명령을 연습하기 시작했습니다 (model_20000 은 넓힌 첫 iteration 의 학습을 한 번 포함합니다 · ASTRA 13).')
i0 = s.index('<p><b>확인하는 방법</b>: 20,500 에서 이어 학습해')
i1 = s.index('</p>', i0) + len('</p>')
s = s[:i0] + ('<p><b>확인하는 방법</b>: 이어 학습한 체크포인트에서 저속 · 멈춤 판정이 돌아오는지 같은 시험지로 봅니다. '
              '밤에 돌린 CMD-R 「안 고친」 갈래 (E1 20,000 에서 넓힌 범위 그대로 4,000 iteration · 시드 1042) 가 그 첫 관찰입니다 (<a href="#cmdr">CMD-R 절</a>). '
              '범위를 넓히지 않고 같은 만큼 더 학습한 대조가 없으므로, 돌아오든 돌아오지 않든 「범위 확대가 원인」 이라고는 쓰지 않습니다 (ASTRA 13 · 15).</p>') + s[i1:]

# ---------- 6. gap 절의 옛 순서 ----------
rep('<h3>다음 실험 순서 (설계 문서 · 팀장 결정 대기)</h3>',
    '<h3>다음 실험 순서 (10/12 설계 문서)</h3>\n      <p class="superseded">10/13 에 바뀌었습니다. G1 은 따로 돌리지 않고, P1 자리는 「이상적 지도 입력 비교」 한 시드 예비가 되며, 그 앞에 v2 와 같은 시험지를 먼저 세웁니다 (ASTRA 9 · 11 · <a href="#next">다음 실험 절</a>). 아래는 기록으로 남깁니다.</p>')

# ---------- 7. 결론 항목 ----------
rep("20,000 에서 명령 범위를 두 배로 넓힌 직후라 생긴 흔들림으로 보입니다 (추정 · <a href=\"#drop\">20499 절</a>).",
    "20,000 에서 명령 범위를 두 배로 넓힌 직후입니다. 원인은 아직 모릅니다 (<a href=\"#drop\">20499 절</a>).")
rep("학습 지형에도 0 % 입니다. 다음 단계는 gap 을 연습시키고, student 에게 지도를 주는 순서입니다 (<a href=\"#gap\">gap 절</a>).",
    "학습 지형에도 0 % 이고, v2 의 미경험 지형 시험에서도 0.5 m/s 이하 gap 기준선 도달 0 ~ 4 % · 징검다리 0 % 입니다. 다음은 같은 시험지를 세운 뒤 「지도를 주면 달라지나」 를 봅니다 (<a href=\"#next\">다음 실험 절</a>).")

# ---------- 7b. ASTRA 15 (4판에서 이어진 문장의 범위 · 인과 · 시제) ----------
rep('학습 지형 8 종 × 명령 11 가지 × 출발 자리 두 종류 = 116 칸을 칸마다 100 판씩 평가했습니다.',
    '가운데 출발 8 지형 × 명령 11 가지 88 칸과 띠 출발 7 지형 × 명령 4 가지 28 칸, 합계 116 칸을 칸마다 100 판씩 평가했습니다.')
rep('0.3 m/s 로 걷다 멈추라고 하면 4 cm 안에서 서지만, 1 초 동안 완전히 가만히 있지를 못합니다. 센서 noise 를 켜면 거의 다 실패합니다 (<a href="#noise">아래</a>).',
    '0.3 m/s 로 걷다 멈추면 대개 몇 cm 안에서 서지만 (예: E1 20,499 평지 · noise 켬, 멈춘 뒤 이동 중앙값 약 3.9 cm), 1 초 동안 정지 문턱 안에 머무는 판은 적습니다 (같은 칸 100 판 중 6 판). noise 를 켜면 대부분 미달입니다 (<a href="#noise">아래</a>).')
rep('<li>판정 기준 (팀장 결정): 경계 (기준 ±10 %) 를 통과로 셀지 · 저속 명령은 비율로 잴지 · noise 켬을 주 조건으로 할지.</li>',
    '<li>기존 Q 의 판정 기준 (팀장 결정 대기): 경계 (기준 ±10 %) 를 통과로 셀지 · 저속 명령은 비율로 잴지 · noise 켬을 주 조건으로 할지. CMD-R 은 따로 정한 상대 오차 · noise 켬 주 조건을 씁니다.</li>')
rep('<h3>지금 못 하는 까닭 (코드로 확인)</h3>', '<h3>코드로 확인한 제약과 원인 후보</h3>')
rep('<li><b>볼 수 없습니다.</b> 배포 student 는 지형을 보지 않습니다. 틈은 발이 빠진 다음에야 압니다. 앞발이 허공을 디디면 그때는 이미 늦습니다.</li>',
    '<li><b>앞의 높이를 직접 받지 않습니다.</b> 배포 student 의 입력에 높이 지도가 없습니다 (코드로 확인). 발 접촉 · 몸 상태 이력으로 반응할 여지는 있고, 이번 취약성의 원인이 이것인지는 나누지 않았습니다.</li>')
rep('그래서 미경험 험지를 건너려면 <b>① 그런 지형을 연습하고 ② 앞의 지형을 보고 ③ 발 놓을 곳을 고르는</b> 세 가지가 필요합니다. 이번 E1 · E2 는 그 셋이 모두 없는 상태의 기준선입니다.',
    '그래서 <b>학습 지형 · 앞쪽 관측 · 발 디딤 제어</b> 가 원인 후보입니다. 다음 비교는 이상적 지도 입력의 효과부터 가립니다 (<a href="#next">다음 실험 절</a>).')
rep('새 명령에 맞는 걸음을 찾느라 다시 넓게 탐색한다는 뜻입니다.', '명령 확대에 적응하려는 탐색이라는 설명은 가설입니다.')
rep('<li><b>평가 칸이 떨어진 쪽으로만 움직였습니다.</b> 칸 × 시드 × noise %%drop_n%% 개 가운데 10 pp 넘게 떨어진 것이 %%drop10%% 개, 10 pp 넘게 오른 것은 %%rise10%% 개입니다.',
    '<li><b>10 pp 이상 큰 변화는 떨어진 쪽에서만 보였습니다.</b> 칸 × 시드 × noise %%drop_n%% 개 가운데 10 pp 이상 떨어진 것이 %%drop10%% 개, 10 pp 이상 오른 것은 %%rise10%% 개입니다.')
rep('<dd>아닙니다. 설계 문서는 E1 의 20,000 체크포인트를 부모로 삼아 「gap 10 %」 군과 「gap 0 %」 대조군을 각각 +8,000 iteration 이어 학습합니다 (G1). student 에게 지도를 줄 때 (P1) 도 부모 가중치를 옮기고 새로 생긴 입력 부분만 초기화합니다.',
    '<dd>아닙니다. 10/12 설계 문서 (이전안) 는 E1 의 20,000 체크포인트를 부모로 삼아 「gap 10 %」 군과 「gap 0 %」 대조군을 각각 +8,000 iteration 이어 학습하는 G1 이었지만, 10/13 에 공통 평가 뒤 같은 희소 지형 학습의 「이상적 지도 입력 비교」 예비로 바뀌었습니다 (<a href="#next">다음 실험 절</a>). 부모 가중치를 옮기고 새로 생긴 입력 부분만 초기화하는 방법은 그대로 쓸 수 있습니다.')
rep('v2 의 미경험 지형 10 종 (gap · 징검다리 · pit · 레일 등) 은 E1 · E2 로 아직 안 쟀습니다. 10/12 밤부터 GPU 1 에서 평가를 만들고 있습니다 (결과 · 실패 영상은 다음 판에).',
    'v2 의 미경험 지형 10 종 (gap · 징검다리 · pit · 레일 등) 은 10/13 밤에 100 조건 · 1 만 판을 평가했고 대표 영상 144 편을 얻었습니다 (<a href="#unseen">미경험 지형 절</a>).')
rep('4,000 iteration 씩 차례로 학습합니다 (env 8,192 · 아침 9 시쯤 끝). 멈추기 · 저속 약점이 그 치우침 때문인지 가립니다. ASTRA 가 띄운 조건을 검증하고 있습니다 (의뢰 7). GPU 1 · CPU: 미경험 지형 평가와 RoboGauge.',
    '4,000 iteration 씩 차례로 학습합니다 (env 8,192). 멈추기 · 저속 약점이 그 치우침 때문인지 가립니다. <span class="sub">(10/12 밤에 쓴 답 · 지금 상태는 <a href="#night">밤사이 한 일</a> 표)</span>')
rep("['b', `<b>지형을 보지 않는 정책이라 gap · 징검다리는 아직 못 배웁니다.</b>",
    "['b', `<b>gap · 징검다리에 약합니다 (원인은 아직 나누지 않음).</b> 지금 student 는 높이 지도를 받지 않고,")

# ---------- 8. 질답 (10/13 더함 · RoboGauge 설명은 ASTRA 13 으로 바로잡음) ----------
rep('<h2>팀장 질문과 답 (10/12 밤)</h2>', '<h2>팀장 질문과 답 (10/12 밤 · 10/13 더함)</h2>')
rep('<dl class="qa">\n    <div><dt>RoboGauge 는 무엇을 재고, 우리도 써야 하나</dt>',
    '<dl class="qa">\n' + rd('v5_qa_add.html').rstrip('\n') + '\n    <div><dt>RoboGauge 는 무엇을 재고, 우리도 써야 하나</dt>')
rep('명령 지연 · 몸통 무게 −1 ~ +3 kg · 마찰 0.2 ~ 1.0 을 무작위로 건 채 평지 · 물결 · 경사 · 계단 오르기 / 내리기 · 장애물을 난이도별로 걷습니다. 속도 오차 · 관절 한계 · 전력 · 몸 흔들림 · 토크 매끄러움 · 미끄러짐 여유 등 8 개 지표를 0 ~ 1 로 매기고, 시드 셋이 모두 통과한 최고 난이도를 Level 로 냅니다.',
    '평지 · 물결 · 경사 앞으로 / 뒤로 · 계단 앞으로 / 뒤로 · 장애물 7 과제를 마찰 9 가지 (0.2 ~ 1.0 고정) 에서, 0 ~ 18 ms 명령 지연과 관측 잡음을 건 채 걷습니다 (이번 실행은 몸통 무게를 바꾸지 않았습니다). 「뒤로」 는 같은 경사 · 계단을 뒤로 걸어 오르는 과제입니다. 탐색용 시드 0 ~ 4 의 다섯 번 가운데 네 번 이상 목표에 닿는 단계를 이진 탐색으로 찾고 (Level), 그 단계에서 속도 추종 · 관절 한계 · 전력 · 자세 등 8 개 지표로 품질을 매겨 합칩니다 (ASTRA 13 이 코드에서 확인해 바로잡음).')
rep('<span class="sub">10/12 밤부터 CPU 로 돌리는 중입니다. 저자 정책 (이름에 0.6953) 으로 먼저 같은 점수가 나오는지 확인한 뒤 E1 · E2 를 잽니다. 결과 · 영상은 다음 판에.</span>',
    '<span class="sub">10/13 01:45 에 끝났습니다. 저자 정책 0.6953 을 0.6954 로 재현했고, 결과는 <a href="#rg">RoboGauge 절</a> 에 있습니다.</span>')

rep('v2 는 지도 입력 235 칸이라 RoboGauge 로 못 잽니다.',
    'v2 는 입력 235 칸 가운데 높이가 187 칸이라 지금 adapter 로는 바로 못 잽니다 (v2 관측 · 출력 adapter 와 높이 생성 경로를 만들고 검증해야 합니다).')

io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
print('page.html 5판 조립 끝', len(s))
