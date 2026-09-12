# -*- coding: utf-8 -*-
"""정본 markdown 을 site 의 연구 페이지로 옮긴다.

    python tools/md2site.py docs/research/20260911-eval-protocol-v2.md \
        --out ../foothold-site/research-20260911-eval-protocol-v2.html

분류: 운영
작성: 오흥재 · 2026-09-12 06:20
근거: 팀장 「평가 정본에 대한 문서도 업로드를 지금 안한 것 같네?」
요지: 정본이 저장소에만 있으면 웹에서 읽는 사람은 닿을 수 없다
상태: 확정

## 왜 이것이 있나

`report-v1.html` 이 「측정 규격과 판정 정의는
`docs/research/20260911-eval-protocol-v2.md` 가 정본입니다」라고 적어 두었는데,
그 문서의 웹판이 없었다. **글자로만 적힌 정본은 웹에서 못 연다.**

연구 페이지를 손으로 쓰던 방식은 표 164줄짜리 정본에는 안 맞는다. 두 번째
정본이 나오면 또 같은 일이 생긴다.

## 무엇을 옮기나

| markdown | 결과 |
|---|---|
| 머리 다섯 줄 (`> 분류:` …) | 문서 머리의 메타 줄 |
| `#` ~ `####` | 절 번호를 떼어 `<h2>` `<h3>` |
| 표 | `<table>` · 숫자 열은 오른쪽 정렬 |
| ``` 코드울 | `<pre>` |
| `` `확인됨` `` | 근거 딱지 |
| `**굵게**` · `` `코드` `` · `[글](주소)` | 그대로 |

## 무엇을 «안» 하나

도면과 SVG 는 안 만든다. 손으로 쓴 연구 페이지의 그림은 그 페이지에 남는다.
이 변환기는 **인용하는 판**을 옮기는 것이지 읽는 판을 만드는 것이 아니다.
"""
from __future__ import annotations

import argparse
import html
import io
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gatelib  # noqa: E402

# site 의 색과 조판. `foothold-site/index.html` 과 같은 값이다.
STYLE = """:root{
  --gnav-width:1100px;--gnav-pad:clamp(18px,3vw,40px);  /* 전역바가 이 폭을 따라온다 */
  --paper:#f6f5f1;--paper-2:#eeece6;--card:#fff;
  --ink:#161c26;--ink-2:#4a5566;--ink-3:#7c8798;
  --rule:#d9d6cd;--brand:#0e7a6e;--dim-soft:#e0f0ed;
  --note:#a86a08;--note-soft:#fbf0dc;
  --stop:#a3342a;--stop-soft:#fbe9e7;
  --grid:rgba(22,28,38,.04);
  /* 본문에 심은 도면이 쓰는 색이다. **하나라도 빠지면 그 칠은 검정으로
     떨어진다** `확인됨` (2026-09-12 · 도면 5장이 전부 검은 상자였다).
     값은 site 색 체계에 맞춘 것이고, 이름은 도면 쪽을 따른다. */
  --accent:#0e7a6e;--accent-soft:#e0f0ed;
  --ok:#0e7a6e;
  --warn:#a86a08;--warn-soft:#fbf0dc;
  --bad:#a3342a;--bad-soft:#fbe9e7;
  --rule-2:#efede6;
}
/* **어두운 화면.** 없으면 site 의 어두운 토큰을 못 받아 본문은 밝은 채로
   전역바만 «흰 로고» 로 바뀐다. 밝은 바에 흰 글씨라 로고가 사라진다
   `확인됨` (2026-09-12 · 관문이 잡았다. 예산안 때와 같은 부류).
   심은 도면의 색도 여기서 함께 뒤집힌다. */
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --paper:#12161d;--paper-2:#191e27;--card:#181d26;
  --ink:#e9e7e1;--ink-2:#adb5c1;--ink-3:#7d8693;
  --rule:#2b323d;--brand:#3ec7b4;--dim-soft:#11302c;
  --note:#dc9a30;--note-soft:#332710;
  --stop:#e56d5e;--stop-soft:#331c19;
  --grid:rgba(233,231,225,.04);
  --accent:#3ec7b4;--accent-soft:#11302c;--ok:#3ec7b4;
  --warn:#dc9a30;--warn-soft:#332710;
  --bad:#e56d5e;--bad-soft:#331c19;--rule-2:#232a35;
}}
:root[data-theme="dark"]{
  --paper:#12161d;--paper-2:#191e27;--card:#181d26;
  --ink:#e9e7e1;--ink-2:#adb5c1;--ink-3:#7d8693;
  --rule:#2b323d;--brand:#3ec7b4;--dim-soft:#11302c;
  --note:#dc9a30;--note-soft:#332710;
  --stop:#e56d5e;--stop-soft:#331c19;
  --grid:rgba(233,231,225,.04);
  --accent:#3ec7b4;--accent-soft:#11302c;--ok:#3ec7b4;
  --warn:#dc9a30;--warn-soft:#332710;
  --bad:#e56d5e;--bad-soft:#331c19;--rule-2:#232a35;
}
*{margin:0;padding:0;box-sizing:border-box}
body{
  font-family:'Pretendard','Malgun Gothic','Segoe UI',system-ui,sans-serif;
  background:var(--paper);color:var(--ink);line-height:1.7;min-height:100vh;
  background-image:linear-gradient(var(--grid) 1px,transparent 1px),
                   linear-gradient(90deg,var(--grid) 1px,transparent 1px);
  background-size:32px 32px;
}
.wrap{max-width:1100px;margin:0 auto;
  padding:clamp(32px,5vh,64px) clamp(18px,3vw,40px) 80px}
a{color:var(--brand)}
.mono,code{font-family:'JetBrains Mono',ui-monospace,'Consolas',monospace;
  font-size:.92em}
code{background:var(--paper-2);padding:1px 5px;border-radius:4px}
.crumb{font-size:.78rem;color:var(--ink-3);margin-bottom:10px}
.crumb a{text-decoration:none;font-weight:600}
.crumb a:hover{text-decoration:underline}
.eyebrow{font-size:.6rem;letter-spacing:.22em;font-weight:700;color:var(--brand);
  text-transform:uppercase;display:flex;align-items:center;gap:10px;margin-bottom:12px}
.eyebrow::after{content:'';flex:1;height:1px;background:var(--rule)}
h1{font-size:clamp(1.6rem,3.4vw,2.4rem);font-weight:800;letter-spacing:-.03em;
  line-height:1.15;text-wrap:balance}
header{border-bottom:2px solid var(--ink);padding-bottom:20px;margin-bottom:8px}
.meta{display:grid;gap:4px;font-size:.82rem;color:var(--ink-2);
  background:var(--card);border:1px solid var(--rule);border-radius:10px;
  padding:14px 18px;margin:22px 0 30px}
.meta b{color:var(--ink);font-weight:700;display:inline-block;min-width:3.2em}
h2{font-size:1.24rem;font-weight:800;letter-spacing:-.02em;margin:44px 0 14px;
  padding-top:18px;border-top:1px solid var(--rule);display:flex;
  align-items:baseline;gap:12px}
h2 .n{font-size:.72rem;color:var(--brand);font-weight:700;letter-spacing:.1em;
  font-family:'JetBrains Mono',ui-monospace,monospace}
h3{font-size:1rem;font-weight:700;margin:28px 0 10px;color:var(--ink)}
h4{font-size:.9rem;font-weight:700;margin:22px 0 8px;color:var(--ink-2)}
p{margin:12px 0}
strong{font-weight:700}
.tw{overflow-x:auto;margin:16px 0}
table{border-collapse:collapse;width:100%;font-size:.88rem;background:var(--card)}
th,td{border:1px solid var(--rule);padding:7px 11px;text-align:left;
  vertical-align:top}
th{background:var(--paper-2);font-weight:700;white-space:nowrap}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
pre{background:#161c26;color:#e8e6e0;border-radius:10px;padding:16px 18px;
  overflow-x:auto;margin:16px 0;font-size:.84rem;line-height:1.6}
pre code{background:none;color:inherit;padding:0}
.fig{margin:24px 0;background:var(--card);border:1px solid var(--rule);
  border-radius:10px;padding:16px 18px 12px}
.fig img,.fig>svg{width:100%;height:auto;display:block}
.fig figcaption{font-size:.8rem;color:var(--ink-3);margin-top:10px;
  padding-top:10px;border-top:1px solid var(--rule)}
.said{background:var(--dim-soft);color:var(--brand);font-size:.7rem;
  font-weight:700;padding:1px 7px;border-radius:4px;white-space:nowrap}
blockquote{border-left:3px solid var(--brand);background:var(--card);
  padding:12px 16px;margin:16px 0;border-radius:0 8px 8px 0;color:var(--ink-2)}
hr{border:0;border-top:1px solid var(--rule);margin:34px 0}
footer{margin-top:48px;padding-top:18px;border-top:1px solid var(--ink);
  font-size:.78rem;color:var(--ink-3);display:grid;gap:5px}
@media(prefers-reduced-motion:reduce){*{animation:none!important}}"""

# 공통 정본(`AGENTS.md` §4-1)은 **머리 여섯 줄**이다. 여섯째 `판` 은
# 살아 있는 문서(규칙·계획·실측·조사)에만 단다. 그래서 앞 다섯은 반드시,
# `판` 은 있으면 실는다 (저장소 실측 · 여섯 줄 65개 · 다섯 줄 40개).
META_KEYS = ("분류", "작성", "근거", "요지", "상태")
META_EXTRA = ("판",)
NUMERIC = re.compile(r"^[\s0-9.,%+\-x×~/]*$")


IMAGES = []

# 원문이 있는 폴더. 그림 경로가 이 기준이라 `as_figure` 가 파일을 열 때 쓴다.
SOURCE_DIR = ""


def site_nav(site_dir):
    """site 의 전역바를 **여기서** 붙인다.

    전에는 만든 뒤에 따로 주입했다. 그러면 **다음에 다시 만들 때 사라진다**
    `확인됨` (2026-09-12 · 정본 페이지의 전역바가 그렇게 날아갔다).
    붙이는 자리는 만드는 자리여야 한다.

    한 벌은 `tools/gnav_extract.py` 가 만든다. 규칙을 여기서 베끼면
    `@media` 가 풀려 로고 색과 바 배경이 어긋난다.
    """
    got = []

    for name in ("gnav.html", "gnav-head.html"):
        path = os.path.join(site_dir, "assets", name)

        if not os.path.isfile(path):
            raise SystemExit("assets/%s 가 없다. tools/gnav_extract.py 를 "
                             "먼저 돌린다" % name)

        got.append(io.open(path, encoding="utf-8").read().strip())

    bar = re.sub(r'href="(?!/|https?:)([^"]+)"', r'href="/\1"', got[0])
    bar = bar.replace('src="assets/', 'src="/assets/')
    bar = bar.replace('class="on"', 'class=""')
    # 「연구」 가 지금 여기다.
    #
    # **빈 class 를 «갈아끼워» 한다.** 앞에 더하면 한 태그에 class 가
    # 둘이 되고 브라우저는 앞의 빈 것만 읽는다. 그래서 「지금 여기」
    # 표시가 안 났다 `확인됨` (2026-09-12 화면 실측).
    bar = bar.replace('<a class="" href="/hub-research.html"',
                      '<a class="on" href="/hub-research.html"')
    return bar, got[1]


def web_path(src):
    """`../assets/visual/x.svg` (lab 기준) -> `/assets/visual/x.svg` (site 기준)."""
    return "/" + src.replace("../", "").lstrip("/")


def inline(text):
    """줄 안의 서식.

    **그림을 «먼저» 잡는다.** 링크 정규식이 `![alt](src)` 의 `[alt](src)` 를
    먼저 먹으면 `!` 만 남아 `!<a href=...>` 가 된다 `확인됨`
    (2026-09-12 · 정본 도면 5장이 전부 그렇게 깨졌다. 팀장이 잡았다).
    """
    out = html.escape(text, quote=False)

    def as_figure(m):
        alt, src = m.group(1), m.group(2)
        IMAGES.append(src)
        body = ""

        # **SVG 는 본문에 심는다.** `<img src>` 로 부르면 그 SVG 는 따로 문서라
        # 페이지의 색 변수를 못 받는다. `var(--ink)` 가 전부 검정으로 떨어져
        # 도면이 검은 덩어리가 된다 `확인됨` (2026-09-12 팀장 지적).
        if src.lower().endswith(".svg") and SOURCE_DIR:
            got = os.path.normpath(os.path.join(SOURCE_DIR, src))

            if os.path.isfile(got):
                svg = io.open(got, encoding="utf-8").read()
                svg = re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", svg)
                body = svg.strip()

        if not body:
            body = ('<img src="%s" alt="%s" loading="lazy">'
                    % (html.escape(web_path(src), quote=True),
                       html.escape(alt, quote=True)))

        return ('<figure class="fig">%s<figcaption>%s</figcaption></figure>'
                % (body, html.escape(alt, quote=False)))

    out = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", as_figure, out)
    out = re.sub(r"`확인됨`", '<span class="said">확인됨</span>', out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', out)
    # `<https://…>` 는 markdown 의 자동 링크다. 안 다루면 꺾쇠가 그대로 보이고
    # 누를 수도 없다 `확인됨` (2026-09-12 · 웹판 링크가 그렇게 나갔다).
    out = re.sub(r"&lt;(https?://[^\s&]+)&gt;", r'<a href="\1">\1</a>', out)
    return out


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def render_table(rows):
    """표 한 장. **숫자 열은 오른쪽으로 민다.**"""
    head = split_row(rows[0])
    body = [split_row(r) for r in rows[2:]]
    align = []

    for i in range(len(head)):
        column = [r[i] for r in body if i < len(r) and r[i]]
        align.append("num" if column and all(NUMERIC.match(c) for c in column) else "")

    out = ['<div class="tw"><table><thead><tr>']

    for i, cell in enumerate(head):
        out.append('<th%s>%s</th>'
                   % (' class="num"' if align[i] else "", inline(cell)))

    out.append("</tr></thead><tbody>")

    for row in body:
        out.append("<tr>")

        for i, cell in enumerate(row):
            cls = align[i] if i < len(align) else ""
            out.append('<td%s>%s</td>' % (' class="num"' if cls else "", inline(cell)))

        out.append("</tr>")

    out.append("</tbody></table></div>")
    return "".join(out)


def convert(text):
    """markdown 본문을 site 조각으로. 머리 다섯 줄은 따로 돌려준다."""
    lines = text.split(chr(10))
    title = ""
    meta = {}
    out = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # 제목 한 줄
        if not title and line.startswith("# "):
            title = line[2:].strip()
            i += 1
            continue

        # 머리 다섯 줄
        # **여섯 줄을 다 읽는다.** 다섯만 읽으면 `판` 줄이 머리를
        # 빠져나가 본문의 인용문으로 떨어진다 `확인됨` (2026-09-12 화면 실측).
        got = re.match(r"^>\s*(%s):\s*(.+)$"
                       % "|".join(META_KEYS + META_EXTRA), line)

        if got:
            meta[got.group(1)] = got.group(2).strip()
            i += 1
            continue

        # 코드울
        if line.startswith("```"):
            j = i + 1
            body = []

            while j < len(lines) and not lines[j].startswith("```"):
                body.append(lines[j])
                j += 1

            out.append("<pre><code>%s</code></pre>"
                       % html.escape(chr(10).join(body), quote=False))
            i = j + 1
            continue

        # 표
        if line.strip().startswith("|") and i + 1 < len(lines) \
                and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            j = i

            while j < len(lines) and lines[j].strip().startswith("|"):
                j += 1

            out.append(render_table(lines[i:j]))
            i = j
            continue

        # 인용
        if line.startswith("> "):
            j = i
            body = []

            while j < len(lines) and lines[j].startswith(">"):
                body.append(lines[j].lstrip(">").strip())
                j += 1

            out.append("<blockquote>%s</blockquote>"
                       % inline(" ".join(x for x in body if x)))
            i = j
            continue

        # 제목
        # **깊은 제목도 받는다.** 전에는 `####` 이후를 통째로 버려서, 합친
        # 정본의 소절 70여 개가 화면에서 사라졌다 `확인됨` (2026-09-12).
        if line.startswith("#### ") or line.startswith("##### "):
            out.append("<h4>%s</h4>" % inline(line.split(" ", 1)[1].strip()))
            i += 1
            continue

        if line.startswith("### "):
            out.append("<h3>%s</h3>" % inline(line[4:].strip()))
            i += 1
            continue

        if line.startswith("## "):
            head = line[3:].strip()
            # 절 번호는 **구분 기호가 따라올 때만** 번호다.
            # 안 그러면 `1부 · 지금…` 이 「1」 + 「부 · 지금…」 로
            # 쪼개진다 `확인됨` (2026-09-12 화면 실측 · 팀장이 잡았다).
            num = re.match(r"^([\d]+(?:[.\-][\d]+)*|부록)\s*[.·]\s*(.+)$",
                           head)

            if num and num.group(2):
                out.append('<h2><span class="n">%s</span>%s</h2>'
                           % (html.escape(num.group(1)), inline(num.group(2))))
            else:
                out.append("<h2>%s</h2>" % inline(head))

            i += 1
            continue

        if line.strip() == "---":
            out.append("<hr>")
            i += 1
            continue

        # 문단. 빈 줄까지 모은다.
        if line.strip():
            j = i
            body = []

            while j < len(lines) and lines[j].strip() \
                    and not lines[j].startswith(("#", ">", "|", "```")) \
                    and lines[j].strip() != "---":
                body.append(lines[j].strip())
                j += 1

            if body:
                piece = inline(" ".join(body))
                # 그림 하나뿐인 문단은 `<p>` 로 감싸지 않는다
                out.append(piece if piece.startswith("<figure")
                           and piece.endswith("</figure>")
                           else "<p>%s</p>" % piece)
                i = j
                continue

        i += 1

    return title, meta, chr(10).join(out)


def page(title, meta, body, source, nav=("", "")):
    lines = ['<!doctype html>', '<html lang="ko">', "<head>",
             '<meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             "<title>%s · FOOTHOLD</title>" % html.escape(title),
             '<meta name="description" content="%s">'
             % html.escape(meta.get("요지", title), quote=True),
             "<style>%s</style>" % STYLE, nav[1], "</head>", "<body>",
             nav[0],
             '<div class="wrap">', "<header>",
             '<div class="crumb"><a href="/">FOOTHOLD</a> · '
             '<a href="/research.html">연구</a> · 정본</div>',
             '<div class="eyebrow">Evaluation Protocol</div>',
             "<h1>%s</h1>" % html.escape(title), "</header>",
             '<div class="meta">']

    for key in META_KEYS + META_EXTRA:
        if meta.get(key):
            lines.append("<div><b>%s</b> %s</div>" % (key, inline(meta[key])))

    lines.append("</div>")
    lines.append(body)
    lines.append("<footer>")
    lines.append("<div>이 문서는 <b>인용하는 판</b>입니다. 숫자와 규격의 정본입니다.</div>")
    lines.append('<div>원문 <span class="mono">%s</span> · '
                 'foothold-lab 저장소가 정본이고 이 쪽은 그것을 옮긴 것입니다.</div>'
                 % html.escape(source))
    lines.append("</footer>")
    lines.append("</div>")
    lines.append("</body>")
    lines.append("</html>")
    return chr(10).join(lines) + chr(10)


def main():
    p = argparse.ArgumentParser(description="정본 markdown 을 site 페이지로")
    p.add_argument("source", help="옮길 markdown")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    # 그림 경로는 원문 기준이다. `inline()` 이 SVG 를 열려면 먼저 알아야 한다.
    global SOURCE_DIR
    SOURCE_DIR = os.path.dirname(os.path.abspath(args.source))
    text = io.open(args.source, encoding="utf-8").read()
    title, meta, body = convert(text)

    # 공지는 `# 제목` 없이 머리의 `요지` 가 제목 노릇을 한다.
    if not title:
        title = re.sub(r"^[^가-힣A-Za-z0-9]*", "", meta.get("요지", "")).strip()

    if not title:
        raise SystemExit("제목을 못 찾았다. `# 제목` 이나 머리의 `요지` 가 필요하다: %s"
                         % args.source)

    missing = [k for k in META_KEYS if not meta.get(k)]

    # 문서 표준 다섯 줄이 없으면 막는다 (`CLAUDE.md` 문서 표준).
    if missing:
        raise SystemExit("머리 다섯 줄에 %s 가 없다" % ", ".join(missing))

    rel = os.path.relpath(args.source, os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..")).replace("\\", "/")
    site = os.path.dirname(os.path.abspath(args.out))
    out = page(title, meta, body, rel, site_nav(site))
    io.open(args.out, "w", encoding="utf-8").write(out)

    # **그림을 같이 옮긴다.** 안 옮기면 페이지만 올라가고 도면이 404 가 된다
    # `확인됨` (2026-09-12 · 정본 도면 5장이 site 에 하나도 없었다).
    here = SOURCE_DIR
    moved = []

    for src in IMAGES:
        got = os.path.normpath(os.path.join(here, src))

        if not os.path.isfile(got):
            raise SystemExit("그림이 없다: %s (본문의 %s)" % (got, src))

        dst = os.path.join(site, web_path(src).lstrip("/").replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(got, dst)
        moved.append(os.path.relpath(dst, site).replace(os.sep, "/"))

    print("  %s · %.1f KB" % (args.out, len(out.encode("utf-8")) / 1024))
    print("  그림 %d장 옮김" % len(moved))

    for name in moved:
        print("    " + name)
    print("  절 %d · 표 %d · 코드울 %d"
          % (out.count("<h2>") + out.count('<h2><span'),
             out.count("<table>"), out.count("<pre>")))

    # **조용한 실패를 막는다.** 옮기다 통째로 비면 소리를 낸다.
    # 원문에 있던 만큼 나왔나. 표가 없는 글(공지)도 있으므로 **원문과 견준다.**
    md_tables = len(re.findall(r"^\s*\|[\s:|-]+\|\s*$", text, re.M))

    if out.count("<table>") != md_tables:
        raise SystemExit("원문 표 %d개인데 %d개만 나왔다"
                         % (md_tables, out.count("<table>")))

    body_only = re.sub(r"<style>.*?</style>", "", out, flags=re.S)

    if len(re.sub(r"<[^>]+>", "", body_only).strip()) < len(text) * 0.5:
        raise SystemExit("옮긴 것이 너무 적다. 원문을 다 읽었는지 보라")

    # 그림이 링크로 깨진 채 나가면 안 된다
    if "!<a href" in out:
        raise SystemExit("그림이 링크로 깨졌다. `![]()` 를 먼저 잡아야 한다")

    if IMAGES and out.count("<figure class=\"fig\">") != len(IMAGES):
        raise SystemExit("본문 그림 %d장인데 %d장만 나왔다"
                         % (len(IMAGES), out.count("<figure class=\"fig\">")))

    # ── 팀장이 잡은 넷. 다시 나가면 안 된다 (2026-09-12) ──────────────
    #
    # **글자가 아니라 뜻을 본다.** 첫 판은 「그 문자열이 있나」 만 봐서
    # codex 가 주입한 아홉 건이 그대로 통과했다 `확인됨` · 주석 안에 넣거나
    # 숫자 엔티티로 쓰거나 빈 껍데기로 개수만 맞추면 다 뚫렸다.
    from gatelib import live, plain
    alive = live(out)          # 주석을 걷어낸 «살아 있는» 부분
    reads = plain(out)         # 엔티티를 푼 «읽히는» 글자

    if "<!--gnav:v1-->" not in alive:
        raise SystemExit("전역바가 없다")

    boot = re.search(r'<script[^>]*id="fh-theme-boot"[^>]*>(.*?)</script>',
                     alive, re.S)

    if not boot:
        raise SystemExit("테마 부팅이 없다. 없으면 어두운 화면이 기본이 된다")

    lack = [why for why, mark in (("저장값을 안 읽는다", "getItem"),
                                  ("표식을 안 찍는다", "dataset.theme"),
                                  ("기본값이 없다", '"light"'))
            if mark not in boot.group(1)]

    if lack:
        raise SystemExit("테마 부팅이 " + " · ".join(lack))

    if not re.search(r'<link[^>]+href="/assets/gnav\.css"', alive):
        raise SystemExit("전역바 CSS 링크가 없다")

    # 한 태그에 class 가 둘이면 발리 반은 무시된다. 조용히 틀린다.
    dup = len(re.findall(r'class="[^"]*"\s+class="', out))

    if dup:
        raise SystemExit("한 태그에 class 가 둘인 자리 %d곳" % dup)

    if re.search(r"<https?://", reads):
        raise SystemExit("`<주소>` 가 글자로 남았다. 자동 링크를 안 풀었다")

    # **도면이 쓰는 색을 페이지가 다 들고 있나.** 하나라도 없으면 그 칠은
    # 검정으로 떨어지는데 오류는 안 난다. 밝음과 어두움을 «둘 다» 센다.
    css = "".join(re.findall(r"<style[^>]*>(.*?)</style>", alive, re.S))
    want = set(re.findall(r"var\((--[a-z0-9-]+)\)",
                          "".join(m.group(0) for m
                                  in re.finditer(r"<svg.*?</svg>", alive, re.S))))

    for state in gatelib.STATES:
        have = set(gatelib.token_map(css, state))
        short = sorted(want - have)

        if short:
            raise SystemExit("표식=%s · OS=%s 에서 도면 색 %s 가 없다. "
                             "검은 상자로 나간다" % (state[0], state[1], " ".join(short)))

    pale = gatelib.token_map(css, ("none", "light")).get("--paper")
    dusk = gatelib.token_map(css, ("none", "dark")).get("--paper")

    if not dusk or pale == dusk:
        raise SystemExit("어두운 토큰이 없거나 밝은 것과 같다 (%s / %s)" % (pale, dusk))

    svgs = [s for s in IMAGES if s.lower().endswith(".svg")]

    # **개수만 맞추면 안 된다.** 빈 `<svg>` 다섯 개로 수량을 맞춘
    # 주입이 통과했다 `확인됨` (2026-09-12 codex 7회차).
    # 그려진 것이 실제로 있는지 센다.
    drawn = [m.group(0) for m in re.finditer(r"<svg.*?</svg>", out, re.S)]

    if svgs and len(drawn) < len(svgs):
        raise SystemExit("SVG %d장 중 %d장만 본문에 심겼다. `<img>` 로 나가면 "
                         "페이지 색을 못 받는다" % (len(svgs), len(drawn)))

    for i, one in enumerate(drawn, 1):
        marks = len(re.findall(r"<(path|rect|circle|line|polyline|polygon|text|g)[ />]",
                               one))

        if marks < 3:
            raise SystemExit("%d번째 도면에 그려진 것이 %d개뿐이다. 껍데기다"
                             % (i, marks))

    # **원문이 아니라 «읽히는 글자» 를 본다.**
    # `&#8212;` 는 화면에서 em dash 로 읽힌다. 원문에 `·` 이 없다고
    # 통과시키면 금지한 것이 그대로 나간다 `확인됨`
    # (2026-09-12 codex 7회차 · em dash 와 `%%` 가 숫자 엔티티로 통과).
    for why, bad in (("em dash", chr(8212)), ("%% 가 새었다", "%%")):
        if bad in out or bad in reads:
            raise SystemExit("나가면 안 되는 것이 있다: %s" % why)


if __name__ == "__main__":
    main()
