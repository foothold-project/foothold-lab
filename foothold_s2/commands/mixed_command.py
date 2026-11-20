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


# v29-5 (lead 11/15 17:23), plan-driven since E1F (lead 2026-11-16 09:26): a free-speed env that draws a slow forward command
# (0.1 <= |v_xy| < 0.3, no rotation) keeps it for U(lo, hi) s instead of the base period (4 s), so the 0.1 command reaches its steady state.
# (lo, hi) is the plan row's `slow_hold_range_s`; no cell / null = off (the E1 row has none). It only ever lengthens the hold: it does nothing
# when the base period is already >= lo (evaluation uses 1e9) or when fixed_cmd is set.
SLOW_HOLD_V_LO = 0.1
SLOW_HOLD_V_HI = 0.3


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
        self.slow_hold = torch.zeros_like(self.stand)         # v29-5: envs whose current command got the long hold (record only)
        self.spin = torch.zeros_like(self.stand)
        self.heading = torch.zeros_like(self.stand)
        self.psi_star = torch.zeros(n, device=dev)

        self.start_xy = torch.zeros(n, 2, device=dev)
        self.max_dist = torch.zeros(n, device=dev)
        self.max_x = torch.zeros(n, device=dev) if getattr(cfg, "track_x_progress", False) else None    # 진행 축 x 최대 이동 (듬성 종류 승급 규칙용 · 기본 꺼짐: None)
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
        self.slot_names = (mc.EX39_SLOTS if self.params.ex39_arm is not None or self.params.curriculum_mode else
                           mc.BASIC_SLOTS if self.params.basic_mode else mc.WT_SLOTS)
        self.slot_counts = torch.zeros(len(self.slot_names), dtype=torch.long, device=dev)
        # Read-only Kit smoke evidence for the latest sampled slot of each env.
        self.slot_current = torch.full((n,), -1, dtype=torch.long, device=dev)
        self.ex39_first_forward_heading_wz_max = None
        self.ex39_first_forward_heading_wz_detail = None
        self.scatter_receipt = None                                                          # 명령 시계 흩기 영수증(첫 env.step 전 마지막 전체 reset 의 것)
        self._stepped = False
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
        if self.max_x is not None:
            self.max_x[env_ids] = 0.0
        self.cmd_sum_xy[env_ids] = 0.0
        self.cmd_sum_w[env_ids] = 0.0
        self.goals[env_ids] = 0
        self.excluded_steps[env_ids] = 0.0
        self.ep_steps[env_ids] = 0.0
        if hasattr(self, "stop_elapsed_s"):
            self.stop_elapsed_s[env_ids] = 0.0

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
        runtime = getattr(self, "stage_runtime", None)
        if runtime is not None:
            runtime.on_reset(ids)
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

    def take_slot_counts(self):
        """이번 update 동안 선택한 명령 모드의 슬롯 재추출 수와 비율."""
        if not (self.params.walkturn_mode or self.params.basic_mode):
            return None
        c = self.slot_counts.cpu().tolist()
        self.slot_counts.zero_()
        total = sum(c)

        return None if total == 0 else {"counts": dict(zip(self.slot_names, c)), "frac": {k: v / total for k, v in zip(self.slot_names, c)}}

    def _resample_command(self, env_ids):
        env_ids = torch.as_tensor(env_ids, device=self.device, dtype=torch.long)

        free = env_ids[~self.is_flag_env[env_ids]]

        if len(free) > 0:
            runtime = getattr(self, "stage_runtime", None)
            groups = ([(free[self.stage_runtime.env_stage[free] == i], i)
                       for i in range(len(runtime.plan.stages))] if runtime is not None else [(free, None)])
            for group, index in groups:
                if len(group) == 0:
                    continue
                was_stand = self.stand[group].clone() if runtime is not None else None
                stone = (self._stone_mask(group) if runtime is not None and getattr(runtime.plan.stages[index], "stone_forward_floor", None) else None)
                gkinds = tuple(getattr(runtime.plan.stages[index], "gap_forward_kinds", ()) or ()) if runtime is not None else ()
                gap = self._kinds_env_all(gkinds)[group] if gkinds else None
                out = (mc.resample_stage(self.gen, len(group), runtime.plan.stages[index], self._yaw(group), stone, gap)
                       if runtime is not None else
                       mc.resample_free_modes(self.gen, len(group), self.params, self.iteration,
                                              self.range_curriculum.vmax_x, self.range_curriculum.vmax_y,
                                              yaw=self._yaw(group)))
                self.vel_command_b[group] = out["cmd"].to(self.device)
                self.stand[group] = out["stand"].to(self.device)
                if not hasattr(self, "stop_elapsed_s"):
                    self.stop_elapsed_s = torch.zeros(self.num_envs, device=self.device)
                if runtime is None:
                    self.stop_elapsed_s[group] = 0.0
                else:
                    self.stop_elapsed_s[group] = mc.stop_elapsed_after_resample(
                        was_stand, self.stand[group], self.stop_elapsed_s[group])
                self.spin[group] = out["spin"].to(self.device)
                self.heading[group] = out["heading"].to(self.device)
                self.psi_star[group] = out["psi_star"].to(self.device)
                self.new_task.on_resample(group, out["cmd"].to(self.device), self.params)
                if stone is not None:
                    self._stone_note(out, stone, float(runtime.plan.stages[index].stone_forward_floor))
                if gap is not None:
                    self._gap_note(out, gap)
                if "slot" in out:
                    self.slot_counts += torch.bincount(out["slot"].to(self.device), minlength=len(self.slot_names))
                    self.slot_current[group] = out["slot"].to(self.device)
                if self.cfg.fixed_cmd is not None:
                    self.vel_command_b[group] = torch.tensor(self.cfg.fixed_cmd, device=self.device)
                    self.stand[group] = False
                    self.spin[group] = False
                    self.heading[group] = False
                if runtime is not None:
                    runtime.record_command_sample(group, self.vel_command_b[group],
                                                  self.slot_current[group], self.heading[group])

        self._apply_slow_hold(free)

        flag = env_ids[self.is_flag_env[env_ids]]

        if len(flag) > 0:
            self.params.flag_vmax = self.range_curriculum.flag_vmax        # 깃발 속도 커리큘럼 (14 §4)
            mc.flag_resample(self.flag_state, self._flag_row[flag], self.gen, self.params)
            record_flag = getattr(getattr(self, "stage_runtime", None), "record_flag_command_sample", None)
            if record_flag is not None:
                record_flag(flag)
            self.stand[flag] = False
            self.spin[flag] = False
            self.heading[flag] = False
            # The flag command is written by flag_step at the next compute. Until then the env must not follow
            # the command of an earlier free episode: a reset outside env.step (the start-up resets) has no
            # compute after it, and the first action would follow that stale command.
            self.vel_command_b[flag] = 0.0

    def _flag_turn_first_rad(self):
        """The plan row's `flag_turn_first_rad` (stage 0 of the stage runtime = the running row), or None = off (E1, E1F and every plan without the cell)."""
        override = getattr(self, "flag_turn_first_override", None)        # the official flag eval sets this (--flag-turn-first plan); None = the running row
        if override is not None:
            return float(override["rad"])
        runtime = getattr(self, "stage_runtime", None)
        stages = getattr(getattr(runtime, "plan", None), "stages", None)
        value = getattr(stages[0], "flag_turn_first_rad", None) if stages else None
        return float(value) if value else None

    def _flag_turn_first_scope(self):
        """The plan row's `flag_turn_first_scope` ("first" | "all"); "all" when the cell is missing."""
        override = getattr(self, "flag_turn_first_override", None)
        if override is not None:
            return str(override["scope"])
        runtime = getattr(self, "stage_runtime", None)
        stages = getattr(getattr(runtime, "plan", None), "stages", None)
        return str(getattr(stages[0], "flag_turn_first_scope", "all") or "all") if stages else "all"

    def _stone_env_all(self):
        """(num_envs,) bool: the env's terrain column is a stepping-stones kind (the EX-42 column table the entry puts on the env). A missing table is an error:
        the cell would otherwise be silently off."""
        table = getattr(getattr(self._env, "unwrapped", self._env), "_ex42_column_table", None)
        if table is None:
            raise ValueError("EX-42 stone_forward_floor needs the column table (raw._ex42_column_table) on the environment")
        runtime = getattr(self, "stage_runtime", None)
        stages = getattr(getattr(runtime, "plan", None), "stages", None)
        extra = set(getattr(stages[0], "stone_forward_floor_kinds", ()) or ()) if stages else set()
        names = {"%s/%s" % (row["family"], row["kind"]) for row in table}
        if extra - names:
            raise ValueError("EX-42 stone_forward_floor kinds not in the column table: %s" % sorted(extra - names))
        kinds = torch.tensor([("%s/%s" % (row["family"], row["kind"]) in extra) if extra else str(row["kind"]).startswith("stepping_stones") for row in table],
                             dtype=torch.bool, device=self.device)
        columns = self._env.scene.terrain.terrain_types.long().to(self.device)
        if bool(((columns < 0) | (columns >= len(kinds))).any()):
            raise ValueError("EX-42 stone_forward_floor: a terrain column is outside the column table")
        return kinds[columns]

    def _kinds_env_all(self, kinds):
        """(num_envs,) bool: the env's terrain column is one of `kinds` ("family/kind"). Unknown names or a missing table are errors (never a silent off)."""
        table = getattr(getattr(self._env, "unwrapped", self._env), "_ex42_column_table", None)
        if table is None:
            raise ValueError("EX-42 gap_forward_kinds needs the column table (raw._ex42_column_table) on the environment")
        names = {"%s/%s" % (row["family"], row["kind"]) for row in table}
        if set(kinds) - names:
            raise ValueError("EX-42 gap_forward_kinds not in the column table: %s" % sorted(set(kinds) - names))
        lut = torch.tensor(["%s/%s" % (row["family"], row["kind"]) in set(kinds) for row in table], dtype=torch.bool, device=self.device)
        columns = self._env.scene.terrain.terrain_types.long().to(self.device)
        if bool(((columns < 0) | (columns >= len(lut))).any()):
            raise ValueError("EX-42 gap_forward_kinds: a terrain column is outside the column table")
        return lut[columns]

    def _gap_note(self, out, gap):
        """Record only: commands drawn on the listed columns (forward, turn in place, smallest forward vx) and forward draws elsewhere."""
        if not hasattr(self, "_gap_acc"):
            self._gap_acc = torch.zeros(4, device=self.device)
            self._gap_min = torch.full((), 9.0, device=self.device)
        slot = out["slot"].to(self.device)
        vx = out["cmd"][:, 0].to(self.device)
        g = gap.to(self.device)
        go, turn = g & (slot == 0), g & ((slot == 3) | (slot == 4))
        self._gap_acc += torch.stack([go.sum(), turn.sum(), (g & ~go & ~turn).sum(), (~g & (slot == 0)).sum()]).float()
        if bool(go.any()):
            self._gap_min = torch.minimum(self._gap_min, vx[go].min())

    def gap_forward_summary(self):
        """(kinds, envs on them, envs, forward draws there, turn draws there, other draws there (must be 0), forward draws elsewhere, smallest forward vx there) or None."""
        runtime = getattr(self, "stage_runtime", None)
        stages = getattr(getattr(runtime, "plan", None), "stages", None)
        kinds = tuple(getattr(stages[0], "gap_forward_kinds", ()) or ()) if stages else ()
        if not kinds:
            return None
        acc = getattr(self, "_gap_acc", torch.zeros(4, device=self.device)).tolist()
        low = float(getattr(self, "_gap_min", torch.full((), 9.0)))
        return (kinds, int(self._kinds_env_all(kinds).sum()), int(self.num_envs), int(acc[0]), int(acc[1]), int(acc[2]), int(acc[3]), None if low > 8 else low)

    def _stone_mask(self, group):
        return self._stone_env_all()[group]

    def _stone_note(self, out, stone, floor):
        """Record only: forward commands drawn this resample on stone envs and on the rest (counts, those below `floor`, the smallest on stones)."""
        if not hasattr(self, "_stone_acc"):
            self._stone_acc = torch.zeros(5, device=self.device)
            self._stone_min = torch.full((), 9.0, device=self.device)
        fwd = (out["slot"] == 0).to(self.device)
        vx = out["cmd"][:, 0].to(self.device)
        on, off = fwd & stone, fwd & ~stone
        self._stone_acc += torch.stack([on.sum(), (on & (vx < floor)).sum(), off.sum(), (off & (vx < floor)).sum(), torch.tensor(1, device=self.device)]).float()
        if bool(on.any()):
            self._stone_min = torch.minimum(self._stone_min, vx[on].min())

    def stone_floor_summary(self):
        """(floor or None, stone envs, envs, forward draws on stones, of them below floor, forward draws elsewhere, of them below floor, smallest stone forward vx).
        Counts are since the term was made (the cell's receipt line prints them as they are)."""
        runtime = getattr(self, "stage_runtime", None)
        stages = getattr(getattr(runtime, "plan", None), "stages", None)
        floor = getattr(stages[0], "stone_forward_floor", None) if stages else None
        if not floor:
            return None
        acc = getattr(self, "_stone_acc", torch.zeros(5, device=self.device)).tolist()
        low = float(getattr(self, "_stone_min", torch.full((), 9.0)))
        return (float(floor), int(self._stone_env_all().sum()), int(self.num_envs), int(acc[0]), int(acc[1]), int(acc[2]), int(acc[3]), None if low > 8 else low)

    def _apply_slow_hold(self, ids):
        """v29-5, plan-driven (E1F): after the free envs drew their command, envs on the slow band (0.1 <= |v_xy| < 0.3, wz == 0, no heading / spin /
        stand) get time_left = U(lo, hi) s, where (lo, hi) is the plan row's `slow_hold_range_s` of the env's stage. No cell, null or 0 (the E1 row, the
        stage-zero view, any plan without the cell) = off: no draw from the generator, the base time_left stays."""
        if len(ids) == 0:
            return
        self.slow_hold[ids] = False
        if self.cfg.fixed_cmd is not None:
            return
        runtime = getattr(self, "stage_runtime", None)
        if runtime is None:
            return
        stages = runtime.plan.stages
        for index in range(len(stages)):
            hold_range = getattr(stages[index], "slow_hold_range_s", None)
            if not hold_range or float(self.cfg.resampling_time_range[1]) >= float(hold_range[0]):
                continue
            group = ids[runtime.env_stage[ids] == index]
            if len(group) == 0:
                continue
            cmd = self.vel_command_b[group]
            speed = torch.linalg.norm(cmd[:, :2], dim=1)
            hold = ((speed >= SLOW_HOLD_V_LO) & (speed < SLOW_HOLD_V_HI) & (cmd[:, 2].abs() <= 1e-6)
                    & ~self.heading[group] & ~self.spin[group] & ~self.stand[group])
            if hold.any():
                sel = group[hold]
                lo, hi = float(hold_range[0]), float(hold_range[1])
                u = torch.rand(len(sel), generator=self.gen, device=self.device)
                self.time_left[sel] = lo + (hi - lo) * u
                self.slow_hold[sel] = True

    _turn_sum = 0.0
    _turn_cnt = 0.0
    _turn_first_sum = _turn_first_cnt = _turn_rest_sum = _turn_rest_cnt = 0.0
    flag_turn_last_detail = None

    def flag_turn_summary(self):
        """Record only: (the running row's flag_turn_first_rad or None, share of flag-env steps since the last call that were on the turn-in-place branch, steps counted)."""
        frac = self._turn_sum / self._turn_cnt if self._turn_cnt else 0.0
        count = self._turn_cnt
        self.flag_turn_last_detail = (self._flag_turn_first_scope(),
                                      self._turn_first_sum / self._turn_first_cnt if self._turn_first_cnt else 0.0, self._turn_first_cnt,
                                      self._turn_rest_sum / self._turn_rest_cnt if self._turn_rest_cnt else 0.0, self._turn_rest_cnt)
        self._turn_sum = self._turn_cnt = 0.0
        self._turn_first_sum = self._turn_first_cnt = self._turn_rest_sum = self._turn_rest_cnt = 0.0
        return self._flag_turn_first_rad(), frac, count

    def slow_hold_summary(self):
        """Record only: (number of envs now holding a slow command, their mean time_left in s)."""
        n = int(self.slow_hold.sum().item())

        return n, (float(self.time_left[self.slow_hold].mean().item()) if n else 0.0)

    def _update_command(self):
        self._stepped = True                                  # 흩기는 학습(첫 step) 시작 뒤에는 다시 하지 않는다
        yaw = self._yaw()
        pos = self.robot.data.root_pos_w[:, :2]
        dt = self._env.step_dt

        free = ~self.is_flag_env
        runtime = getattr(self, "stage_runtime", None)
        if runtime is not None:
            applied = mc.apply_stage_heading(self.vel_command_b, self.heading, self.stand,
                                             self.psi_star, yaw, self.slot_current,
                                             runtime.env_stage, runtime.plan.stages)
        else:
            applied = mc.apply_heading(self.vel_command_b, self.heading, self.stand,
                                       self.psi_star, yaw, self.params)
        self.vel_command_b[free] = applied[free]
        if runtime is not None:
            self.stop_elapsed_s = torch.where(self.stand, self.stop_elapsed_s + dt,
                                              torch.zeros_like(self.stop_elapsed_s))
        if self.params.ex39_arm == "B" and self.ex39_first_forward_heading_wz_max is None:
            first_forward = (self.slot_current == 0) & self.heading & free
            if first_forward.any():
                expected = mc.heading_wz(self.psi_star[first_forward], yaw[first_forward],
                                         self.params.heading_stiffness, self.params.wz_max)
                observed = self.vel_command_b[first_forward, 2]
                self.ex39_first_forward_heading_wz_max = float(
                    observed.abs().max().item())
                self.ex39_first_forward_heading_wz_detail = {
                    "env_count": int(first_forward.sum().item()),
                    "observed_abs_max": self.ex39_first_forward_heading_wz_max,
                    "expected_abs_max": float(expected.abs().max().item()),
                    "error_abs_max": float((observed - expected).abs().max().item()),
                    "heading_error_abs_max": float(mc.wrap_to_pi(
                        self.psi_star[first_forward] - yaw[first_forward]).abs().max().item()),
                }

        if len(self.flag_ids) > 0:
            self.flag_turn_first_rad = self._flag_turn_first_rad()
            cmd = mc.flag_step(self.flag_state, pos[self.flag_ids], yaw[self.flag_ids], dt, self.params, self.flag_turn_first_rad, self._flag_turn_first_scope())
            sel = self.is_flag_env[self.flag_ids]
            self.vel_command_b[self.flag_ids[sel]] = cmd[sel]
            self.goals[self.flag_ids[sel]] = self.flag_state.passed[sel]
            st = self.flag_state
            spin_or_back = (st.v < self.params.flag_spin_threshold) | (st.backoff_left > 0)
            self.excluded_steps[self.flag_ids[sel]] += spin_or_back[sel].float()
            self._turn_sum += float(st.turning[sel].sum().item())      # record only
            self._turn_cnt += float(sel.sum().item())
            first_flag = (st.idx == 0)[sel]                              # record only: the same split on the first flag and the later ones
            self._turn_first_sum += float(st.turning_first[sel].sum().item())
            self._turn_first_cnt += float(first_flag.sum().item())
            self._turn_rest_sum += float((st.turning[sel] & ~first_flag).sum().item())
            self._turn_rest_cnt += float((~first_flag).sum().item())

        self.ep_steps += 1.0

        self.max_dist = torch.maximum(self.max_dist, torch.linalg.norm(pos - self.start_xy, dim=1))
        if self.max_x is not None:
            self.max_x = torch.maximum(self.max_x, pos[:, 0] - self.start_xy[:, 0])
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
    track_x_progress: bool = False
    """듬성 종류 올림 규칙 (plan terrain_promotion): 켜면 에피소드마다 진행 축 x 최대 이동 max_x 를 같이 센다. 꺼짐이면 max_x 는 None 이고 아무것도 더 계산하지 않는다."""
    clock_scatter: bool = False
    """EX-35: 새 프로세스의 첫 reset 직후 env 마다 다음 교체 시점을 U(0, resampling 주기) 로 흩는다."""
    params: dict = {}
    """`mixed_core.CommandParams` 필드 덮어쓰기."""
