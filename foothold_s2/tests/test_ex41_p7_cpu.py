"""Final saved SHA is a request, never an implicit graduation."""
import json
import pytest
from foothold_s2.tests.test_ex41_fixed_cpu import fixture
from foothold_s2.curriculum.continuous import sha256


def test_actual_finish_emits_exact_final_checkpoint_request_once(tmp_path):
    r,_=fixture(tmp_path,smoke=(2,4,6,8,10))
    for n in (1,2,4,6,8,10,12):r.on_update_start(n)
    assert r.finished and not r.graduated
    cp=tmp_path/'model_11.pt';cp.write_bytes(b'known final smoke state')
    r.on_checkpoint(11,cp);r.on_checkpoint(11,cp)
    paths=list((r.log_dir/'final_eval_requests').glob('*.json'));assert len(paths)==1
    row=json.loads(paths[0].read_text())
    assert row['status']=='pending' and row['training_finished'] and not row['graduated']
    assert row['checkpoint']=={'iteration':11,'path':str(cp.resolve()),'sha256':sha256(cp)}
    assert row['schedule_sha256']==r.plan.effective_sha256 and row['stage_id']=='T0_prime'
    assert row['dr_scale']==r.dr_scale(12)
    old=tmp_path/'model_10.pt';old.write_bytes(b'older')
    with pytest.raises(ValueError,match='last completed'):r.on_checkpoint(10,old)
    assert len(list((r.log_dir/'final_eval_requests').glob('*.json')))==1


def test_regular_checkpoint_does_not_claim_final_evaluation(tmp_path):
    r,_=fixture(tmp_path);r.on_update_start(1)
    cp=tmp_path/'model_50.pt';cp.write_bytes(b'known intermediate')
    r.on_checkpoint(50,cp)
    assert not (r.log_dir/'final_eval_requests').exists() and not r.graduated
