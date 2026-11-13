import argparse
import ast
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from foothold_s2.eval import action_sampling_probe as probe
from foothold_s2.eval import adapters, eval_dr_mode, n21_dr_record

ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location('pair_prepare',ROOT/'inbox/jay/20261114-analysis/action-pair/prepare.py')
prepare=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(prepare)


def arguments(**updates):
    d=dict(action_sampling_probe=True,action_mode='sample',command_suite='e1_v2',commands='fwd0.1,fwd0.2',
           envs=64,steps=300,modes='eval_gt,eval_pred',fixed_terrain=True,fixed_level=0,terrain_set='default',
           mesh_dir='/mesh',dr_mode='off',ex42_evaluation_plan=Path('/plan'),eval_seed=42)
    d.update(updates); return SimpleNamespace(**d)


def test_existing_mean_and_diagnostic_output_separate():
    a=arguments(action_sampling_probe=False,action_mode='mean')
    probe.validate(a); assert probe.output_name(a)=='map_modes.json'
    sentinel=object(); assert probe.wrap(sentinel,a,'cpu') is sentinel
    a=arguments(); probe.validate(a)
    assert probe.output_name(a)=='action_probe_map_modes.json'
    assert probe.receipt(a)['formal_score_eligible'] is False
    assert probe.receipt(a)['latent_mode']=='mean'


@pytest.mark.parametrize('bad',[{'action_sampling_probe':False},{'command_suite':'core'},
    {'commands':'all'},{'modes':'eval_gt'},{'envs':32},{'steps':301},{'fixed_terrain':False},
    {'fixed_level':2},{'dr_mode':'on'},{'mesh_dir':None},{'ex42_evaluation_plan':None},
    {'axis_v2':True},{'gait_contact_sweep':True},{'eval_seed':-1}])
def test_unsafe_scope_rejected(bad):
    with pytest.raises(ValueError): probe.validate(arguments(**bad))


class TinyActor:
    std=torch.full((12,), .47)
    def act(self,obs): return torch.distributions.Normal(torch.zeros_like(obs),torch.full_like(obs,.47)).sample()
    def act_inference(self,obs): return torch.zeros_like(obs)


def actual_s2_policy(mode):
    p=adapters.S2Policy.__new__(adapters.S2Policy)
    p.z_mode='mean'; p.act_mode=mode; p.pstate=SimpleNamespace()
    calls=[]
    def step(state,inp,gmap,*,deterministic):
        calls.append(deterministic); return inp
    p.runner=SimpleNamespace(device='cpu',_split=lambda x:(x,None,None,None,None,None),
        _ppo_obs=lambda x,est:x,alg=SimpleNamespace(policy=TinyActor()),
        perception=SimpleNamespace(ingest=lambda state,o,depth:o,step=step))
    return p,calls


def test_actual_s2_sampling_changes_action_not_external_rng_or_latent():
    obs=torch.ones(64,12)
    mean,calls=actual_s2_policy('mean'); assert torch.equal(mean(obs),torch.zeros_like(obs))
    sample,calls=actual_s2_policy('sample'); w=probe.wrap(sample,arguments(),'cpu')
    torch.manual_seed(703); expected_state=torch.random.get_rng_state().clone()
    first=w(obs); second=w(obs)
    assert torch.equal(expected_state,torch.random.get_rng_state())
    assert calls==[True,True] and not torch.equal(first,torch.zeros_like(obs))
    assert not torch.equal(first,second)
    again,_=actual_s2_policy('sample'); w2=probe.wrap(again,arguments(),'cpu')
    assert torch.equal(first,w2(obs)) and torch.equal(second,w2(obs))
    generator=torch.Generator().manual_seed(42)
    # Normal.sample is mean + std * epsilon with the private seeded stream.
    expected=torch.empty_like(obs).normal_(generator=generator)*.47
    assert torch.allclose(first,expected,atol=1e-7,rtol=1e-6)
    assert .40 < float(first.std()) < .55


def test_private_rng_restored_on_policy_error():
    def bad(obs):
        torch.rand(5); raise ValueError('known failure')
    p=probe.IsolatedActionPolicy(bad,'cpu',42); state=torch.random.get_rng_state().clone()
    with pytest.raises(ValueError,match='known failure'): p(None)
    assert torch.equal(state,torch.random.get_rng_state())


def test_std_reads_loaded_parameter_not_assumed_value():
    p,_=actual_s2_policy('sample')
    p.runner.alg.policy=SimpleNamespace(log_std=torch.full((12,),.3).log())
    assert probe.learned_std(p)==pytest.approx([.3]*12)
    p.runner.alg.policy.log_std[0]=float('nan')
    with pytest.raises(ValueError,match='invalid loaded'): probe.learned_std(p)


def parser_prefix(argv,monkeypatch):
    import sys
    path=ROOT/'foothold_s2/eval/eval_map_modes.py'; tree=ast.parse(path.read_text())
    nodes=[]
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('parser','args') for t in node.targets):
            nodes.append(node)
        elif isinstance(node,ast.Expr) and isinstance(node.value,ast.Call):
            f=node.value.func
            if isinstance(f,ast.Attribute) and isinstance(f.value,ast.Name) and (
                f.value.id=='parser' and f.attr=='add_argument' or f.value.id=='eval_dr_mode' and f.attr=='add_arguments'):
                nodes.append(node)
        elif isinstance(node,ast.Try) and 'action_sampling_probe.validate' in ast.unparse(node):
            nodes.append(node); break
    monkeypatch.setattr(sys,'argv',['eval']+argv)
    ns=dict(argparse=argparse,Path=Path,n21_dr_record=n21_dr_record,eval_dr_mode=eval_dr_mode,action_sampling_probe=probe)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
    return ns['args']


def test_real_parser_and_policy_call_route_selected_action(monkeypatch):
    base=['--task','FootholdS2-Go2-S2-SB-v0','--checkpoint','/model.pt','--out','/out',
          '--mesh-dir','/mesh','--ex42-evaluation-plan','/plan','--fixed-terrain','--fixed-level','0',
          '--command-suite','e1_v2','--commands','fwd0.1,fwd0.2','--modes','eval_gt,eval_pred']
    args=parser_prefix(base+['--action-sampling-probe','--action-mode','sample'],monkeypatch)
    assert args.action_mode=='sample'
    with pytest.raises(SystemExit): parser_prefix(base+['--action-mode','sample'],monkeypatch)
    path=ROOT/'foothold_s2/eval/eval_map_modes.py'; tree=ast.parse(path.read_text())
    assignments=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='policy' for t in n.targets)]
    call=next(n for n in assignments if 'act_mode=args.action_mode' in ast.unparse(n))
    wrap=next(n for n in assignments if 'action_sampling_probe.wrap' in ast.unparse(n))
    seen=[]
    def make(*a,**kw): seen.append(kw); return actual_s2_policy(kw['act_mode'])[0]
    ns=dict(args=args,adapters=SimpleNamespace(S2Policy=make),runner=None,env=SimpleNamespace(num_envs=64),
            mode='eval_gt',dev='cpu',action_sampling_probe=probe)
    exec(compile(ast.Module(body=[call,wrap],type_ignores=[]),str(path),'exec'),ns)
    assert seen==[{'z_mode':'mean','act_mode':'sample','map_mode':'eval_gt'}]
    assert isinstance(ns['policy'],probe.IsolatedActionPolicy)


def fixture_pair(tmp_path):
    cp='a'*64
    for action in ('mean','sample'):
        folder=tmp_path/action; folder.mkdir()
        r=probe.receipt(arguments(action_mode=action))
        d=dict(action_sampling_probe=r,checkpoint_sha256=cp,eval_seed=42,envs=64,steps=300,
               fixed_terrain={'fixed_level':0},env_arrays={},commands={'fwd0.1':[.1,0,0],'fwd0.2':[.2,0,0]},
               dr_off=['physics_material'],policy_dt_s=.02,ex42_mesh={'mesh_sha256':'b'*64},
               action_std_by_cell={}, source_sha256={'eval_map_modes.py':'c'*16},
               terrain_hash={'eval_gt/fwd0.1':'d'*64},
               evaluation_friction={'state':'verified','plan_sha256':'e'*64},
               run_identity={'code_head':'f'*40,'code_dirty_files':0,'action_sampling_probe':r})
        for mode in ('eval_gt','eval_pred'):
            for case in ('fwd0.1','fwd0.2'):
                name=f'env_arrays_{mode}_{case}.npz';d['env_arrays'][mode+'/'+case]=name
                d['action_std_by_cell'][mode+'/'+case]=[.47]*12
                ident={'checkpoint_sha256':cp,'eval_seed':42,'action_sampling_probe':r}
                np.savez(folder/name,run_identity=json.dumps(ident),vx=np.full((300,64),float(case[3:])),
                         alive=np.ones((300,64),bool),dt=.02,start_xy=np.zeros((64,2)))
        (folder/'action_probe_map_modes.json').write_text(json.dumps(d))
    return cp


def test_readback_known_full_follow_and_missing_case(tmp_path):
    cp=fixture_pair(tmp_path); result=prepare.verify_pair(tmp_path,cp,42,0)
    assert len(result['cells'])==4
    assert all(abs(x[m]['R_median']-1)<1e-12 for x in result['cells'] for m in ('mean','sample'))
    path=tmp_path/'sample/action_probe_map_modes.json';d=json.loads(path.read_text())
    del d['env_arrays']['eval_pred/fwd0.2'];path.write_text(json.dumps(d))
    with pytest.raises(ValueError,match='exactly four'): prepare.verify_pair(tmp_path,cp,42,0)


def test_readback_rejects_initial_placement_difference(tmp_path):
    cp=fixture_pair(tmp_path);path=tmp_path/'sample/env_arrays_eval_gt_fwd0.1.npz'
    with np.load(path) as z: arrays=dict(z)
    arrays['start_xy'][1,0]=.01;np.savez(path,**arrays)
    with pytest.raises(ValueError,match='start_xy'): prepare.verify_pair(tmp_path,cp,42,0)


@pytest.mark.parametrize('change', ['sha','seed','plan','source','std','action','command','head'])
def test_readback_rejects_mixed_evidence(tmp_path,change):
    cp=fixture_pair(tmp_path);path=tmp_path/'sample/action_probe_map_modes.json'
    d=json.loads(path.read_text())
    if change=='sha': d['checkpoint_sha256']='b'*64
    if change=='seed': d['eval_seed']=7
    if change=='plan': d['evaluation_friction']['plan_sha256']='0'*64
    if change=='source': d['source_sha256']['eval_map_modes.py']='1'*16
    if change=='std': d['action_std_by_cell']['eval_gt/fwd0.1']=[.8]*12
    if change=='action': d['action_sampling_probe']['action_mode']='mean'
    if change=='command': d['commands']['fwd0.1']=[.2,0,0]
    if change=='head': d['run_identity']['code_head']='0'*40
    path.write_text(json.dumps(d))
    with pytest.raises(ValueError): prepare.verify_pair(tmp_path,cp,42,0,'f'*40,'e'*64)


def test_prepared_commands_use_actual_parser_contract(monkeypatch):
    cmds=prepare.commands(ROOT,Path('/model.pt'),Path('/plan'),Path('/mesh'),Path('/out'),'cuda:0',42,0)
    for mode,cmd in cmds.items():
        # The three AppLauncher options are checked by its own parser at Kit entry.
        args=cmd[4:]
        index=args.index('--device'); del args[index:index+2]
        args.remove('--headless'); args=[a for a in args if not a.startswith('--kit_args=')]
        parsed=parser_prefix(args,monkeypatch)
        assert parsed.action_mode==mode and parsed.eval_seed==42
        assert parsed.envs==64 and parsed.steps==300
