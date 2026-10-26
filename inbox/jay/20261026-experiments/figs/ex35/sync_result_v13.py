"""Sync the generated EX-35 v1.3 result to its map and local status page."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
DATA = Path(__file__).with_name("result_data.json")
EXP_MAP = ROOT / "inbox/jay/20261021-experiments/EXP-MAP.md"
LAB = Path("C:/Users/AI-WS01/s2_lab/lab_status/index.html")
KST = timezone(timedelta(hours=9))


def replace_one(source: str, pattern: str, replacement: str) -> str:
    updated, count = re.subn(pattern, lambda _match: replacement, source, count=1, flags=re.M)
    assert count == 1, pattern
    return updated


def render_exp_map(source: str, data: dict) -> str:
    assert data["window_decision"] == "STOP" and data["window_row"] == 6
    assert data["window_evidence"]["a11"]["state"] == "clear"
    t, x = data["training"], data["window_evidence"]
    status = (
        f"> 상태: 10/27 최종 기록 · EX-35 m{t['completed_iteration']} 학습 rc {t['exit_code']} · "
        f"m1950/m2000 MAINTAIN_FAIL · 창 STOP 6행 (A11 판독 반영) · {data['canonical']} 유지 · "
        "비결정성 원인 미확인"
    )
    summary = (
        "- **EX-35 최종 판정**: [RESULT-EX35 v1.3](../20261026-experiments/RESULT-EX35-1027.md)는 "
        f"학습 m{t['completed_iteration']} 종료(rc {t['exit_code']})와 m1950·m2000의 `MAINTAIN_FAIL` 두 건을 원자료에서 생성했다. "
        f"기본 창 `STOP` {data['window_default_row']}행 뒤 A11 다섯 항목 「없음」 판독을 반영한 재실행은 "
        f"`STOP` {data['window_row']}행 (REVERT)이다. 정본 `{data['canonical']}` 유지, EX-35 연장 없음. "
        "16 env 회전은 GPU1 사슬, 64 env 네 칸은 GPU0 재평가를 합쳤다. "
        f"사슬 대 재평가 map64 수치 {x['map64_numeric_changed']}/{x['map64_numeric_comparable']}칸이 달랐고 "
        f"같은 GPU0 반복도 {x['repro_a1_a2_changed']}/{x['repro_numeric_count']}칸 달랐다. "
        "코드 변경 영향과 비결정성 원인은 분리되지 않았다. A11 발자국의 좌우 휨은 수치 미측이다."
    )
    row = (
        "| [EX-35 S-B10 명령 S2a](EXP-EX35-SB10-cmd-S2a.md) | S-B10 m1500 명령 S2a 첫 축 | "
        f"부모 sha256 `{t['parent_sha256']}` | 학습 m{t['completed_iteration']} rc {t['exit_code']}; "
        f"m1950·m2000 `MAINTAIN_FAIL`. A11 판독 뒤 창 `STOP` {data['window_row']}행 (REVERT), "
        f"연장 없음. 정본 {data['canonical']} | "
        f"[RESULT-EX35 v1.3](../20261026-experiments/RESULT-EX35-1027.md) · GPU0 반복 "
        f"{x['repro_a1_a2_changed']}/{x['repro_numeric_count']} 불일치 원인 미확인 |"
    )
    source = replace_one(source, r"^> 상태:.*$", status)
    source = replace_one(source, r"^- \*\*EX-35 최종 판정\*\*:.*$", summary)
    return replace_one(source, r"^\| \[EX-35 S-B10 명령 S2a\].*$", row)


def render_lab(source: str, data: dict, now: datetime) -> str:
    assert data["window_decision"] == "STOP" and data["window_row"] == 6
    x = data["window_evidence"]
    stamp = now.astimezone(KST).strftime("%Y-%m-%d %H:%M KST")
    short_stamp = now.astimezone(KST).strftime("%m/%d %H:%M KST")
    source = replace_one(source, r"마지막 원자료 대조 <b>[^<]+</b>", f"마지막 원자료 대조 <b>{stamp}</b>")
    paragraph = (
        f"<p>EX-35 m1950 · m2000 저장본은 MAINTAIN_FAIL. 기본 창 STOP {data['window_default_row']}행 뒤 A11 다섯 항목 없음 판독을 "
        f"반영한 재실행은 STOP {data['window_row']}행 (REVERT). 연장 없음, 정본 {data['canonical']} 유지. "
        "16 env 회전은 GPU1 사슬, 64 env 네 칸은 GPU0 재평가를 합쳤다. "
        f"사슬 대 재평가 map64 {x['map64_numeric_changed']}/{x['map64_numeric_comparable']}, "
        f"같은 GPU0 반복 {x['repro_a1_a2_changed']}/{x['repro_numeric_count']} 수치가 달랐다. "
        "코드 변경 영향과 비결정성 원인은 미확인.</p>"
    )
    source = replace_one(
        source,
        r'(?s)<section class="decide">\s*<h2>[^<]+</h2>\s*<p>.*?</p>',
        f'<section class="decide">\n  <h2>팀장이 정할 것 · {short_stamp}</h2>\n  {paragraph}',
    )
    gpu1 = (
        '<div class="row"><div class="k">GPU1</div><div><span class="pill wait">평가 증거</span>'
        f"EX-35 16 env 회전 사슬과 GPU0 64 env 재평가의 합본 창 판정 STOP {data['window_row']}행. "
        "같은 GPU0 반복도 달라 재현성 원인 미확인.</div></div>"
    )
    return replace_one(source, r'<div class="row"><div class="k">GPU1</div><div>.*?</div></div>', gpu1)


def update(data_path: Path = DATA, exp_map: Path = EXP_MAP, lab: Path = LAB, now: datetime | None = None) -> None:
    data = json.loads(data_path.read_text(encoding="utf-8"))
    moment = now or datetime.now(KST)
    map_text = render_exp_map(exp_map.read_text(encoding="utf-8"), data)
    lab_text = render_lab(lab.read_text(encoding="utf-8"), data, moment)
    exp_map.write_text(map_text, encoding="utf-8", newline="\n")
    lab.write_text(lab_text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    update()
