"""Recount a four-flag EX-42 named-kind cell from its pinned Kit artifacts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from foothold_s2.eval.ex42_flag_cells import MODES, contract, score_trace
from foothold_s2.eval.fixed_terrain import assignment_sha256, kind_assignment
from foothold_s2.terrains.ex42_flags import load_flag_table


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_kind_flag_cell(folder: Path, *, plan: dict, plan_sha256: str,
                        mesh: dict, checkpoint_sha256: str, seed: int,
                        family: str, kind: str, level: int) -> dict:
    """The training default is four flags; GT and pred judge, off records only."""
    cells = contract(plan)
    folder = Path(folder)
    receipt_path = folder / "flag_cells.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    expected_cases = {f"flag_four_{mode}" for mode in MODES}
    identity = {"family": family, "kind": kind, "level": level}
    if (receipt.get("format") != "foothold-ex42-flag-eval/1" or
            receipt.get("state") != "done" or receipt.get("count") != "flag_four" or
            receipt.get("kind_cell") != identity or receipt.get("envs") != 64 or
            receipt.get("plan_sha256") != plan_sha256 or
            receipt.get("checkpoint_sha256") != checkpoint_sha256 or
            receipt.get("mesh_sha256") != mesh["mesh_sha256"] or
            receipt.get("seed") != seed or set(receipt.get("cases", {})) != expected_cases):
        raise ValueError("EX-42 kind flag receipt identity or coverage differs")
    table = [{"family": f, "kind": k} for f, k in zip(mesh["column_family"], mesh["columns"])]
    levels, types = kind_assignment(64, 10, table, family, kind, level)
    flags = load_flag_table(mesh["mesh_npz"], 10, len(table))
    if flags is None or not np.isfinite(flags[levels, types, :4]).all():
        raise ValueError("EX-42 named-kind flag targets absent from pinned mesh")
    output = {}
    for mode in MODES:
        case_id = f"flag_four_{mode}"
        trace_path = folder / f"{case_id}.npz"
        raw_path = folder / f"{case_id}.json"
        indexed = receipt["cases"][case_id]
        if (indexed.get("trace_file") != str(trace_path) or
                indexed.get("raw_file") != str(raw_path) or
                indexed.get("trace_sha256") != _sha(trace_path) or
                indexed.get("raw_sha256") != _sha(raw_path)):
            raise ValueError("EX-42 kind flag source path or SHA differs")
        raw = json.loads(raw_path.read_text(encoding="utf-8-sig"))
        spec = cells["case_specs"][case_id]
        if (raw.get("case_id") != case_id or
                any(raw.get(key) != value for key, value in spec.items()) or
                raw.get("trace_sha256") != indexed["trace_sha256"] or
                raw.get("fixed_terrain", {}).get("assignment_sha256") != assignment_sha256(levels, types) or
                raw["fixed_terrain"].get("cols") != len(table) or
                raw["fixed_terrain"].get("family") != family or
                raw["fixed_terrain"].get("kind") != kind):
            raise ValueError("EX-42 kind flag case or assignment differs")
        with np.load(trace_path, allow_pickle=False) as archive:
            trace = {key: archive[key] for key in archive.files}
        if (not np.array_equal(trace["terrain_levels"], levels) or
                not np.array_equal(trace["terrain_types"], types) or
                not np.array_equal(trace["flags_w"], flags[levels, types, :4]) or
                not np.isfinite(trace["env_origins_w"]).all()):
            raise ValueError("EX-42 kind flag coordinates or terrain differ from pinned mesh")
        measured = score_trace(trace, spec, cells)
        if (any(raw.get(key) != measured[key] for key in measured) or
                any(indexed.get(key) != raw.get(key) for key in
                    ("envs", "valid_count", "success_count", "survival_count"))):
            raise ValueError("EX-42 kind flag score differs from raw trace")
        output[mode] = {"case_id": f"{family}/{kind}/L{level}/flag_four/{mode}",
                        "role": "record_only" if mode == "probe_prop_only" else "judge",
                        "completion": "flag_reach_0.3m", **{key: measured[key] for key in
                          ("envs", "valid_count", "success_count", "survival_count")},
                        "evidence": {"receipt": {"path": str(receipt_path), "sha256": _sha(receipt_path)},
                                     "raw": {"path": str(raw_path), "sha256": _sha(raw_path)},
                                     "trace": {"path": str(trace_path), "sha256": _sha(trace_path)}}}
    return output
