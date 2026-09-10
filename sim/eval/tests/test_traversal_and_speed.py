"""새 분석 열 셋을 못 박는다. `traversal_success` · `gate_speed_mps` · `speed_drop_ratio`.

셋 다 **판정이 아니다.** 이 파일에서 가장 중요한 시험은
`TraversalIsNotJudgement` 이고, 그것이 「이 열을 아무리 흔들어도 `overall_success`
가 안 바뀐다」를 못 박는다.

돌리는 법 (Isaac 도 GPU 도 필요 없습니다):

    python -m unittest discover -s sim/eval/tests -v
"""

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
import terrains


def case(**over):
    """기본 한 에피소드. `test_metrics.py` 의 것과 같은 값이다."""
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


def straight_path(distance_m, step_m=0.02):
    """+x 로 곧게 가는 경로 표본. 0 부터 `distance_m` 까지."""
    count = int(round(distance_m / step_m)) + 1

    return [(index * step_m, 0.0) for index in range(count)]


class TraversalSuccessMeaning(unittest.TestCase):
    """생존 · 전진 · 방향 셋만 본다. 속도 추종은 안 본다."""

    def test_세_축의_AND_다(self):
        for survival in (True, False):
            for progress in (True, False):
                for direction in (True, False):
                    with self.subTest(s=survival, p=progress, d=direction):
                        self.assertEqual(
                            metrics.traversal_success(survival, progress, direction),
                            survival and progress and direction,
                        )

    def test_속도_추종은_인자에도_없다(self):
        # 인자가 셋뿐인 것이 「속도 추종을 안 본다」의 보증이다.
        # 넷째 인자를 넣으면 여기서 걸린다.
        with self.assertRaises(TypeError):
            metrics.traversal_success(True, True, True, True)

    def test_불리언_타입이다(self):
        self.assertIsInstance(metrics.traversal_success(1, 1, 1), bool)

    def test_속도만_떨어진_에피소드에서_둘이_갈린다(self):
        # 이 열이 존재하는 이유가 이 한 줄이다. 속도 오차만 문턱을 넘긴다.
        got = metrics.episode_metrics(**case(velocity_error_sum=90.0))

        self.assertFalse(got["tracking_success"])
        self.assertFalse(got["overall_success"])
        self.assertTrue(got["traversal_success"])

    def test_넘어진_에피소드는_둘_다_실패다(self):
        got = metrics.episode_metrics(
            **case(timed_out=False, terminated=True, elapsed_s=2.31)
        )

        self.assertFalse(got["overall_success"])
        self.assertFalse(got["traversal_success"])

    def test_통과한_에피소드는_둘_다_통과다(self):
        got = metrics.episode_metrics(**case())

        self.assertTrue(got["overall_success"])
        self.assertTrue(got["traversal_success"])

    def test_통과보다_느슨하지_좁지_않다(self):
        # `overall_success` 가 참이면 `traversal_success` 도 반드시 참이다.
        # 반대는 아니다. 이것이 「두 층」의 뜻이다.
        for survival in (True, False):
            for progress in (True, False):
                for tracking in (True, False):
                    for direction in (True, False):
                        overall = metrics.overall_success(
                            survival, progress, tracking, direction
                        )
                        traversal = metrics.traversal_success(
                            survival, progress, direction
                        )

                        if overall:
                            self.assertTrue(traversal)


class TraversalIsNotJudgement(unittest.TestCase):
    """★ 이 열은 성공률이 아니다. 판정 5축을 한 칸도 안 건드린다."""

    JUDGEMENT = (
        "overall_success",
        "survival_success",
        "progress_success",
        "tracking_success",
        "direction_success",
    )

    def test_새_열_셋은_전부_추가분이다(self):
        # 추가분 목록에 있어야 스냅샷 대조 시험들이 이 열을 건너뛴다.
        for column in ("traversal_success", "gate_speed_mps", "speed_drop_ratio"):
            self.assertIn(column, metrics.ADDED_COLUMNS)
            self.assertIn(column, metrics.RAW_COLUMNS)

    def test_속도_인자를_줘도_판정_5축이_안_바뀐다(self):
        path = straight_path(3.0)

        without = metrics.episode_metrics(**case(path_xy=path, end_xy=(3.0, 0.0)))

        with_speed = metrics.episode_metrics(
            **case(
                path_xy=path,
                end_xy=(3.0, 0.0),
                path_speed_mps=[0.01] * len(path),
                obstacle_zone_m=(0.75, 2.0),
                gate_progress_m=2.0,
            )
        )

        for column in self.JUDGEMENT:
            self.assertEqual(without[column], with_speed[column], column)

    def test_속도가_0이어도_판정이_안_바뀐다(self):
        # 「장애물 앞에서 완전히 멈췄다」가 성공률을 깎으면 안 된다.
        path = straight_path(3.0)

        stopped = metrics.episode_metrics(
            **case(
                path_xy=path,
                end_xy=(3.0, 0.0),
                path_speed_mps=[0.0] * len(path),
                obstacle_zone_m=(0.75, 2.0),
            )
        )

        self.assertTrue(stopped["overall_success"])
        self.assertEqual(stopped["speed_drop_ratio"], 0.0)

    def test_속도_열을_안_주면_판정이_스냅샷_그대로다(self):
        without = metrics.episode_metrics(**case())
        with_speed = metrics.episode_metrics(
            **case(path_speed_mps=[0.5], obstacle_zone_m=(0.0, 10.0))
        )

        for column in metrics.RAW_COLUMNS:
            if column in metrics.ADDED_COLUMNS or column not in without:
                continue

            self.assertEqual(without[column], with_speed[column], column)

    def test_안_주면_속도_두_열은_None(self):
        got = metrics.episode_metrics(**case())

        self.assertIsNone(got["gate_speed_mps"])
        self.assertIsNone(got["speed_drop_ratio"])

    def test_통과_판정은_언제나_값이_있다(self):
        # 새 입력이 없어도 셈할 수 있으므로 `None` 이 되면 안 된다.
        # 그래야 `test_metrics.py` 의 「파생값이 원시 열에 다 들어간다」가 산다.
        got = metrics.episode_metrics(**case())

        self.assertIsInstance(got["traversal_success"], bool)


class GateSpeed(unittest.TestCase):
    """통과선을 지나는 순간의 전진 속도."""

    def test_표본이_통과선_위에_정확히_있으면_그_값(self):
        got = metrics.gate_speed_mps(
            (0.0, 0.0),
            [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)],
            [0.9, 0.4, 1.1],
            (1.0, 0.0),
            1.0,
        )

        self.assertAlmostEqual(got, 0.4)

    def test_앞뒤_표본_사이를_보간한다(self):
        # 1.0 m 에서 0.4, 2.0 m 에서 1.4. 통과선 1.5 m 면 가운데인 0.9.
        got = metrics.gate_speed_mps(
            (0.0, 0.0),
            [(1.0, 0.0), (2.0, 0.0)],
            [0.4, 1.4],
            (1.0, 0.0),
            1.5,
        )

        self.assertAlmostEqual(got, 0.9)

    def test_통과선을_못_넘기면_None(self):
        got = metrics.gate_speed_mps(
            (0.0, 0.0), [(0.0, 0.0), (0.5, 0.0)], [1.0, 1.0], (1.0, 0.0), 3.0
        )

        self.assertIsNone(got)

    def test_빈_경로는_None(self):
        self.assertIsNone(
            metrics.gate_speed_mps((0.0, 0.0), [], [], (1.0, 0.0), 1.0)
        )

    def test_첫_표본이_이미_통과선_너머면_그_표본(self):
        got = metrics.gate_speed_mps(
            (0.0, 0.0), [(5.0, 0.0)], [0.7], (1.0, 0.0), 1.0
        )

        self.assertAlmostEqual(got, 0.7)

    def test_시작점이_원점이_아니어도_된다(self):
        got = metrics.gate_speed_mps(
            (-4.5, 7.25),
            [(-4.5, 7.25), (-2.5, 7.25)],
            [0.2, 1.0],
            (1.0, 0.0),
            2.0,
        )

        self.assertAlmostEqual(got, 1.0)

    def test_전방축이_45도여도_맞다(self):
        root = math.sqrt(0.5)

        got = metrics.gate_speed_mps(
            (0.0, 0.0),
            [(0.0, 0.0), (root, root), (2 * root, 2 * root)],
            [0.3, 0.6, 0.9],
            (root, root),
            1.0,
        )

        self.assertAlmostEqual(got, 0.6, places=5)

    def test_통과선을_안_주면_열이_None(self):
        got = metrics.episode_metrics(
            **case(
                path_xy=straight_path(3.0),
                end_xy=(3.0, 0.0),
                path_speed_mps=[0.5] * len(straight_path(3.0)),
            )
        )

        self.assertIsNone(got["gate_speed_mps"])

    def test_평균_속도_오차와_다른_것을_잰다(self):
        # 앞에서 느리고 뒤에서 빠른 에피소드와 내내 고른 에피소드는
        # 평균이 같아도 통과선 속도가 다르다. 이 열이 있는 이유다.
        path = straight_path(4.0)
        gate = 1.0

        slow_then_fast = [0.2 if x < 2.0 else 0.8 for x, _ in path]

        # 뒤집어서 만든다. 그래야 두 목록의 **합이 글자 그대로 같다.**
        # 조건을 뒤집어 적으면 표본 수가 홀수일 때 평균이 살짝 어긋난다.
        fast_then_slow = list(reversed(slow_then_fast))

        self.assertAlmostEqual(
            sum(slow_then_fast) / len(slow_then_fast),
            sum(fast_then_slow) / len(fast_then_slow),
        )

        a = metrics.gate_speed_mps((0.0, 0.0), path, slow_then_fast, (1.0, 0.0), gate)
        b = metrics.gate_speed_mps((0.0, 0.0), path, fast_then_slow, (1.0, 0.0), gate)

        self.assertNotAlmostEqual(a, b)


class SpeedDropRatio(unittest.TestCase):
    """장애물 구간에서 얼마나 줄였나."""

    def test_구간_안_최저값을_집는다(self):
        path = straight_path(3.0)
        speed = [0.3 if 0.75 <= x <= 1.5 else 1.0 for x, _ in path]

        got = metrics.obstacle_zone_min_speed_mps(
            (0.0, 0.0), path, speed, (1.0, 0.0), 0.75, 1.5
        )

        self.assertAlmostEqual(got, 0.3)

    def test_구간_밖의_느린_값은_안_본다(self):
        path = straight_path(3.0)

        # 구간 밖(2.5 m 뒤)에서만 느리다. 구간은 0.75~1.5 다.
        speed = [0.1 if x > 2.5 else 1.0 for x, _ in path]

        got = metrics.obstacle_zone_min_speed_mps(
            (0.0, 0.0), path, speed, (1.0, 0.0), 0.75, 1.5
        )

        self.assertAlmostEqual(got, 1.0)

    def test_구간에_표본이_없으면_None(self):
        # 0.5 m 에서 넘어진 에피소드. 장애물에 닿지도 못했다.
        path = straight_path(0.5)

        got = metrics.obstacle_zone_min_speed_mps(
            (0.0, 0.0), path, [1.0] * len(path), (1.0, 0.0), 0.75, 1.5
        )

        self.assertIsNone(got)

    def test_폭이_없는_구간은_None(self):
        path = straight_path(3.0)

        got = metrics.obstacle_zone_min_speed_mps(
            (0.0, 0.0), path, [1.0] * len(path), (1.0, 0.0), 0.75, 0.75
        )

        self.assertIsNone(got)

    def test_명령_속도로_나눈다(self):
        self.assertAlmostEqual(metrics.speed_drop_ratio(0.5, 1.0), 0.5)
        self.assertAlmostEqual(metrics.speed_drop_ratio(0.5, 2.0), 0.25)

    def test_안_줄였으면_1_근처(self):
        self.assertAlmostEqual(metrics.speed_drop_ratio(1.0, 1.0), 1.0)

    def test_뒤로_밀리면_음수다(self):
        # 「많이 줄였다」의 극단이지 결측이 아니다. 0 으로 자르지 않는다.
        self.assertAlmostEqual(metrics.speed_drop_ratio(-0.2, 1.0), -0.2)

    def test_최저값이_None_이면_비율도_None(self):
        self.assertIsNone(metrics.speed_drop_ratio(None, 1.0))

    def test_명령이_0이면_None(self):
        # 0 으로 나누지 않는다. 그리고 0 을 돌려주지도 않는다.
        self.assertIsNone(metrics.speed_drop_ratio(0.5, 0.0))

    def test_에피소드_열까지_이어진다(self):
        path = straight_path(3.0)
        speed = [0.25 if 0.75 <= x <= 1.5 else 1.0 for x, _ in path]

        got = metrics.episode_metrics(
            **case(
                path_xy=path,
                end_xy=(3.0, 0.0),
                command_vx=1.0,
                path_speed_mps=speed,
                obstacle_zone_m=(0.75, 1.5),
            )
        )

        self.assertAlmostEqual(got["speed_drop_ratio"], 0.25)

    def test_구간을_안_주면_열이_None(self):
        path = straight_path(3.0)

        got = metrics.episode_metrics(
            **case(
                path_xy=path,
                end_xy=(3.0, 0.0),
                path_speed_mps=[1.0] * len(path),
            )
        )

        self.assertIsNone(got["speed_drop_ratio"])


class ObstacleZoneFromConfig(unittest.TestCase):
    """장애물 구간을 **설정에서** 계산한다. 지형 이름으로 박아 두지 않는다."""

    class MeshGapTerrainCfg(object):
        platform_width = 1.5
        gap_width_range = (0.15, 0.40)

    class MeshFloatingRingTerrainCfg(object):
        platform_width = 1.5
        ring_width_range = (0.25, 0.60)

    class MeshRailsTerrainCfg(object):
        platform_width = 1.5
        rail_thickness_range = (0.08, 0.18)

    class MeshPitTerrainCfg(object):
        platform_width = 1.5
        pit_depth_range = (0.10, 0.30)

    class HfWaveTerrainCfg(object):
        pass

    class HfDiscreteObstaclesTerrainCfg(object):
        platform_width = 1.5

    TILE = 8.0

    def zone(self, cfg, difficulty=0.5):
        return terrains.obstacle_zone_m(cfg, difficulty, self.TILE)

    def test_구간_시작은_플랫폼의_절반이다(self):
        start, _, _ = self.zone(self.HfDiscreteObstaclesTerrainCfg())

        self.assertAlmostEqual(start, 0.75)

    def test_플랫폼이_없는_지형은_0에서_시작한다(self):
        # `wave` 는 물결이 타일 전체에 깔린다. 로봇 발밑도 이미 물결이다.
        start, end, basis = self.zone(self.HfWaveTerrainCfg())

        self.assertAlmostEqual(start, 0.0)
        self.assertAlmostEqual(end, 4.0)
        self.assertTrue(basis.startswith("tile_half:"))

    def test_gap_은_틈의_바깥_모서리까지다(self):
        start, end, basis = self.zone(self.MeshGapTerrainCfg())

        # 0.75 + (0.15 + 0.5 x 0.25) = 1.025
        self.assertAlmostEqual(start, 0.75)
        self.assertAlmostEqual(end, 1.025)
        self.assertEqual(basis, "gap_width_range")

    def test_floating_ring_은_고리의_바깥_모서리까지다(self):
        _, end, basis = self.zone(self.MeshFloatingRingTerrainCfg())

        # 0.75 + (0.25 + 0.5 x 0.35) = 1.175
        self.assertAlmostEqual(end, 1.175)
        self.assertEqual(basis, "ring_width_range")

    def test_rails_는_바깥_레일의_바깥_모서리까지다(self):
        _, end, basis = self.zone(self.MeshRailsTerrainCfg())

        # 안쪽 = 1.5 + (8.0 - 1.5) x 0.6 = 5.4 -> 절반 2.7, 두께 0.18 을 더해 2.88
        self.assertAlmostEqual(end, 2.88)
        self.assertEqual(basis, "rail_2_outer_edge")

    def test_pit_은_규칙이_없어_타일_절반을_쓴다(self):
        # 구덩이는 장애물이 플랫폼 가장자리의 턱 하나뿐이라, 그것으로 끝을
        # 잡으면 폭이 0 이 된다. 그래서 타일 절반이고, 근거에 그것이 남는다.
        start, end, basis = self.zone(self.MeshPitTerrainCfg())

        self.assertAlmostEqual(start, 0.75)
        self.assertAlmostEqual(end, 4.0)
        self.assertEqual(basis, "tile_half:MeshPitTerrainCfg")

    def test_모르는_설정도_죽지_않고_타일_절반을_쓴다(self):
        class SomeFutureTerrainCfg(object):
            platform_width = 2.0

        start, end, basis = self.zone(SomeFutureTerrainCfg())

        self.assertAlmostEqual(start, 1.0)
        self.assertAlmostEqual(end, 4.0)
        self.assertEqual(basis, "tile_half:SomeFutureTerrainCfg")

    def test_난이도를_올리면_구간이_넓어진다(self):
        _, easy, _ = self.zone(self.MeshGapTerrainCfg(), difficulty=0.1)
        _, hard, _ = self.zone(self.MeshGapTerrainCfg(), difficulty=0.9)

        self.assertLess(easy, hard)

    def test_구간은_언제나_시작보다_끝이_크다(self):
        for cfg in (
            self.MeshGapTerrainCfg(),
            self.MeshFloatingRingTerrainCfg(),
            self.MeshRailsTerrainCfg(),
            self.MeshPitTerrainCfg(),
            self.HfWaveTerrainCfg(),
            self.HfDiscreteObstaclesTerrainCfg(),
        ):
            for difficulty in (0.0, 0.25, 0.5, 1.0):
                with self.subTest(cfg=type(cfg).__name__, d=difficulty):
                    start, end, _ = self.zone(cfg, difficulty)

                    self.assertGreater(end, start)


if __name__ == "__main__":
    unittest.main(verbosity=2)
