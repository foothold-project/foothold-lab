"""Opt-in within-episode map outages and delayed depth restoration.

The episode-level map choice remains the baseline.  An eligible map-on row
waits, loses map attention for a sampled interval, then regains map attention
while fresh depth is held for a sampled number of depth ticks.  Neither GRU
nor proprioceptive/depth history is reset at a transition.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os

import torch


ENV_KEY = "EX42_MAP_TRANSITION_JSON"


@dataclass(frozen=True)
class Config:
    wait_s: tuple[float, float]
    off_s: tuple[float, float]
    restore_depth_ticks: tuple[int, int]
    seed: int

    def receipt(self) -> dict:
        return {"wait_s": list(self.wait_s), "off_s": list(self.off_s),
                "restore_depth_ticks": list(self.restore_depth_ticks), "seed": self.seed}


def read_config(environ=None) -> Config | None:
    raw = (os.environ if environ is None else environ).get(ENV_KEY)
    if raw is None:
        return None
    data = json.loads(raw)
    if not isinstance(data, dict) or set(data) != {"wait_s", "off_s", "restore_depth_ticks", "seed"}:
        raise ValueError("map transition needs wait_s, off_s, restore_depth_ticks, seed")

    def pair(key, *, integral=False):
        value = data[key]
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError(f"map transition {key} must be a two-element list")
        if integral and any(type(x) is not int for x in value):
            raise ValueError(f"map transition {key} must contain integers")
        out = tuple(int(x) if integral else float(x) for x in value)
        if not all(math.isfinite(x) for x in out) or out[1] < out[0]:
            raise ValueError(f"map transition {key} range is invalid")
        return out

    wait = pair("wait_s")
    off = pair("off_s")
    delay = pair("restore_depth_ticks", integral=True)
    if wait[0] <= 0 or off[0] < 0.1 or off[1] > 10.0 or delay[0] < 0 or delay[1] > 20:
        raise ValueError("map transition durations are outside the supported range")
    if type(data["seed"]) is not int or not 0 <= data["seed"] < 2**63:
        raise ValueError("map transition seed must be a nonnegative integer")
    return Config(wait, off, delay, data["seed"])


class MapTransition:
    """Per-env three phase clock.  `step` is called before each policy input."""

    def __init__(self, cfg: Config, n: int, device, dt: float, depth_tick: int):
        if not math.isfinite(dt) or dt <= 0 or depth_tick < 1:
            raise ValueError("map transition needs positive dt and depth tick")
        self.cfg, self.n, self.device, self.depth_tick = cfg, n, device, depth_tick
        self.gen = torch.Generator(device=device).manual_seed(cfg.seed)
        self.wait_range = tuple(max(1, math.ceil(v / dt)) for v in cfg.wait_s)
        self.off_range = tuple(max(1, math.ceil(v / dt)) for v in cfg.off_s)
        self.phase = torch.zeros(n, dtype=torch.long, device=device)  # 0 wait, 1 off, 2 depth recovery
        self.wait_left = torch.zeros(n, dtype=torch.long, device=device)
        self.off_left = torch.zeros(n, dtype=torch.long, device=device)
        self.depth_left = torch.zeros(n, dtype=torch.long, device=device)
        self.base_off = torch.zeros(n, dtype=torch.bool, device=device)
        self.eligible = torch.ones(n, dtype=torch.bool, device=device)
        self.off_starts = self.on_restores = self.held_depth_ticks = 0

    def _draw(self, bounds: tuple[int, int], n: int) -> torch.Tensor:
        return torch.randint(bounds[0], bounds[1] + 1, (n,), device=self.device, generator=self.gen)

    def reset(self, rows: torch.Tensor, base_off: torch.Tensor, eligible: torch.Tensor | None = None) -> None:
        rows = rows.bool()
        if rows.shape != (self.n,) or base_off.shape != (self.n,):
            raise ValueError("map transition reset needs N-row masks")
        if eligible is not None and eligible.shape != (self.n,):
            raise ValueError("map transition eligibility needs N rows")
        self.base_off[rows] = base_off.bool()[rows]
        if eligible is not None:
            self.eligible[rows] = eligible.bool()[rows]
        self.phase[rows] = 0
        self.wait_left[rows] = self._draw(self.wait_range, int(rows.sum()))
        self.off_left[rows] = 0
        self.depth_left[rows] = 0

    def step(self, depth_tick_now: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        if depth_tick_now.shape != (self.n,):
            raise ValueError("map transition needs N depth-tick flags")
        active = ~self.base_off & self.eligible
        waiting = (self.phase == 0) & active
        self.wait_left[waiting] -= 1
        start = waiting & (self.wait_left == 0)
        if bool(start.any()):
            self.phase[start] = 1
            self.off_left[start] = self._draw(self.off_range, int(start.sum())) - 1
            self.off_starts += int(start.sum())

        old_off = (self.phase == 1) & ~start
        self.off_left[old_off] -= 1
        restored = old_off & (self.off_left < 0)
        if bool(restored.any()):
            self.phase[restored] = 2
            self.depth_left[restored] = self._draw(self.cfg.restore_depth_ticks, int(restored.sum()))
            self.on_restores += int(restored.sum())

        off = self.base_off | (self.phase == 1)
        hold = (self.phase == 2) & (self.depth_left > 0) & depth_tick_now.bool()
        self.depth_left[hold] -= 1
        self.held_depth_ticks += int(hold.sum())
        finished = (self.phase == 2) & (self.depth_left == 0)
        if bool(finished.any()):
            self.phase[finished] = 0
            self.wait_left[finished] = self._draw(self.wait_range, int(finished.sum()))
        return off, hold

    def take_counts(self) -> dict[str, int]:
        counts = {"off_starts": self.off_starts, "on_restores": self.on_restores,
                  "held_depth_ticks": self.held_depth_ticks}
        self.off_starts = self.on_restores = self.held_depth_ticks = 0
        return counts

    def state_dict(self) -> dict:
        return {"config": self.cfg.receipt(), "generator_state": self.gen.get_state()}

    def load_state_dict(self, value: dict) -> None:
        if not isinstance(value, dict) or value.get("config") != self.cfg.receipt() or value.get("generator_state") is None:
            raise ValueError("map transition checkpoint config or RNG state differs")
        self.gen.set_state(value["generator_state"].cpu())
