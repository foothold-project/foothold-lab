"""boundary_log recorder (CG:380 / CG:381): between two save boundaries, how many episodes really ended per
(column, level band, direction group, assigned map mode). The EX-42 stage runtime feeds it each step; at every save
boundary it writes `learned_cells_<it>.json` (the raw material of the `learned_cells` exit item) and starts a new window.

Rules kept from the contract (planner CONTRACT-E2-LEARNED-CELLS-EXCHANGE-1111 section 3):
  - the level, column and command slot are the ones the episode had while it ran: the snapshot is taken before
    `env.step` (the step itself resets the finished envs onto their next level);
  - the assigned mode is `map_off` at the done (the new draw happens after), `map_off` or `map_on_adaptive`;
  - an episode counts once (per-env serial) and only when it started inside the window (an episode that began before
    the last boundary, or before this process resumed, is left out);
  - the recorder never stops training: a failure is reported and the file is simply absent (the exit item then HOLDs).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

FORMAT = "foothold-ex42-learned-cells/1"
LEVEL_BANDS = ((0, 2), (3, 5), (6, 9))
MODES = ("map_on_adaptive", "map_off")
GROUPS = ("forward", "reverse", "side_left", "side_right", "turn_left", "turn_right", "stand", "flag")
SLOT_GROUP = {"forward": "forward", "diag_fwd_left": "forward", "diag_fwd_right": "forward",
              "reverse": "reverse", "diag_back_left": "reverse", "diag_back_right": "reverse",
              "side_left": "side_left", "side_right": "side_right",
              "walk_left": "turn_left", "spin_left": "turn_left",
              "walk_right": "turn_right", "spin_right": "turn_right", "stand": "stand"}


def band_of_level(level: int) -> int:
    for index, (lo, hi) in enumerate(LEVEL_BANDS):
        if lo <= level <= hi:
            return index
    raise ValueError(f"EX-42 learned_cells level {level} is outside every band")


def group_index_for_slots(slot_names) -> list[int]:
    """Group index per command slot id (the slot order of the command term)."""
    return [GROUPS.index(SLOT_GROUP[name]) for name in slot_names]


class LearnedCellRecorder:
    def __init__(self, num_envs: int, num_columns: int, slot_names, *, stage_id: str, plan_sha256: str,
                 device="cpu", start_iteration: int = 0, rank: int = 0, world_size: int = 1):
        import torch

        self.torch = torch
        self.num_columns = int(num_columns)
        self.slot_group = torch.as_tensor(group_index_for_slots(slot_names), dtype=torch.long, device=device)
        self.flag_group = GROUPS.index("flag")
        self.band_of = torch.as_tensor([band_of_level(level) for level in range(LEVEL_BANDS[-1][1] + 1)],
                                       dtype=torch.long, device=device)
        self.stage_id, self.plan_sha256 = stage_id, plan_sha256
        self.rank, self.world_size = int(rank), int(world_size)
        shape = (self.num_columns, len(LEVEL_BANDS), len(GROUPS), len(MODES))
        self.counts = torch.zeros(shape, dtype=torch.long, device=device)
        self.window_from = int(start_iteration)
        self.episode_start = torch.full((num_envs,), int(start_iteration), dtype=torch.long, device=device)
        self.episode_steps = torch.zeros(num_envs, dtype=torch.long, device=device)
        self.serial = torch.zeros(num_envs, dtype=torch.long, device=device)
        self.excluded_started_before_window = 0
        self.duplicate_skipped = 0
        self._pre = None

    def pre_step(self, levels, types, slots, is_flag) -> None:
        """Snapshot before env.step: where each env stands and what command slot it follows."""
        self._pre = (levels.detach().clone().long(), types.detach().clone().long(),
                     slots.detach().clone().long(), is_flag.detach().clone().bool())

    def post_step(self, done, map_off, iteration: int) -> int:
        """Count the episodes that ended in this step. `map_off` is the value used for the episode (before the redraw)."""
        torch = self.torch
        if self._pre is None:
            raise RuntimeError("EX-42 learned_cells post_step has no matching pre_step")
        levels, types, slots, is_flag = self._pre
        self._pre = None
        self.episode_steps += 1
        ids = (done > 0).nonzero(as_tuple=False).flatten()
        if not ids.numel():
            return 0
        fresh = self.episode_steps[ids] >= 1                                    # an episode that lasted a step
        self.duplicate_skipped += int((~fresh).sum())
        inside = self.episode_start[ids] >= self.window_from
        self.excluded_started_before_window += int((fresh & ~inside).sum())
        keep = ids[fresh & inside]
        if keep.numel():
            band = self.band_of[levels[keep].clamp(0, self.band_of.numel() - 1)]
            group = torch.where(is_flag[keep], torch.full_like(band, self.flag_group), self.slot_group[slots[keep]])
            mode = map_off[keep].bool().long()
            flat = ((types[keep] * len(LEVEL_BANDS) + band) * len(GROUPS) + group) * len(MODES) + mode
            self.counts.view(-1).index_add_(0, flat, torch.ones_like(flat))
        self.serial[ids] += 1
        self.episode_start[ids] = int(iteration)
        self.episode_steps[ids] = 0
        return int(keep.numel())

    def snapshot(self, iteration: int, column_table=None) -> dict[str, Any]:
        nz = self.counts.nonzero(as_tuple=False)
        rows = [[int(c), LEVEL_BANDS[int(b)][0], GROUPS[int(g)], MODES[int(m)], int(self.counts[c, b, g, m])]
                for c, b, g, m in nz.tolist()]
        body = {"format": FORMAT, "stage_id": self.stage_id, "plan_sha256": self.plan_sha256,
                "window": {"from_it": self.window_from, "to_it": int(iteration)},
                "rank": self.rank, "world_size": self.world_size,
                "axes": {"level_bands": [list(b) for b in LEVEL_BANDS], "groups": list(GROUPS), "modes": list(MODES),
                         "columns": self.num_columns},
                "columns": [dict(row) for row in column_table] if column_table else None,
                "cells": rows, "total": int(self.counts.sum()),
                "excluded_started_before_window": self.excluded_started_before_window,
                "duplicate_skipped": self.duplicate_skipped, "episodes_counted_once": True}
        body["sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return body

    def close_window(self, iteration: int) -> None:
        self.counts.zero_()
        self.window_from = int(iteration)
        self.excluded_started_before_window = 0
        self.duplicate_skipped = 0

    def write(self, directory: str | Path, iteration: int, column_table=None) -> Path:
        body = self.snapshot(iteration, column_table)
        name = (f"learned_cells_{iteration}.json" if self.world_size <= 1
                else f"learned_cells_{iteration}_rank{self.rank}.json")
        path = Path(directory) / name
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(body, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
        self.close_window(iteration)
        return path


def fold_cells(documents: list[dict[str, Any]]) -> dict[tuple, int]:
    """Sum the ranks' files into {(column, band_first_level, group, mode): n}. Mixed windows or plans are refused."""
    first = documents[0]
    total: dict[tuple, int] = {}
    for doc in documents:
        if (doc.get("format") != FORMAT or doc["window"] != first["window"] or doc["plan_sha256"] != first["plan_sha256"]
                or doc["stage_id"] != first["stage_id"]):
            raise ValueError("EX-42 learned_cells files differ in window, plan or stage")
        for column, band, group, mode, n in doc["cells"]:
            total[(column, band, group, mode)] = total.get((column, band, group, mode), 0) + n
    return total
