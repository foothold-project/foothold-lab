"""CPU readback of a completed W09 + W08 chain before E1F plan publication."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re


def validate_flag_chain(path, *, template, checkpoint, baseline_ref, mesh_ref, evidence_dir, gate_path):
    # Lazy import: ordinary materialize does not depend on the optional flag evaluator.
    from foothold_s2.eval.ex42_flag_cells import contract, read_evidence, summarize_repeats
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_stage_materialize import _json, _ref, _checked_ref, _canonical, digest

    path = Path(path).resolve(strict=True)
    chain_pin = _ref(path)
    chain = _json(path)
    if chain.get('format') != 'foothold-ex42-w09-w08-chain/1' or chain.get('state') != 'complete':
        raise ValueError('W09/W08 chain is not complete')
    if chain.get('checkpoint_sha256') != digest(checkpoint) or Path(chain.get('checkpoint', '')).resolve() != Path(checkpoint).resolve():
        raise ValueError('W09/W08 parent checkpoint differs from predecessor exit')
    gate_ref = chain.get('e1_gate')
    if _checked_ref(gate_ref, path.parent) != Path(gate_path).resolve():
        raise ValueError('W09/W08 E1 gate differs from materialize predecessor gate')
    gate = _json(gate_path)
    if (gate_ref.get('measurement') != gate.get('measurement')
            or gate_ref.get('measurement_sha256') != gate.get('measurement_sha256')):
        raise ValueError('W09/W08 E1 measurement identity differs')
    flag_plan = EX42Plan.load(_checked_ref({'path': chain.get('plan'), 'sha256': chain.get('plan_sha256')}, path.parent))
    flag_settings, target_settings = deepcopy(contract(flag_plan.document)), deepcopy(contract(template.document))
    for settings in (flag_settings, target_settings):
        for pin in ('calibration', 'calibration_sha256', 'flag_baseline'):
            settings.pop(pin, None)
    if _canonical(flag_settings) != _canonical(target_settings):
        raise ValueError('W09/W08 flag evaluation contract differs from target template')
    mesh_sha = chain.get('mesh_sha256')
    if not isinstance(mesh_sha, str) or re.fullmatch('[0-9a-f]{64}', mesh_sha) is None:
        raise ValueError('W09/W08 mesh SHA is missing')
    mesh = _checked_ref(mesh_ref, evidence_dir)
    mesh_dir = Path(chain.get('mesh_dir', '')).resolve(strict=True)
    manifest_path = mesh_dir / 'mesh_manifest.json'
    manifest = _json(manifest_path)
    if (mesh.resolve() != (mesh_dir / 'terrain_mesh.npz').resolve()
            or manifest.get('format') != 'foothold-ex42-combined-mesh/1'
            or manifest.get('seed') != 42 or manifest.get('mesh_sha256') != mesh_sha
            or manifest.get('mesh_file_sha256') not in (None, digest(mesh))):
        raise ValueError('W09/W08 mesh differs from the parent-exit mesh evidence')
    baseline_path = _checked_ref(chain.get('w09_baseline'), path.parent)
    if baseline_path != _checked_ref(baseline_ref, evidence_dir):
        raise ValueError('W09 baseline differs from materialize evidence binding')
    calibration_path = _checked_ref(chain.get('w08_calibration'), path.parent)
    rounds = chain.get('rounds')
    seeds = [42, *flag_settings['repeat_seeds']]
    if (not isinstance(rounds, list) or len(rounds) != 6
            or [row.get('seed') for row in rounds] != seeds):
        raise ValueError('W09/W08 requires six ordered rounds, with five calibration repeats')
    roots = [Path(row['root']).resolve(strict=True) for row in rounds]
    if len(set(roots)) != 6:
        raise ValueError('W09/W08 repeats reuse an output directory')
    artifacts = {'flag_calibration': _ref(calibration_path), 'flag_baseline': _ref(baseline_path),
                 'flag_evaluation_plan': {'path':str(flag_plan.path), 'sha256':flag_plan.sha256},
                 'flag_chain_receipt': chain_pin, 'flag_mesh_manifest': _ref(manifest_path)}
    for i, (root, seed) in enumerate(zip(roots, seeds)):
        receipt_path = root / 'round_receipt.json'
        receipt = _json(receipt_path)
        if (receipt.get('format') != 'foothold-ex42-flag-round/1' or receipt.get('state') != 'complete'
                or receipt.get('failures') != {} or receipt.get('seed') != seed
                or receipt.get('checkpoint_sha256') != chain['checkpoint_sha256']
                or receipt.get('plan_sha256') != flag_plan.sha256 or receipt.get('mesh_sha256') != mesh_sha
                or set(receipt.get('steps', {})) != {'flag_one', 'flag_four'}
                or any(v.get('state') != 'done' or type(v.get('rc')) is not int or v['rc'] != 0
                       for v in receipt['steps'].values())):
            raise ValueError(f'W09/W08 round {i} is incomplete or differs from chain identity')
        artifacts[f'flag_round_{i}'] = _ref(receipt_path)
        for count in ('flag_one', 'flag_four'):
            child_path = root / 'flag_cells' / count / 'flag_cells.json'
            child = _json(child_path)
            if child.get('mesh_sha256') != mesh_sha:
                raise ValueError(f'W09/W08 child {i}/{count} mesh differs')
            artifacts[f'flag_child_{i}_{count}'] = _ref(child_path)
            for case, raw in child.get('cases', {}).items():
                for kind in ('raw', 'trace'):
                    ref={'path':raw.get(kind+'_file'), 'sha256':raw.get(kind+'_sha256')}
                    checked=_checked_ref(ref, child_path.parent)
                    artifacts[f'flag_{i}_{case}_{kind}']={'path':str(checked), 'sha256':ref['sha256']}
    cases, receipts = {}, {}
    for count in ('flag_one', 'flag_four'):
        folder = roots[0] / 'flag_cells' / count
        cases.update(read_evidence(folder, plan=flag_plan.document, plan_sha256=flag_plan.sha256,
                                  checkpoint_sha256=chain['checkpoint_sha256'], seed=42, count=count))
        receipts[count] = _ref(folder / 'flag_cells.json')
    expected_baseline = dict(format='foothold-ex42-w09-flag-baseline/1', state='measured',
        checkpoint_sha256=chain['checkpoint_sha256'], plan_sha256=flag_plan.sha256,
        mesh_sha256=mesh_sha, seed=42, receipts=receipts, judge_cells=cases)
    if _canonical(_json(baseline_path)) != _canonical(expected_baseline):
        raise ValueError('W09 baseline differs from its raw traces')
    calibration = summarize_repeats([root / 'flag_cells' for root in roots[1:]],
        plan=flag_plan.document, plan_sha256=flag_plan.sha256, checkpoint_sha256=chain['checkpoint_sha256'])
    if _canonical(_json(calibration_path)) != _canonical(calibration):
        raise ValueError('W08 calibration differs from its five raw repeats')
    return artifacts
