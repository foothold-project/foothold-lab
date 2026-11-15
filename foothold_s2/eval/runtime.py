"""Kit 쪽 롤아웃 엔진. 축 1 · 축 3 · START 시험지가 같은 루프를 쓴다.

한 env 가 한 판씩 돌고, 판이 끝나면 쌓아 둔 배열을 `judge` 에 넘겨 행 하나를 얻는다.
판정 식은 여기 없다 (`judge.py` 한 곳). 여기는 «무엇을 언제 읽는가» 만 정한다.

지켜야 할 순서 (옛 하네스가 값을 잃은 자리)
  1. 상태는 `env.step()` «전» 에 읽는다. 스텝 안에서 끝난 판은 그 자리에서 리셋되고
     접촉 센서 이력이 0 으로 지워지기 때문이다.
  2. 명령은 `env.step()` «전» 에 쓴다. 다음 관측이 그 명령을 담는다.
  3. 판이 끝난 env 의 다음 판 명령은 `_resample` 이 쓴다 (리셋은 step 안에서 일어난다).
"""

import math
import time

import numpy as np
import torch

from foothold_s2.eval import judge

COMMAND_TOLERANCE = 1.0e-5


class CommandPin:
    """env 마다 «원래 명령» 을 쥐고, 리셋 때 그것을 다시 쓰게 하는 장치.

    `base` 는 (N, 3) 이고 판 시작 때의 명령이다. 도달 뒤 정지가 있으면 `want` 가 0 으로
    바뀌지만 리셋된 env 의 다음 판은 다시 `base` 로 시작한다.
    """

    def __init__(self, num_envs, device, base):
        self.base = torch.as_tensor(base, dtype=torch.float32, device=device).reshape(num_envs, 3).clone()
        self.want = self.base.clone()
        self.device = device

    def restart(self, env_ids):
        self.want[env_ids] = self.base[env_ids]


class EpisodeRunner:
    """고정 명령 한 벌로 지형 여러 개를 돈다.

    `mode` 가 "axis1" 이면 v2 와 같게 끝까지 걷는다 (정지 없음), "command" 이면 명령 방향
    진행이 `reference_m` 에 닿는 순간 명령을 0 으로 바꾸고 시간 T 까지 서 있게 한다 (41 §5).
    """

    def __init__(self, adapter_env, policy, policy_nn, pin, *, terrain_names, envs_per_terrain,
                 episodes, duration_s, mode, judge_kwargs, reference_m=None, command_s=None, log=print):
        self.env = adapter_env["env"]
        self.raw = adapter_env["raw"]
        self.policy = policy
        self.policy_nn = policy_nn
        self.pin = pin
        self.terrain_names = list(terrain_names)
        self.envs_per_terrain = envs_per_terrain
        self.episodes = episodes
        self.duration_s = duration_s
        self.mode = mode
        self.judge_kwargs = judge_kwargs
        self.reference_m = reference_m
        self.command_s = command_s
        self.log = log

    def targets(self, recorded):
        """env 별 목표 판 수. 지형당 총 `episodes` 판을 그 지형의 env 들에 고르게 나눈다."""
        n_env = self.envs_per_terrain * len(self.terrain_names)
        out = torch.zeros(n_env, dtype=torch.long, device=self.raw.device)
        base, extra = divmod(self.episodes, self.envs_per_terrain)

        for name in recorded:
            first = self.terrain_names.index(name) * self.envs_per_terrain

            for k in range(self.envs_per_terrain):
                out[first + k] = base + (1 if k < extra else 0)

        return out

    def run(self, recorded, on_episode, wall_limit_s=None, obs=None, targets=None, env_tags=None):
        raw, env, pin = self.raw, self.env, self.pin
        device = raw.device
        dt = raw.step_dt
        n_env = raw.num_envs
        robot = raw.scene["robot"]
        command_term = raw.command_manager.get_term("base_velocity")

        max_steps = int(round(self.duration_s / dt)) + 2
        # `targets` 를 직접 주면(START 시험지: env 마다 (종류, 레벨) 가 정해져 있다) 그대로 쓴다.
        targets = self.targets(recorded) if targets is None else targets.to(device)
        total = int(targets.sum().item())
        counts = torch.zeros(n_env, dtype=torch.long, device=device)

        length = torch.zeros(n_env, dtype=torch.long, device=device)
        pos_buf = torch.zeros((n_env, max_steps, 2), device=device)
        yaw_buf = torch.zeros((n_env, max_steps), device=device)
        vel_buf = torch.zeros((n_env, max_steps, 2), device=device)
        wz_buf = torch.zeros((n_env, max_steps), device=device)
        cmd_buf = torch.zeros((n_env, max_steps, 3), device=device)
        on_buf = torch.zeros((n_env, max_steps), dtype=torch.bool, device=device)
        err_buf = torch.zeros((n_env, max_steps), device=device)

        cum_proj = torch.zeros(n_env, device=device)
        reached = torch.zeros(n_env, dtype=torch.bool, device=device)
        on = torch.ones(n_env, dtype=torch.bool, device=device)

        lin = pin.base[:, :2]
        lin_norm = torch.linalg.vector_norm(lin, dim=1)
        has_lin = lin_norm > 1.0e-9
        unit = lin / lin_norm.clamp_min(1.0e-9).unsqueeze(1)

        terrain_types = raw.scene.terrain.terrain_types.detach().cpu().tolist()
        env_index = torch.arange(n_env, device=device)

        if obs is None:
            obs = env.get_observations()

        started = time.time()
        steps_done = 0

        while True:
            if torch.all(counts >= targets):
                break

            if wall_limit_s is not None and time.time() - started > wall_limit_s:
                raise RuntimeError("시간 제한 %.0f s 를 넘었습니다 (끝낸 판 %d/%d)"
                                   % (wall_limit_s, int(counts.sum().item()), total))

            active = counts < targets

            # 1. 스텝 전 상태.
            pos = robot.data.root_pos_w[:, :2].clone()
            q = robot.data.root_quat_w
            yaw = torch.atan2(2.0 * (q[:, 0] * q[:, 3] + q[:, 1] * q[:, 2]),
                              1.0 - 2.0 * (q[:, 2] ** 2 + q[:, 3] ** 2))
            vel_b = robot.data.root_lin_vel_b[:, :2].clone()
            wz_b = robot.data.root_ang_vel_b[:, 2].clone()
            cmd_now = command_term.commands[:, :3].clone() if hasattr(command_term, "commands") \
                else command_term.vel_command_b[:, :3].clone()

            deviation = torch.max(torch.abs(cmd_now - pin.want)).item()

            if deviation > COMMAND_TOLERANCE:
                raise RuntimeError("명령이 도중에 바뀌었습니다. 최대 편차 %.3e" % deviation)

            err = torch.linalg.vector_norm(vel_b - cmd_now[:, :2], dim=1)

            room = active & (length < max_steps)
            idx = env_index[room]
            at = length[room]
            pos_buf[idx, at] = pos[room]
            yaw_buf[idx, at] = yaw[room]
            vel_buf[idx, at] = vel_b[room]
            wz_buf[idx, at] = wz_b[room]
            cmd_buf[idx, at] = cmd_now[room]
            on_buf[idx, at] = on[room]
            err_buf[idx, at] = err[room]
            length[room] += 1

            # 명령 방향 진행 누적. 이 표본의 속도가 이 스텝을 지난다 (judge 가 한 칸 미는 것과 짝).
            if self.mode == "command":
                step_proj = (vel_b * unit).sum(dim=1) * dt
                cum_proj += torch.where(active & on & has_lin, step_proj, torch.zeros_like(step_proj))

            # 2. 정책 -> 스텝.
            with torch.inference_mode():
                actions = self.policy(obs)

            if self.mode == "command" and self.reference_m is not None:
                hit = active & on & has_lin & (cum_proj >= self.reference_m - judge.REACH_EPS)

                if hit.any():
                    reached |= hit
                    on = on & ~hit
                    pin.want[hit] = 0.0

            if self.mode == "command" and self.command_s is not None:
                # 명령 유지 시간이 정해진 칸 (41 §4 결정 2): 그 시간이 지나면 기준 거리에 못 닿아도 명령을 0 으로.
                expire = active & on & (length >= int(round(self.command_s / dt)))

                if expire.any():
                    on = on & ~expire
                    pin.want[expire] = 0.0

            self._write_command(command_term, pin.want)

            with torch.inference_mode():
                obs, _reward, dones, _extras = env.step(actions)
                self.policy_nn.reset(dones)

            steps_done += 1
            terminated = raw.reset_terminated.clone()
            timed_out = raw.reset_time_outs.clone()
            done_ids = torch.nonzero((terminated | timed_out) & active, as_tuple=False).squeeze(-1)

            for env_id in done_ids.tolist():
                n = int(length[env_id].item())
                row = self._judge_one(env_id, n, pos_buf, yaw_buf, vel_buf, wz_buf, cmd_buf,
                                      on_buf, err_buf, bool(timed_out[env_id]),
                                      bool(terminated[env_id]), dt)
                row["terrain"] = self.terrain_names[int(terrain_types[env_id])]
                row["env_id"] = env_id

                if env_tags is not None:
                    row.update(env_tags[env_id])

                row["episode"] = int(counts[env_id].item()) + 1
                counts[env_id] += 1
                on_episode(row)

                length[env_id] = 0
                cum_proj[env_id] = 0.0
                reached[env_id] = False
                on[env_id] = True
                pin.restart(env_id)

            # 판이 끝나 `_resample` 이 쓴 명령(원래 명령)과 want 를 맞춘다.
            if done_ids.numel():
                self._write_command(command_term, pin.want)

        self.obs = obs

        return {"steps": steps_done, "wall_s": time.time() - started, "episodes": int(counts.sum().item())}

    @staticmethod
    def _write_command(command_term, want):
        if hasattr(command_term, "commands"):
            command_term.commands[:, :3] = want
        else:
            command_term.vel_command_b[:, :3] = want

    def _judge_one(self, env_id, n, pos_buf, yaw_buf, vel_buf, wz_buf, cmd_buf, on_buf,
                   err_buf, timed_out, terminated, dt):
        pos = pos_buf[env_id, :n].cpu().numpy().astype(np.float64)
        yaw = yaw_buf[env_id, :n].cpu().numpy().astype(np.float64)

        if self.mode == "axis1":
            fwd = (math.cos(yaw[0]), math.sin(yaw[0]))
            err = err_buf[env_id, :n].cpu().numpy().astype(np.float64)

            return judge.judge_axis1(pos, err, fwd, timed_out, terminated, dt, **self.judge_kwargs)

        vel = vel_buf[env_id, :n].cpu().numpy().astype(np.float64)
        wz = wz_buf[env_id, :n].cpu().numpy().astype(np.float64)
        cmd = cmd_buf[env_id, :n].cpu().numpy().astype(np.float64)
        act = on_buf[env_id, :n].cpu().numpy()

        return judge.judge_command(pos, yaw, vel, wz, cmd, act, timed_out, terminated, dt,
                                   reference_m=self.reference_m, **self.judge_kwargs)
