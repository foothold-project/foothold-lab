"""Ledger 0a5c1629: R5's .2 m/s floor applies to both GT and PRED."""
import pytest
from boundary_rules import decide
from test_boundary_rules import snapshot, treatment


def ready_r5():
    anchor, previous, now = snapshot(250, low=.65), snapshot(500, low=.7), snapshot(750, low=.75)
    current = treatment(250, 0., .2)
    current['anchor'] = anchor
    gait = {'valid': True, 'valid_conditions': True, 'contact_definition': 'norm_Fxyz_gt_1N'}
    return anchor, previous, now, current, gait


@pytest.mark.parametrize('mode', ['eval_gt', 'eval_pred'])
@pytest.mark.parametrize('level', [0, 5])
@pytest.mark.parametrize('ratio,expected', [(.4999, 'OBSERVE'), (.5, 'R5')])
def test_r5_floor_requires_each_gt_pred_cell_at_least_half(mode, level, ratio, expected):
    anchor, previous, now, current, gait = ready_r5()
    now['metrics'][f'low/L{level}/{mode}/fwd0.2/R'] = ratio
    result = decide(now, snapshot(0), previous, anchor, treatment=current, gait=gait)
    assert result['rule'] == expected
    assert result['changes'] == ({'feet_air_time_threshold': .04, 'feet_air_time': .1} if expected == 'R5' else {})


def test_r5_floor_does_not_turn_off_mode_into_a_judge():
    anchor, previous, now, current, gait = ready_r5()
    for level in (0, 5):
        now['metrics'][f'low/L{level}/probe_prop_only/fwd0.2/R'] = 0.
    result = decide(now, snapshot(0), previous, anchor, treatment=current, gait=gait)
    assert result['rule'] == 'R5'
    assert result['changes'] == {'feet_air_time_threshold': .04, 'feet_air_time': .1}
