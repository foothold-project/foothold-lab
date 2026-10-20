"""승급 · 강등 term 과 명령 범위 커리큘럼 term (14 §4 · §5). Kit 안에서만 불린다. 규칙은 `rules.py`.

Isaac 의 reset 순서는 curriculum → 이벤트 → command reset 이라, 이 term 이 읽는 `max_dist` 등은 «방금 끝난 에피소드» 값이다.
"""

from __future__ import annotations

import torch

from foothold_s2.curriculum import rules


def terrain_levels_mixed(env, env_ids, command_name: str = "base_velocity", resample_s: float = 4.0):
    """깃발 env 는 깃발 규칙, 자유 속도 env 는 거리 규칙으로 지형 단계를 올리고 내린다. 단계 평균을 돌려준다."""
    term = env.command_manager.get_term(command_name)
    terrain = env.scene.terrain
    env_ids = torch.as_tensor(env_ids, device=env.device, dtype=torch.long)

    # 점 명령 합을 «재추출 한 번당 한 번 뽑힌 값의 합» 단위로 (rules.judge_free 의 0.5 x 합 x 4 s x 0.9 식에 맞춤)
    cmd_sum = term.cmd_sum_xy[env_ids] * env.step_dt / resample_s
    size_x = terrain.cfg.terrain_generator.size[0]
    num_goals = torch.full((len(env_ids),), term.cfg.flag_count, device=env.device)

    move = rules.judge(term.is_flag_env[env_ids], term.max_dist[env_ids], cmd_sum, term.goals[env_ids],
                       num_goals, size_x=size_x)
    terrain.update_env_origins(env_ids, move > 0, move < 0)

    return torch.mean(terrain.terrain_levels.float())


class _Acc:
    """한 반복 동안 자유 속도 env 의 추종 보상 비율을 모은다."""

    def __init__(self):
        self.lin = 0.0
        self.ang = 0.0
        self.n = 0
        self.last_iter = -1


def command_range_curriculum(env, env_ids, command_name: str = "base_velocity",
                             lin_term: str = "track_lin_vel", ang_term: str = "track_ang_vel"):
    """추종 보상 에피소드 합 / (가중치 x 에피소드 길이) 의 평균이 둘 다 gamma 이상이면 vmax 를 0.25 올린다 (반복당 한 번).

    평균은 한 반복 동안 끝난 자유 속도 env 에피소드로 낸다. 돌려주는 값은 현재 vx 상한.
    """
    term = env.command_manager.get_term(command_name)
    rm = env.reward_manager
    env_ids = torch.as_tensor(env_ids, device=env.device, dtype=torch.long)

    if not hasattr(term, "_range_acc"):
        term._range_acc = _Acc()

    acc = term._range_acc
    free = env_ids[~term.is_flag_env[env_ids]]

    if len(free) > 0:
        horizon = env.max_episode_length_s
        w_lin = rm.get_term_cfg(lin_term).weight
        w_ang = rm.get_term_cfg(ang_term).weight
        acc.lin += float((rm._episode_sums[lin_term][free] / (w_lin * horizon)).sum())
        acc.ang += float((rm._episode_sums[ang_term][free] / (w_ang * horizon)).sum())
        acc.n += len(free)

    it = term.iteration

    if it != acc.last_iter and acc.n > 0:
        term.range_curriculum.update(acc.lin / acc.n, acc.ang / acc.n, iteration=it)
        acc.lin = acc.ang = 0.0
        acc.n = 0

    acc.last_iter = it

    return torch.tensor(term.range_curriculum.vmax_x)
