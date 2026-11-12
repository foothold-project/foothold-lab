"""E4/E5 consumers: raw task suites plus stage-aware common evidence.

No available common kind consumer means HOLD, even if every paper/direction
trace passes. The optional dependency is read at judgment time so registration
itself cannot masquerade as a successfully measured exit.
"""
from __future__ import annotations

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
    """Recount the stage's opened named kinds from raw NPZ (current and previous window) with the E3 common readers.

    Nothing the caller put in a score can replace the raw reader: exposure comes from the training receipt, each
    representative cell from its forward and flag traces. Returns the four gate items plus the per-cell bundles.
    """
    from foothold_s2.ex42_e3_judge import _mesh
    from foothold_s2.eval import ex42_late_stage_kinds as kinds

    stage = ctx.stage_id
    evaluation = Path(ctx.evaluation)
    mesh = _mesh(current, evaluation)
    now = kinds.recount(current, plan=ctx.plan, evaluation=evaluation, mesh=mesh, stage_id=stage)
    old = None
    if prior is not None:
        prior_folder = (prior.get('late_kind') or {}).get('evaluation')
        if not prior_folder:
            raise ValueError('previous boundary has no late kind evidence folder')
        prior_evaluation = Path(prior_folder).parent
        prior_mesh = _mesh(prior, prior_evaluation)
        if prior_mesh['mesh_sha256'] != mesh['mesh_sha256']:
            raise ValueError('late stage prior and current evaluation mesh differ')
        old = kinds.recount(prior, plan=ctx.plan, evaluation=prior_evaluation, mesh=prior_mesh, stage_id=stage)
    current['late_kind'] = {**(current.get('late_kind') or {}), 'mesh_sha256': mesh['mesh_sha256'],
                            'evaluation': now['evaluation']}
    inventory = now.get('inventory') or {}
    exposure = ({'role': 'judge', 'judgement': 'PASS'} if now.get('exposure_found') else
                hold(now.get('reason') or 'stage exposure receipt absent'))
    targets = (hold(now.get('reason') or 'stage kind targets not evaluated') if not inventory else
               hold('level target missing') if inventory['missing_targets'] else
               {'role': 'judge', 'judgement': 'PASS'})
    if inventory:
        targets['missing'] = inventory['missing_targets']
    items = {'exposure': exposure, 'level_targets': targets,
             'kind_current': {'role': 'judge', 'judgement': now['judgement']},
             'kind_previous': ({'role': 'judge', 'judgement': old['judgement']} if old else hold('previous_boundary_missing'))}
    cells_now, cells_old = now.get('cells') or {}, (old or {}).get('cells') or {}
    if cells_now and cells_old and set(cells_now) != set(cells_old):
        items['kind_previous'] = hold('late kind cell set differs between windows')
    return {'items': items, 'cells_now': cells_now, 'cells_previous': cells_old,
            'registered_kind_passes': kinds.passed_kinds(old),
            'learned_cells_min': kinds.spec_for(ctx.plan, stage)['learned_cells_min']}


def common_gates(ctx, current, prior, *, baseline, measured):
    """Call the shared learned-cells and exchange-watch APIs only once the raw kind input contract is satisfied."""
    try:
        source = common_inputs(ctx, current, prior)
        required = {'exposure', 'kind_current', 'kind_previous', 'level_targets'}
        if (not isinstance(source, dict) or set(source.get('items', {})) != required or
                any(v.get('role') != 'judge' or v.get('judgement') not in ('PASS', 'HOLD', 'FAIL')
                    for v in source['items'].values())):
            raise ValueError('common kind raw reader result is incomplete')
        items = {'kind_' + k: v for k, v in source['items'].items()}
        plan_sha = current.get('execution_plan_sha256')
        if not isinstance(plan_sha, str) or not plan_sha:
            raise ValueError('score lacks the pinned execution plan SHA')
        minimum = source['learned_cells_min']
        if type(minimum) is not int or minimum != 32:
            raise ValueError('stage learned_cells 32 threshold missing')
        from foothold_s2.ex42_learned_cells_evidence import judge_two_boundaries
        from foothold_s2.ex42_exchange_watch import compare
        items['learned_cells'] = judge_two_boundaries(
            ctx.checkpoint, stage_id=ctx.stage_id, plan=ctx.plan, plan_sha256=plan_sha,
            interval=ctx.plan['evaluation']['interval_updates'],
            min_episodes=minimum, registered_kind_passes=source['registered_kind_passes'])
        comparisons = []
        for key, bundle in source['cells_now'].items():
            if prior is not None and key in source['cells_previous']:
                comparisons.append(compare(
                    current, prior, measured=measured, baseline=baseline, kind_now=bundle,
                    kind_previous=source['cells_previous'][key], stage_id=ctx.stage_id,
                    kind_score_key='late_kind'))
        items['exchange_watch'] = {
            'role': 'judge', 'judgement': aggregate(r['judgement'] for r in comparisons),
            'cells': comparisons, 'reason': None if comparisons else 'late stage previous kind comparison missing'}
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
