# -*- coding: utf-8 -*-
"""02_team/TEAM_ACCESS.md → 05_deliverables/team-access.html

  ★ 원문은 Markdown 이 단일 진실이다. 이 파일은 **옮겨 적지 않는다**. 읽어서 변환한다.
    (setup.html 은 손으로 옮겨 만든 탓에 원문과 갈라질 위험을 계속 안고 있다.
     새 페이지부터는 이 방식으로 간다.)

  md 에 없는 것을 여기서 더하지 않는다. 다만 **읽는 순서**는 손본다. 
  팀원이 가장 자주 쓰는 것(접속 주소)과 가장 자주 어기는 것(프로세스 정리)을
  본문 위로 끌어올린 요약 카드를 표지 아래에 넣는다. 내용은 전부 원문에서 가져온다.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hl
import mdpage

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)                                  # 05_deliverables
SRC = os.path.join(__import__('roots').proj(), '02_team', 'TEAM_ACCESS.md')
OUT = os.path.join(VAULT, 'team-access.html')

# ★ 표 규칙 (2026-09-14). 팀장이 폰에서 「난이도」가 난/이/도 로 접히는 것을
#   잡았다. 원인이 셋 겹쳐 있었고, 하나만 고쳤을 때는 나머지 둘이 그대로
#   무너뜨렸다.
#     1. `searchbox` 의 `main table{min-width:0}` 이 `min-width` 를 무력화
#        (2026-08-28 사고의 «남은 반쪽» 이었다. 지웠다)
#     2. 420 px 고정폭 안에서 긴 열이 짧은 열을 먹어 「단계」가 39 px 가 됨
#     3. `overflow-wrap:anywhere` 가 min-content 폭을 «한 글자» 로 붕괴시켜
#        표 레이아웃에 그 좁힘을 허용함. `word-break:keep-all` 이 있어도
#        anywhere 가 이긴다
#
#   그래서 열 수로 나누지 않고 «모든 표» 에 같은 규칙을 준다. 처음엔 다섯 열
#   이상에만 `wide` 를 달았는데, 3열짜리가 그대로 무너졌다 (표 20 「단계」).
#     · min-width:max-content     내용이 요구하는 폭을 확보하고 `.tw` 가 스크롤
#     · width:100%                넓은 화면에서는 여전히 컨테이너를 채움
#     · 칸 폭 상한 26ch          긴 산문 칸이 표를 1542 px 로 펴지 않게 막는다
#     · overflow-wrap:break-word  넘칠 때만 자르되 min-content 는 안 무너뜨림
#     · code 의 nowrap 은 푼다    anywhere 를 막으려던 것이라 같이 없앤다.
#                                 두면 긴 경로가 칸 밖으로 197 px 넘친다
#
#   실측 (같은 출처 iframe 390/430/768/1280 px · 표 69개 · 평가 프로토콜 정본.
#   `resize_window` 는 성공을 찍고도 창을 안 바꾼 전과가 있어 쓰지 않았다):
#     머리말 2줄 이상  17개 -> 0개     최대 표폭  659 px -> 617 px
#     칸 밖 넘침        0곳 -> 0곳     1280 px 에서 990 px 그대로 (무변화)
#     짧은 토큰 쪼개짐   6건 -> 0건    (「rails」「27」「16」 이 갈라지던 것)
#
#   관문: `tablefix.blocky` 가 표를 짜부라뜨리는 규칙을, `tools/predeploy.py` 가
#   이 두 선언이 사라지거나 뒤집히는 것을 본다. 둘 다 알려진 답으로 시험한다.
CSS = r"""
:root{
  --paper:#f6f5f1;--paper-2:#eeece6;--card:#fff;
  --ink:#161c26;--ink-2:#4a5566;--ink-3:#7c8798;
  --rule:#d9d6cd;--dim:#0e7a6e;--dim-soft:#e0f0ed;
  --note:#a86a08;--note-soft:#fbf0dc;
  --stop:#a3342a;--stop-soft:#fbe9e7;
  --grid:rgba(22,28,38,.04);
  --measure:760px;
  /* ★ --dim / --note 를 연한 배경(--*-soft) 위 글자로 쓰면 대비가 모자란다.
     실측 --dim on --dim-soft = 4.43 · --note on --note-soft = 3.93 (둘 다 4.5 미달).
     그런 자리에는 아래 진한 짝을 쓴다. DESIGN.md §2 참조. */
  --dim-ink:#0b6459;
  --note-ink:#8a5600;
}
@media (prefers-color-scheme:dark){
  :root{
    --paper:#12161d;--paper-2:#191e27;--card:#181d26;
    --ink:#e9e7e1;--ink-2:#adb5c1;--ink-3:#7d8693;
    --rule:#2b323d;--dim:#3ec7b4;--dim-soft:#11302c;
    --note:#dc9a30;--note-soft:#332710;
    --stop:#e56d5e;--stop-soft:#331c19;
    --grid:rgba(233,231,225,.035);
    /* 어두운 모드에서는 soft 배경이 어두우므로 원래 토큰이 이미 충분히 밝다 */
    --dim-ink:#3ec7b4;
    --note-ink:#dc9a30;
  }
}
*{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:64px}
body{font-family:'Pretendard','Malgun Gothic','Segoe UI',system-ui,sans-serif;
  background:var(--paper);color:var(--ink);line-height:1.75;font-size:15px;
  -webkit-font-smoothing:antialiased;
  background-image:linear-gradient(var(--grid) 1px,transparent 1px),
                   linear-gradient(90deg,var(--grid) 1px,transparent 1px);
  background-size:32px 32px}

.top{position:sticky;top:0;z-index:60;background:var(--paper);border-bottom:1px solid var(--rule)}
.top .row{max-width:calc(var(--measure) + 4rem);margin:0 auto;padding:.55rem 1.5rem;
  display:flex;align-items:center;gap:.8rem;flex-wrap:wrap}
.top .home{font-size:.72rem;font-weight:700;color:var(--ink-2);text-decoration:none;
  border:1px solid var(--rule);background:var(--card);padding:.26rem .6rem;border-radius:4px}
.top .home:hover{border-color:var(--dim);color:var(--dim)}
.top .doc{font-size:.72rem;color:var(--ink-3);letter-spacing:.02em}
.top .sp{flex:1}
.pdfbtn{background:var(--card);border:1px solid var(--rule);color:var(--ink-2);
  padding:.26rem .6rem;font-family:inherit;font-size:.66rem;font-weight:800;letter-spacing:.1em;
  text-transform:uppercase;cursor:pointer;border-radius:4px;transition:.15s;line-height:1.3}
.pdfbtn:hover{border-color:var(--dim);color:var(--dim);background:var(--dim-soft)}
#prog{position:absolute;left:0;bottom:-1px;height:2px;background:var(--dim);width:0;transition:width .12s}

.wrap{max-width:calc(var(--measure) + 4rem);margin:0 auto;padding:2.2rem 1.5rem 5rem}

.hero{padding-bottom:1.6rem;border-bottom:2px solid var(--ink);margin-bottom:1.8rem}
.eyebrow{font-size:.62rem;font-weight:800;letter-spacing:.22em;text-transform:uppercase;
  color:var(--dim);margin-bottom:.5rem}
h1{font-size:2rem;font-weight:800;letter-spacing:-.02em;line-height:1.25;margin-bottom:.7rem}
.lede{font-size:1rem;color:var(--ink-2);max-width:min(42em,100%);word-break:keep-all}
.meta{display:flex;flex-wrap:wrap;gap:.35rem 1.6rem;margin-top:1rem;font-size:.72rem}
.meta .k{color:var(--ink-3);margin-right:.4rem}
.meta .v{color:var(--ink-2);font-weight:700}

section{margin-top:2.6rem}
h2{font-size:1.28rem;font-weight:800;letter-spacing:-.01em;padding-bottom:.45rem;
  border-bottom:1px solid var(--rule);margin-bottom:1rem}
h3{font-size:1rem;font-weight:800;margin:1.5rem 0 .55rem;color:var(--ink)}
h4{font-size:.88rem;font-weight:800;margin:1.1rem 0 .4rem;color:var(--ink-2)}
/* ★ 2026-09-08 감사 F-04. 모바일에서 페이지가 가로로 늘어났다.
   원인은 keep-all 의 «짝» 이 빠진 것이다. word-break:keep-all 은 한국어를
   낱말 중간에서 안 끊으려고 쓰는데, 그것만 두면 긴 URL 처럼 끊을 자리가
   없는 토큰이 상자 밖으로 삐져나가 페이지 자체를 넓힌다.
   p 에는 overflow-wrap 이 있었는데 li·td 에는 없었다. 실측에서 넘친 것이
   정확히 li 였다 (research-cloud-gpu-options: li 안쪽 폭 729px · 화면 345px).
   anywhere 는 «끊을 데가 없을 때만» 끊는다. 한국어 문장은 그대로 keep-all 이다.
   표와 pre 는 자기 컨테이너(.tw)에서 스크롤하므로 여기서 건드리지 않는다. */
p{margin:.6rem 0;overflow-wrap:anywhere;word-break:keep-all}
ul,ol{margin:.6rem 0 .6rem 1.2rem}
li{margin:.24rem 0;word-break:keep-all;overflow-wrap:anywhere}
dd,dt,figcaption,blockquote{overflow-wrap:anywhere}
b{font-weight:800}
a{color:var(--dim)}
code{font-family:'Consolas','D2Coding',monospace;font-size:.9em;background:var(--paper-2);
  border:1px solid var(--rule);padding:.05rem .28rem;border-radius:3px;word-break:break-all}
.vlink{font-size:.82em;color:var(--ink-3);background:var(--paper-2);border:1px solid var(--rule);
  padding:.02rem .32rem;border-radius:3px}
.vlink i{font-style:normal;opacity:.75}
blockquote{border-left:3px solid var(--dim);background:var(--dim-soft);padding:.7rem .95rem;
  margin:1rem 0;font-size:.88rem;color:var(--ink-2)}
blockquote p{margin:.25rem 0}
blockquote b{color:var(--ink)}

/* 표: 모바일에서 가로 스크롤 (DESIGN.md §5) */
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:1rem 0;border:1px solid var(--rule)}
/* 좁은 화면에서 칸이 짜부라지지 않게. 까닭은 이 파일 «표 규칙» 주석에. */
table{border-collapse:collapse;width:100%;min-width:max-content;font-size:.82rem;background:var(--card)}
th,td{border-bottom:1px solid var(--rule);padding:.5rem .7rem;text-align:left;vertical-align:top;
  word-break:keep-all;overflow-wrap:break-word}
th,td{max-width:26ch}/* 폭허용: 문단이 아니라 표 «열» 상한. 없으면 긴 산문 칸이 표를 1542 px 로 편다. 1280 px 에서는 무변화 (실측) */
td code,th code{white-space:normal;word-break:keep-all;overflow-wrap:break-word;max-width:none}
td .n,td .o{white-space:nowrap;overflow-wrap:normal}
th{background:var(--ink);color:var(--paper);font-weight:800;font-size:.72rem;
  letter-spacing:.04em;border-bottom:none}
tbody tr:last-child td{border-bottom:none}
tbody tr:nth-child(even){background:var(--paper-2)}

/* 코드 블록 + 복사 버튼 */
.cb{margin:1rem 0;border:1px solid var(--rule);background:#0f141b}
.cb-h{display:flex;align-items:center;gap:.5rem;padding:.3rem .6rem;background:#1a212b;
  border-bottom:1px solid #2b323d;font-size:.62rem;font-weight:800;letter-spacing:.1em;
  text-transform:uppercase;color:#7d8693}
.cb-h .copy{margin-left:auto;background:#232b36;border:1px solid #39424f;color:#c8cfd8;
  font-family:inherit;font-size:.62rem;font-weight:800;letter-spacing:.06em;padding:.16rem .5rem;
  border-radius:3px;cursor:pointer;transition:.14s}
.cb-h .copy:hover{background:var(--dim);border-color:var(--dim);color:#fff}
.cb-h .copy.done{background:#1b6b4a;border-color:#1b6b4a;color:#fff}
.cb pre{margin:0;padding:.75rem .85rem;overflow-x:auto;color:#dfe4ea;
  font-family:'Consolas','D2Coding',monospace;font-size:.76rem;line-height:1.7}
.cb pre .c{color:#6f7a88}

/* ── 표지 아래 요약 카드 ── */
.pin{display:grid;grid-template-columns:1fr 1fr;gap:.9rem;margin:1.6rem 0 .4rem}
@media (max-width:640px){.pin{grid-template-columns:1fr}}
.pin>div{border:1px solid var(--rule);background:var(--card);padding:.85rem .95rem}
.pin .lab{font-size:.6rem;font-weight:800;letter-spacing:.16em;text-transform:uppercase;
  color:var(--ink-3);margin-bottom:.4rem}
.pin.hot>div{border-color:var(--note);background:var(--note-soft)}
.big{font-family:'Consolas','D2Coding',monospace;font-size:1.05rem;font-weight:800;
  color:var(--dim-ink);word-break:break-all}
/* 본문(§3)에 나오는 접속 주소는 페이지에서 가장 자주 쓰는 값이다. 눈에 띄게 */
section .addr{border:2px solid var(--dim);background:var(--dim-soft);padding:.7rem .9rem}
section .addr .big{font-size:1.2rem}
.addr{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;margin-top:.2rem}
.addr .copy{background:var(--card);border:1px solid var(--dim);color:var(--dim);
  font-family:inherit;font-size:.64rem;font-weight:800;letter-spacing:.06em;
  padding:.16rem .5rem;border-radius:3px;cursor:pointer;transition:.14s}
.addr .copy:hover{background:var(--dim);color:#fff}
.addr .copy.done{background:#1b6b4a;border-color:#1b6b4a;color:#fff}

/* ── 도구 4종 역할 구분 (팀원이 가장 헷갈리는 것) ── */
.tools{display:grid;grid-template-columns:repeat(4,1fr);gap:.75rem;margin:1.2rem 0}
@media (max-width:820px){.tools{grid-template-columns:repeat(2,1fr)}}
@media (max-width:460px){.tools{grid-template-columns:1fr}}
.tool{border:1px solid var(--rule);background:var(--card);padding:.85rem .8rem;display:flex;
  flex-direction:column;gap:.35rem}
.tool.pick{border:2px solid var(--dim);background:var(--dim-soft)}
.tool .n{font-size:.6rem;font-weight:800;letter-spacing:.14em;color:var(--ink-3)}
.tool .t{font-size:.95rem;font-weight:800;line-height:1.3}
.tool.pick .t{color:var(--dim-ink)}
.tool .q{font-size:.76rem;color:var(--ink-2);flex:1}
.tool .f{font-size:.68rem;color:var(--ink-3);border-top:1px solid var(--rule);padding-top:.35rem;
  margin-top:.2rem;line-height:1.6}
.tool .f b{color:var(--ink-2)}
.tool .badge{display:inline-block;font-size:.6rem;font-weight:800;padding:.08rem .35rem;
  border-radius:2px;background:var(--dim);color:#fff;letter-spacing:.04em}
.tool .badge.warn{background:var(--note)}
.tool .badge.off{background:var(--ink-3)}

/* ── 경고 박스 (프로세스 정리) ── */
.warnbox{border:2px solid var(--note);background:var(--note-soft);padding:1rem 1.1rem;margin:1.2rem 0}
.warnbox .wh{font-size:.95rem;font-weight:800;color:var(--note-ink);margin-bottom:.5rem}
.warnbox .line{font-size:.92rem;font-weight:800;color:var(--ink);margin:.4rem 0}
.warnbox p{font-size:.84rem;color:var(--ink-2)}

/* 공개 페이지에서 가려진 값 안내 */
.redacted-note{display:block;font-size:.72rem;color:var(--ink-3);margin-top:.35rem;
  font-family:'Pretendard','Malgun Gothic',system-ui,sans-serif;font-weight:400}
.redacted-note b{color:var(--note-ink)}

/* 미확인 표시: 확정처럼 읽히면 안 된다 */
.unk{display:inline-block;font-size:.62rem;font-weight:800;letter-spacing:.06em;
  background:var(--stop);color:#fff;padding:.08rem .38rem;border-radius:2px;
  vertical-align:.08em;margin-right:.3rem}

@media print{
  @page{size:A4 portrait;margin:14mm 12mm}
  html{font-size:10.5px}
  body{background:#fff!important;background-image:none!important}
  .top,.pdfbtn,.copy{display:none!important}
  .wrap{max-width:none;padding:0}
  section{break-inside:auto;margin-top:1.4rem}
  h2,h3{break-after:avoid}
  .tw,.cb,blockquote,.tool,.warnbox,.pin>div{break-inside:avoid;page-break-inside:avoid}
  .tools,.pin{display:block}
  .tool,.pin>div{margin-bottom:.5rem}
  .cb{background:#f4f5f7!important;border:1px solid #ccc!important}
  .cb-h{background:#e9ecef!important;color:#555!important;border-color:#ccc!important}
  .cb pre{color:#161c26!important;white-space:pre-wrap!important;word-break:break-all}
  .cb pre .c{color:#666!important}
  a[href^="http"]::after{content:' (' attr(href) ')';font-size:.85em;color:#666;word-break:break-all}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .mdimg{break-inside:avoid;page-break-inside:avoid}
}

/* 마크다운 그림·영상: mdpage 가 만드는 <figure class="mdimg"> */
.mdimg{margin:1.5rem 0;padding:0}
.mdimg img{display:block;width:100%;height:auto;border:1px solid var(--rule);
  border-radius:4px;background:var(--card)}
.mdvid video{display:block;width:100%;height:auto;border:1px solid var(--rule);
  border-radius:4px;background:#0f141b}
.mdimg figcaption{font-size:.74rem;color:var(--ink-3);margin-top:.45rem;line-height:1.5}
"""
CSS += hl.CSS          # 코드 문법 강조 (hl.py 가 단일 원본)


JS = r"""
/* ★ 2026-09-08 감사 F-05. 이 블록은 98장에 실리는데 그 안의 두 요소는
   페이지마다 있기도 없기도 하다. 없는 요소에 그냥 붙여서 예외가 났다.
     pdfBtn  무방비 리스너 108장 · 버튼 8장 -> 100장에서 «로드 즉시» 예외
     prog    참조 99장 · 요소 1장          -> 98장에서 «스크롤할 때» 예외
   pdfBtn 쪽은 로드 순간 죽어 뒤따르는 스크립트가 통째로 멈춘다.
   prog 쪽은 잠복이라 스크롤하기 전까지 멀쩡해 보였고, 그래서 감사가
   런타임 예외를 1건만 관측했다. 정적으로는 98장이 안고 있었다.
   둘 다 «있을 때만» 붙인다. */
(function(){
  var pdf = document.getElementById('pdfBtn');
  if (pdf) pdf.addEventListener('click', function(){ window.print(); });
})();
(function(){
  var bar = document.getElementById('prog');
  if (!bar) return;
  addEventListener('scroll', function(){
    var h = document.documentElement;
    var p = h.scrollTop / Math.max(1, h.scrollHeight - h.clientHeight);
    bar.style.width = (p * 100) + '%';
  }, {passive:true});
})();
/* 복사 버튼: 코드 블록과 접속 주소 공용 */
document.addEventListener('click', function(e){
  var b = e.target.closest && e.target.closest('.copy');
  if (!b) return;
  var t = b.dataset.copy || (b.closest('.cb') && b.closest('.cb').querySelector('pre').innerText);
  if (!t) return;
  navigator.clipboard.writeText(t).then(function(){
    var old = b.textContent;
    b.textContent = '복사됨'; b.classList.add('done');
    setTimeout(function(){ b.textContent = old; b.classList.remove('done'); }, 1400);
  });
});
"""

# 원문 §2 표를 카드로: 내용은 TEAM_ACCESS.md 에서 그대로 가져온 것이다
TOOLS = [
    ('01', 'TensorBoard', '학습이 잘 되고 있나<br>곡선 · 보상 · 성공률',
     '동시 <b>제한 없음</b><br>RAM 78 MB', '가장 많이 씀', '', True),
    ('02', 'SSH → <code>--headless</code>', '학습 실행 · 중지',
     '여러 명<br>무거운 건 GPU 2장 = 2명', '설정 예정', 'warn', False),
    ('03', 'Isaac Sim GUI', '로봇이 <b>어떻게 걷는지</b> (3D)',
     '워크스테이션 앞 <b>1명</b><br>RAM 13.5GB · VRAM 9GB', '무거움', 'off', False),
    ('04', 'Isaac Sim 스트리밍', '3D 화면을 <b>원격으로</b>',
     '화면 <b>1개 공유</b><br>RAM 13.5GB · VRAM 9GB', '미확인', 'warn', False),
]


def mark_unverified(html):
    """「미확인 / 미정 / 미설치」에 빨간 배지를 붙인다.

      왜: 이 문서에는 확정 사실과 미확정이 섞여 있다. 팀원이 둘을 구분 못 하면
      "스트리밍으로 5명이 각자 본다" 같은 잘못된 계획이 선다. 사용자가 명시한 제약이다.

      ★ 태그 안(<b>미확인</b> 의 꺾쇠 사이)을 건드리면 HTML 이 깨진다.
        그래서 태그 단위로 쪼개 **텍스트 조각에만** 적용한다.
        (앞서 정규식 lookaround 로 피하려다 정작 <b>로 감싼 것들을 전부 놓쳤다.)
    """
    words = ('미확인', '미정', '미설치', '미조사', '미측정')
    out = []
    for chunk in re.split(r'(<[^>]*>)', html):
        if chunk.startswith('<'):
            out.append(chunk); continue
        for w in words:
            chunk = chunk.replace(w, '<span class="unk">%s</span>' % w)
        out.append(chunk)
    return ''.join(out)


def build():
    md = io.open(SRC, encoding='utf-8').read()
    title = mdpage.h1(md)

    # 표지에 쓸 앞머리(> 인용 블록)를 떼어내고, 본문은 첫 '---' 다음부터
    body_md = md.split('\n---\n', 1)[1] if '\n---\n' in md else md
    body = mdpage.render(body_md)

    # ★ .tools 로 감싸야 그리드가 된다. 안 감싸면 카드가 세로로 쭉 늘어선다.
    tools = '<div class="tools">' + ''.join(
        '<div class="tool%s"><div class="n">%s</div><div class="t">%s</div>'
        '<div class="q">%s</div><div class="f">%s</div>'
        '<div><span class="badge %s">%s</span></div></div>'
        % (' pick' if pick else '', n, t, q, f, cls, badge)
        for n, t, q, f, badge, cls, pick in TOOLS) + '</div>'

    # 이 주소는 scan.REDACT 가 웹으로 나갈 때 자리표시자로 바꾼다.
    # 원문(md)과 볼트에는 실제 값이 남는다. 팀원은 거기서 본다.
    TB = 'http://192.168.0.5:6006'
    pin = (
        '<div class="pin">'
        '  <div><div class="lab">가장 자주 쓸 것. TensorBoard</div>'
        '    <div class="addr"><span class="big">http://192.168.0.5:6006</span>'
        '      <button class="copy" type="button" data-copy="http://192.168.0.5:6006">복사</button></div>'
        '    <div style="font-size:.72rem;color:var(--ink-3);margin-top:.35rem">'
        '      학원 내부망에서만 · 여러 명 동시 접속 OK</div></div>'
        '  <div><div class="lab">구조</div>'
        '    <div style="font-size:.9rem;font-weight:800;line-height:1.6">'
        '      워크스테이션 1대 = <span style="color:var(--dim)">서버</span><br>'
        '      노트북 5대 = <span style="color:var(--dim)">클라이언트</span></div>'
        '    <div style="font-size:.72rem;color:var(--ink-3);margin-top:.35rem">'
        '      각자 노트북에 Isaac Sim을 설치하지 않습니다</div></div>'
        '</div>'
        '<div class="pin hot"><div style="grid-column:1/-1">'
        '  <div class="lab" style="color:var(--note-ink)">작업 끝나면 반드시</div>'
        '  <div style="font-size:.98rem;font-weight:800">창을 닫아도 프로세스는 죽지 않습니다.</div>'
        '  <div style="font-size:.8rem;color:var(--ink-2);margin-top:.3rem">'
        '    <code>nvidia-smi</code> 로 확인하고 <code>Stop-Process</code> 로 정리하세요. '
        '    5명이 각자 좀비를 남기면 <b>아무도 학습을 못 돌립니다.</b> → §6</div>'
        '</div></div>')

    # §2 표 자리에 카드를 끼운다 (표는 그대로 두고 카드를 앞에 붙인다. 원문 손실 없음)
    body = body.replace('<h2>2. 도구가 4개다. 헷갈리지 말 것</h2>',
                        '<h2>2. 도구가 4개다. 헷갈리지 말 것</h2>' + tools, 1)

    # TensorBoard 주소 강조 + 복사 버튼
    body = body.replace(
        '<div class="cb"><div class="cb-h">text<button class="copy" type="button" '
        'aria-label="복사">복사</button></div><pre>http://192.168.0.5:6006</pre></div>',
        '<div class="addr" style="margin:1rem 0"><span class="big">http://192.168.0.5:6006</span>'
        '<button class="copy" type="button" data-copy="http://192.168.0.5:6006">복사</button></div>')

    # §6 을 경고 박스로 감싼다
    body = body.replace(
        '<h3>창을 닫아도 프로세스는 죽지 않습니다</h3>',
        '<div class="warnbox"><div class="wh">🔴 창을 닫아도 프로세스는 죽지 않습니다</div>'
        '<p>아래는 실측 기록입니다. 규칙이 아니라 <b>실제로 일어난 일</b>입니다.</p></div>', 1)

    body = mark_unverified(body)

    # ── 공개 저장소로 나갈 값 치환 ──
    #   볼트는 PRIVATE 이라 실제 주소를 둬도 되지만 foothold-site 는 PUBLIC 이다.
    #   장비 주소를 공개 페이지에 남기지 않는다. (scan.py 가 남아 있으면 빌드를 세운다)
    import scan
    body, hits = scan.redact(body)
    pin, ph = scan.redact(pin)
    hits += ph
    if hits:
        body = body.replace('<span class="big">http://&lt;워크스테이션&gt;:6006</span>',
                            '<span class="big">http://&lt;워크스테이션&gt;:6006</span>'
                            + scan.REDACT_NOTE, 1)

    html = (
        '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>%s · FOOTHOLD</title>\n'
        '<meta name="description" content="워크스테이션 1대=서버, 노트북 5대=클라이언트. '
        'TensorBoard 접속·학습 실행·프로세스 정리 규칙. 2026-08-05 AI-WS01 실측 기준.">\n'
        '<style>%s</style>\n</head>\n<body>\n\n'
        '<div class="top"><div class="row">'
        '<a class="home" href="index.html">← 표지로</a>'
        '<span class="doc">FOOTHOLD · 팀원 사용 가이드</span><span class="sp"></span>'
        '<button class="pdfbtn" id="pdfBtn" type="button">PDF 저장</button>'
        '</div><div id="prog"></div></div>\n\n'
        '<div class="wrap">\n\n'
        '<div class="hero">\n'
        '  <div class="eyebrow">Team Access · 접속과 운영</div>\n'
        '  <h1>%s</h1>\n'
        '  <p class="lede">팀원은 <b>자기 노트북에 Isaac Sim을 설치하지 않습니다.</b> '
        '워크스테이션 한 대를 함께 씁니다. 무엇을 어떻게 쓰는지, 그리고 '
        '<b>끝나고 무엇을 반드시 해야 하는지</b>를 적었습니다.</p>\n'
        '  <div class="meta">'
        '<div><span class="k">대상</span><span class="v">팀원 4명</span></div>'
        '<div><span class="k">검증</span><span class="v">2026-08-05 · AI-WS01</span></div>'
        '<div><span class="k">구조</span><span class="v">서버 1 · 클라이언트 5</span></div>'
        '<div><span class="k">짝 문서</span><span class="v">개발환경 구축 가이드(관리자용)</span></div>'
        '</div>\n</div>\n\n'
        '%s\n\n%s\n\n</div>\n<script>%s</script>\n</body>\n</html>\n'
        % (title, CSS, title, pin, body, JS))

    io.open(OUT, 'w', encoding='utf-8').write(html)
    return html


if __name__ == '__main__':
    h = build()
    print('team-access.html : %d bytes · 섹션 %d · 표 %d · 코드 %d'
          % (len(h), h.count('<section'), h.count('<table'), h.count('class="cb"')))
