"""Known-answer a76e thresholds, including same-direction corroboration."""
from copy import deepcopy
import pytest

from boundary_demote import SPECS, evaluate


def snapshot(n, value=.8):
    s=dict(iteration=n,errors=[],provenance_errors=[],metrics={},fingerprints={},
           checkpoint_sha256=f'{n:064x}',plan_sha256='a'*64,score_config_sha256='b'*64,
           sources={},audit=dict(errors=[],off_cells={}))
    for spec in SPECS:
        for mode in ('eval_gt','eval_pred','probe_prop_only'):
            key=spec.key(mode)
            s['metrics'][key]=value if spec.direction=='higher' else .1
            s['fingerprints'][key]=dict(seed=42,envs=64,steps=300,mesh='c'*64,
                assignment='d'*64,level=spec.level,case=spec.case,dr_off=True)
    from boundary_demote import OFF_KEYS
    for key in OFF_KEYS:
        s['audit']['off_cells'][key]=dict(valid=64,survival=64,
                                          fingerprint=dict(seed=42,mesh='c'*64))
    return s


def cell(report, spec):
    return next(r for r in report['cells'] if r['cell']==spec.cell)


@pytest.mark.parametrize('spec', SPECS, ids=lambda s:s.cell)
@pytest.mark.parametrize('offset,expected',[(-.000001,'KEEP'),(0,'DEMOTE'),(.000001,'DEMOTE')])
def test_each_threshold_below_equal_above(spec,offset,expected):
    old=snapshot(250);now=snapshot(500)
    sign=-1 if spec.direction=='higher' else 1
    now['metrics'][spec.key('eval_gt')]+=sign*(spec.threshold+offset)
    # PRED corroborates the direction, but need not cross the full threshold.
    now['metrics'][spec.key('eval_pred')]+=sign*spec.threshold/4
    result=evaluate(now,[old])
    r=cell(result,spec)
    assert r['state']==expected
    assert r['eval_gt']['adverse_delta']==pytest.approx(spec.threshold+offset)
    assert r['eval_pred']['threshold_crossed'] is False


@pytest.mark.parametrize('bad_mode',['eval_gt','eval_pred'])
def test_one_mode_alone_without_same_direction_is_recorded_not_demoted(bad_mode):
    spec=SPECS[0];old=snapshot(250);now=snapshot(500)
    other='eval_pred' if bad_mode=='eval_gt' else 'eval_gt'
    now['metrics'][spec.key(bad_mode)]=.6
    for other_value in (.8,.9):
        now['metrics'][spec.key(other)]=other_value
        r=cell(evaluate(now,[old]),spec)
        assert r['state']=='ONE_MODE_DROP'
        assert r[bad_mode]['threshold_crossed'] is True
        assert not r['same_direction']


def test_all_past_boundaries_and_separate_best_iterations_not_previous_only():
    spec=SPECS[0];a,b,c,d=[snapshot(n) for n in (250,500,750,1000)]
    a['metrics'][spec.key('eval_gt')]=.95
    b['metrics'][spec.key('eval_pred')]=.93
    c['metrics'][spec.key('eval_gt')]=.79
    d['metrics'][spec.key('eval_gt')]=.81  # Better than previous, below the old best.
    r=cell(evaluate(d,[c,a,b]),spec)
    assert r['state']=='DEMOTE'
    assert r['eval_gt']['best_iteration']==250
    assert r['eval_pred']['best_iteration']==500
    assert r['eval_gt']['previous_delta']==pytest.approx(.02)
    assert r['eval_gt']['adverse_delta']==pytest.approx(.14)


def test_first_boundary_excludes_parent_and_future():
    p=snapshot(0,1.5);s=snapshot(250,.1)
    result=evaluate(s,[p])
    assert result['state']=='BASELINE_ONLY'
    assert not result['demoted_cells']
    assert all(r['state']=='FIRST_BOUNDARY' for r in result['cells'])
    assert evaluate(s,[snapshot(500)])['state']=='HOLD'


@pytest.mark.parametrize('fault',['missing','duplicate','NaN','seed','mesh','plan','checkpoint','audit','raw','PRED'])
def test_missing_or_unverified_history_is_not_skipped(fault):
    a,b,c=[snapshot(n) for n in (250,500,750)];spec=SPECS[0]
    if fault=='missing': history=[b]
    else:
        history=[a,b]
        if fault=='duplicate':history.append(deepcopy(a))
        if fault=='NaN':a['metrics'][spec.key('eval_gt')]=float('nan')
        if fault in ('seed','mesh'):a['fingerprints'][spec.key('eval_gt')][fault]='foreign'
        if fault=='plan':a['plan_sha256']='f'*64
        if fault=='checkpoint':a['provenance_errors'].append('wrong checkpoint')
        if fault=='audit':a['audit']['errors'].append('wrong P1 pin')
        if fault=='raw':a['errors'].append('bad raw')
        if fault=='PRED':del a['metrics'][spec.key('eval_pred')]
    result=evaluate(c,history)
    assert result['state']=='HOLD'
    assert cell(result,spec)['state']=='HOLD'
    assert not result['demoted_cells']


def test_yaw_best_means_minimum_error_and_current_can_set_new_best():
    spec=next(s for s in SPECS if s.cell=='yaw/L2/fwd1.0/p90_abs_rad')
    a,b,c=[snapshot(n) for n in (250,500,750)]
    for mode in ('eval_gt','eval_pred'):
        a['metrics'][spec.key(mode)]=.07
        b['metrics'][spec.key(mode)]=.15
        c['metrics'][spec.key(mode)]=.13
    r=cell(evaluate(c,[a,b]),spec)
    assert r['state']=='DEMOTE' and r['eval_gt']['best_iteration']==250
    assert r['eval_gt']['adverse_delta']==pytest.approx(.06)
    for mode in ('eval_gt','eval_pred'):c['metrics'][spec.key(mode)]=.05
    r=cell(evaluate(c,[a,b]),spec)
    assert r['state']=='KEEP' and r['eval_gt']['best_iteration']==750


def test_off_survival_sixty_inclusive_and_same_cell_twice():
    from boundary_demote import OFF_KEYS
    a,b=[snapshot(n) for n in (250,500)];key=OFF_KEYS[0]
    b['audit']['off_cells'][key]['survival']=60
    assert evaluate(b,[a])['map_off_survival']['state']=='PASS'
    b['audit']['off_cells'][key]['survival']=59
    assert evaluate(b,[a])['map_off_survival']['state']=='SINGLE_FAIL_RECORD'
    a['audit']['off_cells'][key]['survival']=59
    result=evaluate(b,[a])
    assert result['map_off_survival']['state']=='ROLLBACK'
    assert result['map_off_survival']['rollback_cells']==[key]
    assert result['apply_ready'] is False
    del b['audit']['off_cells'][key]
    assert evaluate(b,[a])['map_off_survival']['state']=='HOLD'


def test_fixed_cell_coverage_and_thresholds():
    assert len(SPECS)==18 and len({s.cell for s in SPECS})==18
    assert {s.threshold for s in SPECS if s.case=='fwd0.1'}=={.10}
    assert {s.threshold for s in SPECS if s.case=='fwd0.2'}=={.02}
    assert {s.threshold for s in SPECS if '0.2' in s.case and s.case.startswith('side')}=={.03}
    assert {s.threshold for s in SPECS if '0.4' in s.case}=={.04}
    assert {s.threshold for s in SPECS if '0.5' in s.case and s.case.startswith('side')}=={.02}
    assert {(s.case,s.metric,s.threshold) for s in SPECS if s.suite=='yaw'}=={
        ('fwd0.5','median_abs_rad',.02),('fwd0.5','p90_abs_rad',.05),
        ('fwd1.0','median_abs_rad',.03),('fwd1.0','p90_abs_rad',.06)}
