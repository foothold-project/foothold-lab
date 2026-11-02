"""Lead 21:2x follow-up: actual JSON readers, record-only P3 and durable errors."""
import json
from pathlib import Path

import pytest

from foothold_s2 import ex41_score_watch as watch
from foothold_s2.curriculum import ex41_symmetry as sym
from foothold_s2.curriculum.continuous import load_plan
from foothold_s2.tests.test_ex41_fixed_cpu import fixture, counts, tick
from foothold_s2.tests.test_ex41_runtime_cpu import score
from foothold_s2.tests.test_ex41_score_clock_cpu import clock_rows
from foothold_s2.tests.test_ex41_score_watch_cpu import native, replay_run, replay_tick, TABLE, SOURCE


def test_real_map_p3_survives_absent_w78_and_marks_exact_missing_pairs(tmp_path):
    cp, folder = native(6000)
    row = watch.collect(cp, 'S2a', folder, load_plan(TABLE, arm='B'))
    bundle = row['metrics']['critic_mirror_symmetry']
    sym.validate(bundle)
    expected = sym.map_pairs(watch.read(folder/'map64/map_modes.json'))
    for mode in sym.MODES:
        assert {k: v for k, v in bundle['modes'][mode].items() if k.startswith('map64/')} == expected[mode]
        assert len(bundle['missing_pairs'][mode]) == 16
        assert all(k.startswith('w78/') for k in bundle['missing_pairs'][mode])
        assert all(bundle['modes'][mode][k]['reason'] == 'missing_side' for k in bundle['missing_pairs'][mode])
    assert row['components']['critic_mirror_symmetry'] == 'partial_missing_w78'
    assert row['evaluation_state'] == 'complete' and len(row['metrics']['maintenance_counts']) == 26


@pytest.mark.parametrize('left,right', [(0., 0.), (-.2, -.7), (0., -.4)])
def test_both_nonpositive_preserved_and_reported_without_mirror_activation(tmp_path, left, right):
    r, consumer = fixture(tmp_path)
    map_rows = {m: {'map64/'+k: sym.pair(1., 1.) for k in sym.MAP_PAIRS} for m in sym.MODES}
    map_rows['eval_gt']['map64/side'] = sym.pair(left, right)
    assert map_rows['eval_gt']['map64/side']['reason'] == 'both_nonpositive'
    bundle = sym.combine(map_rows, None)
    score(r, 250, metrics={'maintenance_counts': counts(r), 'stand_min_passed': 64,
                           'critic_mirror_symmetry': bundle})
    r.on_update_start(251)
    events = [json.loads(x) for x in (r.log_dir/'stage_log.jsonl').read_text(encoding='utf-8').splitlines()]
    event = next(x for x in events if x['event'] == 'critic_mirror_both_nonpositive')
    assert event['pair_ids'] == ['map64/side'] and event['score_iteration'] == 250
    observation = next(x for x in events if x['event'] == 'critic_mirror_observation')
    pair = observation['observations'][-1]['pairs']['map64/side']
    assert pair['left'] == left and pair['right'] == right and pair['symmetry'] is None
    assert not observation['condition_met'] and not consumer.ex41_critic_mirror


@pytest.mark.parametrize('bad_iteration', [750, 1200, 1250])
@pytest.mark.parametrize('defect', ['nan', 'sha'])
def test_other_iteration_error_does_not_erase_exact_expected_score(tmp_path, bad_iteration, defect):
    r, _ = fixture(tmp_path)
    tick(r, 751); tick(r, 1001)
    score(r, 1000, metrics={'maintenance_counts': counts(r), 'stand_min_passed': 64})
    bad = score(r, bad_iteration, metrics={'maintenance_counts': counts(r), 'stand_min_passed': 64})
    data = watch.read(bad)
    if defect == 'nan':
        data['metrics']['gait_sync'] = float('nan')
    else:
        data['evidence'][0]['sha256'] = '0'*64
    bad.write_text(json.dumps(data), encoding='utf-8')
    r.on_update_start(1251)
    assert str(bad) in r._score_rejections
    assert clock_rows(r)[-1]['selected_score_iteration'] == 1000
    assert not r.clock.paused and r.dr_scale(1501) > r.dr_scale(1251)


def final_request(run, iteration, stage='T0_prime'):
    plan = load_plan(TABLE, arm='B'); cp = run/f'model_{iteration}.pt'
    doc = {'format': 'foothold-ex41-final-eval-request/1', 'training_finished': True, 'graduated': False,
           'checkpoint': {'iteration': iteration, 'path': str(cp.resolve()), 'sha256': watch.sha256(cp)},
           'stage_id': stage, 'parent_sha256': plan.parent_sha256, 'schedule_sha256': plan.effective_sha256,
           'plan_sha256': plan.sha256}
    doc['request_id'] = watch.digest(doc)
    folder = run/'final_eval_requests'; folder.mkdir(exist_ok=True)
    path = folder/f'final_{iteration}_{doc["checkpoint"]["sha256"][:12]}.json'
    path.write_text(json.dumps(doc), encoding='utf-8')
    return path


@pytest.mark.parametrize('late', [False, True])
def test_final_stage_mismatch_receipt_preserves_score_and_does_not_starve_next(tmp_path, late):
    run = replay_run(tmp_path); state = watch.initial_state(run, TABLE, watch.DEFAULT_CONFIG)
    if not late: request = final_request(run, 5750)
    first = replay_tick(tmp_path, run, state)
    original = Path(first['score_path']).read_bytes()
    if late: request = final_request(run, 5750)
    request_bytes = request.read_bytes()
    second = replay_tick(tmp_path, run, state)
    assert second['iteration'] == 6000 and second['state'] == 'complete'
    assert Path(first['score_path']).read_bytes() == original and request.read_bytes() == request_bytes
    errors = list((tmp_path/'out/final_request_errors').glob('*.json'))
    assert len(errors) == 1
    receipt = watch.read(errors[0])
    assert receipt['event'] == 'final_request_rejected' and receipt['alert'] is True
    assert receipt['request']['sha256'] == watch.sha256(request) and 'stage' in receipt['reason']
    assert not receipt['graduated']
    assert replay_tick(tmp_path, run, state)['state'] == 'idle'
    assert len(list((tmp_path/'out/final_request_errors').glob('*.json'))) == 1
    (run/'train_start_status.json').write_text('{"state":"done"}', encoding='utf-8')
    assert watch.completion(run, load_plan(TABLE, arm='B'), state)['state'] == 'final_request_error'


def test_main_loop_continues_after_invalid_final_request(tmp_path, monkeypatch):
    run = replay_run(tmp_path); final_request(run, 5750, stage='S2a')
    (run/'train_start_status.json').write_text('{"state":"done"}', encoding='utf-8')
    stable = watch._stable
    monkeypatch.setattr(watch, '_stable', lambda p, t, s: stable(p, 0, lambda _: None))
    class StopCPUProbe(Exception): pass
    def stop_after_later_score(_):
        path = tmp_path/'out/watch_state.json'
        data = watch.read(path)
        if len(data['done']) == 2: raise StopCPUProbe()
    monkeypatch.setattr(watch.time, 'sleep', stop_after_later_score)
    with pytest.raises(StopCPUProbe):
        watch.main(['--run-dir', str(run), '--out-root', str(tmp_path/'out'),
                    '--score-dir', str(tmp_path/'scores'), '--replay-root', str(SOURCE/'score-watch-b')])
    saved = watch.read(tmp_path/'out/watch_state.json')
    assert sorted(r['iteration'] for r in saved['done'].values()) == [5750, 6000]
    assert saved['final_request_errors']
    assert not (tmp_path/'out/watch_completion.json').exists()
