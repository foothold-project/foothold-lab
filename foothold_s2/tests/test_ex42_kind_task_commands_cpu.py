"""E2 kind envs draw forward 1.0 or the flag only (CG E.3 kind_task row). Real plan row, real sampler code; the Isaac
command term is a stand-in holding the same fields. No Kit, no GPU."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
import torch

from foothold_s2.commands import ex42_shares as cs
from foothold_s2.commands import mixed_core as mc
from foothold_s2.curriculum import continuous
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_training_entry as entry

TABLE = Path(__file__).parents[1] / "curriculum/ex42-prep.yaml"
KIND = "A/stepping_stones_low"


def _plan(stage_id="E2"):
    plan = EX42Plan.load(TABLE)
    return plan, next(s for s in plan.document["stages"] if s["id"] == stage_id)


def setup(n=20000, stage_id="E2", mutate=None, seed=42):
    """20 % of the envs on the kind column ... 5 % in the plan; the table gives column 1 to every 20th env."""
    plan, stage = _plan(stage_id)
    if mutate:
        mutate(stage)
    contract = cs.read_contract(plan, stage_id)
    source, old = entry.load_ex42_stage_zero_source(plan)
    term = NS(gen=mc.make_generator(seed), is_flag_env=torch.zeros(n, dtype=torch.bool),
              slot_current=torch.full((n,), -1), cfg=NS(dynamic_flags=True, force_flag_provider=None))
    types = (torch.arange(n) % 20 == 0).long()                   # column 1 = stepping_stones_low
    raw = NS(num_envs=n, device="cpu", _ex42_column_table=[{"family": "A", "kind": "pyramid_stairs"},
                                                         {"family": "A", "kind": "stepping_stones_low"}],
             scene=NS(terrain=NS(terrain_types=types)))
    runtime = NS(plan=NS(stages=[old]), env_stage=torch.zeros(n, dtype=torch.long))
    controller = cs.CommandShares(contract, old)
    controller.attach(raw, term, runtime)
    return plan, contract, controller, term, raw, runtime


def _consume(t, r, raw):
    """Stand-in for the command term's resample: every non-flag env takes a slot drawn from its own stage."""
    for index in sorted(set(r.env_stage.tolist())):
        ids = torch.nonzero((r.env_stage == index) & ~t.is_flag_env).flatten()
        if len(ids):
            t.slot_current[ids] = mc.resample_stage(t.gen, len(ids), r.plan.stages[index], torch.zeros(len(ids)))["slot"]


def test_kind_envs_get_forward_one_or_the_flag_and_nothing_else():
    _, contract, c, t, raw, r = setup()
    assert contract["other_columns"] == "kind_task_command_set" and list(contract["kind_commands"]) == [KIND]
    ids = torch.arange(raw.num_envs)
    c.reset(ids)
    kind = raw.scene.terrain.terrain_types == 1
    free = ids[kind & ~t.is_flag_env]
    assert len(free) > 0 and bool(r.env_stage[free].eq(2).all())
    out = mc.resample_stage(t.gen, len(free), r.plan.stages[2], torch.zeros(len(free)))
    assert out["slot"].eq(mc.EX39_SLOTS.index("forward")).all()
    assert torch.equal(out["cmd"], torch.tensor([[1.0, 0.0, 0.0]]).expand(len(free), 3))     # no reverse, side, spin, stand
    assert not bool(out["heading"].any()) and not bool(out["stand"].any())
    # the consumed-command check of the run (continuous.command_bad) accepts them under their own stage
    bad = continuous.command_bad(out["cmd"], out["slot"], out["heading"], r.env_stage[free], NS(stages=r.plan.stages))
    assert not bool(bad.any())
    reverse = out["cmd"].clone()
    reverse[:, 0] = -0.5
    assert bool(continuous.command_bad(reverse, torch.full_like(out["slot"], 6), out["heading"], r.env_stage[free],
                                       NS(stages=r.plan.stages)).all())


def test_kind_flag_share_follows_the_plan_weight():
    _, contract, c, t, raw, r = setup(n=40000)
    c.reset(torch.arange(raw.num_envs))
    kind = raw.scene.terrain.terrain_types == 1
    assert contract["kind_commands"][KIND]["flag"] == 0.37
    assert float(t.is_flag_env[kind].float().mean()) == pytest.approx(0.37, abs=0.04)
    assert bool(r.env_stage[kind & t.is_flag_env].eq(0).all())       # a flag env is judged by the flag allocator


def test_continuous_env_commands_and_flags_keep_their_values():
    """Same seed, same env table: the continuous envs' flag draws and stages equal those of a contract without the bundle."""
    _, _, c1, t1, raw1, r1 = setup(n=4000)
    plan, stage = _plan()
    stage["terrain"].pop("kind_task")
    stage["terrain"]["exposure_at_E2"]["positive"] = [x for x in stage["terrain"]["exposure_at_E2"]["positive"] if "kind" not in x]
    contract = cs.read_contract(plan, "E2")
    assert "kind_commands" not in contract and contract["other_columns"] == "unchanged_source_stage"
    source, old = entry.load_ex42_stage_zero_source(plan)
    t0 = NS(gen=mc.make_generator(42), is_flag_env=torch.zeros(4000, dtype=torch.bool),
            slot_current=torch.full((4000,), -1), cfg=NS(dynamic_flags=True, force_flag_provider=None))
    r0 = NS(plan=NS(stages=[old]), env_stage=torch.zeros(4000, dtype=torch.long))
    c0 = cs.CommandShares(contract, old)
    c0.attach(raw1, t0, r0)
    ids = torch.arange(4000)
    c0.reset(ids)
    c1.reset(ids)
    cont = raw1.scene.terrain.terrain_types == 0
    assert torch.equal(t0.is_flag_env[cont], t1.is_flag_env[cont]) and torch.equal(r0.env_stage[cont], r1.env_stage[cont])


def _fails(mutate, match):
    plan, stage = _plan()
    mutate(stage)
    with pytest.raises(ValueError, match=match):
        cs.read_contract(plan, "E2")


def test_an_opened_kind_without_commands_or_with_a_bad_cell_is_refused_before_launch():
    cell = lambda s: s["terrain"]["kind_task"]["A"]["stepping_stones_low"]            # noqa: E731
    _fails(lambda s: s["terrain"].pop("kind_task"), "without kind_task")
    _fails(lambda s: cell(s).pop("command_weights"), "without kind_task")
    _fails(lambda s: cell(s).update(command_weights={"forward_1.0": 0.5, "flag": 0.4}), "sum to 1")
    _fails(lambda s: cell(s).update(command_weights={"forward_1.0": 1.2, "flag": -0.2}), "sum to 1")
    _fails(lambda s: cell(s).update(command_weights={"forward_1.0": 1.0}), "match command_set")
    _fails(lambda s: cell(s).update(command_set=["forward_1.0", "flag", "reverse"],
                                    command_weights={"forward_1.0": 0.5, "flag": 0.3, "reverse": 0.2}), "only forward_1.0, flag")
    _fails(lambda s: cell(s).update(command_set=["flag"], command_weights={"flag": 1.0}), "forward_1.0")
    _fails(lambda s: s["terrain"]["kind_task"]["A"].update(gaps=dict(cell(s))), "does not open")
    _fails(lambda s: s["terrain"]["exposure_at_E2"]["positive"].append({"family": "A", "kinds_of": "evaluation", "exposure": 0.1, "level_cap": 0}), "other than continuous")


def test_a_bundle_without_a_mesh_column_is_refused_at_attach():
    plan, _ = _plan()
    contract = cs.read_contract(plan, "E2")
    source, old = entry.load_ex42_stage_zero_source(plan)
    c = cs.CommandShares(contract, old)
    raw = NS(num_envs=8, device="cpu", _ex42_column_table=[{"family": "A", "kind": "pyramid_stairs"}],
             scene=NS(terrain=NS(terrain_types=torch.zeros(8, dtype=torch.long))))
    term = NS(gen=mc.make_generator(1), is_flag_env=torch.zeros(8, dtype=torch.bool), slot_current=torch.full((8,), -1),
              cfg=NS(dynamic_flags=True, force_flag_provider=None))
    with pytest.raises(ValueError, match="without a mesh column"):
        c.attach(raw, term, NS(plan=NS(stages=[old]), env_stage=torch.zeros(8, dtype=torch.long)))


def test_two_resets_and_hundreds_of_steps_never_leave_the_kind_command_domain():
    _, _, c, t, raw, r = setup(n=6000, seed=5)
    ids = torch.arange(raw.num_envs)
    kind = raw.scene.terrain.terrain_types == 1
    for _ in range(2):                                              # two starts, as the launch smoke does
        c.reset(ids)
        _consume(t, r, raw)
        for step in range(300):
            free = ids[kind & ~t.is_flag_env]
            if step % 50 == 0:                                      # a resample period
                out = mc.resample_stage(t.gen, len(free), r.plan.stages[2], torch.zeros(len(free)))
                t.slot_current[free] = out["slot"]
                cmd = out["cmd"]
                bad = continuous.command_bad(cmd, out["slot"], out["heading"], r.env_stage[free], NS(stages=r.plan.stages))
                assert not bool(bad.any())
            c.pre_step()
    assert bool(t.is_flag_env[kind].any()) and bool((~t.is_flag_env[kind]).any())


def test_the_record_counts_the_kind_bundle_on_its_own_denominator(tmp_path):
    _, _, c, t, raw, r = setup(n=2000)
    ids = torch.arange(raw.num_envs)
    c.reset(ids)
    _consume(t, r, raw)
    kind = raw.scene.terrain.terrain_types == 1
    c.pre_step()
    ckpt = tmp_path / "model_250.pt"
    ckpt.write_bytes(b"x")
    c.write(tmp_path, 250, ckpt, plan_sha="a" * 64, stage_id="E2")
    doc = json.loads((tmp_path / "command_shares_250_rank0.json").read_text())
    steps = doc["cumulative"]["steps"]
    assert steps["all"]["total"] == 2000 and steps[f"kind:{KIND}"]["total"] == int(kind.sum())
    assert steps[f"kind:{KIND}"]["counts"]["forward"] + steps[f"kind:{KIND}"]["counts"]["flag"] == int(kind.sum())
    assert doc["cumulative"]["reset_modes"][f"kind:{KIND}"]["total"] == int(kind.sum())
    assert doc["configured"]["kind_commands"][KIND]["flag"] == 0.37


def test_a_column_cannot_be_both_continuous_and_a_kind_bundle():
    plan, _ = _plan()
    contract = cs.read_contract(plan, "E2")
    contract["kind_commands"]["A/pyramid_stairs"] = {"family": "A", "kind": "pyramid_stairs", "flag": 0.1}
    source, old = entry.load_ex42_stage_zero_source(plan)
    c = cs.CommandShares(contract, old)
    raw = NS(num_envs=8, device="cpu", _ex42_column_table=[{"family": "A", "kind": "pyramid_stairs"},
                                                         {"family": "A", "kind": "stepping_stones_low"}],
             scene=NS(terrain=NS(terrain_types=torch.zeros(8, dtype=torch.long))))
    term = NS(gen=mc.make_generator(1), is_flag_env=torch.zeros(8, dtype=torch.bool), slot_current=torch.full((8,), -1),
              cfg=NS(dynamic_flags=True, force_flag_provider=None))
    with pytest.raises(ValueError, match="both continuous and a kind bundle"):
        c.attach(raw, term, NS(plan=NS(stages=[old]), env_stage=torch.zeros(8, dtype=torch.long)))
