"""HiPAN 모드 2 상위 과제 상태 (설계 §3 N2): env 마다 방 · 시작 · 목표 · A* 경로 · PGCL 부목표 · v_des · 방문 격자 · 명령 이력.

한 과제 (시작 + 목표 + 경로) 는 PGCL 이 새 과제를 요청할 때까지 이어진다 (22 §4): 중간 수준은 같은 시작 · 목표로 부목표 간격만 늘려 다시 한다.
env 는 방 번호를 round robin 으로 받는다 (env i -> 방 i mod 방 수). 방 틀 좌표 (m, 방 모서리 기준) 로 일한다.
numpy 만 (Kit 없음). 에피소드를 실제로 되돌리는 일 (몸 놓기 · 관절 기본 자세) 은 `NavEnv.place` 몫이다.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from foothold_s2.nav import grade_map as gm
from foothold_s2.nav import gvd_astar, hl_rewards_term, pgcl, rewards_hl, teacher_maps, teacher_obs


@dataclass
class RoomAsset:
    room: object
    grade: gm.GradeMap
    voxels: teacher_maps.RoomVoxels


def make_asset(room, table: dict) -> RoomAsset:
    return RoomAsset(room, gm.make_grade_map(room, table), teacher_maps.RoomVoxels.from_room(room))


class NavTask:
    def __init__(self, assets: list, num_envs: int, rng: np.random.Generator, *, d0: float = 1.0, step: float = 1.0,
                 final_successes: int = 5, v_des_range=rewards_hl.V_DES_RANGE, min_task_m: float = 2.0, max_task_tries: int = 20, origin_xy=None):
        if not assets or num_envs < 1:
            raise ValueError("assets and num_envs are required")
        self.assets, self.n, self.rng = assets, int(num_envs), rng
        self.room_id = np.arange(self.n) % len(assets)
        self.pgcl = [pgcl.PGCL(d0, step, final_successes=final_successes) for _ in range(self.n)]
        self.start = np.zeros((self.n, 2)); self.goal = np.zeros((self.n, 2)); self.path = [None] * self.n
        self.v_des = np.zeros(self.n); self.v_des_range = v_des_range
        self.visit = rewards_hl.VisitGrid(self.n)
        self.cmd_prev = np.zeros((self.n, 3)); self.cmd_prev2 = np.zeros((self.n, 3))
        self.subgoal = np.zeros((self.n, 2))
        self.min_task_m, self.max_task_tries = min_task_m, max_task_tries
        self.voxels = {i: a.voxels for i, a in enumerate(assets)}
        self.origin_xy = origin_xy        # (n, 2) env 별 origins 열의 x y (방 틀). None = 방 가운데 (옛 꼴). 시작점 K 개 방은 이 값을 낸다

    # ---- 과제
    def _new_task(self, i: int) -> None:
        g = self.assets[self.room_id[i]].grade
        for _ in range(self.max_task_tries):
            s, t = gm.sample_free_points(g, self.rng, 2)
            if np.linalg.norm(s - t) < self.min_task_m:
                continue
            p = gvd_astar.find_path(g, s, t)
            if p.found:
                self.start[i], self.goal[i], self.path[i] = s, t, p.points
                return
        raise RuntimeError(f"env {i}: no start/goal with a path after {self.max_task_tries} tries")

    def reset_envs(self, env_ids) -> dict:
        """끝난 env (또는 처음 전부) 를 새 에피소드로. 돌려주는 값: 놓을 시작 위치 (k, 2) 방 틀 · yaw (k,) · 이번 에피소드의 PGCL 결과."""
        ids = np.atleast_1d(np.asarray(env_ids, dtype=int))
        outcome = []
        for i in ids:
            p = self.pgcl[i]
            outcome.append("fresh" if not p._sub else p.end_episode())
            if self.path[i] is None or p.needs_new_task:
                self._new_task(i)
                p.needs_new_task = False
            p.start_episode(self.path[i], self.assets[self.room_id[i]].grade)
            self.subgoal[i] = p.target.point
        self.v_des[ids] = rewards_hl.sample_v_des(self.rng, len(ids), self.v_des_range)
        self.visit.reset(ids)
        self.cmd_prev[ids] = 0.0; self.cmd_prev2[ids] = 0.0
        yaw = self.rng.uniform(-np.pi, np.pi, len(ids))
        return {"start_xy": self.start[ids].copy(), "yaw": yaw, "outcome": outcome}

    # ---- 매 상위 틱
    def step(self, state) -> dict:
        """상위 틱 하나가 끝난 `NavState` 로 보상 · 부목표 갱신. 돌려주는 값: reward (n,) · 항 dict · 관측 재료 · 이 틱 목표 도달 (n,)."""
        pos_room = teacher_obs.to_room_frame(state.pos_local, self.origin_xy)
        for i in range(self.n):
            tgt = self.pgcl[i].update(pos_room[i, :2])
            self.subgoal[i] = (self.goal[i] if tgt is None else tgt.point)
        eta = self.visit.visit(pos_room[:, :2])
        total, terms = hl_rewards_term.reward(
            state, pos_room_xy=pos_room[:, :2], subgoal_xy=self.subgoal, eta=eta, v_des=self.v_des,
            cmd_prev=self.cmd_prev, cmd_prev2=self.cmd_prev2)
        self.cmd_prev2 = self.cmd_prev.copy()
        self.cmd_prev = np.asarray(state.applied)[:, :3].copy()
        reached = np.array([p.all_reached for p in self.pgcl])
        return {"reward": total, "terms": terms, "subgoal": self.subgoal.copy(), "room_id": self.room_id.copy(),
                "task_reached": reached, "eta": eta}

    def observation(self, state) -> dict:
        """teacher 관측 (부목표는 보상 갱신 뒤의 값). `step` 뒤에 부른다."""
        return teacher_obs.build(self.voxels, self.room_id, state, self.cmd_prev, self.subgoal, origin_xy=self.origin_xy)
