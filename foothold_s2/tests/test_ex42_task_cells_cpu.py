import copy
import numpy as np
import pytest

from foothold_s2.eval.ex42_task_cells import summarize, compare_cross_direction, expanded_e_exit


def trace(n=64, steps=60):
    root = np.zeros((steps, n, 3))
    root[..., 0] = np.linspace(0, 7, steps)[:, None]
    root[..., 1] = 4
    root[..., 2] = .9
    feet = np.repeat(root[:, :, None], 4, axis=2)
    feet[..., 2] = .6
    return dict(root_pos_w=root, foot_pos_w=feet,
        contact=np.ones((steps,n,4), bool), alive=np.ones((steps,n),bool),
        reset_valid=np.ones(n,bool), tile_offset_w=np.zeros((n,3)),
        initial_root_pos_w=root[0].copy(), body_vel_b=np.zeros((steps,n,3)),
        command_b=np.broadcast_to([1.,0,0],(steps,n,3)).copy(),
        initial_yaw_rad=np.zeros(n), forbidden_contact=np.zeros((steps,n),bool))


def spec(task='box_center_pass'):
    return dict(task=task, map_mode='eval_gt', role='judge', command_b=[1.,0,0],
        hold_s=.5, foot_height_tolerance_m=.08, valid_min=48, success_min=52,
        survival_min=60, dt=.1, steps=60)


def anchors():
    return dict(center_bounds_xy=[2,3,3,5], center_top_m=.6, exit_x=6,
        exit_bounds_y=[3,5], support_floor_m=.6)


def test_box_bypass_does_not_count_as_central_pass():
    t=trace(); t['root_pos_w'][:,0,1]=2
    t['foot_pos_w'][:,0,:,1]=2
    out=summarize(t,spec=spec(),anchors=anchors())
    assert out['success_count']==63
    assert out['per_env'][0]['bypass'] is True
    assert out['per_env'][1]['center_pass'] is True


def test_center_xy_without_top_contact_is_bypass():
    t=trace(); t['foot_pos_w'][:,:, :,2]=0
    out=summarize(t,spec=spec(),anchors=anchors())
    assert out['success_count']==0


def test_reach_then_fall_is_failure_not_removed_from_denominator():
    t=trace(); t['alive'][-1,0]=False
    out=summarize(t,spec=spec(),anchors=anchors())
    assert (out['valid_count'],out['success_count'],out['survival_count'])==(64,63,63)


def test_resurrection_rejected_and_nan_not_silently_removed():
    t=trace(); t['alive'][3,0]=False
    with pytest.raises(ValueError,match='alive'): summarize(t,spec=spec(),anchors=anchors())
    t=trace();t['root_pos_w'][4,0,0]=np.nan
    with pytest.raises(ValueError,match='finite'): summarize(t,spec=spec(),anchors=anchors())


def test_tile_end_requires_lane_and_hold():
    t=trace();t['root_pos_w'][:,0,1]=20
    out=summarize(t,spec=spec('tile_end_reach'),anchors=anchors())
    assert out['success_count']==63
    t=trace();t['root_pos_w'][:-1,:,0]=0
    assert summarize(t,spec=spec('tile_end_reach'),anchors=anchors())['success_count']==0


def cross_row(distance=2.,survivors=60,valid=64):
    return dict(envs=64,valid_count=valid,survival_count=survivors,
        projected_distance_m=[distance]*64,role='record_only',
        checkpoint_sha256='a'*64,seed=42,map_mode='eval_gt',command_b=[0,.5,0],
        steps=300,dt=.02)


def test_cross_direction_exact_pair_and_first_window_record():
    row,flat=cross_row(),cross_row(4.)
    assert compare_cross_direction(row,flat,window_index=1)['role']=='record_only'
    assert compare_cross_direction(row,flat,window_index=2)['judgement']=='PASS'
    assert compare_cross_direction(cross_row(1.999),flat,window_index=2)['judgement']=='FAIL'
    assert compare_cross_direction(cross_row(survivors=59),flat,window_index=2)['judgement']=='FAIL'
    for key,value in [('seed',43),('map_mode','eval_pred'),('steps',301),('dt',.01),
                      ('checkpoint_sha256','b'*64),('command_b',[0,-.5,0])]:
        other=copy.deepcopy(flat);other[key]=value
        with pytest.raises(ValueError,match='pair'): compare_cross_direction(row,other,window_index=2)


def test_cross_nonpositive_flat_invalid_floor_and_proportional_threshold():
    assert compare_cross_direction(cross_row(),cross_row(0),window_index=2)['judgement']=='HOLD'
    assert compare_cross_direction(cross_row(valid=47,survivors=47),cross_row(),window_index=2)['judgement']=='HOLD'
    assert compare_cross_direction(cross_row(survivors=45,valid=48),cross_row(),window_index=2)['judgement']=='PASS'
    assert compare_cross_direction(cross_row(survivors=44,valid=48),cross_row(),window_index=2)['judgement']=='FAIL'


def test_projection_is_signed_world_direction_and_freezes_dead_env():
    t=trace();s=spec('cross_dir_half_flat');s['command_b']=[0,.5,0]
    t['command_b'][:]=[0,.5,0];t['initial_yaw_rad'][:]=-np.pi/2
    out=summarize(t,spec=s,anchors=anchors())
    assert np.allclose(out['projected_distance_m'],7.)


def test_expanded_e_requires_all_four_measured_exits():
    rows={k:dict(level=level,judgement='PASS') for k,level in
        [('slope_steep',6),('slope_steep_inv',6),('stairs_high',3),('stairs_high_inv',3)]}
    assert expanded_e_exit(rows)['judgement']=='PASS'
    rows['slope_steep']['level']=5
    assert expanded_e_exit(rows)['judgement']=='HOLD'
    del rows['stairs_high']
    assert expanded_e_exit(rows)['judgement']=='HOLD'
