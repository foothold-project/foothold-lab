"""MGDP 보상 묶음의 순수 계산 (EX-13 · EX-14, SONNET-X13). Kit 없이 시험된다. Kit 쪽 항 클래스는 `mgdp_terms.py`.

원본: MGDP `legged_gym/envs/random_dog/random_dog.py` (feet_air_time 1004 행 · motion_trot 803 행), `envs/base/legged_robot.py` (stand_still 1099 행 ·
only_positive_rewards 237 행). 식은 아래 «고친 곳» 말고는 원문 그대로다.

고친 곳 (lead 지시 · 문서 `mgdp_rewards.md` 에도 적음):
1. motion_trot: 원문은 관절각 q 의 대각 다리 차를 쓰지만 Go2 기본 자세는 hip 이 왼쪽 +0.1 · 오른쪽 -0.1 이라 원식 그대로면 서 있기만 해도 상수 벌점 0.4 가 생긴다.
   그래서 q 대신 (q - q_default) 의 대각 차를 쓴다. 관절 짝은 번호가 아니라 이름으로 맺는다(Isaac Lab 은 종류별 hip 4 · thigh 4 · calf 4 순서, legged_gym 은 다리별).
2. stand_still: 원식은 |cmd_xy| < 0.1 만 문으로 쓰는데 START 제자리 회전(vx = 0, wz != 0)에서 켜져 회전을 막는다. |cmd_xy| < 0.1 그리고 |wz| < 0.1 일 때만 켠다.
3. feet_air_time 은 원문 그대로(접촉 판정 Fz > 1 N 과 직전 접촉 OR, 첫 접촉에서만 sum(air_time - 0.5), |cmd_xy| > 0.1 일 때만).
   Isaac Lab mdp.feet_air_time 과 달리 접촉 직전 step 의 dt 까지 더한 값을 쓰고(원문 순서: air += dt 를 보상 계산 앞에서), 접촉 판정에 직전 접촉과의 OR 을 쓴다.
"""

from __future__ import annotations

import torch

LEG_PAIRS = (("FL", "RR"), ("FR", "RL"))          # 대각 다리 짝(trot)
KINDS = ("hip", "thigh", "calf")
ENV_GAIT_LEVEL = 3                                  # MGDP random_dog_config_stage1.py:17 env_gait = 3: 지형 단계가 이보다 크면 trot 벌점 0
TROT_STEP_LIMIT = 2e4                               # random_dog.py:826 common_step_counter > 2e4 면 0 (update 약 833 회 = 2e4 / 24)
CONTACT_FORCE_N = 1.0                               # random_dog.py:1010
AIR_TIME_THRESHOLD_S = 0.5                          # random_dog.py:1015
CMD_THRESHOLD = 0.1


def pair_indices(joint_names) -> tuple[list[int], list[int]]:
    """관절 이름 목록 -> (A 인덱스들, B 인덱스들). A[i] 와 B[i] 가 대각 짝의 같은 종류 관절이다 (FL-RR 의 hip · thigh · calf, 그다음 FR-RL)."""
    idx = {n: i for i, n in enumerate(joint_names)}
    a, b = [], []

    for l1, l2 in LEG_PAIRS:
        for kind in KINDS:
            a.append(idx[f"{l1}_{kind}_joint"])
            b.append(idx[f"{l2}_{kind}_joint"])

    return a, b


def trot_penalty(dq: torch.Tensor, a: list[int], b: list[int], terrain_levels: torch.Tensor, step_counter: float,
                 env_gait: int = ENV_GAIT_LEVEL, step_limit: float = TROT_STEP_LIMIT) -> torch.Tensor:
    """sum |dq_A - dq_B| (dq = q - q_default). 지형 단계 > env_gait 인 env 는 0, 전체 step 이 step_limit 을 넘으면 전부 0 (원문과 같은 부등호)."""
    rew = (dq[:, a] - dq[:, b]).abs().sum(dim=1)
    rew = torch.where(terrain_levels > env_gait, torch.zeros_like(rew), rew)

    if step_counter > step_limit:
        rew = rew * 0.0

    return rew


def stand_still_penalty(dq: torch.Tensor, cmd: torch.Tensor, thr: float = CMD_THRESHOLD) -> torch.Tensor:
    """sum |q - q_default|, 명령이 «정말 0 근처» 일 때만: |cmd_xy| < thr 그리고 |wz| < thr."""
    gate = (cmd[:, :2].norm(dim=1) < thr) & (cmd[:, 2].abs() < thr)

    return dq.abs().sum(dim=1) * gate


def air_time_step(air: torch.Tensor, last_contacts: torch.Tensor, fz: torch.Tensor, cmd_xy_norm: torch.Tensor, dt: float,
                  threshold: float = AIR_TIME_THRESHOLD_S, force_n: float = CONTACT_FORCE_N, cmd_thr: float = CMD_THRESHOLD):
    """MGDP _reward_feet_air_time 한 step. air (N,4) · last_contacts (N,4 bool) · fz (N,4) 발 수직력. 돌려줌: (보상 (N,), 새 air, 새 last_contacts)."""
    contact = fz > force_n
    contact_filt = contact | last_contacts
    first_contact = (air > 0.0) & contact_filt
    air = air + dt
    rew = ((air - threshold) * first_contact).sum(dim=1)
    rew = rew * (cmd_xy_norm > cmd_thr)
    air = air * (~contact_filt)

    return rew, air, contact


def clamp_positive(total: torch.Tensor, clipped_steps: torch.Tensor | None = None):
    """only_positive_rewards: 한 step 의 보상 합을 0 아래로 자른다 (legged_robot.py:237). 돌려줌: (잘린 합, 잘렸는지(N,) bool, 갱신된 잘린 step 수).
    (원문은 termination 보상을 자른 뒤에 더한다. 우리 env 에는 termination 보상 항이 없다.)"""
    neg = total < 0.0
    steps = None if clipped_steps is None else clipped_steps + neg.to(clipped_steps.dtype)

    return torch.clamp(total, min=0.0), neg, steps
