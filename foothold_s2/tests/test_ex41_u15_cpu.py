"""Known all-link contact forces, no Kit."""
from types import SimpleNamespace
import pytest
import torch
from foothold_s2.rewards import w86_runtime as wr
from foothold_s2.tests.test_w86_runtime_cpu import sample


def test_all_link_contacts_by_name_with_invalid_env_excluded(tmp_path):
    d=sample(); names=['base','FL_foot','RR_calf','FL_thigh','Head_lower','custom_link']
    d['all_link_names']=names;d['all_forces']=torch.zeros(3,6,3)
    d['all_forces'][0,:,2]=torch.tensor([0.,2.,3.,0.,1.,0.])
    d['all_forces'][1,:,2]=torch.tensor([4.,0.,5.,6.,0.,7.])
    d['all_forces'][2,:,2]=100;d['physical_valid'][2]=False
    env=SimpleNamespace(num_envs=3,device='cpu',step_dt=.02,common_step_counter=1)
    r=wr.W86Runtime(env,tmp_path,source=lambda:d);r.refresh()
    state=r.state_dict()
    resumed=wr.W86Runtime(env,tmp_path/'resume',source=lambda:d);resumed.load_state_dict(state)
    for recorder in (r,resumed):
        row=recorder.flush(50)['all_link_contact']
        assert row['threshold_n']==1 and row['source']=='net_forces_w'
        links=row['links'];assert list(links)==names
        assert [links[n]['contact_frames'] for n in names]==[1,1,2,1,0,1]
        assert [links[n]['valid_frames'] for n in names]==[2]*6
        assert [links[n]['force_peak_n'] for n in names]==[4,2,5,6,1,7]
        assert links['RR_calf']['mean_force_n']==4 and links['RR_calf']['contact_ratio']==1
        assert links['Head_lower']['group']=='trunk' and links['custom_link']['group']=='other'


def test_all_link_order_change_is_not_silently_merged(tmp_path):
    d=sample();d['all_link_names']=['base','RR_calf'];d['all_forces']=torch.zeros(3,2,3)
    env=SimpleNamespace(num_envs=3,device='cpu',step_dt=.02,common_step_counter=1)
    r=wr.W86Runtime(env,tmp_path,source=lambda:d);r.refresh()
    d['all_link_names'].reverse();env.common_step_counter=2
    with pytest.raises(ValueError,match='link order'):r.refresh()


def test_missing_all_links_is_unavailable_not_zero(tmp_path):
    env=SimpleNamespace(num_envs=3,device='cpu',step_dt=.02,common_step_counter=1)
    r=wr.W86Runtime(env,tmp_path,source=sample);r.refresh()
    assert r.flush(50)['all_link_contact']=={'status':'unavailable','reason':'source_has_no_all_link_forces'}
