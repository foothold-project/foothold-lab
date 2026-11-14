"""EX-42 candidate: a share of E1 free envs gets 'stop 1~2 s -> slow forward 0.1~0.2 held 6 s'.
The real MixedVelocityCommand runs on a CPU double of Isaac's CommandTerm only; the stage view and runtime are the E1 ones."""
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
import torch

from foothold_s2.commands import mixed_core as mc
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.runners import command_rng
from foothold_s2.scripts import ex42_training_entry as entry

TABLE = Path(__file__).parents[1] / "curriculum/ex42-prep.yaml"
N, DT = 400, 0.02


class Base:
    """Isaac CommandTerm.reset / compute order: time_left is assigned before _resample_command."""
    def __init__(self, cfg, env):
        self.cfg, self._env = cfg, env
        self.num_envs, self.device = env.num_envs, env.device
        self.metrics = {}
        self.time_left = torch.full((self.num_envs,), 4.0)

    def _resample(self, ids):
        ids = torch.as_tensor(ids, dtype=torch.long)
        if len(ids):
            self.time_left[ids] = 4.0                        # Isaac draws the period, the term may overwrite it
            self._resample_command(ids)

    def reset(self, env_ids=None):
        self._resample(torch.arange(self.num_envs) if env_ids is None else env_ids)
        return {}

    def compute(self, dt):
        self.time_left -= dt
        self._resample((self.time_left <= 0).nonzero().flatten())
        self._update_command()


def build(monkeypatch, share, stage_id="E1"):
    managers = types.ModuleType("isaaclab.managers"); managers.CommandTerm = Base; managers.CommandTermCfg = object
    utils = types.ModuleType("isaaclab.utils"); utils.configclass = lambda c: c
    monkeypatch.setitem(sys.modules, "isaaclab.managers", managers)
    monkeypatch.setitem(sys.modules, "isaaclab.utils", utils)
    monkeypatch.setattr(mc, "STAND_START_SEQ_SHARE", share)
    spec = importlib.util.spec_from_file_location("_standseq_mixed", TABLE.parents[1] / "commands/mixed_command.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    plan = EX42Plan.load(TABLE)
    source, old = entry.load_ex42_stage_zero_source(plan)
    view = entry.make_ex42_stage_zero_plan_view(source, old, {"parent_sha256": "b" * 64}, ex42_plan=plan, stage_id=stage_id)
    robot = NS(data=NS(root_pos_w=torch.zeros(N, 3), heading_w=torch.zeros(N), root_lin_vel_b=torch.zeros(N, 3)))
    scene = type("Scene", (), {"__getitem__": lambda self, k: robot})()
    scene.terrain = NS(env_origins=torch.zeros(N, 3), terrain_types=torch.arange(N) % 2)
    raw = NS(num_envs=N, device="cpu", scene=scene, common_step_counter=0, step_dt=DT,
             _ex42_column_table=[{"family": "A", "kind": "pyramid_stairs"}, {"family": "A", "kind": "gaps"}])
    cfg = NS(asset_name="robot", params={"curriculum_mode": True}, seed=42, flag_stride=0, dynamic_flags=True,
             force_flag_provider=None, flag_provider=None, flag_count=4, fixed_cmd=None, clock_scatter=False, steps_per_iter=24)
    term = module.MixedVelocityCommand(cfg, raw)
    runtime = entry.EX42StageZeroRuntime(stage_zero_plan=view, plan_sha256="a" * 64, approval_sha256="b" * 64,
                                         parent_sha256="c" * 64, maximum_updates=max(entry._stage_caps(stage_id)), push_vmax_mps=2., stage_id=stage_id)
    runtime.attach_environment(raw, term)
    return term, robot, runtime


def run(term, steps, record=None):
    for i in range(steps):
        term.compute(DT)
        if record is not None:
            record(i)


def test_default_is_off_and_untouched(monkeypatch):
    assert mc.STAND_START_SEQ_SHARE == 0.0
    term, _, _ = build(monkeypatch, 0.0)
    assert not term.stand_seq.mask.any()
    term.reset()
    run(term, 500)
    assert term.take_stand_seq_stats() is None
    env_state = {}
    command_rng.save_command_rng(term, env_state)
    assert "stand_seq_state" not in env_state


def test_mask_is_even_and_exact():
    for share in (0.15, 0.25, 0.5):
        assert int(mc.stand_start_mask(1000, share).sum()) == int(1000 * share)
    assert not mc.stand_start_mask(1000, 0.0).any()
    with pytest.raises(ValueError):
        mc.stand_start_mask(10, 1.0)
    # Not the small-noise set: both pick by index, the sets must not coincide.
    from foothold_s2.runners.ex41_critic_mirror import small_noise_mask
    sn = small_noise_mask(1000, 0.25)
    ss = mc.stand_start_mask(1000, 0.25)
    assert int((sn & ss).sum()) < int(ss.sum())


def test_sequence_comes_out_through_the_real_e1_path(monkeypatch):
    term, robot, runtime = build(monkeypatch, 0.15)
    assert runtime.stage_id == "E1"
    term.reset()
    mask = term.stand_seq.mask
    chosen = mask.nonzero().flatten()
    others = (~mask).nonzero().flatten()
    log = []                                                   # per step: (stand, vx, spin, heading, slot) of the chosen envs
    def rec(i):
        log.append((term.stand[chosen].clone(), term.vel_command_b[chosen].clone(), term.spin[chosen].clone(),
                    term.heading[chosen].clone(), term.stand_seq.slow_active[chosen].clone()))
    rec(-1)
    run(term, int(40 / DT), rec)
    stand = torch.stack([l[0] for l in log]); cmd = torch.stack([l[1] for l in log])
    spin = torch.stack([l[2] for l in log]); heading = torch.stack([l[3] for l in log])
    slow = torch.stack([l[4] for l in log])                    # the sequence's own slow phase, not any ordinary 0.1~0.2 sample
    assert (cmd[..., 0][slow] >= 0.1 - 1e-6).all() and (cmd[..., 0][slow] <= 0.2 + 1e-6).all()
    assert (cmd[..., 1:][slow] == 0).all() and not stand[slow].any()
    assert not spin[slow].any() and not heading[slow].any()
    for e in range(len(chosen)):
        s, w = stand[:, e], slow[:, e]
        assert s[0], "an episode starts with the stop"
        first_slow = int(w.nonzero()[0])
        stop_len = first_slow * DT
        assert 1.0 - 1e-6 <= stop_len <= 2.0 + 0.1, stop_len
        run_len = 0
        k = first_slow
        while k < len(w) and w[k]:
            run_len += 1; k += 1
        assert abs(run_len * DT - 6.0) <= 0.1, run_len * DT           # literal: the order asks for 6 s
        vx = cmd[first_slow, e, 0]
        assert (cmd[first_slow:first_slow + run_len, e, 0] == vx).all()
    # the other envs are not forced into the order: they never start with a 1~2 s stop then exactly 6 s slow
    assert not bool(term.stand_seq.mask[others].any())
    stats = term.take_stand_seq_stats()
    assert stats["envs"] == len(chosen) and stats["slow_starts"] >= len(chosen) and stats["stop_starts"] >= len(chosen)
    assert term.take_stand_seq_stats()["slow_starts"] == 0


def test_tracking_is_recorded_only_two_to_six_seconds_after_slow_start(monkeypatch):
    term, robot, _ = build(monkeypatch, 0.15)
    term.reset()
    chosen = term.stand_seq.mask.nonzero().flatten()
    robot.data.root_lin_vel_b[:, 0] = 0.0
    run(term, int(5 / DT))
    term.take_stand_seq_stats()
    robot.data.root_lin_vel_b[chosen, 0] = 0.12              # walks at the commanded speed
    run(term, int(10 / DT))
    walking = term.take_stand_seq_stats()
    assert walking["tracked_steps_2_6s"] > 0 and walking["moving_fraction_2_6s"] > 0.99
    robot.data.root_lin_vel_b[:, 0] = 0.0                    # stays still
    run(term, int(10 / DT))
    still = term.take_stand_seq_stats()
    assert still["tracked_steps_2_6s"] > 0 and still["moving_fraction_2_6s"] < 0.01


def test_flag_envs_are_never_chosen_and_other_stages_are_untouched(monkeypatch):
    term, _, _ = build(monkeypatch, 0.15, stage_id="E1")
    term.is_flag_env[:] = False
    term.is_flag_env[::4] = True
    term.reset()
    ids = torch.arange(N)
    flag_ids = ids[term.is_flag_env]
    # flag envs resample through the flag machine, never through the sequence: their phase never leaves the start
    run(term, int(30 / DT))
    assert (term.stand_seq.phase[flag_ids] == 0).all()
    other, _, _ = build(monkeypatch, 0.15, stage_id="E0")
    other.reset(); run(other, 300)
    assert other.take_stand_seq_stats()["slow_starts"] == 0


def test_resume_gives_the_same_sequence(monkeypatch):
    a, _, _ = build(monkeypatch, 0.15)
    a.reset(); run(a, 400)
    state = {}
    command_rng.save_command_rng(a, state)
    gen_state = {k: (v.clone() if torch.is_tensor(v) else v) for k, v in a.stand_seq.state_dict().items()}
    b, _, _ = build(monkeypatch, 0.15)
    b.reset()
    command_rng.restore_command_rng(b, state)
    for k, v in gen_state.items():
        assert torch.equal(b.stand_seq.state_dict()[k], v), k
    assert torch.equal(a.stand_seq.mask, b.stand_seq.mask)


def test_reset_restarts_the_order_at_the_stop(monkeypatch):
    term, _, _ = build(monkeypatch, 0.15)
    term.reset()
    chosen = term.stand_seq.mask.nonzero().flatten()
    run(term, int(3.5 / DT))                                   # past stop (<= 2 s): every chosen env is in the slow or later phase
    assert term.stand_seq.phase[chosen].ne(1).any()
    term.reset(chosen)
    assert term.stand[chosen].all() and (term.vel_command_b[chosen] == 0).all()
    assert (term.stand_seq.phase[chosen] == 1).all() and not term.stand_seq.slow_active[chosen].any()


def test_tracking_window_is_two_to_six_seconds_exactly():
    seq = mc.StandStartSequence(10, 1, share=0.5)
    seq.slow_active[:] = True
    vel, cmd = torch.zeros(10), torch.full((10,), 0.1)
    for _ in range(int(1.9 / DT)):
        seq.step(vel, cmd, DT)
    assert seq.counts["tracked_steps"] == 0                    # first 1.9 s after the start: not recorded
    for _ in range(int(0.3 / DT)):
        seq.step(vel, cmd, DT)
    assert 0 < seq.counts["tracked_steps"] <= 10 * 10          # crossed 2 s
    seq.counts["tracked_steps"] = 0.0
    for _ in range(int(5 / DT)):
        seq.step(vel, cmd, DT)
    assert seq.counts["tracked_steps"] <= 10 * int(4.0 / DT) + 10   # nothing counted after 6 s
