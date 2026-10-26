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
from foothold_s2.curriculum import rules as curriculum_rules

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
        if cfg.flag_stride > 0:
            self.is_flag_env = (torch.arange(n, device=dev) % cfg.flag_stride) == 0
        else:
            self.is_flag_env = torch.zeros(n, dtype=torch.bool, device=dev)
        self._base_flag = self.is_flag_env.clone()
        if cfg.dynamic_flags:
            # 깃발 방식 여부가 reset 마다 칸 집단에 따라 바뀐다 (S2: 듬성한 칸 전부 + 이어진 칸의 20 %). 상태는 모든 env 몫.
            self.flag_ids = torch.arange(n, device=dev)
            self._flag_row = torch.arange(n, device=dev)
        else:
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
        self.cmd_sum_w = torch.zeros(n, 2, device=dev)       # J-T10: 세계 좌표 기대 변위 합 R(yaw_t) · 명령 (매 스텝 실제 yaw). 기본은 판정에 안 쓰고 병행 기록만
        self.frame_stats = curriculum_rules.FrameCompareStats()
        self.goals = torch.zeros(n, dtype=torch.long, device=dev)
        self.new_task = mc.NewTaskMark(n, dev)               # 새 과제(걸으며 돌기 등) 명령을 받은 에피소드 표식. 지형 커리큘럼이 승급 · 강등에서 뺀다 (JUDGE-SPEC 5)
        self.new_task_stats = curriculum_rules.NewTaskStats()
        self.excluded_steps = torch.zeros(n, device=dev)     # 깃발 env 가 제자리 회전 · 물러나기로 쓴 스텝 (14 §5 판정에서 뺀다)
        self.ep_steps = torch.zeros(n, device=dev)

        count = cfg.flag_count
        self.flag_state = mc.FlagState.new(torch.zeros(len(self.flag_ids), count, 2, device=dev))
        self.exposure = mc.ExposureLog()
        self.slot_counts = torch.zeros(len(mc.WT_SLOTS), dtype=torch.long, device=dev)      # S2a 슬롯별 재추출 수(update 마다 runner 가 꺼냄)
        self.scatter_receipt = None                                                          # 명령 시계 흩기 영수증(첫 env.step 전 마지막 전체 reset 의 것)
        self._stepped = False
        self.episode_scatter_receipt = None
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
    def walk_frac(self) -> torch.Tensor:
        """에피소드 중 «걷는 시간» 비율 (제자리 회전 · 물러나기 제외). 깃발 env 의 승급 판정에 쓴다."""
        return 1.0 - self.excluded_steps / torch.clamp(self.ep_steps, min=1.0)

    @property
    def had_new_task(self) -> torch.Tensor:
        """(N,) bool: 이 에피소드에서 새 과제 명령을 받았는가. 읽는 쪽은 `terrain_levels_mixed`."""
        return self.new_task.flag

    def mark_new_task_consumed(self, mask):
        """매 스텝 바뀌는 새 과제(정지 -> 재출발 프로파일 등)가 이 스텝에 실제로 소비된 env 를 표시한다(호출은 그 과제를 넣는 쪽)."""
        self.new_task.on_consumed(mask)

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
        self.new_task.clear(env_ids)                          # Isaac 순서가 curriculum -> command reset 이라 curriculum 이 지난 에피소드 표식을 읽은 뒤에 비운다. 재추출은 이 뒤(reset 안 super().reset)에서 다시 켠다
        pos = self.robot.data.root_pos_w[env_ids, :2]
        self.start_xy[env_ids] = pos
        self.max_dist[env_ids] = 0.0
        self.cmd_sum_xy[env_ids] = 0.0
        self.cmd_sum_w[env_ids] = 0.0
        self.goals[env_ids] = 0
        self.excluded_steps[env_ids] = 0.0
        self.ep_steps[env_ids] = 0.0

        if self.cfg.dynamic_flags and self.cfg.force_flag_provider is not None:
            forced = self.cfg.force_flag_provider(self._env.scene.terrain, env_ids)
            self.is_flag_env[env_ids] = self._base_flag[env_ids] | forced

        flag_ids = env_ids[self.is_flag_env[env_ids]]

        if len(flag_ids) > 0:
            rows = self._flag_row[flag_ids]
            origins = self._env.scene.terrain.env_origins[flag_ids, :2]
            if self.cfg.flag_provider is not None:
                flags = self.cfg.flag_provider(self._env.scene.terrain, flag_ids, self.cfg.flag_count)
            else:
                flags = torch.stack([mc.straight_flag_line(o, self.cfg.flag_count)
                                     for o in origins.cpu()]).to(self.device)
            self.flag_state.reset(rows, flags=flags)

    # ------------------------------------------------------------ CommandTerm

    def reset(self, env_ids=None):
        """에피소드 처음: 기록과 깃발을 새 출발점으로 비운 뒤 재추출 (Isaac 은 이 시점에 spawn 이 이미 정해져 있다)."""
        ids = torch.arange(self.num_envs, device=self.device) if env_ids is None             else torch.as_tensor(env_ids, device=self.device, dtype=torch.long)
        self._reset_episode_state(ids)

        extras = super().reset(env_ids)
        self._maybe_scatter_clock(ids)
        counts = torch.bincount(self.mode_ids, minlength=len(mc.MODES)).float() / self.num_envs

        for name, frac in zip(mc.MODES, counts.tolist()):
            extras[f"mode_fraction_{name}"] = frac

        extras["vmax_x"] = self.range_curriculum.vmax_x
        extras["flag_vmax"] = self.range_curriculum.flag_vmax
        fl = self.is_flag_env[self.flag_ids]

        if fl.any():
            st = self.flag_state
            extras["flag_envs_fraction"] = float(fl.float().mean())
            extras["flag_spin_fraction"] = float((st.v[fl] < self.params.flag_spin_threshold).float().mean())
            extras["flag_backoff_fraction"] = float((st.backoff_left[fl] > 0).float().mean())

        return extras

    def _maybe_scatter_clock(self, ids):
        """EX-35: 전체 reset 직후 env 마다 다음 교체 시점을 U(0, resample_s) 로 흩는다. 첫 env.step 전까지의 전체 reset 마다 다시 흩어(영수증은 마지막 것):
        RslRlVecEnvWrapper 의 첫 reset 과 이어 가기의 reset_segment_physics 의 reset 이 둘 다 시계를 4 s 로 되돌리므로 «한 번만» 이면 학습 직전 시계는 흩어져 있지 않다."""
        if not self.cfg.clock_scatter or self._stepped or len(ids) != self.num_envs:
            return
        period = float(self.cfg.resampling_time_range[1])
        self.time_left[:] = mc.scatter_clock(self.gen, self.num_envs, period).to(self.device)
        self.scatter_receipt = mc.scatter_receipt(self.time_left, period)
        env = self._env                                       # 에피소드 진행도도 흩는다: 이어 가기는 init_at_random_ep_len 을 끄므로 20 s 뒤 모든 env 가 함께 reset 되어 명령 시계가 다시 맞춰진다
        max_len = int(env.max_episode_length)
        env.episode_length_buf[:] = mc.scatter_episode(self.gen, self.num_envs, max_len).to(env.episode_length_buf.device)
        self.episode_scatter_receipt = mc.scatter_receipt(env.episode_length_buf.float() * env.step_dt, max_len * env.step_dt, bins=5)

    def take_slot_counts(self):
        """이번 update 동안의 S2a 슬롯 재추출 수와 비율(없거나 S2a 가 아니면 None)."""
        if not self.params.walkturn_mode:
            return None
        c = self.slot_counts.cpu().tolist()
        self.slot_counts.zero_()
        total = sum(c)

        return None if total == 0 else {"counts": dict(zip(mc.WT_SLOTS, c)), "frac": {k: v / total for k, v in zip(mc.WT_SLOTS, c)}}

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
            self.new_task.on_resample(free, out["cmd"].to(self.device), self.params)
            if "slot" in out:
                self.slot_counts += torch.bincount(out["slot"].to(self.device), minlength=len(mc.WT_SLOTS))

            if self.cfg.fixed_cmd is not None:
                self.vel_command_b[free] = torch.tensor(self.cfg.fixed_cmd, device=self.device)
                self.stand[free] = False
                self.spin[free] = False
                self.heading[free] = False

        flag = env_ids[self.is_flag_env[env_ids]]

        if len(flag) > 0:
            self.params.flag_vmax = self.range_curriculum.flag_vmax        # 깃발 속도 커리큘럼 (14 §4)
            mc.flag_resample(self.flag_state, self._flag_row[flag], self.gen, self.params)
            self.stand[flag] = False
            self.spin[flag] = False
            self.heading[flag] = False

    def _update_command(self):
        self._stepped = True                                  # 흩기는 학습(첫 step) 시작 뒤에는 다시 하지 않는다
        yaw = self._yaw()
        pos = self.robot.data.root_pos_w[:, :2]
        dt = self._env.step_dt

        free = ~self.is_flag_env
        self.vel_command_b[free] = mc.apply_heading(self.vel_command_b, self.heading, self.stand,
                                                    self.psi_star, yaw, self.params)[free]

        if len(self.flag_ids) > 0:
            cmd = mc.flag_step(self.flag_state, pos[self.flag_ids], yaw[self.flag_ids], dt, self.params)
            sel = self.is_flag_env[self.flag_ids]
            self.vel_command_b[self.flag_ids[sel]] = cmd[sel]
            self.goals[self.flag_ids[sel]] = self.flag_state.passed[sel]
            st = self.flag_state
            spin_or_back = (st.v < self.params.flag_spin_threshold) | (st.backoff_left > 0)
            self.excluded_steps[self.flag_ids[sel]] += spin_or_back[sel].float()

        self.ep_steps += 1.0

        self.max_dist = torch.maximum(self.max_dist, torch.linalg.norm(pos - self.start_xy, dim=1))
        self.cmd_sum_xy += self.vel_command_b[:, :2]
        self.cmd_sum_w += mc.world_cmd_step(yaw, self.vel_command_b[:, :2])
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
    """`(terrain, env_ids (m,), count) -> (m, count, 2)` 월드 좌표. None 이면 칸 가운데 직선. S2 가 갈아 끼운다."""
    dynamic_flags: bool = False
    force_flag_provider: object = None
    """`(terrain, env_ids) -> bool (m,)` 이 칸에서는 반드시 깃발 방식. dynamic_flags 일 때만 쓴다."""
    fixed_cmd: tuple = None
    """평가용: 모든 자유 속도 env 에 이 (vx, vy, wz) 만 낸다. flag_stride 0 이면 깃발 env 없음."""
    clock_scatter: bool = False
    """EX-35: 새 프로세스의 첫 reset 직후 env 마다 다음 교체 시점을 U(0, resampling 주기) 로 흩는다."""
    params: dict = {}
    """`mixed_core.CommandParams` 필드 덮어쓰기."""
