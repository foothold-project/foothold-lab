"""Bounded automatic-stage authorization only; never starts training or sends messages."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from foothold_s2.curriculum.ex42_prep import (
    EX42Plan, _read_yaml, scoped_automatic_policy, authorization_validators,
)
from foothold_s2.ex42_gate_checks import validate_ex42_map_score, validate_score_pair


TRANSITION_KEYS = ('prior_plan_sha', 'gate_sha256', 'new_plan_sha')


def _read_transition(path, *, prior_plan_sha, new_plan_sha, gate_sha256, parent_sha256) -> dict[str, Any]:
    """materialize's transition.json: prior_plan_sha (= the gate receipt's plan), gate_sha256, new_plan_sha, and
    optionally parent_sha256. All must match; nothing else is trusted."""
    if path is None:
        raise ValueError('EX-42 automatic gate was scored under another plan and no transition record links it')
    raw = Path(path).resolve(strict=True).read_bytes()
    record = json.loads(raw)
    if not isinstance(record, dict) or any(not isinstance(record.get(key), str) for key in TRANSITION_KEYS):
        raise ValueError('EX-42 transition record lacks prior_plan_sha, gate_sha256 or new_plan_sha')
    if (record['prior_plan_sha'] != prior_plan_sha or record['new_plan_sha'] != new_plan_sha
            or record['gate_sha256'] != gate_sha256
            or record.get('parent_sha256', parent_sha256) != parent_sha256):
        raise ValueError('EX-42 transition record does not chain this gate receipt to this plan')
    return {'path': str(Path(path).resolve()), 'sha256': hashlib.sha256(raw).hexdigest(), **record}


def validate_automatic_stage_launch(
    plan: EX42Plan, approvals_path: str | Path, *, target_stage: str,
    parent_manifest_path: str | Path, gate_receipt_path: str | Path,
    expected_gate_sha256: str, transition_path: str | Path | None = None,
) -> dict[str, Any]:
    """Require an existing bounded cell and pinned predecessor PASS on the real parent.

    The dispatcher must call this before launching and deliver the required notification.
    This function is not a dispatcher and does not bypass the normal launch preflight.
    """
    path = Path(approvals_path).resolve(strict=True)
    if hashlib.sha256(path.read_bytes()).hexdigest() != plan.document['stage_zero']['approval_sha256']:
        raise ValueError('EX-42 automatic approval SHA differs from plan pin')
    if not scoped_automatic_policy(_read_yaml(path).get('automatic_launch_allowed')):
        raise ValueError('EX-42 scoped automatic policy is not enabled')
    validators = authorization_validators(plan)
    if target_stage not in validators:
        raise ValueError('EX-42 automatic target has no supported approval cell')
    cell = _read_yaml(path).get(f"stage_{target_stage.lower()}_authorization", {})
    scope = cell.get("scope", {}) if isinstance(cell, dict) else {}
    proof = validators[target_stage](path, scope.get("parent_sha256") if isinstance(scope, dict) else None)
    if proof.get("entry_gate_adapter_ready") is not True:
        raise ValueError(f"EX-42 {target_stage} stage-specific entry gate adapter is pending")
    parent = plan.verify_parent_manifest(parent_manifest_path, stage_id=target_stage)
    if parent['checkpoint_sha256'] != proof['scope']['parent_sha256']:
        raise ValueError('EX-42 automatic parent differs from approval')
    gate_path = Path(gate_receipt_path).resolve(strict=True)
    raw = gate_path.read_bytes()
    gate_sha = hashlib.sha256(raw).hexdigest()
    if gate_sha != expected_gate_sha256:
        raise ValueError('EX-42 automatic gate receipt SHA differs')
    gate = json.loads(raw)
    source_stage = gate.get('stage_id') if isinstance(gate, dict) else None
    if (not isinstance(gate, dict) or gate.get('judgment') != 'PASS'
            or source_stage not in proof['source_stage_ids']):
        raise ValueError('EX-42 automatic gate must be predecessor PASS under this plan')
    transition = None
    if gate.get('plan_sha256') != plan.sha256:
        # The gate was scored under the plan the predecessor ran with. This plan is a later one published by
        # ex42_stage_materialize; it is accepted only through that tool's transition record, which names the
        # gate's plan, this gate receipt and this plan.
        transition = _read_transition(transition_path, prior_plan_sha=gate.get('plan_sha256'),
                                      new_plan_sha=plan.sha256, gate_sha256=gate_sha,
                                      parent_sha256=parent['checkpoint_sha256'])
    stage = next(row for row in plan.document['stages'] if row['id'] == target_stage)
    iteration = stage['parent']['manifest_local_update']
    manifest = json.loads(Path(parent_manifest_path).read_text(encoding='utf-8-sig'))
    validate_score_pair(expected_iteration=iteration, score=gate, manifest=manifest,
                        checkpoint_exists=True, checkpoint_sha256=parent['checkpoint_sha256'])
    validate_ex42_map_score(gate, ['gt', 'pred', 'off'])
    measurement_name = gate.get('measurement')
    if not isinstance(measurement_name, str) or not measurement_name:
        raise ValueError('EX-42 automatic gate measurement is absent')
    measurement = Path(measurement_name)
    if not measurement.is_absolute():
        measurement = gate_path.parent / measurement
    if (not measurement.is_file()
            or hashlib.sha256(measurement.read_bytes()).hexdigest() != gate.get('measurement_sha256')):
        raise ValueError('EX-42 automatic gate measurement SHA differs')
    return {**proof, 'automatic_launch_authorized': True, 'source_stage_id': source_stage,
            'parent': parent, 'gate_receipt_path': str(gate_path), 'gate_sha256': gate_sha,
            'notification_required': True, 'training_started': False,
            **({'transition': transition} if transition else {})}
