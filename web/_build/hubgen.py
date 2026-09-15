# -*- coding: utf-8 -*-
"""허브 · 표지 재구성 · 전역 상단바 (팀장 확정 구조 2026-08-26 · 6-7).

  구조
      ┌──────────────────────────────────┐
      │        주 간 다 이 제 스 트        │   맨 위 띠
      ├──────────────────────────────────┤
      │ 자료실 | 커리큘럼 | 예산안 …        │   바로가기 (ia.QUICK 이 정본)
      ├──────────────────────────────────┤
      │ 기획 | 일정 | 회의 | 연구 | 기술 | 파이프라인 │   허브 (ia.HUBS 가 정본)
      └──────────────────────────────────┘

  ★ 배정은 ia.py 가 유일 원본이다. 여기서 페이지 목록을 다시 만들지 않는다.
    두 곳이 각자 목록을 가지면 반드시 갈라진다 (2026-08-26 덱 장수에서 겪었다).

  ★ 2026-08-25 사고 재발 방지: ia.py 가 «미배정 0» 을 보장한 뒤에만 돈다.
    분류가 없어 조용히 빠지는 페이지가 있으면 그 전에 빌드가 선다.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ia

# 정본 저장소 경로. 묶음 설명을 ROLES.md 에서 읽는 데 쓴다.
try:
    import docs_pages as _dp
    _LAB = next((x for x in _dp.LAB_CANDIDATES
                 if os.path.isdir(os.path.join(x, 'docs'))), None)
except Exception:
    _LAB = None
if _LAB:
    try:
        ia.load_area_what(_LAB)
    except Exception:
        pass

NAV_A, NAV_B = '<!--gnav:v1-->', '<!--/gnav:v1-->'
IDX_A, IDX_B = '<!--home:v1-->', '<!--/home:v1-->'


_LEAN = None


def leaned_on():
    """{페이지: 이 글을 근거로 삼는 문서 수}. 관계표에서 뽑는다.

    ★ 왜 (2026-08-29 · #73)
      허브 카드가 전부 같은 크기에 파일명순이었다. 「단순 나열」이다.
      팀장 철칙 3: **크기와 순서가 뜻을 실어야 한다.**

      뜻을 실을 재료는 이미 있다. 온톨로지의 참조 관계 85개다.
      **남들이 많이 딛고 선 글이 먼저다.** 손으로 고른 목록이 아니라
      관계표가 정하므로, 문서가 늘면 순서도 저절로 따라온다.
    """
    global _LEAN
    if _LEAN is not None:
        return _LEAN
    _LEAN = {}
    try:
        import standing
        import mdlinks
        g = standing._graph(_LAB)
        for rel, d in g.items():
            page = mdlinks.resolve('docs/' + rel)
            if page:
                _LEAN[page] = len([c for c in (d.get('children') or []) if c in g])
    except Exception as e:
        print('  [!] 참조 수를 못 읽음: %s' % e)
    return _LEAN


def _added(page):
    """그 페이지가 공개 저장소에 처음 올라간 날. 없으면 오늘(= 이번에 처음 나감)."""
    import newbadge
    return newbadge.first_added(_site(), page) or recent_today()


# 그 묶음 전체를 한 장으로 보여주는 페이지. 목차는 목록 맨 앞이다.
# 마감이 없다는 이유로 맨 뒤에 떨어지면 「12개 다 보고 나서야 요약이 나오는」 꼴이 된다.
GROUP_INDEX = {'deliverables.html'}

_DUE = re.compile(r'(\d{1,2})\s*월\s*(\d{1,2})\s*일')


def _due(v):
    """카드가 말하는 마감. 「기획발표 · 9월 4일」 -> 904. 없으면 맨 뒤(9999).

    ★ 관문 날짜는 이미 카드 메타에 글자로 있다. 그것을 그대로 읽는다.
      날짜 목록을 여기 다시 적으면 두 자리가 갈라진다.
    """
    for s in (v[4] if len(v) > 4 else '', v[3] if len(v) > 3 else ''):
        m = _DUE.search(s or '')
        if m:
            return int(m.group(1)) * 100 + int(m.group(2))
    return 9999


def _daynum(page):
    """등록일을 정렬용 숫자로. 20260829 처럼."""
    try:
        return int(_added(page).replace('-', ''))
    except Exception:
        return 0


def recent_today():
    import recent
    return recent.today_iso()


_KEEP = re.compile(r'<(pre|textarea|script)\b.*?</\1>', re.S | re.I)


def tidy(t):
    """빈 줄이 매 빌드마다 불어나는 것을 막는다 (2026-08-29 실측).

    마커 블록을 지울 때 앞뒤 빈 줄이 남고, 다음 빌드가 다시 넣으면서
    또 남긴다. 실측: index.html 이 하루 만에 빈 줄 335 -> 438 줄.
    오류가 안 나는 실패라 아무도 못 봤다 (원칙 2).

    `<pre>` `<textarea>` `<script>` 안은 줄바꿈이 뜻을 가지므로 건드리지 않는다.
    """
    holes = []

    def stash(m):
        holes.append(m.group(0))
        return '\x00%d\x00' % (len(holes) - 1)

    s = _KEEP.sub(stash, t)
    s = re.sub(r'\n[ \t]*(?:\n[ \t]*){2,}', '\n\n', s)
    return re.sub(r'\x00(\d+)\x00', lambda m: holes[int(m.group(1))], s)


_GNAV = re.compile(r'[ \t]*' + re.escape(NAV_A) + r'[\s\S]*?' + re.escape(NAV_B)
                   + r'[ \t]*\r?\n?')


def strip_gnav(t):
    """옛 전역바를 «자기 공백까지» 거둔다 (2026-09-02 실측).

    전에는 블록만 지우고 앞뒤 공백을 남겼다. 삽입은 매번 줄바꿈을 더하므로
    `<body>` 뒤 칸이 빌드마다 하나씩 늘었다. 오류는 안 난다 (원칙 2).

    ★ 자기 블록에 «붙어 있는» 공백만 거둔다. 주변 본문 공백은 건드리지 않는다.
      그래서 `[ \\t]*` 와 줄바꿈 하나까지만 먹고, 그 앞줄은 그대로 둔다.
    """
    return _GNAV.sub('', t)


def _kat_gnav():
    """★ 답을 아는 입력. 공백을 정확히 자기 것만 거두는가."""
    blk = NAV_A + '<nav>x</nav>' + NAV_B
    tail = '<div class="wrap">본문</div>'
    cases = [
        ('<body>' + blk + tail, '<body>' + tail),                       # 공백 0
        ('<body>\n' + blk + '\n' + tail, '<body>\n' + tail),            # 공백 1
        ('<body>\n   ' + blk + '   \n' + tail, '<body>\n' + tail),      # 여러 칸
        ('<body>\r\n' + blk + '\r\n' + tail, '<body>\r\n' + tail),      # CRLF
        ('<body>' + blk + blk + tail, '<body>' + tail),                 # 중복
    ]
    for src, want in cases:
        got = strip_gnav(src)
        if got != want:
            return False, '%r -> %r (기대 %r)' % (src[:40], got[:40], want[:40])
    # 관련 없는 주변 본문 공백은 보존한다
    keep = '<p>앞</p>\n\n\n<p>뒤</p>'
    if strip_gnav(keep) != keep:
        return False, '전역바가 없는데 본문 공백을 건드렸다'
    if strip_gnav('<p>앞</p>\n\n' + blk + '\n<p>뒤</p>') != '<p>앞</p>\n\n<p>뒤</p>':
        return False, '앞쪽 빈 줄까지 먹었다'
    return True, ''


_EMPTY_AT = re.compile(r'@[a-zA-Z-]+[^{};]*\{\s*\}\s*')
_EMPTY_STYLE = re.compile(r'<style[^>]*>\s*</style>\s*')


def strip_empty_css(t):
    """규칙을 걷어낸 뒤 남은 «빈 껍데기» 를 없앤다 (2026-09-02 실측).

    `#themeBtn{...}` 만 지우면 그것을 감싸던 `@media print{}` 가 남는다.
    생성 페이지는 매 빌드 다시 쓰니 하나로 그치지만, 손으로 관리하는 페이지는
    주입만 받으므로 **빌드마다 하나씩 쌓인다.** 실측 77개였다.

    ★ 안쪽부터 바깥쪽으로 반복한다. `@media{@supports{}}` 처럼 겹쳐 있으면
      한 번에 다 안 지워진다. 더 안 줄어들 때까지 돈다.
    """
    for _ in range(5):
        before = t
        t = _EMPTY_AT.sub('', t)
        t = _EMPTY_STYLE.sub('', t)
        if t == before:
            break
    return t


def _kat_empty_css():
    """★ 답을 아는 입력. 지워야 할 것만 지우는지 본다."""
    cases = [
        ('<style>\n@media print{}\n</style>', ''),
        ('<style>@media print{}</style><p>x</p>', '<p>x</p>'),
        ('<style>@media print{.a{color:red}}</style>',
         '<style>@media print{.a{color:red}}</style>'),      # 내용 있으면 그대로
        ('<style>.a{color:red}</style>', '<style>.a{color:red}</style>'),
        ('<style>@media print{@supports (x:y){}}</style>', ''),  # 겹친 껍데기
        ('<style id="ia-css">@media print{}.b{x:1}</style>',
         '<style id="ia-css">.b{x:1}</style>'),              # 한 블록에 섞이면 껍데기만
    ]
    for src, want in cases:
        got = strip_empty_css(src)
        if got != want:
            return False, '%r -> %r (기대 %r)' % (src, got, want)
    return True, ''


def _site():
    """공개 저장소 클론 위치. 「최근 올라온 것」의 날짜를 git 에서 읽는 데 쓴다.
    build.py 가 이미 찾아 두었으면 그것을 쓴다(두 곳이 각자 찾으면 갈라진다)."""
    b = sys.modules.get('build')
    if b is not None and getattr(b, 'SITE', None):
        return b.SITE
    import build as _b
    return _b.SITE

CSS = '''<style id="ia-css">
/* ★ 허브 이동 때 «흔들림» 실측 원인 셋 (2026-08-31 팀장 지적)
   ① 문서가 짧은 페이지엔 스크롤바가 없어 좌우가 15px 튄다 -> 항상 자리를 잡는다
   ② 허브 본문 폭이 824, 표지가 1000 -> PRD §4-1 대로 1040 한 벌
   ③ navctl 안에 <script> 가 인라인 요소로 들어가 바 높이가 2px 달랐다 */
html{scrollbar-gutter:stable}
/* ★ 실측 (팀장 8/31 · 백과): 페이지가 가진 «고정» 요소(사이드바 · 떠 있는 버튼)가
   top:0 이라 sticky 전역바 «뒤» 로 깔려 안 보였다. 바 높이(2.94rem)만큼 내린다.
   바 자신과 그 안의 것은 제외한다. */
/* ★ 9/1 실측: 2.94rem = 47.04px 인데 바의 실제 높이는 48px 이었다.
   1px 틈이 생겨 아래 요소가 바 밑으로 비쳤다. 실측값을 쓴다. */
body :not(.gnav):not(.gnav *){--navh:48px}
nav:not(.gnav),aside{top:var(--navh)!important;height:calc(100vh - var(--navh))!important}
/* ★ 9/1 실측 (커리큘럼): 「1 / 44 · 표지로 · PDF」 줄이 top:0 sticky 라
   전역바와 48px «전부» 겹쳐 스크롤 중 아예 안 보였다. nav·aside 만 내리던
   규칙이 <div> 로 만든 상단 줄을 통째로 비켜간 것이다 (철칙 4: 관문이 한
   층위만 봤다). 이름이 아니라 «역할» 로 잡는다. */
body .topbar:not(.gnav),body .subnav,body .deckbar,body .pagebar{
  top:var(--navh)!important}
body .topbar .row{max-width:1040px!important;box-sizing:border-box}
body>button[class]:not(.gnav *),body>a[class]:not(.gnav *){top:calc(var(--navh) + 7px)!important}
/* PRD §4-1: 바깥 컨테이너 1040 한 벌. 셸(research.html)이 --measure 기반 824 를
   물려주고 표지는 1000 이라 페이지마다 본문 좌표가 달랐다 (실측 179 vs 91). */
/* box-sizing 이 content-box 인 페이지는 패딩이 폭 밖에 붙어 1080 이 됐다
   (예산·자료실 실측). 컨테이너는 border-box 로 못박는다. */
body .wrap,main.wrap,div.wrap{max-width:1040px!important;box-sizing:border-box}
/* .wrap 을 안 쓰고 main 을 컨테이너로 쓰는 페이지(커리큘럼 784 · 백과 931)도
   같은 폭으로. 실측으로 잡았다. */
/* ⑤ 커리큘럼만 784. #deck 제외 규칙이 커리큘럼을 통째로 비켜갔다.
   덱 슬라이드 «안» 은 그대로 두고 컨테이너 폭만 맞춘다. */
main#deck{max-width:1040px!important;margin-left:auto;margin-right:auto}
body main:not(.wrap):not(#deck){max-width:1040px!important;
  margin-left:auto;margin-right:auto}
@media print{.wrap{max-width:none!important}}
.gnav .navctl script{display:none}
/* ★ 9/1: 검색 버튼은 런타임에 JS 가 만든다. 그때 «그 페이지의 PDF 버튼
   클래스» 를 복사해 페이지마다 크기가 달랐다 (팀장: 돋보기 크기가 변한다).
   복사는 searchbox 에서 없앴고, 여기서 바의 규격으로 못박는다. */
.gnav .fh-sbtn{font-size:.8rem!important;font-weight:600!important;letter-spacing:-.01em!important;line-height:1.5!important;padding:.34rem .55rem!important;height:1.85rem!important;gap:.28rem!important;border:0!important;background:transparent!important;position:static!important;box-sizing:border-box!important}
.gnav .fh-sbtn svg{width:11px!important;height:11px!important;flex:none}
.gnav{position:sticky;top:0;z-index:220;background:var(--paper);
  border-bottom:1px solid var(--rule);font-size:.82rem}
/* ★ 바 높이가 44 / 48 / 50 세 가지였다 (실측). 바가 «페이지의 line-height» 를
   물려받아 링크 높이가 27 / 31 / 33 으로 달라졌다. 바는 자기 값으로 선다. */
/* 바도 border-box 로. content-box 인 페이지에서 1078px 이 되어 좌표가
   51 로 밀렸다 (예산·자료실 실측). */
.gnav *{box-sizing:border-box}
.side,aside,.toc,.sidebar,.sticky,.stick{z-index:60}
.gnav{z-index:220}
.gnav .in{max-width:1040px;margin:0 auto;padding:.5rem 1.2rem;display:flex;
  align-items:center;gap:.1rem;flex-wrap:wrap;line-height:1.5;min-height:2.6rem;
  box-sizing:border-box;height:2.94rem}
/* 높이를 값으로 못박는다. 페이지마다 제어 버튼 수가 달라 45~47px 로 흔들렸다. */
.gnav a,.gnav .q,.gnav .navctl>*{line-height:1.5}
/* ★ 팀장 3차 지적 (8/31). 실측으로 남아 있던 어긋남:
     굵기 650 / 600 두 종 · 색 두 종 · 높이 25 / 26 / 29px 세 종 ·
     세로 위치 9 / 10 / 11px 세 종 («다크» 버튼만 3px 낮고 1px 위로 밀림).
   상단바 «모든» 항목이 같은 상자로 선다. 하나라도 예외를 두면 또 어긋난다. */
/* ★ 9/1 실측: 버튼 폭이 페이지마다 2px 달랐다. 원인은 «선언된 폰트 스택» 이
   달라서다 (기획 Arial · 백과·커리큘럼 Pretendard). 같은 글자여도 폭이 다르다.
   바는 자기 폰트를 갖는다. 그래야 페이지를 옮겨도 안 흔들린다. */
.gnav a,.gnav button,.gnav .navctl>*{
  font-family:'Pretendard','Malgun Gothic','Apple SD Gothic Neo','Segoe UI',system-ui,sans-serif!important;letter-spacing:-.01em!important;  font-size:.8rem!important;font-weight:600!important;
  line-height:1.5!important;color:var(--ink-3)!important;
  padding:.34rem .55rem!important;border-radius:4px!important;
  border:0!important;background:transparent!important;
  display:inline-flex!important;align-items:center!important;
  height:1.85rem!important;box-sizing:border-box!important;
  white-space:nowrap;text-decoration:none;cursor:pointer}
.gnav a:hover,.gnav button:hover,.gnav .navctl>*:hover{
  color:var(--ink)!important;background:var(--paper-2)!important}
.gnav a.home{margin-right:.6rem;padding:.34rem .3rem!important}
.gnav .lgi,.gnav .lgr{display:block}
.gnav .lgr{display:none}
@media (prefers-color-scheme:dark){.gnav .lgi{display:none}.gnav .lgr{display:block}}
html[data-theme="dark"] .gnav .lgi{display:none}
html[data-theme="dark"] .gnav .lgr{display:block}
html[data-theme="light"] .gnav .lgi{display:block}
html[data-theme="light"] .gnav .lgr{display:none}
/* ★ 현재 위치 (팀장 8/31: 밑줄이 별로다). 글자를 진하게 + 옅은 면.
   밑줄·알약 대신 «지금 여기» 를 조용히 말한다. */
.gnav a.on{color:var(--ink)!important;font-weight:800!important;
  background:var(--paper-2)!important}
.gnav a.on:hover{background:var(--paper-2)!important}
.gnav .sp{flex:1}

/* ★ 2026-08-28. 검색·다크 버튼이 position:fixed 로 «떠다니며» 상단바를 덮었다.
   모바일 실측: 검색 버튼이 「파이프라인」 글자를 가렸고(둘 다 z-index:70 이라
   나중에 그려지는 쪽이 이긴다), 다크 버튼은 iOS 에서 주소창이 접히자
   화면 중간으로 튀어 카드 글씨를 덮었다(fixed 의 고질적 재계산).
   떠다니게 두는 대신 **상단바 안의 정상 요소**로 앉힌다.
   상단바는 이미 sticky 라 따라오고, 흐름 안이라 아무것도 안 가린다. */
.gnav .navctl{display:inline-flex;align-items:center;gap:.3rem;margin-left:auto}
/* ★ 통일성 실측 (팀장 8/31): 바 안에 폰트 3종(13.1 / 12.2 / 9.9px) ·
   반경 2종(4px / 99px) · 굵기 3종이 섞여 있었다. 두 등급으로 줄인다.
   허브(주) .82rem 700 · 바로가기와 제어(부) .76rem 600 · 반경은 전부 4px. */
.gnav .navctl>*{position:static!important;inset:auto!important;top:auto!important;
  right:auto!important;bottom:auto!important;left:auto!important;z-index:auto!important;
  margin:0!important}
/* ★ 모바일 실측 (2026-08-31 · 390px): 상단바가 13개 항목을 wrap 해 3줄이 되고
   화면 상단 1/8 을 먹었다. 모바일에서는 **허브 여섯만** 한 줄로 두고
   가로 스크롤로 넘긴다. 바로가기는 접는다 (표지와 각 허브에서 닿는다). */
@media (max-width:720px){
  .gnav{height:auto}
  .gnav .in{padding:.4rem .7rem;flex-wrap:nowrap;overflow-x:auto;height:auto;
    min-height:2.7rem;scrollbar-width:none}
  .gnav .in::-webkit-scrollbar{display:none}
  .gnav .q{display:none}
  .gnav .sp{display:none}
  .gnav a.home{margin-right:.35rem;flex:none}
  .gnav a{flex:none;padding:.3rem .45rem}
  /* ★ 2026-09-08 팀장 지적: 모바일에서 검색·테마가 화면 밖이다.
     실측(390px · 같은 출처 iframe · 높이 30000): .navctl 오른쪽 끝이 x=860.
     바가 가로로 스크롤되는 것은 8/31 팀장 확정이라 그대로 둔다. 다만 그 결정은
     «허브 링크» 를 한 줄에 두려던 것이었고, 검색·테마까지 밀려날 이유는 없었다.
     완비 관문 [3.46] 은 「토글이 있는가」만 보고 「닿는가」는 아무도 안 봤다.
     스크롤 컨테이너 안에서 sticky 로 오른쪽에 붙여 언제나 닿게 한다. */
  .gnav .navctl{margin-left:auto;flex:none;position:sticky;right:0;
    background:var(--paper);padding-left:.35rem;z-index:1}
}

.band{display:block;text-decoration:none;color:inherit;background:var(--paper-2);
  border:1px solid var(--rule);border-radius:var(--p-radius,8px);
  padding:1rem 1.2rem;margin:0 0 14px;transition:border-color .12s,background .12s}
/* ★ 호버 한 벌 (팀장 정정 8/31): 슬롭은 «위·왼쪽 악센트 바» 였지 테두리가 아니었다.
   「최근 올라온 것」처럼 **호버에 테두리 색이 들어가** 눈에 띄게 한다.
   표지 아홉 · 바로가기 · 최근 목록이 같은 방식으로 반응한다. */
.band:hover,.bands3 .band:hover,.hubs a:hover,.quick a:hover{
  border-color:var(--dim)}
.hubs a.hot:hover,.bands3 .b-deliv:hover{border-color:var(--note)}
.band .t{font-size:1.06rem;font-weight:850;letter-spacing:.02em}
.band .d{font-size:.8rem;color:var(--ink-3);margin-top:.22rem}
.band .w{float:right;font-family:ui-monospace,Consolas,monospace;font-size:.72rem;
  color:var(--ink-3);font-weight:700}

/* ★ 표지 3열 (팀장 8/31): 디자인 시스템 안에서 배경톤 베리에이션.
   토큰의 soft 짝을 써서 셋을 구분한다. 새 색을 만들지 않는다. */
.bands3{display:grid;grid-template-columns:repeat(3,1fr);gap:.6rem;margin:0 0 14px}
/* ★ 팀장 재지적: 「면과 위쪽 한 줄」도 AI 슬롭이다. 악센트 바를 전부 뺀다.
   구분은 배경 면 · 여백 · 글자 위계로만. 색은 뜻이 있을 때만 (급한 것). */
.bands3 .band{margin:0;padding:.9rem 1.1rem;min-height:5.2rem;
  display:flex;flex-direction:column;justify-content:center;
  border:1px solid var(--rule)}
.bands3 .band .t{font-size:.98rem}
/* ★ 배경톤 베리에이션 (팀장 8/31). 새 색을 만들지 않는다.
   토큰의 soft 짝을 쓰되 «뜻» 에 맞춰 고른다:
     팀 공지 = 우리 안에서 도는 것 -> dim-soft
     다이제스트 = 지난 것을 갈무리 -> paper-2 (중립)
     산출물 = 급한 것 -> note-soft */
.bands3 .b-notice{background:var(--dim-soft)}
.bands3 .b-digest{background:var(--paper-2)}
.bands3 .b-deliv{background:var(--note-soft)}
.bands3 .b-deliv .d{color:var(--note-ink,var(--note));font-weight:700}
@media (max-width:820px){.bands3{grid-template-columns:1fr}}
.quick{display:grid;grid-template-columns:repeat(auto-fit,minmax(10.5rem,1fr));
  gap:.6rem;margin:0 0 16px}
.quick a{display:block;text-decoration:none;color:inherit;background:var(--card);
  border:1px solid var(--rule);border-radius:var(--p-radius,8px);
  padding:.72rem .85rem;transition:border-color .12s}
.quick .k{font-size:.92rem;font-weight:800}
.quick .e{font-family:ui-monospace,Consolas,monospace;font-size:.6rem;font-weight:700;
  letter-spacing:.09em;text-transform:uppercase;color:var(--ink-3);margin-top:.08rem}
.quick .d{font-size:.72rem;color:var(--ink-3);line-height:1.5;margin-top:.3rem}

/* ★ v3: PC 3열×2행 (팀장 지시 2026-08-30). 좁으면 흘러내린다. */
.hubs{display:grid;grid-template-columns:repeat(3,1fr);gap:.6rem;margin:0 0 28px}
@media (max-width:720px){.hubs{grid-template-columns:repeat(auto-fit,minmax(9.5rem,1fr))}}
.hubs a.hot .d{color:var(--note-ink,var(--note));font-weight:700}
/* ★ 높이 통일 (팀장 8/31): 설명 길이가 달라 행마다 높이가 달랐다.
   같은 격자 안에서 늘려 맞추고, 설명은 두 줄로 잘라 통일한다. */
/* ★ AI 슬롭 제거 (팀장 8/31): 카드마다 두른 외곽선을 없앤다.
   구분은 «면(배경)» 과 위쪽 3px 한 줄로만. 선을 겹쳐 두르지 않는다. */
/* 허브 여섯: 흰 카드 다섯의 반복이 단조로웠다. «무엇을 보러 가는가» 로 톤을 나눈다.
     밖에 보이는 것(기획·회의) = card 흰 면
     우리가 만든 것(연구·기술) = paper-2
     굴리는 것(파이프라인)     = paper-2 · 옅은 글자
     급한 것(일정)             = note-soft
   전부 기존 토큰이다. 새 색 없음. */
.hubs a{display:flex;flex-direction:column;text-decoration:none;color:inherit;
  background:var(--card);border:1px solid var(--rule);
  border-radius:var(--p-radius,8px);padding:.9rem 1rem;min-height:6.4rem;
  transition:border-color .12s,background .12s}
.hubs a:nth-child(4),.hubs a:nth-child(5),.hubs a:nth-child(6){background:var(--paper-2)}
.hubs a.hot{background:var(--note-soft)}
.hubs .d{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
  overflow:hidden;margin-top:auto}

.hubs .k{font-size:1rem;font-weight:850}
.hubs .e{font-family:ui-monospace,Consolas,monospace;font-size:.6rem;font-weight:700;
  letter-spacing:.09em;text-transform:uppercase;color:var(--ink-3);margin-top:.08rem}
.hubs .d{font-size:.73rem;color:var(--ink-3);line-height:1.5;margin-top:.34rem}
.hubs .n{font-size:.7rem;color:var(--ink-3);font-weight:700;margin-top:.3rem}

.hlede{font-size:.74rem;color:var(--ink-3);margin:-2px 0 9px;line-height:1.5}
.hv{border:1px solid var(--rule);border-radius:3px;padding:0 4px;font-weight:700;
  font-size:.92em;margin-left:.4rem;color:var(--ink-3)}
.hgroup{margin:26px 0 8px;font-size:.7rem;font-weight:800;letter-spacing:.12em;
  color:var(--ink-3);border-bottom:1px solid var(--rule);padding-bottom:.35rem}
.hlist{display:grid;gap:.5rem}
.hlist a{display:block;text-decoration:none;color:inherit;background:var(--card);
  border:1px solid var(--rule);border-radius:var(--p-radius,8px);padding:.65rem .85rem}
.hlist a:hover{border-color:var(--dim)}
.hlist a{position:relative;padding-left:3.1rem}
.hlist .hn{position:absolute;left:.85rem;top:.68rem;font-family:ui-monospace,Consolas,monospace;
  font-size:.72rem;font-weight:800;color:var(--ink-3);letter-spacing:.02em}
.hlist .t{font-size:.92rem;font-weight:750}
.hlist .d{font-size:.75rem;color:var(--ink-3);line-height:1.55;margin-top:.2rem}
.hlist .m{font-size:.7rem;color:var(--ink-3);margin-top:.35rem;
  font-variant-numeric:tabular-nums;opacity:.85}

/* 「먼저 볼 것」. 이 허브에 처음 왔으면 여기서 시작한다 (#73). */
.hhero{display:block;text-decoration:none;color:inherit;margin:0 0 1.5rem;
  border:1px solid var(--dim);border-radius:8px;background:var(--card);
  padding:1rem 1.15rem 1.05rem;position:relative}
.hhero:hover{border-color:var(--ink-3)}
.hhero .hk{font-size:.6rem;font-weight:800;letter-spacing:.16em;color:var(--dim);
  margin-bottom:.4rem}
.hhero .t{font-size:1.28rem;font-weight:820;line-height:1.3;letter-spacing:-.01em}
.hhero .d{font-size:.88rem;color:var(--ink-2,var(--ink-3));line-height:1.6;
  margin-top:.4rem}
.hhero .m{font-size:.72rem;color:var(--ink-3);margin-top:.55rem;
  font-variant-numeric:tabular-nums}
.hhero .hv{font-size:.62rem;margin-left:.5rem;vertical-align:.3em}
@media (max-width:560px){.hhero .t{font-size:1.08rem}}

/* 2026-09-14. 아직 다크 색을 못 정한 손그림 그림 5장은 다크에서 흰 판 위에
   올린다. 그림을 한 획도 안 고치고도 어두운 페이지에서 읽힌다. 어느 그림이
   여기 드는지는 `tools/svg_theme.py` 가 «파일을 재서» 정하고 빌드가 붙인다. */
[data-theme="dark"] img[data-plate]{background:#fff;border-radius:8px;
  padding:10px;box-sizing:border-box}

/* 표지 「최근 올라온 것」. ia-css 는 모든 페이지에 실리므로 여기 한 자리면 된다. */
.recent{display:grid;gap:.45rem;margin:0 0 10px}
.recent a{display:flex;gap:.75rem;align-items:baseline;flex-wrap:wrap;
  text-decoration:none;color:inherit;border:1px solid var(--rule);
  background:var(--card);border-radius:var(--p-radius,8px);padding:.5rem .85rem}
.recent a:hover{border-color:var(--dim)}
.recent .rd{flex:none;font-size:.72rem;color:var(--ink-3);
  font-variant-numeric:tabular-nums;min-width:3.2em}
.recent .rk{flex:none;font-size:.62rem;font-weight:800;letter-spacing:.08em;
  color:var(--dim);min-width:4.6em}
.recent .rt{font-size:.86rem;font-weight:750;line-height:1.45}
.recent .rn{flex:none;font-size:.58rem;font-weight:800;background:var(--dim);
  color:var(--paper);border-radius:3px;padding:1px 5px;letter-spacing:.06em}
@media (max-width:560px){
  .recent a{gap:.4rem}
  .recent .rt{flex-basis:100%}
}
</style>'''


# ★ 묶음을 놓는 순서. 「무엇을 먼저 봐야 하나」다.
#   결과 -> 결정 -> 만드는 법 -> 밑바탕 순. 가나다순이 아니다.
GROUP_ORDER = [
    # ── 일정 허브: 「급한 것부터」
    '지금 어디까지',
    '무엇을 언제까지',
    '계획',
    # ── 기획 허브: 「밖에 보이는 것부터」
    '밖으로 내보내는 것',
    '안에서 쓰는 것',
    # ── 회의 허브: 「누가 정했나」
    '무엇을 정했나',
    '팀 내부에서 정한 것',
    '멘토에게 받은 것',
    '운영진과 맞춘 것',
    '조선대와 맞춘 것',
    '현장 기록',
    # ── 연구·파이프라인: 결과 (우리가 낸 숫자)
    '얼마나 걷나 · 평가와 지표',
    '정책을 어떻게 학습시키나',
    # 결정과 계획
    '계획과 결정',
    # 만드는 법
    '지형과 씬을 어떻게 만드나',
    '트윈과 렌더',
    '실기 항법 · ROS 2 와 SLAM',
    '센서로 무엇을 보나',
    'ROS 2 학습 (조선대 수업 정리)',
    '환경 세우기',
    # 밑바탕
    '인프라 · 자동화 · 예산',
    '자동으로 도는 것',
    '일하는 규칙',
    '기록 · 발표 · 대외보고',
    '안내',
]

# 묶음 이름이 없을 때. 「문서」는 무엇이든 될 수 있어 아무것도 안 걸러 준다
# (팀장 지적 2026-08-28). 무엇인지 모르겠다고 솔직히 적는다.
GROUP_FALLBACK = '아직 안 갈린 것'


def _cover_tiles():
    """표지 타일의 차례. 허브 + 밖에 있는 목적지를 정해진 자리에 끼운다.

    ★ 전역바와 «같은 차례» 여야 한다. 둘이 다르면 표지에서 본 자리와
      상단바에서 누르는 자리가 달라진다. 그래서 한 함수로 모은다.
    """
    out = []
    for h in ia.HUBS:
        out.append(h)
        if h[0] == ia.OUTSIDE_AFTER:
            for href, ko, en, lede in ia.OUTSIDE:
                out.append((href, ko, en, href, lede))
    return out


def gnav(cur, ctl=''):
    """전역 상단바. 모든 페이지에 같은 것이 붙는다."""
    # ★ #85: 로고는 글씨가 아니라 정본 워드마크다 (5도 슬라이스가 식별 요소).
    #   라이트=ink · 다크=reverse 를 CSS 로 갈아탄다. 자산은 [1.87] 이 복사한다.
    a = ['<div class="gnav"><div class="in">',
         '<a class="home" href="index.html">'
         '<img class="lgi" src="assets/brand/foothold-wordmark-ink.svg" '
         'alt="FOOTHOLD" height="15">'
         '<img class="lgr" src="assets/brand/foothold-wordmark-reverse.svg" '
         'alt="" height="15"></a>']
    for key, ko, en, f, _ in ia.HUBS:
        a.append('<a class="%s" href="%s">%s</a>'
                 % ('on' if cur == key else '', f, ko))
        # ★ 밖에 있는 목적지는 «정해진 자리» 에 끼운다. 끝에 붙이면
        #   assets/gnav.html 과 차례가 어긋나 페이지를 오갈 때 메뉴가 움직인다.
        if key == ia.OUTSIDE_AFTER:
            for href, oko, _en, _lede in ia.OUTSIDE:
                a.append('<a class="%s" href="%s">%s</a>'
                         % ('on' if cur == href else '', href, oko))
    a.append('<span class="sp"></span>')
    for f, ko, _, _ in ia.QUICK:
        a.append('<a class="q%s" href="%s">%s</a>'
                 % (' on' if cur == f else '', f, ko))
    # 검색·다크가 앉을 자리. 비어 있으면 searchbox JS 가 채운다.
    a.append('<span class="navctl">%s</span>' % (ctl or ''))
    a.append('</div></div>')
    return NAV_A + ''.join(a) + NAV_B


# 전체화면 덱. 문서 흐름 주입물(상단바·도장)이 슬라이드를 덮는다 (팀장 실측 8/31).
DECK_PAGES = {'team-intro.html', 'pitch.html'}


def strip_old_topbar(t):
    """전역바 이전의 보조 내비(.top)를 걷어낸다.

    ★ 실측 (팀장 8/31 · team-lead): 「표지로 · 페이지명 · PDF 저장」 줄이
      본문 1040 과 어긋난 824 폭으로 떠 있었다. 전역바가 생기기 전 유물이라
      «표지로» 는 로고와 중복이고 «페이지명» 은 바로 아래 h1 과 중복이다.
      쓸모 있는 것은 PDF 버튼 하나뿐이라 그것만 상단바로 옮긴다.
    """
    m = re.search(r'<div class="top">.*?</div>\s*</div>', t, re.S)
    if not m:
        return t, ''
    seg = m.group(0)
    pdf = ''
    mb = re.search(r'<button[^>]*id="pdfBtn".*?</button>', seg, re.S)
    if mb:
        pdf = mb.group(0)
    return t[:m.start()] + t[m.end():], pdf


def inject_nav(path, cur):
    """상단바를 넣는다. 마커로 감싸 몇 번 돌려도 하나만 남는다.

    ★ 모든 페이지가 <body> 를 갖고 있지는 않다. automation.html 은 doctype·html·
      head·body 가 전부 없는 조각이라 <body> 를 찾다가 조용히 건너뛰었다.
      «못 찾으면 건너뛴다» 는 조용한 실패다. 삽입 지점을 단계적으로 찾는다.
    """
    t = io.open(path, encoding='utf-8').read()
    t = strip_gnav(t)
    t, _pdf = strip_old_topbar(t)
    # ★ 실측 (팀장 9/1): tech-* 와 예산안에 파비콘이 없었다. head 를 손대는
    #   김에 없으면 넣는다. 브랜드 자산은 [1.87] 이 이미 복사해 둔다.
    if 'rel="icon"' not in t and '</head>' in t:
        t = t.replace('</head>',
                      '<link rel="icon" type="image/svg+xml" '
                      'href="assets/brand/foothold-favicon.svg">' + chr(10)
                      + '</head>', 1)
    # ★ 2026-08-31 실측. 여기가 «이미 있으면 건너뛴다» 였다. 그래서 CSS 를 고쳐도
    #   손으로 관리하는 페이지(setup 등)에는 **옛 CSS 가 박제**됐다. 허브는 매번
    #   새로 생성되니 반영되어 「허브만 되고 나머지는 안 되는」 현상이 났다.
    #   마커 구역처럼 통째로 갈아끼운다.
    t = re.sub(r'<style id="ia-css">.*?</style>', '', t, flags=re.S)
    if '</head>' in t:
        t = t.replace('</head>', CSS + '\n</head>', 1)
    else:
        # 조각 문서: 첫 <style> 뒤, 없으면 맨 앞
        m = re.search(r'</style>', t)
        t = (t[:m.end()] + '\n' + CSS + t[m.end():]) if m else (CSS + '\n' + t)

    # 떠 있던 다크 버튼을 상단바 슬롯으로 옮긴다 (fixed 를 없애는 것이 목적)
    # ★ 9/1 실측 (팀장이 두 번 지적한 «버튼이 미세하게 움직인다» 의 답).
    #   여기가 «페이지에 토글이 있으면 그것을 쓴다» 였다. 그래서 테마 버튼이
    #   세 종류로 갈렸다: 허브·표지·예산안 «테마» 40.9px · 자료실·백과 «다크»
    #   46.3px · 커리큘럼 «다크» 43px. 오른쪽 묶음이 그만큼 밀려 팀 자료실 ·
    #   도메인 백과 · 학습 커리큘럼 · 예산안 네 버튼이 8.3px 흔들렸다
    #   (왼쪽 여섯은 흔들림 0 이었다. 팀장이 본 그대로다).
    #   더구나 페이지가 가진 토글은 저장 키·기본값도 제각각이라 자료실은
    #   «다크로 시작» 했다. 바는 자기 버튼 하나만 쓴다. 글자도 «테마» 로 고정한다
    #   (상태에 따라 «다크»/«라이트» 로 바뀌면 폭이 다시 흔들린다).
    for _mb in list(re.finditer(r'<button[^>]*id="themeBtn".*?</button>', t, re.S))[::-1]:
        t = t[:_mb.start()] + t[_mb.end():]
    # ★ 9/1 배포본 실측: 버튼만 걷어내니 «페이지가 가진 토글 스크립트» 가 살아남아
    #   내 버튼을 찾아 b.textContent = 다크 로 덧칠하고 클릭 핸들러를 하나 더 달았다.
    #   그래서 로컬 파일에는 «테마» 인데 화면에는 «다크» 46.3px 로 떴다
    #   (원칙 3: 파일을 본 것은 결과가 아니다. 화면을 봐야 안다).
    #   버튼을 지웠으면 그 버튼을 부리던 스크립트도 함께 지운다.
    _oldjs = re.compile(r'<script[^>]*>(?:(?!</script>).)*getElementById\('
                        r'[^)]*themeBtn[^)]*\)(?:(?!</script>).)*</script>', re.S)
    for _ms in list(_oldjs.finditer(t))[::-1]:
        t = t[:_ms.start()] + t[_ms.end():]
    # ★ 9/1 세 번째 실측 (팀장이 세 번 지적한 그것). 버튼과 스크립트를 지웠는데도
    #   폭이 달랐다: 자료실 46.3px · 예산안 40.9px. 같은 «테마» 두 글자인데.
    #   원인은 페이지가 가진 #themeBtn CSS 다. 옛 «떠 있는 버튼» 용이라
    #   position:fixed 와 letter-spacing:.12em 을 갖고 있고, id 선택자(1,0,0)라
    #   전역바의 클래스 규칙을 이긴다. 1.536px x 2글자 = 그 5.4px 차이였다.
    #   버튼을 지웠으면 그 버튼의 CSS 도 지운다. 셋이 한 벌이다.
    t = re.sub(r'#themeBtn[^{}]*\{[^}]*\}\s*', '', t)
    # ★ 2026-09-02 실측. 위 한 줄이 «껍데기» 를 남겼다.
    #   darkmode 가 넣는 `@media print{#themeBtn{display:none!important}}` 에서
    #   안쪽 규칙만 지워져 `<style>@media print{}</style>` 가 남는다.
    #   생성 페이지는 매 빌드 통째로 다시 쓰니 하나로 그치지만, 손으로 관리하는
    #   brief · index · setup 은 주입만 받으므로 **빌드마다 하나씩 쌓였다.**
    #   실측: 세 장 모두 77개. 오류가 안 나는 실패다 (원칙 2).
    #   빈 줄을 tidy 로 막았듯, 빈 껍데기도 여기서 막는다.
    t = strip_empty_css(t)
    # ★ 2026-09-02 정정. 전에는 여기서 darkmode 의 소유 마커를 뗐다.
    #   그러자 darkmode 가 «자기 옛 블록» 을 못 찾아 매 빌드 새로 하나씩 붙였다
    #   (실측: index 의 light 블록이 1회 2개 -> 3회 4개, 매회 +590자).
    #   마커는 남의 것이다. 걷어내지 않는다. darkmode 가 짝마커로 자기 범위를
    #   갖게 됐으므로 안을 비워도 다음 빌드가 정확히 제 블록을 지운다.
    ctl = _pdf                       # 옛 보조 내비에서 건진 PDF 버튼
    if True:
        # ★ #85: 토글 없는 페이지 27장 실측. 팀장 결정(08-09)은 「모든 페이지」다.
        #   버튼과 JS 를 여기서 만들어 준다. 페이지가 다크 CSS 를 이미 갖고 있으면
        #   (거의 전부) 그대로 동작한다.
        # ★ 실측 (팀장 9/1): 저장 키가 둘이었다. 표지는 'foothold-theme',
        #   내가 만든 토글은 'theme'. 서로 못 읽어 «표지는 밝은데 허브는 다크» 가
        #   났다. 사이트 정본 키 하나로 통일한다.
        # ★ 2026-09-14. 팀장이 「SVG 컬러가 이전 컬러로 돌아갔다」고 잡았다.
        #   `<img>` 안의 그림은 «격리된 문서» 라 이 페이지의 data-theme 이 안 닿고,
        #   그림은 OS 설정(prefers-color-scheme)만 볼 수 있었다. OS 가 라이트인
        #   사람이 사이트를 다크로 바꾸면 그림만 라이트로 남았다.
        #
        #   정하는 자리를 여기 하나로 모은다. 테마마다 구운 파일을 갈아끼운다.
        #   짝은 `tools/svg_theme.py` 가 굽고, 어느 그림이 짝을 갖는지는 빌드가
        #   `data-themed` 로 표시한다. 브라우저에서 «이름» 으로 고르지 않는다.
        #
        #   클릭과 첫 로드가 같은 함수를 부른다. 한쪽만 달면 새로 연 페이지와
        #   토글한 페이지가 서로 다른 말을 한다.
        _figs_js = "window.fhFigs=function(t){try{var g=document.querySelectorAll('img[data-themed]'),i,e,u,q,b;for(i=0;i<g.length;i++){e=g[i];u=e.getAttribute('src');if(!u)continue;q=u.indexOf('?');b=(q<0?u:u.slice(0,q));if(!e.dataset.fhLight)e.dataset.fhLight=b.replace(/\\.dark\\.svg$/,'.svg');b=e.dataset.fhLight;if(t==='dark')b=b.replace(/\\.svg$/,'.dark.svg');if(b!==(q<0?u:u.slice(0,q)))e.setAttribute('src',b+(q<0?'':u.slice(q)));}}catch(err){}};"
        _js = ("var h=document.documentElement,"
               "t=h.dataset.theme==='dark'?'light':'dark';h.dataset.theme=t;"
               "try{localStorage.setItem('foothold-theme',t)}catch(e){}"
               ";if(window.fhFigs)window.fhFigs(t)")
        ctl = ('<button id="themeBtn" type="button" aria-label="테마 전환" '
               'onclick="' + _js + '" '
               'style="cursor:pointer;background:var(--card);color:var(--ink-3);'
               'border:1px solid var(--rule);border-radius:99px">테마</button>')
        # ★ 9/1 팀장 실측: 「백과는 라이트로 시작하는데 커리큘럼은 다크」.
        #   여기가 원인이다. 조건이 «앞 3000자에 data-theme 글자가 있나» 였는데
        #   커리큘럼은 CSS 에 :root[data-theme=...] 를 일찍 갖고 있어 «이미 있다» 로
        #   판정돼 부트 스크립트를 못 받았다. 스크립트가 없으면 data-theme 이
        #   안 붙고 미디어쿼리가 이겨 OS 다크인 사람에게 다크로 뜬다.
        #   CSS 가 아니라 «부트 스크립트가 있나» 를 본다.
        # ★ 스크립트를 navctl «안»에 넣으면 인라인 상자가 생겨 바 높이가 달라진다.
        #   머리로 올린다 (실측: 48px vs 50px).
        boot = ('<script id="fh-theme-boot">try{'
                'var _t=localStorage.getItem("foothold-theme")'
                '||localStorage.getItem("theme");'
                'if(_t)document.documentElement.dataset.theme=_t;'
                'else document.documentElement.dataset.theme="light"}'
                'catch(e){}</script>'
                '<script id="fh-figs">' + _figs_js +
                'document.addEventListener("DOMContentLoaded",'
                'function(){window.fhFigs(document.documentElement.dataset.theme)});</script>')
        # ★ 2026-09-03 (foothold-lab#137). 여기가 «없으면 넣는다» 였다. 그래서
        #   첫 빌드와 두 번째 빌드의 head 순서가 갈렸다. 첫 빌드는 ia-css 를 넣은
        #   뒤 부트를 넣어 «ia-css 다음 부트» 가 되는데, 두 번째 빌드는 이미 있는
        #   부트를 그 자리에 둔 채 ia-css 만 새로 넣어 «부트 다음 ia-css» 가 됐다.
        #   내용은 같고 순서만 달라 A1 과 A2 가 바이트로 갈렸다 (허브 6장 실측).
        #   위 ia-css 와 똑같이 «걷어내고 언제나 다시 넣는다». 자리가 한 곳으로 고정된다.
        t = re.sub(r'<script id="fh-theme-boot">.*?</script>', '', t, flags=re.S)
        t = re.sub(r'<script id="fh-figs">.*?</script>', '', t, flags=re.S)
        if '</head>' in t:
            t = t.replace('</head>', boot + '</head>', 1)
        else:
            t = boot + t

    # ★ 삽입과 제거를 대칭으로. 자기 블록 앞뒤 공백을 «정확히 한 줄» 로 못박는다.
    #   전에는 제거가 공백을 안 거두고 삽입만 반복해 <body> 뒤 칸이 빌드마다
    #   하나씩 늘었다 (실측: setup·budget·chosun-materials 이 매 빌드 +1자).
    m = re.search(r'<body[^>]*>', t)
    if m:
        rest = t[m.end():].lstrip(' \t\r\n')
        t = t[:m.end()] + '\n' + gnav(cur, ctl) + '\n' + rest
    else:
        # body 가 없는 조각. 스타일 블록 다음, 실제 내용 앞에 넣는다.
        m = re.search(r'</style>\s*', t)
        pos = m.end() if m else 0
        rest = t[pos:].lstrip(' \t\r\n')
        t = t[:pos] + gnav(cur, ctl) + '\n' + rest
    io.open(path, 'w', encoding='utf-8', newline='\n').write(tidy(t))
    return True


def _shell(title, body, cur):
    base = io.open(os.path.join(VAULT, 'research.html'), encoding='utf-8').read()
    head = base.split('</head>', 1)[0]
    head = re.sub(r'<title>.*?</title>', '<title>%s · FOOTHOLD</title>' % title,
                  head, flags=re.S)
    return ('%s\n%s\n</head>\n<body>\n%s\n<div class="wrap">\n%s\n</div>\n</body>\n</html>\n'
            % (head, CSS, gnav(cur), body))


def build_hubs(assigned):
    made = []
    for key, ko, en, fname, lede in ia.HUBS:
        items = [(p, v) for p, v in assigned.items() if v[0] == key]
        # 회의는 최신이 위. 나머지는 갈래 묶음 안에서 제목순.
        groups = {}
        for p, v in items:
            groups.setdefault(v[1] or GROUP_FALLBACK, []).append((p, v))
        # ★ 2026-08-29. 가나다순이었다. 그래서 「기록」이 맨 위, 「안내」가
        #   중간에 오는 뜻 없는 배열이 나왔다. 팀장 지적: 「순서에 뜻이 없다」
        #   읽는 순서로 놓는다. 목록에 없는 묶음은 뒤로, 그 안에서 큰 것부터.
        # ★ 2026-08-29 실측. 「아직 안 갈린 것 3」이 일정 허브 «중간» 에 박혀 있었다.
        #   목록에 없는 묶음과 미분류가 같은 자리를 받아, 미분류가 크면 앞으로 왔다.
        #   미분류는 «무슨 일이 있어도» 맨 뒤다. 분류를 안 한 것이 위에 오면
        #   순서가 뜻을 잃는다 (철칙 3: 크기와 순서가 뜻을 실어야 한다).
        def rank(g):
            if g == GROUP_FALLBACK:
                return (2, 0, g)
            if g in GROUP_ORDER:
                return (0, GROUP_ORDER.index(g), g)
            return (1, -len(groups[g]), g)
        order = sorted(groups.keys(), key=rank)
        # ★ 허브마다 「무엇이 먼저인가」가 다르다 (#73). 한 규칙을 전부에 쓰면
        #   어딘가는 반드시 뜻을 잃는다. 실측으로 잡았다: 산출물 12장이 참조수순으로
        #   섞여 9/4 다음에 12/11 이 왔다. **일정 허브에서 순서란 마감이다.**
        for g in order:
            if key == 'meeting':
                groups[g].sort(key=lambda x: x[0], reverse=True)   # 최신이 위
            elif key == 'schedule':
                # 마감이 가까운 것이 위. 단 «그 묶음의 목차» 페이지는 맨 앞이다.
                groups[g].sort(key=lambda x: (0 if x[0] in GROUP_INDEX else _due(x[1]),
                                              x[1][2]))
            else:
                # 남들이 많이 딛고 선 글 -> 최근 것 순. 파일명순이 아니다.
                lean = leaned_on()
                groups[g].sort(key=lambda x: (-lean.get(x[0], 0),
                                              -_daynum(x[0]), x[0]))

        # ★ 「먼저 볼 것」 (#73 · 철칙 3: 크기와 순서가 뜻을 실어야 한다)
        #   손으로 고르지 않는다. **첫 묶음의 첫 카드**다. 묶음 순서(GROUP_ORDER)가
        #   이미 「무엇을 먼저 봐야 하나」를 담고 있고, 묶음 안 순서는 「남들이 많이
        #   딛고 선 글」이 정한다. 그 둘의 결론을 크기로 한 번 더 말할 뿐이다.
        #   목록이 아니라 «관계와 순서» 가 정하므로 문서가 늘어도 손이 안 간다.
        hero = None
        if order and groups[order[0]]:
            hero = groups[order[0]][0]
            groups[order[0]] = groups[order[0]][1:]
            if not groups[order[0]]:
                order = order[1:]

        chunks = []
        if hero:
            hp, hv = hero
            chunks.append(
                '<a class="hhero" data-added="%s" href="%s">'
                '<div class="hk">먼저 볼 것</div>'
                '<div class="t">%s%s</div>%s%s</a>'
                % (_added(hp), hp, hv[2],
                   ('<span class="hv">%s</span>' % hv[5]) if len(hv) > 5 and hv[5] else '',
                   ('<div class="d">%s</div>' % hv[3]) if hv[3] else '',
                   ('<div class="m">%s</div>' % hv[4]) if len(hv) > 4 and hv[4] else ''))
        for g in order:
            rows = groups[g]
            # ★ 2026-08-29. 묶음 이름만으로는 무엇이 들었는지 모른다.
            #   한 줄 설명을 붙인다. 8갈래 묶음은 ROLES.md 표에서 읽어 온다.
            # ★ 이름을 glede 로 둔다. lede 로 두면 «페이지 한 줄 설명» 변수를
            #   덮어 표지 설명이 통째로 사라진다. 실제로 그렇게 짰다가 잡았다.
            glede = ''
            try:
                glede = ia.group_lede(g, _LAB)
            except Exception:
                pass
            chunks.append('<div class="hgroup">%s <span style="font-weight:600">%d</span></div>'
                          % (g, len(rows)))
            if glede:
                chunks.append('<div class="hlede">%s</div>' % glede)
            # 넘버링과 작성 메타. 「이 글이 언제 등록됐는지」가 없어서 UX 가 나빴다
            # (팀장 지적 2026-08-26). 번호는 묶음 안에서 1부터 센다.
            cards = []
            for n, (p, v) in enumerate(rows, 1):
                meta = v[4] if len(v) > 4 else ''
                ver = v[5] if len(v) > 5 else ''
                # ★ #75. NEW 배지가 허브에서만 안 떴다. 이유는 둘이었다.
                #   ① newbadge 의 카드 정규식이 `class="doc|rcard"` 만 봤는데
                #      허브 카드는 클래스가 없다.
                #   ② newbadge 는 [1.88], 허브 생성은 [1.898]. 나중에 덮어 썼다.
                #   판정 JS 는 `a[data-added]` 라 이미 범용이다. 날짜만 주면 된다.
                #   날짜 계산은 newbadge 것을 그대로 빌린다 (두 자리에 두지 않는다).
                cards.append(
                    '<a data-added="%s" href="%s"><span class="hn">%02d</span>'
                    '<div class="t">%s%s</div>%s%s</a>'
                    % (_added(p), p, n, v[2],
                       ('<span class="hv">%s</span>' % ver) if ver else '',
                       ('<div class="d">%s</div>' % v[3]) if v[3] else '',
                       ('<div class="m">%s</div>' % meta) if meta else ''))
            chunks.append('<div class="hlist">%s</div>' % ''.join(cards))
        body = ('<h1>%s <span style="font-size:.6em;color:var(--ink-3);'
                'font-weight:600">%s</span></h1>\n<p class="lede">%s</p>\n%s'
                % (ko, en, lede, ''.join(chunks)))
        io.open(os.path.join(VAULT, fname), 'w', encoding='utf-8',
                newline='\n').write(_shell(ko, body, key))
        made.append((fname, ko, len(items)))
    return made


def home_block(assigned):
    """표지 상단: 띠 + 바로가기 + 허브."""
    dig = sorted([p for p, v in assigned.items() if v[0] == '_banner'], reverse=True)
    parts = []
    # 관문 D-day 는 다이제스트 띠보다 위에 온다. 「언제까지」가 「무엇을 했나」보다 급하다.
    try:
        import deliverables_page as dlv
        _lab = dlv.lab_root()
        if _lab:
            parts.append(dlv.band_html(dlv.build_rows(_lab, dlv.today_kst())))
    except Exception as _e:
        print('  [!] D-day 띠 생략: %s' % _e)
    # ★ 표지 개정 (팀장 8/31): 바로가기 4버튼 제거 (전역바와 완전 중복).
    #   공지를 표지로 끌어올려 다이제스트와 «같은 줄 2열»로 놓는다.
    # ★ 표지 상단 3열 (#95 · 팀장 지시 8/31): 공지 · 다이제스트 · 산출물.
    #   타겟 축을 처음으로 화면에 쓴다. 팀원은 「뭐가 바뀌었나」, 운영진·멘토는
    #   「지금 무엇을 내고 있나」를 표지 첫 줄에서 받는다. 산출물이 3클릭이었다.
    three = []
    if os.path.exists(os.path.join(VAULT, 'notice-latest.html')):
        three.append('<a class="band b-notice" href="notice-latest.html">'
                     '<div class="t">팀 공지</div>'
                     '<div class="d">지금 무엇이 바뀌었나</div></a>')
    if dig:
        wk = re.search(r'(\d{4})-W(\d+)', dig[0])
        three.append('<a class="band b-digest" href="%s"><span class="w">%s</span>'
                     '<div class="t">주간 다이제스트</div>'
                     '<div class="d">이번 주에 알게 된 것</div></a>'
                     % (dig[0], ('%s년 %s주차' % wk.groups()) if wk else ''))
    if os.path.exists(os.path.join(VAULT, 'deliverables.html')):
        try:
            import deliverables_page as _dlv
            _rows = [r for r in _dlv.build_rows(_dlv.lab_root(), _dlv.today_kst())
                     if r[3] >= 0]
            _near = min(_rows, key=lambda r: r[3]) if _rows else None
            # ★ 2026-09-16. 죽은 수였다. 첫 화면에 D-14 와 D-15 가 같이 떴다.
            _sub = (('<span class="dd-live" data-due="%s">D-%d</span> '
                     '%s · %d장')
                    % (_near[1].isoformat(), _near[3], _near[0], len(_near[4]))
                    if _near else '무엇을 언제까지 내는가')
        except Exception:
            _sub = '무엇을 언제까지 내는가'
        three.append('<a class="band b-deliv" href="deliverables.html">'
                     '<div class="t">산출물 현황</div>'
                     '<div class="d">%s</div></a>' % _sub)
    if three:
        parts.append('<div class="bands3">%s</div>' % ''.join(three))
    # ★ v3: 타일이 장수 대신 «상태 한 줄»을 말한다. 산문이 아니라 코드가
    #   계산한다 (hub3.state_lines). 급한 허브만 색이 다르다.
    import hub3
    try:
        st = hub3.state_lines()
    except Exception as _e:
        print('  [!] 타일 상태줄 계산 실패: %s' % _e)
        st = {}
    parts.append('<div class="hubs">%s</div>' % ''.join(
        '<a class="%s" href="%s"><div class="k">%s</div><div class="e">%s</div>'
        '<div class="d">%s</div></a>'
        % ('hot' if st.get(k, ('', False))[1] else '', f, ko, en,
           st.get(k, (lede, False))[0])
        for k, ko, en, f, lede in _cover_tiles()))
    extra = ''
    try:
        import deliverables_page as dlv
        extra = '<style>%s</style><script>%s</script>' % (dlv.CSS, dlv.JS)
    except Exception:
        pass
    return IDX_A + CSS + extra + '\n' + '\n'.join(parts) + IDX_B


def main():
    ok, why = _kat_empty_css()
    if not ok:
        print('  [!] 빈 CSS 껍데기 제거 자기시험 실패: %s' % why)
        return False
    ok, why = _kat_gnav()
    if not ok:
        print('  [!] 전역바 공백 정규화 자기시험 실패: %s' % why)
        return False
    assigned = ia.main()
    if assigned is None:
        return False
    # ★ v3 (결정 20260830-hub-v3): 여섯 허브는 각자의 뼈대로 그린다.
    #   build_hubs(한 틀 여섯 장)는 v3 실패 시 대비용으로만 남긴다.
    import hub3
    made = hub3.build(assigned, VAULT, _shell, _site())
    print('  허브 %d개: %s' % (len(made),
                              ' · '.join('%s %d장' % (m[1], m[2]) for m in made)))

    # 산출물 현황 페이지. 허브 셸을 그대로 써서 생김새가 어긋나지 않게 한다.
    try:
        import deliverables_page as dlv
        _lab = dlv.lab_root()
        if _lab:
            _rows = dlv.build_rows(_lab, dlv.today_kst())
            _body = ('<h1>산출물 현황 <span style="font-size:.6em;color:var(--ink-3);font-weight:600">Deliverables</span></h1>'
                     '<p class="lede">우리가 무엇을 언제까지 내는가. 상태는 각 문서의 「상태」 줄이 정한다. 문서를 고치면 다음 배포에 그대로 반영된다.</p>'
                     + '<style>' + dlv.CSS + '</style>' + dlv.body_html(_rows))
            io.open(os.path.join(VAULT, 'deliverables.html'), 'w', encoding='utf-8',
                    newline='\n').write(_shell('산출물 현황', _body, 'schedule'))
            _n = sum(len(r[4]) for r in _rows)
            print('  산출물 현황: 관문 %d개 · 산출물 %d개' % (len(_rows), _n))
    except Exception as _e:
        print('  [!] 산출물 페이지 실패: %s' % _e)

    idx = os.path.join(VAULT, 'index.html')
    t = io.open(idx, encoding='utf-8').read()
    t = re.sub(re.escape(IDX_A) + r'.*?' + re.escape(IDX_B), '', t, flags=re.S)
    m = re.search(r'<h2 class="sec">', t)
    if not m:
        print('  [!] 표지 삽입 지점을 못 찾음'); return False
    t = t[:m.start()] + home_block(assigned) + '\n\n' + t[m.start():]
    io.open(idx, 'w', encoding='utf-8', newline='\n').write(tidy(t))
    # 표지 블록 다음이 「현재 상태」, 그 다음이 「최근 올라온 것」이다.
    # 셋 다 마커로 감싸여 있고 서로의 마커 안으로 들어가지 않는다.
    import recent as _recent
    _recent.inject(VAULT, _site(), assigned)
    # ★ 숫자를 손으로 적지 않는다. 8/29 에 여섯째 허브를 더하고도 화면이
    #   「허브 5」라고 말하고 있었다. 원천에서 센다 (셀프클레임 원칙).
    print('  표지: 띠 + 바로가기 %d + 허브 %d 주입'
          % (sum(1 for v in assigned.values() if v[0] == '_quick'), len(ia.HUBS)))

    # 전역 상단바를 모든 배포 페이지에
    n = 0
    # ★ 실측 (팀장 8/31): 허브 6장에 «지금 여기» 표시가 없었다.
    #   허브 페이지는 ROOT 라 assigned 에 없어 이 루프를 안 탔고, 그래서
    #   전역바 CSS 갱신도 못 받았다. 허브 자신도 목록에 넣는다.
    targets = list(assigned.items())
    targets += [(h[3], (h[0], '', h[1], h[4])) for h in ia.HUBS]
    # ★ 2026-09-03 (foothold-lab#137). 허브와 «똑같은 이유» 로 하나가 더 빠져 있었다.
    #   assigned 는 이 함수 맨 앞에서 만들어진다. deliverables.html 은 그보다 «뒤» 에
    #   만들어지므로, 이전 빌드의 파일이 남아 있지 않은 트리에서는 assigned 에도
    #   ia.HUBS 에도 없어 이 루프를 안 탔다. 그래서 전역바도 테마 토글도 못 받았다.
    #   이전 파일이 있으면 그것이 이미 받아 둔 것을 넘겨받아 아무도 몰랐다.
    #   실측: 소스에서만 만든 빌드의 deliverables.html 은 themeBtn 0 이었고
    #   [3.45] 브랜드 관문이 «토글없음 0 -> 1» 로 잡았다.
    #   ia 는 이 페이지를 'schedule' 로 배정한다. 여기서 넣는 값도 같게 둬야
    #   첫 빌드와 다음 빌드의 결과가 같다.
    if 'deliverables.html' not in assigned:
        targets.append(('deliverables.html', ('schedule', '', '산출물 현황', '')))
    for p, v in targets:
        f = os.path.join(VAULT, p)
        if not os.path.exists(f):
            continue
        if p in DECK_PAGES:
            continue                      # 덱은 자체 «← 표지» 내비를 쓴다
        cur = v[0] if not v[0].startswith('_') else (p if v[0] == '_quick' else '')
        if inject_nav(f, cur):
            n += 1
    for _, _, _, f, _ in ia.HUBS:
        pass
    print('  전역 상단바 %d개 페이지' % n)
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main() else 1)
