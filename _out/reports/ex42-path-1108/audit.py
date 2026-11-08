from pathlib import Path
import sys,json,hashlib,inspect,importlib.metadata
from types import SimpleNamespace
import torch
ROOT=Path('D:/mai-wt/foothold-lab/runner-ex42-w65-7916a52')
sys.path.insert(0,str(ROOT))
from foothold_s2.commands import mixed_core as mc
from foothold_s2.scripts.ex42_training_entry import load_ex42_stage_zero_source
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.rewards.w86_runtime import W86Runtime
from rsl_rl.algorithms import PPO
import yaml
plan=EX42Plan.load(ROOT/'foothold_s2/curriculum/ex42-prep.yaml')
source,stage=load_ex42_stage_zero_source(plan)
gen=torch.Generator(device='cpu').manual_seed(42)
out=mc.resample_stage(gen,3072,stage,torch.zeros(3072))
counts=torch.zeros(len(mc.WT_SLOTS),dtype=torch.long)
try:
 counts+=torch.bincount(out['slot'],minlength=len(mc.WT_SLOTS)); slot_error=None
except Exception as e:slot_error=f'{type(e).__name__}: {e}'
try:json.dumps({'w86':W86Runtime.__new__(W86Runtime)}); json_error=None
except Exception as e:json_error=f'{type(e).__name__}: {e}'
p=Path('C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/main/EX-41-B-main_20261104_235522/model_6000.pt')
sd=torch.load(p,map_location='cpu',weights_only=False)
agent=yaml.safe_load((p.parent/'params/agent.yaml').read_text(encoding='utf-8'))
result={'source_head':'7916a52fa07c6774eb59db2b69f4b7a5068cea63','torch':torch.__version__,'rsl':importlib.metadata.version('rsl-rl-lib'),'ppo_source':inspect.getfile(PPO),'ppo_signature':str(inspect.signature(PPO)),'init_storage':str(inspect.signature(PPO.init_storage)), 'wt_slots':list(mc.WT_SLOTS),'ex41_slots':list(mc.EX39_SLOTS),'sample_max':out['slot'].max().item(),'sample_counts':torch.bincount(out['slot'],minlength=13).tolist(),'slot_error':slot_error,'json_error':json_error,'parent_sha':hashlib.sha256(p.read_bytes()).hexdigest(),'parent_keys':list(sd),'model_shapes':{k:list(v.shape) for k,v in sd['model_state_dict'].items()},'optimizer_groups':len(sd['optimizer_state_dict']['param_groups']),'ppo_learning_rate':sd['ppo_learning_rate'],'optimizer_lr':[g['lr'] for g in sd['optimizer_state_dict']['param_groups']],'perception_lr':[g['lr'] for g in sd['perception_optimizer_state_dict']['param_groups']],'rng_keys':list(sd['rng']),'rng_cuda_count':len(sd['rng'].get('cuda',[])),'parent_pose':sd['ex41_pose_commands'],'normalization':{k:v for k,v in sd['normalization_state'].items() if k!='running_buffers'},'normalization_buffer_keys':list(sd['normalization_state']['running_buffers']),'map_switch_p':sd['map_switch']['p_map_off'],'parent_cfg':{k:agent[k] for k in ('policy','algorithm','num_steps_per_env','save_interval')},'parent_perception':sd['perception_cfg'],'source_stage_rewards':stage.rewards}
assert slot_error and json_error
folder=Path('D:/mai-tmp/analyst/ex42-path-1108');folder.mkdir(exist_ok=True)
(folder/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k in ('ppo_source','rsl','wt_slots','sample_counts','slot_error','json_error','parent_sha','ppo_learning_rate','optimizer_lr','parent_pose','normalization','map_switch_p')},ensure_ascii=False,indent=2))

# Execute the production method body with a recording sink; no file writer or Kit.
import ast, os
from foothold_s2.scripts.ex42_training_entry import EX42StageZeroRuntime
tree=ast.parse((ROOT/'foothold_s2/runners/start_runner.py').read_text(encoding='utf-8'))
cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='StartRunner')
fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_manifest_checkpoint')
seen=[]
scope={'run_manifest':SimpleNamespace(update_progress=lambda *args:seen.append(args)),'os':os}
exec(compile(ast.Module(body=[fn],type_ignores=[]),str(ROOT/'foothold_s2/runners/start_runner.py'),'exec'),scope)
spy=SimpleNamespace(manifest={},manifest_dir='readonly-spy',num_steps_per_env=24,gpu_world_size=1,log_dir='readonly-spy',_check_code=lambda n:None)
scope['_manifest_checkpoint'](spy,50,'model_50.pt',3072)
rt=EX42StageZeroRuntime(stage_zero_plan=SimpleNamespace(stages=(stage,)),plan_sha256=plan.sha256,approval_sha256='not-consumed-by-this-interface-probe',parent_sha256=result['parent_sha'])
missing={}
for name in ('record_pre_step','record_post_step'):
 try:getattr(rt,name)
 except AttributeError as e:missing[name]=str(e)
assert len(missing)==2 and seen[0][2]==51
with (p.parent/'train_extra.jsonl').open(encoding='utf-8') as f:
 for lineno,line in enumerate(f,1):
  if line.strip():last=json.loads(line)
supp={'manifest_cpu':{'input_completed':50,'published_completed':seen[0][2],'published_steps':seen[0][3],'actual_steps':50*24*3072},'missing_runtime_methods':missing,'parent_train_extra_line':lineno,'parent_update':last['it'],'parent_push_schedule':last['ex40_dr']['push_schedule'],'parent_push_actual':{k:v for k,v in last['ex40_dr']['actual_samples'].items() if k.startswith('push')},'source_sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [ROOT/'foothold_s2/scripts/ex42_training_entry.py',ROOT/'foothold_s2/scripts/train_start.py',ROOT/'foothold_s2/ex42_chain.py',ROOT/'foothold_s2/runners/start_runner.py']}}
(folder/'supplement.json').write_text(json.dumps(supp,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(supp,ensure_ascii=False,indent=2))
