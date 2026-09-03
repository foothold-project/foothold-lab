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
import re
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
@page { size: A4; margin: 15mm 14mm 16mm 14mm; }
:root { --ink:#1a1a1a; --muted:#5a5a5a; --line:#d8d8d8; --accent:#c2410c; --wash:#faf8f6; }
* { box-sizing: border-box; }
body {
  font-family: "Malgun Gothic","맑은 고딕","Apple SD Gothic Neo","Noto Sans KR",sans-serif;
  font-size: 9.5pt; line-height: 1.62; color: var(--ink);
  margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
h1 { font-size: 18pt; letter-spacing:-.02em; margin: 0 0 3mm; padding-bottom: 2.4mm;
     border-bottom: 2.2pt solid var(--accent); }
h2 { font-size: 12.6pt; margin: 6.5mm 0 2.4mm; padding-left: 2.2mm;
     border-left: 3.2pt solid var(--accent); break-after: avoid; }
h3 { font-size: 10.8pt; margin: 4.4mm 0 1.6mm; color:#333; break-after: avoid; }
h4 { font-size: 10.4pt; margin: 4mm 0 1.5mm; color: var(--muted); break-after: avoid; }
/* 문단을 쪽 경계에서 쪼개지 않는다. Chrome 은 orphans/widows 를 안
   듣기 때문에, 이 문서처럼 문단이 짧을 때는 통째로 넘기는 쪽이 낫다.
   안 그러면 「다.」 한 음절만 다음 쪽 머리에 남는다. */
p, li { margin: 0 0 2.1mm; break-inside: avoid; }
li { margin-bottom: 1.1mm; }
/* 제목이 쪽 끝에 홀로 남는 것을 막는다. 제목만 붙잡으면 「제목 + 도입
   한 줄」만 남고 표·도식이 다음 쪽으로 가므로 도입 문단도 함께 잡는다. */
h1, h2, h3, h4 { break-inside: avoid; }
strong { font-weight: 700; }
hr { border: 0; border-top: .6pt solid var(--line); margin: 5mm 0; }
a { color: inherit; text-decoration: none; }

/* 표는 쪽을 넘어 이어질 수 있어야 한다. 통째로 avoid 를 걸면 긴 표가
   다음 쪽으로 통째로 밀려 앞쪽에 빈 반 쪽이 남는다. 행은 안 쪼갠다. */
table { width: 100%; border-collapse: collapse; margin: 3mm 0 5mm;
        font-size: 8.7pt; break-inside: auto; }
/* 한글은 낱말 안에서 끊지 않는다. keep-all 이 없으면 좁은 칸에서
   「오흥/재」 「커스터마/이징」처럼 이름과 낱말이 두 줄로 쪼개진다. */
th, td { border: .5pt solid var(--line); padding: 1.5mm 2mm; text-align: left;
         vertical-align: top; line-height: 1.5;
         word-break: keep-all; overflow-wrap: break-word; }
th { background: var(--wash); font-weight: 700; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
/* 짧은 표는 통째로 넘긴다. 6행짜리 표가 머리와 한 줄만 남기고 갈리면
   쪽 끝에 토막이 남는다. 판정은 generator 가 행 수와 글자 수로 한다. */
table.tight { break-inside: avoid; }

img { max-width: 100%; height: auto; display: block; margin: 3mm auto 4mm;
      break-inside: avoid; }

blockquote { margin: 2.4mm 0 3mm; padding: 2.2mm 3.4mm; background: var(--wash);
             border-left: 2.4pt solid var(--accent); color:#333; break-inside: avoid; }
blockquote p { margin: 0; }

ul, ol { margin: 0 0 3mm; padding-left: 6mm; }

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

    # 끝에 남은 구분선과 빈 줄을 턴다. 안 그러면 빈 쪽이 하나 더 붙는다
    while lines and (not lines[-1].strip() or lines[-1].strip() == "---"):
        lines.pop()
    return "\n".join(lines) + "\n"


TIGHT_ROWS = 9       # 이보다 행이 많으면 쪽을 넘어 이어지게 둔다
TIGHT_CHARS = 400    # 행이 적어도 칸 글자가 많으면 한 쪽에 안 들어간다


def mark_tight_tables(html):
    """한 쪽에 들어갈 만한 표에 tight 를 달아 쪽 경계에서 안 갈리게 한다."""
    out, pos = [], 0
    while True:
        i = html.find("<table", pos)
        if i < 0:
            out.append(html[pos:])
            return "".join(out)
        j = html.find("</table>", i)
        if j < 0:
            out.append(html[pos:])
            return "".join(out)
        j += len("</table>")
        block = html[i:j]
        rows = block.count("<tr")
        text = re.sub(r"<[^>]+>", "", block)
        out.append(html[pos:i])
        if rows <= TIGHT_ROWS and len(text) <= TIGHT_CHARS:
            out.append(block.replace("<table", '<table class="tight"', 1))
        else:
            out.append(block)
        pos = j


PAGEBREAK = '<div style="break-before: page"></div>'
ORPHAN_TAIL = 0.14   # 제목 아래 남은 내용이 쪽 높이의 이만큼도 안 되면 고아다


def orphan_headings(pdf_path):
    """쪽 끝에 홀로 남은 절 제목을 찾는다. PyMuPDF 가 없으면 건너뛴다.

    제목의 위치가 아니라 **그 아래에 실린 내용의 세로 길이**로 판정한다.
    제목이 쪽 중간에 있어도 밑에 두 줄만 붙어 있으면 고아다.
    """
    try:
        import fitz
    except ImportError:
        return None
    found = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            h = page.rect.height
            blocks = [b for b in page.get_text("blocks") if b[4].strip()]
            if not blocks:
                continue
            bottom = max(b[3] for b in blocks)
            for b in blocks:
                line = b[4].strip().split("\n")[0].strip()
                if not re.match(r"^\d+\.\s", line):
                    continue
                if (bottom - b[1]) / h < ORPHAN_TAIL:
                    found.append(line)
    return found


def insert_breaks(md_text, headings):
    """해당 제목 앞에 쪽 나눔을 넣는다. 이미 있으면 그대로 둔다."""
    lines = md_text.split("\n")
    out, hit = [], 0
    for ln in lines:
        if ln.startswith("## ") and ln[3:].strip() in headings:
            if not (out and out[-1].strip() == PAGEBREAK):
                out.append(PAGEBREAK)
                out.append("")
                hit += 1
        out.append(ln)
    return "\n".join(out), hit


BIG_GAP = 0.34   # 이보다 아래가 비면 「휑한 쪽」으로 센다


def layout_score(pdf_path):
    """작을수록 좋은 조판 점수. 고아 제목이 가장 무겁고, 그다음이 휑한 쪽이다."""
    try:
        import fitz
    except ImportError:
        return None
    orphans = len(orphan_headings(pdf_path) or [])
    gaps = []
    with fitz.open(pdf_path) as doc:
        pages = doc.page_count
        for page in doc:
            blocks = [b for b in page.get_text("blocks") if b[4].strip()]
            h = page.rect.height
            gaps.append(1.0 if not blocks else (h - max(b[3] for b in blocks)) / h)
    big = sum(1 for g in gaps if g > BIG_GAP)
    return orphans * 100 + big * 12 + pages + sum(gaps), orphans, big, pages


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
    ap.add_argument("--no-balance", action="store_true",
                    help="쪽 끝 제목 정리를 끈다")
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

    body = src.read_text(encoding="utf-8")
    if args.submission:
        body = strip_for_submission(body)
    staged = html.with_name(html.stem + ".src.md")

    def bake(text):
        staged.write_text(text, encoding="utf-8")
        subprocess.run(
            ["pandoc", str(staged), "-f", "gfm", "-t", "html5", "-s",
             "--metadata", "title=" + src.stem, "-c", css.name, "-o", str(html)],
            check=True,
        )
        html.write_text(mark_tight_tables(html.read_text(encoding="utf-8")),
                        encoding="utf-8")
        subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
             "--run-all-compositor-stages-before-draw", "--virtual-time-budget=8000",
             f"--print-to-pdf={out}", html.as_uri()],
            check=True,
        )
        if not out.is_file():
            sys.exit("Chrome 이 PDF 를 안 냈다.")

    bake(body)

    # 쪽 끝에 홀로 남은 절 제목이 있으면 그 앞을 끊고 다시 굽는다.
    # CSS 로 제목·도입·본문을 통째로 묶으면 여백이 크게 벌어져서, 실제로
    # 고아가 생긴 자리만 골라 끊는다. 넉넉히 두 번이면 수렴한다.
    if not args.no_balance:
        best = layout_score(out)
        if best is None:
            print("  (PyMuPDF 가 없어 쪽 균형 검사를 건너뛴다)")
        else:
            for _ in range(4):
                bad = orphan_headings(out)
                if not bad:
                    break
                trial, hit = insert_breaks(body, {bad[0]})
                if not hit:
                    break
                bake(trial)
                score = layout_score(out)
                if score[0] < best[0]:
                    body, best = trial, score
                    print(f"  쪽 나눔 추가: {bad[0]}"
                          f"  (고아 {score[1]} · 휑한 쪽 {score[2]} · {score[3]}쪽)")
                else:
                    # 끊으면 오히려 나빠진다. 되돌리고 그대로 둔다
                    print(f"  쪽 나눔 보류: {bad[0]}  (끊으면 여백이 더 커진다)")
                    bake(body)
                    break
            print(f"  조판 결과: 고아 {best[1]} · 휑한 쪽 {best[2]} · {best[3]}쪽")

    if not args.keep_html:
        html.unlink(missing_ok=True)
        css.unlink(missing_ok=True)
        staged.unlink(missing_ok=True)
    print(f"{out}  {out.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
