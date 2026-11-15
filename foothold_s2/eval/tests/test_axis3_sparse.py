"""ASTRA-N1: 8x8 생성기와 두 옆 칸의 실행·집계 계약. GPU/Kit 없음."""

import ast
import copy
import os
from pathlib import Path
import sys
import types

import numpy as np
import pytest

from foothold_s2.eval import cells, manifest, s0_chain, s0_tables, terrain_sets, sparse_starts


def test_two_side_cells_keep_fixed_and_observed_even_at_same_speed():
    for value in (0.2, 0.35):
        rows = cells.axis3_table(value)
        for direction, sign in (("left", 1), ("right", -1)):
            side = [r for r in rows if r["group"] == "sparse" and r["direction"] == direction]
            assert len(side) == 2
            assert {r["variant"] for r in side} == {"fixed", "observed"}
            assert [r["commands"] for r in side] == [
                [(0., sign * 0.2, 0.)], [(0., sign * value, 0.)]]
        jobs = s0_chain.expand_jobs("e1", "R", ("axis3",), vy_obs=value)
        left = [j for j in jobs if "sparse_left" in j["name"]]
        assert len(left) == len({j["out"] for j in left}) == 2
        assert {j["rows"] for j in left} == {700}
        assert "--cmd_basis" in left[1]["args"]


def test_missing_or_zero_observation_is_not_fabricated():
    for value, status in ((None, "needs_vy_obs"), (0.0, "zero_vy_obs")):
        sides = [r for r in cells.axis3_table(value)
                 if r["group"] == "sparse" and r["direction"] in ("left", "right")]
        assert len(sides) == 4
        assert [r["commands"] for r in sides if r["variant"] == "observed"] == [[], []]
        assert {r["status"] for r in sides if r["variant"] == "observed"} == {status}


@pytest.mark.parametrize("value", [-0.1, float("nan"), float("inf")])
def test_invalid_observed_speed_is_rejected(value):
    with pytest.raises(ValueError):
        cells.axis3_table(value)


def test_axis3_entry_keeps_all_seven_terrains_and_short_rule(tmp_path):
    # Execute only the real function body: importing this entry point would start Kit.
    tree = ast.parse((Path(terrain_sets.__file__).parent / "run_eval.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "do_axis3")
    ns = {"cells": cells, "manifest": manifest, "os": os}
    calls = []
    def generator(names, difficulty, seed, start_cmd=None, root_height_m=.4):
        plan = {name: {"status": "ready"} for name in names}
        return types.SimpleNamespace(axis3_starts=plan, sub_terrains=dict.fromkeys(names))
    ns['adapters'] = types.SimpleNamespace(sparse_start_root_height=lambda _: .4)
    ns['make_adapter'] = lambda: None
    ns["terrain_sets"] = types.SimpleNamespace(merged_generator=generator, sparse_starts=sparse_starts)
    ns["rsj"] = types.SimpleNamespace(summarize_axis3_cell=None)
    ns["save_episode_outputs"] = lambda *args: None
    def run(*args, **kwargs):
        calls.append((args, kwargs))
        return [], {}, None, 0.02
    ns["run_episode_axis"] = run
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<do_axis3>", "exec"), ns)
    for direction, cmd, distance in [("back", "-0.3,0,0", 0.6),
                                     ("left", "0,0.2,0", 0.4),
                                     ("right", "0,-0.35,0", 0.7)]:
        ns["args"] = types.SimpleNamespace(cmd=cmd, group="sparse", terrains="all",
                                          direction=direction, difficulty=.5, seed=42, cmd_basis="",
                                          out=str(tmp_path), episodes=100)
        ns["do_axis3"]()
        args, kw = calls[-1]
        assert args[1] == ["gap", "stepping_stones", "floating_ring", "stepping_stones_start",
                           "balance_beams", "stepping_beams", "gaps_start"]
        assert args[4] == 4.0 and args[5] == pytest.approx(distance)
        assert kw["command_s"] == 2.0
        assert kw["fixed_start"] is True


def test_merged_generator_uses_real_8x8_mesh_functions_without_kit(monkeypatch):
    # Only Isaac cfg construction is substituted. The mapping and mesh functions are real.
    class Cfg:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
            if hasattr(type(self), "function"):
                self.function = type(self).function
    fake = types.ModuleType("isaaclab.terrains")
    fake.SubTerrainBaseCfg = Cfg
    utils = types.ModuleType("isaaclab.utils")
    utils.configclass = lambda cls: cls
    pkg = types.ModuleType("isaaclab")
    pkg.terrains, pkg.utils = fake, utils
    for name, module in (("isaaclab", pkg), ("isaaclab.terrains", fake), ("isaaclab.utils", utils)):
        monkeypatch.setitem(sys.modules, name, module)
    base = types.SimpleNamespace(size=(8., 8.), sub_terrains={
        name: Cfg(proportion=.1) for name in ("gap", "stepping_stones", "floating_ring")})
    monkeypatch.setattr(terrain_sets, "v2_generator", lambda _: (copy.deepcopy(base), None))
    cfg = terrain_sets.merged_generator(cells.TERRAIN_GROUPS["sparse"], .5, 42)
    assert cfg.size == (8., 8.) and cfg.num_cols == 7
    assert set(cfg.sub_terrains) == set(cells.TERRAIN_GROUPS["sparse"])
    for name, kind in [("stepping_stones_start", "stepping_stones_high"),
                       ("balance_beams", "balance_beams"), ("stepping_beams", "stepping_beams"),
                       ("gaps_start", "gaps")]:
        sub = cfg.sub_terrains[name]
        assert sub.kind == kind and sub.size == (8., 8.)
        meshes, origin = type(sub).function(.5, sub)
        bounds = np.array([m.bounds for m in meshes])
        assert np.min(bounds[:, 0, 0]) == pytest.approx(0.)
        assert np.max(bounds[:, 1, 0]) == pytest.approx(8.)
        assert np.min(bounds[:, 0, 1]) == pytest.approx(0.)
        assert np.max(bounds[:, 1, 1]) == pytest.approx(8.)
        assert origin == pytest.approx([.5, 4., 0.])
    plan = sparse_starts.start_plan(.5, (-.3, 0., 0.))
    cfg = terrain_sets.merged_generator(cells.START_SHEETS, .5, 42, start_cmd=(-.3, 0., 0.))
    assert cfg.use_cache is False
    for name, start in plan.items():
        if start['status'] == 'no_start':
            assert name not in cfg.sub_terrains
            assert cfg.axis3_starts[name]['previous_origin'] is not None
            continue
        sub = cfg.sub_terrains[name]
        _, origin = sub.function(.5, sub)
        assert origin == pytest.approx(start["origin"])
        assert origin[0] != .5


def test_same_speed_side_results_are_not_overwritten_or_pooled(tmp_path):
    jobs = s0_chain.expand_jobs("e1", str(tmp_path), ("axis3",), vy_obs=.2)
    left = [j for j in jobs if "sparse_left" in j["name"]]
    assert len(left) == 2
    for job, success in zip(left, (True, False)):
        Path(job["out"]).mkdir(parents=True)
        manifest.write_csv(str(Path(job["out"]) / "axis3_raw.csv"), [{
            "terrain": "gaps_start", "R_body": success, "S": success, "J_body": success,
            "cmd_progress_ratio": float(success), "cmd_progress_ratio_capped": float(success),
            "yaw_dev_flag": False, "yaw_dev_deg": 0.0, "velocity_mae_mps": 0.0}])
    rows, _ = s0_tables.axis3_tables(str(tmp_path), ["e1"], vy_obs=.2)
    left = [r for r in rows if r["group"] == "sparse" and r["direction"] == "left"]
    assert [r["S_rate"] for r in left] == [1., 0.]
    comparison = s0_tables.compare_policies([], left)
    assert sorted(r["e1"] for r in comparison if r["extra"] == "J_body|S") == ["0.0|0.0", "1.0|1.0"]


def test_cli_observation_is_policy_specific_and_reaches_tables(tmp_path, monkeypatch):
    captured = []
    class NoKitScheduler:
        def __init__(self, jobs, *args):
            captured.extend(jobs)
        def log(self, text):
            pass
        def worker(self, gpu):
            pass
    monkeypatch.setattr(s0_chain, "Scheduler", NoKitScheduler)
    monkeypatch.setattr(s0_chain, "job_done", lambda job: True)
    root = str(tmp_path / "raw")
    assert s0_chain.main(["--root", root, "--policies", "e1,v2", "--axes", "axis3",
                          "--vy_obs", "e1=0.35"]) == 0
    observed = [j for j in captured if "__vy_obs" in j["name"]]
    assert len(observed) == 2 and all(j["name"].startswith("e1/") for j in observed)
    assert "--cmd=0,0.35,0" in observed[0]["args"]
    out = str(tmp_path / "tables")
    assert s0_tables.main(["--root", root, "--out", out, "--policies", "e1,v2",
                          "--vy_obs", "e1=0.35"]) == 0
    rows = manifest.read_csv(str(Path(out) / "axis3_cells.csv"))
    observed = [r for r in rows if r["variant"] == "observed"]
    assert {r["status"] for r in observed if r["policy"] == "e1"} == {"not_run"}
    assert {r["status"] for r in observed if r["policy"] == "v2"} == {"needs_vy_obs"}


@pytest.mark.parametrize("specs", [
    ["e1=-0.1"], ["e1=nan"], ["e1=inf"], ["other=0.2"], ["e1=0.2", "e1=0.3"], ["0.2"]])
def test_cli_rejects_invalid_or_ambiguous_observations(specs):
    with pytest.raises(ValueError):
        s0_chain.parse_vy_obs(specs, ["e1", "v2"])
