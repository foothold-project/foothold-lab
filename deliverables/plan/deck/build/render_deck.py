# -*- coding: utf-8 -*-
"""슬라이드 원본과 deck-data, SVG를 자립형 HTML 한 파일로 렌더한다."""

from __future__ import annotations

import argparse
import base64
import html
import json
from pathlib import Path


def inline_asset(deck_root: Path, visual: dict) -> str:
    asset = visual.get("asset")
    if not asset:
        return ""
    path = deck_root / asset
    if not path.exists():
        raise SystemExit(f"웹 덱 렌더 실패: 시각 자산이 없습니다: {asset}")
    if path.suffix.lower() == ".svg":
        return path.read_text(encoding="utf-8")
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'<img src="data:{mime};base64,{data}" alt="{html.escape(visual.get("alt", ""))}">'


def chip(evidence: dict) -> str:
    return (f'<span class="chip {html.escape(evidence["class"])}">'
            f'<b>{html.escape(evidence["category"])}</b> · {html.escape(evidence["chip"])}'
            f'</span>')


def gate_svg(data: dict, compact: bool = False) -> str:
    gates = data["summary"]["gates"]
    start = gates[0]["date"]
    end = gates[-1]["date"]
    from datetime import date
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    width = 1220
    points = []
    for gate in gates:
        ratio = (date.fromisoformat(gate["date"]) - a).days / max(1, (b - a).days)
        x = 74 + ratio * 1068
        points.append((x, gate))
    out = [f'<svg class="gate-svg" viewBox="0 0 {width} 360" role="img" aria-label="다섯 관문 타임라인">',
           '<line x1="74" y1="164" x2="1142" y2="164" class="timeline-line"/>']
    for index, (x, gate) in enumerate(points):
        y = 164
        out.append(f'<circle cx="{x:.1f}" cy="{y}" r="12" class="gate-dot"/>')
        anchor = "start" if index == 0 else "end" if index == len(points)-1 else "middle"
        out.append(f'<text x="{x:.1f}" y="{112 if index % 2 == 0 else 226}" text-anchor="{anchor}" class="gate-name">{html.escape(gate["name"])}</text>')
        out.append(f'<text x="{x:.1f}" y="{136 if index % 2 == 0 else 250}" text-anchor="{anchor}" class="gate-date">{html.escape(gate["date"][5:].replace("-", "."))}</text>')
        if not compact:
            out.append(f'<text x="{x:.1f}" y="{286 if index % 2 == 0 else 314}" text-anchor="{anchor}" class="gate-count">이슈 {gate["issueCount"]} · 완료 {gate["completedCount"]}</text>')
    out.append('</svg>')
    return "".join(out)


def render_visual(deck_root: Path, slide: dict, deck_data: dict) -> str:
    kind = slide["visual"].get("type")
    if kind == "wbs-timeline":
        status = deck_data["implementationStages"]
        disabled = (f'<div class="stage-off"><b>구현 단계 막대 비활성</b>'
                    f'<span>{html.escape(status["reason"])}</span></div>') if not status["active"] else ""
        return '<div class="timeline-wrap">' + gate_svg(deck_data) + disabled + '</div>'
    if kind == "gate-timeline":
        return '<div class="timeline-wrap compact">' + gate_svg(deck_data, compact=True) + '</div>'
    return inline_asset(deck_root, slide["visual"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slides", default="deliverables/plan/deck/content/slides.json")
    parser.add_argument("--data", default="deliverables/plan/deck/content/deck-data.json")
    parser.add_argument("--output", default="deliverables/plan/deck/index.html")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[4]
    deck_root = repo_root / "deliverables" / "plan" / "deck"
    slides_doc = json.loads((repo_root / args.slides).read_text(encoding="utf-8"))
    deck_data = json.loads((repo_root / args.data).read_text(encoding="utf-8"))
    slides = slides_doc.get("slides")
    if not slides or len(slides) != 11:
        raise SystemExit("웹 덱 렌더 실패: 슬라이드 원본은 정확히 11장이어야 합니다")
    seconds = sum(s["notes"]["seconds"] for s in slides)
    if seconds > 600:
        raise SystemExit(f"웹 덱 렌더 실패: 발표자 노트 합계가 10분을 넘습니다: {seconds}초")
    for slide in slides:
        if not 40 <= slide["notes"]["seconds"] <= 70:
            raise SystemExit(f"웹 덱 렌더 실패: {slide['id']} 시간은 40~70초여야 합니다")

    sections = []
    notes = []
    for number, slide in enumerate(slides, 1):
        chips = "".join(chip(item) for item in slide["evidence"])
        body = "".join(f'<p>{html.escape(line)}</p>' for line in slide.get("body", []))
        visual = render_visual(deck_root, slide, deck_data)
        sections.append(f'''<section class="slide" data-slide="{number}" aria-label="{number}번 슬라이드">
          <div class="kicker">FOOTHOLD · {number:02d}</div>
          <h1>{html.escape(slide["headline"])}</h1>
          <div class="copy">{body}</div>
          <div class="visual">{visual}</div>
          <div class="evidence">{chips}</div>
          <div class="folio">{number} / 11</div>
        </section>''')
        note_evidence = "".join(f'<li>{html.escape(e["category"])} · {html.escape(e["chip"])} · {html.escape(e.get("condition", ""))}</li>' for e in slide["evidence"])
        source_list = "".join(f'<li>{html.escape(source)}</li>' for source in slide["sources"])
        notes.append(f'''<article class="note" data-note="{number}"><h2>{number}. {html.escape(slide["headline"])}</h2>
          <p><b>말할 시간</b> {slide["notes"]["seconds"]}초</p><p>{html.escape(slide["notes"]["script"])}</p>
          <h3>근거 상태</h3><ul>{note_evidence}</ul><h3>Sources</h3><ul>{source_list}</ul></article>''')

    css = (deck_root / "build" / "theme.css").read_text(encoding="utf-8")
    js = (deck_root / "build" / "deck.js").read_text(encoding="utf-8")
    meta = deck_data["meta"]
    document = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{html.escape(slides_doc["title"])}</title><style>{css}</style></head><body>
    <main id="deck">{"".join(sections)}</main><aside id="notes" aria-label="발표자 노트"><header><b>발표자 노트</b><span>합계 {seconds}초 · {seconds//60}분 {seconds%60}초</span></header>{"".join(notes)}</aside>
    <div id="meta">WBS {deck_data["summary"]["issueCount"]}개 · 생성 {html.escape(meta["generatedAt"])} · {html.escape(meta["contentSha256"][:12])}</div>
    <button id="theme" aria-label="색상 모드 전환">◐</button><button id="notes-toggle" aria-label="발표자 노트 열기">N</button>
    <script>{js}</script></body></html>'''
    output = repo_root / args.output
    output.write_text(document, encoding="utf-8")
    print(f"웹 덱 생성: {output.relative_to(repo_root)} · 11장 · {seconds}초")


if __name__ == "__main__":
    main()
