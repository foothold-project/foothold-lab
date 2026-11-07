"""CPU contract for EX-42 N21 record-only DR evaluation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml


N21_COMMANDS = {
    "fwd0.5": (0.5, 0.0, 0.0),
    "fwd1.0": (1.0, 0.0, 0.0),
    "spin+1.2": (0.0, 0.0, 1.2),
    "spin-1.2": (0.0, 0.0, -1.2),
    "back0.5": (-0.5, 0.0, 0.0),
    "side+0.5": (0.0, 0.5, 0.0),
    "side-0.5": (0.0, -0.5, 0.0),
    "stop": (0.0, 0.0, 0.0),
}
CONTINUOUS_KINDS = (
    "pyramid_stairs", "pyramid_stairs_inv", "boxes", "random_rough",
    "hf_pyramid_slope", "hf_pyramid_slope_inv", "stage_stairs",
)
MAP_MODES = ("eval_gt", "eval_pred", "probe_prop_only")
N21_SCHEMA = "foothold-ex42-n21-dr-record-only/1"
DEFAULT_APPROVAL = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-approvals.yaml"


def validate_request(args) -> None:
    """Fail closed before Kit unless this is the agreed N21 measurement cell."""
    if args.dr_mode != "on":
        raise ValueError("N21 record-only requires --dr-mode on")
    if args.dr_scale != 1.0:
        raise ValueError("N21 requires approved DR scale 1.0")
    if args.command_suite != "n21" or args.commands != "all":
        raise ValueError("N21 requires the exact eight-command suite")
    if tuple(args.modes.split(",")) != MAP_MODES:
        raise ValueError("N21 requires eval_gt,eval_pred,probe_prop_only in canonical order")
    if args.terrain_set not in ("n21-continuous", "n21-flat"):
        raise ValueError("N21 requires the continuous-seven or flat selector")
    if not args.fixed_terrain or args.fixed_level != 2:
        raise ValueError("N21 requires fixed terrain at level 2")
    if args.envs != 64:
        raise ValueError("N21 requires 64 total envs; this is not 64 envs per terrain kind")
    if args.n21_point not in ("parent_e0", "stage_end"):
        raise ValueError("N21 point must be parent_e0 or stage_end")
    if not args.n21_stage:
        raise ValueError("N21 requires an explicit approved stage id")
    if args.n21_point == "parent_e0" and args.n21_stage != "EX42_0_T0_prime":
        raise ValueError("N21 parent_e0 must use the approved EX42_0_T0_prime baseline id")
    if args.n21_point == "stage_end" and args.n21_stage == "EX42_0_T0_prime":
        raise ValueError("N21 stage_end requires a completed EX-42 stage, not the parent baseline")


def validate_entrypoint(args) -> None:
    """Keep every DR-on map evaluation in the isolated N21 record-only lane."""
    if getattr(args, "n21_record_only", False):
        validate_request(args)
        return
    if getattr(args, "dr_mode", "off") == "on":
        raise ValueError("DR-on map evaluation requires --n21-record-only")
    if (getattr(args, "terrain_set", "default") in ("n21-continuous", "n21-flat")
            or getattr(args, "command_suite", "core") == "n21"):
        raise ValueError("N21 selectors require --n21-record-only")


def approval_record(path: str | Path, stage: str, scale: float,
                    dr_table_path: str | Path = DEFAULT_APPROVAL.parent / "ex41-fixed5000.yaml") -> dict[str, Any]:
    """Read, validate and fingerprint the DR approval without inventing ranges."""
    approval_path = Path(path)
    raw = approval_path.read_bytes()
    doc = yaml.safe_load(raw.decode("utf-8")) or {}
    dr = doc.get("domain_randomization")
    if not isinstance(dr, dict) or dr.get("approved") is not True:
        raise ValueError("N21 DR approval is missing or not approved")
    scales = dr.get("stage_scales")
    if not isinstance(scales, dict) or stage not in scales:
        raise ValueError("N21 stage has no approved DR scale: %s" % stage)
    approved_scale = scales[stage]
    if isinstance(approved_scale, bool) or not isinstance(approved_scale, (int, float)) or float(approved_scale) != float(scale):
        raise ValueError("N21 requested scale differs from approved stage scale")
    decision_id = dr.get("decision_id")
    rationale = dr.get("rationale")
    if not isinstance(decision_id, str) or not decision_id.strip() or not isinstance(rationale, str) or not rationale.strip():
        raise ValueError("N21 DR approval decision id/rationale is missing")

    curriculum_dir = DEFAULT_APPROVAL.parent
    prep_path = curriculum_dir / "ex42-prep.yaml"
    prep_raw = prep_path.read_bytes()
    prep_doc = yaml.safe_load(prep_raw.decode("utf-8-sig")) or {}
    source = ((prep_doc.get("stage_zero") or {}).get("source") or {})
    source_name = source.get("path")
    expected_normalized_sha = source.get("normalized_sha256")
    if (not isinstance(source_name, str) or Path(source_name).name != source_name
            or not isinstance(expected_normalized_sha, str) or len(expected_normalized_sha) != 64):
        raise ValueError("N21 EX-42 range source pin is missing or malformed")
    source_path = (curriculum_dir / source_name).resolve(strict=True)
    requested_table = Path(dr_table_path).resolve(strict=True)
    if requested_table != source_path:
        raise ValueError("N21 DR table must be the EX-42 approved parent range source: %s" % source_path)
    source_raw = source_path.read_bytes()
    normalized_sha = hashlib.sha256(source_raw.replace(b"\r\n", b"\n")).hexdigest()
    if normalized_sha != expected_normalized_sha:
        raise ValueError("N21 EX-42 parent range source SHA differs from the pinned plan")

    return {
        "path": str(approval_path.resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "decision_id": decision_id,
        "stage": stage,
        "scale": float(approved_scale),
        "rationale": rationale,
        "range_source": {
            "path": str(source_path),
            "sha256": hashlib.sha256(source_raw).hexdigest(),
            "normalized_sha256": normalized_sha,
            "pinned_by_ex42_prep": str(prep_path.resolve()),
            "prep_sha256": hashlib.sha256(prep_raw).hexdigest(),
        },
    }


def terrain_spec(terrain_set: str) -> dict[str, Any]:
    if terrain_set == "n21-continuous":
        return {"selector": terrain_set, "kinds": list(CONTINUOUS_KINDS), "fixed_level": 2,
                "env_count": 64, "assignment": "fixed_terrain env-index mapping across seven continuous kinds"}
    if terrain_set == "n21-flat":
        return {"selector": terrain_set, "kinds": ["flat"], "fixed_level": 2,
                "env_count": 64, "assignment": "all 64 envs assigned to flat at fixed level 2"}
    raise ValueError("unknown N21 terrain selector: %s" % terrain_set)


def configure_terrain(env_cfg, terrain_set: str, seed: int) -> None:
    """Install the explicitly selected, fixed L2 terrain family before gym.make."""
    from foothold_s2.terrains import columns
    from foothold_s2.terrains.rough_go2_cfg import build_generator, continuous_subterrains

    if terrain_set == "n21-continuous":
        sub_terrains, count = continuous_subterrains(), columns.CONTINUOUS_COLS
    elif terrain_set == "n21-flat":
        from foothold_s2.terrains.sparse_terrains import sparse_subterrains

        sub_terrains, count = sparse_subterrains({"flat": 1.0}), columns.FULL_COLS
    else:
        raise ValueError("unknown N21 terrain selector: %s" % terrain_set)
    env_cfg.scene.terrain.terrain_generator = build_generator(sub_terrains, count, seed=int(seed))


def receipt(document: dict[str, Any], *, approval: dict[str, Any], terrain_set: str) -> dict[str, Any]:
    """Wrap a DR-on evaluation document in an unmistakable record-only contract."""
    if not isinstance(document, dict) or "dr" not in document or document["dr"].get("mode") != "on":
        raise ValueError("N21 receipt requires a completed DR-on result")
    modes = document.get("modes")
    if not isinstance(modes, dict) or set(modes) != set(MAP_MODES):
        raise ValueError("N21 receipt is missing one or more map modes")
    if any(not isinstance(modes[mode], dict) or set(modes[mode]) != set(N21_COMMANDS) for mode in MAP_MODES):
        raise ValueError("N21 receipt is missing one or more representative command cells")
    point, stage = document.get("n21_point"), document.get("n21_stage")
    if point not in ("parent_e0", "stage_end") or not isinstance(stage, str) or not stage:
        raise ValueError("N21 receipt point/stage identity is missing")
    if point == "parent_e0" and stage != "EX42_0_T0_prime":
        raise ValueError("N21 parent receipt must identify EX42_0_T0_prime")
    if point == "stage_end" and stage == "EX42_0_T0_prime":
        raise ValueError("N21 stage-end receipt cannot be the parent baseline")
    dr = document["dr"]
    if (not isinstance(approval, dict) or approval.get("stage") != stage
            or float(approval.get("scale", -1.0)) != float(dr.get("scale", -2.0))
            or not isinstance(approval.get("sha256"), str) or len(approval["sha256"]) != 64
            or not isinstance(approval.get("range_source"), dict)):
        raise ValueError("N21 receipt approval does not match its stage/scale or range source")
    fixed = document.get("fixed_terrain")
    if (not isinstance(fixed, dict) or fixed.get("fixed_level") != 2
            or fixed.get("num_envs") != 64):
        raise ValueError("N21 receipt fixed terrain/env assignment differs")
    result = dict(document)
    result.update({
        "schema": N21_SCHEMA,
        "record_only": True,
        "decision_use": "record_only; not eligible for EX-40/EX-41 maintenance or promotion",
        "n21": {
            "point": document.get("n21_point"),
            "stage": document.get("n21_stage"),
            "commands": list(N21_COMMANDS),
            "map_modes": list(MAP_MODES),
            "terrain": terrain_spec(terrain_set),
            "approval": approval,
        },
    })
    return result
