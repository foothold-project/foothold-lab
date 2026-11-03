"""Read C-layer attempt receipts and report wall-time phases without GPU claims."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def measure(root: Path, limit: int = 10) -> list[dict]:
    starts = sorted(root.glob("attempts/*/[0-9]*/started.json"),
                    key=lambda path: path.stat().st_ctime, reverse=True)
    rows = []
    for started in starts:
        attempt = started.parent
        child = attempt / "child.log"
        composed = attempt / "compose.log"
        styled = attempt / "styled.json"
        closed = attempt / "closed.json"
        if not all(path.is_file() for path in (child, composed, styled, closed)):
            continue
        progress = [json.loads(line.split("C76_PROGRESS ", 1)[1])
                    for line in child.read_text(encoding="utf-8", errors="replace").splitlines()
                    if "C76_PROGRESS " in line]
        if not progress or progress[-1]["frame"] != 450:
            continue
        start_s = started.stat().st_ctime
        end_s = closed.stat().st_mtime
        child_s = child.stat().st_mtime - child.stat().st_ctime
        capture_s = progress[-1]["elapsed_s"]
        compose_s = styled.stat().st_mtime - composed.stat().st_ctime
        total_s = end_s - start_s
        if min(total_s, child_s, capture_s, compose_s) < 0 or capture_s > child_s + 2:
            raise ValueError(f"invalid timing receipt: {attempt}")
        rows.append({"cell": attempt.parent.name, "ordinal": attempt.name,
                     "start_epoch_s": round(start_s, 3),
                     "total_s": round(total_s, 3),
                     "kit_child_s": round(child_s, 3),
                     "capture_loop_s": round(capture_s, 3),
                     "kit_outside_capture_s": round(max(0, child_s - capture_s), 3),
                     "compose_s": round(compose_s, 3),
                     "audit_other_s": round(max(0, total_s - child_s - compose_s), 3),
                     "capture_wall_fraction": round(capture_s / total_s, 5),
                     "kit_child_wall_fraction": round(child_s / total_s, 5),
                     "result": json.loads(closed.read_text(encoding="utf-8"))["result"],
                     "source": str(attempt)})
        if len(rows) == limit:
            break
    if len(rows) != limit:
        raise ValueError(f"only {len(rows)} complete 450-frame attempts, need {limit}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--csv", required=True, type=Path)
    args = parser.parse_args()
    rows = measure(args.out)
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({key: round(sum(row[key] for row in rows) / len(rows), 3)
                      for key in ("total_s", "kit_child_s", "capture_loop_s",
                                  "kit_outside_capture_s", "compose_s", "audit_other_s",
                                  "capture_wall_fraction", "kit_child_wall_fraction")}, indent=2))


if __name__ == "__main__":
    main()
