"""START runner 시험용 가짜 VecEnv. Kit 없이 runner 의 배선(수집 · 두 손실 · 리셋 · 저장)을 돌린다.

관측은 시드 고정 난수, 보상은 행동 크기에 따른 값, done 은 env 마다 정해진 주기로 낸다. 실제 물리와는 무관하다.
"""

from __future__ import annotations

import torch
from tensordict import TensorDict


class FakeStartEnv:
    def __init__(self, num_envs: int = 8, episode_len: int = 13, seed: int = 0, device: str = "cpu") -> None:
        self.num_envs = num_envs
        self.num_actions = 12
        self.device = device
        self.max_episode_length = episode_len
        self.episode_length_buf = torch.zeros(num_envs, dtype=torch.long)
        self.g = torch.Generator().manual_seed(seed)
        self.cfg = type("Cfg", (), {"seed": seed})()
        self.t = 0
        self._obs = self._make()

    def _make(self) -> TensorDict:
        n, g = self.num_envs, self.g
        return TensorDict(
            {
                "policy": torch.randn(n, 45, generator=g),
                "depth": torch.rand(n, 60, 60, generator=g),
                "gt_map": torch.randn(n, 512, generator=g) * 0.1,
                "gt_feet": torch.randn(n, 100, generator=g) * 0.1,
                "base_vel": torch.randn(n, 3, generator=g),
                "contacts": (torch.rand(n, 4, generator=g) > 0.5).float(),
                # 잡음 없는 critic 묶음 52 (o45 clean + 몸 선속도 3 + 발 접촉 4). 별도 생성기라 위 값의 난수 흐름을 바꾸지 않는다
                "critic": torch.randn(n, 52, generator=torch.Generator().manual_seed(10_000 + self.t)),
            },
            batch_size=[n],
        )

    def get_observations(self) -> TensorDict:
        return self._obs

    def step(self, actions: torch.Tensor):
        self.t += 1
        self.episode_length_buf += 1
        # env 번호만큼 어긋난 주기로 끝난다 (env 마다 다른 스텝에서 done)
        dones = ((self.episode_length_buf + torch.arange(self.num_envs)) % self.max_episode_length == 0)
        self.episode_length_buf[dones] = 0
        rewards = 1.0 - 0.01 * actions.pow(2).sum(-1) + 0.1 * torch.arange(self.num_envs).float()
        self._obs = self._make()
        extras = {"time_outs": torch.zeros(self.num_envs, dtype=torch.bool)}
        return self._obs, rewards, dones.long(), extras


def train_cfg(num_steps: int = 24, perception: dict | None = None) -> dict:
    return {
        "num_steps_per_env": num_steps,
        "save_interval": 1000,
        "obs_groups": {},
        "policy": {"class_name": "StartActorCritic", "init_noise_std": 1.0, "actor_obs_normalization": False,
                   "critic_obs_normalization": False},
        "algorithm": {"class_name": "PPO", "num_learning_epochs": 5, "num_mini_batches": 4, "clip_param": 0.2,
                      "gamma": 0.99, "lam": 0.95, "value_loss_coef": 1.0, "entropy_coef": 0.01,
                      "learning_rate": 1e-3, "max_grad_norm": 1.0, "schedule": "adaptive", "desired_kl": 0.01},
        "perception": perception or {"microbatch_envs": 4},
    }
