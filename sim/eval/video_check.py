# -*- coding: utf-8 -*-
"""찍은 영상이 **정말 찍혔는지** 본다.

분류: 운영
작성: Claude 세션 (오흥재 지시) · 2026-09-20
근거: 실측. `gap_vx0.5_H` 600 프레임이 전부 검정으로 나왔고 종료 코드는 0 이었다
요지: 프레임 수 · 바이트/프레임 · 밝기 · 렌더러 로그 넷을 보고 하나라도 어긋나면 죽는다
상태: 확정
판: v1.0

## 무엇이 있었나 `확인됨`

2026-09-20. `gap_vx0.5_H` 를 찍었는데 **600 프레임이 전부 완전한 검정**이었다.

- **종료 코드는 0** 이었다
- **mp4 도 trace 도 만들어졌다**
- **물리는 돌았다** · `trace.csv` 173 KB · 전진 2.24 m · MAE 0.181 이 다 살아 있다
- **HUD 패스도 성공**했다. 검은 화면 위에 계기를 곱게 그렸다

그래서 「실패 0」으로 보고됐고 배포본에 실려 팀장이 찾았다.

## 신호는 있었다

```
gap_vx0.5_H.mp4      33 KB · 55 바이트/프레임
gap_vx0.5_v1.mp4    960 KB · 1600 바이트/프레임
```

**33 KB 는 12 초짜리 1280x720 영상일 수가 없다.** 검정이라 압축이 거의 다
먹은 것이다. 그리고 `record.log` 에 답이 그대로 있었다.

```
[Warning] [omni.hydra.rtx] HydraEngine rtx failed creating scene renderer.
[Warning] [omni.usd] failed to add hydra engine - uid: 1024, name: 'rtx'
```

**아무도 안 읽었다.**

## 왜 넷을 다 보나

- **프레임 수**만 보면 검은 프레임도 세어진다
- **바이트/프레임**만 보면 «반쯤» 렌더된 것을 못 잡는다
- **밝기**가 핵심이다. 그런데 표본 몇 장만 보므로 그것만으로도 모자라다
- **로그**에 원인이 적혀 있다. 나머지 셋이 아슬아슬하게 통과해도 로그는 안다

`pillow` 도 `imageio` 도 없는 자리에서는 밝기를 못 재므로 **그때는 밝기만
건너뛰고 나머지를 본다.** 건너뛴 것을 통과로 보고하지 않는다.
"""

from __future__ import annotations

import os
import re

# 화면이 이보다 어두우면 안 찍힌 것으로 본다. 정상 컷은 176 ~ 189 였고
# 검은 컷은 0.0 이었다. 10 이면 둘을 가르고도 한참 남는다.
MIN_MEAN_LUMA = 10.0

# 1280x720 · crf 26 정상 컷이 1600 ~ 2600 바이트/프레임이었다. 검은 컷은 55 다.
MIN_BYTES_PER_FRAME = 200

# 이 줄이 로그에 있으면 렌더러가 안 떴다.
RENDERER_FAILURE = re.compile(
    r"(hydra.*fail|failed to add hydra|failed creating scene renderer)",
    re.IGNORECASE)


def renderer_failed(log_text):
    """로그에서 렌더러 실패 줄을 찾아 돌려준다. 없으면 빈 리스트."""
    return [line.strip() for line in log_text.splitlines()
            if RENDERER_FAILURE.search(line)]


def mean_luma(path, samples=5):
    """표본 프레임의 평균 밝기. 읽을 도구가 없으면 `None`.

    **`None` 을 통과로 보지 않는다.** 부르는 쪽이 「못 쟀다」로 적는다.
    """
    try:
        import imageio.v2 as imageio
        import numpy as np
    except ImportError:
        return None

    reader = imageio.get_reader(path)

    try:
        try:
            count = reader.count_frames()
        except Exception:  # noqa: BLE001
            return None

        if not count:
            return None

        picks = sorted({int(count * f) for f in
                        [(i + 1) / (samples + 1) for i in range(samples)]})
        values = []

        for index in picks:
            frame = np.asarray(reader.get_data(min(index, count - 1)))
            values.append(float(frame.mean()))
    finally:
        reader.close()

    return sum(values) / len(values) if values else None


# 한 프레임에 전진이 이만큼 «줄면» 리셋이다. 0.5 m/s 로 0.02 초에
# 되돌아갈 수 있는 거리가 아니다.
RESET_FWD_DROP_M = 0.30

# 한 프레임에 몸 높이가 이만큼 «뛰면» 리셋이다. 스폰 높이는 0.40 m 다.
RESET_Z_JUMP_M = 0.25


def split_attempts(rows):
    """trace 행을 **시도 단위로** 쪼갠다.

    **평가 하네스는 낙상에서 판을 끝내지만 녹화기는 안 끝낸다**
    (`record_terrain_demo.py:695` 가 `dones` 로 정책만 되돌린다). 그 사이
    **환경이 스스로 리셋**하므로 **한 컷 안에 여러 시도가 들어간다.**

    그러면 화면의 「전진 N m」는 **마지막 시도의 값**이지 컷 전체가 아니다.
    캡션을 「12 초에 2.24 m」로 쓰면 틀린다 `확인됨`.

    **두 가지로 잡는다.** 하나만 보면 놓친다.

    - 전진이 한 프레임에 `RESET_FWD_DROP_M` 넘게 «줄면»
    - 몸 높이가 한 프레임에 `RESET_Z_JUMP_M` 넘게 «뛰면»

    **앞선 판은 전진 낙차에 「직전 높이가 0.25 m 아래」를 «그리고» 로 묶었다가
    고리 앞에서 0.286 m 로 «서 있다» 리셋된 판을 놓쳤다** `확인됨`.
    뒤집히지 않고도 리셋된다. 없앤 것은 그 «추가 조건» 이다.

    실제로 아홉 컷에서 갈라진 세 자리는 **전부 전진 낙차로** 잡혔다. 높이
    도약은 **전진이 별로 안 줄면서 리셋되는 경우**(스폰 근처에서 뒤집힌 판)를
    받는 그물이다.

    돌려주는 것은 구간 목록이다. 하나면 한 판이다.
    """
    if not rows:
        return []

    cuts = []

    for index in range(1, len(rows)):
        before, here = rows[index - 1], rows[index]

        dropped = (before["fwd_m"] - here["fwd_m"]) > RESET_FWD_DROP_M
        jumped = (here["base_z_m"] - before["base_z_m"]) > RESET_Z_JUMP_M

        if dropped or jumped:
            cuts.append(index)

    segments = []
    start = 0

    for cut in cuts + [len(rows)]:
        chunk = rows[start:cut]

        if chunk:
            segments.append({
                "t_start_s": chunk[0]["t_s"],
                "t_end_s": chunk[-1]["t_s"],
                "reached_m": max(r["fwd_m"] for r in chunk),
                "max_abs_roll_deg": max(abs(r["roll_deg"]) for r in chunk),
                "frames": len(chunk),
            })

        start = cut

    return segments


def read_trace_rows(path):
    """trace CSV 에서 쪼개기에 필요한 열만 읽는다. 머리말(`#`)은 건너뛴다."""
    import csv

    with open(path, encoding="utf-8-sig") as handle:
        lines = [line for line in handle if not line.startswith("#")]

    rows = []

    for row in csv.DictReader(lines):
        try:
            rows.append({
                "t_s": float(row["t_s"]),
                "fwd_m": float(row["fwd_m"]),
                "base_z_m": float(row["base_z_m"]),
                "roll_deg": float(row["roll_deg"]),
            })
        except (KeyError, TypeError, ValueError):
            continue

    return rows


def verify_render(path, expected_frames=None, log_path=None,
                  min_mean_luma=MIN_MEAN_LUMA,
                  min_bytes_per_frame=MIN_BYTES_PER_FRAME,
                  samples=5):
    """찍은 영상을 검사한다. 어긋나면 `RuntimeError`.

    돌려주는 것은 잰 값 사전이다. **「못 쟀다」는 `None` 으로 남는다.**
    """
    problems = []
    report = {"path": path, "bytes": None, "frames": None,
              "bytes_per_frame": None, "mean_luma": None,
              "renderer_errors": []}

    if not os.path.isfile(path):
        raise RuntimeError("영상이 없다: %s" % path)

    report["bytes"] = os.path.getsize(path)

    if report["bytes"] == 0:
        raise RuntimeError("영상이 0 바이트다: %s" % path)

    # -- 렌더러 로그. 나머지가 통과해도 이것만으로 죽인다.
    if log_path and os.path.isfile(log_path):
        with open(log_path, encoding="utf-8", errors="replace") as handle:
            hits = renderer_failed(handle.read())

        report["renderer_errors"] = hits[:3]

        if hits:
            problems.append(
                "렌더러가 안 떴다. 로그에 이 줄이 있다:\n      " +
                "\n      ".join(hits[:3]))

    # -- 프레임 수
    luma = mean_luma(path, samples=samples)
    report["mean_luma"] = luma

    try:
        import imageio.v2 as imageio

        reader = imageio.get_reader(path)

        try:
            report["frames"] = reader.count_frames()
        finally:
            reader.close()
    except Exception:  # noqa: BLE001
        report["frames"] = None

    if report["frames"]:
        report["bytes_per_frame"] = report["bytes"] / report["frames"]

        if expected_frames is not None and report["frames"] != expected_frames:
            problems.append(
                "프레임이 %d 장인데 %d 장을 기대했다"
                % (report["frames"], expected_frames))

        if report["bytes_per_frame"] < min_bytes_per_frame:
            problems.append(
                "바이트/프레임이 %.0f 다 (문턱 %d). 화면이 거의 안 그려지면 "
                "압축이 다 먹어 이렇게 작아진다"
                % (report["bytes_per_frame"], min_bytes_per_frame))

    if luma is not None and luma < min_mean_luma:
        problems.append(
            "표본 프레임 평균 밝기가 %.1f 다 (문턱 %.0f). 화면이 검다"
            % (luma, min_mean_luma))

    if problems:
        raise RuntimeError(
            "찍힌 영상이 쓸 수 없다: %s\n  - %s"
            % (path, "\n  - ".join(problems)))

    return report
