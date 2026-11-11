"""Bounded automatic-stage authorization only; never starts training or sends messages."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from foothold_s2.curriculum.ex42_prep import (
    EX42Plan, STAGE_ZERO_ID, _read_yaml, scoped_automatic_policy,
    validate_stage_e0_authorization, validate_stage_e1_authorization,
    validate_stage_e1f_authorization, validate_stage_e2_authorization,
)
from foothold_s2.ex42_gate_checks import validate_ex42_map_score, validate_score_pair


def validate_automatic_stage_launch(
    plan: EX42Plan, approvals_path: str | Path, *, target_stage: str,
    parent_manifest_path: str | Path, gate_receipt_path: str | Path,
    expected_gate_sha256: str,
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
    validators = {'E0': validate_stage_e0_authorization, 'E1': validate_stage_e1_authorization,
                  'E1F': validate_stage_e1f_authorization, 'E2': validate_stage_e2_authorization}
    if target_stage not in validators:
        raise ValueError('EX-42 automatic target has no supported approval cell')
    if target_stage in ("E1F", "E2"):
        cell = _read_yaml(path).get(f"stage_{target_stage.lower()}_authorization", {})
        proof = validators[target_stage](plan, path, cell.get("scope", {}).get("parent_sha256"))
        # Never treat the generic 26-cell PASS as D44/flag or sparse-entry proof.
        if proof.get("entry_gate_adapter_ready") is not True:
            raise ValueError(f"EX-42 {target_stage} stage-specific entry gate adapter is pending")
    parent = plan.verify_parent_manifest(parent_manifest_path, stage_id=target_stage)
    proof = validators[target_stage](plan, path, parent['checkpoint_sha256'])
    gate_path = Path(gate_receipt_path).resolve(strict=True)
    raw = gate_path.read_bytes()
    gate_sha = hashlib.sha256(raw).hexdigest()
    if gate_sha != expected_gate_sha256:
        raise ValueError('EX-42 automatic gate receipt SHA differs')
    gate = json.loads(raw)
    source_stage = {'E0': STAGE_ZERO_ID, 'E1': 'E0'}[target_stage]
    if (not isinstance(gate, dict) or gate.get('judgment') != 'PASS'
            or gate.get('stage_id') != source_stage or gate.get('plan_sha256') != plan.sha256):
        raise ValueError('EX-42 automatic gate must be predecessor PASS under this plan')
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
            'notification_required': True, 'training_started': False}
