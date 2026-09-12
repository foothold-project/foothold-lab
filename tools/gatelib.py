# -*- coding: utf-8 -*-
"""관문이 **글자가 아니라 뜻**을 보게 하는 공용 도구.

분류: 운영
작성: 오흥재 · 2026-09-12 19:10
근거: codex 검수 7회차 · 결함 주입 36건 중 20건을 새 관문이 통과시킴
요지: 문자열 존재 검사는 주석·엔티티·동등 표현 셋으로 전부 우회된다
상태: 확정

## 왜 이것이 있나

전역바·정본 관문을 새로 세우고 「알려진 답 시험」까지 돌렸는데, codex 가
결함을 주입하자 **20건이 그대로 통과**했다. 사례를 늘어놓으면 스무 가지
같지만 부류는 셋뿐이다.

| 부류 | 주입 예 | 왜 통과했나 |
|---|---|---|
| 주석 속에 남기기 | `<!-- fh-theme-boot -->` · `/* --gnav-width:… */` | 글자는 있다 |
| 다른 표기로 쓰기 | `&#8212;` (em dash) · `&#37;&#37;` | 글자가 다르다 |
| 형태만 남기기 | 빈 `<svg>` 5개 · 폭을 `1px` 로 | 개수는 맞다 |

**이것은 내가 이미 아는 실패다.** 메모리에 「관문은 재측정이어야 한다 ·
문자열 검사 관문은 조작한 보고서 5종을 다 통과시켰다」 라고 적어 두고도
같은 관문을 또 만들었다.

## 무엇을 주나

    live(text)      주석을 걷어낸 «살아 있는» 부분만
    plain(text)     엔티티를 풀고 태그를 벗긴 본문 글자
    css_of(...)     페이지가 실제로 적용받는 CSS (링크한 시트까지)
    top_rules(css)  중괄호를 세어 자른 최상위 규칙 (`@media` 가 통째로 남는다)
    token_map(css)  테마별로 «실제로 이기는» 토큰 값
    shown(css, ...) 그 테마에서 실제로 보이는 것이 무엇인가

앞의 둘만 써도 스무 건 중 열은 막힌다. 뒤의 셋은 「개수가 맞다」 를
「값이 맞다」 로 바꾼다.
"""
from __future__ import annotations

import html as _html
import io
import os
import re

# ── 1. 죽은 글자를 걷어낸다 ──────────────────────────────────────────

HTML_COMMENT = re.compile(r"<!--(?!\s*/?gnav:v1\s*-->).*?-->", re.S)
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)


def live(text, keep_marks=True):
    """**주석을 걷어낸다.**

    주석 안에 남은 글자는 화면에 아무 일도 하지 않는다. 그런데 「있나」만
    보는 관문은 그것을 찾아 내고 통과시킨다 `확인됨` (2026-09-12 · 부팅
    스크립트를 주석으로 바꾸고 폭 선언을 주석에 넣은 주입 다섯이 전부 통과).

    `keep_marks` 는 `<!--gnav:v1-->` 처럼 **주석 자체가 표식인** 것을 남긴다.
    """
    out = HTML_COMMENT.sub(" ", text) if keep_marks else re.sub(
        r"<!--.*?-->", " ", text, flags=re.S)
    return CSS_COMMENT.sub(" ", out)


def plain(text):
    """엔티티를 풀고 태그를 벗긴 **읽히는 글자**.

    `&#8212;` 는 화면에서 em dash 로 읽힌다. 원문에 `—` 이 없다고
    통과시키면 금지한 것이 그대로 나간다 `확인됨` (2026-09-12 · em dash 와
    `%%` 가 숫자 엔티티로 통과).
    """
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    body = re.sub(r"<[^>]*>", " ", body)
    # 두 번 푼다. `&amp;#8212;` 처럼 겹쳐 쓴 것도 화면에서는 한 번 더 풀린다.
    return _html.unescape(_html.unescape(body))


# ── 2. CSS 를 규칙 단위로 자른다 ─────────────────────────────────────

def top_rules(css):
    """중괄호를 세어 최상위 규칙으로 자른다. `@media` 가 통째로 남는다.

    `\\.gnav[^}]*}` 같은 정규식은 **중첩 블록을 첫 `}` 에서 자른다.**
    그렇게 뽑은 CSS 를 페이지에 붙였다가 로고 색이 뒤집혔다.
    """
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

        yield css[i:k].strip()
        i = k


def css_of(path, site, follow=True, skip=()):
    """그 페이지가 **실제로 적용받는** CSS 전부. 주석은 걷어낸다.

    안에 쓴 `<style>` 만 보면, 시트로 옮긴 규칙을 못 본다.
    """
    text = io.open(path, encoding="utf-8", errors="replace").read()
    body = live(text)
    css = "".join(re.findall(r"<style[^>]*>(.*?)</style>", body, re.S))

    if not follow:
        return css

    here = os.path.dirname(os.path.abspath(path))

    for one in re.findall(r'<link[^>]+href="([^"]+\.css)"', body):
        if one.startswith(("http://", "https://", "//")):
            continue

        # 공유 시트를 건너뛸 수 있어야 한다. 안 그러면 그 시트의 규칙을
        # 「이 페이지가 베낀 것」 으로 센다.
        if any(one.endswith(s) for s in skip):
            continue

        got = (os.path.join(site, one.lstrip("/").replace("/", os.sep))
               if one.startswith("/") else
               os.path.join(here, one.replace("/", os.sep)))

        if os.path.isfile(got):
            css += "\n" + live(io.open(got, encoding="utf-8",
                                       errors="replace").read())

    return css


# ── 3. 「있나」 대신 「이기나」 ───────────────────────────────────────

STATES = (("none", "light"), ("none", "dark"),
          ("light", "dark"), ("dark", "light"))
"""화면은 둘이 아니라 **논이다.**

    (표식, OS 설정)
    ("none",  "light")   고른 적 없음 · OS 밝음
    ("none",  "dark")    고른 적 없음 · OS 어두움   <- 사고는 여기서 난다
    ("light", "dark")    밝음을 고름 · OS 는 어두움   <- 고른 것이 이겨야 한다
    ("dark",  "light")   어두움을 고름 · OS 는 밝음

**가운데 둘을 빼면 사고가 안 잡힌다.** `@media` 를 평면으로 풀거나
다리 정의를 지워도, `html[data-theme=...]` 규칙이 뒤에 있어 **표식이
있는 두 상태는 멀집하다** `확인됨` (2026-09-12 · 그래서 관문이 네 건을
통과시켰다). 표식이 없는 상태가 기본값이고, 거기서 깨진다.
"""


def _state(theme):
    """`"light"` 같은 짧은 이름도 받는다."""
    if isinstance(theme, tuple):
        return theme

    return ("light", "light") if theme == "light" else ("dark", "dark")


def _applies(selector, theme):
    """이 규칙이 그 상태에서 적용되나."""
    stamp, os_pref = _state(theme)
    head = selector.strip()
    flat = head.replace(" ", "")

    if head.startswith("@media"):
        if "prefers-color-scheme:dark" in flat:
            return os_pref == "dark"

        if "prefers-color-scheme:light" in flat:
            return os_pref == "light"

        return "max-width" not in head and "min-width" not in head

    if 'not([data-theme="light"])' in flat:
        return stamp != "light"

    if 'not([data-theme="dark"])' in flat:
        return stamp != "dark"

    if 'data-theme="dark"' in flat:
        return stamp == "dark"

    if 'data-theme="light"' in flat:
        return stamp == "light"

    return True


def _walk(css, theme):
    """그 상태에서 적용되는 규칙을 `(셀렉터, 선언부)` 로 차례대로.

    **주석을 먼저 걷는다.** 안 걷으면 `/* @media x {` 처럼 껍데기를
    주석으로 만든 주입이 구조를 놓치게 한다.
    """
    for rule in top_rules(CSS_COMMENT.sub(" ", css)):
        head, _, body = rule.partition("{")

        if not _applies(head, theme):
            continue

        if head.strip().startswith("@"):
            for inner in _walk(body.rstrip().rstrip("}"), theme):
                yield inner
            continue

        yield head.strip(), body.rstrip().rstrip("}")


# «알려진» 시작 요소. 이것들로 시작하는 셀렉터만 토큰을 정의할 수 있다.
# `.never:root[...]` 처럼 모르는 클래스가 앞에 붙으면 그 규칙은 안 맞는다.
KNOWN = ("html", ":root", "body", "*", ".gnav")

def reaches_root(selector):
    """이 셀렉터가 **뿌리 요소에 닿을 수 있나.**

    `.never:root[data-theme="dark"]` 처럼 알 수 없는 클래스가 앞에 붙으면
    그 규칙은 영원히 안 맞는다. 그런데 `data-theme="dark"` 라는 글자만
    보면 「어두운 토큰이 있다」 고 판정해 버린다 `확인됨`
    (2026-09-12 · 그 주입 하나가 끝까지 관문을 뚫었다).

    첫 덩어리만 본다. 그것이 뿌리에 해당하는 자리다.
    """
    for one in selector.split(","):
        one = one.strip()

        if not one:
            continue

        head = re.split(r"[\s>+~]", one, 1)[0]

        # 조건과 가상 선택자를 떼어 내고 «무엇으로 시작하는가» 만 남긴다.
        bare = head

        for pat in (r"\[[^\]]*\]", r":not\([^)]*\)", r"::[a-z-]+",
                    r":(?!root)[a-z-]+(?:\([^)]*\))?"):
            bare = re.sub(pat, "", bare)

        if bare and bare not in KNOWN:
            return False

    return True


def token_map(css, theme, scope=":root"):
    """그 상태에서 **실제로 이기는** 토큰 값. 나중 규칙이 이긴다."""
    got = {}

    for head, body in _walk(css, theme):
        if scope not in head and "html" not in head and ".gnav" not in head:
            continue

        # 자칭 뿌리 규칙이더라도 **실제로 닿을 수 있어야** 세어 준다.
        if not reaches_root(head):
            continue

        for name, value in re.findall(r"(--[A-Za-z0-9_-]+)\s*:\s*([^;]+)", body):
            got[name] = value.strip()

    return got


def shown(css, theme, selectors):
    """그 상태에서 각 셀렉터의 `display` 가 무엇으로 «끝나는가»."""
    out = {s: None for s in selectors}

    for head, body in _walk(css, theme):
        hit = re.search(r"display\s*:\s*([a-z-]+)", body)

        if not hit:
            continue

        for one in head.split(","):
            one = one.strip()

            for want in selectors:
                if one == want or one.endswith(" " + want):
                    out[want] = hit.group(1)

    return out


def unbridged(css, prefix=".gnav"):
    """전역바 규칙이 **페이지 토큰에 직접 기대는** 자리.

    `background:var(--paper)` 처럼 쓰면 그 이름을 안 쓰는 페이지에서
    바가 투명해진다. 다리(`--np` 등)를 건넘는지 «규칙마다» 본다.

    다리를 **정의하는** 줄 (`--np:var(--paper,기본값)`) 은 누수가 아니다.
    그것이 바로 다리다. 예전에는 그것까지 세어 자기 자신을 고발했다.
    """
    leaks = []

    for rule in top_rules(CSS_COMMENT.sub(" ", css)):
        head, _, body = rule.partition("{")

        if prefix not in head:
            continue

        for decl in body.rstrip().rstrip("}").split(";"):
            name, _, value = decl.partition(":")
            name = name.strip()

            # 다리를 정의하는 줄은 건너뛴다.
            if name.startswith("--n"):
                continue

            for used in re.findall(r"var\((--[A-Za-z0-9_-]+)", value):
                # 이 둘은 페이지가 «일부러» 선언하는 것이다. 누수가 아니다.
                if used in ("--gnav-width", "--navh"):
                    continue

                if not used.startswith("--n"):
                    leaks.append((head.strip()[:48], name or "?", used))

    return leaks
