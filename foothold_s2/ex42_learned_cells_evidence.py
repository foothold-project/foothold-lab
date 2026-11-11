"""Read boundary episode counts without promoting an unapproved cell definition."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml

FORMAT = "foothold-ex42-learned-cells/1"
BANDS = [[0, 2], [3, 5], [6, 9]]
GROUPS = ["forward", "reverse", "side_left", "side_right", "turn_left", "turn_right", "stand", "flag"]
MODES = ["map_on_adaptive", "map_off"]
def read_stage_exposure(checkpoint: Path, *, stage_id: str, plan: dict,
                        plan_sha256: str, column_table: list[dict]) -> dict | None:
    """Recompute each rank's live placement and the approved K ladder from its boundary receipt."""
    from foothold_s2.ex42_exposure_receipt import fold_ranks, opened_kinds, recompute_from_plan
    from types import SimpleNamespace
    from foothold_s2.terrains.ex42_exposure import column_shares, exposure_by_column, low_level_floor
    from foothold_s2.terrains.ex42_k_ladder import ladder_terrain

    checkpoint = Path(checkpoint)
    match = re.fullmatch(r"model_(\d+)\.pt", checkpoint.name)
    if match is None:
        raise ValueError("EX-42 stage exposure checkpoint name invalid")
    iteration = int(match.group(1))
    directory = checkpoint.parent
    ranked = sorted(directory.glob(f"exposure_receipt_{iteration}_rank*.json"))
    single = directory / f"exposure_receipt_{iteration}.json"
    if single.is_file() and ranked:
        raise ValueError("EX-42 stage exposure single and ranked receipts mixed")
    paths = ranked or ([single] if single.is_file() else [])
    if not paths:
        return None
    documents = [json.loads(path.read_text(encoding="utf-8-sig")) for path in paths]
    row = fold_ranks(documents)
    for doc in documents:
        recompute_from_plan(doc, SimpleNamespace(document=plan))
    if any(path.name != (f"exposure_receipt_{iteration}.json" if doc["world_size"] == 1 else
                         f"exposure_receipt_{iteration}_rank{doc['rank']}.json")
           for path, doc in zip(paths, documents)):
        raise ValueError("EX-42 stage exposure receipt name differs")
    stages = [stage for stage in plan.get("stages", []) if stage.get("id") == stage_id]
    e0 = [stage for stage in plan.get("stages", []) if stage.get("id") == "E0"]
    if (row.get("stage_id") != stage_id or row.get("plan_sha256") != plan_sha256 or
            row.get("iteration") != iteration or row.get("kind") != "boundary" or
            any(doc.get("ladder_outcomes") != row.get("ladder_outcomes") for doc in documents) or
            [(r.get("family"), r.get("kind")) for r in row["column_rows"]] !=
            [(r.get("family"), r.get("kind")) for r in column_table] or
            not isinstance(row.get("mesh_sha256"), str) or
            not re.fullmatch(r"[0-9a-f]{64}", row["mesh_sha256"]) or
            type(row.get("boundary_index")) is not int or row["boundary_index"] < 0 or
            not isinstance(row.get("ladder_outcomes"), list) or
            len(row["ladder_outcomes"]) != row["boundary_index"] or
            len(stages) != 1 or len(e0) != 1):
        raise ValueError("EX-42 stage exposure identity or SHA differs")
    profile_name = stages[0].get("training_mesh_profile")
    if profile_name is not None:
        profile = (plan.get("training_mesh_profiles") or {}).get(profile_name) or {}
        if row["mesh_sha256"] != profile.get("geometry_sha256"):
            raise ValueError("EX-42 stage exposure mesh SHA differs from plan")
    terrain = {**stages[0]["terrain"], "kind_task": e0[0]["terrain"]["kind_task"]}
    terrain, moves = ladder_terrain(terrain, stage_id, row["boundary_index"], row["ladder_outcomes"])
    exposure, caps = exposure_by_column(terrain, column_table, stage_id)
    shares = column_shares(terrain, column_table, stage_id)
    expected_rows = [{"column": i, "family": item["family"], "kind": item["kind"],
                      "exposure": exposure[i], "level_cap": caps[i], "share": shares[i],
                      "open": bool(exposure[i] > 0)} for i, item in enumerate(column_table)]
    if (row["column_rows"] != expected_rows or row["opened_kinds"] != opened_kinds(expected_rows) or
            row.get("k_ladder_moves") != moves or
            row.get("low_floor") != low_level_floor(terrain, column_table, stage_id)):
        raise ValueError("EX-42 stage exposure differs from recomputed exposure")
    for doc in documents:
        live = doc.get("live")
        if not isinstance(live, dict) or type(live.get("envs")) is not int or live["envs"] < 1:
            raise ValueError("EX-42 stage exposure live placement absent")
        cells = live.get("per_column_level")
        if not isinstance(cells, dict) or not cells:
            raise ValueError("EX-42 stage exposure live cells absent")
        counted_levels = {}
        counted_columns = set()
        total = 0
        for key, count in cells.items():
            parts = re.fullmatch(r"(0|[1-9]\d*):(0|[1-9]\d*)", key)
            if parts is None or type(count) is not int or count < 1:
                raise ValueError("EX-42 stage exposure live cell invalid")
            col, level = (int(part) for part in parts.groups())
            if col >= len(exposure) or exposure[col] <= 0 or level > caps[col]:
                raise ValueError("EX-42 stage exposure live cell outside approved exposure")
            total += count
            counted_columns.add(col)
            counted_levels[level] = counted_levels.get(level, 0) + count
        per_level = live.get("per_level")
        if (total != live["envs"] or live.get("columns_used") != sorted(counted_columns) or
                not isinstance(per_level, list) or
                any(type(value) is not int or value < 0 for value in per_level) or
                any(counted_levels.get(level, 0) != value for level, value in enumerate(per_level)) or
                max(counted_levels) >= len(per_level) or live.get("levels_max") != max(counted_levels)):
            raise ValueError("EX-42 stage exposure live totals differ")
    return {**row, "exposure": exposure, "level_caps": caps,
            "receipts": [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                         for path in paths]}


def read_boundary(checkpoint: Path, *, stage_id: str, plan_sha256: str, interval: int) -> dict:
    """SHA-check both ranks and expose counts; absent registration stays HOLD."""
    checkpoint = Path(checkpoint)
    match = re.fullmatch(r"model_(\d+)\.pt", checkpoint.name)
    if match is None or type(interval) is not int or interval < 1:
        raise ValueError("EX-42 learned_cells boundary identity invalid")
    iteration = int(match.group(1))
    directory = checkpoint.parent
    ranked = sorted(directory.glob(f"learned_cells_{iteration}_rank*.json"))
    single = directory / f"learned_cells_{iteration}.json"
    if single.is_file() and ranked:
        raise ValueError("EX-42 learned_cells single and ranked receipts mixed")
    paths = ranked or ([single] if single.is_file() else [])
    if not paths:
        return {"role": "judge", "judgement": "HOLD", "reason": "학습 종료 에피소드 원자료 없음",
                "source": "assigned_mode_cumulative", "receipts": []}
    seen = set()
    counts = {}
    receipts = []
    world_size = None
    window = None
    columns = None
    column_table = None
    for path in paths:
        raw = path.read_bytes()
        row = json.loads(raw.decode("utf-8-sig"))
        checksum = row.pop("sha256", None)
        body_sha = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        expected_name = (f"learned_cells_{iteration}.json" if row.get("world_size") == 1 else
                         f"learned_cells_{iteration}_rank{row.get('rank')}.json")
        if (checksum != body_sha or row.get("format") != FORMAT or path.name != expected_name or
                row.get("stage_id") != stage_id or row.get("plan_sha256") != plan_sha256 or
                row.get("episodes_counted_once") is not True or
                row.get("axes") != {"level_bands": BANDS, "groups": GROUPS,
                                    "modes": MODES, "columns": row.get("axes", {}).get("columns")}):
            raise ValueError(f"EX-42 learned_cells identity or SHA differs: {path}")
        size, rank = row.get("world_size"), row.get("rank")
        if (type(size) is not int or size < 1 or type(rank) is not int or not 0 <= rank < size or
                rank in seen or (world_size is not None and world_size != size)):
            raise ValueError("EX-42 learned_cells rank coverage differs")
        seen.add(rank)
        world_size = size
        span = row.get("window")
        if (not isinstance(span, dict) or type(span.get("from_it")) is not int or
                span.get("to_it") != iteration or not 0 <= span["from_it"] < iteration or
                iteration - span["from_it"] > interval or (window is not None and window != span)):
            raise ValueError("EX-42 learned_cells boundary window differs")
        window = span
        axes = row["axes"]
        ncols = axes["columns"]
        if type(ncols) is not int or ncols < 1 or (columns is not None and columns != ncols):
            raise ValueError("EX-42 learned_cells column count differs")
        columns = ncols
        table = row.get("columns")
        if (not isinstance(table, list) or len(table) != ncols or
                any(not isinstance(item, dict) or not isinstance(item.get("family"), str) or
                    not isinstance(item.get("kind"), str) for item in table) or
                (column_table is not None and column_table != table)):
            raise ValueError("EX-42 learned_cells column table differs")
        column_table = table
        cells = row.get("cells")
        if not isinstance(cells, list) or type(row.get("total")) is not int or row["total"] < 0:
            raise ValueError("EX-42 learned_cells counts missing")
        local = set()
        subtotal = 0
        for cell in cells:
            if (not isinstance(cell, list) or len(cell) != 5 or type(cell[0]) is not int or
                    not 0 <= cell[0] < ncols or cell[1] not in (0, 3, 6) or
                    cell[2] not in GROUPS or cell[3] not in MODES or
                    type(cell[4]) is not int or cell[4] < 1):
                raise ValueError("EX-42 learned_cells cell invalid")
            key = tuple(cell[:4])
            if key in local:
                raise ValueError("EX-42 learned_cells duplicate cell")
            local.add(key)
            subtotal += cell[4]
            counts[key] = counts.get(key, 0) + cell[4]
        if subtotal != row["total"]:
            raise ValueError("EX-42 learned_cells total differs")
        receipts.append({"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
                         "rank": rank, "total": subtotal})
    if seen != set(range(world_size)):
        return {"role": "judge", "judgement": "HOLD", "reason": "학습 종료 에피소드 rank 결측",
                "source": "assigned_mode_cumulative", "receipts": receipts,
                "ranks_present": sorted(seen), "world_size": world_size}
    return {"role": "judge", "judgement": "HOLD", "reason": "원자료 집계 (판정 전)",
            "source": "assigned_mode_cumulative", "receipts": receipts,
            "window": window, "world_size": world_size, "total": sum(counts.values()),
            "column_table": column_table,
            "cells": [[*key, value] for key, value in sorted(counts.items())]}


def judge_two_boundaries(checkpoint: Path, *, stage_id: str, plan: dict,
                         plan_sha256: str, interval: int, min_episodes: int,
                         previous_kind_pass: bool = False,
                         registered_kind_passes: dict[tuple[str, str], bool] | None = None) -> dict:
    """CG:381 registration, two adjacent save windows, no proxy counts."""
    if (not isinstance(stage_id, str) or not stage_id or
            type(min_episodes) is not int or min_episodes < 1):
        raise ValueError("EX-42 learned_cells stage threshold invalid")
    if stage_id != "E2" and (not isinstance(registered_kind_passes, dict) or
            any(not isinstance(key, tuple) or len(key) != 2 or
                any(not isinstance(part, str) or not part for part in key) or
                type(value) is not bool for key, value in registered_kind_passes.items())):
        raise ValueError("EX-42 learned_cells prior kind pass registry invalid")
    checkpoint = Path(checkpoint)
    iteration = int(re.fullmatch(r"model_(\d+)\.pt", checkpoint.name).group(1))
    current = read_boundary(checkpoint, stage_id=stage_id,
                            plan_sha256=plan_sha256, interval=interval)
    previous = read_boundary(checkpoint.with_name(f"model_{iteration - interval}.pt"),
                             stage_id=stage_id, plan_sha256=plan_sha256, interval=interval) if iteration > interval else None
    receipts = [*(previous or {}).get("receipts", []), *current.get("receipts", [])]
    if (previous is None or "cells" not in current or "cells" not in previous or
            previous["window"]["to_it"] != current["window"]["from_it"] or
            current["window"]["to_it"] - previous["window"]["from_it"] != 2 * interval or
            previous["column_table"] != current["column_table"]):
        return {"role": "judge", "judgement": "HOLD", "source": "assigned_mode_cumulative",
                "reason": "연속 두 경계 학습 종료 원자료 결측 또는 창 불일치", "receipts": receipts}
    agent_path = checkpoint.parent / "params" / "agent.yaml"
    if not agent_path.is_file():
        return {"role": "judge", "judgement": "HOLD", "source": "assigned_mode_cumulative",
                "reason": "배정 지도 끔 확률 원자료 없음", "receipts": receipts}
    agent = yaml.safe_load(agent_path.read_text(encoding="utf-8-sig"))
    p_off = (agent.get("perception") or {}).get("p_map_off") if isinstance(agent, dict) else None
    if type(p_off) not in (int, float) or not 0 <= p_off <= 1:
        raise ValueError("EX-42 learned_cells assigned map-off probability invalid")
    from foothold_s2.terrains.ex42_exposure import exposure_by_column
    from foothold_s2.runners.map_switch import ELIGIBLE_NAMES

    stage = next(row for row in plan["stages"] if row["id"] == stage_id)
    e0 = next(row for row in plan["stages"] if row["id"] == "E0")
    terrain = {**stage["terrain"], "kind_task": e0["terrain"]["kind_task"]}
    table = current["column_table"]
    if stage_id == "E2":
        exposure, caps = exposure_by_column(terrain, table, stage_id)
    else:
        actual = read_stage_exposure(checkpoint, stage_id=stage_id, plan=plan,
                                     plan_sha256=plan_sha256, column_table=table)
        if actual is None:
            return {"role": "judge", "judgement": "HOLD", "source": "assigned_mode_cumulative",
                    "reason": "학습 단계 노출 영수증 없음", "receipts": receipts}
        exposure, caps = actual["exposure"], actual["level_caps"]
    continuous = set(e0["terrain"]["kind_task"]["continuous"])
    registered = set()
    for column, row in enumerate(table):
        family, kind = row["family"], row["kind"]
        if exposure[column] <= 0 or (stage_id == "E2" and family != "A"):
            continue
        if family == "A" and kind in continuous:
            groups = GROUPS  # the flag group opened at E1F, before E2
            modes = MODES if p_off > 0 and kind in ELIGIBLE_NAMES else MODES[:1]
        elif stage_id == "E2" and kind == "stepping_stones_low" and previous_kind_pass:
            groups, modes = ("forward", "flag"), MODES[:1]
        elif stage_id != "E2" and registered_kind_passes.get((family, kind)) is True:
            groups, modes = ("forward", "flag"), MODES[:1]
        else:
            continue  # new kind registers only after its first passing window
        for band in (0, 3, 6):
            if band > caps[column]:
                continue
            for group in groups:
                for mode in modes:
                    registered.add((family, kind, band, group, mode))
    if not registered:
        raise ValueError(f"EX-42 learned_cells has no registered {stage_id} cells")
    counted = {}
    for window in (previous, current):
        for column, band, group, mode, n in window["cells"]:
            row = table[column]
            key = (row["family"], row["kind"], band, group, mode)
            counted[key] = counted.get(key, 0) + n
    pending = [[*key, counted.get(key, 0)] for key in sorted(registered)
               if counted.get(key, 0) < min_episodes]
    return {"role": "judge", "judgement": "HOLD" if pending else "PASS",
            "source": "assigned_mode_cumulative", "threshold": min_episodes,
            "window_boundaries": 2, "window": {"from_it": previous["window"]["from_it"],
                                                "to_it": current["window"]["to_it"]},
            "p_map_off": p_off, "agent_config": {"path": str(agent_path),
                                                 "sha256": hashlib.sha256(agent_path.read_bytes()).hexdigest()},
            "registered_count": len(registered), "pending": pending,
            **({"stage_exposure": actual["receipts"]}
               if stage_id != "E2" else {}),
            "receipts": receipts, "total": previous["total"] + current["total"]}
