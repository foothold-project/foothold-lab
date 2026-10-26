"""EX-35 창 판정의 기록 · 경고 축 계산 (카드 v0.9 4b.1 A1 · A7 · A8 · A9) 과 원자료 유한성 검사. CPU, Kit 없음.

- A7 몸 기울기: tilt = arccos(1 - 2(x^2 + y^2)) (root_quat = w x y z). env 별 (살아 있는 스텝) 평균 · p95, kept env 를 모은 뒤 중앙값. planner `tilt_slip.py` 와 같은 식.
- A8 접촉 링크 평면 속도: 네 발 링크 중 접촉력 > 1 N 인 링크의 link_xy_speed. env 별 평균 · p95 -> kept env 를 모은 뒤 중앙값. 접촉점 접선 속도가 아니라 «접촉 링크 평면 속도» 다.
- A1 보행 위상: 완전 주기만(두 처음 접촉 사이 구간이 모두 살아 있을 것), 대각 쌍(FL+RR 대 FR+RL) 사이 위상을 env 별로 재고 env 동일 가중 원형 평균. 기록 축(문턱 없음). analyst recompute.py 의 `phase` 와 같은 식.
- A9 학습 곡선: tfevents 의 창(최신 저장본 회차까지 50 회) 평균 6 개 + 비유한값 검사. 경고선은 카드 숫자 그대로, NaN 만 연장 불가.
- 유한성: 필수 원자료(살아 있는 스텝의 wz · vx · root_quat · 접촉력 · link_xy_speed, 평가 JSON 의 숫자)에 NaN · inf 가 있으면 목록으로 돌려준다(경고 문턱 초과와 구별).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from foothold_s2.eval import judge_stats as S

FEET = [4, 8, 14, 18]                       # 발 링크 번호 FL FR RL RR
HZ = 200
SIX = tuple(S.SIX_CASES)
FWD = ("fwd0.5", "fwd1.0")
MODES = ("eval_gt", "probe_prop_only")

A9_WARN = {                                 # 카드 4b.1 A9: 모두 경고(기록), 연장 불가는 NaN · 비유한값뿐
    "Loss/value_function": (">", 0.072), "Loss/kl_probe/ppo_mean": (">", 0.05), "Loss/entropy": ("<", 7.5),
    "Episode_Termination/bad_orientation": (">", 0.25), "Train/mean_reward": ("<", 11.9),
}
A9_TAGS = ("Loss/value_function", "Loss/kl_probe/ppo_mean", "Loss/entropy", "Policy/mean_noise_std", "Episode_Termination/bad_orientation", "Train/mean_reward")
A9_NOISE_RANGE = (0.35, 0.80)

A7_WARN = {"rot_mean_med": 8.0, "rot_p95_med": 14.0, "fwd_plus_deg": 1.5}      # A7 경고선(가정): 회전 여섯 평균 중앙값 <= 8.0 · p95 중앙값 <= 14, 전진 env 평균 <= 기준 + 1.5
A8_WARN = {"rot_mean_med": 0.12, "rot_p95_med": 0.40, "fwd_mult": 1.4}          # A8 경고선(가정): 회전 평균 중앙값 <= 0.12 · p95 <= 0.40, 전진 <= 기준 x 1.4


class AxisInputError(ValueError):
    """축을 계산할 자료가 없거나 모양이 틀리다(판정 불가로 올린다)."""


def _z(path):
    p = Path(path)

    if not p.is_file():
        raise AxisInputError("파일 없음: %s" % path)

    return np.load(p)


# ------------------------------------------------------------------ 유한성


def nonfinite_in_npz(path) -> list:
    """살아 있는 스텝의 wz · vx · root_quat · force · link_xy_speed 에 비유한값이 있으면 이름 목록."""
    z = _z(path)
    alive = z["alive"].astype(bool)
    bad = []

    for k in ("wz", "vx", "root_quat", "force", "link_xy_speed"):
        if k not in z.files:
            raise AxisInputError("%s 에 %s 배열이 없다" % (path, k))

        a = np.asarray(z[k], dtype=np.float64)
        m = alive if a.ndim == 2 else alive[..., None]
        sel = np.where(np.broadcast_to(m, a.shape), a, 0.0)

        if not np.isfinite(sel).all():
            bad.append(k)

    return bad


def nonfinite_in_json(obj, prefix="") -> list:
    out = []

    if isinstance(obj, dict):
        for k, v in obj.items():
            out += nonfinite_in_json(v, prefix + "/" + str(k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out += nonfinite_in_json(v, prefix + "[%d]" % i)
    elif isinstance(obj, float) and not math.isfinite(obj):
        out.append(prefix)

    return out


def finite_scan(d, cases, modes=("eval_gt", "probe_prop_only", "eval_pred")) -> list:
    """저장본 폴더의 필수 원자료 유한성. [{file, arrays}] 와 평가 JSON 의 비유한 경로."""
    d = Path(d)
    out = []

    for mode in modes:
        for c in cases:
            p = d / ("turn16_" + mode) / ("arrays_%s.npz" % c)
            bad = nonfinite_in_npz(p)

            if bad:
                out.append({"file": "turn16_%s/arrays_%s.npz" % (mode, c), "arrays": bad})

    for rel in ("map64/map_modes.json", "map64_eval_pred/map_modes.json", "hardlevel/L6/map_modes.json", "hardlevel/L9/map_modes.json"):
        p = d / rel

        if not p.is_file():
            raise AxisInputError("파일 없음: %s" % p)

        bad = nonfinite_in_json(json.loads(p.read_text(encoding="utf-8")))

        if bad:
            out.append({"file": rel, "json_paths": bad[:10]})

    return out


# ------------------------------------------------------------------ A7 · A8


def _per_env_tilt_slip(path):
    z = _z(path)
    alive, kept = z["alive"].astype(bool), z["kept"].astype(bool)
    q = z["root_quat"]
    x, y = q[..., 1], q[..., 2]
    tilt = np.degrees(np.arccos(np.clip(1.0 - 2.0 * (x * x + y * y), -1.0, 1.0)))
    on = z["force"][..., FEET] > 1.0
    sp = z["link_xy_speed"][..., FEET]
    rows = []

    for e in range(alive.shape[0]):
        a = alive[e]

        if not kept[e] or not a.any():
            continue

        t, c, s = tilt[e][a], on[e][a], sp[e][a]
        rows.append((float(t.mean()), float(np.percentile(t, 95)), float(s[c].mean()) if c.any() else float("nan"), float(np.percentile(s[c], 95)) if c.any() else float("nan")))

    return rows


def tilt_slip_axes(d, mode) -> dict:
    """한 모드: 회전 여섯 경우 kept env 모음의 중앙값, 전진 두 경우 env 동일 가중 평균. (planner tilt_slip.py 와 같은 정의)"""
    d = Path(d)
    rot, fwd = [], {}

    for c in SIX:
        rot += _per_env_tilt_slip(d / ("turn16_" + mode) / ("arrays_%s.npz" % c))

    for c in FWD:
        r = _per_env_tilt_slip(d / ("turn16_" + mode) / ("arrays_%s.npz" % c))

        if not r:
            raise AxisInputError("%s/%s: kept env 가 없다" % (mode, c))

        a = np.array(r, dtype=float)
        fwd[c] = {"tilt_mean_deg": float(np.nanmean(a[:, 0])), "slip_mean": float(np.nanmean(a[:, 2])), "n": len(r)}

    if not rot:
        raise AxisInputError("%s: 회전 여섯 경우에 kept env 가 없다" % mode)

    a = np.array(rot, dtype=float)
    med = np.nanmedian(a, axis=0)

    return {"rot_env": len(rot), "rot_tilt_mean_med": float(med[0]), "rot_tilt_p95_med": float(med[1]), "rot_slip_mean_med": float(med[2]), "rot_slip_p95_med": float(med[3]), "fwd": fwd}


# ------------------------------------------------------------------ A1


def _hits(on, valid):
    return np.flatnonzero((~on[:-1]) & on[1:] & valid[:-1] & valid[1:]) + 1


def pair_phase_env(a, b, valid):
    """완전 주기만. 반환 (각도 목록, 주기 목록(s))."""
    ha, hb = _hits(a, valid), _hits(b, valid)
    angles, periods = [], []

    for lo, hi in zip(ha[:-1], ha[1:]):
        if not valid[lo:hi + 1].all():
            continue

        ch = hb[(hb >= lo) & (hb < hi)]

        if len(ch):
            angles.append(360.0 * (ch[0] - lo) / (hi - lo))
            periods.append((hi - lo) / HZ)

    return angles, periods


def gait_phase_axis(d, mode, cases=FWD) -> dict:
    """전진 두 경우: kept env 마다 대각 쌍(FL+RR 대 FR+RL) 위상을 재고, env 동일 가중 원형 평균(도)과 집중도 R · 유효 주기 수."""
    out = {}

    for c in cases:
        z = _z(Path(d) / ("turn16_" + mode) / ("arrays_%s.npz" % c))
        alive, kept = z["alive"].astype(bool), z["kept"].astype(bool)
        on = z["force"][..., FEET] > 1.0
        env_deg, cycles, periods = [], 0, []

        for e in range(alive.shape[0]):
            if not kept[e]:
                continue

            v = alive[e]
            ang, per = pair_phase_env(on[e][:, 0] & on[e][:, 3], on[e][:, 1] & on[e][:, 2], v)
            cycles += len(ang)
            periods += per

            if ang:
                zc = np.mean(np.exp(1j * np.asarray(ang) * np.pi / 180))

                if abs(zc) >= 1e-8:
                    env_deg.append(float(np.angle(zc) * 180 / np.pi % 360))

        if env_deg:
            zc = np.mean(np.exp(1j * np.asarray(env_deg) * np.pi / 180))
            out[c] = {"deg": float(np.angle(zc) * 180 / np.pi % 360), "R": float(abs(zc)), "envs_with_cycles": len(env_deg), "cycles": cycles, "period_median_s": float(np.median(periods))}
        else:
            out[c] = {"deg": None, "R": None, "envs_with_cycles": 0, "cycles": cycles, "period_median_s": None}

    return out


# ------------------------------------------------------------------ A9


def _scalar_events(run_dir):
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

    ea = EventAccumulator(str(run_dir), size_guidance={"scalars": 0})
    ea.Reload()

    return ea


LOG_PERIOD_UPDATES = 1            # 로거 계약: rsl_rl 학습 runner 가 update 마다 기록한다(start_runner.py 의 log 호출). 남은 자료에서 주기를 추정하지 않는다


def _window_complete(tag, allsteps, steps, end_it, window):
    """창 입력 완전성: 계약 주기(1 update)로 창 (end_it-window, end_it] 의 모든 step 이 한 번씩 있어야 한다. 모자라면 AxisInputError(= HOLD_NO_DATA)."""
    period, need = LOG_PERIOD_UPDATES, window // LOG_PERIOD_UPDATES
    got = sorted(steps)
    lo = end_it - window

    if len(set(got)) != len(got):
        raise AxisInputError("%s: 창 (%d, %d] 에 같은 step 이 두 번 이상 있다(중복 기록)" % (tag, lo, end_it))

    if end_it - got[-1] >= period:
        raise AxisInputError("%s: 창 끝 %d 에 기록이 없다(마지막 %d, 기대 주기 %d)" % (tag, end_it, got[-1], period))

    edges = [lo] + got
    gaps = [(a, b) for a, b in zip(edges, edges[1:]) if b - a > period]

    if gaps:
        raise AxisInputError("%s: 창 안에 빠진 구간이 있다(기대 주기 %d): %s" % (tag, period, gaps[:3]))

    if len(got) != need:
        raise AxisInputError("%s: 창 안 기록 %d 개 != 기대 %d (기대 주기 %d update)" % (tag, len(got), need, period))


def curve_axis(run_dir, end_it, window=50) -> dict:
    """학습 폴더 tfevents 의 (end_it - window, end_it] 창 평균 6 개와 비유한값. 경고는 카드 A9 숫자. 태그가 없으면 AxisInputError."""
    ea = _scalar_events(run_dir)
    have = set(ea.Tags().get("scalars", []))
    miss = [t for t in A9_TAGS if t not in have]

    if miss:
        raise AxisInputError("tfevents 에 태그 없음: %s" % miss)

    out, nonfinite, warn = {}, [], []

    for t in A9_TAGS:
        allsteps = np.array([e.step for e in ea.Scalars(t)], dtype=np.int64)
        ev = [e for e in ea.Scalars(t) if end_it - window < e.step <= end_it]

        if not ev:
            raise AxisInputError("%s: 창 (%d, %d] 에 기록이 없다" % (t, end_it - window, end_it))

        _window_complete(t, allsteps, [e.step for e in ev], end_it, window)

        vals = np.array([e.value for e in ev], dtype=np.float64)

        if not np.isfinite(vals).all():
            nonfinite.append(t)

        m = float(np.nanmean(vals)) if np.isfinite(vals).any() else float("nan")
        out[t] = {"mean": m, "n": len(ev)}

        if t in A9_WARN and math.isfinite(m):
            op, lim = A9_WARN[t]

            if (op == ">" and m > lim) or (op == "<" and m < lim):
                warn.append({"tag": t, "mean": m, "limit": lim, "op": op})

    ns = out["Policy/mean_noise_std"]["mean"]

    if math.isfinite(ns) and not (A9_NOISE_RANGE[0] <= ns <= A9_NOISE_RANGE[1]):
        warn.append({"tag": "Policy/mean_noise_std", "mean": ns, "limit": list(A9_NOISE_RANGE), "op": "range"})

    return {"window": [end_it - window, end_it], "tags": out, "nonfinite_tags": nonfinite, "warnings": warn}


def a7_a8_warnings(cur: dict, base: dict) -> list:
    """A7 · A8 경고(기록, 멈춤 아님). 문턱은 카드 숫자 그대로(회전: 절대, 전진: 기준 + 1.5° · 기준 x 1.4)."""
    w = []

    for key, lim, nm in (("rot_tilt_mean_med", A7_WARN["rot_mean_med"], "A7 회전 기울기 평균 중앙값"), ("rot_tilt_p95_med", A7_WARN["rot_p95_med"], "A7 회전 기울기 p95 중앙값"),
                         ("rot_slip_mean_med", A8_WARN["rot_mean_med"], "A8 회전 접촉 링크 속도 평균 중앙값"), ("rot_slip_p95_med", A8_WARN["rot_p95_med"], "A8 회전 접촉 링크 속도 p95 중앙값")):
        if not cur[key] <= lim:
            w.append({"axis": nm, "value": cur[key], "limit": lim})

    for c in FWD:
        if not cur["fwd"][c]["tilt_mean_deg"] <= base["fwd"][c]["tilt_mean_deg"] + A7_WARN["fwd_plus_deg"]:
            w.append({"axis": "A7 전진 %s 기울기 평균" % c, "value": cur["fwd"][c]["tilt_mean_deg"], "limit": base["fwd"][c]["tilt_mean_deg"] + A7_WARN["fwd_plus_deg"]})

        if not cur["fwd"][c]["slip_mean"] <= base["fwd"][c]["slip_mean"] * A8_WARN["fwd_mult"]:
            w.append({"axis": "A8 전진 %s 접촉 링크 속도 평균" % c, "value": cur["fwd"][c]["slip_mean"], "limit": base["fwd"][c]["slip_mean"] * A8_WARN["fwd_mult"]})

    return w
