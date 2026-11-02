"""Fixed5000 endpoints, pause/recovery/exhaustion and real committed runtime."""
import copy
import json
from pathlib import Path
import subprocess
import pytest
import yaml
from foothold_s2.curriculum.continuous import load_plan,make_runtime,sha256
from foothold_s2.curriculum.ex41_fixed import (Clock,CELLS,maintenance,baseline_counts,
    maintenance_cells,build_maintenance_counts)
from foothold_s2.tests.ex41_runtime_fixture import attach_consumer,commit_inputs
from foothold_s2.tests.test_ex41_runtime_cpu import score
from foothold_s2.runners.start_runner import curriculum_finished, curriculum_update_number

TABLE=Path(__file__).parents[1]/'curriculum/ex41-fixed5000.yaml'


def fixture(tmp,smoke=None):
    repo=tmp/'repo'; repo.mkdir(parents=True)
    doc=yaml.safe_load(TABLE.read_text())
    baseline={'checkpoint_iteration':6000,'checkpoint_sha256':doc['parent_sha256'],
              'cells':{k:{'alive_envs_at_end':64} for k in CELLS}}
    bp=repo/'baseline.json'; bp.write_text(json.dumps(baseline))
    doc['fixed_schedule']['maintenance_baseline']={'path':str(bp),'sha256':sha256(bp)}
    (repo/TABLE.name).write_text(yaml.safe_dump(doc))
    boundary=yaml.safe_load(TABLE.with_name(doc['boundary_file']).read_text())
    boundary['values']['w71_ready']=True
    approvals=yaml.safe_load(TABLE.with_name(doc['approval_file']).read_text())
    approvals['fields']['w71_ready']={'decision_id':'CPU-exact-consumer','choices':[False,True]}
    for name,data in ((doc['boundary_file'],boundary),(doc['approval_file'],approvals)):
        (repo/name).write_text(yaml.safe_dump(data),encoding='utf-8',newline='\n')
    def git(*a): return subprocess.check_output(['git','-C',str(repo),*a],stderr=subprocess.PIPE)
    git('init','-q');git('config','core.autocrlf','false');git('add','--','.')
    git('-c','user.name=CPU','-c','user.email=cpu@example.invalid','-c','commit.gpgsign=false','commit','-qm','fixed fixture')
    plan=load_plan(repo/TABLE.name,arm='B',smoke_boundaries=smoke)
    r=make_runtime(plan,4,'cpu',tmp/'run'); consumer=attach_consumer(r);r.start(plan.parent_sha256)
    return r,consumer


def counts(r,passed=64):
    return {k:{'passed':passed,'baseline_passed':v,'total':64} for k,v in r.baseline.items()}


def tick(r,n,*,failed=False,stand=64,stage_pass=False):
    c=counts(r)
    if failed: c[CELLS[-1]]['passed']=60
    score(r,n-1,passed=stage_pass,metrics={'maintenance_counts':c,'stand_min_passed':stand})
    r.on_update_start(n)


def test_actual_parent_baseline_has_all39_pinned_cells():
    p=load_plan(TABLE,arm='B');b=baseline_counts(p)
    assert len(b)==39 and p.parent_update==6000 and p.initial_dr_scale==.5
    assert p.fixed_schedule['duration_updates']==5000
    assert [s.id for s in p.stages]==['S2a','S2b','S2c','S2d','S2e','T0_prime']


def test_nominal_clock_endpoints_and_slopes():
    c=Clock()
    for n,expected in [(1,.5),(750,.5),(751,.5),(1751,.65),(2751,.8),(4001,1.),(5001,1.)]:
        assert c.scale(n)==pytest.approx(expected)
    assert c.scale(1751)-c.scale(1750)==pytest.approx(.15/1000)
    assert c.scale(4001)-c.scale(4000)==pytest.approx(.2/1250)


def test_any_cell_fails_exact_minus3_passes_and_missing_is_unknown():
    b={k:64 for k in CELLS};c={k:{'passed':61,'baseline_passed':64,'total':64} for k in CELLS}
    assert maintenance(c,b)==[]
    c[CELLS[-1]]['passed']=60;assert maintenance(c,b)==[CELLS[-1]]
    c.pop(CELLS[0]); assert maintenance(c,b) is None
    c={k:{'passed':64,'baseline_passed':63,'total':64} for k in CELLS}
    assert maintenance(c,b) is None


def test_pause_two_distinct_adjacent_recoveries_resume_same_slope():
    c=Clock();c.boundary(751,[],750)
    c.boundary(1001,['bad'],1000); scale=c.scale(1001)
    assert c.paused and c.scale(1251)==scale
    c.boundary(1251,[],1250);assert c.paused
    c.boundary(1501,[],1500);assert not c.paused and c.pause_used==500
    assert c.scale(1501)==scale
    assert c.scale(1751)-scale==pytest.approx(.15/4)
    assert c.position(1751)==1  # Stage end delayed by same 500 updates.


def test_reused_or_gapped_evidence_cannot_fake500_recovery():
    c=Clock();c.boundary(751,['bad'],750)
    c.boundary(1001,[],1000);c.boundary(1251,[],1000)
    assert c.paused and c.recovered==1
    c.boundary(1501,[],1500);assert c.paused


def test_pause_budget_freezes_dr_but_schedule_finishes():
    c=Clock();c.boundary(751,['bad'],750)
    for n in (1001,1251,1501,1751): event=c.boundary(n,['bad'],n-1)
    assert c.pause_used==1000 and not c.paused and c.frozen_scale==.5
    assert event=='dr_pause_budget_exhausted_frozen_report'
    assert c.scale(6001)==.5 and c.time(6001)==5000 and c.position(6001)==5


def test_runtime_fixed_stages_ignore_early_pass_or_newtask_failure(tmp_path):
    r,_=fixture(tmp_path);r.on_update_start(1)
    expected={751:'S2b',1751:'S2c',2751:'S2d',4001:'S2e',4501:'T0_prime'}
    for n in range(251,5002,250):
        tick(r,n,stage_pass=n<750)
        if n in expected: assert r.effective['stage_id']==expected[n]
    assert r.finished and not r.graduated and r.dr_scale(5001)==1.
    assert curriculum_finished(r)
    assert curriculum_update_number(r, 0) == 1
    assert curriculum_update_number(r, 6500) == 6501
    assert r._stage_baseline_sha==r.plan.parent_sha256


def test_start_runner_consumes_terminal_flag_before_next_rollout():
    source=(Path(__file__).parents[1]/"runners/start_runner.py").read_text(encoding="utf-8")
    boundary=source.index("continuous.on_update_start(curriculum_it)")
    stop=source.index("if curriculum_finished(continuous):",boundary)
    rollout=source.index("for step_k in range(self.num_steps_per_env):",stop)
    assert boundary < stop < rollout


def test_runtime_stand_halves_only_swing_once_no_pair_or_mirror(tmp_path):
    r,_=fixture(tmp_path)
    for n in (251,501): tick(r,n,stand=60)
    assert r.effective['reward_weights']['swing']==-5.
    assert r.effective['reward_weights']['zero_yaw']==-.5 and r.effective['reward_weights']['stumble']==-2.
    assert not r._pair_bias and not r._mirror_pending


def test_runtime_pause_and_resume_state_exact(tmp_path):
    r,_=fixture(tmp_path/'a'); tick(r,751,failed=True);tick(r,1001)
    state=r.state_dict()
    p=load_plan(r.plan.path,arm='B');b=make_runtime(p,4,'cpu',tmp_path/'b',segment_index=1)
    attach_consumer(b);b.load_state_dict(state)
    assert b.clock.__dict__==r.clock.__dict__
    for runtime in (r,b): tick(runtime,1251)
    assert b.clock.__dict__==r.clock.__dict__ and b.dr_scale(1501)==r.dr_scale(1501)
    assert not b.clock.paused and b.clock.pause_used==500


def test_fixed_smoke_five_boundaries_all_six_stages(tmp_path):
    r,_=fixture(tmp_path,smoke=(2,4,6,8,10))
    for n,name in zip((2,4,6,8,10),('S2b','S2c','S2d','S2e','T0_prime')):
        r.on_update_start(n);assert r.effective['stage_id']==name
    r.on_update_start(12);assert r.finished and not r.graduated


def test_invalid_config_does_not_hide_safety_score(tmp_path):
    r,_=fixture(tmp_path);r.on_update_start(1)
    p=score(r,250,metrics={'maintenance_counts':counts(r)})
    d=json.loads(p.read_text());d['safety_stop']=True;p.write_text(json.dumps(d))
    snap=copy.deepcopy(r._snapshot);snap['config']['values']['ppo']['clip_param']=.1
    commit_inputs(r,snap);r.on_update_start(251)
    assert r.stop_requested


def test_invalid_manual_config_cannot_hide_dr_hold_or_stop_fixed_schedule(tmp_path):
    r,_=fixture(tmp_path)
    snap=copy.deepcopy(r._snapshot);snap['config']['values']['ppo']['clip_param']=.1
    commit_inputs(r,snap);tick(r,751,failed=True)
    assert r.clock.paused and r.dr_scale(1001)==.5 and not r.stop_requested
    assert r.effective['stage_id']=='S2b' and 'clip_param' not in r.effective['ppo']
    rows=[json.loads(line) for line in (r.log_dir/'ex41_application.jsonl').read_text().splitlines()]
    assert any(row['status']=='rejected' for row in rows)


def test_full_runtime_exhaustion_finishes_without_fake_full_dr(tmp_path):
    r,_=fixture(tmp_path)
    for n in range(251,6002,250): tick(r,n,failed=True)
    assert r.finished and not r.stop_requested and r.clock.pause_used==1000
    assert r.effective['stage_id']=='T0_prime' and r.dr_scale(6001)==.5
    assert not r.clock.extension


def test_corrupted_saved_clock_rejected(tmp_path):
    r,_=fixture(tmp_path/'a');state=r.state_dict();state['fixed_clock']['frozen_scale']=float('nan')
    b=make_runtime(load_plan(r.plan.path,arm='B'),4,'cpu',tmp_path/'b',segment_index=1)
    attach_consumer(b)
    with pytest.raises(ValueError,match='clock frozen'): b.load_state_dict(state)


def test_d110_extension_exactly_once_full_dr_only(tmp_path):
    r,_=fixture(tmp_path)
    for n in range(251,4502,250):
        if n==4501: r._level_history=[(i,.1 if i<=4250 else .7) for i in range(4050,4501,50)]
        tick(r,n)
    assert r.clock.extension==500 and r.effective['stage_id']=='S2e'
    tick(r,4751);tick(r,5001);assert r.effective['stage_id']=='T0_prime' and not r.finished
    tick(r,5251);tick(r,5501);assert r.finished and r.clock.extension==500


def test_second_recovery_at_pause_cap_wins_over_freezing():
    c=Clock();c.boundary(751,['bad'],750)
    for n in (1001,1251): c.boundary(n,['bad'],n-1)
    c.boundary(1501,[],1500)
    event=c.boundary(1751,[],1750)
    assert event=='dr_resume_same_slope' and not c.paused
    assert c.pause_used==1000 and c.frozen_scale is None
    assert c.scale(2001)==pytest.approx(.5375)


def test_late_boundary_cannot_overrun_pause_accounting():
    c=Clock();c.boundary(751,['bad'],750)
    for n in (1001,1251,1501): c.boundary(n,['bad'],n-1)
    c.boundary(2001,['bad'],2000)
    assert c.pause_used==1000 and c.elapsed==1000 and c.anchor==2001
    assert c.frozen_scale==.5


def test_stale_score_does_not_count_as_current_window_and_warns_twice(tmp_path):
    r,_=fixture(tmp_path);tick(r,751,failed=True)
    r.on_update_start(1001);r.on_update_start(1251)
    rows=[json.loads(x) for x in (r.log_dir/'stage_log.jsonl').read_text().splitlines()]
    assert any(x['event']=='maintenance_evidence_missing_warning' and x['iteration']==1251 for x in rows)
    assert r.clock.recovered==0 and r.clock.paused


@pytest.mark.parametrize('key,value',[('last_score_iteration','1500'),('last_score_iteration',2000),('anchor',751),('anchor',2)])
def test_clock_resume_rejects_wrong_score_type_and_anchor(tmp_path,key,value):
    r,_=fixture(tmp_path/'a');tick(r,251);state=r.state_dict();state['fixed_clock'][key]=value
    b=make_runtime(load_plan(r.plan.path,arm='B'),4,'cpu',tmp_path/'b',segment_index=1)
    attach_consumer(b)
    with pytest.raises(ValueError,match='clock'):b.load_state_dict(state)


def test_stand_missing_reports_unknown_never_pass_default(tmp_path):
    r,_=fixture(tmp_path)
    score(r,250,metrics={'maintenance_counts':counts(r)});r.on_update_start(251)
    rows=[json.loads(x) for x in (r.log_dir/'stage_log.jsonl').read_text().splitlines()]
    assert any(x['event']=='stand_evidence_missing' for x in rows)
    assert r.effective['reward_weights']['swing']==-10.


def test_native_producer_actual_parent_contract_uses_alive_not_success():
    p=load_plan(TABLE,arm='B');b=baseline_counts(p)
    raw=json.loads(Path(p.fixed_schedule['maintenance_baseline']['path']).read_text(encoding='utf-8-sig'))
    c=build_maintenance_counts(raw,b,total_envs=64)
    assert len(c)==39 and maintenance(c,b)==[]
    for key in CELLS: assert c[key]['passed']==raw['cells'][key]['alive_envs_at_end']
    assert min(b.values())==60 and 'eval_pred/stop_record_only' in c
    # Deliberately conflicting pass count: it must never become survival.
    raw['cells'][CELLS[0]]={'alive_envs_at_end':60,'passed_envs':64}
    assert build_maintenance_counts(raw,b,total_envs=64)[CELLS[0]]['passed']==60
    raw['cells'][CELLS[0]]={'passed_envs':64}
    with pytest.raises(ValueError,match='alive_envs'):build_maintenance_counts(raw,b,total_envs=64)


@pytest.mark.parametrize('total',[63,64.0,True])
def test_native_producer_rejects_wrong_denominator(total):
    with pytest.raises(ValueError,match='64'):build_maintenance_counts({},dict.fromkeys(CELLS,64),total_envs=total)


def test_record_only_selection_26_or39_and_plan_hash(tmp_path):
    r,_=fixture(tmp_path);old_sha=r.plan.sha256
    doc=yaml.safe_load(r.plan.path.read_text());doc['fixed_schedule']['include_record_only']=False
    r.plan.path.write_text(yaml.safe_dump(doc))
    p=load_plan(r.plan.path,arm='B');b=baseline_counts(p)
    assert p.sha256!=old_sha and len(b)==26 and tuple(b)==maintenance_cells(False)
    raw={'cells':{k:{'alive_envs_at_end':64} for k in CELLS}}
    raw['cells']['eval_pred/stop_record_only']['alive_envs_at_end']=0
    assert maintenance(build_maintenance_counts(raw,b,total_envs=64),b)==[]
    with pytest.raises(ValueError,match='bool'):maintenance_cells(1)


def test_stage_change_retains_audit_history_but_not_stale_recovery(tmp_path):
    r,_=fixture(tmp_path);tick(r,751,failed=True)
    assert r.effective['stage_id']=='S2b' and [s['iteration'] for s in r._history]==[750]
    r.on_update_start(1001)
    assert r.clock.recovered==0 and r._missing_maintenance_boundaries==1


def test_rejected_apply_accounts_time_and_resume_is_valid(tmp_path,monkeypatch):
    r,_=fixture(tmp_path/'a');tick(r,751,failed=True)
    for n in (1001,1251):tick(r,n,failed=True)
    original=r._apply
    monkeypatch.setattr(r,'_apply',lambda *a,**k:False)
    tick(r,1501,failed=True)
    assert r.clock.anchor==1501 and r.clock.pause_used==750
    monkeypatch.setattr(r,'_apply',original);tick(r,1751,failed=True)
    assert r.clock.pause_used==1000
    b=make_runtime(load_plan(r.plan.path,arm='B'),4,'cpu',tmp_path/'b',segment_index=1)
    attach_consumer(b);b.load_state_dict(r.state_dict())
    assert b.clock.__dict__==r.clock.__dict__


@pytest.mark.parametrize('safety_at_end',[False,True])
def test_hold1000_plus_extension500_finishes_at6501(tmp_path,safety_at_end):
    r,_=fixture(tmp_path)
    for n in range(251,6502,250):
        if n==5501:
            assert r.stage_entry_iteration==5001
            r._level_history=[(i,.1 if i<=5250 else .7) for i in range(5050,5501,50)]
        if safety_at_end and n==6501:
            p=score(r,n-1,metrics={'maintenance_counts':counts(r),'stand_min_passed':64})
            data=json.loads(p.read_text());data['safety_stop']=True;p.write_text(json.dumps(data))
            r.on_update_start(n)
        else:tick(r,n,failed=n in (751,1751))
        if n<6501:assert not r.finished
    assert r.finished is not safety_at_end and r.stop_requested is safety_at_end
    assert r.clock.pause_used==1000 and r.clock.extension==500
    assert r.dr_scale(6501)==1. and r.effective['stage_id']=='T0_prime'
    resumed=make_runtime(load_plan(r.plan.path,arm='B'),4,'cpu',tmp_path/'resumed',segment_index=1)
    attach_consumer(resumed);resumed.load_state_dict(r.state_dict())
    assert resumed.stop_requested is safety_at_end and resumed.finished is not safety_at_end


def test_second_missing_warning_survives_resume(tmp_path):
    r,_=fixture(tmp_path/'a');tick(r,751,failed=True);r.on_update_start(1001)
    b=make_runtime(load_plan(r.plan.path,arm='B'),4,'cpu',tmp_path/'b',segment_index=1)
    attach_consumer(b);b.load_state_dict(r.state_dict());b.on_update_start(1251)
    rows=[json.loads(x) for x in (b.log_dir/'stage_log.jsonl').read_text().splitlines()]
    assert any(x['event']=='maintenance_evidence_missing_warning' for x in rows)


def test_stand_threshold_and_clock_accounting_cannot_be_changed_silently(tmp_path):
    r,_=fixture(tmp_path/'a')
    doc=yaml.safe_load(r.plan.path.read_text());doc['automatic']['stand_min_passed']=60
    r.plan.path.write_text(yaml.safe_dump(doc))
    with pytest.raises(ValueError,match='stand_min_passed'):load_plan(r.plan.path,arm='B')
    doc['automatic']['stand_min_passed']=61;r.plan.path.write_text(yaml.safe_dump(doc))
    tick(r,251);state=r.state_dict();state['fixed_clock']['elapsed']+=1
    b=make_runtime(load_plan(r.plan.path,arm='B'),4,'cpu',tmp_path/'b',segment_index=1)
    attach_consumer(b)
    with pytest.raises(ValueError,match='clock'):b.load_state_dict(state)


@pytest.mark.parametrize('bad',['nan','sha','stand_missing','iteration_nan','truncated','evidence_sha'])
def test_latest_invalid_json_cannot_be_hidden_by_older_pass(tmp_path,bad):
    r,_=fixture(tmp_path);tick(r,751);tick(r,1001)
    score(r,1200,metrics={'maintenance_counts':counts(r),'stand_min_passed':64})
    p=score(r,1250,metrics={'maintenance_counts':counts(r),'stand_min_passed':64})
    d=json.loads(p.read_text())
    if bad=='nan':d['metrics']['gait_sync']=float('nan')
    if bad=='sha':d['checkpoint_sha256']='0'*64
    if bad=='stand_missing':del d['metrics']['stand_min_passed']
    if bad=='iteration_nan':d['iteration']=float('nan')
    if bad=='evidence_sha':d['evidence'][0]['sha256']='0'*64
    p.write_text('{"iteration":' if bad=='truncated' else json.dumps(d));r.on_update_start(1251)
    assert r.clock.paused and r.clock.recovered==0
    assert r.dr_scale(1501)==r.dr_scale(1251)
    rows=[json.loads(x) for x in (r.log_dir/'stage_log.jsonl').read_text().splitlines()]
    assert any(x['event']=='score_rejected' and str(p) in x['path'] for x in rows)
    assert any(x['event']=='latest_score_invalid_hold' for x in rows)


def test_invalid_evidence_persists_resume_and_new_good_scores_recover(tmp_path):
    r,_=fixture(tmp_path/'a');tick(r,751);tick(r,1001)
    p=score(r,1250,metrics={'maintenance_counts':counts(r),'stand_min_passed':64})
    data=json.loads(p.read_text());data['checkpoint_sha256']='0'*64;p.write_text(json.dumps(data))
    r.on_update_start(1251);assert r.clock.paused
    b=make_runtime(load_plan(r.plan.path,arm='B'),4,'cpu',tmp_path/'b',segment_index=1)
    attach_consumer(b);b.load_state_dict(r.state_dict())
    assert b._score_rejections==r._score_rejections and b._score_rejections
    tick(b,1501);assert b.clock.paused and b.clock.recovered==1
    tick(b,1751);assert not b.clock.paused and b.clock.pause_used==500


