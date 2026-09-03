"""`metrics.py` 가 Candidate 스냅샷과 같은 값을 내는지 고정한다.

왼쪽은 우리가 쓴 순수 함수, **오른쪽은 스냅샷 파일에서 잘라 온 원문**입니다.
스냅샷이 바뀌면 이 시험이 깨집니다.

돌리는 법 (Isaac 도 GPU 도 필요 없습니다):

    python -m unittest discover -s sim/eval/tests -v
"""

import hashlib
import io
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.dirname(HERE)

for path in (EVAL_DIR, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import metrics
import snapshot_oracle as oracle


TERRAIN_NAMES = ("gap", "pit", "rails")


def case(**over):
    """기본 한 판. 필요한 것만 덮어쓴다."""
    base = {
        "start_xy": (0.0, 0.0),
        "end_xy": (2.85, 0.11),
        "forward_dir": (1.0, 0.0),
        "velocity_error_sum": 18.0,
        "reward_sum": 90.0,
        "sample_count": 300,
        "elapsed_s": 6.0,
        "timed_out": True,
        "terminated": False,
        "path_xy": None,
        "command_vx": 0.5,
        "eval_duration": 6.0,
        "min_progress_ratio": 0.70,
        "max_velocity_mae": 0.25,
        "max_lateral_drift": 0.75,
    }
    base.update(over)
    return base


ROOT_HALF = math.sqrt(0.5)

CASES = {
    "통과": case(),
    "넘어짐": case(timed_out=False, terminated=True, elapsed_s=2.31),
    "전진 부족": case(end_xy=(1.20, 0.05)),
    "전진이 문턱과 정확히 같다": case(end_xy=(2.10, 0.0)),
    "속도 오차 초과": case(velocity_error_sum=90.0),
    "속도 오차가 문턱과 정확히 같다": case(velocity_error_sum=75.0),
    "좌우 이탈 초과": case(end_xy=(2.85, 0.90)),
    "좌우 이탈이 문턱과 정확히 같다": case(end_xy=(2.85, 0.75)),
    "좌로 이탈 (부호 반대)": case(end_xy=(2.85, -0.90)),
    "뒤로 감": case(end_xy=(-1.40, 0.20)),
    "전방축이 45도": case(forward_dir=(ROOT_HALF, ROOT_HALF), end_xy=(2.0, 2.0)),
    "전방축이 -y": case(forward_dir=(0.0, -1.0), end_xy=(0.3, -2.9)),
    "시작점이 원점이 아니다": case(start_xy=(-4.5, 7.25), end_xy=(-1.7, 7.4)),
    "스텝 0 (0 나눗셈 방지)": case(sample_count=0),
    "이상 거리 0": case(command_vx=0.0),
    "20초 · 1.0 m/s 새 기준": case(
        command_vx=1.0,
        eval_duration=20.0,
        end_xy=(13.12, 0.42),
        sample_count=1000,
        elapsed_s=20.0,
    ),
    "경로가 크게 나갔다 돌아온다": case(
        end_xy=(2.85, 0.05),
        path_xy=((0.5, 0.30), (1.2, 1.10), (2.0, 0.60), (2.85, 0.05)),
    ),
    "경로가 좌우로 흔들린다": case(
        end_xy=(2.85, 0.02),
        path_xy=((0.6, -0.55), (1.4, 0.62), (2.1, -0.31), (2.85, 0.02)),
    ),
}


class SnapshotIsIntact(unittest.TestCase):
    """대조 대상이 원래 그 파일인지부터 본다."""

    def test_해시가_SHA256SUMS와_같다(self):
        sums_path = os.path.join(
            EVAL_DIR, "provenance", "candidate-20260822", "SHA256SUMS"
        )

        expected = {}
        with io.open(sums_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    digest, name = line.split(None, 1)
                    expected[name.lstrip("*")] = digest

        with open(oracle.SNAPSHOT_PATH, "rb") as f:
            got = hashlib.sha256(f.read()).hexdigest()

        self.assertEqual(expected["eval_generalization.py"], got)


class EpisodeMetricsMatchSnapshot(unittest.TestCase):
    """한 판의 파생값 13개가 스냅샷과 같은가."""

    def test_모든_경우에서_같다(self):
        for name, values in CASES.items():
            with self.subTest(case=name):
                want = oracle.run_episode_block(values)
                got = metrics.episode_metrics(**values)

                # 스냅샷에 없던 열은 ADDED_COLUMNS 에 적힌 것뿐이어야 한다.
                self.assertEqual(
                    set(got) - set(want),
                    set(metrics.ADDED_COLUMNS),
                    "스냅샷과 달라진 열이 적어 둔 것과 다르다",
                )
                self.assertEqual(
                    set(want) - set(got), set(), "스냅샷 열이 사라졌다"
                )

                for column in sorted(want):
                    self.assertEqual(
                        want[column],
                        got[column],
                        f"{name} · {column} 이 다르다",
                    )

    def test_측면축의_방향까지_같다(self):
        # lateral_drift_m 은 abs() 라 축 부호가 뒤집혀도 값이 같다.
        # 그래서 최종 열만 보면 방향이 고정되지 않는다. 중간값을 직접 못 박는다.
        # #125 1번이 최대 이탈을 추적할 때 이 방향이 뜻을 갖는다.
        for name, values in CASES.items():
            with self.subTest(case=name):
                namespace = oracle.run_episode_block_namespace(values)
                want = namespace["lateral_axis"]

                got = metrics.lateral_axis(values["forward_dir"])

                self.assertEqual((want.x, want.y), got, name)

    def test_불리언은_bool_타입이다(self):
        got = metrics.episode_metrics(**CASES["통과"])

        for column in (
            "overall_success",
            "survival_success",
            "progress_success",
            "tracking_success",
            "direction_success",
        ):
            self.assertIsInstance(got[column], bool, column)


class KnownValues(unittest.TestCase):
    """손으로 셈한 값. 스냅샷과 우리 함수가 함께 틀리는 것을 막는다."""

    def test_전방과_측면_분해(self):
        # 전방축이 45도일 때 (2,2) 변위는 전방 2√2 · 측면 0.
        got = metrics.episode_metrics(**CASES["전방축이 45도"])

        self.assertAlmostEqual(got["forward_progress_m"], 2.0 * math.sqrt(2.0))
        self.assertAlmostEqual(got["lateral_drift_m"], 0.0)

    def test_문턱은_이상과_비율의_곱(self):
        # 0.5 m/s · 6 s = 3.0 m · 0.70 = 2.10 m
        self.assertEqual(metrics.ideal_distance_m(0.5, 6.0), 3.0)
        self.assertAlmostEqual(metrics.min_progress_m(0.70, 3.0), 2.10)

    def test_경계는_이상이고_이하다(self):
        # progress 는 >= · direction 은 <= 다. 문턱값 자체는 통과다.
        self.assertTrue(metrics.progress_success(2.10, 2.10))
        self.assertTrue(metrics.direction_success(0.75, 0.75))
        self.assertFalse(metrics.progress_success(2.09, 2.10))
        self.assertFalse(metrics.direction_success(0.76, 0.75))

    def test_이탈은_부호를_지운다(self):
        left = metrics.lateral_drift_m((2.85, 0.9), (1.0, 0.0))
        right = metrics.lateral_drift_m((2.85, -0.9), (1.0, 0.0))

        self.assertAlmostEqual(left, right)
        self.assertAlmostEqual(left, 0.9)

    def test_변위는_경로를_더하지_않는다(self):
        # 나갔다 돌아오면 끝점 변위는 0 이다. #125 7번 문서 오기의 핵심.
        self.assertEqual(metrics.displacement((0.0, 0.0), (0.0, 0.0)), (0.0, 0.0))

    def test_이상거리가_0이면_비율은_0(self):
        self.assertEqual(metrics.progress_ratio(1.5, 0.0), 0.0)

    def test_스텝이_0이어도_나누어진다(self):
        self.assertEqual(metrics.step_count(0), 1)
        self.assertEqual(metrics.velocity_mae_mps(3.0, 0), 3.0)


class PeakLateralDrift(unittest.TestCase):
    """#125 1번. 스텝별 최대 좌우 이탈. **관측용이고 판정은 건드리지 않는다.**"""

    FORWARD = (1.0, 0.0)

    def test_빈_경로는_0(self):
        self.assertEqual(
            metrics.peak_lateral_drift_m((0.0, 0.0), (), self.FORWARD), 0.0
        )

    def test_경로가_한_점이면_그_점의_이탈(self):
        got = metrics.peak_lateral_drift_m(
            (0.0, 0.0), ((2.85, 0.42),), self.FORWARD
        )

        self.assertAlmostEqual(got, 0.42)

    def test_스텝_최대를_집는다(self):
        # 최댓값이 중간에 있고 끝점은 작다. 끝점만 보면 못 잡는 값이다.
        path = ((0.5, 0.30), (1.2, 1.10), (2.0, 0.60), (2.85, 0.05))

        got = metrics.peak_lateral_drift_m((0.0, 0.0), path, self.FORWARD)

        self.assertAlmostEqual(got, 1.10)

    def test_부호가_반대여도_같은_최댓값(self):
        left = ((0.5, 0.30), (1.2, 1.10), (2.85, 0.05))
        right = ((0.5, -0.30), (1.2, -1.10), (2.85, -0.05))

        self.assertAlmostEqual(
            metrics.peak_lateral_drift_m((0.0, 0.0), left, self.FORWARD),
            metrics.peak_lateral_drift_m((0.0, 0.0), right, self.FORWARD),
        )

    def test_좌우로_흔들려도_가장_큰_쪽을_집는다(self):
        path = ((0.6, -0.55), (1.4, 0.62), (2.1, -0.31), (2.85, 0.02))

        got = metrics.peak_lateral_drift_m((0.0, 0.0), path, self.FORWARD)

        self.assertAlmostEqual(got, 0.62)

    def test_언제나_0_이상이다(self):
        path = ((0.6, -0.55), (1.4, -0.62))

        got = metrics.peak_lateral_drift_m((0.0, 0.0), path, self.FORWARD)

        self.assertGreaterEqual(got, 0.0)
        self.assertAlmostEqual(got, 0.62)

    def test_순간값은_부호를_남긴다(self):
        # peak 은 abs 지만, 그 재료인 lateral_offset_m 은 방향을 남긴다.
        left = metrics.lateral_offset_m((0.0, 0.0), (1.0, 0.5), self.FORWARD)
        right = metrics.lateral_offset_m((0.0, 0.0), (1.0, -0.5), self.FORWARD)

        self.assertAlmostEqual(left, 0.5)
        self.assertAlmostEqual(right, -0.5)

    def test_끝점_이탈은_순간값의_절댓값과_같다(self):
        start, end, forward = (-4.5, 7.25), (-1.7, 7.4), (0.0, -1.0)

        endpoint = metrics.lateral_drift_m(
            metrics.displacement(start, end), forward
        )
        moment = abs(metrics.lateral_offset_m(start, end, forward))

        self.assertAlmostEqual(endpoint, moment)

    def test_시작점이_원점이_아니어도_된다(self):
        start = (-4.5, 7.25)
        path = ((-3.0, 7.55), (-2.2, 6.45), (-1.7, 7.30))

        got = metrics.peak_lateral_drift_m(start, path, self.FORWARD)

        self.assertAlmostEqual(got, 0.80)

    def test_전방축이_45도여도_맞다(self):
        forward = (ROOT_HALF, ROOT_HALF)
        # (1,-1) 은 전방축에 수직이고 길이 √2 다.
        path = ((1.0, -1.0), (0.5, 0.5))

        got = metrics.peak_lateral_drift_m((0.0, 0.0), path, forward)

        self.assertAlmostEqual(got, math.sqrt(2.0))

    # ---------------------------------------------------- 판정 불변

    def test_최댓값은_끝점_이탈보다_작지_않다(self):
        for name, values in CASES.items():
            with self.subTest(case=name):
                got = metrics.episode_metrics(**values)

                self.assertGreaterEqual(
                    got["peak_lateral_drift_m"],
                    got["lateral_drift_m"],
                    name,
                )

    def test_경로를_안_주면_끝점_하나짜리_경로다(self):
        got = metrics.episode_metrics(**CASES["통과"])

        self.assertAlmostEqual(
            got["peak_lateral_drift_m"], got["lateral_drift_m"]
        )

    def test_판정은_끝점_그대로다(self):
        # 중간에 문턱(0.75 m)을 크게 넘겼다가 끝점은 0.05 m 로 돌아온 경우.
        # 멘토 기준대로 direction_success 는 True 여야 한다.
        got = metrics.episode_metrics(**CASES["경로가 크게 나갔다 돌아온다"])

        self.assertGreater(got["peak_lateral_drift_m"], 0.75)
        self.assertLess(got["lateral_drift_m"], 0.75)
        self.assertTrue(got["direction_success"])
        self.assertTrue(got["overall_success"])

    def test_경로를_바꿔도_판정_5축은_안_바뀐다(self):
        without = metrics.episode_metrics(**case(end_xy=(2.85, 0.05)))
        with_path = metrics.episode_metrics(
            **case(
                end_xy=(2.85, 0.05),
                path_xy=((1.2, 1.10), (2.0, -0.90), (2.85, 0.05)),
            )
        )

        for column in metrics.RAW_COLUMNS:
            if column in metrics.ADDED_COLUMNS or column not in without:
                continue
            self.assertEqual(without[column], with_path[column], column)

        self.assertNotEqual(
            without["peak_lateral_drift_m"], with_path["peak_lateral_drift_m"]
        )


class SummaryMatchesSnapshot(unittest.TestCase):
    """지형별 집계가 스냅샷과 같은가."""

    @staticmethod
    def rows():
        made = []
        for terrain in TERRAIN_NAMES:
            for episode, values in enumerate(CASES.values()):
                derived = metrics.episode_metrics(**values)
                row = {"terrain": terrain, "episode": episode}
                row.update(derived)
                made.append(row)
        return made

    def test_요약이_같다(self):
        made = self.rows()

        want = oracle.run_summarize_results(made, TERRAIN_NAMES)
        got = metrics.summarize(made, TERRAIN_NAMES)

        self.assertEqual(want, got)

    @staticmethod
    def stringify(rows, columns):
        return [
            {k: (str(v) if k in columns else v) for k, v in row.items()}
            for row in rows
        ]

    def test_수치열이_문자열이어도_같다(self):
        # CSV 를 되읽으면 수치가 문자열로 온다. 스냅샷은 float() 로 되돌린다.
        numeric = {
            "duration_s",
            "forward_progress_m",
            "lateral_drift_m",
            "velocity_mae_mps",
            "mean_reward_per_step",
        }

        made = self.stringify(self.rows(), numeric)

        want = oracle.run_summarize_results(made, TERRAIN_NAMES)
        got = metrics.summarize(made, TERRAIN_NAMES)

        self.assertEqual(want, got)

    def test_판정열이_문자열이면_둘_다_같은_오류(self):
        # 스냅샷은 int(r["overall_success"]) 를 쓴다. "True" 는 int() 가 못 받는다.
        # 실제 하네스는 메모리 안 행을 그대로 넘기므로 이 경우가 생기지 않는다.
        # 우리 함수도 같은 자리에서 같은 오류를 내야 한다.
        made = self.stringify(self.rows(), {"overall_success"})

        with self.assertRaises(ValueError):
            oracle.run_summarize_results(made, TERRAIN_NAMES)

        with self.assertRaises(ValueError):
            metrics.summarize(made, TERRAIN_NAMES)

    def test_전부_생존하면_낙상시간은_빈칸(self):
        made = [
            row for row in self.rows() if row["survival_success"]
        ]

        got = metrics.summarize(made, TERRAIN_NAMES)

        for row in got:
            self.assertEqual(row["mean_fall_time_s"], "")


class ColumnContract(unittest.TestCase):
    """CSV 열 순서를 스냅샷에 못 박는다."""

    def test_추가분을_빼면_스냅샷_열_순서(self):
        without_added = tuple(
            c for c in metrics.RAW_COLUMNS if c not in metrics.ADDED_COLUMNS
        )

        self.assertEqual(oracle.dict_key_order(543), without_added)

    def test_추가분은_원시_열에_들어_있다(self):
        for column in metrics.ADDED_COLUMNS:
            self.assertIn(column, metrics.RAW_COLUMNS)

    def test_추가분의_자리도_못_박는다(self):
        # 끝점 이탈 바로 뒤에 둔다. 같은 것을 두 가지로 잰 값이라 붙어 있어야
        # CSV 를 눈으로 볼 때 비교가 된다.
        columns = list(metrics.RAW_COLUMNS)

        self.assertEqual(
            columns.index("peak_lateral_drift_m"),
            columns.index("lateral_drift_m") + 1,
        )

    def test_추가분은_스냅샷에_없던_이름이다(self):
        snapshot_columns = set(oracle.dict_key_order(543))

        for column in metrics.ADDED_COLUMNS:
            self.assertNotIn(column, snapshot_columns)

    def test_요약_열_순서(self):
        self.assertEqual(oracle.dict_key_order(272), metrics.SUMMARY_COLUMNS)

    def test_파생값이_원시_열에_다_들어간다(self):
        derived = set(metrics.episode_metrics(**CASES["통과"]))

        # 원시 열에서 파생값이 아닌 것: 식별자와 초기 자세.
        identity = {
            "terrain",
            "env_id",
            "episode",
            "start_x_offset_m",
            "start_y_offset_m",
            "start_yaw_deg",
        }

        self.assertEqual(set(metrics.RAW_COLUMNS) - identity, derived)


if __name__ == "__main__":
    unittest.main(verbosity=2)
