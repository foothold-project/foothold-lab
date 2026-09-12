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
import sys

sys.stdout.reconfigure(encoding="utf-8")

# site 의 색과 조판. `foothold-site/index.html` 과 같은 값이다.
STYLE = """:root{
  --paper:#f6f5f1;--paper-2:#eeece6;--card:#fff;
  --ink:#161c26;--ink-2:#4a5566;--ink-3:#7c8798;
  --rule:#d9d6cd;--brand:#0e7a6e;--dim-soft:#e0f0ed;
  --note:#a86a08;--note-soft:#fbf0dc;
  --stop:#a3342a;--stop-soft:#fbe9e7;
  --grid:rgba(22,28,38,.04);
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
.said{background:var(--dim-soft);color:var(--brand);font-size:.7rem;
  font-weight:700;padding:1px 7px;border-radius:4px;white-space:nowrap}
blockquote{border-left:3px solid var(--brand);background:var(--card);
  padding:12px 16px;margin:16px 0;border-radius:0 8px 8px 0;color:var(--ink-2)}
hr{border:0;border-top:1px solid var(--rule);margin:34px 0}
footer{margin-top:48px;padding-top:18px;border-top:1px solid var(--ink);
  font-size:.78rem;color:var(--ink-3);display:grid;gap:5px}
@media(prefers-reduced-motion:reduce){*{animation:none!important}}"""

META_KEYS = ("분류", "작성", "근거", "요지", "상태")
NUMERIC = re.compile(r"^[\s0-9.,%+\-x×~/]*$")


def inline(text):
    """줄 안의 서식. **굵게** · `코드` · [글](주소) · `확인됨` 딱지."""
    out = html.escape(text, quote=False)
    out = re.sub(r"`확인됨`", '<span class="said">확인됨</span>', out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', out)
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
        got = re.match(r"^>\s*(%s):\s*(.+)$" % "|".join(META_KEYS), line)

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
        if line.startswith("### "):
            out.append("<h3>%s</h3>" % inline(line[4:].strip()))
            i += 1
            continue

        if line.startswith("## "):
            head = line[3:].strip()
            num = re.match(r"^([\d.\-]+|부록)\s*[.·]?\s*(.*)$", head)

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
                out.append("<p>%s</p>" % inline(" ".join(body)))
                i = j
                continue

        i += 1

    return title, meta, chr(10).join(out)


def page(title, meta, body, source):
    lines = ['<!doctype html>', '<html lang="ko">', "<head>",
             '<meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             "<title>%s · FOOTHOLD</title>" % html.escape(title),
             '<meta name="description" content="%s">'
             % html.escape(meta.get("요지", title), quote=True),
             "<style>%s</style>" % STYLE, "</head>", "<body>",
             '<div class="wrap">', "<header>",
             '<div class="crumb"><a href="/">FOOTHOLD</a> · '
             '<a href="/research.html">연구</a> · 정본</div>',
             '<div class="eyebrow">Evaluation Protocol</div>',
             "<h1>%s</h1>" % html.escape(title), "</header>",
             '<div class="meta">']

    for key in META_KEYS:
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

    text = io.open(args.source, encoding="utf-8").read()
    title, meta, body = convert(text)

    if not title:
        raise SystemExit("첫 줄에 `# 제목` 이 없다: %s" % args.source)

    missing = [k for k in META_KEYS if not meta.get(k)]

    # 문서 표준 다섯 줄이 없으면 막는다 (`CLAUDE.md` 문서 표준).
    if missing:
        raise SystemExit("머리 다섯 줄에 %s 가 없다" % ", ".join(missing))

    rel = os.path.relpath(args.source, os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..")).replace("\\", "/")
    out = page(title, meta, body, rel)
    io.open(args.out, "w", encoding="utf-8").write(out)

    print("  %s · %.1f KB" % (args.out, len(out.encode("utf-8")) / 1024))
    print("  절 %d · 표 %d · 코드울 %d"
          % (out.count("<h2>") + out.count('<h2><span'),
             out.count("<table>"), out.count("<pre>")))

    # **조용한 실패를 막는다.** 옮기다 통째로 비면 소리를 낸다.
    if out.count("<table>") < 5 or len(out) < 8000:
        raise SystemExit("옮긴 것이 너무 적다. 원문을 다 읽었는지 보라")

    for bad in (chr(8212), "%%"):
        if bad in out:
            raise SystemExit("나가면 안 되는 것이 있다: %r" % bad)


if __name__ == "__main__":
    main()
