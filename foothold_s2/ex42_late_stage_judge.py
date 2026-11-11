"""E4/E5 consumers: raw task suites plus stage-aware common evidence.

No available common kind consumer means HOLD, even if every paper/direction
trace passes. The optional dependency is read at judgment time so registration
itself cannot masquerade as a successfully measured exit.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import yaml

from foothold_s2.eval.ex42_late_stage_tasks import DATA_ERRORS, read_two_windows
from foothold_s2.eval.ex42_task_cells import sha256
from foothold_s2.ex42_e0_judge import judge as maintenance, load_baseline
from foothold_s2.ex42_stage_judges import StageJudge, aggregate, previous_window, register

MODES = ('eval_gt', 'eval_pred', 'probe_prop_only')


def hold(reason):
    return {'role': 'judge', 'judgement': 'HOLD', 'reason': reason}


def exit_verdict(items):
    required = {'maintenance_current', 'maintenance_previous', 'task_current',
                'task_previous', 'learned_cells', 'exchange_watch'}
    if (not required <= set(items) or not any(k.startswith('kind_') for k in items) or
            any(row.get('role') != 'judge' or row.get('judgement') not in ('PASS', 'HOLD', 'FAIL')
                for row in items.values())):
        raise ValueError('late stage required judge gates missing or demoted to record')
    return aggregate(v['judgement'] for v in items.values())


def common_inputs(ctx, current, prior):
    """Port to the E3 named-kind reader; missing integration is explicit HOLD.

    read_stage_bundle(ctx, current, previous=prior, stage_id=ctx.stage_id) must
    verify actual exposure and recount named-kind forward/flag NPZ. It returns
    items, kind_now, kind_previous, kind_subcells, registered_kind_passes and
    execution_plan (the actual SHA-bound training plan). This extra port is
    recorded in CONTRACT-E4-E5-EXIT-1112 pending the E3 consumer implementation.
    No score payload supplied by the caller can replace the raw reader.
    """
    try:
        module = importlib.import_module('foothold_s2.ex42_e3_judge')
    except ModuleNotFoundError as exc:
        if exc.name != 'foothold_s2.ex42_e3_judge':
            raise
        return None
    reader = getattr(module, 'read_stage_bundle', None)
    if reader is None:
        return None
    return reader(ctx, current, previous=prior, stage_id=ctx.stage_id)


def common_gates(ctx, current, prior, *, baseline, measured):
    """Call b97d60ce APIs only after the raw-kind input contract is satisfied."""
    try:
        source = common_inputs(ctx, current, prior)
        if source is None:
            return {'kind_windows': hold('stage_common_kind_consumer_unavailable'),
                    'learned_cells': hold('stage_common_kind_consumer_unavailable'),
                    'exchange_watch': hold('stage_common_kind_consumer_unavailable')}
        required = {'exposure', 'kind_current', 'kind_previous', 'level_targets'}
        if (not isinstance(source, dict) or set(source.get('items', {})) != required or
                any(v.get('role') != 'judge' or v.get('judgement') not in ('PASS', 'HOLD', 'FAIL')
                    for v in source['items'].values())):
            raise ValueError('common kind raw reader result is incomplete')
        items = {'kind_' + k: v for k, v in source['items'].items()}
        execution = source['execution_plan']
        if (sha256(execution['path']) != execution['sha256'] or
                execution['sha256'] != current.get('execution_plan_sha256')):
            raise ValueError('common kind execution plan SHA differs')
        execution_plan = yaml.safe_load(Path(execution['path']).read_text(encoding='utf-8-sig'))
        approvals = Path(execution['path']).parent / execution_plan['approval_file']
        approval = yaml.safe_load(approvals.read_text(encoding='utf-8-sig'))
        authorization = approval[f'stage_{ctx.stage_id.lower()}_authorization']
        minimum = authorization.get('exit_gate', {}).get('learned_cells_min')
        if authorization.get('approved') is not True or type(minimum) is not int or minimum != 32:
            raise ValueError('stage learned_cells 32 threshold authorization missing')
        from foothold_s2.ex42_learned_cells_evidence import judge_two_boundaries
        from foothold_s2.ex42_exchange_watch import compare
        items['learned_cells'] = judge_two_boundaries(
            ctx.checkpoint, stage_id=ctx.stage_id, plan=execution_plan,
            plan_sha256=execution['sha256'], interval=ctx.plan['evaluation']['interval_updates'],
            min_episodes=minimum, registered_kind_passes=source['registered_kind_passes'])
        items['exchange_watch'] = compare(
            current, prior, measured=measured, baseline=baseline,
            kind_now=source['kind_now'], kind_previous=source['kind_previous'],
            stage_id=ctx.stage_id, kind_score_key='late_kind',
            kind_subcells=tuple(source['kind_subcells']))
        return items
    except (*DATA_ERRORS, ImportError) as exc:
        return {'kind_windows': hold(f'{type(exc).__name__}: {exc}'),
                'learned_cells': hold('common_kind_evidence_invalid'),
                'exchange_watch': hold('common_kind_evidence_invalid')}


class LateKindTwoWindowJudge(StageJudge):
    def __init__(self, stage_id):
        if stage_id not in ('E4', 'E5'):
            raise ValueError('late stage must be E4/E5')
        self.stage_id = stage_id
        self.name = f'kind_two_window_{stage_id.lower()}'

    def judge(self, ctx, score):
        if ctx.stage_id != self.stage_id:
            raise ValueError('late stage adapter/context identity differs')
        baseline = load_baseline(ctx.root, ctx.cfg, ctx.digest)
        baseline['_sha256'] = ctx.cfg['baseline']['sha256']
        measured = ctx.plan['assumptions_pending_lead']['q4_two_window_range']['value']['measured']
        current = maintenance(score, baseline, measured)
        current['stage_id'] = self.stage_id
        try:
            prior = previous_window(ctx)
            prior_maintenance = maintenance(prior, baseline, measured) if prior else None
        except DATA_ERRORS as exc:
            prior = prior_maintenance = None
            prior_error = f'{type(exc).__name__}: {exc}'
        else:
            prior_error = 'previous_boundary_missing'
        items = {'maintenance_current': {'role': 'judge', 'judgement': current['judgement']},
                 'maintenance_previous': ({'role': 'judge', 'judgement': prior_maintenance['judgement']}
                                           if prior_maintenance else hold(prior_error))}
        try:
            map_path = Path(ctx.evaluation) / 'map64/map_modes.json'
            map_row = json.loads(map_path.read_text(encoding='utf-8-sig'))
            if map_row['checkpoint_sha256'] != ctx.checkpoint_sha or map_row['eval_seed'] != ctx.seed:
                raise ValueError('late task map64 checkpoint/seed differs')
            from foothold_s2.eval.ex42_mesh_eval import preflight
            mesh = preflight(Path(map_row['ex42_mesh']['manifest']).parent)
            if mesh['mesh_sha256'] != map_row['ex42_mesh']['mesh_sha256']:
                raise ValueError('late task pinned training mesh differs')
            tasks = read_two_windows(ctx.evaluation, checkpoint=ctx.checkpoint, previous=prior,
                stage_id=self.stage_id, plan=ctx.plan, plan_sha256=ctx.digest(ctx.plan_path),
                seed=ctx.seed, training_mesh_sha256=mesh['mesh_sha256'])
            current['late_kind'] = {'mesh_sha256': mesh['mesh_sha256']}
        except DATA_ERRORS as exc:
            tasks = {k: hold(f'{type(exc).__name__}: {exc}') for k in ('current', 'previous')}
        items.update({'task_' + which: row for which, row in tasks.items()})
        items.update(common_gates(ctx, current, prior, baseline=baseline, measured=measured))
        verdict = exit_verdict(items)
        current.update(judgement=verdict, reason=f'{self.stage_id}: raw tasks and common two-window evidence',
            late_evidence={'evaluation': str(Path(ctx.evaluation).resolve()),
                           'plan_file': str(Path(ctx.plan_path).resolve()),
                           'config_file': str(Path(ctx.cfg_path).resolve())},
            stage_exit={'adapter': self.name, 'judgement': verdict, 'windows': 2, 'items': items})
        return current

    def verify(self, score, judgment, expected, plan=None):
        """Re-run every exit consumer from pinned files, including the prior NPZ."""
        from foothold_s2.ex42_stage_judges import _map39_cell_check
        if plan is None or score.get('stage_id') != self.stage_id:
            raise ValueError('late stage verification stage/plan missing')
        if _map39_cell_check(score, judgment, MODES) != expected:
            raise ValueError('late stage maintenance aggregate differs')
        evidence = score.get('late_evidence') or {}
        plan_path = Path(evidence.get('plan_file', ''))
        config_path = Path(evidence.get('config_file', ''))
        if (sha256(plan_path) != score['maintenance_source_sha256'] or
                sha256(config_path) != score['score_config_sha256'] or
                yaml.safe_load(plan_path.read_text(encoding='utf-8-sig')) != plan):
            raise ValueError('late stage pinned context differs')
        cp = Path(score['checkpoint'])
        if sha256(cp) != score['checkpoint_sha256']:
            raise ValueError('late stage checkpoint changed')
        ctx = SimpleNamespace(stage_id=self.stage_id, checkpoint=cp, checkpoint_sha=sha256(cp),
            evaluation=Path(evidence['evaluation']), root=Path(__file__).resolve().parents[1],
            cfg=json.loads(config_path.read_text(encoding='utf-8-sig')), cfg_path=config_path,
            digest=sha256, plan=plan, plan_path=plan_path, seed=score['conditions']['eval_seed'])
        recounted = self.judge(ctx, score)
        if (recounted['judgement'] != judgment or recounted['stage_exit'] != score.get('stage_exit') or
                recounted['stage_exit']['items']['maintenance_current']['judgement'] != expected):
            raise ValueError('late stage exit differs from raw recomputation')
        return {'stage_exit': recounted['stage_exit']}


register(LateKindTwoWindowJudge('E4'))
register(LateKindTwoWindowJudge('E5'))
