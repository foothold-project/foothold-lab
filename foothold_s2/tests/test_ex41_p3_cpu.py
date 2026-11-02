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


def measured(r,n,ratio):
    score(r,n,metrics={'maintenance_counts':counts(r),'stand_min_passed':64,'w78_min_lr_ratio':ratio})


@pytest.mark.parametrize('ratios,expected',[( (.79,.7),True),((.8,.7),False),((.79,.85),False),((.79,float('nan')),False)])
def test_two_distinct_scores_record_condition_but_never_enable(tmp_path,ratios,expected):
    r,consumer=fixture(tmp_path);r.on_update_start(1)
    measured(r,250,ratios[0]);r.on_update_start(251)
    measured(r,500,ratios[1]);r.on_update_start(501)
    rows=[json.loads(x) for x in (r.log_dir/'stage_log.jsonl').read_text().splitlines()]
    events=[x for x in rows if x['event']=='critic_mirror_observation']
    assert [x['iteration'] for x in events]==[1,251,501]
    assert events[-1]['condition_met'] is expected
    assert events[-1]['automatic_activation'] is False
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
    prev={'iteration':250,'metrics':{'w78_min_lr_ratio':.4}}
    current={'iteration':500,'metrics':{'w78_min_lr_ratio':.5}}
    r=SimpleNamespace(clock=SimpleNamespace(settings={'interval_updates':250}),_history=[prev,current],
        _score_rejections={'bad':{'iteration':250}},plan=SimpleNamespace(automatic={'critic_both_fail_fraction':.8}),
        effective={'critic_mirror':False},_write=rows.append)
    EX41FixedRuntime._record_mirror_observation(r,501,current)
    assert not rows[-1]['condition_met']
    r._score_rejections={}
    EX41FixedRuntime._record_mirror_observation(r,501,None)
    assert not rows[-1]['condition_met']
    current['iteration']=1250;prev['iteration']=1000
    EX41FixedRuntime._record_mirror_observation(r,1251,current)
    assert not rows[-1]['within_first1000'] and not rows[-1]['condition_met']
