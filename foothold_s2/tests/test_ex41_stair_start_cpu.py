"""P4-2 known angles, real reset hook, terrain rows, and n0 receipt."""
import json
from types import SimpleNamespace as NS

import pytest
import torch

from foothold_s2.rewards import stair_start_hist as H, w86_runtime as W
from foothold_s2.curriculum.ex41 import terrain_distribution


def env_fixture(degrees=(0.,30.,60.,85.,-30.,180.,270.,359.)):
    yaw=torch.deg2rad(torch.tensor(degrees,dtype=torch.float64))
    q=torch.zeros(len(yaw),4,dtype=torch.float64); q[:,0]=torch.cos(yaw/2); q[:,3]=torch.sin(yaw/2)
    cfg=NS(curriculum=True,num_cols=4,num_rows=10,sub_terrains={
        n:NS(proportion=.25) for n in (*H.STAIRS,'random_rough')})
    terrain=NS(cfg=NS(terrain_generator=cfg),terrain_types=torch.zeros(len(yaw),dtype=torch.long),
               terrain_levels=torch.zeros(len(yaw),dtype=torch.long))
    class Scene(dict): pass
    scene=Scene(robot=NS(data=NS(root_quat_w=q))); scene.terrain=terrain
    return NS(scene=scene,num_envs=len(yaw),device='cpu',step_dt=.02,common_step_counter=0)


def test_known_bins_widths_and_full_yaw_preserved():
    hist=H.StairStartHistogram('cpu')
    yaw=torch.deg2rad(torch.tensor([0.,15.,30.,45.,60.,75.,89.,90.,-30.,180.],dtype=torch.float64))
    hist.add(yaw,torch.zeros(10,dtype=torch.long))
    row=hist.snapshot()
    assert row['by_terrain']['pyramid_stairs']['counts']==[3,2,3,2]
    assert sum(row['by_terrain']['pyramid_stairs']['yaw_counts'])==10
    assert row['uniform_expected_fraction']==[1/6,1/3,1/3,1/6]


def test_reset_hook_catches_pre_adapter_reset_and_publishes_terrain_row():
    env=env_fixture((0.,30.,60.,85.))
    before=env.scene['robot'].data.root_quat_w.clone()
    W.reset_runtime(env,torch.arange(4))
    row=terrain_distribution(env)['stair_start_angle_hist']
    assert row['by_terrain']['pyramid_stairs']['counts']==[1,1,1,1]
    assert row['resets_seen']==4 and row['sample_count']==4
    torch.testing.assert_close(before,env.scene['robot'].data.root_quat_w)
    # Name/column lookup follows actual generator, not env index.
    env.scene.terrain.terrain_types[:]=torch.tensor([1,2,3,0])
    W.reset_runtime(env,torch.arange(4))
    row=terrain_distribution(env)['stair_start_angle_hist']
    assert row['by_terrain']['pyramid_stairs_inv']['counts']==[1,0,0,0]
    assert row['by_terrain']['stage_stairs']['counts']==[0,1,0,0]
    assert row['sample_count']==7 and row['resets_seen']==8


def test_nonfinite_quaternion_and_unknown_terrain_are_visible():
    env=env_fixture((0.,30.,60.,85.))
    env.scene['robot'].data.root_quat_w[1]=float('nan')
    env.scene['robot'].data.root_quat_w[2]=0
    env.scene.terrain.terrain_types[3]=9
    W.reset_runtime(env,None)
    row=H.snapshot(env)
    assert row['sample_count']==1
    assert row['by_terrain']['pyramid_stairs']['invalid_yaw']==2
    assert row['unclassified']==1
    json.dumps(row,allow_nan=False)


def test_no_stair_samples_not_claimed_uniform():
    env=env_fixture(); env.scene.terrain.terrain_types[:]=3
    W.reset_runtime(env,None)
    assert H.snapshot(env)['status']=='no_stair_reset_samples'
    assert H.snapshot(env)['sample_count']==0


def test_n0_attachment_receipt_and_no_duplicate_cache_reset(tmp_path,monkeypatch):
    env=env_fixture((0.,30.,60.,85.)); W.reset_runtime(env,None)
    monkeypatch.setattr(W,'PhysicalSource',lambda env:lambda: {})
    adapter=W.attach_runtime(env,NS(is_ex41=True),tmp_path)
    row=json.loads((tmp_path/'ex41_stair_start.jsonl').read_text(encoding='utf-8'))
    assert row['initialization_index']==0 and row['iteration'] is None
    assert row['stair_start_angle_hist']['sample_count']==4
    adapter.on_reset(torch.arange(4))
    assert H.snapshot(env)['sample_count']==4
    W.reset_runtime(env,torch.arange(2))
    assert H.snapshot(env)['sample_count']==6


def test_missing_metadata_records_error_and_preserves_reset():
    calls=[]
    env=NS(device='cpu',_ex41_w86=NS(on_reset=lambda ids:calls.append(ids)))
    W.reset_runtime(env,None)
    assert len(calls)==1 and H.snapshot(env)['error'].startswith('AttributeError')


def test_50_and_boundary_output_contains_reset_histogram(tmp_path):
    from foothold_s2.tests.ex41_runtime_fixture import real_runtime
    from foothold_s2.tests.test_ex41_u12_cpu import scene_for
    runtime,runner=real_runtime(tmp_path)
    runtime.on_update_start(1)
    terrain=scene_for(runtime,runner)
    env=runner.env.unwrapped; env.device='cpu'
    terrain.cfg.terrain_generator.sub_terrains={n:NS(proportion=.5) for n in H.STAIRS[:2]}
    env.scene['robot'].data.root_quat_w=torch.tensor([[1.,0,0,0]]*4)
    W.reset_runtime(env,None)
    runtime.flush_consumption(50)
    runtime.on_update_start(251)
    W.reset_runtime(env,torch.tensor([0]))
    runtime.flush_consumption(251)
    rows=[json.loads(line) for line in (runtime.log_dir/'stage_log.jsonl').read_text().splitlines()]
    rows={r['iteration']:r for r in rows if r.get('event')=='terrain_distribution'}
    assert rows[50]['stair_start_angle_hist']['sample_count']==4
    assert rows[251]['stair_start_angle_hist']['sample_count']==5
