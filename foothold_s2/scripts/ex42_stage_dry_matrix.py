"""Read the real plan through each stage's validator, materializer and CPU launcher.

Absent predecessor evidence remains absent. This tool never fills measurements with
synthetic PASS, never starts Kit, and records the first refusal of each independent path.
"""
import argparse
import os
from pathlib import Path
import sys

from foothold_s2.scripts.ex42_remeasure import read, ref, save

STAGES = ('E1F', 'E2', 'E3', 'E4', 'E5', 'M', 'E6a', 'E6b')


def probe(plan_path, approvals, output, *, evidence_root, source_plan=None, env=None):
    from foothold_s2.curriculum.ex42_prep import EX42Plan, authorization_validators
    from foothold_s2.ex42_stage_materialize import materialize
    from foothold_s2.ex42_stage_judges import adapter_for
    from foothold_s2.scripts.ex42_stage_launcher import build
    plan = EX42Plan.load(plan_path)
    validators = authorization_validators(plan)
    rows = []
    output, evidence_root = Path(output), Path(evidence_root)
    output.mkdir(parents=True, exist_ok=False)
    for stage in STAGES:
        row = next(r for r in plan.document['stages'] if r['id'] == stage)
        inputs_path = evidence_root / f'{stage}-inputs.json'
        supplied = read(inputs_path) if inputs_path.is_file() else {}
        source = supplied.get('source_plan', source_plan if stage == 'E1F' and source_plan else str(plan.path))
        missing = evidence_root / stage / 'NOT_YET_PRODUCED'
        parent = supplied.get('parent_manifest', str(missing / 'manifest.json'))
        gate = supplied.get('gate_receipt', str(missing / 'p1_score.json'))
        evidence = supplied.get('evidence', str(missing / 'evidence.json'))
        item = {'stage': stage, 'enabled': row.get('enabled'), 'parent': row.get('parent'),
                'inputs_supplied': bool(supplied), 'actual_measurements_supplied': bool(supplied),
                'entry_adapter': row.get('authorization_contract', {}).get('entry_gate_adapter'), 'checks': {}}
        for name, operation in (
                ('validator', lambda: validators[stage](approvals, (row.get('parent') or {}).get('sha256'))),
                ('exit_adapter', lambda: adapter_for(plan.document, stage))):
            try:
                result = operation()
                item['checks'][name] = {'state': 'PASS' if result is not None else 'MISSING',
                                        'detail': getattr(result, 'name', None)}
            except (ValueError, KeyError, OSError, TypeError) as exc:
                item['checks'][name] = {'state': 'REFUSED', 'reason': str(exc)}
        try:
            result = materialize(plan=plan.path, source_plan=source, approvals=approvals, target=stage,
                        parent_manifest=parent, gate_receipt=gate, evidence=evidence,
                        budget_limit=plan.document['training_budget']['maximum_updates'],
                        budget_used=supplied.get('budget_used', 0),
                        budget_basis=plan.document['training_budget']['basis'],
                        out=output / f'{stage}-materialized', flag_chain=supplied.get('flag_chain'))
            item['checks']['materialize'] = {'state': 'PASS', 'result': result}
        except (ValueError, KeyError, OSError, TypeError) as exc:
            result = None
            item['checks']['materialize'] = {'state': 'REFUSED', 'reason': str(exc)}
        launch_env = dict(env or os.environ, EX42_AUTO_ACTION='next_stage', EX42_AUTO_TARGET_STAGE=stage,
                          EX42_AUTO_PLAN=str(plan.path), EX42_AUTO_APPROVALS=str(approvals),
                          EX42_AUTO_PARENT_MANIFEST=str(parent), ISAAC311_PYTHON=sys.executable)
        if result:
            launch_env.update(result['launch_env'])
        try:
            argv, child, summary = build(launch_env, dry_run=True)
            # No torchrun or Kit: the caller can inspect the exact CPU preflight argv.
            # A real first-update check additionally needs an actual parent model.
            item['checks']['launcher'] = {'state': 'ARGV_ONLY', 'argv': argv, 'summary': summary,
                                          'cuda_visible_devices': child.get('CUDA_VISIBLE_DEVICES')}
        except (ValueError, KeyError, OSError, TypeError) as exc:
            item['checks']['launcher'] = {'state': 'REFUSED', 'reason': str(exc)}
        rows.append(item)
    result = {'plan': ref(plan_path), 'approvals': ref(approvals), 'rows': rows,
              'training_started': False, 'scope': 'CPU path calls; future measured artifacts are not fabricated'}
    save(output / 'dry-matrix.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('plan', 'approvals', 'output', 'evidence-root'):
        parser.add_argument('--' + arg, type=Path, required=True)
    parser.add_argument('--source-plan', type=Path)
    args = parser.parse_args(argv)
    result = probe(args.plan, args.approvals, args.output, evidence_root=args.evidence_root,
                   source_plan=str(args.source_plan) if args.source_plan else None)
    for row in result['rows']:
        print(row['stage'], ', '.join(f"{name}={check['state']}:{check.get('reason', '')}" for name, check in row['checks'].items()))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
