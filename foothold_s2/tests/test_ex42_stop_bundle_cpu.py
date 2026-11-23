"""EX42_STOP_BUNDLE (lead 2026-11-23): stop-slot stagger / lateral / load penalties and the four-foot delay.

The command term is the real MixedVelocityCommand with the real E1F / E2 plan rows and stage runtime (e1f_term, only Isaac's CommandTerm
base is a double); the stand mask and stop_elapsed_s come from its own _resample_command and _update_command. Robot and contact sensor
data are fake tensors. CPU only.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.rewards import ex42_stop_bundle as sb
from foothold_s2.rewards.basic_gait_bundle import four_foot_contact_at_stop
from foothold_s2.tests.test_ex42_flag_command_contract_cpu import e1f_term

N = 2048
JOINTS = [f"{leg}_{j}_joint" for leg in ("FL", "FR", "RL", "RR") for j in ("hip", "thigh", "calf")]
DEFAULT_Q = [0.1, 0.8, -1.5, -0.1, 0.8, -1.5, 0.1, 1.0, -1.5, -0.1, 1.0, -1.5]       # Isaac Lab UNITREE_GO2_CFG
ROBOT = SimpleNamespace(name="robot", body_ids=[0, 1, 2, 3])
SENSOR = SimpleNamespace(name="contact_forces", body_ids=[0, 1, 2, 3])


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    sb._COUNTS.clear()
    sb._SUMS.clear()
    sb._STARTED["done"] = False
    monkeypatch.delenv(sb.ENV_SWITCH, raising=False)
    monkeypatch.delenv(sb.PARAMS_ENV, raising=False)


def _env(monkeypatch, stage_id="E1F"):
    command, runtime, data = e1f_term(monkeypatch, {}, n=N, stage_id=stage_id)
    raw = command._env
    raw._ex42_column_table = [raw._ex42_column_table[0], {"family": "A", "kind": "balance_beams"}]
    runtime.command_allocation.column_continuous = torch.tensor([True, False])
    raw.scene.terrain.terrain_types = (torch.arange(N) % 2).long()        # col 0 continuous · col 1 A balance_beams (sparse)
    raw.command_manager = SimpleNamespace(get_command=lambda _: command.command, get_term=lambda _: command)
    raw.scene.robot.joint_names = list(JOINTS)
    data.default_joint_pos = torch.tensor(DEFAULT_Q).repeat(N, 1)
    ref = sb.reference_y(JOINTS, data.default_joint_pos)
    pos = torch.zeros(N, 4, 3)
    pos[:, :, 0] = torch.tensor([0.19, 0.19, -0.19, -0.19])
    pos[:, :, 1] = ref
    data.body_pos_w = pos
    data.applied_torque = torch.zeros(N, 12)
    force = torch.zeros(N, 4, 3)
    force[:, :, 2] = 30.0
    raw.scene.sensors = {"contact_forces": SimpleNamespace(data=SimpleNamespace(net_forces_w=force))}
    return command, raw, data


def _draw(command, seed=7):
    command.time_left[:] = 4.0
    command.gen.manual_seed(seed)
    command._resample_command(torch.arange(N))


def test_reference_y_known_answer():
    ref = sb.reference_y(JOINTS, torch.tensor([DEFAULT_Q]))[0]
    assert ref[0] == pytest.approx(0.17260, abs=2e-5) and ref[1] == pytest.approx(-0.17260, abs=2e-5)
    assert ref[2] == pytest.approx(0.17167, abs=2e-5) and ref[3] == pytest.approx(-0.17167, abs=2e-5)
    zero = sb.reference_y(JOINTS, torch.zeros(1, 12))[0]                 # hip 0: hip + thigh offsets only
    assert torch.allclose(zero, torch.tensor([0.142, -0.142, 0.142, -0.142]))


def test_on_penalties_only_on_stop_envs_of_non_sparse_columns(monkeypatch):
    monkeypatch.setenv(sb.ENV_SWITCH, "1")
    command, raw, data = _env(monkeypatch)
    _draw(command)
    data.body_pos_w[:, 0, 0] += 0.05                                       # FL 5 cm ahead of FR: stagger 0.05 m
    data.body_pos_w[:, :, 1] += torch.tensor([0.01, -0.01, 0.01, -0.01])  # every foot 1 cm outward: lateral 0.04 m
    raw.scene.sensors["contact_forces"].data.net_forces_w[:, :, 2] = torch.tensor([10.0, 20.0, 30.0, 40.0])
    stagger = sb.ex42_stop_stagger(raw, "base_velocity", ROBOT)
    lateral = sb.ex42_stop_lateral(raw, "base_velocity", ROBOT)
    load = sb.ex42_stop_load(raw, "base_velocity", SENSOR)
    cols = raw.scene.terrain.terrain_types
    stand = command.stand
    slot = command.slot_current
    names = command.slot_names
    spin = (slot == names.index("spin_left")) | (slot == names.index("spin_right"))
    want = stand & (cols == 0)
    assert int(want.sum()) > 50 and int((stand & (cols == 1)).sum()) > 50 and int((spin & (cols == 0)).sum()) > 50
    assert bool((command.command[stand] == 0).all())
    for value, expected in ((stagger, 0.05), (lateral, 0.04), (load, 0.6)):
        assert torch.allclose(value[want], torch.full_like(value[want], expected), atol=1e-6)   # known answers
        assert bool((value[~want] == 0).all())                             # walking, spinning, flag and sparse-column envs: exactly 0
    s = sb.summary()
    assert s["stop_steps"] == s["stagger_nonzero"] == s["lateral_nonzero"] == s["load_nonzero"] == int(want.sum())
    assert s["env_steps"] == N
    json.dumps(s, allow_nan=False)


def test_no_deviation_gives_zero_on_stop_envs(monkeypatch):
    monkeypatch.setenv(sb.ENV_SWITCH, "1")
    command, raw, _ = _env(monkeypatch)
    _draw(command)
    assert bool((sb.ex42_stop_stagger(raw, "base_velocity", ROBOT) == 0).all())
    assert float(sb.ex42_stop_lateral(raw, "base_velocity", ROBOT).abs().max()) < 1e-6
    assert bool((sb.ex42_stop_load(raw, "base_velocity", SENSOR) == 0).all())


def test_yaw_frame(monkeypatch):
    monkeypatch.setenv(sb.ENV_SWITCH, "1")
    command, raw, data = _env(monkeypatch)
    _draw(command)
    data.body_pos_w[:, 0, 0] += 0.05
    before = sb.ex42_stop_stagger(raw, "base_velocity", ROBOT).clone()
    yaw = torch.full((N,), 1.1)
    c, s = torch.cos(yaw)[:, None], torch.sin(yaw)[:, None]
    x, y = data.body_pos_w[..., 0].clone(), data.body_pos_w[..., 1].clone()
    data.body_pos_w[..., 0], data.body_pos_w[..., 1] = c * x - s * y + 3.0, s * x + c * y - 2.0
    data.root_pos_w[:, 0], data.root_pos_w[:, 1] = 3.0, -2.0
    data.heading_w = yaw
    assert torch.allclose(sb.ex42_stop_stagger(raw, "base_velocity", ROBOT), before, atol=1e-6)


def test_four_foot_pays_only_after_the_delay(monkeypatch):
    monkeypatch.setenv(sb.ENV_SWITCH, "1")
    command, raw, _ = _env(monkeypatch)
    command.reset(torch.arange(N))                                          # episode start: stop_elapsed_s = 0
    stop = command.stand.clone()
    assert int(stop.sum()) > 50
    delayed = sb.wrap_four_foot(four_foot_contact_at_stop, 1.0)
    paid_at = None
    for k in range(1, 61):                                                  # the k-th reward step under stand sees k x dt
        command._update_command()
        old = four_foot_contact_at_stop(raw, "base_velocity", SENSOR)
        new = delayed(raw, "base_velocity", sensor_cfg=SENSOR)
        assert bool((old[stop] == 1).all()) and bool((old[~stop] == 0).all())
        if k < 50:
            assert bool((new == 0).all()), k
        else:
            assert bool((new[stop] == 1).all()) and bool((new[~stop] == 0).all()), k
            paid_at = paid_at or k
    assert paid_at == 50
    s = sb.summary()
    assert s["ff_withheld"] == 49 * int(stop.sum()) and s["ff_paid"] == 11 * int(stop.sum())


def test_off_registers_nothing_and_commands_are_bit_identical(monkeypatch):
    cfg = SimpleNamespace(rewards=SimpleNamespace(ex39_four_foot_stop=SimpleNamespace(func=four_foot_contact_at_stop, weight=0.1)))
    before = dict(vars(cfg.rewards))
    assert sb.register(cfg) is False and vars(cfg.rewards) == before
    assert cfg.rewards.ex39_four_foot_stop.func is four_foot_contact_at_stop and sb.summary() is None
    off, raw_off, _ = _env(monkeypatch)
    state = off.gen.get_state().clone()
    _draw(off)
    cmd_off, slot_off, gen_off = off.command.clone(), off.slot_current.clone(), off.gen.get_state().clone()
    ff_off = four_foot_contact_at_stop(raw_off, "base_velocity", SENSOR)
    monkeypatch.setenv(sb.ENV_SWITCH, "1")
    on, raw_on, _ = _env(monkeypatch)
    on.gen.set_state(state)
    _draw(on)
    sb.ex42_stop_stagger(raw_on, "base_velocity", ROBOT)
    assert torch.equal(on.command, cmd_off) and torch.equal(on.slot_current, slot_off) and torch.equal(on.gen.get_state(), gen_off)
    assert torch.equal(four_foot_contact_at_stop(raw_on, "base_velocity", SENSOR), ff_off)


def test_register_on(monkeypatch, capsys):
    monkeypatch.setenv(sb.ENV_SWITCH, "1")
    monkeypatch.setenv(sb.PARAMS_ENV, "stagger=-0.5,ff_delay=0.8")
    term = lambda **kw: SimpleNamespace(**kw)                               # noqa: E731
    entity = lambda name, **kw: SimpleNamespace(name=name, **kw)            # noqa: E731
    cfg = SimpleNamespace(rewards=SimpleNamespace(ex39_four_foot_stop=SimpleNamespace(func=four_foot_contact_at_stop, weight=0.1)))
    assert sb.register(cfg, term, entity) is True
    r = cfg.rewards
    assert (r.ex42_stop_stagger.weight, r.ex42_stop_lateral.weight, r.ex42_stop_load.weight) == (-0.5, -0.3, -0.05)
    assert r.ex42_stop_stagger.params["asset_cfg"].body_names == list(sb.FEET) and r.ex42_stop_load.params["sensor_cfg"].preserve_order
    assert r.ex39_four_foot_stop.func.ex42_stop_bundle_delay == 0.8 and r.ex39_four_foot_stop.weight == 0.1
    assert sb.register(cfg, term, entity) is False                          # once only
    assert "EX42_STOP_BUNDLE where=start stagger=-0.5 lateral=-0.3 load=-0.05 ff_delay_s=0.8" in capsys.readouterr().out


@pytest.mark.parametrize("switch, params", [("yes", ""), ("", "stagger=-1"), ("1", "stagger=0.1"), ("1", "foo=1"),
                                            ("1", "ff_delay=-1"), ("1", "load=x")])
def test_bad_values_refuse(monkeypatch, switch, params):
    monkeypatch.setenv(sb.ENV_SWITCH, switch)
    monkeypatch.setenv(sb.PARAMS_ENV, params)
    with pytest.raises(ValueError):
        sb.enabled() and sb.params()


def test_weight_table_numbers():
    t = sb.weight_table()
    assert t["four_foot_lost_by_restep"] == pytest.approx(0.03) and t["steps"] == 200
    st = t["rows"]["stagger"]
    assert st["threshold_abs_weight"] == pytest.approx(0.15) and st["per_step_at_threshold"] == pytest.approx(1.5e-4)
    assert st["per_step_at_weight"] == pytest.approx(3.0e-4) and st["window_total_at_weight"] == pytest.approx(0.06)
    assert t["rows"]["load"]["threshold_abs_weight"] == pytest.approx(0.025)
    assert all(row["beats_restep"] for row in t["rows"].values())          # the defaults beat a re-step at the table's deviations


def test_shares_record_carries_the_counts(monkeypatch, tmp_path):
    from foothold_s2.commands.ex42_shares import CommandShares
    monkeypatch.setenv(sb.ENV_SWITCH, "1")
    command, raw, _ = _env(monkeypatch)
    _draw(command)
    sb.ex42_stop_stagger(raw, "base_velocity", ROBOT)
    alloc = command.stage_runtime.command_allocation
    assert isinstance(alloc, CommandShares)
    alloc.write(tmp_path, 50, None, plan_sha="x" * 64, stage_id="E1F")
    doc = json.loads(next(tmp_path.glob("command_shares_50_rank*.json")).read_text())
    assert doc["stop_bundle"]["env_steps"] == N and doc["stop_bundle"]["stop_steps"] > 0


def test_walk_to_stand_transitions_per_20s_episode_on_e2(monkeypatch):
    """Planner: stand share 0.1111 of free draws, a draw every 4 s -> 4 resamples after the episode-start draw,
    walk -> stand = 4 x p x (1 - p) = 0.395 per free env per 20 s. Measured through the real E2 row."""
    n = 8192
    command, _, _ = e1f_term(monkeypatch, {}, n=n, stage_id="E2")
    command.gen.manual_seed(11)
    ids = torch.arange(n)
    command.reset(ids)
    trans = torch.zeros(n)
    for _ in range(4):
        was = command.stand.clone()
        command._resample_command(ids)
        trans += (~was & command.stand).float()
    free = ~command.is_flag_env
    p = float(command.stand[free].float().mean())
    assert 0.10 < p < 0.12
    assert 0.36 < float(trans[free].mean()) < 0.42 and 0.31 < float(trans.mean()) < 0.38


def test_known_answer_penalties_in_reward_units(monkeypatch):
    """Lead 13:11 (1): stagger 0 -> 0 · stagger 0.05 m -> weight x 0.05 x dt = -0.3 x 0.05 x 0.02 = -3.0e-4 per step (the
    weight table's per-step value) · outside the stop slot -> 0 · sparse column -> 0."""
    monkeypatch.setenv(sb.ENV_SWITCH, "1")
    command, raw, data = _env(monkeypatch)
    _draw(command)
    cols, stand = raw.scene.terrain.terrain_types, command.stand
    w, dt = sb.DEFAULTS["stagger"], raw.step_dt
    assert bool((sb.ex42_stop_stagger(raw, "base_velocity", ROBOT) * w * dt == 0).all())          # stagger 0 -> 0
    data.body_pos_w[:, 2, 0] -= 0.05                                                                # RL 5 cm behind RR
    reward = sb.ex42_stop_stagger(raw, "base_velocity", ROBOT) * w * dt
    expected = sb.weight_table()["rows"]["stagger"]["per_step_at_weight"]
    assert expected == pytest.approx(3.0e-4)
    assert torch.allclose(reward[stand & (cols == 0)], torch.full((int((stand & (cols == 0)).sum()),), -expected), atol=1e-9)
    assert bool((reward[~stand] == 0).all())                                                        # outside the stop slot
    assert bool((reward[stand & (cols == 1)] == 0).all())                                           # sparse column


def test_front_hip_torque_record(monkeypatch):
    """Lead 13:11 (3): record only, mean (|tau_FL_hip| + |tau_FR_hip|) / 2 over active stop env-steps."""
    monkeypatch.setenv(sb.ENV_SWITCH, "1")
    command, raw, data = _env(monkeypatch)
    _draw(command)
    data.applied_torque[:, JOINTS.index("FL_hip_joint")] = -3.0
    data.applied_torque[:, JOINTS.index("FR_hip_joint")] = 5.0
    data.applied_torque[:, JOINTS.index("RL_hip_joint")] = 100.0                                   # not counted
    active = command.stand & (raw.scene.terrain.terrain_types == 0)
    data.applied_torque[~active, JOINTS.index("FL_hip_joint")] = 50.0                               # not in the stop slot: not counted
    sb.ex42_stop_stagger(raw, "base_velocity", ROBOT)
    sb.ex42_stop_stagger(raw, "base_velocity", ROBOT)
    s = sb.summary()
    assert s["stop_steps"] == 2 * int(active.sum()) and s["front_hip_abs_torque_mean_nm"] == pytest.approx(4.0)
