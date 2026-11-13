"""E1F continues with the reward cells E1 really ran with in its last segment (decisions.tsv 2026-11-13 21:50). CPU only."""
import json
from pathlib import Path

import pytest
import yaml

from foothold_s2.tests import test_ex42_materialize_cpu as parent_tests

known = parent_tests.known
run = parent_tests.run


def _readbacks(known):
    return [known['parent_manifest'].parent / f'segment_rewards_b6_rank{rank}.json' for rank in range(2)]


def _rewrite(path, **changes):
    body = json.loads(path.read_text())
    for cell, value in changes.pop('cells', {}).items():
        body['live'][cell] = value
        if body['asked'] is not None:
            body['asked'][cell] = value
    body.update(changes)
    path.write_text(json.dumps(body))


def _e1f(result):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    plan = EX42Plan.load(result['plan'])
    return plan, next(x for x in plan.document['stages'] if x['id'] == 'E1F')


def test_e1f_row_gets_the_last_segment_live_values_including_an_adjustment(known):
    for path in _readbacks(known):
        _rewrite(path, source='adjust_file', cells={'slow_track': 0.2})
    result = run(known)
    plan, row = _e1f(result)
    source_row = next(x for x in yaml.safe_load(Path(known['source_plan']).read_text())['stages'] if x['id'] == 'E1')
    assert row['rewards'] == {**source_row['rewards'], 'slow_track': 0.2}
    assert row['rewards']['zero_yaw'] == -1.0 and row['rewards']['track_lin_vel_std'] == 0.35
    transition = json.loads(Path(result['transition']).read_text())
    assert transition['inherited_rewards']['boundary_index'] == 6
    assert transition['inherited_rewards']['origin'] == 'segment_rewards readback'
    assert transition['inherited_rewards']['values'] == row['rewards']
    assert {'inherited_rewards.readback0', 'inherited_rewards.readback1'} <= set(transition['artifacts'])
    # the stage start reads the same cells from the published row
    from foothold_s2.commands.ex42_segment_adjust import stage_rewards
    assert stage_rewards(plan, 'E1F') == row['rewards']
    from foothold_s2.ex42_stage_materialize import validate_materialized_transition
    validate_materialized_transition(plan, target_stage='E1F', gate_receipt_path=known['gate_receipt'],
                                     expected_gate_sha256=parent_tests.sha(known['gate_receipt']))


def test_a_readback_changed_after_publication_no_longer_replays(known):
    result = run(known)
    plan, _ = _e1f(result)
    from foothold_s2.ex42_stage_materialize import validate_materialized_transition
    for path in _readbacks(known):
        _rewrite(path, cells={'zero_yaw': -0.5})
    with pytest.raises(ValueError):
        validate_materialized_transition(plan, target_stage='E1F', gate_receipt_path=known['gate_receipt'],
                                         expected_gate_sha256=parent_tests.sha(known['gate_receipt']))


@pytest.mark.parametrize('bad', ['missing', 'ranks_differ', 'boundary', 'stage', 'plan_sha', 'cell_missing',
                                 'outside_limits', 'live_differs_from_asked', 'not_a_number'])
def test_a_broken_last_segment_readback_is_refused_not_replaced_by_defaults(known, bad):
    first, second = _readbacks(known)
    if bad == 'missing':
        first.unlink(); second.unlink()
    elif bad == 'ranks_differ':
        _rewrite(second, cells={'slow_track': 0.2})
    elif bad == 'boundary':
        _rewrite(first, boundary_index=5)
    elif bad == 'stage':
        _rewrite(first, stage_id='E0')
    elif bad == 'plan_sha':
        _rewrite(first, plan_sha256='0' * 64)
    elif bad == 'cell_missing':
        body = json.loads(first.read_text()); body['live'].pop('zero_yaw'); first.write_text(json.dumps(body))
    elif bad == 'outside_limits':
        for path in (first, second):
            _rewrite(path, cells={'zero_yaw': -5.0})
    elif bad == 'live_differs_from_asked':
        body = json.loads(first.read_text()); body['live']['zero_yaw'] = -0.5; first.write_text(json.dumps(body))
    else:
        body = json.loads(first.read_text()); body['live']['zero_yaw'] = 'x'; body['asked'] = None
        first.write_text(json.dumps(body))
    with pytest.raises(ValueError):
        run(known)
    assert not Path(known['out']).exists()


def _manifest(known, segments):
    body = json.loads(known['parent_manifest'].read_text())
    if segments is None:
        body.pop('ex42_resume_segments')
    else:
        body['ex42_resume_segments'] = segments
    known['parent_manifest'].write_text(json.dumps(body))


@pytest.mark.parametrize('segments,iteration', [(None, 1750), ([], 1750), ([{'local_update_origin': 250}], 250)])
def test_a_run_never_resumed_before_the_exit_inherits_the_source_plan_row(known, segments, iteration):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_stage_materialize import inherited_rewards
    _manifest(known, segments)
    for path in _readbacks(known):
        path.unlink()
    source = EX42Plan.load(known['source_plan'])
    limits = Path(known['plan']).parent / 'ex42-reward-adjust-limits.yaml'
    row, refs = inherited_rewards(source, 'E1', known['parent_manifest'], iteration, limits)
    assert refs == {} and row['boundary_index'] == 0 and row['origin'] == 'source plan row'
    assert row['values'] == next(x for x in source.document['stages'] if x['id'] == 'E1')['rewards']


def test_the_last_started_segment_speaks_even_when_it_ran_across_later_boundaries(known):
    # resumed at 250 and 500 only, then one long segment to 1750: boundary 2's readback is the one in force at the exit
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_stage_materialize import inherited_rewards
    _manifest(known, [{'local_update_origin': 250}, {'local_update_origin': 500}])
    run_dir = known['parent_manifest'].parent
    for rank, path in enumerate(_readbacks(known)):
        _rewrite(path, boundary_index=2, cells={'slow_track': 0.2})
        path.rename(run_dir / f'segment_rewards_b2_rank{rank}.json')
    source = EX42Plan.load(known['source_plan'])
    row, refs = inherited_rewards(source, 'E1', known['parent_manifest'], 1750,
                                  Path(known['plan']).parent / 'ex42-reward-adjust-limits.yaml')
    assert row['boundary_index'] == 2 and row['values']['slow_track'] == 0.2 and len(refs) == 2


@pytest.mark.parametrize('segments', [[{'local_update_origin': 100}], [{'local_update_origin': '250'}], ['x'], {'a': 1}])
def test_an_invalid_resumed_segment_record_is_refused(known, segments):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_stage_materialize import inherited_rewards
    _manifest(known, segments)
    with pytest.raises(ValueError):
        inherited_rewards(EX42Plan.load(known['source_plan']), 'E1', known['parent_manifest'], 1750,
                          Path(known['plan']).parent / 'ex42-reward-adjust-limits.yaml')


def test_a_source_stage_without_reward_cells_inherits_nothing(known):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_stage_materialize import inherited_rewards
    source = EX42Plan.load(known['source_plan'])
    limits = Path(known['plan']).parent / 'ex42-reward-adjust-limits.yaml'
    assert inherited_rewards(source, 'E0', known['parent_manifest'], 250, limits) == (None, {})


def test_a_template_row_with_its_own_cells_is_not_overwritten(known):
    document = yaml.safe_load(Path(known['plan']).read_text())
    own = dict(next(x for x in document['stages'] if x['id'] == 'E1')['rewards'], zero_yaw=-0.75)
    next(x for x in document['stages'] if x['id'] == 'E1F')['rewards'] = own
    template = Path(known['plan']).parent / 'own-cells.yaml'
    template.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True))
    known['plan'] = template
    for path in _readbacks(known):
        path.unlink()                     # not needed, and not read, when the template speaks for itself
    result = run(known)
    _, row = _e1f(result)
    assert row['rewards'] == own
    assert 'inherited_rewards' not in json.loads(Path(result['transition']).read_text())
