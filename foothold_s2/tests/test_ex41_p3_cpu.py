"""D101 observation only; D130 permits no automatic mirror activation."""
import json
import hashlib
import pytest
from foothold_s2.curriculum import w72
from foothold_s2.tests.test_ex41_fixed_cpu import fixture,counts
from foothold_s2.tests.test_ex41_runtime_cpu import score
from foothold_s2.tests.ex41_runtime_fixture import commit_inputs
from foothold_s2.tests.test_ex41_symmetry_cpu import known_bundle
from foothold_s2.curriculum.ex41_symmetry import pair
from foothold_s2 import ex41_score_watch

STAGE_BY_END = {750:'S2a',1750:'S2b',2750:'S2c',4000:'S2d',4500:'S2e',
                5000:'T0_prime',5500:'T0_prime'}


def measured(r,n,ratio):
    bundle=known_bundle()
    for mode in bundle['modes'].values():
        for key in mode:mode[key]=pair(1.,1.)
    bundle['modes']['eval_gt']['map64/side']=pair(ratio,1.)
    score(r,n,metrics={'maintenance_counts':counts(r),'stand_min_passed':64,'critic_mirror_symmetry':bundle})


def _stage_end_report(run_dir, root, iteration, ratio, *, valid=True):
    bundle=known_bundle()
    for mode in bundle['modes'].values():
        for key in mode:mode[key]=pair(1.,1.)
    bundle['modes']['eval_gt']['map64/side']=pair(ratio,1.)
    if not valid:bundle['modes']['eval_gt']['map64/side']['symmetry']=None
    cp_sha=f'{iteration:064x}'
    row={'format':'foothold-ex41-stage-end-auxiliary/1','iteration':iteration,
         'checkpoint_sha256':cp_sha,'stage_id':STAGE_BY_END[iteration],'state':'complete',
         'p3_symmetry_report':{'format':'foothold-ex41-p3-stage-end/1','state':'complete',
             'checkpoint_iteration':iteration,'checkpoint_sha256':cp_sha,'source':'stage_end_w78',
             'metrics':bundle}}
    sidecar=root/f'stage_end_auxiliary_{iteration}.json'
    sidecar.write_text(json.dumps(row,allow_nan=False),encoding='utf-8')
    ex41_score_watch._publish_stage_end_report(run_dir,sidecar,deliver=False)
    return sidecar


@pytest.mark.parametrize('ratios,expected',[( (.79,.7),True),((.8,.7),False),((.79,.85),False)])
def test_two_stage_end_sidecars_drive_p3_observation_only(tmp_path,ratios,expected):
    r,consumer=fixture(tmp_path);r.on_update_start(1)
    root=tmp_path/'sidecars';root.mkdir()
    _stage_end_report(r.log_dir,root,750,ratios[0])
    _stage_end_report(r.log_dir,root,1750,ratios[1])
    r._record_mirror_observation(2001,None)
    rows=[json.loads(x) for x in (r.log_dir/'stage_log.jsonl').read_text().splitlines()]
    events=[x for x in rows if x['event']=='critic_mirror_observation']
    assert events[-1]['observations'][-1]['iteration']==1750
    assert events[-1]['condition_met'] is expected
    assert events[-1]['automatic_activation'] is False
    assert not r.effective['critic_mirror'] and not consumer.ex41_critic_mirror


def test_p3_sidecar_report_is_linked_and_delivered_through_existing_channels(tmp_path, monkeypatch):
    monkeypatch.setenv("EX41_ALLOW_EXTERNAL_ALERT_DELIVERY", "1")
    from foothold_s2.ex41_ops import deliver_pending_alerts
    run=tmp_path/'run';run.mkdir();root=tmp_path/'sidecars';root.mkdir()
    _stage_end_report(run,root,750,.5)
    sent=[]
    receipts=deliver_pending_alerts(run,
        orchestration_sender=lambda subject,body:sent.append(('orca',subject,body)) or True,
        telegram_sender=lambda body:sent.append(('telegram',body)) or True)
    assert len(receipts)==1 and len(sent)==2
    assert 'stage-end report' in sent[0][1].lower()
    assert 'stage-end w57/w78 report' in sent[0][2].lower()
    assert 'p3 metrics recorded' in sent[1][1].lower()
    alert=json.loads((run/'ex41_reports/alerts.jsonl').read_text().splitlines()[0])
    assert alert['kind']=='stage_end_auxiliary_report'
    assert alert['p3_state']=='complete' and alert['report_sha256']


def test_manual_mirror_needs_new_committed_approval_before_setter(tmp_path):
    r,consumer=fixture(tmp_path);r.on_update_start(1)
    snapshot=w72.read_committed_pair(r.plan.boundary_path,r.plan.approvals_path)
    snapshot['config']['values']['critic_mirror']=True
    # The pinned approvals now include this field; remove it to model the
    # intended missing-approval counterexample before adding a fresh approval.
    snapshot['approvals']['fields'].pop('critic_mirror', None)
    commit_inputs(r,snapshot);r.on_update_start(251)
    assert not consumer.ex41_critic_mirror and not r.effective['critic_mirror']
    snapshot['approvals']['fields']['critic_mirror']={'decision_id':'CPU-MANUAL-ONLY','choices':[False,True]}
    commit_inputs(r,snapshot);r.on_update_start(501)
    assert consumer.ex41_critic_mirror and r.effective['critic_mirror']
    receipt=r.boundary_receipt()
    assert receipt['status']=='applied' and receipt['readback']['authorization']['gate']=='W72'
    assert receipt['readback']['authorization']['approval_sha256']==hashlib.sha256(r.plan.approvals_path.read_bytes()).hexdigest()


def test_core_score_field_cannot_replace_missing_stage_end_sidecars(tmp_path):
    r,consumer=fixture(tmp_path);r.on_update_start(1)
    measured(r,250,.5);r.on_update_start(251)
    rows=[json.loads(x) for x in (r.log_dir/'stage_log.jsonl').read_text().splitlines()]
    event=[x for x in rows if x['event']=='critic_mirror_observation'][-1]
    assert event['observations']==[] and not event['condition_met']
    assert not r.effective['critic_mirror'] and not consumer.ex41_critic_mirror


def test_delayed_stage_end_sidecar_is_fresh_by_checkpoint_identity(tmp_path):
    r,_=fixture(tmp_path);r.on_update_start(1)
    root=tmp_path/'sidecars';root.mkdir()
    _stage_end_report(r.log_dir,root,750,.5)
    _stage_end_report(r.log_dir,root,1750,.5)
    r._record_mirror_observation(5001,None)
    rows=[json.loads(x) for x in (r.log_dir/'stage_log.jsonl').read_text().splitlines()]
    event=[x for x in rows if x['event']=='critic_mirror_observation'][-1]
    assert event['fresh'] is True and event['new_score'] is True
    assert event['matching_pair_ids']==['map64/side']


def test_different_bad_pairs_or_record_only_mode_do_not_trigger(tmp_path):
    r,consumer=fixture(tmp_path);r.on_update_start(1)
    root=tmp_path/'sidecars';root.mkdir()
    _stage_end_report(r.log_dir,root,750,.5)
    _stage_end_report(r.log_dir,root,1750,.5,valid=False)
    r._record_mirror_observation(2001,None)
    rows=[json.loads(x) for x in (r.log_dir/'stage_log.jsonl').read_text().splitlines()]
    event=[x for x in rows if x['event']=='critic_mirror_observation'][-1]
    assert not event['condition_met'] and not event['matching_pair_ids']
    assert event['hold_reason']=='latest_stage_end_invalid:p3_metrics_invalid'
    assert not r.effective['critic_mirror'] and not consumer.ex41_critic_mirror


def test_latest_2750_sidecar_sha_mismatch_holds_instead_of_falling_back(tmp_path):
    r,consumer=fixture(tmp_path);r.on_update_start(1)
    root=tmp_path/'sidecars';root.mkdir()
    _stage_end_report(r.log_dir,root,750,.5)
    _stage_end_report(r.log_dir,root,1750,.5)
    latest=_stage_end_report(r.log_dir,root,2750,.5)
    latest.write_text(latest.read_text(encoding='utf-8')+' ',encoding='utf-8')

    r._record_mirror_observation(3001,None)

    rows=[json.loads(x) for x in (r.log_dir/'stage_log.jsonl').read_text().splitlines()]
    event=[x for x in rows if x['event']=='critic_mirror_observation'][-1]
    assert event['condition_met'] is False
    assert event['hold_reason']=='latest_stage_end_invalid:sidecar_sha256_mismatch'
    assert event['observations'][-1]['iteration']==2750
    alert=json.loads((r.log_dir/'ex41_reports'/'alerts.jsonl').read_text().splitlines()[-1])
    assert alert['kind']=='p3_stage_end_observation_hold'
    assert alert['reason']==event['hold_reason']
    assert not consumer.ex41_critic_mirror


def test_missing_s2b_blocks_nonadjacent_s2a_s2c_comparison(tmp_path):
    r,consumer=fixture(tmp_path);r.on_update_start(1)
    root=tmp_path/'sidecars';root.mkdir()
    _stage_end_report(r.log_dir,root,750,.5)
    _stage_end_report(r.log_dir,root,2750,.5)

    r._record_mirror_observation(3001,None)

    rows=[json.loads(x) for x in (r.log_dir/'stage_log.jsonl').read_text().splitlines()]
    event=[x for x in rows if x['event']=='critic_mirror_observation'][-1]
    assert event['condition_met'] is False
    assert event['hold_reason']=='stage_end_records_not_adjacent'
    alert=json.loads((r.log_dir/'ex41_reports'/'alerts.jsonl').read_text().splitlines()[-1])
    assert alert['kind']=='p3_stage_end_observation_hold'
    assert alert['reason']==event['hold_reason']
    assert not consumer.ex41_critic_mirror


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
    assert not candidates
    state=r.state_dict();assert state['last_mirror_observed_score'] is None
    other=make_runtime(load_plan(r.plan.path,arm='B'),4,'cpu',tmp_path/'b',segment_index=1)
    attach_consumer(other);other.load_state_dict(state)
    assert other._last_mirror_observed_score is None
