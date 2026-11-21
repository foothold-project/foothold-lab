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

import math
import re
from dataclasses import dataclass

import numpy as np

from foothold_s2.lab_compat import quat_wxyz, th
from foothold_s2.nav import lower_adapter
from foothold_s2.nav.command_space import CommandSpace, HOLD_STEPS

TERM_NAME = "base_velocity"
SENSOR_NAME = "contact_forces"
COLLISION_BODIES = ("base", ".*_thigh", "Head_.*")      # 충돌 몸체 = 몸통 · 허벅지 · 머리 (논문 미기재 · 가정 · 설계 §5). 이름은 Go2 USD 기준 (Kit 확인 전 미확인)
COLLISION_FORCE_N = 1.0                                 # 가정 (D44 평가기의 발 접촉 문턱과 같은 값)


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
    ang_vel_b: np.ndarray        # (n, 3)
    q: np.ndarray                # (n, J) 관절 위치
    q0: np.ndarray               # (J,) 기본 자세
    proprio: np.ndarray          # (n, 45) 하위 관측의 앞 45 칸 (o45 = 하위 고유감각 · teacher 관측의 o_p)
    collision: np.ndarray        # (n,) bool 이 윈도 안에서 충돌 몸체가 문턱 이상 힘을 받았다


def _np(x):
    return x.detach().cpu().numpy().copy()


DEFAULT_EPISODE_S = 90.0              # 경로 길이로 시간을 못 정할 때의 고정 에피소드 길이 (초)


class NavEnv:
    def __init__(self, env, lower, space: CommandSpace, *, term_name: str = TERM_NAME, fix_heading=None,
                 sensor_name: str | None = SENSOR_NAME, collision_bodies=COLLISION_BODIES, collision_force_n: float = COLLISION_FORCE_N):
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
        from foothold_s2.nav import pose_actions

        if pose_actions.enabled() and not lower.pose_active:
            raise ValueError("HIPAN_POSE_ACTIONS=1 needs a lower policy with a posture receipt (lower_adapter.pose_active_from_receipt: E6a passed)")
        self.hold = space.hold_steps
        self.obs = None
        if fix_heading is None:
            from foothold_s2.eval.map_mode_cells import disable_heading_for_fixed_eval as fix_heading
        self.collision_force_n = float(collision_force_n)
        self.sensor = None if sensor_name is None else self.raw.scene[sensor_name]
        self.collision_ids = None
        if self.sensor is not None:
            names = list(self.sensor.body_names)
            ids = [i for i, nm in enumerate(names) if any(re.fullmatch(pat, nm) for pat in collision_bodies)]
            if not ids:
                raise ValueError(f"no contact sensor body matches {collision_bodies}: {names}")
            self.collision_ids = ids
        self._fix_heading = fix_heading        # 에피소드가 끝나 명령 항이 다시 뽑히면 heading 이 다시 켜질 수 있다: 덮어쓰기 전에 끈다

    # ---- 상태 읽기
    def _body(self):
        d = self.raw.scene["robot"].data
        return th(d.root_pos_w), quat_wxyz(d.root_quat_w), th(d.root_lin_vel_b), th(d.root_ang_vel_b)[:, 2]

    def _nav_tensors(self):
        """하위 env 의 두 종료 항 (nav_env_cfg.nav_force_reset · nav_episode_timeout) 이 읽는 텐서: 되돌림 요청 (n,) bool · env 별 에피소드 최대 스텝 (n,)."""
        import torch

        raw = self.raw
        if getattr(raw, "_nav_force", None) is None:
            dev = self.term.vel_command_b.device
            raw._nav_force = torch.zeros(self.n, dtype=torch.bool, device=dev)
            raw._nav_max_steps = torch.full((self.n,), int(math.ceil(DEFAULT_EPISODE_S / float(raw.step_dt))), dtype=torch.long, device=dev)
        return raw

    def request_reset(self, env_ids) -> None:
        """이 env 들을 다음 상위 틱 첫 하위 스텝에 Isaac 이 되돌리게 한다 (과제 성공 종료). 되돌림은 보통 종료와 같은 길 (events · 명령 · 하위 정책 reset)."""
        import torch

        raw = self._nav_tensors()
        raw._nav_force[torch.as_tensor(np.asarray(env_ids, dtype=np.int64), device=raw._nav_force.device)] = True

    def set_episode_seconds(self, env_ids, seconds) -> None:
        """env 별 에피소드 최대 길이 (초). 하위 env 의 시간 초과 항 (nav_episode_timeout) 이 읽는다."""
        import torch

        raw = self._nav_tensors()
        steps = np.maximum(np.ceil(np.asarray(seconds, dtype=float) / float(raw.step_dt)), 1).astype(np.int64)
        raw._nav_max_steps[torch.as_tensor(np.asarray(env_ids, dtype=np.int64), device=raw._nav_max_steps.device)] = torch.as_tensor(steps, device=raw._nav_max_steps.device)

    def reset(self) -> NavState:
        import torch

        try:
            self._nav_tensors()
        except AttributeError:               # 가짜 env (step_dt 없음)
            pass
        self.env.reset()
        self.obs = self.env.get_observations()
        self.lower.reset(torch.ones(self.n, dtype=torch.bool, device=self.term.vel_command_b.device))
        self.space.reset()
        self._fix_heading(self.term)
        if bool(self.term.heading.any()) or bool(self.term.is_flag_env.any()):
            raise RuntimeError("flag mode is on: lower commands would be rewritten (configure the env first)")
        return self._state(None, np.zeros((self.hold, self.n, 3)), np.zeros(self.n, bool), np.full(self.n, -1, np.int32),
                           np.zeros(self.n, bool))

    def _collision_now(self) -> np.ndarray:
        if self.sensor is None:
            return np.zeros(self.n, bool)
        import torch

        force = torch.linalg.vector_norm(th(self.sensor.data.net_forces_w)[:, self.collision_ids], dim=-1)
        return _np((force > self.collision_force_n).any(dim=1)).astype(bool)

    def _proprio(self) -> np.ndarray:
        # rsl_rl 3.x 는 TensorDict (batch shape (n,) 라 .shape 가 있음 · 로컬 2.3.2 Kit 에서 IndexError) 를 준다: "policy" 키가 있으면 그것을 쓴다
        obs = self.obs["policy"] if hasattr(self.obs, "keys") and "policy" in self.obs.keys() else self.obs
        return _np(obs[:, :45])

    def _state(self, applied, track_err, done, done_step, timed_out, collision=None) -> NavState:
        pos, quat, vel, yaw = self._body()
        data = self.raw.scene["robot"].data
        origins = self.raw.scene.env_origins
        z5 = np.zeros((self.n, 5))
        return NavState(
            pos_w=_np(pos), quat_w=_np(quat), pos_local=_np(pos - origins), vel_b=_np(vel), yaw_rate=_np(yaw),
            applied=z5 if applied is None else applied.cmd.copy(),
            stand=np.zeros(self.n, bool) if applied is None else applied.stand.copy(),
            modified=np.zeros(self.n, bool) if applied is None else applied.modified.copy(),
            track_err=track_err, done=done, done_step=done_step, timed_out=timed_out,
            ang_vel_b=_np(th(data.root_ang_vel_b)), q=_np(th(data.joint_pos)), q0=_np(th(data.default_joint_pos)[0]),
            proprio=self._proprio(), collision=np.zeros(self.n, bool) if collision is None else collision)

    def _note_terms(self, first: bool) -> None:
        """이 윈도 안에서 종료 항 (몸 닿음 · 기울기 · 시간 · ...) 별로 한 번이라도 켜진 env 수. GPU 에서 OR 하고 윈도 끝에 한 번만 센다 (term_counts)."""
        try:
            tm = self.env.unwrapped.termination_manager
            if first:
                self._term_acc = {}
            for name in tm.active_terms:
                v = tm.get_term(name).bool()
                self._term_acc[name] = v if name not in self._term_acc else (self._term_acc[name] | v)
        except (AttributeError, KeyError, RuntimeError):
            self._term_acc = {}

    @property
    def term_counts(self) -> dict:
        return {k: int(v.sum().item()) for k, v in getattr(self, "_term_acc", {}).items()}

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
        collided = np.zeros(self.n, bool)
        from foothold_s2.nav import pose_actions

        a, pose = pose_actions.split(a) if a.ndim == 2 and a.shape[1] in (3, 5) else (a, None)
        for k in range(self.hold):
            applied = self.space.step(a) if pose is None else self.space.step(a, pose_action=pose)
            self._fix_heading(self.term)
            lower_adapter.apply_command(self.term, applied.cmd, applied.stand, self.lower.pose_active)
            action = self.lower.act(self.obs)
            self.obs, _reward, done, extras = self.env.step(action)
            self.lower.reset(done)
            self._note_terms(k == 0)
            _p, _q, vel, yaw = self._body()
            errs.append(lower_adapter.tracking_error(applied.cmd[:, :3], _np(vel), _np(yaw)))
            d = _np(done).astype(bool)
            collided |= self._collision_now()
            done_step[(done_step < 0) & d] = k
            done_any |= d
            t = (extras or {}).get("time_outs") if isinstance(extras, dict) else None
            if t is not None:
                timed |= _np(t).astype(bool) & d
        return self._state(applied, np.stack(errs), done_any, done_step, timed, collided)
