"""승급 · 강등 term 과 명령 범위 커리큘럼 term (14 §4 · §5). Kit 안에서만 불린다. 규칙은 `rules.py`.

Isaac 의 reset 순서는 curriculum → 이벤트 → command reset 이라, 이 term 이 읽는 `max_dist` 등은 «방금 끝난 에피소드» 값이다.
"""

from __future__ import annotations

import torch

from foothold_s2.curriculum import rules
from foothold_s2.terrains import s2_runtime


def terrain_levels_mixed(env, env_ids, command_name: str = "base_velocity", resample_s: float = 4.0, world_frame: bool = True, mask_new_task: bool = False):
    """깃발 env 는 깃발 규칙, 자유 속도 env 는 거리 규칙으로 지형 단계를 올리고 내린다. 단계 평균을 돌려준다.

    world_frame (J-T10, 팀장 결정 8 로 기본 켬): 참이면 자유 속도 판정의 명령 합을 몸 기준 `cmd_sum_xy` 대신 세계 좌표 기대 변위 `cmd_sum_w` 로 낸다.
    mask_new_task (JUDGE-SPEC v0.8 5.2 의 3, 기본 False): 참이면 새 과제 명령을 받은 에피소드의 move 를 0 으로 덮는다(옛 동작). 거짓이면 덮지 않고 `term.new_task_stats` 로 기록만 한다.
    False 를 주면 옛 동작(몸 기준 합)이고 옛 식과 비트 단위로 같다. 어느 쪽이든 두 판정을 모두 계산해 9 칸 표(`term.frame_stats`)로 병행 기록하니 갈린 에피소드 수는 계속 남는다.
    """
    term = env.command_manager.get_term(command_name)
    terrain = env.scene.terrain
    env_ids = torch.as_tensor(env_ids, device=env.device, dtype=torch.long)

    # 점 명령 합을 «재추출 한 번당 한 번 뽑힌 값의 합» 단위로 (rules.judge_free 의 0.5 x 합 x 4 s x 0.9 식에 맞춤)
    cmd_sum = term.cmd_sum_xy[env_ids] * env.step_dt / resample_s
    size_x = terrain.cfg.terrain_generator.size[0]
    num_goals = torch.full((len(env_ids),), term.cfg.flag_count, device=env.device)

    move = rules.judge(term.is_flag_env[env_ids], term.max_dist[env_ids], cmd_sum, term.goals[env_ids],
                       num_goals, size_x=size_x, walk_frac=term.walk_frac[env_ids])
    marked = getattr(term, "had_new_task", None)
    cmd_sum_w = getattr(term, "cmd_sum_w", None)

    if cmd_sum_w is None and world_frame:
        raise ValueError("world_frame=True 인데 명령 term 에 cmd_sum_w 가 없다")
    if cmd_sum_w is not None:                                    # 병행 기록: 세계 좌표 판정을 같은 식으로 한 번 더 계산한다(끔이면 판정에 쓰지 않는다)
        move_w = rules.judge(term.is_flag_env[env_ids], term.max_dist[env_ids], cmd_sum_w[env_ids] * env.step_dt / resample_s, term.goals[env_ids],
                             num_goals, size_x=size_x, walk_frac=term.walk_frac[env_ids])
        stats = getattr(term, "frame_stats", None)

        if stats is not None:
            stats.add(move, move_w, None if marked is None else marked[env_ids], world_frame=world_frame, select=~term.is_flag_env[env_ids])
        if world_frame:
            move = move_w

    if marked is not None:                                       # 새 과제 명령을 받은 에피소드는 승급 · 강등에서 뺀다(행 유지, JUDGE-SPEC 5.2). 표식이 모두 거짓이면 이 블록은 move 를 바꾸지 않는다
        marked = marked[env_ids]
        term.new_task_stats.add(move, marked, terrain.terrain_levels[env_ids])
        if mask_new_task:
            move = rules.mask_new_task(move, marked)

    terrain.update_env_origins(env_ids, move > 0, move < 0)

    return torch.mean(terrain.terrain_levels.float())


class _Acc:
    """한 반복 동안 env 에피소드의 추종 보상 비율을 모은다 (자유 속도용 · 깃발용 하나씩)."""

    def __init__(self):
        self.lin = 0.0
        self.ang = 0.0
        self.n = 0

    def add(self, lin_sum, ang_sum, n):
        self.lin += lin_sum
        self.ang += ang_sum
        self.n += n

    def take(self):
        out = (self.lin / self.n, self.ang / self.n) if self.n > 0 else None
        self.lin = self.ang = 0.0
        self.n = 0

        return out


def apply_range_update(rc, free_acc, flag_acc, iteration, flag_median_level):
    """반복이 바뀌는 순간 두 상한을 따로 올린다. 순수 계산(시험 가능). 돌려주는 값: (자유 올림, 깃발 올림)."""
    free = free_acc.take()
    flag = flag_acc.take()
    up_free = rc.update(free[0], free[1], iteration=iteration) if free is not None else False
    up_flag = rc.update_flag(flag[0], flag[1], flag_median_level, iteration=iteration) if flag is not None else False

    return up_free, up_flag


def command_range_curriculum(env, env_ids, command_name: str = "base_velocity",
                             lin_term: str = "track_lin_vel", ang_term: str = "track_ang_vel"):
    """추종 보상 에피소드 합 / (가중치 x 에피소드 길이) 의 평균이 둘 다 gamma 이상이면 상한을 0.25 올린다 (반복당 한 번).

    자유 속도 env 는 vmax_x · vmax_y 를, 깃발 env 는 깃발 속도 상한 flag_vmax 를 올린다(깃발은 그 env 들의 지형 레벨 중앙값 >= 5
    조건이 더 붙는다, 14 §4). 평균은 한 반복 동안 끝난 에피소드로 낸다. 돌려주는 값은 현재 상한들(로그).
    """
    term = env.command_manager.get_term(command_name)
    rm = env.reward_manager
    env_ids = torch.as_tensor(env_ids, device=env.device, dtype=torch.long)

    if not hasattr(term, "_range_acc"):
        term._range_acc = (_Acc(), _Acc())
        term._range_last_iter = -1

    free_acc, flag_acc = term._range_acc
    horizon = env.max_episode_length_s
    w_lin = rm.get_term_cfg(lin_term).weight
    w_ang = rm.get_term_cfg(ang_term).weight
    is_flag = term.is_flag_env[env_ids]

    for acc, ids in ((free_acc, env_ids[~is_flag]), (flag_acc, env_ids[is_flag])):
        if len(ids) > 0:
            acc.add(float((rm._episode_sums[lin_term][ids] / (w_lin * horizon)).sum()),
                    float((rm._episode_sums[ang_term][ids] / (w_ang * horizon)).sum()), len(ids))

    it = term.iteration

    if it != term._range_last_iter:
        flag_levels = env.scene.terrain.terrain_levels[term.is_flag_env].float()
        median = float(flag_levels.median()) if len(flag_levels) > 0 else 0.0
        apply_range_update(term.range_curriculum, free_acc, flag_acc, it, median)

    term._range_last_iter = it

    return {"vmax_x": term.range_curriculum.vmax_x, "flag_vmax": term.range_curriculum.flag_vmax}


def judge_settings(env_cfg) -> dict:
    """실제로 쓰이는 판정 설정(manifest `terrain_judge`). 커리큘럼 term 의 함수 기본값에 설정의 params 를 덮어 읽는다. term 이 없으면 빈 사전."""
    import inspect

    cur = getattr(getattr(env_cfg, "curriculum", None), "terrain_levels", None)

    if cur is None or getattr(cur, "func", None) is None:
        return {}
    sig = inspect.signature(cur.func).parameters
    params = dict(getattr(cur, "params", None) or {})

    return {k: bool(params.get(k, sig[k].default)) for k in ("world_frame", "mask_new_task") if k in sig}


def apply_judge_args(env_cfg, world_frame=None, mask_new_task=None) -> None:
    """실행 인자(on/off 문자열 또는 bool, None 이면 건드리지 않음)를 커리큘럼 term params 에 쓴다. 그 term 이 모르는 인자면 거절."""
    import inspect

    cur = getattr(getattr(env_cfg, "curriculum", None), "terrain_levels", None)

    if cur is None or getattr(cur, "func", None) is None:
        if world_frame is not None or mask_new_task is not None:
            raise ValueError("커리큘럼 terrain_levels term 이 없어 판정 인자를 줄 수 없다")
        return
    sig = inspect.signature(cur.func).parameters

    for k, v in {"world_frame": world_frame, "mask_new_task": mask_new_task}.items():
        if k not in sig:
            if v is not None:
                raise ValueError(f"커리큘럼 term {cur.func.__name__} 은 {k} 인자를 받지 않는다")
            continue
        params = dict(cur.params or {})
        params[k] = bool(params.get(k, sig[k].default)) if v is None else v in (True, "on")      # 인자가 없어도 실제 값을 params 에 박아 env.yaml 에 남긴다
        cur.params = params


OLD_PARENT_JUDGE = "world_frame=False (10/26 이전)"


def parent_judge(checkpoint_path) -> dict | str:
    """이어 시작하는 부모 체크포인트가 어떤 판정으로 학습됐나. 같은 폴더의 manifest.json 의 modes.terrain_judge 를 읽고, 없으면 결정 8 이전의 옛 판정 문구."""
    import json
    import os

    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(checkpoint_path)), "manifest.json"), encoding="utf-8") as f:
            found = json.load(f)["modes"]["terrain_judge"]
    except (OSError, KeyError, TypeError, ValueError):
        return OLD_PARENT_JUDGE

    return found if isinstance(found, dict) and "world_frame" in found else OLD_PARENT_JUDGE


def judged_with(parent) -> str:
    """JUDGE-SPEC J-T10 의 start_checkpoint_judged_with: 부모가 세계 좌표 판정이면 world_frame, 아니면(옛 문구 포함) body_frame."""
    return "world_frame" if isinstance(parent, dict) and parent.get("world_frame") is True else "body_frame"


def stage_T(iteration, offset):
    """이 단계의 반복 수 T (p_advance 의 입력). 이어 시작한 회차(offset)를 빼서 0 부터 센다."""
    return max(0, int(iteration) - int(offset))


def terrain_levels_s2(env, env_ids, command_name: str = "base_velocity", resample_s: float = 4.0, seed: int = 0,
                      t_start: int = 1000, t_end: int = 8000, p_max: float = 0.9, world_frame: bool = True, mask_new_task: bool = False):
    """S2 · S1-b: 승급 · 강등(`terrain_levels_mixed`) 뒤 듬성한 env 의 열을 p_advance 로 다시 뽑는다 (15 §5 · §8.1 ①).

    S2 는 T_start 1000 · T_end 8000, S1-b 는 자체 반복 수 기준 0 · 1500 (15 §5 · VERIFY-lead-final 7).

    `env.s2_tables` (`s2_runtime.S2Tables`) 가 있어야 한다. env 생성 직후 한 번 붙인다 (`attach_s2_tables`).
    """
    import numpy as np

    value = terrain_levels_mixed(env, env_ids, command_name, resample_s, world_frame=world_frame, mask_new_task=mask_new_task)
    term = env.command_manager.get_term(command_name)

    if not hasattr(env, "_s2_rng"):
        env._s2_rng = np.random.default_rng(seed)

    # T = 이 단계의 반복 수. S1-b 는 S1-a 체크포인트에서 이어 시작하므로 env.stage_iteration_offset(이어 시작한 회차) 를 빼서 0 부터 센다
    T = stage_T(term.iteration, getattr(env, "stage_iteration_offset", 0))
    s2_runtime.reassign(env.scene.terrain, env.s2_tables, env_ids, T, env._s2_rng, T_start=t_start, T_end=t_end, p_max=p_max)

    return value


def attach_s2_tables(env, side_table, layout, flag_count: int = 4):
    """생성기가 끝난 뒤 side table 을 (줄, 열) 에 묶고 텐서를 env 에 붙인다. 명령 term 의 깃발 공급자도 이어 준다."""
    terrain = env.scene.terrain
    gen = terrain.cfg.terrain_generator
    side_table.bind_all(layout.names, gen.num_rows)
    env.s2_tables = s2_runtime.S2Tables(side_table, layout, gen.num_rows, env.device, flag_count)
    cmd_cfg = env.command_manager.get_term("base_velocity").cfg
    cmd_cfg.flag_provider = env.s2_tables.flag_provider
    cmd_cfg.force_flag_provider = env.s2_tables.force_flag
