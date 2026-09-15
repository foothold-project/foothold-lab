# -*- coding: utf-8 -*-
"""그림이 «사이트 테마» 를 따르게 한다.

> 분류: 운영
> 작성: 오흥재 (Claude 세션) · 2026-09-14 21:40
> 근거: 실측 (브라우저에서 다크로 바꾸고 화면을 봤다)
> 요지: `<img>` 안의 그림은 OS 설정만 보므로, 테마별 파일을 만들어 토글이 갈아끼운다
> 상태: 확정

## 무엇이 틀렸었나

팀장이 「웹페이지 들어가면 SVG 컬러가 이전 컬러로 돌아갔다」고 했다.
실제로 봤다. **페이지는 다크인데 그림만 라이트로 남아 있었다.**

까닭은 자리가 둘인데 한쪽만 있었기 때문이다.

    사이트가 테마를 정하는 법    `<html data-theme="dark">`  (토글 버튼)
    그림이 테마를 정하는 법      `@media(prefers-color-scheme:dark)`  (OS 설정)

`<img src="x.svg">` 로 넣은 그림은 **격리된 문서**라 부모 페이지의
`data-theme` 이 안 닿는다. 그래서 그림은 OS 설정만 본다. OS 가 라이트인
사람이 사이트를 다크로 바꾸면 그림만 라이트로 남는다. 그 반대도 같다.

`tools/svg_selfcontained.py` 가 팔레트를 파일 안에 넣어 «색이 아예 안 나오던 것»
은 고쳤지만, 그 팔레트가 무엇을 보고 갈리는지는 안 고쳤다. 절반만 고친 것이다.

## 무엇을 하나

그림을 **테마마다 한 장씩** 만들고, 무엇을 볼지는 페이지가 정하게 한다.

    x.svg        :root 에 라이트 팔레트.  media query 없음
    x.dark.svg   :root 에 다크  팔레트.  media query 없음

media query 를 **지운다**. 남겨 두면 「OS 다크 + 사이트 라이트」인 사람이
라이트 파일을 받고도 다크로 그려진다. 정하는 자리를 하나로 만든다.

페이지 쪽은 `web/_build/darkmode.py` 의 `apply()` 가 `src` 를 갈아끼운다.

## 왜 인라인이 아닌가

`mdpage.py` 에 적힌 대로 인라인은 이미 재 보고 버린 길이다 (정본 한 장이
167 KB -> 869 KB · 검색 색인 오염 · 빌드 10분 초과). 그 결정을 지킨다.

## 관문

`check()` 가 배포본을 다시 잰다. `<img>` 로 불리는 그림마다 다크 짝이
있는지, 그리고 어느 파일에도 media query 가 안 남았는지 본다.
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)

# `tools/svg_selfcontained.py` 와 **같은 값**이어야 한다. 거기서 읽어 온다.
# 손으로 베끼면 한쪽만 바뀌고 조용히 어긋난다 (이 파일이 존재하는 이유가 그것이다).
sys.path.insert(0, HERE)
import svg_selfcontained as SC  # noqa: E402

LIGHT, DARK = SC.LIGHT, SC.DARK

DARK_SUFFIX = ".dark.svg"
_MEDIA = re.compile(r"@media\s*\([^)]*prefers-color-scheme[^)]*\)\s*\{.*?\}\s*\}",
                    re.S | re.I)
_ROOT = re.compile(r":root\s*\{[^{}]*\}")


def _decl(d):
    return "".join("%s:%s;" % (k, v) for k, v in sorted(d.items()))


def paint(text, palette):
    """그 그림을 한 테마로 못박는다. media query 는 지운다.

    돌려주는 것은 (새 내용, 무엇을 했는지).
    """
    if "<style" not in text:
        return None, "style 블록이 없다"

    out, n_media = _MEDIA.subn("", text)
    out, n_root = _ROOT.subn(":root{%s}" % _decl(palette), out, count=1)

    if not n_root:
        return None, ":root 를 못 찾았다"

    return out, "팔레트 1곳 · media query %d곳 지움" % n_media


def dark_name(path):
    return path[: -len(".svg")] + DARK_SUFFIX


def write_pair(path):
    """한 그림에서 라이트본과 다크본을 만든다. 돌려주는 것은 (바꿨나, 말)."""
    src = io.open(path, encoding="utf-8").read()

    light, why_l = paint(src, LIGHT)
    dark, why_d = paint(src, DARK)

    if light is None or dark is None:
        return False, why_l or why_d

    changed = False

    if light != src:
        io.open(path, "w", encoding="utf-8", newline="\n").write(light)
        changed = True

    dp = dark_name(path)
    old = io.open(dp, encoding="utf-8").read() if os.path.isfile(dp) else None

    if old != dark:
        io.open(dp, "w", encoding="utf-8", newline="\n").write(dark)
        changed = True

    return changed, why_l


def _selftest():
    """관문 자신을 먼저 시험한다. 내가 아는 답으로 돌려 본다."""
    base = ('<svg xmlns="http://www.w3.org/2000/svg"><style>\n'
            ':root{--ink:#000000;--card:#ffffff;}\n'
            '@media(prefers-color-scheme:dark){:root{--ink:#ffffff;}}\n'
            '</style><rect fill="var(--card)"/></svg>')

    bad = []

    light, _ = paint(base, LIGHT)
    dark, _ = paint(base, DARK)

    for name, got, want_ink in (("라이트", light, LIGHT["--ink"]),
                                ("다크", dark, DARK["--ink"])):
        if got is None:
            bad.append("%s: 아무것도 안 나왔다" % name)
            continue
        if "prefers-color-scheme" in got:
            bad.append("%s: media query 가 안 지워졌다" % name)
        if want_ink not in got:
            bad.append("%s: --ink 가 %s 가 아니다" % (name, want_ink))
        if len(_ROOT.findall(got)) != 1:
            bad.append("%s: :root 가 %d개" % (name, len(_ROOT.findall(got))))

    # 두 판이 실제로 달라야 한다. 같으면 아무 일도 안 한 것이다.
    if light == dark:
        bad.append("라이트와 다크가 같다 (아무것도 안 바뀐 것)")

    # style 이 없는 그림은 건드리지 않는다
    none_, why = paint("<svg><rect/></svg>", LIGHT)
    if none_ is not None:
        bad.append("style 없는 그림을 건드렸다")

    if bad:
        print("  [!] 자기시험 실패: %s" % " · ".join(bad))
        return False

    print("  자기시험 4/4 통과")
    return True


def themeable(path):
    """이 그림이 테마 짝을 가질 수 있나. 파일을 읽어 판정한다."""
    if not os.path.isfile(path):
        return False
    t = io.open(path, encoding="utf-8", errors="ignore").read()
    return paint(t, LIGHT)[0] is not None


def mark_pages(site):
    """그림마다 표를 붙인다. 돌려주는 것은 (짝 표시 수, 판 표시 수, 판 목록).

    `data-themed`  테마 짝이 실제로 파일로 있는 그림. 토글이 갈아끼운다
    `data-plate`   짝을 못 만드는 그림. 다크에서 흰 판 위에 올린다

    이름으로 고르지 않는다. 파일이 있나 없나로 고른다. 이름으로 고르면
    이름이 바뀔 때 조용히 빗나간다 (2026-09-14 에 그렇게 한 장을 놓쳤다).
    """
    figs = _figs_in_pages(site)
    themed, plate = set(), set()

    # ★ 2026-09-15. 전에는 「style 블록이 있나」(themeable)까지 봤다. 그런데
    #   손그림 그림 5장은 style 블록 없이 `tools/svg_dark_hand.py` 가 색을
    #   직접 바꿔 다크판을 구웠다. 짝이 실제로 있는데도 「밝은 판」으로 갈렸다.
    #   **판정은 파일이 있나 없나로 한다.** 어떻게 만들었는지는 안 따진다.
    for r in figs:
        if os.path.isfile(os.path.join(site, dark_name(r))):
            themed.add(os.path.basename(r))
        else:
            plate.add(os.path.basename(r))

    n_t = n_p = 0
    for root, _dirs, files in os.walk(site):
        if os.sep + "." in root:
            continue
        for f in files:
            if not f.endswith(".html"):
                continue
            p = os.path.join(root, f)
            t = io.open(p, encoding="utf-8", errors="ignore").read()
            out = t

            # 먼저 옛 표를 «언제나» 걷는다. 「있으면 건너뛴다」로 두면 옛 표가
            # 박제돼 새 규칙이 영영 반영 안 된다 (ia-css 에서 두 번 겪었다).
            out = re.sub(r'\s+data-(?:themed|plate)(?=[\s>])', '', out)

            for attr, names in (("data-themed", themed), ("data-plate", plate)):
                for nm in names:
                    out = re.sub(
                        r'(<img[^>]*src="[^"]*' + re.escape(nm) + r'[^"]*")',
                        r'\1 ' + attr, out)

            if out != t:
                io.open(p, "w", encoding="utf-8", newline="\n").write(out)
            n_t += out.count("data-themed")
            n_p += out.count("data-plate")

    return n_t, n_p, sorted(plate)


def plate_pages(site):
    """옛 이름. `mark_pages` 로 넘긴다."""
    n_t, n_p, plate = mark_pages(site)
    return n_p, plate


def _figs_in_pages(site):
    """페이지들이 `<img>` 로 부르는 그림을, 사이트 기준 «경로» 로 돌려준다.

    폴더를 손으로 적지 않는다. `assets/visual` 만 세다가 `assets/architecture.svg`
    같은 것을 통째로 놓친 적이 있다 (2026-09-14). 페이지가 부르는 것을 센다.
    브랜드 마크는 이미 따로 밝은판/어두운판을 갖고 있어 뺀다.
    """
    skip = ("wordmark", "logo", "favicon", "icon", "lockup", "brand")
    want = set()
    for root, _dirs, files in os.walk(site):
        if os.sep + "." in root:
            continue
        for f in files:
            if not f.endswith(".html"):
                continue
            page = os.path.join(root, f)
            s = io.open(page, encoding="utf-8", errors="ignore").read()
            for m in re.findall(r'<img[^>]+src="([^"]*\.svg)[^"]*"', s):
                rel = m.split("?")[0]
                name = os.path.basename(rel)
                if name.endswith(DARK_SUFFIX) or any(k in name for k in skip):
                    continue
                if rel.startswith("/"):
                    p = os.path.normpath(os.path.join(site, rel.lstrip("/")))
                else:
                    p = os.path.normpath(os.path.join(os.path.dirname(page), rel))
                want.add(os.path.relpath(p, site).replace("\\", "/"))
    return want


def check(site, _unused=None):
    """배포본을 다시 잰다. 문자열을 찾는 것이 아니라 파일을 세고 읽는다."""
    want = _figs_in_pages(site)

    # 짝을 «만들 수 있는데» 없는 것만 결함이다. 손그림 그림은 밝은 판으로 간다.
    missing = sorted(r for r in want
                     if themeable(os.path.join(site, r))
                     and not os.path.isfile(os.path.join(site, dark_name(r))))
    plated = sorted(r for r in want
                    if not os.path.isfile(os.path.join(site, dark_name(r))))

    # 아직 OS 설정을 보는 파일이 있으면, 토글과 서로 다른 말을 하게 된다
    left = []
    for r in sorted(want):
        p = os.path.join(site, r)
        if not os.path.isfile(p):
            continue
        if "prefers-color-scheme" in io.open(p, encoding="utf-8",
                                             errors="ignore").read():
            left.append(r)

    ok = not missing and not left
    print("  페이지가 부르는 그림 %d종 · 짝 있음 %d · 밝은 판 %d · "
          "짝 빠짐 %d · OS설정을 보는 파일 %d"
          % (len(want), len(want) - len(plated) - len(missing), len(plated),
             len(missing), len(left)))
    if plated:
        print("     밝은 판 (다크 색 미정): %s"
              % ", ".join(os.path.basename(x) for x in plated))

    if missing:
        print("     다크 짝이 없다: %s" % ", ".join(os.path.basename(x) for x in missing[:6]))
    if left:
        print("     아직 OS 설정을 본다: %s" % ", ".join(os.path.basename(x) for x in left[:6]))

    return ok


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    write = "--write" in argv
    dirs = [a for a in argv if not a.startswith("--")] or [
        os.path.join(LAB, "docs", "assets", "visual"),
        os.path.join(LAB, "web", "assets", "visual"),
    ]

    if not _selftest():
        return 1

    total = 0
    for d in dirs:
        if not os.path.isdir(d):
            print("  [!] 폴더가 없다: %s" % d)
            return 1
        n = 0
        for f in sorted(os.listdir(d)):
            if not f.endswith(".svg") or f.endswith(DARK_SUFFIX):
                continue
            if not write:
                n += 1
                continue
            changed, why = write_pair(os.path.join(d, f))
            if changed:
                n += 1
            elif why and "지움" not in why:
                print("     건너뜀 %s · %s" % (f, why))
        print("  %s · %s %d장" % (d, "고침" if write else "대상", n))
        total += n

    if not write:
        print("  (--write 를 줘야 실제로 씁니다)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
