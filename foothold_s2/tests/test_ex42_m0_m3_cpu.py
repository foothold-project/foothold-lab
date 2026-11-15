import copy
import json
import numpy as np
import pytest
from foothold_s2.tools import ex42_m0_m3 as m


def test_known_timing_input_and_nonfinite_rejected():
    assert m.statistics([1., 2., 3.]) == {'count': 3, 'mean_s': 2., 'p50_s': 2., 'p95_s': 2.9, 'max_s': 3.}
    for values in ([], [float('nan')], [float('inf')], [0.], [-1.]):
        with pytest.raises(ValueError): m.statistics(values)


def sample_probe():
    rows=[]
    for n in m.ENV_COUNTS:
        rows.append({'num_envs': n, 'memory': {'free_min_gib': 3., 'allocated_gib': .5,
            'reserved_gib': .7, 'max_allocated_gib': .6, 'max_reserved_gib': .8},
            'casts': [{ 'pattern': p, 'reset_proxy': reset, 'rays_per_env': rays,
                'warmup':20, 'cold_s':.1, 'timings_s':[.01]*100, 'cuda_event_s':[.009]*100,
                'statistics':m.statistics([.01]*100)}
                for p,rays in m.PATTERNS.items() for reset in (False,True)]})
    return {'format':m.PROBE_FORMAT,'status':'measured','identity':{'mesh_file_sha256':'a'*64},
        'contact_mesh_uploaded':True,'warp_mesh_uploaded':True,'training_started':False,
        'scope':m.PROBE_SCOPE,'elapsed_seconds':20.,'rows':rows}


def test_complete_probe_requires_all_sizes_and_patterns():
    p=sample_probe(); assert m.probe_errors(p,p['identity']) == []
    for change in ('size','pattern','low_free','nan','stats','identity','status','contact','time'):
        d=copy.deepcopy(p)
        if change=='size': d['rows'].pop(1)
        if change=='pattern': d['rows'][0]['casts'].pop()
        if change=='low_free': d['rows'][1]['memory']['free_min_gib']=1.99
        if change=='nan': d['rows'][2]['casts'][0]['timings_s'][2]=float('nan')
        if change=='stats': d['rows'][2]['casts'][0]['statistics']['mean_s']=9.
        if change=='identity': d['identity']={}
        if change=='status': d['status']='timeout'
        if change=='contact': d['contact_mesh_uploaded']=False
        if change=='time': d['elapsed_seconds']=601.
        assert m.probe_errors(d,p['identity']), change


def test_cpu_manifest_is_never_complete_without_probe():
    cpu={'identity':{'mesh_file_sha256':'a'*64},'M0':{'status':'measured'},'M1':{'status':'measured'}}
    result=m.assemble(cpu,None)
    assert result['status']=='HOLD' and result['blockers']==['M2_M3_missing']
    result=m.assemble(cpu,sample_probe())
    assert result['status']=='PASS'
    cpu['M0']['status']='missing'
    assert m.assemble(cpu,sample_probe())['status']=='HOLD'


def test_receipts_are_immutable_and_hash_checked(tmp_path):
    p=tmp_path/'r.json';m.write_once(p,{'x':1})
    ref=m.file_ref(p)
    assert m.read_ref(ref)=={'x':1}
    with pytest.raises(FileExistsError): m.write_once(p,{'x':2})
    p.write_text('{"x":3}')
    with pytest.raises(ValueError,match='SHA'): m.read_ref(ref)


def test_memory_guard_stops_before_next_size():
    assert m.memory_ok(2.)
    assert not m.memory_ok(1.999)
    assert not m.memory_ok(float('nan'))


def test_kit_help_is_cpu_only_and_wrong_pin_fails_before_import(tmp_path):
    import subprocess,sys,os
    env=os.environ|{'CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1'}
    cmd=[sys.executable,'-m','foothold_s2.scripts.ex42_m0_m3_probe']
    p=subprocess.run(cmd+['--help'],capture_output=True,text=True,env=env)
    assert p.returncode==0 and '--expected-npz-sha256' in p.stdout
    # A minimally-shaped directory must not get as far as importing Isaac.
    for filename in ('terrain_mesh.npz','terrain_manifest.json','aggregate_measurements.json'):
        (tmp_path/filename).write_text('{}')
    (tmp_path/'mesh_manifest.json').write_text(json.dumps({'mesh_sha256':'b'*64,'seed':42}))
    p=subprocess.run(cmd+['--mesh-dir',str(tmp_path),'--out',str(tmp_path/'probe.json'),
        '--device','cuda:1','--expected-npz-sha256','a'*64],capture_output=True,text=True,env=env)
    assert p.returncode!=0 and 'pinned NPZ SHA mismatch before Kit' in p.stderr
    assert not (tmp_path/'probe.json').exists()


def test_real_e2_receipt_is_hold_and_binds_source_files():
    folder=m.Path('/home/jay/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333_flags_E2_1111_v2')
    if not folder.exists(): pytest.skip('local raw E2 mesh not present')
    cpu=m.cpu_inventory(folder,m.REPO/'foothold_s2/curriculum/ex42-prep.yaml')
    assert cpu['identity']['mesh_file_sha256']=='59b0bf3e3023f40da828b86eebff4513222e13452c70fc49b8951d7e8d42d771'
    assert cpu['M0']['kind_rows']==46 and cpu['M0']['unique_physical_kinds']==39
    assert len(cpu['M0']['column_table'])==76 and len(cpu['M0']['sampled_levels'])==228
    assert cpu['M1']['original_generation_seconds']==pytest.approx(9.176870384999347)
    assert m.assemble(cpu,None)['status']=='HOLD'
    for ref in cpu['sources'].values(): assert m.sha(ref['path'])==ref['sha256']


def test_pinned_plan_includes_relative_ex41_dependency(tmp_path):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    source=m.REPO/'foothold_s2/curriculum/ex42-prep.yaml'
    p=m.pin_plan(source,tmp_path)
    assert m.sha(p)==m.sha(source)
    plan=EX42Plan.load(p)
    assert (tmp_path/plan.document['stage_zero']['source']['path']).is_file()
    assert m.pin_plan(source,tmp_path)==p


def test_real_pending_receipt_cannot_be_promoted_by_changing_status(tmp_path):
    source=m.Path('/home/jay/mai/tmp/analyst-lx/e2-m0m3-1112/m0-m3-pending.json')
    if not source.exists(): pytest.skip('local CPU measurement not present')
    doc=json.loads(source.read_text())
    with pytest.raises(ValueError,match='incomplete'):
        m.verify_receipt(source,m.sha(source),mesh_dir=doc['mesh_dir'])
    doc['status']='PASS';doc['blockers']=[]
    for r in doc['checks'].values():r['status']='PASS'
    forged=tmp_path/'forged.json';m.write_once(forged,doc)
    with pytest.raises(ValueError,match='contract|verdict'):
        m.verify_receipt(forged,m.sha(forged),mesh_dir=doc['mesh_dir'])


def test_cpu_api_has_not_bootstrapped_kit():
    import sys
    assert 'isaaclab.app' not in sys.modules
