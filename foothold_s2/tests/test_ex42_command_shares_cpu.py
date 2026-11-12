"""Declared command shares reach the actual mixed sampler, with explicit denominators."""
from copy import deepcopy
from types import SimpleNamespace as NS
from pathlib import Path
import json
import pytest
import torch
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_training_entry as entry
from foothold_s2.commands import mixed_core as mc
from foothold_s2.commands import ex42_shares as cs

TABLE = Path(__file__).parents[1] / 'curriculum/ex42-prep.yaml'


@pytest.fixture(autouse=True)
def materialized_stage_table(monkeypatch):
    # Runtime normally adopts a materialized plan with an actual parent pin.
    doc = EX42Plan.load(TABLE).document
    for stage in doc['stages']:
        if stage['id']=='E3':
            stage['parent']={'manifest_local_update':1500,'cumulative_update':15500,'checkpoint_key':'model_1500.pt'}
    specs=entry.e_stage_table(doc['stages'])
    monkeypatch.setattr(entry,'E_STAGE_SPECS',specs)
    monkeypatch.setattr(entry,'E_STAGES',{k:(v['updates'],v['parent_local'],v['parent_cumulative']) for k,v in specs.items()})



def setup(stage_id='E3', n=10000):
    plan = EX42Plan.load(TABLE)
    # Test vector, not a policy decision: all free mass on reverse, flag .15.
    shares = dict.fromkeys(mc.EX39_SLOTS, 0.0)
    shares.update(reverse=.85, flag=.15)
    stage = next(s for s in plan.document['stages'] if s['id'] == stage_id)
    stage['shares'] = shares
    source, old = entry.load_ex42_stage_zero_source(plan)
    contract = cs.read_contract(plan, stage_id)
    term = NS(gen=mc.make_generator(42), is_flag_env=torch.zeros(n, dtype=torch.bool),
              slot_current=torch.full((n,), -1), cfg=NS(dynamic_flags=True, force_flag_provider=None))
    raw = NS(num_envs=n, device='cpu', _ex42_column_table=[{'family':'A','kind':'pyramid_stairs'},
                  {'family':'A','kind':'gaps'}], scene=NS(terrain=NS(terrain_types=torch.arange(n)%2)))
    runtime = NS(plan=NS(stages=[old]), env_stage=torch.zeros(n,dtype=torch.long))
    controller = cs.CommandShares(contract, old)
    controller.attach(raw, term, runtime)
    return plan, contract, controller, term, raw, runtime


def test_missing_shares_and_bad_sum_fail_closed_legacy_unchanged():
    p, _, _, _, _, _ = setup()
    st = next(s for s in p.document['stages'] if s['id']=='E3')
    del st['shares']
    with pytest.raises(ValueError, match='shares'): cs.read_contract(p,'E3')
    st['shares']={'flag':.15}
    with pytest.raises(ValueError, match='slots'): cs.read_contract(p,'E3')
    assert cs.read_contract(p,'E0') is None
    assert cs.read_contract(p,'E1') is None
    assert cs.read_contract(p,'EX42_0_T0_prime') is None


@pytest.mark.parametrize('bad', [float('nan'),float('inf'),-.1,True,1.2])
def test_invalid_share(bad):
    p,*_=setup()
    next(s for s in p.document['stages'] if s['id']=='E3')['shares']['flag']=bad
    with pytest.raises(ValueError): cs.read_contract(p,'E3')


def test_actual_sample_conditional_denominator_and_record(tmp_path):
    p, contract, c, t, raw, r = setup()
    ids=torch.arange(raw.num_envs)
    c.reset(ids)
    continuous=raw.scene.terrain.terrain_types==0
    frac=float(t.is_flag_env[continuous].float().mean())
    assert .13 < frac < .17
    assert not t.is_flag_env[~continuous].any()
    assert r.env_stage[continuous].eq(1).all()
    assert r.env_stage[~continuous].eq(0).all()
    free=ids[continuous & ~t.is_flag_env]
    out=mc.resample_stage(t.gen,len(free),r.plan.stages[1],torch.zeros(len(free)))
    assert out['slot'].eq(mc.EX39_SLOTS.index('reverse')).all()
    assert (out['cmd'][:,0]<0).all()
    t.slot_current[free]=out['slot']
    # Noncontinuous remains the old stage, separately counted in the all-env denominator.
    other=ids[~continuous]
    o=mc.resample_stage(t.gen,len(other),r.plan.stages[0],torch.zeros(len(other)))
    t.slot_current[other]=o['slot']
    c.samples(free,out['slot']);c.samples(other,o['slot']);c.samples(ids[t.is_flag_env],None)
    c.pre_step()
    checkpoint=tmp_path/'model_250.pt';checkpoint.write_bytes(b'checkpoint')
    c.write(tmp_path,250,checkpoint,plan_sha='a'*64,stage_id='E3')
    doc=json.loads((tmp_path/'command_shares_250_rank0.json').read_text())
    assert doc['configured']['shares']==contract['shares']
    s=doc['cumulative']['samples']
    assert s['continuous']['total']==5000 and s['all']['total']==10000
    assert s['continuous']['fractions']['flag']==pytest.approx(frac)
    assert s['all']['fractions']['flag']==pytest.approx(frac/2)
    assert doc['cumulative']['steps']==s
    assert doc['cumulative']['reset_modes']['continuous']['total']==5000
    assert doc['checkpoint']['sha256']
    # 2026-11-12 19:46: a name left behind is moved aside (never lost), and the live counts are written
    again=c.write(tmp_path,250,checkpoint,plan_sha='a'*64,stage_id='E3')
    assert json.loads((tmp_path/'superseded'/'command_shares_250_rank0.0.json').read_text())==doc
    assert json.loads((tmp_path/'command_shares_250_rank0.json').read_text())==again


def test_rng_continuation_and_counters_are_exact():
    p,k,c,t,raw,r=setup(n=64)
    ids=torch.arange(64)
    c.reset(ids)
    state=deepcopy(c.state_dict());rng=t.gen.get_state()
    c.reset(ids)
    expected=t.is_flag_env.clone();counts=c.state_dict()
    _,_,d,u,_,_=setup(n=64)
    d.load_state_dict(state);u.gen.set_state(rng);d.reset(ids)
    assert torch.equal(u.is_flag_env,expected)
    assert d.state_dict()==counts
    state['contract']['shares']['flag']=.2
    with pytest.raises(ValueError,match='contract'):d.load_state_dict(state)


def test_real_runtime_and_train_cfg_hooks():
    p,k,_,_,_,_=setup(n=8)
    source,old=entry.load_ex42_stage_zero_source(p)
    view=entry.make_ex42_stage_zero_plan_view(source,old,{"parent_sha256":"b"*64},ex42_plan=p,stage_id='E3')
    assert view.command_contract==k
    # Keep the source/reward adapter's single T0 stage intact.
    assert view.stages==[old]
    cfg=NS(commands=NS(base_velocity=NS(dynamic_flags=False,flag_stride=0,force_flag_provider=None)))
    cs.configure_env(cfg,k)
    assert cfg.commands.base_velocity.dynamic_flags is True
    runtime=entry.EX42StageZeroRuntime(stage_zero_plan=view,plan_sha256='a'*64,
        approval_sha256='b'*64,parent_sha256='c'*64,maximum_updates=4000,push_vmax_mps=2.,stage_id='E3')
    _,_,_,t,raw,_=setup(n=8)
    runtime.attach_environment(raw,t)
    runtime.on_reset(torch.arange(8))
    assert runtime.command_allocation is not None
    assert runtime.state_dict()['command_allocation']['contract']==k
    src=(TABLE.parents[1]/'scripts/train_start.py').read_text()
    assert 'ex42_plan=EX42_STAGE_ZERO_PLAN, stage_id=EX42_STAGE_ID' in src
    assert 'configure_ex42_command_env' in src


def test_actual_mixed_term_reset_resample_and_flag_hook(monkeypatch, tmp_path):
    """Only Isaac's base class is a CPU double. Real command methods and RNG execute."""
    import sys, types, importlib.util
    class Base:
        def __init__(self,cfg,env):
            self.cfg,self._env=cfg,env
            self.num_envs,self.device=env.num_envs,env.device
            self.metrics={}
        def reset(self,env_ids=None):
            self._resample_command(torch.arange(self.num_envs) if env_ids is None else env_ids)
            return {}
    managers=types.ModuleType('isaaclab.managers');managers.CommandTerm=Base;managers.CommandTermCfg=object
    utils=types.ModuleType('isaaclab.utils');utils.configclass=lambda c:c
    monkeypatch.setitem(sys.modules,'isaaclab.managers',managers)
    monkeypatch.setitem(sys.modules,'isaaclab.utils',utils)
    spec=importlib.util.spec_from_file_location('_ex42_actual_mixed',TABLE.parents[1]/'commands/mixed_command.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    p,contract,_,_,raw,_=setup(n=1000)
    class Scene:
        def __getitem__(self,key):return self.robot
    scene=Scene();scene.terrain=raw.scene.terrain
    scene.terrain.env_origins=torch.zeros(1000,3)
    scene.robot=NS(data=NS(root_pos_w=torch.zeros(1000,3),heading_w=torch.zeros(1000)))
    raw.scene=scene;raw.common_step_counter=0
    cfg=NS(asset_name='robot',params={'curriculum_mode':True},seed=42,flag_stride=0,dynamic_flags=True,
           force_flag_provider=None,flag_provider=None,flag_count=4,fixed_cmd=None,clock_scatter=False,steps_per_iter=24)
    t=module.MixedVelocityCommand(cfg,raw)
    source,old=entry.load_ex42_stage_zero_source(p)
    view=entry.make_ex42_stage_zero_plan_view(source,old,{'parent_sha256':'b'*64},ex42_plan=p,stage_id='E3')
    r=entry.EX42StageZeroRuntime(stage_zero_plan=view,plan_sha256='a'*64,approval_sha256='b'*64,
            parent_sha256='c'*64,maximum_updates=4000,push_vmax_mps=2.,stage_id='E3')
    r.attach_environment(raw,t)
    t.reset()
    continuous=raw.scene.terrain.terrain_types==0
    assert t.is_flag_env[continuous].any() and not t.is_flag_env[~continuous].any()
    assert t.slot_current[continuous & ~t.is_flag_env].eq(mc.EX39_SLOTS.index('reverse')).all()
    r.runner=NS(log_dir=str(tmp_path),save_interval=50);r.record_pre_step();r.record_post_step(torch.zeros(1000,dtype=torch.bool))
    r.on_update_start(250)
    cp=tmp_path/'model_250.pt';cp.write_bytes(b'cp')
    r.flush_consumption(250)
    r.on_checkpoint(250,cp)
    d=json.loads((tmp_path/'command_shares_250_rank0.json').read_text())
    assert d['cumulative']['samples']['all']['total']==1000
    assert d['cumulative']['samples']['continuous']['counts']['flag']==int(t.is_flag_env.sum())
    assert d['cumulative']['steps']==d['cumulative']['samples']
    assert int(r.command_samples)==1000-int(t.is_flag_env.sum())


def test_denominator_contract_cannot_be_changed():
    p,*_=setup()
    p.document['command_allocation']['conditional_denominator']='all'
    with pytest.raises(ValueError,match='denominators'):cs.read_contract(p,'E3')


def test_preflight_missing_declaration_fails_before_checkpoint_or_kit(tmp_path,monkeypatch):
    p,*_=setup()
    next(s for s in p.document['stages'] if s['id']=='E3').pop('shares')
    monkeypatch.setattr(entry.EX42Plan,'load',lambda path:p)
    with pytest.raises(ValueError,match='explicit stages.*shares'):
        entry.validate_ex42_stage_e_cli(stage_id='E3',plan_path=TABLE,approvals_path=tmp_path/'absent',
          experiment_path=tmp_path/'absent',parent_checkpoint_path=tmp_path/'absent',log_dir=tmp_path/'new',
          task=entry.STAGE_ZERO_TASK_ID,device='cuda:0',headless=True,distributed=False,max_iterations=4000,
          num_envs=3072,map_input='reconstruction',force_gt=False,approved_switch=True)


def test_reset_reassignment_and_empty_denominators(tmp_path):
    _,_,c,t,raw,r=setup(n=1000)
    ids=torch.arange(1000);c.reset(ids)
    assert t.is_flag_env.any()
    raw.scene.terrain.terrain_types.fill_(1)
    c.reset(ids)
    assert not t.is_flag_env.any()
    assert r.env_stage.eq(0).all()
    cp=tmp_path/'model_250.pt';cp.write_bytes(b'cp')
    doc=c.write(tmp_path,250,cp,plan_sha='a'*64,stage_id='E3')
    assert doc['cumulative']['steps']['continuous']['total']==0
    assert doc['cumulative']['steps']['continuous']['fractions']['flag'] is None


def test_conflicting_allocator_is_rejected():
    p,k,*_=setup()
    for stride,force in [(5,None),(0,lambda *a:None)]:
        cfg=NS(commands=NS(base_velocity=NS(dynamic_flags=False,flag_stride=stride,force_flag_provider=force)))
        with pytest.raises(ValueError,match='allocator'):cs.configure_env(cfg,k)


def test_rank1_receipt_does_not_depend_on_rank0_checkpoint(monkeypatch,tmp_path):
    p,k,c,t,raw,r=setup(n=10)
    c.reset(torch.arange(10))
    monkeypatch.setenv('RANK','1');monkeypatch.setenv('WORLD_SIZE','2')
    d=c.write(tmp_path,250,None,plan_sha='a'*64,stage_id='E3')
    assert d['rank']==1 and d['world_size']==2
    assert d['checkpoint'] is None
    assert (tmp_path/'command_shares_250_rank1.json').is_file()
    c.restart_counts(250)
    c.reset(torch.arange(10))
    d=c.write(tmp_path,500,None,plan_sha='a'*64,stage_id='E3')
    assert d['count_origin_update']==250
    assert d['cumulative']['reset_modes']['all']['total']==10


def test_registered_e1f_is_ready():
    p=EX42Plan.load(TABLE)
    k=cs.read_contract(p,'E1F')
    assert k['shares']['flag']==.10 and sum(k['shares'].values())==pytest.approx(1.)
