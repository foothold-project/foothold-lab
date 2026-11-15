"""Kit-backed EX-42 per-kind terrain measurement and manifest assembly.

No dimensions or geometry hashes are invented here. Family-specific callers
must supply measured dimensions and actual cfg objects; incomplete family
receipts remain partial and cannot pass the production gate.
"""
from __future__ import annotations

from collections import Counter
import copy
import hashlib
import math
import time
from typing import Any, Iterable

from foothold_s2.curriculum.ex42_prep import EX42Plan

RECEIPT_FORMAT = "foothold-ex42-kind-measurement/1"
MANIFEST_FORMAT = "foothold-ex42-terrain-manifest/1"
# Linux ai-lx01 has two cards and lead assigns the idle one; the receipt records the real device.
MEASURE_DEVICES = ("cuda:0", "cuda:1")


def measure_kind_with_kit(
    *, family: str, kind: str, preset_id: str, generator_cfg: Any,
    subterrain_cfg: Any, original_dimensions_m: dict[str, float],
    training_dimensions_m: dict[str, float], evaluation_dimensions_m: dict[str, float],
    evaluation_axis_directions: dict[str, str], paper_reference: str,
    physical_flag: bool, source_head: str, seed: int, device: str = "cuda:1",
) -> tuple[dict[str, Any], float]:
    """Generate one isolated tile in Kit, hash raw geometry, and return its row."""
    if (not isinstance(family, str) or not family
            or not isinstance(kind, str) or not kind
            or not isinstance(preset_id, str) or not preset_id
            or not isinstance(paper_reference, str) or not paper_reference.strip()):
        raise ValueError("EX-42 measured kind identity and reference are required")
    if type(physical_flag) is not bool:
        raise ValueError("EX-42 physical_flag must be explicit true or false")
    for label, dimensions in (("original", original_dimensions_m),
                              ("training", training_dimensions_m),
                              ("evaluation", evaluation_dimensions_m)):
        if (not isinstance(dimensions, dict) or not dimensions
                or any(not isinstance(key, str) or not key
                       or isinstance(value, bool) or not isinstance(value, (int, float))
                       or not math.isfinite(float(value)) or value <= 0
                       for key, value in dimensions.items())):
            raise ValueError(f"EX-42 {label} dimensions must be declared positive numeric values")
    if not isinstance(evaluation_axis_directions, dict):
        raise ValueError("EX-42 evaluation axis directions must be a mapping")
    if (len(source_head) != 40 or any(c not in "0123456789abcdef" for c in source_head)
            or type(seed) is not int):
        raise ValueError("EX-42 measurement source SHA or seed invalid")
    from isaaclab.terrains import TerrainGenerator

    cfg = copy.deepcopy(generator_cfg)
    cfg.num_rows, cfg.num_cols = 1, 1
    cfg.use_cache = False
    cfg.curriculum = True
    cfg.seed = seed
    cfg.sub_terrains = {kind: copy.deepcopy(subterrain_cfg)}
    cfg.sub_terrains[kind].proportion = 1.0
    started = time.perf_counter()
    generated = TerrainGenerator(cfg)
    elapsed = time.perf_counter() - started
    mesh = generated.terrain_mesh
    vertices, faces = mesh.vertices, mesh.faces
    if len(vertices) == 0 or len(faces) == 0:
        raise ValueError(f"EX-42 generated empty mesh for {family}/{kind}")
    return ({
        "family": family,
        "kind": kind,
        "preset_id": preset_id,
        "original_dimensions_m": dict(original_dimensions_m),
        "training_dimensions_m": dict(training_dimensions_m),
        "evaluation_dimensions_m": dict(evaluation_dimensions_m),
        "evaluation_axis_directions": dict(evaluation_axis_directions),
        "geometry_sha256": hashlib.sha256(vertices.tobytes() + faces.tobytes()).hexdigest(),
        "geometry_bounds_m": [[float(v) for v in row] for row in mesh.bounds.tolist()],
        "paper_reference": paper_reference,
        "physical_flag": physical_flag,
        "measurement_provenance": {
            "source_head": source_head, "seed": seed, "device": device,
            "vertex_count": int(len(vertices)), "face_count": int(len(faces)),
            "generation_seconds": elapsed,
        },
    }, elapsed)


def build_family_receipt(
    family: str, rows: list[dict[str, Any]], *, receipt_id: str,
    source_head: str, seed: int, device: str = "cuda:1",
) -> dict[str, Any]:
    """Seal Kit-generated rows as a non-training family measurement receipt."""
    if not rows or any(row.get("family") != family for row in rows):
        raise ValueError("EX-42 family receipt rows must all belong to its family")
    if device not in MEASURE_DEVICES:
        raise ValueError(f"EX-42 terrain measurement device must be one of {MEASURE_DEVICES}")
    if (not receipt_id or len(source_head) != 40
            or any(c not in "0123456789abcdef" for c in source_head)
            or type(seed) is not int):
        raise ValueError("EX-42 family receipt identity, source SHA, or seed invalid")
    for row in rows:
        provenance = row.get("measurement_provenance")
        if (not isinstance(provenance, dict) or provenance.get("source_head") != source_head
                or provenance.get("seed") != seed or provenance.get("device") != device):
            raise ValueError("EX-42 family receipt row provenance mismatch")
    return {
        "format": RECEIPT_FORMAT, "state": "passed", "receipt_id": receipt_id,
        "family": family, "source_head": source_head, "seed": seed,
        "device": device, "kit_started": True, "training_started": False,
        "kinds": rows,
    }


def _validate_kind_row(row: dict[str, Any]) -> None:
    required = {
        "family", "kind", "preset_id", "original_dimensions_m",
        "training_dimensions_m", "evaluation_dimensions_m",
        "evaluation_axis_directions", "geometry_sha256", "paper_reference",
        "physical_flag",
    }
    missing = required - row.keys()
    if missing:
        raise ValueError(f"EX-42 measured kind row missing fields: {sorted(missing)}")
    provenance = row.get("measurement_provenance")
    if (not isinstance(row["family"], str) or not row["family"]
            or not isinstance(row["kind"], str) or not row["kind"]
            or not isinstance(row["preset_id"], str) or not row["preset_id"]
            or type(row["physical_flag"]) is not bool
            or not isinstance(row["paper_reference"], str)
            or not row["paper_reference"].strip()
            or not isinstance(row["geometry_sha256"], str)
            or len(row["geometry_sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in row["geometry_sha256"])):
        raise ValueError("EX-42 kind identity, source, physical flag, or geometry SHA invalid")
    if (not isinstance(provenance, dict) or provenance.get("kit_receipt_state") != "passed"
            or provenance.get("training_started") is not False
            or provenance.get("device") not in MEASURE_DEVICES
            or not isinstance(provenance.get("source_head"), str)
            or len(provenance["source_head"]) != 40
            or any(c not in "0123456789abcdef" for c in provenance["source_head"])
            or not isinstance(provenance.get("receipt_id"), str)
            or not provenance["receipt_id"]):
        raise ValueError("EX-42 kind must reference a passed queued Kit measurement")
    for key in ("original_dimensions_m", "training_dimensions_m", "evaluation_dimensions_m"):
        dimensions = row[key]
        if (not isinstance(dimensions, dict) or not dimensions
                or any(isinstance(value, bool) or not isinstance(value, (int, float))
                       or not math.isfinite(float(value)) or value <= 0
                       for value in dimensions.values())):
            raise ValueError(f"EX-42 kind dimensions invalid: {key}")
    train, evaluate = row["training_dimensions_m"], row["evaluation_dimensions_m"]
    directions = row["evaluation_axis_directions"]
    if set(train) != set(evaluate) or not isinstance(directions, dict) or set(directions) != set(train):
        raise ValueError("EX-42 measured kind axis metadata is incomplete")
    for axis, direction in directions.items():
        if direction not in {"higher", "lower", "same"}:
            raise ValueError(f"EX-42 measured kind direction invalid: {axis}")
        if ((direction == "higher" and not evaluate[axis] > train[axis])
                or (direction == "lower" and not evaluate[axis] < train[axis])
                or (direction == "same" and evaluate[axis] != train[axis])):
            raise ValueError(f"EX-42 measured dimensions contradict declared direction: {axis}")


def assemble_manifest(
    plan: EX42Plan, family_receipts: Iterable[dict[str, Any]], *,
    aggregate_measurements: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Combine family receipts; only exact complete inventory becomes measured."""
    expected_counts = plan.document["terrain_manifest_contract"]["kind_count_by_family"]
    kinds: list[dict[str, Any]] = []
    receipt_ids: set[str] = set()
    seen_kinds: set[tuple[str, str]] = set()
    for receipt in family_receipts:
        if not isinstance(receipt, dict) or receipt.get("format") != RECEIPT_FORMAT:
            raise ValueError("EX-42 family measurement receipt format mismatch")
        if receipt.get("state") != "passed":
            raise ValueError("EX-42 family measurement receipt did not pass")
        receipt_id = receipt.get("receipt_id")
        if not isinstance(receipt_id, str) or not receipt_id or receipt_id in receipt_ids:
            raise ValueError("EX-42 family measurement receipt_id missing or duplicated")
        receipt_ids.add(receipt_id)
        source_head = receipt.get("source_head")
        if (not isinstance(source_head, str) or len(source_head) != 40
                or any(c not in "0123456789abcdef" for c in source_head)):
            raise ValueError("EX-42 measurement receipt source_head missing or invalid")
        if (receipt.get("training_started") is not False
                or receipt.get("device") not in MEASURE_DEVICES or receipt.get("kit_started") is not True):
            raise ValueError("EX-42 measurement must be a queued non-training Kit probe")
        family = receipt.get("family")
        if family not in expected_counts:
            raise ValueError(f"EX-42 unknown measured terrain family: {family}")
        rows = receipt.get("kinds")
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"EX-42 family receipt has no measured kinds: {family}")
        for source_row in rows:
            if not isinstance(source_row, dict) or source_row.get("family") != family:
                raise ValueError("EX-42 kind row family differs from its receipt")
            row = dict(source_row)
            provenance = dict(row.get("measurement_provenance") or {})
            provenance.update({
                "receipt_id": receipt_id, "kit_receipt_state": receipt["state"],
                "training_started": False, "device": receipt["device"],
                "source_head": source_head,
            })
            row["measurement_provenance"] = provenance
            _validate_kind_row(row)
            identity = (row["family"], row["kind"])
            if identity in seen_kinds:
                raise ValueError(f"EX-42 duplicate terrain kind across receipts: {identity[0]}/{identity[1]}")
            seen_kinds.add(identity)
            kinds.append(row)

    counts = Counter(row["family"] for row in kinds)
    if any(count > expected_counts[family] for family, count in counts.items()):
        raise ValueError("EX-42 measured family contains more kinds than the canonical inventory")
    complete = counts == Counter(expected_counts)
    measurements = dict(aggregate_measurements or {})
    required_metrics = plan.document["terrain_manifest_contract"]["required_measurements"]
    missing_metrics = [
        key for key in required_metrics
        if (type(measurements.get(key)) not in (int, float)
            or not math.isfinite(float(measurements[key])) or measurements[key] <= 0)
    ]
    manifest = {
        "format": MANIFEST_FORMAT,
        "status": "partial",
        "training_presets": plan.document["environment"]["training_presets"],
        "measurements": measurements,
        "kinds": kinds,
        "receipt_ids": sorted(receipt_ids),
        "family_counts_observed": dict(sorted(counts.items())),
        "family_counts_expected": expected_counts,
        "blockers": [],
    }
    if not complete:
        manifest["blockers"].append("per_kind_inventory_incomplete")
    if missing_metrics:
        manifest["blockers"].append("aggregate_measurements_missing:" + ",".join(missing_metrics))
    if complete and not missing_metrics:
        manifest["status"] = "measured"
        plan.validate_terrain_manifest(manifest)
    return manifest
