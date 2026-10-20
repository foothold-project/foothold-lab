# -*- coding: utf-8 -*-
"""foothold-lab docs/COLLAB.md → collab.html

  원본은 lab 레포의 COLLAB.md 다. 팀 규칙의 단일 진실이 팀 공간(org)에 살고,
  사이트는 그것을 게시한다. 빌드가 lab 클론 경로에서 읽는다.

  세션 규칙 2(웹 구조도 ASCII 금지)에 따라, md 의 <!--SVG:*--> 마커 자리에
  인라인 SVG(테마 변수 사용: 다크 대응)를 주입한다.
"""
import io
import re
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mdpage
import team_access                          # CSS · JS 재사용

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
# lab 클론 위치 후보: 기계마다 다르므로 전부 훑는다.
#   ★ 하드코딩된 세션 스크래치패드 경로 하나만 두면 다른 기계에서 빌드가 죽는다
#     (2026-08-11 워크스테이션에서 실제로 죽었다).
# ★ 2026-09-09. 아래 목록보다 docs_pages.LAB_CANDIDATES 를 «먼저» 본다.
#   lab 경로 규칙이 여러 자리에 흩어져 있었고, 빌드 입력을 고정 워크트리
#   (_lab-main)로 옮겼을 때 여기만 옛 경로를 봐서 낡은 문서를 실었다.
#   단일 원본에서 파생하고, 못 찾으면 아래 기존 후보로 내려간다.
def _from_single_source(name):
    try:
        import docs_pages
        return [os.path.join(c, "docs", name) for c in docs_pages.LAB_CANDIDATES]
    except Exception:
        return []


CANDIDATES = _from_single_source("COLLAB.md") + [
    # 상설 클론 (워크스테이션 · 노트북 공통 위치)
    r"C:\Users\AI-WS01\Desktop\jay\인공지능사관학교\foothold-lab\docs\COLLAB.md",
    os.path.expanduser(r"~\Desktop\jay\인공지능사관학교\foothold-lab\docs\COLLAB.md"),
    os.path.expanduser(r"~\OneDrive\Desktop\인공지능사관학교\foothold-lab\docs\COLLAB.md"),
    # 노트북 세션의 작업 클론
    r"C:\Users\<사용자>\AppData\Local\Temp\claude\C--Users-<사용자>-OneDrive-Desktop----------Claude\ee46b076-055c-4800-9fd3-9aa63c002829\scratchpad\repos\lab2\docs\COLLAB.md",
    # 볼트 미러 (최후)
    os.path.join(__import__('roots').proj(), '02_team', 'COLLAB.md'),
]
OUT = os.path.join(VAULT, 'collab.html')

# ── SVG ① 일의 흐름: 손 2가지 + 자동 레일 ──
SVG_FLOW = r"""
<figure class="fdia" style="margin:1.4rem 0;background:var(--card);border:1px solid var(--rule);padding:1rem 1.1rem">
<svg viewBox="0 0 760 240" xmlns="http://www.w3.org/2000/svg" style="display:block;width:100%;height:auto">
  <defs><marker id="cah" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
    <path d="M0,0 L7,3.5 L0,7 z" fill="var(--ink-3)"/></marker></defs>
  <text x="14" y="26" font-size="12" font-weight="800" fill="var(--ink)">사람이 하는 것 (딱 두 가지)</text>
  <rect x="14" y="40" width="150" height="52" fill="none" stroke="var(--ink)" stroke-width="2.5"/>
  <text x="89" y="62" text-anchor="middle" font-size="12.5" font-weight="800" fill="var(--ink)">① 이슈 만들기</text>
  <text x="89" y="79" text-anchor="middle" font-size="10" fill="var(--ink-2)">레포에서 · 템플릿 채우기</text>
  <rect x="596" y="40" width="150" height="52" fill="none" stroke="var(--ink)" stroke-width="2.5"/>
  <text x="671" y="62" text-anchor="middle" font-size="12.5" font-weight="800" fill="var(--ink)">② Closes #번호</text>
  <text x="671" y="79" text-anchor="middle" font-size="10" fill="var(--ink-2)">끝낼 때 커밋 메시지에</text>
  <text x="380" y="72" text-anchor="middle" font-size="11" fill="var(--ink-3)">…… 작업 ……</text>
  <line x1="164" y1="66" x2="330" y2="66" stroke="var(--ink-3)" stroke-width="1.6" marker-end="url(#cah)"/>
  <line x1="430" y1="66" x2="592" y2="66" stroke="var(--ink-3)" stroke-width="1.6" marker-end="url(#cah)"/>
  <text x="14" y="132" font-size="12" font-weight="800" fill="var(--dim)">자동으로 따라오는 것</text>
  <line x1="89" y1="92" x2="89" y2="146" stroke="var(--dim)" stroke-width="1.6" stroke-dasharray="5 4" marker-end="url(#cah)"/>
  <line x1="671" y1="92" x2="671" y2="146" stroke="var(--dim)" stroke-width="1.6" stroke-dasharray="5 4" marker-end="url(#cah)"/>
  <g font-size="10.5" font-weight="700">
    <rect x="14"  y="150" width="108" height="34" fill="var(--dim-soft)" stroke="var(--dim)"/>
    <text x="68"  y="171" text-anchor="middle" fill="var(--dim-ink)">보드 자동 등록</text>
    <rect x="132" y="150" width="108" height="34" fill="var(--dim-soft)" stroke="var(--dim)"/>
    <text x="186" y="166" text-anchor="middle" fill="var(--dim-ink)">담당자 = 나</text>
    <text x="186" y="179" text-anchor="middle" font-weight="400" font-size="9.5" fill="var(--dim-ink)">시작일 · 마감 +7일</text>
    <rect x="250" y="150" width="108" height="34" fill="var(--dim-soft)" stroke="var(--dim)"/>
    <text x="304" y="171" text-anchor="middle" fill="var(--dim-ink)">알림 "새 작업"</text>
    <rect x="490" y="150" width="108" height="34" fill="var(--dim-soft)" stroke="var(--dim)"/>
    <text x="544" y="171" text-anchor="middle" fill="var(--dim-ink)">이슈 닫힘 → Done</text>
    <rect x="608" y="150" width="108" height="34" fill="var(--dim-soft)" stroke="var(--dim)"/>
    <text x="662" y="171" text-anchor="middle" fill="var(--dim-ink)">알림 "완료"</text>
  </g>
  <text x="380" y="222" text-anchor="middle" font-size="10.5" fill="var(--note-ink)" font-weight="700">
    + 매주 월요일 09:00: 지난주 요약이 디스코드로 (자동)</text>
</svg>
<figcaption style="font-size:.72rem;color:var(--ink-3);margin-top:.5rem">
  실선 = 사람 · 점선 = 자동. 검증 완료(2026-08-08, 제로베이스 테스트 8경로).</figcaption>
</figure>
"""

# ── SVG ② 브랜치 전략 (rl) ──
SVG_BRANCH = r"""
<figure class="fdia" style="margin:1.4rem 0;background:var(--card);border:1px solid var(--rule);padding:1rem 1.1rem">
<svg viewBox="0 0 760 210" xmlns="http://www.w3.org/2000/svg" style="display:block;width:100%;height:auto">
  <defs><marker id="bah" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
    <path d="M0,0 L7,3.5 L0,7 z" fill="var(--ink-2)"/></marker></defs>
  <g font-size="11.5" font-weight="800">
    <text x="16" y="46"  fill="var(--stop)">main</text>
    <text x="16" y="106" fill="var(--note-ink)">dev</text>
    <text x="16" y="166" fill="var(--dim-ink)">feature/*</text>
  </g>
  <line x1="70" y1="40"  x2="740" y2="40"  stroke="var(--stop)" stroke-width="2.5"/>
  <line x1="70" y1="100" x2="740" y2="100" stroke="var(--note)" stroke-width="2.5"/>
  <g stroke="var(--dim)" stroke-width="2.5">
    <line x1="120" y1="160" x2="300" y2="160"/>
    <line x1="340" y1="160" x2="560" y2="160"/>
  </g>
  <g font-size="9.5" fill="var(--ink-2)">
    <text x="128" y="150">feature/obs-tuning</text>
    <text x="348" y="150">feature/terrain</text>
  </g>
  <path d="M 120 100 L 120 160" stroke="var(--dim)" stroke-width="1.6" fill="none"/>
  <path d="M 340 100 L 340 160" stroke="var(--dim)" stroke-width="1.6" fill="none"/>
  <path d="M 300 160 C 320 160, 320 100, 336 100" stroke="var(--ink-2)" stroke-width="1.6" fill="none" marker-end="url(#bah)"/>
  <path d="M 560 160 C 580 160, 580 100, 596 100" stroke="var(--ink-2)" stroke-width="1.6" fill="none" marker-end="url(#bah)"/>
  <path d="M 640 100 C 660 100, 660 40, 676 40" stroke="var(--ink-2)" stroke-width="1.6" fill="none" marker-end="url(#bah)"/>
  <g font-size="9.5" font-weight="800" fill="var(--ink)">
    <text x="298" y="128">PR</text><text x="558" y="128">PR</text><text x="640" y="68">PR</text>
  </g>
  <circle cx="120" cy="160" r="4" fill="var(--dim)"/><circle cx="340" cy="160" r="4" fill="var(--dim)"/>
  <circle cx="336" cy="100" r="4" fill="var(--note)"/><circle cx="596" cy="100" r="4" fill="var(--note)"/>
  <circle cx="676" cy="40" r="4" fill="var(--stop)"/>
  <g font-size="10" fill="var(--ink-3)">
    <text x="70" y="26">배포·제출 가능한 상태만 · 직접 push 금지(룰셋)</text>
    <text x="70" y="86">통합 브랜치. feature 들이 PR 로 모인다</text>
    <text x="70" y="196">브랜치 = PR 로 합칠 코드 변경 단위. 이슈 연결은 커밋의 Closes #번호가 한다</text>
  </g>
</svg>
<figcaption style="font-size:.72rem;color:var(--ink-3);margin-top:.5rem">
  foothold-go2 의 흐름 (feature -> dev -> main). lab 은 브랜치에서 PR 로 올린다.</figcaption>
</figure>
"""


def _ver(md):
    """원본 md 의 «> 판: v2.0» 을 그대로 쓴다.

    ★ 2026-08-28. 전에는 생성기에 «v1.0 · 2026-08-09 승인» 이 하드코딩돼 있었다.
      md 를 v2.0 으로 올려도 웹은 v1.0 을 찍었다. 생성기와 문서가 갈라진 것이다.
      판은 문서가 말해야 한다. 여기서 다시 적지 않는다."""
    m = re.search(r'^>\s*판\s*:\s*(v[\d.]+)\s*$', md, re.M)
    return m.group(1) if m else ''


def build():
    src = next((c for c in CANDIDATES if os.path.exists(c)), None)
    if not src:
        raise SystemExit('[!] COLLAB.md 원본을 찾을 수 없음')
    md = io.open(src, encoding='utf-8').read()
    title = mdpage.h1(md)
    body_md = md.split('\n---\n', 1)[-1] if '\n---\n' in md[:600] else md
    body = mdpage.render(body_md)
    # ★ mdpage 는 HTML 주석을 이스케이프해서 <p>&lt;!--SVG:flow--&gt;</p> 로 만든다.
    #   그 형태를 정확히 치환한다 (원문 형태도 함께: 파이프라인이 바뀌어도 동작하게).
    for marker, svg in (('SVG:flow', SVG_FLOW), ('SVG:branch', SVG_BRANCH)):
        for pat in ('<p>&lt;!--%s--&gt;</p>' % marker, '<!--%s-->' % marker):
            body = body.replace(pat, svg)
    if 'SVG:' in body:
        raise SystemExit('[!] SVG 마커가 치환되지 않고 남아 있음')

    html = (
        '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>%s · FOOTHOLD</title>\n'
        '<meta name="description" content="FOOTHOLD 팀의 협업 규칙: 원칙, 역할, 일의 흐름, '
        '브랜치 전략, 회의·결정·실험 규율, 온보딩 30분.">\n'
        '<style>%s\n.fdia svg text{font-family:inherit}</style>\n</head>\n<body>\n\n'
        '<div class="top"><div class="row">'
        '<a class="home" href="index.html">← 표지로</a>'
        '<span class="doc">FOOTHOLD · 협업 규칙</span><span class="sp"></span>'
        '<button class="pdfbtn" id="pdfBtn" type="button">PDF 저장</button>'
        '</div><div id="prog"></div></div>\n\n'
        '<div class="wrap">\n\n'
        '<div class="hero">\n'
        '  <div class="eyebrow">Collab · 우리가 일하는 방식</div>\n'
        '  <h1>%s</h1>\n'
        '  <p class="lede">규칙보다 이유가 먼저다. <b>기록이 우리를 증명하고, 측정이 판단을 대신하고, '
        '침묵은 성공이 아니다.</b> 손으로 하는 건 두 가지뿐이고 나머지는 자동이다. '
        '이 문서 전체가 공개다. 우리의 실패와 번복까지 포함해서.</p>\n'
        '  <div class="meta">'
        '<div><span class="k">판</span><span class="v">%s</span></div>'
        '<div><span class="k">원본</span><span class="v">foothold-lab / docs / COLLAB.md</span></div>'
        '<div><span class="k">온보딩</span><span class="v">§14: 30분이면 첫 작업까지</span></div>'
        '<div><span class="k">자동화</span><span class="v">8경로 검증 완료 (08-08)</span></div>'
        '</div>\n</div>\n\n'
        '%s\n\n</div>\n<script>%s</script>\n</body>\n</html>\n'
        % (title, team_access.CSS, title, _ver(md) or 'v1.0', body, team_access.JS))
    io.open(OUT, 'w', encoding='utf-8').write(html)
    return html


if __name__ == '__main__':
    h = build()
    print('collab.html : %d bytes · 섹션 %d · 표 %d · SVG %d'
          % (len(h), h.count('<section'), h.count('<table'), h.count('<svg')))
