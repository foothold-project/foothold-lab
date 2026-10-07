# -*- coding: utf-8 -*-
"""foothold-lab docs/FLOW.md → flow.html

  프로젝트 전체 흐름 페이지. 팀원과 심사자가 "무엇을 어떤 순서로 하는가"를
  한 장으로 파악하게 하는 것이 목적이다.

  세션 규칙 2(웹 구조도 ASCII 금지)에 따라 <!--SVG:*--> 마커 자리에
  인라인 SVG 를 주입한다. 테마 변수를 써서 다크 모드에 대응한다.
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
# lab 클론 위치 후보: 기계마다 다르므로 전부 훑는다 (collab_page 와 동일 원칙)
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


CANDIDATES = _from_single_source("FLOW.md") + [
    r"C:\Users\AI-WS01\Desktop\jay\인공지능사관학교\foothold-lab\docs\FLOW.md",
    os.path.expanduser(r"~\Desktop\jay\인공지능사관학교\foothold-lab\docs\FLOW.md"),
    os.path.expanduser(r"~\OneDrive\Desktop\인공지능사관학교\foothold-lab\docs\FLOW.md"),
    # 노트북 세션 작업 클론
    r"C:\Users\<사용자>\AppData\Local\Temp\claude\C--Users-<사용자>-OneDrive-Desktop----------Claude"
    r"\ee46b076-055c-4800-9fd3-9aa63c002829\scratchpad\repos\lab2\docs\FLOW.md",
    os.path.join(__import__('roots').proj(), '02_team', 'FLOW.md'),
]
OUT = os.path.join(VAULT, 'flow.html')


# ── SVG ① 전체 파이프라인 ────────────────────────────────────
SVG_PIPELINE = r"""
<figure class="fdia" style="margin:1.4rem 0;background:var(--card);border:1px solid var(--rule);padding:1rem 1.1rem">
<svg viewBox="0 0 780 400" xmlns="http://www.w3.org/2000/svg" style="display:block;width:100%;height:auto">
  <defs>
    <marker id="pah" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
      <path d="M0,0 L8,4 L0,8 z" fill="var(--ink-2)"/></marker>
    <marker id="pad" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
      <path d="M0,0 L8,4 L0,8 z" fill="var(--dim)"/></marker>
  </defs>

  <text x="14" y="20" font-size="11" font-weight="800" fill="var(--ink-3)">트랙 A · 시뮬레이션</text>
  <line x1="130" y1="16" x2="766" y2="16" stroke="var(--rule)" stroke-width="1"/>

  <rect x="14" y="34" width="150" height="80" fill="none" stroke="var(--ink)" stroke-width="2.5"/>
  <text x="89" y="58" text-anchor="middle" font-size="12.5" font-weight="800" fill="var(--ink)">험지에서 학습</text>
  <text x="89" y="76" text-anchor="middle" font-size="9.5" fill="var(--ink-2)">Isaac Lab · 4,096마리</text>
  <text x="89" y="92" text-anchor="middle" font-size="9.5" fill="var(--ink-2)">회색 지형 · 렌더 끔</text>
  <text x="89" y="106" text-anchor="middle" font-size="9.5" fill="var(--ink-3)">1회 약 133분</text>

  <rect x="204" y="34" width="150" height="80" fill="none" stroke="var(--ink)" stroke-width="2.5"/>
  <text x="279" y="58" text-anchor="middle" font-size="12.5" font-weight="800" fill="var(--ink)">미경험 지형 평가</text>
  <text x="279" y="76" text-anchor="middle" font-size="9.5" fill="var(--ink-2)">10종 · 각 50에피소드</text>
  <text x="279" y="92" text-anchor="middle" font-size="10" font-weight="800" fill="var(--stop)">5종 통과 · 5종 실패</text>
  <text x="279" y="106" text-anchor="middle" font-size="9.5" fill="var(--ink-3)">전부 아니면 전무</text>
  <line x1="164" y1="74" x2="200" y2="74" stroke="var(--ink-2)" stroke-width="1.6" marker-end="url(#pah)"/>

  <rect x="394" y="34" width="150" height="80" fill="none" stroke="var(--ink)" stroke-width="2.5"/>
  <text x="469" y="58" text-anchor="middle" font-size="12.5" font-weight="800" fill="var(--ink)">실패 5종 파인튜닝</text>
  <text x="469" y="76" text-anchor="middle" font-size="9.5" fill="var(--ink-2)">5인이 하나씩 레시피</text>
  <text x="469" y="92" text-anchor="middle" font-size="9.5" fill="var(--ink-2)">혼합 단일 런으로 합침</text>
  <text x="469" y="106" text-anchor="middle" font-size="9.5" fill="var(--ink-3)">체크포인트는 못 합친다</text>
  <line x1="354" y1="74" x2="390" y2="74" stroke="var(--ink-2)" stroke-width="1.6" marker-end="url(#pah)"/>

  <rect x="584" y="34" width="182" height="80" fill="var(--dim-soft)" stroke="var(--dim)" stroke-width="2.5"/>
  <text x="675" y="58" text-anchor="middle" font-size="12.5" font-weight="800" fill="var(--ink)">트윈 · 렌더</text>
  <text x="675" y="76" text-anchor="middle" font-size="9.5" fill="var(--ink-2)">실공간 복원 · 3DGS</text>
  <text x="675" y="92" text-anchor="middle" font-size="9.5" fill="var(--ink-2)">Path Tracing 시연</text>
  <text x="675" y="106" text-anchor="middle" font-size="9.5" fill="var(--ink-3)">학습 기여도 0 · 보여주기</text>
  <line x1="544" y1="74" x2="580" y2="74" stroke="var(--ink-2)" stroke-width="1.6" marker-end="url(#pah)"/>

  <path d="M 279 114 L 279 138 L 469 138 L 469 118" stroke="var(--dim)" stroke-width="1.6"
        stroke-dasharray="6 4" fill="none" marker-end="url(#pad)"/>
  <text x="374" y="152" text-anchor="middle" font-size="9.5" font-weight="700" fill="var(--dim)">어디서 깨지는지가 다음 학습의 지시서</text>

  <text x="14" y="196" font-size="11" font-weight="800" fill="var(--ink-3)">트랙 B · 실물 Go2</text>
  <line x1="112" y1="192" x2="766" y2="192" stroke="var(--rule)" stroke-width="1"/>

  <rect x="14" y="210" width="170" height="76" fill="var(--paper-2)" stroke="var(--ink-3)" stroke-width="2"/>
  <text x="99" y="234" text-anchor="middle" font-size="12.5" font-weight="800" fill="var(--ink)">순정 보행</text>
  <text x="99" y="252" text-anchor="middle" font-size="9.5" fill="var(--ink-2)">걷는 방법은 로봇이 안다</text>
  <text x="99" y="270" text-anchor="middle" font-size="10" font-weight="800" fill="var(--ink-3)">우리는 안 건드린다</text>

  <rect x="224" y="210" width="150" height="76" fill="none" stroke="var(--ink)" stroke-width="2.5"/>
  <text x="299" y="234" text-anchor="middle" font-size="12.5" font-weight="800" fill="var(--ink)">인지</text>
  <text x="299" y="252" text-anchor="middle" font-size="9.5" fill="var(--ink-2)">LiDAR · 카메라</text>
  <text x="299" y="270" text-anchor="middle" font-size="9.5" fill="var(--ink-2)">주변을 읽는다</text>
  <line x1="184" y1="248" x2="220" y2="248" stroke="var(--ink-2)" stroke-width="1.6" marker-end="url(#pah)"/>

  <rect x="414" y="210" width="150" height="76" fill="none" stroke="var(--ink)" stroke-width="2.5"/>
  <text x="489" y="234" text-anchor="middle" font-size="12.5" font-weight="800" fill="var(--ink)">SLAM</text>
  <text x="489" y="252" text-anchor="middle" font-size="9.5" fill="var(--ink-2)">지도를 만들고</text>
  <text x="489" y="270" text-anchor="middle" font-size="9.5" fill="var(--ink-2)">자기 위치를 안다</text>
  <line x1="374" y1="248" x2="410" y2="248" stroke="var(--ink-2)" stroke-width="1.6" marker-end="url(#pah)"/>

  <rect x="604" y="210" width="162" height="76" fill="none" stroke="var(--ink)" stroke-width="2.5"/>
  <text x="685" y="234" text-anchor="middle" font-size="12.5" font-weight="800" fill="var(--ink)">Nav2 자율주행</text>
  <text x="685" y="252" text-anchor="middle" font-size="9.5" fill="var(--ink-2)">목적지를 주면 간다</text>
  <text x="685" y="270" text-anchor="middle" font-size="9.5" fill="var(--ink-2)">막히면 돌아간다</text>
  <line x1="564" y1="248" x2="600" y2="248" stroke="var(--ink-2)" stroke-width="1.6" marker-end="url(#pah)"/>

  <text x="99" y="304" text-anchor="middle" font-size="9.5" fill="var(--ink-3)">우리가 보내는 것은</text>
  <text x="99" y="318" text-anchor="middle" font-size="9.5" font-weight="700" fill="var(--ink-2)">«초속 몇 미터로 어느 쪽»</text>

  <rect x="224" y="330" width="542" height="42" fill="var(--note-soft)" stroke="var(--note)" stroke-width="1.6"/>
  <text x="495" y="348" text-anchor="middle" font-size="11" font-weight="800" fill="var(--note)">두 트랙이 만나는 곳</text>
  <text x="495" y="364" text-anchor="middle" font-size="9.5" fill="var(--ink-2)">같은 험지를 시뮬과 실기로 건넌 비교 · 트윈으로 먼저 리허설한 코스</text>
  <path d="M 675 118 L 675 200 L 675 206" stroke="var(--ink-3)" stroke-width="1.6" stroke-dasharray="4 4" fill="none"/>

  <text x="14" y="392" font-size="9.5" fill="var(--ink-3)">실선 = 데이터가 흐르는 방향 · 점선 = 사람이 도는 개선 루프</text>
  <text x="500" y="392" font-size="9.5" font-weight="700" fill="var(--ink-3)">두 트랙은 서로를 기다리지 않는다</text>
</svg>
<figcaption style="font-size:.72rem;color:var(--ink-3);margin-top:.5rem">
  ★ 2026-08-19 에 한 줄기(학습 → 증류 → 실기 이전)를 <b>두 트랙</b>으로 바꿨다.
  실물에는 정책을 안 올린다. 순정 보행 위에 항법을 얹는다.</figcaption>
</figure>
"""




# ── SVG ④ 실기에서 도는 한 사이클 (50Hz) ────────────────────



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
        raise SystemExit('[!] FLOW.md 원본을 찾을 수 없음')
    md = io.open(src, encoding='utf-8').read()
    title = mdpage.h1(md)
    # ★ 2026-08-27: 이 자르기가 FLOW.md 머리의 «구판 주의» 경고까지 지웠다.
    #   원본은 옳은데 빌드가 안전장치를 없앤 것이다. 그래서 폐기된 실기 저수준
    #   계획이 아무 경고 없이 「처음 왔다면」 페이지로 나갔다.
    #   머리에 경고가 있으면 자르지 않는다.
    head = md[:900]
    keep_head = ('구판' in head) or ('폐기' in head) or ('구판 주의' in head)
    body_md = md if keep_head else (
        md.split('\n---\n', 1)[-1] if '\n---\n' in head else md)
    body = mdpage.render(body_md)

    # ★ 2026-08-28. 도식이 다섯이었는데 넷이 폐기된 절(증류 · 제어 층 · 실기 런타임)의
    #   그림이었다. FLOW v2.0 에서 그 절들을 걷어냈으므로 그림도 함께 지운다.
    #   쓰지 않는 그림을 남겨 두면 다음 사람이 «아직 하는 일» 로 읽는다.
    for marker, svg in (('SVG:pipeline', SVG_PIPELINE),):
        for pat in ('<p>&lt;!--%s--&gt;</p>' % marker, '<!--%s-->' % marker):
            body = body.replace(pat, svg)
    if 'SVG:' in body:
        raise SystemExit('[!] SVG 마커가 치환되지 않고 남아 있음')

    html = (
        '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>%s · FOOTHOLD</title>\n'
        '<meta name="description" content="FOOTHOLD 프로젝트 전체 흐름: 시뮬 학습부터 '
        '증류, 새 지형 시험, sim2sim, 실물 배포, 극사실 렌더까지. 로봇공학을 몰라도 읽히게.">\n'
        '<style>%s\n.fdia svg text{font-family:inherit}</style>\n</head>\n<body>\n\n'
        '<div class="top"><div class="row">'
        '<a class="home" href="index.html">← 표지로</a>'
        '<span class="doc">FOOTHOLD · 프로젝트 전체 흐름</span><span class="sp"></span>'
        '<button class="pdfbtn" id="pdfBtn" type="button">PDF 저장</button>'
        '</div><div id="prog"></div></div>\n\n'
        '<div class="wrap">\n\n'
        '<div class="hero">\n'
        '  <div class="eyebrow">Flow · 무엇을 어떤 순서로 하는가</div>\n'
        '  <h1>%s</h1>\n'
        '  <p class="lede">학습은 시뮬에서, 확인은 실물에서. '
        '<b>시뮬은 학습장이고 실기는 시험장이다</b>: 실기에서는 학습하지 않는다. '
        '용어는 나올 때마다 그 자리에서 푼다. 마지막 절 «자주 헷갈리는 것»부터 읽어도 된다.</p>\n'
        '  <div class="meta">'
        '<div><span class="k">원본</span><span class="v">foothold-lab / docs / FLOW.md</span></div>'
        '<div><span class="k">판</span><span class="v">%s</span></div>'
        '<div><span class="k">두 트랙</span><span class="v">A 시뮬 RL·트윈 (9/30) · B 순정 보행 위 SLAM·Nav2 (12/11)</span></div>'
        '<div><span class="k">별도 갈래</span><span class="v">극사실 렌더 (학습 기여도 0)</span></div>'
        '<div><span class="k">실측</span><span class="v">씬 분리 성공 · PT 1.75초/프레임</span></div>'
        '</div>\n</div>\n\n'
        '%s\n\n</div>\n<script>%s</script>\n</body>\n</html>\n'
        % (title, team_access.CSS, title, _ver(md) or 'v1.0', body, team_access.JS))
    io.open(OUT, 'w', encoding='utf-8').write(html)
    return html


if __name__ == '__main__':
    h = build()
    print('flow.html : %d bytes · 섹션 %d · 표 %d · SVG %d'
          % (len(h), h.count('<section'), h.count('<table'), h.count('<svg')))
