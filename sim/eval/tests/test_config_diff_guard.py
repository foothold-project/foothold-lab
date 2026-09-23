# -*- coding: utf-8 -*-
"""`config_diff_guard` 가 «실제로 막는지» 확인한다.

분류: 실험
작성: Claude 세션 (오흥재 지시) · 2026-09-21
근거: v2a 대 v2b 실측 (685 칸 중 셋이 다름)
요지: 알려진 답 하나(진짜 사고)와, 관문이 놓칠 법한 모양들을 같이 본다
상태: 확정
판: v1.0
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config_diff_guard as guard


class FlattenTests(unittest.TestCase):

    def test_nested_dicts_become_dotted_paths(self):
        self.assertEqual(
            guard.flatten({"sim": {"device": "cuda:0", "dt": 0.005}}),
            {"sim.device": "'cuda:0'", "sim.dt": "0.005"})

    def test_lists_are_one_value(self):
        """목록은 통째로 한 칸이다. 길이가 달라도 한 줄로 잡힌다."""
        a = guard.flatten({"r": {"lin_vel_x": (0.4, 1.5)}})
        b = guard.flatten({"r": {"lin_vel_x": [0.4, 1.5, 9.9]}})
        self.assertEqual(list(a), ["r.lin_vel_x"])
        _, unexpected, _ = guard.compare(a, b)
        self.assertEqual(len(unexpected), 1)

    def test_tuple_and_list_with_same_contents_are_equal(self):
        """yaml 이 tuple 로 읽든 list 로 읽든 같은 값이면 안 걸려야 한다."""
        a = guard.flatten({"r": (0.4, 1.5)})
        b = guard.flatten({"r": [0.4, 1.5]})
        self.assertEqual(a, b)

    def test_number_and_string_are_not_conflated(self):
        """0.1 과 '0.1' 은 다른 값이다. repr 로 두는 까닭이다."""
        a = guard.flatten({"x": 0.1})
        b = guard.flatten({"x": "0.1"})
        self.assertNotEqual(a, b)

    def test_float_written_two_ways_is_equal(self):
        """0.10 과 0.1 은 같은 float 다. 걸리면 안 된다."""
        self.assertEqual(guard.flatten({"x": 0.10}), guard.flatten({"x": 0.1}))


class CompareTests(unittest.TestCase):

    def setUp(self):
        self.a = guard.flatten({
            "commands": {"base_velocity": {"rel_standing_envs": 0.02}},
            "sim": {"device": "cuda:0", "dt": 0.005},
            "log_dir": "/a",
        })
        self.b = guard.flatten({
            "commands": {"base_velocity": {"rel_standing_envs": 0.10}},
            "sim": {"device": "cuda:1", "dt": 0.005},
            "log_dir": "/b",
        })

    def test_the_real_accident_is_caught(self):
        """**알려진 답.** v2a 대 v2b 에서 실제로 난 사고 모양이다."""
        expected, unexpected, unchanged = guard.compare(
            self.a, self.b, ["commands.base_velocity.rel_standing_envs"])
        self.assertEqual([k for k, _, _ in expected],
                         ["commands.base_velocity.rel_standing_envs"])
        self.assertEqual([k for k, _, _ in unexpected], ["sim.device"])
        self.assertEqual(unchanged, [])

    def test_log_dir_is_ignored_by_default(self):
        _, unexpected, _ = guard.compare(self.a, self.b)
        self.assertNotIn("log_dir", [k for k, _, _ in unexpected])

    def test_device_is_not_ignored_by_default(self):
        """**이 도구가 생긴 까닭.** 기본 무시 목록에 장치를 넣으면 안 된다."""
        self.assertNotIn("sim.device", guard.DEFAULT_IGNORE)

    def test_intended_but_unchanged_is_a_problem(self):
        """「바꿨다고 적었는데 «안» 바뀐 것」도 사고다."""
        _, _, unchanged = guard.compare(self.a, self.b, ["sim.dt"])
        self.assertEqual([k for k, _ in unchanged], ["sim.dt"])

    def test_a_key_present_in_only_one_side_is_unexpected(self):
        """한쪽에만 있는 칸도 차이다. None 대 값으로 잡힌다."""
        b = dict(self.b)
        b["scene.new_thing"] = "1"
        _, unexpected, _ = guard.compare(
            self.a, b, ["commands.base_velocity.rel_standing_envs"])
        self.assertIn("scene.new_thing", [k for k, _, _ in unexpected])

    def test_identical_configs_pass_cleanly(self):
        """**반대쪽도 본다.** 늘 막는 관문은 관문이 아니라 고장이다."""
        expected, unexpected, unchanged = guard.compare(self.a, dict(self.a))
        self.assertEqual((expected, unexpected, unchanged), ([], [], []))

    def test_ignoring_the_device_hides_it(self):
        """무시 목록에 넣으면 사라진다. 그래서 «무시를 늘리는 것» 이 위험하다."""
        _, unexpected, _ = guard.compare(
            self.a, self.b, ["commands.base_velocity.rel_standing_envs"],
            ignore=("log_dir", "sim.device"))
        self.assertEqual(unexpected, [])


if __name__ == "__main__":
    unittest.main()
