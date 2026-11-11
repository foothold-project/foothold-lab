"""Recount a named-kind forward and four-flag pair from pinned Kit traces."""
from __future__ import annotations

from pathlib import Path

from foothold_s2.eval.ex42_kind_flag_cells import read_kind_flag_cell
from foothold_s2.eval.ex42_task_evidence import read_evidence
from foothold_s2.eval.ex42_task_suite import validate_request
from foothold_s2.eval.ex42_mesh_eval import preflight
from foothold_s2.ex42_e2_judge import MODES, score_mode


def read_stage_kind_bundle(folder: Path, *, stage_id: str, family: str, kind: str,
                           level: int, plan: dict, plan_sha256: str, mesh: dict,
                           checkpoint_sha256: str, seed: int) -> dict:
    """A mode can pass only when its forward and flag raw traces both recount."""
    folder = Path(folder)
    request_path = folder / "forward" / "request.json"
    request = validate_request(request_path)
    expected = {"stage_id": stage_id, "family": family, "kind": kind, "level": level,
                "plan_sha256": plan_sha256, "checkpoint_sha256": checkpoint_sha256,
                "seed": seed, "group": "kind", "envs": 64}
    if any(request.get(key) != value for key, value in expected.items()):
        raise ValueError("EX-42 stage kind request identity differs")
    source = preflight(request["source_mesh"])
    if source["mesh_sha256"] != mesh["mesh_sha256"]:
        raise ValueError("EX-42 stage kind source mesh differs")
    forward = read_evidence(folder / "forward" / "result", request_path=request_path)
    flags = read_kind_flag_cell(folder / "flag_four", plan=plan,
                                plan_sha256=plan_sha256, mesh=mesh,
                                checkpoint_sha256=checkpoint_sha256, seed=seed,
                                family=family, kind=kind, level=level)
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
        output[mode] = scored
    return output
