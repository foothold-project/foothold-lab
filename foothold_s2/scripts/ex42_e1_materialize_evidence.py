"""Build the verifier #678 E1F materialization input from completed E1 artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any

from foothold_s2.curriculum.ex42_prep import EX42Plan


FORMAT = "foothold-ex42-materialize-evidence/1"


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    def reject(value):
        raise ValueError(f"non-finite JSON value {value} in {path}")

    data = json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=reject)
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    _finite(data)
    return data


def _finite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite measured value")
    if isinstance(value, dict):
        for child in value.values():
            _finite(child)
    elif isinstance(value, list):
        for child in value:
            _finite(child)


def _read_applied_cap_compat(ref, *, base, source_plan, stage, parent_manifest):
    """#678 read_applied_cap contract, for checkouts before that PR is integrated."""
    preflights, exposures = [], []
    log = Path(ref["path"])
    if not log.is_absolute():
        log = Path(base) / log
    log = log.resolve(strict=True)
    if _sha(log) != ref.get("sha256"):
        raise ValueError("applied-cap exposure log SHA differs")
    for line in log.read_text(encoding="utf-8", errors="strict").splitlines():
        if line.startswith(f"EX42_STAGE_{stage}_PREFLIGHT "):
            dest = preflights
            prefix = f"EX42_STAGE_{stage}_PREFLIGHT "
        elif line.startswith("EX42_E0_EXPOSURE "):
            dest = exposures
            prefix = "EX42_E0_EXPOSURE "
        else:
            continue
        try:
            row = json.loads(line[len(prefix):], parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite log value {value}")))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid {prefix.strip()} log row") from exc
        if not isinstance(row, dict):
            raise ValueError(f"invalid {prefix.strip()} log row")
        _finite(row)
        dest.append(row)
    if not preflights:
        raise ValueError("applied cap log lacks source-stage preflight")
    world = preflights[0].get("world_size")
    if (type(world) is not int or world <= 0 or len(preflights) != world or len(exposures) != world
            or sorted(row.get("rank", -1) for row in preflights) != list(range(world))):
        raise ValueError("applied cap log has incomplete/duplicate ranks")
    parent_manifest = Path(parent_manifest).resolve(strict=True)
    caps = []
    for preflight in preflights:
        approval = preflight.get("approval") or {}
        if (preflight.get("stage_id") != stage or preflight.get("world_size") != world
                or approval.get("approvals_sha256") != source_plan.document["stage_zero"]["approval_sha256"]
                or (preflight.get("rank") == 0 and
                    Path(preflight.get("output_dir", "")).resolve() != parent_manifest.parent)):
            raise ValueError("applied cap source run identity differs")
    for exposure in exposures:
        columns, values = exposure.get("exposed_columns"), exposure.get("level_caps")
        if (not isinstance(columns, list) or not columns or len(set(columns)) != len(columns)
                or not isinstance(values, list) or not values
                or any(type(column) is not int or column < 0 or column >= len(values) for column in columns)
                or any(type(cap) is not int or cap < 0 for cap in values)):
            raise ValueError("applied level cap receipt invalid")
        active = {values[column] for column in columns}
        if len(active) != 1:
            raise ValueError("continuous inherited caps are heterogeneous")
        caps.append(active.pop())
    if len(set(caps)) != 1:
        raise ValueError("applied level cap differs across ranks")
    return caps[0], {"path": str(log), "sha256": _sha(log)}


def _parse_applied_cap(log_path: Path, *, plan: EX42Plan, run: Path, manifest_path: Path) -> int:
    # Use the verifier's implementation when #678 is present in the integrated checkout.
    try:
        from foothold_s2.ex42_stage_materialize import read_applied_cap
    except ModuleNotFoundError as exc:
        if exc.name != "foothold_s2.ex42_stage_materialize":
            raise
        read_applied_cap = _read_applied_cap_compat
    cap, _exposure_ref = read_applied_cap(
        {"path": str(log_path.resolve(strict=True)), "sha256": _sha(log_path)},
        base=log_path.parent, source_plan=plan, stage="E1", parent_manifest=manifest_path)
    return cap


def build_evidence(*, source_plan_path: str | Path, parent_manifest_path: str | Path,
                   gate_receipt_path: str | Path, training_log_path: str | Path,
                   evaluation_mesh_path: str | Path, w09_baseline_path: str | Path,
                   evaluation_plan_path: str | Path | None = None) -> dict[str, Any]:
    plan_path = Path(source_plan_path).resolve(strict=True)
    plan = EX42Plan.load(plan_path)
    evaluation_path = Path(evaluation_plan_path).resolve(strict=True) if evaluation_plan_path else plan_path
    evaluation_plan = EX42Plan.load(evaluation_path)
    if "E1" not in plan.runtime_stage_ids:
        raise ValueError("source plan does not contain E1")
    manifest_path = Path(parent_manifest_path).resolve(strict=True)
    run = manifest_path.parent
    manifest = _json(manifest_path)
    gate_path = Path(gate_receipt_path).resolve(strict=True)
    gate = _json(gate_path)
    from foothold_s2.curriculum.ex42_prep import stage_exit_updates
    if (gate.get("state") != "complete" or gate.get("stage_id") != "E1"
            or gate.get("judgment") != "PASS" or gate.get("checkpoint_iteration") not in stage_exit_updates(plan.document, "E1")
            or gate.get("plan_sha256") != plan.sha256):
        raise ValueError("E1 exit boundary evaluation receipt is not complete PASS for the source plan")
    iteration = gate.get("checkpoint_iteration")
    checkpoint_sha = gate.get("checkpoint_sha256")
    checkpoints = manifest.get("checkpoints") or {}
    checkpoint = run / f"model_{iteration}.pt" if type(iteration) is int else None
    if (checkpoint is None or not checkpoint.is_file() or not isinstance(checkpoint_sha, str)
            or _sha(checkpoint) != checkpoint_sha
            or checkpoints.get(checkpoint.name) != checkpoint_sha):
        raise ValueError("E1 gate checkpoint is not the manifest-published checkpoint")
    measurement_path = gate.get("measurement")
    measurement_sha = gate.get("measurement_sha256")
    if not isinstance(measurement_path, str) or not isinstance(measurement_sha, str):
        raise ValueError("E1 boundary receipt lacks its measurement receipt")
    measurement = Path(measurement_path)
    if not measurement.is_absolute():
        measurement = gate_path.parent / measurement
    measurement = measurement.resolve(strict=True)
    if _sha(measurement) != measurement_sha:
        raise ValueError("E1 boundary measurement receipt SHA differs")
    measured = _json(measurement)
    measured_policy_sha = measured.get("maintenance_source_sha256")
    if (measured.get("checkpoint_sha256") != checkpoint_sha
            or measured.get("judgement") != "PASS"
            or (evaluation_plan.sha256 != plan.sha256 and measured_policy_sha != evaluation_plan.sha256)
            or (evaluation_plan.sha256 == plan.sha256 and measured_policy_sha not in (None, plan.sha256))):
        raise ValueError("E1 measurement checkpoint or plan identity differs")

    training_log = Path(training_log_path).resolve(strict=True)
    cap = _parse_applied_cap(training_log, plan=plan, run=run, manifest_path=manifest_path)
    mesh_path = Path(evaluation_mesh_path).resolve(strict=True)
    mesh_doc = _json(mesh_path.parent / "mesh_manifest.json")
    terrain = plan.document["assumptions_pending_lead"]["terrain_manifest_measurements"]
    terrain = terrain.get("value") if isinstance(terrain, dict) else None
    if (mesh_doc.get("format") != "foothold-ex42-combined-mesh/1" or mesh_doc.get("seed") != 42
            or not isinstance(terrain, dict) or mesh_doc.get("mesh_sha256") != terrain.get("mesh_sha256")
            or mesh_doc.get("mesh_file_sha256") not in (None, _sha(mesh_path))):
        raise ValueError("evaluation NPZ is not the plan-pinned seed-42 combined mesh")
    baseline_path = Path(w09_baseline_path).resolve(strict=True)
    baseline = _json(baseline_path)
    if not baseline:
        raise ValueError("W09 baseline artifact is empty")
    evidence = {
        "format": FORMAT,
        "target_stage": "E1F",
        "source_stage": "E1",
        "source_plan_sha256": plan.sha256,
        "checkpoint_sha256": checkpoint_sha,
        "gate_sha256": _sha(gate_path),
        "exposure_receipt": {"path": str(training_log), "sha256": _sha(training_log)},
        "applied_level_cap": cap,
        "bindings": {
            "prerequisites.predecessor_exit.evaluation_mesh_sha256": {
                "path": str(mesh_path), "sha256": _sha(mesh_path)},
            "prerequisites.flag_baseline.sha256": {
                "path": str(baseline_path), "sha256": _sha(baseline_path)},
        },
    }
    if evaluation_plan.sha256 != plan.sha256:
        evidence["evaluation_plan"] = {"path": str(evaluation_path), "sha256": _sha(evaluation_path)}
    return evidence


def write_evidence(*, out_path: str | Path, **inputs) -> dict[str, Any]:
    destination = Path(out_path).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"refusing to replace materialization evidence: {destination}")
    row = build_evidence(**inputs)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(row, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(name, destination)
    finally:
        Path(name).unlink(missing_ok=True)
    return row


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source-plan", "parent-manifest", "gate-receipt", "training-log",
                 "evaluation-mesh", "w09-baseline", "out"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--evaluation-plan")
    args = vars(parser.parse_args(argv))
    out = args.pop("out")
    try:
        print(json.dumps({"state": "ready", "evidence": str(Path(out).absolute()),
                          "record": write_evidence(out_path=out, **{
                              key.replace("-", "_"): value for key, value in args.items()})},
                         ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"state": "blocked", "reason": f"{type(exc).__name__}: {exc}"},
                         ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
