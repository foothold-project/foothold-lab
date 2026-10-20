"""지각 재생 버퍼 (12 §6.1 · §8). PPO rollout 버퍼와 따로 둔다.

수집은 torch.inference_mode() 안이라(rsl_rl 3.1.2 on_policy_runner.py 101 행) 그때 만든 손실로는 backward 할 수 없다.
그래서 지각 입력을 여기에 모아 두고, PPO update 뒤 gradient 를 켠 순환 재생으로 L_TR + L_IE 를 다시 계산한다.

보관 목록(12 §6.1): 깊이 2 프레임(float16) · 몸 관측 o_t · 이력(10 x 45, 가정(rl): 재생에서 rollout 앞쪽 이력을 다시 만들
수 없어서 스텝마다 저장) · 정답 지도 H^b · H^f · 속도 v · 다음 관측 o_{t+1} · done · 깊이 틱 · 첫 스텝 · 두 GRU 시작 상태 ·
AdaSmpl 플래그. 길이 = rollout 과 같은 T 스텝.
"""

from __future__ import annotations

import torch

from foothold_s2.models.start_perception import (
    DEPTH_FRAMES,
    DEPTH_HW,
    FOOT_CELLS,
    HIST_LEN,
    MAP_X,
    MAP_Y,
    OBS_DIM,
)


class PerceptionReplay:
    def __init__(self, num_envs: int, num_steps: int, device, depth_dtype=torch.float16) -> None:
        self.N, self.T, self.device = num_envs, num_steps, device
        z = lambda *s, dt=torch.float32: torch.zeros(*s, dtype=dt, device=device)  # noqa: E731
        self.data = {
            "depth2": z(num_steps, num_envs, DEPTH_FRAMES, DEPTH_HW, DEPTH_HW, dt=depth_dtype),
            "obs": z(num_steps, num_envs, OBS_DIM),
            "hist": z(num_steps, num_envs, HIST_LEN, OBS_DIM),
            "gt_map": z(num_steps, num_envs, MAP_X, MAP_Y),
            "gt_feet": z(num_steps, num_envs, FOOT_CELLS),
            "base_vel": z(num_steps, num_envs, 3),
            "next_obs": z(num_steps, num_envs, OBS_DIM),
            "done": z(num_steps, num_envs, dt=torch.bool),
            "tick": z(num_steps, num_envs, dt=torch.bool),
            "first": z(num_steps, num_envs, dt=torch.bool),
            "use_gt": z(num_steps, num_envs, dt=torch.bool),
        }
        self.h_prop0 = z(num_envs, 128)
        self.h_terr0 = z(num_envs, 128)
        self.step = 0

    def start(self, h_prop: torch.Tensor, h_terr: torch.Tensor) -> None:
        """rollout 시작 때 두 GRU 상태를 따로 저장한다 (12 §6.1)."""
        self.h_prop0.copy_(h_prop)
        self.h_terr0.copy_(h_terr)
        self.step = 0

    def add_pre(self, inp: dict, obs: torch.Tensor, gt_map, gt_feet, base_vel, use_gt) -> None:
        """env.step 전, 이번 스텝의 지각 입력과 정답."""
        if self.step >= self.T:
            raise OverflowError("지각 재생 버퍼가 찼다. start() 를 먼저 불러야 한다")
        t = self.step
        d = self.data
        d["depth2"][t].copy_(inp["depth2"])
        d["hist"][t].copy_(inp["hist"])
        d["tick"][t].copy_(inp["tick"])
        d["first"][t].copy_(inp["first"])
        d["obs"][t].copy_(obs)
        d["gt_map"][t].copy_(gt_map)
        d["gt_feet"][t].copy_(gt_feet.reshape(self.N, -1))
        d["base_vel"][t].copy_(base_vel)
        d["use_gt"][t].copy_(use_gt)

    def add_post(self, next_obs: torch.Tensor, done: torch.Tensor) -> None:
        """env.step 뒤. done 이면 next_obs 는 새 에피소드 첫 관측이라 ô 정답으로 쓰지 않는다(재생에서 마스크)."""
        t = self.step
        self.data["next_obs"][t].copy_(next_obs)
        self.data["done"][t].copy_(done.bool().view(-1))
        self.step += 1

    def full(self) -> bool:
        return self.step == self.T

    def env_batches(self, num_minibatches: int, num_epochs: int, generator: torch.Generator | None = None):
        """env 단위 minibatch (12 §6.1: env 단위 · 시간축은 자르지 않음). epoch 마다 섞는다."""
        mb = self.N // num_minibatches
        if mb == 0:
            raise ValueError(f"env {self.N} 개를 minibatch {num_minibatches} 개로 나눌 수 없다")
        for _ in range(num_epochs):
            perm = torch.randperm(self.N, generator=generator).to(self.device)
            for i in range(num_minibatches):
                yield perm[i * mb : (i + 1) * mb]

    def gather(self, idx: torch.Tensor) -> dict[str, torch.Tensor]:
        out = {k: v[:, idx] for k, v in self.data.items()}
        out["h_prop0"] = self.h_prop0[idx]
        out["h_terr0"] = self.h_terr0[idx]
        return out

    def nbytes(self) -> int:
        return sum(v.numel() * v.element_size() for v in self.data.values())
