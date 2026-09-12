# -*- coding: utf-8 -*-
"""site 의 전역바를 **한 파일로** 뽑는다.

    python tools/gnav_extract.py --site ../foothold-site

분류: 운영
작성: 오흥재 · 2026-09-12 16:40
근거: 팀장 「FOOTHOLD 왼쪽 상단 로고 컬러 틀어지네」 · 「전역바 투명해지는거 확인했어?」
요지: 전역바를 페이지마다 베끼면 어긋난다. 한 파일을 링크한다
상태: 확정

## 왜 이것이 있나

내가 만든 페이지 다섯 장에 전역바를 붙일 때 **규칙을 평면으로 베꼈다.**
그래서 `@media (prefers-color-scheme:dark)` 의 중괄호가 풀렸고, 안에 있던

    .gnav .lgi{display:none} .gnav .lgr{display:block}

가 조건 없이 적용돼 **밝은 화면에서 흰 로고가 떴다** `확인됨`.
같은 이유로 바 배경 규칙도 짝이 안 맞아 **전역바가 투명**해졌다.

고치는 방법은 「이번엔 잘 베끼기」가 아니다. **베끼지 않는 것**이다.
여기서 `assets/gnav.css` 한 장을 만들고, 페이지는 그것을 링크한다.

## 어떻게 뽑나

중괄호를 세어 최상위 규칙 단위로 자른다. `@media` 는 통째로 살아 남는다.
정규식 한 줄로 `\\.gnav[^}]*}` 처럼 뽑으면 **중첩된 블록이 첫 `}` 에서
잘려** 지금 겪은 일이 그대로 재현된다.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

# 이 셀렉터나 변수가 든 최상위 규칙은 전역바의 것이다.
MARKS = (".gnav", "--navh")

HEAD = """/* FOOTHOLD 전역바.

   **이 파일이 정본이다.** 페이지에 규칙을 베끼지 말고 이것을 링크한다.
       <link rel="stylesheet" href="/assets/gnav.css">

   tools/gnav_extract.py 가 index.html 에서 뽑는다. 손으로 고치지 않는다.
*/
"""

# **바가 자기 색을 들고 다닌다.**
# 전에는 `var(--paper)` 를 그대로 썼다. 그 이름을 안 쓰는 페이지(보고서는
# `--bg` 였다)에 붙이자 **바가 투명**해졌다 `확인됨` (2026-09-12 팀장 지적).
# 페이지 값이 있으면 그것을 쓰고, 없으면 자기 값으로 칠한다.
BRIDGE = """/* 페이지 토큰이 있으면 그것을, 없으면 이 값을 쓴다. */
.gnav{--np:var(--paper,#f6f5f1);--np2:var(--paper-2,#eeece6);
  --ni:var(--ink,#161c26);--ni3:var(--ink-3,#7c8798);--nr:var(--rule,#d9d6cd)}
@media (prefers-color-scheme:dark){
  html:not([data-theme="light"]) .gnav{
    --np:var(--paper,#12161d);--np2:var(--paper-2,#191e27);
    --ni:var(--ink,#e9e7e1);--ni3:var(--ink-3,#7d8693);--nr:var(--rule,#2b323d)}
}
html[data-theme="dark"] .gnav{
  --np:var(--paper,#12161d);--np2:var(--paper-2,#191e27);
  --ni:var(--ink,#e9e7e1);--ni3:var(--ink-3,#7d8693);--nr:var(--rule,#2b323d)}
html[data-theme="light"] .gnav{
  --np:var(--paper,#f6f5f1);--np2:var(--paper-2,#eeece6);
  --ni:var(--ink,#161c26);--ni3:var(--ink-3,#7c8798);--nr:var(--rule,#d9d6cd)}

"""

TAIL = """
/* **바가 본문 폭을 따라간다.**
   갤러리는 본문이 1440, 정본은 1100, 보고서는 960 인데 바 안쪽은 1040
   하나였다. 그래서 로고와 본문의 왼쪽 끝이 어긋났다 `확인됨`
   (2026-09-12 팀장: 「위에 전역바도 다 틀어지고 있어」 · 실측 30px).

   폭을 얼마로 쓸지는 그 페이지가 정한다. 여기서는 **그 값을 따라간다.**
   페이지는 `:root{--gnav-width:1440px}` 한 줄만 적으면 된다. */
.gnav .in{max-width:var(--gnav-width,1040px)}
"""

BRIDGED = (("var(--paper-2)", "var(--np2)"), ("var(--paper)", "var(--np)"),
           ("var(--ink-3)", "var(--ni3)"), ("var(--ink)", "var(--ni)"),
           ("var(--rule)", "var(--nr)"))


def top_rules(css):
    """중괄호를 세어 최상위 규칙으로 자른다. `@media` 가 통째로 남는다."""
    i, n = 0, len(css)

    while i < n:
        j = css.find("{", i)

        if j < 0:
            break

        depth, k = 1, j + 1

        while k < n and depth:
            if css[k] == "{":
                depth += 1
            elif css[k] == "}":
                depth -= 1
            k += 1

        yield css[i:k]
        i = k


def extract(site):
    text = io.open(os.path.join(site, "index.html"), encoding="utf-8").read()
    css = "".join(re.findall(r"<style[^>]*>(.*?)</style>", text, re.S))
    keep = [r for r in top_rules(css) if any(m in r for m in MARKS)]
    nav = re.search(r"<!--gnav:v1-->.*?<!--/gnav:v1-->", text, re.S)

    if not nav:
        raise SystemExit("index.html 에 <!--gnav:v1--> 가 없다")

    if not keep:
        raise SystemExit("전역바 규칙을 하나도 못 찾았다")

    body = "\n".join(r.strip() for r in keep) + "\n"

    for old, new in BRIDGED:
        body = body.replace(old, new)

    # **테마 부팅도 같이 간다.** site 의 기본은 «밝음» 인데, 이 스크립트가
    # 없는 페이지는 아무 표식도 안 달려 `prefers-color-scheme:dark` 가 이긴다.
    # 그래서 보고서만 어두운 화면으로 열렸다 `확인됨` (2026-09-12 팀장 지적).
    boot = re.search(r'<script id="fh-theme-boot">.*?</script>', text, re.S)

    if not boot:
        raise SystemExit("index.html 에 fh-theme-boot 가 없다")

    head = ('<link rel="stylesheet" href="/assets/gnav.css">' + "\n"
            + boot.group(0) + "\n")
    return nav.group(0), HEAD + BRIDGE + body + TAIL, head


def check(css):
    """**조용한 실패를 소리 나게 한다.** 뽑기는 했는데 알맹이가 빠지면 막는다."""
    need = [
        ("어두운 화면 조건", "@media (prefers-color-scheme:dark)"),
        ("로고 되비침", ".gnav .lgr"),
        ("바 자체", ".gnav{"),
    ]
    missing = [why for why, mark in need if mark not in css.replace(" {", "{")]

    if missing:
        raise SystemExit("뽑은 CSS 에 %s 가 없다" % " · ".join(missing))

    # 로고 전환은 **조건 안에서만** 나와야 한다. 조건 밖에 있으면 늘 이긴다.
    bare = [r for r in top_rules(css)
            if ".lgi" in r and not r.lstrip().startswith(("@", "html["))
            and "display:none" in r.split("{", 1)[1]]

    if len(bare) > 1:
        raise SystemExit("조건 없는 로고 숨김 규칙이 %d개다. 밝은 화면에서 "
                         "흰 로고가 뜬다" % len(bare))

    # 페이지 토큰에 기대면 그 이름을 안 쓰는 페이지에서 바가 투명해진다.
    leaked = sorted(set(re.findall(r"var\((--(?:paper|ink|rule)[a-z0-9-]*)\)",
                                   css)) - {"--paper", "--paper-2", "--ink",
                                            "--ink-3", "--rule"})

    if leaked:
        raise SystemExit("다리를 안 건넌 변수가 있다: %s" % " ".join(leaked))

    for name in ("--np", "--ni", "--nr"):
        if css.count("var(%s" % name) < 1:
            raise SystemExit("%s 를 쓰는 규칙이 없다. 다리가 안 걸렸다" % name)


def wearers(site):
    """`gnav.css` 를 링크한 페이지를 **전부** 훑는다.

    ★ 커널 철칙 4: 관문이 한 층위만 보면 나머지 자리에서 조용히 무너진다.
    바 한 벌을 만들어 놓아도, **그 바를 쓰는 쪽**이 갖춰야 할 것이 있다.

    | 없으면 | 벌어지는 일 |
    |---|---|
    | 테마 부팅 | 표식이 없어 어두운 화면이 기본이 된다 |
    | 어두운 토큰 | 본문은 밝은데 바만 흰 로고로 바뀐다 (로고가 사라진다) |
    | `--gnav-width` | 바 안쪽과 본문 왼쪽 끝이 어긋난다 |
    | 베낀 `.gnav` 규칙 | 한 벌을 고쳐도 그 페이지만 옛날 것으로 남는다 |
    """
    bad = []

    for here, _dirs, names in os.walk(site):
        if ".git" in here or "node_modules" in here:
            continue

        for name in names:
            if not name.endswith(".html"):
                continue

            path = os.path.join(here, name)

            # `assets/` 의 것은 페이지가 아니라 조각이다. 자기 자신은 안 센다.
            if os.path.basename(here) == "assets":
                continue
            text = io.open(path, encoding="utf-8", errors="replace").read()

            if "/assets/gnav.css" not in text:
                continue

            rel = os.path.relpath(path, site).replace(os.sep, "/")
            sheets = [m for m in re.findall(r'href="([^"]+\.css)"', text)
                      if not m.startswith(("http", "//"))]
            css = "".join(re.findall(r"<style[^>]*>(.*?)</style>", text, re.S))

            for one in sheets:
                got = os.path.join(site, one.lstrip("/").replace("/", os.sep)) \
                    if one.startswith("/") else os.path.join(here, one)

                if os.path.isfile(got) and not got.endswith("gnav.css"):
                    css += io.open(got, encoding="utf-8", errors="replace").read()

            miss = []

            if "fh-theme-boot" not in text:
                miss.append("테마 부팅")

            if "--gnav-width" not in css:
                miss.append("--gnav-width")

            if not re.search(r'data-theme="dark"|prefers-color-scheme:\s*dark', css):
                miss.append("어두운 토큰")

            copied = len(re.findall(r"\.gnav[^{]*\{", css))

            if copied:
                miss.append("베낀 .gnav 규칙 %d개" % copied)

            if miss:
                bad.append((rel, miss))

    return bad


def main():
    p = argparse.ArgumentParser(description="전역바를 한 파일로 뽑는다")
    p.add_argument("--site", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "foothold-site"))
    args = p.parse_args()
    site = os.path.abspath(args.site)
    nav, css, head = extract(site)
    check(css)
    into = os.path.join(site, "assets")
    os.makedirs(into, exist_ok=True)

    for name, text in (("gnav.css", css), ("gnav.html", nav + "\n"),
                       ("gnav-head.html", head)):
        io.open(os.path.join(into, name), "w", encoding="utf-8").write(text)
        print("  assets/%-15s %.1f KB" % (name, len(text.encode("utf-8")) / 1024))

    print("  규칙 %d개 · @media %d개" % (css.count("{"), css.count("@media")))

    bad = wearers(site)

    if bad:
        print()
        print("  !! 이 바를 쓰는데 갖출 것이 빠진 페이지 %d장" % len(bad))

        for rel, miss in bad:
            print("     %-46s %s" % (rel, " · ".join(miss)))

        raise SystemExit("바를 쓰는 쪽이 안 갖춰졌다. 화면에서 조용히 무너진다")

    print("  이 바를 쓰는 페이지 전부 갖춤")


if __name__ == "__main__":
    main()
