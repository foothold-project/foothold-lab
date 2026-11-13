"""Literal boundary cases from ledger 73abb340 and reviewer #784.

Each threshold is varied alone. No expected result is computed by a rule helper.
"""
import pytest
import boundary_rules
from boundary_rules import decide
from test_boundary_rules import snapshot, treatment


@pytest.mark.parametrize('level', [0, 5])
@pytest.mark.parametrize('ratio,want', [(.55, 'R6'), (.6, 'KEEP'), (.61, 'KEEP')])
def test_r6_fwd02_threshold_is_060_not_050(level, ratio, want):
    now = snapshot()
    now['metrics'][f'low/L{level}/eval_gt/fwd0.2/R'] = ratio
    result = decide(now, snapshot(0), treatment=treatment())
    assert result['rule'] == want
    assert result['changes'] == ({'slow_track': .2} if want == 'R6' else {})


@pytest.mark.parametrize('mode', ['eval_gt', 'eval_pred'])
@pytest.mark.parametrize('median,want', [(.099, 'KEEP'), (.10, 'KEEP'), (.13, 'R2')])
def test_r2_median_threshold_is_010_not_015(mode, median, want):
    now = snapshot()
    now['metrics'][f'yaw/L2/{mode}/fwd1.0/median_abs_rad'] = median
    # A p90 trigger must not conceal a missed median trigger.
    now['metrics'][f'yaw/L2/{mode}/fwd1.0/p90_abs_rad'] = .19
    result = decide(now, snapshot(0), treatment=treatment())
    assert result['rule'] == want
    assert result['changes'] == ({'zero_yaw': -1.25} if want == 'R2' else {})


@pytest.mark.parametrize('elapsed,want', [(0, False), (250, False), (499, False),
                                         (500, True), (750, True)])
def test_r5_observation_requires_500_updates(elapsed, want):
    # The independent elapsed-time condition must survive a future change to
    # the separate two-clean-window guard. Use a genuine consumed predicate.
    complete = getattr(boundary_rules, 'r5_observation_complete', None)
    assert callable(complete), 'R5 elapsed-time contract must be independently testable'
    assert complete(1000 + elapsed, 1000) is want


def test_r5_missing_activation_is_not_a_completed_observation():
    complete = getattr(boundary_rules, 'r5_observation_complete', None)
    assert callable(complete)
    assert complete(2000, None) is False


@pytest.mark.parametrize('elapsed,want', [(250, 'OBSERVE'), (500, 'R5')])
def test_r5_full_decision_waits_for_two_post_activation_boundaries(elapsed, want):
    anchor = snapshot(250, low=.65)
    now = snapshot(250 + elapsed, low=.75)
    previous = anchor if elapsed == 250 else snapshot(500, low=.7)
    current = treatment(250, 0., .2)
    current['anchor'] = anchor
    gait = dict(valid=True, valid_conditions=True, contact_definition='norm_Fxyz_gt_1N')
    result = decide(now, snapshot(0), previous, anchor, treatment=current, gait=gait)
    assert result['rule'] == want
    assert result['changes'] == ({'feet_air_time_threshold': .04, 'feet_air_time': .1}
                                 if want == 'R5' else {})


@pytest.mark.parametrize('passed,want', [(61, 'OBSERVE'), (60, 'ROLLBACK'),
                                       (59, 'ROLLBACK')])
def test_stand_drop_includes_exactly_four_envs(passed, want):
    anchor = snapshot(250, low=.65)
    first, second = snapshot(500, low=.7), snapshot(750, low=.75)
    key = 'stand/flat/eval_gt/stand/success'
    first['metrics'][key] = second['metrics'][key] = passed
    current = treatment(250, 0., .2)
    current['anchor'] = anchor
    result = decide(second, snapshot(0), first, anchor, treatment=current)
    assert result['rule'] == want
    assert result['changes'] == ({'slow_track': 0.} if want == 'ROLLBACK' else {})


def test_stand_exact_four_drop_needs_two_windows_not_one():
    anchor, first, second = snapshot(250, low=.65), snapshot(500, low=.7), snapshot(750, low=.75)
    first['metrics']['stand/flat/eval_gt/stand/success'] = 61
    second['metrics']['stand/flat/eval_gt/stand/success'] = 60
    current = treatment(250, 0., .2)
    current['anchor'] = anchor
    result = decide(second, snapshot(0), first, anchor, treatment=current)
    assert result['rule'] == 'OBSERVE'
    assert result['changes'] == {}
