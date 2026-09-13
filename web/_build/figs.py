# -*- coding: utf-8 -*-
"""커리큘럼 도식: 레퍼런스 영상의 시각 문법
   ① 절개도  ② 분해도  ③ 빨강 단일 강조  ④ 숫자를 화면에 박기

   ★ 폭 설계: 본문 컬럼이 784px(main max-width)로 고정이므로
      viewBox 폭을 420 으로 잡아 약 1.75배로 확대 렌더된다.
      → 8.4px 글자가 화면에서 약 14.7px 로 보인다(본문 16px 대비 적정).
      가로로 넓히지 말고 세로로 쌓을 것.
"""
W = 420


def fig(svg, cap, h):
    return ('\n<figure class="fdia">\n<svg viewBox="0 0 %d %d" role="img">%s</svg>\n'
            '<figcaption>%s</figcaption>\n</figure>\n' % (W, h, svg, cap))


# ══════════════════════ A2 · 로봇을 숫자로 보기 ══════════════════════
A2 = fig('''
<text x="100" y="13" class="t-h">앞에서</text>
<text x="100" y="26" class="t-s">옆으로 벌린다</text>
<rect x="16" y="34" width="168" height="112" class="s-panel"/>
<rect x="66" y="52" width="68" height="22" rx="5" class="s-box"/>
<text x="100" y="67" class="t-s2">몸통</text>
<circle cx="74" cy="74" r="4.6" class="f-note"/><circle cx="126" cy="74" r="4.6" class="f-note"/>
<line x1="74" y1="74" x2="60" y2="128" class="s-leg"/>
<line x1="126" y1="74" x2="140" y2="128" class="s-leg"/>
<path d="M74,74 A18,18 0 0,0 59,90" class="s-arc"/>
<path d="M126,74 A18,18 0 0,1 141,90" class="s-arc"/>
<text x="100" y="141" class="t-lab-n">hip abduction</text>

<text x="320" y="13" class="t-h">옆에서</text>
<text x="320" y="26" class="t-s">앞뒤로 젓고 · 접는다</text>
<rect x="236" y="34" width="168" height="112" class="s-panel"/>
<rect x="272" y="52" width="96" height="22" rx="5" class="s-box"/>
<text x="320" y="67" class="t-s2">몸통</text>
<circle cx="356" cy="74" r="4.8" class="f-dim"/>
<line x1="356" y1="74" x2="330" y2="106" class="s-leg2"/>
<text x="364" y="90" class="t-lab-d">hip pitch</text>
<circle cx="330" cy="106" r="4.8" class="f-stop"/>
<line x1="330" y1="106" x2="352" y2="134" class="s-leg"/>
<text x="322" y="118" class="t-lab-s" text-anchor="end">knee</text>
<circle cx="352" cy="134" r="3.6" class="f-ink"/>
<text x="320" y="141" class="t-n">3 × 4 = <tspan class="t-big">12개</tspan></text>

<rect x="16" y="160" width="388" height="96" class="s-alert"/>
<text x="30" y="179" class="t-alert-h">★ 그런데 없는 것이 더 중요합니다</text>
<line x1="30" y1="186" x2="390" y2="186" class="s-rule-s"/>
<text x="30" y="203" class="t-alert-b">몸통 속도</text>
<text x="390" y="203" class="t-x" text-anchor="end">센서가 아예 없음</text>
<text x="30" y="216" class="t-alert-s">자동차 속도계가 없는 셈. 지금 얼마나 빨리 가는지 모른다.</text>
<text x="30" y="234" class="t-alert-b">방위 (어느 쪽을 보나)</text>
<text x="390" y="234" class="t-x" text-anchor="end">나침반 없음</text>
<text x="30" y="247" class="t-alert-s">방향이 조금씩 계속 틀어진다.</text>
''',
'<b>정책이 보는 것과 못 보는 것.</b> 관절 12개와 IMU는 있지만 <b>속도계와 나침반이 없습니다.</b> '
'A12 「관측 설계」가 이 그림에서 출발합니다.', 264)


# ══════════════════════ A3 · 좌표계와 회전 ══════════════════════
A3 = fig('''
<text x="100" y="13" class="t-h">world 기준</text>
<text x="100" y="26" class="t-s">세상이 기준. 중력은 늘 아래</text>
<rect x="16" y="34" width="168" height="114" class="s-panel"/>
<line x1="34" y1="132" x2="166" y2="132" class="s-rule"/>
<g transform="translate(100,92) rotate(-20)"><rect x="-32" y="-10" width="64" height="20" rx="4" class="s-box"/></g>
<line x1="100" y1="50" x2="100" y2="122" class="s-grav"/>
<polygon points="100,128 96,118 104,118" class="f-note"/>
<text x="110" y="64" class="t-lab-n">중력</text>
<text x="100" y="144" class="t-s2">로봇이 기울어도 그대로</text>

<text x="320" y="13" class="t-h">base 기준: 로봇의 눈</text>
<text x="320" y="26" class="t-s">몸통을 수평으로 놓고 다시 본다</text>
<rect x="236" y="34" width="168" height="114" class="s-panel"/>
<rect x="288" y="82" width="64" height="20" rx="4" class="s-box"/>
<line x1="320" y1="50" x2="342" y2="118" class="s-grav-d"/>
<polygon points="344,124 336,117 343,113" class="f-dim"/>
<text x="348" y="76" class="t-lab-d">중력이</text>
<text x="348" y="88" class="t-lab-d">기울어 보인다</text>
<text x="320" y="144" class="t-s2">같은 중력, 다른 방향</text>

<rect x="16" y="162" width="388" height="82" class="s-key"/>
<text x="30" y="181" class="t-key-h">projected_gravity: 로봇 기준으로 본 중력</text>
<line x1="30" y1="188" x2="390" y2="188" class="s-rule"/>
<text x="30" y="205" class="t-key-b">숫자 <tspan class="t-em2">3개</tspan>면 끝납니다. 기울면 이 3개가 변하고, 로봇은 이걸로 자세를 압니다.</text>
<text x="30" y="221" class="t-key-s">사람의 평형 감각에 해당합니다. 눈을 감아도 어느 쪽이 위인지 아는 그 감각이요.</text>
<text x="30" y="236" class="t-key-s">관측 벡터의 절반이 이 계열입니다. 그래서 A12에서 다시 나옵니다.</text>
''',
'<b>"기울었다"를 숫자로 만드는 법.</b> 같은 중력인데 <b>누구 기준으로 보느냐</b>에 따라 방향이 달라집니다. '
'로봇 기준으로 본 중력이 <code>projected_gravity</code>이고, 이것이 로봇의 평형 감각입니다.', 252)


# ══════════════════════ A4 · PD 제어 ══════════════════════
A4 = fig('''
<text x="210" y="14" class="t-h">신경망은 모터를 직접 돌리지 않습니다</text>

<rect x="16" y="28" width="96" height="46" rx="4" class="s-stage"/>
<text x="64" y="47" class="t-st-h">신경망</text>
<text x="64" y="62" class="t-st-b">"30도로 놔라"</text>
<text x="64" y="86" class="t-s3">목표 각도만 말한다</text>

<line x1="116" y1="51" x2="140" y2="51" class="s-flow"/>
<polygon points="146,51 136,46 136,56" class="f-ink"/>

<rect x="150" y="24" width="140" height="54" rx="4" class="s-stage-k"/>
<text x="220" y="42" class="t-st-h">PD 제어기</text>
<text x="220" y="60" class="t-formula">kp×(목표−현재) + kd×(0−속도)</text>
<text x="220" y="72" class="t-s3">= 토크. 한 줄이 전부다.</text>

<line x1="294" y1="51" x2="318" y2="51" class="s-flow"/>
<polygon points="324,51 314,46 314,56" class="f-ink"/>

<rect x="328" y="28" width="76" height="46" rx="4" class="s-stage"/>
<text x="366" y="47" class="t-st-h">모터</text>
<text x="366" y="62" class="t-st-b">힘을 준다</text>
<text x="366" y="86" class="t-s3">토크를 받는다</text>

<line x1="16" y1="104" x2="404" y2="104" class="s-rule"/>

<text x="80" y="124" class="t-h2">kp가 크면</text>
<rect x="16" y="130" width="128" height="42" class="s-mini-s"/>
<text x="80" y="148" class="t-mini-b">뻣뻣하다</text>
<text x="80" y="163" class="t-mini-s">세게 당김 · 진동한다</text>

<text x="210" y="124" class="t-h2">kd가 크면</text>
<rect x="146" y="130" width="128" height="42" class="s-mini-s"/>
<text x="210" y="148" class="t-mini-b">흐물거린다</text>
<text x="210" y="163" class="t-mini-s">브레이크 · 굼뜨다</text>

<text x="340" y="124" class="t-h2">그래서</text>
<rect x="276" y="130" width="128" height="42" class="s-mini-d"/>
<text x="340" y="148" class="t-mini-b2">둘의 균형이 보행</text>
<text x="340" y="163" class="t-mini-s">이 두 숫자가 전부다</text>
''',
'<b>"신경망이 모터를 돌린다"는 흔한 오해입니다.</b> 신경망은 <b>목표 각도만</b> 말하고, 실제로 힘을 주는 건 '
'PD 제어기입니다. 로봇이 뻣뻣하거나 흐물거리는 이유가 전부 이 두 숫자(kp·kd)에 있습니다.', 180)


# ══════════════════════ A5 · 제어 루프 ══════════════════════
A5 = fig('''
<text x="210" y="14" class="t-h">두 개의 루프가 다른 속도로 돕니다</text>

<circle cx="96" cy="88" r="54" class="s-ring-d"/>
<text x="96" y="52" class="t-ring-h">정책 루프</text>
<text x="96" y="86" class="t-ring-big">50 Hz</text>
<text x="96" y="102" class="t-ring-s">초당 50번</text>
<text x="96" y="118" class="t-ring-s">"어떻게 걸을까"</text>
<text x="96" y="160" class="t-s3">신경망이 목표 각도를 낸다</text>

<circle cx="324" cy="88" r="54" class="s-ring-n"/>
<text x="324" y="52" class="t-ring-h">제어 루프</text>
<text x="324" y="86" class="t-ring-big2">500 Hz</text>
<text x="324" y="102" class="t-ring-s">초당 500번</text>
<text x="324" y="118" class="t-ring-s">"그 각도로 맞춰라"</text>
<text x="324" y="160" class="t-s3">PD가 토크를 낸다</text>

<line x1="156" y1="76" x2="258" y2="76" class="s-flow"/>
<polygon points="264,76 254,71 254,81" class="f-ink"/>
<text x="210" y="69" class="t-lab-c">목표 각도</text>

<line x1="258" y1="104" x2="156" y2="104" class="s-flow-b"/>
<polygon points="150,104 160,99 160,109" class="f-ink"/>
<text x="210" y="119" class="t-lab-c">센서 값</text>

<rect x="16" y="176" width="388" height="62" class="s-key"/>
<text x="30" y="195" class="t-key-h">왜 10배 차이인가</text>
<line x1="30" y1="202" x2="390" y2="202" class="s-rule"/>
<text x="30" y="218" class="t-key-b">신경망은 무겁고 느립니다. 그런데 모터는 훨씬 자주 잡아줘야 안 넘어집니다.</text>
<text x="30" y="232" class="t-key-s">그래서 신경망이 한 번 말하면 PD가 열 번 실행합니다.</text>
''',
'<b>A2·A3·A4가 여기서 합쳐집니다.</b> 정책은 초당 50번 "어떻게 걸을까"를 정하고, PD는 초당 500번 "그 각도로 맞춰라"를 '
'실행합니다. 이 그림이 프로젝트 전체의 뼈대입니다.', 246)


# ══════════════════════ A9 · 학습 곡선 읽기 ══════════════════════
A9 = fig('''
<text x="100" y="13" class="t-h">정상</text>
<rect x="16" y="22" width="168" height="102" class="s-panel"/>
<line x1="34" y1="110" x2="168" y2="110" class="s-axis"/>
<line x1="34" y1="34" x2="34" y2="110" class="s-axis"/>
<path d="M34,106 C62,100 74,70 96,58 C122,44 142,40 166,38" class="s-curve-d"/>
<text x="100" y="140" class="t-s2">올라가다 완만해진다</text>
<text x="100" y="152" class="t-lab-d2">좋다</text>

<text x="320" y="13" class="t-h">붕괴</text>
<rect x="236" y="22" width="168" height="102" class="s-panel"/>
<line x1="254" y1="110" x2="388" y2="110" class="s-axis"/>
<line x1="254" y1="34" x2="254" y2="110" class="s-axis"/>
<path d="M254,106 C276,96 288,60 306,50 L312,48 L316,104 L322,52 L328,106 L336,56 L344,108 L356,58 L368,106 L380,64 L388,102" class="s-curve-s"/>
<circle cx="310" cy="48" r="3.4" class="f-stop"/>
<text x="316" y="41" class="t-lab-s">여기서 깨졌다</text>
<text x="320" y="140" class="t-s2">치솟다 요동친다</text>
<text x="320" y="152" class="t-lab-s2">되돌려야 한다</text>

<rect x="16" y="166" width="388" height="88" class="s-key"/>
<text x="30" y="185" class="t-key-h">곡선 하나만 보면 안 됩니다. 영상을 같이 보세요</text>
<line x1="30" y1="192" x2="390" y2="192" class="s-rule"/>
<text x="30" y="209" class="t-key-b">① 보상은 오르는데 걷는 게 이상하다 → <tspan class="t-em">보상 해킹</tspan> (A10)</text>
<text x="30" y="226" class="t-key-b">② 보상이 아예 안 오른다 → 보상 설계나 관측이 잘못됐다</text>
<text x="30" y="243" class="t-key-b">③ 오르다 폭발한다 → 학습률이 크거나 에피소드가 너무 짧다</text>
''',
'<b>숫자가 오른다고 잘 되는 게 아닙니다.</b> 반드시 <b>곡선과 영상을 같이</b> 보세요. '
'보상은 오르는데 로봇이 기어가고 있으면 그건 성공이 아니라 A10의 보상 해킹입니다.', 262)


# ══════════════════════ A10 · 보상 해킹 ══════════════════════
A10 = fig('''
<text x="210" y="14" class="t-h">우리가 시킨 것 ≠ 로봇이 한 것</text>

<rect x="16" y="24" width="180" height="108" class="s-panel"/>
<text x="106" y="42" class="t-h2">우리가 준 보상</text>
<rect x="30" y="50" width="152" height="22" class="s-code"/>
<text x="106" y="65" class="t-formula2">앞으로 간 거리 × 큰 값</text>
<text x="106" y="88" class="t-s3">의도</text>
<text x="106" y="104" class="t-st-b">"앞으로 잘 걸어라"</text>
<text x="106" y="122" class="t-s3">사람은 당연히 걷는 걸 상상한다</text>

<line x1="202" y1="78" x2="216" y2="78" class="s-flow"/>
<polygon points="222,78 212,73 212,83" class="f-stop"/>

<rect x="224" y="24" width="180" height="108" class="s-alert"/>
<text x="314" y="42" class="t-alert-h2">로봇이 찾아낸 답</text>
<rect x="238" y="50" width="152" height="22" class="s-code-s"/>
<text x="314" y="65" class="t-formula2">몸을 던져 미끄러진다</text>
<text x="314" y="88" class="t-s3">결과</text>
<text x="314" y="104" class="t-alert-b2">보상 최고점. 걷지는 않음.</text>
<text x="314" y="122" class="t-alert-i2">규칙을 어긴 적이 없다. 그게 문제다</text>

<rect x="16" y="148" width="388" height="76" class="s-key"/>
<text x="30" y="167" class="t-key-h">이게 이 프로젝트에서 제일 자주 터집니다</text>
<line x1="30" y1="174" x2="390" y2="174" class="s-rule"/>
<text x="30" y="191" class="t-key-b">로봇은 <tspan class="t-em">우리가 쓴 대로</tspan> 합니다. <tspan class="t-em">우리가 원한 대로</tspan>가 아니라.</text>
<text x="30" y="207" class="t-key-s">그래서 보상을 고칠 때는 한 번에 하나만 바꾸고, 매번 영상을 봅니다.</text>
<text x="30" y="219" class="t-key-s">두 개를 같이 바꾸면 원인을 영원히 못 찾습니다.</text>
''',
'<b>강화학습이 배신하는 방식.</b> 로봇은 규칙을 어기지 않습니다. 우리가 쓴 규칙의 <b>빈틈</b>을 찾아냅니다. '
'그래서 보상 설계가 이 프로젝트의 실제 난이도입니다.', 232)


# ══════════════════════ A12 · 관측 설계 (급소) ══════════════════════
A12 = fig('''
<text x="210" y="14" class="t-h">★ 이 프로젝트의 급소</text>

<rect x="16" y="24" width="184" height="132" class="s-panel-d"/>
<text x="108" y="42" class="t-h2-d">정책에게 주는 것</text>
<line x1="30" y1="49" x2="186" y2="49" class="s-rule"/>
<text x="30" y="65" class="t-list-d">관절 각도</text><text x="186" y="65" class="t-num" text-anchor="end">12</text>
<text x="30" y="80" class="t-list-d">관절 각속도</text><text x="186" y="80" class="t-num" text-anchor="end">12</text>
<text x="30" y="95" class="t-list-d">몸통 각속도 (IMU)</text><text x="186" y="95" class="t-num" text-anchor="end">3</text>
<text x="30" y="110" class="t-list-d">projected_gravity</text><text x="186" y="110" class="t-num" text-anchor="end">3</text>
<text x="30" y="125" class="t-list-d">직전 행동</text><text x="186" y="125" class="t-num" text-anchor="end">12</text>
<line x1="30" y1="132" x2="186" y2="132" class="s-rule"/>
<text x="30" y="148" class="t-list-b">전부 로봇 몸에서 나온다</text>
<text x="186" y="149" class="t-num-big" text-anchor="end">42</text>

<rect x="220" y="24" width="184" height="132" class="s-alert"/>
<text x="312" y="42" class="t-alert-h2">주고 싶지만 못 주는 것</text>
<line x1="234" y1="49" x2="390" y2="49" class="s-rule-s"/>
<text x="234" y="67" class="t-list-s">몸통 속도</text>
<text x="390" y="67" class="t-x" text-anchor="end">센서 없음</text>
<text x="234" y="88" class="t-list-s">지형 높이 맵</text>
<text x="390" y="88" class="t-x" text-anchor="end">MCF 끄면 소실</text>
<text x="234" y="109" class="t-list-s">지면 마찰계수</text>
<text x="390" y="109" class="t-x" text-anchor="end">측정 불가</text>
<text x="234" y="130" class="t-list-s">지면 강성</text>
<text x="390" y="130" class="t-x" text-anchor="end">측정 불가</text>
<text x="312" y="149" class="t-alert-i2">시뮬에는 있고, 실물에는 없다</text>

<rect x="16" y="172" width="388" height="96" class="s-key"/>
<text x="30" y="191" class="t-key-h">그래서 이게 급소입니다</text>
<line x1="30" y1="198" x2="390" y2="198" class="s-rule"/>
<text x="30" y="215" class="t-key-b">시뮬에서 <tspan class="t-em">있는 값</tspan>으로 학습시키면 잘 걷습니다.</text>
<text x="30" y="230" class="t-key-b">실물에 올리면 그 값이 없어서 <tspan class="t-em">즉시 무너집니다.</tspan></text>
<text x="30" y="247" class="t-key-s">해법은 두 갈래: ① 실물에도 있는 값만 쓴다(blind) ② 학습 때만 특권 정보를 쓰고 실전엔 추정한다.</text>
<text x="30" y="260" class="t-key-s">우리 주제 "미경험 지형 적응"이 정확히 이 지점입니다. 지면 물성을 모르는 채 적응해야 하니까요.</text>
''',
'<b>관측 설계가 왜 급소인가.</b> 시뮬레이터는 마찰계수를 알지만 <b>실제 로봇은 모릅니다.</b> '
'그 차이를 무시하고 학습하면 시뮬에서만 잘 걷는 정책이 나옵니다. 이 프로젝트가 푸는 문제가 바로 이것입니다.', 276)


FIGURES = {
    'A2': A2, 'A3': A3, 'A4': A4, 'A5': A5,
    'A9': A9, 'A10': A10, 'A12': A12,
}
