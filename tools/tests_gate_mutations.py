# -*- coding: utf-8 -*-
"""codex 가 **통과시킨** 주입을 고친 관문에 다시 먹인다.

관문을 고쳤다고 말하려면, 그 관문을 뚫었던 바로 그 입력으로 다시 시험해야
한다. 「이제 잘 될 것이다」 는 추론이다.

    python replay_mutations.py
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

JAY = os.path.join(r"C:\Users\AI-WS01\Desktop\jay",
                   "\uc778\uacf5\uc9c0\ub2a5\uc0ac\uad00\ud559\uad50")
LAB = os.path.join(JAY, "foothold-lab")
SITE = os.path.join(JAY, "foothold-site")
sys.path.insert(0, os.path.join(LAB, "tools"))

CSS = os.path.join(SITE, "assets", "gnav.css")


# ── check() 를 뚫었던 여섯 ────────────────────────────────────────────
def flatten_logo_media(css):
    """`@media` 껍질을 벗겨 안쪽 규칙을 무조건 적용되게 한다."""
    return re.sub(r"@media \(prefers-color-scheme:dark\)\{(\.gnav \.lg[^}]*\}[^}]*)\}",
                  r"\1", css)


def remove_logo_media(css):
    return re.sub(r"@media \(prefers-color-scheme:dark\)\{\.gnav \.lgi[^}]*\}[^}]*\}",
                  "", css)


def force_logo_hidden(css):
    return css + "\n.gnav .lgi{display:none}\n"


def background_unbridged(css):
    """다리를 도로 걷어 페이지 토큰에 직접 기대게 한다."""
    return css.replace("background:var(--np)", "background:var(--paper)", 1)


def bridge_removed(css):
    return re.sub(r"\.gnav\{--np:[^}]*\}", ".gnav{}", css, count=1)


def marks_to_comments(css):
    """필요한 표식을 전부 주석 안으로 옮긴다. 글자는 그대로 있다."""
    body = re.sub(r"@media \(prefers-color-scheme:dark\)\{", "/* @media x {", css)
    return body


CHECK_CASES = [
    ("flatten-logo-media", flatten_logo_media),
    ("remove-logo-media", remove_logo_media),
    ("force-logo-hidden", force_logo_hidden),
    ("background-unbridged-paper", background_unbridged),
    ("bridge-definitions-removed", bridge_removed),
    ("all-required-marks-comments", marks_to_comments),
]


# ── wearers() 를 뚫었던 다섯 ─────────────────────────────────────────
def boot_inert_comment(text):
    return text.replace('<script id="fh-theme-boot">',
                        '<!-- fh-theme-boot --><script id="fh-theme-boot">', 1) \
               .replace("dataset.theme", "noop", 1)


def boot_removed(text):
    return re.sub(r'<script id="fh-theme-boot">.*?</script>', "", text, flags=re.S)


def width_wrong(text):
    return re.sub(r"--gnav-width:\s*[0-9]+px", "--gnav-width:1px", text, count=1)


def width_in_comment(text):
    return re.sub(r"(--gnav-width:\s*[0-9]+px;)", r"/* \1 */", text, count=1)


def dark_in_comment(text):
    return re.sub(r'(:root\[data-theme="dark"\]\{)', r"/* x */ .never\1", text, count=1)


def copied_nav_equivalent(text):
    return text.replace("</head>", "<style>.gnav a{color:red}</style></head>", 1)


PAGE = "gallery/view/index.html"
SHEET = "gallery/gallery.css"

# 주입마다 **어느 파일을** 고치는지 적는다. 폭과 토큰은 시트에 있어서,
# 페이지만 고치면 헛방이다 (처음 시험에서 세 건이 그러했다).
WEAR_CASES = [
    ("boot-inert-comment", PAGE, boot_inert_comment),
    ("boot-removed", PAGE, boot_removed),
    ("width-wrong-1px", SHEET, width_wrong),
    ("width-in-comment", SHEET, width_in_comment),
    ("dark-in-comment", SHEET, dark_in_comment),
    ("copied-nav-equivalent-selector", PAGE, copied_nav_equivalent),
]


def run_check(css_text):
    import gnav_extract

    try:
        gnav_extract.check(css_text)
        return False, "통과"
    except SystemExit as e:
        return True, str(e)[:70]
    except Exception as e:  # noqa: BLE001
        return True, "%s: %s" % (type(e).__name__, str(e)[:50])


def run_wearers(target, mangle):
    """site 의 **실제 배치를 그대로** 베껰 한 페이지를 망가뜨린 뒤 관문을 돌린다.

    경로를 낙작 바꾸면 시트를 못 찾아 **원본까지 막힌다.** 그러면
    「막았다」 가 주입 때문인지 틀에서 비롯된 것인지 구분이 안 된다.
    """
    tmp = tempfile.mkdtemp()

    try:
        hold = os.path.join(tmp, "site")
        os.makedirs(os.path.join(hold, "assets"))
        shutil.copy2(CSS, os.path.join(hold, "assets", "gnav.css"))
        shutil.copytree(os.path.join(SITE, "gallery"),
                        os.path.join(hold, "gallery"),
                        ignore=shutil.ignore_patterns("v1", "*.mp4", "*.jpg"))
        hit = os.path.join(hold, target.replace("/", os.sep))
        # **먼저 읽고 나중에 쓴다.** 한 줄로 붙이면 `open(w)` 가 먼저
        # 평가돼 파일을 비우고, 그 뒤에 읽으니 **빈 문서를 시험**하게 된다
        # `확인됨` (2026-09-12 · 이 시험틀이 그래서 여섯 건을 무의미하게 돌렸다).
        was = io.open(hit, encoding="utf-8").read()
        io.open(hit, "w", encoding="utf-8").write(mangle(was))

        import gnav_extract
        bad = gnav_extract.wearers(hold)
        hits = [b for b in bad if "view" in b[0]]
        return bool(hits), (hits[0][1] if hits else ["통과"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    good = io.open(CSS, encoding="utf-8").read()
    rows = []

    ok, why = run_check(good)
    rows.append(("check", "원본", not ok, why))

    for name, fn in CHECK_CASES:
        got = fn(good)

        if got == good:
            raise SystemExit('%s 가 입력을 안 바꿈. 시험이 무의미하다' % name)

        blocked, why = run_check(got)
        rows.append(("check", name, blocked, why))

    blocked, why = run_wearers(PAGE, lambda t: t)
    rows.append(("wearers", "원본", not blocked, why))

    for name, target, fn in WEAR_CASES:
        src = io.open(os.path.join(SITE, target.replace("/", os.sep)),
                      encoding="utf-8").read()

        if fn(src) == src:
            raise SystemExit("%s 가 %s 를 안 바꿈. 헛방이다" % (name, target))

        blocked, why = run_wearers(target, fn)
        rows.append(("wearers", name, blocked, why))

    print("  %-9s %-32s %s" % ("관문", "주입", "결과"))
    print("  " + "-" * 74)
    slip = 0

    for fam, name, blocked, why in rows:
        if name == "원본":
            mark = "통과해야 함 · " + ("OK" if blocked else "!! 막혔다")
            if not blocked:
                slip += 1
        else:
            mark = "막음" if blocked else "!! 통과시킴"
            if not blocked:
                slip += 1
        note = why if isinstance(why, str) else " / ".join(why)
        print("  %-9s %-32s %s" % (fam, name, mark))

        if blocked and name != "원본":
            print("  %-9s %-32s   -> %s" % ("", "", note[:62]))

    print()
    print("  주입 %d건 중 통과시킨 것 %d건"
          % (len(rows) - 2, slip))
    return 1 if slip else 0


if __name__ == "__main__":
    sys.exit(main())
