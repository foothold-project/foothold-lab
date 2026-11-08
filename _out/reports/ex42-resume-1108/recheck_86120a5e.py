"""H1/L1 scoped CPU audit of the exact caller and actual checkpoint bytes."""
from pathlib import Path
from types import SimpleNamespace
import ast
import hashlib
import json
import subprocess
import sys

import torch
import yaml

ROOT = Path('D:/mai-wt/foothold-lab/runner-ex42-resume-w65')
HEAD = '86120a5ea6aa2a4a070a4cd92501daa7161a992a'
OUT = Path('D:/mai-tmp/analyst/ex42-resume-86120a5e')
RUN = Path('C:/Users/AI-WS01/s2_lab/ex42_main_20261108_123914/main/EX-42-B-stagezero_20261108_123914')
PARENT_MANIFEST = Path('C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/main/EX-41-B-main_20261104_235522/manifest.json')
assert subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()==HEAD
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT))
torch.set_num_threads(4)
from foothold_s2.scripts import ex42_training_entry as entry
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.ex42_chain import EX42TrainingChain

def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

source=RUN/'model_350.pt'
assert sha(source)=='7c01f11657b2d66b5fe3b5324f889aea5749c0cebb00333472fb6322342ca75c'
saved=torch.load(source,map_location='cpu',weights_only=False)
plan,parent,receipt,preflight=entry.validate_ex42_stage_zero_cli(
    plan_path=ROOT/'foothold_s2/curriculum/ex42-prep.yaml',
    approvals_path=ROOT/'foothold_s2/curriculum/ex42-approvals.yaml',
    parent_manifest_path=PARENT_MANIFEST, log_dir=OUT/'never_created_training_run',
    task=entry.STAGE_ZERO_TASK_ID,device='cuda:0',headless=True,distributed=False,
    max_iterations=1000,num_envs=3072,map_input='reconstruction',force_gt=False,
    approved_switch=True,resume_from=source,self_resume=True,resume_smoke=True,resume_updates=5)
assert parent['iter']==6000 and saved['iter']==350

rows=[]
def record(name,**fields):
    row={'test':name,**fields};rows.append(row)
    print(json.dumps(row,ensure_ascii=False),flush=True)

record('actual_cli_checkpoint_source',returned_iter=parent['iter'],resume_iter=saved['iter'],
    level_differences=int((parent['env_state']['terrain_levels']!=saved['env_state']['terrain_levels']).sum()),
    type_differences=int((parent['env_state']['terrain_types']!=saved['env_state']['terrain_types']).sum()))

class Scene(SimpleNamespace):
    def __getitem__(self,key):
        assert key=='robot';return self.robot

class GeneratorCapture:
    def set_state(self,state): self.state=state.clone()

n=len(saved['env_state']['terrain_levels'])
origins=torch.zeros(10,23,3)
origins[:,:,0]=torch.arange(10)[:,None]*8
origins[:,:,1]=torch.arange(23)[None,:]*8
terrain=SimpleNamespace(terrain_levels=torch.zeros(n,dtype=torch.long),
    terrain_types=torch.zeros(n,dtype=torch.long),terrain_origins=origins,env_origins=torch.zeros(n,3))
default_root=torch.zeros(n,13);default_root[:,2]=.4;default_root[:,3]=1
root_pos=torch.zeros(n,3)
asset=SimpleNamespace(device='cpu',data=SimpleNamespace(default_root_state=default_root,root_pos_w=root_pos))
asset.write_root_pose_to_sim=lambda pose,env_ids:root_pos.__setitem__(env_ids,pose[:,:3])
asset.write_root_velocity_to_sim=lambda *a,**k:None
scene=Scene(terrain=terrain,env_origins=terrain.env_origins,robot=asset)
command=SimpleNamespace(gen=GeneratorCapture(),range_curriculum=SimpleNamespace())
env=SimpleNamespace(scene=scene,command_manager=SimpleNamespace(get_term=lambda name:command))
env.unwrapped=env
runner=StartRunner.__new__(StartRunner);runner.env=env

events=Path('C:/isaac/isaaclab/source/isaaclab/isaaclab/envs/mdp/events.py')
fn=next(x for x in ast.parse(events.read_text(encoding='utf-8')).body
        if isinstance(x,ast.FunctionDef) and x.name=='reset_root_state_uniform')
ns={'torch':torch,'SceneEntityCfg':lambda name:SimpleNamespace(name=name),
    'math_utils':SimpleNamespace(sample_uniform=lambda lo,hi,shape,device:torch.zeros(shape),
        quat_from_euler_xyz=lambda r,p,y:torch.tensor([1.,0,0,0]).expand(len(r),4),quat_mul=lambda a,b:a)}
module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),fn],type_ignores=[])
exec(compile(ast.fix_missing_locations(module),str(events),'exec'),ns)
reset=lambda:ns['reset_root_state_uniform'](env,torch.arange(n),{}, {})
train=ROOT/'foothold_s2/scripts/train_start.py'
tree=ast.parse(train.read_text(encoding='utf-8'))
main_ast=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='main')
assert not any(isinstance(x,ast.Global) and 'EX42_STAGE_ZERO_ROOT_XY_READBACK' in x.names
               for x in ast.walk(main_ast))
pre_reset=next(x for x in ast.walk(tree) if isinstance(x,ast.If) and x.lineno==944)
caller_ns={'EX42_STAGE_ZERO_RESUME':str(source),'EX42_STAGE_ZERO_CHECKPOINT':parent,
    'restore_stage_zero_resume_terrain_before_reset':entry.restore_stage_zero_resume_terrain_before_reset,
    'env':env,'json':json}
exec(compile(ast.Module(body=[pre_reset],type_ignores=[]),str(train),'exec'),caller_ns)
reset();reset()  # event-only CPU execution for both explicit and wrapper reset
runner._load_env_state(saved['env_state'])
cfg=yaml.load((RUN/'params/env.yaml').read_text(encoding='utf-8'),Loader=yaml.BaseLoader)
pose_range=cfg['events']['reset_base']['params']['pose_range']
bad=entry.build_stage_zero_resume_root_xy_readback(env,pose_range=pose_range)
assert bad['outside_reset_bounds_count']>0
record('actual_caller_parent_reset_then_m350_load',**bad)

# Control: helper receives the requested resume checkpoint, not the old parent.
entry.restore_stage_zero_resume_terrain_before_reset(env,saved)
reset();reset();runner._load_env_state(saved['env_state'])
good=entry.build_stage_zero_resume_root_xy_readback(env,pose_range=pose_range)
assert good['outside_reset_bounds_count']==0
record('helper_control_with_m350',**good)

# Python local binding: keep the exact assignment and manifest IF from main.
assignment=next(x for x in ast.walk(tree) if isinstance(x,ast.Assign) and x.lineno==1049)
mode_if=next(x for x in ast.walk(tree) if isinstance(x,ast.If) and x.lineno==1276)
scope=ast.FunctionDef(name='scope_probe',args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),
    body=[ast.If(test=ast.Name(id='EX42_STAGE_ZERO_RESUME',ctx=ast.Load()),body=[assignment],orelse=[]),mode_if],decorator_list=[])
ns={'EX42_STAGE_ZERO_RESUME':None,'EX42_STAGE_ZERO_PLAN':object(),
    'EX42_STAGE_ZERO_ROOT_XY_READBACK':None,'EX42_STAGE_ZERO_CHAIN_RECEIPT':{},'modes':{}}
exec(compile(ast.fix_missing_locations(ast.Module(body=[scope],type_ignores=[])),str(train),'exec'),ns)
try:
    ns['scope_probe']()
except UnboundLocalError as exc:
    record('fresh_start_readback_local_scope',exception=type(exc).__name__,message=str(exc))
else:
    raise AssertionError('expected unbound local for fresh non-resume branch')

# Actual constructor with scratch receipts only. Invalid previous identity must
# stop before builder, while valid extra provenance currently remains at risk.
receipt_dir=OUT/'receipt_probe'
def builder():
    return EX42TrainingChain(plan=plan,approvals_path=ROOT/'foothold_s2/curriculum/ex42-approvals.yaml',
        parent_manifest_path=PARENT_MANIFEST,run_dir=receipt_dir,repo_root=ROOT,queue_path=OUT/'unused_queue.json')
builder()
p=receipt_dir/'startup_receipt.json';original=json.loads(p.read_text(encoding='utf-8'))
bad_receipt={**original,'plan_sha256':'bad'};p.write_text(json.dumps(bad_receipt),encoding='utf-8')
calls=[]
def counted_builder():
    calls.append(1);return builder()
try:
    entry.build_stage_zero_chain_with_receipt_checks(receipt_dir,plan_sha256=plan.sha256,
        parent_sha256=receipt['parent_sha256'],allow_existing_run=True,builder=counted_builder)
except ValueError as exc:
    assert not calls and json.loads(p.read_text(encoding='utf-8'))==bad_receipt
    record('L1_invalid_previous_before_builder',rejected=True,builder_calls=0,message=str(exc))
else:
    raise AssertionError('invalid old identity accepted')
p.write_text(json.dumps({**original,'audit_provenance_marker':'preserve_me'}),encoding='utf-8')
old_sha=sha(p)
_,check=entry.build_stage_zero_chain_with_receipt_checks(receipt_dir,plan_sha256=plan.sha256,
    parent_sha256=receipt['parent_sha256'],allow_existing_run=True,builder=builder)
marker='audit_provenance_marker' in json.loads(p.read_text(encoding='utf-8'))
assert not marker and check['previous_sha256']==old_sha and check['receipt_changed']
record('L1_valid_receipt_provenance',marker_preserved=marker,previous_sha_recorded=True,receipt_changed=True)
result={'head':HEAD,'scope':'CPU, no Kit/physics/training; actual checkpoints and caller AST',
    'checkpoint_sha256':sha(source),'parent_sha256':receipt['parent_sha256'],'tests':rows,
    'source_hashes':{str(p.relative_to(ROOT)):sha(p) for p in
        [train,ROOT/'foothold_s2/scripts/ex42_training_entry.py',ROOT/'foothold_s2/ex42_chain.py']}}
(OUT/'recheck.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
assert subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()==HEAD
print('RECHECK_WRITTEN',OUT/'recheck.json')
