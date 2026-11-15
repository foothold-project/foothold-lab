"""PIE 표 II의 카메라 장착 오차와 HFOV 오차를 TopDown reset 때 적용한다."""

from __future__ import annotations

import torch

from foothold_s2.sensors import depth_cam_cfg


def quat_mul(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    aw, av = a[..., :1], a[..., 1:]
    bw, bv = b[..., :1], b[..., 1:]
    return torch.cat((aw * bw - (av * bv).sum(-1, keepdim=True),
                      aw * bv + bw * av + torch.cross(av, bv, dim=-1)), dim=-1)


def quat_apply(q: torch.Tensor, v: torch.Tensor) -> torch.Tensor:
    t = 2.0 * torch.cross(q[..., 1:], v, dim=-1)
    return v + q[..., :1] * t + torch.cross(q[..., 1:], t, dim=-1)


def camera_intrinsic_fx(hfov_deg: torch.Tensor) -> torch.Tensor:
    """848→106→중앙60 crop: 106화소 원영상의 fx를 crop에서도 유지한다."""
    return 53.0 / torch.tan(torch.deg2rad(hfov_deg) / 2.0)


def randomize_topdown_camera(env, env_ids, camera_name: str = "depth_cam") -> None:
    ids = torch.as_tensor(env_ids, dtype=torch.long, device=env.device)
    n = len(ids)
    if n == 0:
        return
    camera = env.scene.sensors[camera_name]
    pos_jitter = (torch.rand(n, 3, device=env.device) * 2 - 1) * 0.010
    pitch = torch.deg2rad(torch.full((n,), depth_cam_cfg.PITCH_DEG, device=env.device)
                         + (torch.rand(n, device=env.device) * 2 - 1))
    local_quat = torch.stack((torch.cos(pitch / 2), torch.zeros_like(pitch),
                              torch.sin(pitch / 2), torch.zeros_like(pitch)), dim=-1)
    local_pos = torch.as_tensor(depth_cam_cfg.OFFSET_POS, device=env.device).expand(n, -1) + pos_jitter
    # reset_root_state_uniform은 Lab의 내부 buffer를 먼저 쓰고 view는 다음 sim step에 갱신한다.
    # 이 시점 set_world_poses()는 옛 view pose를 읽어 잘못된 offset을 만든다.
    # Lab 2.3.2 ray_caster_camera.py:264-265, 428-456의 per-env offset buffer를 설정한다.
    camera._offset_pos[ids] = local_pos
    camera._offset_quat[ids] = local_quat
    hfov = 86.0 + torch.rand(n, device=env.device) * 2.0
    # data property raycasts when outdated. Read the cached matrix directly
    # so the old rays cannot fill the first post-reset frame before new fx.
    matrices = camera._data.intrinsic_matrices[ids].clone()
    matrices[:, 0, 0] = camera_intrinsic_fx(hfov)
    camera.set_intrinsic_matrices(matrices, env_ids=ids)
    camera.reset(ids)  # invalidate after both pose and ray directions change
