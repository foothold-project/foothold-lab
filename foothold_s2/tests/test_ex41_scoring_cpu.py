"""G6 real m6000 raw evidence versus pinned 39-cell score, and bad-input cases."""
import copy
import json
from pathlib import Path
from datetime import datetime,timezone
import pytest
from foothold_s2.curriculum.continuous import load_plan
from foothold_s2.curriculum.ex41_fixed import baseline_counts,maintenance
from foothold_s2.curriculum.ex41_scoring import (MODES,measurement_bundle,enrich_score_metrics,
                                               maintenance_counts_from_map_modes)
from foothold_s2.scripts.ex41_startup import enrich_score_file

ROOT=Path('C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/score-watch-b/model_6000_d5e9ec400f33')
TABLE=Path(__file__).parents[1]/'curriculum/ex41-fixed5000.yaml'


@pytest.fixture(scope='module')
def actual():
    plan=load_plan(TABLE,arm='B')
    baseline_path=Path(plan.fixed_schedule['maintenance_baseline']['path'])
    native=json.loads(baseline_path.read_text(encoding='utf-8-sig'))
    stands={m:ROOT/f'stand_{m}'/'stand.json' for m in MODES}
    return plan,native,stands


def test_actual_m6000_generated_file_matches_all39_and_stand_cells(actual,tmp_path):
    plan,native,stands=actual
    draft={'format':'foothold-ex41-score/1','iteration':6000,'stage_id':'S2e',
        'schedule_sha256':plan.effective_sha256,'parent_sha256':plan.parent_sha256,
        'baseline_checkpoint_sha256':plan.parent_sha256,'checkpoint_path':native['checkpoint'],
        'checkpoint_sha256':native['checkpoint_sha256'],'created_at':datetime.now(timezone.utc).isoformat(),
        'metrics':{},'evidence':[],'maintenance_pass':False,'stage_pass':False,'safety_stop':False}
    result=enrich_score_metrics(draft,ROOT/'map64/map_modes.json',stands,plan)
    out=tmp_path/'score_6000.json';out.write_text(json.dumps(result,allow_nan=False))
    got=json.loads(out.read_text());counts=got['metrics']['record_counts']
    assert len(counts)==39 and len(got['metrics']['maintenance_counts'])==26
    assert maintenance(got['metrics']['maintenance_counts'],baseline_counts(plan))==[]
    assert set(got['metrics']['maintenance_counts'])==set(counts)-{k for k in counts if k.startswith('eval_pred/')}
    for key,row in got['metrics']['maintenance_counts'].items():assert row==counts[key]
    for key,row in counts.items():assert row['passed']==row['baseline_passed']==native['cells'][key]['alive_envs_at_end']
    for mode,row in got['metrics']['stand_counts'].items():
        key=f'{mode}/flat_stand'+('_record_only' if mode=='eval_pred' else '')
        assert row['passed']==native['cells'][key]['passed_envs']==64 and row['total']==64
    assert got['metrics']['stand_min_passed']==64 and len(got['evidence'])==8
    assert got['stage_pass'] is False and not draft['metrics']


def test_runner_score_entry_uses_required_three_stand_sources(actual,tmp_path):
    plan,native,stands=actual
    draft={'format':'foothold-ex41-score/1','iteration':6000,'stage_id':'S2e',
        'schedule_sha256':plan.effective_sha256,'parent_sha256':plan.parent_sha256,
        'baseline_checkpoint_sha256':plan.parent_sha256,'checkpoint_path':native['checkpoint'],
        'checkpoint_sha256':native['checkpoint_sha256'],'metrics':{},'evidence':[],
        'maintenance_pass':False,'stage_pass':False,'safety_stop':False}
    source=tmp_path/'draft.json';source.write_text(json.dumps(draft))
    target=tmp_path/'score.json'
    enrich_score_file(source,ROOT/'map64/map_modes.json',stands,TABLE,target)
    result=json.loads(target.read_text())
    assert set(result['metrics']['stand_counts'])==set(MODES)
    assert len(result['metrics']['maintenance_counts'])==39
    assert len(result['evidence'])==8


def test_runner_score_entry_rejects_missing_stand_path(actual,tmp_path):
    plan,native,stands=actual
    draft={'format':'foothold-ex41-score/1','iteration':6000,'stage_id':'S2e',
        'schedule_sha256':plan.effective_sha256,'parent_sha256':plan.parent_sha256,
        'baseline_checkpoint_sha256':plan.parent_sha256,'checkpoint_path':native['checkpoint'],
        'checkpoint_sha256':native['checkpoint_sha256'],'metrics':{},'evidence':[],
        'maintenance_pass':False,'stage_pass':False,'safety_stop':False}
    source=tmp_path/'draft.json';source.write_text(json.dumps(draft))
    with pytest.raises(ValueError,match='three modes'):
        enrich_score_file(source,ROOT/'map64/map_modes.json',
                          {k:v for k,v in stands.items() if k!='eval_pred'},TABLE,tmp_path/'out.json')


def test_b3_is_not_extended_maintenance_source(actual):
    plan,_,_=actual; data=json.loads((ROOT/'map64_b3/map_modes.json').read_text(encoding='utf-8-sig'))
    with pytest.raises(ValueError,match='extended'):maintenance_counts_from_map_modes(data,baseline_counts(plan))


@pytest.mark.parametrize('bad',['missing_mode','duplicate_env','count_lie','alive_string'])
def test_map_numeric_contract_rejects_bad_inputs(actual,bad):
    plan,_,_=actual;data=json.loads((ROOT/'map64/map_modes.json').read_text(encoding='utf-8-sig'))
    if bad=='missing_mode':del data['modes']['eval_pred']
    else:
        row=data['modes']['eval_gt']['fwd0.5']
        if bad=='duplicate_env':row['per_env'][1]['env']=0
        if bad=='count_lie':row['alive_envs_at_end']=0
        if bad=='alive_string':row['per_env'][0]['alive_at_end']='true'
    with pytest.raises(ValueError):maintenance_counts_from_map_modes(data,baseline_counts(plan))


def test_missing_stand_mode_is_error_not64(actual):
    plan,native,stands=actual;bad=copy.copy(stands);bad.pop('eval_pred')
    with pytest.raises(ValueError,match='three modes'):
        measurement_bundle(ROOT/'map64/map_modes.json',bad,native['checkpoint'],baseline_counts(plan))
