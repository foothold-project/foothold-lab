# -*- coding: utf-8 -*-
"""`probe_metrics.py` 시험. **2026-09-18 검증에서 잡힌 결함을 못 박는다.**

여기 있는 시험 가운데 넷은 실제로 있었던 결함에서 나왔다. 고쳤다는 것과
고쳐진 채로 남는 것은 다른 일이라, 그 자리마다 시험을 건다.

    정지 판정   창이 1초를 못 채워도 통과시켰다
    낙상 집계   표본이 모자란 env 를 빼서 가장 심하게 실패한 판이 사라졌다
    접지 판정   접촉력 이력 최댓값을 써서 미끄러짐이 부풀었다
    낙상 시각   스텝 시작 시각으로 적어 한 스텝 빨랐다

Isaac 도 GPU 도 없이 돈다.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import probe_metrics  # noqa: E402


JOINTS = ["j{}".format(i) for i in range(12)]
DT = 0.02


def make_row(frame, cmd=(0.0, 0.0, 0.0), speed=0.0, vx=0.0, wz=0.0,
             target=0.0, contact=5.0, foot_x=0.0, foot_y=0.0):
    """시험용 한 줄. 93열 가운데 이 모듈이 읽는 것만 채운다."""
    row = {
        "frame": frame,
        "t_s": frame * DT,
        "cmd_vx_mps": cmd[0],
        "cmd_vy_mps": cmd[1],
        "cmd_wz_rps": cmd[2],
        "vx_mps": vx,
        "vy_mps": 0.0,
        "speed_mps": speed,
        "base_wz_rps": wz,
        "pitch_deg": 0.0,
        "roll_deg": 0.0,
        "base_z_m": 0.32,
    }

    for slot in probe_metrics.FOOT_SLOTS:
        row["foot_x_{}_m".format(slot)] = foot_x
        row["foot_y_{}_m".format(slot)] = foot_y
        row["foot_contact_{}_n".format(slot)] = contact

    for name in JOINTS:
        row["joint_target_{}".format(name)] = target

    return row


class 정지판정은창을온전히채워야한다(unittest.TestCase):
    """검증 2번. 마지막 한 표본만 느려도 «멈췄다» 가 되면 안 된다."""

    def test_마지막_한_표본만_느리면_정지가_아니다(self):
        # 100 표본 내내 명령 0 인데 속도는 마지막 하나만 0 이다.
        rows = [make_row(i, speed=1.0) for i in range(99)]
        rows.append(make_row(99, speed=0.0))

        when, note = probe_metrics.stop_time_s(rows, DT)

        self.assertIsNone(when, "한 표본으로 정지를 선언하면 안 된다")
        self.assertIsNotNone(note)

    def test_1초_내내_느리면_정지다(self):
        # 앞 50 은 빠르고 뒤 50 (= 1.0초) 은 느리다.
        rows = [make_row(i, speed=1.0) for i in range(50)]
        rows += [make_row(50 + i, speed=0.0) for i in range(50)]

        when, note = probe_metrics.stop_time_s(rows, DT)

        self.assertIsNotNone(when, note)
        self.assertAlmostEqual(when, 50 * DT, places=6)

    def test_온전한_창이_남으면_이른_쪽을_집는다(self):
        # 100 표본 내내 느리고, 70 번에서만 명령이 잠깐 들어온다.
        # 0 ~ 49 가 명령 0 · 저속으로 «온전한 1초» 라 그 자리가 정답이다.
        rows = [make_row(i, speed=0.0) for i in range(100)]
        rows[70]["cmd_vx_mps"] = 1.0

        when, note = probe_metrics.stop_time_s(rows, DT)

        self.assertIsNotNone(when, note)
        self.assertAlmostEqual(when, 0.0, places=6)

    def test_모든_창이_명령에_걸리면_정지가_아니다(self):
        # 60 표본 · 창 50 이라 창이 시작할 수 있는 자리는 0 ~ 10 뿐이다.
        # 30 번에 명령이 들어오면 그 열한 창이 **전부** 30 번을 품는다.
        rows = [make_row(i, speed=0.0) for i in range(60)]
        rows[30]["cmd_vx_mps"] = 1.0

        when, note = probe_metrics.stop_time_s(rows, DT)

        self.assertIsNone(when, "명령이 다시 들어온 구간을 정지로 세면 안 된다")
        self.assertIsNotNone(note)

    def test_명령이_0_이_안_되면_사유가_남는다(self):
        rows = [make_row(i, cmd=(1.0, 0.0, 0.0), speed=1.0) for i in range(100)]

        when, note = probe_metrics.stop_time_s(rows, DT)

        self.assertIsNone(when)
        self.assertIn("0", note)


class 낙상은모든env가분모다(unittest.TestCase):
    """검증 1번. 표본이 모자란 env 가 낙상률에서 사라지면 안 된다."""

    def test_첫스텝_낙상이_집계에_남는다(self):
        rows = [make_row(i) for i in range(100)]

        healthy = [
            probe_metrics.episode_metrics(rows, DT, JOINTS, None)
            for _ in range(3)
        ]
        # 첫 스텝에 넘어져 표본이 한 개뿐인 env 한 대.
        fallen = [probe_metrics.degenerate_entry(1, DT, 0.02)]

        result = probe_metrics.aggregate(healthy, fallen, "stop", "시험")

        self.assertEqual(result["envs"], 4, "넘어진 env 도 한 대다")
        self.assertEqual(result["fell_count"], 1)
        self.assertAlmostEqual(result["fell_ratio"], 0.25)
        self.assertEqual(result["envs_with_timeseries"], 3)
        self.assertEqual(result["envs_degenerate"], 1)

    def test_전부_첫스텝에_넘어져도_낙상률이_1_이다(self):
        fallen = [probe_metrics.degenerate_entry(1, DT, 0.02) for _ in range(4)]

        result = probe_metrics.aggregate([], fallen, "stop", "시험")

        self.assertEqual(result["envs"], 4)
        self.assertAlmostEqual(result["fell_ratio"], 1.0)


class 접지는지금힘으로본다(unittest.TestCase):
    """검증 3번. 안 닿은 발을 닿았다고 세면 미끄러짐이 부푼다."""

    def test_접촉력이_문턱_아래면_미끄러짐에_안_센다(self):
        rows = [
            make_row(0, contact=0.0, foot_x=0.0),
            make_row(1, contact=0.0, foot_x=0.1),
        ]

        self.assertIsNone(
            probe_metrics.foot_slip_m(rows),
            "안 닿은 발의 이동은 미끄러짐이 아니다",
        )

    def test_닿은_채_움직이면_미끄러짐이다(self):
        rows = [
            make_row(0, contact=5.0, foot_x=0.0),
            make_row(1, contact=5.0, foot_x=0.1),
        ]

        # 발 넷이 각각 0.1 m 움직였다.
        self.assertAlmostEqual(probe_metrics.foot_slip_m(rows), 0.4, places=5)

    def test_발_열이_비면_None_이다(self):
        rows = [make_row(0), make_row(1)]

        for slot in probe_metrics.FOOT_SLOTS:
            rows[0]["foot_contact_{}_n".format(slot)] = None
            rows[1]["foot_contact_{}_n".format(slot)] = None

        self.assertIsNone(probe_metrics.foot_slip_m(rows))
        self.assertIsNone(probe_metrics.quad_stance_s(rows, DT))


class 네발동시접지(unittest.TestCase):

    def test_가장_긴_구간을_돌려준다(self):
        rows = [make_row(i, contact=5.0) for i in range(10)]
        rows[4]["foot_contact_fl_n"] = 0.0      # 한 번 끊는다

        # 0~3 이 네 칸, 5~9 가 다섯 칸. 긴 쪽은 다섯이다.
        self.assertAlmostEqual(
            probe_metrics.quad_stance_s(rows, DT), 5 * DT, places=6
        )


class 관절목표각변화량(unittest.TestCase):
    """이 도구의 요점. 굳었는지 움직이는지를 가르는 단서."""

    def test_상수로_굳으면_0_이다(self):
        rows = [make_row(i, target=0.5) for i in range(10)]

        deltas = probe_metrics.joint_target_deltas(rows, JOINTS)

        self.assertEqual(len(deltas), 9)
        self.assertEqual(max(deltas), 0.0)

    def test_움직이면_12관절_합이_나온다(self):
        rows = [make_row(0, target=0.0), make_row(1, target=0.1)]

        deltas = probe_metrics.joint_target_deltas(rows, JOINTS)

        self.assertEqual(len(deltas), 1)
        self.assertAlmostEqual(deltas[0], 12 * 0.1, places=6)


class 추종비와응답곡선(unittest.TestCase):

    def test_요레이트_추종비는_뒤쪽_절반으로_낸다(self):
        # 명령 +1.0 인 구간 10칸. 앞 5칸은 과도(0.0), 뒤 5칸은 0.8.
        rows = [make_row(i, cmd=(0.0, 0.0, 1.0), wz=0.0) for i in range(5)]
        rows += [make_row(5 + i, cmd=(0.0, 0.0, 1.0), wz=0.8) for i in range(5)]

        follow = probe_metrics.yaw_follow(rows)

        self.assertIn("+1.00", follow)
        self.assertAlmostEqual(follow["+1.00"]["ratio"], 0.8, places=5)

    def test_명령_0_은_추종비를_안_낸다(self):
        rows = [make_row(i, cmd=(0.0, 0.0, 0.0), wz=0.0) for i in range(10)]

        self.assertEqual(probe_metrics.yaw_follow(rows), {})

    def test_응답곡선도_뒤쪽_절반이다(self):
        rows = [make_row(i, cmd=(1.0, 0.0, 0.0), vx=0.0) for i in range(5)]
        rows += [make_row(5 + i, cmd=(1.0, 0.0, 0.0), vx=0.9) for i in range(5)]

        curve = probe_metrics.response_curve(rows)

        self.assertIn("1.00", curve)
        self.assertAlmostEqual(curve["1.00"], 0.9, places=5)


class 판정이아니다(unittest.TestCase):
    """**성공률을 만들지 마십시오.** 판정은 하네스의 네 축 AND 하나다."""

    def test_성공_이름의_열을_안_만든다(self):
        rows = [make_row(i) for i in range(50)]

        entry = probe_metrics.episode_metrics(rows, DT, JOINTS, None)
        result = probe_metrics.aggregate([entry], [], "stop", "시험")

        for key in list(entry) + list(result):
            self.assertNotIn(
                "success", key.lower(),
                "프로브는 성공률을 내지 않는다. 다섯째 판정축을 만들지 마십시오",
            )


class 평균은없는값을0으로안만든다(unittest.TestCase):

    def test_전부_None_이면_None_이다(self):
        self.assertIsNone(probe_metrics.mean([None, None]))

    def test_None_을_빼고_평균한다(self):
        self.assertAlmostEqual(probe_metrics.mean([1.0, None, 3.0]), 2.0)


if __name__ == "__main__":
    unittest.main()
