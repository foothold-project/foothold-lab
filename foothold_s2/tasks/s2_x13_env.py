"""EX-13 env: 보상 합을 0 아래로 자르는 only_positive_rewards (MGDP · legged_gym legged_robot.py:237). Kit 안에서만 불린다. 계산은 rewards/mgdp_core.clamp_positive.

reward_manager 가 항별 값(_step_reward · Episode_Reward/<항>)을 만든 뒤 합만 자른다. 그래서 항별 기록(reward_split 의 항별 값 · Episode_Reward)은 자르기 전 값이고,
얼마나 잘렸는지는 `reward_neg_clipped`(env-step 마다 bool) 와 Episode_Reward/only_positive_clipped_fraction(에피소드 평균 잘린 비율)으로 따로 남긴다.
"""

import torch

from isaaclab.envs import ManagerBasedRLEnv

from foothold_s2.rewards import mgdp_core as mc


class FootholdS2PosRewardEnv(ManagerBasedRLEnv):
    def __init__(self, cfg, render_mode=None, **kwargs):
        super().__init__(cfg, render_mode=render_mode, **kwargs)
        self.reward_neg_clipped = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)
        self._clip_steps = torch.zeros(self.num_envs, device=self.device)

        if getattr(cfg, "only_positive_rewards", False):
            orig = self.reward_manager.compute

            def compute(*args, **kw):
                total = orig(*args, **kw)
                clipped, neg, self._clip_steps = mc.clamp_positive(total, self._clip_steps)
                self.reward_neg_clipped = neg

                return clipped

            self.reward_manager.compute = compute

    def _reset_idx(self, env_ids):
        ids = torch.as_tensor(env_ids, device=self.device, dtype=torch.long)
        frac = (self._clip_steps[ids] / self.episode_length_buf[ids].clamp(min=1).float()).mean() if len(ids) > 0 else torch.zeros((), device=self.device)
        super()._reset_idx(env_ids)
        self.extras.setdefault("log", {})["Episode_Reward/only_positive_clipped_fraction"] = frac
        self._clip_steps[ids] = 0.0
