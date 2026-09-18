# -*- coding: utf-8 -*-
"""`cmd_metrics.py` 시험. **2026-09-18 검증에서 잡힌 결함을 못 박는다.**

고쳤다는 것과 고쳐진 채로 남는 것은 다른 일이라, 잡힌 자리마다 시험을 건다.

**무엇을 «어떻게» 막는지 갈라 적는다.** 2회차 검증에서 이 구별을 안 해 둔 것이
걸렸다. 머리글은 넷을 다 막는다고 적었는데 실제로는 둘만 막고 있었다.

    정지 판정   계산이 틀리면 잡는다        (계산 모듈을 직접 부른다)
    낙상 집계   계산이 틀리면 잡는다        (같음)
    접지 판정   계산이 틀리면 잡는다        (같음)
    수집 경로   **구문 나무로** 막는다      (`collect_sample` 은 torch 가 필요하다)
    낙상 시각   **구문 나무로** 막는다      (Isaac 루프 안에 있다)

뒤 둘은 `eval_command_response.py` 안에 있고 그 파일은 모듈을 읽는 것만으로
`AppLauncher` 가 돌아 Isaac 없이는 import 가 안 된다. 그래서 **구문 나무를**
읽어 막는다. 값을 재는 것이 아니라 코드의 모양을 본다.

처음에는 낱말 찾기로 걸었는데 3회차 검증에서 **양쪽으로 다 뚫렸다.** 주석에
걸려 헛물고, 진짜 코드를 주석 뒤에 숨기면 못 잡았다. 구문 나무에는 주석이
없어서 둘 다 안 생긴다.

Isaac 도 GPU 도 없이 돈다.
"""

import ast
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import command_response_metrics as cmd_metrics  # noqa: E402


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

    for slot in cmd_metrics.FOOT_SLOTS:
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

        when, note = cmd_metrics.stop_time_s(rows, DT)

        self.assertIsNone(when, "한 표본으로 정지를 선언하면 안 된다")
        self.assertIsNotNone(note)

    def test_1초_내내_느리면_정지다(self):
        # 앞 50 은 빠르고 뒤 50 (= 1.0초) 은 느리다.
        rows = [make_row(i, speed=1.0) for i in range(50)]
        rows += [make_row(50 + i, speed=0.0) for i in range(50)]

        when, note = cmd_metrics.stop_time_s(rows, DT)

        self.assertIsNotNone(when, note)
        self.assertAlmostEqual(when, 50 * DT, places=6)

    def test_온전한_창이_남으면_이른_쪽을_집는다(self):
        # 100 표본 내내 느리고, 70 번에서만 명령이 잠깐 들어온다.
        # 0 ~ 49 가 명령 0 · 저속으로 «온전한 1초» 라 그 자리가 정답이다.
        rows = [make_row(i, speed=0.0) for i in range(100)]
        rows[70]["cmd_vx_mps"] = 1.0

        when, note = cmd_metrics.stop_time_s(rows, DT)

        self.assertIsNotNone(when, note)
        self.assertAlmostEqual(when, 0.0, places=6)

    def test_모든_창이_명령에_걸리면_정지가_아니다(self):
        # 60 표본 · 창 50 이라 창이 시작할 수 있는 자리는 0 ~ 10 뿐이다.
        # 30 번에 명령이 들어오면 그 열한 창이 **전부** 30 번을 품는다.
        rows = [make_row(i, speed=0.0) for i in range(60)]
        rows[30]["cmd_vx_mps"] = 1.0

        when, note = cmd_metrics.stop_time_s(rows, DT)

        self.assertIsNone(when, "명령이 다시 들어온 구간을 정지로 세면 안 된다")
        self.assertIsNotNone(note)

    def test_명령이_0_이_안_되면_사유가_남는다(self):
        rows = [make_row(i, cmd=(1.0, 0.0, 0.0), speed=1.0) for i in range(100)]

        when, note = cmd_metrics.stop_time_s(rows, DT)

        self.assertIsNone(when)
        self.assertIn("0", note)


class 낙상은모든env가분모다(unittest.TestCase):
    """검증 1번. 표본이 모자란 env 가 낙상률에서 사라지면 안 된다."""

    def test_첫스텝_낙상이_집계에_남는다(self):
        rows = [make_row(i) for i in range(100)]

        healthy = [
            cmd_metrics.episode_metrics(rows, DT, JOINTS, None)
            for _ in range(3)
        ]
        # 첫 스텝에 넘어져 표본이 한 개뿐인 env 한 대.
        fallen = [cmd_metrics.degenerate_entry(1, DT, 0.02)]

        result = cmd_metrics.aggregate(healthy, fallen, "stop", "시험")

        self.assertEqual(result["envs"], 4, "넘어진 env 도 한 대다")
        self.assertEqual(result["fell_count"], 1)
        self.assertAlmostEqual(result["fell_ratio"], 0.25)
        self.assertEqual(result["envs_with_timeseries"], 3)
        self.assertEqual(result["envs_degenerate"], 1)

    def test_전부_첫스텝에_넘어져도_낙상률이_1_이다(self):
        fallen = [cmd_metrics.degenerate_entry(1, DT, 0.02) for _ in range(4)]

        result = cmd_metrics.aggregate([], fallen, "stop", "시험")

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
            cmd_metrics.foot_slip_m(rows),
            "안 닿은 발의 이동은 미끄러짐이 아니다",
        )

    def test_닿은_채_움직이면_미끄러짐이다(self):
        rows = [
            make_row(0, contact=5.0, foot_x=0.0),
            make_row(1, contact=5.0, foot_x=0.1),
        ]

        # 발 넷이 각각 0.1 m 움직였다.
        self.assertAlmostEqual(cmd_metrics.foot_slip_m(rows), 0.4, places=5)

    def test_발_열이_비면_None_이다(self):
        rows = [make_row(0), make_row(1)]

        for slot in cmd_metrics.FOOT_SLOTS:
            rows[0]["foot_contact_{}_n".format(slot)] = None
            rows[1]["foot_contact_{}_n".format(slot)] = None

        self.assertIsNone(cmd_metrics.foot_slip_m(rows))
        self.assertIsNone(cmd_metrics.quad_stance_s(rows, DT))


class 네발동시접지(unittest.TestCase):

    def test_가장_긴_구간을_돌려준다(self):
        rows = [make_row(i, contact=5.0) for i in range(10)]
        rows[4]["foot_contact_fl_n"] = 0.0      # 한 번 끊는다

        # 0~3 이 네 칸, 5~9 가 다섯 칸. 긴 쪽은 다섯이다.
        self.assertAlmostEqual(
            cmd_metrics.quad_stance_s(rows, DT), 5 * DT, places=6
        )


class 관절목표각변화량(unittest.TestCase):
    """이 도구의 요점. 굳었는지 움직이는지를 가르는 단서."""

    def test_상수로_굳으면_0_이다(self):
        rows = [make_row(i, target=0.5) for i in range(10)]

        deltas = cmd_metrics.joint_target_deltas(rows, JOINTS)

        self.assertEqual(len(deltas), 9)
        self.assertEqual(max(deltas), 0.0)

    def test_움직이면_12관절_합이_나온다(self):
        rows = [make_row(0, target=0.0), make_row(1, target=0.1)]

        deltas = cmd_metrics.joint_target_deltas(rows, JOINTS)

        self.assertEqual(len(deltas), 1)
        self.assertAlmostEqual(deltas[0], 12 * 0.1, places=6)


class 추종비와응답곡선(unittest.TestCase):

    def test_요레이트_추종비는_뒤쪽_절반으로_낸다(self):
        # 명령 +1.0 인 구간 10칸. 앞 5칸은 과도(0.0), 뒤 5칸은 0.8.
        rows = [make_row(i, cmd=(0.0, 0.0, 1.0), wz=0.0) for i in range(5)]
        rows += [make_row(5 + i, cmd=(0.0, 0.0, 1.0), wz=0.8) for i in range(5)]

        follow = cmd_metrics.yaw_follow(rows)

        self.assertIn("+1.00", follow)
        self.assertAlmostEqual(follow["+1.00"]["ratio"], 0.8, places=5)

    def test_명령_0_은_추종비를_안_낸다(self):
        rows = [make_row(i, cmd=(0.0, 0.0, 0.0), wz=0.0) for i in range(10)]

        self.assertEqual(cmd_metrics.yaw_follow(rows), {})

    def test_응답곡선도_뒤쪽_절반이다(self):
        rows = [make_row(i, cmd=(1.0, 0.0, 0.0), vx=0.0) for i in range(5)]
        rows += [make_row(5 + i, cmd=(1.0, 0.0, 0.0), vx=0.9) for i in range(5)]

        curve = cmd_metrics.response_curve(rows)

        self.assertIn("1.00", curve)
        self.assertAlmostEqual(curve["1.00"], 0.9, places=5)


class 판정이아니다(unittest.TestCase):
    """**성공률을 만들지 마십시오.** 판정은 하네스의 네 축 AND 하나다."""

    def test_성공_이름의_열을_안_만든다(self):
        rows = [make_row(i) for i in range(50)]

        entry = cmd_metrics.episode_metrics(rows, DT, JOINTS, None)
        result = cmd_metrics.aggregate([entry], [], "stop", "시험")

        for key in list(entry) + list(result):
            self.assertNotIn(
                "success", key.lower(),
                "프로브는 성공률을 내지 않는다. 다섯째 판정축을 만들지 마십시오",
            )


class 평균은없는값을0으로안만든다(unittest.TestCase):

    def test_전부_None_이면_None_이다(self):
        self.assertIsNone(cmd_metrics.mean([None, None]))

    def test_None_을_빼고_평균한다(self):
        self.assertAlmostEqual(cmd_metrics.mean([1.0, None, 3.0]), 2.0)


if __name__ == "__main__":
    unittest.main()


HARNESS_SOURCE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "eval_command_response.py",
)


def harness_source():
    return io.open(HARNESS_SOURCE_PATH, encoding="utf-8").read()


def harness_tree():
    """하네스 원문을 **구문 나무로** 읽는다.

    낱말 찾기로 관문을 걸면 주석에 걸려 헛물고, 반대로 진짜 코드를 주석 뒤에
    숨기면 못 잡는다. 3회차 검증에서 둘 다 재현됐다. 실제로
    `fell_at[newly] = t  # 주석에 t + dt` 로 바꾸니 관문 다섯이 전부 통과했다.

    **구문 나무에는 주석이 없다.** 그래서 이 방식만 쓴다.
    """
    return ast.parse(harness_source())


def function_node(name):
    for node in ast.walk(harness_tree()):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node

    raise AssertionError("함수를 못 찾았다: {}".format(name))


def attribute_names(node):
    return {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}


class 수집경로는구문나무로막는다(unittest.TestCase):
    """`collect_sample()` 과 낙상 시각. **주석이 아니라 코드를 본다.**

    이 둘은 `torch` 와 Isaac 루프 안에 있어 여기서 돌려 볼 수가 없다. 값이
    아니라 코드의 «모양» 을 보는 관문이라는 것을 알고 건다. 되돌아가는 것만은
    막는다.
    """

    def test_발_접촉력은_이력이_아니라_지금_값을_쓴다(self):
        attrs = attribute_names(function_node("collect_sample"))

        self.assertIn(
            "net_forces_w", attrs,
            "접지는 «지금» 접촉력으로 봐야 한다. 이력 최댓값은 10 ms 앞의 힘을 "
            "끌어와 이미 뗀 발을 접지로 세게 만든다",
        )

        self.assertNotIn(
            "net_forces_w_history", attrs,
            "발 접촉력을 이력에서 끌어오는 판으로 되돌아갔다",
        )

        self.assertNotIn(
            "amax", attrs,
            "이력 축으로 amax 를 쓰면 이력 최댓값으로 되돌아간 것이다",
        )

    def test_낙상_시각은_스텝이_끝난_시각이다(self):
        """`fell_at[...] = t + dt` 여야 한다. `t` 하나면 한 스텝 빠르다."""
        assignments = []

        for node in ast.walk(harness_tree()):
            if not isinstance(node, ast.Assign):
                continue

            for target in node.targets:
                if (isinstance(target, ast.Subscript)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "fell_at"):
                    assignments.append(node.value)

        self.assertTrue(assignments, "`fell_at` 에 값을 넣는 자리가 없다")

        for value in assignments:
            self.assertIsInstance(
                value, ast.BinOp,
                "낙상 시각이 `t` 하나로 되돌아갔다. 종료는 env.step() 뒤에 "
                "확인하므로 `t + dt` 여야 한다",
            )
            self.assertIsInstance(value.op, ast.Add)

            names = {n.id for n in ast.walk(value) if isinstance(n, ast.Name)}
            self.assertEqual(
                names, {"t", "dt"},
                "낙상 시각은 `t + dt` 다. 지금은 {}".format(sorted(names)),
            )

    def test_주행_하네스를_import_하지_않는다(self):
        """불간섭. 끌어다 쓰면 그쪽 argparse 와 AppLauncher 가 함께 돈다."""
        imported = set()

        for node in ast.walk(harness_tree()):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

        for banned in ("eval_generalization", "report"):
            self.assertNotIn(
                banned, imported,
                "주행 하네스를 import 하면 불간섭이 깨진다",
            )

    def test_성공률_열을_만들지_않는다(self):
        """다섯째 판정축 금지. 문자열 상수만 본다(주석은 안 본다)."""
        literals = {
            n.value for n in ast.walk(harness_tree())
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        }

        for banned in ("overall_success", "traversal_success"):
            self.assertNotIn(
                banned, literals,
                "명령 응답 하네스는 판정을 내지 않는다. 판정은 주행 하네스의 "
                "네 축 AND 하나다",
            )

    def test_출력_폴더를_덮어쓰지_않는다(self):
        """같은 폴더에 두 번 쓰면 앞 실행의 parquet 이 남아 섞인다."""
        names = {
            n.name for n in ast.walk(harness_tree())
            if isinstance(n, ast.FunctionDef)
        }

        self.assertIn(
            "refuse_dirty_output_dir", names,
            "출력 폴더 재사용을 막는 관문이 사라졌다. 3회차 검증에서 앞 실행의 "
            "ep0002.parquet 이 남는 것이 재현됐다",
        )
