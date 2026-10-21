"""Check decision, experiment-card, chain, and schedule synchronization.

The schedule's last update is the latest Git commit touching SCHEDULE-NOW.md.
No GPU, Kit, or experiment process is started by this read-only checker.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


DEFAULT_CHAIN = Path("C:/Users/AI-WS01/s2_lab/chain/chain_state.json")
DECISION_REL = Path("inbox/jay/20261019-design/DECISION-SYNC.md")
MAP_REL = Path("inbox/jay/20261021-experiments/EXP-MAP.md")
SCHEDULE_REL = Path("inbox/jay/20261019-design/SCHEDULE-NOW.md")
CARD_NAME = re.compile(r"EXP-[A-Za-z0-9-]+\.md\Z")
CARD_LINK = re.compile(r"\[[^]]+\]\((EXP-[A-Za-z0-9-]+\.md)\)")
VIDEO_PATH = re.compile(
    r"(?:[A-Za-z]:[/\\]|\.{1,2}[/\\]|/|[A-Za-z0-9_.-]+[/\\])"
    r"[^\s<>()[\]`]+\.(?:mp4|mov|mkv|webm)(?:\?[^\s<>()[\]`]*)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Row:
    area: str
    item: str
    ok: bool
    detail: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def split_row(line: str) -> list[str]:
    if not line.startswith("|") or not line.endswith("|"):
        raise ValueError("표 행의 앞뒤 | 누락")
    return [cell.strip() for cell in line[1:-1].split("|")]


def marked_table(text: str, marker: str, expected: tuple[str, ...]) -> list[list[str]]:
    lines = text.splitlines()
    indices = [i for i, line in enumerate(lines) if line.strip() == marker]
    if len(indices) != 1:
        raise ValueError(f"{marker} 표시가 정확히 한 번 필요함")
    start = indices[0] + 1
    if start + 1 >= len(lines):
        raise ValueError(f"{marker} 뒤 표 누락")
    header = split_row(lines[start])
    if tuple(header[: len(expected)]) != expected:
        raise ValueError(f"{marker} 표 머리 불일치: {header}")
    separator = split_row(lines[start + 1])
    if len(separator) != len(header) or any(not re.fullmatch(r":?-{3,}:?", x) for x in separator):
        raise ValueError(f"{marker} 표 구분선 오류")
    rows: list[list[str]] = []
    for line in lines[start + 2 :]:
        if not line.strip():
            break
        cells = split_row(line)
        if len(cells) != len(header):
            raise ValueError(f"{marker} 열 개수 불일치: {line[:80]}")
        rows.append(cells)
    if not rows:
        raise ValueError(f"{marker} 데이터 행 없음")
    return rows


def decision_rows(text: str) -> list[Row]:
    rows = marked_table(text, "<!-- exp-sync:decision:v1 -->", ("체크", "결정"))
    findings: list[Row] = []
    seen: set[str] = set()
    for cells in rows:
        check, name = cells[:2]
        if not name or name in seen:
            findings.append(Row("결정", name or "이름 없음", False, "결정 이름 누락 또는 중복"))
        elif check == "[x]":
            findings.append(Row("결정", name, True, "반영 자리 확인 표시"))
        elif check == "[ ]":
            findings.append(Row("결정", name, False, "반영 자리 미완료"))
        else:
            findings.append(Row("결정", name, False, "체크는 [x] 또는 [ ]만 허용"))
        seen.add(name)
    return findings


def experiment_cards(text: str) -> tuple[dict[str, str], list[Row]]:
    rows = marked_table(text, "<!-- exp-sync:experiments:v1 -->", ("카드",))
    cards: dict[str, str] = {}
    findings: list[Row] = []
    for cells in rows:
        match = CARD_LINK.fullmatch(cells[0])
        if match is None:
            findings.append(Row("실험 목록", cells[0], False, "첫 칸에 EXP-*.md 카드 링크 필요"))
            continue
        filename = match.group(1)
        if not CARD_NAME.fullmatch(filename):
            findings.append(Row("실험 목록", filename, False, "카드 파일 이름 오류"))
            continue
        identifier = filename.removeprefix("EXP-").removesuffix(".md")
        if identifier in cards:
            findings.append(Row("실험 목록", identifier, False, "실험 ID 중복"))
        else:
            cards[identifier] = filename
    return cards, findings


def sections(text: str) -> dict[str, str]:
    headings = list(re.finditer(r"^##[ \t]+(.+?)\s*$", text, re.MULTILINE))
    return {
        match.group(1): text[match.end() : headings[i + 1].start() if i + 1 < len(headings) else len(text)].strip()
        for i, match in enumerate(headings)
    }


def card_row(identifier: str, path: Path) -> Row:
    if not path.is_file():
        return Row("실험 카드", identifier, False, f"파일 없음: {path.name}")
    parts = sections(read_text(path))
    missing = [label for label in ("가설", "설정", "결과", "다음") if not any(
        heading.startswith(label) and body for heading, body in parts.items()
    )]
    result = next((body for heading, body in parts.items() if heading == "결과"), "")
    if result and "영상 없음 · 미확인" not in result and VIDEO_PATH.search(result) is None:
        missing.append("결과 절의 영상 경로 또는 영상 없음 · 미확인")
    return Row("실험 카드", identifier, not missing, "4절·영상 확인" if not missing else "누락: " + ", ".join(missing))


def chain_rows(map_text: str, cards: dict[str, str], state_path: Path) -> list[Row]:
    table = marked_table(map_text, "<!-- exp-sync:chain:v1 -->", ("사슬 작업", "카드 또는 분류"))
    mapping: dict[str, str] = {}
    findings: list[Row] = []
    for name_cell, target, *_ in table:
        name = name_cell.strip("`")
        if not name or name in mapping:
            findings.append(Row("사슬 목록", name or "이름 없음", False, "작업 이름 누락 또는 중복"))
        elif target != "운영" and target not in cards:
            findings.append(Row("사슬 목록", name, False, f"지도에 없는 카드 ID: {target}"))
        mapping[name] = target
    try:
        state = json.loads(read_text(state_path))
    except (OSError, ValueError) as exc:
        return findings + [Row("사슬 상태", str(state_path), False, f"읽기 실패: {exc}")]
    if not isinstance(state, dict):
        return findings + [Row("사슬 상태", str(state_path), False, "최상위 JSON 객체 필요")]
    for name, value in sorted(state.items()):
        if not isinstance(value, dict):
            findings.append(Row("사슬 상태", name, False, "상태 객체 아님"))
            continue
        if value.get("state") not in {"running", "done"}:
            continue
        target = mapping.get(name)
        findings.append(Row("사슬 상태", name, target is not None,
                            f"{value['state']} · {target}" if target else f"{value['state']} · EXP-MAP 이름 없음"))
    return findings


def git_schedule_time(repo: Path) -> datetime:
    result = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%cI", "--", SCHEDULE_REL.as_posix()],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    stamp = result.stdout.strip()
    if not stamp:
        raise ValueError("SCHEDULE-NOW의 갱신 커밋 없음")
    return datetime.fromisoformat(stamp)


def schedule_row(updated: datetime, now: datetime) -> Row:
    if updated.tzinfo is None or now.tzinfo is None:
        return Row("일정", "SCHEDULE-NOW", False, "시각에 UTC 오프셋 필요")
    age = now - updated
    if age < timedelta(0):
        return Row("일정", "SCHEDULE-NOW", False, f"미래 갱신 시각: {updated.isoformat()}")
    return Row("일정", "SCHEDULE-NOW", age <= timedelta(hours=24),
               f"마지막 파일 커밋 {updated.isoformat()} · {age.total_seconds() / 3600:.1f} h 전")


def audit(repo: Path, state_path: Path, now: datetime, updated: datetime | None = None) -> list[Row]:
    findings: list[Row] = []
    try:
        decision_text = read_text(repo / DECISION_REL)
        findings.extend(decision_rows(decision_text))
    except (OSError, ValueError) as exc:
        findings.append(Row("결정", DECISION_REL.name, False, str(exc)))
    try:
        map_text = read_text(repo / MAP_REL)
        cards, errors = experiment_cards(map_text)
        findings.extend(errors)
        for identifier, filename in cards.items():
            findings.append(card_row(identifier, repo / MAP_REL.parent / filename))
        findings.extend(chain_rows(map_text, cards, state_path))
    except (OSError, ValueError) as exc:
        findings.append(Row("실험 지도", MAP_REL.name, False, str(exc)))
    try:
        if not (repo / SCHEDULE_REL).is_file():
            raise FileNotFoundError(SCHEDULE_REL)
        findings.append(schedule_row(updated or git_schedule_time(repo), now))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        findings.append(Row("일정", SCHEDULE_REL.name, False, str(exc)))
    return findings


def render(rows: list[Row]) -> str:
    def safe(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ")

    lines = ["| 구역 | 항목 | 상태 | 내용 |", "|---|---|---|---|"]
    for row in rows:
        lines.append(f"| {safe(row.area)} | {safe(row.item)} | {'확인' if row.ok else '누락'} | {safe(row.detail)} |")
    failed = sum(not row.ok for row in rows)
    lines.append(f"\n확인 {len(rows) - failed} · 누락 {failed} · 종료 코드 {1 if failed else 0}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--chain-state", type=Path, default=DEFAULT_CHAIN)
    args = parser.parse_args(argv)
    rows = audit(args.repo_root.resolve(), args.chain_state, datetime.now().astimezone())
    print(render(rows))
    return int(any(not row.ok for row in rows))


if __name__ == "__main__":
    sys.exit(main())
