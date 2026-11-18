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


class WindowYawCheck:
    """QUAT_CHECK 의 이동 창 판 (선택). 한 틱 변위는 걸음 흔들림에 크게 흔들리므로, W 틱 창에서
    (창 변위 방향) - (창 평균 vel_b 방향) 을 몸이 본 방향의 독립 추정으로 삼아 창 안 해석 yaw (원 평균) 와 비교한다.
    창 변위가 min_disp m 이상이고 창 안에서 끝나지 않은 표본만 쓴다. 판정 줄 (결과 전 고정): 가장 긴 창 중앙값이 10 도 안이면 틀 결함 없음."""

    def __init__(self, windows=(1, 5, 10), min_disp=0.05, min_speed=0.05):
        self.windows, self.min_disp, self.min_speed = tuple(sorted(windows)), min_disp, min_speed
        self.H = max(self.windows) + 1
        self.pos, self.vb, self.yaw, self.age = [], [], [], None
        self.errs = {w: [] for w in self.windows}
        self.ticks = 0

    def push(self, pos_xy, v_b, yaw, done) -> None:
        pos_xy, v_b, yaw, done = (np.asarray(x, float) for x in (pos_xy, v_b, yaw, done))
        done = done.astype(bool)
        self.age = np.zeros(len(yaw), int) if self.age is None else np.where(done, 0, self.age + 1)
        self.pos.append(pos_xy.copy()); self.vb.append(v_b[:, :2].copy()); self.yaw.append(yaw.copy())
        self.pos, self.vb, self.yaw = self.pos[-self.H:], self.vb[-self.H:], self.yaw[-self.H:]
        self.ticks += 1
        for w in self.windows:
            if len(self.pos) <= w:
                continue
            disp = self.pos[-1] - self.pos[-1 - w]
            vm = np.sum(self.vb[-w:], axis=0)
            ys = np.stack(self.yaw[-w:])
            ym = np.arctan2(np.sin(ys).mean(0), np.cos(ys).mean(0))
            use = (self.age >= w + 1) & (np.linalg.norm(disp, axis=1) >= self.min_disp) & (np.linalg.norm(vm, axis=1) >= self.min_speed * w)
            if use.any():
                est = np.arctan2(disp[:, 1], disp[:, 0]) - np.arctan2(vm[:, 1], vm[:, 0])
                self.errs[w].append(_wrap_deg(est - ym)[use])

    def table(self) -> dict:
        out = {}
        for w in self.windows:
            e = np.concatenate(self.errs[w]) if self.errs[w] else np.zeros(0)
            out[w] = {"samples": int(len(e)), "median_deg": float(np.median(e)) if len(e) else None,
                      "within_30": float((e <= 30).mean()) if len(e) else None, "within_10": float((e <= 10).mean()) if len(e) else None}
        return out

    def summary_line(self) -> str:
        parts = [f"W={w} n={r['samples']} median={r['median_deg']:.1f} in30={r['within_30']:.2f} in10={r['within_10']:.2f}"
                 for w, r in self.table().items() if r["samples"]]
        return "QUAT_WINDOWS ticks=%d min_disp=%g | %s" % (self.ticks, self.min_disp, " | ".join(parts) or "no samples")
