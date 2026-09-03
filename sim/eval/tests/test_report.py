"""`report.py` 의 Wilson 구간과 CSV 되읽기를 고정한다.

발표에 나가는 숫자를 내는 코드입니다. 손계산과 대조해 못 박습니다.

돌리는 법 (Isaac 도 GPU 도 필요 없습니다):

    python -m unittest discover -s sim/eval/tests -v
"""

import csv
import io
import math
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.dirname(HERE)

for path in (EVAL_DIR, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import metrics
import report


def wilson_by_hand(k, n, z=report.Z_95):
    """식을 따로 한 번 더 적는다. 구현과 같은 값이 나와야 한다."""
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))
    return centre - half, centre + half


class WilsonInterval(unittest.TestCase):
    """Wald 대신 Wilson 을 쓰는 이유가 그대로 성립하는지 본다."""

    def test_matches_hand_calculation(self):
        for k, n in ((50, 100), (90, 100), (1, 7), (23, 41)):
            with self.subTest(k=k, n=n):
                low, high = report.wilson_interval(k, n)
                want_low, want_high = wilson_by_hand(k, n)

                self.assertAlmostEqual(low, want_low, places=12)
                self.assertAlmostEqual(high, want_high, places=12)

    def test_keeps_width_at_the_edges(self):
        """0/n 과 n/n 에서도 폭이 남는다. Wald 는 여기서 0 으로 찌그러진다."""
        for k in (0, 100):
            with self.subTest(k=k):
                low, high = report.wilson_interval(k, 100)

                self.assertGreater(high - low, 0.03)
                self.assertLess(high - low, 0.04)

    def test_stays_inside_zero_and_one(self):
        for k, n in ((0, 5), (5, 5), (0, 1), (1, 1)):
            with self.subTest(k=k, n=n):
                low, high = report.wilson_interval(k, n)

                self.assertGreaterEqual(low, 0.0)
                self.assertLessEqual(high, 1.0)

    def test_narrows_as_episodes_grow(self):
        """판을 늘리면 구간이 좁아진다."""
        widths = []

        for n in (25, 100, 400):
            low, high = report.wilson_interval(n // 2, n)
            widths.append(high - low)

        self.assertGreater(widths[0], widths[1])
        self.assertGreater(widths[1], widths[2])

    def test_contains_the_observed_rate(self):
        # p=0 과 p=1 에서 경계는 **정확히** 관측값이다. 구현이 float 로 계산하므로
        # 1e-12 만큼의 반올림 여유를 둔다. 여유를 넘는 어긋남은 식이 틀린 것이다.
        slack = 1.0e-12

        for k, n in ((0, 100), (37, 100), (100, 100)):
            with self.subTest(k=k, n=n):
                low, high = report.wilson_interval(k, n)

                self.assertLessEqual(low, k / n + slack)
                self.assertGreaterEqual(high, k / n - slack)

    def test_empty_sample_is_not_a_crash(self):
        self.assertEqual(report.wilson_interval(0, 0), (0.0, 0.0))


def write_raw_csv(path, rows):
    """하네스가 쓰는 것과 같은 열 순서로 원시 CSV 를 만든다."""
    with io.open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics.RAW_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)


def raw_row(**over):
    base = {
        "terrain": "flat",
        "env_id": 100,
        "episode": 1,
        "start_x_offset_m": 0.0,
        "start_y_offset_m": 0.0,
        "start_yaw_deg": 0.0,
        "overall_success": False,
        "survival_success": True,
        "progress_success": True,
        "tracking_success": True,
        "direction_success": False,
        "termination_reason": "timeout",
        "duration_s": 12.0,
        "forward_progress_m": 11.4,
        "ideal_distance_m": 12.0,
        "progress_ratio": 0.95,
        "lateral_drift_m": 0.25,
        "peak_lateral_drift_m": 0.3,
        "velocity_mae_mps": 0.11,
        "mean_reward_per_step": 0.5,
    }
    base.update(over)
    return base


class ReadRows(unittest.TestCase):
    """CSV 에서 되읽은 `"True"` 가 판정에 그대로 쓰일 수 있어야 한다."""

    def test_booleans_come_back_as_booleans(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "generalization_raw.csv")
            write_raw_csv(path, [raw_row(), raw_row(overall_success=True, episode=2)])

            rows = report.read_rows(path)

        self.assertIs(rows[0]["overall_success"], False)
        self.assertIs(rows[1]["overall_success"], True)
        self.assertIs(rows[0]["survival_success"], True)

    def test_read_rows_feeds_metrics_summarize(self):
        """되읽은 행이 `metrics.summarize` 에 그대로 들어가야 한다.

        스냅샷의 `int(r[...])` 가 문자열 `"True"` 를 못 받기 때문에 두는 시험입니다.
        """
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "generalization_raw.csv")
            write_raw_csv(path, [raw_row(), raw_row(episode=2, overall_success=True)])

            rows = report.read_rows(path)

        summary = metrics.summarize(rows, ("flat",))

        self.assertEqual(summary[0]["episodes"], 2)
        self.assertAlmostEqual(summary[0]["overall_success_rate"], 0.5)


class Analyse(unittest.TestCase):

    def _analyse(self, rows):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "generalization_raw.csv")
            write_raw_csv(path, rows)

            return report.analyse(report.read_rows(path), "flat")

    def test_counts_every_axis(self):
        rows = [
            raw_row(episode=1, direction_success=True, overall_success=True),
            raw_row(episode=2),
            raw_row(episode=3),
            raw_row(episode=4),
        ]

        result = self._analyse(rows)

        self.assertEqual(result["episodes"], 4)
        self.assertEqual(result["axes"]["overall_success"]["successes"], 1)
        self.assertEqual(result["axes"]["direction_success"]["successes"], 1)
        self.assertEqual(result["axes"]["survival_success"]["successes"], 4)

    def test_separates_falls_from_timeouts(self):
        rows = [
            raw_row(episode=1, termination_reason="timeout"),
            raw_row(episode=2, termination_reason="base_contact"),
            raw_row(episode=3, termination_reason="base_contact"),
        ]

        result = self._analyse(rows)

        self.assertEqual(result["timeout"], 1)
        self.assertEqual(result["fell"], 2)

    def test_peak_drift_is_never_below_endpoint_drift(self):
        """관측 열의 뜻이 유지되는지. 최대 이탈은 끝점 이탈보다 작을 수 없다."""
        rows = [
            raw_row(episode=1, lateral_drift_m=0.25, peak_lateral_drift_m=0.31),
            raw_row(episode=2, lateral_drift_m=0.60, peak_lateral_drift_m=0.60),
        ]

        result = self._analyse(rows)

        self.assertGreaterEqual(result["peak_drift"]["mean"], result["endpoint_drift"]["mean"])
        self.assertGreaterEqual(result["peak_drift"]["max"], result["endpoint_drift"]["max"])

    def test_median_of_even_sample_is_the_midpoint(self):
        rows = [
            raw_row(episode=1, lateral_drift_m=0.10),
            raw_row(episode=2, lateral_drift_m=0.20),
            raw_row(episode=3, lateral_drift_m=0.30),
            raw_row(episode=4, lateral_drift_m=0.60),
        ]

        result = self._analyse(rows)

        self.assertAlmostEqual(result["endpoint_drift"]["median"], 0.25)
        self.assertAlmostEqual(result["endpoint_drift"]["max"], 0.60)

    def test_unknown_terrain_is_an_error_not_a_zero(self):
        """기록이 없는 지형을 0% 로 조용히 내지 않는다."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "generalization_raw.csv")
            write_raw_csv(path, [raw_row()])

            rows = report.read_rows(path)

        with self.assertRaises(ValueError):
            report.analyse(rows, "gap")


if __name__ == "__main__":
    unittest.main()
