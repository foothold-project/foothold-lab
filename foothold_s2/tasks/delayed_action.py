"""행동 지연 (17 §5, 시스템 지연 0~15 ms). Kit 안에서만 불린다.

관절 목표는 제어 스텝마다 한 번 정해지고 시뮬 하위 스텝(5 ms) 마다 적용된다. env 마다 reset 때 지연 d (하위 스텝 수,
0~3 = 0~15 ms) 를 뽑아, 제어 스텝의 첫 d 개 하위 스텝에는 «직전 제어 스텝의 목표» 를 적용한다.
"""

import math

import torch

from isaaclab.envs.mdp.actions import JointPositionAction, JointPositionActionCfg
from isaaclab.utils import configclass


class DelayedJointPositionAction(JointPositionAction):
    def __init__(self, cfg, env):
        super().__init__(cfg, env)
        self.max_delay_substeps = int(math.floor(cfg.max_delay_s / env.physics_dt + 1e-9))
        self.delay = torch.zeros(env.num_envs, dtype=torch.long, device=self.device)
        self._prev = self._offset.clone() if torch.is_tensor(self._offset) else torch.zeros_like(self.processed_actions)
        self._sub = 0
        self._ex40_sample_counts = None

    def process_actions(self, actions):
        self._prev = self.processed_actions.clone()
        super().process_actions(actions)
        self._sub = 0

    def apply_actions(self):
        use_prev = (self._sub < self.delay)[:, None]
        target = torch.where(use_prev, self._prev, self.processed_actions)
        self._asset.set_joint_position_target(target, joint_ids=self._joint_ids)
        self._sub += 1

    def reset(self, env_ids=None):
        super().reset(env_ids)
        ids = slice(None) if env_ids is None else env_ids
        n = self.num_envs if env_ids is None else len(env_ids)
        if getattr(self.cfg, "dr_scale_from_env", False):
            scale = getattr(self._env, "_ex40_dr_scale", None)
            if scale is None or not 0.0 <= float(scale) <= 1.0:
                raise RuntimeError("EX-40 delayed action requires a scheduled _ex40_dr_scale")
            self.max_delay_substeps = int(math.floor(
                float(scale) * self.cfg.max_delay_s / self._env.physics_dt + 1e-9))
        self.delay[ids] = torch.randint(0, self.max_delay_substeps + 1, (n,), device=self.device)
        self._prev[ids] = self._asset.data.joint_pos[ids][:, self._joint_ids]
        if getattr(self.cfg, "dr_scale_from_env", False):
            histogram = torch.bincount(self.delay[ids].flatten(), minlength=self.max_delay_substeps + 1)
            if self._ex40_sample_counts is None or self._ex40_sample_counts.numel() < histogram.numel():
                grown = torch.zeros(histogram.numel(), dtype=torch.long, device=self.device)
                if self._ex40_sample_counts is not None:
                    grown[:self._ex40_sample_counts.numel()] = self._ex40_sample_counts
                self._ex40_sample_counts = grown
            self._ex40_sample_counts[:histogram.numel()] += histogram


@configclass
class DelayedJointPositionActionCfg(JointPositionActionCfg):
    class_type: type = DelayedJointPositionAction
    max_delay_s: float = 0.015
    dr_scale_from_env: bool = False
