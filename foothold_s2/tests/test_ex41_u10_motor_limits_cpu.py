"""Use explicit motor limits, never the PhysX 1e9 effort sentinel, for U10."""
from types import SimpleNamespace
import pytest
import torch
from foothold_s2.rewards import w86_runtime as wr
from foothold_s2.tests.test_w86_runtime_cpu import sample


def robot():
    return SimpleNamespace(data=SimpleNamespace(joint_effort_limits=torch.full((2,12),1e9)),
        actuators={'legs':SimpleNamespace(joint_indices=slice(0,8),effort_limit=torch.full((2,8),23.5)),
                   'knees':SimpleNamespace(joint_indices=[8,9,10,11],effort_limit=torch.full((2,4),45.43))})


def test_motor_limits_not_physx_sentinel_and_dynamic_values():
    r=robot(); actual=wr.actuator_effort_limits(r)
    torch.testing.assert_close(actual[:,8:],torch.full((2,4),45.43))
    assert (torch.full((2,4),45.)/actual[:,8:]>=.9).all()
    assert not (torch.full((2,4),45.)/r.data.joint_effort_limits[:,8:]>=.9).any()
    r.actuators['knees'].effort_limit[1,0]=30.
    assert wr.actuator_effort_limits(r)[1,8]==30.


@pytest.mark.parametrize('bad',['missing','overlap','shape','nonfinite'])
def test_motor_mapping_rejects_unknown_limits(bad):
    r=robot()
    if bad=='missing': del r.actuators['knees']
    if bad=='overlap': r.actuators['knees'].joint_indices=[7,8,9,10]
    if bad=='shape': r.actuators['knees'].effort_limit=torch.ones(1,4)
    if bad=='nonfinite': r.actuators['knees'].effort_limit[0,0]=float('nan')
    with pytest.raises(ValueError): wr.actuator_effort_limits(r)


def test_u10_records_motor_denominator_torque_and_sample_period(tmp_path):
    env=SimpleNamespace(num_envs=2,device='cpu',step_dt=.02,common_step_counter=1)
    d=sample(2); d['effort_limits']=wr.actuator_effort_limits(robot())
    d['torque'][:,8:]=45.
    runtime=wr.W86Runtime(env,tmp_path,source=lambda:d)
    runtime.refresh(); row=runtime.flush(1)
    assert row['control_dt_s']==.02
    for cell in row['knee_effort']['joints'].values():
        assert cell['ratio']==1. and cell['valid_frames']==2
        assert cell['detail_valid_frames']==2
        assert cell['mean_abs_applied_torque_nm']==45.
        assert cell['mean_effort_limit_nm']==pytest.approx(45.43)
