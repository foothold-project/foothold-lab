"""H2: bytes with a correct hash are not necessarily a contact measurement."""
import hashlib
import json
import copy

import numpy as np
import pytest

from boundary_read import load_gait


def proof(source, sha):
    return {'format':'analyst-r5-contact-evidence/1', 'checkpoint_sha256':'a'*64,
            'contact_definition':'norm_Fxyz_gt_1N', 'window_seconds':[1,6], 'dt':.02,
            'feet':{f:{'complete_intervals':20,'contributing_envs':16,
                       'single_sample_fraction':0., 'height_median_m':.01,
                       'drag_fraction':.8, 'negative_fraction_at_0p5':.9}
                    for f in ('FL','FR','RL','RR')},
            'sources':[{'path':str(source),'sha256':sha}]}


def test_plain_text_with_valid_sha_is_not_contact_evidence(tmp_path):
    raw = tmp_path/'not_contact.txt'
    raw.write_text('not a contact measurement')
    p = tmp_path/'proof.json'
    p.write_text(json.dumps(proof(raw, hashlib.sha256(raw.read_bytes()).hexdigest())))
    result = load_gait(p, 'a'*64)
    assert not result['valid'] and not result['valid_conditions']
    assert result['issues']


def complete_raw():
    contact = np.broadcast_to((np.arange(300)%8 < 4)[:,None,None], (300,64,4)).copy()
    force = np.zeros((300,64,4,3))
    # Horizontal force distinguishes norm > 1 from the rejected Fz-only mask.
    force[:,:,:,0] = contact*2.
    return dict(format=np.array('foothold-r5-contact-raw/1'),
                producer=np.array('foothold_s2.eval.ex42_gait_contact'),
                contact_definition=np.array('norm_Fxyz_gt_1N'),foot_names=np.array(['FL','FR','RL','RR']),
                dt=np.array(.02),window_seconds=np.array([1,6]),command=np.array([.2,0.,0.]),
                run_identity=np.array(json.dumps(dict(checkpoint_sha256='a'*64,eval_seed=42,
                                                       mode='eval_gt',code_head='b'*40))),
                alive=np.ones((300,64),bool), contact=contact, force_xyz_n=force,
                foot_height_m=np.where(contact,0.,.04), foot_xy_speed_mps=np.full((300,64,4),.1))


def make_evidence(tmp_path, arrays):
    raw=tmp_path/'contact.npz';np.savez_compressed(raw,**arrays)
    d=proof(raw,hashlib.sha256(raw.read_bytes()).hexdigest())
    # Known-answer: 31 complete .08s flights/env.
    d['feet']={f:dict(complete_intervals=31*64,contributing_envs=64,
                      single_sample_fraction=0.,height_median_m=.04,
                      drag_fraction=126/250,negative_fraction_at_0p5=1.)
               for f in ('FL','FR','RL','RR')}
    p=tmp_path/'proof.json';p.write_text(json.dumps(d));return p


def test_known_contact_raw_is_recomputed_not_just_hashed(tmp_path):
    p=make_evidence(tmp_path,complete_raw())
    got=load_gait(p,'a'*64)
    assert got['valid'] and got['valid_conditions'],got
    assert got['feet']['RR']['complete_intervals']==1984


@pytest.mark.parametrize('field,value',[
    ('format',np.array('arbitrary/1')),
    ('contact_definition',np.array('Fz_gt_1N')),
    ('foot_names',np.array(['FR','FL','RL','RR'])),
    ('contact',np.zeros((300,64,4),bool)),
    ('force_xyz_n',np.zeros((1,64,4,3))),
    ('foot_height_m',np.full((300,64,4),np.nan)),
    ('run_identity',np.array(json.dumps(dict(checkpoint_sha256='c'*64,eval_seed=42,mode='eval_gt',code_head='b'*40)))),
])
def test_well_hashed_but_wrong_measurement_stays_invalid(tmp_path,field,value):
    z=complete_raw();z[field]=value
    got=load_gait(make_evidence(tmp_path,z),'a'*64)
    assert not got['valid'] and got['issues']


def test_declared_foot_statistics_cannot_override_raw(tmp_path):
    p=make_evidence(tmp_path,complete_raw());d=json.loads(p.read_text())
    d['feet']['RR']['negative_fraction_at_0p5']=.9;p.write_text(json.dumps(d))
    got=load_gait(p,'a'*64)
    assert not got['valid'] and 'declared/raw' in got['issues'][0]


def test_source_hash_mismatch_is_not_recomputed_as_trusted_evidence(tmp_path):
    p=make_evidence(tmp_path,complete_raw());d=json.loads(p.read_text())
    d['sources'][0]['sha256']='f'*64;p.write_text(json.dumps(d))
    got=load_gait(p,'a'*64)
    assert not got['valid'] and 'SHA mismatch' in got['issues'][0]


def test_real_m250_force_only_csv_cannot_fill_unmeasured_height_and_drag(tmp_path):
    from pathlib import Path
    raw=Path('/home/jay/data/foothold/s2_lab/gait_contact_m250_20261113_191959/gait_raw_fwd0.2.csv')
    if not raw.is_file():pytest.skip('read-only m250 gait source unavailable')
    d=proof(raw,hashlib.sha256(raw.read_bytes()).hexdigest())
    d['checkpoint_sha256']='763a1eae9947385164b9606b8c60dd392747e3d540b8b448b86b2eb877bcf374'
    p=tmp_path/'proof.json';p.write_text(json.dumps(d))
    got=load_gait(p,d['checkpoint_sha256'])
    assert not got['valid'] and got['issues']
