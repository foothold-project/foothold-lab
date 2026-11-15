"""Atomic observation and sensor packet contract. Actual Isaac source accessor is still unverified."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import torch

from s2_env_adapter_17v import AdapterFault, yaw_from_quat_wxyz


def raw_sha(pos: torch.Tensor, hits: torch.Tensor) -> str:
    if not bool(torch.isfinite(pos).all()):
        raise AdapterFault("sensor position nonfinite")
    h = hashlib.sha256()
    for tensor in (pos, hits):
        value = tensor.detach().cpu().contiguous()
        h.update(str(tuple(value.shape)).encode())
        h.update(value.numpy().tobytes())
    return h.hexdigest()


@dataclass(frozen=True)
class AtomicPacket:
    obs: dict
    sensor: object
    root_pos_w: torch.Tensor
    root_quat_w: torch.Tensor
    episode_ids: torch.Tensor
    sim_step: int
    sensor_step: int
    sensor_generation: int
    sensor_raw_sha256: str
    packet_id: str
    source_receipt: dict

    def validate(self, *, previous: "AtomicPacket | None", previous_done: torch.Tensor | None):
        if type(self.sim_step) is not int or type(self.sensor_step) is not int or self.sim_step < 0:
            raise AdapterFault("packet step invalid")
        if self.sensor_step != self.sim_step:
            raise AdapterFault("sensor not updated for observation step")
        if type(self.sensor_generation) is not int or self.sensor_generation < 0:
            raise AdapterFault("sensor generation invalid")
        if not self.packet_id or not isinstance(self.packet_id, str):
            raise AdapterFault("packet id missing")
        if self.source_receipt != {"generation": self.sensor_generation, "step": self.sensor_step,
                                    "raw_sha256": self.sensor_raw_sha256}:
            raise AdapterFault("sensor source receipt mismatched")
        if raw_sha(self.sensor.data.pos_w, self.sensor.data.ray_hits_w) != self.sensor_raw_sha256:
            raise AdapterFault("sensor raw bytes differ from source receipt")
        if self.root_pos_w.shape != self.sensor.data.pos_w.shape or self.root_quat_w.shape != (self.root_pos_w.shape[0], 4):
            raise AdapterFault("pose shape mismatch")
        if not bool(torch.isfinite(self.root_pos_w).all()):
            raise AdapterFault("root pose nonfinite")
        yaw = yaw_from_quat_wxyz(self.root_quat_w)
        if self.episode_ids.shape != (self.root_pos_w.shape[0],) or self.episode_ids.dtype not in (torch.int32, torch.int64):
            raise AdapterFault("episode ids invalid")
        if previous is not None:
            if self.sim_step <= previous.sim_step or self.sensor_generation <= previous.sensor_generation or self.packet_id == previous.packet_id:
                raise AdapterFault("stale sensor packet")
            if previous_done is None or previous_done.shape != self.episode_ids.shape:
                raise AdapterFault("previous termination mask missing")
            if bool((self.episode_ids[previous_done] <= previous.episode_ids[previous_done]).any()):
                raise AdapterFault("reset episode id did not advance")
            if bool((self.episode_ids[~previous_done] != previous.episode_ids[~previous_done]).any()):
                raise AdapterFault("non-reset episode id changed")
        return yaw
