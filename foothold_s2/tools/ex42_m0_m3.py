"""Pinned E2 mesh measurements. CPU inventory + lead-run Kit proxy + strict receipt.

CG:400 and lead 11/12 decision: M1 uses the actual saved-NPZ loading path,
first/repeat RSS and original generator receipt. OS caches are NOT evicted.
M2 is terrain collision/ray upload and ray buffers, NOT full RL/PPO VRAM.
M3 is the approved downward-grid proxy, NOT real camera latency or accuracy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import resource
import time

import numpy as np

FORMAT='foothold-ex42-m0-m3/1'
PROBE_FORMAT='foothold-ex42-m0-m3-kit/1'
ENV_COUNTS=(128,512,3072)
PATTERNS={'height_scan_proxy':187,'depth_proxy':3600,'combined_proxy':3787}
PROBE_SCOPE='terrain_collision_and_warp_upload_plus_downward_proxy_buffers_no_robot_no_PPO'
REPO=Path(__file__).resolve().parents[2]


def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()


def file_ref(path):
    p=Path(path).resolve(strict=True)
    return {'path':str(p),'sha256':sha(p)}


def read_ref(ref):
    p=Path(ref['path'])
    if sha(p)!=ref['sha256']: raise ValueError(f'SHA mismatch: {p}')
    return json.loads(p.read_text(encoding='utf-8'))


def write_once(path,doc):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    content=json.dumps(doc,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if path.exists():
        if path.read_text(encoding='utf-8')==content: return
        raise FileExistsError(path)
    with path.open('x',encoding='utf-8') as f: f.write(content)


def statistics(values):
    a=np.asarray(values,dtype=float)
    if a.ndim!=1 or not len(a) or not np.isfinite(a).all() or (a<=0).any():
        raise ValueError('timings must be finite positive samples')
    return {'count':len(a),'mean_s':float(a.mean()),'p50_s':float(np.median(a)),
            'p95_s':float(np.percentile(a,95)),'max_s':float(a.max())}


def memory_ok(free_gib):
    return isinstance(free_gib,(float,int)) and math.isfinite(free_gib) and free_gib>=2.


def rss_bytes():
    # Linux current resident bytes; keep ru_maxrss separately as a high-water value.
    import os
    return int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')


def identity(folder):
    folder=Path(folder).resolve(strict=True)
    manifest=json.loads((folder/'mesh_manifest.json').read_text())
    return {name:sha(folder/file) for name,file in (
        ('mesh_file_sha256','terrain_mesh.npz'),('mesh_manifest_sha256','mesh_manifest.json'),
        ('terrain_manifest_sha256','terrain_manifest.json'),('aggregate_sha256','aggregate_measurements.json'))} | {
            'geometry_sha256':manifest['mesh_sha256'],'seed':manifest['seed']}


def cpu_inventory(folder,table):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.terrains.ex42_mesh_mount import load_combined_mesh
    from foothold_s2.terrains.ex42_column_reset import build_column_table
    from foothold_s2.tools.ex42_mesh_flags import verify_annotation
    from foothold_s2.tools.ex42_execution_manifest import column_face_mask
    folder=Path(folder).resolve(strict=True)
    # Measure first access before verification warms the file in this process.
    # This is not a claim that the kernel/page/disk caches were cold.
    load_rows=[]
    for label in ('cold_first_process_read','warm_repeat_process_read'):
        rss_before=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        current_before=rss_bytes()
        t=time.perf_counter()
        data=load_combined_mesh(folder/'terrain_mesh.npz')
        with np.load(folder/'terrain_mesh.npz',allow_pickle=False) as z: flags=z['flags'].copy()
        load_rows.append({'label':label,'seconds':time.perf_counter()-t,
            'rss_before_bytes':current_before,'rss_after_bytes':rss_bytes(),
            'maxrss_before_bytes':rss_before,'maxrss_after_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024})
        if label.startswith('cold'): del data,flags
    proof=verify_annotation(folder)
    meta=json.loads((folder/'mesh_manifest.json').read_text())
    manifest=json.loads((folder/'terrain_manifest.json').read_text())
    plan=EX42Plan.load(table);plan.validate_terrain_manifest(manifest)
    if manifest['provenance']['aggregate_sha256']!=sha(folder/'aggregate_measurements.json'):
        raise ValueError('manifest aggregate SHA differs')
    if manifest['provenance']['flag_annotation']['mesh_file_sha256']!=sha(folder/'terrain_mesh.npz'):
        raise ValueError('terrain manifest binds another NPZ')
    aggregate=json.loads((folder/'aggregate_measurements.json').read_text())
    generation=meta['generation_seconds_by_family']
    if (set(generation)!=set(meta['families_present']) or any(not math.isfinite(v) or v<=0 for v in generation.values())
            or not math.isclose(sum(generation.values()),aggregate['generation_seconds'],rel_tol=1e-10)):
        raise ValueError('family generation times differ from aggregate')
    columns=build_column_table(data['column_family'])
    # Sizes come from the generating modules, not nominal handwritten values.
    from foothold_s2.terrains import ame2_preset as b,jeplo_preset as c,hipan_posture as d,sparse_terrains as a
    sizes={'A':a.TILE[0],'B':b.SIZE,'C':c.SIZE,'D':d.TILE_SIZE[0],'E':a.TILE[0]}
    v,f=data['vertices'],data['faces'];centroids=v[f].mean(1);rows=data['origins'].shape[0]
    sampled=[]
    for col,item in enumerate(columns):
        family=item['family'];n=data['column_family'].count(family)
        local_col=col-data['column_family'].index(family);s=sizes[family]
        mask=column_face_mask(centroids,columns=[local_col],total_columns=n,size=(s,s),rows=rows,offset=meta['offsets_m'][family])
        for level in (0,5,9):
            keep=mask & (centroids[:,0]>=-rows*s/2+level*s) & (centroids[:,0]<-rows*s/2+(level+1)*s)
            indices=np.unique(f[keep]);pts=v[indices]
            if not len(pts): raise ValueError(f'empty level geometry {family}/{item["kind"]}/{level}')
            sampled.append({'column':col,'family':family,'kind':item['kind'],'level':level,
                'face_count':int(keep.sum()),'bounds_m':[pts.min(0).tolist(),pts.max(0).tolist()],
                'origin_m':data['origins'][level,col].tolist(),
                'flags_xy_m':flags[level,col].tolist() if np.isfinite(flags[level,col]).all() else None})
    return {'format':FORMAT,'stage_id':'E2','mesh_dir':str(folder),'identity':identity(folder),
        'sources':{'mesh':file_ref(folder/'mesh_manifest.json'),'terrain':file_ref(folder/'terrain_manifest.json'),
            'aggregate':file_ref(folder/'aggregate_measurements.json'),'plan':file_ref(table),
            'plan_parent':file_ref(Path(table).parent/plan.document['stage_zero']['source']['path']),
            'plan_approvals':file_ref(Path(table).parent/plan.document['approval_file']),
            'original_mesh':file_ref(Path(proof['source'])/'mesh_manifest.json')},
        'M0':{'status':'measured','annotation_verification':proof,'column_table':columns,
            'kind_rows':len(manifest['kinds']),'unique_physical_kinds':len({(r['geometry_family'],r['kind']) for r in manifest['kinds']}),
            'sampled_levels':sampled,'height_representation':'actual triangle bounds per L0/L5/L9; original heightfields not stored'},
        'M1':{'status':'measured','loading':load_rows,'os_cache_evicted':False,
            'rss_kind':'current /proc/self/statm RSS and process lifetime ru_maxrss high-water',
            'generation_seconds_by_family':generation,'original_generation_seconds':aggregate['generation_seconds'],
            'flag_generation_seconds':meta['flag_generation_seconds'],
            'legacy_generator_cache':'not used by pinned NPZ load path; lead 11/12 CG:400 interpretation'},
        'training_started':False}


def probe_errors(probe,expected):
    errors=[]
    try:
        if probe['format']!=PROBE_FORMAT or probe['status']!='measured': errors.append('probe_incomplete')
        if probe['identity']!=expected: errors.append('probe_identity_mismatch')
        if probe['training_started'] is not False or probe['scope']!=PROBE_SCOPE: errors.append('probe_scope')
        if probe['contact_mesh_uploaded'] is not True or probe['warp_mesh_uploaded'] is not True: errors.append('upload_missing')
        if not 0<float(probe['elapsed_seconds'])<=600: errors.append('time_budget')
        if [r['num_envs'] for r in probe['rows']]!=list(ENV_COUNTS): errors.append('memory_size_sequence')
        expected_cases={(p,r) for p in PATTERNS for r in (False,True)}
        for row in probe['rows']:
            memory=row['memory']
            if not memory_ok(memory['free_min_gib']): errors.append('memory_headroom')
            if any(not math.isfinite(memory[k]) or memory[k]<0 for k in ('allocated_gib','reserved_gib','max_allocated_gib','max_reserved_gib')): errors.append('memory_invalid')
            casts=row['casts']
            if len(casts)!=6 or {(r['pattern'],r['reset_proxy']) for r in casts}!=expected_cases: errors.append('ray_cases')
            for r in casts:
                if r['rays_per_env']!=PATTERNS[r['pattern']] or r['warmup']!=20 or len(r['timings_s'])!=100: errors.append('ray_contract')
                if len(r['cuda_event_s'])!=100: errors.append('cuda_event_count')
                statistics(r['cuda_event_s'])
                statistics([r['cold_s']])
                stats=statistics(r['timings_s'])
                if any(not math.isclose(float(stats[k]),float(r['statistics'][k]),rel_tol=1e-10) for k in stats): errors.append('ray_statistics')
    except (KeyError,TypeError,ValueError,OverflowError): errors.append('malformed_probe')
    return sorted(set(errors))


def assemble(cpu,probe):
    blockers=[name+'_missing' for name in ('M0','M1') if cpu.get(name,{}).get('status')!='measured']
    blockers+=['M2_M3_missing'] if probe is None else probe_errors(probe,cpu['identity'])
    return dict(cpu,status='HOLD' if blockers else 'PASS',blockers=blockers,
        M2={'status':'missing' if probe is None else ('measured' if not blockers else 'incomplete')},
        M3={'status':'missing' if probe is None else ('measured' if not blockers else 'incomplete'),
            'scope':'downward-grid proxy, not camera accuracy/latency'},kit_probe=probe)


def attach_contract(doc,cpu_ref,probe_ref=None):
    folder=Path(doc['mesh_dir'])
    doc['cpu_ref']=cpu_ref
    doc['probe_ref']=probe_ref
    doc['mesh']={'geometry_sha256':doc['identity']['geometry_sha256'],
        'files':{f:file_ref(folder/f) for f in ('terrain_mesh.npz','mesh_manifest.json','terrain_manifest.json')}}
    doc['checks']={}
    for name in ('M0','M1','M2','M3'):
        ref=cpu_ref if name in ('M0','M1') else probe_ref
        passed=doc[name]['status']=='measured' and ref is not None
        doc['checks'][name]={'status':'PASS' if passed else 'HOLD','evidence':[ref] if ref else []}
    return doc


def verify_receipt(path,expected_sha256,*,mesh_dir):
    """Consumer entry. Hash refs + current NPZ identity + raw timing recount, no claimed PASS trust."""
    doc=read_ref({'path':str(path),'sha256':expected_sha256})
    if doc.get('format')!=FORMAT or doc.get('stage_id')!='E2' or doc.get('identity')!=identity(mesh_dir):
        raise ValueError('M0-M3 identity mismatch')
    cpu=read_ref(doc['cpu_ref'])
    if any(cpu.get(k)!=doc.get(k) for k in ('identity','M0','M1')):
        raise ValueError('CPU raw receipt differs')
    expected_contract=attach_contract(dict(doc),doc['cpu_ref'],doc.get('probe_ref'))
    if doc['mesh']!=expected_contract['mesh'] or doc['checks']!=expected_contract['checks']:
        raise ValueError('M0-M3 consumer contract differs')
    for ref in doc['sources'].values(): read_ref(ref) if Path(ref['path']).suffix=='.json' else _check_ref(ref)
    fresh=cpu_inventory(mesh_dir,doc['sources']['plan']['path'])
    if doc['M0']!=json.loads(json.dumps(fresh['M0'],allow_nan=False)):
        raise ValueError('M0 inventory differs from actual mesh')
    for key in ('generation_seconds_by_family','original_generation_seconds','flag_generation_seconds','legacy_generator_cache'):
        if doc['M1'].get(key)!=fresh['M1'][key]: raise ValueError('M1 source generation differs')
    loading=doc['M1'].get('loading',[])
    if [r.get('label') for r in loading]!=['cold_first_process_read','warm_repeat_process_read']:
        raise ValueError('M1 read timing pair missing')
    statistics([r['seconds'] for r in loading])
    for r in loading:
        if not (0<r['maxrss_before_bytes']<=r['maxrss_after_bytes']): raise ValueError('M1 RSS invalid')
    if doc.get('probe_ref'):
        if Path(doc['probe_ref']['path']).with_suffix('.timeout.json').exists():
            raise ValueError('Kit probe timeout marker present')
        if read_ref(doc['probe_ref'])!=doc.get('kit_probe'): raise ValueError('probe raw receipt differs')
    rebuilt=assemble(doc,doc.get('kit_probe'))
    if doc.get('status')!=rebuilt['status'] or doc.get('blockers')!=rebuilt['blockers']:
        raise ValueError('M0-M3 verdict differs from raw measurements')
    if rebuilt['status']!='PASS': raise ValueError('M0-M3 incomplete: '+','.join(rebuilt['blockers']))
    return rebuilt


def _check_ref(ref):
    if sha(ref['path'])!=ref['sha256']: raise ValueError('SHA mismatch')


def pin_plan(table,destination):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    table=Path(table);plan=EX42Plan.load(table)
    source_name=plan.document['stage_zero']['source']['path']
    approval_name=plan.document['approval_file']
    if Path(approval_name).name!=approval_name: raise ValueError('approval must be a sibling filename')
    pinned=Path(destination)/('plan-'+sha(table)+'.yaml')
    pinned.parent.mkdir(parents=True,exist_ok=True)
    for src,dst in ((table.parent/source_name,pinned.parent/source_name),
                    (table.parent/approval_name,pinned.parent/approval_name),(table,pinned)):
        content=src.read_bytes()
        if dst.exists():
            if dst.read_bytes()!=content: raise ValueError('pinned plan dependency differs')
        else:
            with dst.open('xb') as f: f.write(content)
    EX42Plan.load(pinned)
    return pinned


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mesh-dir',type=Path,required=True)
    p.add_argument('--table',type=Path,default=REPO/'foothold_s2/curriculum/ex42-prep.yaml')
    p.add_argument('--probe',type=Path)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(argv)
    # Preserve the exact table used for this readback. A later branch switch must
    # not invalidate the evidence by changing a worktree-local source file.
    pinned=pin_plan(args.table,args.out.parent)
    cpu=cpu_inventory(args.mesh_dir,pinned)
    probe=json.loads(args.probe.read_text()) if args.probe else None
    result=assemble(cpu,probe)
    cpu_path=args.out.with_name(args.out.stem+'.cpu.json')
    write_once(cpu_path,cpu)
    attach_contract(result,file_ref(cpu_path),file_ref(args.probe) if args.probe else None)
    write_once(args.out,result)
    print(json.dumps({'status':result['status'],'blockers':result['blockers'],'receipt':file_ref(args.out)}))
    return 0 if result['status']=='PASS' else 2


if __name__=='__main__': raise SystemExit(main())
