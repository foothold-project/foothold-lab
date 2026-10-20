"""승급 · 강등 규칙 (14 §5). torch (CPU/GPU 공용). Isaac Lab 쪽 term 은 `terrain_levels_mixed.py`.

방식마다 다르다.
  깃발      승급: 깃발을 다 지남. 강등: 깃발 절반 미만 (JEPLO 868~872 의 식).
  자유 속도 승급: 스폰에서 최대 이동 거리 > 지형 길이 / 2 (8 m 칸이면 4 m).
            강등: 최대 이동 거리 < 0.5 x ||그 에피소드에 뽑힌 명령 벡터의 합|| x 재추출 간격 x 0.9.
  명령을 한 번도 안 받은 에피소드(정지 · 제자리 회전만)는 승급 · 강등 판정에서 뺀다 (14 §5 가정).
반환값: +1 승급, -1 강등, 0 유지.
"""

import torch


def judge_free(max_dist_m, cmd_sum_xy, size_x=8.0, resample_s=4.0, factor=0.9, eps=1.0e-9):
    """자유 속도 env 들의 판정. `cmd_sum_xy` (n, 2) = 에피소드 동안 뽑힌 (vx, vy) 의 합(움직임 명령 재추출만)."""
    max_dist_m = torch.as_tensor(max_dist_m, dtype=torch.float32)
    cmd_sum_xy = torch.as_tensor(cmd_sum_xy, dtype=torch.float32)
    norm = torch.linalg.norm(cmd_sum_xy, dim=1)
    out = torch.zeros(len(max_dist_m), dtype=torch.long, device=max_dist_m.device)
    active = norm > eps
    up = active & (max_dist_m > size_x / 2.0)
    down = active & (max_dist_m < 0.5 * norm * resample_s * factor) & ~up
    out[up] = 1
    out[down] = -1

    return out


def judge_flag(goals_covered, num_goals, walk_frac=None, min_walk=0.25):
    """깃발 env 들의 판정.

    `walk_frac` (n,) = 에피소드 중 «걷는 시간» 비율. 제자리 회전(v < 0.3) · 물러나기 구간은 깃발 수 판정에서 시간만큼 뺀다
    (14 §5 116 행): 필요한 깃발 수를 `num_goals x walk_frac` 로 줄인다. 걷는 시간이 `min_walk` 미만이면 판정에서 뺀다(0, 가정).
    `walk_frac` 이 None 이면 예전 식(전부 통과 승급, 절반 미만 강등).
    """
    goals_covered = torch.as_tensor(goals_covered)
    num_goals = torch.as_tensor(num_goals)
    out = torch.zeros(len(goals_covered), dtype=torch.long, device=goals_covered.device)

    if walk_frac is None:
        required = num_goals.float()
        valid = torch.ones_like(out, dtype=torch.bool)
    else:
        walk_frac = torch.as_tensor(walk_frac, dtype=torch.float32, device=goals_covered.device)
        required = num_goals.float() * walk_frac
        valid = walk_frac >= min_walk

    up = valid & (goals_covered.float() >= required - 1.0e-6)
    down = valid & (goals_covered.float() * 2.0 < required) & ~up
    out[up] = 1
    out[down] = -1

    return out


def judge(is_flag, max_dist_m, cmd_sum_xy, goals_covered, num_goals, size_x=8.0, walk_frac=None):
    """두 방식을 한 번에. 깃발 env 는 깃발 규칙, 나머지는 자유 속도 규칙."""
    is_flag = torch.as_tensor(is_flag, dtype=torch.bool)

    return torch.where(is_flag, judge_flag(goals_covered, num_goals, walk_frac), judge_free(max_dist_m, cmd_sum_xy, size_x))
