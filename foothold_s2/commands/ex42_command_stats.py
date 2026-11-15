"""EX-42: what the command sampler actually handed out during one update. No Kit imports.

The plan row says which ranges, shares and turn overlay a stage should draw; this records what was drawn, from the
commands the term installed (`record_command_sample`). `take()` gives one train_extra row and starts the next update:

    {"samples": n, "slots": {slot: {"n", "share", "vx": [min, max], "vy_abs": [min, max], "wz_abs": [min, max]}},
     "turn_overlay": {"moving": n, "turned": n, "fraction": turned / moving},   # reverse / side / diagonal slots
     "out_of_range": n}                                                          # samples the stage's own check refuses

A record only: it never changes a command and never stops the training.
"""
from __future__ import annotations

from types import SimpleNamespace

import torch

from foothold_s2.commands.mixed_core import EX39_SLOTS

MOVING = ("reverse", "side_left", "side_right", "diag_fwd_left", "diag_fwd_right", "diag_back_left", "diag_back_right")


class CommandStats:
    def __init__(self, stage):
        self.plan = SimpleNamespace(stages=[stage])
        self._device = None

    def _reset(self, device) -> None:
        slots = len(EX39_SLOTS)
        self._device = device
        self._n = torch.zeros(slots, dtype=torch.long, device=device)
        self._low = torch.full((slots, 3), float("inf"), device=device)
        self._high = torch.full((slots, 3), float("-inf"), device=device)
        self._moving_ids = torch.tensor([EX39_SLOTS.index(name) for name in MOVING], device=device)
        self._counts = torch.zeros(3, dtype=torch.long, device=device)          # moving, turned, out of range

    def add(self, commands, slots, heading) -> None:
        if len(slots) == 0:
            return
        if self._device is None:
            self._reset(commands.device)
        from foothold_s2.curriculum.continuous import command_bad
        command, slot = commands.detach().float(), slots.detach().long()
        values = torch.stack((command[:, 0], command[:, 1].abs(), command[:, 2].abs()), dim=1)
        index = slot[:, None].expand(-1, 3)
        self._n += torch.bincount(slot, minlength=len(EX39_SLOTS))
        self._low.scatter_reduce_(0, index, values, "amin")
        self._high.scatter_reduce_(0, index, values, "amax")
        moving = torch.isin(slot, self._moving_ids)
        bad = command_bad(command, slot, heading.detach().bool(), torch.zeros_like(slot), self.plan)
        self._counts += torch.stack((moving.sum(), (moving & (values[:, 2] > 1e-6)).sum(), bad.sum()))

    def take(self) -> dict | None:
        if self._device is None or int(self._n.sum()) == 0:
            return None
        n, low, high = self._n.cpu().tolist(), self._low.cpu().tolist(), self._high.cpu().tolist()
        moving, turned, bad = self._counts.cpu().tolist()
        total = sum(n)
        out = {"samples": total,
               "slots": {name: {"n": n[i], "share": n[i] / total, "vx": [low[i][0], high[i][0]],
                                "vy_abs": [low[i][1], high[i][1]], "wz_abs": [low[i][2], high[i][2]]}
                         for i, name in enumerate(EX39_SLOTS) if n[i]},
               "turn_overlay": {"moving": moving, "turned": turned, "fraction": turned / moving if moving else None},
               "out_of_range": bad}
        self._reset(self._device)
        return out
