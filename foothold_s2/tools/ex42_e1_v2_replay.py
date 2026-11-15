"""Read-only E1 v2 history table; old GT-only G1b never supplies missing modes."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import yaml

from foothold_s2.ex42_e1_v2 import _map_cell, _source, judge_cells, measure_cells


def build(run: Path, g1b_root: Path, plan: dict) -> list[dict]:
    rows = []
    for iteration in range(250, 2251, 250):
        folder = run / "eval" / "scores" / f"m{iteration}"
        score_file = folder / "ex42_score.json"
        if not score_file.is_file():
            rows.append({"iteration": iteration, "state": "미측정", "reason": "ex42_score.json 없음"})
            continue
        score = json.loads(score_file.read_text(encoding="utf-8-sig"))
        cells = measure_cells(folder, score["checkpoint_sha256"], 42)
        for level in (0, 5):
            raw = g1b_root / f"m{iteration}seg" / f"hipan_g1b_L{level}" / "map_modes.json"
            if not raw.is_file():
                continue
            doc = _source(raw, score["checkpoint_sha256"], 42, ("eval_gt",), level=level)
            cells["low"][f"L{level}"] = {"eval_gt": {
                case: _map_cell(raw, doc, "eval_gt", case)
                for case in ("fwd0.1", "fwd0.2", "side+0.2", "side+0.4", "side-0.4")}}
            cells["sources"][f"historical_low_L{level}"] = str(raw)
        v2 = judge_cells(cells, plan)
        turn = [value["success_count"] for key, value in score.get("d44_cells", {}).items()
                if key.startswith("turn_")]
        stop = [value["success_count"] for key, value in score.get("d44_cells", {}).items()
                if key.startswith("stop_restart_")]
        row = {"iteration": iteration, "state": "역사 원자료 진단, 공식 판정 아님",
               "checkpoint_sha256": score["checkpoint_sha256"],
               "maintenance": score.get("maintenance_judgement"),
               "d44_turn_min_success": min(turn) if turn else None,
               "d44_stop_min_success_record_only": min(stop) if stop else None,
               "v2_partial_judgement": v2["judgement"],
               "missing_judge_cells": sum(value.get("judgement") == "HOLD" and value.get("reason") == "평가 열 없음"
                                          for value in v2["items"].values()),
               "sources": cells["sources"]}
        for level in (0, 5):
            for case in ("fwd0.1", "fwd0.2"):
                cell = cells["low"][f"L{level}"].get("eval_gt", {}).get(case)
                row[f"L{level}_{case}_GT_R"] = round(cell["R"], 6) if cell else None
        for mode in ("eval_gt", "eval_pred"):
            yaw = cells["yaw"].get(mode, {}).get("fwd1.0")
            row[f"Y1_{mode}_fwd1.0_median_abs_rad"] = round(yaw["median_abs_rad"], 6) if yaw else None
            row[f"Y1_{mode}_fwd1.0_p90_abs_rad"] = round(yaw["p90_abs_rad"], 6) if yaw else None
        rows.append(row)
    return rows


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--g1b-root", type=Path, required=True)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    plan = yaml.safe_load(a.plan.read_text(encoding="utf-8-sig"))
    rows = build(a.run, a.g1b_root, plan)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "e1_v2_history.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    keys = sorted(set().union(*(row.keys() for row in rows)) - {"sources"})
    with (a.out / "e1_v2_history.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows({k: row.get(k) for k in keys} for row in rows)
    print(json.dumps({"rows": len(rows), "output": str(a.out),
                      "present": sum(row["state"] != "미측정" for row in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
