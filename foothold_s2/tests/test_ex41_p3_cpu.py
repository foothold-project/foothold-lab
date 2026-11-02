"""D101 observation only; D130 permits no automatic mirror activation."""
import json
import hashlib
import pytest
from foothold_s2.curriculum import w72
from foothold_s2.tests.test_ex41_fixed_cpu import fixture,counts
from foothold_s2.tests.test_ex41_runtime_cpu import score
from foothold_s2.tests.ex41_runtime_fixture import commit_inputs
from foothold_s2.curriculum.ex41_fixed import EX41FixedRuntime
from types import SimpleNamespace
from foothold_s2.tests.test_ex41_symmetry_cpu import known_bundle
from foothold_s2.curriculum.ex41_symmetry import pair


def measured(r,n,ratio):
    bundle=known_bundle()
    for mode in bundle['modes'].values():
        for key in mode:mode[key]=pair(1.,1.)
    bundle['modes']['eval_gt']['map64/side']=pair(ratio,1.)
    score(r,n,metrics={'maintenance_counts':counts(r),'stand_min_passed':64,'critic_mirror_symmetry':bundle})


@pytest.mark.parametrize('ratios,expected',[( (.79,.7),True),((.8,.7),False),((.79,.85),False),((-.1,.7),True)])
def test_two_distinct_scores_record_condition_but_never_enable(tmp_path,ratios,expected):
    r,consumer=fixture(tmp_path);r.on_update_start(1)
    measured(r,250,ratios[0]);r.on_update_start(251)
    measured(r,500,ratios[1]);r.on_update_start(501)
    rows=[json.loads(x) for x in (r.log_dir/'stage_log.jsonl').read_text().splitlines()]
    events=[x for x in rows if x['event']=='critic_mirror_observation']
    assert [x['iteration'] for x in events]==[1,251,501]
    assert events[-1]['condition_met'] is expected
    assert events[-1]['automatic_activation'] is False
    assert len([x for x in rows if x['event']=='critic_mirror_candidate'])==int(expected)
    assert not r.effective['critic_mirror'] and not consumer.ex41_critic_mirror


def test_manual_mirror_needs_new_committed_approval_before_setter(tmp_path):
    r,consumer=fixture(tmp_path);r.on_update_start(1)
    snapshot=w72.read_committed_pair(r.plan.boundary_path,r.plan.approvals_path)
    snapshot['config']['values']['critic_mirror']=True
    commit_inputs(r,snapshot);r.on_update_start(251)
    assert not consumer.ex41_critic_mirror and not r.effective['critic_mirror']
    snapshot['approvals']['fields']['critic_mirror']={'decision_id':'CPU-MANUAL-ONLY','choices':[False,True]}
    commit_inputs(r,snapshot);r.on_update_start(501)
    assert consumer.ex41_critic_mirror and r.effective['critic_mirror']
    receipt=r.boundary_receipt()
    assert receipt['status']=='applied' and receipt['readback']['authorization']['gate']=='W72'
    assert receipt['readback']['authorization']['approval_sha256']==hashlib.sha256(r.plan.approvals_path.read_bytes()).hexdigest()


def test_observer_rejects_invalid_previous_and_late_or_reused_score():
    rows=[]
    prev={'iteration':250,'metrics':{'critic_mirror_symmetry':known_bundle(.4,1.)}}
    current={'iteration':500,'metrics':{'critic_mirror_symmetry':known_bundle(.5,1.)}}
    r=SimpleNamespace(clock=SimpleNamespace(settings={'interval_updates':250}),_history=[prev,current],
        _score_rejections={'bad':{'iteration':250}},plan=SimpleNamespace(automatic={'critic_both_fail_fraction':.8},gate_cfg={'maximum_score_age':500}),
        effective={'critic_mirror':False},_write=rows.append)
    EX41FixedRuntime._record_mirror_observation(r,501,current)
    assert not rows[-1]['condition_met']
    r._score_rejections={}
    EX41FixedRuntime._record_mirror_observation(r,501,None)
    assert not rows[-1]['condition_met']
    current['iteration']=1250;prev['iteration']=1000
    EX41FixedRuntime._record_mirror_observation(r,1251,current)
    assert rows[-1]['condition_met']  # latest 19:3x rule has no first-1000 cutoff
    EX41FixedRuntime._record_mirror_observation(r,1501,current)
    assert rows[-1]['fresh'] and not rows[-1]['new_score'] and not rows[-1]['condition_met']
    EX41FixedRuntime._record_mirror_observation(r,1751,current)
    assert not rows[-1]['fresh'] and not rows[-1]['condition_met']


def test_different_bad_pairs_or_record_only_mode_do_not_trigger():
    rows=[];a=known_bundle(1.,1.);b=known_bundle(1.,1.)
    a['modes']['eval_gt']['map64/side']=pair(.5,1.)
    b['modes']['eval_gt']['map64/spin']=pair(.5,1.)
    for x in (a,b):x['modes']['eval_pred']['map64/side']=pair(.1,1.)
    prev={'iteration':250,'metrics':{'critic_mirror_symmetry':a}}
    current={'iteration':500,'metrics':{'critic_mirror_symmetry':b}}
    r=SimpleNamespace(clock=SimpleNamespace(settings={'interval_updates':250}),_history=[prev,current],
        _score_rejections={},plan=SimpleNamespace(automatic={'critic_both_fail_fraction':.8},gate_cfg={'maximum_score_age':500}),
        effective={'critic_mirror':False},_write=rows.append)
    EX41FixedRuntime._record_mirror_observation(r,501,current)
    assert not rows[-1]['condition_met'] and not rows[-1]['matching_pair_ids']
    b['modes']['eval_gt']['map64/side']=pair(.6,1.)
    r._last_mirror_observed_score=None
    EX41FixedRuntime._record_mirror_observation(r,501,current)
    assert rows[-1]['event']=='critic_mirror_candidate' and rows[-1]['matching_pair_ids']==['map64/side']


def test_latest_nan_pair_rejected_by_actual_json_reader(tmp_path):
    r,consumer=fixture(tmp_path);r.on_update_start(1)
    measured(r,250,.5);r.on_update_start(251)
    bundle=known_bundle(.5,1.)
    bundle['modes']['eval_gt']['map64/side']['symmetry']=float('nan')
    score(r,500,metrics={'maintenance_counts':counts(r),'stand_min_passed':64,'critic_mirror_symmetry':bundle})
    r.on_update_start(501)
    rows=[json.loads(x) for x in (r.log_dir/'stage_log.jsonl').read_text().splitlines()]
    assert not [x for x in rows if x['event']=='critic_mirror_candidate']
    assert r._score_rejections and not consumer.ex41_critic_mirror


def test_shadow_evaluation_one_boundary_late_and_resume_dedup(tmp_path):
    from foothold_s2.curriculum.continuous import load_plan,make_runtime
    from foothold_s2.tests.ex41_runtime_fixture import attach_consumer
    r,_=fixture(tmp_path/'a');r.on_update_start(1);r.on_update_start(251)
    measured(r,250,.5);r.on_update_start(501)
    measured(r,500,.6);r.on_update_start(751)
    rows=[json.loads(x) for x in (r.log_dir/'stage_log.jsonl').read_text().splitlines()]
    candidates=[x for x in rows if x['event']=='critic_mirror_candidate']
    assert len(candidates)==1 and candidates[0]['iteration']==751
    state=r.state_dict();assert state['last_mirror_observed_score']==500
    other=make_runtime(load_plan(r.plan.path,arm='B'),4,'cpu',tmp_path/'b',segment_index=1)
    attach_consumer(other);other.load_state_dict(state)
    assert other._last_mirror_observed_score==500
