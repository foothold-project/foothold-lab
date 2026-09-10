"""시계열 parquet 의 스키마 · 쓰기 · 되읽기.

**스키마 시험은 `pyarrow` 없이 돕니다.** 열 이름과 순서, 파일 이름 규칙, 발
자리 맞춤, 사원수 변환은 표준 라이브러리만으로 셈합니다.

`pyarrow` 가 있어야 도는 것은 **왕복 시험 넷**뿐이고, 없으면 건너뜁니다.
CI 러너에는 `pyarrow` 가 없습니다(`.github/workflows/sim-tests.yml`).
건너뛴 개수와 이유는 `run_sim_tests.py` 가 매번 찍으므로 조용히 줄지 않습니다.

돌리는 법:

    python -m unittest discover -s sim/eval/tests -v
"""

import math
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

import timeseries
from overlay import trace as trace_mod

try:
    import pyarrow  # noqa: F401

    HAS_PYARROW = True
except ImportError:
    HAS_PYARROW = False

NEEDS_PYARROW = unittest.skipUnless(
    HAS_PYARROW, "pyarrow 가 없습니다 (parquet 왕복 시험만 건너뜁니다)"
)

# Go2 의 관절 12개. `probe_go2_joint_limits.py` 가 내는 이름과 같은 꼴입니다.
GO2_JOINTS = (
    "FL_hip_joint", "FR_hip_joint", "RL_hip_joint", "RR_hip_joint",
    "FL_thigh_joint", "FR_thigh_joint", "RL_thigh_joint", "RR_thigh_joint",
    "FL_calf_joint", "FR_calf_joint", "RL_calf_joint", "RR_calf_joint",
)


def sample_rows(count, columns, dt=0.02):
    """앞뒤가 맞는 줄 목록. `frame` 과 `t_s` 만 뜻이 있고 나머지는 채움값입니다."""
    rows = []

    for index in range(count):
        row = {name: float(index) for name in columns}
        row["frame"] = index
        row["t_s"] = index * dt
        rows.append(row)

    return rows


class ColumnContract(unittest.TestCase):
    """열 이름과 순서. **바꾸면 이미 나온 parquet 을 못 읽는다.**"""

    def setUp(self):
        self.columns = timeseries.columns_for(GO2_JOINTS)

    def test_Go2_는_92열이다(self):
        # trace 16 + 몸통 16 + 발 12 + 관절 4 x 12.
        self.assertEqual(len(self.columns), 92)

    def test_겹치는_이름이_없다(self):
        self.assertEqual(len(self.columns), len(set(self.columns)))

    def test_앞_16열은_trace_와_글자_그대로_같다(self):
        # 두 벌을 만들지 않았다는 것의 보증이다. `overlay/hud.py` 가 아는
        # 열 이름이 여기서도 그대로 통해야 한다.
        self.assertEqual(
            self.columns[:len(trace_mod.TRACE_COLUMNS)],
            tuple(trace_mod.TRACE_COLUMNS),
        )

    def test_trace_열을_하나도_안_빠뜨린다(self):
        for name in trace_mod.TRACE_COLUMNS:
            self.assertIn(name, self.columns)

    def test_관절_열은_값_종류로_묶인다(self):
        # `joint_pos_*` 12개가 먼저 다 오고 그 다음이 `joint_vel_*` 다.
        joint = timeseries.joint_columns(GO2_JOINTS)

        self.assertEqual(len(joint), 4 * len(GO2_JOINTS))

        for block, prefix in enumerate(timeseries.JOINT_PREFIXES):
            chunk = joint[block * len(GO2_JOINTS):(block + 1) * len(GO2_JOINTS)]

            for name in chunk:
                self.assertTrue(name.startswith(prefix + "_"), name)

    def test_관절_넷을_전부_담는다(self):
        # 각도 · 속도 · 토크가 팀장이 적은 셋이고, 목표 각도를 하나 더 담는다.
        self.assertEqual(
            timeseries.JOINT_PREFIXES,
            ("joint_pos", "joint_vel", "joint_torque", "joint_target"),
        )

    def test_발_열은_네_자리를_다_갖는다(self):
        for slot in timeseries.FOOT_SLOTS:
            self.assertIn("foot_x_{}_m".format(slot), self.columns)
            self.assertIn("foot_y_{}_m".format(slot), self.columns)
            self.assertIn("foot_z_{}_m".format(slot), self.columns)
            self.assertIn("foot_contact_{}_n".format(slot), self.columns)

    def test_관절_수가_달라지면_열_수도_달라진다(self):
        fewer = timeseries.columns_for(GO2_JOINTS[:6])

        self.assertEqual(len(self.columns) - len(fewer), 4 * 6)

    def test_파일_이름은_네_자리다(self):
        self.assertEqual(timeseries.episode_filename(1), "ep0001.parquet")
        self.assertEqual(timeseries.episode_filename(19000), "ep19000.parquet")

    def test_파일_이름_순서가_번호_순서다(self):
        # 사전 순으로 늘어놓아도 번호 순이어야 한다. 폴더를 세는 관문이
        # 그것을 전제로 한다.
        names = [timeseries.episode_filename(i) for i in range(1, 1000)]

        self.assertEqual(names, sorted(names))


class FootSlots(unittest.TestCase):
    """찾은 순서를 믿지 않고 이름으로 자리를 정한다."""

    def test_순서가_섞여_있어도_자리를_맞춘다(self):
        slots = timeseries.foot_slots(
            [7, 3, 9, 5],
            ["RR_foot", "FL_foot", "RL_foot", "FR_foot"],
        )

        # FL FR RL RR 순서로 다시 세운다.
        self.assertEqual(slots, [3, 5, 9, 7])

    def test_넷이_아니면_None(self):
        self.assertIsNone(timeseries.foot_slots([1, 2], ["FL_foot", "FR_foot"]))

    def test_모르는_이름이_섞이면_None(self):
        slots = timeseries.foot_slots(
            [1, 2, 3, 4],
            ["FL_foot", "FR_foot", "RL_foot", "XX_foot"],
        )

        self.assertIsNone(slots)

    def test_소문자여도_잡는다(self):
        slots = timeseries.foot_slots(
            [1, 2, 3, 4],
            ["fl_foot", "fr_foot", "rl_foot", "rr_foot"],
        )

        self.assertEqual(slots, [1, 2, 3, 4])


class EulerFromQuat(unittest.TestCase):
    """사원수 -> 도. 순서를 틀리면 오류 없이 값만 틀린다."""

    def test_단위_사원수는_전부_0도(self):
        roll, pitch, yaw = timeseries.euler_deg_from_quat(1.0, 0.0, 0.0, 0.0)

        self.assertAlmostEqual(roll, 0.0)
        self.assertAlmostEqual(pitch, 0.0)
        self.assertAlmostEqual(yaw, 0.0)

    def test_yaw_90도(self):
        half = math.sqrt(0.5)

        _, _, yaw = timeseries.euler_deg_from_quat(half, 0.0, 0.0, half)

        self.assertAlmostEqual(yaw, 90.0, places=5)

    def test_roll_90도(self):
        half = math.sqrt(0.5)

        roll, _, _ = timeseries.euler_deg_from_quat(half, half, 0.0, 0.0)

        self.assertAlmostEqual(roll, 90.0, places=5)

    def test_pitch_는_구간_밖에서도_안_터진다(self):
        # `asin` 의 인자가 부동소수 때문에 1 을 아주 살짝 넘을 수 있다.
        _, pitch, _ = timeseries.euler_deg_from_quat(
            math.sqrt(0.5) + 1e-12, 0.0, math.sqrt(0.5) + 1e-12, 0.0
        )

        self.assertAlmostEqual(pitch, 90.0, places=3)

    def test_record_flat_baseline_과_같은_값을_낸다(self):
        # 같은 식이 두 자리에 있다. 둘이 갈라지면 영상 위 숫자와 parquet 이
        # 다른 말을 하게 된다. 여기서 나란히 돌려 못 박는다.
        def theirs(w, x, y, z):
            sin_roll = 2.0 * (w * x + y * z)
            cos_roll = 1.0 - 2.0 * (x * x + y * y)
            roll = math.atan2(sin_roll, cos_roll)

            sin_pitch = max(-1.0, min(1.0, 2.0 * (w * y - z * x)))
            pitch = math.asin(sin_pitch)

            return (math.degrees(roll), math.degrees(pitch))

        quats = (
            (1.0, 0.0, 0.0, 0.0),
            (0.9239, 0.3827, 0.0, 0.0),
            (0.9239, 0.0, 0.3827, 0.0),
            (0.7071, 0.0, 0.0, 0.7071),
            (0.6, 0.5, 0.4, 0.4796),
        )

        for quat in quats:
            with self.subTest(quat=quat):
                roll, pitch, _ = timeseries.euler_deg_from_quat(*quat)
                want_roll, want_pitch = theirs(*quat)

                self.assertAlmostEqual(roll, want_roll, places=9)
                self.assertAlmostEqual(pitch, want_pitch, places=9)


class NotANumber(unittest.TestCase):
    """안 잰 값과 0 을 가른다."""

    def test_NaN_은_None_이_된다(self):
        self.assertIsNone(timeseries.not_nan(float("nan")))

    def test_None_은_None_이다(self):
        self.assertIsNone(timeseries.not_nan(None))

    def test_0_은_0_그대로다(self):
        self.assertEqual(timeseries.not_nan(0.0), 0.0)

    def test_보통_값은_그대로다(self):
        self.assertEqual(timeseries.not_nan(-1.25), -1.25)


class CsvSizeMeasurement(unittest.TestCase):
    """parquet 이 얼마나 작은지를 말하려면 CSV 도 재야 한다."""

    def test_실제로_바이트를_센다(self):
        columns = timeseries.columns_for(GO2_JOINTS)
        rows = sample_rows(10, columns)

        size = timeseries.measure_csv_size(rows, columns)

        self.assertGreater(size, 0)

    def test_줄이_늘면_바이트도_는다(self):
        columns = timeseries.columns_for(GO2_JOINTS)

        small = timeseries.measure_csv_size(sample_rows(10, columns), columns)
        big = timeseries.measure_csv_size(sample_rows(100, columns), columns)

        self.assertGreater(big, small)


@NEEDS_PYARROW
class ParquetRoundTrip(unittest.TestCase):
    """썼으면 되읽힌다. **되읽어 보지 않고 「썼다」를 결과로 치지 않는다.**"""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.columns = timeseries.columns_for(GO2_JOINTS)
        self.path = os.path.join(self.dir, "ep0001.parquet")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_쓴_것이_그대로_되읽힌다(self):
        rows = sample_rows(50, self.columns)

        timeseries.write(self.path, {"terrain": "gap", "dt_s": 0.02}, rows,
                         self.columns)

        meta, back = timeseries.read(self.path)

        self.assertEqual(meta["terrain"], "gap")
        self.assertEqual(meta["schema"], timeseries.SCHEMA)
        self.assertEqual(int(meta["rows"]), 50)
        self.assertEqual(int(meta["columns"]), len(self.columns))

        self.assertEqual(len(back), 50)
        self.assertEqual(len(back[0]), len(self.columns))
        self.assertEqual(list(back[0].keys()), list(self.columns))

    def test_빈_칸은_0_이_아니라_빈_칸으로_남는다(self):
        rows = sample_rows(5, self.columns)

        for row in rows:
            del row["foot_z_fl_m"]

        timeseries.write(self.path, {"dt_s": 0.02}, rows, self.columns)

        _, back = timeseries.read(self.path)

        for row in back:
            self.assertIsNone(row["foot_z_fl_m"])

        # 옆 열은 멀쩡해야 한다.
        self.assertIsNotNone(back[0]["foot_z_fr_m"])

    def test_줄이_빠지면_읽을_때_죽는다(self):
        rows = sample_rows(10, self.columns)
        del rows[4]

        timeseries.write(self.path, {"dt_s": 0.02}, rows, self.columns)

        with self.assertRaises(timeseries.TimeseriesError):
            timeseries.read(self.path)

    def test_스키마가_다르면_읽을_때_죽는다(self):
        rows = sample_rows(5, self.columns)

        timeseries.write(self.path, {"schema": "다른것/9", "dt_s": 0.02}, rows,
                         self.columns)

        with self.assertRaises(timeseries.TimeseriesError):
            timeseries.read(self.path)

    def test_담을_줄이_없으면_안_쓴다(self):
        with self.assertRaises(timeseries.TimeseriesError):
            timeseries.write(self.path, {}, [], self.columns)

    def test_CSV_보다_작다(self):
        # 「parquet 이 작다」를 이론이 아니라 **재서** 말한다.
        # 줄이 많아야 열 압축이 듣는다. 20초 x 50 Hz = 1000 줄이 실제 크기다.
        rows = sample_rows(1000, self.columns)

        timeseries.write(self.path, {"dt_s": 0.02}, rows, self.columns)

        parquet_bytes = os.path.getsize(self.path)
        csv_bytes = timeseries.measure_csv_size(rows, self.columns)

        self.assertLess(parquet_bytes, csv_bytes)

    def test_접으면_판정_표의_그_줄이_나온다(self):
        rows = sample_rows(10, self.columns)

        for index, row in enumerate(rows):
            row["fwd_m"] = 0.5 * index
            row["lat_m"] = 0.01 * index
            row["vel_err_mps"] = 0.10

        checks = timeseries.verify_against_row(
            rows,
            {
                "forward_progress_m": 4.5,
                "lateral_drift_m": 0.09,
                "peak_lateral_drift_m": 0.09,
                "velocity_mae_mps": 0.10,
            },
        )

        for name, want, got, delta, ok in checks:
            self.assertTrue(ok, "{} 표={} 시계열={}".format(name, want, got))

    def test_어긋나면_대조가_실패로_나온다(self):
        rows = sample_rows(10, self.columns)

        for index, row in enumerate(rows):
            row["fwd_m"] = 0.5 * index

        checks = timeseries.verify_against_row(
            rows, {"forward_progress_m": 99.0}
        )

        failed = [c[0] for c in checks if not c[4]]

        self.assertIn("forward_progress_m", failed)


class PyarrowGate(unittest.TestCase):
    """없으면 **조용히 넘어가지 않고** 무엇을 깔라고 말한다."""

    def test_없으면_안내가_있는_오류다(self):
        if HAS_PYARROW:
            self.assertIsNotNone(timeseries.require_pyarrow())
            return

        with self.assertRaises(timeseries.TimeseriesError) as caught:
            timeseries.require_pyarrow()

        self.assertIn("pip install pyarrow", str(caught.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
