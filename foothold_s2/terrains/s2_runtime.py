"""S2 학습 중 지형 조회 (flags · 집단 태그) 와 reset 재배정. torch. Isaac 객체는 duck typing 으로만 건드린다(`terrain.terrain_levels` 등)."""

import numpy as np
import torch

from foothold_s2.commands import mixed_core as mc
from foothold_s2.terrains import progression
from foothold_s2.terrains.s2_layout import Layout


class S2Tables:
    """(줄, 열) 로 색인되는 텐서. 이어진 칸의 깃발은 NaN (직선으로 대체)."""

    def __init__(self, side_table, layout: Layout, num_rows, device, flag_count=4):
        self.layout = layout
        self.flags = torch.full((num_rows, layout.num_cols, flag_count, 2), float("nan"), device=device)
        self.group_col = layout.group_by_col

        sample = next(iter(side_table.by_cell.values()))
        h, w = sample["inner"].shape
        self.inner = torch.zeros(num_rows, layout.num_cols, h, w, dtype=torch.bool, device=device)
        self.outer = torch.zeros_like(self.inner)

        for (r, c), v in side_table.by_cell.items():
            self.flags[r, c] = torch.as_tensor(v["flags_world"], dtype=torch.float32, device=device)
            self.inner[r, c] = torch.as_tensor(v["inner"], device=device)
            self.outer[r, c] = torch.as_tensor(v["outer"], device=device)

    def force_flag(self, terrain, env_ids):
        """듬성한 칸 (틈 포함) 의 env 는 깃발 방식 (15 §1: 듬성한 발판 지형군의 명령은 깃발)."""
        grp = self.group_col[terrain.terrain_types[env_ids].cpu().numpy()]

        return torch.as_tensor(grp != "continuous", device=env_ids.device)

    def flag_provider(self, terrain, env_ids, count):
        lvl = terrain.terrain_levels[env_ids]
        typ = terrain.terrain_types[env_ids]
        out = self.flags[lvl, typ][:, :count]
        straight = torch.stack([mc.straight_flag_line(o, count) for o in terrain.env_origins[env_ids, :2].cpu()]
                               ).to(out.device)
        missing = torch.isnan(out).any(dim=(1, 2))

        return torch.where(missing[:, None, None], straight, out)


def reassign(terrain, tables: S2Tables, env_ids, iteration, rng, **p_kw):
    """reset 때 전환 대상(듬성한, 틈 제외) env 의 열을 p_advance 로 다시 뽑고 원점을 갱신한다 (15 §5 · §8.1 ①).

    레벨은 이미 승급 · 강등으로 바뀐 뒤여야 한다. 반환: 바뀐 열 번호를 쓴 env 수.
    """
    ids = torch.as_tensor(env_ids, device=terrain.terrain_types.device, dtype=torch.long)
    groups = tables.group_col[terrain.terrain_types[ids].cpu().numpy()]
    new = progression.reassign_columns(rng, groups, tables.layout.easy_cols, tables.layout.hard_cols,
                                       iteration, **p_kw)
    changed = new >= 0

    if changed.any():
        sel = ids[torch.as_tensor(changed, device=ids.device)]
        terrain.terrain_types[sel] = torch.as_tensor(new[changed], device=ids.device, dtype=terrain.terrain_types.dtype)
        terrain.env_origins[ids] = terrain.terrain_origins[terrain.terrain_levels[ids], terrain.terrain_types[ids]]

    return int(np.count_nonzero(changed))
