"""HiPAN bench task table for the 3D (no-posture) policy: the same tasks as a posture table, paths without posture (lead 11/22 13:39).

The rooms, starts and goals are copied unchanged (no new draw). Only the path side changes:
  * pose_active False, so hl_bench.install_bench_table plans every task on the training grade map (no crawl cells) and the
    per-env time limit (path / 0.3 + 10 s) follows that path;
  * shortest_m = shortest_stand_m (the standing shortest on the same body-clearance map the source table used);
    a task with no standing path on that map keeps its row (bench needs equal task counts per room) with
    stand_blocked True and shortest_m = the training-map A* length, so a scorer can leave it out;
  * shortest_pose_m keeps the source shortest_m.

  python -m foothold_s2.nav.bench_tasks_stand --src foothold_s2/nav/bench_tasks_wfc_s0_body25 --out foothold_s2/nav/bench_tasks_wfc_s0_body25_stand
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from foothold_s2.nav import bench_tasks as bt
from foothold_s2.nav import grade_map as gm
from foothold_s2.nav import gvd_astar
from foothold_s2.nav import room_generator as rg


def path_length(points) -> float:
    p = np.asarray(points, float)
    return float(np.sum(np.linalg.norm(np.diff(p, axis=0), axis=1))) if len(p) > 1 else 0.0


def stand_doc(doc: dict, table: dict) -> tuple[dict, dict]:
    if not doc.get("pose_active"):
        raise ValueError(f"{doc['type']}: the source table is already without posture")
    if any("shortest_stand_m" not in t for t in doc["tasks"]):
        raise ValueError(f"{doc['type']}: the source table has no shortest_stand_m")
    room = rg.build_room(rg.load_spec(bt.NAV / doc["room_spec"]))
    g = gm.make_grade_map(room, table, pose_active=False)
    rows, blocked, no_path = [], 0, 0
    for t in doc["tasks"]:
        pp = gvd_astar.find_path(g, np.asarray(t["start_xy"], float), np.asarray(t["goal_xy"], float), straighten=True)
        if not pp.found:
            no_path += 1
        train_m = round(path_length(pp.points), 4) if pp.found else None
        row = {k: v for k, v in t.items() if k != "shortest_stand_m"}
        row["shortest_pose_m"] = t["shortest_m"]
        row["train_path_m"] = train_m
        if t["shortest_stand_m"] is None:
            blocked += 1
            row["stand_blocked"] = True
            row["shortest_m"] = train_m
        else:
            row["stand_blocked"] = False
            row["shortest_m"] = t["shortest_stand_m"]
        rows.append(row)
    if no_path:
        raise ValueError(f"{doc['type']}: {no_path} tasks have no path on the training grade map (hl_bench would refuse them)")
    out = {**doc, "pose_active": False, "tasks": rows,
           "derived_from": {"pose_active": True, "rule": "same rooms/starts/goals; shortest_m = shortest_stand_m (or training-map A* when stand_blocked)"}}
    return out, {"type": doc["type"], "tasks": len(rows), "stand_blocked": blocked}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    src, out = Path(a.src), Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} exists (never overwritten)")
    table = gm.load_grade_table(bt.NAV / "grade_table_draft.yaml")
    docs = [(p, json.loads(p.read_text(encoding="utf-8"))) for p in sorted(src.glob("tasks_*.json"))]
    if not docs:
        raise SystemExit(f"no tasks_*.json in {src}")
    made = [stand_doc(d, table) for _, d in docs]
    out.mkdir(parents=True)
    for (p, _), (doc, _) in zip(docs, made):
        (out / p.name).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    counts = [c for _, c in made]
    print(json.dumps({"out": str(out), "types": counts, "stand_blocked_total": sum(c["stand_blocked"] for c in counts)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
