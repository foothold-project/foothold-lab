"""T5 probe 의 고정 칸: 평지 계열 2 env + random_rough 2 env, 모두 레벨 0 (설계 §7.1 '평지와 rough 중앙', SONNET-X25).

열 번호 -> 종류 이름은 설치 Isaac Lab 의 고정 배치 식(terrain_generator.py `_generate_curriculum_terrains`: index / num_cols + 0.001 < cumsum(proportion))을
terrains.columns.column_types 로 되풀이해 계산한다(시험이 설치 소스에 이 식이 그대로 있는지 대조). 종류 이름은 실행 중인 env 의 지형 생성기 cfg 에서 읽는다.
평지 열: 이름이 'flat' 인 열이 있으면 그것, 없으면 경사 피라미드(hf_pyramid_slope)의 레벨 0 -- 순수 평지가 아니라 «경사 최저 난이도, 중앙 평탄 플랫폼 2 m» 이며
기록에 그 사실(flat_note)을 적는다. 그것도 없으면 만들지 않고 거절한다. 각 그룹에서 첫 열과 마지막 열을 쓴다(중복 없이 2 개, 그룹 열이 1 개면 거절).
"""

from __future__ import annotations

import numpy as np

from foothold_s2.eval.fixed_terrain import assignment_sha256
from foothold_s2.terrains import columns

FLAT_PREFERENCE = ("flat", "hf_pyramid_slope")
ROUGH = "random_rough"
LEVEL = 0


def column_names(sub_terrain_proportions: dict, num_cols: int) -> list[str]:
    return columns.column_types(sub_terrain_proportions, num_cols)


def pick(names: list[str], num_envs: int = 4, level: int = LEVEL):
    """names = 열 번호 -> 종류 이름. 반환: (levels, types, flat_kind, tiles). env 순서 = [평지 첫 열 x k, 평지 끝 열 x k, rough 첫 열 x k, rough 끝 열 x k], k = num_envs / 4.
    4 의 배수 env 를 받는다(4 env 는 k=1 이라 예전 배치와 같다). 같은 칸의 env 들은 reset 때 spawn 이 서로 다르다."""
    if num_envs < 4 or num_envs % 4:
        raise ValueError(f"probe 고정 칸은 4 env 의 배수(4 env 용 배치를 칸마다 같은 수로 늘림)만 받는다(받은 값 {num_envs})")
    per = num_envs // 4
    flat_kind = next((k for k in FLAT_PREFERENCE if k in names), None)

    if flat_kind is None:
        raise ValueError(f"평지 계열 열({FLAT_PREFERENCE})이 지형 생성기에 없다: {sorted(set(names))}")
    flat_cols = [i for i, n in enumerate(names) if n == flat_kind]
    rough_cols = [i for i, n in enumerate(names) if n == ROUGH]

    for kind, cs in ((flat_kind, flat_cols), (ROUGH, rough_cols)):
        if len(cs) < 2:
            raise ValueError(f"{kind} 열이 2 개 미만이다: {cs}")
    types = np.repeat(np.array([flat_cols[0], flat_cols[-1], rough_cols[0], rough_cols[-1]], dtype=np.int64), per)
    levels = np.full(num_envs, int(level), dtype=np.int64)
    tiles = [{"env": i, "kind": names[int(types[i])], "level": int(levels[i]), "col": int(types[i])} for i in range(num_envs)]

    return levels, types, flat_kind, tiles


def record(levels, types, flat_kind: str, tiles: list, rows: int, cols: int, level: int = LEVEL) -> dict:
    if flat_kind == "flat":
        note = None if level == 0 else "평지 열이어도 레벨 %d 는 바닥이 평평하다는 뜻이 아니다(열 종류만 같고 난이도를 올렸다)" % level
    elif level == 0:
        note = "순수 평지 열이 생성기에 없어 경사 피라미드 레벨 0(경사 최저 난이도, 중앙 평탄 플랫폼)을 평지 계열로 썼다"
    else:
        note = "순수 평지 열이 없어 경사 피라미드를 평지 계열 자리에 썼고 레벨 %d 라 더는 평지가 아니다(경사가 레벨에 따라 커진다)" % level

    return {"rows": rows, "cols": cols, "levels_used": level + 1, "levels": [int(level)], "fixed_level": int(level), "num_envs": int(len(levels)), "assignment_sha256": assignment_sha256(levels, types), "tiles": tiles, "flat_kind": flat_kind, "flat_note": note}


def apply_to(raw, level=None) -> dict:
    """raw = env.unwrapped (env 4 개). 생성기 cfg 에서 이름을 읽어 고르고 terrain 에 덮어쓴다. 호출한 쪽이 이어서 env.reset() 한다."""
    from foothold_s2.eval import fixed_terrain

    gen = raw.scene.terrain.cfg.terrain_generator
    props = {name: float(sub.proportion) for name, sub in gen.sub_terrains.items()}
    rows, cols = int(raw.scene.terrain.terrain_origins.shape[0]), int(raw.scene.terrain.terrain_origins.shape[1])

    if cols != gen.num_cols:
        raise RuntimeError(f"terrain_origins 열 수 {cols} 가 생성기 num_cols {gen.num_cols} 와 다르다")
    level = LEVEL if level is None else fixed_terrain.check_level(level, rows)
    levels, types, flat_kind, tiles = pick(column_names(props, cols), int(raw.scene.terrain.terrain_levels.shape[0]), level)
    fixed_terrain.apply_assignment(raw, levels, types, rows, cols, level + 1, fixed_level=level)

    return record(levels, types, flat_kind, tiles, rows, cols, level)
