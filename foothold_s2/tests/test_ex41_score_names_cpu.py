"""Canonical score names must identify the actual checkpoint, CPU only."""
import json
import re

import pytest

from foothold_s2.tests.test_ex41_fixed_cpu import fixture, counts, tick
from foothold_s2.tests.test_ex41_runtime_cpu import score


@pytest.mark.parametrize('name',[
    'score_1000.json', 'score_1000_copy.json', 'score_01000_{sha}.json',
    'score_1000_x.json', 'score_1000_000000000000.json',
    'score_１０００_{sha}.json', 'score_1000_abcdef１２３４５６.json',
    'score_1000_{sha}0.json', 'score_1000_ABCDEF012345.json',
])
def test_noncanonical_or_wrong_hash_score_holds_dr(tmp_path,name):
    r,_=fixture(tmp_path); tick(r,751); tick(r,1001)
    score(r,1200,metrics={'maintenance_counts':counts(r),'stand_min_passed':64})
    valid=score(r,1000,metrics={'maintenance_counts':counts(r),'stand_min_passed':64})
    body=json.loads(valid.read_text())
    target=valid.with_name(name.format(sha=body['checkpoint_sha256'][:12]))
    valid.rename(target)  # only this test's newly created temporary fixture
    r.on_update_start(1251)
    assert str(target) in r._score_rejections
    assert 'filename' in r._score_rejections[str(target)]['reason']
    assert r.clock.paused and r.clock.recovered==0
    assert r.dr_scale(1501)==r.dr_scale(1251)


def test_name_hash_and_actual_checkpoint_are_accepted(tmp_path):
    r,_=fixture(tmp_path); tick(r,751); tick(r,1001)
    path=score(r,1000,metrics={'maintenance_counts':counts(r),'stand_min_passed':64})
    body=json.loads(path.read_text())
    assert re.fullmatch(r'score_1250_[0-9a-f]{12}\.json',path.name)
    assert path.name==f'score_1250_{body["checkpoint_sha256"][:12]}.json'
    # D153 consumes the exact score at n - 1 - 250, so update 1501
    # consumes the score just written for update 1250.
    r.on_update_start(1501)
    assert r._history[-1]['iteration']==1250 and not r._score_rejections


def test_matching_filename_and_false_body_hash_still_checks_checkpoint(tmp_path):
    r,_=fixture(tmp_path); tick(r,751); tick(r,1001)
    valid=score(r,1000,metrics={'maintenance_counts':counts(r),'stand_min_passed':64})
    body=json.loads(valid.read_text()); body['checkpoint_sha256']='0'*64
    valid.write_text(json.dumps(body))
    target=valid.with_name('score_1000_000000000000.json');valid.rename(target)
    r.on_update_start(1251)
    assert r.clock.paused and r.clock.recovered==0
    assert 'checkpoint differs' in r._score_rejections[str(target)]['reason']


def test_already_seen_body_cannot_bypass_new_filename_hash_check(tmp_path):
    r,_=fixture(tmp_path); tick(r,751); tick(r,1001)
    valid=score(r,1000,metrics={'maintenance_counts':counts(r),'stand_min_passed':64})
    r.on_update_start(1251)
    target=valid.with_name('score_1000_000000000000.json')
    target.write_bytes(valid.read_bytes())
    r.on_update_start(1501)
    assert 'filename SHA12' in r._score_rejections[str(target)]['reason']
    assert r.clock.paused and r.clock.recovered==0
