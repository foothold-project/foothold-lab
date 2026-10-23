"""R/S/J 집계와 칸 요약. 순수 파이썬.

J <= R 이고 J <= S 가 늘 맞아야 한다 (41 §5). 한 행이라도 어기면 `RSJError` 로 죽는다.
집계 숫자는 행에서 센다. 손으로 쓰지 않는다.
"""

from foothold_s2.eval.stats import wilson


class RSJError(ValueError):
    """R/S/J 관계가 깨진 행 또는 집계."""


def check_row(row):
    """한 행의 R/S/J 일관성. `R` 이 None 이면(정지 · 제자리 회전) J 도 None 이어야 한다."""
    r, s, j = row.get("R_body"), row.get("S"), row.get("J_body")

    if r is None:
        if j is not None:
            raise RSJError("R 이 정의되지 않은 칸에 J=%r 가 있습니다" % (j,))
        return

    if j and not r:
        raise RSJError("J > R 인 행: R=%r S=%r J=%r" % (r, s, j))

    if j and not s:
        raise RSJError("J > S 인 행: R=%r S=%r J=%r" % (r, s, j))

    if j != bool(r and s):
        raise RSJError("J 가 R AND S 와 다릅니다: R=%r S=%r J=%r" % (r, s, j))


def _rate(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]

    if not vals:
        return {"n": 0, "k": 0, "rate": None, "lo": None, "hi": None}

    k = sum(1 for v in vals if v)
    lo, hi = wilson(k, len(vals))

    return {"n": len(vals), "k": k, "rate": k / len(vals), "lo": lo, "hi": hi}


def _mean(rows, key):
    vals = [float(r[key]) for r in rows if r.get(key) is not None]

    return sum(vals) / len(vals) if vals else None


def summarize_rsj(rows):
    """R/S/J 세 비율 + Wilson. 행마다 먼저 일관성을 본다."""
    for row in rows:
        check_row(row)

    out = {key: _rate(rows, key) for key in ("R_body", "S", "J_body")}

    if out["J_body"]["n"]:
        if out["J_body"]["k"] > min(out["R_body"]["k"], out["S"]["k"] if out["S"]["n"] else 0):
            raise RSJError("집계에서 J > min(R, S): %r" % (out,))

    return out


def summarize_axis1_cell(rows):
    """축 1 한 칸. 성분 넷 + R/S/J + 평균."""
    out = {"episodes": len(rows)}

    for key in ("overall_success", "survival_success", "progress_success",
                "tracking_success", "direction_success"):
        rate = _rate(rows, key)
        out[key] = rate["rate"]
        out[key + "_k"] = rate["k"]

    lo, hi = wilson(out["overall_success_k"], len(rows)) if rows else (None, None)
    out["overall_lo"], out["overall_hi"] = lo, hi

    rsj = summarize_rsj(rows)

    for key, val in rsj.items():
        out[key + "_rate"] = val["rate"]
        out[key + "_lo"] = val["lo"]
        out[key + "_hi"] = val["hi"]

    out["mean_forward_progress_m"] = _mean(rows, "forward_progress_m")
    out["mean_velocity_mae_mps"] = _mean(rows, "velocity_mae_mps")
    out["mean_lateral_drift_m"] = _mean(rows, "peak_lateral_drift_m")

    return out


def summarize_axis3_cell(rows):
    """축 3 한 칸. 방향 이탈은 따로 비율로 남긴다."""
    out = {"episodes": len(rows)}
    rsj = summarize_rsj(rows)

    for key, val in rsj.items():
        out[key + "_rate"] = val["rate"]
        out[key + "_n"] = val["n"]
        out[key + "_lo"] = val["lo"]
        out[key + "_hi"] = val["hi"]

    dev = _rate(rows, "yaw_dev_flag")
    out["yaw_dev_rate"] = dev["rate"]
    out["yaw_dev_n"] = dev["n"]
    out["yaw_dev_lo"], out["yaw_dev_hi"] = dev["lo"], dev["hi"]

    out["mean_cmd_progress_ratio"] = _mean(rows, "cmd_progress_ratio")
    out["mean_cmd_progress_ratio_capped"] = _mean(rows, "cmd_progress_ratio_capped")
    out["mean_velocity_mae_mps"] = _mean(rows, "velocity_mae_mps")
    out["mean_yaw_follow_ratio"] = _mean(rows, "yaw_follow_ratio")
    out["mean_yaw_dev_deg"] = _mean(rows, "yaw_dev_deg")
    out["mean_heading_err_deg"] = _mean(rows, "heading_err_deg")
    out["mean_lateral_dev_m"] = _mean(rows, "lateral_dev_m")
    out["mean_gate_lateral_dev_m"] = _mean(rows, "gate_lateral_dev_m")

    out["degenerate"] = degenerate_flag(out)

    return out


def degenerate_flag(summary):
    """시나리오 (d): 칸의 R · S · J 비율이 전부 0 이거나 전부 1 이면 칸 설계 문제일 수 있다.

    비율이 정의된 것(n > 0)만 본다. 정의된 것이 없으면 False.
    """
    rates = [summary[k + "_rate"] for k in ("R_body", "S", "J_body") if summary.get(k + "_n")]

    if not rates:
        return False

    return all(r == 0.0 for r in rates) or all(r == 1.0 for r in rates)
