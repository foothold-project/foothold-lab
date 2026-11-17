"""EX-42 E2~E5 「새 학습이 되는지」 재는 축 (planner DESIGN-E2E5-LEARNING-AXES-1117 v0.1 · 5a2e88ea). CPU 탐침 출력 (env_arrays npz · extra npz) 을 한 표로.

세 줄:  (가) 유지  = 느린 걸음 탐침 (실제 속도 · 성공 수) + 속도 추정 기울기 + 연속 지형 한 열 (생존 · 전진 거리)
        (나) 새 종  = 그 단계가 연 종 (checkpoint 의 열린 종 · 레벨 상한) 의 고정 열에서 «기준선 도달 · 끝까지 생존 · 넘어짐» 을 따로 센 세 숫자 (합치지 않음)
        (다) 지도   = 복원 지도 대 정답 지도 · 칸별 오차 (종류별) + 구멍 칸 (놓친 · 없는) 비율

값 (구멍 문턱 0.1 m · 느린 띠 · 창 100 step) 은 설계 초안의 가정이고, 여기서 정한 정의는 각 함수 docstring 에 적는다. 이 모듈은 numpy 만 쓴다 (CPU · Kit 없음).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

HOLE_DROP_M = 0.1           # 설계 초안 가정: 구멍 = 양옆 칸이 이 값 이상 높은 칸
HOLE_REACH_CELLS = 2        # 양옆을 보는 칸 수 (한 축에서 왼쪽 · 오른쪽 각각 1~REACH 칸 가운데 가장 높은 것)
HOLE_COLUMNS = ("hole_n", "missed_n", "nonhole_n", "false_n", "hole_abs_sum", "nonhole_abs_sum")
SLOW_WINDOW_START = 100     # line50.py 와 같은 창: 처음 100 step 은 걸음이 자리 잡는 시간
STALL_M = 0.25              # 가정: 끝까지 살았는데 시작에서 이만큼도 못 간 env = 「멈춘」 것
SLOPE_MIN_ENVS = 8


# ---------------------------------------------------------------- 구멍 칸 (다-2)
def hole_mask(m, drop: float = HOLE_DROP_M, reach: int = HOLE_REACH_CELLS) -> np.ndarray:
    """(..., R, C) 높이 지도 -> 같은 모양 bool. 한 칸이 «구멍» = 같은 줄 또는 같은 열에서 양쪽 모두, 1~reach 칸 안에 그 칸보다 drop 이상 높은 칸이 있다.
    한쪽만 높은 칸 (계단 모서리 · 비탈) 은 구멍이 아니다. 지도 가장자리 밖은 칸이 없는 것으로 본다 (그쪽은 높지 않음). 비유한 칸은 구멍도 이웃도 아니다."""
    a = np.asarray(m, dtype=np.float64)
    a = np.where(np.isfinite(a), a, -np.inf)                       # 비유한 칸은 높은 이웃이 될 수 없고, 구멍이 되지도 않게 아래에서 거른다
    finite = np.isfinite(np.asarray(m, dtype=np.float64))
    out = np.zeros(a.shape, dtype=bool)
    for axis in (-2, -1):
        size = a.shape[axis]
        lo = np.full(a.shape, -np.inf)
        hi = np.full(a.shape, -np.inf)
        for d in range(1, reach + 1):
            if d >= size:
                break
            sl_dst_l = [slice(None)] * a.ndim; sl_src_l = [slice(None)] * a.ndim
            sl_dst_l[axis] = slice(d, None); sl_src_l[axis] = slice(0, size - d)       # lo[i] = a[i - d]
            lo[tuple(sl_dst_l)] = np.maximum(lo[tuple(sl_dst_l)], a[tuple(sl_src_l)])
            sl_dst_r = [slice(None)] * a.ndim; sl_src_r = [slice(None)] * a.ndim
            sl_dst_r[axis] = slice(0, size - d); sl_src_r[axis] = slice(d, None)       # hi[i] = a[i + d]
            hi[tuple(sl_dst_r)] = np.maximum(hi[tuple(sl_dst_r)], a[tuple(sl_src_r)])
        out |= (lo - a >= drop) & (hi - a >= drop)
    return out & finite


def hole_stats(refined, gt_map, drop: float = HOLE_DROP_M, reach: int = HOLE_REACH_CELLS) -> np.ndarray:
    """(N, R, C) 두 지도 -> (N, 6) = HOLE_COLUMNS 순서의 한 step 값.
    hole_n = 정답이 구멍인 칸 수 · missed_n = 그 가운데 복원 지도가 구멍으로 안 그린 칸 (같은 규칙을 복원 지도에 적용) · nonhole_n = 정답이 구멍이 아닌 칸 수 ·
    false_n = 그 가운데 복원 지도가 구멍으로 그린 칸 (없는 구멍) · hole_abs_sum / nonhole_abs_sum = 각 칸 집합의 |복원 - 정답| 합 [m]."""
    r = np.asarray(refined, dtype=np.float64)
    g = np.asarray(gt_map, dtype=np.float64)
    if r.shape != g.shape or r.ndim != 3:
        raise ValueError("hole_stats needs two (N, R, C) maps of the same shape")
    hg, hr = hole_mask(g, drop, reach), hole_mask(r, drop, reach)
    err = np.abs(np.where(np.isfinite(r), r, np.nan) - g)
    ok = np.isfinite(err)
    n = r.shape[0]
    out = np.zeros((n, len(HOLE_COLUMNS)), dtype=np.float64)
    flat = lambda x: x.reshape(n, -1)                                                    # noqa: E731
    out[:, 0] = flat(hg & ok).sum(1)
    out[:, 1] = flat(hg & ~hr & ok).sum(1)
    out[:, 2] = flat(~hg & ok).sum(1)
    out[:, 3] = flat(~hg & hr & ok).sum(1)
    out[:, 4] = np.where(flat(hg & ok), flat(np.nan_to_num(err)), 0.0).sum(1)
    out[:, 5] = np.where(flat(~hg & ok), flat(np.nan_to_num(err)), 0.0).sum(1)
    return out


def hole_summary(stats, alive) -> dict:
    """stats (S, N, 6) · alive (S, N) bool -> 살아 있는 step 만 합친 비율. 구멍 칸이 하나도 없으면 missed_frac 은 None (값 없음 · 0 이 아니다)."""
    s = np.asarray(stats, dtype=np.float64)
    al = np.asarray(alive, dtype=bool)
    if s.shape[:2] != al.shape:
        raise ValueError("hole stats and alive shapes differ: %s vs %s" % (s.shape, al.shape))
    s = np.where(np.isfinite(s) & al[..., None], s, 0.0).sum((0, 1))
    hole, missed, nonhole, false, hole_abs, nonhole_abs = (float(x) for x in s)
    return {"hole_cells": hole, "missed_hole_frac": (missed / hole) if hole > 0 else None,
            "false_hole_frac": (false / nonhole) if nonhole > 0 else None,
            "hole_abs_err_cm": (100.0 * hole_abs / hole) if hole > 0 else None,
            "nonhole_abs_err_cm": (100.0 * nonhole_abs / nonhole) if nonhole > 0 else None}


# ---------------------------------------------------------------- 가-1 느린 걸음 (planner line50.py 와 같은 식)
def keep_cell(true, command, *, s0: int = SLOW_WINDOW_START) -> dict:
    """한 칸 (명령 한 개 · 한 모드) 의 (S, N, 3) 실제 몸 속도 -> 명령 축의 실제 평균 속도와 성공 수.
    성공 = env 의 창 평균 / 명령 이 0.8~1.2 이고, 25 step 평균과 명령의 평균 절대 차 (MAE) 가 명령의 20 % 이하. line50.py one() 과 같은 식 (그 파일은 planner 폴더)."""
    c = np.asarray(command, dtype=np.float64)
    ax = 0 if abs(c[0]) > 0 else 1
    cmd = float(c[ax])
    t = np.asarray(true, dtype=np.float64)[s0:, :, ax]
    r = t.mean(0) / cmd
    n = t.shape[0] // 25
    mae = np.abs(t[:n * 25].reshape(n, 25, -1).mean(1) - cmd).mean(0)
    ok = int(((r >= 0.8) & (r <= 1.2) & (mae <= 0.2 * abs(cmd))).sum())
    return {"actual": float(t.mean()), "ok": ok, "mae_over": int((mae > 0.2 * abs(cmd)).sum()), "axis": ax, "command": cmd}


# ---------------------------------------------------------------- 가-2 속도 추정 기울기
def slope_fit(true_x, est_x, *, window_start: int = SLOW_WINDOW_START) -> dict:
    """한 모드의 느린 걸음 칸들 -> env 마다 시간 평균 (실제, 추정) 점을 모아 est = intercept + slope * true 로 최소제곱.
    true_x, est_x: (S, N) 이거나 그런 배열의 list (칸마다). 점 = (칸 × env) · env 평균은 window_start 이후 step.
    slope = 실제를 0.01 바꿨을 때 추정이 따라 움직이는 비율 (1 이 이상) · intercept = 실제 0 에서의 추정 (영점). 점이 SLOPE_MIN_ENVS 개 미만이거나 실제 값이 퍼지지 않으면 None."""
    ts = true_x if isinstance(true_x, (list, tuple)) else [true_x]
    es = est_x if isinstance(est_x, (list, tuple)) else [est_x]
    if len(ts) != len(es):
        raise ValueError("slope_fit: true and est lists differ in length")
    xs, ys = [], []
    for t, e in zip(ts, es):
        t, e = np.asarray(t, dtype=np.float64), np.asarray(e, dtype=np.float64)
        n = min(len(t), len(e))
        xs.append(t[window_start:n].mean(0)); ys.append(e[window_start:n].mean(0))
    x, y = np.concatenate(xs), np.concatenate(ys)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if x.size < SLOPE_MIN_ENVS or float(x.std()) < 1e-6:
        return {"slope": None, "intercept": None, "points": int(x.size), "true_std": float(x.std()) if x.size else None}
    slope, intercept = np.polyfit(x, y, 1)
    return {"slope": float(slope), "intercept": float(intercept), "points": int(x.size), "true_std": float(x.std())}


# ---------------------------------------------------------------- 나 새 종: 세 숫자
def kind_counts(arrays: dict, anchor: dict | None, *, settle_s: float, envs: int) -> dict:
    """한 종 칸의 env_arrays (alive · dones · dt · root_x_local_m · root_y_local_m) -> 세 숫자를 따로.
    reached = 기준선 (anchor) 에 닿은 env 수 (닿은 뒤 살아 있었는지는 묻지 않음) · survived = 끝까지 산 env 수 · fell = 중간에 끝난 (넘어짐 · 빠짐) env 수 ·
    completed = 공식 규칙 (닿고 settle_s 동안 계속 생존) 을 통과한 수. anchor 가 None 이면 기준선이 없는 종이라 reached · completed 는 None (값 없음).
    평균 이동 속도 [m/s] = 끝까지 산 env 의 시작에서 끝까지 직선 거리 / 시간 · 멈춘 비율 = 끝까지 산 env 가운데 그 거리가 STALL_M 미만인 비율."""
    alive = np.asarray(arrays["alive"], dtype=bool)
    x = np.asarray(arrays["root_x_local_m"], dtype=np.float64)
    dt = float(np.asarray(arrays["dt"]))
    if alive.shape != x.shape or alive.shape[1] != envs:
        raise ValueError("kind trace shape differs from the env count")
    survived_mask = alive[-1]
    fell = int((~survived_mask).sum())
    y = np.asarray(arrays["root_y_local_m"], dtype=np.float64)
    moved = np.hypot(x[-1] - x[0], y[-1] - y[0])               # 시작 방향이 무작위일 수 있어 +x 가 아니라 이동 거리의 크기로 센다 (m50 실측: +x 전진은 -3 ~ +3 m 로 퍼짐)
    seconds = alive.shape[0] * dt
    surv_moved = moved[survived_mask]
    out = {"envs": envs, "survived": int(survived_mask.sum()), "fell": fell,
           "mean_forward_speed": float(surv_moved.mean() / seconds) if surv_moved.size else None,
           "stalled_frac": float((surv_moved < STALL_M).mean()) if surv_moved.size else None,
           "reached": None, "completed": None}
    if anchor is not None:
        from foothold_s2.eval.ex42_kind_completion import score_with_anchor

        scored = score_with_anchor({"root_x_local_m": x, "root_y_local_m": np.asarray(arrays["root_y_local_m"], dtype=np.float64),
                                    "alive": alive, "dt": dt}, anchor, settle_s=settle_s, envs=envs)
        out["reached"] = sum(r["first_reach_step"] is not None for r in scored["per_env"])
        out["completed"] = int(scored["success_count"])
    return out


def continuous_counts(arrays: dict, *, envs: int) -> dict:
    """가-3: 연속 지형 한 열. 생존 수 · 평균 이동 거리 [m] (env 별 시작에서 마지막으로 살아 있던 자리까지의 직선 거리 · 방향 무관). 키 이름 mean_forward_m 는 표 호환용."""
    alive = np.asarray(arrays["alive"], dtype=bool)
    x = np.asarray(arrays["root_x_local_m"], dtype=np.float64)
    if alive.shape != x.shape or alive.shape[1] != envs:
        raise ValueError("continuous trace shape differs from the env count")
    last = np.where(alive.any(0), alive.shape[0] - 1 - np.argmax(alive[::-1], axis=0), 0)
    y = np.asarray(arrays["root_y_local_m"], dtype=np.float64)
    dist = np.hypot(x[last, np.arange(envs)] - x[0], y[last, np.arange(envs)] - y[0])
    return {"envs": envs, "survived": int(alive[-1].sum()), "mean_forward_m": float(dist.mean())}


# ---------------------------------------------------------------- 한 줄 표
def _fmt(v, spec="{:.3f}", none="-"):
    return none if v is None or (isinstance(v, float) and not math.isfinite(v)) else spec.format(v)


def percentile_or_none(values, q):
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    return float(np.quantile(v, q)) if v.size else None


def format_line(it: int, row: dict) -> str:
    """row = {"keep": {"fwd0.1": {...}}, "slope": {"gt": {...}, "pred": {...}}, "continuous": {...}, "kinds": {kind: {mode: counts}}, "map": {kind: {mode: {...}}}}.
    GT 열 | 복원 열 두 열로 적는다 (design 2 절 · 정답 지도 | 복원 지도)."""
    parts = [f"m{it}"]
    keep = row.get("keep") or {}
    for name in ("fwd0.1", "side+0.2", "side-0.2", "fwd0.3"):
        c = keep.get(name)
        if c:
            parts.append(f"{name} 실제 {_fmt(c['gt']['actual'], '{:+.3f}')}|{_fmt(c['pred']['actual'], '{:+.3f}')} 성공 {c['gt']['ok']}|{c['pred']['ok']}")
    sl = row.get("slope") or {}
    if sl:
        parts.append("추정 기울기 %s|%s 영점 %s|%s" % (_fmt((sl.get('gt') or {}).get('slope'), '{:.2f}'), _fmt((sl.get('pred') or {}).get('slope'), '{:.2f}'),
                                                   _fmt((sl.get('gt') or {}).get('intercept'), '{:+.3f}'), _fmt((sl.get('pred') or {}).get('intercept'), '{:+.3f}')))
    ct = row.get("continuous")
    if ct:
        parts.append(f"연속 {ct['kind']} L{ct['level']} 생존 {ct['gt']['survived']}|{ct['pred']['survived']} 전진 {_fmt(ct['gt']['mean_forward_m'], '{:.2f}')}|{_fmt(ct['pred']['mean_forward_m'], '{:.2f}')}")
    for kind, cells in (row.get("kinds") or {}).items():
        g, p = cells.get("eval_gt"), cells.get("eval_pred")
        if not g or not p:
            parts.append(f"새 종 {kind} 값 없음")
            continue
        parts.append(f"새 종 {kind} 도달 {_fmt(g['reached'], '{}')}|{_fmt(p['reached'], '{}')} 생존 {g['survived']}|{p['survived']} 넘어짐 {g['fell']}|{p['fell']} "
                     f"속도 {_fmt(g['mean_forward_speed'], '{:.2f}')}|{_fmt(p['mean_forward_speed'], '{:.2f}')} 멈춤 {_fmt(g['stalled_frac'], '{:.2f}')}|{_fmt(p['stalled_frac'], '{:.2f}')}")
    for kind, modes in (row.get("map") or {}).items():
        m = modes.get("eval_pred") or {}
        parts.append(f"지도 {kind} 오차 평균 {_fmt(m.get('err_mean_cm'), '{:.1f}')}cm p90 {_fmt(m.get('err_p90_cm'), '{:.1f}')}cm 놓친구멍 {_fmt(m.get('missed_hole_frac'), '{:.2f}')} 없는구멍 {_fmt(m.get('false_hole_frac'), '{:.3f}')}")
    return " · ".join(parts)


def write_table(path, it: int, row: dict) -> str:
    line = format_line(it, row)
    Path(path).write_text(json.dumps({"it": it, "row": row, "line": line}, ensure_ascii=False, indent=1, default=lambda o: None if o is None else str(o)), encoding="utf-8")
    return line
