# -*- coding: utf-8 -*-
"""codex 가 `md2site` 관문을 뚫었던 아홉 건을 다시 먹인다.

관문은 **산출물**을 검사한다. 그러니 결함은 산출물에 주입해야 한다.
변환기를 부른 뒤 결과 HTML 을 망가뜨리고, 관문 부분만 다시 돌린다.
"""
import io
import os
import re
import subprocess
import sys
import tempfile

JAY = os.path.join(r"C:\Users\AI-WS01\Desktop\jay",
                   "\uc778\uacf5\uc9c0\ub2a5\uc0ac\uad00\ud559\uad50")
LAB = os.path.join(JAY, "foothold-lab")
SITE = os.path.join(JAY, "foothold-site")
SRC = os.path.join(LAB, "docs", "research", "20260911-eval-protocol-v2.md")
sys.path.insert(0, os.path.join(LAB, "tools"))


# ── codex 가 통과시킨 아홉 ────────────────────────────────────────────
def nav_removed_comment_retained(out):
    """바를 지우고 표식만 주석으로 남긴다."""
    return re.sub(r"<!--gnav:v1-->.*?<!--/gnav:v1-->",
                  "<!-- gnav:v1 was here -->", out, flags=re.S)


def boot_inert(out):
    """부팅 스크립트를 빈 껍데기로."""
    return re.sub(r'(<script[^>]*id="fh-theme-boot"[^>]*>).*?(</script>)',
                  r"\1\2", out, flags=re.S)


def css_link_commented(out):
    return out.replace('<link rel="stylesheet" href="/assets/gnav.css">',
                       '<!-- <link rel="stylesheet" href="/assets/gnav.css"> -->', 1)


def autolink_reverted(out):
    """자동 링크를 도로 글자로."""
    m = re.search(r'<a href="(https?://[^"]+)">\1</a>', out)

    if not m:
        return out

    return out.replace(m.group(0), "&lt;%s&gt;" % m.group(1), 1)


def autolink_numeric_entities(out):
    m = re.search(r'<a href="(https?://[^"]+)">\1</a>', out)

    if not m:
        return out

    return out.replace(m.group(0), "&#60;%s&#62;" % m.group(1), 1)


def light_token_removed(out):
    return out.replace("--ok:#0e7a6e;", "", 1)


def light_token_comment(out):
    return out.replace("--ok:#0e7a6e;", "/* --ok:#0e7a6e; */", 1)


def dark_token_removed(out):
    """어두운 블록을 통째로 없앤다."""
    out = re.sub(r"@media \(prefers-color-scheme:dark\)\{:root[^@]*?\}\}", "", out,
                 count=1, flags=re.S)
    return re.sub(r':root\[data-theme="dark"\]\{[^}]*\}', "", out, count=1)


def inline_svg_reverted(out):
    return re.sub(r"<svg.*?</svg>", '<img src="/x.svg" alt="">', out, flags=re.S)


def inline_svg_reverted_decoys(out):
    """빈 `<svg>` 다섯 개로 개수만 맞춘다."""
    return re.sub(r"<svg.*?</svg>", '<svg viewBox="0 0 1 1"></svg>', out, flags=re.S)


def em_dash_raw(out):
    return out.replace("</body>", "<p>" + chr(8212) + "</p></body>", 1)


def em_dash_entity(out):
    return out.replace("</body>", "<p>&#8212;</p></body>", 1)


def double_percent_raw(out):
    return out.replace("</body>", "<p>%%</p></body>", 1)


def double_percent_entities(out):
    return out.replace("</body>", "<p>&#37;&#37;</p></body>", 1)


CASES = [
    ("nav-removed-comment-retained", nav_removed_comment_retained),
    ("boot-inert", boot_inert),
    ("css-link-commented", css_link_commented),
    ("autolink-reverted", autolink_reverted),
    ("autolink-numeric-entities", autolink_numeric_entities),
    ("light-token-removed", light_token_removed),
    ("light-token-comment", light_token_comment),
    ("dark-token-removed", dark_token_removed),
    ("inline-svg-reverted", inline_svg_reverted),
    ("inline-svg-reverted-decoys", inline_svg_reverted_decoys),
    ("em-dash-raw", em_dash_raw),
    ("em-dash-entity", em_dash_entity),
    ("double-percent-raw", double_percent_raw),
    ("double-percent-entities", double_percent_entities),
]


def gates(out, images):
    """`md2site.main()` 의 관문 부분만 떼어 돌린다."""
    import gatelib
    alive = gatelib.live(out)
    reads = gatelib.plain(out)

    if "<!--gnav:v1-->" not in alive:
        raise SystemExit("\uc804\uc5ed\ubc14\uac00 \uc5c6\ub2e4")

    boot = re.search(r'<script[^>]*id="fh-theme-boot"[^>]*>(.*?)</script>',
                     alive, re.S)

    if not boot:
        raise SystemExit("\ud14c\ub9c8 \ubd80\ud305\uc774 \uc5c6\ub2e4")

    lack = [w for w, m in (("\uc800\uc7a5\uac12", "getItem"),
                           ("\ud45c\uc2dd", "dataset.theme"),
                           ("\uae30\ubcf8\uac12", '"light"')) if m not in boot.group(1)]

    if lack:
        raise SystemExit("\ud14c\ub9c8 \ubd80\ud305\uc5d0 %s \uc774 \uc5c6\ub2e4" % " \u00b7 ".join(lack))

    if not re.search(r'<link[^>]+href="/assets/gnav\.css"', alive):
        raise SystemExit("\uc804\uc5ed\ubc14 CSS \ub9c1\ud06c\uac00 \uc5c6\ub2e4")

    if re.search(r"<https?://", reads):
        raise SystemExit("`<\uc8fc\uc18c>` \uac00 \uae00\uc790\ub85c \ub0a8\uc558\ub2e4")

    css = "".join(re.findall(r"<style[^>]*>(.*?)</style>", alive, re.S))
    want = set(re.findall(r"var\((--[a-z0-9-]+)\)",
                          "".join(m.group(0) for m
                                  in re.finditer(r"<svg.*?</svg>", alive, re.S))))

    for state in gatelib.STATES:
        short = sorted(want - set(gatelib.token_map(css, state)))

        if short:
            raise SystemExit("\ud45c\uc2dd=%s OS=%s \uc5d0\uc11c \ub3c4\uba74 \uc0c9 %s \uac00 \uc5c6\ub2e4"
                             % (state[0], state[1], " ".join(short)))

    pale = gatelib.token_map(css, ("none", "light")).get("--paper")
    dusk = gatelib.token_map(css, ("none", "dark")).get("--paper")

    if not dusk or pale == dusk:
        raise SystemExit("\uc5b4\ub450\uc6b4 \ud1a0\ud070\uc774 \uc5c6\uac70\ub098 \ubc1d\uc740 \uac83\uacfc \uac19\ub2e4")

    drawn = [m.group(0) for m in re.finditer(r"<svg.*?</svg>", out, re.S)]

    if images and len(drawn) < images:
        raise SystemExit("SVG %d\uc7a5 \uc911 %d\uc7a5\ub9cc \uc2ec\uacbc\ub2e4" % (images, len(drawn)))

    for i, one in enumerate(drawn, 1):
        marks = len(re.findall(
            r"<(path|rect|circle|line|polyline|polygon|text|g)[ />]", one))

        if marks < 3:
            raise SystemExit("%d\ubc88\uc9f8 \ub3c4\uba74\uc5d0 \uadf8\ub824\uc9c4 \uac83\uc774 %d\uac1c\ubfd0\uc774\ub2e4" % (i, marks))

    for why, bad in (("em dash", chr(8212)), ("%%", "%%")):
        if bad in out or bad in reads:
            raise SystemExit("\ub098\uac00\uba74 \uc548 \ub418\ub294 \uac83: %s" % why)


def main():
    tmp = tempfile.mkdtemp()
    out_path = os.path.join(SITE, "_replay_probe.html")
    done = subprocess.run(
        [sys.executable, os.path.join(LAB, "tools", "md2site.py"), SRC,
         "--out", out_path], capture_output=True, text=True, errors="replace",
        cwd=LAB)

    if done.returncode:
        print(done.stdout + done.stderr)
        raise SystemExit("\uc6d0\ubcf8 \ubcc0\ud658\uc774 \uc2e4\ud328\ud588\ub2e4")

    good = io.open(out_path, encoding="utf-8").read()
    os.remove(out_path)
    slip = 0

    try:
        gates(good, 5)
        print("  %-34s %s" % ("\uc6d0\ubcf8", "\ud1b5\uacfc \u00b7 OK"))
    except SystemExit as e:
        print("  %-34s !! \uc6d0\ubcf8\uc774 \ub9c9\ud614\ub2e4: %s" % ("\uc6d0\ubcf8", e))
        slip += 1

    for name, fn in CASES:
        got = fn(good)

        if got == good:
            print("  %-34s !! \uc8fc\uc785\uc774 \ud5db\ubc29" % name)
            slip += 1
            continue

        try:
            gates(got, 5)
            print("  %-34s !! \ud1b5\uacfc\uc2dc\ud398" % name)
            slip += 1
        except SystemExit as e:
            print("  %-34s \ub9c9\uc74c \u00b7 %s" % (name, str(e)[:44]))

    print()
    print("  \uc8fc\uc785 %d\uac74 \uc911 \uc0c8\uc5b4\ub098\uac04 \uac83 %d\uac74" % (len(CASES), slip))
    return 1 if slip else 0


if __name__ == "__main__":
    sys.exit(main())
