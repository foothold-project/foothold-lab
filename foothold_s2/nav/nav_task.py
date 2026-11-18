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


LV_KEYS = ("l1", "l2", "l3p")        # 회차 행의 수준별 칸 접미사 (PGCL 수준 1 · 2 · 3 이상)


def _lv_key(level: int) -> str:
    return LV_KEYS[min(max(int(level), 1), 3) - 1]


SAME_START_M = 0.05                  # 리셋 뒤 몸이 과제 시작 자리에서 이만큼 안이면 같은 과제를 그대로 (길을 다시 내지 않음)
EPISODE_SPEED_MPS, EPISODE_EXTRA_S = 0.3, 10.0   # 에피소드 길이 = 경로 길이 / 0.3 + 10 초 (planner 03:57 가정)

class NavTask:
    def __init__(self, assets: list, num_envs: int, rng: np.random.Generator, *, d0: float = 1.0, step: float = 1.0,
                 final_successes: int = 5, v_des_range=rewards_hl.V_DES_RANGE, min_task_m: float = 2.0, max_task_tries: int = 20, origin_xy=None,
                 room_rows=None, straighten: bool = True, path_range_m=(4.0, 25.0), winding_frac: float = 0.5, winding_min: float = 1.2, goal_candidates: int = 8,
                 reach_m: float = pgcl.REACH_M):
        if not assets or num_envs < 1:
            raise ValueError("assets and num_envs are required")
        self.assets, self.n, self.rng = assets, int(num_envs), rng
        self.room_id = np.arange(self.n) % len(assets)
        if room_rows is not None:
            self.set_rooms_from_rows(room_rows)
        self.reach_m = float(reach_m)     # 부목표 도달 반경 (기본 pgcl.REACH_M = 논문 0.1 m · 바꾸면 논문 밖: PGCL 도달 판정과 r1 의 arrive 가 같은 값)
        self.pgcl = [pgcl.PGCL(d0, step, reach_m=self.reach_m, final_successes=final_successes) for _ in range(self.n)]
        self._dmin = np.full(self.n, np.inf)   # env 별: 지금 부목표까지 이 에피소드에서 가장 가까웠던 거리 (부목표가 바뀌면 다시)
        self.start = np.zeros((self.n, 2)); self.goal = np.zeros((self.n, 2)); self.path = [None] * self.n
        self.v_des = np.zeros(self.n); self.v_des_range = v_des_range
        self.visit = rewards_hl.VisitGrid(self.n)
        self.visit_reset = "episode"      # "task" (--visit-reset task) = 방문 격자 (η) 를 새 과제를 뽑을 때만 비움 (같은 과제를 PGCL 이 유지하는 동안 쌓임) · 기본 "episode" = 에피소드마다 비움 (지금과 같음 · 논문 미기재)
        self._fresh_task: set = set()     # 이번 reset 에서 새 과제가 뽑힌 env (visit_reset == "task" 일 때 격자를 비울 대상)
        self.cmd_prev = np.zeros((self.n, 3)); self.cmd_prev2 = np.zeros((self.n, 3))
        self.subgoal = np.zeros((self.n, 2))
        self.min_task_m, self.max_task_tries = min_task_m, max_task_tries
        # 방 설계 (DESIGN-HIPAN-ROOMS-1117 3.3): 목표는 경로 길이로 뽑고 (path_range_m) 과제의 winding_frac 는 굴곡 비 (경로 / 직선) winding_min 이상인 쌍에서 뽑는다.
        # goal_candidates 개를 뽑아 길을 내 보고 조건에 맞는 것을 고른다. 맞는 것이 없으면 (좁은 방 · 시작이 구석) 길이만 맞는 것 · 그것도 없으면 옛 꼴 (직선 min_task_m 이상) 로 물러선다.
        self.straighten, self.path_range_m = bool(straighten), tuple(path_range_m)
        self.table = None; self.table_tol_m = 0.75; self.table_sha256 = None; self.task_table_hits = 0; self.task_table_miss = 0; self.task_redraw_on_reset = 0   # 시작 · 목표 · 경로 표 (build_table): 학습 중에는 표에서 뽑는다
        self.winding_frac, self.winding_min, self.goal_candidates = float(winding_frac), float(winding_min), int(goal_candidates)
        self.task_new = 0                 # 새로 뽑은 과제 수 (누적)
        self.task_winding = 0             # 그 가운데 굴곡 비 winding_min 이상 (누적)
        self.task_relaxed = 0             # 목표 조건 (경로 길이 범위) 을 못 맞춰 옛 꼴로 물러선 수 (누적)
        self.ratio_edges = (1.1, 1.2, 1.5, 2.0)
        self.ratio_hist = np.zeros(len(self.ratio_edges) + 1, dtype=np.int64)       # 뽑힌 쌍의 굴곡 비 분포: <1.1 · 1.1~1.2 · 1.2~1.5 · 1.5~2 · 2 이상
        # 논문 밖 덧붙임 (r_shape, planner 06:47): 틱 보상 = w x (앞 틱 남은 경로 길이 - 지금), 틱당 +-shape_clip 로 자름. 남은 길이 = 지금 부목표까지 직선 + 그 부목표에서 목표까지 경로 (부목표 이음).
        # shape_w 0 (기본) = 끔. 수준 2 이상 env 는 0. 수준 2 이상 env 비율이 shape_start_frac 을 넘으면 (회차 평균) 그 뒤 shape_decay_iters 회에 걸쳐 w 가 0 으로.
        self.shape_w, self.shape_clip, self.shape_start_frac, self.shape_decay_iters = 0.0, 0.5, 0.10, 100
        self.shape_scale, self._shape_decay_on, self._tail = 1.0, False, {}
        self.shape_all_levels = False      # True (--shape-levels all) = 수준 2 이상 env 에도 r_shape (기본 False = 수준 1 만, 지금과 같음)
        self.shape_decay = True            # False (--shape-decay off) = 배율 1.0 고정 (감쇠 안 함 · 기본 True = 지금과 같음)
        self.redraw_on_fall = False       # True = 넘어진 뒤 (과제를 못 끝냄) 에도 표에서 새 과제 · False (기본, 논문 IV-C2) = 같은 과제 유지: 새 과제는 PGCL 이 요청할 때만
        self.tick_s = None                # 상위 틱 한 번의 초 (hold x step_dt). 호출한 쪽이 넣는다. None = 에피소드 길이는 틱 수로만
        self._st = None                   # 회차 통계 합 (take_stats 가 읽고 비운다)
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
    def build_table(self, starts_by_room, per_start: int = 32, tol_m: float = 0.75, seed: int = 0, log=None) -> str:
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

    def episode_seconds(self, env_ids=None, speed_mps: float = EPISODE_SPEED_MPS, extra_s: float = EPISODE_EXTRA_S):
        """env 별 에피소드 최대 길이 (초) = 과제 경로 길이 / speed + extra (논문에 없음: 우리 가정). 길이를 못 재면 고정 90 초."""
        ids = range(self.n) if env_ids is None else np.atleast_1d(env_ids)
        out = []
        for i in ids:
            pts = self.path[int(i)]
            out.append(90.0 if pts is None else self._length(pts) / speed_mps + extra_s)
        return np.array(out)

    def _table_same_goal(self, i: int, s):
        """표의 가장 가까운 시작점 줄에서 지금 목표와 같은 목표의 길 (없으면 None). 같은 과제 재도전 때 A* 를 안 돌리려고."""
        tb = self.table[self.room_id[i]]
        d = np.linalg.norm(tb["starts"] - np.asarray(s, float), axis=1)
        k = int(d.argmin())
        if d[k] > self.table_tol_m:
            return None
        for t, pts in tb["rows"][k]["ok"] + tb["rows"][k]["wound"]:
            if np.allclose(t, self.goal[i], atol=1e-9):
                pts = pts.copy(); pts[0] = np.asarray(s, float)
                self.task_table_hits += 1
                return pts
        return None

    # ---- 회차 통계 (읽기 전용: 학습에 쓰이지 않는다)
    def _stat(self):
        if self._st is None:
            self._st = {"ticks": 0, "sub_reached": 0, "lvl": np.zeros(3), "r": {}, "vcmd": 0.0, "vbody": 0.0, "stand": 0.0,
                        "eps": 0, "cos": 0.0, "cos_n": 0, "cosd": 0.0, "cosd_n": 0, "yerr": 0.0, "yok": 0, "yn": 0, "prog": 0.0, "dsub0": 0.0, "dsub1": 0.0, "plen": 0.0, "ep_ticks": 0.0,
                        "out": {"hold": 0, "level_up": 0, "final_success": 0, "new_task": 0},
                        "lv": {k: np.zeros(7) for k in LV_KEYS}}     # 수준별 (l1 · l2 · l3p): [eps, prog, dend, succ, sub_reached, cos, cos_n]
        if getattr(self, "_ep_n", None) is None:
            self._ep_n = np.zeros(self.n, dtype=np.int64)
            self._pos_prev = np.full((self.n, 2), np.nan)
        return self._st

    def _note_episode_end(self, i, p) -> None:
        st = self._stat()
        if not p._sub:
            return
        st["eps"] += 1
        if not p.all_reached and np.isfinite(self._dmin[i]):
            st.setdefault("dmin", []).append(float(self._dmin[i]))     # 끝까지 못 닿은 에피소드의 마지막 부목표 최소 거리
        self._dmin[i] = np.inf
        st["prog"] += p._i / len(p._sub)
        tgt = p._sub[min(p._i, len(p._sub) - 1)].point
        lv = st["lv"][_lv_key(p.level)]
        lv[0] += 1; lv[1] += p._i / len(p._sub); lv[3] += float(p.all_reached)
        if not np.isnan(self._pos_prev[i, 0]):
            st["dsub1"] += float(np.linalg.norm(self._pos_prev[i] - np.asarray(tgt)))
            lv[2] += float(np.linalg.norm(self._pos_prev[i] - np.asarray(tgt)))
        st["ep_ticks"] += float(self._ep_n[i])

    def _note_outcome(self, name: str) -> None:
        out = self._stat()["out"]
        if name in out:
            out[name] += 1

    def _note_episode_start(self, i, p, s) -> None:
        st = self._stat()
        self._ep_n[i] = 0
        self._pos_prev[i] = np.nan if s is None else np.asarray(s, float)
        st["dsub0"] += float(np.linalg.norm(np.asarray(s if s is not None else self.start[i]) - p.target.point))
        st["plen"] += self._length(self.path[i])

    def take_stats(self) -> dict:
        """이번 회차의 통계 (nv_ 접두): 부목표 도달 수 · 에피소드 끝 진행 비 · PGCL 수준 분포 · 끝 결과 수 · 보상 항 평균 · 속도 · 서 있는 비율 · 부목표 거리 · 경로 길이 · 에피소드 길이. 읽고 비운다."""
        st = self._stat()
        if st["ticks"] == 0 and st["eps"] == 0:
            return {}
        t, e = max(st["ticks"], 1), max(st["eps"], 1)
        out = {"nv_sub_reached": st["sub_reached"], "nv_episodes": st["eps"], "nv_progress_end": st["prog"] / e,
               "nv_lvl1": st["lvl"][0] / t, "nv_lvl2": st["lvl"][1] / t, "nv_lvl3p": st["lvl"][2] / t,
               "nv_v_cmd": st["vcmd"] / t, "nv_v_body": st["vbody"] / t, "nv_stand_frac": st["stand"] / t,
               "nv_dsub_start": st["dsub0"] / e, "nv_dsub_end": st["dsub1"] / e, "nv_path_len": st["plen"] / e}
        out.update({f"nv_out_{k}": v for k, v in st["out"].items()})
        out.update({f"nv_{k}": v / t for k, v in st["r"].items()})
        for k in ("r1", "r2"):
            if k in st["r"]:
                out[f"nv_{k}_sum"] = st["r"][k]          # 회차 안 틱마다 env 평균 보상의 합 (nv_r1 · nv_r2 는 그 합 / 틱 수)
        out["nv_ep_ticks"] = st["ep_ticks"] / e
        out["nv_cos_vel_sub"] = st["cos"] / st["cos_n"] if st["cos_n"] else 0.0
        out["nv_cos_n"] = st["cos_n"]
        out["nv_cos_disp"] = st["cosd"] / st["cosd_n"] if st["cosd_n"] else 0.0         # 틱 사이 위치 변화 방향과 부목표 방향의 cos (yaw 안 씀)
        out["nv_cos_disp_n"] = st["cosd_n"]
        out["nv_yaw_err_deg"] = st["yerr"] / st["yn"] if st["yn"] else -1.0            # 해석 yaw 대 (위치 변화 방향 - 몸 속도 방향) 의 절대 차 평균 (도). 쿼터니언 순서가 맞으면 작다
        out["nv_yaw_ok_frac"] = st["yok"] / st["yn"] if st["yn"] else -1.0             # 그 차가 30 도 안인 비율
        out["nv_yaw_n"] = st["yn"]
        for k, (n_e, prog, dend, succ, subr, cos, cos_n) in ((k, st["lv"][k]) for k in LV_KEYS):   # 수준별 (읽기만): 에피소드가 없으면 -1
            out[f"nv_eps_{k}"] = int(n_e); out[f"nv_sub_reached_{k}"] = int(subr); out[f"nv_cos_n_{k}"] = int(cos_n)
            out[f"nv_prog_{k}"] = prog / n_e if n_e else -1.0
            out[f"nv_dend_{k}"] = dend / n_e if n_e else -1.0
            out[f"nv_succ_{k}"] = succ / n_e if n_e else -1.0
            out[f"nv_cos_{k}"] = cos / cos_n if cos_n else -1.0
        out["nv_dsub_min"] = float(np.median(st["dmin"])) if st.get("dmin") else -1.0      # 에피소드마다 (끝까지 못 닿은 것) 지금 부목표까지 최소 거리의 중앙값 · -1 = 해당 에피소드 없음
        if self.shape_w:
            out["nv_shape_scale"] = self.shape_scale
            if not self._shape_decay_on and (st["lvl"][1] + st["lvl"][2]) / t > self.shape_start_frac:
                self._shape_decay_on = True
            if self._shape_decay_on and self.shape_decay:
                self.shape_scale = max(0.0, self.shape_scale - 1.0 / self.shape_decay_iters)
        if self.tick_s:
            out["nv_ep_s"] = st["ep_ticks"] * self.tick_s / e
        self._st = None
        return out

    def _note_task(self, i: int) -> None:
        s, t, pts = self.start[i], self.goal[i], self.path[i]
        straight = float(np.linalg.norm(s - t))
        r = self._length(pts) / max(straight, 1e-6)
        self.task_new += 1
        self._fresh_task.add(int(i))
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
            self._note_episode_end(i, p)
            outcome.append("fresh" if not p._sub else p.end_episode())
            self._note_outcome(outcome[-1])
            s = None if start_xy is None else start_xy[j]
            if self.path[i] is None or p.needs_new_task:
                self._new_task(i, s)
                p.needs_new_task = False
            elif s is not None and self.table is not None and self.redraw_on_fall:
                self.task_redraw_on_reset += 1                              # 표가 있으면 넘어진 뒤에도 표에서 새 과제 (같은 목표로 다시 A* 를 돌리지 않는다)
                self._new_task(i, s)
            elif s is not None and np.linalg.norm(np.asarray(s, float) - self.start[i]) <= SAME_START_M:
                pass                                                        # 같은 과제를 그 시작 자리에서 다시 (리셋 때 몸이 시작 자리로 돌아온다): 길 · 목표 그대로
            elif s is not None:
                pts = self._table_same_goal(i, s) if self.table is not None else None      # 같은 목표 재도전: 표에 그 목표의 길이 있으면 그것 (A* 없음)
                if pts is None:
                    pts = self._plan(i, s, self.goal[i])
                if pts is None:
                    self._new_task(i, s)
                else:
                    self.start[i], self.path[i] = s, pts
            p.start_episode(self.path[i], self.assets[self.room_id[i]].grade)
            self.subgoal[i] = p.target.point
            self._note_episode_start(i, p, s)
        self.v_des[ids] = rewards_hl.sample_v_des(self.rng, len(ids), self.v_des_range)
        if self.visit_reset == "task":
            self.visit.reset([int(i) for i in np.atleast_1d(ids) if int(i) in self._fresh_task])
        else:
            self.visit.reset(ids)
        self._fresh_task.difference_update(int(i) for i in np.atleast_1d(ids))
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
        st = self._stat()
        i_before = np.array([p._i for p in self.pgcl])
        i0 = sum(p._i for p, d in zip(self.pgcl, done) if not d)
        for i in range(self.n):
            if done[i]:
                continue
            tgt = self.pgcl[i].update(pos_room[i, :2])
            self.subgoal[i] = (self.goal[i] if tgt is None else tgt.point)
        st["sub_reached"] += sum(p._i for p, d in zip(self.pgcl, done) if not d) - i0
        for i in range(self.n):                                          # nv_dsub_min 재료: 지금 부목표까지 가장 가까웠던 거리 (부목표가 넘어가면 다시 잰다)
            if done[i] or self.pgcl[i].target is None:
                continue
            if self.pgcl[i]._i != i_before[i]:
                self._dmin[i] = np.inf
            self._dmin[i] = min(self._dmin[i], float(np.linalg.norm(pos_room[i, :2] - np.asarray(self.pgcl[i].target.point))))
        eta = self.visit.visit(pos_room[:, :2], active=~done)
        total, terms = hl_rewards_term.reward(
            state, pos_room_xy=pos_room[:, :2], subgoal_xy=self.subgoal, eta=eta, v_des=self.v_des,
            cmd_prev=self.cmd_prev, cmd_prev2=self.cmd_prev2, arrive_m=self.reach_m)
        # r1 (부목표 도달): update 가 부목표를 넘긴 뒤 바뀐 subgoal 로 재면 닿은 틱에 이미 다음 부목표를 봐서 늘 0 이었다 (G3 nv_r1 = 0). 넘긴 개수 (한 틱에 둘이면 2) 를 직접 준다.
        passed = np.array([p._i for p in self.pgcl]) - i_before
        terms = dict(terms)
        terms["r1"] = rewards_hl.WEIGHTS["r1"] * passed.astype(np.float64)
        for i in np.nonzero(passed)[0]:
            st["lv"][_lv_key(self.pgcl[i].level)][4] += int(passed[i])
        if self.shape_w:
            terms["r_shape"] = self._shape_reward(pos_room[:, :2], i_now=np.array([p._i for p in self.pgcl]))
        total = sum(terms.values())
        if done.any():
            terms = {k: (np.where(done, v if k == "r10" else 0.0, v)) for k, v in terms.items()}
            total = sum(terms.values())
        self.cmd_prev2 = self.cmd_prev.copy()
        self.cmd_prev = np.asarray(state.applied)[:, :3].copy()
        reached = np.array([p.all_reached for p in self.pgcl]) & ~done
        self._quat0 = np.asarray(state.quat_w)[0]
        self._note_cos(state, pos_room[:, :2], done)
        self._note_tick(state, pos_room[:, :2], terms, done)
        return {"reward": total, "terms": terms, "subgoal": self.subgoal.copy(), "room_id": self.room_id.copy(),
                "task_reached": reached, "eta": eta, "done": done}

    def _tail_len(self, i) -> np.ndarray:
        """env i 의 부목표 k 에서 목표까지 이음 길이 (k = 0 .. len, 마지막은 0). 부목표 목록이 바뀌면 다시 만든다."""
        sub = self.pgcl[i]._sub
        hit = self._tail.get(i)
        if hit is None or hit[0] is not sub:
            pts = np.array([np.asarray(q.point, float) for q in sub] + [np.asarray(self.goal[i], float)])
            seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
            tail = np.concatenate([np.cumsum(seg[::-1])[::-1], [0.0]])             # tail[k] = k 번째 부목표 (len 이면 목표) 에서 목표까지
            hit = self._tail[i] = (sub, pts, tail)
        return hit

    def _remaining(self, i, xy, k) -> float:
        """xy 에서 k 번째 부목표 (k >= len 이면 목표) 로 직선 + 거기서 목표까지 이음 길이."""
        _sub, pts, tail = self._tail_len(i)
        return float(np.linalg.norm(np.asarray(xy, float) - pts[min(k, len(pts) - 1)]) + tail[min(k, len(pts) - 1)])

    def _shape_reward(self, pos_xy, i_now) -> np.ndarray:
        """w x (앞 틱 - 지금 남은 길이). 둘 다 지금 부목표 번호로 재서 부목표를 넘는 틱에도 값이 안 튄다. 첫 틱 (앞 위치 없음) 0, 수준 2 이상 env 0 (shape_all_levels 가 True 이면 수준 2 이상도 같은 식)."""
        out = np.zeros(self.n)
        prev = self._pos_prev
        for i in range(self.n):
            if (self.pgcl[i].level >= 2 and not self.shape_all_levels) or not self.pgcl[i]._sub or np.isnan(prev[i, 0]):
                continue
            out[i] = self._remaining(i, prev[i], int(i_now[i])) - self._remaining(i, pos_xy[i], int(i_now[i]))
        return np.clip(self.shape_w * out, -self.shape_clip, self.shape_clip) * self.shape_scale

    def _note_cos(self, state, pos_xy, done) -> None:
        """몸 속도 방향 (방 틀) 과 부목표 방향의 cos. 속도 0.05 m/s 아래 · 끝난 env 는 뺀다 (nv_cos_vel_sub)."""
        st = self._stat()
        v = np.asarray(state.vel_b)[:, :2]
        yaw = teacher_obs.yaw_from_quat_wxyz(state.quat_w)
        self._note_disp(v, yaw, pos_xy, done)
        c, s_ = np.cos(yaw), np.sin(yaw)
        vw = np.stack([c * v[:, 0] - s_ * v[:, 1], s_ * v[:, 0] + c * v[:, 1]], axis=1)
        d = self.subgoal - pos_xy
        nv, nd = np.linalg.norm(vw, axis=1), np.linalg.norm(d, axis=1)
        ok = (nv >= 0.05) & (nd > 1e-9) & ~done
        if ok.any():
            cc = (vw * d).sum(1) / np.maximum(nv * nd, 1e-12)
            st["cos"] += float(cc[ok].sum())
            st["cos_n"] += int(ok.sum())
            for i in np.nonzero(ok)[0]:
                a = st["lv"][_lv_key(self.pgcl[i].level)]
                a[5] += float(cc[i]); a[6] += 1

    QUAT_CHECK_TICKS = 50          # 처음 이 틱 수 동안 env 0 의 쿼터니언 · yaw 점검 줄을 찍는다 (QUAT_CHECK)
    YAW_TOL_DEG = 30.0

    def _note_disp(self, v_b, yaw, pos_xy, done) -> None:
        """yaw 에 의존하지 않는 측정: 앞 틱 위치 -> 지금 위치 변화 (월드) 와 부목표 방향의 cos (nv_cos_disp), 그리고 쿼터니언 순서 점검
        (변화 방향 - 몸 속도 방향 = 몸이 본 방향 yaw 의 독립 추정; 해석한 yaw 와 비교). `_pos_prev` 는 이 틱이 끝나기 전의 앞 틱 위치."""
        st = self._stat()
        prev = self._pos_prev
        disp = pos_xy - prev
        dn, vn = np.linalg.norm(disp, axis=1), np.linalg.norm(v_b, axis=1)
        thr = 0.05 * self.tick_s if self.tick_s else 0.005
        d2 = self.subgoal - prev
        n2 = np.linalg.norm(d2, axis=1)
        ok = ~np.isnan(prev[:, 0]) & ~done & (dn >= thr) & (n2 > 1e-9)
        if ok.any():
            st["cosd"] += float(((disp[ok] * d2[ok]).sum(1) / (dn[ok] * n2[ok])).sum())
            st["cosd_n"] += int(ok.sum())
        mv = ok & (vn >= 0.05)
        if mv.any():
            est = np.arctan2(disp[:, 1], disp[:, 0]) - np.arctan2(v_b[:, 1], v_b[:, 0])
            err = np.degrees(np.abs((est - yaw + np.pi) % (2 * np.pi) - np.pi))
            st["yerr"] += float(err[mv].sum()); st["yok"] += int((err[mv] <= self.YAW_TOL_DEG).sum()); st["yn"] += int(mv.sum())
            qc = getattr(self, "_qc_n", 0)
            if qc < self.QUAT_CHECK_TICKS:
                self._qc_n = qc + 1
                self._qc_err = getattr(self, "_qc_err", []) + [err[mv]]
                if mv[0] and qc < 8:
                    q = getattr(self, "_quat0", None)
                    print(f"QUAT_CHECK tick={qc} env0 quat_wxyz={None if q is None else np.round(q, 4).tolist()} yaw_deg={np.degrees(yaw[0]):.1f} yaw_from_motion_deg={np.degrees(est[0]):.1f} err_deg={err[0]:.1f}", flush=True)
                if self._qc_n == self.QUAT_CHECK_TICKS:
                    e = np.concatenate(self._qc_err)
                    print(f"QUAT_CHECK summary ticks={self.QUAT_CHECK_TICKS} samples={len(e)} err_deg_median={np.median(e):.1f} within_{self.YAW_TOL_DEG:g}deg={float((e <= self.YAW_TOL_DEG).mean()):.2f} (yaw 해석이 맞으면 median 은 작고 비율은 1 에 가깝다)", flush=True)
                    self._qc_err = []

    def _note_tick(self, state, pos_xy, terms, done) -> None:
        st = self._stat()
        st["ticks"] += 1
        lv = np.array([p.level for p in self.pgcl])
        st["lvl"] += [(lv == 1).mean(), (lv == 2).mean(), (lv >= 3).mean()]
        for k, v in terms.items():
            st["r"][k] = st["r"].get(k, 0.0) + float(np.mean(v))
        st["vcmd"] += float(np.linalg.norm(np.asarray(state.applied)[:, :2], axis=1).mean())
        vb = np.linalg.norm(np.asarray(state.vel_b)[:, :2], axis=1)
        st["vbody"] += float(vb.mean()); st["stand"] += float((vb < 0.05).mean())
        self._ep_n += 1
        self._pos_prev = np.where(done[:, None], self._pos_prev, pos_xy)

    def observation(self, state) -> dict:
        """teacher 관측 (부목표는 보상 갱신 뒤의 값). `step` 뒤에 부른다."""
        return teacher_obs.build(self.voxels, self.room_id, state, self.cmd_prev, self.subgoal, origin_xy=self.origin_xy)
