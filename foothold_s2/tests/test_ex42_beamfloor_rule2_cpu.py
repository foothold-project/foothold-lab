"""E2 beam floor and solved-cap redraw through the real command term and terrain reset path."""
from __future__ import annotations

import types

import numpy as np
import pytest
import torch

from foothold_s2.curriculum import ex41
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.terrains import ex42_exposure as exposure
from foothold_s2.terrains.ex42_column_reset import build_column_table
from foothold_s2.tests.test_ex42_flag_command_contract_cpu import PLAN, e1f_term
from foothold_s2.tests.test_ex42_low_floor_cpu import _installed_update

MESH = '/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_ABCDE_b613/terrain_mesh.npz'
N = 760


def _real_path(monkeypatch, *, floor='', rule2='', levels=5, existing_floor=True, stage_id='E1F'):
    monkeypatch.setenv('EX42_BEAM_LEVEL_FLOOR', floor)
    monkeypatch.setenv('EX42_RULE2_RANDOM_AT_CAP', rule2)
    command, runtime, _ = e1f_term(monkeypatch, {}, n=N, stage_id=stage_id)
    raw = command._env
    family = np.load(MESH, allow_pickle=False)['column_family'].tolist()
    table = build_column_table(family)
    assert len(table) == 76 and sum(r['family'] == 'A' and r['kind'] == 'balance_beams' for r in table) > 0
    raw._ex42_column_table = table
    types_ = torch.arange(N) % 76
    origins = torch.zeros(10, 76, 3)
    origins[:, :, 0] = torch.arange(10)[:, None]
    origins[:, :, 1] = torch.arange(76)[None, :]
    terrain = types.SimpleNamespace(
        terrain_origins=origins, terrain_levels=torch.zeros(N, dtype=torch.long),
        terrain_types=types_.clone(), env_origins=torch.zeros(N, 3), max_terrain_level=10,
        cfg=types.SimpleNamespace(terrain_generator=types.SimpleNamespace(size=(8.0, 8.0), num_rows=10, num_cols=76,
                                                                         curriculum=True, column_family=family)))
    terrain.update_env_origins = types.MethodType(_installed_update(), terrain)
    raw.scene.terrain = terrain
    runtime.command_allocation.attach(raw, command, runtime)
    plan = EX42Plan.load(PLAN)
    stage = next(r for r in plan.document['stages'] if r['id'] == 'E2')
    spec = exposure.low_level_floor(stage['terrain'], table, stage['id']) if existing_floor else None
    parent = {'terrain_types': types_, 'terrain_levels': torch.full((N,), levels, dtype=torch.long)}
    exposure.apply_exposure(terrain, [1.0] * 76, [5] * 76, generator=command.gen,
                            parent_env_state=parent, table=table, parent_same_mesh=True, low_floor=spec)
    raw._ex41_terrain = {'policy': 'performance', 'level_cap': 5}
    raw.command_manager = types.SimpleNamespace(get_term=lambda _: command)
    command.is_flag_env[:] = False
    command.max_dist[:] = 8.0
    command.cmd_sum_w[:] = torch.tensor([1.0, 0.0]) / raw.step_dt
    command.ep_steps[:] = 100
    return raw, terrain, command, table


def _beam(terrain, table):
    cols = torch.tensor([r['family'] == 'A' and r['kind'] == 'balance_beams' for r in table])
    return cols[terrain.terrain_types]


def test_beam_floor_raises_only_reset_beams_and_writes_receipt(monkeypatch, capsys):
    raw, terrain, _, table = _real_path(monkeypatch, floor='0.7')
    beam = _beam(terrain, table)
    # Force a known deficit after the initial placement; no other column may be reassigned by the beam gate.
    terrain.terrain_levels[beam] = 5
    ids = torch.nonzero(beam).flatten()
    terrain.env_origins[ids] = terrain.terrain_origins[5, terrain.terrain_types[ids]]
    before = terrain.terrain_levels.clone()
    ex41.ex41_terrain_levels(raw, ids)
    row = terrain.low_level_floor.receipt()['beam_level_floor']
    assert row['beam_envs'] == len(ids) and row['demoted'] > 0
    assert row['low_share_before'] < row['low_share_after']
    assert row['low_share_after'] >= 0.7 - 1 / len(ids)
    untouched = torch.ones(N, dtype=torch.bool)
    untouched[ids] = False
    assert torch.equal(terrain.terrain_levels[untouched], before[untouched])
    assert torch.equal(terrain.env_origins, terrain.terrain_origins[terrain.terrain_levels, terrain.terrain_types])
    assert f'EX42_BEAM_LEVEL_FLOOR where=start floor=0.7 max_level=2 columns={int(beam[:76].sum())}/76' in capsys.readouterr().out


def test_beam_floor_never_moves_a_beam_outside_the_reset_batch(monkeypatch):
    raw, terrain, _, table = _real_path(monkeypatch, floor='0.7')
    beam_ids = torch.nonzero(_beam(terrain, table)).flatten()
    terrain.terrain_levels[beam_ids] = 5
    terrain.env_origins[beam_ids] = terrain.terrain_origins[5, terrain.terrain_types[beam_ids]]
    reset = beam_ids[:10]
    ex41.ex41_terrain_levels(raw, reset)
    assert bool((terrain.terrain_levels[beam_ids[10:]] == 5).all())
    assert terrain.low_level_floor.receipt()['beam_level_floor']['low_share_after'] < 0.7


def test_rule2_redistributes_only_solved_cap_envs(monkeypatch, capsys):
    raw, terrain, command, table = _real_path(monkeypatch, rule2='1', existing_floor=False)
    assert command.stage_runtime is not None  # the real command term is attached to its real source runtime
    beam = _beam(terrain, table)
    ids = torch.arange(N)
    terrain.terrain_levels[ids[::2]] = 4
    terrain.env_origins[ids] = terrain.terrain_origins[terrain.terrain_levels, terrain.terrain_types]
    ex41.ex41_terrain_levels(raw, ids)
    result = terrain.terrain_levels
    assert bool((result[::2] == 5).all())
    assert bool(((result[1::2] >= 0) & (result[1::2] <= 5)).all())
    assert int((result[1::2] < 5).sum()) > 100
    assert set(result[1::2].tolist()) == set(range(6))
    row = raw._ex42_rule2_random_at_cap
    assert row['resent'] == N // 2 and sum(row['by_kind'].values()) == N // 2
    assert 'A/balance_beams' in row['by_kind'] and len(row['by_kind']) > 2
    assert torch.equal(terrain.env_origins, terrain.terrain_origins[result, terrain.terrain_types])
    lines = capsys.readouterr().out
    assert 'EX42_RULE2_RANDOM_AT_CAP where=start columns=76' in lines
    assert f'EX42_RULE2_RANDOM_AT_CAP resent={N // 2} by_kind=' in lines
    ex41.ex41_terrain_levels(raw, torch.arange(0, 200, 2))
    assert 'EX42_RULE2_RANDOM_AT_CAP resent=' not in capsys.readouterr().out
    ex41.ex41_terrain_levels(raw, torch.arange(200, 400, 2))
    assert 'EX42_RULE2_RANDOM_AT_CAP resent=580 by_kind=' in capsys.readouterr().out


def test_both_gates_share_the_real_reset_and_keep_origins_consistent(monkeypatch):
    raw, terrain, _, table = _real_path(monkeypatch, floor='0.7', rule2='1')
    terrain.terrain_levels[:] = 5
    terrain.env_origins[:] = terrain.terrain_origins[terrain.terrain_levels, terrain.terrain_types]
    ex41.ex41_terrain_levels(raw, torch.arange(N))
    beam = _beam(terrain, table)
    receipt = terrain.low_level_floor.receipt()['beam_level_floor']
    assert receipt['beam_envs'] == int(beam.sum()) and receipt['low_share_after'] >= 0.7
    assert raw._ex42_rule2_random_at_cap['resent'] == N
    terrain_receipt = ex41.terrain_distribution(raw)
    assert terrain_receipt['beam_level_floor'] == receipt
    assert terrain_receipt['rule2_random_at_cap']['resent'] == N
    assert torch.equal(terrain.env_origins, terrain.terrain_origins[terrain.terrain_levels, terrain.terrain_types])


def test_off_gate_keeps_levels_and_rng_state_byte_equal(monkeypatch):
    raw, terrain, command, _ = _real_path(monkeypatch)
    state = command.gen.get_state().clone()
    ex41.ex41_terrain_levels(raw, torch.arange(N))
    levels, origins, after = terrain.terrain_levels.clone(), terrain.env_origins.clone(), command.gen.get_state().clone()
    raw2, terrain2, command2, _ = _real_path(monkeypatch, floor='0', rule2='0')
    command2.gen.set_state(state)
    ex41.ex41_terrain_levels(raw2, torch.arange(N))
    assert torch.equal(levels, terrain2.terrain_levels) and torch.equal(origins, terrain2.env_origins)
    assert torch.equal(after, command2.gen.get_state())
    command._resample_command(torch.arange(N))
    command2._resample_command(torch.arange(N))
    assert torch.equal(command.vel_command_b, command2.vel_command_b)
    assert torch.equal(command.slot_current, command2.slot_current)
    assert torch.equal(command.gen.get_state(), command2.gen.get_state())
    assert 'beam_level_floor' not in terrain2.low_level_floor.receipt()
    assert not hasattr(raw2, '_ex42_rule2_random_at_cap')


@pytest.mark.parametrize('value', ['bad', 'nan', '-0.1', '1.1'])
def test_beam_fraction_refuses_invalid_values(monkeypatch, value):
    monkeypatch.setenv('EX42_BEAM_LEVEL_FLOOR', value)
    plan = EX42Plan.load(PLAN)
    row = next(r for r in plan.document['stages'] if r['id'] == 'E2')
    with pytest.raises(ValueError, match='EX42_BEAM_LEVEL_FLOOR'):
        exposure.low_level_floor(row['terrain'], [{'family': 'A', 'kind': 'balance_beams'}], row['id'])


def test_rule2_refuses_an_invalid_switch(monkeypatch):
    raw, _, _, _ = _real_path(monkeypatch)
    monkeypatch.setenv('EX42_RULE2_RANDOM_AT_CAP', 'maybe')
    with pytest.raises(ValueError, match='EX42_RULE2_RANDOM_AT_CAP'):
        ex41.ex41_terrain_levels(raw, torch.arange(N))


def test_e2_wide_commands_and_rule2_both_reach_the_real_term_and_reset(monkeypatch, capsys):
    from foothold_s2.commands import ex42_cmd_wide as wide
    from foothold_s2.curriculum.continuous import command_bad

    monkeypatch.setenv(wide.ENV_SWITCH, '1')
    monkeypatch.setenv(wide.SHARE_ENV, '0.5')
    raw, terrain, command, _ = _real_path(monkeypatch, rule2='1', existing_floor=False, stage_id='E2')
    command.reset(torch.arange(N))
    command.time_left[:] = 4.0
    command._resample_command(torch.arange(N))
    free = ~command.is_flag_env
    assert command.stage_runtime.stage_id == 'E2'
    assert wide.summary()['diag_above_old_max'] > 0
    assert wide.summary()['turned_forward'] > 0
    assert not bool(command_bad(command.command, command.slot_current, command.heading,
                                command.stage_runtime.env_stage, command.stage_runtime.plan,
                                ex42_stage_id='E2')[free].any())
    command.max_dist[:] = 8.0
    command.cmd_sum_w[:] = torch.tensor([1.0, 0.0]) / raw.step_dt
    command.ep_steps[:] = 100
    terrain.terrain_levels[:] = 5
    terrain.env_origins[:] = terrain.terrain_origins[terrain.terrain_levels, terrain.terrain_types]
    ex41.ex41_terrain_levels(raw, torch.arange(N))
    assert raw._ex42_rule2_random_at_cap['resent'] > 0
    lines = capsys.readouterr().out
    assert 'EX42_CMD_WIDE where=start stage=E2' in lines
    assert 'EX42_RULE2_RANDOM_AT_CAP resent=' in lines


def test_both_off_gates_keep_e2_commands_levels_and_rng_byte_equal(monkeypatch):
    from foothold_s2.commands import ex42_cmd_wide as wide

    monkeypatch.delenv(wide.ENV_SWITCH, raising=False)
    raw, terrain, command, _ = _real_path(monkeypatch, rule2='', existing_floor=False, stage_id='E2')
    command.reset(torch.arange(N))
    command._resample_command(torch.arange(N))
    command.max_dist[:] = 8.0
    command.cmd_sum_w[:] = torch.tensor([1.0, 0.0]) / raw.step_dt
    command.ep_steps[:] = 100
    terrain.terrain_levels[:] = 5
    ex41.ex41_terrain_levels(raw, torch.arange(N))
    cmd, slot, level, rng = (command.command.clone(), command.slot_current.clone(),
                             terrain.terrain_levels.clone(), command.gen.get_state().clone())
    monkeypatch.setenv(wide.ENV_SWITCH, '0')
    raw2, terrain2, command2, _ = _real_path(monkeypatch, rule2='0', existing_floor=False, stage_id='E2')
    command2.reset(torch.arange(N))
    command2._resample_command(torch.arange(N))
    command2.max_dist[:] = 8.0
    command2.cmd_sum_w[:] = torch.tensor([1.0, 0.0]) / raw2.step_dt
    command2.ep_steps[:] = 100
    terrain2.terrain_levels[:] = 5
    ex41.ex41_terrain_levels(raw2, torch.arange(N))
    assert torch.equal(command2.command, cmd) and torch.equal(command2.slot_current, slot)
    assert torch.equal(terrain2.terrain_levels, level) and torch.equal(command2.gen.get_state(), rng)
