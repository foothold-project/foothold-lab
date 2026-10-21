"""START 원문 명령 계약 (SONNET-X11, ASTRA-X13 H3). Kit 없이 시험된다.

한 transition 에 실제로 소비된 명령 c = [vx, vy, wz] 가 모두 다음을 만족해야 한다(허용오차 tol):
    세 값이 모두 유한, vx = 0 또는 vx in [0.3, 1.5], vy = 0, 전진(vx > 0)이면 wz = 0, 제자리 회전(vx = 0)이면 |wz| <= 1.2.
"""

from __future__ import annotations

import torch

TOL = 1e-5
VX_MIN, VX_MAX, WZ_SPIN = 0.3, 1.5, 1.2


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
