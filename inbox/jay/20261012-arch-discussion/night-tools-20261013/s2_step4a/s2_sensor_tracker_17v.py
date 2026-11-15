"""Version-bound RayCaster update observer. No Isaac import; wrapping private method needs live review."""
from __future__ import annotations

from types import SimpleNamespace

import torch

from s2_env_adapter_17v import AdapterFault
from s2_packet_17v import raw_sha


class SensorUpdateTracker:
    def __init__(self, sensor, *, num_envs: int, step_getter):
        if type(num_envs) is not int or num_envs <= 0 or not callable(step_getter):
            raise ValueError("tracker arguments")
        original = getattr(sensor, "_update_buffers_impl", None)
        if not callable(original):
            raise AdapterFault("RayCaster update hook missing")
        self.sensor, self.original, self.step_getter = sensor, original, step_getter
        self.num_envs = num_envs
        self.generations = [0]*num_envs
        self.last_steps = [-1]*num_envs
        self.installed = True
        def tracked(env_ids):
            result = original(env_ids)
            ids = [int(x) for x in env_ids]
            step = int(step_getter())
            for i in ids:
                if i < 0 or i >= num_envs:
                    raise AdapterFault("sensor update env id out of range")
                self.generations[i] += 1
                self.last_steps[i] = step
            return result
        sensor._update_buffers_impl = tracked

    def snapshot(self):
        d = self.sensor.data  # RayCaster.data triggers _update_outdated_buffers, see ray_caster.py:110-114.
        step = int(self.step_getter())
        if not self.installed or any(x != step for x in self.last_steps) or min(self.generations) <= 0:
            raise AdapterFault("not every RayCaster env updated for this control step")
        pos = d.pos_w.detach().clone()
        hits = d.ray_hits_w.detach().clone()
        if pos.shape != (self.num_envs, 3) or hits.shape != (self.num_envs, 187, 3):
            raise AdapterFault("RayCaster snapshot shape mismatch")
        digest = raw_sha(pos, hits)
        generation = min(self.generations)
        receipt = {"generation": generation, "step": step, "raw_sha256": digest}
        frozen_sensor = SimpleNamespace(cfg=self.sensor.cfg, data=SimpleNamespace(pos_w=pos, ray_hits_w=hits))
        return frozen_sensor, receipt

    def source_receipt(self):
        _, receipt = self.snapshot()
        return receipt

    def detach(self):
        if self.installed:
            self.sensor._update_buffers_impl = self.original
            self.installed = False
