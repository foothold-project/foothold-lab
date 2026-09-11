"""프레임별 계측 기록(trace). 스키마 · 읽기 · 쓰기 · 대조.

## 왜 이 파일이 필요한가

`generalization_raw.csv` 는 **한 판에 한 줄**입니다. `forward_progress_m` 도
`velocity_mae_mps` 도 판 전체를 하나로 접은 값입니다. 그 표로는
「3.2초에 속도가 떨어졌다」를 그릴 수 없습니다. **접기 전의 값**이 필요하고,
그것을 담는 것이 이 파일의 trace CSV 입니다.

**판정 표를 대신하지 않습니다.** trace 는 관측이고, 통과·실패는 여전히
`generalization_raw.csv` 가 정본입니다. 그 둘이 어긋나면 `verify_against_row()`
가 소리를 냅니다.

## 프레임과 줄이 어떻게 맞는가

`record_flat_baseline.py` 는 **시뮬 스텝 하나에 프레임 하나**를 찍습니다.
녹화가 시작될 때 스텝 전 상태로 한 장을 찍고, 그 뒤로는 스텝마다 한 장씩입니다.

| 무엇 | 언제의 상태인가 |
|---|---|
| 프레임 0 | 판의 첫 스텝 **직전** |
| 프레임 k | k 번 스텝을 밟은 **직후** |

trace 줄도 같은 자리에서 적습니다. 스텝을 밟기 직전에 한 줄입니다. 그래서
**trace 줄 번호 = 프레임 번호** 이고, 시각은 `t_s = frame / fps` 입니다.

판이 끝나는 스텝에서는 프레임을 안 찍습니다(로봇이 이미 리셋된 화면이라).
그 스텝의 trace 줄은 남으므로 **trace 가 영상보다 한 줄 길 수 있습니다.**
`render.py` 가 이것을 알고 있고, 그보다 크게 어긋나면 거부합니다.

## 파일 모양

머리에 `# 키 = 값` 메타 줄이 오고, 그 다음이 보통의 CSV 입니다.
`docs/assets/eval/lvl*.csv` 가 이미 쓰는 방식과 같습니다.

```
# schema = foothold-trace/2
# terrain = pit
# fps = 50
...
frame,t_s,cmd_vx_mps,...
0,0.0,1.0,...
```

`torch` 도 `isaaclab` 도 쓰지 않습니다. Isaac 안에서도, 이 워크스테이션에서도
그대로 임포트됩니다.
"""

import csv
import io
import math

SCHEMA = "foothold-trace/2"

# 판 갈이
#   /1  2026-09-10  처음
#   /2  2026-09-11  `yaw_deg` 추가. 출발 축에서 얼마나 틀어졌는가.
#                   roll·pitch 만 적고 yaw 를 안 적어서, 「카메라가 왜 도느냐」를
#                   물었을 때 원자료로 답할 수 없었다 (팀장 지적).
#
# **한 판 안에서는 순서를 바꾸지 마십시오.** 판을 올릴 때만 바꿉니다.
#
# 옛 판은 아래 `READABLE_SCHEMAS` 에 「그 판에 없던 열」을 적어 두면 읽습니다.
# 거기 없는 판은 거부합니다. 아무 판이나 받아 주는 자리가 아닙니다.
TRACE_COLUMNS = (
    "frame",
    "t_s",
    # 속도. 명령과 실제를 나란히 둔다. 이 도구가 있는 이유다.
    "cmd_vx_mps",
    "vx_mps",
    "vy_mps",
    "speed_mps",
    "vel_err_mps",
    # 자리. 출발 자세 기준의 전방축 · 측면축이다. 세계좌표가 아니다.
    "fwd_m",
    "lat_m",
    # 자세. 지금은 안 그리지만 적어 둔다(§ README «뺀 것»).
    "base_z_m",
    "pitch_deg",
    "roll_deg",
    # 출발 축 대비 틀어진 각. 왼쪽이 양수. 세계좌표 yaw 가 아니다.
    "yaw_deg",
    # 네 발 높이. 지형면이 아니라 세계 z 다. 안 그린다(§ README «뺀 것»).
    "foot_z_fl_m",
    "foot_z_fr_m",
    "foot_z_rl_m",
    "foot_z_rr_m",
)

# **읽을 수 있는 판과, 그 판에 없던 열.**
#
# 판을 올릴 때 «열이 늘기만» 했다면 옛 파일도 읽을 수 있습니다. 없는 열은
# 빈 칸(`None`)으로 옵니다. 이 형식에서 빈 칸은 원래 「안 쟀다」는 뜻이라
# 거짓말이 아닙니다.
#
# 열의 «뜻» 이 바뀌었다면 여기 넣지 마십시오. 그때는 거부해야 맞습니다.
# 같은 이름으로 다른 것을 읽으면 아무도 못 잡습니다.
READABLE_SCHEMAS = {
    "foothold-trace/1": ("yaw_deg",),
    SCHEMA: (),
}

# 숫자로 되읽을 열. `frame` 만 정수다.
_INT_COLUMNS = ("frame",)

# 메타 줄 중 숫자로 되읽을 것.
_META_FLOAT_KEYS = (
    "fps",
    "dt_s",
    "command_vx_mps",
    "eval_duration_s",
    "gate_m",
    "max_lateral_drift_m",
    "max_velocity_mae_mps",
)

_META_INT_KEYS = ("env_id", "episode", "slowmo")


class TraceError(ValueError):
    """trace 가 스스로 앞뒤가 안 맞을 때. 조용히 넘기지 않는다."""


class Trace(object):
    """메타 한 벌과 프레임 줄 목록.

    `rows[i]` 는 열 이름을 키로 갖는 딕셔너리이고, 수치는 이미 `float` 입니다.
    """

    def __init__(self, meta, rows):
        self.meta = dict(meta)
        self.rows = list(rows)

    # ------------------------------------------------------------ 편의

    def __len__(self):
        return len(self.rows)

    def column(self, name):
        """열 하나를 목록으로. 빈 칸은 `None` 으로 남습니다."""
        return [row.get(name) for row in self.rows]

    @property
    def schema(self):
        """이 파일이 어느 판으로 쓰였는가."""
        return self.meta.get("schema")

    @property
    def absent_columns(self):
        """이 판에 원래 없던 열. 값을 물으면 전부 `None` 입니다.

        옛 판을 읽었을 때 「왜 이 열이 비었나」에 답하는 자리입니다.
        """
        return tuple(READABLE_SCHEMAS.get(self.schema, ()))

    @property
    def fps(self):
        """**찍은 주기**다. 담긴 영상의 fps 가 아니다.

        슬로우모션이면 둘이 다르다. 이 값은 언제나 «시뮬레이션을 초당 몇 번
        재었나» 이고, `t_s` 가 그 주기를 따른다.
        """
        return float(self.meta["fps"])

    @property
    def slowmo(self):
        """몇 배 느리게 담았는가. 없으면 1 이다.

        영상의 프레임 `i` 는 trace 의 줄 `i` 와 **일대일**이다. 시각으로
        집으면 이 배수만큼 밀린다.
        """
        try:
            return max(1, int(self.meta.get("slowmo", 1)))
        except (TypeError, ValueError):
            return 1

    @property
    def dt_s(self):
        return float(self.meta.get("dt_s", 1.0 / self.fps))

    @property
    def duration_s(self):
        """줄 수 x 스텝 시간. `duration_s` 판정값과 같은 정의입니다."""
        return len(self.rows) * self.dt_s

    @property
    def command_vx(self):
        return float(self.meta["command_vx_mps"])

    def at_time(self, t_s):
        """그 시각에 **가장 가까운** 줄. 없으면 `None`.

        영상 프레임의 시각으로 부릅니다. 반올림이라 프레임 하나 안쪽에서만
        움직입니다.
        """
        if not self.rows:
            return None

        index = int(round(t_s / self.dt_s))

        if index < 0:
            index = 0
        elif index >= len(self.rows):
            index = len(self.rows) - 1

        return self.rows[index]

    def value_range(self, name, fallback=(0.0, 1.0)):
        """열의 (최솟값, 최댓값). 값이 하나도 없으면 `fallback`."""
        values = [v for v in self.column(name) if v is not None]

        if not values:
            return fallback

        return (min(values), max(values))


# ---------------------------------------------------------------- 쓰기


def format_meta_line(key, value):
    return "# {} = {}\n".format(key, value)


def write(path, meta, rows):
    """trace CSV 하나를 쓴다.

    `rows` 는 `TRACE_COLUMNS` 를 키로 갖는 딕셔너리 목록입니다. 없는 열은
    빈 칸으로 나갑니다. **없는 열을 0 으로 채우지 않습니다.** 0 은 「쟀는데
    0 이었다」는 뜻이고, 빈 칸은 「안 쟀다」는 뜻입니다.

    등록 안 된 열을 주면 **거부합니다.** 예전에는 `extrasaction="ignore"` 라
    조용히 버렸습니다. 새 열을 재서 넣어도 파일에는 안 들어가고 아무도
    모릅니다 `확인됨` (2026-09-11 · `yaw_deg` 를 넣었는데 안 나왔다).
    """
    ordered = dict(meta)
    ordered.setdefault("schema", SCHEMA)

    # **자기가 안 쓰는 판 이름을 적지 못하게 한다.**
    #
    # 이 함수는 언제나 지금 `TRACE_COLUMNS` 를 통째로 쓴다. 그런데 머리말의
    # 판 이름은 `meta` 에서 그대로 받아 적었다. 그래서 `schema` 만 옛 판으로
    # 주면 **내용은 새 판이고 이름만 옛 판인 파일**이 나왔다
    # `확인됨` (2026-09-11 · 시험을 쓰다 드러남).
    #
    # 옛 판 파일은 «그때 그 코드» 가 만든 것이지 지금 코드가 만드는 것이 아니다.
    if ordered["schema"] != SCHEMA:
        raise TraceError(
            "{} 에 schema 를 {} 로 적으려 합니다. 이 함수는 {} 만 씁니다. "
            "옛 판 파일을 새로 만들지 마십시오.".format(
                path, ordered["schema"], SCHEMA
            )
        )

    # **등록 안 된 열을 소리 나게 만든다.** 쓰기 전에 다 본다. 절반 쓰다
    # 멈추면 앞뒤 안 맞는 파일이 남는다.
    known = set(TRACE_COLUMNS)
    for index, row in enumerate(rows):
        unknown = sorted(set(row) - known)
        if unknown:
            raise TraceError(
                "{} 의 {} 번째 줄에 등록 안 된 열이 있습니다: {}. "
                "`TRACE_COLUMNS` 에 넣고 `SCHEMA` 판을 올리십시오.".format(
                    path, index, unknown
                )
            )

    with io.open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(format_meta_line("schema", ordered.pop("schema")))

        for key in sorted(ordered):
            handle.write(format_meta_line(key, ordered[key]))

        writer = csv.DictWriter(
            handle, fieldnames=list(TRACE_COLUMNS), extrasaction="raise",
            lineterminator="\n",
        )
        writer.writeheader()

        for row in rows:
            writer.writerow(row)


# ---------------------------------------------------------------- 읽기


def _coerce_meta(meta):
    out = dict(meta)

    for key in _META_FLOAT_KEYS:
        if key in out and out[key] != "":
            out[key] = float(out[key])

    for key in _META_INT_KEYS:
        if key in out and out[key] != "":
            out[key] = int(out[key])

    return out


def _coerce_row(raw, absent=()):
    """CSV 한 줄을 수치로. `absent` 는 그 판에 없던 열이다.

    없던 열은 **빈 칸으로 채워 넣는다.** 키 자체를 빼면 `row["yaw_deg"]` 가
    `KeyError` 로 죽는다. 옛 판을 읽는 쪽은 그 열이 있는지 없는지 모르고
    그냥 물을 뿐이고, 「안 쟀다」의 답은 `None` 이다.
    """
    row = {key: None for key in absent}

    for key, text in raw.items():
        if key is None or key not in TRACE_COLUMNS:
            continue

        if text is None or text == "":
            row[key] = None
        elif key in _INT_COLUMNS:
            row[key] = int(text)
        else:
            row[key] = float(text)

    return row


def read(path):
    """trace CSV 를 읽어 `Trace` 로. 앞뒤가 안 맞으면 `TraceError`."""
    meta = {}
    body = []

    with io.open(path, "r", encoding="utf-8", newline="") as handle:
        for line in handle:
            if line.startswith("#"):
                text = line[1:].strip()

                if "=" in text:
                    key, value = text.split("=", 1)
                    meta[key.strip()] = value.strip()

                continue

            body.append(line)

    schema = meta.get("schema")

    if schema not in READABLE_SCHEMAS:
        raise TraceError(
            "{} 의 schema 가 {} 입니다. 읽을 수 있는 판은 {} 입니다.".format(
                path, schema, ", ".join(sorted(READABLE_SCHEMAS))
            )
        )

    reader = csv.DictReader(body)
    fieldnames = reader.fieldnames or []

    # 그 판에 원래 없던 열은 빼고 센다. 나머지가 하나라도 없으면 거부한다.
    absent_by_design = READABLE_SCHEMAS[schema]
    missing = [c for c in TRACE_COLUMNS
               if c not in fieldnames and c not in absent_by_design]

    if missing:
        raise TraceError("{} 에 열이 없습니다: {}".format(path, missing))

    # **있어야 할 열이 없는 것도 소리 나게 한다.** 옛 판이라 없는 것과,
    # 파일이 깨져서 없는 것은 다르다. 앞의 것만 봐준다.
    surprise = [c for c in absent_by_design if c in fieldnames]

    if surprise:
        raise TraceError(
            "{} 는 {} 판인데 {} 열이 들어 있습니다. 머리말의 판 이름이 "
            "내용과 다릅니다.".format(path, schema, surprise)
        )

    rows = [_coerce_row(raw, absent_by_design) for raw in reader]

    if not rows:
        raise TraceError("{} 에 프레임 줄이 없습니다.".format(path))

    trace = Trace(_coerce_meta(meta), rows)

    _check_self_consistent(trace, path)

    return trace


def _check_self_consistent(trace, path):
    """줄 번호가 0 부터 1씩 오르는가. 시각이 그 번호와 맞는가.

    **조용한 실패를 소리 나게 만드는 자리입니다.** 줄이 빠진 trace 로 겹쳐 그리면
    영상은 멀쩡히 나오고 값만 밀립니다. 눈으로는 안 잡힙니다.
    """
    dt = trace.dt_s

    for index, row in enumerate(trace.rows):
        if row["frame"] != index:
            raise TraceError(
                "{}: {} 번째 줄의 frame 이 {} 입니다. {} 여야 합니다.".format(
                    path, index, row["frame"], index
                )
            )

        expected_t = index * dt

        if row["t_s"] is None or abs(row["t_s"] - expected_t) > 1.0e-6:
            raise TraceError(
                "{}: frame {} 의 t_s 가 {} 입니다. {:.6f} 여야 합니다.".format(
                    path, index, row["t_s"], expected_t
                )
            )


# ---------------------------------------------------------------- 대조


def _as_float(value):
    if value is None or value == "":
        return None

    return float(value)


def verify_against_row(trace, row, tolerance=0.002):
    """trace 를 접으면 판정 표의 그 줄이 나오는가.

    `record_flat_baseline.py` 가 「영상 속 판 = 표 속 판」을 대조로 보장하는 것과
    같은 뜻입니다. trace 는 그 판을 프레임마다 펼친 것이므로, **다시 접으면
    원래 값이 나와야 합니다.** 안 나오면 영상 위의 숫자를 믿을 수 없습니다.

    돌려주는 것은 `(항목, 표값, trace값, 차이, 통과여부)` 목록입니다.
    부르는 쪽이 하나라도 실패면 멈춥니다. 여기서는 안 죽입니다. 무엇이
    얼마나 틀렸는지 전부 보여 주고 나서 부르는 쪽이 판단하게 합니다.
    """
    checks = []

    def add(name, expected, got):
        if expected is None or got is None:
            checks.append((name, expected, got, None, False))
            return

        diff = abs(expected - got)
        checks.append((name, expected, got, diff, diff <= tolerance))

    fwd = [v for v in trace.column("fwd_m") if v is not None]
    lat = [v for v in trace.column("lat_m") if v is not None]
    err = [v for v in trace.column("vel_err_mps") if v is not None]

    add("duration_s", _as_float(row.get("duration_s")), trace.duration_s)

    add(
        "forward_progress_m",
        _as_float(row.get("forward_progress_m")),
        fwd[-1] if fwd else None,
    )

    add(
        "lateral_drift_m",
        _as_float(row.get("lateral_drift_m")),
        abs(lat[-1]) if lat else None,
    )

    add(
        "peak_lateral_drift_m",
        _as_float(row.get("peak_lateral_drift_m")),
        max(abs(v) for v in lat) if lat else None,
    )

    add(
        "velocity_mae_mps",
        _as_float(row.get("velocity_mae_mps")),
        sum(err) / len(err) if err else None,
    )

    return checks


# ---------------------------------------------------------------- 주춤 찾기


def slowdown_spans(trace, ratio=0.6, min_duration_s=0.15):
    """실제 속도가 명령의 `ratio` 아래로 `min_duration_s` 넘게 머문 구간.

    **팀이 지금 보려는 것이 이것입니다.** 「장애물 앞에서 주춤한다」를
    사람이 눈으로 세는 대신 재서 표시합니다. `hud.py` 가 이 구간을 속도
    그래프 아래 띠로 그리고, CLI 가 목록으로 찍습니다.

    기본값의 근거는 없습니다. **고르라고 인자로 뺐습니다.** 0.6 은
    「명령의 60% 아래」, 0.15초는 「걸음 하나(약 0.3초)의 절반」입니다.
    걸음마다 오르내리는 정상 변동을 구간으로 세지 않으려는 자리입니다.

    돌려주는 것은 `(시작초, 끝초, 그 구간 최저속도)` 목록입니다.
    """
    if not trace.rows:
        return []

    floor = trace.command_vx * ratio
    dt = trace.dt_s

    spans = []
    start = None
    lowest = None

    for row in trace.rows:
        speed = row.get("speed_mps")

        if speed is None:
            continue

        if speed < floor:
            if start is None:
                start = row["t_s"]
                lowest = speed
            elif speed < lowest:
                lowest = speed
        elif start is not None:
            end = row["t_s"]

            if end - start >= min_duration_s:
                spans.append((start, end, lowest))

            start = None
            lowest = None

    if start is not None:
        end = trace.rows[-1]["t_s"] + dt

        if end - start >= min_duration_s:
            spans.append((start, end, lowest))

    return spans


# ---------------------------------------------------------------- 판정 4축


def running_verdict(trace, row_at, gate_m, max_lateral_drift, max_velocity_mae,
                    min_progress_m, fell):
    """그 순간까지의 판정 4축 상태.

    **판이 끝난 뒤의 확정 판정이 아닙니다.** 「지금까지의 값으로 보면 어느 축이
    떨어지는 중인가」입니다. 그래서 «전진» 은 판 끝에 가서야 참이 될 수 있고,
    «방향» 은 통과선을 넘기 전에는 아직 물을 수 없습니다.

    돌려주는 것은 축 이름에서 `True` / `False` / `None` 으로 가는 딕셔너리입니다.
    `None` 은 **아직 물을 수 없다**는 뜻이고, 화면에서 회색으로 나갑니다.
    """
    if row_at is None:
        return {"survival": None, "progress": None,
                "tracking": None, "direction": None}

    upto = [r for r in trace.rows if r["t_s"] <= row_at["t_s"] + 1.0e-9]

    errors = [r["vel_err_mps"] for r in upto if r.get("vel_err_mps") is not None]
    mae = sum(errors) / len(errors) if errors else None

    fwd = row_at.get("fwd_m")

    # 방향은 통과선 위에서만 묻는다. 못 넘겼으면 아직 «미정» 이다.
    direction = None

    if fwd is not None and fwd >= gate_m:
        crossing = None
        previous = None

        for r in upto:
            f = r.get("fwd_m")
            l = r.get("lat_m")

            if f is None or l is None:
                continue

            if f >= gate_m:
                if previous is None:
                    crossing = abs(l)
                else:
                    bf, bl = previous
                    span = f - bf
                    t = 0.0 if span <= 0.0 else (gate_m - bf) / span
                    crossing = abs(bl + t * (l - bl))
                break

            previous = (f, l)

        if crossing is not None:
            direction = bool(crossing <= max_lateral_drift)

    return {
        "survival": (not fell) if fell is not None else None,
        "progress": bool(fwd >= min_progress_m) if fwd is not None else None,
        "tracking": bool(mae <= max_velocity_mae) if mae is not None else None,
        "direction": direction,
    }


def hypot(x, y):
    """평면 크기. `math.hypot` 을 한 자리에 모아 둔 것뿐입니다."""
    return math.hypot(x, y)
