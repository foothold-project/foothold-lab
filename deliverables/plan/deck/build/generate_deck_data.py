# -*- coding: utf-8 -*-
"""WBS xlsx를 표준 라이브러리만으로 읽어 덱용 스냅샷을 만든다."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
REQUIRED = ("관문", "WBS", "담당자", "완료율", "저장소")


def fail(message: str) -> "None":
    raise SystemExit("deck-data 생성 실패: " + message)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference)
    if not letters:
        fail(f"셀 주소를 읽을 수 없습니다: {reference}")
    value = 0
    for letter in letters.group(0):
        value = value * 26 + ord(letter) - 64
    return value - 1


def shared_strings(archive: zipfile.ZipFile) -> list[str]:
    name = "xl/sharedStrings.xml"
    if name not in archive.namelist():
        return []
    root = ET.fromstring(archive.read(name))
    return ["".join(node.text or "" for node in item.findall(".//m:t", NS))
            for item in root.findall("m:si", NS)]


def sheet_path(archive: zipfile.ZipFile, title: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall("r:Relationship", REL_NS)}
    for sheet in workbook.findall("m:sheets/m:sheet", NS):
        if sheet.attrib.get("name") == title:
            rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = targets.get(rel_id, "")
            if not target:
                fail(f"'{title}' 시트의 XML 경로를 찾을 수 없습니다")
            return target.lstrip("/") if target.startswith("/xl/") else "xl/" + target.lstrip("/")
    fail(f"'{title}' 시트가 없습니다")


def read_rows(xlsx: Path) -> list[list[str]]:
    if not xlsx.exists() or xlsx.stat().st_size == 0:
        fail(f"xlsx가 없거나 비었습니다: {xlsx}")
    try:
        with zipfile.ZipFile(xlsx) as archive:
            strings = shared_strings(archive)
            root = ET.fromstring(archive.read(sheet_path(archive, "WBS")))
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        fail(f"xlsx 구조를 읽을 수 없습니다: {exc}")

    rows: list[list[str]] = []
    for row in root.findall(".//m:sheetData/m:row", NS):
        sheet_row = int(row.attrib.get("r", len(rows) + 1))
        while len(rows) < sheet_row - 1:
            rows.append([])
        values: dict[int, str] = {}
        for cell in row.findall("m:c", NS):
            ref = cell.attrib.get("r", "")
            kind = cell.attrib.get("t")
            value = cell.find("m:v", NS)
            inline = cell.find("m:is", NS)
            text = ""
            if kind == "inlineStr" and inline is not None:
                text = "".join(n.text or "" for n in inline.findall(".//m:t", NS))
            elif value is not None and value.text is not None:
                text = strings[int(value.text)] if kind == "s" else value.text
            values[column_index(ref)] = text.strip()
        width = max(values) + 1 if values else 0
        rows.append([values.get(i, "") for i in range(width)])
    if not rows or not any(rows):
        fail("WBS 시트에 셀이 하나도 없습니다")
    return rows


def load_gates(repo_root: Path):
    source = repo_root / "tools" / "build_wbs.py"
    spec = importlib.util.spec_from_file_location("build_wbs_for_deck", source)
    if spec is None or spec.loader is None:
        fail(f"GATES 원본을 불러올 수 없습니다: {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    gates = getattr(module, "GATES", None)
    if not gates or len(gates) != 5:
        fail("tools/build_wbs.py의 GATES가 없거나 다섯 개가 아닙니다")
    return gates


def parse_percent(value: str) -> float | None:
    cleaned = value.strip().replace("%", "")
    if cleaned == "":
        return None
    try:
        number = float(cleaned)
    except ValueError:
        fail(f"완료율을 숫자로 읽을 수 없습니다: {value}")
    if "%" not in value and 0 <= number <= 1:
        number *= 100
    if not 0 <= number <= 100:
        fail(f"완료율이 0~100 범위를 벗어났습니다: {value}")
    return number


def build_snapshot(xlsx: Path, repo_root: Path) -> dict:
    rows = read_rows(xlsx)
    header_at = next((i for i, row in enumerate(rows) if all(name in row for name in REQUIRED)), None)
    if header_at is None:
        fail("필수 열이 없습니다. 필요한 열: " + ", ".join(REQUIRED))
    header = rows[header_at]
    indexes = {name: header.index(name) for name in REQUIRED}
    implementation_column = header.index("구현 단계") if "구현 단계" in header else None

    items = []
    for row_number, row in enumerate(rows[header_at + 1 :], start=header_at + 2):
        def get(name: str) -> str:
            index = indexes[name]
            return row[index].strip() if index < len(row) else ""

        if not any(get(name) for name in REQUIRED):
            continue
        item = {
            "gate": get("관문"),
            "wbs": get("WBS"),
            "owner": get("담당자"),
            "completion": parse_percent(get("완료율")),
            "repository": get("저장소"),
        }
        if implementation_column is not None:
            stage = row[implementation_column].strip() if implementation_column < len(row) else ""
            if not stage:
                fail(f"{row_number}행 구현 단계가 비었습니다")
            item["implementationStage"] = stage
        items.append(item)
    if not items:
        fail("헤더 아래에 WBS 이슈 행이 없습니다")

    gates = []
    for name, due, deliverable in load_gates(repo_root):
        members = [item for item in items if item["gate"] == name]
        gates.append({
            "name": name,
            "date": due.isoformat(),
            "deliverable": deliverable,
            "issueCount": len(members),
            "completedCount": sum(1 for item in members if item["completion"] is not None and item["completion"] >= 100),
        })

    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).replace(microsecond=0).isoformat()
    payload = {
        "meta": {
            "generatedAt": now,
            "source": xlsx.relative_to(repo_root).as_posix(),
            "sourceSha256": sha256(xlsx),
            "sheet": "WBS",
            "headerRow": header_at + 1,
        },
        "implementationStages": {
            "active": implementation_column is not None,
            "reason": "구현 단계 열이 없어 단계 막대를 비활성화했습니다" if implementation_column is None else "구현 단계 열을 읽었습니다",
        },
        "summary": {
            "issueCount": len(items),
            "completedCount": sum(1 for item in items if item["completion"] is not None and item["completion"] >= 100),
            "gates": gates,
        },
        "items": items,
    }
    digest_source = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["meta"]["contentSha256"] = hashlib.sha256(digest_source).hexdigest()
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", default="deliverables/plan/wbs.xlsx")
    parser.add_argument("--output", default="deliverables/plan/deck/content/deck-data.json")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[4]
    xlsx = (repo_root / args.xlsx).resolve()
    output = (repo_root / args.output).resolve()
    snapshot = build_snapshot(xlsx, repo_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    meta = snapshot["meta"]
    summary = snapshot["summary"]
    print(f"deck-data 생성: {output.relative_to(repo_root)}")
    print(f"이슈 {summary['issueCount']}개 · 완료 {summary['completedCount']}개")
    print(f"생성일 {meta['generatedAt']} · 원본 SHA-256 {meta['sourceSha256']}")
    print(snapshot["implementationStages"]["reason"])


if __name__ == "__main__":
    main()
