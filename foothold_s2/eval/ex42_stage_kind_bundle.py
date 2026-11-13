"""Recount a named-kind forward and four-flag pair from pinned Kit traces."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from foothold_s2.eval.ex42_kind_flag_cells import read_kind_flag_cell
from foothold_s2.eval.ex42_task_evidence import read_evidence
from foothold_s2.eval.ex42_task_suite import validate_request
from foothold_s2.eval.ex42_mesh_eval import preflight
from foothold_s2.eval.ex42_flag_cells import MODES, read_evidence as read_global_flags

# Where the four-flag half of an E3 cell comes from (lead 2026-11-12 02:18). The pinned E3 mesh has no per-kind flag targets on
# the continuous A columns, so those kinds use the stage's global flag_cells/flag_four evidence; every other opened kind uses
# its own kind flag_four child. The mesh is not regenerated and its SHA does not move.
GLOBAL_FLAGS = "global_flag_cells"
KIND_FLAGS = "kind_flag_four"


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def e3_target_inventory(plan: dict, opened_kinds: dict[str, int]) -> dict:
    """CG E3 explicit target kinds, and L0/L5/current-cap cells of kinds actually open."""
    spec = plan["evaluation"]["e3_kind_exit"]
    e0 = next(row for row in plan["stages"] if row["id"] == "E0")
    continuous = e0["terrain"]["kind_task"]["continuous"]
    targets = {(spec["continuous_family"], kind): spec["continuous_min_level"]
               for kind in continuous}
    targets.update({("A", kind): spec["start_min_level"] for kind in spec["start_kinds"]})
    targets.update({(family, kind): spec["easy_min_level"]
                    for family, kinds in spec["easy_kinds"].items() for kind in kinds})
    if (len(continuous) != 7 or
            spec["start_kinds"] != ["stepping_stones_low", "stepping_stones_high",
                                    "balance_beams", "stepping_beams", "gaps"] or
            spec["easy_kinds"] != {"B": ["stair_up", "stair_down", "rough", "boxes"],
                                   "C": ["pyramid_stairs", "inverted_pyramid_stairs",
                                         "discrete_grid", "flat"]} or
            len(targets) != len(continuous) + len(spec["start_kinds"]) +
            sum(len(kinds) for kinds in spec["easy_kinds"].values()) or
            spec["representative_levels"] != [0, 5, "current_cap"] or
            spec["judge_modes"] != ["eval_gt", "eval_pred"] or
            spec["record_modes"] != ["probe_prop_only"]):
        raise ValueError("EX-42 E3 named-kind target list or representative levels differ")
    missing = []
    for (family, kind), cap in sorted(targets.items()):
        actual = opened_kinds.get(f"{family}/{kind}")
        if type(actual) is not int or actual < cap:
            missing.append({"family": family, "kind": kind, "required_level": cap,
                            "opened_level": actual})
    cells = []
    for name, cap in sorted(opened_kinds.items()):
        if type(cap) is not int or cap < 0 or "/" not in name:
            raise ValueError("EX-42 E3 opened kind identity invalid")
        family, kind = name.split("/", 1)
        if (family, kind) not in targets:
            raise ValueError("EX-42 E3 opened kind outside approved target set")
        source = GLOBAL_FLAGS if family == spec["continuous_family"] and kind in continuous else KIND_FLAGS
        for level in sorted({0, cap} | ({5} if cap >= 5 else set())):
            cells.append({"family": family, "kind": kind, "level": level, "flag_source": source})
    return {"targets": [{"family": family, "kind": kind, "level": cap}
                         for (family, kind), cap in sorted(targets.items())],
            "missing_targets": missing, "opened_cells": cells}


def read_global_flag_rows(folder: Path | None, *, plan: dict, plan_sha256: str,
                          checkpoint_sha256: str, seed: int) -> dict:
    """The stage's global four-flag cell as one row per map mode, recounted from its pinned traces."""
    if folder is None or not (Path(folder) / "flag_cells.json").is_file():
        raise ValueError("EX-42 E3 global flag_four receipt absent")
    folder = Path(folder)
    judged = read_global_flags(folder, plan=plan, plan_sha256=plan_sha256,
                               checkpoint_sha256=checkpoint_sha256, seed=seed, count="flag_four")
    if not {f"flag_four_{mode}" for mode in MODES if mode != "probe_prop_only"} <= set(judged):
        raise ValueError("EX-42 E3 global flag judge rows absent")
    rows = {}
    for mode in MODES:
        case = f"flag_four_{mode}"
        if case in judged:
            row = dict(judged[case])
        else:        # the reader recounts and SHA-checks the record-only trace too, but hands back judge rows only
            raw_path = folder / f"{case}.json"
            raw = json.loads(raw_path.read_text(encoding="utf-8-sig"))
            row = {key: raw[key] for key in ("case_id", "envs", "valid_count", "success_count", "survival_count")}
            row.update(raw_file=str(raw_path), raw_sha256=_sha(raw_path))
        row["source"] = GLOBAL_FLAGS
        rows[mode] = row
    return rows


def read_e3_window(folder: Path, *, inventory: dict, plan: dict, plan_sha256: str,
                   mesh: dict, checkpoint_sha256: str, seed: int,
                   global_flag_dir: Path | None = None, stage_id: str = "E3") -> dict:
    """Recount every opened representative cell; a missing child never becomes a pass."""
    folder = Path(folder)
    if global_flag_dir is None:
        global_flag_dir = folder.parent / "flag_cells" / "flag_four"
    expected = {f"{cell['family']}/{cell['kind']}/L{cell['level']}": cell
                for cell in inventory["opened_cells"]}
    if not expected or not folder.is_dir():
        raise ValueError("EX-42 E3 named-kind raw window absent")
    families = ("A", "B", "C", *sorted({cell["family"] for cell in expected.values()} - {"A", "B", "C"}))
    observed = {f"{family}/{kind}/L{level}" for family in families
                for kind_dir in (folder / family).glob("*") if kind_dir.is_dir()
                for kind in (kind_dir.name,) for level_dir in kind_dir.glob("L*")
                if level_dir.is_dir() for level in (level_dir.name[1:],)}
    if observed != set(expected):
        raise ValueError("EX-42 E3 named-kind raw cell coverage differs")
    return {key: read_stage_kind_bundle(folder / cell["family"] / cell["kind"] / f"L{cell['level']}",
                                        stage_id=stage_id, family=cell["family"], kind=cell["kind"],
                                        level=cell["level"], plan=plan, plan_sha256=plan_sha256,
                                        mesh=mesh, checkpoint_sha256=checkpoint_sha256, seed=seed,
                                        flag_source=cell.get("flag_source", KIND_FLAGS),
                                        global_flag_dir=global_flag_dir)
            for key, cell in expected.items()}


def read_stage_kind_bundle(folder: Path, *, stage_id: str, family: str, kind: str,
                           level: int, plan: dict, plan_sha256: str, mesh: dict,
                           checkpoint_sha256: str, seed: int, flag_source: str = KIND_FLAGS,
                           global_flag_dir: Path | None = None) -> dict:
    """A mode can pass only when its forward and flag raw traces both recount."""
    from foothold_s2.ex42_e2_judge import score_mode
    folder = Path(folder)
    request_path = folder / "forward" / "request.json"
    request = validate_request(request_path)
    match = re.fullmatch(r"model_(\d+)\.pt", Path(request["checkpoint"]).name)
    if match is None:
        raise ValueError("EX-42 E3 named-kind checkpoint name invalid")
    iteration = int(match.group(1))
    expected = {"stage_id": stage_id, "family": family, "kind": kind, "level": level,
                "plan_sha256": plan_sha256, "checkpoint_sha256": checkpoint_sha256,
                "seed": seed, "group": "kind", "envs": 64,
                "window_index": max(1, iteration // plan["evaluation"]["interval_updates"])}
    if any(request.get(key) != value for key, value in expected.items()):
        raise ValueError("EX-42 stage kind request identity differs")
    source = preflight(request["source_mesh"])
    if source["mesh_sha256"] != mesh["mesh_sha256"]:
        raise ValueError("EX-42 stage kind source mesh differs")
    forward = read_evidence(folder / "forward" / "result", request_path=request_path)
    if flag_source == GLOBAL_FLAGS:
        if (folder / "flag_four").exists():          # two flag sources for one cell: refuse instead of choosing
            raise ValueError("EX-42 continuous kind cell has a kind flag trace beside the global flag source")
        flags = read_global_flag_rows(global_flag_dir, plan=plan, plan_sha256=plan_sha256,
                                      checkpoint_sha256=checkpoint_sha256, seed=seed)
    elif flag_source == KIND_FLAGS:
        flags = read_kind_flag_cell(folder / "flag_four", plan=plan,
                                    plan_sha256=plan_sha256, mesh=mesh,
                                    checkpoint_sha256=checkpoint_sha256, seed=seed,
                                    family=family, kind=kind, level=level)
    else:
        raise ValueError("EX-42 stage kind flag source is not registered")
    cases = {mode: f"{family}_{kind}_forward_{mode}" for mode in MODES}
    if set(forward["rows"]) != set(cases.values()) or set(flags) != set(MODES):
        raise ValueError("EX-42 stage kind forward or flag case list differs")
    spec = plan["evaluation"]["e2_kind_cells"]
    promotion = plan["evaluation"]["promotion"]
    output = {}
    for mode, case in cases.items():
        row = forward["rows"][case]
        if row.get("map_mode") != mode:
            raise ValueError("EX-42 stage kind forward mode differs")
        scored = score_mode(row, flags[mode], valid_min_each=spec["valid_min_each"],
                            success_min=promotion["success_min"],
                            survival_min=promotion["survival_min"],
                            weak_fraction=spec["weak_subcell_warning_fraction_of_success_floor"])
        scored["role"] = "record_only" if mode == "probe_prop_only" else "judge"
        scored["flag_source"] = flag_source
        output[mode] = scored
    return output
