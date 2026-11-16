"""N1 Kit 확인의 계산부 (설계 §3.1 · 팀장 11/16 결정 3): 같은 무작위 명령을 정답 지도 (eval_gt) 와 복원 지도 (eval_pred) 로 한 번씩 굴려
추종 오차 95 분위를 나란히 적고, 차이가 20 % 를 넘으면 teacher 도 복원 지도로 돌린다. numpy 만 쓴다 (CPU 시험).

입력은 `NavState.track_err` 를 상위 틱마다 쌓은 (T, hold, n, 3) 과 `done_step` (T, n) 이다. 끝난 env 의 끝난 하위 스텝 (재설정 직전 값) 과 그 뒤 나머지 스텝은 모두 버린다 (Isaac 가 되돌린 새 에피소드의 값이 섞이지 않게). 20 % 는 「전체 L2 오차의 95 분위」 의 상대 차이로 센다 (가정: 칸별 값은 같이 적되 결정은 전체 한 값).
"""
from __future__ import annotations

import numpy as np

THRESHOLD = 0.20
QUANTILE = 0.95
CHANNELS = ("vx", "vy", "wz")
CHANNEL_FLOOR = 0.02                  # 칸 하나로 recon 을 정하려면 절대 차이가 이 값 (m/s · rad/s) 이상이어야 한다 (planner (a))


def valid_mask(done_step: np.ndarray, hold: int) -> np.ndarray:
    """(T, n) done_step (-1 = 안 끝남) -> (T, hold, n) 쓸 수 있는 하위 스텝. 끝난 스텝과 그 뒤는 제외 (planner F1: 끝난 스텝의 값은
    넘어짐 · 재설정 순간이라 추종 오차가 아니다)."""
    d = np.asarray(done_step)
    k = np.arange(hold)[None, :, None]
    ended = d[:, None, :] >= 0
    return ~ended | (k < d[:, None, :])


def fall_counts(done_step: np.ndarray, timed_out: np.ndarray) -> dict:
    """맵 한 번의 끝남 요약: 끝난 틱 수 · 그중 시간 초과가 아닌 것 (= 낙상 · 충돌 등). 두 지도 사이 낙상 수 차이를 같이 적는다."""
    d, t = np.asarray(done_step) >= 0, np.asarray(timed_out, dtype=bool)
    if d.shape != t.shape:
        raise ValueError("done_step and timed_out must have the same (T, n) shape")
    return {"ended": int(d.sum()), "falls": int((d & ~t).sum()), "timed_out": int((d & t).sum())}


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
            **{c: float(np.quantile(np.abs(sel[:, i]), quantile)) for i, c in enumerate(CHANNELS)},
            "bias": {c: float(sel[:, i].mean()) for i, c in enumerate(CHANNELS)}}      # 부호 있는 칸별 평균 (실제 - 명령)


def compare_maps(gt: dict, pred: dict, *, threshold: float = THRESHOLD, channel_floor: float = CHANNEL_FLOOR,
                 commands_sha256: str | None = None, falls_gt: dict | None = None, falls_pred: dict | None = None) -> dict:
    """gt · pred = `p95` 의 결과. 결정 (planner (a)): 복원 지도로 돈 teacher 로 바꾼다 (recon) = 전체 L2 95 분위가 threshold 넘게 다르거나,
    칸 (vx vy wz) 하나가 threshold 넘게 다르면서 절대 차이가 channel_floor 이상 (아주 작은 값의 비율 잡음은 거른다). 어느 쪽으로 다르든 같다.
    commands_sha256 = 두 번 모두 같은 명령 열을 썼다는 증거 (호출한 쪽이 계산해 넣는다)."""
    rel = {k: abs(pred[k] - gt[k]) / max(gt[k], 1e-9) for k in ("l2", *CHANNELS)}
    absd = {k: abs(pred[k] - gt[k]) for k in ("l2", *CHANNELS)}
    why = []
    if rel["l2"] > threshold:
        why.append("l2")
    why += [c for c in CHANNELS if rel[c] > threshold and absd[c] >= channel_floor]
    return {"gt": gt, "pred": pred, "relative_difference": rel, "absolute_difference": absd, "threshold": threshold,
            "channel_floor": channel_floor, "recon_reasons": why, "teacher_map": "recon" if why else "gt",
            "bias_gt": gt.get("bias"), "bias_pred": pred.get("bias"), "commands_sha256": commands_sha256,
            "falls_gt": falls_gt, "falls_pred": falls_pred}
