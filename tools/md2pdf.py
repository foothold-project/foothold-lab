#!/usr/bin/env python3
"""마크다운 제출본을 PDF 로 굽는다.

왜 이 조합인가. 이 저장소는 설치할 것이 없어야 한다(AGENTS.md §1).
LaTeX 없이 한글 조판이 되는 경로가 필요해서 pandoc 으로 HTML 을 만들고
Chrome 의 인쇄 엔진으로 PDF 를 뽑는다. 둘 다 이 워크스테이션에 이미 있다.

  python tools/md2pdf.py deliverables/plan/proposal.md --submission

같은 이름의 .pdf 가 옆에 생긴다. 중간 HTML 은 지운다(--keep-html 로 남긴다).

--submission 은 저장소 안에서만 뜻이 있는 것을 PDF 에서 뺀다.
  · 파일명이 제목으로 올라가는 pandoc 표제 블록
  · 문서 맨 앞의 팀 표준 머리 (분류 · 작성 · 근거 · 요지 · 상태 · 이슈)
  · <!-- 제출본 제외 --> 와 <!-- /제출본 제외 --> 사이

마크다운 원본은 안 고친다. 빼는 것은 PDF 를 구울 때만이다.
"""
import argparse
import os
import pathlib
import shutil
import subprocess
import sys

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    "google-chrome",
    "chromium",
]

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm; }
:root { --ink:#1a1a1a; --muted:#5a5a5a; --line:#d8d8d8; --accent:#c2410c; --wash:#faf8f6; }
* { box-sizing: border-box; }
body {
  font-family: "Malgun Gothic","맑은 고딕","Apple SD Gothic Neo","Noto Sans KR",sans-serif;
  font-size: 10.2pt; line-height: 1.72; color: var(--ink);
  margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
h1 { font-size: 20pt; letter-spacing:-.02em; margin: 0 0 4mm; padding-bottom: 3mm;
     border-bottom: 2.2pt solid var(--accent); }
h2 { font-size: 13.5pt; margin: 9mm 0 3mm; padding-left: 2.4mm;
     border-left: 3.2pt solid var(--accent); break-after: avoid; }
h3 { font-size: 11.4pt; margin: 6mm 0 2mm; color:#333; break-after: avoid; }
h4 { font-size: 10.4pt; margin: 4mm 0 1.5mm; color: var(--muted); break-after: avoid; }
p { margin: 0 0 2.6mm; }
strong { font-weight: 700; }
hr { border: 0; border-top: .6pt solid var(--line); margin: 7mm 0; }
a { color: inherit; text-decoration: none; }

table { width: 100%; border-collapse: collapse; margin: 3mm 0 5mm;
        font-size: 9.3pt; break-inside: avoid; }
th, td { border: .5pt solid var(--line); padding: 1.9mm 2.4mm; text-align: left;
         vertical-align: top; line-height: 1.55; }
th { background: var(--wash); font-weight: 700; }
tr { break-inside: avoid; }

blockquote { margin: 3mm 0 4mm; padding: 2.6mm 4mm; background: var(--wash);
             border-left: 2.4pt solid var(--accent); color:#333; break-inside: avoid; }
blockquote p { margin: 0; }

ul, ol { margin: 0 0 3mm; padding-left: 6mm; }
li { margin-bottom: 1.1mm; }

pre { background:#f5f3f1; border:.5pt solid var(--line); border-radius: 1mm;
      padding: 3mm 3.5mm; font-size: 8.4pt; line-height: 1.5; overflow: visible;
      white-space: pre; break-inside: avoid; }
code { font-family: Consolas,"D2Coding",monospace; font-size: .92em; }
p code, td code, li code { background:#f0eeec; padding: .3mm 1mm; border-radius: .8mm; }
pre code { background: none; padding: 0; }

sup { font-size: .72em; }
"""

HIDE_TITLE_BLOCK = "\nheader#title-block-header { display: none; }\n"

EXCLUDE_OPEN = "<!-- 제출본 제외 -->"
EXCLUDE_CLOSE = "<!-- /제출본 제외 -->"


def strip_for_submission(text):
    """저장소 안에서만 뜻이 있는 것을 덜어낸다. 원본 파일은 안 고친다."""
    while EXCLUDE_OPEN in text and EXCLUDE_CLOSE in text:
        head, rest = text.split(EXCLUDE_OPEN, 1)
        _, tail = rest.split(EXCLUDE_CLOSE, 1)
        text = head + tail.lstrip("\n")

    # 맨 앞 팀 표준 머리. 제목 줄(#) 바로 뒤에 오는 인용 덩어리만 본다
    lines = text.split("\n")
    i = 0
    while i < len(lines) and (not lines[i].strip() or lines[i].startswith("# ")):
        i += 1
    if i < len(lines) and lines[i].startswith("> 분류:"):
        j = i
        while j < len(lines) and lines[j].startswith(">"):
            j += 1
        del lines[i:j]
        while i < len(lines) and not lines[i].strip():
            del lines[i]
        # 머리를 뺐으면 그 아래 구분선도 뺀다. 제목 밑에 줄이 두 겹으로 남는다
        if i < len(lines) and lines[i].strip() == "---":
            del lines[i]
            while i < len(lines) and not lines[i].strip():
                del lines[i]
    return "\n".join(lines)


def find_chrome():
    for c in CHROME_CANDIDATES:
        if os.path.isfile(c):
            return c
        found = shutil.which(c)
        if found:
            return found
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("-o", "--out")
    ap.add_argument("--keep-html", action="store_true")
    ap.add_argument("--submission", action="store_true",
                    help="저장소 전용 표기를 뺀 제출본으로 굽는다")
    args = ap.parse_args()

    src = pathlib.Path(args.source).resolve()
    if not src.is_file():
        sys.exit(f"없는 파일: {src}")
    out = pathlib.Path(args.out).resolve() if args.out else src.with_suffix(".pdf")
    html = out.with_suffix(".html")

    if not shutil.which("pandoc"):
        sys.exit("pandoc 이 없다. HTML 변환 경로가 막힌다.")
    chrome = find_chrome()
    if not chrome:
        sys.exit("Chrome 을 못 찾았다. PDF 인쇄 경로가 막힌다.")

    css = html.with_name(html.stem + ".css")
    css.write_text(CSS + (HIDE_TITLE_BLOCK if args.submission else ""), encoding="utf-8")

    feed = src
    staged = None
    if args.submission:
        staged = html.with_name(html.stem + ".src.md")
        staged.write_text(strip_for_submission(src.read_text(encoding="utf-8")),
                          encoding="utf-8")
        feed = staged

    subprocess.run(
        ["pandoc", str(feed), "-f", "gfm", "-t", "html5", "-s",
         "--metadata", "title=" + src.stem, "-c", css.name, "-o", str(html)],
        check=True,
    )

    subprocess.run(
        [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         "--run-all-compositor-stages-before-draw", "--virtual-time-budget=8000",
         f"--print-to-pdf={out}", html.as_uri()],
        check=True,
    )
    if not out.is_file():
        sys.exit("Chrome 이 PDF 를 안 냈다.")

    if not args.keep_html:
        html.unlink(missing_ok=True)
        css.unlink(missing_ok=True)
        if staged:
            staged.unlink(missing_ok=True)
    print(f"{out}  {out.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
