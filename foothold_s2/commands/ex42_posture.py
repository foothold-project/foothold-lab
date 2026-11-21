"""EX-42 하위 자세 명령 (몸 높이 · roll) 을 배우는 최소 경로 (lead 2026-11-21 19:34 · 팀장 18:51 「하위가 자세를 배워 오고 상위는 원문 그대로」).
기본 꺼짐: EX42_POSTURE=1 일 때만 켜진다. 꺼짐이면 env 설정 · 관측 (자세 칸 0) · 보상 · runner 확인이 r3 와 같은 바이트다.

켜짐이면:
  - 명령: env 마다 [h, roll] 을 원문 범위에서 고르게 뽑는다. h ∈ [0.1, 0.4] m (지면 기준 몸 높이) · roll ∈ [-1.0, 1.0] rad (2604.26504.txt:635).
    속도 명령이 바뀌거나 새 에피소드면 다시 뽑는다 (heading 항과 같은 방식 · 명령 항 코드는 고치지 않는다).
  - 관측: actor 96:98 · critic 664:666 의 자세 칸 = [h - H0, roll] (D93 순서: 높이 변화 · roll). H0 = 공칭 몸 높이 (가정 0.31 m · EX42_POSTURE_H0).
  - 보상 (원문 Table III · 2604.26504.txt:597-605 · 627): 높이 w3 0.2 · exp(-|hc - hB| / 0.0025) · roll w4 0.2 · exp(-|θc - θ_roll| / 0.05).
    hB = 몸통 z - 높이 스캐너가 맞힌 바닥 z 평균 (스캐너가 없으면 env 원점 z).
  - runner: 자세 칸이 0 이 아니어도 받는다 (범위 · 유한성만 확인).
범위 · 가중은 env 값으로 바꿀 수 있다 (EX42_POSTURE_H_RANGE "lo,hi" · EX42_POSTURE_ROLL_RANGE · EX42_POSTURE_HEIGHT_W · EX42_POSTURE_ROLL_W).
CG C8a~C8c 의 단계 (높이 좁게 → 넓게 → roll) 를 따르려면 범위 env 값을 단계마다 바꿔 새 판을 띄운다 (실시간 칸은 둘째 단계).
No Kit import at module level.
"""
from __future__ import annotations

import math
import os

import torch

ENV_SWITCH = "EX42_POSTURE"
PAPER_H = (0.1, 0.4)                 # 2604.26504.txt:635
PAPER_ROLL = (-1.0, 1.0)
PAPER_W = (0.2, 0.2)                 # 2604.26504.txt:627 w3L · w4L
H0_DEFAULT = 0.31                    # 공칭 몸 높이 (가정 · CG C8a 의 공칭 근처 U[0.28, 0.34] 의 가운데)
HEIGHT_TERM, ROLL_TERM = "ex42_posture_height", "ex42_posture_roll"
STATE = "_ex42_posture_state"


def enabled() -> bool:
    value = os.environ.get(ENV_SWITCH, "")
    if value not in ("", "0", "1"):
        raise ValueError(f"{ENV_SWITCH} must be 0 or 1 (got {value!r})")
    extra = [k for k in ("EX42_POSTURE_H_RANGE", "EX42_POSTURE_ROLL_RANGE", "EX42_POSTURE_H0", "EX42_POSTURE_HEIGHT_W", "EX42_POSTURE_ROLL_W")
             if os.environ.get(k, "") != ""]
    if value != "1" and extra:
        raise ValueError(f"{', '.join(extra)} set but {ENV_SWITCH} is not 1")
    return value == "1"


def _pair(name, default):
    raw = os.environ.get(name, "")
    if raw == "":
        return tuple(map(float, default))
    try:
        lo, hi = (float(v) for v in raw.split(","))
    except ValueError:
        raise ValueError(f"{name} must be 'lo,hi' (got {raw!r})") from None
    if not (math.isfinite(lo) and math.isfinite(hi) and lo <= hi):
        raise ValueError(f"{name} must be finite with lo <= hi (got {raw!r})")
    return lo, hi


def _num(name, default, lo=0.0):
    raw = os.environ.get(name, "")
    try:
        v = float(raw) if raw != "" else float(default)
    except ValueError:
        raise ValueError(f"{name} must be a number (got {raw!r})") from None
    if not math.isfinite(v) or v < lo:
        raise ValueError(f"{name} must be finite and >= {lo} (got {raw!r})")
    return v


def settings() -> dict:
    h, roll = _pair("EX42_POSTURE_H_RANGE", PAPER_H), _pair("EX42_POSTURE_ROLL_RANGE", PAPER_ROLL)
    if not (PAPER_H[0] <= h[0] and h[1] <= PAPER_H[1] and PAPER_ROLL[0] <= roll[0] and roll[1] <= PAPER_ROLL[1]):
        raise ValueError(f"posture ranges must stay inside the paper ranges h {PAPER_H} roll {PAPER_ROLL} (got {h} {roll})")
    return {"h": h, "roll": roll, "h0": _num("EX42_POSTURE_H0", H0_DEFAULT, 0.05),
            "height_w": _num("EX42_POSTURE_HEIGHT_W", PAPER_W[0]), "roll_w": _num("EX42_POSTURE_ROLL_W", PAPER_W[1])}


class PostureState:
    def __init__(self, n, device, cfg, seed=0):
        self.cfg = cfg
        self.target = torch.zeros((n, 2), device=device)        # [h (m), roll (rad)]
        self.target[:, 0] = cfg["h0"]
        self.command = torch.full((n, 3), float("nan"), device=device)
        self.gen = torch.Generator(device="cpu").manual_seed(int(seed) + 4243)

    def update(self, command, new_episode):
        changed = ~(command == self.command).all(-1) | new_episode.bool()
        k = int(changed.sum())
        if k:
            u = torch.rand((k, 2), generator=self.gen).to(self.target.device)
            (hl, hh), (rl, rh) = self.cfg["h"], self.cfg["roll"]
            self.target[changed] = torch.stack([hl + (hh - hl) * u[:, 0], rl + (rh - rl) * u[:, 1]], 1)
            self.command[changed] = command[changed]
        return changed


def _state(env):
    st = getattr(env, STATE, None)
    if st is None:
        st = PostureState(env.num_envs, env.device, settings())
        setattr(env, STATE, st)
    return st


def posture_command_obs(env, command_name: str = "base_velocity"):
    """관측 칸 (N, 2) = [h - H0, roll]. 매 스텝 불리며 명령이 바뀐 env · 새 에피소드 env 의 목표를 다시 뽑는다."""
    st = _state(env)
    command = env.command_manager.get_command(command_name)[:, :3]
    st.update(command, env.episode_length_buf <= 1)
    out = st.target.clone()
    out[:, 0] -= st.cfg["h0"]
    return out


def body_roll(quat_wxyz):
    w, x, y, z = quat_wxyz.unbind(-1)
    return torch.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))


def body_height(env):
    root_z = env.scene["robot"].data.root_pos_w[:, 2]
    try:
        hits = env.scene["height_scanner"].data.ray_hits_w[..., 2]
    except (KeyError, AttributeError):
        return root_z - env.scene.env_origins[:, 2]
    hits = torch.where(torch.isfinite(hits), hits, torch.full_like(hits, float("nan")))
    ground = torch.nanmean(hits, dim=1)
    return root_z - torch.where(torch.isfinite(ground), ground, env.scene.env_origins[:, 2])


def height_tracking(env):
    st = _state(env)
    return torch.exp(-(st.target[:, 0] - body_height(env)).abs() / 0.0025)


def roll_tracking(env):
    st = _state(env)
    return torch.exp(-(st.target[:, 1] - body_roll(env.scene["robot"].data.root_quat_w)).abs() / 0.05)


def register_observation(obs_group) -> bool:
    """apply_ex41_pose_observation 이 만든 PoseCommandGroup 의 칸 함수를 바꾼다 (스위치가 켜졌을 때만)."""
    if not enabled():
        return False
    obs_group.pose_cmd.func = posture_command_obs
    obs_group.pose_cmd.params = {"command_name": "base_velocity"}
    return True


def register_rewards(env_cfg, term_cfg_class=None) -> bool:
    if not enabled() or hasattr(env_cfg.rewards, HEIGHT_TERM):
        return False
    cfg = settings()
    if term_cfg_class is None:
        from isaaclab.managers import RewardTermCfg as term_cfg_class
    setattr(env_cfg.rewards, HEIGHT_TERM, term_cfg_class(func=height_tracking, weight=cfg["height_w"], params={}))
    setattr(env_cfg.rewards, ROLL_TERM, term_cfg_class(func=roll_tracking, weight=cfg["roll_w"], params={}))
    print(f"EX42_POSTURE where=start h={list(cfg['h'])} roll={list(cfg['roll'])} h0={cfg['h0']} height_w={cfg['height_w']} roll_w={cfg['roll_w']}", flush=True)
    return True


def check_runner_pose(pose) -> None:
    """runner 의 자세 칸 확인 (스위치 켜짐): 유한 · 범위 안. 꺼짐은 runner 가 옛 0 확인을 그대로 한다."""
    cfg = settings()
    if not torch.isfinite(pose).all():
        raise ValueError("EX-42 posture pose_cmd must be finite")
    dh, roll = pose[:, 0], pose[:, 1]
    eps = 1e-5
    if (dh < cfg["h"][0] - cfg["h0"] - eps).any() or (dh > cfg["h"][1] - cfg["h0"] + eps).any() \
            or (roll < cfg["roll"][0] - eps).any() or (roll > cfg["roll"][1] + eps).any():
        raise ValueError("EX-42 posture pose_cmd is outside the posture ranges")
