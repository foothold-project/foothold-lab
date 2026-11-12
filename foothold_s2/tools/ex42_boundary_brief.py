"""EX-42 경계 분석 한 장 (lead 11/12 · 팀장 13:36 「250 판단 → 다음 구간 적용」).

경계 하나의 원자료를 읽어 한 표로 모은다. 판정은 하지 않는다 (판정은 P1 · 규칙표 몫). 빠진 원자료는 칸을
'없음' 으로 남기고 지어내지 않는다.

    python -m foothold_s2.tools.ex42_boundary_brief --label m250 \
        --score <boundary>/ex42_score.json --d44 <boundary>/d44 \
        --g1 <g1 map_modes.json> --g1b <g1b map_modes.json> --events <run dir> --at 250 \
        [--prev <앞 경계 brief.json>] --out <brief.json>
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import statistics as st
from pathlib import Path

import numpy as np

CURVE_TAGS = ("Train/mean_reward", "Curriculum/terrain_levels", "Metrics/base_velocity/error_vel_xy",
              "Metrics/base_velocity/error_vel_yaw", "Episode_Termination/bad_orientation", "Policy/mean_noise_std",
              "Episode_Reward/ex41_foot_slip")


def _yaw_deg(q):
    w, x, y, z = q[..., 0], q[..., 1], q[..., 2], q[..., 3]
    return np.degrees(np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))


def d44_block(folder: Path) -> dict:
    out = {}
    for case in sorted(folder.glob("*.json")):
        if case.name == "d44_cells.json":
            continue
        doc = json.loads(case.read_text(encoding="utf-8"))
        per = doc.get("per_env") or []
        reasons = {}
        for e in per:
            if not e.get("success"):
                reasons[e.get("reason")] = reasons.get(e.get("reason"), 0) + 1
        row = {"success": doc.get("success_count"), "envs": doc.get("envs"), "fail_reasons": reasons}
        trace = case.with_suffix(".npz")
        if doc.get("task") == "stop_restart" and trace.is_file():
            z = np.load(trace)
            yaw = _yaw_deg(z["root_quat_w"])
            latch = z["top_latched_at"]
            end = np.where(latch >= 0, latch, yaw.shape[0] - 1)
            dh = np.array([yaw[end[e], e] - yaw[0, e] for e in range(yaw.shape[1])])
            dh = np.abs((dh + 180) % 360 - 180)
            ok = np.array([bool(e.get("success")) for e in per])
            row["heading_drift_deg_median"] = {"success": float(np.median(dh[ok])) if ok.any() else None,
                                               "fail": float(np.median(dh[~ok])) if (~ok).any() else None}
            row["heading_over_10deg"] = int((dh > 10).sum())
        out[case.stem] = row
    return out


def command_block(path: Path) -> dict:
    """G1 / G1b: 명령 축 진행 비율 (1 - 오차/명령 크기) 과 생존. 명령 0 축은 오차만."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = {}
    for name, cmd in doc["commands"].items():
        r = doc["modes"]["eval_gt"][name]
        pe = r["per_env"]
        med = lambda k: st.median([e[k] for e in pe])
        err = {"vx": med("vx_abs_error_mean_alive_mps"), "vy": med("vy_abs_error_mean_alive_mps"),
               "wz": med("wz_abs_error_mean_alive_radps")}
        follow = {}
        for axis, value in zip(("vx", "vy", "wz"), cmd):
            if abs(value) > 1e-9:
                follow[axis] = round(1 - err[axis] / abs(value), 3)
        rows[name] = {"command": cmd, "alive": r["alive_envs_at_end"],
                      "error": {k: round(v, 3) for k, v in err.items()}, "follow": follow}
    return {"source": str(path), "rows": rows}


def curve_block(run: Path, at: int, window: int = 50) -> dict:
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
    files = sorted(glob.glob(str(run / "events*")))
    if not files:
        return {"missing": "events"}
    ea = EventAccumulator(files[-1], size_guidance={"scalars": 0})
    ea.Reload()
    have = set(ea.Tags()["scalars"])
    out = {}
    for tag in CURVE_TAGS:
        if tag not in have:
            continue
        pts = [(s.step, s.value) for s in ea.Scalars(tag) if at - window < s.step <= at]
        if pts:
            out[tag] = round(float(np.mean([v for _, v in pts])), 4)
    return {"window": [at - window + 1, at], "mean": out}


def score_block(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    items = {k: v.get("judgement") for k, v in (doc.get("maintenance_items") or {}).items()}
    return {"judgement": doc.get("judgement"), "maintenance_judgement": doc.get("maintenance_judgement"),
            "maintenance_items": items, "reason": doc.get("reason")}


def build(args) -> dict:
    brief = {"format": "foothold-ex42-boundary-brief/1", "label": args.label, "at": args.at}
    brief["score"] = score_block(args.score) if args.score and args.score.is_file() else "없음"
    brief["d44"] = d44_block(args.d44) if args.d44 and args.d44.is_dir() else "없음"
    brief["g1"] = command_block(args.g1) if args.g1 and args.g1.is_file() else "없음"
    brief["g1b"] = command_block(args.g1b) if args.g1b and args.g1b.is_file() else "없음"
    brief["curves"] = curve_block(args.events, args.at) if args.events else "없음"
    if args.prev and args.prev.is_file():
        brief["prev_label"] = json.loads(args.prev.read_text(encoding="utf-8")).get("label")
    return brief


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True)
    p.add_argument("--at", type=int, required=True)
    p.add_argument("--score", type=Path)
    p.add_argument("--d44", type=Path)
    p.add_argument("--g1", type=Path)
    p.add_argument("--g1b", type=Path)
    p.add_argument("--events", type=Path)
    p.add_argument("--prev", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    brief = build(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(brief, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
