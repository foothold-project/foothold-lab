"""B2a 기하 채널 (DESIGN-MAP-EDGE 11 절): 깊이 영상의 점들을 몸 기울기로 보정해 32 x 16 격자에 찍는다. 학습 없음 · torch 만 · Kit 없음.

입력: depth (B, 60, 60) 정규화 깊이 ((d - 0.2) / 2.8 · 미검출 1.0 · depth_aug.normalize 와 같은 약속) ·
      gravity (B, 3) 몸 틀 중력 방향 (정책 관측 45 칸의 3:6 열 = projected_gravity_b · 서 있으면 (0, 0, -1)).
출력: height (B, 32, 16) 보이는 칸의 높이 (z_hit - z_base, 정답 지도와 같은 약속 · clip ±1 · 안 보인 칸 0) ·
      seen (B, 32, 16) 보였으면 1.

식 (planner 와 맞출 것):
  1. 화소 (u, v) -> 카메라 광선 (앞 1, 왼 -(u - CX) / FX, 위 -(v - CY) / FY) · 점 = 깊이 d 의 distance_to_image_plane 이라 광선에 d 를 그대로 곱한다 (앞 성분이 1).
  2. 장착 자세 (아래 35 도 · +y 축 회전) 로 돌려 몸 틀로 옮기고 장착 위치 (0.25, 0, 0.12) 를 더한다.
  3. 몸 기울기 보정: z' = -g (위) · x' = 몸 앞축에서 z' 성분을 뺀 것 (yaw 만 몸을 따른다) · y' = z' x x'. 점을 (x', y', z') 성분으로 바꾼다. 몸 원점 높이 = 0 이라 z' 성분이 곧 z_hit - z_base.
  4. 칸: 행 = floor((x' + 0.5) / 0.05) (0..31 · 가운데 -0.475 ~ 1.075) · 열 = floor((y' + 0.4) / 0.05) (0..15, 왼쪽이 큰 열은 Y_FLIP 로) · 한 칸에 점이 여럿이면 AGG (max 가 기본: 단차를 살림 · mean 은 평균).
기록의 깊이 두 프레임 (depth2) 중 FRAME 0 (더 새로운 쪽 · 지연 1 틱) 을 쓴다. 몸 자세는 그 스텝 값이라 프레임 시각과 최대 0.1 ~ 0.2 s 어긋난다 (근사)."""
from __future__ import annotations

import torch

from foothold_s2.sensors import depth_cam_cfg as cam

MAP_X, MAP_Y, RES = 32, 16, 0.05
X0, Y0 = -0.5, -0.4                       # 격자 모서리 (몸 틀): 칸 중심 x -0.475 .. 1.075 · y -0.375 .. 0.375 (start_obs.py 와 같다)
NEAR, FAR = 0.2, 3.0                      # depth_aug.NEAR / FAR 와 같다 (이 모듈은 torch 만 쓰려고 복사 · 시험이 같음을 확인)
MISS = 0.999                              # 정규화 값이 이 이상이면 미검출 (또는 구멍 채움) 로 보고 버린다
CLIP_M = 1.0
EPS = 1e-6


def _rays_body(device=None, dtype=torch.float32) -> torch.Tensor:
    """(60, 60, 3) 몸 틀 방향 (앞 성분 = 카메라 광축 성분 1 이 되도록 장착 회전만 적용한 것)."""
    u = torch.arange(cam.WIDTH, dtype=dtype, device=device)
    v = torch.arange(cam.HEIGHT, dtype=dtype, device=device)
    vv, uu = torch.meshgrid(v, u, indexing="ij")
    r = torch.stack([torch.ones_like(uu), -(uu + 0.5 - cam.CX) / cam.FX, -(vv + 0.5 - cam.CY) / cam.FY], -1)
    w, x, y, z = cam.OFFSET_ROT
    # 회전 행렬 (w, x, y, z) -> R
    R = torch.tensor([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]], dtype=dtype, device=device)
    return r @ R.T


def level_frame(gravity: torch.Tensor) -> torch.Tensor:
    """(B, 3) 몸 틀 중력 -> (B, 3, 3) 행 = (x', y', z') 축의 몸 틀 성분. 서 있으면 단위 행렬."""
    g = gravity / gravity.norm(dim=-1, keepdim=True).clamp_min(EPS)
    z = -g
    fwd = torch.tensor([1.0, 0.0, 0.0], dtype=g.dtype, device=g.device).expand_as(z)
    x = fwd - (fwd * z).sum(-1, keepdim=True) * z
    x = x / x.norm(dim=-1, keepdim=True).clamp_min(EPS)
    y = torch.cross(z, x, dim=-1)
    return torch.stack([x, y, z], 1)


def project(depth: torch.Tensor, gravity: torch.Tensor, *, agg: str = "max", y_flip: bool = False) -> tuple[torch.Tensor, torch.Tensor]:
    """depth (B, 60, 60) 정규화 · gravity (B, 3) -> (height, seen) 각 (B, 32, 16)."""
    if agg not in ("max", "mean"):
        raise ValueError(f"agg 는 max | mean: {agg}")
    b = depth.shape[0]
    dm = depth.float() * (FAR - NEAR) + NEAR
    ok = depth.float() < MISS
    rays = _rays_body(depth.device, torch.float32)                                       # (60, 60, 3)
    mount = torch.tensor(cam.OFFSET_POS, dtype=torch.float32, device=depth.device)
    p = mount + dm[..., None] * rays                                                      # (B, 60, 60, 3) 몸 틀
    q = torch.einsum("bij,bhwj->bhwi", level_frame(gravity.float()), p)                   # (x', y', z')
    row = torch.floor((q[..., 0] - X0) / RES).long()
    col = torch.floor((q[..., 1] - Y0) / RES).long()
    if y_flip:
        col = MAP_Y - 1 - col
    ok = ok & (row >= 0) & (row < MAP_X) & (col >= 0) & (col < MAP_Y)
    h = q[..., 2].clamp(-CLIP_M, CLIP_M)
    flat = (row * MAP_Y + col).clamp(0, MAP_X * MAP_Y - 1) + torch.arange(b, device=depth.device)[:, None, None] * (MAP_X * MAP_Y)
    flat, h, ok = flat.reshape(-1), h.reshape(-1), ok.reshape(-1)
    n = b * MAP_X * MAP_Y
    cnt = torch.zeros(n, device=depth.device).index_add_(0, flat[ok], torch.ones_like(h[ok]))
    if agg == "max":
        out = torch.full((n,), -float("inf"), device=depth.device).scatter_reduce(0, flat[ok], h[ok], "amax", include_self=True)
    else:
        out = torch.zeros(n, device=depth.device).index_add_(0, flat[ok], h[ok]) / cnt.clamp_min(1.0)
    seen = cnt > 0
    out = torch.where(seen, out, torch.zeros_like(out))
    return out.view(b, MAP_X, MAP_Y), seen.view(b, MAP_X, MAP_Y).float()


def channels(depth2: torch.Tensor, gravity: torch.Tensor, *, frame: int = 0, agg: str = "max", y_flip: bool = False) -> torch.Tensor:
    """U-Net 에 붙일 두 장 (B, 2, 32, 16) = (보이는 칸 높이, 보였나). depth2 (B, 2, 60, 60) 의 frame 번째 쪽을 쓴다."""
    h, s = project(depth2[:, frame], gravity, agg=agg, y_flip=y_flip)
    return torch.stack([h, s], 1)
