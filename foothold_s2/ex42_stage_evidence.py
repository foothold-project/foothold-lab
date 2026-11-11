"""Materialize inputs from a real predecessor PASS; never manufacture missing measurements.

Common producers: evaluation mesh receipt, inherited W08 calibration and W09
baseline, actual predecessor stage ID. M0-M3, opening-order logs, Q12 and M branch
records require their own pinned producers through the optional bindings manifest.
"""
from __future__ import annotations

import json
from pathlib import Path

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.ex42_stage_materialize import (_checked_ref, _json, _ref, _row,
                                               validate_source_exit, EVIDENCE_FORMAT, digest)


def produce(*, template_path, source_path, target, gate_path, manifest_path, output_dir, bindings_path=None):
    from foothold_s2.ex42_stage_handoff import measured_budget
    template, source = EX42Plan.load(template_path), EX42Plan.load(source_path)
    gate_path = Path(gate_path).resolve(strict=True)
    gate = _json(gate_path)
    if gate.get('state') != 'complete' or gate.get('judgment') != 'PASS' or gate.get('plan_sha256') != source.sha256:
        raise ValueError('stage evidence requires actual predecessor PASS under its source plan')
    row = _row(template, target)
    contract = row['authorization_contract']
    if gate.get('stage_id') not in contract['source_stage_ids']:
        raise ValueError('stage evidence predecessor does not match target')
    budget = measured_budget(template.path, source.path, manifest_path, gate_path)
    policy = source
    if gate.get('evaluation_plan'):
        policy = EX42Plan.load(_checked_ref(gate['evaluation_plan'], gate_path.parent))
    validate_source_exit(source, gate, gate_path, evaluation_plan=policy)
    bindings = {}
    paths = set(contract['required_sha256_paths']) | set(contract['required_string_paths'])
    paths |= set(contract['required_boolean_paths']) - {'critic_mirror'}
    if bindings_path:
        declaration = _json(bindings_path)
        for key, value in declaration.get(target, {}).items():
            if key not in paths:
                raise ValueError(f'unregistered binding: {key}')
            path = _checked_ref(value, Path(bindings_path).parent)
            bindings[key] = dict(value, path=str(path))
    mesh_key = 'prerequisites.predecessor_exit.evaluation_mesh_sha256'
    if mesh_key in paths:
        receipt = _json(gate_path.parent / 'eval_receipt.json')
        if receipt.get('checkpoint_sha256') != gate['checkpoint_sha256'] or receipt.get('state') not in ('running', 'done'):
            raise ValueError('mesh producer belongs to a different checkpoint or failed evaluation')
        mesh = receipt.get('ex42_mesh') or {}
        npz = Path(mesh.get('mesh_npz', '')).resolve(strict=True)
        manifest = _json(mesh.get('manifest', ''))
        if (manifest.get('mesh_sha256') != mesh.get('mesh_sha256')
                or manifest.get('mesh_file_sha256') != digest(npz)):
            raise ValueError('mesh producer SHA differs')
        bindings[mesh_key] = _ref(npz)
    flags = source.document.get('evaluation', {}).get('flag_cells') or {}
    for key, name in (('prerequisites.calibration_sha256', 'calibration'),
                      ('prerequisites.flag_baseline.sha256', 'flag_baseline')):
        if key in paths:
            pin = flags.get(name)
            if pin:
                bindings[key] = _ref(_checked_ref(pin, source.path.parent))
    stage_key = 'prerequisites.predecessor_exit.stage_id'
    if stage_key in paths:
        bindings[stage_key] = dict(_ref(gate_path), pointer='stage_id')
    # materialize derives the matching path from its baseline SHA reference.
    automatically_set = {'critic_mirror'}
    if 'prerequisites.flag_baseline.sha256' in bindings:
        automatically_set.add('prerequisites.flag_baseline.path')
    fixed = contract.get('required_values') or {}
    missing = []
    for key in paths - set(bindings) - automatically_set:
        # Only a registered fixed value is already determined without a new measured producer.
        if key not in fixed:
            missing.append(key)
    if missing:
        raise ValueError('missing measured producers: ' + ', '.join(sorted(missing)))
    document = {'format': EVIDENCE_FORMAT, 'target_stage': target, 'source_stage': gate['stage_id'],
                'source_plan_sha256': source.sha256, 'gate_sha256': digest(gate_path),
                'checkpoint_sha256': gate['checkpoint_sha256'], 'bindings': bindings, 'budget_observed': budget}
    if policy.sha256 != source.sha256:
        document['evaluation_plan'] = _ref(policy.path)
    axes = row.get('boundary_axes') or []
    if len(axes) == 1:
        document['boundary_axis'] = axes[0]
    # Multiple axes need a pre-registered entry axis. A gate must not choose one
    # after observing performance. The planner's table is wired separately.
    output = Path(output_dir) / f'{target}_{digest(gate_path)[:12]}.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'
    if output.exists():
        if output.read_text(encoding='utf-8') != text:
            raise ValueError('existing generated evidence differs; never overwrite')
    else:
        with output.open('x', encoding='utf-8') as stream:
            stream.write(text)
    return output
