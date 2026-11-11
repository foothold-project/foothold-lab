"""상위 출력 -> 하위가 배운 명령으로 옮기는 층 (PLAN-HIPAN-V2 §4.2 · M2). numpy 만 쓴다.

하위의 학습 명령은 연속 상자가 아니라 13 슬롯이다. 슬롯 범위는 `ex42-prep.yaml` 의 `stage_zero.ranges` · `shares` 에서 읽고
(숫자를 코드에 다시 적지 않는다), 슬롯 부호 규칙은 `curriculum/continuous.py` 의 W55 검사와 같다
(left: wz > 0 · vy > 0, right: 반대, diag_fwd: vx > 0, diag_back: vx < 0).
방식 셋을 설정 한 줄로 고른다 (기본 clip, 계획 §9 물음 1 은 G1 측정 뒤 lead 가 정함):
  clip     자르기만: 슬롯 범위 전체를 감싸는 상자 안으로 자르고 vx 상한을 적용
  project  슬롯 투영: 가장 가까운 슬롯 상자로 옮김 (유클리드 거리 · 같으면 앞 슬롯)
  slot     슬롯 + 크기: 상위가 슬롯 번호 하나와 크기 [0, 1] 둘을 냄. 슬롯 상자 안 값 (크기는 상자 대각 보간)
공통: 상위 1 틱 = 하위 5 스텝 같은 명령 유지 · 자세 스위치가 꺼져 있으면 (Δh, roll) = 0 · 세 칸이 모두 0 가까이면 stand 표지 ·
값을 고쳤으면 `modified` 표지 · 실제 넣은 명령을 `last_applied` 로 되돌림 (상위 관측의 c_{t-1}).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

MODES = ("clip", "project", "slot")
HOLD_STEPS = 5
STAND_EPS = 0.05       # 가정 (계획 §4.2)
VX_MAX = 1.0           # lead 11/12 00:56: 하위 속도 상한 1.0 m/s
MOD_EPS = 1e-6


@dataclass(frozen=True)
class Slot:
    name: str
    lo: tuple   # (vx, vy, wz) 하한
    hi: tuple


def _signed(name: str, ranges: dict) -> Slot:
    r = ranges
    z = (0.0, 0.0)
    left = name.endswith("left")
    s = 1.0 if left else -1.0

    def sgn(iv):                       # 절대값 구간 [a, b] -> 부호 붙인 (lo, hi)
        a, b = iv
        return (a, b) if s > 0 else (-b, -a)

    if name == "forward":
        vx, vy, wz = tuple(r["forward_vx"]), z, z
    elif name.startswith("walk_"):
        vx, vy, wz = tuple(r["walk_vx"]), z, sgn(r["walk_wz_abs"])
    elif name.startswith("spin_"):
        vx, vy, wz = z, z, sgn(r["spin_wz_abs"])
    elif name == "stand":
        vx = vy = wz = z
    elif name == "reverse":
        vx, vy, wz = tuple(r["reverse_vx"]), z, z
    elif name.startswith("side_"):
        vx, vy, wz = z, sgn(r["side_vy_abs"]), z
    elif name.startswith("diag_"):
        a, b = r["diag_vx_abs"]
        vx = (a, b) if name.startswith("diag_fwd") else (-b, -a)
        vy, wz = sgn(r["diag_vy_abs"]), z
    else:
        raise ValueError(f"unknown command slot {name!r}")
    return Slot(name, (vx[0], vy[0], wz[0]), (vx[1], vy[1], wz[1]))


def slots_from_prep(path, section: str = "stage_zero") -> tuple:
    d = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    sec = d.get(section)
    if not isinstance(sec, dict) or "shares" not in sec or "ranges" not in sec:
        raise ValueError(f"prep section {section!r} has no shares/ranges")
    shares, ranges = sec["shares"], sec["ranges"]
    out = tuple(_signed(name, ranges) for name in shares)
    if len(out) != 13:
        raise ValueError(f"expected 13 command slots, got {len(out)}")
    return out


@dataclass
class Applied:
    cmd: np.ndarray        # (n, 5) vx vy wz dh roll
    stand: np.ndarray      # (n,) bool
    modified: np.ndarray   # (n,) bool: 명령 공간 층이 vx vy wz 값을 고쳤다 (보상 r9 지시자)
    pose_masked: np.ndarray  # (n,) bool: 자세 스위치 꺼짐 때문에 Δh · roll 을 0 으로 눌렀다
    ticked: bool           # 이 스텝에 상위 명령을 새로 받았다


class CommandSpace:
    def __init__(self, slots, mode: str = "clip", pose_active: bool = False,
                 vx_max: float = VX_MAX, hold_steps: int = HOLD_STEPS, stand_eps: float = STAND_EPS):
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        if hold_steps < 1 or vx_max <= 0 or stand_eps < 0:
            raise ValueError("hold_steps >= 1, vx_max > 0, stand_eps >= 0 required")
        self.slots = tuple(slots)
        self.names = tuple(s.name for s in self.slots)
        self.lo = np.array([s.lo for s in self.slots], dtype=np.float64)    # (13, 3)
        self.hi = np.array([s.hi for s in self.slots], dtype=np.float64)
        self.mode, self.pose_active = mode, bool(pose_active)
        self.vx_max, self.hold_steps, self.stand_eps = float(vx_max), int(hold_steps), float(stand_eps)
        self.box_lo, self.box_hi = self.lo.min(0), self.hi.max(0)
        self.box_hi[0] = min(self.box_hi[0], self.vx_max)
        self.reset()

    def reset(self):
        self._step = 0
        self._held = None
        self.last_applied = None

    def _clamp_vx(self, c):
        return np.minimum(c, np.array([self.vx_max, np.inf, np.inf]))

    def map_action(self, action) -> tuple:
        """상위 행동 1 개 묶음 -> (명령 (n,3), 고쳤나 (n,)). clip · project: action (n, >=3). slot: action (n, 3) = (슬롯 번호, 크기 a, 크기 b)."""
        a = np.asarray(action, dtype=np.float64)
        if a.ndim != 2 or not np.isfinite(a).all():
            raise ValueError("action must be a finite (n, k) array")
        if self.mode == "slot":
            if a.shape[1] != 3:
                raise ValueError("slot mode action is (index, size_a, size_b)")
            idx = np.clip(np.rint(a[:, 0]).astype(int), 0, len(self.slots) - 1)
            s = np.clip(a[:, 1:3], 0.0, 1.0)
            lo, hi = self.lo[idx], self.hi[idx]
            width = hi - lo
            free = width > 0
            # 폭이 있는 칸이 하나면 크기 a, 둘이면 (a, b) 순서대로 (vx · vy · wz 순서)
            order = np.cumsum(free, axis=1) - 1
            t = np.where(free, np.take_along_axis(s, np.clip(order, 0, 1), axis=1), 0.0)
            cmd = lo + t * width
            bad_idx = (a[:, 0] < -0.5) | (a[:, 0] > len(self.slots) - 0.5)
            return self._clamp_vx(cmd), bad_idx
        if a.shape[1] < 3:
            raise ValueError("action needs at least vx, vy, wz")
        raw = a[:, :3]
        if self.mode == "clip":
            cmd = np.clip(raw, self.box_lo, self.box_hi)
        else:
            clamped = np.clip(raw[:, None, :], self.lo[None], self.hi[None])        # (n, 13, 3)
            dist = ((clamped - raw[:, None, :]) ** 2).sum(-1)
            best = dist.argmin(1)                                                   # 같으면 앞 슬롯
            cmd = self._clamp_vx(clamped[np.arange(len(raw)), best])
        mod = (np.abs(cmd - raw) > MOD_EPS).any(1)
        return cmd, mod

    def step(self, action, pose_action=None) -> Applied:
        """하위 스텝 1 번마다 부른다. 상위 틱 (hold_steps 번에 한 번) 에만 action 을 받고 그 사이에는 직전 명령을 유지한다.
        action 은 틱이 아닌 스텝에는 무시된다. 첫 호출은 항상 틱."""
        tick = self._held is None or self._step % self.hold_steps == 0
        if tick:
            cmd3, mod = self.map_action(action)
            n = len(cmd3)
            pose = np.zeros((n, 2))
            masked = np.zeros(n, dtype=bool)
            if pose_action is not None:
                p = np.asarray(pose_action, dtype=np.float64)
                if p.shape != (n, 2) or not np.isfinite(p).all():
                    raise ValueError("pose_action must be finite (n, 2)")
                if self.pose_active:
                    pose = p
                else:
                    masked = (np.abs(p) > MOD_EPS).any(1)
            stand = np.linalg.norm(cmd3, axis=1) < self.stand_eps
            cmd3 = np.where(stand[:, None], 0.0, cmd3)
            self._held = Applied(np.concatenate([cmd3, pose], 1), stand, mod, masked, True)
        else:
            h = self._held
            if len(np.asarray(action)) != len(h.cmd):
                raise ValueError("number of envs changed inside a hold window")
            self._held = Applied(h.cmd, h.stand, h.modified, h.pose_masked, False)
        self._step += 1
        self.last_applied = self._held.cmd.copy()
        return self._held
