"""Known flag traces -> W09/W08 -> immutable materialize, without Kit."""
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
import yaml

from foothold_s2.tests import test_ex42_materialize_cpu as parent_tests

known = parent_tests.known
sha, dump = parent_tests.sha, parent_tests.dump


def flags():
    specs = {f'{count}_{mode}': {'count':count, 'map_mode':mode,
        'role':'record_only' if mode == 'probe_prop_only' else 'judge'}
        for count in ('flag_one','flag_four') for mode in ('eval_gt','eval_pred','probe_prop_only')}
    return dict(reach_radius_m=.3,stop_hold_s=.5,stop_speed_mps=.05,seconds=12.,flag_speed_mps=1.,
                repeat_seeds=[42,42,43,44,45],calibration={'path':None,'sha256':None},
                judge_cases=[k for k,v in specs.items() if v['role']=='judge'],
                record_cases=[k for k,v in specs.items() if v['role']=='record_only'],case_specs=specs)


def write_round(root, plan, plan_sha, checkpoint_sha, mesh_sha, seed):
    from foothold_s2.eval.ex42_flag_cells import score_trace
    from foothold_s2.eval.fixed_terrain import fixed_assignment, assignment_sha256
    levels, types = fixed_assignment(64,10,23)
    for name,count in [('flag_one',1),('flag_four',4)]:
        folder=root/'flag_cells'/name; folder.mkdir(parents=True)
        rec=dict(format='foothold-ex42-flag-eval/1',state='done',plan_sha256=plan_sha,
                 checkpoint_sha256=checkpoint_sha,mesh_sha256=mesh_sha,seed=seed,envs=64,count=name,cases={})
        for mode in ('eval_gt','eval_pred','probe_prop_only'):
            case=f'{name}_{mode}'; spec=plan['evaluation']['flag_cells']['case_specs'][case]
            targets=np.array([[.5+j,0] for j in range(count)])
            pos=np.zeros((120,64,3));vel=np.zeros_like(pos)
            for t in range(120): pos[t,:,0]=targets[min(t//10,count-1),0]
            trace=dict(root_pos_w=pos,root_vel_w=vel,alive=np.ones((120,64),bool),
                flags_w=np.broadcast_to(targets,(64,count,2)).copy(),dt=np.array(.1),
                env_origins_w=np.zeros((64,3)),terrain_levels=levels,terrain_types=types)
            npz=folder/(case+'.npz');np.savez_compressed(npz,**trace)
            row=dict(case_id=case,**spec,**score_trace(trace,spec,plan['evaluation']['flag_cells']),
                trace_file=str(npz),trace_sha256=sha(npz),fixed_terrain=dict(cols=23,assignment_sha256=assignment_sha256(levels,types)))
            raw=folder/(case+'.json');dump(raw,row)
            rec['cases'][case]={k:row[k] for k in ('trace_file','trace_sha256','envs','valid_count','success_count','survival_count')}
            rec['cases'][case].update(raw_file=str(raw),raw_sha256=sha(raw))
        dump(folder/'flag_cells.json',rec)
    dump(root/'round_receipt.json',dict(format='foothold-ex42-flag-round/1',state='complete',seed=seed,
        checkpoint_sha256=checkpoint_sha,plan_sha256=plan_sha,mesh_sha256=mesh_sha,failures={},
        steps={n:{'state':'done','rc':0} for n in ('flag_one','flag_four')}))


@pytest.fixture
def ready(known):
    from foothold_s2.eval.ex42_flag_cells import read_evidence, summarize_repeats
    # Keep the actual E1 source plan/gate frozen while adding flags to the new template.
    original=known['plan'].parent/'original-e1.yaml';original.write_bytes(known['plan'].read_bytes());known['source_plan']=original
    doc=yaml.safe_load(known['plan'].read_text());doc['evaluation']['flag_cells']=flags()
    known['plan'].write_text(yaml.safe_dump(doc))
    flag_plan=known['plan'].parent/'flag-eval.yaml';flag_plan.write_bytes(known['plan'].read_bytes())
    cp=known['parent_manifest'].parent/'model_1000.pt';cp_sha=sha(cp)
    root=known['out'].parent/'flag-chain';root.mkdir()
    mesh_sha='a'*64;rounds=[]
    mesh_dir=root/'mesh';mesh_dir.mkdir();mesh_file=mesh_dir/'terrain_mesh.npz';mesh_file.write_bytes(b'known mounted mesh bytes')
    dump(mesh_dir/'mesh_manifest.json',dict(format='foothold-ex42-combined-mesh/1',seed=42,mesh_sha256=mesh_sha,mesh_file_sha256=sha(mesh_file)))
    for i,seed in enumerate([42,42,42,43,44,45]):
        folder=root/f'round_{i}';write_round(folder,doc,sha(flag_plan),cp_sha,mesh_sha,seed)
        rounds.append({'root':str(folder),'seed':seed})
    cases={};receipts={}
    for name in ('flag_one','flag_four'):
        folder=Path(rounds[0]['root'])/'flag_cells'/name
        cases.update(read_evidence(folder,plan=doc,plan_sha256=sha(flag_plan),checkpoint_sha256=cp_sha,seed=42,count=name))
        receipts[name]={'path':str(folder/'flag_cells.json'),'sha256':sha(folder/'flag_cells.json')}
    baseline=dump(root/'w09_baseline.json',dict(format='foothold-ex42-w09-flag-baseline/1',state='measured',
        checkpoint_sha256=cp_sha,plan_sha256=sha(flag_plan),mesh_sha256=mesh_sha,seed=42,receipts=receipts,judge_cells=cases))
    cal=summarize_repeats([Path(r['root'])/'flag_cells' for r in rounds[1:]],plan=doc,
                         plan_sha256=sha(flag_plan),checkpoint_sha256=cp_sha)
    calibration=dump(root/'w08_calibration.json',cal)
    chain=root/'chain_receipt.json';dump(chain,dict(format='foothold-ex42-w09-w08-chain/1',state='complete',
        checkpoint=str(cp),checkpoint_sha256=cp_sha,
        e1_gate=dict(path=str(known['gate_receipt']),sha256=sha(known['gate_receipt']),
                     measurement=json.loads(known['gate_receipt'].read_text())['measurement'],
                     measurement_sha256=json.loads(known['gate_receipt'].read_text())['measurement_sha256']),plan=str(flag_plan),plan_sha256=sha(flag_plan),
        mesh_sha256=mesh_sha,mesh_dir=str(mesh_dir),rounds=rounds,w09_baseline=baseline,w08_calibration=calibration))
    ev=json.loads(known['evidence'].read_text());ev['bindings']['prerequisites.flag_baseline.sha256']=baseline;ev['bindings']['prerequisites.predecessor_exit.evaluation_mesh_sha256']={'path':str(mesh_file),'sha256':sha(mesh_file)};dump(known['evidence'],ev)
    known['flag_chain']=chain
    return known


def test_cli_materialize_only_pins_calibration_and_replays_transition(ready):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_stage_materialize import validate_materialized_transition
    before={p:p.read_bytes() for p in [ready['plan'],ready['source_plan'],ready['approvals'],ready['gate_receipt']]}
    cmd=[sys.executable,'-m','foothold_s2.ex42_stage_materialize','--materialize-only',
         '--expected-flag-chain-sha256',sha(ready['flag_chain'])]
    for name,value in ready.items(): cmd.extend(['--'+name.replace('_','-'),str(value)])
    completed=subprocess.run(cmd,capture_output=True,text=True)
    assert completed.returncode==0, completed.stdout+completed.stderr
    result=json.loads(completed.stdout);assert result['training_started'] is False
    plan=EX42Plan.load(result['plan']);a=yaml.safe_load(Path(result['approvals']).read_text())
    chain=json.loads(ready['flag_chain'].read_text())
    assert plan.document['evaluation']['flag_cells']['calibration']==chain['w08_calibration']
    assert plan.document['evaluation']['flag_cells']['calibration_sha256']==chain['w08_calibration']['sha256']
    assert a['stage_e1f_authorization']['prerequisites']['calibration_sha256']==chain['w08_calibration']['sha256']
    assert a['stage_e1f_authorization']['prerequisites']['flag_baseline']['sha256']==chain['w09_baseline']['sha256']
    assert plan.document['assumptions_pending_lead']['q4_two_window_range']==yaml.safe_load(ready['plan'].read_text())['assumptions_pending_lead']['q4_two_window_range']
    validate_materialized_transition(plan,target_stage='E1F',gate_receipt_path=ready['gate_receipt'],expected_gate_sha256=sha(ready['gate_receipt']))
    from foothold_s2.ex42_e1f_judge import _calibration
    from foothold_s2.ex42_auto_authorization import validate_automatic_stage_launch
    assert _calibration(plan.document)['judgement']=='PASS'
    launch_proof=validate_automatic_stage_launch(plan,result['approvals'],target_stage='E1F',
        parent_manifest_path=ready['parent_manifest'],gate_receipt_path=ready['gate_receipt'],
        expected_gate_sha256=sha(ready['gate_receipt']))
    assert launch_proof['scope']['maximum_updates']==750
    assert all(p.read_bytes()==value for p,value in before.items())
    again=subprocess.run(cmd,capture_output=True,text=True)
    assert again.returncode==2


@pytest.mark.parametrize('bad', ['incomplete','missing_repeat','wrong_parent','wrong_plan','raw_tamper',
                                  'calibration_forged','baseline_forged','round_hold','wrong_mesh','binding_mismatch','wrong_gate','child_rc'])
def test_invalid_chain_publishes_no_plan(ready,bad):
    from foothold_s2.ex42_stage_materialize import materialize
    chain=json.loads(ready['flag_chain'].read_text())
    if bad=='incomplete':chain['state']='running'
    elif bad=='missing_repeat':chain['rounds'].pop()
    elif bad=='wrong_parent':chain['checkpoint_sha256']='0'*64
    elif bad=='wrong_plan':chain['plan_sha256']='0'*64
    elif bad=='wrong_gate':chain['e1_gate']['sha256']='0'*64
    elif bad=='raw_tamper':
        p=Path(chain['rounds'][1]['root'])/'flag_cells/flag_four/flag_four_eval_gt.npz';p.write_bytes(b'broken')
    elif bad in ('calibration_forged','baseline_forged'):
        key='w08_calibration' if bad.startswith('calibration') else 'w09_baseline'
        p=Path(chain[key]['path']);d=json.loads(p.read_text())
        if key=='w08_calibration':d['repeat_width']['flag_four_eval_gt']['success_count']=8
        else:d['judge_cells']['flag_one_eval_gt']['success_count']=0
        chain[key]=dump(p,d)
        if key=='w09_baseline':
            ev=json.loads(ready['evidence'].read_text());ev['bindings']['prerequisites.flag_baseline.sha256']=chain[key];dump(ready['evidence'],ev)
    elif bad=='child_rc':
        p=Path(chain['rounds'][2]['root'])/'round_receipt.json';d=json.loads(p.read_text());d['steps']['flag_one']['rc']=1;dump(p,d)
    elif bad in ('round_hold','wrong_mesh'):
        p=Path(chain['rounds'][2]['root'])/'round_receipt.json';d=json.loads(p.read_text());d['state' if bad=='round_hold' else 'mesh_sha256']='HOLD' if bad=='round_hold' else 'b'*64;dump(p,d)
    else:
        ev=json.loads(ready['evidence'].read_text());ev['bindings']['prerequisites.flag_baseline.sha256']['sha256']='0'*64;dump(ready['evidence'],ev)
    dump(ready['flag_chain'],chain)
    with pytest.raises((ValueError,OSError,KeyError)):materialize(**ready)
    assert not ready['out'].exists()


def test_inputs_match_pinned_688_producer_functions(ready):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.scripts.ex42_flag_baseline_chain import make_baseline, make_calibration
    chain=json.loads(ready['flag_chain'].read_text());plan=EX42Plan.load(chain['plan'])
    baseline=make_baseline(Path(chain['rounds'][0]['root']),plan=plan,
        checkpoint_sha256=chain['checkpoint_sha256'],mesh_sha256=chain['mesh_sha256'],seed=42)
    calibration=make_calibration([Path(r['root']) for r in chain['rounds'][1:]],plan=plan,
        checkpoint_sha256=chain['checkpoint_sha256'])
    assert baseline==json.loads(Path(chain['w09_baseline']['path']).read_text())
    assert calibration==json.loads(Path(chain['w08_calibration']['path']).read_text())


def test_cli_wrong_chain_pin_refuses_without_output(ready):
    cmd=[sys.executable,'-m','foothold_s2.ex42_stage_materialize','--materialize-only',
         '--expected-flag-chain-sha256','0'*64]
    for key,value in ready.items():cmd.extend(['--'+key.replace('_','-'),str(value)])
    result=subprocess.run(cmd,capture_output=True,text=True)
    assert result.returncode==2
    assert 'flag-chain SHA differs' in result.stdout
    assert not ready['out'].exists()
