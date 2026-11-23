"""Build the E2 report draft from pinned decision ledger lines."""
from __future__ import annotations

import html
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
LEDGER = HERE.parent / "decisions.tsv"
REPO = HERE.parents[3]
SOURCE_HEAD = HERE / "report_head.html"
ROWS = LEDGER.read_text(encoding="utf-8-sig").splitlines()
LEDGER_COMMIT = subprocess.check_output(
    ["git", "-C", str(REPO), "log", "-1", "--format=%H", "--", str(LEDGER.relative_to(REPO))], text=True
).strip()
LEDGER_URL = f"https://github.com/foothold-project/foothold-lab/blob/{LEDGER_COMMIT}/{LEDGER.relative_to(REPO)}"


def evidence(needle: str, *, limit: int = 220) -> tuple[str, str]:
    hits = [(i, row) for i, row in enumerate(ROWS, 1) if needle in row]
    if len(hits) != 1:
        raise ValueError(f"expected one ledger row for {needle!r}, got {len(hits)}")
    line, row = hits[0]
    parts = row.split("\t")
    quote = parts[2] if len(parts) > 2 else row
    quote = quote[:limit].rstrip() + ("…" if len(quote) > limit else "")
    if "\u2014" in quote:
        raise ValueError(f"em dash in ledger excerpt, line {line}")
    return quote, f"{LEDGER_URL}#L{line}"


SOURCES = {
    "canon": evidence("정본 3 m15500 은 C/box L4"),
    "parent": evidence("m1250 E 전진 0.5 열"),
    "b250": evidence("E2b m250 지킬 칸"),
    "b500": evidence("평균대 L5 공식 지도 이득 E2b m500"),
    "b750": evidence("평균대 L5 공식 지도 이득 E2b m750"),
    "p1": evidence("E2b m750 P1 공식"),
    "clean": evidence("E2b m500 남은 칸"),
    "keep750": evidence("E2b m750 지킬 칸 · 지도 이득 끝"),
    "delay": evidence("m1500E2 (본줄 · m1250 E raw"),
    "dp": evidence("판정 = 적응 없음 (턱걸이"),
    "camera": evidence("목표 5 · 6 얼림 후보 E2b m250"),
    "camera_edge": evidence("목표 5 B/beam L4 복원 지도 결함 덤프"),
    "onnx": evidence("목표 6 E2b m250 ONNX 나옴"),
    "onnx_limit": evidence("E2b ONNX 는 app-lx 에 안 넘김"),
}


def ref(key: str) -> str:
    return SOURCES[key][1]


def quote(key: str) -> str:
    return SOURCES[key][0]


SECTIONS = [
    ("목표와 평가 항목", [
        ("지킬 칸", "확인된 범위만", "b250"),
        ("다음 지형 묶음", "계획 · 실행 대조 필요", "canon"),
        ("평균대 지도 이득", "두 경계 근거 있음", "b750"),
        ("깃발 방향", "이 초안의 E2b 근거 미확인", None),
        ("카메라 자리와 복원 오차", "경계별 근거 일부 있음", "camera"),
        ("ONNX 실기 넘김", "제한 근거 있음", "onnx_limit"),
        ("추가 목표 항목 가", "정식 목표 문구 미확인", None),
        ("추가 목표 항목 나", "정식 목표 문구 미확인", None),
        ("추가 목표 항목 다", "정식 목표 문구 미확인", None),
        ("추가 목표 항목 라", "정식 목표 문구 미확인", None),
    ]),
    ("학습 줄기", [
        ("START 기반 기준 저장본", "canon"),
        ("이전 E 경계 저장본", "parent"),
        ("E2b 첫 경계", "b250"),
        ("E2b 다음 경계", "b500"),
        ("E2b 최근 경계", "b750"),
    ]),
    ("평균대와 지킬 칸", [
        ("공식 지도 이득 첫 창", "b500"),
        ("공식 지도 이득 다음 창", "b750"),
        ("단계 평가", "p1"),
        ("깨끗이 건넘", "clean"),
        ("지킬 칸 첫 경계", "b250"),
        ("지킬 칸 최근 경계", "keep750"),
    ]),
    ("지연 처치", [
        ("지연 없는 E2b", "delay"),
        ("지연 유지 DP", "dp"),
    ]),
    ("카메라와 ONNX", [
        ("카메라 자리 평가", "camera"),
        ("복원 지도 테두리 사례", "camera_edge"),
        ("ONNX 산출", "onnx"),
        ("실기 넘김 제한", "onnx_limit"),
    ]),
]


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    return "| " + " | ".join(headers) + " |\n| " + " | ".join("---" for _ in headers) + " |\n" + "\n".join(
        "| " + " | ".join(cell.replace("|", "\\|").replace("\n", " ") for cell in row) + " |" for row in rows
    )


def make_markdown() -> str:
    out = [
        "# EX-42 E2 결과 보고서 · 초안",
        "> 분류: 시뮬 결과 보고서 초안",
        "> 작성: Claude 세션 (오흥재 지시, scripter-lx) · 2026-11-24",
        f"> 근거: [결정 원장]({LEDGER_URL}) · {LEDGER_COMMIT}",
        "> 요지: 경계별 평가 근거를 모아 정식 보고서의 빈칸과 한계를 드러낸다",
        "> 상태: 초안 · 발행 금지 · 원장 밖 숫자 미확인",
        "",
        "이 문서는 보고서 구조와 원장 근거의 연결을 시험하는 초안이다. 인용은 원장 행에서 생성하며 재집계 결과가 아니다.",
    ]
    for idx, (title, items) in enumerate(SECTIONS, 1):
        out.extend(["", f"## {idx}. {title}", ""])
        if idx == 1:
            rows = [[str(i), label, status, f"[원장]({ref(key)})" if key else "미확인"] for i, (label, status, key) in enumerate(items, 1)]
            out.append(md_table(["항", "임시 평가 항목", "상태", "근거"], rows))
            out.extend(["", "정식 목표 열 항의 문구와 번호는 이 초안에서 미확인이다. 위 항목명은 보고서 자리 표시이며 목표 달성 판정이 아니다."])
        else:
            rows = [[label, quote(key), f"[원장]({ref(key)})"] for label, key in items]
            out.append(md_table(["칸", "원장 원문 발췌", "근거"], rows))
            if idx == 3:
                out.extend(["", "공식 지도 이득과 깨끗이 건넘은 서로 다른 지표다. 최근 경계의 깨끗이 판정은 미확인이다."])
            if idx == 5:
                out.extend(["", "ONNX 산출과 실기 넘김 판정은 분리한다. 다른 카메라 자리의 모서리 오차와 실기 경로 확인은 미확인이다."])
    out.extend(["", "## 6. 못 한 것과 다음", "", "- 열 목표의 승인 원문, 최근 경계 깨끗이 채점, 실기 넘김 여부는 미확인이다.", "- 정식 원자료와 평가 영수증을 대조한 뒤 표와 그림을 채운다. 이 초안은 발행하지 않는다.", "", "## 부록 A. 출처와 판 이력", "", f"- 원장 판: `{LEDGER_COMMIT}`", "- v0.1 · 원장 근거 연결과 빈칸을 둔 보고서 뼈대.", ""])
    result = "\n".join(out)
    if "\u2014" in result:
        raise ValueError("em dash in markdown")
    return result


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def html_table(headers: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{esc(x)}</th>" for x in headers)
    body = "".join("<tr>" + "".join(f"<td>{x}</td>" for x in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"


def make_html() -> str:
    head = SOURCE_HEAD.read_text(encoding="utf-8").split("</head>", 1)[0]
    head = head.replace("FOOTHOLD 데이터 산출물 명세서", "FOOTHOLD · E2 결과 보고서 초안")
    head += """
<style>
@page :first { @bottom-left { content: ""; } @bottom-right { content: ""; } }
.cover-page { break-after: page; padding-top: 55mm; }
.toc-page { break-after: page; }
.chapter { break-before: page; }
.compact td { max-width: 125mm; overflow-wrap: anywhere; }
.cite { font-size: var(--font-small); color: var(--sub); }
</style>
"""
    pages = [f"""{head}</head><body>
<section class="cover-page"><div class="kicker">FOOTHOLD · 연구 보고서 초안</div>
<h1>EX-42 E2 결과 보고서</h1><p>시뮬레이션 평가 근거와 미확인 항목</p>
<p>FOOTHOLD: Sim-to-Field, Terrain-Adaptive Mission Platform for Legged Robots<br>시뮬에서 현장까지, 미경험 험지 사족보행 로봇 임무 플랫폼</p>
<p>인공지능사관학교 7기 AI 도약과정 · FOOTHOLD (실증-02)</p>
<p>작성: Claude 세션 (오흥재 지시, scripter-lx)<br>팀원·포지션: 정식 역할 정본 대조 전, 미확인</p>
<p>최종발표 대비 초안 · 2026-11-24 · v0.1<br>
<a href="https://github.com/foothold-project/foothold-lab">foothold-project/foothold-lab</a></p>
<p>발행 금지 · 수치는 원장 발췌 · 정식 평가표와 대조 전</p></section>
<section class="toc-page"><h1>목차</h1>
<p>1. 목표와 평가 항목 · 3쪽</p><p>2. 학습 줄기 · 4쪽</p>
<p>3. 평균대와 지킬 칸 · 5쪽</p><p>4. 지연 처치 · 6쪽</p>
<p>5. 카메라와 ONNX · 7쪽</p><p>6. 못 한 것과 다음 · 8쪽</p>
<p class="cite">원장 판 {esc(LEDGER_COMMIT)}</p></section>"""]
    for idx, (title, items) in enumerate(SECTIONS, 1):
        pages.append(f'<section class="chapter"><h2>{idx}. {esc(title)}</h2>')
        if idx == 1:
            rows = [[str(i), esc(label), esc(status), f'<a href="{esc(ref(key))}">원장</a>' if key else "미확인"] for i, (label, status, key) in enumerate(items, 1)]
            pages.append(html_table(["항", "임시 평가 항목", "상태", "근거"], rows))
            pages.append("<p>정식 목표 열 항의 문구와 번호는 미확인이다. 이 표는 보고서 자리 표시이며 달성 판정이 아니다.</p>")
        else:
            rows = [[esc(label), esc(quote(key)), f'<a href="{esc(ref(key))}">원장 행</a>'] for label, key in items]
            pages.append(html_table(["칸", "원장 원문 발췌", "근거"], rows))
            if idx == 3:
                pages.append("<p>공식 지도 이득과 깨끗이 건넘은 서로 다른 지표다. 최근 경계의 깨끗이 판정은 미확인이다.</p>")
            if idx == 5:
                pages.append("<p>ONNX 산출과 실기 넘김 판정은 분리한다. 다른 카메라 자리의 모서리 오차는 미확인이다.</p>")
        pages.append("</section>")
    pages.append(f"<section class=chapter><h2>6. 못 한 것과 다음</h2><p>열 목표의 승인 원문, 최근 경계 깨끗이 채점, 실기 넘김 여부는 미확인이다. 정식 원자료와 평가 영수증을 대조한 뒤 표와 그림을 채운다.</p><h3>부록 A. 출처와 판 이력</h3><p>원장 판: {esc(LEDGER_COMMIT)}</p><p>v0.1 · 원장 근거 연결과 빈칸을 둔 보고서 뼈대.</p></section></body></html>")
    result = "\n".join(pages)
    if "\u2014" in result:
        raise ValueError("em dash in HTML")
    return result


def main() -> None:
    HERE.joinpath("report.md").write_text(make_markdown(), encoding="utf-8")
    HERE.joinpath("report.html").write_text(make_html(), encoding="utf-8")
    print(f"ledger={LEDGER_COMMIT} rows={len(SOURCES)}")


if __name__ == "__main__":
    main()
