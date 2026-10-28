"""항별 보상을 «움직이는 env-step» 과 «멈춘 env-step» 으로 나눠 기록한다 (SONNET-X11, lead 요청, astra X12 · X13 H4). 기록만 하고 학습에는 쓰지 않는다. Kit 없이 시험된다.

시점: Isaac Lab 의 step 은 «보상 계산 -> 종료 env reset -> 명령 재표집 -> 관측» 순이다. 보상과 같은 시점(reset 전)의 값을 맞추려고 `attach(env)` 가
reward_manager.compute 를 한 번 감싸서 보상 직후에 보상 · 명령 · 몸 속도 · reset 표시를 같이 찍는다(명령은 그 step 에 실제로 쓰인 값).
분류는 env-step 마다 한다(명령을 창에서 먼저 평균하지 않는다):
- 직진 명령(vx > 0): 몸 vx 의 지수평균 >= 0.05 m/s 이면 움직임, 아니면 멈춤 (평가의 정지 판정 `v < 0.05` 와 같은 문턱)
- 제자리 회전 명령(vx = 0, wz != 0): 부호를 지킨 추종 비율 ema(wz) * sign(cmd wz) / |cmd wz| >= 0.1 이면 움직임, 아니면 멈춤
- 명령이 전부 0 이면 어느 집단에도 넣지 않고 비율만 센다
지수평균(시간 상수 약 10 스텝 = 0.2 s)은 한 step 의 속도 잡음이 분류를 흔들지 않게 하는 것이고, env 가 reset 되었거나 명령이 바뀐(차이 > 1e-6) 다음 step 에는 현재 값으로 다시 시작한다.
집계는 env-step 합과 개수로 한다: 항별 평균은 집단에 속한 모든 env-step 의 평균, 비율은 전체 env-step 대비.
필요한 속성이 없으면 조용히 끄지 않고 summary 가 {"unavailable": 이유} 를 돌려준다.
"""

from __future__ import annotations

import torch

NAMED = ("track_lin_vel", "track_ang_vel", "action_rate", "action_smoothness")
MOVE_VX = 0.05
MOVE_YAW_FOLLOW = 0.1
EMA_ALPHA = 0.1
EPS = 1e-6
BASIC_GROUPS = ("forward", "walkturn", "spin", "stand", "reverse", "side")
BASIC_STAND_LINEAR_MPS = 0.05
BASIC_STAND_YAW_RADPS = 0.1


def basic_group_ids(cmd: torch.Tensor) -> torch.Tensor:
    """보상과 같은 시점의 명령을 기본 보행 여섯 묶음으로 나눈다."""
    vx, vy, wz = cmd[..., 0], cmd[..., 1], cmd[..., 2]
    x, y, z = vx.abs() > EPS, vy.abs() > EPS, wz.abs() > EPS
    out = torch.full(vx.shape, -1, dtype=torch.long, device=cmd.device)
    out[(vx > EPS) & ~y & ~z] = 0
    out[(vx > EPS) & ~y & z] = 1
    out[~x & ~y & z] = 2
    out[~x & ~y & ~z] = 3
    out[(vx < -EPS) & ~y & ~z] = 4
    out[~x & y & ~z] = 5
    return out


class StepClassifier:
    """env-step 분류 상태(지수평균). `classify` 는 한 step 의 (속도, 명령, 직전 reset 표시)를 받아 (moving, stalled, nomove) 불리언 (N,) 셋을 돌려준다."""

    def __init__(self):
        self.ema_vx = None
        self.ema_wz = None
        self.prev_cmd = None
        self.prev_reset = None

    def classify(self, vx: torch.Tensor, wz: torch.Tensor, cmd: torch.Tensor, reset_prev: torch.Tensor | None = None,
                 vy: torch.Tensor | None = None, basic_mode: bool = False):
        fresh = torch.zeros_like(vx, dtype=torch.bool) if reset_prev is None else reset_prev.bool()

        if basic_mode and vy is None:
            raise ValueError("basic reward split needs body vy")
        if self.ema_vx is None:
            self.ema_vx, self.ema_wz = vx.clone(), wz.clone()
            if basic_mode:
                self.ema_vy = vy.clone()
        else:
            changed = (cmd - self.prev_cmd).abs().amax(dim=-1) > EPS
            fresh = fresh | changed
            self.ema_vx = torch.where(fresh, vx, (1 - EMA_ALPHA) * self.ema_vx + EMA_ALPHA * vx)
            self.ema_wz = torch.where(fresh, wz, (1 - EMA_ALPHA) * self.ema_wz + EMA_ALPHA * wz)
            if basic_mode:
                self.ema_vy = torch.where(fresh, vy, (1 - EMA_ALPHA) * self.ema_vy + EMA_ALPHA * vy)

        self.prev_cmd = cmd.clone()
        if basic_mode:
            group = basic_group_ids(cmd)
            yaw_follow = self.ema_wz * torch.sign(cmd[:, 2]) / cmd[:, 2].abs().clamp_min(EPS)
            moving = ((group == 0) & (self.ema_vx >= MOVE_VX))
            moving |= (group == 1) & (self.ema_vx >= MOVE_VX) & (yaw_follow >= MOVE_YAW_FOLLOW)
            moving |= (group == 4) & (-self.ema_vx >= MOVE_VX)
            moving |= (group == 5) & (self.ema_vy * torch.sign(cmd[:, 1]) >= MOVE_VX)
            moving |= (group == 2) & (yaw_follow >= MOVE_YAW_FOLLOW)
            active = group != 3
            return moving, active & ~moving, ~active
        straight = cmd[:, 0].abs() > EPS
        spin = (~straight) & (cmd[:, 2].abs() > EPS)
        nomove = ~(straight | spin)
        follow = self.ema_wz * torch.sign(cmd[:, 2]) / cmd[:, 2].abs().clamp_min(EPS)
        moving = (straight & (self.ema_vx >= MOVE_VX)) | (spin & (follow >= MOVE_YAW_FOLLOW))
        stalled = (straight | spin) & ~moving

        return moving, stalled, nomove


def split_stats(rew: torch.Tensor, names: list[str], vx: torch.Tensor, wz: torch.Tensor, cmd: torch.Tensor, reset: torch.Tensor | None = None,
                clf: StepClassifier | None = None, reset_before: torch.Tensor | None = None, clipped: torch.Tensor | None = None,
                vy: torch.Tensor | None = None, basic_mode: bool = False) -> dict:
    """rew (T, N, K) 가중치 곱한 항별 값 · vx (T, N) · wz (T, N) · cmd (T, N, 3) · reset (T, N) 그 step 에 종료된 env. 전부 보상과 같은 시점(reset 전)."""
    T, N, _ = rew.shape
    clf = clf or StepClassifier()
    sums = {"moving": torch.zeros(rew.shape[2]), "stalled": torch.zeros(rew.shape[2])}
    counts = {"moving": 0, "stalled": 0, "nomove": 0}
    clip_counts = {"moving": 0, "stalled": 0}                 # only_positive_rewards 로 합이 0 으로 잘린 env-step (EX-13 만 의미가 있다)
    group_counts = torch.zeros(len(BASIC_GROUPS), dtype=torch.long, device=rew.device) if basic_mode else None
    group_rewards = torch.zeros(len(BASIC_GROUPS), rew.shape[2], device=rew.device) if basic_mode else None
    group_following = torch.zeros(len(BASIC_GROUPS), dtype=torch.long, device=rew.device) if basic_mode else None
    group_invalid = torch.zeros((), dtype=torch.long, device=rew.device) if basic_mode else None

    for t in range(T):
        prev = (reset_before if t == 0 else reset[t - 1]) if reset is not None else None
        moving, stalled, nomove = clf.classify(vx[t], wz[t], cmd[t], prev,
                                                vy=vy[t] if vy is not None else None, basic_mode=basic_mode)
        if basic_mode:
            groups = basic_group_ids(cmd[t])
            # Stand is successful when both planar and yaw motion are small.
            # It remains a no-move command in the legacy aggregate counts.
            stand_following = (clf.ema_vx.square() + clf.ema_vy.square() < BASIC_STAND_LINEAR_MPS ** 2)
            stand_following &= clf.ema_wz.abs() < BASIC_STAND_YAW_RADPS
            following = moving | ((groups == 3) & stand_following)
            group_invalid += (groups < 0).sum()
            for i in range(len(BASIC_GROUPS)):
                mask = groups == i
                group_counts[i] += mask.sum()
                group_rewards[i] += rew[t][mask].sum(0).float()
                group_following[i] += (mask & following).sum()
        counts["moving"] += int(moving.sum())
        counts["stalled"] += int(stalled.sum())
        counts["nomove"] += int(nomove.sum())
        sums["moving"] += rew[t][moving].sum(0).float().cpu()
        sums["stalled"] += rew[t][stalled].sum(0).float().cpu()

        if clipped is not None:
            clip_counts["moving"] += int((clipped[t] & moving).sum())
            clip_counts["stalled"] += int((clipped[t] & stalled).sum())

    total = T * N
    idx = {n: i for i, n in enumerate(names)}
    out = {"frac_moving": counts["moving"] / total, "frac_stalled": counts["stalled"] / total, "frac_no_move_command": counts["nomove"] / total,
           "env_steps": total, "reset_env_steps": int(reset.sum()) if reset is not None else None,
           "only_positive_clipped_frac": (float(clipped.float().mean()) if clipped is not None else None)}      # 항별 값은 자르기 전 값이다

    for label in ("moving", "stalled"):
        if counts[label] == 0:
            out[label] = None
            continue

        mean = sums[label] / counts[label]
        g = {n: (float(mean[idx[n]]) if n in idx else None) for n in NAMED}
        g["other_penalty_sum"] = float(sum(float(mean[i]) for n, i in idx.items() if n not in NAMED))
        g["total"] = float(mean.sum())
        g["env_steps"] = counts[label]
        g["only_positive_clipped_frac"] = (clip_counts[label] / counts[label]) if clipped is not None else None
        out[label] = g

    if basic_mode:
        if int(group_invalid):
            raise ValueError("basic reward split saw a command outside the six groups")
        group_counts = group_counts.cpu()
        group_rewards = group_rewards.cpu()
        group_following = group_following.cpu()
        out["by_basic_group"] = {
            name: {"env_steps": int(group_counts[i]), "fraction": int(group_counts[i]) / total,
                   "following_env_steps": int(group_following[i]),
                   "reward_terms_mean": {key: float(group_rewards[i, j] / group_counts[i])
                                         for j, key in enumerate(names)} if group_counts[i] else None}
            for i, name in enumerate(BASIC_GROUPS)
        }

    return out


class RewardSplit:
    """reward_manager.compute 를 감싸 보상 직후(reset 전)의 보상 · 명령 · 속도 · reset 표시를 step 마다 모은다."""

    def __init__(self, basic_mode: bool = False):
        self.basic_mode = basic_mode
        self.rew, self.vx, self.vy, self.wz, self.cmd, self.reset, self.clipped = [], [], [], [], [], [], []
        self.names = None
        self.error = None
        self.attached = False
        self._snap = None
        self.clf = StepClassifier()                     # 창이 바뀌어도 지수평균 상태를 이어 간다
        self.last_reset = None

    def attach(self, env) -> None:
        try:
            rm = env.reward_manager
            robot = env.scene["robot"]
            term = env.command_manager.get_term("base_velocity")
            orig = rm.compute
            self.names = list(rm.active_terms)
        except Exception as exc:                                              # noqa: BLE001
            self.error = f"속성 없음: {exc!r}"

            return

        def wrapped(*a, **k):
            out = orig(*a, **k)
            self._snap = (rm._step_reward.detach().clone(), robot.data.root_lin_vel_b[:, 0].detach().clone(),
                          robot.data.root_lin_vel_b[:, 1].detach().clone() if self.basic_mode else None,
                          robot.data.root_ang_vel_b[:, 2].detach().clone(),
                          term.vel_command_b[:, :3].detach().clone(), env.reset_buf.detach().clone(),
                          (env.reward_neg_clipped.detach().clone() if hasattr(env, "reward_neg_clipped") else None))

            return out

        rm.compute = wrapped
        self.attached = True

    def add(self) -> None:
        """env.step 이 끝난 뒤 부른다. 이번 step 의 찍은 값을 쌓는다. 안 찍혔으면 오류로 기록한다(조용히 건너뛰지 않는다)."""
        if self.error is not None:
            return

        if not self.attached or self._snap is None:
            self.error = "보상 직후 값이 찍히지 않았다 (attach 안 됨 또는 compute 호출 없음)"

            return

        r, vx, vy, wz, cmd, rst, clipped = self._snap
        self._snap = None
        self.rew.append(r)
        self.vx.append(vx)
        if vy is not None:
            self.vy.append(vy)
        self.wz.append(wz)
        self.cmd.append(cmd)
        self.reset.append(rst)
        self.clipped.append(clipped)

    def summary(self):
        if self.error is not None:
            err = self.error
            self.reset_window()

            return {"unavailable": err}

        if not self.rew:
            return {"unavailable": "기록된 step 이 없다"}

        out = split_stats(torch.stack(self.rew), self.names, torch.stack(self.vx), torch.stack(self.wz), torch.stack(self.cmd), torch.stack(self.reset),
                          clf=self.clf, reset_before=self.last_reset,
                          clipped=(torch.stack(self.clipped) if self.clipped and self.clipped[0] is not None else None),
                          vy=torch.stack(self.vy) if self.basic_mode else None, basic_mode=self.basic_mode)
        self.last_reset = self.reset[-1].clone()
        self.reset_window()

        return out

    def reset_window(self):
        self.rew, self.vx, self.vy, self.wz, self.cmd, self.reset, self.clipped = [], [], [], [], [], [], []
