"""legged_gym A1 기저 묶음 (EX-15, SONNET-X15)의 Kit 없는 계산. Kit 쪽 항은 `lg_terms.py`.

원본: leggedrobotics/legged_gym master `legged_gym/envs/base/legged_robot.py` (_process_dof_props · _reward_dof_pos_limits · _reward_collision),
`envs/a1/a1_config.py` (dof_pos_limits -10.0, torques -0.0002, soft_dof_pos_limit 0.9).

여기에는 «시험이 비교할 기준 식» 두 개와 충돌 몸체 확인만 둔다. 실제 보상은 Isaac Lab 의 `mdp.joint_pos_limits` 를 쓴다:
그 식(한계 밖 초과량의 합)은 legged_gym 과 같고, soft 한계는 Go2 로봇 cfg 의 `soft_joint_pos_limit_factor=0.9`(UNITREE_GO2_CFG)가 중심 ± 0.5 x 반폭 x 0.9 로 만든다
(Isaac Lab articulation.py:767~768 = legged_gym _process_dof_props 와 같은 식). 그래서 로봇 cfg 도 reset 클램프도 바꾸지 않는다.
"""

from __future__ import annotations

import torch

COLLISION_BODY_PATTERNS = ["base", ".*_thigh", ".*_calf", "Head_.*"]     # START 의 ["base", ".*_thigh", "Head_.*"] 에 calf 추가


def lg_soft_limits(hard: torch.Tensor, soft_factor: float = 0.9) -> torch.Tensor:
    """legged_robot.py _process_dof_props: m = (lo + hi) / 2, r = hi - lo, soft = m ∓ 0.5 r soft_factor. hard (..., 2) -> (..., 2)."""
    m = (hard[..., 0] + hard[..., 1]) / 2
    r = hard[..., 1] - hard[..., 0]

    return torch.stack([m - 0.5 * r * soft_factor, m + 0.5 * r * soft_factor], dim=-1)


def lg_dof_pos_limits(q: torch.Tensor, soft_limits: torch.Tensor) -> torch.Tensor:
    """legged_robot.py _reward_dof_pos_limits 그대로: -(q - lo).clip(max=0) + (q - hi).clip(min=0) 의 관절 합."""
    out = -(q - soft_limits[..., 0]).clip(max=0.0)
    out += (q - soft_limits[..., 1]).clip(min=0.0)

    return out.sum(dim=1)


def isaac_joint_pos_limits(q: torch.Tensor, soft_limits: torch.Tensor) -> torch.Tensor:
    """Isaac Lab isaaclab/envs/mdp/rewards.py joint_pos_limits 의 식(위 mdp 함수와 같은 계산)."""
    out = -(q - soft_limits[..., 0]).clip(max=0.0)
    out += (q - soft_limits[..., 1]).clip(min=0.0)

    return torch.sum(out, dim=1)


def check_collision_bodies(body_names, penalised_ids) -> dict:
    """충돌 벌점 몸체 확인: calf 4 개 · foot 4 개가 서로 다른 강체로 존재하고, 벌점 대상에 calf 는 모두 들어 있고 foot 은 하나도 없어야 한다.
    foot 이 calf 의 일부(별도 foot 강체 없음)이거나 foot 이 벌점 대상이면 예외(정상 접지가 벌점이 되는 일을 막는다). 돌려줌: 이름 확인표."""
    names = list(body_names)
    calf = [i for i, n in enumerate(names) if str(n).endswith("_calf")]
    foot = [i for i, n in enumerate(names) if str(n).endswith("_foot")]
    pen = set(range(len(names))) if isinstance(penalised_ids, slice) else set(int(i) for i in penalised_ids)

    if len(calf) != 4 or len(foot) != 4:
        raise RuntimeError(f"calf {len(calf)} 개 · foot {len(foot)} 개: 별도 foot 강체가 없으면(foot 이 calf 의 일부) calf 를 충돌 벌점에 넣으면 정상 접지가 벌점이 된다")

    if set(calf) & set(foot):
        raise RuntimeError("calf 와 foot 이 같은 강체다")

    if not set(calf) <= pen:
        raise RuntimeError("calf 가 충돌 벌점 대상에 다 들어 있지 않다")

    if set(foot) & pen:
        raise RuntimeError("foot 이 충돌 벌점 대상에 들어 있다 (정상 접지가 벌점이 된다)")

    return {"calf": [names[i] for i in calf], "foot": [names[i] for i in foot], "penalised": [names[i] for i in sorted(pen)]}
