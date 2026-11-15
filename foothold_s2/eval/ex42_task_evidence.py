"""Immutable per-case NPZ/JSON receipts, with the #664 case-list convention."""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np

from foothold_s2.eval.ex42_task_cells import sha256,summarize,judge_counts,compare_cross_direction
from foothold_s2.eval.ex42_task_suite import validate_request
from foothold_s2.eval.ex42_task_mesh import preflight

FORMAT='foothold-ex42-task-eval/1'


def write_json(path,doc):
    with Path(path).open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(doc,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def publish_case(folder,spec,trace,*,anchors,identity):
    folder=Path(folder);case=spec['case_id'];raw=folder/(case+'.npz');js=folder/(case+'.json')
    if raw.exists() or js.exists():raise FileExistsError(case)
    result=summarize(trace,spec=spec,anchors=anchors)
    with raw.open('xb') as stream:np.savez_compressed(stream,**trace)
    row={**result,**identity,'case_id':case,'task':spec['task'],'role':spec['role'],
         'trace_file':str(raw.resolve()),'trace_sha256':sha256(raw)}
    write_json(js,row)
    return {k:row[k] for k in ('case_id','task','role','map_mode','envs','valid_count','success_count',
        'survival_count','trace_file','trace_sha256')}|{'raw_file':str(js.resolve()),'raw_sha256':sha256(js)}


def read_case(index,spec,*,anchors,identity):
    raw=Path(index['raw_file']);npz=Path(index['trace_file'])
    if raw.stem!=spec['case_id'] or npz.stem!=spec['case_id'] or raw.parent!=npz.parent:
        raise ValueError('case file identity differs')
    if sha256(raw)!=index['raw_sha256'] or sha256(npz)!=index['trace_sha256']:
        raise ValueError('case bytes changed')
    row=json.loads(raw.read_text(encoding='utf-8'))
    for key,value in identity.items():
        if row.get(key)!=value:raise ValueError('case identity differs: '+key)
    for key in ('case_id','task','map_mode','role'):
        if row.get(key)!=spec[key] or index.get(key)!=spec[key]:raise ValueError('case contract differs: '+key)
    if row.get('trace_file')!=str(npz) or row.get('trace_sha256')!=index['trace_sha256']:
        raise ValueError('case trace pointer differs')
    with np.load(npz,allow_pickle=False) as data:
        result=summarize(data,spec=spec,anchors=anchors)
    for key,value in result.items():
        if row.get(key)!=value:raise ValueError('case raw recomputation differs: '+key)
    for key in ('envs','valid_count','success_count','survival_count'):
        if index.get(key)!=result[key]:raise ValueError('case index count differs: '+key)
    return row


def read_evidence(folder,*,request_path,flat_reference=False):
    """Returns all rows, judgment rows separately, and no silent missing cells."""
    folder=Path(folder).resolve();request_path=Path(request_path).resolve();req=validate_request(request_path)
    doc=json.loads((folder/'task_cells.json').read_text(encoding='utf-8'))
    expected_identity={k:req[k] for k in ('checkpoint_sha256','plan_sha256','seed')}
    expected_identity['request_sha256']=sha256(request_path)
    if (doc.get('format')!=FORMAT or doc.get('state')!='done' or doc.get('flat_reference')!=flat_reference
            or doc.get('identity')!=expected_identity or set(doc.get('cases',{}))!=set(req['case_specs'])):
        raise ValueError('task suite identity or exact case list differs')
    key='flat_replica' if flat_reference else 'replica'
    data=preflight(req[key+'_dir']);meta=data['receipt']
    if doc.get('replica_mesh_sha256')!=meta['mesh_sha256'] or doc.get('source_mesh_sha256')!=req['source_mesh_sha256']:
        raise ValueError('task suite terrain identity differs')
    anchors=meta['task_anchors']
    rows={}
    for case,spec in req['case_specs'].items():
        index=doc['cases'][case]
        if Path(index['raw_file']).parent!=folder:raise ValueError('case output escapes suite')
        rows[case]=read_case(index,spec,anchors=anchors,identity=expected_identity)
    if req['dr_mode']=='on':
        dr=doc.get('dr')
        if not isinstance(dr,dict) or dr.get('mode')!='on' or dr.get('scale')!=1. or dr.get('table_sha256')!=req['dr_table_sha256']:
            raise ValueError('G18 actual DR evidence missing')
        if set(dr.get('readback',{}))!=set(rows):raise ValueError('G18 incomplete per-case readback')
        if any(len(v.get('push_events',[]))!=1 for v in dr['readback'].values()):raise ValueError('G18 push not fired exactly once')
    elif doc.get('dr') is not None:raise ValueError('DR-on evidence in task judgment')
    if flat_reference:return {'rows':rows,'role':'record_only','flat_reference':True}
    flat=None
    if 'flat_replica_dir' in req:
        flat=read_evidence(Path(request_path).parent/'flat_result',request_path=request_path,flat_reference=True)['rows']
    judgments={}
    for case,spec in req['case_specs'].items():
        row=rows[case]
        if spec['task']=='cross_dir_half_flat':
            result=compare_cross_direction(row,flat[case],window_index=req['window_index'],settings=req['cross_settings'])
        else:result=judge_counts(row,valid_min=spec['valid_min'],success_min=spec['success_min'],survival_min=spec['survival_min'])
        if spec['role']=='record_only':result={**result,'role':'record_only','judgement':'RECORD'}
        else:result['role']='judge'
        judgments[case]=result
    return {'rows':rows,'cases':judgments,'judge_rows':{k:rows[k] for k in req['judge_cases']},
            'receipt_file':str(folder/'task_cells.json'),'receipt_sha256':sha256(folder/'task_cells.json')}
