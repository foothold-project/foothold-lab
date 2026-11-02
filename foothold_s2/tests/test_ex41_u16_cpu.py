"""Foot slip is a measured zero-weight diagnostic, not the old ground adapter."""
from types import SimpleNamespace
import pytest
import torch
from foothold_s2.rewards import w86_runtime as wr, basic_gait_bundle as basic
from foothold_s2.tests.test_w86_runtime_cpu import sample


def test_zero_weight_term_is_measured_without_reward_manager_call(tmp_path):
    d=sample(1);d['velocity_xy'][:]=0
    d['velocity_xy'][0,0]=torch.tensor([.3,.4]);d['forces'][0,0,2]=2.
    d['velocity_xy'][0,1]=torch.tensor([3.,4.])  # In the air, not sliding.
    env=SimpleNamespace(num_envs=1,device='cpu',step_dt=.02,common_step_counter=1)
    env._ex41_w86=wr.W86Runtime(env,tmp_path,source=lambda:d)
    assert wr.invalid_env(env).tolist()==[False]  # TerminationManager calls this even with reward weight0.
    row=env._ex41_w86.flush(250)
    assert row['terms']['foot_slip']['sum']==pytest.approx(.25)
    assert row['terms']['foot_slip']['denominator']==1
    assert row['terms']['foot_slip']['mean']==pytest.approx(.25)


@pytest.mark.parametrize('value',[0.,-.05])
def test_old_unverified_feet_regulation_is_not_unlocked(value):
    with pytest.raises(ValueError,match='ground adapter is unverified'):
        basic.validate_settings(dict.fromkeys(basic.WEIGHT_NAMES),False,value)
