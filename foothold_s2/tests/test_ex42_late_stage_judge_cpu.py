"""Consumer gates, independently from the task-reader physics known-input tests."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from foothold_s2.ex42_stage_judges import adapter_for
from foothold_s2 import ex42_late_stage_judge as late
from foothold_s2.ex42_score import config, digest, ROOT


def inputs(tmp_path, stage):
    cfg, cfg_path = config()
    pp = ROOT / cfg['maintenance_source']
    plan = yaml.safe_load(pp.read_text(encoding='utf-8-sig'))
    # The baseline is real pinned data. Construct an exact parent-median score
    # to isolate whether a missing new-task consumer can improperly pass exit.
    from foothold_s2.ex42_e0_judge import load_baseline
    base = load_baseline(ROOT, cfg, digest)
    cp = tmp_path / 'model_500.pt'; cp.write_bytes(b'CPU identity fixture, not a runnable model')
    score = dict(stage_id=stage, checkpoint=str(cp), checkpoint_sha256=digest(cp),
        score_config_sha256=digest(cfg_path), maintenance_source_sha256=digest(pp),
        conditions={'envs': 64, 'eval_seed': 42}, map64={}, maintenance_items={})
    for path, value in base['metrics'].items():
        parts = path.split('/')
        if len(parts) == 4 and parts[0] == 'map64':
            _, mode, case, metric = parts
            score['map64'].setdefault(mode, {}).setdefault(case, {})[metric] = value['parent_median']
    ctx = SimpleNamespace(root=ROOT, cfg=cfg, cfg_path=cfg_path, digest=digest,
        plan=plan, plan_path=pp, checkpoint=cp, checkpoint_sha=digest(cp),
        evaluation=tmp_path / 'm500', seed=42, stage_id=stage)
    return ctx, score


@pytest.mark.parametrize('stage', ['E4', 'E5'])
def test_registry_and_passing_parent_without_new_raw_is_hold(tmp_path, stage):
    ctx, score = inputs(tmp_path, stage)
    adapter = adapter_for(ctx.plan, stage)
    assert adapter.name == 'kind_two_window_' + stage.lower()
    result = adapter.judge(ctx, score)
    assert result['stage_exit']['items']['maintenance_current']['judgement'] == 'PASS'
    assert result['judgement'] == 'HOLD'
    assert result['stage_exit']['items']['task_current']['judgement'] == 'HOLD'
    assert result['stage_exit']['items']['learned_cells']['judgement'] == 'HOLD'
    assert adapter.verify(result, 'HOLD', 'PASS', plan=ctx.plan)['stage_exit'] == result['stage_exit']
    forged = copy.deepcopy(result)
    forged['judgement'] = forged['stage_exit']['judgement'] = 'PASS'
    for row in forged['stage_exit']['items'].values():
        row['judgement'] = 'PASS'
    with pytest.raises(ValueError, match='raw recomputation'):
        adapter.verify(forged, 'PASS', 'PASS', plan=ctx.plan)


def test_known_maintenance_fail_survives_missing_common_and_tasks(tmp_path):
    ctx, score = inputs(tmp_path, 'E4')
    score['map64']['eval_gt']['fwd1.0']['alive_at_end'] = 0
    result = adapter_for(ctx.plan, 'E4').judge(ctx, score)
    assert result['judgement'] == 'FAIL'
    assert result['stage_exit']['items']['learned_cells']['judgement'] == 'HOLD'


def test_wrong_stage_cannot_reuse_an_adapter(tmp_path):
    ctx, score = inputs(tmp_path, 'E4')
    ctx.stage_id = 'E5'
    with pytest.raises(ValueError, match='identity'):
        adapter_for(ctx.plan, 'E4').judge(ctx, score)


@pytest.mark.parametrize('missing', ['exposure', 'kind_current', 'kind_previous', 'level_targets'])
def test_common_port_requires_all_gates_before_calling_shared_apis(tmp_path, monkeypatch, missing):
    ctx, score = inputs(tmp_path, 'E4')
    items = {key: {'role': 'judge', 'judgement': 'PASS'} for key in
             ('exposure', 'kind_current', 'kind_previous', 'level_targets') if key != missing}
    monkeypatch.setattr(late, 'common_inputs', lambda *args: {'items': items})
    result = late.common_gates(ctx, score, None, baseline={}, measured={})
    assert set(result) == {'kind_windows', 'learned_cells', 'exchange_watch'}
    assert all(v['judgement'] == 'HOLD' for v in result.values())


def test_common_pass_names_without_pinned_execution_plan_are_hold(tmp_path, monkeypatch):
    ctx, score = inputs(tmp_path, 'E4')
    source = {'items': {key: {'role': 'judge', 'judgement': 'PASS'} for key in
                       ('exposure', 'kind_current', 'kind_previous', 'level_targets')},
              'execution_plan': {'path': str(tmp_path / 'absent'), 'sha256': 'a' * 64}}
    monkeypatch.setattr(late, 'common_inputs', lambda *args: source)
    result = late.common_gates(ctx, score, None, baseline={}, measured={})
    assert result['kind_windows']['judgement'] == 'HOLD'


def test_prep_only_declares_two_adapters_without_changing_approvals():
    plan = yaml.safe_load((ROOT / 'foothold_s2/curriculum/ex42-prep.yaml').read_text(encoding='utf-8'))
    for stage in ('E4', 'E5'):
        assert adapter_for(plan, stage).name == 'kind_two_window_' + stage.lower()


@pytest.mark.parametrize('key', ['maintenance_current', 'maintenance_previous', 'task_current',
    'task_previous', 'learned_cells', 'exchange_watch', 'kind_windows'])
def test_each_required_gate_is_effective_even_when_all_others_pass(key):
    # Deliberate fault isolation: these are gate states, not fabricated measurements.
    items = {k: {'role': 'judge', 'judgement': 'PASS'} for k in
             ('maintenance_current', 'maintenance_previous', 'task_current',
              'task_previous', 'learned_cells', 'exchange_watch', 'kind_windows')}
    assert late.exit_verdict(items) == 'PASS'
    items[key]['judgement'] = 'HOLD'
    assert late.exit_verdict(items) == 'HOLD'
    items[key]['judgement'] = 'FAIL'
    assert late.exit_verdict(items) == 'FAIL'
    items[key]['role'] = 'record_only'
    with pytest.raises(ValueError, match='demoted'):
        late.exit_verdict(items)
