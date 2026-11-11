import copy
import json
import pytest
from foothold_s2.eval.ex42_task_evidence import publish_case,read_case
from foothold_s2.eval.ex42_task_cells import sha256
from foothold_s2.tests.test_ex42_task_cells_cpu import trace,spec,anchors


def test_raw_recompute_rejects_role_counts_and_identity_mutations(tmp_path):
    s={**spec(),'case_id':'C_box_forward_eval_gt'}
    identity=dict(checkpoint_sha256='a'*64,seed=42,plan_sha256='b'*64,request_sha256='c'*64)
    row=publish_case(tmp_path,s,trace(),anchors=anchors(),identity=identity)
    assert read_case(row,s,anchors=anchors(),identity=identity)['success_count']==64
    for field,value in [('success_count',63),('role','record_only'),('checkpoint_sha256','d'*64)]:
        doc=json.loads((tmp_path/(s['case_id']+'.json')).read_text())
        changed=copy.deepcopy(doc);changed[field]=value
        (tmp_path/(s['case_id']+'.json')).write_text(json.dumps(changed))
        index={**row,field:value,'raw_sha256':sha256(row['raw_file'])}
        with pytest.raises(ValueError):read_case(index,s,anchors=anchors(),identity=identity)
        (tmp_path/(s['case_id']+'.json')).write_text(json.dumps(doc))


def test_existing_evidence_never_overwritten(tmp_path):
    s={**spec(),'case_id':'C_box_forward_eval_gt'};identity=dict(checkpoint_sha256='a'*64,seed=42,plan_sha256='b'*64,request_sha256='c'*64)
    publish_case(tmp_path,s,trace(),anchors=anchors(),identity=identity)
    with pytest.raises(FileExistsError):publish_case(tmp_path,s,trace(),anchors=anchors(),identity=identity)


def test_end_to_end_request_receipt_exact_list_and_cross_pair(tmp_path):
    from pathlib import Path
    from foothold_s2.terrains.ex42_eval_terrains import write_mesh
    from foothold_s2.eval.ex42_task_suite import create_request,validate_request
    from foothold_s2.eval.ex42_task_evidence import read_evidence,write_json,FORMAT
    from foothold_s2.eval.ex42_task_mesh import preflight
    p=Path(__file__).parents[1]/'curriculum/ex42-prep.yaml'
    checkpoint=tmp_path/'cpu_fixture.pt';checkpoint.write_bytes(b'CPU test identity, not a runnable model')
    source=tmp_path/'source';write_mesh(source,kinds=['eval_slope_35'],seed=42)
    path=create_request(plan_path=p,checkpoint=checkpoint,source_mesh=source,out=tmp_path/'request',
        family='V',kind='eval_slope_35',level=0,stage='E5',group='directions',window_index=2,steps=300)
    req=validate_request(path);identity={k:req[k] for k in ('checkpoint_sha256','plan_sha256','seed')}
    identity['request_sha256']=sha256(path)
    for flat in (True,False):
        folder=path.parent/('flat_result' if flat else 'result');folder.mkdir()
        replica=preflight(req[('flat_replica_dir' if flat else 'replica_dir')])['receipt']
        cases={}
        for name,s in req['case_specs'].items():
            t=trace(steps=300);t['command_b'][:]=s['command_b'];t['initial_yaw_rad'][:]=s['approach_yaw_rad']
            t['root_pos_w'][...,0]*=.8 if not flat else 1.
            cases[name]=publish_case(folder,s,t,anchors=replica['task_anchors'],identity=identity)
        write_json(folder/'task_cells.json',dict(format=FORMAT,state='done',flat_reference=flat,
            identity=identity,source_mesh_sha256=req['source_mesh_sha256'],replica_mesh_sha256=replica['mesh_sha256'],
            cases=cases,dr=None))
    result=read_evidence(path.parent/'result',request_path=path)
    assert len(result['rows'])==12
    assert result['cases']['eval_slope_35_reverse_eval_gt']['judgement']=='PASS'
    assert result['cases']['eval_slope_35_reverse_probe_prop_only']['judgement']=='RECORD'
    index=path.parent/'result/task_cells.json';doc=json.loads(index.read_text())
    doc['cases'].pop('eval_slope_35_reverse_eval_gt');index.write_text(json.dumps(doc))
    with pytest.raises(ValueError,match='case list'):read_evidence(path.parent/'result',request_path=path)
