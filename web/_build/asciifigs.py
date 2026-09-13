# -*- coding: utf-8 -*-
"""원본의 ASCII 아트 도식(<pre class="dia">)을 SVG 도식으로 교체한다.

  ┌─────┐ 같은 박스 그림은 폰트·자간에 따라 어긋나고, 모바일에서 줄이 깨지고,
  PDF에서도 정렬이 무너진다. 내용은 그대로 두고 표현만 바꾼다.

  키 = 원본 <pre> 안의 고유 문자열. 원본이 바뀌어 키를 못 찾으면 빌드가 알려준다.
"""

W = 420


def fig(svg, cap, h):
    return ('\n<figure class="fdia">\n<svg viewBox="0 0 %d %d" role="img">%s</svg>\n'
            '<figcaption>%s</figcaption>\n</figure>\n' % (W, h, svg, cap))


def chip(x, y, t, cls='c-n', w=25):
    """단계 칩 하나"""
    return ('<rect x="%g" y="%g" width="%g" height="15" rx="3" class="%s-b"/>'
            '<text x="%g" y="%g" class="%s-t">%s</text>'
            % (x, y, w, cls, x + w / 2, y + 10.8, cls, t))


def row(y, items, label, x0=30):
    """칩 한 줄 + 오른쪽 설명"""
    s, x = '', x0
    for t, on in items:
        s += chip(x, y, t, 'c-k' if on else 'c-n')
        x += 29
    s += '<text x="392" y="%g" class="a-lab">%s</text>' % (y + 10.6, label)
    return s


# ══════════════════ #1 전체 구조 ══════════════════
STRUCT = fig('''
<rect x="16" y="20" width="388" height="126" class="s-secA"/>
<text x="30" y="36" class="a-h">구간 A · 공통 기반</text>
<text x="392" y="36" class="a-h-r">전원 동일 · 17단계</text>
<line x1="30" y1="42" x2="390" y2="42" class="a-rule"/>
''' + row(50, [('A1', 0), ('A2', 0), ('A3', 0), ('A4', 0), ('A5', 1)], '로봇과 제어를 이해')
   + row(72, [('A6', 1), ('A7', 0)], '직접 만져본다')
   + row(94, [('A8', 0), ('A9', 0), ('A10', 1), ('A11', 0)], '강화학습을 겪는다')
   + row(116, [('A12', 1), ('A13', 0), ('A14', 0), ('A15', 0), ('A16', 0), ('A17', 0)], '우리 것으로 좁힌다') + '''
<line x1="210" y1="146" x2="210" y2="164" class="a-flow"/>
<polygon points="210,170 205,160 215,160" class="a-fill-ink"/>

<rect x="16" y="172" width="388" height="88" class="s-secB"/>
<text x="30" y="188" class="a-h">구간 B · 작업 영역별</text>
<text x="392" y="188" class="a-h-r">여덟 갈래</text>
<line x1="30" y1="194" x2="390" y2="194" class="a-rule"/>
<g class="a-branch">
<rect x="30" y="202" width="84" height="22" class="c-b-b"/><text x="72" y="216" class="c-b-t">A 정책학습</text>
<rect x="122" y="202" width="84" height="22" class="c-b-b"/><text x="164" y="216" class="c-b-t">A 지형씬</text>
<rect x="214" y="202" width="84" height="22" class="c-b-b"/><text x="256" y="216" class="c-b-t">A 평가</text>
<rect x="306" y="202" width="84" height="22" class="c-b-b"/><text x="348" y="216" class="c-b-t">A 트윈렌더</text>
<rect x="30" y="228" width="84" height="22" class="c-b-b"/><text x="72" y="242" class="c-b-t">B 항법</text>
<rect x="122" y="228" width="84" height="22" class="c-b-b"/><text x="164" y="242" class="c-b-t">B 인지</text>
<rect x="214" y="228" width="84" height="22" class="c-b-b"/><text x="256" y="242" class="c-b-t">C 기록</text>
<rect x="306" y="228" width="84" height="22" class="c-b-b"/><text x="348" y="242" class="c-b-t">C 운영</text>
</g>

<line x1="210" y1="260" x2="210" y2="278" class="a-flow"/>
<polygon points="210,284 205,274 215,274" class="a-fill-ink"/>

<rect x="16" y="286" width="388" height="48" class="s-secC"/>
<text x="30" y="302" class="a-h">구간 C · 실전</text>
<text x="392" y="302" class="a-h-r">다시 다 같이</text>
<line x1="30" y1="308" x2="390" y2="308" class="a-rule"/>
''' + ''.join(chip(30 + i * 46, 314, 'C%d' % (i + 1), 'c-k' if i == 5 else 'c-n', 42)
              for i in range(8)) + '''
''',
'<b>구간 A는 다섯 명이 똑같이 지납니다.</b> 그 뒤에야 여덟 갈래로 나뉘고, 실전에서 다시 합쳐집니다. '
'갈래는 사람 수가 아니라 <b>일의 종류</b>입니다. 한 사람이 둘을 맡기도 합니다. '
'초록 칩(A5·A6·A10·A12·C6)은 <b>관문</b>입니다. 여기서 막히면 다음으로 못 갑니다.', 342)


# ══════════════════ #2 A4 · PD 공식 ══════════════════
PD = fig('''
<text x="210" y="16" class="a-h-c">토크를 만드는 한 줄</text>
<rect x="16" y="26" width="388" height="40" class="s-formula"/>
<text x="210" y="52" class="a-formula">토크 = <tspan class="a-kp">kp</tspan> × (목표각도 − 현재각도)  +  <tspan class="a-kd">kd</tspan> × (0 − 현재속도)</text>

<line x1="92" y1="76" x2="92" y2="90" class="a-tie-kp"/>
<line x1="316" y1="76" x2="316" y2="90" class="a-tie-kd"/>

<rect x="24" y="92" width="176" height="44" class="s-term-kp"/>
<text x="112" y="109" class="a-term-h-kp">멀리 있으면 세게 당긴다</text>
<text x="112" y="126" class="a-term-b">목표에서 벗어난 만큼 비례해 힘을 준다</text>

<rect x="220" y="92" width="176" height="44" class="s-term-kd"/>
<text x="308" y="109" class="a-term-h-kd">빨리 움직이면 브레이크</text>
<text x="308" y="126" class="a-term-b">속도가 붙으면 반대로 눌러 진동을 막는다</text>
''',
'<b>PD 제어는 이 한 줄이 전부입니다.</b> 앞항이 “목표로 끌어당기는 힘”, 뒷항이 “너무 빨리 가지 않게 잡는 힘”. '
'로봇이 뻣뻣하거나 흐물거리는 이유가 전부 이 두 숫자에 있습니다.', 146)


# ══════════════════ #3 A5 · 제어 루프 6단계 ══════════════════
LOOP = fig('''
<text x="210" y="16" class="a-h-c">한 바퀴가 이렇게 돕니다</text>

<rect x="52" y="26" width="316" height="46" class="s-step-d"/>
<text x="66" y="43" class="a-sn">①</text><text x="86" y="43" class="a-st">관측: 숫자 47개</text>
<text x="86" y="58" class="a-sb">관절각 12 · 관절속도 12 · IMU 6 · 명령속도 3 · 직전행동 12 · 보행위상 2</text>

<line x1="210" y1="72" x2="210" y2="84" class="a-flow"/><polygon points="210,90 205,80 215,80" class="a-fill-ink"/>
<text x="222" y="83" class="a-hz">초당 50번</text>

<rect x="52" y="92" width="316" height="30" class="s-step-hi"/>
<text x="66" y="111" class="a-sn">②</text><text x="86" y="111" class="a-st">정책 <tspan class="a-sb2">(신경망): 우리가 학습시키는 유일한 것</tspan></text>

<line x1="210" y1="122" x2="210" y2="132" class="a-flow"/><polygon points="210,138 205,128 215,128" class="a-fill-ink"/>

<rect x="52" y="140" width="316" height="26" class="s-step-n"/>
<text x="66" y="157" class="a-sn">③</text><text x="86" y="157" class="a-st">목표 관절각 12개</text>

<line x1="210" y1="166" x2="210" y2="176" class="a-flow"/><polygon points="210,182 205,172 215,172" class="a-fill-ink"/>
<text x="222" y="175" class="a-hz">초당 500번</text>

<rect x="52" y="184" width="316" height="26" class="s-step-n"/>
<text x="66" y="201" class="a-sn">④</text><text x="86" y="201" class="a-st">PD 제어기</text>

<line x1="210" y1="210" x2="210" y2="220" class="a-flow"/><polygon points="210,226 205,216 215,216" class="a-fill-ink"/>

<rect x="52" y="228" width="316" height="26" class="s-step-n"/>
<text x="66" y="245" class="a-sn">⑤</text><text x="86" y="245" class="a-st">모터 토크 <tspan class="a-sb2">→ 다리가 실제로 움직임</tspan></text>

<line x1="210" y1="254" x2="210" y2="264" class="a-flow"/><polygon points="210,270 205,260 215,260" class="a-fill-ink"/>

<rect x="52" y="272" width="316" height="26" class="s-step-n"/>
<text x="66" y="289" class="a-sn">⑥</text><text x="86" y="289" class="a-st">물리 <tspan class="a-sb2">: 땅에 닿고, 미끄러지고, 자세가 바뀜</tspan></text>

<path d="M52,285 L28,285 L28,49 L52,49" class="a-loop"/>
<polygon points="58,49 48,44 48,54" class="a-fill-dim"/>
<text x="22" y="170" class="a-loop-lab" transform="rotate(-90 22 170)">자세가 바뀌었으니 관측도 바뀐다</text>
''',
'<b>A2·A3·A4가 여기서 합쳐집니다.</b> ①에서 ⑥까지가 한 바퀴이고, 그 바퀴가 초당 50번 돕니다. '
'우리가 학습으로 바꾸는 것은 <b>② 하나뿐</b>입니다.', 306)


# ══════════════════ #4 A8 · 강화학습 순환 ══════════════════
RL = fig('''
<text x="210" y="16" class="a-h-c">강화학습은 이 순환이 전부입니다</text>

<rect x="24" y="34" width="96" height="34" rx="4" class="s-step-hi"/>
<text x="72" y="55" class="a-node">정책</text>

<line x1="124" y1="51" x2="152" y2="51" class="a-flow"/><polygon points="158,51 148,46 148,56" class="a-fill-ink"/>
<text x="141" y="44" class="a-edge">행동</text>

<rect x="162" y="34" width="112" height="34" rx="4" class="s-step-n"/>
<text x="218" y="49" class="a-node">환경</text>
<text x="218" y="62" class="a-node-s">시뮬레이션</text>

<line x1="278" y1="51" x2="306" y2="51" class="a-flow"/><polygon points="312,51 302,46 302,56" class="a-fill-ink"/>
<text x="295" y="44" class="a-edge">점수</text>

<rect x="316" y="34" width="80" height="34" rx="4" class="s-step-d"/>
<text x="356" y="55" class="a-node">PPO</text>

<path d="M356,68 L356,90 L72,90 L72,72" class="a-loop"/>
<polygon points="72,66 67,76 77,76" class="a-fill-dim"/>
<text x="214" y="86" class="a-edge-d">수정: 반복 수백만 번</text>
''',
'<b>정책 → 환경 → 점수 → 수정 → 다시 정책.</b> 이 고리를 수백만 번 돌립니다. '
'실물로는 불가능한 횟수라 시뮬레이터가 필요합니다.', 100)


# ══════════════════ #5 C · 실전 8단계 ══════════════════
STAGES = [
    ('C1', '환경 재현', '공개 정책을 우리 환경에서 그대로 돌린다', 0),
    ('C2', '기준 정책', '이후 모든 비교의 기준을 만들고 고정한다', 0),
    ('C3', '보상 실험', '보상 항목을 하나씩 바꿔본다', 0),
    ('C4', '랜덤화 실험', '랜덤화를 하나씩 추가하며 손실을 기록한다', 0),
    ('C5', '커스텀 지형', '우리가 만든 지형에서 학습시킨다', 0),
    ('C6', '교차 검증', '다른 물리 엔진에서도 걷는가: 실기 전 마지막 관문', 1),
    ('C7', '실기 배포', '실제 로봇에 올린다', 0),
    ('C8', '최종 보고', '지표 + 시연 영상 + 한계까지 정직하게', 0),
]
_rows = ''
for i, (cid, name, desc, gate) in enumerate(STAGES):
    y = 26 + i * 34
    k = 'k' if gate else 'n'
    _rows += ('<rect x="16" y="%g" width="388" height="26" class="s-step-%s"/>'
              '<rect x="16" y="%g" width="34" height="26" class="s-cid-%s"/>'
              '<text x="33" y="%g" class="a-cid-%s">%s</text>'
              '<text x="60" y="%g" class="a-cname">%s</text>'
              '<text x="392" y="%g" class="a-cdesc">%s</text>'
              % (y, k, y, k, y + 17, k, cid, y + 17, name, y + 17, desc))
    if i < len(STAGES) - 1:
        _rows += ('<line x1="33" y1="%g" x2="33" y2="%g" class="a-flow"/>'
                  '<polygon points="33,%g 29,%g 37,%g" class="a-fill-ink"/>'
                  % (y + 26, y + 32, y + 34, y + 27, y + 27))

STEPS = fig(_rows,
            '<b>C6이 관문입니다.</b> 다른 물리 엔진에서도 걷는 것을 확인하기 전에는 실제 로봇에 올리지 않습니다. '
            '선행 사례는 이 단계를 건너뛰었다가 몇 주를 잃었습니다.', 26 + len(STAGES) * 34 - 8)


# 원본 <pre class="dia"> 안의 고유 문자열 → 교체할 도식
BY_KEY = {
    '구간 A · 공통 기반': STRUCT,
    '멀리 있으면 세게 당긴다': PD,
    '숫자 47개': LOOP,
    '반복 수백만 번': RL,
    'C1 환경 재현': STEPS,
}


CSS = r"""
/* ═══ ASCII 도식 대체 SVG ═══ */
.fdia .a-h{font-size:9.4px;font-weight:800;fill:var(--ink)}
.fdia .a-h-r{font-size:8px;fill:var(--ink-3);text-anchor:end}
.fdia .a-h-c{font-size:10px;font-weight:800;fill:var(--ink);text-anchor:middle}
.fdia .a-rule{stroke:var(--rule);stroke-width:1}
.fdia .a-lab{font-size:8.2px;fill:var(--ink-2);text-anchor:end}
.fdia .a-flow{stroke:var(--ink-3);stroke-width:1.3}
.fdia .a-fill-ink{fill:var(--ink-3)}
.fdia .a-fill-dim{fill:var(--dim)}
.fdia .a-loop{fill:none;stroke:var(--dim);stroke-width:1.2;stroke-dasharray:4 3}
.fdia .a-loop-lab{font-size:7.4px;fill:var(--dim);text-anchor:middle}
.fdia .a-hz{font-size:7.6px;font-weight:700;fill:var(--note)}

.fdia .s-secA{fill:var(--dim-soft);stroke:var(--dim);stroke-width:1.3}
.fdia .s-secB{fill:var(--note-soft);stroke:var(--note);stroke-width:1.3}
.fdia .s-secC{fill:var(--card);stroke:var(--ink-2);stroke-width:1.3}

.fdia .c-n-b{fill:var(--card);stroke:var(--ink-3);stroke-width:.9}
.fdia .c-n-t{font-size:8.4px;font-weight:700;fill:var(--ink-2);text-anchor:middle}
.fdia .c-k-b{fill:var(--dim);stroke:var(--dim);stroke-width:.9}
.fdia .c-k-t{font-size:8.4px;font-weight:800;fill:#fff;text-anchor:middle}
.fdia .c-b-b{fill:var(--card);stroke:var(--note);stroke-width:1.1}
.fdia .c-b-t{font-size:8.4px;font-weight:800;fill:var(--note);text-anchor:middle;letter-spacing:.06em}

.fdia .s-formula{fill:var(--dim-soft);stroke:var(--dim);stroke-width:1.4}
.fdia .a-formula{font-size:11.4px;font-weight:700;fill:var(--ink);text-anchor:middle;
  font-family:'Consolas','D2Coding',monospace}
.fdia .a-kp{fill:var(--dim);font-weight:800}
.fdia .a-kd{fill:var(--note);font-weight:800}
.fdia .a-tie-kp{stroke:var(--dim);stroke-width:1.2;stroke-dasharray:3 2}
.fdia .a-tie-kd{stroke:var(--note);stroke-width:1.2;stroke-dasharray:3 2}
.fdia .s-term-kp{fill:var(--card);stroke:var(--dim);stroke-width:1.1}
.fdia .s-term-kd{fill:var(--card);stroke:var(--note);stroke-width:1.1}
.fdia .a-term-h-kp{font-size:9px;font-weight:800;fill:var(--dim);text-anchor:middle}
.fdia .a-term-h-kd{font-size:9px;font-weight:800;fill:var(--note);text-anchor:middle}
.fdia .a-term-b{font-size:7.6px;fill:var(--ink-2);text-anchor:middle}

.fdia .s-step-n{fill:var(--card);stroke:var(--rule);stroke-width:1}
.fdia .s-step-d{fill:var(--dim-soft);stroke:var(--dim);stroke-width:1.2}
/* 어두운 채움 위에 어두운 글씨가 올라가 안 보이던 문제 → 연한 강조로 통일 */
.fdia .s-step-k{fill:var(--dim-soft);stroke:var(--dim);stroke-width:1.4}
.fdia .s-step-hi{fill:var(--dim-soft);stroke:var(--dim);stroke-width:1.6}
.fdia .s-cid-n{fill:var(--paper-2);stroke:var(--rule);stroke-width:1}
.fdia .s-cid-k{fill:var(--dim);stroke:var(--dim);stroke-width:1}
.fdia .a-cid-n{font-size:8.4px;font-weight:800;fill:var(--ink-2);text-anchor:middle}
.fdia .a-cid-k{font-size:8.4px;font-weight:800;fill:#fff;text-anchor:middle}
.fdia .a-cname{font-size:8.8px;font-weight:800;fill:var(--ink)}
.fdia .a-cdesc{font-size:8px;fill:var(--ink-2);text-anchor:end}
.fdia .a-sn{font-size:9.6px;font-weight:800;fill:var(--dim)}
.fdia .a-st{font-size:9px;font-weight:800;fill:var(--ink)}
.fdia .a-sb{font-size:7.6px;fill:var(--ink-2)}
.fdia .a-sb2{font-size:7.8px;font-weight:400;fill:var(--ink-2)}
.fdia .a-node{font-size:9.6px;font-weight:800;fill:var(--ink);text-anchor:middle}
.fdia .a-node-s{font-size:7.4px;fill:var(--ink-3);text-anchor:middle}
.fdia .a-edge{font-size:7.8px;font-weight:700;fill:var(--ink-3);text-anchor:middle}
.fdia .a-edge-d{font-size:7.8px;font-weight:700;fill:var(--dim);text-anchor:middle}
"""
