"""Insert a generated EX-35 terrain summary into EXP-MAP."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
DATA = Path(__file__).with_name("result_data.json")
MAP = ROOT / "inbox/jay/20261021-experiments/EXP-MAP.md"
MARKER = "- **EX-35 같은 기준 지형별 비교**:"


def render_line(data: dict) -> str:
    terrain = data["terrain_compare"]
    measured = [row for row in terrain["rows"] if row["measured"] and row["mode"] == "켬" and row["command"] == "fwd1.0"]
    gains = [row["child_median_m"] - row["parent_median_m"] for row in measured]
    assert len(terrain["rows"]) == 126 and sum(row["measured"] for row in terrain["rows"]) == 98
    assert len(measured) == 21 and all(gain > 0 for gain in gains)
    repeat = terrain["repeat"]
    return (
        f"{MARKER} [RESULT-EX35 v1.5](../20261026-experiments/RESULT-EX35-1027.md)의 "
        f"동일 코드·cuda:0·시드·칸 배정 표는 {len(terrain['rows'])}행 중 "
        f"{sum(row['measured'] for row in terrain['rows'])}행 측정이다. "
        f"지도 켬 fwd1.0 {len(measured)}칸의 m2000 거리 중앙값 차이는 "
        f"{min(gains):.2f}~{max(gains):.2f} m다. "
        f"L9 상자 가림 생존은 같은 m2000 저장본 재측정에서 "
        f"{repeat['earlier_alive']}/{repeat['n']}→{repeat['current_alive']}/{repeat['n']}이지만 "
        "두 재측정의 코드 해시가 달라 원인 분리는 미완료다. "
        "L6·L9 복원 지도는 env별 원자료가 없어 미측정이며, 한 번의 거리·생존 차이를 "
        "개선이나 퇴보로 확정하지 않는다. L0~2·L6·L9는 기존 고정 칸과 10/26 추가 칸이다."
    )


def sync(source: str, data: dict) -> str:
    heading = "## 10/27 최종 · EX-35 결과 기록\n"
    if source.count(heading) != 1:
        raise ValueError("EX-35 result section absent or duplicated")
    line = render_line(data)
    if MARKER in source:
        lines = source.splitlines(keepends=True)
        found = [index for index, item in enumerate(lines) if item.startswith(MARKER)]
        if len(found) != 1:
            raise ValueError("terrain summary duplicated")
        lines[found[0]] = line + "\n"
        source = "".join(lines)
    else:
        source = source.replace(heading, heading + "\n" + line + "\n", 1)
    return source.replace("RESULT-EX35 v1.4", "RESULT-EX35 v1.5")


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    old = MAP.read_text(encoding="utf-8")
    new = sync(old, data)
    if new != old:
        MAP.write_text(new, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
