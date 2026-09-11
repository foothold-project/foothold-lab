"""행렬 선언을 못 박는다. `sim/eval/matrix.py`.

    python -m pytest sim/eval/tests/test_matrix.py

## 여기서 지키는 것

| 시험 | 막는 사고 |
|---|---|
| 지형 집합 둘이 다 든다 | `unseen10` 만 돌려 기존 험지 수치가 통째로 비는 것 |
| 모델 전부가 성적표에 든다 | 비교 대상 하나가 조용히 빠지는 것 |
| 빠진 칸을 센다 | 결과가 모자란 채로 보고서가 만들어지는 것 |
| 빈 파일은 «있는 것»이 아니다 | 실패한 실행의 껍데기를 성공으로 세는 것 |
"""

import io
import os
import shutil
import sys
import tempfile
import unittest

# 요구 규격. **여기 손으로 적는다.** `matrix` 에서 가져오지 않는다.
EPISODES = 100
SETS = {
    "rough6": ("pyramid_stairs", "pyramid_stairs_inv", "boxes", "random_rough",
               "hf_pyramid_slope", "hf_pyramid_slope_inv"),
    "unseen10": ("gap", "pit", "rails", "floating_ring", "stepping_stones",
                 "discrete_obstacles", "star", "wave", "repeated_boxes",
                 "repeated_cylinders"),
}

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.dirname(HERE)

if EVAL_DIR not in sys.path:
    sys.path.insert(0, EVAL_DIR)

import matrix  # noqa: E402

MODELS = ("baseline", "A", "foothold-v1")


class RequiredTest(unittest.TestCase):
    def setUp(self):
        self.cells = matrix.required_cells(MODELS)

    def test_지형_집합_둘이_다_든다(self):
        """**이것이 이 파일이 있는 이유다.**

        2026-09-11 에 `unseen10` 만 돌려 기존 험지 6종이 통째로 비었다.
        """
        sets = {c.terrain_set for c in self.cells}

        self.assertEqual(sets, {"rough6", "unseen10"})

    def test_성적표에_모델이_전부_든다(self):
        score = [c for c in self.cells if c.role == "성적표"]

        self.assertEqual({c.model for c in score}, set(MODELS))

        # 모델 3 x 집합 2 x 속도 3
        self.assertEqual(len(score), 3 * 2 * 3)

    def test_곡선은_최신_모델만(self):
        curve = [c for c in self.cells if c.role == "곡선"]

        self.assertEqual({c.model for c in curve}, {"foothold-v1"})

        # 집합 2 x 속도 3 x 난이도 6
        self.assertEqual(len(curve), 2 * 3 * 6)

    def test_합이_54칸(self):
        self.assertEqual(len(self.cells), 18 + 36)

    def test_같은_칸이_두_번_안_든다(self):
        paths = [c.rel_path for c in self.cells]

        self.assertEqual(len(paths), len(set(paths)))

    def test_곡선_모델을_직접_고를_수_있다(self):
        cells = matrix.required_cells(MODELS, newest="A")
        curve = [c for c in cells if c.role == "곡선"]

        self.assertEqual({c.model for c in curve}, {"A"})

    def test_모델_목록에_없는_곡선_모델은_거부한다(self):
        with self.assertRaises(ValueError):
            matrix.required_cells(MODELS, newest="foothold-v9")

    def test_모델이_없으면_거부한다(self):
        with self.assertRaises(ValueError):
            matrix.required_cells([])

    def test_자리_이름(self):
        cell = matrix.Cell("foothold-v1", "unseen10", 1.0, 0.5, "성적표")

        self.assertEqual(cell.rel_path.replace(chr(92), "/"),
                         "foothold-v1/unseen10/d0.5/v1")


class MissingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="foothold-matrix-")
        self.cells = matrix.required_cells(MODELS)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fill(self, cell, whole=True):
        """**진짜 CSV 를 쓴다.**

        예전에는 `"x" * 400` 을 썼다. 관문이 크기만 보던 때는 그것으로 됐지만,
        지금은 지형 구성과 판 수를 센다 `확인됨` (2026-09-12 검증 3회차 6번 ·
        머리글만 남긴 1,082 바이트 파일이 「있다」로 세어졌다).
        """
        path = os.path.join(self.tmp, cell.rel_path)
        os.makedirs(path, exist_ok=True)
        # **검증 대상의 상수와 목록을 안 읽는다.** 읽으면 그것이 틀려도 시험이
        # 통과한다 `확인됨` (2026-09-12 검증 5회차 4번).
        names = SETS[cell.terrain_set]
        rows = ["terrain,env_id,episode,overall_success"]

        if whole:
            for name in names:
                for i in range(EPISODES):
                    rows.append("%s,%d,%d,1" % (name, i // 10, i))

        with io.open(os.path.join(path, "generalization_raw.csv"),
                     "w", encoding="utf-8") as handle:
            handle.write(chr(10).join(rows) + chr(10))

    def test_아무것도_없으면_전부_빠짐(self):
        self.assertEqual(len(matrix.missing(self.tmp, self.cells)), len(self.cells))

    def test_채운_만큼_줄어든다(self):
        for cell in self.cells[:5]:
            self.fill(cell)

        self.assertEqual(len(matrix.missing(self.tmp, self.cells)),
                         len(self.cells) - 5)

    def test_다_채우면_없다(self):
        for cell in self.cells:
            self.fill(cell)

        self.assertEqual(matrix.missing(self.tmp, self.cells), [])

    def test_머리글만_있는_것은_있는_것이_아니다(self):
        """**실패한 실행도 폴더와 머리글은 남긴다.**

        크기로 세면 1,082 바이트라 「있다」가 된다 `확인됨`
        (2026-09-12 검증 3회차 6번).
        """
        for cell in self.cells:
            self.fill(cell, whole=False)

        self.assertEqual(len(matrix.missing(self.tmp, self.cells)), len(self.cells))

    def test_판이_모자라면_있는_것이_아니다(self):
        for cell in self.cells:
            self.fill(cell)

        cell = self.cells[0]
        path = os.path.join(self.tmp, cell.rel_path, "generalization_raw.csv")
        lines = io.open(path, encoding="utf-8").read().splitlines(True)
        io.open(path, "w", encoding="utf-8").write("".join(lines[:-1]))

        self.assertEqual(len(matrix.missing(self.tmp, self.cells)), 1)

    def test_폴더만_있는_것도_아니다(self):
        for cell in self.cells:
            os.makedirs(os.path.join(self.tmp, cell.rel_path), exist_ok=True)

        self.assertEqual(len(matrix.missing(self.tmp, self.cells)), len(self.cells))


class DescribeTest(unittest.TestCase):
    def test_한_줄_요약(self):
        text = matrix.describe(matrix.required_cells(MODELS))

        self.assertIn("성적표 18칸", text)
        self.assertIn("곡선 36칸", text)
        self.assertIn("합 54칸", text)


if __name__ == "__main__":
    unittest.main()
