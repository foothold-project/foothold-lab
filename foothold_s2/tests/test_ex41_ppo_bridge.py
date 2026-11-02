"""CPU contract bridge: analyst W86 producer to a pinned scripter consumer.

Set EX41_PPO_CONSUMER_ROOT to the independently committed consumer worktree.
This deliberately does not copy or modify runner-owned source files.
"""
import copy
import os
from pathlib import Path
from types import SimpleNamespace
import subprocess
import pytest
import torch
from foothold_s2.rewards import w86_runtime as wr
from foothold_s2.tests.test_w86_runtime_cpu import sample

ROOT=os.environ.get('EX41_PPO_CONSUMER_ROOT')
pytestmark=pytest.mark.skipif(not ROOT,reason='set pinned EX41_PPO_CONSUMER_ROOT')
if ROOT:
    root=Path(ROOT)
    head=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD']).decode().strip()
    if head!='36f6cddf4eb7e34ba21a7c6a0aa95f34dbfc34bd':
        raise ValueError('CPU bridge requires reviewed consumer 36f6cddf')
    import foothold_s2.models
    import foothold_s2.runners
    import foothold_s2.tests
    for module,folder in [(foothold_s2.models,'models'),(foothold_s2.runners,'runners'),(foothold_s2.tests,'tests')]:
        module.__path__=[str(root/'foothold_s2'/folder),*module.__path__]
    from foothold_s2.tests.test_ex41_ppo_valid import _alg


@pytest.mark.parametrize('mirror',[False,True])
@pytest.mark.parametrize('all_bad',[False,True])
def test_actual_w86_mask_preserves_valid_loss_kl_gradients(tmp_path,mirror,all_bad):
    torch.manual_seed(123)
    actual,obs=_alg(mirror=mirror)
    reference,_=_alg(mirror=mirror)
    with torch.no_grad(): actual.policy.std.fill_(.46)
    reference.policy.load_state_dict(copy.deepcopy(actual.policy.state_dict()))
    reference.optimizer.load_state_dict(copy.deepcopy(actual.optimizer.state_dict()))
    env=SimpleNamespace(num_envs=4,device='cpu',step_dt=.02,common_step_counter=1)
    physics=sample(4)
    if all_bad: physics['sole_z'][:]=1e6
    else: physics['yaw'][1]=1e6
    adapter=wr.W86Runtime(env,tmp_path,source=lambda:physics); env._ex41_w86=adapter
    runner=SimpleNamespace(env=SimpleNamespace(unwrapped=env),alg=actual)
    adapter.refresh()
    torch.manual_seed(5)
    actions=actual.act(obs)
    # Independent action-path detection must survive pending clear as well.
    actions[1,0]=float('nan'); wr.quarantine_actions(runner,actions)
    torch.manual_seed(5); reference.act(obs)
    raw=obs.clone(); rew=torch.full((4,),.2); done=torch.ones(4)
    raw,rew,done,extra=wr.quarantine_step(runner,raw,rew,done,{})
    assert torch.equal(actual.policy.std,reference.policy.std)
    expected=torch.zeros(4,dtype=torch.bool) if all_bad else torch.tensor([True,False,True,True])
    assert torch.equal(extra['ex41_ppo_valid'],expected) and not adapter.pending.any()
    actual.process_env_step(obs,rew,done,extra)
    reference.process_env_step(obs,torch.full((4,),.2),torch.ones(4),{'ex41_ppo_valid':expected})
    assert torch.equal(actual.storage.valid[0],expected)
    actual.compute_returns(obs); reference.compute_returns(obs)
    assert torch.equal(actual.storage.advantages,reference.storage.advantages)
    torch.manual_seed(91); a=actual.update()
    torch.manual_seed(91); b=reference.update()
    assert a==b and actual.learning_rate==reference.learning_rate
    for x,y in zip(actual.policy.parameters(),reference.policy.parameters(),strict=True):
        assert torch.equal(x,y)
    if all_bad:
        assert a['ppo_skipped_batches']==2 and not actual.optimizer.state
