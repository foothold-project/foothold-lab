"""D435i 깊이 전처리 · 증강 (11 §2 · §2.1). torch 만 쓰고 Kit 없이 CPU 로 시험한다.

START 에는 깊이 잡음이 없다(논문 미기재 · PIE 표 II 에도 없음). 우리 추가로 JEPLO 식 증강을 D435i 판으로 넣는다
(APPROVED B). JEPLO 코드는 GPLv3 라 옮기지 않고 식만 보고 새로 썼다. 도형 넷 · Perlin 구멍 · 거리 잡음의 값은 11 §2.1 표.

순서(가정(rl)): 미터 깊이 -> 거리 잡음 -> 0.3 m 미만 무효 -> near/far 정규화(미검출 1.0) -> 구멍 -> 가림 도형.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn.functional as F

NEAR, FAR = 0.2, 3.0  # 11 §2 가정 (SPEC 155 행)


@dataclass
class DepthAugCfg:
    enabled: bool = True
    noise_sigma_m: float = 0.005  # 11 §2.1 (JEPLO 코드 값, D435i 실측으로 바꿀 것)
    min_valid_m: float = 0.3  # D435i 0.3 m 미만 무효 (가정)
    hole_level_max: float = 0.4  # Perlin 구멍 수준 U[0, 0.4]
    hole_fill: tuple[float, float] = (0.9, 1.0)
    max_shapes: int = 2  # 프레임마다 0~2 개
    noise_grid: int = 6  # 매끈한 잡음의 성긴 격자 칸 수 (가정(rl))


def normalize(depth_m: torch.Tensor) -> torch.Tensor:
    """(d - 0.2) / 2.8 -> [0, 1]. 미검출(inf · nan · far 초과) = 1.0 (11 §2)."""
    d = torch.nan_to_num(depth_m, nan=float("inf"), posinf=float("inf"))
    out = ((d - NEAR) / (FAR - NEAR)).clamp(0.0, 1.0)
    return torch.where(torch.isfinite(d) & (d <= FAR), out, torch.ones_like(out))


def smooth_noise(n: int, h: int, w: int, grid: int, generator=None, device="cpu") -> torch.Tensor:
    """Perlin 꼴의 매끈한 잡음 (0~1): 성긴 균등 난수 격자를 bicubic 으로 키운다. 가정(rl): 정식 Perlin 기울기 잡음이 아님."""
    g = torch.rand(n, 1, grid, grid, generator=generator, device=device)
    return F.interpolate(g, size=(h, w), mode="bicubic", align_corners=True).clamp(0, 1)[:, 0]


def shape_masks(n: int, h: int, w: int, max_shapes: int, generator=None, device="cpu") -> torch.Tensor:
    """원 · 직사각 · 정사각 · 사다리꼴 0~max 개를 합친 가림 마스크 (N, H, W) bool."""
    yy, xx = torch.meshgrid(torch.arange(h, device=device).float(), torch.arange(w, device=device).float(), indexing="ij")
    mask = torch.zeros(n, h, w, dtype=torch.bool, device=device)
    counts = torch.randint(0, max_shapes + 1, (n,), generator=generator, device=device)
    for k in range(max_shapes):
        active = counts > k
        kind = torch.randint(0, 4, (n,), generator=generator, device=device)
        cx = torch.rand(n, generator=generator, device=device) * w
        cy = torch.rand(n, generator=generator, device=device) * h
        a = 3 + torch.rand(n, generator=generator, device=device) * (w / 4)  # 반폭 3~18 화소 (가정(rl))
        b = 3 + torch.rand(n, generator=generator, device=device) * (h / 4)
        dx, dy = xx[None] - cx[:, None, None], yy[None] - cy[:, None, None]
        A, B = a[:, None, None], b[:, None, None]
        circle = dx**2 + dy**2 <= A**2
        rect = (dx.abs() <= A) & (dy.abs() <= B)
        square = (dx.abs() <= A) & (dy.abs() <= A)
        # 사다리꼴: 위가 좁고 아래가 넓다
        trap = (dy.abs() <= B) & (dx.abs() <= A * (0.5 + 0.5 * (dy + B) / (2 * B)))
        kk = kind[:, None, None]
        m = torch.where(kk == 0, circle, torch.where(kk == 1, rect, torch.where(kk == 2, square, trap)))
        mask |= m & active[:, None, None]
    return mask


def augment(depth_m: torch.Tensor, cfg: DepthAugCfg, generator=None) -> torch.Tensor:
    """(N, H, W) 미터 깊이 -> (N, H, W) 정규화 · 증강 깊이. 증강을 끄면 normalize 와 같다."""
    if not cfg.enabled:
        return normalize(depth_m)
    n, h, w = depth_m.shape
    dev = depth_m.device
    d = depth_m + torch.randn(depth_m.shape, generator=generator, device=dev) * cfg.noise_sigma_m
    d = torch.where(d < cfg.min_valid_m, torch.full_like(d, float("inf")), d)
    out = normalize(d)
    level = torch.rand(n, 1, 1, generator=generator, device=dev) * cfg.hole_level_max
    holes = smooth_noise(n, h, w, cfg.noise_grid, generator, dev) < level
    lo, hi = cfg.hole_fill
    fill = lo + (hi - lo) * torch.rand(depth_m.shape, generator=generator, device=dev)
    out = torch.where(holes, fill, out)
    if cfg.max_shapes > 0:
        occ = shape_masks(n, h, w, cfg.max_shapes, generator, dev)
        out = torch.where(occ, torch.ones_like(out), out)
    return out
