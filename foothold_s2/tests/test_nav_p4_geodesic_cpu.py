"""HiPAN P4 경로 보상 측지 거리 스위치 (HIPAN_SHAPE_GEODESIC · lead 11/22 05:43 · 기본 꺼짐). 실제 학습 방 · 실제 NavTask. CPU only.
  - 끔: 남은 길이는 옛 직선 식 그대로 (측지 지도를 만들지 않음 · 값이 옛 식과 바이트 같음)
  - 켬: 목표가 벽 뒤에 있을 때 벽을 돌아가는 걸음 (직선 거리는 늘고 측지 거리는 줆) 이 + 보상 (끔이면 -)
  - 비용: 과제마다 지도 한 번 · 틱마다 보간 한 번 (시간 기록)."""
from __future__ import annotations

import time

import numpy as np
import pytest

from foothold_s2.nav import grade_map as gm, kit_factories as kf


def test_switch_parse():
    assert kf.shape_geodesic({}) is False and kf.shape_geodesic({"HIPAN_SHAPE_GEODESIC": "0"}) is False
    assert kf.shape_geodesic({"HIPAN_SHAPE_GEODESIC": "1"}) is True
    with pytest.raises(ValueError):
        kf.shape_geodesic({"HIPAN_SHAPE_GEODESIC": "yes"})


def _task(tmp_path, clear=None, monkeypatch=None):
    from foothold_s2.nav import p2_task_dist as pd
    if clear:
        monkeypatch.setenv("HIPAN_PATH_CLEAR_M", str(clear))
    task, env_start, _s, _nf = pd.build("on", 64, tmp_path)
    if clear:
        kf.apply_path_clear(task, task.assets, kf.path_clear_m())
    return task, env_start


def _detour_step(task, i):
    """목표 기준 측지 지도에서: 한 걸음 (0.10 m) 으로 측지 거리는 0.05 m 넘게 줄고 직선 거리는 0.02 m 넘게 느는 자리 (벽을 돌아가는 걸음)."""
    d = task._geo_map(i); res = task._geo[i][2]
    goal = np.asarray(task.goal[i], float)
    g = task._pg(i)
    free = np.argwhere(g.grade != gm.BLOCKED)
    rng = np.random.default_rng(1)
    for c in free[rng.permutation(len(free))[:20000]]:
        a = (c + 0.5) * res
        for ang in np.linspace(0, 2 * np.pi, 16, endpoint=False):
            b = a + 0.10 * np.array([np.cos(ang), np.sin(ang)])
            cb = (b / res).astype(int)
            if not (0 <= cb[0] < d.shape[0] and 0 <= cb[1] < d.shape[1]) or g.grade[cb[0], cb[1]] == gm.BLOCKED:
                continue
            if task._geo_len(i, a) - task._geo_len(i, b) > 0.05 and np.linalg.norm(b - goal) - np.linalg.norm(a - goal) > 0.02:
                return a, b
    return None


def _final_level(task, i):
    """env i 를 마지막 수준 (부목표 = 목표 하나) 으로."""
    p = task.pgcl[i]
    p.level = 99
    p.start_episode(task.path[i], task._pg(i))
    assert p.is_final and len(p._sub) == 1


@pytest.mark.parametrize("clear", [None, 0.25])
def test_detour_around_a_wall_is_rewarded_only_when_on(tmp_path, monkeypatch, clear):
    task, env_start = _task(tmp_path, clear, monkeypatch)
    i = 0
    task._new_task(i, env_start[i]); _final_level(task, i)
    task.shape_w, task.shape_clip, task.shape_all_levels = 5.0, 0.5, True
    task.shape_geodesic = True
    step = _detour_step(task, i)
    assert step is not None, "no detour step found in this room"
    a, b = step
    pos = np.tile(b, (task.n, 1)); task._pos_prev = np.full((task.n, 2), np.nan); task._pos_prev[i] = a
    i_now = np.zeros(task.n, dtype=int)
    on = task._shape_reward(pos, i_now)[i]
    task.shape_geodesic = False
    off = task._shape_reward(pos, i_now)[i]
    assert on > 0 > off, (on, off)


def test_off_keeps_the_straight_formula_bytes_and_builds_no_map(tmp_path):
    task, env_start = _task(tmp_path)
    rng = np.random.default_rng(3)
    for i in range(8):
        task._new_task(i, env_start[i]); _final_level(task, i)
    assert task.shape_geodesic is False
    for i in range(8):
        _sub, pts, tail = task._tail_len(i)
        for _ in range(20):
            xy = rng.uniform(0, 20, 2); k = int(rng.integers(0, 3))
            old = float(np.linalg.norm(np.asarray(xy, float) - pts[min(k, len(pts) - 1)]) + tail[min(k, len(pts) - 1)])   # 30a0ea51c 의 식
            assert task._remaining(i, xy, k) == old
    assert task.geo_maps_built == 0 and task._geo == {}


def test_cost_per_task_and_per_tick(tmp_path, capsys):
    task, env_start = _task(tmp_path)
    task.shape_geodesic = True
    n = 12
    for i in range(n):
        task._new_task(i, env_start[i]); _final_level(task, i)
    t0 = time.perf_counter()
    for i in range(n):
        task._geo_map(i)
    build = (time.perf_counter() - t0) / n
    xy = np.asarray(env_start[:n], float)
    t0 = time.perf_counter()
    for _ in range(50):
        for i in range(n):
            task._geo_len(i, xy[i])
    look = (time.perf_counter() - t0) / (50 * n)
    with capsys.disabled():
        print(f"\nP4_COST map_per_task_s={build:.4f} lookup_per_env_tick_us={look * 1e6:.1f} maps={task.geo_maps_built} "
              f"(1024 env x one lookup per tick ~ {look * 1024 * 1e3:.2f} ms per tick)")
    assert task.geo_maps_built == n
    task._geo_map(0); assert task.geo_maps_built == n            # 같은 과제는 다시 만들지 않음
    assert build < 2.0 and look < 1e-3
