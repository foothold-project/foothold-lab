"""N1 Kit 확인의 계산부 (설계 §3.1 · 팀장 11/16 결정 3): 같은 무작위 명령을 정답 지도 (eval_gt) 와 복원 지도 (eval_pred) 로 한 번씩 굴려
추종 오차 95 분위를 나란히 적고, 차이가 20 % 를 넘으면 teacher 도 복원 지도로 돌린다. numpy 만 쓴다 (CPU 시험).

입력은 `NavState.track_err` 를 상위 틱마다 쌓은 (T, hold, n, 3) 과 `done_step` (T, n) 이다. 끝난 env 의 끝난 하위 스텝부터 그 에피소드 안의
나머지 스텝은 버린다 (Isaac 가 되돌린 새 에피소드의 값이 섞이지 않게). 20 % 는 「전체 L2 오차의 95 분위」 의 상대 차이로 센다 (가정: 칸별 값은 같이 적되 결정은 전체 한 값).
"""
from __future__ import annotations

import numpy as np

THRESHOLD = 0.20
QUANTILE = 0.95
CHANNELS = ("vx", "vy", "wz")


def valid_mask(done_step: np.ndarray, hold: int) -> np.ndarray:
    """(T, n) done_step (-1 = 안 끝남) -> (T, hold, n) 쓸 수 있는 하위 스텝. 끝난 스텝은 포함, 그 뒤는 제외."""
    d = np.asarray(done_step)
    k = np.arange(hold)[None, :, None]
    ended = d[:, None, :] >= 0
    return ~ended | (k <= d[:, None, :])


def p95(track_err: np.ndarray, done_step: np.ndarray, quantile: float = QUANTILE) -> dict:
    e = np.asarray(track_err, dtype=np.float64)
    if e.ndim != 4 or e.shape[-1] != 3 or not np.isfinite(e).all():
        raise ValueError("track_err must be a finite (T, hold, n, 3) array")
    m = valid_mask(done_step, e.shape[1])
    if m.shape != e.shape[:3]:
        raise ValueError("done_step must be (T, n)")
    if not m.any():
        raise ValueError("no usable lower steps")
    sel = e[m]                                              # (k, 3)
    norm = np.linalg.norm(sel, axis=1)
    return {"samples": int(len(sel)), "l2": float(np.quantile(norm, quantile)),
            **{c: float(np.quantile(np.abs(sel[:, i]), quantile)) for i, c in enumerate(CHANNELS)}}


def compare_maps(gt: dict, pred: dict, *, threshold: float = THRESHOLD) -> dict:
    """gt · pred = `p95` 의 결과. 결정: 복원 지도 오차가 정답 지도 오차보다 threshold 넘게 다르면 (어느 쪽으로든) teacher 도 복원 지도."""
    base = max(gt["l2"], 1e-9)
    rel = {k: abs(pred[k] - gt[k]) / max(gt[k], 1e-9) for k in ("l2", *CHANNELS)}
    return {"gt": gt, "pred": pred, "relative_difference": rel, "threshold": threshold,
            "teacher_map": "recon" if abs(pred["l2"] - gt["l2"]) / base > threshold else "gt"}
