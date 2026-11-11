"""Canonical record-only dimensions, physical surfaces and coverage of prep IDs."""
from pathlib import Path

import numpy as np
import pytest
import yaml

from foothold_s2.terrains import ex42_eval_terrains as et
from foothold_s2.terrains.ex42_mesh_mount import MeshHeights


def sample(kind, points):
    t = et.build_tile(kind, seed=42)
    return t, MeshHeights(t.mesh.vertices, t.mesh.faces).at(np.asarray(points))


@pytest.mark.parametrize('height', [.27, .30])
def test_record_stair_height_is_physical(height):
    t, z = sample(f'eval_stairs_{round(100*height):03d}', [[.99,4],[1.01,4],[1.31,4]])
    assert z == pytest.approx([0,height,2*height])
    assert t.dimensions['role'] == 'record'


@pytest.mark.parametrize('kind,width', [('eval_balance_090',.09),('eval_balance_0765',.0765)])
def test_record_beam_width_is_physical(kind,width):
    t, z = sample(kind, [[4,4-width/2+.001],[4,4+width/2-.001],
                          [4,4-width/2-.001],[4,4+width/2+.001]])
    assert z[:2] == pytest.approx([t.dimensions['support_height_m']]*2)
    assert z[2:] == pytest.approx([-t.dimensions['depth_m']]*2)


@pytest.mark.parametrize('kind,width', [('gap_090',.9),('gap_100',1.)])
def test_record_gap_width_is_physical(kind,width):
    support=(6-3*width)/4
    t,z=sample(kind,[[1+support-.001,4],[1+support+.001,4],
                     [1+support+width-.001,4],[1+support+width+.001,4]])
    assert z == pytest.approx([0,-t.dimensions['depth_m'],-t.dimensions['depth_m'],0])
    assert t.dimensions['gap_width_m'] == width


@pytest.mark.parametrize('kind,before,after', [('high_ledge_075',0,.75),
    ('climb_down_075',.75,0),('climb_down_088',.88,0)])
def test_record_ledge_height_is_physical(kind,before,after):
    t,z=sample(kind,[[3.99,4],[4.01,4]])
    assert z == pytest.approx([before,after])
    assert t.origin[2] == before


def test_consecutive_height_is_per_rise_not_total():
    t,z=sample('consecutive_040', [[.8,4],[2.4,4],[4,4],[5.6,4],[7.2,4]])
    assert z == pytest.approx([0,.4,.8,.4,0])
    assert t.dimensions['rise_m'] == .4
    assert t.dimensions['top_height_m'] == .8


def test_crawl_is_air_under_a_roof_not_a_solid_block():
    from foothold_s2.tests.test_hipan_posture_cpu import _first_triangle_hit
    t=et.build_tile('crawl_020',seed=42)
    assert _first_triangle_hit([t.mesh],[4,4,.1],[0,0,1]) == pytest.approx(.1)
    assert _first_triangle_hit([t.mesh],[4,4,.1],[0,0,-1]) == pytest.approx(.1)
    assert _first_triangle_hit([t.mesh],[1,4,.1],[1,0,0]) == float('inf')


def test_all_prep_paper_cases_resolve_without_making_reverse_new_geometry():
    from foothold_s2.terrains.ex42_eval_records import case_contract
    cfg=yaml.safe_load((Path(__file__).parents[1]/'curriculum/ex42-prep.yaml').read_text())
    cells=cfg['terrain_manifest_contract']['evaluation_paper_cells']
    ids=[case for value in cells.values() for case in (value if isinstance(value,list) else [value])]
    for case in ids:
        contract=case_contract(case)
        assert contract['geometry_id'] in et.KINDS
    reverse=case_contract('eval_stairs_015_reverse')
    assert reverse['geometry_id']=='eval_stairs_015'
    assert reverse['body_command_vx_sign']==-1
    assert reverse['approach_yaw_rad']==pytest.approx(np.pi)
    assert reverse['training_allowed'] is False


def test_later_record_columns_do_not_change_original_twenty_one():
    assert len(et.KINDS)==32
    assert et.KINDS[20]==et.SURFACE_SPIN
    from foothold_s2.scripts.ex42_eval_mesh_build import GROUPS
    assert len(GROUPS['start'])==12
    assert len(GROUPS['records'])==11
