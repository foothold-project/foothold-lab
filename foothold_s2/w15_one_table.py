"""Build a descriptive W15 comparison directly from saved 64-env JSON receipts."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import median

from foothold_s2.eval.map_mode_cells import commands, SEQUENCES


FIELDS = ("model", "iteration", "mode", "command", "envs", "survived", "survival_fraction",
          "vx_error_mps", "vy_error_mps", "yaw_error_radps", "body_displacement_m",
          "repeat_survival_width", "repeat_vx_error_width_mps", "repeat_displacement_width_m", "source")
COMMANDS = (*commands("extended"), *SEQUENCES)


def _med(rows: list[dict], key: str):
    values = [float(r[key]) for r in rows if r.get(key) is not None]
    return median(values) if values else None


def _measure(summary: dict, command: str) -> dict:
    if command in SEQUENCES:
        summary = summary["phases"][-1]
    rows = summary.get("per_env")
    if rows is None:
        # Earlier parent receipts have aggregate metrics only. Do not invent
        # per-env tracking or displacement from a different definition.
        if summary.get("alive_envs_at_end") is None:
            raise ValueError("parent receipt lacks survival evidence")
        return {"envs": 64, "survived": int(summary["alive_envs_at_end"]),
                "survival_fraction": int(summary["alive_envs_at_end"]) / 64}
    if not isinstance(rows, list) or len(rows) != 64:
        raise ValueError("W15 measurement requires 64 per-env rows")
    return {"envs": 64, "survived": sum(r["alive_at_end"] for r in rows),
            "survival_fraction": sum(r["alive_at_end"] for r in rows) / 64,
            "vx_error_mps": _med(rows, "vx_abs_error_mean_alive_mps"),
            "vy_error_mps": _med(rows, "vy_abs_error_mean_alive_mps"),
            "yaw_error_radps": _med(rows, "wz_abs_error_mean_alive_radps"),
            "body_displacement_m": _med(rows, "world_xy_displacement_m")}


def read_receipt(model: str, iteration: int, path: Path, *, e1: bool = False) -> list[dict]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if data.get("command_suite") != "extended" and not (model == "parent" and data.get("command_suite") in (None, "core")):
        raise ValueError("unexpected command suite")
    if len(data.get("terrain_tiles") or []) != 64 and not (model == "parent" and data.get("envs") == 64):
        raise ValueError("W15 receipt terrain count differs from 64")
    if data.get("checkpoint_iter") not in (None, iteration):
        raise ValueError("W15 checkpoint iteration differs from requested row")
    out = []
    available = ("native_student",) if e1 else ("eval_gt", "eval_pred")
    for mode in available:
        by_command = (data.get("modes") or {}).get(mode) or {}
        by_sequence = (data.get("sequences") or {}).get(mode) or {}
        for command in COMMANDS:
            summary = by_sequence.get(command) if command in SEQUENCES else by_command.get(command)
            row = {"model": model, "iteration": iteration, "mode": mode, "command": command,
                   "source": str(path.resolve()),
                   "device": (data.get("run_identity") or {}).get("gpu_uuid")}
            if summary is not None:
                row.update(_measure(summary, command))
            out.append(row)
    return out


def _files(root: Path) -> list[tuple[int, Path]]:
    if not root.exists():
        return []
    result = []
    for unit in sorted(root.glob("m*")):
        if not unit.is_dir() or not unit.name[1:].isdigit():
            continue
        candidates = sorted(unit.glob("attempt_*/map64/map_modes.json"))
        if not candidates:
            candidates = sorted(unit.glob("map64/map_modes.json"))
        result.extend((int(unit.name[1:]), path) for path in candidates)
    return result


def build(parent: Path, a_root: Path, ex38_root: Path, e1: Path) -> list[dict]:
    rows = read_receipt("parent", 1500, parent)
    rows += read_receipt("E1", 20000, e1, e1=True)
    for model, root in (("EX-36A", a_root), ("EX-38", ex38_root)):
        for iteration, path in _files(root):
            if model == "EX-36A" and not 1750 <= iteration <= 3000:
                continue
            rows += read_receipt(model, iteration, path)
    # Retain requested missing cells explicitly. E1's native-student input is
    # reported separately; it is never mislabeled as eval_gt or eval_pred.
    for model, iterations in (("parent", (1500,)), ("EX-36A", range(1750, 3001, 250)),
                              ("EX-38", (*range(1750, 3001, 250), 3001)),
                              ("E1", (20000,))):
        for iteration in iterations:
            for mode in ("eval_gt", "eval_pred"):
                for command in COMMANDS:
                    if not any((r["model"], r["iteration"], r["mode"], r["command"]) ==
                               (model, iteration, mode, command) for r in rows):
                        rows.append({"model": model, "iteration": iteration,
                                     "mode": mode, "command": command})
    return collapse(rows)


def collapse(rows: list[dict]) -> list[dict]:
    grouped = {}
    for row in rows:
        grouped.setdefault((row["model"], row["iteration"], row["mode"], row["command"]), []).append(row)
    result = []
    for _, group in sorted(grouped.items()):
        row = dict(group[0])
        distinct_devices = {r.get("device") for r in group if r.get("device")}
        for key, target in (("survival_fraction", "repeat_survival_width"),
                            ("vx_error_mps", "repeat_vx_error_width_mps"),
                            ("body_displacement_m", "repeat_displacement_width_m")):
            values = [r[key] for r in group if r.get(key) is not None]
            row[target] = max(values) - min(values) if len(distinct_devices) >= 2 and len(values) >= 2 else None
        result.append(row)
    return result


def write(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows({key: (r.get(key) if r.get(key) is not None else "미측") for key in FIELDS} for r in rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("parent", "a-root", "ex38-root", "e1", "out"):
        parser.add_argument("--" + key, type=Path, required=True)
    a = parser.parse_args(argv)
    rows = build(a.parent, a.a_root, a.ex38_root, a.e1)
    write(rows, a.out)
    print(json.dumps({"rows": len(rows), "measured": sum("envs" in r for r in rows),
                      "out": str(a.out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
