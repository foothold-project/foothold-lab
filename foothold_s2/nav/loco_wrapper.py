"""얼린 EX-42 하위 정책을 속도 명령 (vx, vy, wz) 으로 부르는 래퍼.

하위 actor 입력 98 = o45 (정책 관측) + est51 (지각 추정) + pose2 (EX-41 자세 명령, 0).
o45 의 앞 순서: base_ang_vel 3, projected_gravity 3, velocity_commands 3 (6:9), 관절 36.
이 래퍼는 («체크포인트 sha 고정 · 입력 98 검사 · 명령 칸 덮어쓰기 · actor 평균 행동») 만 맡는다.
est51 을 만드는 지각 쪽과 env 는 부르는 쪽 몫이다. torch 는 체크포인트를 읽을 때만 쓴다.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

ACTOR_INPUT = 98
ACTION_DIM = 12
CMD_SLICE = slice(6, 9)
POSE_SLICE = slice(96, 98)
HIDDEN = (512, 256, 128)


def file_sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _elu(x):
    return np.where(x > 0, x, np.expm1(np.minimum(x, 0)))


class FrozenLocoPolicy:
    def __init__(self, layers, command_limits, sha256):
        if len(layers) != len(HIDDEN) + 1:
            raise ValueError("actor must have 4 linear layers")
        dims = [ACTOR_INPUT, *HIDDEN, ACTION_DIM]
        for (w, b), din, dout in zip(layers, dims[:-1], dims[1:]):
            if w.shape != (dout, din) or b.shape != (dout,):
                raise ValueError(f"actor layer shape {w.shape} differs from ({dout}, {din})")
            if not (np.isfinite(w).all() and np.isfinite(b).all()):
                raise ValueError("actor weights must be finite")
        lim = np.asarray(command_limits, dtype=np.float64)
        if lim.shape != (3,) or not (np.isfinite(lim).all() and (lim > 0).all()):
            raise ValueError("command_limits must be three positive finite |max| values (vx, vy, wz)")
        self.layers = [(w.astype(np.float32), b.astype(np.float32)) for w, b in layers]
        self.limits = lim.astype(np.float32)
        self.sha256 = sha256

    @classmethod
    def from_checkpoint(cls, path, expected_sha256: str, command_limits):
        path = Path(path)
        if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
            raise ValueError("expected_sha256 must be a 64 hex digest")
        digest = file_sha256(path)
        if digest != expected_sha256.lower():
            raise ValueError(f"checkpoint sha256 {digest[:8]} differs from pinned {expected_sha256[:8]}")
        import torch

        state = torch.load(path, map_location="cpu", weights_only=False)
        model = state.get("model_state_dict") if isinstance(state, dict) else None
        if not isinstance(model, dict):
            raise ValueError("checkpoint has no model_state_dict")
        if state.get("ex41_pose_commands") is not True:
            raise ValueError("checkpoint must carry ex41_pose_commands (98 input)")
        first = model.get("actor.0.weight")
        if first is None or tuple(first.shape) != (HIDDEN[0], ACTOR_INPUT):
            raise ValueError(f"actor input must be {ACTOR_INPUT}")
        norm = state.get("normalization_state") or {}
        if norm.get("actor_obs_enabled"):
            raise ValueError("actor observation normalization is not supported by this wrapper")
        layers = [(model[f"actor.{i}.weight"].numpy(), model[f"actor.{i}.bias"].numpy()) for i in (0, 2, 4, 6)]
        return cls(layers, command_limits, digest)

    def clip_command(self, cmd):
        c = np.asarray(cmd, dtype=np.float32)
        if c.shape != (3,) or not np.isfinite(c).all():
            raise ValueError("command must be 3 finite values (vx, vy, wz)")
        return np.clip(c, -self.limits, self.limits)

    def act(self, obs, cmd=None):
        """obs (98,) 또는 (N, 98). cmd (3,) 또는 (N, 3) 를 주면 명령 칸 6:9 를 그 값 (한계 안으로 자름) 으로 바꾼다."""
        x = np.asarray(obs, dtype=np.float32)
        if x.shape[-1] != ACTOR_INPUT or x.ndim not in (1, 2):
            raise ValueError(f"actor input must have last dimension {ACTOR_INPUT}, got {x.shape}")
        if not np.isfinite(x).all():
            raise ValueError("observation must be finite")
        if np.count_nonzero(x[..., POSE_SLICE]):
            raise ValueError("pose command columns must be zero for this frozen policy")
        x = x.copy()
        if cmd is not None:
            c = np.asarray(cmd, dtype=np.float32)
            if c.shape[-1] != 3 or not np.isfinite(c).all() or c.shape[:-1] != x.shape[:-1]:
                raise ValueError("cmd must be (..., 3) finite and match obs batch")
            x[..., CMD_SLICE] = np.clip(c, -self.limits, self.limits)
        for i, (w, b) in enumerate(self.layers):
            x = x @ w.T + b
            if i < len(self.layers) - 1:
                x = _elu(x)
        return x
