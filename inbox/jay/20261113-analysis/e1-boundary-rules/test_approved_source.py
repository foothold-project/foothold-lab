"""Actual historical traces, plus a different-checkpoint score with valid JSON pins."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import pytest

LIVE=Path('/home/jay/data/foothold/s2_lab/ex42_main_20261113_174400/main/EX-42-B-E1-again_20261113_174400')
SCORE=LIVE/'eval/scores/m250/ex42_score.json'


def read_audit(path):
    # The core H1 reader and execution v19 reward parser have different module
    # revisions. Production isolates them; tests must preserve that boundary.
    p=Path(__file__).with_name('approved_source.py')
    proc=subprocess.run([sys.executable,'-B',str(p),'--score',str(path)],capture_output=True,text=True)
    assert proc.returncode==0,proc.stderr
    return json.loads(proc.stdout)


def test_actual_map_off_has_exact_21_judges_and_c1_not_fabricated():
    d=read_audit(SCORE)
    assert not d['errors']
    assert len(d['cells'])==72
    assert len(d['off_cells'])==21
    assert len(d['off_record_cells'])==6
    assert not any('side' in k for k in d['off_cells'] if 'L5' in k)
    assert d['off_record_cells']['e1_v2/L5/side+0.2']['valid']==64
    assert all(r['valid']==64 for r in d['off_cells'].values())
    assert d['off_cells']['map64/fwd0.5']['survival']==64
    assert not d['required_complete'] and d['wide_errors']
    assert d['treatment_sha256']=='202f5d5641d25a0d241a6f185a2941be16b119c9b9d92ad6454f33cb0fce1987'


def test_rewritten_checkpoint_in_score_and_receipt_still_fails_actual_npz(tmp_path):
    p=tmp_path/'m250';p.mkdir()
    for child in SCORE.parent.iterdir():
        if child.name not in ('ex42_score.json','p1_score.json'):(p/child.name).symlink_to(child,target_is_directory=child.is_dir())
    s=json.loads(SCORE.read_text());s['checkpoint_sha256']='a'*64
    raw=json.dumps(s).encode();(p/'ex42_score.json').write_bytes(raw)
    r=json.loads(SCORE.with_name('p1_score.json').read_text())
    r.update(checkpoint_sha256='a'*64,measurement=str(p/'ex42_score.json'),measurement_sha256=hashlib.sha256(raw).hexdigest())
    (p/'p1_score.json').write_text(json.dumps(r))
    d=read_audit(p/'ex42_score.json')
    assert d['errors'] and not d['required_complete'] and not d['all_judge_pass']


def test_p1_pin_is_required_not_merely_score_pass(tmp_path):
    p=tmp_path/'m250';p.mkdir()
    (p/'ex42_score.json').write_bytes(SCORE.read_bytes())
    d=read_audit(p/'ex42_score.json')
    assert d['errors'] and not d['required_complete']


def test_isolated_cli_matches_reader_and_ignores_cuda_env(tmp_path):
    p=Path(__file__).with_name('approved_source.py')
    proc=subprocess.run([sys.executable,'-B',str(p),'--score',str(SCORE)],capture_output=True,text=True)
    assert proc.returncode==0
    d=json.loads(proc.stdout)
    assert d['off_cells']['e1_v2/L5/fwd0.2']['valid']==64


def wide_fixture():
    items={};endpoints={}
    for mode in ('eval_gt','eval_pred'):
        endpoints[mode]={}
        for case in ('side+0.8','side-0.8','wide_L3_fwd1.0','wide_L6_fwd1.0'):
            items[f'{case}/{mode}']=dict(role='judge',judgement='PASS',valid=64,
                success=60,survival=64,success_min=52,survival_min=60)
            if case.startswith('side'):endpoints[mode][case]=dict(R=1.,mae_mps=.1)
        items[f'symmetry/side0.8/{mode}']=dict(role='judge',judgement='PASS',S=1.)
    return dict(cells={'endpoints':endpoints},judged=dict(items=items,cap=6,reached_level={'eval_gt':6,'eval_pred':6}),
                code='known-input',code_sha256='a'*64),dict(R_min=.8,R_max=1.2,mae_fraction=.2,symmetry_min=.8)


def test_c1_record_missing_does_not_add_a_graduation_veto():
    from approved_source import add_wide
    w,cfg=wide_fixture();out=dict(cells={},gaps={},off_record_cells={})
    add_wide(out,w,cfg)
    assert len(out['cells'])==10
    assert out['wide']['record_warning']=='L9 record missing'
    assert len(out['wide']['record_warnings'])==4
    assert all(g==0 for g in out['gaps'].values())


def test_c1_endpoint_ratio_and_mae_deficits_are_part_of_extension():
    from approved_source import add_wide
    w,cfg=wide_fixture();out=dict(cells={},gaps={},off_record_cells={})
    w['cells']['endpoints']['eval_pred']['side+0.8'].update(R=.6,mae_mps=.25)
    w['judged']['items']['side+0.8/eval_pred']['judgement']='FAIL'
    add_wide(out,w,cfg)
    assert out['gaps']['side+0.8/eval_pred/R']==pytest.approx(.2)
    assert out['gaps']['side+0.8/eval_pred/mae_mps']==pytest.approx(.09)


@pytest.mark.parametrize('fault',['missing','demoted','valid63'])
def test_c1_judged_row_missing_demoted_or_63_is_not_accepted(fault):
    from approved_source import add_wide
    w,cfg=wide_fixture();out=dict(cells={},gaps={},off_record_cells={});key='wide_L6_fwd1.0/eval_pred'
    if fault=='missing':del w['judged']['items'][key]
    elif fault=='demoted':w['judged']['items'][key]['role']='record_only'
    else:w['judged']['items'][key]['valid']=63
    with pytest.raises(ValueError):add_wide(out,w,cfg)
