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


def mask_new_task(move, had_new_task):
    """새 과제 표식이 있는 에피소드는 승급 · 강등에서 뺀다(행 유지, 0). 표식이 모두 거짓이면 입력과 비트 단위로 같다 (JUDGE-SPEC 5.2 3).

    임시 행 유지다(성과 기반 지형 커리큘럼 완성이 아니다). 표식 없는 env · 에피소드는 기존 규칙 그대로.
    """
    move = torch.as_tensor(move)
    mark = torch.as_tensor(had_new_task, dtype=torch.bool, device=move.device)
    out = move.clone()
    out[mark] = 0

    return out


class NewTaskStats:
    """update 한 번 동안의 표식 통계 (JUDGE-SPEC 5.2 6). `add` 로 쌓고 `take` 로 꺼내 비운다. 순수 torch.

    에피소드 수, 표식 참 수 · 비율, 표식 유무별 판정 수(표식 있는 쪽은 «막지 않았다면» 의 원래 판정과 실제 0 을 함께), 지형 행별 에피소드 수(전체 · 표식).
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.episodes = 0
        self.marked = 0
        self.unmarked_up = self.unmarked_down = self.unmarked_stay = 0
        self.marked_would_up = self.marked_would_down = self.marked_would_stay = 0
        self.row_total = {}
        self.row_marked = {}

    def add(self, move_raw, had_new_task, levels):
        move_raw = torch.as_tensor(move_raw).cpu()
        mark = torch.as_tensor(had_new_task, dtype=torch.bool).cpu()
        levels = torch.as_tensor(levels).cpu().long()
        self.episodes += int(move_raw.numel())
        self.marked += int(mark.sum())
        um, mm = ~mark, mark
        self.unmarked_up += int(((move_raw > 0) & um).sum())
        self.unmarked_down += int(((move_raw < 0) & um).sum())
        self.unmarked_stay += int(((move_raw == 0) & um).sum())
        self.marked_would_up += int(((move_raw > 0) & mm).sum())
        self.marked_would_down += int(((move_raw < 0) & mm).sum())
        self.marked_would_stay += int(((move_raw == 0) & mm).sum())

        for lv in levels.unique().tolist():
            sel = levels == lv
            self.row_total[int(lv)] = self.row_total.get(int(lv), 0) + int(sel.sum())
            self.row_marked[int(lv)] = self.row_marked.get(int(lv), 0) + int((sel & mark).sum())

    def take(self):
        """쌓인 통계를 사전으로 꺼내고 비운다. 쌓인 것이 없으면 None."""
        if self.episodes == 0:
            return None

        out = {"episodes": self.episodes, "marked": self.marked, "marked_frac": self.marked / self.episodes,
               "unmarked": {"up": self.unmarked_up, "down": self.unmarked_down, "stay": self.unmarked_stay},
               "marked_would_have": {"up": self.marked_would_up, "down": self.marked_would_down, "stay": self.marked_would_stay},
               "marked_actual": {"up": 0, "down": 0, "stay": self.marked},
               "per_row": {str(k): v for k, v in sorted(self.row_total.items())}, "per_row_marked": {str(k): v for k, v in sorted(self.row_marked.items())}}
        self.reset()

        return out
