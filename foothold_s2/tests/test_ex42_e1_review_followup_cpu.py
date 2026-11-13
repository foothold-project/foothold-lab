"""Reviewer survivors: real raw inputs, no provenance-validation doubles."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from foothold_s2 import ex42_e1_v2 as v
from foothold_s2.tests.test_ex42_e1_source_identity_cpu import synthetic_map
from foothold_s2.tests.test_ex42_e1_v2_cpu import PLAN, V24, _write_segment


def _yaw_source(folder):
    folder.mkdir(parents=True, exist_ok=True)
    case, mode = 'fwd1.0', 'eval_gt'
    raw = folder / f'axis_v2_{mode}_{case}.npz'
    np.savez_compressed(raw, yaw=np.zeros((300, 64)), alive=np.ones((300, 64), bool),
                        heading_pre=np.zeros((300, 64), bool),
                        cmd_post=np.zeros((300, 64, 3)), start_yaw=np.zeros(64))
    doc = dict(checkpoint_sha256='a'*64, eval_seed=42,
               run_identity=dict(checkpoint_sha256='a'*64, eval_seed=42),
               modes={mode: {case: dict(raw_file=str(raw), raw_sha256=v._sha(raw),
                   per_env=[dict(yaw_signed_accum_rad=0.) for _ in range(64)])}})
    return folder/'axis_v2.json', doc, raw


def test_raw_terrain_assignment_cannot_change_with_identical_motion(tmp_path):
    p, doc, arrays, name = synthetic_map(tmp_path)
    assert v._map_cell(p, doc, 'eval_gt', 'side+0.2')['R'] == pytest.approx(1.)
    arrays['assignment_sha256'] = np.array('c'*64)
    np.savez_compressed(tmp_path/name, **arrays)
    with pytest.raises(ValueError, match='terrain assignment identity'):
        v._map_cell(p, doc, 'eval_gt', 'side+0.2')


def test_yaw_other_case_filename_is_rejected_even_with_matching_sha(tmp_path):
    p, doc, raw = _yaw_source(tmp_path)
    assert v._yaw_cell(p, doc, 'eval_gt', 'fwd1.0')['median_abs_rad'] == 0.
    renamed = raw.with_name('axis_v2_eval_gt_fwd0.5.npz')
    raw.rename(renamed)
    doc['modes']['eval_gt']['fwd1.0']['raw_file'] = str(renamed)
    with pytest.raises(ValueError, match='yaw case identity'):
        v._yaw_cell(p, doc, 'eval_gt', 'fwd1.0')


def test_equal_rank_rewards_still_must_match_requested_rewards(tmp_path):
    _write_segment(tmp_path, 1)
    assert v.treatment(tmp_path/'model_500.pt', 500, PLAN)['state'] == 'complete'
    p = tmp_path/'segment_commands_b1.json'
    doc = json.loads(p.read_text())
    doc['rewards']['values']['zero_yaw'] -= .25
    p.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match='boundary identity'):
        v.treatment(tmp_path/'model_500.pt', 500, PLAN)


def _evaluation(folder):
    """Exact tracking for 6 s, all 64 alive; net yaw .06 rad, away from both limits."""
    identity = dict(checkpoint_sha256='a'*64, eval_seed=42)
    alive = np.ones((300, 64), bool)
    for level, cases in [(0, v.LOW_CASES), (5, v.LOW_CASES),
                         (None, ('side+0.5', 'side-0.5'))]:
        dest = folder/('map64' if level is None else f'e1_v2/L{level}')
        dest.mkdir(parents=True)
        doc = dict(checkpoint_sha256='a'*64, eval_seed=42, envs=64, steps=300,
                   run_identity=identity, command_suite='e1_v2', commands={}, env_arrays={},
                   fixed_terrain=dict(fixed_level=level, assignment_sha256='b'*64),
                   modes={mode: {} for mode in v.MODES})
        for case in cases:
            speed = float(case[3:] if case.startswith('fwd') else case[4:])
            forward = case.startswith('fwd')
            command = [speed, 0., 0.] if forward else [0., speed, 0.]
            doc['commands'][case] = command
            for mode in v.MODES:
                name = f'env_arrays_{mode}_{case}.npz'
                doc['env_arrays'][f'{mode}/{case}'] = name
                np.savez_compressed(dest/name, alive=alive, alive_steps=alive.sum(0),
                    alive_end=alive[-1], dt=np.array(.02),
                    vx=np.full((300, 64), speed if forward else 0.),
                    run_identity=np.array(json.dumps(identity)), assignment_sha256=np.array('b'*64))
                doc['modes'][mode][case] = dict(command=command, env_count=64, alive_envs_at_end=64,
                    per_env=[dict(env=i, samples_alive=300, command_xy_projection_integral_m=abs(speed)*6,
                                  vx_abs_error_mean_alive_mps=0., vy_abs_error_mean_alive_mps=0.)
                             for i in range(64)])
        (dest/'map_modes.json').write_text(json.dumps(doc))
    dest = folder/'axis_v2'
    dest.mkdir()
    doc = dict(checkpoint_sha256='a'*64, eval_seed=42, envs=64, steps=300,
               run_identity=identity, fixed_terrain=dict(fixed_level=2), modes={})
    for mode in v.MODES:
        doc['modes'][mode] = {}
        for case in v.YAW_CASES:
            raw = dest/f'axis_v2_{mode}_{case}.npz'
            np.savez_compressed(raw, yaw=np.repeat(np.linspace(.0002, .06, 300)[:, None], 64, axis=1), alive=alive,
                start_yaw=np.zeros(64), heading_pre=np.zeros((300, 64), bool),
                cmd_post=np.zeros((300, 64, 3)))
            doc['modes'][mode][case] = dict(raw_file=str(raw), raw_sha256=v._sha(raw),
                per_env=[dict(yaw_signed_accum_rad=.06) for _ in range(64)])
    (dest/'axis_v2.json').write_text(json.dumps(doc))


@pytest.fixture
def two_windows(tmp_path):
    from foothold_s2.tests.test_ex42_e1_judge_cpu import _inputs, _cells
    score, baseline, measured, plan = _inputs()
    next(row for row in plan['stages'] if row['id'] == 'E1').update(copy.deepcopy(V24['E1']))
    plan['evaluation']['e1_exit_v2'] = copy.deepcopy(PLAN['evaluation']['e1_exit_v2'])
    score.update(checkpoint_sha256='a'*64, execution_plan_sha256='a'*64,
                 d44_cells=_cells(plan, tmp_path), stage_id='E1')
    _write_segment(tmp_path, 1, plan)
    current, prior = tmp_path/'current', tmp_path/'prior'
    for p in (current, prior):
        _evaluation(p)
    score['e1_v2_evaluation'] = str(current)
    score['e1_v2_cells'] = v.measure_cells(current, 'a'*64, 42)
    previous = copy.deepcopy(score)
    previous['e1_v2_evaluation'] = str(prior)
    previous['e1_v2_cells'] = v.measure_cells(prior, 'a'*64, 42)
    previous['e1_exit_v2'] = dict(current=v.judge_cells(previous['e1_v2_cells'], plan))
    def judge():
        return v.judge_e1_v2(score, baseline, measured, plan, previous=previous,
            checkpoint=tmp_path/'model_500.pt', evaluation=current, seed=42)
    assert judge()['judgement'] == 'PASS'
    return score, previous, judge, current, prior, plan


def test_previous_cached_pass_requires_previous_raw_revalidation(two_windows):
    _, _, judge, _, prior, _ = two_windows
    p = prior/'e1_v2/L0/map_modes.json'
    doc = json.loads(p.read_text())
    doc['run_identity']['eval_seed'] = 999
    p.write_text(json.dumps(doc))
    got = judge()
    assert got['judgement'] == 'HOLD' and 'identity' in got['e1_exit_v2']['provenance_error']


def test_previous_pass_with_another_execution_plan_must_hold(two_windows):
    _, previous, judge, _, _, _ = two_windows
    previous['execution_plan_sha256'] = 'c'*64
    got = judge()
    assert got['judgement'] == 'HOLD' and 'previous execution plan' in got['reason']


def test_same_raw_through_directory_symlink_does_not_hold(two_windows, tmp_path):
    score, _, _, current, _, _ = two_windows
    alias = tmp_path/'alias'
    alias.symlink_to(current, target_is_directory=True)
    cached_before = copy.deepcopy(score)
    got = v._verified_cells(score, alias, 42)
    assert got['low']['L0']['eval_gt']['fwd0.1']['R'] == pytest.approx(1.)
    assert score == cached_before  # Normalization must not rewrite the stored receipt.


def test_different_file_with_same_bytes_is_not_a_path_alias(two_windows, tmp_path):
    import shutil
    score, _, _, current, _, _ = two_windows
    other = tmp_path/'other'
    shutil.copytree(current, other)
    with pytest.raises(ValueError, match='cached cells'):
        v._verified_cells(score, other, 42)


def test_alias_does_not_hide_changed_numbers(two_windows, tmp_path):
    score, _, _, current, _, _ = two_windows
    alias = tmp_path/'alias'
    alias.symlink_to(current, target_is_directory=True)
    score['e1_v2_cells']['low']['L0']['eval_gt']['fwd0.1']['R'] = .9
    with pytest.raises(ValueError, match='cached cells'):
        v._verified_cells(score, alias, 42)


def test_final_adapter_verification_accepts_same_files_through_alias(two_windows, tmp_path):
    from foothold_s2.ex42_stage_judges import ADAPTERS
    from foothold_s2.tests.test_ex42_e1_judge_cpu import _inputs
    score, _, _, current, _, plan = two_windows
    _, baseline, measured, _ = _inputs()
    checkpoint = tmp_path/'model_250.pt'
    scored = v.judge_e1_v2(score, baseline, measured, plan, previous=None,
                           checkpoint=checkpoint, evaluation=current, seed=42)
    scored['checkpoint'] = str(checkpoint)
    adapter = ADAPTERS['map39_e1_v2_two_window']
    adapter.verify(scored, scored['judgement'], scored['maintenance_judgement'], plan)
    alias = tmp_path/'alias'
    alias.symlink_to(current, target_is_directory=True)
    scored['e1_v2_evaluation'] = str(alias)
    got = adapter.verify(scored, scored['judgement'], scored['maintenance_judgement'], plan)
    assert got['e1_exit_v2']['judgement'] == 'HOLD'  # First window has no prior window.


def test_actual_m250_mount_alias_has_identical_cells():
    from foothold_s2.tests.test_ex42_e1_source_identity_cpu import RUN
    p = RUN/'eval/scores/m250/ex42_score.json'
    if not p.is_file():
        pytest.skip('read-only m250 source unavailable')
    score = json.loads(p.read_text())
    actual = v._verified_cells(score, RUN/'eval/scores/m250', 42)
    assert actual['low']['L0']['eval_gt']['fwd0.1']['R'] == pytest.approx(.44670258, abs=1e-8)
