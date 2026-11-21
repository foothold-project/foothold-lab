"""HiPAN 원문 시험 과제 (lead 11/21 18:52 · HIPAN-FIDELITY-ORDER C · opus-code-lx). numpy · scipy 만, Kit 없음.

원문 (2604.26504.txt:727-728): 시험 환경 넷 (Corridor · Room · Complex-1 · Complex-2) 마다 거리 구간 [5, 10] · [10, 20] · [20, 30] m 에서
충돌 없는 시작-목표 쌍을 100 개씩 = 300 과제, 시드 10 개의 평균 · 표준편차. SR 은 목표 0.2 m 안 도착 비율, SPL 은 최단 대 실제 길이.

원문에 없는 것 (지어내지 않고 가정으로 적음):
  - 시험 환경의 치수 (학습 환경만 20 x 20 m 로 적힘, 535 행) -> 여기서는 20 x 20 m.
  - 거리를 최단 경로로 재는지 직선으로 재는지 -> 최단 경로 길이 (nav_score.make_tasks) · 직선 거리도 같이 적는다.
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


def room_path(kind: str) -> Path:
    return NAV / "rooms" / f"bench_{kind}.yaml"


def make_type_tasks(kind: str, *, task_seed: int = 0, pose_active: bool = False, table=None, per_band: int = PER_BAND) -> dict:
    spec_path = room_path(kind)
    spec = rg.load_spec(spec_path)
    room = rg.build_room(spec)
    table = table or gm.load_grade_table(NAV / "grade_table_draft.yaml")
    g = gm.make_grade_map(room, table, pose_active=pose_active)
    tasks = ns.make_tasks(g, np.random.default_rng(task_seed), per_band=per_band, bands=PAPER_BANDS_M)
    rows = []
    for i, t in enumerate(tasks):
        euclid = float(np.hypot(t.goal[0] - t.start[0], t.goal[1] - t.start[1]))
        rows.append({"id": i, "band": int(t.band), "start_xy": list(t.start), "goal_xy": list(t.goal),
                     "shortest_m": round(float(t.shortest_m), 4), "euclid_m": round(euclid, 4),
                     "needs_sparse": bool(t.needs_sparse)})
    return {"format": "foothold-hipan-bench-tasks/1", "type": kind, "title": TITLES[kind],
            "room_spec": str(spec_path), "room_spec_sha256": hashlib.sha256(spec_path.read_bytes()).hexdigest(),
            "size_m": float(spec.get("size_m", rg.ROOM_M)), "task_seed": int(task_seed), "pose_active": bool(pose_active),
            "bands_m": [list(b) for b in PAPER_BANDS_M], "per_band": per_band, "eval_seeds": list(SEEDS),
            "success_m": ns.SUCCESS_M, "distance": "shortest path on the grade map (assumption; paper does not say)",
            "tasks": rows}


def band_table(docs: list[dict]) -> str:
    lines = ["| 유형 | 구간 (m) | 과제 수 | 최단 중앙 · 최소 · 최대 (m) | 직선 중앙 · 최소 · 최대 (m) | 최단/직선 중앙 | 듬성 필요 |",
             "|---|---|---|---|---|---|---|"]
    for d in docs:
        for b, (lo, hi) in enumerate(d["bands_m"]):
            rs = [r for r in d["tasks"] if r["band"] == b]
            s = np.array([r["shortest_m"] for r in rs]); e = np.array([r["euclid_m"] for r in rs])
            ratio = np.median(s / np.maximum(e, 1e-6))
            lines.append(f"| {d['title']} | [{lo:g}, {hi:g}] | {len(rs)} | {np.median(s):.2f} · {s.min():.2f} · {s.max():.2f} | "
                         f"{np.median(e):.2f} · {e.min():.2f} · {e.max():.2f} | {ratio:.2f} | {sum(r['needs_sparse'] for r in rs)} |")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--types", nargs="+", default=list(TYPES), choices=TYPES)
    ap.add_argument("--task-seed", type=int, default=0)
    ap.add_argument("--pose-active", action="store_true", help="머리 위 장애 아래를 자세 명령으로 지날 수 있다고 보고 등급 지도를 만든다")
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    docs = []
    for kind in a.types:
        doc = make_type_tasks(kind, task_seed=a.task_seed, pose_active=a.pose_active)
        path = out / f"tasks_{kind}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        docs.append(doc)
        print(f"{kind}: {len(doc['tasks'])} tasks -> {path}", flush=True)
    (out / "DIST-TABLE.md").write_text(band_table(docs) + "\n", encoding="utf-8")
    print(band_table(docs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
