"""Lead 19:5x: boundary next-update n501 consumes completed checkpoint m250."""
import json
from foothold_s2.tests.test_ex41_fixed_cpu import fixture,counts
from foothold_s2.tests.test_ex41_runtime_cpu import score


def put(runtime,n):
    return score(runtime,n,metrics={'maintenance_counts':counts(runtime),'stand_min_passed':64})


def clock_rows(runtime):
    return [r for line in (runtime.log_dir/'stage_log.jsonl').read_text().splitlines()
            if (r:=json.loads(line))['event']=='dr_score_clock']


def test_m250_arrives_after_n251_used_at_n501(tmp_path):
    r,_=fixture(tmp_path);r.on_update_start(1);r.on_update_start(251)
    put(r,250);r.on_update_start(501)
    assert clock_rows(r)[-1]['selected_score_iteration']==250
    put(r,500);r.on_update_start(751)
    assert clock_rows(r)[-1]['selected_score_iteration']==500
    assert not r.clock.paused


def test_missing_expected_never_uses_newer_or_older_pass(tmp_path):
    r,_=fixture(tmp_path);r.on_update_start(1)
    put(r,250);r.on_update_start(501)
    put(r,750);r.on_update_start(751)  # expected500 absent; newer750 is not a replacement
    assert clock_rows(r)[-1]['selected_score_iteration'] is None
    assert r.clock.paused and not r.stop_requested and r.dr_scale(1001)==.5


def test_exact_error_rejects_old_pass_and_needs_new_adjacent_recovery(tmp_path):
    r,_=fixture(tmp_path);r.on_update_start(1)
    put(r,250);r.on_update_start(501)
    bad=put(r,500);data=json.loads(bad.read_text());data['metrics']['gait_sync']=float('nan')
    bad.write_text(json.dumps(data));r.on_update_start(751)
    assert r.clock.paused and clock_rows(r)[-1]['state']=='missing_evidence'
    put(r,750);r.on_update_start(1001);assert r.clock.paused and r.clock.recovered==1
    put(r,1000);r.on_update_start(1251);assert not r.clock.paused and r.clock.pause_used==500


def test_previous_stage_exact_checkpoint_arrives_after_stage_transition(tmp_path):
    r,_=fixture(tmp_path);r.on_update_start(1)
    put(r,500)
    old=put(r,750);data=json.loads(old.read_text());old.unlink()  # fixture delivery withheld
    r.on_update_start(751);assert r.effective['stage_id']=='S2b'
    old.write_text(json.dumps(data));assert data['stage_id']=='S2a'
    r.on_update_start(1001)
    assert clock_rows(r)[-1]['selected_score_iteration']==750 and not r.clock.paused


def test_unknown_stage_is_not_allowed_by_lagged_clock(tmp_path):
    r,_=fixture(tmp_path);r.on_update_start(1)
    p=put(r,500);data=json.loads(p.read_text());data['stage_id']='invented';p.write_text(json.dumps(data))
    r.on_update_start(751)
    assert r.clock.paused and clock_rows(r)[-1]['state']=='missing_evidence'


def test_known_but_wrong_stage_cannot_spoof_previous_stage_evidence(tmp_path):
    r,_=fixture(tmp_path);r.on_update_start(1);put(r,500);r.on_update_start(751)
    p=put(r,750);d=json.loads(p.read_text());assert d['stage_id']=='S2a'
    d['stage_id']='S2b';p.write_text(json.dumps(d))
    r.on_update_start(1001)
    assert r.clock.paused and clock_rows(r)[-1]['state']=='missing_evidence'
