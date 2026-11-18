#!/usr/bin/env python3
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path


JOINTS = (
    "FR_hip", "FR_thigh", "FR_calf", "FL_hip", "FL_thigh", "FL_calf",
    "RR_hip", "RR_thigh", "RR_calf", "RL_hip", "RL_thigh", "RL_calf",
)


def finite(values):
    return [value for value in values if math.isfinite(value)]


def floats(rows, field):
    return [float(row[field]) for row in rows]


def summarize(rows):
    if not rows:
        raise ValueError("monitor CSV has no data rows")

    body_heights = finite([
        float(row.get("body_height", "nan")) for row in rows
    ])
    body_height_mean = (
        sum(body_heights) / len(body_heights) if body_heights else None
    )
    body_height_stddev = (
        math.sqrt(sum((value - body_height_mean) ** 2 for value in body_heights)
                  / len(body_heights))
        if body_heights else None
    )

    result = {
        "samples": len(rows),
        "duration_s": floats(rows, "t_s")[-1] - floats(rows, "t_s")[0],
        "callback_delta": {
            key: int(rows[-1][key]) - int(rows[0][key])
            for key in (
                "state_callbacks", "cmd_callbacks", "sport_callbacks",
                "error_callbacks",
            )
        },
        "message_age_ms_max": {
            key: max(finite(floats(rows, key)), default=None)
            for key in ("state_age_ms", "cmd_age_ms", "sport_age_ms")
        },
        "soc_pct": {
            "start": int(rows[0]["soc_pct"]),
            "end": int(rows[-1]["soc_pct"]),
        },
        "sport_marker_counts": dict(Counter(row["sport_error_code"] for row in rows)),
        "sport_mode_counts": dict(Counter(row.get("sport_mode", "") for row in rows)),
        "gait_type_counts": dict(Counter(row.get("gait_type", "") for row in rows)),
        "body_height_m": {
            "samples": len(body_heights),
            "mean": body_height_mean,
            "population_stddev": body_height_stddev,
            "min": min(body_heights) if body_heights else None,
            "max": max(body_heights) if body_heights else None,
        },
        "error_callbacks_end": int(rows[-1]["error_callbacks"]),
        "motors": {},
    }

    global_max = (-math.inf, None)
    for joint in JOINTS:
        temperatures = floats(rows, f"temp_{joint}")
        reserves = [int(row[f"reserve0_{joint}"]) for row in rows]
        lost = [int(row[f"lost_{joint}"]) for row in rows]
        kp = finite(floats(rows, f"kp_{joint}"))
        kd = finite(floats(rows, f"kd_{joint}"))
        motor = {
            "temp_c": {
                "start": temperatures[0],
                "max": max(temperatures),
                "end": temperatures[-1],
            },
            "reserve0_nonzero_samples": sum(value != 0 for value in reserves),
            "reserve0_values": sorted(set(reserves)),
            "lost_max": max(lost),
            "kp_max": max(kp) if kp else None,
            "kd_max": max(kd) if kd else None,
        }
        result["motors"][joint] = motor
        if motor["temp_c"]["max"] > global_max[0]:
            global_max = (motor["temp_c"]["max"], joint)

    result["global_max_temp_c"] = global_max[0]
    result["global_max_temp_joint"] = global_max[1]
    return result


def main():
    if len(sys.argv) not in (2, 3):
        print(f"usage: {sys.argv[0]} MONITOR.csv [SUMMARY.json]", file=sys.stderr)
        return 2
    input_path = Path(sys.argv[1])
    with input_path.open(newline="", encoding="utf-8") as stream:
        summary = summarize(list(csv.DictReader(stream)))
    payload = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if len(sys.argv) == 3:
        Path(sys.argv[2]).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
