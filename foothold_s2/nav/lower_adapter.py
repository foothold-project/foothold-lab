"""얼린 하위 정책을 부르는 접점 (PLAN-HIPAN-V2 §4.1 · M1).

새 추론 경로를 만들지 않는다: `ex41_eval_loader.load_checkpoint_for_eval` -> `adapters.load_s2_runner` -> `adapters.S2Policy`
호출만 한다. Isaac Lab 이 필요한 import 는 모두 함수 안 (Kit 없이 이 파일을 import 하고 가짜 runner 로 시험할 수 있다).
fail-closed: actor 입력 98 아님 · `ex41_pose_commands` 표지 없음 · 저장본 sha 가 등록값과 다름 · 스텝 dt 가 0.02 아님.
하위 actor 입력 98 = o45 + est51 + pose2. est51 (models/start_perception.py:39 · :355) = [z 0:16, v 16:19, zf 19:35, zb 35:51].
"""
from __future__ import annotations

import hashlib
from pathlib import Path

ACTOR_INPUTS = 98
DT = 0.02
POSE_STAGES = ("E6a", "E6b")       # 자세 단계를 통과한 저장본의 단계 id (가정 · verifier 와 꼴 맞춤)
MAP_MODES = ("eval_gt", "eval_pred")


def file_sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pose_active_from_receipt(receipt, checkpoint_sha256: str) -> bool:
    """자세 스위치는 「저장본이 E6a 를 통과했다」 는 영수증 (단계 id · 저장본 sha) 으로만 켠다."""
    if not isinstance(receipt, dict):
        return False
    return (receipt.get("stage_id") in POSE_STAGES
            and receipt.get("checkpoint_sha256") == checkpoint_sha256
            and receipt.get("passed") is True)


def prepare(env_cfg, checkpoint, expected_sha256: str):
    """gym.make 전에 부른다. sha 검사 + 평가 경계의 cfg 준비. 돌려주는 값: (checkpoint_state, preparation)."""
    digest = file_sha256(checkpoint)
    if not isinstance(expected_sha256, str) or digest != expected_sha256.lower():
        raise ValueError(f"lower checkpoint sha256 {digest[:8]} differs from the registered value")
    from foothold_s2.eval import ex41_eval_loader

    state, prep = ex41_eval_loader.load_checkpoint_for_eval(env_cfg, checkpoint)
    if state.get("ex41_pose_commands") is not True or prep.get("actor_input_width") != ACTOR_INPUTS:
        raise ValueError("lower policy must be the 98-input ex41_pose_commands checkpoint")
    return state, dict(prep, checkpoint_sha256=digest)


class LowerPolicy:
    def __init__(self, policy, n, checkpoint_sha256, pose_active, dt=DT):
        self._policy = policy
        self.n = n
        self.checkpoint_sha256 = checkpoint_sha256
        self.pose_active = bool(pose_active)
        self.dt = dt

    @classmethod
    def load(cls, checkpoint, env, device, map_mode, *, agent_cfg, checkpoint_state, checkpoint_sha256,
             pose_receipt=None):
        """env 는 gym.make 가 끝난 RslRlVecEnvWrapper. checkpoint_state 는 `prepare` 가 준 것."""
        if map_mode not in MAP_MODES:
            raise ValueError(f"map_mode must be one of {MAP_MODES} (never inherited from force_gt)")
        raw = env.unwrapped
        dt = float(raw.step_dt)
        if abs(dt - DT) > 1e-9:
            raise ValueError(f"lower step dt {dt} is not {DT}")
        from foothold_s2.eval import adapters

        runner, _ = adapters.load_s2_runner(env, agent_cfg, checkpoint, device, checkpoint_state=checkpoint_state)
        policy = adapters.S2Policy(runner, env.num_envs, z_mode="mean", act_mode="mean", map_mode=map_mode)
        return cls(policy, env.num_envs, checkpoint_sha256,
                   pose_active_from_receipt(pose_receipt, checkpoint_sha256), dt)

    @property
    def capabilities(self) -> dict:
        return {"actor_inputs": ACTOR_INPUTS, "pose_commands": True, "pose_active": self.pose_active,
                "dt": self.dt, "map_mode": self._policy.map_mode, "checkpoint_sha256": self.checkpoint_sha256}

    def act(self, obs):
        """관절 행동 (n, 12). gradient 없음 (S2Policy 안쪽이 torch.inference_mode)."""
        return self._policy(obs)

    def reset(self, dones) -> None:
        self._policy.reset(dones)


def apply_command(term, cmd5, stand, pose_active: bool) -> None:
    """명령 항 (`base_velocity`) 에 적용 명령을 쓴다. 평가기와 같은 방식 (eval/ex42_d44_eval.py): vel_command_b[:, :3] · stand 덮어쓰기,
    heading · 깃발 모드가 켜져 있으면 거절. 자세 칸은 `pose_active` 가 아니면 0 이어야 한다."""
    import torch

    cmd = torch.as_tensor(cmd5, dtype=term.vel_command_b.dtype, device=term.vel_command_b.device)
    if cmd.ndim != 2 or cmd.shape[1] != 5 or not bool(torch.isfinite(cmd).all()):
        raise ValueError("command must be a finite (n, 5) tensor")
    if not pose_active and bool((cmd[:, 3:] != 0).any()):
        raise ValueError("pose columns must be zero while the pose switch is off")
    if bool(term.heading.any()) or bool(term.is_flag_env.any()):
        raise RuntimeError("heading or flag mode is on: commands would be rewritten")
    term.vel_command_b[:, :3] = cmd[:, :3]
    term.stand.copy_(torch.as_tensor(stand, dtype=torch.bool, device=term.stand.device))


def tracking_error(applied_cmd3, body_vel_b, yaw_rate):
    """추종 오차 (n, 3) = 실제 [vx, vy, wz] - 적용 명령. 상위 보상 r6 · 명령 반응 지도 (G1) 의 재료."""
    import numpy as np

    actual = np.concatenate([np.asarray(body_vel_b, dtype=np.float64)[:, :2],
                             np.asarray(yaw_rate, dtype=np.float64).reshape(-1, 1)], axis=1)
    return actual - np.asarray(applied_cmd3, dtype=np.float64)[:, :3]
