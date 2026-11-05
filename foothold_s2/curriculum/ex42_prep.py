"""EX-42 preparation contract. Importing this module never starts Isaac Sim."""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


STAGE_IDS = ("E0", "E1", "E1F", "E2", "E3", "E4", "E5", "M", "E6a", "E6b")
FAMILIES = ("A", "B", "C", "D", "E", "continuous")
CANONICAL_V016_COMMIT = "69e5ac6bb5a5e16f8b5c419e8674237f3f597dd8"
EXPECTED_D182 = {
    "expert_advice_decisions": ["D176-4", "D176-8", "D176-6", "D176-7"],
    "consecutive_hold": "exposure_only_training_continues",
    "foot_drag": {"baseline_fraction": 0.25, "spread_multiplier": 2,
                   "judge_from_stage": "E2", "class": "assumption"},
    "physical_flag_cells": "evaluation_record_only",
    "extension_e": {"slope_deg": 35.0, "stairs_height_m": 0.30},
    "pallets_l9": {"gap_m": 0.35, "height_delta_m": 0.30,
                   "one_axis_per_boundary": True},
}
EX42_FORMAT = "foothold-ex42-curriculum/1"
BOUNDARY_FORMAT = "foothold-ex42-boundary/1"
APPROVAL_FORMAT = "foothold-ex42-approvals/1"


def _read_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"EX-42 document must be a YAML mapping: {path}")
    return value


@dataclass(frozen=True)
class EX42Plan:
    path: Path
    document: dict[str, Any]
    sha256: str
    is_ex42: bool = True

    @classmethod
    def load(cls, path: str | Path) -> "EX42Plan":
        plan_path = Path(path).resolve(strict=True)
        raw = plan_path.read_bytes()
        doc = _read_yaml(plan_path)
        if doc.get("format") != EX42_FORMAT:
            raise ValueError("EX-42 curriculum format mismatch")
        if doc.get("status") != "preparation_only":
            raise ValueError("EX-42 table status must remain preparation_only")
        design = doc.get("design")
        if (not isinstance(design, dict)
                or design.get("canonical_commit") != CANONICAL_V016_COMMIT
                or design.get("canonical_version") != "v0.16"
                or design.get("d182_decisions") != EXPECTED_D182):
            raise ValueError("EX-42 table must match canonical v0.16 and D182")
        env = doc.get("environment")
        if not isinstance(env, dict) or env.get("num_envs") != 3072:
            raise ValueError("EX-42 requires the preregistered 3072 environment count")
        if tuple(env.get("training_presets", {}).keys()) != FAMILIES:
            raise ValueError("EX-42 terrain preset families/order differ from the contract")
        stages = doc.get("stages")
        if not isinstance(stages, list) or tuple(row.get("id") for row in stages) != STAGE_IDS:
            raise ValueError("EX-42 stage table must contain the ten canonical stages in order")
        for row in stages:
            if (type(row.get("minimum_updates")) is not int
                    or type(row.get("maximum_updates")) is not int
                    or type(row.get("extension_updates")) is not int
                    or row["minimum_updates"] <= 0
                    or row["maximum_updates"] < row["minimum_updates"]
                    or row["extension_updates"] < 0):
                raise ValueError(f"EX-42 invalid update range for {row.get('id')}")
            if not isinstance(row.get("boundary_axes"), list) or not row["boundary_axes"]:
                raise ValueError(f"EX-42 stage has no registered boundary axis: {row.get('id')}")
            if row.get("hold_policy") != "hold_exposure_continue_training":
                raise ValueError(f"EX-42 hold must stop exposure only: {row.get('id')}")
            expected_floors = {"reverse": 0.05, "side_left": 0.03, "side_right": 0.03}
            if row.get("terrain", {}).get("floors", {}).get("global_command_floor") != expected_floors:
                raise ValueError(f"EX-42 stage global command floors differ from D176: {row.get('id')}")
        evaluation = doc.get("evaluation", {})
        if (evaluation.get("judge_cells") != 26 or evaluation.get("record_only_cells") != 13
                or evaluation.get("total_cells") != 39
                or evaluation.get("map_modes") != ["gt", "pred", "off"]
                or evaluation.get("judge_cells", 0) + evaluation.get("record_only_cells", 0)
                != evaluation.get("total_cells")):
            raise ValueError("EX-42 evaluation must preserve 26 judge plus 13 record-only cells")
        promotion = evaluation.get("promotion", {})
        if promotion != {"window_episodes": 64, "windows": 2, "success_min": 52,
                         "survival_min": 60, "hold_if_invalid": True}:
            raise ValueError("EX-42 per-kind advancement gate differs from D159")
        pending = doc.get("assumptions_pending_lead")
        if not isinstance(pending, dict) or not pending:
            raise ValueError("EX-42 unresolved assumptions must remain visible")
        if set(pending) != {"evaluation_friction", "q4_two_window_range",
                            "next_jump_study_start", "terrain_manifest_measurements",
                            "runtime_integration"}:
            raise ValueError("EX-42 unresolved items must match the current measured gaps")
        allocation = doc.get("command_allocation", {})
        if (allocation.get("total_denominator") != 3072
                or allocation.get("conditional_denominator") != "continuous_environments"
                or allocation.get("continuous_share_min") != 0.43
                or allocation.get("global_command_floor") != {
                    "reverse": 0.05, "side_left": 0.03, "side_right": 0.03}):
            raise ValueError("EX-42 command share denominators or global floors differ from D176")
        terrain_contract = doc.get("terrain_manifest_contract", {})
        if terrain_contract.get("evaluation_axis_rule") != "harder_per_axis":
            raise ValueError("EX-42 evaluation size must be checked per axis")
        return cls(plan_path, doc, hashlib.sha256(raw).hexdigest())

    def validate_terrain_manifest(self, manifest: dict[str, Any]) -> None:
        contract = self.document["terrain_manifest_contract"]
        if manifest.get("format") != "foothold-ex42-terrain-manifest/1":
            raise ValueError("EX-42 terrain manifest format mismatch")
        if manifest.get("status") != "measured":
            raise ValueError("EX-42 terrain manifest is not measured")
        if manifest.get("training_presets") != self.document["environment"]["training_presets"]:
            raise ValueError("EX-42 terrain preset IDs differ from the table")
        measurements = manifest.get("measurements")
        if not isinstance(measurements, dict):
            raise ValueError("EX-42 terrain measurements missing")
        for key in contract["required_measurements"]:
            value = measurements.get(key)
            if (type(value) not in (int, float) or isinstance(value, bool)
                    or not math.isfinite(float(value)) or value <= 0):
                raise ValueError(f"EX-42 terrain measurement missing or invalid: {key}")
        kinds = manifest.get("kinds")
        if not isinstance(kinds, list) or not kinds:
            raise ValueError("EX-42 terrain manifest requires a nonempty per-kind inventory")
        seen: set[tuple[str, str]] = set()
        counts = {family: 0 for family in FAMILIES}
        for row in kinds:
            if not isinstance(row, dict) or any(key not in row for key in contract["each_kind_fields"]):
                raise ValueError("EX-42 terrain kind row is incomplete")
            family, kind = row["family"], row.get("kind")
            if family not in FAMILIES or not isinstance(kind, str) or not kind:
                raise ValueError("EX-42 terrain kind identity invalid")
            if (family, kind) in seen:
                raise ValueError(f"EX-42 duplicate terrain kind: {family}/{kind}")
            seen.add((family, kind))
            counts[family] += 1
            for dimension_key in ("original_dimensions_m", "training_dimensions_m", "evaluation_dimensions_m"):
                dims = row[dimension_key]
                if (not isinstance(dims, dict) or not dims
                        or any(type(v) not in (int, float) or isinstance(v, bool)
                               or not math.isfinite(float(v)) or v <= 0 for v in dims.values())):
                    raise ValueError(f"EX-42 terrain dimensions invalid: {family}/{kind}/{dimension_key}")
            train = row["training_dimensions_m"]
            evaluate = row["evaluation_dimensions_m"]
            directions = row["evaluation_axis_directions"]
            if set(train) != set(evaluate):
                raise ValueError(f"EX-42 eval/train dimension axes differ: {family}/{kind}")
            if not isinstance(directions, dict) or set(directions) != set(train):
                raise ValueError(f"EX-42 evaluation axis directions missing: {family}/{kind}")
            for axis, direction in directions.items():
                if direction not in {"higher", "lower", "same"}:
                    raise ValueError(f"EX-42 evaluation axis direction invalid: {family}/{kind}/{axis}")
                if ((direction == "higher" and not evaluate[axis] > train[axis])
                        or (direction == "lower" and not evaluate[axis] < train[axis])
                        or (direction == "same" and evaluate[axis] != train[axis])):
                    raise ValueError(f"EX-42 evaluation axis does not match direction: {family}/{kind}/{axis}")
            if not isinstance(row["geometry_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["geometry_sha256"]):
                raise ValueError(f"EX-42 geometry SHA missing: {family}/{kind}")
            if not isinstance(row["paper_reference"], str) or not row["paper_reference"].strip():
                raise ValueError(f"EX-42 paper reference missing: {family}/{kind}")
            if type(row["physical_flag"]) is not bool:
                raise ValueError(f"EX-42 physical flag must be an explicit boolean: {family}/{kind}")
        if counts != contract["kind_count_by_family"]:
            raise ValueError(f"EX-42 terrain inventory counts differ: {counts}")

    def launch_blockers(self, approvals_path: str | Path,
                        graduation_path: str | Path | None,
                        terrain_manifest_path: str | Path | None) -> list[str]:
        approvals = _read_yaml(Path(approvals_path).resolve(strict=True))
        blockers = ["runtime_integration_pending"]
        if approvals.get("format") != APPROVAL_FORMAT:
            blockers.append("approval_format_invalid")
        if approvals.get("production_launch_allowed") is not True:
            blockers.append("explicit_lead_approval_missing")
        if approvals.get("automatic_launch_allowed") is not False:
            blockers.append("automatic_launch_must_remain_disabled")
        if graduation_path is None or not Path(graduation_path).is_file():
            blockers.append("ex41_graduation_receipt_missing")
        if terrain_manifest_path is None or not Path(terrain_manifest_path).is_file():
            blockers.append("terrain_manifest_missing")
        else:
            manifest = _read_yaml(Path(terrain_manifest_path).resolve(strict=True))
            try:
                self.validate_terrain_manifest(manifest)
            except (KeyError, TypeError, ValueError):
                blockers.append("terrain_measurements_unverified")
        pending = self.document["assumptions_pending_lead"]
        if any(item.get("approved") is not True for item in pending.values()):
            blockers.append("design_assumptions_pending")
        return blockers


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"EX-42 W72 snapshot unavailable: {detail}")
    return result.stdout


def read_committed_boundary_pair(boundary_path: str | Path,
                                 approvals_path: str | Path) -> dict[str, Any]:
    """Read one clean Git revision, matching W72's boundary-only snapshot rule."""
    paths = [Path(boundary_path).resolve(strict=True), Path(approvals_path).resolve(strict=True)]
    roots = [_git(path.parent, "rev-parse", "--show-toplevel").decode().strip() for path in paths]
    if roots[0] != roots[1]:
        raise ValueError("EX-42 boundary and approvals must share one worktree")
    root = Path(roots[0])
    relative = [path.relative_to(root).as_posix() for path in paths]
    head = _git(root, "rev-parse", "HEAD").decode().strip()
    if _git(root, "status", "--porcelain", "--", *relative).strip():
        raise ValueError("EX-42 W72 refuses dirty or untracked boundary inputs")
    blobs = [_git(root, "show", f"{head}:{name}") for name in relative]
    if _git(root, "rev-parse", "HEAD").decode().strip() != head:
        raise ValueError("EX-42 W72 HEAD changed during snapshot")
    docs = [yaml.safe_load(blob.decode("utf-8-sig")) for blob in blobs]
    if not isinstance(docs[0], dict) or docs[0].get("format") != BOUNDARY_FORMAT:
        raise ValueError("EX-42 W72 boundary format mismatch")
    if not isinstance(docs[1], dict) or docs[1].get("format") != APPROVAL_FORMAT:
        raise ValueError("EX-42 W72 approval format mismatch")
    return {"commit": head,
            "boundary_sha256": hashlib.sha256(blobs[0]).hexdigest(),
            "approval_sha256": hashlib.sha256(blobs[1]).hexdigest(),
            "boundary": docs[0], "approvals": docs[1]}


def validate_boundary_transition(before: dict[str, Any], after: dict[str, Any],
                                 approvals: dict[str, Any], *,
                                 registered_axes: dict[str, set[str]]) -> list[dict[str, Any]]:
    """Require a committed, approved, single-axis transition at a W72 boundary."""
    old, new = before.get("values"), after.get("values")
    if not isinstance(old, dict) or not isinstance(new, dict):
        raise ValueError("EX-42 W72 values mapping required")
    axis = after.get("axis_id")
    allowed = after.get("allowed_diff_paths")
    if axis not in registered_axes or not isinstance(allowed, list) or not allowed:
        raise ValueError("EX-42 W72 axis is unregistered")
    if set(allowed) != registered_axes[axis]:
        raise ValueError("EX-42 W72 allowed_diff_paths differ from axis registry")
    decisions: list[dict[str, Any]] = []
    for key in sorted(allowed):
        old_value, new_value = old.get(key), new.get(key)
        if old_value == new_value:
            continue
        permit = approvals.get("fields", {}).get(key)
        if (not isinstance(permit, dict) or not isinstance(permit.get("decision_id"), str)
                or not permit["decision_id"]):
            raise ValueError(f"EX-42 W72 unapproved field: {key}")
        bounds = permit.get("bounds")
        if bounds is not None:
            if (not isinstance(new_value, (int, float)) or isinstance(new_value, bool)
                    or not math.isfinite(float(new_value)) or not isinstance(bounds, list)
                    or len(bounds) != 2 or not bounds[0] <= new_value <= bounds[1]):
                raise ValueError(f"EX-42 W72 value outside approved bounds: {key}")
        choices = permit.get("choices")
        if choices is not None and new_value not in choices:
            raise ValueError(f"EX-42 W72 value outside approved choices: {key}")
        decisions.append({"path": key, "before": old_value, "after": new_value,
                          "decision_id": permit["decision_id"], "axis_id": axis})
    changed_paths = {key for key in set(old) | set(new) if old.get(key) != new.get(key)}
    if changed_paths != {row["path"] for row in decisions}:
        raise ValueError("EX-42 W72 changes must be listed and approved on the single axis")
    return decisions


def score_cell_roles(judge_cells: dict[str, Any], record_cells: dict[str, Any]) -> dict[str, Any]:
    """Build a score payload preserving the 26 judge and 13 record-only values."""
    if len(judge_cells) != 26 or len(record_cells) != 13:
        raise ValueError("EX-42 score requires exactly 26 judge and 13 record-only cells")
    overlap = set(judge_cells) & set(record_cells)
    if overlap:
        raise ValueError(f"EX-42 score cell roles overlap: {sorted(overlap)}")
    return {"judge_cells": judge_cells, "record_only_cells": record_cells,
            "judge_count": len(judge_cells), "record_only_count": len(record_cells),
            "total_cells": len(judge_cells) + len(record_cells)}


def validate_command_shares(continuous_share: float,
                            conditional_shares: dict[str, float], *,
                            floors: dict[str, float] | None = None,
                            total_envs: int = 3072) -> dict[str, float]:
    """Validate conditional command shares against whole-environment floors."""
    if type(total_envs) is not int or total_envs != 3072:
        raise ValueError("EX-42 command denominator must remain 3072 environments")
    values = [continuous_share, *conditional_shares.values()]
    if any(type(value) not in (int, float) or isinstance(value, bool)
           or not math.isfinite(float(value)) or not 0.0 <= value <= 1.0
           for value in values):
        raise ValueError("EX-42 command shares must be finite fractions in [0, 1]")
    if abs(sum(conditional_shares.values()) - 1.0) > 1e-9:
        raise ValueError("EX-42 conditional command shares must sum to one")
    required = floors or {"reverse": 0.05, "side_left": 0.03, "side_right": 0.03}
    realized = {name: float(continuous_share) * float(conditional_shares.get(name, 0.0))
                for name in required}
    for name, floor in required.items():
        if type(floor) not in (int, float) or isinstance(floor, bool) or not 0 <= floor <= 1:
            raise ValueError(f"EX-42 invalid global command floor: {name}")
        if realized[name] + 1e-12 < floor:
            raise ValueError(f"EX-42 global floor not met: {name}={realized[name]:.6f} < {floor:.6f}")
    return realized
