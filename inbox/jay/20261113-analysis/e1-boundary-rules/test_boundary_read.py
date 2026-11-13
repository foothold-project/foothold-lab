"""Actual parent and archived P1 results are independent known-answer fixtures."""
from pathlib import Path
import json
import pytest
from boundary_read import load_snapshot, comparison_rows, make_adjustment, load_treatment, run

DATA=Path('/home/jay/data/foothold/s2_lab')
PARENT=DATA/'ex42_p1reh_20261113_144455/m13250/ex42_score.json'
OLD=DATA/'ex42_main_20261112_164150/main/EX-42-B-E1-cmd7seg_20261112_164150'
CODE=Path('/home/jay/mai/wt/foothold-lab/ex42-launch-e1-v19')
LIVE=DATA/'ex42_main_20261113_174400/main/EX-42-B-E1-again_20261113_174400'

def test_real_parent_identity_and_recomputed_progress():
    s=load_snapshot(PARENT,iteration=0,code_root=CODE)
    assert not s['errors']
    assert s['maintenance']=='PASS' and s['overall']=='FAIL'
    assert s['metrics']['low/L0/eval_gt/fwd0.2/R']==pytest.approx(.40138822647471295,abs=1e-7)
    assert s['metrics']['yaw/L2/eval_gt/fwd1.0/median_abs_rad']==pytest.approx(.14653050899505615,abs=1e-7)
    assert s['metrics']['yaw/L2/eval_gt/fwd1.0/p90_abs_rad']==pytest.approx(.2311777174472809,abs=1e-7)
    rows=comparison_rows(s,s,s)
    assert len(rows)>150
    assert all(r['parent_delta']==0 and r['previous_delta']==0 for r in rows)

def test_draft_preserves_full_reward_cells_and_does_not_patch_live(tmp_path):
    t=load_treatment(LIVE,250,CODE)
    assert not t['errors']
    d=make_adjustment({'rule':'R6','changes':{'slow_track':.2},'notes':[]},t,250,'proof')
    assert d['schema']=='ex42-segment-adjust/1'
    assert d['plan_sha256']=='9087bf55ae913045a4e2c0268411b21aeed7351b6a871f59a0606160df55acf4'
    assert d['segments']['1']['rewards']['slow_track']==.2
    assert d['segments']['1']['rewards']['zero_yaw']==-1
    assert d['segments']['1']['rewards']['track_lin_vel_std']==.35
    assert len(d['segments']['1']['rewards'])==10
    from types import SimpleNamespace
    import sys,yaml
    sys.path.insert(0,str(CODE))
    from foothold_s2.commands.ex42_segment_adjust import resolve,reward_limits
    plan=SimpleNamespace(sha256=d['plan_sha256'],document=yaml.safe_load((CODE/'foothold_s2/curriculum/ex42-prep.yaml').read_text()))
    assert resolve(plan,'E1',d,1,reward_limits())['rewards']['slow_track']==.2

def test_historical_m500_m750_raw_low_inputs_have_64_denominator():
    for n in (500,750):
        low=DATA/f'hipan_g1_20261112/m{n}seg'
        s=load_snapshot(OLD/f'eval/scores/m{n}/ex42_score.json',iteration=n,code_root=CODE,legacy_low=low)
        assert not s['errors']
        assert s['maintenance']=='PASS'
        assert all(s['metrics'][f'low/L{lev}/eval_gt/{case}/env_count']==64 for lev in (0,5) for case in ('fwd0.1','fwd0.2'))
        assert s['metrics']['low/L0/eval_gt/fwd0.2/R'] > .6 if n==500 else s['metrics']['low/L0/eval_gt/fwd0.2/R'] < .4

def test_incomplete_score_yields_explicit_evidence_hold_and_draft_null(tmp_path):
    p=tmp_path/'m250';p.mkdir();(p/'ex42_score.json').write_text('{"format":"foothold-ex42-maintenance-score/1"}')
    out=tmp_path/'out'
    result=run(p/'ex42_score.json',PARENT,LIVE,CODE,out,iteration=250)
    assert result['decision']['rule']=='EVIDENCE_HOLD'
    assert json.loads((out/'adjustment.draft.json').read_text())['payload'] is None

def test_cli_refuses_output_inside_training_run(tmp_path):
    with pytest.raises(ValueError,match='output'):
        run(PARENT,PARENT,LIVE,CODE,LIVE/'analyst_test_must_not_exist',iteration=0)

def test_next_draft_preserves_existing_applied_segments(tmp_path):
    """Dropping segment 1 would reset slow_track or fail the consumer's replay guard."""
    import sys,yaml
    from types import SimpleNamespace
    sys.path.insert(0,str(CODE))
    from foothold_s2.commands.ex42_segment_adjust import read,resolve,reward_limits
    root=tmp_path/'test_run';root.mkdir()
    for name in ('startup_receipt.json','manifest.json'):
        (root/name).write_bytes((LIVE/name).read_bytes())
    t=load_treatment(root,250,CODE)
    first=make_adjustment({'rule':'R6','changes':{'slow_track':.2},'notes':[]},t,250,'known')
    file=tmp_path/'approved_test_input.json';file.write_text(json.dumps(first))
    plan=SimpleNamespace(sha256=t['plan_sha256'],document=yaml.safe_load((CODE/'foothold_s2/curriculum/ex42-prep.yaml').read_text()))
    rec=read(file,plan,'E1',1,reward_limits());rec.pop('_document')
    (root/'segment_commands_b1.json').write_text(json.dumps(rec))
    for rank in (0,1):
        (root/f'segment_rewards_b1_rank{rank}.json').write_text(json.dumps(dict(plan_sha256=t['plan_sha256'],boundary_index=1,live=first['segments']['1']['rewards'])))
    t=load_treatment(root,500,CODE)
    assert not t['errors']
    second=make_adjustment({'rule':'R6_RAISE','changes':{'slow_track':.3},'notes':[]},t,500,'known')
    assert '1' in second['segments'] and '2' in second['segments']
    prefix={**second,'segments':{'1':second['segments']['1']}}
    assert resolve(plan,'E1',prefix,1,reward_limits())['rewards']['slow_track']==.2
    assert resolve(plan,'E1',second,2,reward_limits())['rewards']['slow_track']==.3

def test_corrupt_npz_and_nan_score_produce_explicit_errors(tmp_path):
    """A truncated zip or a nonfinite score must not become an empty success report."""
    import shutil
    root=tmp_path/'copy';shutil.copytree(PARENT.parent,root,symlinks=False,ignore=shutil.ignore_patterns('e1_v2_repeat_seed*','children','d44*'))
    p=root/'e1_v2/L0/env_arrays_eval_gt_fwd0.1.npz'
    original=p.read_bytes();p.write_bytes(original[:100])
    s=load_snapshot(root/'ex42_score.json',0,CODE)
    assert s['errors'] and any('low_L0' in x for x in s['errors'])
    data=json.loads((root/'ex42_score.json').read_text());data['map64']['eval_gt']['fwd1.0']['vx_abs_error_median_mps']=float('nan')
    (root/'ex42_score.json').write_text(json.dumps(data))
    assert 'nonfinite JSON' in load_snapshot(root/'ex42_score.json',0,CODE)['errors'][0]

def test_rank_readback_disagreement_blocks_adjustment(tmp_path):
    """One rank still at 0 must not produce a pretend already-active 0.2 treatment."""
    from types import SimpleNamespace
    import sys,yaml
    sys.path.insert(0,str(CODE))
    from foothold_s2.commands.ex42_segment_adjust import read,reward_limits
    root=tmp_path/'ranks';root.mkdir()
    for name in ('startup_receipt.json','manifest.json'):(root/name).write_bytes((LIVE/name).read_bytes())
    t=load_treatment(root,250,CODE)
    draft=make_adjustment({'rule':'R6','changes':{'slow_track':.2},'notes':[]},t,250,'known')
    p=tmp_path/'adjust.json';p.write_text(json.dumps(draft))
    plan=SimpleNamespace(sha256=t['plan_sha256'],document=yaml.safe_load((CODE/'foothold_s2/curriculum/ex42-prep.yaml').read_text()))
    rec=read(p,plan,'E1',1,reward_limits());rec.pop('_document');(root/'segment_commands_b1.json').write_text(json.dumps(rec))
    for rank in (0,1):
        live={**draft['segments']['1']['rewards'],'slow_track':.2 if rank==0 else 0.}
        (root/f'segment_rewards_b1_rank{rank}.json').write_text(json.dumps(dict(plan_sha256=t['plan_sha256'],boundary_index=1,live=live)))
    assert 'readback mismatch' in load_treatment(root,500,CODE)['errors'][0]

def test_missing_score_keeps_requested_boundary_in_failure_report(tmp_path):
    s=load_snapshot(tmp_path/'m250/ex42_score.json',code_root=CODE)
    assert s['iteration']==250 and s['errors']
