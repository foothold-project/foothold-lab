"""Materialize inputs from a real predecessor PASS; never manufacture missing measurements.

Common producers: evaluation mesh receipt, inherited W08 calibration and W09
baseline, actual predecessor stage ID. M0-M3, opening-order logs, Q12 and M branch
records require their own pinned producers through the optional bindings manifest.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.ex42_stage_materialize import (_checked_ref, _json, _ref, _row,
                                               validate_source_exit, EVIDENCE_FORMAT, digest)


def validate_m0_m3(path, template):
    """Consume the measurement producer's verdict and pins; SHA alone is not PASS."""
    from foothold_s2.ex42_stage_mesh import pinned_stage_mesh
    path = Path(path)
    report = _json(path)
    if (report.get('format') != 'foothold-ex42-m0-m3/1' or report.get('stage_id') != 'E2'
            or report.get('status') != 'PASS'):
        raise ValueError('M0~M3 measurement receipt is not E2 PASS')
    checks = report.get('checks')
    if not isinstance(checks, dict) or set(checks) != {'M0', 'M1', 'M2', 'M3'}:
        raise ValueError('M0~M3 measurement checks missing')
    for key, item in checks.items():
        if (not isinstance(item, dict) or item.get('status') != 'PASS'
                or not isinstance(item.get('evidence'), list) or not item['evidence']):
            raise ValueError(f'M0~M3 {key} has no measured PASS evidence')
        for ref in item['evidence']:
            _checked_ref(ref, path.parent)
    pinned = pinned_stage_mesh(template.document, 'E2')
    mesh = report.get('mesh') or {}
    if not pinned or mesh.get('geometry_sha256') != pinned['geometry_sha256']:
        raise ValueError('M0~M3 mesh geometry differs from E2 profile')
    files = mesh.get('files') or {}
    for name in ('terrain_mesh.npz', 'mesh_manifest.json'):
        measured = _checked_ref(files.get(name), path.parent)
        if digest(measured) != pinned['files'][name]['sha256']:
            raise ValueError('M0~M3 mesh file differs from E2 profile')
    try:
        from foothold_s2.tools.ex42_m0_m3 import verify_receipt
    except ImportError as exc:
        raise ValueError('M0~M3 measurement verifier unavailable') from exc
    rebuilt = verify_receipt(path, digest(path), mesh_dir=pinned['directory'])
    if rebuilt.get('status') != 'PASS':
        raise ValueError('M0~M3 raw measurement verification did not PASS')


KIND_ORDER_KEY = 'prerequisites.kind_opening_order_recorded'
KIND_ORDER_FORMAT = 'foothold-ex42-kind-opening-order/1'


def kind_opening_order_file(row, template, target, output_dir):
    """(text, path, ref): the fingerprint file of the kind opening order the target row registered in the plan (`terrain.k_ladder.order`).

    What it says: the order in which the kinds open was written down in the plan BEFORE any result of the stage; `order_sha256` is the
    sha256 of that order in sorted-key compact JSON. What it does not say: which kinds actually opened. That is a different record, the
    exposure receipt's `ladder_outcomes` (ex42_exposure_receipt.py), written while the stage runs. Nothing is measured here."""
    order = ((row.get('terrain') or {}).get('k_ladder') or {}).get('order')
    if not isinstance(order, list) or not order:
        raise ValueError(f'{target} row registers no kind opening order (terrain.k_ladder.order)')
    order_sha = hashlib.sha256(json.dumps(order, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                                          allow_nan=False).encode('utf-8')).hexdigest()
    body = {'format': KIND_ORDER_FORMAT, 'target_stage': target, 'template_plan_sha256': template.sha256,
            'order': order, 'order_sha256': order_sha}
    text = json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'
    path = Path(output_dir).resolve() / f'kind_opening_order_{target}.json'
    ref = {'path': str(path), 'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(), 'pointer': 'order_sha256'}
    return text, path, ref


def produce(*, template_path, source_path, target, gate_path, manifest_path, output_dir, bindings_path=None):
    from foothold_s2.ex42_stage_handoff import measured_budget
    template, source = EX42Plan.load(template_path), EX42Plan.load(source_path)
    gate_path = Path(gate_path).resolve(strict=True)
    gate = _json(gate_path)
    first_window = gate.get('state') == 'first_window_handoff'      # E1F m250 on the team lead's recorded approval (ex42_e1f_first_window); never written as a PASS
    if first_window:
        if gate.get('judgment') != 'FIRST_WINDOW_HANDOFF' or gate.get('plan_sha256') != source.sha256 or gate.get('stage_id') != 'E1F':
            raise ValueError('first window handoff receipt does not belong to this E1F plan')
    elif gate.get('state') != 'complete' or gate.get('judgment') != 'PASS' or gate.get('plan_sha256') != source.sha256:
        raise ValueError('stage evidence requires actual predecessor PASS under its source plan')
    row = _row(template, target)
    contract = row['authorization_contract']
    if gate.get('stage_id') not in contract['source_stage_ids']:
        raise ValueError('stage evidence predecessor does not match target')
    budget = measured_budget(template.path, source.path, manifest_path, gate_path)
    policy = source
    if gate.get('evaluation_plan'):
        policy = EX42Plan.load(_checked_ref(gate['evaluation_plan'], gate_path.parent))
    if first_window:
        from foothold_s2.ex42_e1f_first_window import read_first_window_handoff
        read_first_window_handoff(gate_path, policy_plan=policy)      # recounts the raw flag cells, the maintenance table and the ledger line
    else:
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
            if key == 'prerequisites.m0_m3_receipt_sha256':
                validate_m0_m3(path, template)
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
                or manifest.get('mesh_file_sha256') not in (None, digest(npz))):      # the E0 evaluation mesh manifest predates the field (same tolerance as ex42_flag_publication); the geometry sha above still has to match the receipt
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
    kind_order = None
    if KIND_ORDER_KEY in paths and KIND_ORDER_KEY not in bindings:      # a bindings manifest that names it wins
        kind_order = kind_opening_order_file(row, template, target, output_dir)
        bindings[KIND_ORDER_KEY] = kind_order[2]
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
    if first_window:
        document['predecessor_exit'] = {'mode': 'first_window_handoff', 'receipt_sha256': digest(gate_path),
                                        'ledger_line_sha256': gate['lead_approval']['line_sha256'],
                                        'hold_items': gate['hold_items']}
    axes = row.get('boundary_axes') or []
    if len(axes) == 1:
        document['boundary_axis'] = axes[0]
    elif (row.get('boundary') or {}).get('entry_axis') in axes:
        # Multiple axes: only the entry axis the plan registered before any result (row boundary.entry_axis, lead 2026-11-16 11:09).
        # A gate must not choose one after observing performance; no registered entry axis inside the row's axes = none is written
        # and materialize refuses ("multi-axis boundary needs a declared allowed axis").
        document['boundary_axis'] = row['boundary']['entry_axis']
    output = Path(output_dir) / f'{target}_{digest(gate_path)[:12]}.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    if kind_order is not None:
        text_order, path_order, _ = kind_order
        if path_order.exists():
            if path_order.read_text(encoding='utf-8') != text_order:
                raise ValueError('existing kind opening order file differs; never overwrite')
        else:
            with path_order.open('x', encoding='utf-8') as stream:
                stream.write(text_order)
    text = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'
    if output.exists():
        if output.read_text(encoding='utf-8') != text:
            raise ValueError('existing generated evidence differs; never overwrite')
    else:
        with output.open('x', encoding='utf-8') as stream:
            stream.write(text)
    return output
