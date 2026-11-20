"""New E2 v1 boundary judge: raise a kind's level cap by the MAP GAIN (right map - flat map), not by the old window pass.

sonnet-code-lx 11/20 (lead 13:56, planner DESIGN-E2-V1-1120.md v1.1 sections 3 and 4; the rule is fixed by that file, not by this code).
Measurement only here: this module reads the `env_arrays_<mode>_*.npz` files the child runs write (see
`foothold_s2/scripts/ex42_v1_boundary_eval.sh`, which makes them) and writes the ladder evidence file the existing D axis reads
(`raise_kind_caps`: entry b - 1 = {family/kind: {first_window_pass: bool}}). Nothing here starts training or touches a run.

Per kind, at the kind's current level cap, two speeds (0.7, 1.0), five inputs (gt = right map, pred = reconstructed map, flat = flat map,
shift = map pushed 20 cm ahead, off = map tokens masked), seeds 42 43 44 averaged, 64 envs:
  crossed  = envs whose farthest x (max of root_x_local_m) is at least first gap end + 0.3 m (balance beams: 3.0 + 0.3); the C/box kind has no
             gap, its count is the envs alive at the end (`alive`), stated in the receipt.
  floor cell   = right map crossed < FLOOR (8): left out of the judgement (nobody crosses, the gain cannot show).
  ceiling cell = flat map crossed > CEILING (56): left out, and written as a "raise this kind" signal (a flat map already crosses).
Graduation (all four, on the cells that carry the gain):
  1 gain (gt - flat crossed) >= 10 in at least `need` judgeable cells, need = 2 speeds - ceiling speeds (both speeds judgeable: both must show it)
  2 right map crossed >= 48 in those cells
  3 reconstructed map crossed not more than 10 below the right map in those cells
  4 right map alive not more than 10 below the map-off alive in those cells
Both speeds ceiling -> graduated (the kind is raised: "ceiling counts as graduation"). No judgeable cell and no ceiling -> "undecidable"
(neither pass nor fail; `first_window_pass` stays false, the receipt says why).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path

import numpy as np

FLOOR = 8
CEILING = 56
GAIN = 10.0
CROSS_MIN = 48
SLACK = 10.0
SPEEDS = ("0.7", "1.0")
INPUTS = ("gt", "pred", "flat", "shift", "off")
MODE_OF = {"gt": "eval_gt", "pred": "eval_pred", "flat": "eval_gt", "shift": "eval_gt", "off": "probe_prop_only"}
# which output folder (tag suffix) each input comes from: the main run writes gt, pred, off; flat and shift have their own runs
SUFFIX_OF = {"gt": "main", "pred": "main", "off": "main", "flat": "flat", "shift": "shift20"}


def count_crossed(npz_path: str | Path, threshold: float | None) -> tuple[int, int]:
    """(crossed, alive) of one run file. threshold None (C/box): crossed = alive."""
    z = np.load(npz_path)
    alive = z["alive_end"].astype(bool)
    if threshold is None:
        return int(alive.sum()), int(alive.sum())
    return int((z["root_x_local_m"].max(0) >= threshold).sum()), int(alive.sum())


def read_cell(root: str | Path, kind_tag: str, speed: str, seeds=(42, 43, 44), threshold: float | None = None) -> dict | None:
    """Seed-mean {input: (crossed, alive)} of one kind and speed, or None when a file is missing.
    Folder layout: <root>/<kind_tag>_v<speed>_s<seed>_<main|flat|shift20>/env_arrays_<mode>_*.npz (+ DONE)."""
    acc = {i: [] for i in INPUTS}
    for seed in seeds:
        for inp in INPUTS:
            d = Path(root) / f"{kind_tag}_v{speed}_s{seed}_{SUFFIX_OF[inp]}"
            files = sorted(glob.glob(str(d / f"env_arrays_{MODE_OF[inp]}_*.npz")))
            if not files or not (d / "DONE").is_file():
                return None
            acc[inp].append(count_crossed(files[0], threshold))
    return {i: (float(np.mean([v[0] for v in acc[i]])), float(np.mean([v[1] for v in acc[i]]))) for i in INPUTS}


def judge_kind(cells: dict[str, dict | None]) -> dict:
    """cells = {speed: {input: (crossed, alive)} or None}. Returns the verdict with every number behind it."""
    out = {"cells": {}, "ceiling_speeds": [], "floor_speeds": [], "passing_speeds": []}
    judgeable = []
    for sp, c in cells.items():
        if c is None:
            out["cells"][sp] = {"state": "missing"}
            continue
        gt, flat = c["gt"][0], c["flat"][0]
        row = {"gt_crossed": gt, "pred_crossed": c["pred"][0], "flat_crossed": flat, "shift_crossed": c["shift"][0], "off_crossed": c["off"][0],
               "gt_alive": c["gt"][1], "off_alive": c["off"][1], "gain": gt - flat}
        if flat > CEILING:
            row["state"] = "ceiling"; out["ceiling_speeds"].append(sp)
        elif gt < FLOOR:
            row["state"] = "floor"; out["floor_speeds"].append(sp)
        else:
            row["state"] = "judgeable"; judgeable.append(sp)
            row["tests"] = {"gain": row["gain"] >= GAIN, "cross": gt >= CROSS_MIN, "pred": row["pred_crossed"] >= gt - SLACK,
                            "harm": row["gt_alive"] >= row["off_alive"] - SLACK}
            if all(row["tests"].values()):
                out["passing_speeds"].append(sp)
        out["cells"][sp] = row
    missing = [sp for sp, c in cells.items() if c is None]
    need = len(cells) - len(out["ceiling_speeds"])
    if missing:
        out.update(verdict="incomplete", first_window_pass=False, raise_cap=False, need=need)
    elif need == 0:
        out.update(verdict="ceiling", first_window_pass=True, raise_cap=True, need=0)
    elif not judgeable:
        out.update(verdict="undecidable", first_window_pass=False, raise_cap=False, need=need)
    else:
        ok = len(out["passing_speeds"]) >= need
        out.update(verdict="graduate" if ok else "not_yet", first_window_pass=ok, raise_cap=ok, need=need)
    return out


def write_evidence(ladder_list: Path, boundary: int, kinds: dict[str, dict], base: list | None = None) -> list:
    """Write ladder_outcomes_list.json: entry b - 1 holds {family/kind: {first_window_pass, target_level_reached}} for the boundary that just
    ended. An earlier file (`base`) keeps its earlier entries; a missing earlier boundary is {} (the same padding as write_ladder_evidence)."""
    entries = (list(base or []) + [{}] * (boundary - 1))[:boundary - 1]
    entry = {k: {"first_window_pass": bool(v["first_window_pass"]), "target_level_reached": False} for k, v in kinds.items()}
    entries.append(entry)
    Path(ladder_list).parent.mkdir(parents=True, exist_ok=True)
    Path(ladder_list).write_text(json.dumps(entries, sort_keys=True), encoding="utf-8")
    return entries


def find_earlier(out: Path, boundary: int, interval: int = 250) -> list | None:
    """The nearest earlier boundary's ladder_outcomes_list.json next to `out` (<scores>/m<back * interval>/), like write_ladder_evidence; None when none."""
    for back in range(boundary - 1, 0, -1):
        previous = Path(out).parent / f"m{back * interval}" / "ladder_outcomes_list.json"
        if previous.is_file():
            return json.loads(previous.read_text(encoding="utf-8"))
    return None


def first_gap_end(mesh_dir: str | Path, family: str, kind: str, col: int, level: int) -> float:
    """Local x (m, from the env origin) of the end of the first void on the centre line of tile (level, col), the farthest-top ray cast of
    the gate_ends.py of the map-gain tables. Balance beams: 3.0 (the table value). Needs trimesh (eval environment only)."""
    if kind == "balance_beams":
        return 3.0
    import trimesh
    z = np.load(Path(mesh_dir) / "terrain_mesh.npz", allow_pickle=True)
    verts, faces, origins = z["vertices"], z["faces"], z["origins"]
    centre = verts[faces].mean(axis=1)
    o = origins[level, col]
    keep = (np.abs(centre[:, 0] - o[0] - 5) < 7.0) & (np.abs(centre[:, 1] - o[1]) < 6.5)
    mesh = trimesh.Trimesh(vertices=verts, faces=faces[keep], process=False)
    s = np.arange(-1.0, 9.0, 0.02)
    org = np.stack([o[0] + s, o[1] + 0 * s, np.full(len(s), 10.0)], 1)
    loc, ray, _ = mesh.ray.intersects_location(org, np.tile([0, 0, -1.0], (len(s), 1)), multiple_hits=True)
    h = np.full(len(s), np.nan)
    for p, r in zip(loc, ray):
        if np.isnan(h[r]) or p[2] > h[r]:
            h[r] = p[2]
    hole = ~(np.nan_to_num(h - o[2], nan=-9) > -0.2)
    ends = [float(s[i + 1]) for i in np.flatnonzero(np.diff(hole.astype(int))) if hole[i] and s[i + 1] > 0.5]
    if not ends:
        raise ValueError(f"no gap found on {family}/{kind} level {level} column {col}")
    return ends[0]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", required=True, help="folder with the child run outputs")
    ap.add_argument("--kinds", required=True, help="kind=level pairs, e.g. A/gaps=1,A/balance_beams=1,C/box=5")
    ap.add_argument("--mesh-dir", required=True)
    ap.add_argument("--boundary", type=int, required=True, help="boundary number b (iteration / 250)")
    ap.add_argument("--out", required=True, help="eval/scores/m<iter> folder: writes mapgain_outcomes.json and ladder_outcomes_list.json")
    ap.add_argument("--earlier", default=None, help="an earlier ladder_outcomes_list.json to extend (default: the nearest earlier boundary's file next to --out)")
    ap.add_argument("--interval", type=int, default=250, help="iterations per boundary (to find the earlier boundary folders)")
    a = ap.parse_args(argv)
    kinds = {}
    for item in a.kinds.split(","):
        k, lv = item.split("=")
        kinds[k] = int(lv)
    verdicts = {}
    for kind, level in kinds.items():
        fam, name = kind.split("/")
        tag = f"{fam}_{name}_L{level}"
        thr = None
        cells = {}
        for sp in SPEEDS:
            probe = sorted(glob.glob(str(Path(a.root) / f"{tag}_v{sp}_s42_main" / "env_arrays_eval_gt_*.npz")))
            if probe and name != "box":
                z = np.load(probe[0])
                thr = first_gap_end(a.mesh_dir, fam, name, int(z["terrain_col"][0]), int(z["terrain_level"][0])) + 0.3
            cells[sp] = read_cell(a.root, tag, sp, threshold=thr)
        v = judge_kind(cells)
        v["level"] = level
        v["crossed_definition"] = "alive_end" if name == "box" else f"farthest x >= first gap end + 0.3 m ({thr})"
        verdicts[kind] = v
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "mapgain_outcomes.json").write_text(json.dumps(verdicts, indent=1, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    base = json.loads(Path(a.earlier).read_text(encoding="utf-8")) if a.earlier else find_earlier(out, a.boundary, a.interval)
    write_evidence(out / "ladder_outcomes_list.json", a.boundary, verdicts, base)
    for k, v in verdicts.items():
        print(f"{k} L{v['level']}: {v['verdict']} (raise cap: {v['raise_cap']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
