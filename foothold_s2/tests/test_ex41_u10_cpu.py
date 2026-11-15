"""Known per-knee occupancy and exact score-record provenance, without GPU."""
import copy
import json
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.rewards import w86_runtime as wr
from foothold_s2.curriculum import ex41_scoring
from foothold_s2.tests.test_w86_runtime_cpu import sample


def measured(tmp_path):
    env=SimpleNamespace(num_envs=3,device='cpu',step_dt=.02,common_step_counter=1)
    data=sample(); data['knee_ids']=[8,9,10,11]
    data['torque'][:,8:]=torch.tensor([[18.,17.9,20.,0.],[0.,-18.,19.,0.],[20.,20.,20.,20.]])
    data['physical_valid'][2]=False  # Exclude corruption from denominator.
    runtime=wr.W86Runtime(env,tmp_path,source=lambda:data)
    runtime.refresh()
    return runtime.flush(250)


def test_knee_ratios_have_named_numerator_and_valid_denominator(tmp_path):
    row=measured(tmp_path)
    knees=row['knee_effort']
    assert knees['threshold_fraction']==.9 and knees['record_only'] is True
    assert list(knees['joints'])==list(wr.KNEES)
    assert [v['near_limit_frames'] for v in knees['joints'].values()]==[1,1,2,0]
    assert [v['valid_frames'] for v in knees['joints'].values()]==[2]*4
    assert [v['ratio'] for v in knees['joints'].values()]==[.5,.5,1.,0.]


def test_real_curriculum_flush_writes_attached_w86_metrics(tmp_path):
    from foothold_s2.tests.ex41_runtime_fixture import real_runtime
    runtime,runner=real_runtime(tmp_path/'runtime')
    runtime.runner=runner
    env=runner.env.unwrapped
    env.scene.terrain.cfg=SimpleNamespace(terrain_generator=SimpleNamespace(
        curriculum=True,num_cols=2,num_rows=10,
        sub_terrains={'flat':SimpleNamespace(proportion=.5),'rough':SimpleNamespace(proportion=.5)}))
    env.scene.terrain.terrain_types=torch.tensor([0,1,0,1])
    env.num_envs=3; env.device='cpu'; env.step_dt=.02; env.common_step_counter=1
    env._ex41_w86=wr.W86Runtime(env,tmp_path/'metrics',source=sample)
    env._ex41_w86.refresh()
    runtime.flush_consumption(250)
    rows=[json.loads(x) for x in (tmp_path/'metrics/ex41_w86.jsonl').read_text().splitlines()]
    assert len(rows)==1 and rows[0]['iteration']==250
    assert rows[0]['knee_effort']['joints'][wr.KNEES[0]]['valid_frames']==3


def test_score_uses_same_iteration_record_and_retains_evidence_hash(tmp_path):
    row=measured(tmp_path)
    fn=ex41_scoring.enrich_training_metrics
    draft={'iteration':250,'metrics':{},'evidence':[]}
    source=tmp_path/'ex41_w86.jsonl'
    result=fn(draft,source,snapshot_dir=tmp_path/'snapshots')
    assert result['metrics']['training_knee_effort']==row['knee_effort']
    evidence=result['evidence'][0]
    from pathlib import Path
    snapshot=Path(evidence['path'])
    assert evidence['sha256']==ex41_scoring.sha256(snapshot)
    assert json.loads(snapshot.read_text())['record']==row
    with source.open('a') as out:out.write(json.dumps(dict(row,iteration=300))+'\n')
    assert evidence['sha256']==ex41_scoring.sha256(snapshot)
    assert draft=={'iteration':250,'metrics':{},'evidence':[]}
    with pytest.raises(ValueError,match='missing'):
        fn(dict(draft,iteration=251),source,snapshot_dir=tmp_path/'snapshots')


@pytest.mark.parametrize('bad',['ratio_lie','missing_knee','duplicate_iteration','nan'])
def test_training_score_rejects_false_ratios_and_duplicate_records(tmp_path,bad):
    row=measured(tmp_path); broken=copy.deepcopy(row)
    fn=ex41_scoring.enrich_training_metrics
    knee=broken['knee_effort']['joints'][wr.KNEES[0]]
    if bad=='ratio_lie': knee['ratio']=.2
    elif bad=='missing_knee': del broken['knee_effort']['joints'][wr.KNEES[1]]
    elif bad=='nan': knee['ratio']=float('nan')
    source=tmp_path/'bad.jsonl'
    source.write_text(json.dumps(broken)+'\n'+(json.dumps(broken)+'\n' if bad=='duplicate_iteration' else ''),encoding='utf-8')
    with pytest.raises(ValueError):fn({'iteration':250,'metrics':{},'evidence':[]},source,snapshot_dir=tmp_path/'snapshots')
