"""Known-answer tests for the 23:04 approved table, separate from old R2/R6."""
from copy import deepcopy
import pytest
from boundary_approved import off_monitor, diagnosis, departure, apply_approved


def audit(n=1750):
    return dict(iteration=n, errors=[], required_complete=True, cells={
        f'low/L0/{mode}/fwd0.1':dict(judgement='PASS', valid=64)
        for mode in ('eval_gt','eval_pred')},
        off_cells={'map/fwd0.5':dict(survival=64,valid=64,fingerprint='x'),
                   'low/L5/fwd0.2':dict(survival=64,valid=64,fingerprint='y')},
        all_judge_pass=True, treatment_sha256='a'*64, evaluation_sha256='b'*64,
        wide=dict(reached_level={'eval_gt':6,'eval_pred':3},L9={'eval_gt':0,'eval_pred':0}),
        gaps={'low/L0/eval_gt/fwd0.1/R':0.,'low/L0/eval_pred/fwd0.1/R':0.})


def test_off_60_inclusive_and_tracking_is_not_a_gate():
    a=audit();a['off_cells']['map/fwd0.5'].update(survival=60,R=-1.)
    assert off_monitor(a,audit(1500))['state']=='PASS'


def test_off_same_cell_two_windows_only_and_missing_not_recovery():
    a,b=audit(),audit(1500)
    a['off_cells']['map/fwd0.5']['survival']=59
    assert off_monitor(a,b)['state']=='SINGLE_FAIL_RECORD'
    b['off_cells']['low/L5/fwd0.2']['survival']=59
    assert off_monitor(a,b)['state']=='SINGLE_FAIL_RECORD'
    b['off_cells']['map/fwd0.5']['survival']=59
    assert off_monitor(a,b)['rollback_cells']==['map/fwd0.5']
    b['iteration']=1250
    assert off_monitor(a,b)['state']=='SINGLE_FAIL_RECORD'
    a['off_cells']['map/fwd0.5']['valid']=63
    assert off_monitor(a,b)['state']=='HOLD'
    a['off_cells']['map/fwd0.5']['valid']=64
    b['iteration']=1500;b['off_cells']['map/fwd0.5']['fingerprint']='other'
    assert off_monitor(a,b)['state']=='HOLD'


def test_gt_pred_diagnostic_labels_are_per_cell_not_causal_proof():
    a=audit();key='low/L0/eval_pred/fwd0.1';a['cells'][key]['judgement']='FAIL'
    assert diagnosis(a)[0]['interpretation']=='지각 경로 점검'
    a['cells']['low/L0/eval_gt/fwd0.1']['judgement']='FAIL'
    assert diagnosis(a)[0]['interpretation']=='정책·과제 점검'
    a['cells']['low/L0/eval_gt/fwd0.1']['judgement']='HOLD'
    assert diagnosis(a)[0]['interpretation']=='미확인'


def test_d44_and_c1_diagnosis_preserves_the_two_mode_pair():
    a=audit();a['cells']={
        'd44/turn_left_eval_gt':{'judgement':'PASS'},
        'd44/turn_left_eval_pred':{'judgement':'FAIL'},
        'wide_L3_fwd1.0/eval_gt':{'judgement':'FAIL'},
        'wide_L3_fwd1.0/eval_pred':{'judgement':'PASS'}}
    d={r['cell']:r for r in diagnosis(a)}
    assert d['d44/turn_left']['interpretation']=='지각 경로 점검'
    assert d['wide_L3_fwd1.0']['interpretation']=='정책·과제 점검'
    assert all(not r['cause_proven'] for r in d.values())


def test_1750_two_windows_and_l9_is_record_only():
    a,b=audit(),audit(1500)
    assert departure(a,b,audit(1250),{'state':'HOLD'})['next_segment']=='E1F'
    b['treatment_sha256']='c'*64
    assert departure(a,b,audit(1250),None)['next_segment']=='HOLD_DIAGNOSE'
    b=audit(1500);b['all_judge_pass']=False
    assert departure(a,b,audit(1250),None)['next_segment']=='HOLD_DIAGNOSE'
    a['required_complete']=False
    assert departure(a,b,audit(1250),{'state':'PASS'})['next_segment']=='HOLD_DIAGNOSE'


def test_1750_all_deficient_gt_pred_improve_twice_no_other_regression():
    a,b,c=audit(),audit(1500),audit(1250)
    for x,gap in ((a,.1),(b,.2),(c,.3)):
        x['all_judge_pass']=False
        x['gaps']={k:gap for k in x['gaps']}
    ev={'state':'PASS'}
    assert departure(a,b,c,ev)['next_segment']=='E1_EXTEND_250_ONCE'
    a['gaps']['low/L0/eval_pred/fwd0.1/R']=.2
    assert departure(a,b,c,ev)['next_segment']=='HOLD_DIAGNOSE'
    a['gaps']['low/L0/eval_pred/fwd0.1/R']=.1
    for x,v in ((a,.05),(b,.06),(c,.04)):x['gaps']['other']=v
    assert departure(a,b,c,ev)['next_segment']=='HOLD_DIAGNOSE'
    for x,v in ((a,0.),(b,.1),(c,0.)):x['gaps']['other']=v
    assert departure(a,b,c,ev)['next_segment']=='HOLD_DIAGNOSE'
    assert departure(a,b,c,None)['next_segment']=='HOLD_DIAGNOSE'


def test_no_second_extension_and_no_missing_cell_pass():
    a=audit(2000);b=audit(1750);a['all_judge_pass']=False
    assert departure(a,b,audit(1500),{'state':'PASS'})['next_segment']=='HOLD_DIAGNOSE'
    a=audit();a['cells']['low/L0/eval_gt/fwd0.1']['valid']=63
    assert departure(a,audit(1500),audit(1250),None)['next_segment']=='HOLD_DIAGNOSE'
    a=audit();a['off_cells']['map/fwd0.5']['survival']=59
    assert departure(a,audit(1500),audit(1250),None)['next_segment']=='HOLD_DIAGNOSE'


def test_off_rollback_precedes_new_reward_draft_and_is_not_a_checkpoint_rollback():
    a,b=audit(1250),audit(1000)
    for x in (a,b):x['off_cells']['map/fwd0.5']['survival']=59
    core=dict(rule='R6_RAISE',changes={'slow_track':.3},next_segment='UNCHANGED',notes=[],triggered=[])
    t={'last_change':{'before':{'slow_track':0},'fields':['slow_track']}}
    d=apply_approved(core,a,b,None,t,None)
    assert d['rule']=='OFF_SURVIVAL_ROLLBACK' and d['changes']=={'slow_track':0}
    assert 'checkpoint' not in d['changes']
    a['off_cells']['map/fwd0.5']['valid']=63
    d=apply_approved(core,a,b,None,t,None)
    assert d['rule']=='EVIDENCE_HOLD' and d['changes']=={}


def test_prior_to_750_is_counterfactual_only():
    a,b=audit(500),audit(250)
    for x in (a,b):x['off_cells']['map/fwd0.5']['survival']=59
    core=dict(rule='OBSERVE',changes={},next_segment='UNCHANGED',notes=[],triggered=[])
    d=apply_approved(core,a,b,None,{'last_change':None},None)
    assert d['rule']=='OBSERVE'
    assert d['de8_counterfactual']['rule']=='OFF_SURVIVAL_ROLLBACK'


def test_explicit_1000_schedule_keeps_750_on_existing_rules():
    a,b=audit(750),audit(500)
    for x in (a,b):x['off_cells']['map/fwd0.5']['survival']=59
    core=dict(rule='OBSERVE',changes={},next_segment='UNCHANGED',notes=[],triggered=[])
    d=apply_approved(core,a,b,None,{'last_change':None},None,effective_from=1000)
    assert d['rule']=='OBSERVE' and d['de8_counterfactual']['rule']=='OFF_SURVIVAL_ROLLBACK'
    assert d['effective_from']==1000


def test_750_record_does_not_become_first_active_off_failure():
    a,b=audit(1000),audit(750)
    for x in (a,b):x['off_cells']['map/fwd0.5']['survival']=59
    core=dict(rule='OBSERVE',changes={},next_segment='UNCHANGED',notes=[],triggered=[])
    d=apply_approved(core,a,b,None,{'last_change':None},None)
    assert d['rule']=='OBSERVE'
    assert d['map_off_survival']['state']=='SINGLE_FAIL_RECORD'


def test_new_run_first_250_then_500_is_the_first_off_pair():
    core=dict(rule='OBSERVE',changes={},next_segment='UNCHANGED',notes=[],triggered=[])
    a=audit(250);a['off_cells']['map/fwd0.5']['survival']=59
    try:d=apply_approved(core,a,None,None,{'last_change':None},None,effective_from=250)
    except ValueError:d=None
    assert d is not None, 'new run activation 250 must be supported'
    assert d['rule']=='OBSERVE' and d['map_off_survival']['state']=='SINGLE_FAIL_RECORD'
    assert 'de8_counterfactual' not in d
    b=audit(500);b['off_cells']['map/fwd0.5']['survival']=59
    d=apply_approved(core,b,a,None,{'last_change':None},None,effective_from=250)
    assert d['rule']=='OFF_SURVIVAL_ROLLBACK'
    with pytest.raises(ValueError):apply_approved(core,b,a,None,{},None,effective_from=1)


