from pathlib import Path
import yaml
import pytest
from foothold_s2.eval.ex42_task_suite import case_specs, push_applicability, cross_settings


def plan():
    return yaml.safe_load((Path(__file__).parents[1]/'curriculum/ex42-prep.yaml').read_text())


def test_paper_roles_reverse_command_and_record_only_stay_separate():
    p=plan()
    rows=case_specs(p,stage='E4',group='paper',family='V',kind='eval_stairs_010',window_index=2,steps=300)
    assert len(rows)==3
    assert rows['eval_stairs_010_reverse_eval_gt']['command_b']==[-.5,0,0]
    assert sum(r['role']=='judge' for r in rows.values())==2
    assert all(r['role']=='record_only' for r in case_specs(p,stage='E0',group='paper',family='V',kind='eval_stairs_010',window_index=1,steps=300).values())
    for kind in ('eval_slope_45','high_ledge_075','crawl_020','start_go2_eval_both__gaps'):
        assert all(r['role']=='record_only' for r in case_specs(p,stage='E6b',group='paper',family='V',kind=kind,window_index=2,steps=300).values())


def test_four_directions_and_sparse_off_record_first_window():
    p=plan();r=case_specs(p,stage='E5',group='directions',family='C',kind='box',window_index=2,steps=300)
    assert len(r)==12
    assert len({tuple(v['command_b']) for v in r.values()})==4
    assert r['C_box_reverse_eval_gt']['task']=='cross_dir_half_flat'
    assert r['C_box_forward_eval_gt']['task']=='box_center_pass'
    assert all(v['role']=='record_only' for v in r.values() if v['map_mode']=='probe_prop_only')
    assert all(v['role']=='record_only' for k,v in case_specs(p,stage='E5',group='directions',family='C',kind='box',window_index=1,steps=300).items() if '_reverse_' in k)
    with pytest.raises(ValueError):case_specs(p,stage='E5',group='directions',family='C',kind='box',window_index=2,steps=301)


def test_push_mask_exact_no_default_and_never_judge():
    p=plan()
    assert push_applicability(p,'C','box')['status']=='n/a'
    assert push_applicability(p,'E','stairs_high')['status']=='enabled'
    with pytest.raises(ValueError):push_applicability(p,'C','typo')
    assert case_specs(p,stage='E4',group='push',family='C',kind='box',window_index=2,steps=300)=={}
    assert all(v['role']=='record_only' for v in case_specs(p,stage='E4',group='push',family='E',kind='stairs_high',window_index=2,steps=300).values())


def test_missing_or_changed_cross_contract_rejected():
    p=plan();assert cross_settings(p)['valid_min']==48
    del p['evaluation']['cross_dir_half_flat']['statistic']
    with pytest.raises(ValueError):cross_settings(p)


def test_geometry_timing_cannot_fail_perfect_forward_due_to_short_window():
    from foothold_s2.eval.ex42_task_suite import completion_timing
    t=completion_timing(plan(),origin=[.96,4.48,.005],anchors={'exit_x':8.5},speed=1.)
    assert t['steps']==502
    assert t['seconds']==pytest.approx(10.04)
    assert t['seconds']-t['distance_m']>=2.5-1e-9
    r=case_specs(plan(),stage='E5',group='directions',family='C',kind='box',window_index=2,steps=300)
    assert all(v['role']=='record_only' for k,v in r.items() if '_forward_' in k)


def test_direction_judgment_cannot_open_before_e5_and_kind_scope_is_explicit():
    rows=case_specs(plan(),stage='E4',group='directions',family='C',kind='box',window_index=2,steps=300)
    assert all(v['role']=='record_only' for v in rows.values())
    with pytest.raises(ValueError,match='completion evaluator'):
        case_specs(plan(),stage='E2',group='kind',family='B',kind='stones',window_index=2,steps=300)


def test_pre_result_geometry_table_sha_and_measured_row_are_enforced(tmp_path):
    import json
    import numpy as np
    from foothold_s2.eval.ex42_task_suite import validate_geometry_calibration
    from foothold_s2.eval.ex42_task_cells import sha256
    from foothold_s2.eval.ex42_task_mesh import task_anchors
    tile={'family':'E','kind':'stairs_high','level':3,'origin':np.array([.5,4.,0.]),
        'source_mesh_sha256':'1'*64,'size':[8.,8.],'anchors':{},
        'vertices':np.zeros((3,3)),'faces':np.array([[0,1,2]])}
    doc={'sources':{'fixture':{'mesh_sha256':'1'*64}},'rows':[{'family':'E','kind':'stairs_high',
        'level':3,'origin_m':[.5,4.,0.],'anchors':task_anchors(tile)}]}
    file=tmp_path/'geometry.json';file.write_text(json.dumps(doc))
    p=plan();pin=p['evaluation']['forward_completion_timing']['calibration_table']
    pin.update(path=str(file),sha256=sha256(file))
    assert validate_geometry_calibration(p,tile)==sha256(file)
    tile['origin'][0]=4.
    with pytest.raises(ValueError,match='row differs'):validate_geometry_calibration(p,tile)
    file.write_text(json.dumps({**doc,'extra':'changed'}))
    with pytest.raises(ValueError,match='not pinned'):validate_geometry_calibration(p,tile)
