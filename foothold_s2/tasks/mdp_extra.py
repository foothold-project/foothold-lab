"""S1 env 가 쓰는 관측 · 종료 함수 (설치 Isaac Lab 에 없는 것). Kit 안에서만 불린다."""

import torch


def foot_contact(env, sensor_cfg, threshold: float = 1.0):
    """발 접촉 여부 (n, 4) 0/1. critic 관측용."""
    sensor = env.scene.sensors[sensor_cfg.name]
    force = sensor.data.net_forces_w[:, sensor_cfg.body_ids, :]

    return (torch.linalg.norm(force, dim=-1) > threshold).float()


def foot_below_ground(env, sensor_cfg, scanner_cfg, asset_cfg, margin: float = 0.2):
    """어느 발이든 가장 가까운 높이 스캔 점의 지면보다 `margin` 아래면 종료 (17 §7). 스캔 격자 밖의 발은 판정에서 뺀다."""
    asset = env.scene[asset_cfg.name]
    scanner = env.scene.sensors[scanner_cfg.name]
    feet = asset.data.body_pos_w[:, asset_cfg.body_ids, :]
    hits = scanner.data.ray_hits_w
    ok = torch.isfinite(hits).all(dim=-1)
    hits = torch.where(ok[..., None], hits, torch.zeros_like(hits))

    d = torch.linalg.norm(feet[:, :, None, :2] - hits[:, None, :, :2], dim=-1)
    d = torch.where(ok[:, None, :], d, torch.full_like(d, 1.0e6))
    dmin, nearest = d.min(dim=-1)
    ground_z = torch.gather(hits[..., 2], 1, nearest)
    inside = dmin < 0.15

    return ((feet[..., 2] < ground_z - margin) & inside).any(dim=1)
