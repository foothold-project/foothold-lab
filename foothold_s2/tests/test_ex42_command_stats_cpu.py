"""EX-42 sampled-command record (train_extra `ex42_command_samples`): what the sampler actually drew in one update,
per slot, with the turn-overlay fraction and the count of samples the stage's own check refuses."""
from __future__ import annotations

import json
import types
from dataclasses import replace
from pathlib import Path

import pytest
import torch

from foothold_s2.commands import mixed_core as mc
from foothold_s2.commands.ex42_command_stats import MOVING, CommandStats
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_training_entry as te

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "foothold_s2" / "curriculum" / "ex42-prep.yaml"
SLOT = {name: i for i, name in enumerate(mc.EX39_SLOTS)}
N = 120_000


@pytest.fixture(scope="module")
def stage():
    plan = EX42Plan.load(PLAN)
    source = te.load_ex42_stage_zero_source(plan)
    return te.make_ex42_stage_zero_plan_view(source[0], source[1], {"parent_sha256": "0" * 64}, ex42_plan=plan,
                                             stage_id="E1").stages[0]


def draw(stage, n=N, seed=11):
    return mc.resample_stage(mc.make_generator(seed), n, stage, torch.zeros(n))


def one(slot, vx=0.0, vy=0.0, wz=0.0):
    return torch.tensor([[vx, vy, wz]]), torch.tensor([SLOT[slot]]), torch.zeros(1, dtype=torch.bool)


def test_the_record_shows_the_e1_profile_the_sampler_drew(stage):
    stats, out = CommandStats(stage), draw(stage)
    for part in range(4):                               # the term hands the samples over in groups, step by step
        rows = slice(part * N // 4, (part + 1) * N // 4)
        stats.add(out["cmd"][rows], out["slot"][rows], out["heading"][rows])
    row = stats.take()
    assert json.loads(json.dumps(row)) == row and row["samples"] == N and row["out_of_range"] == 0
    assert set(row["slots"]) == set(mc.EX39_SLOTS) and sum(v["n"] for v in row["slots"].values()) == N
    share = {name: cell["share"] for name, cell in row["slots"].items()}
    assert abs(share["forward"] - 0.19) < 0.005 and abs(share["side_left"] - 0.09) < 0.004 and abs(share["side_right"] - 0.09) < 0.004
    for name in ("side_left", "side_right"):
        low, high = row["slots"][name]["vy_abs"]
        assert 0.1 <= low < 0.12 and 0.78 < high <= 0.8             # stage zero stopped at 0.2 .. 0.6
    assert 0.3 <= row["slots"]["walk_left"]["vx"][0] and 1.18 < row["slots"]["walk_left"]["vx"][1] <= 1.2
    assert 0.15 <= row["slots"]["spin_left"]["wz_abs"][0] < 0.17
    overlay = row["turn_overlay"]
    assert overlay["moving"] == sum(row["slots"][name]["n"] for name in MOVING)
    assert abs(overlay["fraction"] - 0.25) < 0.01 and overlay["turned"] == round(overlay["fraction"] * overlay["moving"])
    assert max(row["slots"][name]["wz_abs"][1] for name in MOVING) <= 0.6 + 1e-6
    assert row["slots"]["forward"]["vy_abs"] == [0.0, 0.0]


def test_take_starts_the_next_update_from_nothing(stage):
    stats, out = CommandStats(stage), draw(stage, n=4000)
    assert stats.take() is None
    stats.add(out["cmd"], out["slot"], out["heading"])
    assert stats.take()["samples"] == 4000 and stats.take() is None
    stats.add(*one("side_left", vy=0.5))
    row = stats.take()
    assert row["samples"] == 1 and list(row["slots"]) == ["side_left"] and row["slots"]["side_left"]["vy_abs"] == [0.5, 0.5]
    stats.add(out["cmd"][:0], out["slot"][:0], out["heading"][:0])            # an empty group changes nothing
    assert stats.take() is None


@pytest.mark.parametrize("sample", [
    ("side_left", dict(vy=0.95)),                  # above the E1 side speed
    ("side_right", dict(vy=-0.05)),                # below the slow floor
    ("reverse", dict(vx=-0.5, wz=0.7)),            # an overlay turn above 0.6
    ("walk_left", dict(vx=1.4, wz=0.5)),
    ("forward", dict(vx=0.5, vy=0.2)),
])
def test_a_sample_outside_the_stage_profile_is_counted(stage, sample):
    stats = CommandStats(stage)
    stats.add(*one("side_left", vy=0.5))
    stats.add(*one(sample[0], **sample[1]))
    row = stats.take()
    assert row["samples"] == 2 and row["out_of_range"] == 1


def test_the_count_follows_the_profile_of_the_segment(stage):
    wider = replace(stage, ranges={**stage.ranges, "side_vy_abs": (0.1, 1.0)})      # a segment adjustment inside the limits
    for used, bad in ((stage, 1), (wider, 0)):
        stats = CommandStats(used)
        stats.add(*one("side_left", vy=0.95))
        assert stats.take()["out_of_range"] == bad


def test_overlay_fraction_counts_only_reverse_side_and_diagonal_turns(stage):
    stats = CommandStats(stage)
    stats.add(*one("reverse", vx=-0.5, wz=0.4))
    stats.add(*one("side_left", vy=0.5))
    stats.add(*one("spin_left", wz=1.0))            # a spin is not an overlay
    stats.add(*one("walk_left", vx=0.5, wz=0.5))
    assert stats.take()["turn_overlay"] == {"moving": 2, "turned": 1, "fraction": 0.5}
    stats.add(*one("spin_left", wz=1.0))
    assert stats.take()["turn_overlay"] == {"moving": 0, "turned": 0, "fraction": None}


# ---- the runtime and the runner carry it ----

def runtime(stage):
    return types.SimpleNamespace(command_samples=0, command_allocation=None, command_stats=CommandStats(stage))


def test_the_runtime_records_what_the_term_installed_and_hands_it_over_once(stage):
    holder, out = runtime(stage), draw(stage, n=3072)
    te.EX42StageZeroRuntime.record_command_sample(holder, torch.arange(3072), out["cmd"], out["slot"], out["heading"])
    row = te.EX42StageZeroRuntime.take_command_stats(holder)
    assert holder.command_samples == 3072 and row["samples"] == 3072 and row["out_of_range"] == 0
    assert te.EX42StageZeroRuntime.take_command_stats(holder) is None


def test_a_failing_record_switches_itself_off_and_the_training_goes_on(stage, capsys):
    holder, out = runtime(stage), draw(stage, n=8)
    holder.command_stats.add = lambda *a: (_ for _ in ()).throw(RuntimeError("boom"))
    te.EX42StageZeroRuntime.record_command_sample(holder, torch.arange(8), out["cmd"], out["slot"], out["heading"])
    assert holder.command_stats is None and holder.command_samples == 8
    assert "EX42_COMMAND_STATS_OFF RuntimeError: boom" in capsys.readouterr().out
    te.EX42StageZeroRuntime.record_command_sample(holder, torch.arange(8), out["cmd"], out["slot"], out["heading"])
    assert te.EX42StageZeroRuntime.take_command_stats(holder) is None and holder.command_samples == 16
    broken = runtime(stage)
    broken.command_stats.take = lambda: (_ for _ in ()).throw(RuntimeError("late"))
    assert te.EX42StageZeroRuntime.take_command_stats(broken) is None and broken.command_stats is None


def test_the_runtime_builds_the_record_on_its_own_stage_and_the_runner_writes_it_every_update():
    entry = (ROOT / "foothold_s2" / "scripts" / "ex42_training_entry.py").read_text(encoding="utf-8")
    made = entry.index("self.command_stats = CommandStats(self.stage_config)")
    assert entry.index("self.stage_config = stage_zero_plan.stages[0]") < made
    runner = (ROOT / "foothold_s2" / "runners" / "start_runner.py").read_text(encoding="utf-8")
    take = runner.index('take_command_stats = getattr(continuous, "take_command_stats", None)')
    block = runner[take:runner.index('"train_extra.jsonl"', take)]
    assert "command_stats = take_command_stats() if callable(take_command_stats) else None" in block
    assert 'extra["ex42_command_samples"] = command_stats' in block
    term = (ROOT / "foothold_s2" / "commands" / "mixed_command.py").read_text(encoding="utf-8")
    assert "runtime.record_command_sample(group, self.vel_command_b[group]," in term
