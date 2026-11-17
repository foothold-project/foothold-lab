"""HiPAN 모드 2 상위 과제 상태 (설계 §3 N2): env 마다 방 · 시작 · 목표 · A* 경로 · PGCL 부목표 · v_des · 방문 격자 · 명령 이력.

한 과제 (시작 + 목표 + 경로) 는 PGCL 이 새 과제를 요청할 때까지 이어진다 (22 §4): 중간 수준은 같은 시작 · 목표로 부목표 간격만 늘려 다시 한다.
env 의 방 번호: 기본은 round robin (env i -> 방 i mod 방 수), 여러 방을 한 메시에 쓸 때는 Isaac 이 실제로 준 줄 (`terrain.terrain_levels`) 을
`set_rooms_from_rows` 로 넘긴다 (줄 = 방 번호). 방 틀 좌표 (m, 방 모서리 기준) 로 일한다. numpy 만 (Kit 없음).
시작 위치는 이 층이 정하지 않는다 (G1): Isaac reset 이 놓은 실제 몸 위치 (방 틀) 를 `reset_envs(start_xy=...)` 로 받아 그것을 시작으로 삼고 목표만 뽑는다.
시작 다양성은 방 시작점 K 개 열 (room_generator.start_points) 이 준다. 끝난 env 의 그 틱은 `step` 이 보상 · 방문 · PGCL 을 세지 않는다 (G2).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

from foothold_s2.nav import grade_map as gm
from foothold_s2.nav import room_generator as rg
from foothold_s2.nav import gvd_astar, hl_rewards_term, pgcl, rewards_hl, teacher_maps, teacher_obs


def room_frame_origin_xy(env_origins_xy, rows, pitch_m: float = rg.ROOM_M + rg.ROOM_GAP_M) -> np.ndarray:
    """여러 방 한 메시 (`room_generator.write_rooms`) 에서 env 원점 (메시 좌표 xy) -> 그 방 틀 (방 모서리 기준) 의 원점.
    빼는 값은 env 원점이 아니라 그 env 의 방 줄의 x 이동량 (줄 x pitch) 이다: 원점 자체는 방 틀에서 시작점이어야 하고 (몸 국소 위치 + 이 값 = 방 틀 위치),
    메시 좌표의 원점에서 줄 이동량만 걷어 낸다 (reviewer 03:35 주의 · runner 5baa59d4)."""
    o = np.array(env_origins_xy, dtype=np.float64, copy=True).reshape(-1, 2)
    o[:, 0] -= np.asarray(rows, dtype=np.float64).reshape(-1) * float(pitch_m)
    return o


@dataclass
class RoomAsset:
    room: object
    grade: gm.GradeMap
    voxels: teacher_maps.RoomVoxels


def make_asset(room, table: dict) -> RoomAsset:
    return RoomAsset(room, gm.make_grade_map(room, table), teacher_maps.RoomVoxels.from_room(room))


class NavTask:
    def __init__(self, assets: list, num_envs: int, rng: np.random.Generator, *, d0: float = 1.0, step: float = 1.0,
                 final_successes: int = 5, v_des_range=rewards_hl.V_DES_RANGE, min_task_m: float = 2.0, max_task_tries: int = 20, origin_xy=None,
                 room_rows=None, straighten: bool = True, path_range_m=(4.0, 25.0), winding_frac: float = 0.5, winding_min: float = 1.2, goal_candidates: int = 8):
        if not assets or num_envs < 1:
            raise ValueError("assets and num_envs are required")
        self.assets, self.n, self.rng = assets, int(num_envs), rng
        self.room_id = np.arange(self.n) % len(assets)
        if room_rows is not None:
            self.set_rooms_from_rows(room_rows)
        self.pgcl = [pgcl.PGCL(d0, step, final_successes=final_successes) for _ in range(self.n)]
        self.start = np.zeros((self.n, 2)); self.goal = np.zeros((self.n, 2)); self.path = [None] * self.n
        self.v_des = np.zeros(self.n); self.v_des_range = v_des_range
        self.visit = rewards_hl.VisitGrid(self.n)
        self.cmd_prev = np.zeros((self.n, 3)); self.cmd_prev2 = np.zeros((self.n, 3))
        self.subgoal = np.zeros((self.n, 2))
        self.min_task_m, self.max_task_tries = min_task_m, max_task_tries
        # 방 설계 (DESIGN-HIPAN-ROOMS-1117 3.3): 목표는 경로 길이로 뽑고 (path_range_m) 과제의 winding_frac 는 굴곡 비 (경로 / 직선) winding_min 이상인 쌍에서 뽑는다.
        # goal_candidates 개를 뽑아 길을 내 보고 조건에 맞는 것을 고른다. 맞는 것이 없으면 (좁은 방 · 시작이 구석) 길이만 맞는 것 · 그것도 없으면 옛 꼴 (직선 min_task_m 이상) 로 물러선다.
        self.straighten, self.path_range_m = bool(straighten), tuple(path_range_m)
        self.table = None; self.table_tol_m = 0.3; self.table_sha256 = None; self.task_table_hits = 0; self.task_table_miss = 0   # 시작 · 목표 · 경로 표 (build_table): 학습 중에는 표에서 뽑는다
        self.winding_frac, self.winding_min, self.goal_candidates = float(winding_frac), float(winding_min), int(goal_candidates)
        self.task_new = 0                 # 새로 뽑은 과제 수 (누적)
        self.task_winding = 0             # 그 가운데 굴곡 비 winding_min 이상 (누적)
        self.task_relaxed = 0             # 목표 조건 (경로 길이 범위) 을 못 맞춰 옛 꼴로 물러선 수 (누적)
        self.ratio_edges = (1.1, 1.2, 1.5, 2.0)
        self.ratio_hist = np.zeros(len(self.ratio_edges) + 1, dtype=np.int64)       # 뽑힌 쌍의 굴곡 비 분포: <1.1 · 1.1~1.2 · 1.2~1.5 · 1.5~2 · 2 이상
        self.task_fallbacks = 0           # 실제 시작에서 길을 못 찾아 새 쌍으로 대신한 횟수 (누적)
        self.voxels = {i: a.voxels for i, a in enumerate(assets)}
        self.origin_xy = origin_xy        # (n, 2) env 별 origins 열의 x y (방 틀). None = 방 가운데 (옛 꼴). 시작점 K 개 방은 이 값을 낸다

    def set_rooms_from_rows(self, rows, env_origins_xy=None, pitch_m: float = rg.ROOM_M + rg.ROOM_GAP_M) -> None:
        """env 의 방 번호를 Isaac 이 준 줄 (`terrain.terrain_levels`, 줄 = 방) 에서 읽는다 (G3). 바뀐 env 는 새 과제를 뽑는다. 줄이 방 수 밖이면 거절."""
        rows = np.asarray(rows, dtype=int).reshape(-1)
        if rows.shape[0] != self.n or rows.min() < 0 or rows.max() >= len(self.assets):
            raise ValueError(f"room rows must be {self.n} values in 0..{len(self.assets) - 1}")
        changed = rows != self.room_id if hasattr(self, "path") else np.zeros(self.n, bool)
        self.room_id = rows.copy()
        for i in np.flatnonzero(changed):
            self.path[i] = None
        if env_origins_xy is not None:      # 여러 방 한 메시: 몸 국소 위치 + origin_xy = 방 틀 위치 (줄 x 이동량을 걷어 낸 원점)
            self.origin_xy = room_frame_origin_xy(env_origins_xy, rows, pitch_m)

    # ---- 과제
    def _plan(self, i: int, s, t):
        """s -> t 길 (없거나 s · t 가 막힌 칸이면 None)."""
        try:
            p = gvd_astar.find_path(self.assets[self.room_id[i]].grade, s, t, straighten=self.straighten)
        except ValueError:
            return None
        return p.points if p.found else None

    @staticmethod
    def _length(pts) -> float:
        return float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())

    def _pick_goal(self, i: int, s, g):
        """시작 s 에서 목표 하나: (목표, 길) 또는 None. 경로 길이 path_range_m 안에서 · 과제의 winding_frac 는 굴곡 비 winding_min 이상에서."""
        lo, hi = self.path_range_m
        want_wind = self.rng.random() < self.winding_frac
        ok, wound = [], []
        for t in gm.sample_free_points(g, self.rng, self.goal_candidates):
            straight = float(np.linalg.norm(s - t))
            if straight < self.min_task_m:
                continue
            pts = self._plan(i, s, t)
            if pts is None:
                continue
            L = self._length(pts)
            if not (lo <= L <= hi):
                continue
            (wound if L / straight >= self.winding_min else ok).append((t, pts))
        pool = (wound or ok) if want_wind else (ok + wound)
        if not pool:
            return None
        return pool[int(self.rng.integers(len(pool)))]

    # ---- 시작 · 목표 · 경로 표 (G3 Pod 실측: 새 과제 1 개 = 경로 계산 8 번 · 학습 중에도 도달 · 넘어짐마다 계속 뽑혀 CPU 한 코어에 묶였다)
    def build_table(self, starts_by_room, per_start: int = 32, tol_m: float = 0.3, seed: int = 0, log=None) -> str:
        """방마다 시작점 (K, 2 · 방 틀 m) 마다 목표 후보 per_start 개를 `_pick_goal` 과 같은 규칙으로 걸러 (직선 min_task_m 이상 · 경로 있음 · 길이 path_range_m 안)
        굴곡 (경로 / 직선 >= winding_min) 쌍과 그렇지 않은 쌍으로 나눠 둔다. 뽑을 때 (`_new_task`) 는 `_pick_goal` 과 같은 규칙 (굴곡 쌍 절반 시도 · 없으면 아무 쌍) 으로 표에서만 고른다.
        시작이 표의 어느 시작점에서도 tol_m 보다 멀면 (표가 모르는 자리) 옛 꼴로 직접 길을 낸다. 돌려주는 값 = 표 sha256 (영수증 · 로그용)."""
        rng = np.random.default_rng(int(seed) + 7919)
        lo, hi = self.path_range_m
        self.table, h = [], hashlib.sha256()
        for r, asset in enumerate(self.assets):
            starts = np.asarray(starts_by_room[r], float).reshape(-1, 2)
            g = asset.grade
            rows = []
            for s in starts:
                ok, wound = [], []
                for t in gm.sample_free_points(g, rng, int(per_start)):
                    straight = float(np.linalg.norm(s - t))
                    if straight < self.min_task_m:
                        continue
                    try:
                        pp = gvd_astar.find_path(g, s, t, straighten=self.straighten)
                    except ValueError:
                        continue
                    if not pp.found:
                        continue
                    L = self._length(pp.points)
                    if not (lo <= L <= hi):
                        continue
                    (wound if L / straight >= self.winding_min else ok).append((np.asarray(t, float), pp.points))
                rows.append({"ok": ok, "wound": wound})
                for t, pts in ok + wound:
                    h.update(t.tobytes()); h.update(np.float64(self._length(pts)).tobytes())
            self.table.append({"starts": starts, "rows": rows})
            if log:
                log(f"task table room {r}: starts {len(starts)} ok {sum(len(x['ok']) for x in rows)} wound {sum(len(x['wound']) for x in rows)}")
        self.table_tol_m, self.table_sha256 = float(tol_m), h.hexdigest()
        return self.table_sha256

    def _table_pick(self, i: int, s):
        if self.table is None:
            return None
        tb = self.table[self.room_id[i]]
        d = np.linalg.norm(tb["starts"] - np.asarray(s, float), axis=1)
        k = int(d.argmin())
        if d[k] > self.table_tol_m:
            self.task_table_miss += 1
            return None
        row = tb["rows"][k]
        want_wind = self.rng.random() < self.winding_frac
        pool = (row["wound"] or row["ok"]) if want_wind else (row["ok"] or row["wound"])      # 표: 굴곡 아닌 쪽 뽑기는 굴곡 아닌 쌍만 (굴곡 비율 = winding_frac)
        if not pool:
            self.task_table_miss += 1
            return None
        t, pts = pool[int(self.rng.integers(len(pool)))]
        pts = pts.copy(); pts[0] = np.asarray(s, float)                    # 몸이 실제로 선 자리에서 출발
        self.task_table_hits += 1
        return t.copy(), pts

    def _note_task(self, i: int) -> None:
        s, t, pts = self.start[i], self.goal[i], self.path[i]
        straight = float(np.linalg.norm(s - t))
        r = self._length(pts) / max(straight, 1e-6)
        self.task_new += 1
        self.task_winding += int(r >= self.winding_min)
        self.ratio_hist[int(np.searchsorted(self.ratio_edges, r, side="right"))] += 1

    def _new_task(self, i: int, start=None) -> None:
        """start 가 주어지면 (실제 몸 위치) 그것이 시작이고 목표만 뽑는다. 없으면 시작 · 목표를 둘 다 뽑는다 (옛 꼴 · 시험용)."""
        g = self.assets[self.room_id[i]].grade
        if start is not None:
            got = self._table_pick(i, np.asarray(start, float))
            if got is not None:
                self.start[i], self.goal[i], self.path[i] = np.asarray(start, float), got[0], got[1]
                self._note_task(i)
                return
        for _ in range(self.max_task_tries):
            s = gm.sample_free_points(g, self.rng, 1)[0] if start is None else np.asarray(start, float)
            got = self._pick_goal(i, s, g)
            if got is not None:
                self.start[i], self.goal[i], self.path[i] = s, got[0], got[1]
                self._note_task(i)
                return
        self.task_relaxed += 1
        for _ in range(self.max_task_tries):
            if start is None:
                s, t = gm.sample_free_points(g, self.rng, 2)
            else:
                s, t = np.asarray(start, float), gm.sample_free_points(g, self.rng, 1)[0]
            if np.linalg.norm(s - t) < self.min_task_m:
                continue
            pts = self._plan(i, s, t)
            if pts is not None:
                self.start[i], self.goal[i], self.path[i] = s, t, pts
                self._note_task(i)
                return
        if start is None:
            raise RuntimeError(f"env {i}: no start/goal with a path after {self.max_task_tries} tries")
        # 실제 몸 위치가 길 없는 칸 (막힌 칸 · 갇힌 칸) 이면 학습을 죽이지 않는다 (G3 첫 Pod: 방 6 개 · env 1024 에서 시작점 몇 개가 이래서 229 초에 죽음).
        # 대신 시작 · 목표를 둘 다 새로 뽑은 쌍으로 쓰고 (몸은 그 길의 시작에 있지 않다) 세어 둔다: task_fallbacks.
        self.task_fallbacks += 1
        for _ in range(200):
            s, t = gm.sample_free_points(g, self.rng, 2)
            if np.linalg.norm(s - t) < self.min_task_m:
                continue
            pts = self._plan(i, s, t)
            if pts is not None:
                self.start[i], self.goal[i], self.path[i] = s, t, pts
                self._note_task(i)
                return
        raise RuntimeError(f"env {i}: no start/goal with a path even for a free pair")

    def reset_envs(self, env_ids, start_xy=None) -> dict:
        """끝난 env (또는 처음 전부) 를 새 에피소드로. `start_xy` (k, 2) = Isaac reset 뒤 실제 몸 위치 (방 틀): 그것이 이 에피소드의 시작 (G1).
        과제를 이어 쓰는 env (PGCL 이 새 과제를 요청하지 않음) 는 목표를 그대로 두고 실제 시작에서 길을 다시 낸다 (길이 없으면 새 과제).
        start_xy 가 없으면 옛 꼴 (시작도 이 층이 뽑음 · 시험용). 돌려주는 값: 시작 (k, 2) · yaw (k,) (옛 꼴 호환, 놓기에는 쓰지 않음) · 이번 에피소드의 PGCL 결과."""
        ids = np.atleast_1d(np.asarray(env_ids, dtype=int))
        if start_xy is not None:
            start_xy = np.asarray(start_xy, float).reshape(len(ids), 2)
        outcome = []
        for j, i in enumerate(ids):
            p = self.pgcl[i]
            outcome.append("fresh" if not p._sub else p.end_episode())
            s = None if start_xy is None else start_xy[j]
            if self.path[i] is None or p.needs_new_task:
                self._new_task(i, s)
                p.needs_new_task = False
            elif s is not None:
                pts = self._plan(i, s, self.goal[i])
                if pts is None:
                    self._new_task(i, s)
                else:
                    self.start[i], self.path[i] = s, pts
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
        done = np.asarray(getattr(state, "done", np.zeros(self.n, bool)), bool)
        # G2: 윈도 안에서 끝난 env 의 몸 상태는 이미 되돌려진 새 에피소드의 값이다. 그 틱은 PGCL · 방문 격자를 건드리지 않고
        # 보상은 충돌 (r10, 윈도 안에서 센 값) 만 남기고 나머지 항은 0 (planner 권고 (2)). 호출한 쪽이 곧바로 reset_envs 를 부른다.
        # 알려진 두 가지 (reviewer 02:52 권고, 막지 않음): (1) 끝난 틱에는 r9 (명령 제한) 도 0 이고 넘어짐 · 시간 초과 자체에는 상위 보상 벌점 항이 없다:
        # 「벌점 없는 에피소드 끝」 이 논문 (HiPAN) 의도인지는 논문 종료 벌점 유무를 대조해야 한다 (미확인, 첫 Kit 로그 뒤 결정).
        # (2) 같은 윈도 안에서 마지막 부목표에 닿은 뒤 넘어지면 task_reached 에서 빠진다 (done 이 이긴다). done_step 이전 하위 스텝으로 판정하면 살릴 수 있다: 빈도를 보고 정한다.
        for i in range(self.n):
            if done[i]:
                continue
            tgt = self.pgcl[i].update(pos_room[i, :2])
            self.subgoal[i] = (self.goal[i] if tgt is None else tgt.point)
        eta = self.visit.visit(pos_room[:, :2], active=~done)
        total, terms = hl_rewards_term.reward(
            state, pos_room_xy=pos_room[:, :2], subgoal_xy=self.subgoal, eta=eta, v_des=self.v_des,
            cmd_prev=self.cmd_prev, cmd_prev2=self.cmd_prev2)
        if done.any():
            terms = {k: (np.where(done, v if k == "r10" else 0.0, v)) for k, v in terms.items()}
            total = sum(terms.values())
        self.cmd_prev2 = self.cmd_prev.copy()
        self.cmd_prev = np.asarray(state.applied)[:, :3].copy()
        reached = np.array([p.all_reached for p in self.pgcl]) & ~done
        return {"reward": total, "terms": terms, "subgoal": self.subgoal.copy(), "room_id": self.room_id.copy(),
                "task_reached": reached, "eta": eta, "done": done}

    def observation(self, state) -> dict:
        """teacher 관측 (부목표는 보상 갱신 뒤의 값). `step` 뒤에 부른다."""
        return teacher_obs.build(self.voxels, self.room_id, state, self.cmd_prev, self.subgoal, origin_xy=self.origin_xy)
