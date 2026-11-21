"""P2 과제 분포 대조 (lead 11/22 01:28): 실제 학습 방 (prepare_rooms · room_count 6 · room_seed 1000 · n_starts 64 · grade_table_draft) 과 실제 NavTask._new_task 로
새 과제를 N 번 뽑아 HIPAN_FRESH_TASKS 끔 (고정표 64 x 32) 과 켬 (방 지도에서 새로) 의 굴곡 · 경로 길이 · (시작, 목표) 되풀이 비율 · 뽑기 CPU 시간을 표로. Kit 없음.
    python -m foothold_s2.nav.p2_task_dist --n 1000 --out <json>
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def build(mode: str, num_envs: int, work: Path):
    from foothold_s2.nav import kit_factories as kf, nav_task, room_generator as rg
    os.environ["HIPAN_FRESH_TASKS"] = "1" if mode == "on" else "0"
    cfg = {"lower_checkpoint": "-", "lower_sha256": "-", "num_envs": num_envs, "device": "cpu", "seed": 0, "room_count": 6, "room_seed": 1000,
           "n_starts": 64, "room_dir": str(work / f"rooms_{mode}"), "grade_table": str(ROOT / "foothold_s2/nav/grade_table_draft.yaml")}
    prepared = kf.prepare_rooms(cfg)
    assets = prepared["assets"]
    rows = np.arange(num_envs) % len(assets)
    pitch = rg.ROOM_M + rg.ROOM_GAP_M
    starts = [rg.start_points(a.room, 64, seed=1000 + r)[:, :2] for r, a in enumerate(assets)]
    env_start = np.stack([starts[rows[i]][(i // len(assets)) % 64] for i in range(num_envs)])
    origins = env_start.copy(); origins[:, 0] += rows * pitch          # 메시 좌표 원점 = 방 틀 시작 + 줄 이동 (room_frame_origin_xy 의 역)
    fresh = kf.fresh_tasks()
    per_start = 0 if fresh else 32
    t0 = time.time()
    task = kf.make_task(assets, num_envs, 0, rows, origins, None if not per_start else starts, per_start, reach_m=0.3)
    build_s = time.time() - t0
    if fresh:
        task.path_range_m, task.strict_winding = kf.FRESH_PATH_RANGE_M, True
    return task, env_start, build_s, kf.new_task_after_fails(cfg)


def draw(task, env_start, n: int, seed: int = 0):
    rng = np.random.default_rng(seed)
    rec, times = [], []
    for k in range(n):
        i = int(rng.integers(len(env_start)))
        t0 = time.perf_counter()
        task._new_task(i, env_start[i])
        times.append(time.perf_counter() - t0)
        s, g, pts = task.start[i], task.goal[i], task.path[i]
        L = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum()); d = float(np.linalg.norm(g - s))
        rec.append({"env": i, "room": int(task.room_id[i]), "start": [round(float(x), 2) for x in s], "goal": [round(float(x), 1) for x in g],
                    "path_m": L, "straight_m": d, "wind": L / d if d > 0 else float("nan")})
    return rec, times


def summarize(rec, times):
    w = np.array([r["wind"] for r in rec]); L = np.array([r["path_m"] for r in rec])
    keys = [(r["room"], tuple(r["start"]), tuple(r["goal"])) for r in rec]
    seen, rep = set(), 0
    for k in keys:
        rep += k in seen; seen.add(k)
    edges_w = [0, 1.05, 1.2, 1.5, 99]; edges_l = [0, 5, 10, 20, 30, 999]
    return {"n": len(rec), "repeat_pair_frac": rep / len(rec), "distinct_pairs": len(seen),
            "wind_bins": {f"{a}-{b}": float(((w >= a) & (w < b)).mean()) for a, b in zip(edges_w, edges_w[1:])},
            "wind_ge_1.2": float((w >= 1.2).mean()), "wind_median": float(np.median(w)),
            "path_bins_m": {f"{a}-{b}": float(((L >= a) & (L < b)).mean()) for a, b in zip(edges_l, edges_l[1:])},
            "path_median_m": float(np.median(L)), "draw_ms_median": 1000 * float(np.median(times)), "draw_ms_p90": 1000 * float(np.percentile(times, 90)),
            "relaxed_or_fallback": None}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000); ap.add_argument("--envs", type=int, default=1024); ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--modes", nargs="+", default=["off", "on"])
    a = ap.parse_args(argv)
    out = {}
    with tempfile.TemporaryDirectory(prefix="p2dist_") as tmp:
        for mode in a.modes:
            task, env_start, build_s, nf = build(mode, a.envs, Path(tmp))
            r0, f0 = task.task_relaxed, task.task_fallbacks
            rec, times = draw(task, env_start, a.n)
            s = summarize(rec, times)
            s.update(build_s=build_s, cut_after_fails=nf, path_range_m=list(task.path_range_m), table=task.table is not None,
                     relaxed_or_fallback=int(task.task_relaxed - r0 + task.task_fallbacks - f0))
            out[mode] = s
            print(mode, json.dumps(s, ensure_ascii=False), flush=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
