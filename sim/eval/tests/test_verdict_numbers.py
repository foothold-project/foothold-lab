# -*- coding: utf-8 -*-
"""판정문에 «손으로 적은» 수를 원자료에서 다시 세어 대조한다.

분류: 실험
작성: Claude 세션 (오흥재 지시) · 2026-09-21
근거: 축 2 표의 행 목록을 손으로 적고 안 셌던 일 (2026-09-21)
요지: 문장이 아니라 «자료» 쪽에서 잡는다. 린트는 70 % 로 우는데 이것은 오검출이 0 이다
상태: 확정
판: v1.0

## 왜 이 형태인가

최상급·개수에 범위를 안 밝히는 사고를 **자연어 린트로 잡으려다 오검출
70 % 가 나와 접었다** (`inbox/jay/20260921-superlative-scope.md`).

**그런데 판정문의 수는 대부분 «원자료에서 다시 셀 수 있다».** 세어서
문서에 그 수가 있는지 보면 오검출이 없다.

**못 세는 것은 여기 안 넣는다** · 논문 목록처럼 저장소 바깥 것은
「손으로 적었다」고 문서에 표시하는 것이 답이다 (그 판단은 사람이 한다).
"""

from __future__ import annotations

import io
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(EVAL))
sys.path.insert(0, EVAL)

import axis2_fourpoint as axis2
import fourpoint_table as axis1

RESULTS = os.path.join(EVAL, "results")
BASELINE_JSON = os.path.join(ROOT, "models", "foothold-v1.json")


def read_doc(name):
    """**없으면 실패시킨다.**

    처음에는 `skip` 했는데, 그러면 **문서가 사라졌을 때 시험이 조용히
    안 돌고 묶음이 OK 로 끝난다.** 검증에서 그 구멍이 잡혔다 (문서 셋을
    없는 것으로 두니 11 개가 안 돌고 성공으로 끝났다).
    판정문은 커밋돼 있으므로 «없는 것» 자체가 사고다.
    """
    path = os.path.join(RESULTS, name, "README.md")
    if not os.path.exists(path):
        raise AssertionError("판정문이 없다: " + path)
    with io.open(path, encoding="utf-8") as handle:
        return handle.read()


def axis1_cells(folder):
    """`{(속도, 지형집합, 지형): (퍼센트, 판수)}` · 축 1 한 정책."""
    out = {}
    for label, vdir in axis1.SPEEDS:
        for terrain_set in axis1.TERRAIN_SETS:
            path = os.path.join(RESULTS, folder, terrain_set, "d0.5", vdir,
                                "generalization_summary.csv")
            out.update({(label, terrain_set, terrain): value
                        for terrain, value in axis1.read_run(path).items()})
    return out


def baseline():
    return axis1.load_baseline(BASELINE_JSON)


CELL_COUNT = 48


def tally(folder):
    """v1 대비 `(하락, 상승, 겹침)`.

    **빠진 칸을 조용히 넘기지 않는다.** 예전 판은 `continue` 로 넘겼는데,
    그러면 **자료가 통째로 없어도 `(0, 0, 0)` 이 나와** 「하락 0」 시험이
    거저 통과한다. 검증에서 그 구멍이 잡혔다.
    """
    base, got = baseline(), axis1_cells(folder)
    if len(base) != CELL_COUNT:
        raise AssertionError("기준선이 %d 칸이 아니다: %d" % (CELL_COUNT, len(base)))
    missing = sorted(set(base) - set(got))
    if missing:
        raise AssertionError(
            "%s 에 %d 칸이 없다 (예: %s)" % (folder, len(missing), missing[:2]))
    drops = rises = laps = 0
    for key, (bv, bn) in base.items():
        mark = axis1.verdict(bv, bn, *got[key])
        drops += mark == "하락"
        rises += mark == "상승"
        laps += mark == "겹침"
    return drops, rises, laps


class NvidiaAxis1Tests(unittest.TestCase):
    """`20260921-nvidia-axis1` 의 머릿수."""

    @classmethod
    def setUpClass(cls):
        cls.doc = read_doc("20260921-nvidia-axis1")
        cls.base = baseline()
        cls.got = axis1_cells("20260921-nvidia-axis1")
        # **없거나 덜 찬 것을 «건너뛰지» 않는다.**
        assert len(cls.got) == CELL_COUNT, len(cls.got)

    def test_drop_rise_overlap(self):
        drops, rises, laps = tally("20260921-nvidia-axis1")
        self.assertEqual((drops, rises, laps), (31, 0, 17))
        self.assertIn("진짜 하락 31 · 진짜 상승 0 · 겹침 17", self.doc)

    def test_zero_cells(self):
        zeros = sum(1 for k in self.base if self.got[k][0] == 0)
        base_zeros = sum(1 for k, (v, _) in self.base.items() if v == 0)
        self.assertEqual((zeros, base_zeros), (17, 3))
        self.assertIn("원본 17 칸   대   v1 3 칸", self.doc)

    def test_in_range_drops(self):
        """1.5 는 원본의 학습 범위 밖이다. 0.5 · 1.0 만 세도 16 이어야 한다."""
        drops = 0
        for key, (bv, bn) in self.base.items():
            if key[0] == "1.5 m/s":
                continue
            drops += axis1.verdict(bv, bn, *self.got[key]) == "하락"
        self.assertEqual(drops, 16)
        self.assertIn("32 칸 중 16 칸", self.doc)

    def test_terrains_at_or_below_one_percent_at_1_5(self):
        low = sum(1 for k in self.base
                  if k[0] == "1.5 m/s" and self.got[k][0] <= 1)
        self.assertEqual(low, 12)
        self.assertIn("12 지형이 0 ~ 1 %", self.doc)


class V2abAxis1Tests(unittest.TestCase):
    """`20260921-v2ab` 의 네 점 겹침 수."""

    @classmethod
    def setUpClass(cls):
        cls.doc = read_doc("20260921-v2ab")

    def overlap_count(self, policy):
        cells = axis1.load_policy(os.path.join(RESULTS, "20260921-v2ab"), policy)
        full = [v for v in cells.values() if len(v) == len(axis1.ITERS)]
        self.assertEqual(len(full), CELL_COUNT, "%s 가 덜 찼다" % policy)
        return sum(1 for v in full
                   if axis1.all_overlap([v[i] for i in axis1.ITERS]))

    def test_v2a_overlaps_44(self):
        """**정책과 수를 «붙여» 본다.** 둘을 맞바꿔도 통과하면 안 된다."""
        self.assertEqual(self.overlap_count("v2a"), 44)
        self.assertIn("### v2a · 48 칸 중 **44 칸**", self.doc)

    def test_v2b_overlaps_47(self):
        self.assertEqual(self.overlap_count("v2b"), 47)
        self.assertIn("### v2b · 48 칸 중 **47 칸**", self.doc)

    def test_drops_per_checkpoint(self):
        want = {"v2a": [2, 1, 2, 0], "v2b": [0, 0, 0, 0]}
        for policy, expected in want.items():
            got = []
            for iteration in axis1.ITERS:
                got.append(tally("20260921-v2ab/%s-iter%d" % (policy, iteration))[0])
            self.assertEqual(got, expected, policy)
        # 문서의 0 절 표가 같은 수를 말하는지.
        self.assertIn("| **1** | 축 1 에서 v1 대비 **진짜 하락 0** "
                      "| **3000 에서만 통과** | **네 점 전부 통과** |", self.doc)


class Axis2Tests(unittest.TestCase):
    """`20260921-v2ab-axis2` 의 아홉 칸 통과 수와 행 목록."""

    @classmethod
    def setUpClass(cls):
        cls.doc = read_doc("20260921-v2ab-axis2")

    def test_row_list_is_complete(self):
        """**행이 다 사라져도 통과하면 안 된다.** 그래서 수도 같이 본다."""
        # **빈 요약 `{}` 을 «자료 있음» 으로 치지 않는다.**
        loaded = [n for n, f in axis2.MATRIX_ROWS
                  if axis2.load_dir(os.path.join(ROOT, f))]
        self.assertEqual(len(loaded), len(axis2.MATRIX_ROWS),
                         "표의 판 중 자료가 없는 것이 있다")
        self.assertGreaterEqual(len(loaded), 18)
        wrong_size, missing = axis2.audit_rows(ROOT)
        self.assertEqual((wrong_size, missing), ([], []))
        # 표가 문서에도 18 행으로 들어 있는지.
        # **문서 아무 데나 걸리면 안 된다** · 9 절 표 «블록 안» 의 줄 머리로 찾는다.
        after = self.doc.split("정지낙상 유지낙상", 1)[1]
        block = after.split("```", 1)[0].splitlines()
        for name, _ in axis2.MATRIX_ROWS:
            shown = name.replace(" iter", " ")
            self.assertTrue(
                any(line.startswith(shown + " ") for line in block),
                "9 절 표에 %r 행이 없다" % shown)

    def test_pass_counts(self):
        root = os.path.join(RESULTS, "20260921-v2ab-axis2")
        want = {"v2a": [2, 5, 4, 6], "v2b": [7, 5, 6, 6]}
        for policy, expected in want.items():
            got = []
            for iteration in axis2.ITERS:
                summary = axis2.read_summary(root, policy, iteration)
                self.assertIsNotNone(
                    summary, "%s iter%d 결과가 없다" % (policy, iteration))
                cells = axis2.score(summary)
                # **값이 없는 칸을 «미달» 과 같이 세면 안 된다.**
                # 지표가 사라져도 통과 수는 안 변해서 시험이 거저 통과했다.
                blank = [n for n, v, _ in cells if v is None]
                self.assertEqual(blank, [], "%s iter%d 에 값 없는 칸: %s"
                                 % (policy, iteration, blank))
                got.append(sum(1 for c in cells if c[2]))
            self.assertEqual(got, expected, policy)
        self.assertIn("| **2** | **축 2 아홉 칸 «전부»** | **미달** "
                      "(2 · 5 · 4 · 6) | **미달** "
                      "(7 · 5 · 6 · 6 · 최고도 2 칸 남음) |", self.doc)

    def test_only_f_passes_wz_plus_one(self):
        """**손으로 적은 주장** · 원본 말고 `wz +1.00` 을 넘은 판은 F 뿐."""
        labels = [c[2] for c in axis2.CELLS] + ["wz " + k for k in axis2.YAW_KEYS]
        index = labels.index("wz +1.00")
        winners = []
        for name, folder in axis2.MATRIX_ROWS:
            summary = axis2.load_dir(os.path.join(ROOT, folder))
            if summary and axis2.score(summary)[index][2]:
                winners.append(name)
        self.assertEqual(winners, ["NVIDIA 원본", "F"])
        rows = [l for l in self.doc.splitlines()
                if l.startswith("| **`wz +1.00`**")]
        self.assertEqual(len(rows), 1, rows)
        self.assertIn("**F 뿐**", rows[0])

    def test_six_pass_wz_minus_half(self):
        labels = [c[2] for c in axis2.CELLS] + ["wz " + k for k in axis2.YAW_KEYS]
        index = labels.index("wz -0.50")
        winners = [n for n, f in axis2.MATRIX_ROWS
                   if (axis2.load_dir(os.path.join(ROOT, f)) or {})
                   and axis2.score(axis2.load_dir(os.path.join(ROOT, f)))[index][2]]
        self.assertEqual(len(winners), 7)          # 원본 포함
        others = [n for n in winners if n != "NVIDIA 원본"]
        self.assertEqual(len(others), 6)
        # **「여섯」 만 찾으면 「검증에서 여섯 곳을 고쳤다」에도 걸린다.**
        # 9-1 절의 «그 줄» 을 집어 이름까지 맞춘다.
        # 이 문서에는 `wz -0.50` 로 시작하는 줄이 둘이다 (3 절 문턱표와
        # 9-1 절 목록). **9-1 쪽만 집는다.**
        rows = [l for l in self.doc.splitlines()
                if l.startswith("| `wz -0.50` |") and "여섯" in l]
        self.assertEqual(len(rows), 1, rows)
        row = rows[0]
        # 표는 「v2a 2000」 처럼 적고 목록은 「v2a iter2000」 이라 맞춰 준다.
        for name in others:
            shown = name.replace("석헌 ", "").replace(" iter", " ")
            self.assertIn(shown, row, (shown, row))


class SteppingStonesTests(unittest.TestCase):
    """열 판이 0 이라는 주장. **셋은 0 이 아니었다.**"""

    def test_nonzero_points_are_exactly_three(self):
        nonzero, zeros = [], 0
        for policy in ("v2a", "v2b"):
            cells = axis1.load_policy(
                os.path.join(RESULTS, "20260921-v2ab"), policy)
            self.assertTrue(cells, "%s 결과가 없다" % policy)
            for key, points in cells.items():
                if key[2] != "stepping_stones":
                    continue
                for iteration, (value, _) in points.items():
                    if value != 0:
                        nonzero.append((policy, iteration, key[0], value))
                    else:
                        zeros += 1
        self.assertEqual(
            sorted(nonzero),
            sorted([("v2a", 2500, "0.5 m/s", 1.0),
                    ("v2a", 2500, "1.0 m/s", 4.0),
                    ("v2a", 3000, "1.0 m/s", 1.0)]), nonzero)
        # 0 인 점도 세어 둔다. 셋만 보고 나머지를 안 보면 안 된다.
        self.assertEqual(zeros, 21, zeros)
        # **판정문이 「전부 0」으로 되돌아가지 않았는지** 본다.
        doc = read_doc("20260921-nvidia-axis1")
        self.assertIn("「아무도」라고도 안 쓴다", doc)
        self.assertNotIn("열 판 전부 0 이다", doc)
        # **문서가 말하는 값이 원자료와 같은지.**
        shown = " · ".join("%g" % v for _, _, _, v in sorted(nonzero))
        self.assertEqual(shown, "1 · 4 · 1")
        self.assertIn("1 · 4 · 1 % 가 나왔다", doc)
        # 3 절 표의 «0 인 점» 수와 «어느 체크포인트» 인지도 대조한다.
        counts = {"v2a": 0, "v2b": 0}
        for policy in counts:
            cells = axis1.load_policy(
                os.path.join(RESULTS, "20260921-v2ab"), policy)
            for key, points in cells.items():
                if key[2] != "stepping_stones":
                    continue
                counts[policy] += sum(1 for v, _ in points.values() if v == 0)
        self.assertEqual(counts, {"v2a": 9, "v2b": 12}, counts)
        self.assertIn("v2a 네 점 x 3 중 %d · v2b 네 점 x 3 중 %d"
                      % (counts["v2a"], counts["v2b"]), doc)
        self.assertIn("v2a 2500 의 0.5 m/s 1 % · 1.0 m/s 4 % "
                      "· v2a 3000 의 1.0 m/s 1 %", doc)


if __name__ == "__main__":
    unittest.main()
