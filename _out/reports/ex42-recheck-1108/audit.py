"""Independent CPU contract audit; no Kit, GPU, PPO training or production edits."""
from pathlib import Path
from types import SimpleNamespace, MethodType
from unittest.mock import patch
import ast, hashlib, json, sys
import gymnasium as gym
import torch

ROOT=Path('D:/mai-wt/foothold-lab/analyst-ex42-recheck-eae0bed7')
OUT=Path('D:/mai-tmp/analyst/ex42-recheck-1108')
OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT))
from foothold_s2.scripts import ex42_training_entry as entry
from foothold_s2.scripts.ex41_startup import configure_ex41_command_slots
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.curriculum.ex40_dr_runtime import RuntimeReadback, _sample_radial_push_xy
from foothold_s2.commands import mixed_core as mc
from foothold_s2.rewards.w86_runtime import W86Runtime
from foothold_s2.runners import start_runner as sr

parent_path=Path('C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/main/EX-41-B-main_20261104_235522/model_6000.pt')
parent_sha=hashlib.sha256(parent_path.read_bytes()).hexdigest()
assert parent_sha=='1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613'
parent=torch.load(parent_path,map_location='cpu',weights_only=False)
plan=EX42Plan.load(ROOT/'foothold_s2/curriculum/ex42-prep.yaml')
source,stage=entry.load_ex42_stage_zero_source(plan)
cfg=entry.configure_ex42_stage_zero_train_cfg({},parent,parent_path=parent_path,parent_sha256=parent_sha)
vmax=cfg['ex42_stage_zero_push_vmax_mps']
assert vmax==2.0
term=SimpleNamespace(slot_names=tuple(mc.WT_SLOTS),slot_counts=torch.zeros(5,dtype=torch.long))
configure_ex41_command_slots(term)
sample=mc.resample_stage(torch.Generator().manual_seed(42),3072,stage,torch.zeros(3072))
term.slot_counts+=torch.bincount(sample['slot'],minlength=len(term.slot_names))
assert len(term.slot_names)==13 and int(term.slot_counts.sum())==3072

# Call the installed RewardManager get/set method bodies, not an invented getter.
# Manager construction/term resolution and PhysX are not executed in this CPU audit.
installed=Path('C:/isaac/isaaclab/source/isaaclab/isaaclab/managers/reward_manager.py')
tree=ast.parse(installed.read_text(encoding='utf-8'))
cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='RewardManager')
methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('get_term_cfg','set_term_cfg')]
ns={}
exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)]+methods,type_ignores=[])),str(installed),'exec'),ns)
manager=SimpleNamespace(_term_names=['lin_vel_z'],_term_cfgs=[SimpleNamespace(weight=-2.0)])
for name in ('get_term_cfg','set_term_cfg'):setattr(manager,name,MethodType(ns[name],manager))
env_cfg=SimpleNamespace(rewards=SimpleNamespace(lin_vel_z=SimpleNamespace(weight=-2.0)))
entry.apply_stage_zero_parent_reward_contract(env_cfg,parent_sha256=parent_sha,parent_update=6000)
assert env_cfg.rewards.lin_vel_z.weight==0.0

class VectorContract(gym.Env):
    num_envs=3072
    device='cpu'
    physics_dt=0.005
    def reset(self,*,seed=None,options=None):
        super().reset(seed=seed)
        return None,{}
    def step(self,action):
        raise AssertionError('Physics execution is forbidden in this audit')

raw=VectorContract()
raw.reward_manager=manager
action=SimpleNamespace(delay=torch.tensor([0,1,2,3]),_ex40_sample_counts=None)
raw.action_manager=SimpleNamespace(get_term=lambda name:action)
raw.scene={'robot':SimpleNamespace(actuators={})}
wrapped=gym.wrappers.OrderEnforcing(raw)
assert not hasattr(wrapped,'num_envs') and not hasattr(wrapped,'device')
entry.apply_stage_zero_parent_reward_manager(wrapped,parent_sha256=parent_sha,parent_update=6000)
assert manager.get_term_cfg('lin_vel_z').weight==0.0
rt=entry.EX42StageZeroRuntime(stage_zero_plan=SimpleNamespace(stages=[stage]),plan_sha256=plan.sha256,approval_sha256=hashlib.sha256(b'CPU interface only, not launch authorization').hexdigest(),parent_sha256=parent_sha,push_vmax_mps=vmax)
rt.attach_environment(wrapped,term)
runner=sr.StartRunner.__new__(sr.StartRunner)
runner.log_dir=str(OUT)
rt.attach_runner(runner)
base=RuntimeReadback(raw,source.domain_randomization['full_ranges'],0.015,source.sha256)
dr=entry.EX42StageZeroDRReadback(base,vmax)
runner.ex40_dr_runtime=dr
raw._ex41_w86=W86Runtime.__new__(W86Runtime)
contract={'w86':{'format':'CPU registration evidence','weights':parent['ex41_w86_reward_weights']},'initial_dr':{'scale':1.0},'terrain':{'policy':'performance','level_cap':5}}
reset=json.loads(json.dumps(entry.build_stage_zero_reset_readback(wrapped,dr,contract)))
assert reset['w86_attached'] and reset['lin_vel_z_weight']==0 and reset['push_vmax_mps']==2

dr_trace=[]
done=torch.zeros(3072,dtype=torch.bool)
for loop_index in range(50):
    n=sr.curriculum_update_number(rt,loop_index)
    rt.on_update_start(n)
    dr.update_start(n)
    assert raw._ex40_dr_scale==base.scale==dr.scale==1.0
    assert raw._ex41_push_vmax_mps==2.0
    for _ in range(24):
        rt.record_pre_step()
        # Original callbacks only. This is NOT an environment/PPO rollout.
        rt.record_post_step(done)
    rt.flush_consumption(n)
    summary=dr.summary()
    dr_trace.append({'n':n,'scale':summary['scale'],'vmax':summary['push_schedule']['vmax_mps'],'delay_max_seconds':summary['target_ranges']['delay_max_seconds']})
assert rt.pre_step_count==rt.post_step_count==1200
state=rt.state_dict()
rt2=entry.EX42StageZeroRuntime(stage_zero_plan=SimpleNamespace(stages=[stage]),plan_sha256=plan.sha256,approval_sha256=rt.approval_sha256,parent_sha256=parent_sha,push_vmax_mps=vmax)
rt2.load_state_dict(state)
assert rt2.state_dict()==state
runner.manifest={};runner.manifest_dir=OUT;runner.num_steps_per_env=24;runner.gpu_world_size=1
runner._check_code=lambda n:None
published=[]
with patch.object(sr.run_manifest,'update_progress',side_effect=lambda *a:published.append(a)):
    runner._manifest_checkpoint(50,'model_50.pt',3072)
assert published[0][2:4]==(50,3686400)
torch.manual_seed(42)
xy,magnitude,angles=_sample_radial_push_xy(4096,vmax,device='cpu',dtype=torch.float32)
assert float(magnitude.max())<=2 and torch.allclose(torch.linalg.vector_norm(xy,dim=1),magnitude,atol=1e-6)
result={'head':'eae0bed799dce0e39b04d157ad4e3e79ecb87653','parent_sha256':parent_sha,'parent_shapes':{k:list(parent['model_state_dict'][k].shape) for k in ('actor.0.weight','critic.0.weight')},'h1_counts':term.slot_counts.tolist(),'h2_readback':reset,'h3_counts':{'pre':rt.pre_step_count,'post':rt.post_step_count},'h4_weight':manager.get_term_cfg('lin_vel_z').weight,'h4_installed_methods_sha256':hashlib.sha256(installed.read_bytes()).hexdigest(),'h5_trace':dr_trace,'radial_sample_max':float(magnitude.max()),'model50_manifest':{'completed':published[0][2],'steps':published[0][3]},'state_roundtrip':True,'scope':'CPU helpers and callbacks only; no actual physics, PPO update or model50 save'}
(OUT/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:result[k] for k in ('head','parent_sha256','h1_counts','h3_counts','h4_weight','radial_sample_max','model50_manifest','state_roundtrip','scope')},ensure_ascii=False,indent=2))
