"""Known-answer rule tests, not tests of the report's phrasing."""
from copy import deepcopy
import pytest
from boundary_rules import decide

REWARDS = dict(track_lin_vel_std=.35, track_ang_vel_std=.5, feet_air_time=0.,
    foot_slip=-.15, zero_yaw=-1., feet_air_time_threshold=.5, slow_track=0.,
    slow_track_sigma=.5, slow_track_speed_min=.1, slow_track_speed_max=.3)

def snapshot(iteration=250, low=.9, yaw=.03):
    m={}
    for mode in ('eval_gt','eval_pred','probe_prop_only'):
        for level in (0,5):
            for case in ('fwd0.1','fwd0.2','side+0.4','side-0.4'):
                m[f'low/L{level}/{mode}/{case}/R']=low if case.startswith('fwd') else .9
        for case in ('side+0.5','side-0.5'):
            m[f'map/mixed012/{mode}/{case}/R']=.9
        for case in ('spin+1.2','spin-1.2'):
            m[f'map/mixed012/{mode}/{case}/yaw_follow']=.9
        for case in ('fwd0.5','fwd1.0'):
            m[f'yaw/L2/{mode}/{case}/median_abs_rad']=yaw
            m[f'yaw/L2/{mode}/{case}/p90_abs_rad']=yaw*2
        m[f'stand/flat/{mode}/stand/success']=64
        m[f'map/mixed012/{mode}/stop/speed_median_mps']=.01
        m[f'map/mixed012/{mode}/stop/yaw_speed_median_radps']=.01
    return dict(iteration=iteration, metrics=m, maintenance='PASS', errors=[],
                comparable=True, repeats={}, overall='FAIL')

def treatment(at=None, before=0., after=0.):
    current={**REWARDS,'slow_track':after}
    last=None if at is None else dict(iteration=at,before={**REWARDS,'slow_track':before},
                                    after=current,fields=['slow_track'])
    return dict(current=current,last_change=last,r6_activated_at=at,r6_raised=after==.3,
                errors=[],history=[])

def test_parent_graduation_fail_is_not_r4_and_r6_beats_r2():
    now=snapshot(low=.11,yaw=.3)
    out=decide(now,snapshot(0),treatment=treatment())
    assert out['rule']=='R6'
    assert out['changes']=={'slow_track':.2}
    assert {'R2','R3'} <= set(out['triggered'])

def test_r4_maintenance_hold_wins_over_slow_and_yaw():
    now=snapshot(low=.1,yaw=.3);now['maintenance']='HOLD'
    out=decide(now,snapshot(0),treatment=treatment())
    assert out['rule']=='R4' and out['next_segment']=='DO_NOT_START'

def test_missing_or_nan_never_looks_like_a_safe_nontrigger():
    for value in (None,float('nan')):
        now=snapshot();now['metrics']['low/L5/eval_gt/fwd0.2/R']=value
        out=decide(now,snapshot(0),treatment=treatment())
        assert out['rule']=='EVIDENCE_HOLD' and not out['changes']

def test_new_r5_cannot_be_old_low_ratio_trigger():
    now=snapshot(750,low=.01)
    out=decide(now,snapshot(0),snapshot(500,low=.01),snapshot(250,low=.01),treatment=treatment())
    assert out['changes']=={'slow_track':.2}

def test_r2_changes_only_zero_yaw_when_r6_not_needed():
    out=decide(snapshot(yaw=.3),snapshot(0),treatment=treatment())
    assert out['rule']=='R2' and out['changes']=={'zero_yaw':-1.25}

def test_one_improving_low_cell_prevents_r6_raise():
    parent=snapshot(0); anchor=snapshot(250,low=.1)
    now=snapshot(500,low=.1);now['metrics']['low/L5/eval_gt/fwd0.2/R']=.2
    out=decide(now,parent,anchor,treatment=treatment(250,0,.2))
    assert out['rule']=='OBSERVE' and out['changes']=={}

def test_all_four_nonincreasing_raises_only_once():
    anchor=snapshot(250,low=.25);now=snapshot(500,low=.1)
    out=decide(now,snapshot(0),anchor,treatment=treatment(250,0,.2))
    assert out['rule']=='R6_RAISE' and out['changes']=={'slow_track':.3}
    out=decide(snapshot(750,low=.05),snapshot(0),now,anchor,treatment=treatment(500,.2,.3))
    assert out['changes'].get('slow_track',.3)<=.3

def test_two_same_components_against_fixed_anchor_roll_back_last_value():
    anchor=snapshot(250);first=snapshot(500);second=snapshot(750)
    key='map/mixed012/eval_gt/spin+1.2/yaw_follow'
    first['metrics'][key]=.80;second['metrics'][key]=.82
    t=treatment(250,0,.2);t['anchor']=anchor
    out=decide(second,snapshot(0),first,anchor,treatment=t)
    assert out['rule']=='ROLLBACK' and out['changes']=={'slow_track':0.}

def test_different_cells_or_nonconsecutive_windows_do_not_roll_back():
    anchor=snapshot(250);first=snapshot(500);second=snapshot(750)
    first['metrics']['map/mixed012/eval_gt/spin+1.2/yaw_follow']=.8
    second['metrics']['map/mixed012/eval_gt/spin-1.2/yaw_follow']=.8
    t=treatment(250,0,.2);t['anchor']=anchor
    out=decide(second,snapshot(0),first,anchor,treatment=t)
    assert out['rule']=='OBSERVE' and out['changes']=={}
    first['iteration']=250
    second['metrics']['map/mixed012/eval_gt/spin+1.2/yaw_follow']=.8
    assert decide(second,snapshot(0),first,anchor,treatment=t)['rule']!='ROLLBACK'

def test_r5_requires_same_contact_raw_and_two_clean_windows():
    anchor=snapshot(250,low=.65);first=snapshot(500,low=.7);now=snapshot(750,low=.75)
    t=treatment(250,0,.2);t['anchor']=anchor
    out=decide(now,snapshot(0),first,anchor,treatment=t)
    assert out['rule']!='R5' and not out['changes']
    gait={'valid':True,'checkpoint_sha256':'fixture','contact_definition':'norm_Fxyz_gt_1N',
          'valid_conditions':True,'issues':[]}
    out=decide(now,snapshot(0),first,anchor,treatment=t,gait=gait)
    assert out['rule']=='R5'
    assert out['changes']=={'feet_air_time_threshold':.04,'feet_air_time':.1}

def test_zero_yaw_is_not_strengthened_repeatedly_past_approved_target():
    t=treatment();t['current']['zero_yaw']=-1.25
    out=decide(snapshot(yaw=.3),snapshot(0),treatment=t)
    assert out['changes']=={}

def test_near_threshold_requires_repeats_not_silent_rounding():
    now=snapshot();now['metrics']['low/L0/eval_gt/fwd0.1/R']=.299
    out=decide(now,snapshot(0),treatment=treatment())
    assert out['rule']=='REPEAT_REQUIRED' and out['changes']=={}
    for seed in ('7','13'):
        now['repeats'][seed]=deepcopy(now['metrics'])
    assert decide(now,snapshot(0),treatment=treatment())['rule']=='R6'

def test_invalid_previous_window_cannot_supply_second_regression():
    anchor=snapshot(250);first=snapshot(500);second=snapshot(750)
    key='map/mixed012/eval_gt/spin+1.2/yaw_follow'
    first['metrics'][key]=second['metrics'][key]=.8
    first['errors']=['checkpoint_sha_mismatch']
    t=treatment(250,0,.2);t['anchor']=anchor
    assert decide(second,snapshot(0),first,anchor,treatment=t)['rule']!='ROLLBACK'

def test_slow_track_can_start_after_two_clean_windows_of_prior_yaw_change():
    anchor=snapshot(250,low=.1);first=snapshot(500,low=.1);now=snapshot(750,low=.1)
    t=treatment();t['current']['zero_yaw']=-1.25
    t['last_change']=dict(iteration=250,before=REWARDS,after=t['current'],fields=['zero_yaw'])
    t['anchor']=anchor
    result=decide(now,snapshot(0),first,anchor,treatment=t)
    assert result['rule']=='R6' and result['changes']=={'slow_track':.2}

def test_raise_rejects_changed_prior_low_cell_conditions():
    prev=snapshot(250,low=.25);now=snapshot(500,low=.1)
    prev['fingerprints']={key:dict(mesh='old') for key in __import__('boundary_rules').LOW_KEYS}
    now['fingerprints']={key:dict(mesh='new') for key in __import__('boundary_rules').LOW_KEYS}
    assert decide(now,snapshot(0),prev,treatment=treatment(250,0,.2))['rule']=='EVIDENCE_HOLD'

def test_bad_anchor_or_previous_identity_cannot_drive_an_increase():
    anchor=snapshot(250,low=.25);now=snapshot(500,low=.1)
    anchor['errors']=['identity mismatch']
    out=decide(now,snapshot(0),anchor,treatment=treatment(250,0,.2))
    assert out['rule']=='EVIDENCE_HOLD' and not out['changes']
