"""Independent CPU audit of fixed EX42 self-resume. No Kit or source edits."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import ast
import copy
import hashlib
import json
import random
import shutil
import subprocess
import sys

import numpy as np
import torch
import yaml
from tensordict import TensorDict

ROOT = Path('D:/mai-wt/foothold-lab/runner-ex42-resume-w65')
OUT = Path('D:/mai-tmp/analyst/ex42-resume-2b3e504f')
RUN = Path('C:/Users/AI-WS01/s2_lab/ex42_main_20261108_123914/main/EX-42-B-stagezero_20261108_123914')
HEAD = '2b3e504f75abe524474d992afa4f0ca5f4e08318'
assert subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip() == HEAD
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
from foothold_s2.scripts import ex42_training_entry as entry
from foothold_s2.runners import start_runner as sr
from rsl_rl.modules import ActorCritic
from inventory import describe


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def equal(a, b):
    return describe(a) == describe(b)


class DeviceGeneratorCapture:
    """CUDA generator payload sink; does not claim CPU/CUDA RNG equivalence."""
    def __init__(self):
        self.state = None

    def set_state(self, state):
        self.state = state.clone()

    def get_state(self):
        return self.state.clone()


source = RUN/'model_350.pt'
assert sha(source) == '7c01f11657b2d66b5fe3b5324f889aea5749c0cebb00333472fb6322342ca75c'
saved = torch.load(source, map_location='cpu', weights_only=False)
manifest = json.loads((RUN/'manifest.json').read_text(encoding='utf-8-sig'))
cfg = yaml.safe_load((RUN/'params/agent.yaml').read_text(encoding='utf-8'))
plan = entry.EX42Plan.load(ROOT/'foothold_s2/curriculum/ex42-prep.yaml')
source_plan, stage = entry.load_ex42_stage_zero_source(plan)
pins = saved['continuous_curriculum']
parent = saved['ex42_parent_transfer']
kwargs = dict(plan_sha256=pins['plan_sha256'], approval_sha256=pins['approval_sha256'], parent_receipt=parent)
rows = []


def test(name, fn, reject=False):
    try:
        value = fn()
    except Exception as exc:
        row = dict(test=name, result='REJECTED' if reject else 'FAILED', exception=type(exc).__name__, detail=str(exc))
    else:
        row = dict(test=name, result='UNEXPECTED_ACCEPT' if reject else 'PASS', value=value)
    rows.append(row)
    print(json.dumps(row, ensure_ascii=False, default=str), flush=True)


proof = entry.validate_ex42_stage_zero_resume(checkpoint_path=source, manifest_path=RUN/'manifest.json',
                                            require_latest=False, resume_smoke_updates=5, **kwargs)
test('actual_checkpoint_smoke_preflight', lambda: {k:proof[k] for k in ('local_update_origin','first_resumed_local_update','first_resumed_cumulative_update','requested_updates')})
fixture = OUT/'same_run_fixture'
fixture.mkdir(exist_ok=True)
shutil.copyfile(source, fixture/source.name)
fm = copy.deepcopy(manifest)
fm['run']['log_dir'] = str(fixture)
fm['progress'] = dict(completed_updates=350, total_env_steps=350*24*3072)
fm['checkpoints'] = {source.name:sha(source)}
(fixture/'manifest.json').write_text(json.dumps(fm),encoding='utf-8')
full = entry.validate_ex42_stage_zero_resume(checkpoint_path=fixture/source.name,manifest_path=fixture/'manifest.json',**kwargs)
test('real_bytes_frozen_350_manifest_remaining', lambda: full['requested_updates'])

for label, change in [
    ('wrong_sha', lambda m:m['checkpoints'].update({source.name:'0'*64})),
    ('manifest_behind', lambda m:m['progress'].update(completed_updates=349)),
    ('manifest_ahead', lambda m:m['progress'].update(completed_updates=400)),
    ('wrong_run', lambda m:m['run'].update(log_dir=str(OUT/'other'))),
]:
    m=copy.deepcopy(fm);change(m)
    (fixture/'manifest.json').write_text(json.dumps(m),encoding='utf-8')
    test(label,lambda:entry.validate_ex42_stage_zero_resume(checkpoint_path=fixture/source.name,manifest_path=fixture/'manifest.json',**kwargs),True)
(fixture/'manifest.json').write_text(json.dumps(fm),encoding='utf-8')
test('wrong_plan_sha',lambda:entry.validate_ex42_stage_zero_resume(checkpoint_path=fixture/source.name,manifest_path=fixture/'manifest.json',**{**kwargs,'plan_sha256':'0'*64}),True)
test('smoke_six_updates',lambda:entry.validate_ex42_stage_zero_resume(checkpoint_path=fixture/source.name,manifest_path=fixture/'manifest.json',resume_smoke_updates=6,**kwargs),True)

# Actual neural classes and Adam state consumers; only physics buffers are CPU fixtures.
torch.set_num_threads(4)
runner = sr.StartRunner.__new__(sr.StartRunner)
runner.ex41_pose_commands=True;runner.ex41_critic_mirror=False
runner.ex41_mirror_approval=None;runner.ex41_mirror_hold_reason=None
runner.ex41_parent_transfer=None;runner.ex42_parent_transfer=None
runner.pcfg={**sr.PERCEPTION_DEFAULTS,**saved['perception_cfg']}
runner.policy_cfg=cfg['policy'];runner.device='cpu';runner._resumed=False
runner.map_ratio_events=[];runner.map_switch_changes=[]
runner.p_map_off=saved['map_switch']['p_map_off']
runner.map_switch_gen=DeviceGeneratorCapture()
runner.perception=sr.StartPerception(sr.PerceptionCfg(map_input='reconstruction',force_gt=False))
runner.perception_optimizer=torch.optim.Adam(runner.perception.parameters(),lr=0.0005)
obs=TensorDict({'actor_in':torch.zeros(1,98),'critic_in':torch.zeros(1,666)},batch_size=[1])
policy=ActorCritic(obs,{'policy':['actor_in'],'critic':['critic_in']},12,**cfg['policy'])
runner.alg=SimpleNamespace(policy=policy,optimizer=torch.optim.Adam(policy.parameters(),lr=.123),learning_rate=.123)
runner.adasmpl=sr.AdaSmpl(1.0,1e-6,False)
env_state=saved['env_state'];n=len(env_state['terrain_levels'])
origins=torch.zeros(10,23,3)
origins[:,:,0]=torch.arange(10)[:,None]*8
origins[:,:,1]=torch.arange(23)[None,:]*8
initial_levels=torch.zeros(n,dtype=torch.long)
types=env_state['terrain_types'].clone()
active=origins[initial_levels,types].clone()
terrain=SimpleNamespace(terrain_levels=initial_levels,terrain_types=types,terrain_origins=origins,env_origins=active)
command=SimpleNamespace(gen=DeviceGeneratorCapture(),range_curriculum=SimpleNamespace())
scene=SimpleNamespace(terrain=terrain,env_origins=active)
raw=SimpleNamespace(scene=scene,common_step_counter=0,command_manager=SimpleNamespace(get_term=lambda name:command),cfg=SimpleNamespace(seed=42))
raw.root_pos_w=active.clone()  # fresh env.reset() placed the robot on its initial tile
raw.root_pos_w[:,2]=.4
runner.env=SimpleNamespace(unwrapped=raw)
runtime=entry.EX42StageZeroRuntime(stage_zero_plan=SimpleNamespace(stages=[stage]),plan_sha256=pins['plan_sha256'],
    approval_sha256=pins['approval_sha256'],parent_sha256=pins['parent_sha256'],push_vmax_mps=pins['push_vmax_mps'])
runner.continuous_curriculum=runtime
with patch.object(torch.cuda,'is_available',return_value=False):
    runner.load(str(source),map_location='cpu')
runner.ex42_parent_transfer=saved['ex42_parent_transfer']  # train_start caller line 1017
groups={
 'model_state_dict':runner.alg.policy.state_dict(),
 'optimizer_state_dict':runner.alg.optimizer.state_dict(),
 'perception_state_dict':runner.perception.state_dict(),
 'perception_optimizer_state_dict':runner.perception_optimizer.state_dict(),
 'ppo_learning_rate':runner.alg.learning_rate,'adasmpl':runner.adasmpl.state_dict(),
 'map_switch':runner.map_switch_state(),'env_state':runner._env_state(),
 'continuous_curriculum':runtime.state_dict(),'iter':runner.current_learning_iteration,
 'last_use_gt_frac':runner._last_use_gt_frac,'ex42_parent_transfer':runner.ex42_parent_transfer,
}
checks={k:equal(saved[k],v) for k,v in groups.items()}
test('actual_nn_adam_runtime_restore',lambda:checks)
assert all(checks.values()),checks
rng_cpu={'torch':torch.get_rng_state(),'numpy':np.random.get_state(),'python':random.getstate()}
test('cpu_rng_restore',lambda:{k:equal(v,saved['rng'][k]) for k,v in rng_cpu.items()})
assert all(equal(v,saved['rng'][k]) for k,v in rng_cpu.items())
with patch.object(torch.cuda,'is_available',return_value=True),patch.object(torch.cuda,'set_rng_state_all') as cuda_sink:
    sr.StartRunner.set_rng_state(saved['rng'])
    test('cuda_rng_call_payload_only',lambda:equal(cuda_sink.call_args.args[0],saved['rng']['cuda']))

start=sr.resumed_loop_start(runner.current_learning_iteration,True,runtime)
updates=[sr.curriculum_update_number(runtime,i) for i in range(start,start+full['requested_updates'])]
assert updates==list(range(351,1001))
test('local_cumulative_bounds',lambda:dict(first=updates[0],cumulative_first=12000+updates[0],last=updates[-1],count=len(updates)))
runtime.on_update_start(1000)
test('runtime_rejects_1001',lambda:runtime.on_update_start(1001),True)
runner.log_dir=str(OUT/'not_a_training_run');runner.manifest={};runner.manifest_dir=runner.log_dir
runner.num_steps_per_env=24;runner.gpu_world_size=1;runner._check_code=lambda n:None
with patch.object(sr.run_manifest,'update_progress') as sink:
    runner._manifest_checkpoint(400,'model_400.pt',3072)
    test('manifest_400_consumed_args',lambda:list(sink.call_args.args[2:4]))

offset=torch.linalg.vector_norm(raw.root_pos_w[:,:2]-active[:,:2],dim=1)
test('post_load_robot_vs_restored_origin',lambda:dict(displaced_envs=int((offset>0).sum()),max_m=float(offset.max()),
    note='CPU fixture of reset-before-load order; no physical reset after restoration'))

# Same-run segment creates a new imported-source baseline in memory only.
rebased=copy.deepcopy(fm)
old_imports=copy.deepcopy(rebased['files'])
seg=sr.run_manifest.rebase_files_for_resume(rebased,captured_at='CPU audit')
test('manifest_segment_preserves_old_baseline',lambda:dict(previous_equal=seg['previous']==old_imports,
    active_files=len(seg['active']['imported_sha256']),progress_unchanged=rebased['progress']==fm['progress'],
    checkpoint_map_unchanged=rebased['checkpoints']==fm['checkpoints']))

# Execute the actual installed reset body with deterministic zero noise and a CPU
# pose-write capture. This is not an Isaac physics run.
events_path=Path('C:/isaac/isaaclab/source/isaaclab/isaaclab/envs/mdp/events.py')
reset_ast=next(x for x in ast.parse(events_path.read_text(encoding='utf-8')).body
               if isinstance(x,ast.FunctionDef) and x.name=='reset_root_state_uniform')
class SceneCPU(SimpleNamespace):
    def __getitem__(self,key):
        assert key=='robot'
        return self.robot
default_root=torch.zeros(n,13); default_root[:,2]=.4; default_root[:,3]=1
pose_writes=[]
def write_pose(value,env_ids):
    pose_writes.append(value.clone())
    raw.root_pos_w[env_ids]=value[:,:3]
asset=SimpleNamespace(device='cpu',data=SimpleNamespace(default_root_state=default_root),
                      write_root_pose_to_sim=write_pose,write_root_velocity_to_sim=lambda *a,**k:None)
math_zero=SimpleNamespace(sample_uniform=lambda lo,hi,shape,device:torch.zeros(shape,device=device),
    quat_from_euler_xyz=lambda r,p,y:torch.tensor([1.,0,0,0]).expand(len(r),4),
    quat_mul=lambda a,b:a)
namespace={'torch':torch,'math_utils':math_zero,'SceneEntityCfg':lambda name:SimpleNamespace(name=name)}
module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),reset_ast],type_ignores=[])
exec(compile(ast.fix_missing_locations(module),str(events_path),'exec'),namespace)
assert int((offset>0).sum())==3072 and float(offset.max())==40.
cpu_env=SimpleNamespace(scene=SceneCPU(robot=asset,env_origins=active))
namespace['reset_root_state_uniform'](cpu_env,torch.arange(n),{}, {})
reset_offset=torch.linalg.vector_norm(raw.root_pos_w[:,:2]-active[:,:2],dim=1)
assert len(pose_writes)==1 and float(reset_offset.max())==0.
test('installed_reset_body_cpu_pose_write',lambda:dict(before_displaced=3072,before_max_m=40.,
    after_max_m=float(reset_offset.max()),pose_write_calls=len(pose_writes),
    fixture='zero-noise CPU scene, installed events.py AST; not physical simulation'))

# Execute the exact self-resume IF from train_start with the actual CPU runner.
# Calling the EX41 transplant branch would raise immediately.
train_path=ROOT/'foothold_s2/scripts/train_start.py'
resume_if=next(x for x in ast.walk(ast.parse(train_path.read_text(encoding='utf-8')))
               if isinstance(x,ast.If) and x.lineno==1014)
def forbidden_parent(*args,**kwargs):
    raise AssertionError('EX41 parent transplant was called on EX42 self-resume')
runner.load_ex42_stage_zero_parent=forbidden_parent
ns={'EX42_STAGE_ZERO_RESUME':str(source),'torch':torch,'runner':runner,'json':json,
    'EX42_STAGE_ZERO_RESUME_PROOF':proof}
with patch.object(torch.cuda,'is_available',return_value=False):
    exec(compile(ast.Module(body=[resume_if],type_ignores=[]),str(train_path),'exec'),ns)
assert runner.current_learning_iteration==350
assert equal(runner.alg.policy.state_dict(),saved['model_state_dict'])
test('actual_cli_resume_branch_not_parent',lambda:dict(local=runner.current_learning_iteration,
    first=ns['ex42_transfer']['first_resumed_local_update'],parent_transplant_calls=0))

test('runtime_configuration_1001',lambda:entry.EX42StageZeroRuntime(
    stage_zero_plan=SimpleNamespace(stages=[stage]),plan_sha256=pins['plan_sha256'],
    approval_sha256=pins['approval_sha256'],parent_sha256=pins['parent_sha256'],
    maximum_updates=1001,push_vmax_mps=pins['push_vmax_mps']),True)

# Same-run provenance: constructor replaces the existing startup receipt before
# the post-construction validator inspects it. Only this scratch folder is used.
from foothold_s2.ex42_chain import EX42TrainingChain
receipt_dir=OUT/'receipt_probe'; receipt_dir.mkdir(exist_ok=True)
receipt_path=receipt_dir/'startup_receipt.json'
receipt_path.write_text(json.dumps({'state':'prior_receipt','audit_marker':'preserve_me'}),encoding='utf-8')
before_sha=sha(receipt_path)
test('old_startup_receipt_rejected_before_constructor',lambda:entry.validate_ex42_stage_zero_chain_output(
    receipt_dir,plan_sha256=plan.sha256,parent_sha256=pins['parent_sha256'],allow_existing_run=True),True)
chain=EX42TrainingChain(plan=plan,approvals_path=ROOT/'foothold_s2/curriculum/ex42-approvals.yaml',
    parent_manifest_path='C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/main/EX-41-B-main_20261104_235522/manifest.json',
    run_dir=receipt_dir,repo_root=ROOT,queue_path=OUT/'unused_queue.json')
receipt_result=entry.validate_ex42_stage_zero_chain_output(receipt_dir,plan_sha256=plan.sha256,
    parent_sha256=pins['parent_sha256'],allow_existing_run=True)
assert sha(receipt_path)!=before_sha and 'audit_marker' not in json.loads(receipt_path.read_text(encoding='utf-8'))
test('old_startup_receipt_replaced_before_validation',lambda:dict(state=receipt_result['state'],old_marker_preserved=False))

result={'head':HEAD,'checkpoint_sha256':sha(source),'scope':'CPU consumers only; no Kit/PPO update/physics or CUDA execution',
 'tests':rows,'restore_groups':checks,'state_shapes':{k:list(saved['model_state_dict'][k].shape) for k in ('actor.0.weight','critic.0.weight')},
 'installation':{'rsl_actor':str(sys.modules[ActorCritic.__module__].__file__)},
 'source_hashes':{x:sha(ROOT/x) for x in ['foothold_s2/scripts/train_start.py','foothold_s2/scripts/ex42_training_entry.py','foothold_s2/runners/start_runner.py','foothold_s2/ex42_chain.py']}}
(OUT/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
assert subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()==HEAD
print('AUDIT_WRITTEN',OUT/'audit.json')
