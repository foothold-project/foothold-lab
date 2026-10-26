"""평가용 고정 지형 칸 (SONNET-X25): reset 뒤 terrain_levels / terrain_types 를 정해진 배열로 덮어써 task 가 달라도 같은 칸에서 평가한다.

배열은 env 번호만으로 정해진다(난수 없음): 종류 = i % cols, 레벨 = (i // cols) % LEVELS_USED. 같은 env 수 · 같은 지형 격자(rows x cols)면 task 가 달라도 같은 배열 -> 같은 해시.
rows 가 LEVELS_USED 보다 작거나 cols 가 다르면 거절한다(다른 격자를 같은 칸이라 부르지 않는다).
"""

from __future__ import annotations

import hashlib

import numpy as np

LEVELS_USED = 3                       # 학습 시작 레벨 상한(max_init 2)과 같은 범위의 낮은 행만 쓴다


def check_level(level, rows: int):
    """--fixed-level N: 0 <= N < rows 인 정수만. None 이면 기본(레벨 0~2 를 번갈아)."""
    if level is None:
        return None
    if isinstance(level, bool) or not isinstance(level, (int, np.integer)) or not 0 <= int(level) < rows:
        raise ValueError(f"고정 레벨은 0..{rows - 1} 정수여야 한다: {level!r}")

    return int(level)


def fixed_assignment(num_envs: int, rows: int, cols: int, level=None):
    """기본(level=None): 종류 = i % cols, 레벨 = (i // cols) % LEVELS_USED. level=N: 같은 종류 배열(i % cols)에 모든 env 의 레벨만 N 으로(열 종류는 그대로)."""
    if rows < LEVELS_USED:
        raise ValueError(f"지형 격자 행 수 {rows} 가 고정 칸에 쓰는 레벨 수 {LEVELS_USED} 보다 작다")
    if cols < 1 or num_envs < 1:
        raise ValueError("cols 와 num_envs 는 양수")
    level = check_level(level, rows)
    i = np.arange(num_envs)

    if level is not None:
        return np.full(num_envs, level, dtype=i.dtype), i % cols

    return (i // cols) % LEVELS_USED, i % cols


SPARSE_SET = "sparse50"                 # --terrain-set: 50 열 S2 생성기(연속 7 종 + 듬성 5 종 + flat)로 바꾸고 듬성 5 종 열(23..47)만 고정 칸으로 쓴다


def sparse_column_ids(names) -> list:
    """50 열 이름 배열(columns.column_types)에서 듬성 5 종(flat 제외) 열 번호. 50 열이 아니거나 듬성 열이 없으면 거절."""
    from foothold_s2.runners.map_switch import SPARSE_NAMES

    ids = [j for j, n in enumerate(names) if n in SPARSE_NAMES]

    if not ids:
        raise ValueError("듬성 지형 열이 없다")

    return ids


def sparse_assignment(num_envs: int, names, rows: int, level: int):
    """듬성 칸 고정 배열: 레벨은 모두 level, 종류는 듬성 열 목록을 env 번호 순으로 되풀이(i % 듬성 열 수). 난수 없음."""
    level = check_level(level, rows)
    ids = np.asarray(sparse_column_ids(names), dtype=np.int64)
    i = np.arange(num_envs)

    return np.full(num_envs, level, dtype=i.dtype), ids[i % len(ids)]


def apply_sparse(raw, level) -> dict:
    """raw = env.unwrapped (50 열 생성기). 듬성 5 종 열만 고정 칸으로 덮어쓴다. 기록에 종류 이름 · 열 · 레벨(tiles)을 남긴다."""
    from foothold_s2.terrains import columns

    terrain = raw.scene.terrain
    rows, cols = int(terrain.terrain_origins.shape[0]), int(terrain.terrain_origins.shape[1])
    gen = terrain.cfg.terrain_generator
    names = columns.column_types({k: float(v.proportion) for k, v in gen.sub_terrains.items()}, int(gen.num_cols))

    if cols != int(gen.num_cols) or cols != columns.FULL_COLS:
        raise RuntimeError(f"듬성 고정 칸은 {columns.FULL_COLS} 열 생성기만 받는다(받은 열 수 {cols})")
    levels, types = sparse_assignment(int(terrain.terrain_levels.shape[0]), names, rows, level)
    rec = apply_assignment(raw, levels, types, rows, cols, int(level) + 1, fixed_level=int(level))
    rec["terrain_set"] = SPARSE_SET
    rec["tiles"] = [{"env": i, "kind": names[int(types[i])], "level": int(levels[i]), "col": int(types[i])} for i in range(len(types))]

    return rec


def assignment_sha256(levels, types) -> str:
    return hashlib.sha256(np.asarray(levels, dtype=np.int64).tobytes() + np.asarray(types, dtype=np.int64).tobytes()).hexdigest()


def apply(raw, level=None) -> dict:
    """raw = env.unwrapped. terrain 의 레벨 · 종류 · env 원점을 고정 배열로 바꾼다. 호출한 쪽이 이어서 env.reset() 한다(curriculum 이 꺼져 있어야 레벨이 안 바뀐다)."""
    import torch

    terrain = raw.scene.terrain
    rows, cols = int(terrain.terrain_origins.shape[0]), int(terrain.terrain_origins.shape[1])
    levels, types = fixed_assignment(int(terrain.terrain_levels.shape[0]), rows, cols, level)

    return apply_assignment(raw, levels, types, rows, cols, LEVELS_USED if level is None else int(level) + 1, fixed_level=level)


def apply_assignment(raw, levels, types, rows: int, cols: int, levels_used: int, fixed_level=None) -> dict:
    """주어진 (레벨, 종류) 배열을 terrain 에 덮어쓴다. apply 와 probe 의 종류 이름 배치(probe_tiles)가 같이 쓴다."""
    import torch

    terrain = raw.scene.terrain
    lv = torch.as_tensor(levels, dtype=terrain.terrain_levels.dtype, device=terrain.terrain_levels.device)
    ty = torch.as_tensor(types, dtype=terrain.terrain_types.dtype, device=terrain.terrain_types.device)
    terrain.terrain_levels.copy_(lv)
    terrain.terrain_types.copy_(ty)
    terrain.env_origins.copy_(terrain.terrain_origins[lv, ty])

    if not torch.equal(raw.scene.env_origins, terrain.env_origins):
        raise RuntimeError("scene.env_origins 가 terrain.env_origins 와 다르다")

    return {"rows": rows, "cols": cols, "levels_used": levels_used, "levels": sorted({int(v) for v in np.asarray(levels).tolist()}),
            "fixed_level": None if fixed_level is None else int(fixed_level), "num_envs": int(len(levels)), "assignment_sha256": assignment_sha256(levels, types)}


def describe(record: dict) -> str:
    """결과 표 머리에 찍는 한 줄: 무엇을 고정했고 무엇을 대표하지 않는지. record 는 json 의 fixed_terrain."""
    if record.get("tiles"):                                          # 종류 이름으로 고른 배치(probe): 식 문구 대신 실제 이름 · 레벨 · env 수
        groups: dict = {}
        for t in record["tiles"]:
            groups.setdefault((t["kind"], t["level"]), []).append(t["col"])
        body = " + ".join(f"{k} 레벨 {lv} x {len(cs)} env(열 {','.join(str(c) for c in dict.fromkeys(cs))})" for (k, lv), cs in groups.items())

        return f"고정 칸 · {body} · {record['num_envs']} env · 학습 분포(레벨 0~{record['rows'] - 1}) 대표 아님 · 배열 SHA {record['assignment_sha256'][:12]}"
    levels, types = fixed_assignment(record["num_envs"], record["rows"], record["cols"], record.get("fixed_level"))

    if record.get("fixed_level") is not None:
        return (f"고정 칸 · 레벨 {record['fixed_level']} 만({record['num_envs']} env) · 종류 = env 번호 % {record['cols']} 열 · "
                f"학습 분포(레벨 0~{record['rows'] - 1}) 대표 아님 · 배열 SHA {record['assignment_sha256'][:12]}")
    counts = "/".join(str(int((levels == lv).sum())) for lv in range(record["levels_used"]))

    return (f"고정 칸 · 레벨 0~{record['levels_used'] - 1} 만({record['num_envs']} env 배치 {counts}) · 종류 = env 번호 % {record['cols']} 열 · "
            f"학습 분포(레벨 0~{record['rows'] - 1}) 대표 아님 · 배열 SHA {record['assignment_sha256'][:12]}")
