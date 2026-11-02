"""START 원문 명령 계약 (SONNET-X11, ASTRA-X13 H3). Kit 없이 시험된다.

한 transition 에 실제로 소비된 명령 c = [vx, vy, wz] 가 모두 다음을 만족해야 한다(허용오차 tol):
    세 값이 모두 유한, vx = 0 또는 vx in [0.3, 1.5], vy = 0, 전진(vx > 0)이면 wz = 0, 제자리 회전(vx = 0)이면 |wz| <= 1.2.
"""

from __future__ import annotations

import torch

TOL = 1e-5
VX_MIN, VX_MAX, WZ_SPIN = 0.3, 1.5, 1.2


VX_WALK_MAX, WZ_WALK = 0.8, 0.5
CONTRACTS = ("start", "walkturn_v1", "basic_gait_v1", "basic_gait_ex39")


def start_contract_bad(c: torch.Tensor, tol: float = TOL) -> torch.Tensor:
    """c (..., 3) -> 계약을 어긴 행이면 True (...). NaN · Inf 도 위반."""
    finite = torch.isfinite(c).all(dim=-1)
    z = torch.nan_to_num(c, nan=0.0, posinf=1e9, neginf=-1e9)
    vx, vy, wz = z[..., 0], z[..., 1], z[..., 2]
    ok_vx = (vx.abs() <= tol) | ((vx >= VX_MIN - tol) & (vx <= VX_MAX + tol))
    ok_vy = vy.abs() <= tol
    forward = vx > tol
    ok_wz = torch.where(forward, wz.abs() <= tol, wz.abs() <= WZ_SPIN + tol)

    return ~(finite & ok_vx & ok_vy & ok_wz)


def walkturn_contract_bad(c: torch.Tensor, tol: float = TOL) -> torch.Tensor:
    """EX-35 `walkturn_v1`: vx = 0 또는 [0.3, 1.5], vy = 0, vx > 0.8 이면 wz = 0, 0 < vx <= 0.8 이면 |wz| <= 0.5, vx = 0 이면 |wz| <= 1.2. NaN · Inf 도 위반."""
    finite = torch.isfinite(c).all(dim=-1)
    z = torch.nan_to_num(c, nan=0.0, posinf=1e9, neginf=-1e9)
    vx, vy, wz = z[..., 0], z[..., 1], z[..., 2]
    ok_vx = (vx.abs() <= tol) | ((vx >= VX_MIN - tol) & (vx <= VX_MAX + tol))
    ok_vy = vy.abs() <= tol
    ok_wz = torch.where(vx <= tol, wz.abs() <= WZ_SPIN + tol, torch.where(vx <= VX_WALK_MAX + tol, wz.abs() <= WZ_WALK + tol, wz.abs() <= tol))

    return ~(finite & ok_vx & ok_vy & ok_wz)


def basic_gait_contract_bad(c: torch.Tensor, tol: float = TOL) -> torch.Tensor:
    """새 기본 보행의 여섯 묶음만 허용한다. 몫은 표집기에서 따로 확인한다."""
    finite = torch.isfinite(c).all(dim=-1)
    z = torch.nan_to_num(c, nan=0.0, posinf=1e9, neginf=-1e9)
    vx, vy, wz = z[..., 0], z[..., 1], z[..., 2]
    zero_x, zero_y, zero_z = vx.abs() <= tol, vy.abs() <= tol, wz.abs() <= tol
    forward = (vx >= 0.3 - tol) & (vx <= 1.5 + tol) & zero_y & zero_z
    walk = (vx >= 0.3 - tol) & (vx <= 0.8 + tol) & zero_y & (wz.abs() >= 0.2 - tol) & (wz.abs() <= 0.5 + tol)
    spin = zero_x & zero_y & (wz.abs() >= 0.5 - tol) & (wz.abs() <= 1.2 + tol)
    stand = zero_x & zero_y & zero_z
    reverse = (vx >= -0.8 - tol) & (vx <= -0.2 + tol) & zero_y & zero_z
    side = zero_x & (vy.abs() >= 0.2 - tol) & (vy.abs() <= 0.5 + tol) & zero_z
    return ~(finite & (forward | walk | spin | stand | reverse | side))


def ex39_contract_bad(c: torch.Tensor, heading: torch.Tensor, tol: float = TOL) -> torch.Tensor:
    """D55 thirteen slots, with B heading's per-step wz rewrite on forward/spin only."""
    if heading is None or heading.shape != c.shape[:-1] or heading.dtype != torch.bool:
        raise ValueError("EX-39 heading mask must match the consumed command rows")
    finite = torch.isfinite(c).all(dim=-1)
    z = torch.nan_to_num(c, nan=0.0, posinf=1e9, neginf=-1e9)
    vx, vy, wz = z[..., 0], z[..., 1], z[..., 2]
    zero_x, zero_y, zero_z = vx.abs() <= tol, vy.abs() <= tol, wz.abs() <= tol
    forward = (vx >= 0.3 - tol) & (vx <= 1.5 + tol) & zero_y
    walk = (vx >= 0.3 - tol) & (vx <= 0.8 + tol) & zero_y & (wz.abs() >= 0.2 - tol) & (wz.abs() <= 0.5 + tol)
    spin = zero_x & zero_y & (wz.abs() >= 0.5 - tol) & (wz.abs() <= 1.5 + tol)
    reverse = (vx >= -1.0 - tol) & (vx <= -0.2 + tol) & zero_y & zero_z
    side = zero_x & (vy.abs() >= 0.2 - tol) & (vy.abs() <= 0.6 + tol) & zero_z
    diagonal = (vx.abs() >= 0.3 - tol) & (vx.abs() <= 0.6 + tol) & (vy.abs() >= 0.2 - tol) & (vy.abs() <= 0.5 + tol) & zero_z
    ordinary = (forward & zero_z) | walk | spin | (zero_x & zero_y & zero_z) | reverse | side | diagonal
    # Heading is allowed on the forward or spin slots only. apply_heading clips
    # wz at 2.0; near a target the spin heading may legitimately become zero.
    heading_command = (forward | (zero_x & zero_y)) & (wz.abs() <= 2.0 + tol)
    return ~(finite & torch.where(heading, heading_command, ordinary))


def contract_bad_fn(name):
    """계약 이름 -> 검사 함수. 이름이 None 이면 None(검사 없음), 모르는 이름이면 거절."""
    if name is None:
        return None
    if name == "start":
        return start_contract_bad
    if name == "walkturn_v1":
        return walkturn_contract_bad
    if name == "basic_gait_v1":
        return basic_gait_contract_bad
    if name == "basic_gait_ex39":
        return ex39_contract_bad
    raise ValueError(f"모르는 명령 계약 {name!r} (허용 {CONTRACTS})")


def command_sample_bad(name: str, command: torch.Tensor, heading: torch.Tensor | None = None) -> torch.Tensor:
    """Runner's pre-step validation, including the live EX-39 heading mask."""
    fn = contract_bad_fn(name)
    if fn is None:
        raise ValueError("command_sample_bad requires a configured contract")
    if name == "basic_gait_ex39":
        return fn(command, heading)
    return fn(command)
