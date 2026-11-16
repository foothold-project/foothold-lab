"""HiPAN 모드 2 주행 환경의 몸통 (설계 HIPAN-MODE2-ENTRY §3 N1 · PLAN-HIPAN-V2 M9).

얼린 하위 정책 (`lower_adapter.LowerPolicy`) 을 안에 두고, 상위 행동 하나를 받아 하위 스텝을 `hold_steps` (기본 5 = 0.1 초) 번 돌린다.
하위 관절 행동은 이 안에서 만들고 상위는 (vx, vy, wz) 만 낸다. 명령은 `command_space.CommandSpace` 를 거쳐 하위의 명령 항
(`base_velocity`) 에 덮어쓴다 (D44 평가기와 같은 길: `lower_adapter.apply_command` · 재표본 끔 · heading 끔 · 깃발 끔).

여기서 하는 일: 5 스텝 유지 · 명령 덮어쓰기 · 하위 reset 전달 · 윈도 안 추종 오차 기록 · 몸 상태 읽기.
여기서 하지 않는 일: 보상 · 관측 (N2) · 방 메시 장착 · env cfg (`tasks/nav_env_cfg.py`) · 학습 (N3).
env 는 `RslRlVecEnvWrapper` 꼴 (`reset` · `get_observations` · `step(action) -> obs, reward, done, extras` · `unwrapped`).
Isaac 가 없어도 가짜 env 로 시험한다 (torch 만 필요).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from foothold_s2.nav import lower_adapter
from foothold_s2.nav.command_space import CommandSpace, HOLD_STEPS

TERM_NAME = "base_velocity"


@dataclass
class NavState:
    """상위 틱 하나가 끝났을 때의 상태. 모두 numpy · 처음 축은 env."""
    pos_w: np.ndarray            # (n, 3) 몸통 위치 (월드)
    quat_w: np.ndarray           # (n, 4)
    pos_local: np.ndarray        # (n, 3) env 원점을 뺀 위치 (방 좌표로 쓰는 값)
    vel_b: np.ndarray            # (n, 3) 몸통 좌표 선속도
    yaw_rate: np.ndarray         # (n,)
    applied: np.ndarray          # (n, 5) 실제 넣은 명령 (vx vy wz dh roll)
    stand: np.ndarray            # (n,) bool
    modified: np.ndarray         # (n,) bool 명령 공간 층이 값을 고쳤다 (보상 r9 지시자)
    track_err: np.ndarray        # (hold, n, 3) 하위 스텝마다 (실제 - 명령) vx vy wz
    done: np.ndarray             # (n,) bool 이 윈도 안에서 한 번이라도 끝남 (넘어짐 · 시간 초과 포함)
    done_step: np.ndarray        # (n,) int 처음 끝난 하위 스텝 번호 (없으면 -1)
    timed_out: np.ndarray        # (n,) bool 시간 초과로 끝남 (extras["time_outs"] 가 있을 때)


def _np(x):
    return x.detach().cpu().numpy().copy()


class NavEnv:
    def __init__(self, env, lower, space: CommandSpace, *, term_name: str = TERM_NAME, fix_heading=None):
        if space.hold_steps < 1:
            raise ValueError("hold_steps must be >= 1")
        self.env, self.lower, self.space = env, lower, space
        self.raw = env.unwrapped
        self.term = self.raw.command_manager.get_term(term_name)
        self.n = int(self.term.vel_command_b.shape[0])
        if int(lower.n) != self.n:
            raise ValueError(f"lower policy has {lower.n} envs, environment has {self.n}")
        if space.pose_active != lower.pose_active:
            raise ValueError("pose switch differs between the command space and the lower policy")
        self.hold = space.hold_steps
        self.obs = None
        if fix_heading is None:
            from foothold_s2.eval.map_mode_cells import disable_heading_for_fixed_eval as fix_heading
        self._fix_heading = fix_heading        # 에피소드가 끝나 명령 항이 다시 뽑히면 heading 이 다시 켜질 수 있다: 덮어쓰기 전에 끈다

    # ---- 상태 읽기
    def _body(self):
        d = self.raw.scene["robot"].data
        return d.root_pos_w, d.root_quat_w, d.root_lin_vel_b, d.root_ang_vel_b[:, 2]

    def reset(self) -> NavState:
        import torch

        self.env.reset()
        self.obs = self.env.get_observations()
        self.lower.reset(torch.ones(self.n, dtype=torch.bool, device=self.term.vel_command_b.device))
        self.space.reset()
        self._fix_heading(self.term)
        if bool(self.term.heading.any()) or bool(self.term.is_flag_env.any()):
            raise RuntimeError("flag mode is on: lower commands would be rewritten (configure the env first)")
        return self._state(None, np.zeros((self.hold, self.n, 3)), np.zeros(self.n, bool), np.full(self.n, -1, np.int32),
                           np.zeros(self.n, bool))

    def _state(self, applied, track_err, done, done_step, timed_out) -> NavState:
        pos, quat, vel, yaw = self._body()
        origins = self.raw.scene.env_origins
        z5 = np.zeros((self.n, 5))
        return NavState(
            pos_w=_np(pos), quat_w=_np(quat), pos_local=_np(pos - origins), vel_b=_np(vel), yaw_rate=_np(yaw),
            applied=z5 if applied is None else applied.cmd.copy(),
            stand=np.zeros(self.n, bool) if applied is None else applied.stand.copy(),
            modified=np.zeros(self.n, bool) if applied is None else applied.modified.copy(),
            track_err=track_err, done=done, done_step=done_step, timed_out=timed_out)

    def step(self, high_action) -> NavState:
        """상위 행동 (n, 3) 하나 -> 하위 `hold` 스텝. 중간에 끝난 env 는 Isaac 이 되돌려 놓으므로 남은 스텝도 같은 명령으로 간다
        (벡터 환경이라 건너뛸 수 없다). 끝남은 `done` · `done_step` 으로 알린다."""
        if self.obs is None:
            raise RuntimeError("reset() first")
        a = np.asarray(high_action)
        if a.shape[0] != self.n:
            raise ValueError(f"high action has {a.shape[0]} rows, environment has {self.n}")
        done_any = np.zeros(self.n, bool)
        done_step = np.full(self.n, -1, np.int32)
        timed = np.zeros(self.n, bool)
        errs, applied = [], None
        for k in range(self.hold):
            applied = self.space.step(a)
            self._fix_heading(self.term)
            lower_adapter.apply_command(self.term, applied.cmd, applied.stand, self.lower.pose_active)
            action = self.lower.act(self.obs)
            self.obs, _reward, done, extras = self.env.step(action)
            self.lower.reset(done)
            _p, _q, vel, yaw = self._body()
            errs.append(lower_adapter.tracking_error(applied.cmd[:, :3], _np(vel), _np(yaw)))
            d = _np(done).astype(bool)
            done_step[(done_step < 0) & d] = k
            done_any |= d
            t = (extras or {}).get("time_outs") if isinstance(extras, dict) else None
            if t is not None:
                timed |= _np(t).astype(bool) & d
        return self._state(applied, np.stack(errs), done_any, done_step, timed)
