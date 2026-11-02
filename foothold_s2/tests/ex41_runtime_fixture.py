"""Real committed W72 files plus the actual stage consumer, CPU-only scene."""
from functools import partial
from pathlib import Path
import subprocess
from types import SimpleNamespace
import torch
import yaml
from foothold_s2.curriculum.continuous import load_plan, make_runtime, sha256
from foothold_s2.curriculum.ex41 import apply_runtime_fields

TABLE=Path(__file__).parents[1]/'curriculum/ex41.yaml'


def attach_consumer(runtime):
    terrain=SimpleNamespace(terrain_origins=torch.zeros(10,2,3),terrain_levels=torch.tensor([0,1,2,0]))
    env=SimpleNamespace(scene=SimpleNamespace(terrain=terrain),cfg=SimpleNamespace(episode_length_s=20.))
    runner=SimpleNamespace(env=SimpleNamespace(unwrapped=env),alg=SimpleNamespace(entropy_coef=.07,desired_kl=.08),
        ex41_critic_mirror=False,continuous_curriculum=runtime)
    def setter(enabled,approval=None):
        runner.ex41_critic_mirror=False
        if enabled:
            a=approval
            if (a['gate']!='W72' or a['status']!='APPROVED' or a['approval_id']!=a['approval_sha256']
                or sha256(a['boundary_file'])!=a['config_sha256'] or sha256(a['approval_file'])!=a['approval_sha256']):
                raise ValueError('CPU mirror actual authorization changed')
        runner.ex41_critic_mirror=enabled
    runner.set_ex41_critic_mirror=setter
    runtime.set_stage_changed_hook(partial(apply_runtime_fields,runner))
    return runner


def real_runtime(root,*,parent=7500,smoke=None,w71=False):
    root=Path(root).resolve(); repo=root/'repo'; repo.mkdir(parents=True)
    def git(*args):
        return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.PIPE).decode().strip()
    git('init','-q'); git('config','core.autocrlf','false')
    doc=yaml.safe_load(TABLE.read_text()); boundary=yaml.safe_load(TABLE.with_name('ex41-boundary.yaml').read_text())
    approvals=yaml.safe_load(TABLE.with_name('ex41-approvals.yaml').read_text())
    doc['parent_update']=parent; initial={6000:.5,7500:1.}[parent]
    if parent==6000: doc['parent_sha256']='d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5'
    doc['domain_randomization']['scale']=initial
    boundary['values']['dr']={'target_scale':initial,'ramp_updates':0}
    boundary['values']['w71_ready']=w71
    if w71: approvals['fields']['w71_ready']={'decision_id':'CPU-registered-consumer','choices':[False,True]}
    for name,data in [('ex41.yaml',doc),('ex41-boundary.yaml',boundary),('ex41-approvals.yaml',approvals)]:
        (repo/name).write_text(yaml.safe_dump(data),encoding='utf-8',newline='\n')
    git('add','--','ex41.yaml','ex41-boundary.yaml','ex41-approvals.yaml')
    git('-c','user.name=CPU fixture','-c','user.email=cpu@example.invalid','-c','commit.gpgsign=false','commit','-qm','CPU actual runtime inputs')
    plan=load_plan(repo/'ex41.yaml',arm='B',smoke_boundaries=smoke)
    runtime=make_runtime(plan,4,'cpu',root/'run'); consumer=attach_consumer(runtime)
    runtime.start(plan.parent_sha256)
    actual=runtime.boundary_receipt()['readback']
    assert actual['ppo']=={'entropy_coef':.01,'desired_kl':.01}
    assert actual['authorization']['config_commit']==git('rev-parse','HEAD')
    return runtime,consumer
