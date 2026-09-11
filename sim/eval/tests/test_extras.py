"""더한 열의 계산을 알려진 답으로 못 박는다. `sim/eval/extras.py`.

    python -m pytest sim/eval/tests/test_extras.py

## 여기서 지키는 것

| 시험 | 막는 사고 |
|---|---|
| 백분위 | numpy 없이 만든 식이 조용히 다른 값을 내는 것 |
| 접촉 네 값 | 「닿은 횟수」가 스텝 수를 세어 버리는 것 |
| 미끄러짐 | 공중에 뜬 구간의 이동을 미끄러짐으로 세는 것 |
| 참여도 | 평지에서 0/0 을 1 로 읽어 「완벽히 넘었다」가 되는 것 |
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.dirname(HERE)

if EVAL_DIR not in sys.path:
    sys.path.insert(0, EVAL_DIR)

import extras  # noqa: E402


class PercentileTest(unittest.TestCase):
    def test_알려진_답(self):
        # numpy.percentile([1,2,3,4], 95) == 3.85
        self.assertAlmostEqual(extras.percentile([1, 2, 3, 4], 95), 3.85)
        self.assertAlmostEqual(extras.percentile([1, 2, 3, 4], 50), 2.5)
        self.assertAlmostEqual(extras.percentile([1, 2, 3, 4], 0), 1.0)
        self.assertAlmostEqual(extras.percentile([1, 2, 3, 4], 100), 4.0)

    def test_하나뿐이면_그것(self):
        self.assertEqual(extras.percentile([7.5], 95), 7.5)

    def test_비면_None(self):
        self.assertIsNone(extras.percentile([], 95))
        self.assertIsNone(extras.percentile([None, None], 95))

    def test_None_은_걸러진다(self):
        self.assertAlmostEqual(extras.percentile([1, None, 2, 3, 4], 50), 2.5)


class RmsTest(unittest.TestCase):
    def test_알려진_답(self):
        # 3, 4 의 RMS = sqrt((9+16)/2) = 3.5355...
        self.assertAlmostEqual(extras.rms_from_sum_sq(9 + 16, 2), 3.5355339059327378)

    def test_개수가_0_이면_None(self):
        self.assertIsNone(extras.rms_from_sum_sq(0.0, 0))


class ReliefTest(unittest.TestCase):
    def test_기복(self):
        self.assertAlmostEqual(extras.relief_m(-0.2, 0.3), 0.5)

    def test_평지는_0(self):
        self.assertAlmostEqual(extras.relief_m(0.0, 0.0), 0.0)

    def test_없으면_None(self):
        self.assertIsNone(extras.relief_m(None, 0.3))
        self.assertIsNone(extras.relief_m(float("inf"), 0.3))


class EngagementTest(unittest.TestCase):
    def test_다_넘었으면_1(self):
        self.assertAlmostEqual(extras.engagement_ratio(0.10, 0.10), 1.0)

    def test_비켜_갔으면_0_에_가깝다(self):
        # star 실측: 주변 기복 0.105, 발이 탄 것은 걸음걸이뿐
        self.assertLess(extras.engagement_ratio(0.005, 0.105), 0.1)

    def test_평지면_묻지_않는다(self):
        """**0/0 을 1 로 읽으면 거꾸로 말한다.**

        넘을 것이 없었는데 「완벽히 넘었다」가 되어 버린다.
        """
        self.assertIsNone(extras.engagement_ratio(0.0, 0.0))
        self.assertIsNone(extras.engagement_ratio(0.001, 0.005))

    def test_1_을_넘지_않는다(self):
        self.assertAlmostEqual(extras.engagement_ratio(0.50, 0.10), 1.0)


class ContactTest(unittest.TestCase):
    DT = 0.02

    def test_한_번_닿았다_떨어진다(self):
        forces = [0.0, 0.0, 5.0, 8.0, 3.0, 0.0, 0.0]
        got = extras.contact_summary(forces, self.DT)

        self.assertAlmostEqual(got["peak_force_n"], 8.0)
        self.assertEqual(got["contact_events"], 1)
        self.assertAlmostEqual(got["contact_time_s"], 3 * self.DT)
        self.assertAlmostEqual(got["impulse_proxy_ns"], (5.0 + 8.0 + 3.0) * self.DT)

    def test_닿은_횟수는_스텝_수가_아니다(self):
        """**여기가 틀리기 쉽다.** 닿아 있는 동안 매 스텝을 세면 안 된다."""
        forces = [5.0] * 50
        self.assertEqual(extras.contact_summary(forces, self.DT)["contact_events"], 1)

    def test_두_번_닿으면_둘(self):
        forces = [5.0, 0.0, 5.0]
        self.assertEqual(extras.contact_summary(forces, self.DT)["contact_events"], 2)

    def test_문턱_이하는_안_센다(self):
        forces = [0.5, 0.9, 0.2]
        got = extras.contact_summary(forces, self.DT)

        self.assertEqual(got["contact_events"], 0)
        self.assertAlmostEqual(got["contact_time_s"], 0.0)
        self.assertAlmostEqual(got["impulse_proxy_ns"], 0.0)
        # 최댓값은 문턱과 무관하게 그대로 남는다. 나중에 문턱을 바꿔
        # 되짚을 수 있어야 하기 때문이다.
        self.assertAlmostEqual(got["peak_force_n"], 0.9)

    def test_비면_전부_None(self):
        got = extras.contact_summary([], self.DT)
        self.assertTrue(all(v is None for v in got.values()))


class SlipTest(unittest.TestCase):
    def test_닿은_채_움직이면_센다(self):
        pos = [(0.0, 0.0), (0.03, 0.0), (0.07, 0.0)]
        con = [5.0, 5.0, 5.0]
        self.assertAlmostEqual(extras.foot_slip_m(pos, con), 0.07)

    def test_공중_이동은_안_센다(self):
        """발이 떠 있을 때의 이동은 미끄러짐이 아니라 «걸음» 이다."""
        pos = [(0.0, 0.0), (0.30, 0.0), (0.60, 0.0)]
        con = [0.0, 0.0, 0.0]
        self.assertAlmostEqual(extras.foot_slip_m(pos, con), 0.0)

    def test_착지_순간은_안_센다(self):
        """직전이 공중이면 그 구간은 안 센다. 연속으로 닿아 있어야 한다."""
        pos = [(0.0, 0.0), (0.30, 0.0), (0.31, 0.0)]
        con = [0.0, 5.0, 5.0]
        self.assertAlmostEqual(extras.foot_slip_m(pos, con), 0.01)

    def test_길이가_다르면_None(self):
        self.assertIsNone(extras.foot_slip_m([(0.0, 0.0)], [1.0, 2.0]))


class EpisodeIdTest(unittest.TestCase):
    def test_모양(self):
        self.assertEqual(extras.episode_id("gap", 2, 0.5, 1.0, 7),
                         "gap_s2_d0.50_v1.0_e007")


class ColumnTest(unittest.TestCase):
    def test_묶음별_개수(self):
        self.assertEqual(len(extras.POSTURE_COLUMNS), 8)
        self.assertEqual(len(extras.CONTACT_COLUMNS), 16)
        self.assertEqual(len(extras.ENGAGEMENT_COLUMNS), 3)
        self.assertEqual(len(extras.TRACE_COLUMNS), 5)
        self.assertEqual(len(extras.FOOTHOLD_V1_COLUMNS), 32)

    def test_겹치는_이름이_없다(self):
        self.assertEqual(len(extras.FOOTHOLD_V1_COLUMNS), len(set(extras.FOOTHOLD_V1_COLUMNS)))

    def test_접촉_열_이름(self):
        self.assertIn("foot_peak_force_n", extras.CONTACT_COLUMNS)
        self.assertIn("thigh_contact_events", extras.CONTACT_COLUMNS)
        self.assertIn("calf_impulse_proxy_ns", extras.CONTACT_COLUMNS)
        self.assertIn("base_contact_time_s", extras.CONTACT_COLUMNS)


if __name__ == "__main__":
    unittest.main()
