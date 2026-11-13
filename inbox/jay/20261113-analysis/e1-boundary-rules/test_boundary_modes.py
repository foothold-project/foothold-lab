"""19:28 decision: GT/PRED independently judge; map-off is recorded only."""
from copy import deepcopy
import pytest
import boundary_read
from boundary_rules import decide
from test_boundary_rules import snapshot, treatment


@pytest.mark.parametrize('level', [0, 5])
@pytest.mark.parametrize('speed,low', [(.1, .1), (.2, .4)])
def test_pred_only_low_cell_can_start_r6(level, speed, low):
    now = snapshot()
    key = f'low/L{level}/eval_pred/fwd{speed}/R'
    now['metrics'][key] = low
    result = decide(now, snapshot(0), treatment=treatment())
    assert result['rule'] == 'R6'
    assert result['low_trigger_cells'] == [key]
    assert result['changes'] == {'slow_track': .2}


def test_one_pred_improvement_blocks_raise_even_when_all_gt_decline():
    anchor, now = snapshot(250, low=.4), snapshot(500, low=.2)
    now['metrics']['low/L5/eval_pred/fwd0.2/R'] = .5
    result = decide(now, snapshot(0), anchor, treatment=treatment(250, 0., .2))
    assert result['rule'] == 'OBSERVE' and result['changes'] == {}
    assert len(result['r6_raise_deltas']) == 8


def test_eight_declines_can_raise_and_off_improvement_cannot_veto():
    anchor, now = snapshot(250, low=.4), snapshot(500, low=.2)
    now['metrics']['low/L5/probe_prop_only/fwd0.2/R'] = .8
    result = decide(now, snapshot(0), anchor, treatment=treatment(250, 0., .2))
    assert result['rule'] == 'R6_RAISE'
    assert len(result['r6_raise_deltas']) == 8
    assert result['changes'] == {'slow_track': .3}


@pytest.mark.parametrize('previous_missing', [False, True])
def test_missing_pred_cell_cannot_be_filled_from_gt(previous_missing):
    anchor, now = snapshot(250, low=.4), snapshot(500, low=.2)
    target = anchor if previous_missing else now
    del target['metrics']['low/L0/eval_pred/fwd0.2/R']
    result = decide(now, snapshot(0), anchor, treatment=treatment(250, 0., .2))
    assert result['rule'] == 'EVIDENCE_HOLD' and result['changes'] == {}


@pytest.mark.parametrize('mode', ['eval_gt', 'eval_pred'])
def test_any_judged_map_can_roll_back_with_two_same_bad_windows(mode):
    anchor = snapshot(250, low=.65)
    first, now = snapshot(500, low=.7), snapshot(750, low=.75)
    first['metrics'][f'map/mixed012/{mode}/spin+1.2/yaw_follow'] = .8
    now['metrics'][f'map/mixed012/{mode}/spin+1.2/yaw_follow'] = .8
    current = treatment(250, 0., .2); current['anchor'] = anchor
    result = decide(now, snapshot(0), first, anchor, treatment=current)
    assert result['rule'] == 'ROLLBACK' and result['changes'] == {'slow_track': 0.}


def test_gt_then_pred_decline_is_not_two_windows_for_one_map():
    anchor = snapshot(250, low=.65)
    first, now = snapshot(500, low=.7), snapshot(750, low=.75)
    first['metrics']['map/mixed012/eval_gt/spin+1.2/yaw_follow'] = .8
    now['metrics']['map/mixed012/eval_pred/spin+1.2/yaw_follow'] = .8
    current = treatment(250, 0., .2); current['anchor'] = anchor
    result = decide(now, snapshot(0), first, anchor, treatment=current)
    assert result['rule'] == 'OBSERVE' and result['changes'] == {}


def test_off_regression_is_visible_but_cannot_roll_back():
    anchor = snapshot(250, low=.65)
    first, now = snapshot(500, low=.7), snapshot(750, low=.75)
    key = 'stand/flat/probe_prop_only/stand/success'
    first['metrics'][key] = now['metrics'][key] = 0
    current = treatment(250, 0., .2); current['anchor'] = anchor
    result = decide(now, snapshot(0), first, anchor, treatment=current)
    assert result['rule'] == 'OBSERVE' and result['changes'] == {}
    assert key in result['regression_record_only']['bad']
    assert key not in result['regression']['bad']


def test_pred_maintenance_fail_cannot_hide_behind_aggregate_pass():
    now = snapshot(); now['maintenance_modes']['eval_pred'] = 'FAIL'
    result = decide(now, snapshot(0), treatment=treatment())
    assert result['rule'] == 'R4' and result['next_segment'] == 'DO_NOT_START'


def test_failed_pred_maintenance_in_previous_window_cannot_allow_raise():
    anchor, now = snapshot(250, low=.4), snapshot(500, low=.2)
    anchor['maintenance_modes']['eval_pred'] = 'FAIL'
    result = decide(now, snapshot(0), anchor, treatment=treatment(250, 0., .2))
    assert result['rule'] == 'EVIDENCE_HOLD' and result['changes'] == {}


def test_reader_requires_gt_pred_coverage_not_any_26_judges():
    from test_boundary_read import PARENT
    import json
    doc = json.loads(PARENT.read_text())
    read = getattr(boundary_read, 'maintenance_mode_status', None)
    assert callable(read)
    assert read(doc) == {'eval_gt':'PASS', 'eval_pred':'PASS'}
    for row in doc['cell_judgments']['eval_pred'].values(): row['role'] = 'record_only'
    for row in doc['cell_judgments']['probe_prop_only'].values(): row['role'] = 'judge'
    with pytest.raises(ValueError, match='mode|role'):
        read(doc)


def test_report_modes_do_not_pool_or_fill_missing_pred():
    group = getattr(boundary_read, 'comparisons_by_mode', None)
    assert callable(group)
    rows=[]
    for mode, value in [('eval_gt',.1), ('eval_pred',.2), ('probe_prop_only',.3)]:
        rows.append(dict(cell=f'low/L0/{mode}/fwd0.2/R',unit='ratio',value=value,
                         parent=0.,parent_delta=value,previous=None,previous_delta=None,
                         parent_conditions_match=True))
    row=group(rows)[0]
    assert row['eval_gt']['value'] == .1 and row['eval_pred']['value'] == .2
    assert row['probe_prop_only']['value'] == .3
    assert row['cell'] == 'low/L0/fwd0.2/R'
    assert group([rows[0], rows[2]])[0]['eval_pred'] is None
