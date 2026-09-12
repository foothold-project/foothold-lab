# -*- coding: utf-8 -*-
"""아티팩트 HTML 을 저장소 markdown 으로 되돌린다.

    python tools/artifact2md.py <아티팩트.html> --out docs/research/xxx.md \
        --assets docs/assets/visual --slug eval-v2

분류: 운영
작성: 오흥재 · 2026-09-12 21:30
근거: 팀장 「이 아티팩트는 웹사이트 올리기 전에 형식 보려고 만든건데 왜 만든거냐? 안올릴 자료면?」
요지: 아티팩트에만 사는 내용은 증발한다. 저장소로 되돌려야 웹에도 올라간다
상태: 확정

## 왜 이것이 있나

평가 정본 아티팩트에 **13절 · 표 46 · 도해 8 · 사진 6** 이 들어 있는데,
저장소 markdown 에는 그 내용이 없었다. 그래서 웹판을 만들자 **다른, 더
얇은 문서**가 올라갔다 `확인됨` (2026-09-12 팀장 지적).

★ 업무 철칙 2: 모든 데이터는 휘발되지 않는다. 기억이 아니라 **시스템으로**
남긴다. 아티팩트는 보여 주는 자리이지 사는 자리가 아니다.

## 무엇을 하나

| 아티팩트 | 결과 |
|---|---|
| `<h1>` ~ `<h4>` | `#` ~ `####` |
| `<p>` · `<li>` | 문단 · 목록 |
| `<table>` | markdown 표 |
| `<svg>` | `assets/visual/<slug>-NN.svg` 로 저장하고 `![]()` |
| `<img src="data:...">` | 같은 폴더에 파일로 저장하고 `![]()` |
| `<pre>` | 코드울 |

**도해와 사진을 파일로 내린다.** base64 로 본문에 박혀 있으면 그 문서는
2 MB 가 되고, 고칠 수도 재사용할 수도 없다.
"""
from __future__ import annotations

import argparse
import base64
import html as _html
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

DROP = re.compile(r"<(script|style|template|noscript)\b.*?</\1>", re.S | re.I)
BLOCK = ("h1", "h2", "h3", "h4", "h5", "p", "table", "svg", "img", "pre",
         "ul", "ol", "blockquote", "figure", "hr")


# 아티팩트 원본에 **낱말 치환 사고**가 박혀 있다. 이전 세션이 「판」을
# 「에피소드」로 일괄 치환하며 단어 안까지 바꿨다.
#
#     발판을 밟았다     -> 발에피소드를 밟았다
#     그 판을 그대로    -> 그 에피소드을 그대로
#     가장 잘한 판 하나 -> 가장 잘에피소드 하나
#
# 원본을 못 고치므로 **옮기면서 되돌린다.** 안 그러면 다시 만들 때마다
# 되살아난다 `확인됨` (2026-09-12 codex 10회차가 문장 훼손으로 잡았다).
MENDED = (
    ("발에피소드를 밟았다", "발판을 밟았다"),
    ("그 에피소드을 그대로", "그 판을 그대로"),
    ("가장 잘에피소드 하나", "가장 잘한 판 하나"),
    ("100에피소드가라", "100판짜리"),
    ("에피소드을", "판을"),
)


def mend(text):
    """원본에 박힌 치환 사고를 되돌린다."""
    for bad, good in MENDED:
        text = text.replace(bad, good)

    return text


def text_of(chunk):
    """태그를 벗기고 엔티티를 푼 글자. 줄 안의 서식은 markdown 으로."""
    out = chunk
    # `<br>` 을 공백으로 지우면 두 항목이 한 단어처럼 붙는다.
    # 가운덩점은 표 칸 안에서도 안전하고 경계가 보인다.
    out = re.sub(r"<br\s*/?>", " · ", out, flags=re.I)
    out = re.sub(r"<(strong|b)\b[^>]*>(.*?)</\1>", r"**\2**", out, flags=re.S | re.I)
    out = re.sub(r"<(code|kbd)\b[^>]*>(.*?)</\1>", r"`\2`", out, flags=re.S | re.I)
    out = re.sub(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"[\2](\1)",
                 out, flags=re.S | re.I)
    out = re.sub(r"<[^>]*>", " ", out)
    out = _html.unescape(out)
    return mend(re.sub(r"[ \t ]+", " ", out).strip())


def cells(row):
    """한 줄의 칸. **`colspan` 과 `rowspan` 을 그대로 들고 온다.**

    `(글, 가로폭, 세로폭, 머리칸인가)` 로 돌려준다. 폭을 잃으면 값이 엉뚱한
    열에 놓인다 `확인됨` (2026-09-12 codex 9회차 · 「누적 42,800」 이 총
    에피소드 열이 아니라 둘째 열에 앉았다).
    """
    out = []

    for m in re.finditer(r"<(t[hd])\b([^>]*)>(.*?)</\1>", row, re.S | re.I):
        attr = m.group(2)
        wide = int((re.search(r'colspan="(\d+)"', attr) or [0, 1])[1])
        tall = int((re.search(r'rowspan="(\d+)"', attr) or [0, 1])[1])
        out.append((text_of(m.group(3)).replace("|", "｜"),
                    wide, tall, m.group(1).lower() == "th"))

    return out


def grid_of(chunk):
    """`<table>` 을 **병합을 푼 격자**로 편다.

    `rowspan` 은 아래 줄로 값을 내리고, `colspan` 은 오른쪽으로 빈 칸을 채운다.
    그래야 각 값이 원래 열에 남는다.
    """
    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", chunk, re.S | re.I)
    grid, carry = [], {}

    for raw in rows:
        got = cells(raw)

        if not got:
            continue

        line, col = [], 0

        while col in carry:
            text, left = carry[col]
            line.append(text)
            carry[col] = (text, left - 1) if left > 1 else None

            if carry[col] is None:
                del carry[col]

            col += 1

        for text, wide, tall, _is_head in got:
            line.append(text)

            if tall > 1:
                carry[col] = ("", tall - 1)

            col += 1

            # 가로로 묶인 칸은 오른쪽을 비워 둔다. 값의 열을 지킨다.
            for _ in range(wide - 1):
                line.append("")

                if tall > 1:
                    carry[col] = ("", tall - 1)

                col += 1

            while col in carry:
                text2, left2 = carry[col]
                line.append(text2)
                carry[col] = (text2, left2 - 1) if left2 > 1 else None

                if carry[col] is None:
                    del carry[col]

                col += 1

        grid.append(line)

    return grid, rows


def as_table(chunk):
    """표 한 장. **머리줄이 없으면 만들어 넣는다.**

    전에는 첫 «데이터» 행을 머리로 승격시켜 한 줄이 사라졌다.
    """
    grid, rows = grid_of(chunk)

    if not grid:
        return ""

    wide = max(len(r) for r in grid)
    grid = [r + [""] * (wide - len(r)) for r in grid]
    has_head = bool(re.search(r"<thead\b", chunk, re.I)) or bool(
        re.search(r"<th\b", rows[0], re.I))

    if has_head:
        head, body = grid[0], grid[1:]
    else:
        head, body = [""] * wide, grid

    out = ["| " + " | ".join(head) + " |",
           "|" + "|".join(["---"] * wide) + "|"]

    for r in body:
        out.append("| " + " | ".join(r) + " |")

    return "\n".join(out)


def as_list(chunk, ordered):
    items = re.findall(r"<li\b[^>]*>(.*?)</li>", chunk, re.S | re.I)
    out = []

    for i, one in enumerate(items, 1):
        got = text_of(one)

        if got:
            out.append(("%d. " % i if ordered else "- ") + got)

    return "\n".join(out)


def graphics(chunk, args, seen):
    """덩어리 안의 `<svg>` 와 base64 `<img>` 를 **파일로 내리고** 표기를 돌려준다.

    그림은 `<figure>` 나 `<p>` 안에 들어 있는 일이 많다. 바깥 블록을 먼저
    집으면 그림이 통째로 삼켜져 «글자만» 남는다 `확인됨` (2026-09-12 ·
    첫 판에서 도해 8장과 사진 6장이 전부 사라졌고 관문이 잡았다).
    """
    out = []

    for m in re.finditer(r"<svg\b.*?</svg>", chunk, re.S | re.I):
        seen["svg"] += 1
        name = "%s-fig%02d.svg" % (args.slug, seen["svg"])
        io.open(os.path.join(args.assets, name), "w",
                encoding="utf-8").write(m.group(0))
        cap = re.search(r'aria-label="([^"]*)"', m.group(0))
        out.append("![%s](%s/%s)" % (cap.group(1) if cap else "도해 %d" % seen["svg"],
                                     args.rel, name))
        seen["files"].append(name)

    for m in re.finditer(r'<img\b[^>]*src="data:image/([a-z]+);base64,([^"]+)"[^>]*>',
                         chunk, re.I):
        seen["img"] += 1
        ext = {"jpeg": "jpg"}.get(m.group(1), m.group(1))
        name = "%s-shot%02d.%s" % (args.slug, seen["img"], ext)
        io.open(os.path.join(args.assets, name), "wb").write(
            base64.b64decode(m.group(2)))
        alt = re.search(r'alt="([^"]*)"', m.group(0))
        out.append("![%s](%s/%s)" % (alt.group(1) if alt else "사진 %d" % seen["img"],
                                     args.rel, name))
        seen["files"].append(name)

    return out


def main():
    p = argparse.ArgumentParser(description="아티팩트를 markdown 으로")
    p.add_argument("source")
    p.add_argument("--out", required=True)
    p.add_argument("--assets", required=True, help="도해·사진을 내릴 폴더")
    p.add_argument("--slug", required=True, help="파일 이름 앞머리")
    p.add_argument("--rel", default="../assets/visual",
                   help="markdown 안에서 그림을 가리킬 상대 경로")
    args = p.parse_args()

    raw = io.open(args.source, encoding="utf-8", errors="replace").read()
    i = raw.find("<body")
    body = DROP.sub(" ", raw[i:] if i > 0 else raw)
    os.makedirs(args.assets, exist_ok=True)

    out = []
    seen = {"svg": 0, "img": 0, "files": []}
    pos = 0
    pat = re.compile(r"<(%s)\b" % "|".join(BLOCK), re.I)

    while True:
        m = pat.search(body, pos)

        if not m:
            break

        kind = m.group(1).lower()

        if kind in ("img", "hr"):
            end = body.find(">", m.start()) + 1
            chunk = body[m.start():end]
        else:
            # 같은 이름의 여는 태그를 세어 짝을 맞춘다.
            depth, k = 0, m.start()
            open_pat = re.compile(r"<(/?)%s" % kind, re.I)

            while True:
                got = open_pat.search(body, k)

                if not got:
                    k = len(body)
                    break

                depth += -1 if got.group(1) else 1
                k = got.end()

                if depth == 0:
                    k = body.find(">", k) + 1
                    break

            chunk = body[m.start():k]
            end = k

        pos = end

        # **그림을 «먼저» 꺼낸다.** 바깥 블록의 글자만 남기면 삼켜진다.
        out.extend(graphics(chunk, args, seen))

        # **꺼낸 그림은 덩어리에서 지운다.** 안 지우면 그 SVG 안의
        # `<text>` 가 아래에서 다시 글자로 뽑혀 「평지」 「+1」 같은
        # 토막 문단이 된다 `확인됨` (2026-09-12 · 팀장이 잡았다).
        chunk = re.sub(r"<svg.*?</svg>", " ", chunk, flags=re.S | re.I)
        chunk = re.sub(r'<img[^>]*src="data:[^"]*"[^>]*>', " ", chunk, flags=re.I)

        if kind.startswith("h") and kind[1:].isdigit():
            got = text_of(chunk)

            if got:
                # 「01기준선은…」 처럼 붙은 절 번호를 떼어 낸다.
                # 「01기준선」 처럼 붙은 절 번호만 둔다. 두 자리 숫자가
                # 앞에 올 때만. 안 그러면 `61열로 늘리는 설계` 가
                # `61. 열로 늘리는 설계` 가 된다 `확인됨` (2026-09-12).
                got = re.sub(r"^(\d{2})(?=[가-힣])(?![열번장줄개컷판종초시분개월일년])",
                             r"\1. ", got)
                out.append("#" * int(kind[1]) + " " + got)
        elif kind == "table":
            got = as_table(chunk)

            if got:
                out.append(got)
        elif kind in ("ul", "ol"):
            got = as_list(chunk, kind == "ol")

            if got:
                out.append(got)
        elif kind == "pre":
            # **코드울은 원문 그대로.** `text_of` 를 쓰면 안의 `<code>` 가
            # 인라인 백틱으로 바뀌어 **백틱이 본문에 남는다**
            # `확인됨` (2026-09-12 codex 9회차 · JSON 복사본에 백틱이 섮였다).
            raw = re.sub(r"<[^>]+>", "", chunk)
            got = _html.unescape(raw).strip(chr(10))

            if got.strip():
                out.append("```" + chr(10) + got + chr(10) + "```")
        elif kind in ("p", "blockquote", "figure"):
            got = text_of(chunk)

            if got:
                out.append(("> " + got) if kind == "blockquote" else got)
        elif kind == "hr":
            out.append("---")

    n_svg, n_img, saved = seen["svg"], seen["img"], seen["files"]
    text = "\n\n".join(out) + "\n"
    io.open(args.out, "w", encoding="utf-8").write(text)
    print("  %s · %.1f KB" % (args.out, len(text.encode("utf-8")) / 1024))
    print("  절 %d · 표 %d · 도해 %d · 사진 %d"
          % (sum(1 for l in out if l.startswith("#")),
             sum(1 for l in out if l.startswith("|")), n_svg, n_img))

    for name in saved:
        got = os.path.getsize(os.path.join(args.assets, name))
        print("    %-34s %6.0f KB" % (name, got / 1024))

    # **조용한 실패를 소리 나게 한다.** 뽑았는데 알맹이가 비면 막는다.
    if len(text) < 4000:
        raise SystemExit("뽑은 것이 %d 자뿐이다. 본문을 못 찾았다" % len(text))

    if not n_svg and not n_img:
        raise SystemExit("그림을 하나도 못 내렸다")


if __name__ == "__main__":
    main()
