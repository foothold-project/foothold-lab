"""평가용 고정 지형 칸 (SONNET-X25): reset 뒤 terrain_levels / terrain_types 를 정해진 배열로 덮어써 task 가 달라도 같은 칸에서 평가한다.

배열은 env 번호만으로 정해진다(난수 없음): 종류 = i % cols, 레벨 = (i // cols) % LEVELS_USED. 같은 env 수 · 같은 지형 격자(rows x cols)면 task 가 달라도 같은 배열 -> 같은 해시.
rows 가 LEVELS_USED 보다 작거나 cols 가 다르면 거절한다(다른 격자를 같은 칸이라 부르지 않는다).
"""

from __future__ import annotations

import hashlib

import numpy as np

LEVELS_USED = 3                       # 학습 시작 레벨 상한(max_init 2)과 같은 범위의 낮은 행만 쓴다


def fixed_assignment(num_envs: int, rows: int, cols: int):
    if rows < LEVELS_USED:
        raise ValueError(f"지형 격자 행 수 {rows} 가 고정 칸에 쓰는 레벨 수 {LEVELS_USED} 보다 작다")
    if cols < 1 or num_envs < 1:
        raise ValueError("cols 와 num_envs 는 양수")
    i = np.arange(num_envs)

    return (i // cols) % LEVELS_USED, i % cols


def assignment_sha256(levels, types) -> str:
    return hashlib.sha256(np.asarray(levels, dtype=np.int64).tobytes() + np.asarray(types, dtype=np.int64).tobytes()).hexdigest()


def apply(raw) -> dict:
    """raw = env.unwrapped. terrain 의 레벨 · 종류 · env 원점을 고정 배열로 바꾼다. 호출한 쪽이 이어서 env.reset() 한다(curriculum 이 꺼져 있어야 레벨이 안 바뀐다)."""
    import torch

    terrain = raw.scene.terrain
    rows, cols = int(terrain.terrain_origins.shape[0]), int(terrain.terrain_origins.shape[1])
    levels, types = fixed_assignment(int(terrain.terrain_levels.shape[0]), rows, cols)
    lv = torch.as_tensor(levels, dtype=terrain.terrain_levels.dtype, device=terrain.terrain_levels.device)
    ty = torch.as_tensor(types, dtype=terrain.terrain_types.dtype, device=terrain.terrain_types.device)
    terrain.terrain_levels.copy_(lv)
    terrain.terrain_types.copy_(ty)
    terrain.env_origins.copy_(terrain.terrain_origins[lv, ty])

    if not torch.equal(raw.scene.env_origins, terrain.env_origins):
        raise RuntimeError("scene.env_origins 가 terrain.env_origins 와 다르다")

    return {"rows": rows, "cols": cols, "levels_used": LEVELS_USED, "num_envs": int(len(levels)), "assignment_sha256": assignment_sha256(levels, types)}
