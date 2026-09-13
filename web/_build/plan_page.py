# -*- coding: utf-8 -*-
"""04_plan/PLAN.md → 05_deliverables/plan.html

  원문은 Markdown 이 단일 진실: 옮겨 적지 않고 읽어서 변환한다 (team_access 와 같은 방식).
  이 페이지의 특성: **완성 문서가 아니라 살아있는 설계도**다. 🔶(미확정)가 화면에서
  한눈에 구분되어야 한다. 그림이 결정을 대신해버리면 안 되기 때문.

  CSS/JS 는 team_access 의 것을 그대로 재사용한다 (토큰·인쇄·복사버튼 전부 동일).
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mdpage
import team_access                       # CSS · JS 재사용 (import 만으로는 build() 안 돈다)

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
SRC = os.path.join(__import__('roots').proj(), '04_plan', 'PLAN.md')
OUT = os.path.join(VAULT, 'plan.html')

# 이 페이지 전용 보강: 미확정 강조와 퀘스트 상태
EXTRA_CSS = r"""
/* ── 설계도 페이지 전용 ── */
.live{border:2px solid var(--note);background:var(--note-soft);padding:.9rem 1.1rem;margin:1.2rem 0}
.live b{color:var(--note-ink)}
td:has(> .q-done){background:var(--dim-soft)}
/* 🔶 미확정 마커가 든 셀·행은 눈에 띄게 */
.und-mark{color:var(--stop);font-weight:800}
"""


# ── 배포 경로 도식 ────────────────────────────────────────────────
#   말하려는 것 하나: **정책은 ROS 로 올리지 않는다.** 저수준(50Hz 관절 명령)은
#   Unitree SDK 직행이고, ROS2 는 그 위층이다. 두 층을 시각적으로 분리해 그린다.
#   색 의미(브랜드 §4): teal=확정 경로 · amber=미확정(증류) · 잉크=설명.
SVG_DEPLOY = r'''<figure class="fdia" style="margin:1.4rem 0;background:var(--card);border:1px solid var(--rule);padding:1rem 1.1rem"><svg viewBox="0 0 880 300" role="img"
  aria-label="배포 경로: 학습된 정책에서 Orin NX 제어 프로그램까지, ROS2 는 위층">
  <defs>
    <marker id="pd-a" viewBox="0 0 9 9" refX="6" refY="4.5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M0,0 L9,4.5 L0,9 z" fill="var(--ink-2)"/></marker>
    <marker id="pd-d" viewBox="0 0 9 9" refX="6" refY="4.5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M0,0 L9,4.5 L0,9 z" fill="var(--dim)"/></marker>
  </defs>

  <!-- 위층: ROS2 -->
  <rect x="8" y="8" width="864" height="74" rx="4" fill="var(--paper-2)" stroke="var(--rule)"/>
  <text x="24" y="30" class="lb">위층 · ROS2: 팀의 공통 언어</text>
  <text x="24" y="52" class="tx">목표 지점 주기 · 라이다 구독 · 지도 · 노드 간 통신</text>
  <text x="24" y="70" class="sm">멘토의 "ROS 최우선"은 이 층을 말한다 · 8/10~14 특강 18시간이 그 시작</text>

  <!-- 아래층 제목 -->
  <text x="24" y="112" class="lb2">저수준 · 정책이 실제로 지나가는 길 (ROS 를 거치지 않는다)</text>

  <!-- 단계 4개 -->
  <rect x="8"   y="126" width="180" height="70" rx="4" fill="var(--card)" stroke="var(--dim)" stroke-width="1.6"/>
  <text x="98"  y="152" class="st" text-anchor="middle">학습된 정책</text>
  <text x="98"  y="172" class="sm" text-anchor="middle">.pt · 시뮬 학습 결과</text>

  <rect x="238" y="126" width="180" height="70" rx="4" fill="var(--note-soft)"
        stroke="var(--note)" stroke-width="1.6" stroke-dasharray="5 4"/>
  <text x="328" y="146" class="st" text-anchor="middle">🔶 증류</text>
  <text x="328" y="165" class="sm" text-anchor="middle">더 작은 신경망으로 압축</text>
  <text x="328" y="182" class="sm" text-anchor="middle">멘토 제안 · 미확정</text>

  <rect x="468" y="126" width="180" height="70" rx="4" fill="var(--card)" stroke="var(--dim)" stroke-width="1.6"/>
  <text x="558" y="152" class="st" text-anchor="middle">내보내기</text>
  <text x="558" y="172" class="sm" text-anchor="middle">ONNX / TorchScript</text>

  <rect x="698" y="126" width="174" height="70" rx="4" fill="var(--card)" stroke="var(--ink)" stroke-width="1.8"/>
  <text x="785" y="146" class="st" text-anchor="middle">Orin NX</text>
  <text x="785" y="165" class="sm" text-anchor="middle">Go2 위 컴퓨터</text>
  <text x="785" y="182" class="sm" text-anchor="middle">제어 프로그램 50Hz</text>

  <path d="M188 161 L232 161" stroke="var(--dim)"  stroke-width="1.8" fill="none" marker-end="url(#pd-d)"/>
  <path d="M418 161 L462 161" stroke="var(--dim)"  stroke-width="1.8" fill="none" marker-end="url(#pd-d)"/>
  <path d="M648 161 L692 161" stroke="var(--dim)"  stroke-width="1.8" fill="none" marker-end="url(#pd-d)"/>

  <!-- 관절 명령 -->
  <rect x="698" y="228" width="174" height="56" rx="4" fill="var(--dim-soft)" stroke="var(--dim)"/>
  <text x="785" y="250" class="st" text-anchor="middle">관절 명령</text>
  <text x="785" y="269" class="sm" text-anchor="middle">Unitree SDK (DDS) 직행</text>
  <path d="M785 196 L785 222" stroke="var(--ink-2)" stroke-width="1.8" fill="none" marker-end="url(#pd-a)"/>

  <!-- 위층은 목표만 내려보낸다. 받는 쪽은 Orin 의 제어 프로그램이다 -->
  <path d="M785 82 L785 120" stroke="var(--ink-3)" stroke-width="1.4" stroke-dasharray="4 4"
        fill="none" marker-end="url(#pd-a)"/>
  <text x="770" y="106" class="sm" text-anchor="end">위층은 "어디로" 만 준다. "어떻게 걷나" 는 정책이 정한다</text>

  <style>
    .fdia text{font-family:inherit}
    .lb{font-size:12px;font-weight:800;letter-spacing:.1em;fill:var(--ink-3);text-transform:uppercase}
    .lb2{font-size:12px;font-weight:800;letter-spacing:.06em;fill:var(--dim)}
    .st{font-size:15px;font-weight:800;fill:var(--ink)}
    .tx{font-size:13px;fill:var(--ink-2)}
    .sm{font-size:11.5px;fill:var(--ink-3)}
  </style>
</svg></figure>'''


def build():
    md = io.open(SRC, encoding='utf-8').read()
    title = mdpage.h1(md)
    body_md = md.split('\n---\n', 1)[1] if '\n---\n' in md else md
    body = mdpage.render(body_md)

    # 🔶 를 강조 스팬으로 (md 에는 이모지만 두고 스타일은 여기서)
    #   ★ 반드시 SVG 주입 **전에** 한다. 나중에 하면 SVG <text> 안의 🔶 까지 <span> 으로 감싸는데,
    #     <text> 안의 <span> 은 SVG 가 아니어서 브라우저가 거기서 도형을 끊어버린다 (실제로 깨졌다).
    body = body.replace('🔶', '<span class="und-mark">🔶</span>')

    # 도식 주입: 웹에 ASCII 를 두지 않는다(세션 규칙 2). md 원문에는 마커만 남긴다.
    #   ★ mdpage 는 HTML 주석을 이스케이프한다. 그 형태도 함께 치환한다(collab_page 와 동일 함정).
    for marker, svg in (('SVG:deploy', SVG_DEPLOY),):
        for pat in ('<p>&lt;!--%s--&gt;</p>' % marker, '<!--%s-->' % marker):
            body = body.replace(pat, svg)
    if 'SVG:' in body:
        raise SystemExit('[!] plan: SVG 마커가 치환되지 않고 남아 있음')
    # 주입한 도식이 온전한가: 도형 개수로 확인한다(깨지면 텍스트가 밖으로 새어 나온다)
    if body.count('<figure class="fdia"') and body.count('</svg>') < 1:
        raise SystemExit('[!] plan: 도식이 온전하지 않음')

    html = (
        '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>%s · FOOTHOLD</title>\n'
        '<meta name="description" content="FOOTHOLD 프로젝트 설계도: 7단계 지도, '
        '이야기로 푸는 진행 순서, 퀘스트 보드, KPI 메뉴, 미확정 결정 안건.">\n'
        '<style>%s%s</style>\n</head>\n<body>\n\n'
        '<div class="top"><div class="row">'
        '<a class="home" href="index.html">← 표지로</a>'
        '<span class="doc">FOOTHOLD · 프로젝트 설계도</span><span class="sp"></span>'
        '<button class="pdfbtn" id="pdfBtn" type="button">PDF 저장</button>'
        '</div><div id="prog"></div></div>\n\n'
        '<div class="wrap">\n\n'
        '<div class="hero">\n'
        '  <div class="eyebrow">Plan · 흐름: 퀘스트: 결정</div>\n'
        '  <h1>%s</h1>\n'
        '  <p class="lede">완성본이 아니라 <b>논의 중인 설계도</b>다. '
        '<span class="und-mark">🔶</span> 표시는 아직 팀이 정하지 않은 것. '
        '그 표시들이 곧 다음 회의의 안건이다. 결정이 나면 이 문서가 갱신되고, '
        '갱신 이력이 곧 우리 기획 과정의 기록이 된다.</p>\n'
        '  <div class="meta">'
        '<div><span class="k">관문</span><span class="v">기획발표 9/4 · A-정책 9/12 · MVP 9/30 · NAV 11/7 · FINAL 12/11</span></div>'
        '<div><span class="k">지금</span><span class="v">퀘스트 Q3: 첫 기록 재기</span></div>'
        '<div><span class="k">미확정</span><span class="v">🔶 6건 (§5)</span></div>'
        '<div><span class="k">근거</span><span class="v">8/6 멘토 미팅 · AI-WS01 실측</span></div>'
        '</div>\n</div>\n\n'
        '%s\n\n</div>\n<script>%s</script>\n</body>\n</html>\n'
        % (title, team_access.CSS, EXTRA_CSS, title, body, team_access.JS))

    io.open(OUT, 'w', encoding='utf-8').write(html)
    return html


if __name__ == '__main__':
    h = build()
    print('plan.html : %d bytes · 섹션 %d · 표 %d · 🔶 %d'
          % (len(h), h.count('<section'), h.count('<table'), h.count('und-mark') - 2))
