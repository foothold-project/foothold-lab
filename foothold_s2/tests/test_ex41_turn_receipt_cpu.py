"""W91 known-answer inputs plus read-only replay of historical EX35 arrays."""
import json
from pathlib import Path

import numpy as np
import pytest

from foothold_s2.eval import ex41_turn_receipt as R


def dump(path, value):
    path.write_text(json.dumps(value, allow_nan=False), encoding='utf-8')


@pytest.fixture
def bundle(tmp_path):
    ck = tmp_path / 'model_750.pt'
    ck.write_bytes(b'known checkpoint payload, CPU contract fixture only')
    sha = R.S.sha256_file(ck)
    links = ['base', 'FL_hip', 'FL_thigh', 'FL_calf', 'FL_foot', 'FR_hip', 'FR_thigh',
             'FR_calf', 'FR_foot', 'Head_upper', 'Head_lower', 'RL_hip', 'RL_thigh',
             'RL_calf', 'RL_foot', 'RR_hip', 'RR_thigh', 'RR_calf', 'RR_foot']
    columns = [18]*4 + [19]*4 + [14]*4 + [17]*4
    tiles = [{'env': i, 'col': columns[i], 'level': 0,
              'kind': 'hf_pyramid_slope' if i < 8 else 'random_rough'} for i in range(16)]
    for mode in R.MODES:
        d = tmp_path / ('turn16_' + mode)
        d.mkdir()
        (d/'run.log').write_text('TURNPROBE_DONE {}\n', encoding='utf-8')
        (d/'rc.txt').write_text('0', encoding='utf-8')
        doc = dict(envs=16, map_mode=mode, map_input='reconstruction', checkpoint_iter=750,
            checkpoint_sha256=sha, static=dict(sample_hz=200., physics_dt=.005, link_names=links),
            fixed_terrain=dict(tiles=tiles, assignment_sha256=R.TILE_SHA), protocols={}, forward_gaits={})
        for case in (*R.CASES, *R.FORWARD):
            rotation = case in R.CASES
            proto = R.P.PROTOCOLS[case] if rotation else {'cmd': R.FORWARD[case]}
            meta = dict(cmd=list(proto['cmd']), kept_envs=[True]*16, alive_at_end=16)
            if rotation:
                meta.update(pre=list(proto['pre']) if proto['pre'] else None,
                            terrain_levels_per_env=[0]*16, terrain_types_per_env=columns)
            doc['protocols' if rotation else 'forward_gaits'][case] = meta
            z = {'alive': np.ones((16,1600),bool), 'kept': np.ones(16,bool),
                 'wz': np.full((16,1600),proto['cmd'][2]/2,np.float32),
                 'vx': np.full((16,1600),proto['cmd'][0],np.float32),
                 'force': np.zeros((16,1600,19),np.float32),
                 'feet_pos': np.zeros((16,1600,4,3),np.float32),
                 'root_pos': np.zeros((16,1600,3),np.float32),
                 'root_quat': np.zeros((16,1600,4),np.float32)}
            z['force'][:,:800,list(R.S.FEET)] = 2.
            for k in ('q','qd','target','computed','applied'): z[k] = np.zeros((16,1600,12),np.float32)
            np.savez_compressed(d/('arrays_'+case+'.npz'), **z)
        dump(d/'probe_result.json',doc)
    return tmp_path, ck


def collect(bundle):
    return R.collect(bundle[0],checkpoint=bundle[1],iteration=750,stage='S2a')


def mutate_doc(bundle, fn):
    p = bundle[0]/'turn16_eval_gt/probe_result.json'
    d=json.loads(p.read_text(encoding='utf-8')); fn(d); dump(p,d)


def mutate_array(bundle, fn):
    p=bundle[0]/'turn16_eval_gt/arrays_indep_left.npz'
    with np.load(p) as z: d={k:z[k] for k in z.files}
    fn(d); np.savez_compressed(p,**d)


def test_known_signed_rate_ratio_contact_and_cli(bundle):
    got=collect(bundle)
    assert got['status']=='COMPLETE' and len(got['modes'])==3
    for mode in R.MODES:
        rows=got['modes'][mode]['rows']; assert len(rows)==10
        assert rows['indep_right']['Q']==pytest.approx(.6)
        assert rows['indep_right']['follow_ratio']==pytest.approx(.5)
        assert rows['walk_turn_left']['Q']==pytest.approx(.25)
        assert rows['walk_turn_left']['follow_ratio']==pytest.approx(.5)
        assert rows['indep_left']['C']==.5 and rows['indep_left']['kept']==16
        assert rows['fwd0.5']['body_vx_integral_kept_mean_m']==4.
    assert got['decision'] is None and got['record_only'] and not got['physical_gpu1_verified']
    output=bundle[0]/'receipt.json'
    args=['--root',str(bundle[0]),'--checkpoint',str(bundle[1]),'--iteration','750','--stage','S2a','--out',str(output)]
    assert R.main(args)==0
    before=output.read_bytes(); assert R.main(args)==0 and before==output.read_bytes()
    assert json.loads(before)['modes']['eval_gt']['rows']['indep_left']['C']==.5


@pytest.mark.parametrize('change', ['rc','marker','missing_walk','mode','sha','iteration','tile','command','pre','kept','nan','short'])
def test_incomplete_is_not_complete(bundle,change):
    folder=bundle[0]/'turn16_eval_gt'
    if change=='rc': (folder/'rc.txt').write_text('1')
    elif change=='marker': (folder/'run.log').write_text('NOT_TURNPROBE_DONE')
    elif change=='missing_walk': (folder/'arrays_walk_turn_left.npz').rename(folder/'preserved.npz')
    elif change=='mode': mutate_doc(bundle,lambda d:d.update(map_mode='eval_pred'))
    elif change=='sha': mutate_doc(bundle,lambda d:d.update(checkpoint_sha256='f'*64))
    elif change=='iteration': mutate_doc(bundle,lambda d:d.update(checkpoint_iter=6750))
    elif change=='tile': mutate_doc(bundle,lambda d:d['fixed_terrain']['tiles'][0].update(col=19))
    elif change=='command': mutate_doc(bundle,lambda d:d['protocols']['indep_left'].update(cmd=[0,0,-1.2]))
    elif change=='pre': mutate_doc(bundle,lambda d:d['protocols']['fwd_then_left'].update(pre=None))
    elif change=='kept': mutate_array(bundle,lambda d:d['alive'].__setitem__((0,slice(None)),False))
    elif change=='nan': mutate_array(bundle,lambda d:d['wz'].__setitem__((0,0),np.nan))
    elif change=='short': mutate_array(bundle,lambda d:d.update(force=d['force'][:,:100]))
    got=collect(bundle)
    assert got['status']=='INCOMPLETE' and 'eval_gt' in got['errors']


def test_no_survivors_is_measurement_not_missing(bundle):
    mutate_array(bundle,lambda d:d['kept'].__setitem__(slice(None),False))
    mutate_doc(bundle,lambda d:d['protocols']['indep_left'].update(kept_envs=[False]*16,alive_at_end=0))
    got=collect(bundle)
    assert got['status']=='COMPLETE'
    assert got['modes']['eval_gt']['rows']['indep_left']['Q'] is None
    json.dumps(got,allow_nan=False)


def test_historical_ex35_raw_replay():
    root=Path('C:/mai/wt/foothold-lab/impl-turncases/logs/ex35_eval/m2000')
    if not root.exists(): pytest.skip('historical local raw output absent')
    for mode in R.MODES:
        folder=root/('turn16_'+mode)
        doc=json.loads((folder/'probe_result.json').read_text(encoding='utf-8'))
        row=R.read_mode(folder,mode=mode,checkpoint_sha256=doc['checkpoint_sha256'],iteration=2000)
        assert len(row['rows'])==10
        # Independent direct formula for all eight actual rotation cases.
        for case in R.CASES:
            with np.load(folder/('arrays_'+case+'.npz')) as z:
                k=z['kept']; a=z['alive']; wz=z['wz']; force=z['force']
                sign=np.sign(R.P.PROTOCOLS[case]['cmd'][2])
                q=[float(wz[e][a[e]].astype(float).mean())*sign for e in range(16) if k[e]]
                c=[float((force[e][:,list(R.S.FEET)]>1).all(-1)[a[e]].mean()) for e in range(16) if k[e]]
                assert row['rows'][case]['Q']==pytest.approx(np.mean(q))
                assert row['rows'][case]['C']==pytest.approx(np.mean(c))
