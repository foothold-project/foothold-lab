"""에피소드 하나의 **시간축 원자료**. 스키마 · 쓰기 · 읽기.

## 왜 이 파일이 필요한가

`generalization_raw.csv` 는 **에피소드 하나에 한 줄**입니다. `velocity_mae_mps`
도 `speed_drop_ratio` 도 에피소드 전체를 하나로 접은 값입니다. 그 표로는
「3.2초에 어느 관절이 한계에 닿았나」를 물을 수 없습니다. **접기 전의 값**이
필요하고, 그것을 담는 것이 이 파일입니다.

**판정 표를 대신하지 않습니다.** 통과·실패는 여전히 `generalization_raw.csv`
가 정본입니다. 여기 있는 것은 관측이고, 둘이 어긋나면 `verify_against_row()`
가 소리를 냅니다.

## `overlay/trace.py` 와 무엇이 다른가

**다른 것을 만들지 않았습니다. 넓힌 것입니다.**

| | `overlay/trace.py` | 여기 |
|---|---|---|
| 담는 것 | 영상에 겹쳐 그릴 16열 | 그 16열 **그대로** + 관절 · 발 · 자세 |
| 형식 | CSV 한 장 | parquet, 에피소드마다 한 장 |
| 언제 | 영상 한 편을 다시 찍을 때 | 평가 하네스가 도는 김에 전부 |
| 쓰는 쪽 | `record_flat_baseline.py --trace_csv` | `eval_generalization.py --timeseries` |

앞 16열은 `trace.TRACE_COLUMNS` 를 **그대로 가져다 씁니다.** 이름도 뜻도
같습니다. 그래서 `overlay/hud.py` 가 아는 열 이름이 여기서도 그대로 통하고,
필요하면 parquet 한 장을 trace CSV 로 내려 쓰는 것도 열 이름 대응이 필요 없습니다.

## 왜 parquet 인가

**실측입니다** (2026-09-10 · 아래 «실측» 절). CSV 로 적으면 에피소드 하나가
약 0.87 MB 이고, 19,000 에피소드면 16 GB 입니다. 같은 자료를 parquet 으로
적으면 5~10배 작아집니다. 열마다 형이 같은 수치 자료라 압축이 잘 듣습니다.

**`pyarrow` 가 있어야 씁니다.** 없는데 쓰라고 하면 `TimeseriesError` 로
**시작할 때** 죽습니다. 7분을 돌고 끝에서 죽으면 그 실행이 통째로 버려집니다.

## 파일 모양

에피소드마다 한 장입니다.

```
results/<실행이름>/<지형>/
   generalization_raw.csv        에피소드마다 한 줄
   generalization_summary.csv    집계
   timeseries/
      ep0001.parquet             raw CSV 의 첫째 줄
      ep0002.parquet             raw CSV 의 둘째 줄
```

**번호는 raw CSV 의 줄 순서입니다.** `ep0007.parquet` 은 머리글을 뺀 일곱째
줄입니다. 어느 지형 · 어느 env · 몇 번째 에피소드인지는 파일 안 메타에도
함께 적히므로, 번호만 믿지 않아도 대조가 됩니다.

**성공한 에피소드도 남깁니다.** 실패한 것만 남기면 「같은 난이도에서 넘은 것과
못 넘은 것을 겹쳐 본다」가 안 됩니다. 그 비교가 이 자료의 가장 큰 쓰임새입니다.

## 메타는 어디에

parquet 파일의 **스키마 메타**(key-value)에 넣습니다. `trace.py` 가 CSV 머리에
`# 키 = 값` 줄을 얹는 것과 같은 뜻이고, 자리만 형식에 맞게 옮긴 것입니다.
값은 전부 문자열로 적고, 되읽을 때 형을 되살립니다.

`torch` 도 `isaaclab` 도 쓰지 않습니다. `pyarrow` 는 **부를 때** 들어옵니다.
"""

import io
import math
import os

# 앞 16열은 겹쳐 그리기 trace 와 같은 이름·같은 뜻이다. 두 벌을 만들지 않는다.
from overlay import trace as trace_mod

SCHEMA = "foothold-timeseries/1"

# 발 네 자리. `record_flat_baseline.py` 가 쓰는 순서와 같다.
FOOT_SLOTS = ("fl", "fr", "rl", "rr")

# trace 16열 **뒤에** 붙는 열. 순서를 바꾸지 마십시오.
BASE_COLUMNS = (
    # 세계좌표 몸통 위치. `base_z_m` 은 trace 쪽에 이미 있고 지면 기준이다.
    "base_x_m",
    "base_y_m",
    "base_z_w_m",

    # 자세 사원수. Isaac Lab 순서 그대로 wxyz 다.
    "base_qw",
    "base_qx",
    "base_qy",
    "base_qz",
    "base_yaw_deg",

    # 세계좌표 선속도. trace 의 `vx_mps` `vy_mps` 는 **몸통 좌표계**다.
    "base_vx_w_mps",
    "base_vy_w_mps",
    "base_vz_w_mps",

    # 몸통 좌표계 각속도.
    "base_wx_rps",
    "base_wy_rps",
    "base_wz_rps",

    # 명령. `cmd_vx_mps` 는 trace 쪽에 있다.
    "cmd_vy_mps",
    "cmd_wz_rps",
)

FOOT_COLUMNS = tuple(
    "foot_{}_{}_m".format(axis, slot)
    for axis in ("x", "y")
    for slot in FOOT_SLOTS
) + tuple(
    "foot_contact_{}_n".format(slot) for slot in FOOT_SLOTS
)

# 관절 하나가 갖는 네 값. 이름은 `<접두>_<관절이름>` 으로 붙는다.
JOINT_PREFIXES = (
    "joint_pos",      # 각도 (rad)
    "joint_vel",      # 각속도 (rad/s)
    "joint_torque",   # 실제로 들어간 토크 (N·m · `applied_torque`)
    "joint_target",   # 그 토크를 만든 목표 각도 (rad · `joint_pos_target`)
)

# 정수로 되읽을 열.
_INT_COLUMNS = ("frame",)


class TimeseriesError(ValueError):
    """시계열을 쓸 수 없거나, 쓴 것이 스스로 앞뒤가 안 맞을 때."""


def joint_columns(joint_names):
    """관절 이름 목록에서 관절 열 이름 전부. `접두 x 관절` 순서다.

    `joint_pos_*` 12개가 먼저 오고 그 다음이 `joint_vel_*` 12개입니다.
    관절별로 묶는 대신 값 종류로 묶습니다. 한 종류를 통째로 뽑아 그릴 일이
    훨씬 잦기 때문입니다.
    """
    columns = []

    for prefix in JOINT_PREFIXES:
        for name in joint_names:
            columns.append("{}_{}".format(prefix, name))

    return tuple(columns)


def columns_for(joint_names):
    """이 실행의 열 이름 전부. 관절 수에 따라 길이가 달라진다.

    `trace.TRACE_COLUMNS` 16 + `BASE_COLUMNS` 16 + `FOOT_COLUMNS` 12
    + 관절 4 x N. Go2 는 관절이 12개라 **92열**입니다 `확인됨`
    (`tests/test_timeseries.py` 가 이 숫자를 못 박습니다).
    """
    return (
        tuple(trace_mod.TRACE_COLUMNS)
        + BASE_COLUMNS
        + FOOT_COLUMNS
        + joint_columns(joint_names)
    )


def episode_filename(index):
    """raw CSV 의 몇째 줄인가 -> 파일 이름. 1부터 센다."""
    return "ep{:04d}.parquet".format(index)


def euler_deg_from_quat(w, x, y, z):
    """wxyz 사원수에서 `(roll, pitch, yaw)` 를 **도**로.

    Isaac Lab 의 `root_quat_w` 가 wxyz 순서입니다. 여기서 순서를 틀리면 값만
    조용히 틀립니다. 오류는 안 납니다.

    `record_flat_baseline.py` 의 `euler_from_quat()` 이 roll · pitch 를 같은
    식으로 셈합니다. **합치지 않았습니다.** 그쪽은 첫 프레임의 roll · pitch 가
    출발 자세와 맞는지 보는 검사에 묶여 있어서, 고치면 영상 한 편을 다시 찍어
    확인해야 합니다. 같은 식이라는 것은 `tests/test_timeseries.py` 가 두 함수를
    나란히 돌려 못 박습니다.
    """
    sin_roll = 2.0 * (w * x + y * z)
    cos_roll = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sin_roll, cos_roll)

    sin_pitch = max(-1.0, min(1.0, 2.0 * (w * y - z * x)))
    pitch = math.asin(sin_pitch)

    sin_yaw = 2.0 * (w * z + x * y)
    cos_yaw = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(sin_yaw, cos_yaw)

    return (math.degrees(roll), math.degrees(pitch), math.degrees(yaw))


def not_nan(value):
    """NaN 을 `None` 으로 바꾼다. **빈 칸과 0 을 가르는 자리다.**

    안 잰 값은 버퍼에 NaN 으로 들어옵니다(발을 못 집었을 때). parquet 에
    NaN 을 그대로 적으면 「쟀는데 NaN」이 되고, `None` 으로 적어야 「안 쟀다」가
    됩니다. 0 으로 바꾸면 「발이 지면에 있었다」로 둔갑합니다.
    """
    if value is None or value != value:
        return None

    return value


def foot_slots(found_ids, found_names):
    """`.*_foot` 로 찾은 것을 **FL · FR · RL · RR 자리에 맞춰** 다시 세운다.

    찾은 순서가 곧 FL·FR·RL·RR 이라고 믿으면 안 됩니다. USD 가 강체를 어떤
    순서로 담았는지에 달렸고, 그 순서가 바뀌어도 오류는 안 납니다. 열 이름만
    조용히 틀립니다. 그래서 **이름 앞머리로 자리를 정합니다.**

    넷을 다 못 채우면 `None` 입니다. **0 으로 채우지 않습니다.** 발 열이
    빈 칸이면 「안 쟀다」이고, 0 이면 「발이 지면에 있었다」가 됩니다.

    `record_flat_baseline.py` 가 trace 를 쓸 때 하는 것과 같은 판단입니다.
    그쪽은 본문에 인라인이고, 여기서는 시험할 수 있게 순수 함수로 뺐습니다.
    """
    if len(found_ids) != len(FOOT_SLOTS):
        return None

    order = {slot.upper(): index for index, slot in enumerate(FOOT_SLOTS)}
    slots = [None] * len(FOOT_SLOTS)

    for body_id, body_name in zip(found_ids, found_names):
        index = order.get(body_name.split("_")[0].upper())

        if index is not None:
            slots[index] = body_id

    if any(slot is None for slot in slots):
        return None

    return slots


# ---------------------------------------------------------------- 쓰기


def require_pyarrow():
    """`pyarrow` 를 들여오고, 없으면 **여기서** 죽는다.

    ★ 하네스는 시뮬을 띄우기 **전에** 이 함수를 부릅니다. 없는 채로 시작하면
    에피소드를 다 돌고 첫 파일을 쓰는 자리에서 죽고, 그 실행이 통째로 버려집니다.
    """
    try:
        import pyarrow  # noqa: F401
        import pyarrow.parquet  # noqa: F401
    except ImportError as error:
        raise TimeseriesError(
            "시계열을 parquet 으로 쓰려면 `pyarrow` 가 있어야 합니다.\n"
            "  못 들여옴 : {}\n"
            "  깔기      : python -m pip install pyarrow\n"
            "이 인자(`--timeseries`)를 빼면 지금까지와 똑같이 돕니다.".format(error)
        )

    import pyarrow

    return pyarrow


def write(path, meta, rows, columns):
    """에피소드 하나의 시계열 parquet 한 장.

    `rows` 는 열 이름을 키로 갖는 딕셔너리 목록입니다. 없는 열은 **빈 칸**으로
    나갑니다(parquet 의 null). **0 으로 채우지 않습니다.** 0 은 「쟀는데 0」이고
    빈 칸은 「안 쟀다」입니다. `trace.write()` 와 같은 규칙입니다.
    """
    pa = require_pyarrow()
    import pyarrow.parquet as pq

    if not rows:
        raise TimeseriesError("{}: 담을 줄이 하나도 없습니다.".format(path))

    arrays = []

    for name in columns:
        values = [row.get(name) for row in rows]

        if name in _INT_COLUMNS:
            arrays.append(pa.array(values, type=pa.int32()))
        else:
            arrays.append(pa.array(
                [None if v is None else float(v) for v in values],
                type=pa.float32(),
            ))

    ordered = dict(meta)
    ordered.setdefault("schema", SCHEMA)
    ordered["rows"] = len(rows)
    ordered["columns"] = len(columns)

    schema_meta = {
        str(key).encode("utf-8"): str(value).encode("utf-8")
        for key, value in ordered.items()
    }

    table = pa.Table.from_arrays(
        arrays, schema=pa.schema(
            [pa.field(name, arrays[i].type) for i, name in enumerate(columns)],
            metadata=schema_meta,
        )
    )

    directory = os.path.dirname(os.path.abspath(path))

    if directory:
        os.makedirs(directory, exist_ok=True)

    pq.write_table(table, path, compression="zstd")

    return path


# ---------------------------------------------------------------- 읽기


def read(path):
    """parquet 한 장을 `(메타, 줄 목록)` 으로. 앞뒤가 안 맞으면 `TimeseriesError`."""
    require_pyarrow()
    import pyarrow.parquet as pq

    table = pq.read_table(path)

    raw_meta = table.schema.metadata or {}

    meta = {
        key.decode("utf-8"): value.decode("utf-8")
        for key, value in raw_meta.items()
    }

    if meta.get("schema") != SCHEMA:
        raise TimeseriesError(
            "{} 의 schema 가 {} 입니다. {} 여야 합니다.".format(
                path, meta.get("schema"), SCHEMA
            )
        )

    rows = table.to_pylist()

    if not rows:
        raise TimeseriesError("{} 에 줄이 없습니다.".format(path))

    _check_self_consistent(rows, meta, path)

    return meta, rows


def _check_self_consistent(rows, meta, path):
    """줄 번호가 0 부터 1씩 오르는가. 시각이 그 번호와 맞는가.

    **조용한 실패를 소리 나게 만드는 자리입니다.** 줄이 빠진 시계열로 그림을
    그리면 그림은 멀쩡히 나오고 값만 밀립니다. 눈으로는 안 잡힙니다.
    `trace._check_self_consistent()` 와 같은 검사입니다.
    """
    dt = float(meta.get("dt_s", 0.0))

    for index, row in enumerate(rows):
        if row.get("frame") != index:
            raise TimeseriesError(
                "{}: {} 번째 줄의 frame 이 {} 입니다. {} 여야 합니다.".format(
                    path, index, row.get("frame"), index
                )
            )

        if dt <= 0.0:
            continue

        expected_t = index * dt
        got = row.get("t_s")

        if got is None or abs(got - expected_t) > 1.0e-3:
            raise TimeseriesError(
                "{}: frame {} 의 t_s 가 {} 입니다. {:.6f} 여야 합니다.".format(
                    path, index, got, expected_t
                )
            )


# ---------------------------------------------------------------- 대조


def verify_against_row(rows, row, tolerance=0.05):
    """시계열을 접으면 판정 표의 그 줄이 나오는가.

    `trace.verify_against_row()` 와 같은 뜻입니다. 시계열은 그 에피소드를
    프레임마다 펼친 것이므로 **다시 접으면 원래 값이 나와야 합니다.**

    돌려주는 것은 `(항목, 표값, 시계열값, 차이, 통과여부)` 목록입니다.
    여기서는 안 죽입니다. 무엇이 얼마나 틀렸는지 다 보여 주고 나서 부르는 쪽이
    판단하게 합니다.

    **허용 오차가 `trace` 쪽(0.002)보다 헐겁습니다.** 값을 `float32` 로 적기
    때문입니다. 10 m 근처에서 `float32` 의 최소 간격이 약 1e-6 이라 실제
    오차는 그보다 훨씬 작지만, 자리를 넉넉히 둡니다.
    """
    checks = []

    def add(name, expected, got):
        if expected is None or got is None:
            checks.append((name, expected, got, None, False))
            return

        diff = abs(expected - got)
        checks.append((name, expected, got, diff, diff <= tolerance))

    def column(name):
        return [r.get(name) for r in rows if r.get(name) is not None]

    def as_float(value):
        if value is None or value == "":
            return None

        return float(value)

    fwd = column("fwd_m")
    lat = column("lat_m")
    err = column("vel_err_mps")

    add(
        "forward_progress_m",
        as_float(row.get("forward_progress_m")),
        fwd[-1] if fwd else None,
    )

    add(
        "lateral_drift_m",
        as_float(row.get("lateral_drift_m")),
        abs(lat[-1]) if lat else None,
    )

    add(
        "peak_lateral_drift_m",
        as_float(row.get("peak_lateral_drift_m")),
        max(abs(v) for v in lat) if lat else None,
    )

    add(
        "velocity_mae_mps",
        as_float(row.get("velocity_mae_mps")),
        sum(err) / len(err) if err else None,
    )

    return checks


# ---------------------------------------------------------------- 실측


def measure_csv_size(rows, columns):
    """같은 자료를 CSV 로 적으면 몇 바이트인가. **재보고 말하기 위한 자리다.**

    parquet 이 얼마나 작은지를 말하려면 둘 다 재야 합니다. 이론값으로 말하지
    않습니다 (커널 2-1 · 원칙 4). 하네스가 첫 에피소드 한 장에서만 부릅니다.
    """
    import csv

    buffer = io.StringIO()

    writer = csv.DictWriter(
        buffer, fieldnames=list(columns), extrasaction="ignore", lineterminator="\n"
    )
    writer.writeheader()

    for row in rows:
        writer.writerow(row)

    return len(buffer.getvalue().encode("utf-8"))
