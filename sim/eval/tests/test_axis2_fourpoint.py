# -*- coding: utf-8 -*-
"""`axis2_fourpoint.score` 를 «알려진 답» 으로 시험한다.

분류: 실험
작성: Claude 세션 (오흥재 지시) · 2026-09-21
근거: 20260918-command-baseline 의 D · H · foothold-v1 실측 (판정문에 이미 적힌 수)
요지: 문턱을 다시 안 적는 대신, 이미 보고한 성적이 그대로 나오는지 본다
상태: 확정
판: v1.0
"""

from __future__ import annotations

import io
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import axis2_fourpoint as tool
from verdict_manifest import AXIS2_THRESHOLDS, YAW_RATIO_MIN

BASELINE = os.path.join(
    os.path.dirname(os.path.dirname(HERE)), "eval", "results",
    "20260918-command-baseline")


def load(policy):
    path = os.path.join(BASELINE, policy, "probe_manifest.json")
    if not os.path.exists(path):
        return None
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle).get("summary", {})


class KnownAnswerTests(unittest.TestCase):
    """**이미 보고한 성적**이 그대로 나와야 한다."""

    def check(self, policy, wanted):
        summary = load(policy)
        if summary is None:
            self.skipTest("%s 결과가 없다" % policy)
        passes = sum(1 for cell in tool.score(summary) if cell[2])
        self.assertEqual(passes, wanted, policy)

    def test_d_is_eight(self):
        self.check("D", 8)

    def test_h_is_six(self):
        self.check("H", 6)

    def test_e_is_five(self):
        self.check("E", 5)

    def test_f_is_three(self):
        self.check("F", 3)

    def test_v1_is_zero(self):
        self.check("foothold-v1", 0)

    def test_lim_rails10_3000_is_two(self):
        self.check("lim-rails10-3000", 2)


class ShapeTests(unittest.TestCase):

    def test_nine_cells(self):
        self.assertEqual(len(tool.score({})), 9)

    def test_missing_values_are_not_passes(self):
        """값이 없으면 «통과» 가 아니라 `None` 이다. 빈 칸을 통과로 세면 안 된다."""
        for _, value, ok in tool.score({}):
            self.assertIsNone(value)
            self.assertIsNone(ok)

    def test_thresholds_come_from_the_manifest_module(self):
        """문턱을 여기서 다시 적지 않는다. 갈라지면 안 된다."""
        self.assertEqual(AXIS2_THRESHOLDS[("turn", "fell_ratio")], ("<=", 0.10))
        self.assertEqual(AXIS2_THRESHOLDS[("hold", "residual_speed_mps")],
                         ("<=", 0.005))
        self.assertEqual(YAW_RATIO_MIN, 0.40)

    def test_boundary_is_inclusive(self):
        """문턱 «과 같을 때» 는 통과다. D 의 `wz +0.50` 이 정확히 0.40 이었다."""
        summary = {"turn": {"fell_ratio": 0.10,
                            "yaw_follow_ratio": {"+0.50": 0.40}}}
        cells = dict((name, ok) for name, _, ok in tool.score(summary))
        self.assertTrue(cells["회전 낙상"])
        self.assertTrue(cells["wz +0.50"])

    def test_just_over_the_line_fails(self):
        summary = {"turn": {"fell_ratio": 0.1001,
                            "yaw_follow_ratio": {"+0.50": 0.3999}}}
        cells = dict((name, ok) for name, _, ok in tool.score(summary))
        self.assertFalse(cells["회전 낙상"])
        self.assertFalse(cells["wz +0.50"])

    def test_negative_yaw_ratio_is_a_failure_not_an_absolute_value(self):
        """**부호를 포함해서** 본다. -0.9 를 0.9 로 읽으면 안 된다."""
        summary = {"turn": {"yaw_follow_ratio": {"-1.00": -0.9}}}
        cells = dict((name, ok) for name, _, ok in tool.score(summary))
        self.assertFalse(cells["wz -1.00"])


class RowAuditTests(unittest.TestCase):
    """**손으로 적은 행 목록을 믿지 않는다.**"""

    def test_current_list_is_clean(self):
        wrong_size, missing = tool.audit_rows()
        self.assertEqual(wrong_size, [], "env 64 가 아닌 판이 섞였다")
        self.assertEqual(missing, [], "빠뜨린 env 64 판이 있다")

    def test_a_video_run_would_be_caught(self):
        """`*-videos/axis2/` 는 `num_envs 1` 이라 성적이 아니다."""
        extra = os.path.join("sim", "eval", "results",
                             "20260918-D-videos", "axis2", "D")
        if not os.path.exists(os.path.join(extra, "probe_manifest.json")):
            self.skipTest("촬영본이 없다")
        saved = tool.MATRIX_ROWS
        try:
            tool.MATRIX_ROWS = saved + (("촬영본", extra),)
            wrong_size, _ = tool.audit_rows()
            self.assertEqual([n for n, _ in wrong_size], ["촬영본"])
        finally:
            tool.MATRIX_ROWS = saved

    def test_a_dropped_row_would_be_caught(self):
        saved = tool.MATRIX_ROWS
        try:
            tool.MATRIX_ROWS = tuple(r for r in saved if r[0] != "D")
            _, missing = tool.audit_rows()
            self.assertTrue(any(m.endswith("D") for m in missing), missing)
        finally:
            tool.MATRIX_ROWS = saved


if __name__ == "__main__":
    unittest.main()
