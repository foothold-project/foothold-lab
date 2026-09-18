# -*- coding: utf-8 -*-
"""`probe_metrics.py` 시험. **2026-09-18 검증에서 잡힌 결함을 못 박는다.**

고쳤다는 것과 고쳐진 채로 남는 것은 다른 일이라, 잡힌 자리마다 시험을 건다.

**무엇을 «어떻게» 막는지 갈라 적는다.** 2회차 검증에서 이 구별을 안 해 둔 것이
걸렸다. 머리글은 넷을 다 막는다고 적었는데 실제로는 둘만 막고 있었다.

    정지 판정   계산이 틀리면 잡는다        (`probe_metrics` 를 직접 부른다)
    낙상 집계   계산이 틀리면 잡는다        (같음)
    접지 판정   계산이 틀리면 잡는다        (같음)
    수집 경로   **원문 검사로만** 막는다    (`collect_sample` 은 torch 가 필요하다)
    낙상 시각   **원문 검사로만** 막는다    (Isaac 루프 안에 있다)

뒤 둘은 `probe_command_response.py` 안에 있고 그 파일은 모듈을 읽는 것만으로
`AppLauncher` 가 돌아 Isaac 없이는 import 가 안 된다. 그래서 **원문을 읽어**
막는다. 값을 재는 것이 아니라 코드가 그 자리에 있는지만 본다. 약한 관문이지만
없는 것보다 낫고, 약하다는 것을 여기 적어 둔다.

Isaac 도 GPU 도 없이 돈다.
"""

import io
import os
import re
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


PROBE_SOURCE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "probe_command_response.py",
)


def probe_source():
    return io.open(PROBE_SOURCE_PATH, encoding="utf-8").read()


def probe_function_body(name):
    """`probe_command_response.py` 의 함수 하나만 원문으로 잘라 온다.

    파일 전체를 훑으면 **주석에 적힌 낱말까지 걸린다.** 실제로 그렇게 한 번
    헛걸렸다. 「무엇을 안 쓴다」를 볼 때는 반드시 함수 몸통만 본다.
    """
    source = probe_source()
    start = source.index("def {}(".format(name))
    rest = source[start:]
    end = rest.find(chr(10) + "def ")

    return rest if end == -1 else rest[:end]


class 수집경로는원문으로막는다(unittest.TestCase):
    """`collect_sample()` 과 낙상 시각. **값이 아니라 코드 자리를 본다.**

    이 둘은 `torch` 와 Isaac 루프 안에 있어 여기서 돌려 볼 수가 없다. 약한
    관문이라는 것을 알고 건다. 되돌아가는 것만은 막는다.
    """

    def test_발_접촉력은_이력이_아니라_지금_값을_쓴다(self):
        collect = probe_function_body("collect_sample")

        self.assertIn(
            "contact_sensor.data.net_forces_w[:, foot_sensor_slots, :]",
            collect,
            "접지는 «지금» 접촉력으로 봐야 한다. 이력 최댓값은 10 ms 앞의 "
            "힘을 끌어와 이미 뗀 발을 접지로 세게 만든다",
        )

    def test_발_접촉력에_이력과_amax_를_다시_안_쓴다(self):
        collect = probe_function_body("collect_sample")

        # 주석은 빼고 코드 줄만 본다. 머리글이 이력 이야기를 «설명» 하기 때문이다.
        code = chr(10).join(
            line for line in collect.split(chr(10))
            if not line.lstrip().startswith("#")
        )

        for banned in ("net_forces_w_history", "amax"):
            self.assertNotIn(
                banned, code,
                "`collect_sample()` 이 발 접촉력을 이력에서 끌어오는 판으로 "
                "되돌아갔다",
            )

    def test_낙상_시각은_스텝이_끝난_시각이다(self):
        source = probe_source()

        self.assertIn(
            "fell_at[newly] = t + dt", source,
            "종료는 env.step() 뒤에 확인하므로 t 가 아니라 t + dt 다. "
            "t 로 적으면 첫 스텝 낙상이 0.00 초가 된다",
        )

        self.assertNotIn(
            "fell_at[newly] = t" + chr(10), source,
            "낙상 시각이 한 스텝 빠른 판으로 되돌아갔다",
        )

    def test_판정_하네스를_import_하지_않는다(self):
        """프로브가 판정 경로를 끌어다 쓰면 불간섭이 깨진다."""
        source = probe_source()

        self.assertNotIn(
            "import eval_generalization", source,
            "판정 하네스를 import 하면 그 파일의 argparse 와 AppLauncher 가 "
            "함께 돈다. 불간섭이 깨진다",
        )

    def test_성공률_열을_만들지_않는다(self):
        """다섯째 판정축 금지. `sim/eval/README.md` 의 못이다."""
        source = probe_source()

        for banned in ("overall_success", "traversal_success"):
            self.assertNotIn(
                banned, source,
                "프로브는 판정을 내지 않는다. 판정은 하네스의 네 축 AND 하나다",
            )
