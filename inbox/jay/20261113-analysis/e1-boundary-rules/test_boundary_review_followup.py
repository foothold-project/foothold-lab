"""Known-answer cases for reviewer 19:36's four surviving mutations.

The rollback helper default and its decision consumer are tested separately:
regression() normally passes modes explicitly, so changing only the helper's
default is not an end-to-end decision change. No production logic is altered.
"""
import json
import pytest
from boundary_read import maintenance_mode_status
from boundary_rules import decide, rollback_limits
from test_boundary_read import PARENT
from test_boundary_rules import snapshot, treatment


def test_rollback_default_includes_pred_and_excludes_off():
    """The public default must retain PRED even if an explicit caller is safe."""
    limits = rollback_limits()
    assert 'map/mixed012/eval_pred/spin+1.2/yaw_follow' in limits
    assert 'stand/flat/eval_pred/stand/success' in limits
    assert limits['map/mixed012/eval_pred/spin+1.2/yaw_follow'] == (-1, .05, False)
    assert limits['stand/flat/eval_pred/stand/success'] == (-1, 4, True)
    assert not any('/probe_prop_only/' in key for key in limits)


@pytest.mark.parametrize('case,first_value,last_value', [
    ('map/mixed012/eval_pred/spin+1.2/yaw_follow', .80, .82),
    ('low/L5/eval_pred/side-0.4/R', .80, .82),
    ('yaw/L2/eval_pred/fwd1.0/median_abs_rad', .08, .07),
    ('stand/flat/eval_pred/stand/success', 60, 60),
    ('map/mixed012/eval_pred/stop/speed_median_mps', .05, .04),
])
def test_pred_regression_drives_actual_rollback(case, first_value, last_value):
    """Dropping PRED from regression's default must change this real decision."""
    anchor, previous, now = snapshot(250), snapshot(500), snapshot(750)
    previous['metrics'][case], now['metrics'][case] = first_value, last_value
    current = treatment(250, 0., .2)
    current['anchor'] = anchor
    result = decide(now, snapshot(0), previous, anchor, treatment=current)
    assert result['rule'] == 'ROLLBACK'
    assert result['changes'] == {'slow_track': 0.}
    assert result['two_window_regression'] == [case]


@pytest.mark.parametrize('status', ['FAIL', 'HOLD', None])
def test_prior_pred_nonpass_cannot_supply_second_rollback_window(status):
    """Previous-window validity matters outside the separate R6 raise guard."""
    anchor, previous, now = snapshot(250), snapshot(500), snapshot(750)
    key = 'map/mixed012/eval_pred/spin+1.2/yaw_follow'
    previous['metrics'][key] = now['metrics'][key] = .8
    previous['maintenance_modes']['eval_pred'] = status
    current = treatment(250, 0., .2)
    current['anchor'] = anchor
    result = decide(now, snapshot(0), previous, anchor, treatment=current)
    assert result['rule'] != 'ROLLBACK'
    assert result['changes'] == {}
    assert not result.get('two_window_regression')


@pytest.mark.parametrize('status', ['FAIL', 'HOLD', None])
def test_prior_pred_nonpass_cannot_allow_actual_raise(status):
    """All eight declining cells still cannot override invalid prior PRED."""
    previous, now = snapshot(250, low=.4), snapshot(500, low=.2)
    previous['maintenance_modes']['eval_pred'] = status
    result = decide(now, snapshot(0), previous, treatment=treatment(250, 0., .2))
    assert result['rule'] == 'EVIDENCE_HOLD'
    assert result['changes'] == {}


@pytest.mark.parametrize('missing', [('eval_gt',), ('eval_pred',), ('eval_gt', 'eval_pred')])
def test_missing_judged_mode_verdict_cannot_become_a_treatment(missing):
    """Aggregate PASS and low-speed failure cannot replace either map verdict."""
    now = snapshot(low=.1)
    for mode in missing:
        del now['maintenance_modes'][mode]
    result = decide(now, snapshot(0), treatment=treatment())
    assert result['rule'] == 'EVIDENCE_HOLD'
    assert result['changes'] == {}
    assert 'GT_PRED_maintenance_coverage_missing' in result['missing']


@pytest.mark.parametrize('mode', ['eval_gt', 'eval_pred', 'probe_prop_only'])
@pytest.mark.parametrize('change', ['rename', 'drop'])
def test_real_parent_requires_all_thirteen_named_commands(mode, change):
    """A renamed case keeps the count at 13, but it is a different test sheet."""
    doc = json.loads(PARENT.read_text(encoding='utf-8'))
    assert maintenance_mode_status(doc) == {'eval_gt': 'PASS', 'eval_pred': 'PASS'}
    rows = doc['cell_judgments'][mode]
    stop = rows.pop('stop')
    if change == 'rename':
        rows['stop_not_in_contract'] = stop
        assert len(rows) == 13
    with pytest.raises(ValueError, match='maintenance command coverage differs'):
        maintenance_mode_status(doc)
