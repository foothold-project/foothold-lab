# -*- coding: utf-8 -*-
"""`terrain_split` 을 «알려진 답» 과 «망가뜨린 입력» 으로 시험한다.

분류: 실험
작성: Claude 세션 (오흥재 지시) · 2026-09-23
근거: inbox/jay/20260923-lineage/CRITERIA.md v1.0 2 절 (21 / 3 / 24) · 각 학습이 남긴 params/env.yaml
요지: 분류가 맞는지만 보지 않고, 근거가 없을 때 «멈추는지» 를 같이 본다
상태: 확정
판: v1.0

## 무엇을 시험하나

```
알려진 답    v2a·v2b -> 21 / 3 / 24   CRITERIA 2 절이 적은 수와 같아야 한다
             D·E     -> 18 / 0 / 30   rails 를 «안» 배웠으므로 rails 가 새 지형이다
             F·H     -> 18 / 3 / 27

멈추는가     파일 없음 · sub_terrains 없음 · 둘임 · 비었음
             출처 없는 학습 지형 · 학습이면서 닮은 짝인 지형
```

**「멈추는가」쪽이 이 시험의 요지입니다.** 분류를 못 하는데 조용히
「전부 새 지형」으로 세면 일반화 주장이 부풀려집니다.
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import terrain_split as ts

# 평가 하네스의 16 종 (`generalization_env_cfg.py`). 세 속도로 48 칸이 된다.
EVAL16 = ("discrete_obstacles", "wave", "stepping_stones", "gap", "pit",
          "rails", "star", "floating_ring", "repeated_boxes",
          "repeated_cylinders", "pyramid_stairs", "pyramid_stairs_inv",
          "boxes", "random_rough", "hf_pyramid_slope", "hf_pyramid_slope_inv")

ROUGH6 = ("pyramid_stairs", "pyramid_stairs_inv", "boxes", "random_rough",
          "hf_pyramid_slope", "hf_pyramid_slope_inv")

LOGS = ("C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/%s"
        "/params/env.yaml")
RUNS = {
    "D": "2026-09-18_11-19-19_20260918_gapwidecmd_seed42_iter1500",
    "E": "2026-09-20_00-04-33_20260920_gapE_seed42_iter1500",
    "F": "2026-09-20_09-45-06_20260920_gapF_seed42_iter1500",
    "H": "2026-09-20_16-00-26_20260920_gapH_seed42_iter1500",
    "v2a": "2026-09-21_11-03-23_20260921_v2a_seed42_iter3000",
    "v2b": "2026-09-21_11-03-28_20260921_v2b_seed42_iter3000",
}


def cells_of(terrains):
    """지형 목록 -> 48 칸 열쇠 (속도 셋)."""
    return [(speed, "set", terrain)
            for terrain in terrains
            for speed in ("0.5 m/s", "1.0 m/s", "1.5 m/s")]


def write(text):
    handle = tempfile.NamedTemporaryFile(
        "w", suffix=".yaml", delete=False, encoding="utf-8")
    handle.write(text)
    handle.close()
    return handle.name


class ReadTests(unittest.TestCase):
    """`env.yaml` 읽기."""

    def test_real_v2a_has_eight(self):
        path = LOGS % RUNS["v2a"]
        if not os.path.exists(path):
            self.skipTest("v2a 학습 기록이 이 기계에 없다")
        self.assertEqual(ts.read_sub_terrains(path),
                         list(ROUGH6) + ["omni_gap", "rails"])

    def test_deeper_keys_are_not_collected(self):
        """`size:` 처럼 «한 단계 더 아래» 인 키는 지형이 아니다."""
        path = write("terrain:\n"
                     "  sub_terrains:\n"
                     "    rails:\n"
                     "      function: x\n"
                     "      size:\n"
                     "      - 8.0\n"
                     "    boxes:\n"
                     "      function: y\n"
                     "  other: 1\n")
        try:
            self.assertEqual(ts.read_sub_terrains(path), ["rails", "boxes"])
        finally:
            os.unlink(path)

    def test_stops_at_dedent(self):
        """`sub_terrains` 블록이 끝나면 더 안 읽는다."""
        path = write("terrain:\n"
                     "  sub_terrains:\n"
                     "    rails:\n"
                     "      function: x\n"
                     "  events:\n"
                     "    push_robot:\n")
        try:
            self.assertEqual(ts.read_sub_terrains(path), ["rails"])
        finally:
            os.unlink(path)


class ReadGuardTests(unittest.TestCase):
    """**못 읽으면 멈춘다.** 빈 목록을 돌려주지 않는다."""

    def test_missing_file(self):
        with self.assertRaises(ValueError) as caught:
            ts.read_sub_terrains(os.path.join(HERE, "없는파일.yaml"))
        self.assertIn("없다", str(caught.exception))

    def test_no_sub_terrains_key(self):
        path = write("terrain:\n  size: 8\n")
        try:
            with self.assertRaises(ValueError):
                ts.read_sub_terrains(path)
        finally:
            os.unlink(path)

    def test_two_sub_terrains_blocks_name_both_lines(self):
        """둘이면 «첫째를 고르지 않고» 사람에게 넘긴다."""
        path = write("a:\n  sub_terrains:\n    rails:\n"
                     "b:\n  sub_terrains:\n    boxes:\n")
        try:
            with self.assertRaises(ValueError) as caught:
                ts.read_sub_terrains(path)
            message = str(caught.exception)
            self.assertIn("2 개", message)
            self.assertIn("2", message)
            self.assertIn("5", message)
        finally:
            os.unlink(path)

    def test_empty_block(self):
        path = write("terrain:\n  sub_terrains:\n  other: 1\n")
        try:
            with self.assertRaises(ValueError):
                ts.read_sub_terrains(path)
        finally:
            os.unlink(path)


class KnownAnswerTests(unittest.TestCase):
    """**CRITERIA 2 절이 적은 수**가 그대로 나와야 한다."""

    def counts(self, trained):
        groups = ts.split_cells(cells_of(EVAL16), trained)
        return tuple(len(groups[bucket]) for bucket in
                     (ts.LEARNED, ts.SIMILAR_TO, ts.UNSEEN))

    def test_v2_is_21_3_24(self):
        self.assertEqual(
            self.counts(list(ROUGH6) + ["omni_gap", "rails"]), (21, 3, 24))

    def test_de_is_18_0_30_because_rails_was_not_trained(self):
        trained = list(ROUGH6) + ["forward_gap"]
        self.assertEqual(self.counts(trained), (18, 0, 30))
        self.assertEqual(ts.classify(EVAL16, trained)["rails"], ts.UNSEEN)

    def test_fh_is_18_3_27(self):
        self.assertEqual(self.counts(list(ROUGH6) + ["omni_gap"]), (18, 3, 27))

    def test_every_recorded_run_matches(self):
        """기계에 남아 있는 학습 기록으로 다시 센다."""
        wanted = {"D": (18, 0, 30), "E": (18, 0, 30), "F": (18, 3, 27),
                  "H": (18, 3, 27), "v2a": (21, 3, 24), "v2b": (21, 3, 24)}
        seen = 0
        for name, run in sorted(RUNS.items()):
            path = LOGS % run
            if not os.path.exists(path):
                continue
            seen += 1
            self.assertEqual(self.counts(ts.read_sub_terrains(path)),
                             wanted[name], name)
        if not seen:
            self.skipTest("학습 기록이 이 기계에 없다")

    def test_gap_is_new_terrain_even_for_forward_gap_policies(self):
        """폭을 맞춘 것은 «모양이 닮은 것» 이 아니다 (`gap_wide_env_cfg.py`)."""
        marks = ts.classify(EVAL16, list(ROUGH6) + ["forward_gap"])
        self.assertEqual(marks["gap"], ts.UNSEEN)

    def test_floating_ring_only_similar_when_omni_gap_trained(self):
        self.assertEqual(
            ts.classify(EVAL16, list(ROUGH6) + ["omni_gap"])["floating_ring"],
            ts.SIMILAR_TO)
        self.assertEqual(
            ts.classify(EVAL16, list(ROUGH6))["floating_ring"], ts.UNSEEN)


class ClassifyGuardTests(unittest.TestCase):
    """**근거가 없으면 분류하지 않는다.**"""

    def test_unknown_trained_terrain_stops_and_names_it(self):
        with self.assertRaises(ValueError) as caught:
            ts.classify(EVAL16, list(ROUGH6) + ["새로운지형"])
        self.assertIn("새로운지형", str(caught.exception))

    def test_empty_eval_stops(self):
        with self.assertRaises(ValueError):
            ts.classify([], list(ROUGH6))

    def test_empty_trained_stops(self):
        with self.assertRaises(ValueError):
            ts.classify(EVAL16, [])

    def test_double_counting_stops(self):
        """학습 지형이면서 닮은 짝이기도 하면 두 번 센다."""
        saved = dict(ts.SIMILAR["omni_gap"])
        ts.SIMILAR["omni_gap"] = dict(saved, eval="rails")
        try:
            with self.assertRaises(ValueError) as caught:
                ts.classify(EVAL16, list(ROUGH6) + ["omni_gap", "rails"])
            self.assertIn("두 번", str(caught.exception))
        finally:
            ts.SIMILAR["omni_gap"] = saved

    def test_unknown_bucket_name_stops(self):
        """`classify` 가 모르는 이름을 내면 그 칸이 조용히 사라진다."""
        saved = ts.classify
        ts.classify = lambda ev, tr: {t: "??" for t in ev}
        try:
            with self.assertRaises(ValueError) as caught:
                ts.split_cells(cells_of(EVAL16), list(ROUGH6))
            self.assertIn("모르는 묶음", str(caught.exception))
        finally:
            ts.classify = saved

    def test_split_cells_loses_nothing(self):
        keys = cells_of(EVAL16)
        groups = ts.split_cells(keys, list(ROUGH6) + ["omni_gap", "rails"])
        flat = [key for bucket in ts.BUCKETS for key in groups[bucket]]
        self.assertEqual(sorted(flat), sorted(keys))
        self.assertEqual(len(flat), 48)


class SourceTests(unittest.TestCase):
    """**닮았다는 말에는 그렇게 적은 줄이 붙는다.**"""

    def test_similar_entries_all_cite_a_source(self):
        for name, entry in ts.SIMILAR.items():
            self.assertTrue(entry.get("source"), name)
            self.assertTrue(entry.get("quote"), name)

    def test_sources_only_for_cells_actually_marked_similar(self):
        rows = ts.sources(EVAL16, list(ROUGH6) + ["omni_gap"])
        self.assertEqual([(r[0], r[1]) for r in rows],
                         [("floating_ring", "omni_gap")])
        self.assertIn("omni_gap_terrain.py", rows[0][2])
        # forward_gap 은 닮은 짝이 없으므로 줄이 안 나온다
        self.assertEqual(ts.sources(EVAL16, list(ROUGH6) + ["forward_gap"]), [])

    def test_width_note_only_for_forward_gap(self):
        self.assertEqual(ts.width_notes(list(ROUGH6) + ["omni_gap"]), [])
        notes = ts.width_notes(list(ROUGH6) + ["forward_gap"])
        self.assertEqual(len(notes), 1)
        self.assertIn("0.15", notes[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
