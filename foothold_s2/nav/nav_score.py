"""벤치마크 채점기 (PLAN-HIPAN-V2 §6.4 · M12 의 CPU 부분 · 21 §8). numpy · scipy 만, Kit 없음.

과제 만들기 · 최단 경로 · SR · SPL · 충돌 수 · 우리 추가 지표 일부. 환경을 굴려 궤적을 얻는 일 (eval_nav.py) 은 이 모듈 밖이다.
  SR   = 끝 위치가 최종 목표 0.2 m 안 (논문 728 행) 인 에피소드 비율.
  SPL  = 성공 x 최단 / max(실제 길이, 최단) (최단 = 등급 지도 위 최단 경로 길이 · 8 방향 격자 + 건너뛰기 간선).
  충돌 = 에피소드당 평균 충돌 수 (입력으로 받음).
과제 300 = 거리 구간 셋 x 100 (계획). 구간 경계는 논문 미기재 -> **가정** DISTANCE_BANDS_M (최단 경로 길이 기준).
통과 가능 = BLOCKED 가 아닌 셀. 머리 위 통과가 자세 스위치에 달린 셀은 지도가 이미 반영한다.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

from foothold_s2.nav import grade_map as gm
from foothold_s2.nav import gvd_astar as ga

SUCCESS_M = 0.2
DISTANCE_BANDS_M = ((3.0, 8.0), (8.0, 14.0), (14.0, 40.0))     # 가정
TASKS_PER_BAND = 100
_NB = ((1, 0, 1.0), (0, 1, 1.0), (1, 1, np.sqrt(2.0)), (1, -1, np.sqrt(2.0)))


def _graph(g: gm.GradeMap, stride_m: float | None = None, allow_sparse: bool = True):
    ok = (g.grade != gm.BLOCKED) if allow_sparse else ~np.isin(g.grade, (gm.BLOCKED, gm.SPARSE))
    h, w = ok.shape
    idx = np.arange(h * w).reshape(h, w)
    rows, cols, lens = [], [], []
    for dx, dy, d in _NB:
        xa, xb = slice(0, h - dx), slice(dx, h)
        ya, yb = (slice(0, w - dy), slice(dy, w)) if dy >= 0 else (slice(-dy, w), slice(0, w + dy))
        m = ok[xa, ya] & ok[xb, yb]
        rows.append(idx[xa, ya][m]); cols.append(idx[xb, yb][m]); lens.append(np.full(int(m.sum()), d * g.res))
    if allow_sparse:
        for ax, ay, bx, by, d in ga.jump_edges(g, stride_m):
            rows.append(np.array([ax * w + ay])); cols.append(np.array([bx * w + by])); lens.append(np.array([d / 1000.0 * g.res]))
    r, c, l = np.concatenate(rows), np.concatenate(cols), np.concatenate(lens)
    return coo_matrix((np.concatenate([l, l]), (np.concatenate([r, c]), np.concatenate([c, r]))), shape=(h * w, h * w)).tocsr(), ok


def _cell(g, xy):
    c = (np.asarray(xy, float) / g.res).astype(int)
    if not (0 <= c[0] < g.grade.shape[0] and 0 <= c[1] < g.grade.shape[1]):
        raise ValueError("point outside the room")
    return int(c[0]), int(c[1])


def geodesic_map(g: gm.GradeMap, start_xy, stride_m: float | None = None, allow_sparse: bool = True) -> np.ndarray:
    """(H, W) 시작점에서 각 셀까지 최단 길이 m (못 가면 inf). allow_sparse False = 듬성한 · 건너뛰기를 쓰지 않는 길."""
    graph, ok = _graph(g, stride_m, allow_sparse)
    s = _cell(g, start_xy)
    if not ok[s]:
        raise ValueError("start must be on a passable cell")
    return dijkstra(graph, directed=False, indices=s[0] * g.grade.shape[1] + s[1]).reshape(g.grade.shape)


def shortest_length(g: gm.GradeMap, start_xy, goal_xy, stride_m: float | None = None) -> float:
    d = geodesic_map(g, start_xy, stride_m)
    return float(d[_cell(g, goal_xy)])


@dataclass
class Task:
    start: tuple
    goal: tuple
    shortest_m: float
    band: int
    needs_sparse: bool        # 듬성한 · 건너뛰기 없이는 못 가는 목표 (우리 추가 지표용)


def make_tasks(g: gm.GradeMap, rng: np.random.Generator, per_band: int = TASKS_PER_BAND,
               bands=DISTANCE_BANDS_M, stride_m: float | None = None, max_tries: int = 20000) -> list[Task]:
    """구간마다 per_band 과제. 시작은 무충돌 표본, 목표는 시작의 통과 가능 덩어리 안에서 최단 길이가 구간 안인 평지 셀."""
    tasks: list[Task] = []
    need = [per_band] * len(bands)
    free = gm.sample_free_points(g, rng, max_tries)
    for start in free:
        if not any(need):
            break
        d = geodesic_map(g, start, stride_m)
        d_free = geodesic_map(g, start, stride_m, allow_sparse=False)
        for b, (lo, hi) in enumerate(bands):
            if need[b] <= 0:
                continue
            cand = np.argwhere((d >= lo) & (d < hi) & np.isin(g.grade, (gm.FREE, gm.CONNECTED_ROUGH)))
            if not len(cand):
                continue
            cell = cand[rng.integers(0, len(cand))]
            tasks.append(Task(tuple(map(float, start)), tuple(map((lambda v: float((v + 0.5) * g.res)), cell)),
                              float(d[tuple(cell)]), b, bool(np.isinf(d_free[tuple(cell)]))))
            need[b] -= 1
    if any(need):
        raise RuntimeError(f"could not make {need} more tasks for the bands (the room is too small or blocked)")
    return tasks


def path_length(traj_xy) -> float:
    t = np.asarray(traj_xy, float)
    return float(np.linalg.norm(np.diff(t, axis=0), axis=1).sum()) if len(t) > 1 else 0.0


def score_episode(traj_xy, goal_xy, shortest_m: float, collisions: int = 0, success_m: float = SUCCESS_M) -> dict:
    """한 에피소드: 끝 위치가 목표 success_m 안이면 성공. SPL = 성공 x 최단 / max(실제, 최단)."""
    t = np.asarray(traj_xy, float)
    if t.ndim != 2 or t.shape[1] != 2 or not len(t):
        raise ValueError("trajectory must be (K, 2)")
    if not np.isfinite(shortest_m) or shortest_m <= 0:
        raise ValueError("shortest path length must be positive and finite")
    success = bool(np.linalg.norm(t[-1] - np.asarray(goal_xy, float)) <= success_m)
    length = path_length(t)
    spl = (shortest_m / max(length, shortest_m)) if success else 0.0
    return {"success": success, "spl": float(spl), "length_m": length, "collisions": int(collisions)}


def aggregate(episodes: list[dict], tasks: list[Task] | None = None) -> dict:
    """SR · SPL · 충돌 수 (에피소드 평균), 거리 구간별 SR, 듬성한 지형 너머 목표의 SR (tasks 가 있을 때)."""
    if not episodes:
        raise ValueError("no episodes")
    sr = np.array([e["success"] for e in episodes], float)
    out = {"n": len(episodes), "sr": float(sr.mean()), "spl": float(np.mean([e["spl"] for e in episodes])),
           "collisions": float(np.mean([e["collisions"] for e in episodes]))}
    if tasks is not None:
        if len(tasks) != len(episodes):
            raise ValueError("tasks and episodes differ in length")
        band = np.array([t.band for t in tasks])
        out["sr_by_band"] = {int(b): float(sr[band == b].mean()) for b in sorted(set(band.tolist()))}
        sparse = np.array([t.needs_sparse for t in tasks])
        out["sr_sparse_beyond"] = float(sr[sparse].mean()) if sparse.any() else None
        out["n_sparse_beyond"] = int(sparse.sum())
    return out


def pgcl_gate(sr_with: float, sr_without: float, min_drop: float = 0.10) -> bool:
    """구현 관문 (SPEC 3.2 T2): PGCL 을 끄면 Room SR 이 눈에 띄게 떨어져야 한다 (논문 98.4 -> 76.9). min_drop 은 가정."""
    return (sr_with - sr_without) >= min_drop


def modified_fraction(modified) -> float:
    """명령 공간 층이 값을 고친 걸음의 비율 (command_space.Applied.modified)."""
    m = np.asarray(modified, bool)
    return float(m.mean()) if m.size else 0.0
