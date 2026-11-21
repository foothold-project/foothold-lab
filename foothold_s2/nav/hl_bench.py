"""HiPAN 원문 시험 벤치마크 평가 (lead 11/21 18:52 · HIPAN-FIDELITY-ORDER C · D · opus-code-lx).

원문 (2604.26504.txt:727-728): 네 유형 x 300 과제 (거리 구간 셋 x 100) x 시드 10 · SR (목표 0.2 m 안) · SPL (최단 / max(실제, 최단)).
과제는 bench_tasks.py 가 만든 tasks_<유형>.json. 학습과 같은 환경 (kit_factories.teacher_env) 을 쓰되:
  - 방 = 네 유형의 시험 방 (한 메시 · 방 번호 = 줄 · TYPES 순서), 시작점 = 그 유형 과제 300 개의 시작 (room_generator.write_rooms starts_by_room)
  - 과제 표 = 시작점마다 그 과제의 목표 하나 (install_bench_table) · PGCL 수준은 마지막 수준 고정 (목표만 · 부목표 없음)
  - env 마다 첫 에피소드 하나를 잰다. env 의 시작이 어느 과제인지는 가장 가까운 시작점 (BENCH_TOL_M 안) 으로 정한다.
D (기록 전부): 에피소드마다 틱별 몸 궤적 (x y z · yaw · roll · pitch) · 상위 명령 (5 칸 · 실제 넣은 값) · 하위 추종 오차 (명령 대 몸 속도) · 충돌 ·
  종료 원인 (도달 · 넘어짐 · 시간 초과 · 정체) · 끝 자리의 천장 높이 · 통로 폭 · 지나간 부목표 · 끝 자리에서 목표까지 최단 거리 · 수준.
  틱 배열은 out/<유형>_s<시드>_traj.npz, 에피소드 표는 out/episodes.jsonl, 요약은 out/bench.json, 전부의 sha 목록은 out/MANIFEST.sha256.

원문에 없음: 시험 방 치수 (20 x 20 m 가정) · 거리 기준 (최단 경로 가정) · 시드가 바꾸는 것 (여기서는 평가 시드 = torch · numpy · 과제 rng) ·
  에피소드 시간 상한 (학습과 같은 경로 길이 / 0.3 + 10 초) · 「정체」 정의 (hl_eval STUCK_WINDOW_S 5 초 · 0.10 m).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from foothold_s2.nav import bench_tasks as bt
from foothold_s2.nav import nav_score as ns

BENCH_TOL_M = 0.12                       # 몸이 선 자리 대 과제 시작점 (리셋은 시작점 위에 흔들림 없이 놓는다 · nav_env_cfg reset_jitter_xy off · 처음 선 뒤 흔들림 여유 · 과제끼리 시작 간격 bench_tasks.START_SEP_M 0.3 의 반 밑)
FINAL_LEVEL = 99                         # hl_eval.FINAL_LEVEL 과 같은 값 (마지막 수준 = 목표만)
STUCK_WINDOW_S, STUCK_PATH_M = 5.0, 0.10
TRAJ_FIELDS = ("x", "y", "z", "yaw", "roll", "pitch", "vx_b", "vy_b", "wz_b", "cmd_vx", "cmd_vy", "cmd_wz", "cmd_dh", "cmd_roll",
               "err_vx", "err_vy", "err_wz", "collision", "done")


# ---------------------------------------------------------------- 방 · 시작점 · 과제 표 (CPU)
def load_docs(tasks_dir, types=bt.TYPES) -> list[dict]:
    docs = []
    for kind in types:
        d = json.loads((Path(tasks_dir) / f"tasks_{kind}.json").read_text(encoding="utf-8"))
        if d.get("format") != "foothold-hipan-bench-tasks/1" or d.get("type") != kind:
            raise ValueError(f"tasks_{kind}.json is not a bench task file for {kind}")
        d["room_spec_path"] = str(bt.NAV / d["room_spec"])
        spec_sha = hashlib.sha256(Path(d["room_spec_path"]).read_bytes()).hexdigest()
        if spec_sha != d["room_spec_sha256"]:
            raise ValueError(f"{d['room_spec']} changed since the tasks were made")
        docs.append(d)
    if len({len(d["tasks"]) for d in docs}) != 1:
        raise ValueError("every type needs the same number of tasks (one start column per task)")
    return docs


def bench_rooms(docs):
    """(rooms, starts_by_room) · starts 는 방 틀 (K, 3) · z = 그 셀의 바닥 높이."""
    from foothold_s2.nav import room_generator as rg

    rooms, starts = [], []
    for d in docs:
        room = rg.build_room(rg.load_spec(d["room_spec_path"]))
        xy = np.array([t["start_xy"] for t in d["tasks"]], float)
        ij = np.clip((xy / rg.RES).astype(int), 0, room.height.shape[0] - 1)
        starts.append(np.column_stack([xy, room.height[ij[:, 0], ij[:, 1]]]))
        rooms.append(room)
    return rooms, starts


def install_bench_table(task, docs) -> str:
    """task.table 을 「시작점마다 그 과제의 목표 하나」 로 바꾼다 (NavTask._table_pick 이 그대로 읽는 꼴). 길은 같은 A* (gvd_astar). 돌려주는 값 = 표 sha256."""
    from foothold_s2.nav import gvd_astar

    h = hashlib.sha256()
    table = []
    from foothold_s2.nav import grade_map as gm

    for r, d in enumerate(docs):
        g = task.assets[r].grade
        if d.get("pose_active") and not g.pose_active:          # 과제를 자세 켠 지도에서 뽑았으면 길도 그 지도에서 (머리 위 판 아래로 숙여 지나는 길)
            g = gm.make_grade_map(task.assets[r].room, {**task.grade_table, "sha256": g.table_sha256}, pose_active=True) if hasattr(task, "grade_table") \
                else gm.make_grade_map(task.assets[r].room, gm.load_grade_table(bt.NAV / "grade_table_draft.yaml"), pose_active=True)
        starts = np.array([t["start_xy"] for t in d["tasks"]], float)
        rows = []
        for t in d["tasks"]:
            s, goal = np.asarray(t["start_xy"], float), np.asarray(t["goal_xy"], float)
            pp = gvd_astar.find_path(g, s, goal, straighten=task.straighten)
            if not pp.found:
                raise ValueError(f"{d['type']} task {t['id']}: no A* path on the training grade map")
            rows.append({"ok": [(goal, pp.points)], "wound": []})
            h.update(goal.tobytes()); h.update(s.tobytes())
        table.append({"starts": starts, "rows": rows})
    task.table, task.table_tol_m, task.table_sha256 = table, BENCH_TOL_M, h.hexdigest()
    task.winding_frac = 0.0
    return task.table_sha256


def assign_bench_envs(terrain, num_envs: int) -> dict:
    """env i -> (방 = i % 방 수, 시작 = i // 방 수): 과제마다 env 하나. Isaac 의 무작위 줄 배정으로는 과제의 약 1/3 이 빠진다 (열마다 env 4 · 줄 무작위 4 가지 -> 1 - (3/4)^4).
    terrain = Isaac TerrainImporter (terrain_origins (방, 시작, 3) · terrain_levels · terrain_types · env_origins). num_envs 는 방 x 시작 과 같아야 한다."""
    import torch

    rooms, starts = int(terrain.terrain_origins.shape[0]), int(terrain.terrain_origins.shape[1])
    if num_envs != rooms * starts:
        raise ValueError(f"bench needs num_envs = rooms x starts = {rooms} x {starts} = {rooms * starts}, got {num_envs}")
    ids = torch.arange(num_envs, device=terrain.terrain_levels.device)
    terrain.terrain_levels[:] = (ids % rooms).to(terrain.terrain_levels.dtype)
    terrain.terrain_types[:] = (ids // rooms).to(terrain.terrain_types.dtype)
    terrain.env_origins[:] = terrain.terrain_origins[terrain.terrain_levels.long(), terrain.terrain_types.long()]
    return {"rooms": rooms, "starts": starts, "num_envs": num_envs, "rule": "room = env % rooms, start = env // rooms"}


def task_of(docs, room_id: int, start_xy) -> int:
    """몸이 선 자리에 가장 가까운 과제 번호 (BENCH_TOL_M 밖이면 -1)."""
    starts = np.array([t["start_xy"] for t in docs[room_id]["tasks"]], float)
    d = np.linalg.norm(starts - np.asarray(start_xy, float), axis=1)
    k = int(d.argmin())
    return k if d[k] <= BENCH_TOL_M else -1


# ---------------------------------------------------------------- 기록 (CPU 시험 가능 · env 는 덕 타이핑)
def euler_rpy(quat_wxyz):
    q = np.asarray(quat_wxyz, float)
    w, x, y, z = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
    roll = np.arctan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    pitch = np.arcsin(np.clip(2 * (w * y - z * x), -1.0, 1.0))
    yaw = np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return roll, pitch, yaw


class BenchRecorder:
    """env 마다 첫 에피소드의 틱 배열 (T, N, F) 과 끝 사실. pos_room(state) 는 방 틀 (n, 2) 위치를 돌려주는 함수."""

    def __init__(self, n: int, ticks: int, tick_s: float):
        self.n, self.T, self.tick_s = n, int(ticks), float(tick_s)
        self.traj = np.full((self.T, n, len(TRAJ_FIELDS)), np.nan, dtype=np.float32)
        self.t = 0
        self.live = np.ones(n, bool)
        self.end_tick = np.full(n, -1, int)
        self.reason = np.array([""] * n, dtype=object)
        self.collisions = np.zeros(n, int)
        self.path_xy = [[] for _ in range(n)]
        self.window = max(1, int(math.ceil(STUCK_WINDOW_S / self.tick_s)))

    def observe(self, state, pos_xy, reached):
        """한 상위 틱 뒤. reached (n,) = 이 틱에 목표 도달 (env 기록). 이미 끝난 env 는 더 안 적는다."""
        if self.t >= self.T:
            return
        roll, pitch, yaw = euler_rpy(state.quat_w)
        err = np.asarray(state.track_err, float).mean(0) if np.size(state.track_err) else np.zeros((self.n, 3))
        row = np.column_stack([pos_xy[:, 0], pos_xy[:, 1], state.pos_local[:, 2], yaw, roll, pitch, state.vel_b[:, 0], state.vel_b[:, 1],
                               state.yaw_rate, state.applied[:, 0], state.applied[:, 1], state.applied[:, 2], state.applied[:, 3],
                               state.applied[:, 4], err[:, 0], err[:, 1], err[:, 2], state.collision.astype(float), state.done.astype(float)])
        live = self.live.copy()
        self.traj[self.t, live] = row[live]
        done, reached = np.asarray(state.done, bool), np.asarray(reached, bool)
        for i in np.flatnonzero(live):
            if not done[i]:
                self.path_xy[i].append(pos_xy[i].copy())
            self.collisions[i] += int(bool(state.collision[i]))
            if reached[i] or done[i]:
                self.live[i] = False
                self.end_tick[i] = self.t
                self.reason[i] = "reached" if reached[i] else self._fail_reason(i, state)
        self.t += 1

    def _fail_reason(self, i, state):
        if not bool(state.timed_out[i]):
            return "fall"
        p = self.path_xy[i][-self.window:]
        moved = sum(float(np.linalg.norm(b - a)) for a, b in zip(p[:-1], p[1:])) if len(p) > 1 else 0.0
        return "stuck" if len(p) >= self.window and moved < STUCK_PATH_M else "timeout"

    def close(self):
        for i in np.flatnonzero(self.live):
            self.reason[i] = "horizon"
            self.end_tick[i] = self.t - 1


def end_facts(room, grade, goal_xy, end_xy, goal_geo=None) -> dict:
    """끝 자리의 천장 높이 (머리 위 장애물 아래면 - 바닥 · 없으면 inf) · 통로 폭 (가장 가까운 막힌 칸까지 x 2) · 목표까지 최단 거리."""
    from scipy import ndimage

    from foothold_s2.nav import grade_map as gm
    from foothold_s2.nav import room_generator as rg

    i, j = (np.clip(int(v / rg.RES), 0, room.height.shape[0] - 1) for v in end_xy)
    ceiling = float(room.clearance[i, j] - room.height[i, j]) if np.isfinite(room.clearance[i, j]) else math.inf
    free = np.pad(grade.grade != gm.BLOCKED, 1, constant_values=False)
    width = float(ndimage.distance_transform_edt(free)[1:-1, 1:-1][i, j] * rg.RES * 2.0)
    geo = goal_geo if goal_geo is not None else ns.geodesic_map(grade, goal_xy)
    remain = float(geo[i, j])
    return {"ceiling_m": ceiling, "passage_width_m": width, "goal_shortest_from_end_m": remain if np.isfinite(remain) else None}


def score_type(doc, episodes) -> dict:
    """한 유형 · 한 시드: 과제마다 첫 에피소드 하나 (여러 env 가 같은 과제면 env 번호가 가장 작은 것). SR · SPL 은 nav_score 그대로."""
    by_task = {}
    for e in sorted(episodes, key=lambda e: e["env_id"]):
        if e["task_id"] >= 0 and e["task_id"] not in by_task:
            by_task[e["task_id"]] = e
    rows = []
    for k, e in by_task.items():
        t = doc["tasks"][k]
        s = ns.score_episode(np.array(e["path_xy"]), np.array(t["goal_xy"]), t["shortest_m"], e["collisions"])
        rows.append({**s, "band": t["band"]})
    out = {"tasks_covered": len(rows), "tasks_total": len(doc["tasks"])}
    if rows:
        out.update(sr=float(np.mean([r["success"] for r in rows])), spl=float(np.mean([r["spl"] for r in rows])),
                   by_band={b: float(np.mean([r["success"] for r in rows if r["band"] == b])) for b in range(len(doc["bands_m"]))
                            if any(r["band"] == b for r in rows)})
    return out


# ---------------------------------------------------------------- Runpod 결과 폴더 전부 받기 대조 (SSH · runner 경로 재사용)
def manifest_lines(folder) -> list[str]:
    folder = Path(folder)
    out = []
    for p in sorted(q for q in folder.rglob("*") if q.is_file() and q.name != "MANIFEST.sha256"):
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        out.append(f"{h}  {p.stat().st_size}  {p.relative_to(folder).as_posix()}")
    return out


def write_manifest(folder) -> Path:
    path = Path(folder) / "MANIFEST.sha256"
    path.write_text("\n".join(manifest_lines(folder)) + "\n", encoding="utf-8")
    return path


def verify_manifest(folder) -> list[str]:
    """받은 폴더의 MANIFEST.sha256 (원격에서 쓴 것) 대 실제 파일: 다른 줄 목록 (빈 목록 = 전부 같음 · 빠진 파일 · 크기 · sha 모두 잡음)."""
    folder = Path(folder)
    want = set((folder / "MANIFEST.sha256").read_text(encoding="utf-8").split("\n")) - {""}
    have = set(manifest_lines(folder))
    return sorted(want ^ have)


# ---------------------------------------------------------------- Kit (Runpod)
def run_seed(env, task, docs, actor, *, seed: int, ticks: int, device: str, out: Path) -> list[dict]:
    import torch

    from foothold_s2.nav import hl_eval

    torch.manual_seed(seed); np.random.seed(seed); task.rng = np.random.default_rng(seed)
    hl_eval.fix_levels(task, [FINAL_LEVEL] * task.n, fresh=False)
    obs = env.reset()
    pos = lambda: env._pos_room(env.state, np.arange(task.n))   # noqa: E731
    start = pos().copy()
    rec = BenchRecorder(task.n, ticks, float(task.tick_s))
    with torch.no_grad():
        for _ in range(ticks):
            obs, _r, _d, _to, _info = env.step(actor(obs.to(device)))
            reached = np.asarray(env.task_reached, bool) if hasattr(env, "task_reached") else np.zeros(task.n, bool)
            rec.observe(env.state, pos(), reached)
            if not rec.live.any():
                break
    rec.close()
    geo = {}
    episodes = []
    for i in range(task.n):
        r = int(task.room_id[i]); k = task_of(docs, r, start[i])
        goal = np.asarray(task.goal[i], float)
        end_xy = rec.path_xy[i][-1] if rec.path_xy[i] else start[i]
        key = (r, k)
        if k >= 0 and key not in geo:
            geo[key] = ns.geodesic_map(task.assets[r].grade, goal)
        facts = end_facts(task.assets[r].room, task.assets[r].grade, goal, end_xy, geo.get(key)) if k >= 0 else {}
        p = task.pgcl[i]
        episodes.append({"type": docs[r]["type"], "seed": seed, "env_id": i, "room_id": r, "task_id": k, "reason": str(rec.reason[i]),
                         "end_tick": int(rec.end_tick[i]), "collisions": int(rec.collisions[i]), "level": int(p.level),
                         "subgoals_reached": int(p._i), "subgoals_total": len(p._sub),
                         "start_xy": start[i].tolist(), "goal_xy": goal.tolist(), "end_xy": np.asarray(end_xy).tolist(),
                         "path_xy": [q.tolist() for q in rec.path_xy[i]], **facts})
    for r, d in enumerate(docs):
        ids = np.flatnonzero(np.asarray(task.room_id) == r)
        np.savez_compressed(out / f"{d['type']}_s{seed}_traj.npz", traj=rec.traj[:, ids], env_ids=ids, fields=np.array(TRAJ_FIELDS), tick_s=rec.tick_s)
    return episodes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks-dir", required=True)
    ap.add_argument("--seeds", nargs="+", type=int, default=list(bt.SEEDS))
    ap.add_argument("--ticks", type=int, default=None, help="기본: 가장 긴 과제 경로 / 0.3 + 10 초 (학습과 같은 시간 상한) 의 1.1 배")
    ap.add_argument("--out", required=True)
    ap.add_argument("--print", action="store_true", help="방 · 과제 · 표만 CPU 로 확인하고 Kit 을 띄우지 않는다")
    a = ap.parse_args(argv)
    docs = load_docs(a.tasks_dir)
    if a.print:
        rooms, starts = bench_rooms(docs)
        longest = max(t["shortest_m"] for d in docs for t in d["tasks"])
        print(json.dumps({"types": [d["type"] for d in docs], "tasks_per_type": len(docs[0]["tasks"]), "starts_shape": [len(starts), len(starts[0]), 3],
                          "seeds": a.seeds, "success_m": ns.SUCCESS_M, "bands_m": docs[0]["bands_m"], "longest_shortest_m": longest,
                          "num_envs_needed": len(docs) * len(docs[0]["tasks"]), "out": a.out}, ensure_ascii=False))
        return 0
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} exists (never overwritten)")
    out.mkdir(parents=True)
    rc = 0
    try:
        from foothold_s2.nav import hl_eval, hl_train, kit_factories

        nav, task = kit_factories.teacher_env()                # HIPAN_FACTORY_CONFIG 에 bench_tasks_dir 이 있어야 한다 (prepare_rooms 가 시험 방을 쓴다)
        if getattr(task, "bench_docs", None) is None:
            raise ValueError("factory config has no bench_tasks_dir: the rooms are not the benchmark rooms")
        env = hl_train.TeacherVecEnv(nav, task, device="cuda:0" if _cuda() else "cpu")
        actor, _std, it = hl_eval.load_actor(a.model, device=env.device)
        ticks = a.ticks or int(math.ceil(1.1 * float(np.max(task.episode_seconds())) / float(task.tick_s)))
        summary = {"format": "foothold-hipan-bench-eval/1", "model": a.model, "model_sha256": hashlib.sha256(Path(a.model).read_bytes()).hexdigest(),
                   "iteration": it, "ticks": ticks, "tick_s": float(task.tick_s), "table_sha256": task.table_sha256, "seeds": {}}
        with (out / "episodes.jsonl").open("w", encoding="utf-8") as f:
            for seed in a.seeds:
                eps = run_seed(env, task, docs, actor, seed=seed, ticks=ticks, device=env.device, out=out)
                for e in eps:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
                summary["seeds"][seed] = {d["type"]: score_type(d, [e for e in eps if e["type"] == d["type"]]) for d in docs}
                print(f"BENCH_SEED {seed} " + json.dumps(summary["seeds"][seed], ensure_ascii=False), flush=True)
        per = {d["type"]: [summary["seeds"][s][d["type"]].get("sr") for s in a.seeds] for d in docs}
        summary["sr_mean_std"] = {k: [float(np.mean(v)), float(np.std(v))] for k, v in per.items() if all(x is not None for x in v)}
        (out / "bench.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
        write_manifest(out)
    except BaseException:
        import traceback

        text = traceback.format_exc()
        print(text, flush=True)
        (out / "FAILED.txt").write_text(text, encoding="utf-8")
        rc = 1
    finally:
        from foothold_s2.nav import kit_factories

        kit_factories.finish(rc)
    return rc


def _cuda() -> bool:
    import torch
    return torch.cuda.is_available()


if __name__ == "__main__":
    raise SystemExit(main())
