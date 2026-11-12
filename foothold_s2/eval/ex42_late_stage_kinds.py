"""E4 / E5 named-kind exit evidence: the E3 reader generalised to the late stages, no new physics.

The opened kinds come from the stage's own training exposure receipt (a template cap is not evidence). Every opened kind must
reach its registered level target, and each representative cell (L0, L5, current cap) is recounted from its forward and flag
NPZ through the common stage bundle reader. A missing receipt, child failure, cell or target is HOLD, never PASS.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from foothold_s2.eval.ex42_stage_kind_bundle import GLOBAL_FLAGS, KIND_FLAGS, read_e3_window
from foothold_s2.ex42_stage_judges import aggregate

STAGES = ("E4", "E5")


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def folder_name(stage_id: str) -> str:
    if stage_id not in STAGES:
        raise ValueError("EX-42 late kind stage must be E4 or E5")
    return f"kind_cells_{stage_id.lower()}"


def spec_for(plan: dict, stage_id: str) -> dict:
    spec = plan["evaluation"].get("late_kind_exit")
    if (not isinstance(spec, dict) or spec.get("judge_modes") != ["eval_gt", "eval_pred"] or
            spec.get("record_modes") != ["probe_prop_only"] or
            spec.get("representative_levels") != [0, 5, "current_cap"] or
            type(spec.get("learned_cells_min")) is not int or spec["learned_cells_min"] <= 0 or
            stage_id not in spec or type(spec[stage_id].get("min_level")) is not int):
        raise ValueError("EX-42 late kind exit spec absent or differs")
    return spec


def level_targets(plan: dict, stage_id: str) -> dict[tuple[str, str], int]:
    """Every kind the stage declares (positive rules and the K ladder) and the level it must reach before exit."""
    spec = spec_for(plan, stage_id)[stage_id]
    stage = next(row for row in plan["stages"] if row["id"] == stage_id)
    terrain = stage["terrain"]
    exposure = terrain[f"exposure_at_{stage_id}"]
    continuous = next(row for row in plan["stages"] if row["id"] == "E0")["terrain"]["kind_task"]["continuous"]
    targets: dict[tuple[str, str], int] = {}
    for rule in exposure["positive"]:
        kinds = list(continuous) if "kinds_of" in rule else [rule["kind"]]
        for kind in kinds:
            cap = rule.get("level_cap", 0)
            if type(cap) is not int or cap < 0:
                raise ValueError("EX-42 late kind rule level invalid")
            targets[(rule["family"], kind)] = max(spec["min_level"], cap) if stage_id == "E4" else cap
    for row in (terrain.get("k_ladder") or {}).get("order", []):
        targets.setdefault((row["family"], row["kind"]), spec["min_level"])
    for name, level in (spec.get("level_overrides") or {}).items():
        family, kind = name.split("/", 1)
        if (family, kind) in targets:
            targets[(family, kind)] = max(targets[(family, kind)], level)
    if not targets:
        raise ValueError("EX-42 late stage declares no kinds")
    return targets


def target_inventory(plan: dict, stage_id: str, opened_kinds: dict[str, int]) -> dict:
    targets = level_targets(plan, stage_id)
    continuous = set(next(row for row in plan["stages"] if row["id"] == "E0")["terrain"]["kind_task"]["continuous"])
    missing = []
    for (family, kind), need in sorted(targets.items()):
        actual = opened_kinds.get(f"{family}/{kind}")
        if type(actual) is not int or actual < need:
            missing.append({"family": family, "kind": kind, "required_level": need, "opened_level": actual})
    cells = []
    for name, cap in sorted(opened_kinds.items()):
        family, kind = name.split("/", 1)
        if type(cap) is not int or cap < 0 or (family, kind) not in targets:
            raise ValueError("EX-42 late opened kind outside the declared target set")
        source = GLOBAL_FLAGS if family == "A" and kind in continuous else KIND_FLAGS
        for level in sorted({0, cap} | ({5} if cap >= 5 else set())):
            cells.append({"family": family, "kind": kind, "level": level, "flag_source": source})
    return {"targets": [{"family": f, "kind": k, "level": v} for (f, k), v in sorted(targets.items())],
            "missing_targets": missing, "opened_cells": cells}


def recount(score: dict, *, plan: dict, evaluation: Path, mesh: dict, stage_id: str) -> dict:
    """HOLD for a marker, a missing receipt or a missing global flag file; otherwise every state comes from raw traces."""
    from foothold_s2.ex42_learned_cells_evidence import read_stage_exposure

    folder = Path(evaluation) / folder_name(stage_id)
    if score.get("stage_id") != stage_id or score.get("checkpoint_sha256") is None:
        raise ValueError(f"EX-42 {stage_id} late kind score identity differs")
    marker = folder / "child_failures.json"
    if marker.is_file():
        failure = json.loads(marker.read_text(encoding="utf-8-sig"))
        if (failure.get("format") != f"foothold-ex42-{stage_id.lower()}-child-failures/1" or
                failure.get("checkpoint_sha256") != score["checkpoint_sha256"] or not failure.get("reason")):
            raise ValueError(f"EX-42 {stage_id} child failure marker differs")
        return {"judgement": "HOLD", "reason": failure["reason"], "exposure_found": False,
                "child_failure": {"path": str(marker), "sha256": _sha(marker)},
                "mesh_sha256": mesh["mesh_sha256"], "evaluation": str(folder)}
    table = [{"family": f, "kind": k} for f, k in zip(mesh["column_family"], mesh["columns"])]
    exposure = read_stage_exposure(Path(score["checkpoint"]), stage_id=stage_id, plan=plan,
                                   plan_sha256=score["execution_plan_sha256"], column_table=table)
    if exposure is None:
        return {"judgement": "HOLD", "reason": f"{stage_id} 학습 노출 영수증 없음", "exposure_found": False,
                "mesh_sha256": mesh["mesh_sha256"], "evaluation": str(folder)}
    if exposure["mesh_sha256"] != mesh["mesh_sha256"]:
        raise ValueError(f"EX-42 {stage_id} training and evaluation mesh differ")
    inventory = target_inventory(plan, stage_id, exposure["opened_kinds"])
    global_flags = Path(evaluation) / "flag_cells" / "flag_four"
    sources = sorted({cell["flag_source"] for cell in inventory["opened_cells"]})
    base = {"inventory": inventory, "stage_exposure": exposure["receipts"], "exposure_found": True,
            "mesh_sha256": mesh["mesh_sha256"], "evaluation": str(folder)}
    if GLOBAL_FLAGS in sources and not (global_flags / "flag_cells.json").is_file():
        return {"judgement": "HOLD", "reason": f"{stage_id} 전역 깃발 flag_cells/flag_four 영수증 없음", **base}
    cells = (read_e3_window(folder, inventory=inventory, plan=plan, plan_sha256=score["maintenance_source_sha256"],
                            mesh=mesh, checkpoint_sha256=score["checkpoint_sha256"],
                            seed=score["conditions"]["eval_seed"], global_flag_dir=global_flags, stage_id=stage_id)
             if inventory["opened_cells"] else {})
    states = [row[mode]["judgement"] for row in cells.values() for mode in ("eval_gt", "eval_pred")]
    if inventory["missing_targets"] or not states:
        states.append("HOLD")
    return {"judgement": aggregate(states), "cells": cells, "flag_sources": sources, **base}


def passed_kinds(recounted: dict | None) -> dict[tuple[str, str], bool]:
    """(family, kind) -> some represented cell passed both judged modes (the E3 rule). Only raw recounted cells count."""
    out: dict[tuple[str, str], bool] = {}
    for key, bundle in ((recounted or {}).get("cells") or {}).items():
        family, kind = key.split("/", 2)[:2]
        out[(family, kind)] = out.get((family, kind), False) or all(
            bundle[mode]["judgement"] == "PASS" for mode in ("eval_gt", "eval_pred"))
    return out
