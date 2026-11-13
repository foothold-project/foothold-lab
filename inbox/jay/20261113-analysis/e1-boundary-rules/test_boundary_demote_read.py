"""CPU-only actual score replay and provenance failures at the reader boundary."""
import json
from pathlib import Path
import subprocess
import sys

import pytest
from boundary_demote import read_review, write_review
from boundary_read import RUN, CODE, PARENT, run


@pytest.fixture(scope='module')
def actual():
    return {n:read_review(RUN/f'eval/scores/m{n}/ex42_score.json',RUN,CODE)
            for n in (250,500,750)}


def row(report,key):
    return next(r for r in report['cells'] if r['cell']==key)


def test_actual_three_boundaries_recompute_the_requested_drop(actual):
    assert actual[250]['state']=='BASELINE_ONLY'
    assert actual[250]['history_iterations']==[]
    for n in (500,750):
        r=row(actual[n],'low/L0/fwd0.1/R')
        assert r['state']=='DEMOTE'
        assert r['eval_gt']['best_iteration']==250
        assert r['eval_pred']['best_iteration']==250
        assert r['same_direction'] is True
    # The requested example rules out requiring BOTH maps to cross .10.
    r=row(actual[500],'low/L0/fwd0.1/R')
    assert r['eval_gt']['value']==pytest.approx(.3119739504472818,abs=1e-9)
    assert r['eval_gt']['adverse_delta']==pytest.approx(.13472863091980494,abs=1e-9)
    assert 0 < r['eval_pred']['adverse_delta'] < .10
    assert r['trigger_modes']==['eval_gt']
    r=row(actual[750],'low/L0/fwd0.1/R')
    assert r['eval_gt']['adverse_delta']==pytest.approx(.2745856501360928,abs=1e-9)
    assert r['eval_gt']['previous_delta']==pytest.approx(-.13985701921628785,abs=1e-9)
    for n in (250,500,750):
        d=actual[n]
        assert not d['errors']
        assert len(d['cells'])==18
        assert d['map_off_survival']['state']=='PASS'
        assert len(d['map_off_survival']['items'])==21
        counts={r['cell']:r['survival'] for r in d['map_off_survival']['items']}
        assert counts=={k:(63 if n==500 and k=='map64/back1.0' else 64) for k in counts}


def test_report_is_read_only_and_retains_exact_values(actual,tmp_path):
    d=actual[500];write_review(d,tmp_path/'out')
    import csv
    with (tmp_path/'out/demote_cells.csv').open() as f:
        rows={r['cell']:r for r in csv.DictReader(f)}
    r=rows['low/L0/fwd0.1/R']
    assert float(r['eval_gt_adverse_delta'])==pytest.approx(.13472863091980494,abs=1e-9)
    assert r['eval_pred_threshold_crossed']=='False' and r['state']=='DEMOTE'
    assert 'DEMOTE' in (tmp_path/'out/demote.txt').read_text()
    assert not list((tmp_path/'out').glob('*adjustment*'))
    with pytest.raises(ValueError,match='outside'):
        write_review(d,RUN/'analyst_demote_must_not_be_created')
    with pytest.raises(ValueError,match='outside'):
        write_review(d,CODE/'analyst_demote_must_not_be_created')


def run_clone(tmp_path):
    root=tmp_path/'run';root.mkdir()
    for name in ('startup_receipt.json','manifest.json'):
        (root/name).write_bytes((RUN/name).read_bytes())
    # Read-only aliases keep score/P1 measurement identity unchanged.
    (root/'eval').symlink_to(RUN/'eval',target_is_directory=True)
    return root


@pytest.mark.parametrize('fault',['checkpoint','plan','pin_type','P1','bad_seed'])
def test_actual_reader_rejects_foreign_identity(tmp_path,fault):
    root=run_clone(tmp_path)
    if fault in ('checkpoint','pin_type'):
        p=root/'manifest.json';doc=json.loads(p.read_text())
        if fault=='checkpoint':doc['checkpoints']['model_500.pt']='f'*64
        else:doc['checkpoints']=[]
        p.write_text(json.dumps(doc))
    if fault=='plan':
        p=root/'startup_receipt.json';doc=json.loads(p.read_text());doc['plan_sha256']='f'*64
        p.write_text(json.dumps(doc))
    score=root/'eval/scores/m500/ex42_score.json'
    if fault in ('P1','bad_seed'):
        # Replace only one isolated local boundary, never the real eval tree.
        (root/'eval').unlink();(root/'eval/scores/m500').mkdir(parents=True)
        dst=root/'eval/scores/m500'
        original=RUN/'eval/scores/m500'
        for child in original.iterdir():
            if child.name in ('ex42_score.json','p1_score.json'):
                (dst/child.name).write_bytes(child.read_bytes())
            else:(dst/child.name).symlink_to(child,target_is_directory=child.is_dir())
        (root/'eval/scores/m250').symlink_to(RUN/'eval/scores/m250',target_is_directory=True)
        if fault=='P1':
            p=dst/'p1_score.json';d=json.loads(p.read_text());d['measurement_sha256']='f'*64;p.write_text(json.dumps(d))
        else:
            p=dst/'ex42_score.json';d=json.loads(p.read_text());d['conditions']['eval_seed']=999;p.write_text(json.dumps(d))
    result=read_review(score,root,CODE)
    assert result['state']=='HOLD' and not result['demoted_cells']
    assert any('m500' in e or 'm250' in e for e in result['errors'])


def test_missing_past_boundary_cannot_become_new_best(tmp_path):
    root=run_clone(tmp_path);(root/'eval').unlink();(root/'eval/scores').mkdir(parents=True)
    (root/'eval/scores/m750').symlink_to(RUN/'eval/scores/m750',target_is_directory=True)
    result=read_review(root/'eval/scores/m750/ex42_score.json',root,CODE)
    assert result['state']=='HOLD'
    assert any('m250' in e for e in result['errors'])
    assert any('m500' in e for e in result['errors'])


def test_same_file_alias_path_is_not_a_foreign_run(tmp_path):
    root=run_clone(tmp_path)
    d=read_review(root/'eval/scores/m250/ex42_score.json',root,CODE)
    assert d['state']=='BASELINE_ONLY' and not d['errors']


def test_802_actual_read_emits_demote_but_does_not_change_legacy_prescription(tmp_path):
    d=run(RUN/'eval/scores/m750/ex42_score.json',PARENT,RUN,CODE,tmp_path/'802')
    assert d['demotion_review']['state']=='DEMOTE'
    assert d['decision']['changes']=={}
    assert d['decision']['rule']=='OBSERVE'
    assert 'a76e 경계 칸 내림' in (tmp_path/'802/REPORT.md').read_text()
    assert (tmp_path/'802/demote.txt').is_file()


def test_invalid_cli_boundary_emits_hold_instead_of_traceback(tmp_path):
    script=Path(__file__).with_name('boundary_demote.py')
    out=tmp_path/'invalid_out'
    proc=subprocess.run([sys.executable,'-B',str(script),'--score',str(tmp_path/'wrong/ex42_score.json'),
        '--run-root',str(RUN),'--code-root',str(CODE),'--out',str(out)],capture_output=True,text=True)
    assert proc.returncode==2,proc.stderr
    assert 'HOLD' in proc.stdout and not proc.stderr
    assert json.loads((out/'demotion.json').read_text())['state']=='HOLD'
