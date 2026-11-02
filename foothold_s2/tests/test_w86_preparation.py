"""Known physical states for W86, no environment or policy execution."""
import math
import pytest
import torch

from foothold_s2.rewards import w86


def test_yaw_cost_excludes_nonzero_command_and_heading():
    got = w86.zero_yaw_l1(torch.tensor([.2, -.3, .4]), torch.tensor([0., .1, 0.]),
                          torch.tensor([False, False, True]))
    torch.testing.assert_close(got, torch.tensor([.2, 0., 0.]))


def test_target_follows_highest_ahead_surface_and_vertical_translation():
    below = torch.tensor([[0., 1.]])
    ahead = torch.tensor([[[0., .2], [1., 1.]]])
    target, valid = w86.swing_target(below, ahead)
    torch.testing.assert_close(target, torch.tensor([[.28, 1.08]]))
    assert valid.all()
    moved, _ = w86.swing_target(below+5, ahead+5)
    torch.testing.assert_close(moved, target+5)


def test_missing_ray_is_invalid_and_does_not_become_a_zero_height_ground():
    target, valid = w86.swing_target(torch.tensor([[0., 0.]]),
                                     torch.tensor([[[float('inf')], [float('nan')]]]))
    assert not valid.any()
    assert torch.isfinite(target).all()


def test_ahead_points_use_reverse_sideways_and_rotation_not_always_front():
    feet = torch.tensor([[[1., 0.]], [[1., 0.]], [[1., 0.]]])
    cmd = torch.tensor([[-1., 0., 0.], [0., 1., 0.], [0., 0., 1.]])
    points = w86.ahead_points_body(feet, cmd, torch.tensor([.1]))
    torch.testing.assert_close(points[:, 0, 0], torch.tensor([[.9, 0.], [1., .1], [1., .1]]))


def test_stationary_or_contact_foot_does_not_earn_swing_reward():
    z = torch.zeros(2, 4)
    reward = w86.swing_clearance_cost(z, z+.08, torch.zeros(2, 4, 2),
                             torch.ones(2, 4, dtype=torch.bool), torch.ones_like(z, dtype=torch.bool),
                             torch.tensor([True, False]))
    torch.testing.assert_close(reward, torch.zeros(2))


def test_one_foot_error_has_known_quadratic_cost():
    result = w86.swing_clearance_cost(torch.tensor([[.1]]), torch.tensor([[.2]]), torch.tensor([[[1., 0.]]]),
                             torch.tensor([[False]]), torch.tensor([[True]]), torch.tensor([True]))
    assert result.item() == pytest.approx(.01*math.tanh(2), abs=1e-6)


def test_stumble_is_force_ratio_not_fall_or_edge_truth():
    forces = torch.tensor([[[5., 0., 1.], [0., 0., 0.]], [[4., 0., 1.], [0., 0., 0.]]])
    torch.testing.assert_close(w86.stumble_cost(forces), torch.tensor([1., 0.]))


def test_limit_and_effort_margin_values():
    torch.testing.assert_close(w86.joint_limit_cost(torch.tensor([[0., 1.]]), torch.tensor([0., 0.]),
                                                   torch.tensor([1., 1.]), margin=.1), torch.tensor([.02]))
    torch.testing.assert_close(w86.effort_margin_cost(torch.tensor([[9., 10.]]), torch.tensor([10., 10.])),
                              torch.tensor([.01]), atol=1e-6, rtol=1e-6)


def test_zero_preregistered_terms_cannot_be_enabled_by_weight_update():
    with pytest.raises(ValueError, match='preregistered'):
        w86.propose_weights({'foot_slip': -.1}, reason='measured slip', evidence='metrics.json')


def test_performance_weight_change_requires_evidence_and_cannot_change_yaw():
    with pytest.raises(ValueError):
        w86.propose_weights({'swing': -.25}, reason='', evidence='')
    with pytest.raises(ValueError):
        w86.propose_weights({'zero_yaw': -.2}, reason='x', evidence='a.json')
    update = w86.propose_weights({'swing': -5., 'stumble': -2.5}, reason='registered boundary decision', evidence='score.json')
    assert update['weights']['swing'] == -5.
    assert update['execution_connected'] is False


def test_drag_denominator_is_moving_contact_frames_not_all_frames():
    # N=1, F=2: first foot contacts and slides, second is swinging.
    result = w86.foot_metrics(torch.tensor([[.01, .1]]), torch.zeros(1, 2),
                              torch.tensor([[[.2, 0.], [.2, 0.]]]), torch.tensor([[True, False]]),
                              torch.tensor([True]))
    assert result['contact_moving_frames'].tolist() == [[1, 0]]
    assert result['drag_frames'].tolist() == [[1, 0]]
    assert result['swing_frames'].tolist() == [[0, 1]]


def test_weight_proposal_preserves_other_previous_boundary_changes():
    first = w86.propose_weights({'stumble': -2.5}, reason='one', evidence='one.json')
    second = w86.propose_weights({'swing': -5.}, current_weights=first['weights'],
                                 reason='two', evidence='two.json')
    assert second['weights']['stumble'] == -2.5
    assert first['weights']['swing'] == -10.
    assert second['before'] == first['weights']


def test_preregistered_costs_have_known_values_even_while_weight_zero():
    forces = torch.tensor([[[.2, 0., 0.], [0., 0., .1]]])
    torch.testing.assert_close(w86.collision_cost(forces), torch.tensor([1.]))
    torch.testing.assert_close(w86.air_time_term(torch.tensor([[.7, .3]]),
                                               torch.tensor([[True, False]]), torch.tensor([True])),
                               torch.tensor([.2]))
    torch.testing.assert_close(w86.slip_cost(torch.tensor([[[3., 4.], [9., 0.]]]),
                                           torch.tensor([[True, False]])), torch.tensor([25.]))
    torch.testing.assert_close(w86.smoothness_cost(torch.tensor([[2., 3.]]),
                                                  torch.tensor([[1., 1.]]), torch.tensor([[0., 0.]])),
                               torch.tensor([1.]))
    torch.testing.assert_close(w86.energy_cost(torch.tensor([[2., -3.]]), torch.tensor([[4., 5.]])),
                               torch.tensor([23.]))


def test_preparation_yaml_matches_cost_weights_and_is_unwired():
    from pathlib import Path
    import yaml
    cfg = yaml.safe_load(Path(w86.__file__).with_name('w86-preparation.yaml').read_text(encoding='utf-8'))
    assert cfg['execution_connected'] is False
    assert {k: v['weight'] for k, v in cfg['preregistered'].items()} == {
        k: 0. for k in w86.PREREGISTERED}
    assert {k: v['weight'] for k, v in cfg['terms'].items()} == {
        k: w86.INITIAL_WEIGHTS[k] for k in ('zero_yaw', 'swing')}
    assert {k: v['weight'] for k, v in cfg['existing_terms'].items()} == w86.MAINTAINED_WEIGHTS
    assert set(cfg['preregistered']).isdisjoint(cfg['existing_terms'])
    assert 'sigma_m2' not in cfg['terms']['swing']
    assert cfg['terms']['swing']['includes_contact_feet'] is True


def test_no_bonus_for_hover_and_moving_false_with_airborne_feet():
    # moving drag, moving hover, stationary airborne: none gets positive reward.
    got = w86.swing_clearance_cost(torch.tensor([[0.], [.1], [0.]]), torch.full((3, 1), .08),
                            torch.tensor([[[1., 0.]], [[0., 0.]], [[1., 0.]]]),
                            torch.zeros(3, 1, dtype=torch.bool), torch.ones(3, 1, dtype=torch.bool),
                            torch.tensor([True, True, False]))
    assert got[0] > 0
    torch.testing.assert_close(got[1:], torch.zeros(2))


def test_contact_drag_penalty_is_worse_than_target_height_and_error_never_saturates():
    errors = torch.tensor([[.04], [.08], [.13], [0.]])
    got = w86.swing_clearance_cost(.08-errors, torch.full((4, 1), .08),
                                   torch.tensor([[[.5, 0.]]]*4), torch.ones(4, 1, dtype=torch.bool),
                                   torch.ones(4, 1, dtype=torch.bool), torch.ones(4, dtype=torch.bool))
    torch.testing.assert_close(got, errors[:, 0].square()*math.tanh(1))
    assert 0 < got[0] < got[1] < got[2]
    assert got[3] == 0
    assert w86.INITIAL_WEIGHTS['swing']*got[1] < w86.INITIAL_WEIGHTS['swing']*got[3]


def test_invalid_ray_skips_cost_even_for_contact_drag():
    got = w86.swing_clearance_cost(torch.zeros(1, 1), torch.ones(1, 1), torch.ones(1, 1, 2),
                                   torch.ones(1, 1, dtype=torch.bool), torch.zeros(1, 1, dtype=torch.bool),
                                   torch.ones(1, dtype=torch.bool))
    assert got.item() == 0


def test_inactive_nan_does_not_leak_and_active_nan_fails():
    nan = float('nan')
    torch.testing.assert_close(w86.zero_yaw_l1(torch.tensor([nan]), torch.tensor([.1]),
                                             torch.tensor([False])), torch.zeros(1))
    torch.testing.assert_close(w86.air_time_term(torch.tensor([[nan]]), torch.tensor([[False]]),
                                               torch.tensor([False])), torch.zeros(1))
    torch.testing.assert_close(w86.slip_cost(torch.tensor([[[nan, nan]]]), torch.tensor([[False]])), torch.zeros(1))
    with pytest.raises(ValueError):
        w86.zero_yaw_l1(torch.tensor([nan]), torch.tensor([0.]), torch.tensor([False]))
    with pytest.raises(ValueError):
        w86.effort_margin_cost(torch.tensor([[nan]]), torch.ones(1))
    with pytest.raises(ValueError):
        w86.joint_limit_cost(torch.zeros(1, 1), torch.zeros(1), torch.ones(1), margin=nan)


def test_force_floor_is_optional_diagnostic_and_default_preserves_existing_stumble():
    force = torch.tensor([[[.1, 0., 0.]], [[5., 0., 1.]]])
    torch.testing.assert_close(w86.stumble_cost(force), torch.ones(2))
    torch.testing.assert_close(w86.stumble_cost(force, min_force_n=1.), torch.tensor([0., 1.]))
