"""START Table I 14 항의 식 (16-REWARDS). torch, Kit 없이 CPU 로 시험한다. Isaac Lab 쪽은 `start_rewards.py`.

가중치(16 §1): 선속도 1.5 · 각속도 0.5 · v_z -2.0 · 롤피치 각속도 -0.05 · 자세 -1.0 · 토크 -1e-5 · 행동 변화율 -0.01 ·
부드러움 -0.01 · 관절 일률 -2e-5 · 관절 가속도 -2.5e-7 · 관절 오차 -0.01 · 충돌 -10.0 · 걸려 넘어짐 -1.0 · 발 가장자리 -1.0.
선속도 추종만 START 의 min(v, v_cmd) 형이 아니라 «정확 추종» 이다 (팀장 승인 F-D4 · 우리 변경).
"""

import torch

WEIGHTS = {
    "track_lin_vel": 1.5,
    "track_ang_vel": 0.5,
    "lin_vel_z": -2.0,
    "ang_vel_xy": -0.05,
    "flat_orientation": -1.0,
    "joint_torques": -1.0e-5,
    "action_rate": -0.01,
    "action_smoothness": -0.01,
    "joint_power": -2.0e-5,
    "joint_acc": -2.5e-7,
    "joint_deviation": -0.01,
    "collision": -10.0,
    "stumble": -1.0,
    "foot_edge": -1.0,
}

# S1 은 발 가장자리 항의 가중치를 0 으로 둔다 (16 §5: 마스크 없음, S2-G0 와 보상 세트를 맞춘다)
S1_WEIGHT_OVERRIDES = {"foot_edge": 0.0}

STD2 = 0.25        # exp(-err / 0.25)
COLLISION_N = 0.1  # 충돌 판정 힘 (16 §1 12 항, N 으로 읽음: fable 20a S-13)
EDGE_DIST_CM = (2.5, 5.0)
EDGE_OMEGA = (1.0, 0.5)


def track_lin_exact(v_xy, cmd_xy):
    """B 식: exp(-||cmd - v||^2 / 0.25). 명령이 음수여도 대칭이다."""
    return torch.exp(-torch.sum((cmd_xy - v_xy) ** 2, dim=-1) / STD2)


def track_lin_min_form(v_xy, cmd_xy):
    """A 식(START 원문): exp(-||min(v, cmd) - cmd||^2 / 0.25). 기록용으로만 둔다."""
    return torch.exp(-torch.sum((torch.minimum(v_xy, cmd_xy) - cmd_xy) ** 2, dim=-1) / STD2)


def track_ang_exp(wz, cmd_wz):
    return torch.exp(-((wz - cmd_wz) ** 2) / STD2)


def lin_vel_z_l2(vz):
    return vz ** 2


def ang_vel_xy_l2(w_xy):
    return torch.sum(w_xy ** 2, dim=-1)


def flat_orientation_l2(gravity_b):
    """자세: g_x^2 + g_y^2 (몸 좌표계 중력 단위 벡터)."""
    return torch.sum(gravity_b[..., :2] ** 2, dim=-1)


def joint_torques_l2(tau):
    return torch.sum(tau ** 2, dim=-1)


def action_rate_l2(a_t, a_prev):
    return torch.sum((a_t - a_prev) ** 2, dim=-1)


def action_smoothness_l2(a_t, a_prev, a_prev2):
    """부드러움: sum (a_t - 2 a_{t-1} + a_{t-2})^2."""
    return torch.sum((a_t - 2.0 * a_prev + a_prev2) ** 2, dim=-1)


def joint_power(tau, qd):
    return torch.sum(torch.abs(tau) * torch.abs(qd), dim=-1)


def joint_acc_l2(qdd):
    return torch.sum(qdd ** 2, dim=-1)


def joint_deviation_l2(q, q_default):
    return torch.sum((q - q_default) ** 2, dim=-1)


def collision_count(forces_norm, threshold=COLLISION_N):
    """충돌: 판정 링크 중 힘이 문턱을 넘은 개수. `forces_norm` (n, links)."""
    return torch.sum((forces_norm > threshold).float(), dim=-1)


def stumble(foot_forces):
    """걸려 넘어짐: 어느 발이든 ||F_xy|| > 4 ||F_z|| 이면 1. `foot_forces` (n, feet, 3)."""
    xy = torch.linalg.norm(foot_forces[..., :2], dim=-1)
    z = torch.abs(foot_forces[..., 2])

    return torch.any(xy > 4.0 * z, dim=-1).float()


def foot_edge_penalty(feet_xy, contact, inner_mask, outer_mask, origin_xy, resolution):
    """발 가장자리 항: sum_feet c_i x sum_d w_d E_d[p_i] (부호는 가중치가 준다).

    `inner_mask` · `outer_mask` 는 (H, W) 불리언 격자(2.5 cm · 5 cm 띠, 바깥 띠는 안쪽 띠와 겹치는 곳을 뺀 것).
    S1 에서는 마스크가 없고 가중치가 0 이라 호출되지 않는다. S2 용 식을 같이 시험해 둔다.
    """
    idx = torch.floor((feet_xy - origin_xy) / resolution).long()
    h, w = inner_mask.shape
    ok = (idx[..., 0] >= 0) & (idx[..., 0] < h) & (idx[..., 1] >= 0) & (idx[..., 1] < w)
    ix = idx[..., 0].clamp(0, h - 1)
    iy = idx[..., 1].clamp(0, w - 1)
    inner = inner_mask[ix, iy].float() * ok.float()
    outer = outer_mask[ix, iy].float() * ok.float()

    return torch.sum(contact.float() * (EDGE_OMEGA[0] * inner + EDGE_OMEGA[1] * outer), dim=-1)


def foot_edge_penalty_tiles(feet_xy, contact, inner_all, outer_all, level, col, size=(8.0, 8.0), resolution=0.025):
    """칸별 마스크로 조회하는 발 가장자리 항 (S2). 마스크는 칸 좌표 격자라 발의 월드 좌표에서 칸 모서리를 빼 색인한다.

    `inner_all` · `outer_all` (rows, cols, H, W) bool. `level` · `col` (n,) env 별 현재 칸. 칸 밖의 발은 0.
    칸 모서리의 월드 좌표 = (줄 x size_x, 열 x size_y) (sparse_terrains.tile_to_world 와 같은 변환).
    """
    corner = torch.stack([level.to(feet_xy.dtype) * size[0], col.to(feet_xy.dtype) * size[1]], dim=-1)[:, None, :]
    idx = torch.floor((feet_xy - corner) / resolution).long()
    h, w = inner_all.shape[-2:]
    ok = (idx[..., 0] >= 0) & (idx[..., 0] < h) & (idx[..., 1] >= 0) & (idx[..., 1] < w)
    ix = idx[..., 0].clamp(0, h - 1)
    iy = idx[..., 1].clamp(0, w - 1)
    lv = level[:, None].expand_as(ix)
    cl = col[:, None].expand_as(ix)
    inner = inner_all[lv, cl, ix, iy].float() * ok.float()
    outer = outer_all[lv, cl, ix, iy].float() * ok.float()

    return torch.sum(contact.float() * (EDGE_OMEGA[0] * inner + EDGE_OMEGA[1] * outer), dim=-1)


# 종아리 펴짐 한계 띠 (창 3 처방 후보 1축, 초안 DESIGN-W3 §3.1). 이 값은 «양의 크기»이고 부호는 cfg 가중치가 정한다(다른 벌점 항과 같은 규약).
# 기본 가중치 0 = 꺼짐: Isaac Lab RewardManager 는 weight == 0 인 항을 계산하지 않는다(설치 reward_manager.py).
CALF_BAND_MARGIN = 0.05
CALF_BAND_WEIGHT_OFF = 0.0


def calf_extension_band(q_calf, hard_hi, margin=CALF_BAND_MARGIN):
    """q_calf [N,4] 종아리 네 관절각, hard_hi [N,4] 또는 [4] 시뮬레이터가 아는 hard 상한. 반환 [N] = sum_j max(0, q_j - (hard_hi_j - margin)).
    펴진 쪽(상한)만 본다. 하한 쪽은 0."""
    return torch.clamp(q_calf - (hard_hi - margin), min=0.0).sum(dim=-1)
