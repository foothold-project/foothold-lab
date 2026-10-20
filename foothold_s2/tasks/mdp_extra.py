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


def randomize_motor_strength(env, env_ids, asset_cfg, scale_range=(0.9, 1.1)):
    """모터 세기 배율 (17 §5): DCMotor 의 연속 토크 한계와 정지 토크를 env 마다 같은 배율로 키우고 줄인다.

    시작 때 한 번. 속도 한계 곡선의 기울기 `saturation / velocity_limit` 이 배율만큼 같이 변한다.
    """
    asset = env.scene[asset_cfg.name]
    n = env.scene.num_envs
    scale = torch.empty(n, device=asset.device).uniform_(*scale_range)

    for actuator in asset.actuators.values():
        limit = actuator.effort_limit

        if not hasattr(actuator, "_saturation_effort"):
            continue

        base = actuator._saturation_effort
        base = base if torch.is_tensor(base) else torch.full_like(limit, float(base))
        actuator.effort_limit = limit * scale[:, None]
        actuator._saturation_effort = base * scale[:, None]
        actuator._vel_at_effort_lim = actuator.velocity_limit * (1 + actuator.effort_limit / actuator._saturation_effort)
