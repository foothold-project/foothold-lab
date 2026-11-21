"""P3 몸 폭 여유 대조 (lead 11/22 02:42 · planner hipan_start_stuck). CPU · Kit 없음.
  train : 실제 학습 방 (p2_task_dist.build 'on' = prepare_rooms · 6 방 · seed 1000 · 시작 64) 에서 HIPAN_PATH_CLEAR_M 끔/켬 (여러 값) 마다
          시작 자리 (env 시작 · 중복 뺀 것) 의 출구 (몸 폭 지도에서 붙일 칸 · 1 m 안 · 가장 큰 덩어리) 와 새 과제 N 개 길의 최소 여유 (nav_task._path_facts 잣대) 분포.
  bench : 원문 시험 과제표 (bench_tasks_*) 의 시작 → 목표 A* 길 최소 여유 (같은 잣대 · 등급표 draft · pose_active True = hl_bench 와 같음).
    python -m foothold_s2.nav.p3_clear_dist train --n 400 --clear 0 0.2 0.25 0.3 --out <json>
    python -m foothold_s2.nav.p3_clear_dist bench --tasks-dir <bench_tasks_wfc_s0> --out <json>
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

import numpy as np


def _q(a):
    a = np.asarray([x for x in a if x is not None], float)
    if not len(a):
        return None
    return {"n": int(len(a)), "p10": round(float(np.percentile(a, 10)), 3), "median": round(float(np.median(a)), 3), "p90": round(float(np.percentile(a, 90)), 3),
            "le_0.10": round(float((a <= 0.10 + 1e-9).mean()), 3), "le_0.20": round(float((a <= 0.20 + 1e-9).mean()), 3), "min": round(float(a.min()), 3)}


def train(n: int, clears, envs: int, seed: int = 0) -> dict:
    from foothold_s2.nav import grade_map as gm, kit_factories as kf, p2_task_dist as pd
    out = {}
    with tempfile.TemporaryDirectory(prefix="p3clear_") as tmp:
        for c in clears:
            os.environ["HIPAN_PATH_CLEAR_M"] = "" if c == 0 else str(c)
            task, env_start, _b, _nf = pd.build("on", envs, Path(tmp) / f"c{c}")
            shut = kf.apply_path_clear(task, task.assets, kf.path_clear_m())
            # 시작 자리 출구
            seen, start_clear, exit_ok, snap_m = set(), [], 0, []
            for i in range(len(env_start)):
                key = (int(task.room_id[i]), round(float(env_start[i][0]), 2), round(float(env_start[i][1]), 2))
                if key in seen:
                    continue
                seen.add(key)
                a = task.assets[task.room_id[i]]
                d = __import__("scipy.ndimage", fromlist=["x"]).distance_transform_edt(a.grade.grade != gm.BLOCKED) * a.grade.res
                ij = (np.asarray(env_start[i]) / a.grade.res).astype(int)
                start_clear.append(float(d[ij[0], ij[1]]))
                g = task._pg(i)
                s2 = task._snap(g, env_start[i])
                if s2 is not None:
                    lc = gm.largest_component_mask(gm.passable(g)); c2 = (s2 / g.res).astype(int)
                    if lc[c2[0], c2[1]]:
                        exit_ok += 1; snap_m.append(float(np.linalg.norm(s2 - env_start[i])))
            rng = np.random.default_rng(seed)
            mins, lens, b0 = [], [], (task.task_body_snap, task.task_body_raw, task.task_fallbacks)
            for _ in range(n):
                i = int(rng.integers(len(env_start)))
                task._new_task(i, env_start[i])
                f = task._path_facts(i)
                mins.append(f["min_clear_m"]); lens.append(f["path_len_m"])
            out[str(c)] = {"clear_m": c, "shut_share_by_room": shut, "starts": len(seen), "start_clear_m": _q(start_clear), "exit_ok": exit_ok,
                           "exit_ok_share": round(exit_ok / max(len(seen), 1), 3), "snap_m": _q(snap_m), "tasks": n, "task_min_clear_m": _q(mins), "task_path_m": _q(lens),
                           "body_snap": task.task_body_snap - b0[0], "body_raw": task.task_body_raw - b0[1], "fallbacks": task.task_fallbacks - b0[2]}
            print(c, json.dumps(out[str(c)], ensure_ascii=False), flush=True)
    os.environ.pop("HIPAN_PATH_CLEAR_M", None)
    return out


def bench(tasks_dir: Path) -> dict:
    from scipy import ndimage
    from foothold_s2.nav import grade_map as gm, gvd_astar, room_generator as rg
    table = gm.load_grade_table(Path(__file__).resolve().parent / "grade_table_draft.yaml")
    out = {}
    for f in sorted(Path(tasks_dir).glob("tasks_*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        cand = [Path(tasks_dir) / d["room_spec"], Path(tasks_dir).parent / d["room_spec"]]     # rooms/... 는 nav 폴더 기준 (hl_bench.load_docs 와 같음)
        spec = next(c for c in cand if c.is_file())
        room = rg.build_room(rg.load_spec(spec))
        g = gm.make_grade_map(room, table, pose_active=bool(d.get("pose_active", True)))
        dist = ndimage.distance_transform_edt(g.grade != gm.BLOCKED) * g.res
        mins, starts = [], []
        tasks = d.get("tasks") or [t for band in (d.get("per_band") or []) for t in (band if isinstance(band, list) else band.get("tasks", []))]
        for t in tasks:
            s, e = np.asarray(t["start_xy"], float), np.asarray(t["goal_xy"], float)
            ij = np.clip((s / g.res).astype(int), 0, np.array(g.grade.shape) - 1); starts.append(float(dist[ij[0], ij[1]]))
            try:
                p = gvd_astar.find_path(g, s, e)
            except ValueError:
                continue
            if not p.found:
                continue
            P = p.points; arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
            pts = np.stack([np.interp(np.arange(0.0, arc[-1] + 1e-9, g.res / 2), arc, P[:, k]) for k in (0, 1)], axis=1)
            cells = np.clip((pts / g.res).astype(int), 0, np.array(g.grade.shape) - 1)
            mins.append(float(dist[cells[:, 0], cells[:, 1]].min()))
        out[f.stem] = {"tasks": len(tasks), "paths": len(mins), "task_min_clear_m": _q(mins), "start_clear_m": _q(starts)}
        print(f.stem, json.dumps(out[f.stem], ensure_ascii=False), flush=True)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["train", "bench"]); ap.add_argument("--n", type=int, default=400); ap.add_argument("--envs", type=int, default=1024)
    ap.add_argument("--clear", type=float, nargs="+", default=[0.0, 0.2, 0.25, 0.3]); ap.add_argument("--tasks-dir", type=Path); ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    res = train(a.n, a.clear, a.envs) if a.what == "train" else bench(a.tasks_dir)
    a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
