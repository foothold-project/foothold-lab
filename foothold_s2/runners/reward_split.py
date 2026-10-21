"""항별 보상을 «움직이는 env» 와 «멈춘 env» 로 나눠 기록한다 (SONNET-X11, lead 요청, astra X12). 기록만 하고 학습에는 쓰지 않는다. Kit 없이 시험된다.

한 update(rollout 24 스텝) 동안 env 마다 평균을 내어 나눈다:
- 직진 명령(|명령 vx| > 0): 실제 몸 vx 평균 >= 0.05 m/s 이면 움직임, 아니면 멈춤 (평가의 정지 판정 `v < 0.05` 와 같다)
- 제자리 회전 명령(vx = 0, wz != 0): 부호를 지킨 추종 비율 mean(wz) * sign(cmd wz) / |cmd wz| >= 0.1 이면 움직임, 아니면 멈춤
  (|요 속도| 절댓값 문턱 0.12 대신 부호 있는 평균 비율을 써서 잡음 흔들림이 움직임으로 세어지지 않게 한다)
- 명령이 전부 0 인 env 는 어느 집단에도 넣지 않고 비율만 기록한다
창이 24 스텝(0.48 s)이라 한 창 안의 명령 재표집 · 리셋은 평균에 섞인다(기록용 근사).
항목: track_lin_vel · track_ang_vel · action_rate · action_smoothness · 나머지 벌점 합 · 전체 합 (모두 보상 관리자의 가중치 곱한 초당 값, 집단 안 env · 스텝 평균), 세 집단의 env 비율.
"""

from __future__ import annotations

import torch

NAMED = ("track_lin_vel", "track_ang_vel", "action_rate", "action_smoothness")
MOVE_VX = 0.05
MOVE_YAW_FOLLOW = 0.1
EPS = 1e-6


def split_stats(rew: torch.Tensor, names: list[str], vx: torch.Tensor, wz: torch.Tensor, cmd: torch.Tensor) -> dict:
    """rew (T, N, K) 가중치 곱한 항별 값 · vx (T, N) · wz (T, N) · cmd (T, N, 3)."""
    c = cmd.mean(0)
    straight = c[:, 0].abs() > EPS
    spin = (~straight) & (c[:, 2].abs() > EPS)
    nomove_cmd = ~(straight | spin)
    follow = wz.mean(0) * torch.sign(c[:, 2]) / c[:, 2].abs().clamp_min(EPS)
    moving = (straight & (vx.mean(0) >= MOVE_VX)) | (spin & (follow >= MOVE_YAW_FOLLOW))
    stalled = (straight | spin) & ~moving
    per_env = rew.mean(0)                                       # (N, K) 스텝 평균
    idx = {n: i for i, n in enumerate(names)}
    n_env = rew.shape[1]
    out = {"frac_moving": float(moving.float().sum() / n_env), "frac_stalled": float(stalled.float().sum() / n_env),
           "frac_no_move_command": float(nomove_cmd.float().sum() / n_env)}

    for label, mask in (("moving", moving), ("stalled", stalled)):
        if int(mask.sum()) == 0:
            out[label] = None
            continue

        sel = per_env[mask].mean(0)                             # (K,) 집단 env 평균
        g = {n: (float(sel[idx[n]]) if n in idx else None) for n in NAMED}
        g["other_penalty_sum"] = float(sum(float(sel[i]) for n, i in idx.items() if n not in NAMED))
        g["total"] = float(sel.sum())
        g["n_envs"] = int(mask.sum())
        out[label] = g

    return out


class RewardSplit:
    """스텝마다 env(ManagerBasedRLEnv)에서 항별 보상 · 몸 속도 · 명령을 모아 update 끝에 split_stats 로 집계한다. 필요한 속성이 없으면 비활성(summary 는 None)."""

    def __init__(self):
        self.rew, self.vx, self.wz, self.cmd = [], [], [], []
        self.names = None
        self.enabled = True

    def add(self, env) -> None:
        if not self.enabled:
            return

        try:
            rm = env.reward_manager
            self.names = list(rm.active_terms)
            rew = rm._step_reward.detach().clone()
            data = env.scene["robot"].data
            vx, wz = data.root_lin_vel_b[:, 0].detach().clone(), data.root_ang_vel_b[:, 2].detach().clone()
            cmd = env.command_manager.get_term("base_velocity").vel_command_b[:, :3].detach().clone()
        except Exception:                                                      # noqa: BLE001
            self.enabled = False

            return

        self.rew.append(rew)
        self.vx.append(vx)
        self.wz.append(wz)
        self.cmd.append(cmd)

    def summary(self):
        if not self.enabled or not self.rew:
            self.reset()

            return None

        out = split_stats(torch.stack(self.rew), self.names, torch.stack(self.vx), torch.stack(self.wz), torch.stack(self.cmd))
        self.reset()

        return out

    def reset(self):
        self.rew, self.vx, self.wz, self.cmd = [], [], [], []
