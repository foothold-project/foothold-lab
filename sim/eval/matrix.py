"""종합보고서 한 판에 **반드시 있어야 하는 칸**을 선언한다.

분류: 운영
작성: 오흥재 · 2026-09-11 23:20
근거: 팀장 지적 「기존 험지 6종 수치가 빠진 걸 손으로 찾았다. 시스템화해야 한다」
요지: 무엇이 있어야 하는지를 코드가 선언하고, 없으면 보고서가 안 만들어진다
상태: 확정

## 왜 이 파일이 있나

2026-09-11 에 본 데이터를 `--terrain_set unseen10` 으로만 돌렸다. 그래서
**기존 험지 6종 수치가 통째로 없었다.** 오류는 없었고, 보고서를 그대로
만들었으면 「기존 험지는 안 무너졌다」를 근거 없이 주장할 뻔했다.

사람이 매번 「빠진 게 없나」를 눈으로 세는 것은 시스템이 아니다. 그래서
**있어야 할 칸을 여기 선언**하고, 돌리는 쪽과 보고서 쪽이 같은 선언을 본다.

| 누가 | 이 파일을 어떻게 쓰나 |
|---|---|
| `run_matrix.py` | 여기 적힌 칸을 전부 돌린다 |
| 보고서 생성기 | 여기 적힌 칸이 **다 있는지 세고**, 없으면 거부한다 |

## 무엇이 한 판인가

```
성적표   지형 집합 2개(rough6 · unseen10) x 모델 전부 x 속도 3 x 난이도 0.5
곡선     지형 집합 2개              x 최신 모델 x 속도 3 x 난이도 6단
```

성적표는 모델을 나란히 놓는 자리라 **전 모델**이 필요하고, 곡선은 한계
난이도를 그리는 자리라 최신 모델만 있으면 된다.

torch 도 isaaclab 도 안 쓴다. `tests/test_matrix.py` 가 알려진 답으로 못 박는다.
"""

from __future__ import annotations

import csv
import io
import os
import sys

# 성적표가 서는 난이도. 모델을 나란히 놓고 비교하는 자리다.
SCORECARD_DIFFICULTY = 0.5

# 곡선이 훑는 난이도. 한계 난이도(성공률이 50 % 아래로 떨어지는 자리)를 찾는다.
CURVE_DIFFICULTIES = (0.1, 0.2, 0.3, 0.4, 0.6, 0.7)

SPEEDS = (0.5, 1.0, 1.5)

TERRAIN_SETS = ("rough6", "unseen10")

# 한 칸이 몇 판인가. 지형 하나당이다.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrains  # noqa: E402

EPISODES_PER_TERRAIN = 100


class Cell(object):
    """행렬의 칸 하나. 실행 하나에 대응한다."""

    __slots__ = ("model", "terrain_set", "speed", "difficulty", "role")

    def __init__(self, model, terrain_set, speed, difficulty, role):
        self.model = model
        self.terrain_set = terrain_set
        self.speed = speed
        self.difficulty = difficulty
        self.role = role          # "성적표" 또는 "곡선"

    @property
    def rel_path(self):
        """결과가 놓이는 자리. `<모델>/<집합>/d<난이도>/v<속도>`."""
        return os.path.join(
            self.model, self.terrain_set,
            "d%g" % self.difficulty, "v%g" % self.speed)

    def __repr__(self):
        return "Cell(%s)" % self.rel_path

    def __eq__(self, other):
        return isinstance(other, Cell) and self.rel_path == other.rel_path

    def __hash__(self):
        return hash(self.rel_path)


def required_cells(models, newest=None, speeds=SPEEDS, terrain_sets=TERRAIN_SETS):
    """한 판에 있어야 하는 칸 전부.

    Args:
        models: 모델 이름 목록. 순서가 보고서 표의 열 순서가 된다.
        newest: 곡선을 그릴 모델. 안 주면 `models` 의 마지막.
        speeds: 속도 목록.
        terrain_sets: 지형 집합 목록.

    Returns:
        `Cell` 목록. 중복 없음.
    """
    if not models:
        raise ValueError("모델이 하나도 없습니다.")

    newest = newest or models[-1]

    if newest not in models:
        raise ValueError("곡선 모델 %r 이 모델 목록에 없습니다: %r" % (newest, models))

    cells = []

    # 성적표 · 모델 전부
    for model in models:
        for terrain_set in terrain_sets:
            for speed in speeds:
                cells.append(Cell(model, terrain_set, speed,
                                  SCORECARD_DIFFICULTY, "성적표"))

    # 곡선 · 최신 모델만
    for terrain_set in terrain_sets:
        for speed in speeds:
            for difficulty in CURVE_DIFFICULTIES:
                cells.append(Cell(newest, terrain_set, speed, difficulty, "곡선"))

    return cells


def why_absent(root, cell):
    """그 칸이 왜 「없는」가. 채워져 있으면 `None`.

    **크기로 세지 않는다.** 자료 행을 다 지우고 머리글만 남겨도 1,082 바이트라
    「있다」로 세어졌다 `확인됨` (2026-09-12 검증 3회차 6번 · 그 상태로 보고서가
    「선언한 54칸이 모두 찼습니다」를 찍었다).

    실제로 여는 것은 셋이다.

        1. 파일이 있나
        2. 선언한 지형이 다 있나
        3. 지형마다 판이 `EPISODES_PER_TERRAIN` 만큼 있고 겹치지 않나
    """
    path = os.path.join(root, cell.rel_path, "generalization_raw.csv")

    if not os.path.isfile(path):
        return "파일이 없다"

    names = terrains.TERRAIN_SETS[cell.terrain_set][0]

    try:
        with io.open(path, encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, UnicodeDecodeError) as err:
        return "못 읽는다: %s" % err

    if not rows:
        return "자료 행이 없다"

    if "terrain" not in rows[0]:
        return "terrain 열이 없다"

    seen = {}

    for row in rows:
        seen.setdefault(row["terrain"], []).append(
            (row.get("env_id"), row.get("episode")))

    absent = [n for n in names if n not in seen]

    if absent:
        return "지형 %d종이 없다: %s" % (len(absent), ", ".join(absent[:4]))

    # **양쪽을 다 센다.** 없는 것만 보면 선언 밖 지형이 섞여도 완성이 된다
    # `확인됨` (2026-09-12 검증 4회차 5번 · 지형 이름만 `intruder` 로 바꾼 행을
    # 하나 덧붙였더니 「43,201판 · 빠짐 0칸」으로 통과했다).
    extra = [n for n in sorted(seen) if n not in names]

    if extra:
        return "선언에 없는 지형이 섞였다: %s" % ", ".join(extra[:4])

    for name in names:
        got = seen[name]

        if len(got) != EPISODES_PER_TERRAIN:
            return "%s 가 %d판이다 (%d판이어야 한다)" % (name, len(got),
                                                  EPISODES_PER_TERRAIN)

        if len(set(got)) != len(got):
            return "%s 에 같은 판이 두 번 있다" % name

    return None


def missing(root, cells):
    """`root` 아래에서 **아직 없는** 칸.

    **폴더가 있는 것으로는 안 친다.** 실패한 실행도 폴더는 남긴다.
    """
    return [cell for cell in cells if why_absent(root, cell) is not None]


def describe(cells):
    """사람이 읽는 한 줄 요약."""
    by_role = {}

    for cell in cells:
        by_role.setdefault(cell.role, []).append(cell)

    parts = ["%s %d칸" % (role, len(group)) for role, group in sorted(by_role.items())]

    return " · ".join(parts) + " · 합 %d칸" % len(cells)
