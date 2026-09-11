"""겹쳐 그리기 도구를 못 박는다. `sim/eval/overlay/`.

    python -m unittest discover -s sim/eval/tests -v

## 무엇이 어디까지 돌아가나

`trace.py` 는 **표준 라이브러리만** 씁니다. 그래서 아래 `TraceTest` 무리는
어느 PC 에서나 돕니다. `hud.py` 는 Pillow 를, `render.py` 는 PyAV 를 쓰므로
그 둘이 없으면 해당 시험만 건너뜁니다.

**건너뛴 것을 통과로 보고하지 않습니다.** `unittest` 가 skip 을 따로 셉니다.

## 여기서 지키는 것

| 시험 | 막는 사고 |
|---|---|
| 접었다 펴기 | trace 를 접은 값이 판정 표와 다른 채로 영상에 나가는 것 |
| 줄 번호 · 시각 대조 | 줄이 빠진 trace 로 그려 값이 통째로 밀리는 것 |
| 글꼴 글자 대조 | 라벨을 더하고 글꼴을 안 구워 화면에 네모가 나오는 것 |
| 짝 검사 | 다른 판의 영상과 trace 를 붙여 그리는 것 |
| 자리 검사 | 글자가 패널 밖으로 나가 잘리는 것 |
"""

import io
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.dirname(HERE)

for path in (EVAL_DIR, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

from overlay import trace as trace_mod  # noqa: E402

try:
    from overlay import hud as hud_mod
except ImportError:  # pragma: no cover
    hud_mod = None

try:
    import av  # noqa: F401

    HAS_AV = True
except ImportError:  # pragma: no cover
    HAS_AV = False


DT = 0.02
FPS = 50


def make_meta(**extra):
    meta = {
        "terrain": "pit",
        "env_id": 44,
        "episode": 1,
        "fps": FPS,
        "dt_s": DT,
        "command_vx_mps": 1.0,
        "eval_duration_s": 6.0,
        "gate_m": 3.0,
        "min_progress_m": 3.0,
        "max_lateral_drift_m": 0.75,
        "max_velocity_mae_mps": 0.25,
        "termination_reason": "timeout",
    }
    meta.update(extra)

    return meta


def make_rows(speeds, lats=None, fwd_step=None):
    """속도 목록에서 trace 줄을 만든다. 전진은 속도를 적분한 값으로 둔다."""
    rows = []
    fwd = 0.0
    lat_values = lats or [0.0] * len(speeds)

    for index, speed in enumerate(speeds):
        rows.append({
            "frame": index,
            "t_s": round(index * DT, 6),
            "cmd_vx_mps": 1.0,
            "vx_mps": speed,
            "vy_mps": 0.0,
            "speed_mps": speed,
            "vel_err_mps": abs(1.0 - speed),
            "fwd_m": fwd,
            "lat_m": lat_values[index],
            "base_z_m": 0.32,
            "pitch_deg": 0.0,
            "roll_deg": 0.0,
            "yaw_deg": 0.0,
            "foot_z_fl_m": 0.05,
            "foot_z_fr_m": 0.05,
            "foot_z_rl_m": 0.05,
            "foot_z_rr_m": 0.05,
        })

        fwd += (fwd_step if fwd_step is not None else speed) * DT

    return rows


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="foothold-overlay-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def path(self, name):
        return os.path.join(self.tmp, name)


class TraceRoundTripTest(TempDirTest):
    """쓴 것을 그대로 되읽는가."""

    def test_write_then_read(self):
        rows = make_rows([0.5] * 10)
        target = self.path("t.csv")

        trace_mod.write(target, make_meta(), rows)
        got = trace_mod.read(target)

        self.assertEqual(len(got), 10)
        self.assertEqual(got.meta["terrain"], "pit")
        self.assertEqual(got.meta["env_id"], 44)
        self.assertAlmostEqual(got.fps, 50.0)
        self.assertAlmostEqual(got.dt_s, DT)
        self.assertAlmostEqual(got.duration_s, 0.2)
        self.assertAlmostEqual(got.rows[3]["speed_mps"], 0.5)

    def test_blank_column_stays_none(self):
        """안 잰 열은 0 이 아니라 빈 칸이어야 한다.

        0 으로 채우면 「쟀는데 0 이었다」와 구별이 안 됩니다.
        """
        rows = make_rows([0.5] * 3)

        for row in rows:
            del row["foot_z_fl_m"]

        target = self.path("t.csv")
        trace_mod.write(target, make_meta(), rows)

        got = trace_mod.read(target)

        self.assertIsNone(got.rows[0]["foot_z_fl_m"])
        self.assertIsNotNone(got.rows[0]["foot_z_fr_m"])

    def test_등록_안_된_열은_거부한다(self):
        """새 열을 조용히 버리지 않는가.

        예전에는 `extrasaction="ignore"` 라 등록 안 된 열이 소리 없이
        사라졌습니다. 재서 넣어도 파일에는 없고 아무도 모릅니다.
        `yaw_deg` 를 넣었는데 안 나온 것이 그 때문이었습니다 (2026-09-11).
        """
        rows = make_rows([0.5] * 3)

        for row in rows:
            row["아무도_등록_안_한_열"] = 1.0

        with self.assertRaises(trace_mod.TraceError) as caught:
            trace_mod.write(self.path("t.csv"), make_meta(), rows)

        self.assertIn("아무도_등록_안_한_열", str(caught.exception))

    def test_yaw_는_왕복한다(self):
        """`yaw_deg` 가 실제로 파일에 들어갔다 나오는가.

        열을 등록만 하고 왕복을 안 재면, 쓰기와 읽기 어느 한쪽만 알아도
        통과해 버립니다. 알려진 답으로 시험합니다.
        """
        rows = make_rows([0.5] * 4)

        for index, row in enumerate(rows):
            row["yaw_deg"] = -12.5 + index

        target = self.path("t.csv")
        trace_mod.write(target, make_meta(), rows)

        self.assertIn("yaw_deg", io.open(target, encoding="utf-8").read())

        got = trace_mod.read(target)

        self.assertAlmostEqual(got.rows[0]["yaw_deg"], -12.5)
        self.assertAlmostEqual(got.rows[3]["yaw_deg"], -9.5)

    def make_v1_file(self, path, rows):
        """손으로 `foothold-trace/1` 파일을 만든다.

        `write()` 로는 못 만든다. 그 함수는 언제나 지금 판만 쓴다. 옛 판
        파일은 «그때 그 코드» 가 만든 것이라 여기서도 그대로 흉내 낸다.
        """
        columns = [c for c in trace_mod.TRACE_COLUMNS if c != "yaw_deg"]

        with io.open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write("# schema = foothold-trace/1" + chr(10))

            for key in sorted(make_meta()):
                handle.write("# {} = {}".format(key, make_meta()[key]) + chr(10))

            handle.write(",".join(columns) + chr(10))

            for row in rows:
                handle.write(",".join(
                    "" if row.get(c) is None else repr(row[c])
                    for c in columns) + chr(10))

        return path

    def test_옛_판_trace_를_읽는다(self):
        """`foothold-trace/1` 로 쓴 파일이 여전히 읽혀야 한다.

        판을 `/2` 로 올리면서 이미 저장소에 있던 trace 하나를 못 읽게 만들었다.
        `sim/eval/overlay/README.md` 의 공식 예제가 그 파일을 쓴다
        (2026-09-11 6차 검증이 잡음).

        /1 과 /2 의 차이는 «열이 하나 늘었다» 뿐이다. 없는 열은 `None` 으로
        온다. 이 형식에서 빈 칸은 원래 「안 쟀다」는 뜻이다.
        """
        rows = make_rows([0.5] * 5)
        target = self.make_v1_file(self.path("old.csv"), rows)

        # 파일에 `yaw_deg` 가 정말 없어야 시험이 뜻을 갖는다.
        self.assertNotIn("yaw_deg", io.open(target, encoding="utf-8").read())

        got = trace_mod.read(target)

        self.assertEqual(len(got), 5)
        self.assertEqual(got.schema, "foothold-trace/1")
        self.assertEqual(got.absent_columns, ("yaw_deg",))

        # **`.get()` 이 아니라 `[...]` 로도 물을 수 있어야 한다.**
        # 키를 아예 빼 두면 읽는 쪽이 KeyError 로 죽는다.
        self.assertIsNone(got.rows[0]["yaw_deg"])
        self.assertTrue(all(v is None for v in got.column("yaw_deg")))

        # 나머지 열은 멀쩡해야 한다.
        self.assertAlmostEqual(got.rows[3]["speed_mps"], 0.5)

    def test_옛_판을_새로_쓰지_못한다(self):
        """`write()` 가 자기가 안 쓰는 판 이름을 적지 못하게 한다.

        예전에는 `schema` 만 옛 판으로 주면 내용은 새 판인데 이름만 옛 판인
        파일이 나왔다. 읽는 쪽이 그것을 거부하므로 조용히 틀리지는 않았지만,
        애초에 만들 수 없어야 맞다.
        """
        meta = dict(make_meta())
        meta["schema"] = "foothold-trace/1"

        with self.assertRaises(trace_mod.TraceError) as caught:
            trace_mod.write(self.path("nope.csv"), meta, make_rows([0.5] * 3))

        self.assertIn("foothold-trace/1", str(caught.exception))

    def test_모르는_판은_여전히_거부한다(self):
        """옛 판을 받아 준다고 «아무 판이나» 받는 것은 아니다."""
        target = self.path("future.csv")
        trace_mod.write(self.path("now.csv"), make_meta(), make_rows([0.5] * 3))
        text = io.open(self.path("now.csv"), encoding="utf-8").read()
        io.open(target, "w", encoding="utf-8").write(
            text.replace("foothold-trace/2", "foothold-trace/99", 1))

        with self.assertRaises(trace_mod.TraceError) as caught:
            trace_mod.read(target)

        self.assertIn("foothold-trace/99", str(caught.exception))

    def test_판_이름과_내용이_다르면_거부한다(self):
        """/1 이라 적어 놓고 `yaw_deg` 가 들어 있으면 거짓말이다."""
        # /1 이라고 적어 놓고 열은 /2 로 쓴다. 손으로 만든다.
        target = self.path("liar.csv")
        trace_mod.write(self.path("real.csv"), make_meta(), make_rows([0.5] * 3))
        text = io.open(self.path("real.csv"), encoding="utf-8").read()
        io.open(target, "w", encoding="utf-8").write(
            text.replace("foothold-trace/2", "foothold-trace/1", 1))

        with self.assertRaises(trace_mod.TraceError) as caught:
            trace_mod.read(target)

        self.assertIn("yaw_deg", str(caught.exception))

    def test_missing_row_is_caught(self):
        """줄이 빠지면 읽는 자리에서 죽어야 한다. 조용히 밀리면 안 된다."""
        rows = make_rows([0.5] * 10)
        target = self.path("t.csv")

        trace_mod.write(target, make_meta(), rows)

        with io.open(target, encoding="utf-8") as handle:
            lines = handle.read().splitlines(True)

        # 머리말과 열 이름 줄을 지나 **데이터 줄** 하나를 지운다.
        # 아무 줄이나 지우면 메타 줄이 빠져도 시험이 통과해 버린다.
        header = next(i for i, line in enumerate(lines)
                      if line.startswith("frame,"))

        del lines[header + 5]

        with io.open(target, "w", encoding="utf-8") as handle:
            handle.writelines(lines)

        with self.assertRaises(trace_mod.TraceError):
            trace_mod.read(target)

    def test_wrong_schema_is_caught(self):
        rows = make_rows([0.5] * 3)
        target = self.path("t.csv")

        trace_mod.write(target, make_meta(), rows)

        with io.open(target, encoding="utf-8") as handle:
            text = handle.read().replace(trace_mod.SCHEMA, "something-else/9")

        with io.open(target, "w", encoding="utf-8") as handle:
            handle.write(text)

        with self.assertRaises(trace_mod.TraceError):
            trace_mod.read(target)


class FoldBackTest(unittest.TestCase):
    """**trace 를 접으면 판정 표의 그 줄이 나오는가.**

    답을 아는 입력을 넣고 봅니다. 이 시험이 곧 `record_flat_baseline.py` 안의
    `TRACE vs REPLAY` 대조와 같은 식입니다.
    """

    def test_known_answer(self):
        speeds = [0.4, 0.6, 1.0, 0.0]
        lats = [0.0, -0.3, 0.5, -0.2]

        rows = make_rows(speeds, lats=lats)
        trace = trace_mod.Trace(make_meta(), rows)

        # 손으로 낸 값. `make_rows` 가 전진을 속도로 적분한다.
        expected_fwd = (0.4 + 0.6 + 1.0) * DT
        expected_mae = sum(abs(1.0 - s) for s in speeds) / len(speeds)

        row = {
            "duration_s": len(speeds) * DT,
            "forward_progress_m": expected_fwd,
            "lateral_drift_m": abs(lats[-1]),
            "peak_lateral_drift_m": 0.5,
            "velocity_mae_mps": expected_mae,
        }

        checks = trace_mod.verify_against_row(trace, row)

        self.assertEqual(len(checks), 5)

        for name, want, got, delta, ok in checks:
            self.assertTrue(ok, "{}: 표 {} · trace {} (차이 {})".format(
                name, want, got, delta))

    def test_mismatch_is_reported(self):
        rows = make_rows([1.0] * 4)
        trace = trace_mod.Trace(make_meta(), rows)

        row = {
            "duration_s": 0.08,
            "forward_progress_m": 99.0,
            "lateral_drift_m": 0.0,
            "peak_lateral_drift_m": 0.0,
            "velocity_mae_mps": 0.0,
        }

        failed = [c[0] for c in trace_mod.verify_against_row(trace, row) if not c[4]]

        self.assertIn("forward_progress_m", failed)


class SlowdownTest(unittest.TestCase):
    """주춤 구간을 답을 아는 신호로 시험한다."""

    def test_one_span(self):
        # 0.2초 빠르게, 0.4초 느리게, 0.2초 빠르게.
        speeds = [1.0] * 10 + [0.2] * 20 + [1.0] * 10
        trace = trace_mod.Trace(make_meta(), make_rows(speeds))

        spans = trace_mod.slowdown_spans(trace, ratio=0.6, min_duration_s=0.15)

        self.assertEqual(len(spans), 1)

        start, end, lowest = spans[0]

        self.assertAlmostEqual(start, 0.2, places=6)
        self.assertAlmostEqual(end, 0.6, places=6)
        self.assertAlmostEqual(lowest, 0.2, places=6)

    def test_too_short_is_ignored(self):
        """한 걸음짜리 흔들림을 구간으로 세면 안 된다."""
        speeds = [1.0] * 10 + [0.2] * 3 + [1.0] * 10
        trace = trace_mod.Trace(make_meta(), make_rows(speeds))

        self.assertEqual(trace_mod.slowdown_spans(trace), [])

    def test_span_open_at_the_end(self):
        """끝까지 느린 채로 판이 끝나도 한 구간이다."""
        speeds = [1.0] * 10 + [0.1] * 20
        trace = trace_mod.Trace(make_meta(), make_rows(speeds))

        spans = trace_mod.slowdown_spans(trace)

        self.assertEqual(len(spans), 1)
        self.assertAlmostEqual(spans[0][1], 0.6, places=6)


class VerdictTest(unittest.TestCase):
    """판정 4축의 «지금 상태»."""

    def test_direction_is_undecided_before_the_gate(self):
        rows = make_rows([1.0] * 5)
        trace = trace_mod.Trace(make_meta(), rows)

        state = trace_mod.running_verdict(
            trace, rows[-1], gate_m=3.0, max_lateral_drift=0.75,
            max_velocity_mae=0.25, min_progress_m=3.0, fell=False,
        )

        # 통과선 3 m 를 한참 못 갔다. 방향은 **아직 물을 수 없다.**
        self.assertIsNone(state["direction"])
        self.assertIs(state["progress"], False)
        self.assertIs(state["survival"], True)
        self.assertIs(state["tracking"], True)

    def test_direction_uses_the_gate_crossing(self):
        """통과선을 넘는 **그 순간**의 이탈로 판정한다. 끝점이 아니다."""
        rows = make_rows([1.0] * 4)

        # 전진을 손으로 박는다. 통과선 3.0 을 세 번째 줄에서 넘는다.
        for row, fwd, lat in zip(rows, (0.0, 2.0, 4.0, 6.0),
                                 (0.0, 0.0, 1.0, 0.0)):
            row["fwd_m"] = fwd
            row["lat_m"] = lat

        trace = trace_mod.Trace(make_meta(), rows)

        state = trace_mod.running_verdict(
            trace, rows[-1], gate_m=3.0, max_lateral_drift=0.75,
            max_velocity_mae=0.25, min_progress_m=3.0, fell=False,
        )

        # 2 m 에서 0.0 · 4 m 에서 1.0 이면 3 m 에서는 보간으로 0.5 다.
        # 0.5 <= 0.75 이므로 통과. **끝점 0.0 을 봤다면 이 시험은 뜻이 없다.**
        self.assertIs(state["direction"], True)

    def test_fallen_fails_survival(self):
        rows = make_rows([1.0] * 3)
        trace = trace_mod.Trace(make_meta(), rows)

        state = trace_mod.running_verdict(
            trace, rows[-1], gate_m=3.0, max_lateral_drift=0.75,
            max_velocity_mae=0.25, min_progress_m=3.0, fell=True,
        )

        self.assertIs(state["survival"], False)


@unittest.skipIf(hud_mod is None, "Pillow 가 없습니다")
class FontTest(unittest.TestCase):
    """**라벨을 더하고 글꼴을 안 구우면 여기서 터진다.**

    이것이 부분집합 글꼴의 관문입니다. 이 시험이 없으면 네모가 난 것을
    영상을 만들고 나서야 봅니다.
    """

    def test_fonts_are_present(self):
        for path in (hud_mod.FONT_REGULAR, hud_mod.FONT_BOLD):
            self.assertTrue(
                os.path.exists(path),
                "{} 가 없습니다. build_font.py 로 구우십시오.".format(path),
            )

    def test_every_label_char_is_in_both_fonts(self):
        text = hud_mod.charset()

        self.assertGreater(len(text), 50)

        for path in (hud_mod.FONT_REGULAR, hud_mod.FONT_BOLD):
            missing = hud_mod.missing_glyphs(path, text)

            self.assertEqual(
                missing, [],
                "{} 에 없는 글자: {}".format(os.path.basename(path),
                                            "".join(missing)),
            )

    def test_reserved_font_name_is_gone(self):
        """OFL 1.1 §3. **이름 자리**에 예약된 이름이 남으면 라이선스 위반이다.

        고지 자리(저작권 · 상표 · 설명)는 보지 않습니다. 거기 남은 것은
        위반이 아니라 출처 표시입니다. `build_font.py` 의 `NAME_IDS` 참고.
        """
        from fontTools.ttLib import TTFont

        for path in (hud_mod.FONT_REGULAR, hud_mod.FONT_BOLD):
            font = TTFont(path)

            try:
                for record in font["name"].names:
                    if record.nameID not in (1, 3, 4, 6, 16, 17, 18, 25):
                        continue

                    text = record.toUnicode()

                    self.assertNotIn(
                        "pretendard", text.lower(),
                        "{} 의 nameID {} 에 예약된 이름이 남았습니다: {}"
                        .format(os.path.basename(path), record.nameID, text),
                    )
            finally:
                font.close()


@unittest.skipIf(hud_mod is None, "Pillow 가 없습니다")
class HudTest(unittest.TestCase):
    """그린 결과가 화면 안에 들어오는가 · 정말 그렸는가."""

    def setUp(self):
        speeds = [1.0] * 20 + [0.1] * 40 + [0.9] * 20
        self.trace = trace_mod.Trace(make_meta(), make_rows(speeds))

    def test_renders_at_several_sizes(self):
        for size in ((960, 540), (1280, 720), (1920, 1080)):
            image = hud_mod.render_still(self.trace, size, 40)

            self.assertEqual(image.size, size)

    def test_layout_stays_inside_the_band(self):
        """글자 자리가 패널 밖으로 나가면 잘린다. 자리부터 못 박는다.

        2026-09-09 에 세로축 눈금을 패널 왼쪽 밖에 두어 "1.4" 가 "4" 로
        잘려 나온 적이 있습니다.
        """
        for size in ((960, 540), (1280, 720), (1920, 1080)):
            painter = hud_mod.Hud(size, self.trace)

            bx0, by0, bx1, by1 = painter.band

            boxes = {
                "chart": painter.chart_box,
                "prog": painter.prog_box,
                "drift": painter.drift_box,
            }

            for name, (x0, y0, x1, y1) in boxes.items():
                self.assertGreaterEqual(x0, bx0, "{} {}".format(size, name))
                self.assertLessEqual(x1, bx1, "{} {}".format(size, name))
                self.assertGreaterEqual(y0, by0, "{} {}".format(size, name))
                self.assertLessEqual(y1, by1, "{} {}".format(size, name))

            # 세로축 눈금 자리를 실제로 비워 뒀는가.
            self.assertGreater(painter.chart_box[0] - painter.col_b[0],
                               painter._s(20))

            # 램프 넉 줄이 오른쪽 칸 안에 들어오는가.
            total = 4 * painter.lamp_w + 3 * painter.lamp_gap

            self.assertLessEqual(painter.col_c[0] + total,
                                 painter.col_c[1] + 0.5)

    def test_something_is_actually_drawn(self):
        """**조용한 실패를 소리 나게.** 아무것도 안 그려도 그림은 나온다."""
        from PIL import Image

        size = (640, 360)
        background = Image.new("RGB", size, (20, 20, 20))

        painted = hud_mod.render_still(self.trace, size, 30,
                                       background=background.copy())

        self.assertNotEqual(list(painted.getdata()), list(background.getdata()))

    def test_frames_differ_over_time(self):
        """프레임마다 달라져야 한다. 같으면 trace 를 안 읽고 있는 것이다."""
        size = (640, 360)

        early = hud_mod.render_still(self.trace, size, 5)
        late = hud_mod.render_still(self.trace, size, 70)

        self.assertNotEqual(list(early.getdata()), list(late.getdata()))

    def test_bad_anchor_is_rejected(self):
        with self.assertRaises(ValueError):
            hud_mod.Hud((640, 360), self.trace, anchor="middle")

    def test_axis_is_not_dragged_by_one_spike(self):
        """한 프레임이 튀어도 축이 통째로 늘어나면 안 된다."""
        speeds = [0.5] * 99 + [40.0]
        trace = trace_mod.Trace(make_meta(), make_rows(speeds))

        painter = hud_mod.Hud((640, 360), trace)

        self.assertLess(painter._y_top(), 3.0)


@unittest.skipUnless(HAS_AV, "PyAV 가 없습니다")
@unittest.skipIf(hud_mod is None, "Pillow 가 없습니다")
class RenderTest(TempDirTest):
    """영상 한 벌을 실제로 만들어 되읽는다."""

    def make_video(self, path, frames, size=(320, 180), fps=FPS):
        import av
        from PIL import Image

        container = av.open(path, "w")

        try:
            stream = container.add_stream("libx264", rate=fps)
            stream.width, stream.height = size
            stream.pix_fmt = "yuv420p"
            stream.options = {"crf": "28", "preset": "ultrafast"}

            for index in range(frames):
                shade = 20 + (index * 3) % 200
                image = Image.new("RGB", size, (shade, 40, 60))

                for packet in stream.encode(av.VideoFrame.from_image(image)):
                    container.mux(packet)

            for packet in stream.encode():
                container.mux(packet)
        finally:
            container.close()

        return path

    def test_end_to_end(self):
        from overlay import render as render_mod

        frames = 40
        video = self.make_video(self.path("in.mp4"), frames)

        trace_path = self.path("t.csv")
        trace_mod.write(trace_path, make_meta(),
                        make_rows([1.0] * 10 + [0.1] * 20 + [1.0] * 10))

        out = self.path("out.mp4")

        summary = render_mod.render(video, trace_path, out, crf=28,
                                    preset="ultrafast", progress_every=0)

        self.assertTrue(os.path.exists(out))
        self.assertEqual(summary["out_frames"], frames)
        self.assertEqual(summary["trace_rows"], frames)
        self.assertEqual(len(summary["slowdown_spans"]), 1)

        made = render_mod.probe(out)

        self.assertEqual(made["frames"], frames)
        self.assertEqual((made["width"], made["height"]), (320, 180))

    def test_length_mismatch_refuses_and_writes_nothing(self):
        """**짝이 아닌 영상과 trace 는 거부한다.**

        거부만 하는 것으로는 모자랍니다. 파일을 안 남겨야 합니다.
        """
        from overlay import render as render_mod

        video = self.make_video(self.path("in.mp4"), 200)

        trace_path = self.path("t.csv")
        trace_mod.write(trace_path, make_meta(), make_rows([1.0] * 40))

        out = self.path("out.mp4")

        with self.assertRaises(render_mod.AlignmentError):
            render_mod.render(video, trace_path, out, progress_every=0)

        self.assertFalse(os.path.exists(out))

    def test_장수_차이는_부호까지_본다(self):
        """영상과 trace 의 장수 차이 규칙을 알려진 답으로 시험한다.

        예전 관문은 `abs(차이) > 2` 였다. 글에는 「1장까지 정상」이라 써 놓고
        2장까지 통과시켰고, 방향도 안 봤다. 영상이 trace 보다 «긴» 것은 어떤
        경우에도 정상이 아닌데 그것도 통과했다 (2026-09-11 검증).

        정상은 딱 둘이다. 같거나, trace 가 한 줄 더 길거나.
        """
        from overlay import render as render_mod

        # (영상 장수, trace 줄 수, 통과해야 하는가)
        cases = (
            (40, 40, True),    # 같다
            (40, 41, True),    # 판이 끝나는 스텝. trace 만 한 줄 더
            (40, 42, False),   # 두 줄은 과하다. 예전 관문은 통과시켰다
            (41, 40, False),   # 영상이 더 길다. 있을 수 없다
            (42, 40, False),
        )

        for frames, rows, should_pass in cases:
            with self.subTest(영상=frames, trace=rows):
                video = self.make_video(self.path("in_%d_%d.mp4" % (frames, rows)),
                                        frames)
                trace_path = self.path("t_%d_%d.csv" % (frames, rows))
                trace_mod.write(trace_path, make_meta(), make_rows([1.0] * rows))
                out = self.path("out_%d_%d.mp4" % (frames, rows))

                if should_pass:
                    render_mod.render(video, trace_path, out, progress_every=0)
                    self.assertTrue(os.path.exists(out))
                else:
                    with self.assertRaises(render_mod.AlignmentError):
                        render_mod.render(video, trace_path, out, progress_every=0)
                    self.assertFalse(os.path.exists(out))

    def test_fps_mismatch_refuses(self):
        from overlay import render as render_mod

        video = self.make_video(self.path("in.mp4"), 40, fps=25)

        trace_path = self.path("t.csv")
        trace_mod.write(trace_path, make_meta(), make_rows([1.0] * 40))

        out = self.path("out.mp4")

        with self.assertRaises(render_mod.AlignmentError):
            render_mod.render(video, trace_path, out, progress_every=0)

    def test_probe_counts_instead_of_trusting_metadata(self):
        from overlay import render as render_mod

        video = self.make_video(self.path("in.mp4"), 37)

        self.assertEqual(render_mod.probe(video)["frames"], 37)


if __name__ == "__main__":
    unittest.main()
