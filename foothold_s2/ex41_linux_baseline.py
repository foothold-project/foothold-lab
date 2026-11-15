"""Linux baseline: the EX-41 periodic P1 evaluation bundle + score, on a chosen GPU.

The Windows score_6000 was made by `ex41_eval_once --scope periodic` followed by
`ex41_score_watch.collect(..., periodic_w78_path=..., include_auxiliary=False)`.
This module runs exactly those two steps for one checkpoint. Differences kept explicit:
  - the device is chosen by the caller (the EX-41 role says cuda:1; the baseline spreads two
    checkpoints over cuda:0 and cuda:1), written into a copy of the experiment definition;
  - the Windows idle/priority marker gate (tasklist based) is not used; the launcher script
    starts each checkpoint on its own idle card;
  - no training metrics file (w86) is given, so that score component stays unavailable.
Nothing here edits an existing module, so Windows behaviour is unchanged.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

from foothold_s2 import ex41_eval_once as eo
from foothold_s2.curriculum.continuous import load_plan
from foothold_s2.ex40_score import config, sha256
from foothold_s2.ex40_score_watch import _atomic
from foothold_s2.experiment_registry import operational_definition

STAGE = 'T0_prime'
SCOPE = 'periodic'
DEVICES = ('cuda:0', 'cuda:1')


def baseline_definition(device):
    if device not in DEVICES:
        raise ValueError(f'device must be one of {DEVICES}: {device}')
    definition = copy.deepcopy(operational_definition('EX-41'))
    definition['devices'].update(evaluation=device, w78=device, video=device)
    return definition


def phase_commands(checkpoint, out_root, device, *, table=eo.DEFAULT_TABLE, eval_config=eo.DEFAULT_CONFIG):
    plan = load_plan(table, arm='B')
    return eo.commands(checkpoint, Path(out_root) / 'evaluation', config(eval_config), scope=SCOPE,
                       push_baseline=plan.fixed_schedule['push_baseline'],
                       devices=baseline_definition(device))


def run(checkpoint, out_root, device, expected_sha256, *, table=eo.DEFAULT_TABLE, eval_config=eo.DEFAULT_CONFIG):
    from foothold_s2.ex41_score_watch import collect
    checkpoint, out_root = Path(checkpoint).resolve(strict=True), Path(out_root).resolve()
    if sha256(checkpoint) != expected_sha256:
        raise ValueError(f'checkpoint sha256 differs from {expected_sha256[:8]}')
    if out_root.exists():
        raise ValueError(f'output root already exists (use a new one): {out_root}')
    out_root.mkdir(parents=True)
    bundle = out_root / 'evaluation'
    receipt = eo._evaluate_bundle(checkpoint, bundle, table=table, eval_config=eval_config, scope=SCOPE,
                                  definition=baseline_definition(device), device=device)
    if receipt.get('state') != 'done':
        print(json.dumps({'state': receipt.get('state'), 'reason': receipt.get('reason'), 'rc': receipt.get('rc')}))
        return 5
    plan = load_plan(table, arm='B')
    score = collect(checkpoint, STAGE, bundle, plan, eval_config,
                    periodic_w78_path=bundle / 'w78_v2_sides/terrain_skill_v2.json',
                    include_auxiliary=False)
    score['linux_baseline'] = {'device': device, 'stage_label': STAGE, 'plan': 'EX-41 fixed5000 arm B',
                               'priority_gate': 'not used', 'training_metrics': 'not given'}
    _atomic(out_root / 'score.json', score)
    print(json.dumps({'state': score['evaluation_state'], 'judgement': score.get('judgement_state'),
                      'maintenance_pass': score['maintenance_pass'], 'score': str(out_root / 'score.json')}))
    return 0 if score['evaluation_state'] == 'complete' else 5


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--expected-sha256', required=True)
    p.add_argument('--out-root', type=Path, required=True)
    p.add_argument('--device', choices=DEVICES, required=True)
    p.add_argument('--execute', action='store_true')
    a = p.parse_args(argv)
    if not a.execute:
        print(json.dumps({'state': 'dry', 'commands': phase_commands(a.checkpoint, a.out_root, a.device)}))
        return 0
    return run(a.checkpoint, a.out_root, a.device, a.expected_sha256)


if __name__ == '__main__':
    raise SystemExit(main())
