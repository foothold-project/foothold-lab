"""Actual m250 receipt counterexamples, copied to CPU scratch only."""
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from foothold_s2 import ex42_e1_v2 as v

RUN = Path('/home/jay/data/foothold/s2_lab/ex42_main_20261113_174400/main/'
           'EX-42-B-E1-again_20261113_174400')
SOURCE = RUN / 'eval/scores/m250/e1_v2/L0/map_modes.json'
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def actual_map():
    if not SOURCE.is_file():
        pytest.skip('actual read-only m250 source unavailable')
    return json.loads(SOURCE.read_text())


@pytest.mark.parametrize('field,value', [('checkpoint_sha256', '0'*64), ('eval_seed', 999)])
def test_map_rejects_foreign_raw_identity(tmp_path, actual_map, field, value):
    case = 'side+0.2'
    original = v._map_cell(SOURCE, actual_map, 'eval_gt', case)
    assert original['R'] == pytest.approx(.7043086688, abs=1e-9)
    name = actual_map['env_arrays']['eval_gt/'+case]
    with np.load(SOURCE.with_name(name), allow_pickle=False) as z:
        arrays = {k:z[k] for k in z.files}
    identity = json.loads(arrays['run_identity'].item())
    identity[field] = value
    arrays['run_identity'] = np.array(json.dumps(identity))
    np.savez_compressed(tmp_path/name, **arrays)
    with pytest.raises(ValueError, match='identity'):
        v._map_cell(tmp_path/'map_modes.json', actual_map, 'eval_gt', case)


def test_source_header_must_match_its_own_run_receipt(tmp_path, actual_map):
    doc = copy.deepcopy(actual_map)
    doc['run_identity']['eval_seed'] = 999
    path = tmp_path/'map_modes.json'
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match='identity'):
        v._source(path, actual_map['checkpoint_sha256'], 42, v.MODES, level=0)


@pytest.mark.parametrize('changed', ['all', 'commands', 'rank0', 'rank1'])
def test_treatment_rejects_foreign_plan_even_when_all_receipts_agree(tmp_path, changed):
    if not (RUN/'segment_commands_b1.json').exists():
        pytest.skip('read-only b1 source unavailable')
    plan = yaml.safe_load((Path('/home/jay/mai/wt/foothold-lab/ex42-launch-e1-v24') /
                          'foothold_s2/curriculum/ex42-prep.yaml').read_text())
    (tmp_path/'startup_receipt.json').write_bytes((RUN/'startup_receipt.json').read_bytes())
    for kind, filename in [('commands','segment_commands_b1.json'),
                           ('rank0','segment_rewards_b1_rank0.json'),
                           ('rank1','segment_rewards_b1_rank1.json')]:
        doc = json.loads((RUN/filename).read_text())
        if changed in ('all', kind):
            doc['plan_sha256'] = '0'*64
        (tmp_path/filename).write_text(json.dumps(doc))
    with pytest.raises(ValueError, match='identity'):
        v.treatment(tmp_path/'model_500.pt', 500, plan)


def test_actual_m250_raw_values_survive_identity_validation():
    if not SOURCE.is_file():
        pytest.skip('read-only m250 source unavailable')
    score = json.loads((RUN/'eval/scores/m250/ex42_score.json').read_text())
    actual = v.measure_cells(Path(score['e1_v2_evaluation']), score['checkpoint_sha256'], 42)
    assert actual == score['e1_v2_cells']
    forged=copy.deepcopy(score)
    forged['e1_v2_cells']['low']['L0']['eval_gt']['fwd0.1']['R']=1.
    with pytest.raises(ValueError,match='cached cells'):
        v._verified_cells(forged,Path(score['e1_v2_evaluation']),42)


def synthetic_map(folder):
    folder.mkdir(parents=True, exist_ok=True)
    cp, assignment, case = 'a'*64, 'b'*64, 'side+0.2'
    name = 'env_arrays_eval_gt_'+case+'.npz'
    command = [0., .2, 0.]
    identity = dict(checkpoint_sha256=cp, eval_seed=42)
    alive = np.ones((300,64),bool)
    arrays = dict(alive=alive,alive_end=alive[-1],alive_steps=alive.sum(0),dt=np.array(.02),
                  vx=np.zeros((300,64)),assignment_sha256=np.array(assignment),
                  run_identity=np.array(json.dumps(identity)))
    doc = dict(checkpoint_sha256=cp,eval_seed=42,envs=64,steps=300,run_identity=identity,
               fixed_terrain=dict(fixed_level=0,assignment_sha256=assignment),
               commands={case:command},env_arrays={'eval_gt/'+case:name},
               modes={'eval_gt':{case:dict(env_count=64,command=command,alive_envs_at_end=64,
                  per_env=[dict(env=i,samples_alive=300,command_xy_projection_integral_m=1.2,
                                vy_abs_error_mean_alive_mps=0.) for i in range(64)])}})
    np.savez_compressed(folder/name,**arrays)
    p=folder/'map_modes.json';p.write_text(json.dumps(doc))
    return p,doc,arrays,name


@pytest.mark.parametrize('field,value', [('checkpoint_sha256','c'*64),('eval_seed',999)])
def test_foreign_identity_known_answer_without_external_files(tmp_path,field,value):
    p,doc,arrays,name=synthetic_map(tmp_path)
    assert v._map_cell(p,doc,'eval_gt','side+0.2')['R']==pytest.approx(1.)
    identity=json.loads(arrays['run_identity'].item());identity[field]=value
    arrays['run_identity']=np.array(json.dumps(identity));np.savez_compressed(tmp_path/name,**arrays)
    with pytest.raises(ValueError,match='identity'):
        v._map_cell(p,doc,'eval_gt','side+0.2')


def test_cached_pass_cannot_hide_foreign_source_and_returns_hold(tmp_path):
    from foothold_s2.tests.test_ex42_e1_judge_cpu import _cells, _inputs
    from foothold_s2.tests.test_ex42_e1_v2_cpu import _pass_cells
    score, baseline, measured, plan = _inputs()
    score['d44_cells'] = _cells(plan,tmp_path)
    score['e1_v2_cells'] = _pass_cells()
    score['checkpoint_sha256'] = 'a'*64
    plan['evaluation']['e1_exit_v2'] = yaml.safe_load((ROOT/'foothold_s2/curriculum/ex42-prep.yaml').read_text())['evaluation']['e1_exit_v2']
    p,doc,arrays,name=synthetic_map(tmp_path/'e1_v2/L0')
    # The summary itself is from a different run; pre-counted PASS is untrusted.
    doc['run_identity']['checkpoint_sha256']='c'*64;p.write_text(json.dumps(doc))
    got=v.judge_e1_v2(score,baseline,measured,plan,previous=None,
                      checkpoint=tmp_path/'model_250.pt',evaluation=tmp_path,seed=42)
    assert got['judgement']=='HOLD' and 'identity' in got['reason']


def test_valid_treatment_requires_startup_and_caller_plan_pins(tmp_path):
    from foothold_s2.tests.test_ex42_e1_v2_cpu import _write_segment,PLAN
    _write_segment(tmp_path,1)
    assert v.treatment(tmp_path/'model_500.pt',500,PLAN,expected_plan_sha256='a'*64)['state']=='complete'
    with pytest.raises(ValueError,match='identity'):
        v.treatment(tmp_path/'model_500.pt',500,PLAN,expected_plan_sha256='b'*64)
    for name in ('segment_commands_b1.json','segment_rewards_b1_rank0.json','segment_rewards_b1_rank1.json'):
        p=tmp_path/name;d=json.loads(p.read_text());d['plan_sha256']='c'*64;p.write_text(json.dumps(d))
    with pytest.raises(ValueError,match='identity'):
        v.treatment(tmp_path/'model_500.pt',500,PLAN,expected_plan_sha256='a'*64)


def test_nonobject_receipt_and_boolean_boundary_are_invalid(tmp_path):
    from foothold_s2.tests.test_ex42_e1_v2_cpu import _write_segment,PLAN
    _write_segment(tmp_path,1)
    p=tmp_path/'segment_rewards_b1_rank1.json'
    d=json.loads(p.read_text());d['boundary_index']=True;p.write_text(json.dumps(d))
    with pytest.raises(ValueError,match='identity'):
        v.treatment(tmp_path/'model_500.pt',500,PLAN)
    p.write_text('[]')
    with pytest.raises(ValueError,match='identity'):
        v.treatment(tmp_path/'model_500.pt',500,PLAN)
