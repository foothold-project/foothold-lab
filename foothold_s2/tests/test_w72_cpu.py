"""Known-input W72 approval, Git snapshot, and automatic-control tests."""
import copy
import subprocess
import pytest
from foothold_s2.curriculum import w72


def test_explicit_approval_and_locked_field():
    old={'reward_weights':{'swing':-10., 'stumble':-2., 'zero_yaw':-.5}}
    new=copy.deepcopy(old); new['reward_weights']['swing']=-5.
    approvals={'format':'foothold-ex41-approvals/1','fields':{
        'reward_weights.swing':{'decision_id':'D123','bounds':[-20.,-2.]}}}
    rows=w72.validate_change(old,new,approvals)
    assert rows == [{'path':'reward_weights.swing','before':-10.,'after':-5.,'decision_id':'D123'}]
    new['reward_weights']['stumble']=-2.5
    with pytest.raises(ValueError): w72.validate_change(old,new,approvals)
    for field in ('kp','clip_param','actor_dims'):
        permit={'format':'foothold-ex41-approvals/1','fields':{field:{'decision_id':'BAD','bounds':[0,1000]}}}
        with pytest.raises(ValueError): w72.validate_change({field:1},{field:2},permit)
    new=copy.deepcopy(old); new['reward_weights']['swing']=float('nan')
    with pytest.raises(ValueError): w72.validate_change(old,new,approvals)


def test_git_snapshot_rejects_dirty_and_untracked(tmp_path):
    def git(*args): return subprocess.run(['git','-C',str(tmp_path),*args],check=True,capture_output=True)
    git('init'); git('config','user.name','CPU Test'); git('config','user.email','cpu@example.invalid')
    c=tmp_path/'config.yaml'; a=tmp_path/'approval.yaml'
    c.write_text('format: foothold-ex41-boundary/1\nvalues: {}\n',encoding='utf-8')
    a.write_text('format: foothold-ex41-approvals/1\nfields: {}\n',encoding='utf-8')
    with pytest.raises(ValueError): w72.read_committed_pair(c,a)
    git('add','config.yaml','approval.yaml'); git('commit','-m','known snapshot')
    snap=w72.read_committed_pair(c,a)
    assert snap['config']['values']=={} and len(snap['config_sha256'])==64
    c.write_text('values: {changed: true}\n',encoding='utf-8')
    assert snap['config']['values']=={}  # frozen result
    with pytest.raises(ValueError): w72.read_committed_pair(c,a)


def test_pair_control_is_bounded_and_noise_reverts():
    assert hasattr(w72,'adjust_pair'), 'missing automatic pair consumer'
    bias=0.
    for _ in range(8): bias=w72.adjust_pair(bias, (55, .2), (64,.1))
    assert bias==pytest.approx(.02)
    assert w72.adjust_pair(bias,(64,.11),(64,.10))==0.
    assert w72.adjust_pair(0.,(64,.1),(60,.1))==pytest.approx(-.01)
