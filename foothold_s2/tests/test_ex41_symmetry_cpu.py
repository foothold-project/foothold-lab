"""D101 derived symmetry: real map64 evidence and known signed pair inputs."""
import copy
import json
from pathlib import Path
import numpy as np
import pytest
from foothold_s2.curriculum import ex41_symmetry as sym

ROOT=Path('C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/score-watch-b/model_6000_d5e9ec400f33')


@pytest.mark.parametrize('left,right,value',[(1.4,.7,.5),(-.2,1.,-.2),(.5,.5,1.),(0.,1.,0.),(-.2,-.5,None),(0.,0.,None)])
def test_signed_unclipped_symmetry(left,right,value):
    row=sym.pair(left,right)
    assert row['left']==left and row['right']==right and row['symmetry']==value
    assert row['valid'] is (value is not None)


def test_real_map_pairs_recomputed_with_full_planned_time():
    doc=json.loads((ROOT/'map64/map_modes.json').read_text(encoding='utf-8'))
    rows=sym.map_pairs(doc)
    for mode in sym.MODES:
        assert len(rows[mode])==4
        for key,(left,right) in sym.MAP_PAIRS.items():
            got=rows[mode]['map64/'+key]
            expected=[]
            for case in (left,right):
                r=doc['modes'][mode][case]
                if case.startswith('spin'):
                    values=[p['yaw_follow_mean_alive']*p['samples_alive']/doc['steps']
                            if p['samples_alive'] else 0. for p in r['per_env']]
                else:
                    denominator=np.linalg.norm(r['command'][:2])*doc['policy_dt_s']*doc['steps']
                    values=[p['command_xy_projection_integral_m']/denominator for p in r['per_env']]
                expected.append(float(np.median(values)))
            assert [got['left'],got['right']]==pytest.approx(expected)
            assert got['symmetry']==pytest.approx(min(expected)/max(expected))


def known_bundle(left=.5,right=1.):
    return {'schema':sym.SCHEMA,'decision_mode':'eval_gt','modes':{
        mode:{key:sym.pair(left,right) for key in sym.EXPECTED_PAIRS} for mode in sym.MODES}}


def test_validate_signed_value_and_detect_forged_derived_number():
    rows=known_bundle(-.2,1.4);sym.validate(rows)
    bad=copy.deepcopy(rows);bad['modes']['eval_gt']['map64/side']['symmetry']=.9
    with pytest.raises(ValueError):sym.validate(bad)
    bad=copy.deepcopy(rows);del bad['modes']['eval_gt']['map64/side']
    with pytest.raises(ValueError):sym.validate(bad)


def test_w78_all48_raw_cells_survive_and_are_separate_from_symmetry():
    raw={f'L{l}_a{a:03d}_{m}_{k}':{'left':1.4,'right':.7,'min_lr_ratio':.7}
         for l in (2,5) for a in (0,30,60,90) for m in sym.MODES for k in sym.STAIR_KINDS}
    before=copy.deepcopy(raw)
    map_rows={m:{'map64/'+k:sym.pair(1.,1.) for k in sym.MAP_PAIRS} for m in sym.MODES}
    got=sym.combine(map_rows,raw);sym.validate(got)
    assert raw==before and len(raw)==48
    assert len(got['modes']['eval_gt'])==20
    assert all(r['symmetry']==.5 for k,r in got['modes']['eval_gt'].items() if k.startswith('w78/'))
