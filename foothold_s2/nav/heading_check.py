"""학습 첫 회차 전 자체 점검: 하위만 몸 +x 로 1 초 걷게 한 뒤 월드 변위 방향이 (해석한 yaw) · (해석 yaw 로 돌린 vel_b 방향) 과 맞는지.
쿼터니언 순서 (Lab 2 wxyz · Lab 3 xyzw) 나 몸 틀 속도 해석이 틀리면 정책이 무엇을 배워도 틀린 방향이므로, 어긋나면 오류로 멈춘다 (Pod 돈을 아낀다).
순수 판정 `judge` (numpy · CPU 시험) 와 Kit 쪽 `run` (nav_env 를 직접 몬다: 과제 · 보상 · PGCL 은 건드리지 않음) 으로 나뉜다."""
from __future__ import annotations

import numpy as np

WALK_S = 1.0
MIN_DISP_M = 0.10
TOL_DEG = 30.0
MIN_FRAC = 0.10


def _wrap_deg(a):
    return np.degrees(np.abs((a + np.pi) % (2 * np.pi) - np.pi))


def judge(yaw_samples, vel_b_samples, p0, p1, bad, *, min_disp=MIN_DISP_M, tol_deg=TOL_DEG, min_frac=MIN_FRAC) -> dict:
    """yaw_samples (T, n) 라디안 · vel_b_samples (T, n, 2) · p0 p1 (n, 2) 월드 (env 국소) 위치 · bad (n,) 창 안에서 끝난 env.
    움직인 env (변위 >= min_disp m, 창 안에서 안 끝남) 가 min_frac 미만이면 판정 불능 = 실패. 그 env 들의 변위 방향이
    (a) 평균 yaw (원 평균) 와 (b) 평균 vel_b 를 그 yaw 로 돌린 방향과 중앙값 tol_deg 안이어야 통과."""
    yaw = np.asarray(yaw_samples, float); vb = np.asarray(vel_b_samples, float)
    n = yaw.shape[1]
    disp = np.asarray(p1, float) - np.asarray(p0, float)
    dn = np.linalg.norm(disp, axis=1)
    use = (dn >= min_disp) & ~np.asarray(bad, bool)
    res = {"n": int(n), "moved": int(use.sum()), "ok": False}
    if use.sum() < max(1, int(np.ceil(min_frac * n))):
        res["reason"] = f"inconclusive: only {int(use.sum())} of {n} envs moved >= {min_disp} m"
        return res
    ym = np.arctan2(np.sin(yaw).mean(0), np.cos(yaw).mean(0))
    vm = vb.mean(0)
    vw = np.stack([np.cos(ym) * vm[:, 0] - np.sin(ym) * vm[:, 1], np.sin(ym) * vm[:, 0] + np.cos(ym) * vm[:, 1]], axis=1)
    ang = np.arctan2(disp[:, 1], disp[:, 0])
    e_yaw = _wrap_deg(ang - ym)[use]
    e_vel = _wrap_deg(ang - np.arctan2(vw[:, 1], vw[:, 0]))[use]
    res.update(err_vs_yaw_median_deg=float(np.median(e_yaw)), err_vs_velb_median_deg=float(np.median(e_vel)), median_disp_m=float(np.median(dn[use])))
    res["ok"] = bool(np.median(e_yaw) <= tol_deg and np.median(e_vel) <= tol_deg)
    if not res["ok"]:
        res["reason"] = f"displacement direction differs from the interpreted yaw by median {np.median(e_yaw):.1f} deg (vel_b-rotated {np.median(e_vel):.1f} deg), tolerance {tol_deg} deg"
    return res


def forward_action(nav, vx=0.5):
    """몸 +x 로 vx 를 내는 상위 행동 (n, 3). slot 방식이면 forward 슬롯 번호 + 크기."""
    n = int(nav.n)
    space = nav.space
    if getattr(space, "mode", "clip") == "slot":
        idx = [s.name for s in space.slots].index("forward")
        return np.tile([float(idx), 1.0, 0.0], (n, 1))
    return np.tile([vx, 0.0, 0.0], (n, 1))


def run(nav) -> dict | None:
    """Kit 쪽. 가짜 env (속성 없음) 면 None. 어긋나면 RuntimeError (학습 시작 전에 멈춘다)."""
    if not all(hasattr(nav, a) for a in ("reset", "step", "space", "hold", "n")):
        return None
    from foothold_s2.nav import teacher_obs

    state = nav.reset()
    p0 = np.asarray(state.pos_local)[:, :2].copy()
    ticks = max(1, int(round(WALK_S / (float(nav.hold) * float(nav.raw.step_dt)))))
    action = forward_action(nav)
    ys, vs, bad = [], [], np.zeros(int(nav.n), bool)
    for _ in range(ticks):
        state = nav.step(action)
        ys.append(teacher_obs.yaw_from_quat_wxyz(state.quat_w)); vs.append(np.asarray(state.vel_b)[:, :2].copy())
        bad |= np.asarray(state.done, bool)
    res = judge(np.stack(ys), np.stack(vs), p0, np.asarray(state.pos_local)[:, :2], bad)
    print("HEADING_SELFCHECK " + " ".join(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}" for k, v in res.items()) + f" walk_ticks={ticks}", flush=True)
    if not res["ok"]:
        raise RuntimeError("HEADING_SELFCHECK FAILED: " + res.get("reason", "?") + " (quaternion order or body-frame velocity interpretation is wrong; training not started)")
    return res
