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
STAGE_ZERO_ID = "EX42_0_T0_prime"
RUNTIME_STAGE_IDS = (STAGE_ZERO_ID, *STAGE_IDS)
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


def scoped_automatic_policy(value: Any) -> bool:
    """Only the approved-stage, PASS-required policy can enable automatic dispatch."""
    return (isinstance(value, dict)
            and set(value) == {"mode", "require_gate_pass", "notify", "decision_source"}
            and value.get("mode") == "approved_stage_only"
            and value.get("require_gate_pass") is True
            and value.get("notify") is True
            and value.get("decision_source") == "c5471d370d634ed2a381d8249a10c652c143f699")


def bounded_automatic_policy(value: Any) -> bool:
    """Legacy disabled and explicitly scoped policies both preserve the full-plan block."""
    return value is False or scoped_automatic_policy(value)


def validate_stage_zero_authorization(plan: "EX42Plan", approvals_path: str | Path) -> dict[str, Any]:
    """Validate the separately approved, bounded T0-prime bridge only.

    This does not change the full-plan launch blockers or grant authorization
    to E0 and later. The approval bytes are pinned by the curriculum table.
    """
    path = Path(approvals_path).resolve(strict=True)
    raw = path.read_bytes()
    actual_sha = hashlib.sha256(raw).hexdigest()
    expected_sha = plan.document["stage_zero"].get("approval_sha256")
    if not isinstance(expected_sha, str) or actual_sha != expected_sha:
        raise ValueError("EX-42 stage-zero approval SHA256 differs from pinned table")
    approvals = _read_yaml(path)
    if (approvals.get("format") != APPROVAL_FORMAT
            or approvals.get("status") != "blocked"
            or approvals.get("production_launch_allowed") is not False
            or not bounded_automatic_policy(approvals.get("automatic_launch_allowed"))):
        raise ValueError("EX-42 full-plan launch guard must remain blocked")
    scoped = approvals.get("stage_zero_authorization")
    if not isinstance(scoped, dict) or scoped.get("approved") is not True:
        raise ValueError("EX-42 stage-zero authorization is missing")
    expected_scope = {
        "stage_id": STAGE_ZERO_ID,
        "source_stage_id": "T0_prime",
        "start_update": 0,
        "maximum_updates": 1000,
        "parent_sha256": plan.document["stage_zero"]["parent"]["sha256"],
        "later_stages_authorized": False,
    }
    if scoped.get("scope") != expected_scope:
        raise ValueError("EX-42 stage-zero approval scope differs from the bounded bridge")
    evidence = scoped.get("evidence")
    if (not isinstance(evidence, dict)
            or evidence.get("ex41_graduated") is not False
            or evidence.get("ex41_requires_review") is not True
            or evidence.get("human_review_complete") is not True
            or evidence.get("adopted_parent_decision") != "teamlead-2026-11-07-m12000"
            or evidence.get("stage_zero_decision") != "teamlead-2026-11-08-m13000"):
        raise ValueError("EX-42 stage-zero approval evidence is incomplete")
    decision_id = scoped.get("decision_id")
    approved_at = scoped.get("approved_at")
    if (not isinstance(decision_id, str) or not decision_id.strip()
            or approved_at != "2026-11-08T00:25:58Z"):
        raise ValueError("EX-42 stage-zero approval identity or timestamp is invalid")
    dr = approvals.get("domain_randomization", {})
    if (not isinstance(dr, dict) or dr.get("approved") is not True
            or dr.get("stage_scales", {}).get(STAGE_ZERO_ID) != 1.0):
        raise ValueError("EX-42 stage-zero DR scale must be explicitly approved as 1.0")
    return {"state": "stage_zero_only_authorized", "scope": expected_scope,
            "decision_id": decision_id, "approved_at": approved_at,
            "approvals_path": str(path), "approvals_sha256": actual_sha,
            "production_launch_allowed": False, "later_stages_authorized": False}


def validate_stage_e0_authorization(plan: "EX42Plan", approvals_path: str | Path,
                                    e_parent_sha256: str) -> dict[str, Any]:
    """Read the separately approved, bounded E0 cell (m13000 -> 250 updates). E1 and later are never opened.

    A missing or incomplete cell fails closed. The approvals file bytes are not re-pinned here:
    the launch source lock (audit_ex42_launch_source) protects the file, and the stage-zero
    pin in the curriculum table is left to the lead.
    """
    path = Path(approvals_path).resolve(strict=True)
    approvals = _read_yaml(path)
    if (approvals.get("format") != APPROVAL_FORMAT
            or approvals.get("status") != "blocked"
            or approvals.get("production_launch_allowed") is not False
            or not bounded_automatic_policy(approvals.get("automatic_launch_allowed"))):
        raise ValueError("EX-42 full-plan launch guard must remain blocked")
    cell = approvals.get("stage_e0_authorization")
    if not isinstance(cell, dict) or cell.get("approved") is not True:
        raise ValueError("EX-42 E0 authorization is missing")
    stage = next((row for row in plan.document["stages"] if row.get("id") == "E0"), None)
    if (stage is None or stage.get("enabled") is not True
            or stage.get("minimum_updates") != 250 or stage.get("maximum_updates") != 250
            or stage.get("extension_updates") != 0):
        raise ValueError("EX-42 E0 stage in the curriculum table is not the bounded 250-update stage")
    expected_scope = {
        "stage_id": "E0",
        "start_update": 0,
        "maximum_updates": 250,
        "parent_sha256": e_parent_sha256,
        "later_stages_authorized": False,
    }
    if cell.get("scope") != expected_scope:
        raise ValueError("EX-42 E0 approval scope differs from the bounded E0 stage")
    decision_id = cell.get("decision_id")
    approved_at = cell.get("approved_at")
    if (not isinstance(decision_id, str) or not decision_id.strip()
            or not isinstance(approved_at, str) or not approved_at.strip()
            or not isinstance(cell.get("approver"), str) or not cell["approver"].strip()):
        raise ValueError("EX-42 E0 approval identity or timestamp is missing")
    dr = approvals.get("domain_randomization", {})
    if (not isinstance(dr, dict) or dr.get("approved") is not True
            or dr.get("stage_scales", {}).get("E0") != 1.0):
        raise ValueError("EX-42 E0 DR scale must be explicitly approved as 1.0")
    return {"state": "stage_e0_only_authorized", "scope": expected_scope,
            "decision_id": decision_id, "approved_at": approved_at,
            "approvals_path": str(path),
            "approvals_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "production_launch_allowed": False, "later_stages_authorized": False}


def validate_stage_e1_authorization(plan: "EX42Plan", approvals_path: str | Path,
                                    e1_parent_sha256: str) -> dict[str, Any]:
    """Read the separately approved, bounded E1 first segment (E0 m250 -> 1000 updates).

    Same fail-closed shape as the E0 cell: a missing or incomplete `stage_e1_authorization` raises.
    E1F and later stages are never opened by it. The extension (+500 x 2) and the L+ cap raise are
    separate boundaries and are not covered by this cell.
    """
    path = Path(approvals_path).resolve(strict=True)
    approvals = _read_yaml(path)
    if (approvals.get("format") != APPROVAL_FORMAT
            or approvals.get("status") != "blocked"
            or approvals.get("production_launch_allowed") is not False
            or not bounded_automatic_policy(approvals.get("automatic_launch_allowed"))):
        raise ValueError("EX-42 full-plan launch guard must remain blocked")
    cell = approvals.get("stage_e1_authorization")
    if not isinstance(cell, dict) or cell.get("approved") is not True:
        raise ValueError("EX-42 E1 authorization is missing")
    stage = next((row for row in plan.document["stages"] if row.get("id") == "E1"), None)
    if (stage is None or stage.get("enabled") is not True
            or stage.get("minimum_updates") != 1000 or stage.get("maximum_updates") != 2000
            or stage.get("extension_updates") != 500 or stage.get("critic_mirror") is not True):
        raise ValueError("EX-42 E1 stage in the curriculum table is not the 1000-update first segment with the D174 mirror")
    expected_scope = {
        "stage_id": "E1",
        "start_update": 0,
        "maximum_updates": 1000,
        "parent_sha256": e1_parent_sha256,
        "later_stages_authorized": False,
    }
    if cell.get("scope") != expected_scope:
        raise ValueError("EX-42 E1 approval scope differs from the bounded E1 first segment")
    decision_id = cell.get("decision_id")
    approved_at = cell.get("approved_at")
    if (not isinstance(decision_id, str) or not decision_id.strip()
            or not isinstance(approved_at, str) or not approved_at.strip()
            or not isinstance(cell.get("approver"), str) or not cell["approver"].strip()):
        raise ValueError("EX-42 E1 approval identity or timestamp is missing")
    dr = approvals.get("domain_randomization", {})
    if (not isinstance(dr, dict) or dr.get("approved") is not True
            or dr.get("stage_scales", {}).get("E1") != 1.0):
        raise ValueError("EX-42 E1 DR scale must be explicitly approved as 1.0")
    mirror = approvals.get("fields", {}).get("critic_mirror")
    if (not isinstance(mirror, dict) or mirror.get("approved") is not True
            or mirror.get("decision_id") != "D174" or mirror.get("choices") != [True]
            or mirror.get("boundaries") != ["E1"]):
        raise ValueError("EX-42 E1 critic mirror requires its explicit D174 approval")
    # The approval is conditional on the E0 re-judgement and bounded to the first 1000 updates.
    rejudgment = (cell.get("prerequisites") or {}).get("e0_rejudgment") if isinstance(cell.get("prerequisites"), dict) else None
    if (not isinstance(rejudgment, dict) or rejudgment.get("required_result") != "PASS"
            or rejudgment.get("checkpoint_key") != stage["parent"]["checkpoint_key"]
            or rejudgment.get("checkpoint_sha256") != e1_parent_sha256):
        raise ValueError("EX-42 E1 approval lacks the E0 re-judgement PASS prerequisite on the pinned parent")
    if cell.get("extension_authorized") is not False:
        raise ValueError("EX-42 E1 approval must keep the +500 extension unauthorized")
    interval = cell.get("boundary_evaluation_interval_updates")
    plan_interval = plan.document.get("evaluation", {}).get("interval_updates")
    if (type(interval) is not int or interval <= 0 or interval != plan_interval
            or expected_scope["maximum_updates"] % interval):
        raise ValueError("EX-42 E1 boundary evaluation interval must match the plan evaluation interval and divide 1000")
    return {"state": "stage_e1_only_authorized", "scope": expected_scope,
            "boundary_evaluation_interval_updates": interval, "extension_authorized": False,
            "e0_rejudgment_prerequisite": rejudgment,
            "decision_id": decision_id, "approved_at": approved_at,
            "approvals_path": str(path),
            "approvals_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "production_launch_allowed": False, "later_stages_authorized": False}


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
        if not isinstance(env, dict) or env.get("num_envs") != 6144:
            raise ValueError("EX-42 full plan requires 6144 environments")
        if tuple(env.get("training_presets", {}).keys()) != FAMILIES:
            raise ValueError("EX-42 terrain preset families/order differ from the contract")
        stages = doc.get("stages")
        if not isinstance(stages, list) or tuple(row.get("id") for row in stages) != STAGE_IDS:
            raise ValueError("EX-42 stage table must contain the ten canonical stages in order")
        stage_zero = doc.get("stage_zero")
        if not isinstance(stage_zero, dict) or stage_zero.get("id") != STAGE_ZERO_ID:
            raise ValueError("EX-42 must define the explicit EX-41 T0-prime bridge as stage zero")
        source = stage_zero.get("source")
        if (not isinstance(source, dict) or source.get("experiment_id") != "EX-41"
                or source.get("stage_id") != "T0_prime"):
            raise ValueError("EX-42 stage zero must identify its EX-41 T0-prime source")
        source_name = source.get("path")
        if not isinstance(source_name, str) or Path(source_name).name != source_name:
            raise ValueError("EX-42 stage-zero source must be a same-directory file name")
        source_path = plan_path.parent / source_name
        source_raw = source_path.read_bytes()
        normalized_sha = hashlib.sha256(source_raw.replace(b"\r\n", b"\n")).hexdigest()
        if source.get("normalized_sha256") != normalized_sha:
            raise ValueError("EX-42 stage-zero source SHA differs from the EX-41 fixed table")
        source_doc = _read_yaml(source_path)
        source_stage = next((row for row in source_doc.get("stages", [])
                             if row.get("id") == "T0_prime"), None)
        if source_stage is None:
            raise ValueError("EX-42 T0-prime source stage is missing")
        for key in ("shares", "ranges", "force_gt", "terrain"):
            if stage_zero.get(key) != source_stage.get(key):
                raise ValueError(f"EX-42 stage zero differs from EX-41 T0-prime {key}")
        parent = stage_zero.get("parent")
        if parent != {
                "cumulative_update": 12000,
                "manifest_local_update": 6000,
                "sha256": "1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613",
        }:
            raise ValueError("EX-42 stage zero parent must match the EX-41 cumulative m12000 manifest SHA")
        if (stage_zero.get("minimum_updates") != 1000
                or stage_zero.get("maximum_updates") != 1000
                or stage_zero.get("extension_updates") != 0
                or stage_zero.get("start_update") != 0):
            raise ValueError("EX-42 T0-prime bridge must be exactly 1000 updates from local update zero")
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
            if "critic_mirror" in row and (row.get("id") != "E1" or row["critic_mirror"] is not True):
                raise ValueError("EX-42 critic mirror may be enabled only at E1")
        if next(row for row in stages if row.get("id") == "E1").get("critic_mirror") is not True:
            raise ValueError("EX-42 E1 must enable the approved D174 critic mirror")
        if stage_zero.get("critic_mirror", False) is not False:
            raise ValueError("EX-42 stage zero critic mirror must remain off")
        mirror_approval = (doc.get("approval_file") and
                           _read_yaml(plan_path.parent / doc["approval_file"]).get("fields", {}).get("critic_mirror"))
        if (not isinstance(mirror_approval, dict) or mirror_approval.get("approved") is not True
                or mirror_approval.get("decision_id") != "D174"
                or mirror_approval.get("choices") != [True]
                or mirror_approval.get("boundaries") != ["E1"]):
            raise ValueError("EX-42 E1 critic mirror requires its explicit D174 approval")
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
        if (allocation.get("total_denominator") != env["num_envs"]
                or allocation.get("conditional_denominator") != "continuous_environments"
                or allocation.get("continuous_share_min") != 0.43
                or allocation.get("global_command_floor") != {
                    "reverse": 0.05, "side_left": 0.03, "side_right": 0.03}):
            raise ValueError("EX-42 command share denominators or global floors differ from D176")
        terrain_contract = doc.get("terrain_manifest_contract", {})
        if terrain_contract.get("evaluation_axis_rule") != "harder_per_axis":
            raise ValueError("EX-42 evaluation size must be checked per axis")
        return cls(plan_path, doc, hashlib.sha256(raw).hexdigest())

    @property
    def runtime_stages(self) -> tuple[dict[str, Any], ...]:
        """One stage sequence shared by transition, DR approval, and score identity."""
        zero = self.document["stage_zero"]
        first = {"id": zero["id"], "start": {"fixed_update": zero["start_update"]},
                 "duration": {"minimum_updates": zero["minimum_updates"],
                              "maximum_updates": zero["maximum_updates"],
                              "extension_updates": zero["extension_updates"]},
                 "shares": zero["shares"], "ranges": zero["ranges"],
                 "force_gt": zero["force_gt"], "terrain": zero["terrain"],
                 "critic_mirror": False}
        return (first, *tuple(self.document["stages"]))

    @property
    def runtime_stage_ids(self) -> tuple[str, ...]:
        return tuple(row["id"] for row in self.runtime_stages)

    def stage_id_at(self, local_iteration: int, *, transitions: tuple[dict[str, Any], ...] = ()) -> str:
        """Resolve a checkpoint's stage from the shared sequence and applied receipts.

        EX42_0_T0_prime is known at startup. After its boundary, actual transition
        receipts are required so extensions cannot be mistaken for nominal timing.
        """
        if type(local_iteration) is not int or local_iteration < 0:
            raise ValueError("EX-42 score checkpoint iteration must be a nonnegative integer")
        ids = self.runtime_stage_ids
        if local_iteration <= self.document["stage_zero"]["maximum_updates"]:
            return ids[0]
        current_index = 0
        last_boundary = 0
        for row in transitions:
            if not isinstance(row, dict):
                raise ValueError("EX-42 transition history row is invalid")
            boundary = row.get("boundary_iteration")
            if type(boundary) is not int or boundary <= last_boundary:
                raise ValueError("EX-42 transition history boundary is invalid or out of order")
            if boundary > local_iteration:
                break
            next_index = current_index + 1
            if (next_index >= len(ids) or row.get("stage_before") != ids[current_index]
                    or row.get("stage_after") != ids[next_index]):
                raise ValueError("EX-42 transition history does not follow the shared stage sequence")
            current_index = next_index
            last_boundary = boundary
        if current_index == 0:
            raise ValueError("EX-42 score stage is unknown without an applied stage-zero transition receipt")
        return ids[current_index]

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

    def verify_parent_manifest(self, manifest_path: str | Path, *,
                               stage_id: str = STAGE_ZERO_ID,
                               parent_pin: dict[str, Any] | None = None) -> dict[str, Any]:
        """Resolve the stage-zero or E0 parent by its pinned manifest SHA."""
        if stage_id == STAGE_ZERO_ID:
            selected = self.document["stage_zero"]["parent"]
        else:
            selected = next((row.get("parent") for row in self.document["stages"] if row["id"] == stage_id), None)
            if not isinstance(selected, dict):
                raise ValueError(f"EX-42 unknown pinned parent stage: {stage_id}")
        if parent_pin is not None and any(selected.get(key) != value
                                          for key, value in parent_pin.items()):
            raise ValueError(f"EX-42 {stage_id} parent override differs from the pinned table")
        pin = selected if parent_pin is None else parent_pin
        path = Path(manifest_path).resolve(strict=True)
        try:
            manifest = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"EX-42 parent manifest is unreadable: {exc}") from exc
        if not isinstance(manifest, dict):
            raise ValueError("EX-42 parent manifest must be a JSON object")
        progress = manifest.get("progress")
        local_update = pin["manifest_local_update"]
        if (not isinstance(progress, dict) or type(progress.get("completed_updates")) is not int
                or progress["completed_updates"] < local_update):
            raise ValueError("EX-42 parent manifest has not completed the pinned local update")
        checkpoints = manifest.get("checkpoints")
        if not isinstance(checkpoints, dict):
            raise ValueError("EX-42 parent manifest has no checkpoint inventory")
        expected = pin["sha256"]
        matches = [name for name, digest in checkpoints.items() if digest == expected]
        if len(matches) != 1:
            raise ValueError("EX-42 parent manifest must contain exactly one checkpoint with the pinned SHA")
        if pin.get("checkpoint_key") is not None and matches[0] != pin["checkpoint_key"]:
            raise ValueError("EX-42 parent checkpoint key differs from the pinned E0 parent")
        checkpoint = (path.parent / matches[0]).resolve(strict=True)
        if checkpoint.parent != path.parent or not checkpoint.is_file():
            raise ValueError("EX-42 parent checkpoint must be a file beside its manifest")
        actual = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError("EX-42 parent checkpoint bytes differ from manifest-pinned SHA")
        return {
            "manifest_path": str(path),
            "manifest_completed_updates": progress["completed_updates"],
            "manifest_checkpoint_key": matches[0],
            "checkpoint_path": str(checkpoint),
            "cumulative_update": pin["cumulative_update"],
            "checkpoint_sha256": actual,
        }

    def validate_stage_command_shares(self, stage_id: str, continuous_share: float,
                                      conditional_shares: dict[str, float]) -> dict[str, float]:
        """Validate a candidate boundary allocation against that stage's absolute floors."""
        stage = next((row for row in self.document["stages"] if row["id"] == stage_id), None)
        if stage is None:
            raise ValueError(f"EX-42 command allocation references unknown stage: {stage_id}")
        floors = stage["terrain"]["floors"]["global_command_floor"]
        return validate_command_shares(continuous_share, conditional_shares, floors=floors,
                                       total_envs=self.document["command_allocation"]["total_denominator"])

    def launch_blockers(self, approvals_path: str | Path,
                        graduation_path: str | Path | None,
                        terrain_manifest_path: str | Path | None) -> list[str]:
        approvals = _read_yaml(Path(approvals_path).resolve(strict=True))
        blockers = []
        runtime = self.document["assumptions_pending_lead"]["runtime_integration"]
        if runtime.get("approved") is not True or runtime.get("value", {}).get("merged") is not True:
            blockers.append("runtime_integration_pending")
        if approvals.get("format") != APPROVAL_FORMAT:
            blockers.append("approval_format_invalid")
        if approvals.get("production_launch_allowed") is not True:
            blockers.append("explicit_lead_approval_missing")
        if not bounded_automatic_policy(approvals.get("automatic_launch_allowed")):
            blockers.append("automatic_launch_policy_invalid")
        adoption = self.document["launch"].get("parent_adoption")
        if (self.document["launch"].get("require_ex41_graduation") is not False
                or adoption != {"decision": "285348de", "checkpoints": ["m12000_20261107", "m13000_20261108"]}):
            blockers.append("parent_adoption_decision_missing")
        e_parent = next(row for row in self.document["stages"] if row["id"] == "E0").get("parent")
        if e_parent != {"cumulative_update": 13000, "manifest_local_update": 1000,
                        "checkpoint_key": "model_1000.pt",
                        "sha256": "20365a2c6d70f94f65f1114471f7df198e56d86db6d02d89cea43c666b95e768"}:
            blockers.append("e0_parent_pin_mismatch")
        if graduation_path is None or not Path(graduation_path).is_file():
            blockers.append("e0_parent_manifest_missing")
        else:
            try:
                self.verify_parent_manifest(graduation_path, stage_id="E0")
            except (OSError, KeyError, TypeError, ValueError):
                blockers.append("e0_parent_manifest_invalid")
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
                            total_envs: int = 6144) -> dict[str, float]:
    """Validate conditional command shares against whole-environment floors."""
    if type(total_envs) is not int or total_envs != 6144:
        raise ValueError("EX-42 command denominator must be 6144 environments")
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
