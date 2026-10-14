# -*- coding: utf-8 -*-
"""S2 지도 입력 (판 2): RayCaster 자료 (센서 위치 · 맞은 점) -> height 187 · mask 187 (B) 또는 상수 (A) · 고장 기록.

분류: A/정책학습 · S2 「이상적 지도 입력 비교」 A/B 입력 경로 1 단계 판 2 (CPU · 학습 없음)
작성: 오흥재 (lead 세션 · Claude 하위 작업 작성) · 판 1 2026-10-13 19:21 · 판 2 2026-10-13 23:32
근거: inbox/jay/20261012-arch-discussion/DESIGN-s2-ab-v1.md 6 절 (위 1 ~ 5 절과 다르면 6 절) · VERIFY-astra-17d.md 6.2 · 6.4
      E1 params/env.yaml 446 ~ 490 (height_scanner: base 에 붙음 · offset z 20 · ray_alignment yaw · grid 1.6 x 1.0 · 0.1 · xy · drift 0)
      IsaacLab envs/mdp/observations.py 292 ~ 300 (height_scan = pos_w.z - ray_hits_w.z - offset · offset 기본 0.5)
      IsaacLab sensors/ray_caster/ray_caster.py 218 ~ 224 (cfg.offset 은 ray_starts 에만 더함) · 238 ~ 248 (pos_w = base 위치 + drift)
      IsaacLab utils/warp/ops.py 71 · kernels.py 70 ~ 73 (안 맞은 광선은 xyz 모두 +inf 로 남음)
요지: mask = 지형 충돌 여부. 유한한 hit 은 mask 1 · height = clip(센서 z - hit z - 0.5, -1, 1) (깊은 바닥도 mask 1).
      정상 miss (xyz 모두 +inf) 만 mask 0 · height 1. 센서 위치 비유한 · hit 손상 (NaN · -inf · 일부만 inf) 은 구멍으로 바꾸지 않고
      고장으로 따로 센다. 고장 칸은 자리표시 (height 0 · mask 0) 로 두고 MapFaults 로 돌려준다 (strict 면 예외).
      A 는 지형과 상관없이 height 0 · mask 0 이고, 고장 판정은 B 와 같은 함수로 같게 한다.
상태: CPU 시험 (test_s2.py) · 변이 (mutate_s2.py) 만 거침. Isaac 안의 실제 collision mesh 자료로 돌려 본 적 없음 (미확인)

지도 입력 배치: m = [height 187, mask 187] (열 0 ~ 186 이 height · 187 ~ 373 이 mask). 광선 순서는 센서 순서 그대로
(grid_pattern ordering xy: x 가 가장 빨리 돈다 · 광선 k 의 몸체 좌표 = (x[k % 17], y[k // 17])).
판 1 과 다른 점: 1 m 깊이 분류를 뺐다 · NaN 을 구멍 (mask 0 · height 1) 으로 바꾸던 것을 고장 기록으로 바꿨다 ·
시험용 RayCaster 흉내 (ray_hits_from_terrain) 는 test_s2.py 로 옮겼다 (IsaacLab 의 grid_pattern · quat_apply_yaw 를 직접 씀).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import torch

# ------------------------------------------------------------------ 설정 (E1 params/env.yaml height_scanner 에서 옮김)
GRID_SIZE = (1.6, 1.0)        # pattern_cfg.size (x 길이, y 너비) [m]
GRID_RESOLUTION = 0.1         # pattern_cfg.resolution [m]
GRID_ORDERING = "xy"          # pattern_cfg.ordering
NUM_RAYS = 187                # 17 x 11
HEIGHT_OFFSET = 0.5           # isaaclab height_scan 의 offset 기본값 (env.yaml params 에 offset 없음)
HEIGHT_CLIP = (-1.0, 1.0)     # 설계 6 절 (critic 의 height_scan 항과 같은 범위 · 단 critic 은 이 뒤에 x 2.5)
MISS_HEIGHT = 1.0             # 정상 miss 칸의 height (mask 0)
FAULT_HEIGHT = 0.0            # 고장 칸 자리표시 height. 정상 miss (1, 0) 와도 정상 hit (mask 1) 와도 겹치지 않는다
FAULT_MASK = 0.0              # 고장 칸 자리표시 mask
A_HEIGHT = 0.0                # A 의 상수 height
A_MASK = 0.0                  # A 의 상수 mask (mask 만 실제 값이면 A 가 구멍을 본다 · ASTRA 11 2.2)
MAP_DIM = 2 * NUM_RAYS        # 374


class MapObsFault(RuntimeError):
    """지도 입력에 고장 (센서 위치 비유한 · ray packet 손상) 이 있다. 그 rollout 은 무효."""


@dataclass
class MapFaults:
    """지도 입력의 고장 기록. sensor_bad [N]: 센서 위치에 비유한 값. packet_bad [N, R]: 센서가 정상인 env 에서
    hit 이 유한하지도 정상 miss (xyz 모두 +inf) 도 아닌 광선. 센서가 고장인 env 의 광선은 packet 쪽에 두 번 세지 않는다."""

    sensor_bad: torch.Tensor
    packet_bad: torch.Tensor

    @property
    def n_sensor(self) -> int:
        return int(self.sensor_bad.sum())

    @property
    def n_packet(self) -> int:
        return int(self.packet_bad.sum())

    @property
    def total(self) -> int:
        return self.n_sensor + self.n_packet

    @property
    def env_bad(self) -> torch.Tensor:
        return self.sensor_bad | self.packet_bad.any(dim=-1)

    def as_dict(self) -> dict:
        return {"sensor_nonfinite_envs": self.n_sensor, "ray_packet_bad": self.n_packet, "bad_envs": int(self.env_bad.sum())}


def grid_ray_xy_body(size=GRID_SIZE, resolution=GRID_RESOLUTION, ordering=GRID_ORDERING) -> torch.Tensor:
    """광선 k 의 몸체 (yaw 정렬) 좌표 (x, y) [R, 2]. IsaacLab grid_pattern 과 같은 식 (offset z 20 은 뺌).

    ordering xy 는 torch.meshgrid(indexing="xy") 라서 x 가 가장 빨리 돈다. yx 는 indexing="ij" (y 가 가장 빨리).
    """
    if ordering not in ("xy", "yx"):
        raise ValueError(f"ordering 은 xy 또는 yx: {ordering!r}")
    indexing = "xy" if ordering == "xy" else "ij"
    x = torch.arange(start=-size[0] / 2, end=size[0] / 2 + 1.0e-9, step=resolution)
    y = torch.arange(start=-size[1] / 2, end=size[1] / 2 + 1.0e-9, step=resolution)
    gx, gy = torch.meshgrid(x, y, indexing=indexing)
    return torch.stack([gx.flatten(), gy.flatten()], dim=-1)


def _check_shapes(sensor_pos_w: torch.Tensor, ray_hits_w: torch.Tensor) -> None:
    if sensor_pos_w.dim() != 2 or sensor_pos_w.shape[-1] != 3:
        raise ValueError(f"sensor_pos_w 모양 [N, 3] 이어야 함: {tuple(sensor_pos_w.shape)}")
    if ray_hits_w.dim() != 3 or ray_hits_w.shape[-1] != 3 or ray_hits_w.shape[0] != sensor_pos_w.shape[0]:
        raise ValueError(f"ray_hits_w 모양 [N, R, 3] 이어야 함: {tuple(ray_hits_w.shape)}")


def classify_rays(sensor_pos_w: torch.Tensor, ray_hits_w: torch.Tensor):
    """광선을 셋으로 가른다: hit_valid (센서 정상 · hit xyz 유한) · normal_miss (센서 정상 · hit xyz 모두 +inf) · 고장 (나머지).

    돌려줌: (hit_valid [N, R] bool, normal_miss [N, R] bool, MapFaults)
    """
    _check_shapes(sensor_pos_w, ray_hits_w)
    sensor_ok = torch.isfinite(sensor_pos_w).all(dim=-1)                 # [N]
    hit_finite = torch.isfinite(ray_hits_w).all(dim=-1)                  # [N, R]
    all_pos_inf = (ray_hits_w == math.inf).all(dim=-1)                    # raycast_mesh 의 안 맞음 표현
    ok = sensor_ok.unsqueeze(-1)
    hit_valid = hit_finite & ok
    normal_miss = all_pos_inf & ok
    packet_bad = ~(hit_finite | all_pos_inf) & ok
    return hit_valid, normal_miss, MapFaults(sensor_bad=~sensor_ok, packet_bad=packet_bad)


def height_and_mask(sensor_pos_w: torch.Tensor, ray_hits_w: torch.Tensor, strict: bool = False):
    """B 의 height [N, R] · mask [N, R] (0 또는 1, height 와 같은 dtype) · MapFaults.

    sensor_pos_w: [N, 3] RayCaster data.pos_w (base 위치. cfg.offset z 20 은 들어 있지 않다 · 다시 더하지 않는다)
    ray_hits_w:   [N, R, 3] RayCaster data.ray_hits_w (안 맞은 광선은 xyz 모두 +inf)
    strict: 고장이 하나라도 있으면 MapObsFault 를 낸다. 아니면 고장 칸을 자리표시로 두고 MapFaults 로 알린다.
    """
    hit_valid, normal_miss, faults = classify_rays(sensor_pos_w, ray_hits_w)
    if strict and faults.total:
        raise MapObsFault(f"지도 입력 고장: {faults.as_dict()}")
    sensor_z = sensor_pos_w[:, 2:3]
    hit_z = ray_hits_w[..., 2]
    raw = sensor_z - hit_z - HEIGHT_OFFSET           # isaaclab height_scan 과 같은 식 (센서 z = base z)
    fill = torch.where(normal_miss, torch.full_like(raw, MISS_HEIGHT), torch.full_like(raw, FAULT_HEIGHT))
    height = torch.where(hit_valid, raw.clamp(HEIGHT_CLIP[0], HEIGHT_CLIP[1]), fill)
    mask = torch.where(hit_valid, torch.ones_like(raw), torch.full_like(raw, FAULT_MASK))
    return height, mask, faults


def map_obs_b(sensor_pos_w: torch.Tensor, ray_hits_w: torch.Tensor, strict: bool = False):
    """B 의 지도 입력 [N, 374] = [height, mask] 와 MapFaults."""
    height, mask, faults = height_and_mask(sensor_pos_w, ray_hits_w, strict=strict)
    return torch.cat([height, mask], dim=-1), faults


def map_obs_a(num_envs: int, num_rays: int = NUM_RAYS, device=None, dtype=torch.float32) -> torch.Tensor:
    """A 의 지도 입력 [N, 374]: height 와 mask 모두 상수. 지형 자료를 받지 않는다."""
    height = torch.full((num_envs, num_rays), A_HEIGHT, device=device, dtype=dtype)
    mask = torch.full((num_envs, num_rays), A_MASK, device=device, dtype=dtype)
    return torch.cat([height, mask], dim=-1)


def map_obs(mode: str, sensor_pos_w: torch.Tensor, ray_hits_w: torch.Tensor, strict: bool = False):
    """mode 에 따른 지도 입력과 MapFaults. 고장 판정 (strict 포함) 은 A · B 가 같은 함수로 같게 한다.
    A 는 지도 값으로 상수만 돌려준다 (지형 값은 버린다)."""
    if mode not in ("A", "B"):
        raise ValueError(f"mode 는 A 또는 B: {mode!r}")
    height, mask, faults = height_and_mask(sensor_pos_w, ray_hits_w, strict=strict)
    if mode == "B":
        return torch.cat([height, mask], dim=-1), faults
    return map_obs_a(ray_hits_w.shape[0], ray_hits_w.shape[1], device=ray_hits_w.device, dtype=ray_hits_w.dtype), faults


def is_a_constant(m: torch.Tensor, num_rays: int = NUM_RAYS) -> bool:
    """지도 입력이 A 의 상수와 같은가 (height 칸은 A_HEIGHT · mask 칸은 A_MASK)."""
    if m.shape[-1] != 2 * num_rays:
        return False
    return bool(torch.all(m[..., :num_rays] == A_HEIGHT)) and bool(torch.all(m[..., num_rays:] == A_MASK))


class RunValidityGate:
    """rollout 하나의 유효성 관문 (A · B 같은 것). 지도 고장 · critic 입력 · value 와 그 밖에 넣은 텐서 (return ·
    advantage 등) 의 비유한 값을 센다. 하나라도 있으면 그 rollout 은 무효이고 require_valid() 가 예외를 낸다."""

    FAULT_KEYS = ("sensor_nonfinite_envs", "ray_packet_bad", "critic_input_nonfinite", "value_nonfinite")

    def __init__(self):
        self.counts = {"map_steps": 0, "sensor_nonfinite_envs": 0, "ray_packet_bad": 0,
                       "critic_input_nonfinite": 0, "value_nonfinite": 0}
        self.other_nonfinite = {}

    def add_map(self, faults: MapFaults) -> None:
        self.counts["map_steps"] += 1
        self.counts["sensor_nonfinite_envs"] += faults.n_sensor
        self.counts["ray_packet_bad"] += faults.n_packet

    def add_critic(self, report: dict) -> None:
        self.counts["critic_input_nonfinite"] += int(report["critic_input_nonfinite"])
        self.counts["value_nonfinite"] += int(report["value_nonfinite"])

    def add_nonfinite(self, name: str, t: torch.Tensor) -> None:
        self.other_nonfinite[name] = self.other_nonfinite.get(name, 0) + int((~torch.isfinite(t)).sum())

    @property
    def valid(self) -> bool:
        return all(self.counts[k] == 0 for k in self.FAULT_KEYS) and all(v == 0 for v in self.other_nonfinite.values())

    def require_valid(self) -> None:
        if not self.valid:
            raise MapObsFault(f"rollout 무효: {self.counts} · {self.other_nonfinite}")
