"""혼합 속도 명령 CommandTerm (14 §3~§6). Kit 안에서만 불린다. 계산은 `mixed_core` 가 한다.

- env 번호를 `flag_stride` 로 나눈 나머지가 0 이면 깃발 env (기본 5 → 20 %), 나머지는 자유 속도 env.
- 승급 term 이 읽는 값: `max_dist`(에피소드 중 출발점에서 가장 먼 거리), `cmd_sum_xy`(명령 선속도 합), `goals`(지난 깃발 수).
  Isaac 순서가 curriculum → 이벤트(spawn 설정) → command reset 이라, 승급 term 이 읽을 때 값은 «방금 끝난 에피소드» 것이다.
- 반복 수는 `common_step_counter // steps_per_iter` (PPO 24 스텝).
- S2 도 같은 클래스를 쓴다: 깃발은 `flag_provider` 로 갈아 끼운다 (기본은 칸 가운데 직선 4 깃발).
"""

from __future__ import annotations

from dataclasses import MISSING
from typing import TYPE_CHECKING

import torch

from isaaclab.managers import CommandTerm, CommandTermCfg
from isaaclab.utils import configclass

from foothold_s2.commands import mixed_core as mc

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedRLEnv


class MixedVelocityCommand(CommandTerm):
    cfg: "MixedVelocityCommandCfg"

    def __init__(self, cfg: "MixedVelocityCommandCfg", env: "ManagerBasedRLEnv"):
        super().__init__(cfg, env)

        self.robot = env.scene[cfg.asset_name]
        n, dev = self.num_envs, self.device
        self.params = mc.CommandParams(**cfg.params)
        self.gen = mc.make_generator(cfg.seed, device=dev)
        self.range_curriculum = mc.RangeCurriculum(vmax_x=self.params.vmax_x, vmax_y=self.params.vmax_y)

        self.vel_command_b = torch.zeros(n, 3, device=dev)
        self.is_flag_env = (torch.arange(n, device=dev) % cfg.flag_stride) == 0
        self.flag_ids = self.is_flag_env.nonzero(as_tuple=False).flatten()
        self._flag_row = torch.full((n,), -1, dtype=torch.long, device=dev)
        self._flag_row[self.flag_ids] = torch.arange(len(self.flag_ids), device=dev)

        self.stand = torch.zeros(n, dtype=torch.bool, device=dev)
        self.spin = torch.zeros_like(self.stand)
        self.heading = torch.zeros_like(self.stand)
        self.psi_star = torch.zeros(n, device=dev)

        self.start_xy = torch.zeros(n, 2, device=dev)
        self.max_dist = torch.zeros(n, device=dev)
        self.cmd_sum_xy = torch.zeros(n, 2, device=dev)
        self.goals = torch.zeros(n, dtype=torch.long, device=dev)

        count = cfg.flag_count
        self.flag_state = mc.FlagState.new(torch.zeros(len(self.flag_ids), count, 2, device=dev))
        self.exposure = mc.ExposureLog()
        self.metrics["error_vel_xy"] = torch.zeros(n, device=dev)
        self.metrics["error_vel_yaw"] = torch.zeros(n, device=dev)

    def __str__(self) -> str:
        return (f"MixedVelocityCommand: flag envs {len(self.flag_ids)} / {self.num_envs}, "
                f"vmax ({self.range_curriculum.vmax_x}, {self.range_curriculum.vmax_y})")

    @property
    def command(self) -> torch.Tensor:
        return self.vel_command_b

    @property
    def iteration(self) -> int:
        return int(self._env.common_step_counter // self.cfg.steps_per_iter)

    @property
    def mode_ids(self) -> torch.Tensor:
        return mc.mode_labels(self.is_flag_env, self.stand, self.spin, self.heading)

    # ------------------------------------------------------------ 기록 (승급 term 용)

    def set_range(self, vmax_x: float, vmax_y: float):
        self.range_curriculum.vmax_x = vmax_x
        self.range_curriculum.vmax_y = vmax_y

    def _yaw(self, ids=None):
        h = self.robot.data.heading_w

        return h if ids is None else h[ids]

    def _reset_episode_state(self, env_ids: torch.Tensor):
        pos = self.robot.data.root_pos_w[env_ids, :2]
        self.start_xy[env_ids] = pos
        self.max_dist[env_ids] = 0.0
        self.cmd_sum_xy[env_ids] = 0.0
        self.goals[env_ids] = 0

        flag_ids = env_ids[self.is_flag_env[env_ids]]

        if len(flag_ids) > 0:
            rows = self._flag_row[flag_ids]
            origins = self._env.scene.terrain.env_origins[flag_ids, :2]
            flags = self.cfg.flag_provider(origins, self.cfg.flag_count) if self.cfg.flag_provider is not None \
                else torch.stack([mc.straight_flag_line(o, self.cfg.flag_count) for o in origins.cpu()]).to(self.device)
            self.flag_state.reset(rows, flags=flags)

    # ------------------------------------------------------------ CommandTerm

    def reset(self, env_ids=None):
        """에피소드 처음: 기록과 깃발을 새 출발점으로 비운 뒤 재추출 (Isaac 은 이 시점에 spawn 이 이미 정해져 있다)."""
        ids = torch.arange(self.num_envs, device=self.device) if env_ids is None             else torch.as_tensor(env_ids, device=self.device, dtype=torch.long)
        self._reset_episode_state(ids)

        return super().reset(env_ids)

    def _resample_command(self, env_ids):
        env_ids = torch.as_tensor(env_ids, device=self.device, dtype=torch.long)

        free = env_ids[~self.is_flag_env[env_ids]]

        if len(free) > 0:
            out = mc.resample_free_modes(self.gen, len(free), self.params, self.iteration,
                                         self.range_curriculum.vmax_x, self.range_curriculum.vmax_y)
            self.vel_command_b[free] = out["cmd"].to(self.device)
            self.stand[free] = out["stand"].to(self.device)
            self.spin[free] = out["spin"].to(self.device)
            self.heading[free] = out["heading"].to(self.device)
            self.psi_star[free] = out["psi_star"].to(self.device)

        flag = env_ids[self.is_flag_env[env_ids]]

        if len(flag) > 0:
            mc.flag_resample(self.flag_state, self._flag_row[flag], self.gen, self.params)
            self.stand[flag] = False
            self.spin[flag] = False
            self.heading[flag] = False

    def _update_command(self):
        yaw = self._yaw()
        pos = self.robot.data.root_pos_w[:, :2]
        dt = self._env.step_dt

        free = ~self.is_flag_env
        self.vel_command_b[free] = mc.apply_heading(self.vel_command_b, self.heading, self.stand,
                                                    self.psi_star, yaw, self.params)[free]

        if len(self.flag_ids) > 0:
            cmd = mc.flag_step(self.flag_state, pos[self.flag_ids], yaw[self.flag_ids], dt, self.params)
            self.vel_command_b[self.flag_ids] = cmd
            self.goals[self.flag_ids] = self.flag_state.passed

        self.max_dist = torch.maximum(self.max_dist, torch.linalg.norm(pos - self.start_xy, dim=1))
        self.cmd_sum_xy += self.vel_command_b[:, :2]
        self.exposure.add(self.mode_ids, self.vel_command_b, dt)

    def _update_metrics(self):
        steps = self.cfg.resampling_time_range[1] / self._env.step_dt
        self.metrics["error_vel_xy"] += torch.norm(
            self.vel_command_b[:, :2] - self.robot.data.root_lin_vel_b[:, :2], dim=-1) / steps
        self.metrics["error_vel_yaw"] += torch.abs(
            self.vel_command_b[:, 2] - self.robot.data.root_ang_vel_b[:, 2]) / steps


@configclass
class MixedVelocityCommandCfg(CommandTermCfg):
    class_type: type = MixedVelocityCommand

    asset_name: str = MISSING
    seed: int = 0
    flag_stride: int = 5
    flag_count: int = 4
    steps_per_iter: int = 24
    flag_provider: object = None
    """`(origins_xy (m,2), count) -> (m, count, 2)`. None 이면 칸 가운데 직선. S2 가 갈아 끼운다."""
    params: dict = {}
    """`mixed_core.CommandParams` 필드 덮어쓰기."""
