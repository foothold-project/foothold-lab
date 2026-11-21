"""HiPAN 원문 시험 과제 (lead 11/21 18:52 · HIPAN-FIDELITY-ORDER C · opus-code-lx). numpy · scipy 만, Kit 없음.

원문 (2604.26504.txt:727-728): 시험 환경 넷 (Corridor · Room · Complex-1 · Complex-2) 마다 거리 구간 [5, 10] · [10, 20] · [20, 30] m 에서
충돌 없는 시작-목표 쌍을 100 개씩 = 300 과제, 시드 10 개의 평균 · 표준편차. SR 은 목표 0.2 m 안 도착 비율, SPL 은 최단 대 실제 길이.

원문에 없는 것 (지어내지 않고 가정으로 적음):
  - 시험 환경의 치수 (학습 환경만 20 x 20 m 로 적힘, 535 행) -> 여기서는 20 x 20 m.
  - 거리를 최단 경로로 재는지 직선으로 재는지 -> 최단 경로 길이 (nav_score.make_tasks 와 같은 규칙) · 직선 거리도 같이 적는다.\n  - 시작점을 과제끼리 나눠 쓰는지 -> 과제마다 다른 시작점 (0.3 m 이상 떨어짐 · 평가가 시작 자리로 과제를 가른다).
  - 시드 10 개가 방을 바꾸는지 시뮬레이션 · 정책 잡음만 바꾸는지 -> 과제 목록은 유형마다 하나 (task_seed), 시드 10 개는 평가 쪽.
  - 네 유형의 배치 치수 -> 지금은 nav/rooms/bench_*.yaml (손으로 적은 임시 배치). WFC 판은 아직 없음.

쓰는 법: python -m foothold_s2.nav.bench_tasks --out <폴더> [--types corridor room complex1 complex2] [--task-seed 0] [--pose-active]
  -> <폴더>/tasks_<유형>.json (과제 300 · 최단 · 직선 · 구간 · 듬성 필요 표지) · <폴더>/DIST-TABLE.md (구간별 분포 표)
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from foothold_s2.nav import grade_map as gm
from foothold_s2.nav import nav_score as ns
from foothold_s2.nav import room_generator as rg

NAV = Path(__file__).resolve().parent
TYPES = ("corridor", "room", "complex1", "complex2")
TITLES = {"corridor": "Corridor", "room": "Room", "complex1": "Complex-1", "complex2": "Complex-2"}
PAPER_BANDS_M = ((5.0, 10.0), (10.0, 20.0), (20.0, 30.0))          # 2604.26504.txt:727
PER_BAND = 100
SEEDS = tuple(range(10))                                           # 2604.26504.txt:727 「10 different seeds」 (무엇을 바꾸는지는 원문에 없음)


def room_path(kind: str, rooms: str = "yaml", seed: int = 0) -> Path:
    return NAV / "rooms" / (f"bench_{kind}.yaml" if rooms == "yaml" else f"bench_wfc_{kind}_s{seed}.yaml")


# WFC 네 유형 (원문 727 행의 서술만 있고 치수 · 확률은 원문에 없음 -> 전부 가정). 원문 IV-A (42 행): WFC 타일 (평지 · 거친 면 · 막힌 면) +
# 무작위 벽 · 탁자 · 떠 있는 상자. room_generator 의 두 배치를 쓴다: maze (길 · 벽 · 문 · 막다른 길) · old (타일 + 흩은 장애물).
#   Corridor  = 막다른 복도: maze · 벽 많이 (wall_keep 0.75) · 문 적게 · 탁자 · 상자 없음 (머리 위 장애 없음)
#   Room      = 반쯤 닫힌 방 + 가운데 머리 위 장애: maze · wall_keep 0.55 + 가운데 8 x 8 m 에 탁자 · 떠 있는 상자 (WFC_ROOM_CENTER)
#   Complex-1 = 빽빽한 장애 + 머리 위 장애: old · 막힌 타일 · 벽 · 탁자 · 상자 확률 높게
#   Complex-2 = 얽힌 배치 + 머리 위 장애: maze · wall_keep 0.55 · 문 많이 + 탁자 · 상자 흩음
WFC_PRESETS = {
    "corridor": dict(layout="maze", wall_keep=0.75, keep_choices=(), door_frac=0.2, p_table=0.0, p_box=0.0, p_pillar=0.0, weights=(5.0, 2.0, 2.0, 0.05)),
    "room": dict(layout="maze", wall_keep=0.55, keep_choices=(), door_frac=0.35, p_table=0.0, p_box=0.0, p_pillar=0.05, weights=(5.0, 2.0, 2.0, 0.05)),
    "complex1": dict(layout="old", p_wall=0.5, p_table=0.3, p_box=0.3, weights=(3.0, 3.0, 3.0, 0.05)),
    "complex2": dict(layout="maze", wall_keep=0.55, keep_choices=(), door_frac=0.6, p_table=0.15, p_box=0.15, p_pillar=0.05, weights=(4.0, 3.0, 2.0, 0.05)),
}
WFC_ROOM_CENTER = (6.0, 14.0, 6, 0.5)          # Room: 가운데 x y 6~14 m 에 머리 위 장애 6 개 · 상자 비율 0.5 (가정)
# 자세가 필요한 낮은 천장 판 (lead 19:34 「원문 Room/Complex 수준으로 · 자세 켜면 통과 칸이 뚜렷이 늘어야」). 등급 지도는 천장 여유
# crawl_clearance 0.3 ~ stand_clearance 0.5 m 만 「숙여 지남」 으로 친다 (grade_map.py:70-71) -> 판 아래면 z0 를 U[0.30, 0.45] 로 (모두 가정).
# 유형: 구역 (x y lo~hi m) · 판 수 · 판 한 변 길이 범위 (m). Corridor 는 판 없음 (원문: 벽으로 막힌 길만 시험).
WFC_OVERHEAD = {"room": (5.0, 15.0, 22, (1.0, 2.0)), "complex1": (1.0, 19.0, 26, (0.8, 1.6)), "complex2": (1.0, 19.0, 20, (0.8, 1.6))}
WFC_OVERHEAD_Z0 = (0.30, 0.45)
WFC_OVERHEAD_H = 0.3


def wfc_spec(kind: str, seed: int) -> dict:
    """WFC 유형 방 명세 (room_generator.make_room 의 수락 조건 그대로 · sparse 패치 없음 · 모두 가정)."""
    import dataclasses

    cfg = dataclasses.replace(rg.FIRST_ROUND_CFG, **WFC_PRESETS[kind])
    spec, _room = rg.make_room(seed, cfg)
    if kind == "room":
        lo, hi, n, box_frac = WFC_ROOM_CENTER
        r = np.random.default_rng(seed + 17)
        for _ in range(n):
            x, y = (round(float(v), 1) for v in r.uniform(lo, hi - 1.0, 2))
            spec["primitives"].append({"type": "box", "x": x, "y": y, "w": 0.8, "z0": 0.35, "h": 0.5} if r.random() < box_frac
                                      else {"type": "table", "x": x, "y": y, "w": 0.8, "top": 0.7})
    if kind in WFC_OVERHEAD:
        lo, hi, n, (wl, wh) = WFC_OVERHEAD[kind]
        r = np.random.default_rng(seed + 29)
        for _ in range(n):
            w = round(float(r.uniform(wl, wh)), 1)
            x, y = (round(float(v), 1) for v in r.uniform(lo, hi - w, 2))
            spec["primitives"].append({"type": "box", "x": x, "y": y, "w": w, "z0": round(float(r.uniform(*WFC_OVERHEAD_Z0)), 2), "h": WFC_OVERHEAD_H})
    spec["bench"] = {"type": kind, "preset": {k: (list(v) if isinstance(v, tuple) else v) for k, v in WFC_PRESETS[kind].items()},
                     "overhead": WFC_OVERHEAD.get(kind), "overhead_z0": list(WFC_OVERHEAD_Z0), "assumption": "원문에 치수 · 확률 없음"}
    return spec


def write_wfc_rooms(seed: int = 0) -> list[Path]:
    import yaml

    out = []
    for kind in TYPES:
        path = room_path(kind, "wfc", seed)
        path.write_text("# 분류: B/항법 · HiPAN 원문 시험 방 (WFC 유형 · bench_tasks.wfc_spec 이 만듦 · 손으로 고치지 않음)\n"
                        f"# 작성: Claude 세션 (오흥재 지시, opus-code-lx) · 유형 {kind} · 시드 {seed}\n"
                        "# 근거: 2604.26504.txt:42 · 727 (서술만) · 치수 · 확률은 원문에 없어 가정 (bench_tasks.WFC_PRESETS)\n"
                        + yaml.safe_dump(wfc_spec(kind, seed), allow_unicode=True, sort_keys=False), encoding="utf-8")
        out.append(path)
    return out


START_SEP_M = 0.3            # 과제마다 다른 시작점 (평가가 몸이 선 자리로 과제를 가른다 · hl_bench.BENCH_TOL_M 의 여섯 배)


def unique_start_tasks(g, rng, *, per_band: int, bands, max_tries: int = 40000) -> list:
    """nav_score.make_tasks 와 같은 규칙 (시작 = 무충돌 표본 · 목표 = 그 시작에서 최단 길이가 구간 안인 평지 셀) 이되 시작점 하나에 과제 하나.
    (make_tasks 는 한 시작점에서 구간마다 과제를 뽑아 같은 시작이 셋까지 겹친다: 평가에서 시작으로 과제를 가를 수 없다.)"""
    need = [per_band] * len(bands)
    used: list = []
    tasks: list = []
    for start in gm.sample_free_points(g, rng, max_tries):
        if not any(need):
            break
        if used and np.min(np.linalg.norm(np.asarray(used) - start, axis=1)) < START_SEP_M:
            continue
        d = ns.geodesic_map(g, start)
        d_free = ns.geodesic_map(g, start, allow_sparse=False)
        order = sorted((b for b in range(len(bands)) if need[b] > 0), key=lambda b: -need[b])
        for b in order:
            lo, hi = bands[b]
            cand = np.argwhere((d >= lo) & (d < hi) & np.isin(g.grade, (gm.FREE, gm.CONNECTED_ROUGH)))
            if not len(cand):
                continue
            cell = cand[rng.integers(0, len(cand))]
            tasks.append(ns.Task(tuple(map(float, start)), tuple(map((lambda v: float((v + 0.5) * g.res)), cell)),
                                 float(d[tuple(cell)]), b, bool(np.isinf(d_free[tuple(cell)]))))
            need[b] -= 1
            used.append(np.asarray(start, float))
            break
    if any(need):
        raise RuntimeError(f"could not make {need} more tasks with distinct starts (the room is too small or blocked)")
    return sorted(tasks, key=lambda t: t.band)


def make_type_tasks(kind: str, *, task_seed: int = 0, pose_active: bool = False, table=None, per_band: int = PER_BAND,
                    rooms: str = "yaml", room_seed: int = 0) -> dict:
    spec_path = room_path(kind, rooms, room_seed)
    spec = rg.load_spec(spec_path)
    room = rg.build_room(spec)
    table = table or gm.load_grade_table(NAV / "grade_table_draft.yaml")
    g = gm.make_grade_map(room, table, pose_active=pose_active)
    tasks = unique_start_tasks(g, np.random.default_rng(task_seed), per_band=per_band, bands=PAPER_BANDS_M)
    g_stand = gm.make_grade_map(room, table, pose_active=False) if pose_active else None
    rows = []
    for i, t in enumerate(tasks):
        euclid = float(np.hypot(t.goal[0] - t.start[0], t.goal[1] - t.start[1]))
        row = {"id": i, "band": int(t.band), "start_xy": list(t.start), "goal_xy": list(t.goal),
               "shortest_m": round(float(t.shortest_m), 4), "euclid_m": round(euclid, 4), "needs_sparse": bool(t.needs_sparse)}
        if g_stand is not None:                    # 자세 없이 (서서) 가는 최단 · 못 가면 None: 자세가 줄여 주는 길이 · 자세 없이는 못 가는 과제
            d = ns.geodesic_map(g_stand, np.asarray(t.start))[tuple(int(v / g.res) for v in t.goal)]
            row["shortest_stand_m"] = round(float(d), 4) if np.isfinite(d) else None
        rows.append(row)
    return {"format": "foothold-hipan-bench-tasks/1", "type": kind, "title": TITLES[kind],
            "room_spec": spec_path.relative_to(NAV).as_posix(), "room_spec_sha256": hashlib.sha256(spec_path.read_bytes()).hexdigest(),   # room_spec: nav/ 기준 상대 경로 (Runpod 사본에서도 같은 파일)
            "size_m": float(spec.get("size_m", rg.ROOM_M)), "task_seed": int(task_seed), "pose_active": bool(pose_active),
            "bands_m": [list(b) for b in PAPER_BANDS_M], "per_band": per_band, "eval_seeds": list(SEEDS),
            "success_m": ns.SUCCESS_M, "distance": "shortest path on the grade map (assumption; paper does not say)",
            "tasks": rows}


def posture_cols(rs) -> str:
    if not rs or "shortest_stand_m" not in rs[0]:
        return "자세 지도 아님"
    blocked = sum(r["shortest_stand_m"] is None for r in rs)
    shorter = sum(r["shortest_stand_m"] is not None and r["shortest_stand_m"] > r["shortest_m"] + 0.5 for r in rs)
    return f"{blocked} · {shorter}"


def band_table(docs: list[dict]) -> str:
    lines = ["| 유형 | 구간 (m) | 과제 수 | 최단 중앙 · 최소 · 최대 (m) | 직선 중앙 · 최소 · 최대 (m) | 최단/직선 중앙 | 듬성 필요 | 자세 없이 못 감 · 자세로 짧아짐 (과제 수) |",
             "|---|---|---|---|---|---|---|---|"]
    for d in docs:
        for b, (lo, hi) in enumerate(d["bands_m"]):
            rs = [r for r in d["tasks"] if r["band"] == b]
            s = np.array([r["shortest_m"] for r in rs]); e = np.array([r["euclid_m"] for r in rs])
            ratio = np.median(s / np.maximum(e, 1e-6))
            lines.append(f"| {d['title']} | [{lo:g}, {hi:g}] | {len(rs)} | {np.median(s):.2f} · {s.min():.2f} · {s.max():.2f} | "
                         f"{np.median(e):.2f} · {e.min():.2f} · {e.max():.2f} | {ratio:.2f} | {sum(r['needs_sparse'] for r in rs)} | {posture_cols(rs)} |")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--types", nargs="+", default=list(TYPES), choices=TYPES)
    ap.add_argument("--task-seed", type=int, default=0)
    ap.add_argument("--rooms", choices=("yaml", "wfc"), default="yaml", help="yaml = rooms/bench_<유형>.yaml (손으로 적은 임시) · wfc = WFC 유형 방을 만들어 rooms/bench_wfc_<유형>_s<시드>.yaml 로 쓰고 씀")
    ap.add_argument("--room-seed", type=int, default=0)
    ap.add_argument("--pose-active", action="store_true", help="머리 위 장애 아래를 자세 명령으로 지날 수 있다고 보고 등급 지도를 만든다")
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if a.rooms == "wfc":
        for p in write_wfc_rooms(a.room_seed):
            print(f"wfc room -> {p}", flush=True)
    docs = []
    for kind in a.types:
        doc = make_type_tasks(kind, task_seed=a.task_seed, pose_active=a.pose_active, rooms=a.rooms, room_seed=a.room_seed)
        path = out / f"tasks_{kind}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        docs.append(doc)
        print(f"{kind}: {len(doc['tasks'])} tasks -> {path}", flush=True)
    (out / "DIST-TABLE.md").write_text(band_table(docs) + "\n", encoding="utf-8")
    print(band_table(docs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
