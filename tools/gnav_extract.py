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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    """**뽑기는 했는데 알맹이가 빠졌는가.**

    예전에는 「그 글자가 있나」 만 봤다. codex 7회차가 결함을 주입하자
    여섯 중 여섯이 통과했다 `확인됨`.

    이제 **네 상태에서 실제로 무엇이 보이는지** 를 따진다.
    가장 중요한 것은 **표식이 없고 OS 가 어두운** 상태다. 사고는
    거기서 난다. 그 상태를 빼면 `@media` 를 평면으로 풀어도
    `html[data-theme=...]` 규칙이 뒤에서 멀집해 아무것도 안 잡힌다.
    """
    from gatelib import STATES, shown, token_map, unbridged

    for stamp, os_pref in STATES:
        theme = (stamp, os_pref)
        dark = (stamp == "dark") or (stamp == "none" and os_pref == "dark")
        on, off = ((".gnav .lgr", ".gnav .lgi") if dark
                   else (".gnav .lgi", ".gnav .lgr"))
        got = shown(css, theme, [on, off])

        if got[on] == "none" or got[off] != "none":
            raise SystemExit(
                "표식=%s · OS=%s 에서 로고가 틀리다. %s=%s · %s=%s"
                % (stamp, os_pref, on, got[on], off, got[off]))

        tone = token_map(css, theme)

        for name in ("--np", "--ni", "--nr"):
            if not tone.get(name):
                raise SystemExit("표식=%s · OS=%s 에서 `%s` 가 정의되지 "
                                 "않는다. 다리가 끊겼다" % (stamp, os_pref, name))

    # 밝은 상태와 어두운 상태의 바 배경이 달라야 한다.
    pale = token_map(css, ("none", "light")).get("--np")
    dusk = token_map(css, ("none", "dark")).get("--np")

    if pale == dusk:
        raise SystemExit("표식 없는 밝음·어두움의 바 배경이 같다 (%s). "
                         "한쪽은 글씨가 안 보인다" % pale)

    leaks = unbridged(css)

    if leaks:
        raise SystemExit("다리를 안 건널 자리 %d곳: %s"
                         % (len(leaks),
                            " · ".join("%s 의 %s -> %s" % x for x in leaks[:4])))

    import gatelib

    for why, want_sel, want_prop in (("바 배경", ".gnav", "background"),
                                     ("바 안쪽 폭", ".gnav .in", "max-width")):
        if not any(head == want_sel and want_prop in body
                   for head, body in gatelib._walk(css, ("none", "light"))):
            raise SystemExit("%s 규칙이 없다 (`%s` 에 `%s`)"
                             % (why, want_sel, want_prop))


def wearers(site):
    """`gnav.css` 를 링크한 페이지를 **전부** 훑는다.

    ★ 커널 철칙 4: 관문이 한 층위만 보면 나머지 자리에서 조용히 무너진다.
    바 한 벌을 만들어 놓아도, **그 바를 쓰는 쪽**이 갖춰야 할 것이 있다.

    | 없으면 | 벌어지는 일 |
    |---|---|
    | 테마 부팅 | 표식이 없어 어두운 화면이 기본이 된다 |
    | 어두운 토큰 | 본문은 밝은데 바만 흰 로고로 바뀐다 (로고가 사라진다) |
    | `--gnav-width` | 바 안쪽과 본문 왼쪽 끝이 어깋난다 |
    | 베낀 `.gnav` 규칙 | 한 벌을 고쳐도 그 페이지만 예날 것으로 남는다 |

    **주석을 걷어내고 값을 맞춰 본다.** 예전에는 글자만 봐서, 부팅을
    주석으로 바꾸거나 폭을 `1px` 로 두어도 통과했다 `확인됨`
    (2026-09-12 codex 7회차 · 다섯 건).
    """
    from gatelib import STATES, css_of, live, token_map, top_rules
    bad = []

    for here, dirs, names in os.walk(site):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]

        if os.path.basename(here) == "assets":
            continue

        for name in names:
            if not name.endswith(".html"):
                continue

            path = os.path.join(here, name)
            raw = io.open(path, encoding="utf-8", errors="replace").read()

            if "/assets/gnav.css" not in raw:
                continue

            rel = os.path.relpath(path, site).replace(os.sep, "/")
            body = live(raw)
            css = css_of(path, site)
            # 베낀 것을 셀 때는 «공유 시트를 뺀» 것만 본다.
            own = css_of(path, site, skip=("gnav.css",))
            miss = []

            # 부팅은 «살아있는» 스크립트여야 하고, 테마를 실제로 찍어야 한다.
            boot = re.search(r'<script[^>]*id="fh-theme-boot"[^>]*>(.*?)</script>',
                             body, re.S)

            if not boot:
                miss.append("테마 부팅")
            else:
                # **부팅은 세 가지를 다 해야 한다.** 하나라도 빠지면 껍데기다.
                #   저장된 것을 읽고 · 표식을 찍고 · 없을 때 밝음으로 둔다
                job = boot.group(1)
                lack = [why for why, mark in
                        (("저장값을 안 읽는다", "getItem"),
                         ("표식을 안 찍는다", "dataset.theme"),
                         ("기본값이 없다", '"light"'))
                        if mark not in job]

                if lack:
                    miss.append("테마 부팅이 " + " · ".join(lack))
                elif job.count("dataset.theme") < 2:
                    miss.append("테마 부팅의 분기 한쪽이 표식을 안 찍는다")

            if not re.search(r'<link[^>]+href="/assets/gnav\.css"', body):
                miss.append("한 벌 링크")

            # 폭은 «있나» 가 아니라 «본문과 같나».
            declared = token_map(css, "light").get("--gnav-width")
            holder = None

            for rule in top_rules(css):
                head, _, decl = rule.partition("{")

                if re.match(r"^\s*(body\s+)?(\.wrap|main\.wrap|div\.wrap|\.page)\s*$",
                            head.replace("body.wide", "").split(",")[0]):
                    got = re.search(r"max-width\s*:\s*([0-9]+)px", decl)

                    if got:
                        holder = got.group(1) + "px"

            if not declared:
                miss.append("--gnav-width")
            elif holder and declared.replace(" ", "") != holder:
                miss.append("폭이 본문과 다르다 (선언 %s · 본문 %s)"
                            % (declared, holder))

            # 어두운 토큰은 «있나» 가 아니라 **네 상태 전부에서** 맞는가.
            #
            # 한 상태만 보면 나머지에서 조용히 무너진다. `@media` 는 성하고
            # `[data-theme="dark"]` 만 깨진 경우, 테마를 손으로 고른 사람만
            # 밝은 본문에 흰 로고를 본다 `확인됨` (2026-09-12).
            pale = token_map(css, ("none", "light")).get("--paper")

            for stamp, os_pref in STATES:
                dim = (stamp == "dark") or (stamp == "none" and os_pref == "dark")

                if not dim:
                    continue

                dusk = token_map(css, (stamp, os_pref)).get("--paper")

                if not dusk:
                    miss.append("어두운 토큰 (표식=%s · OS=%s)" % (stamp, os_pref))
                elif pale and pale == dusk:
                    miss.append("어두운 토큰이 밝은 것과 같다 "
                                "(표식=%s · %s)" % (stamp, dusk))

            copied = [r for r in top_rules(own)
                      if re.search(r"(^|[,\s])\.gnav([\s.,:{]|$)", r.partition("{")[0])]

            if copied:
                miss.append("베낀 .gnav 규칙 %d개" % len(copied))

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
