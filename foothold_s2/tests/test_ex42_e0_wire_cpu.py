"""E0 env-cfg seam: the real cfg objects (isaaclab stubbed) end up pointing at the column functions."""
from __future__ import annotations

import ast
import pathlib
import sys
import types

import numpy as np
import pytest
import torch

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_training_entry as te
from foothold_s2.terrains import ex42_column_reset as cr

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / "foothold_s2" / "curriculum" / "ex42-prep.yaml"
REAL = pathlib.Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_ABCDE_b613")


class Term:                                    # stands in for EventTermCfg (func/mode/params)
    def __init__(self, func=None, mode="reset", params=None):
        self.func, self.mode, self.params = func, mode, dict(params or {})


@pytest.fixture(autouse=True)
def isaac_stubs(monkeypatch):
    managers = types.ModuleType("isaaclab.managers")
    managers.EventTermCfg = Term
    utils = types.ModuleType("isaaclab.utils")
    utils.configclass = lambda c: c
    pkg = types.ModuleType("isaaclab")
    monkeypatch.setitem(sys.modules, "isaaclab", pkg)
    monkeypatch.setitem(sys.modules, "isaaclab.managers", managers)
    monkeypatch.setitem(sys.modules, "isaaclab.utils", utils)


def _inner_push(env, env_ids, velocity_range):
    pass


def _env_cfg():
    events = types.SimpleNamespace(
        reset_base=Term(params={"pose_range": {}, "velocity_range": {"x": (0.0, 0.0)}}),
        ex40_push=Term(func=_inner_push, mode="interval", params={"velocity_range": {"x": (-1, 1)}}))
    terrain = types.SimpleNamespace(terrain_generator=None)
    return types.SimpleNamespace(events=events, scene=types.SimpleNamespace(terrain=terrain))


def _plan():
    return EX42Plan.load(PLAN)


def _mesh_dir(tmp_path, families):
    import hashlib, json
    v = np.zeros((3, 3), np.float32); f = np.array([[0, 1, 2]], np.int32)
    sha = hashlib.sha256(v.tobytes() + f.tobytes()).hexdigest()
    n = len(families)
    origins = np.zeros((2, n, 3)); origins[1, :, 0] = 8.0; origins[:, :, 1] = np.arange(n) * 9.0
    np.savez(tmp_path / "terrain_mesh.npz", vertices=v, faces=f, origins=origins, column_family=np.array(families))
    (tmp_path / "mesh_manifest.json").write_text(json.dumps({"mesh_sha256": sha}))
    return tmp_path


def _real_families():
    d = np.load(REAL / "terrain_mesh.npz", allow_pickle=False)
    return [str(v) for v in d["column_family"]]


def test_push_off_kinds_come_from_the_plan_not_from_code():
    off = te.e0_push_off_kinds(_plan())
    assert {"gap", "box", "discrete_obstacles"} <= off["C"] and "flat" not in off["C"]
    assert {"crawl", "high_ledge", "wall"} == off["D"] and "E" not in off
    assert "stepping_stones_low" in off["A"] and "pyramid_stairs" not in off["A"]


@pytest.mark.skipif(not REAL.is_dir(), reason="real mesh not on this machine")
def test_real_cfg_objects_point_at_the_column_functions_and_push_follows_the_columns():
    cfg = _env_cfg()
    receipt = te.prepare_e0_env_cfg(cfg, _plan(), REAL)
    assert cfg.events.reset_base.func is cr.reset_root_state_by_column
    assert cfg.events.ex40_push.func.column_gate_inner is _inner_push
    assert cfg.events.ex40_push.params == {"velocity_range": {"x": (-1, 1)}}
    assert cfg.events.reset_base.params["velocity_range"] == {"x": (0.0, 0.0)}
    assert cfg.scene.terrain.terrain_generator.mesh_npz.endswith("terrain_mesh.npz")
    fam = _real_families()
    table = cr.build_column_table(fam)
    off = cfg.events.ex40_push.func.column_gate_push_off
    assert len(off) == len(fam) == receipt["columns"]
    for c, row in enumerate(table):
        want = (row["family"], row["kind"]) in {
            (f, k) for f, ks in te.e0_push_off_kinds(_plan()).items() for k in ks}
        assert bool(off[c]) == want, (c, row)
    on_kinds = {(r["family"], r["kind"]) for c, r in enumerate(table) if not off[c]}
    off_kinds = {(r["family"], r["kind"]) for c, r in enumerate(table) if off[c]}
    assert ("C", "flat") in on_kinds and ("D", "wall") in off_kinds and ("A", "gaps") in off_kinds
    assert ("E", "slope_steep") in on_kinds
    lo, hi = cfg.events.reset_base.params["lo"], cfg.events.reset_base.params["hi"]
    for c, row in enumerate(table):                # C gap / box / discrete_obstacles start with zero jitter
        if row["family"] == "C" and row["kind"] in ("gap", "box", "discrete_obstacles"):
            assert lo[c, [0, 1, 5]].abs().sum() == 0 and hi[c, [0, 1, 5]].abs().sum() == 0
        elif row["family"] == "E":
            assert hi[c, 0] == pytest.approx(0.5)


def test_missing_family_missing_kind_task_and_missing_push_term_fail_closed(tmp_path):
    with pytest.raises(ValueError, match="all five"):
        te.prepare_e0_env_cfg(_env_cfg(), _plan(), _mesh_dir(tmp_path, ["C"] * 7))
    plan = _plan()
    stage = next(r for r in plan.document["stages"] if r.get("id") == te.STAGE_E0_ID)
    families = _real_families() if REAL.is_dir() else None
    if families:
        (tmp_path / "x").mkdir()
        d = _mesh_dir(tmp_path / "x", families)
        del stage["terrain"]["kind_task"]["E"]["slope_steep"]
        with pytest.raises(ValueError, match="without a kind_task row"):
            te.prepare_e0_env_cfg(_env_cfg(), plan, d)
        stage["terrain"]["kind_task"].pop("C")
        with pytest.raises(ValueError):
            te.prepare_e0_env_cfg(_env_cfg(), plan, d)
    plan2 = _plan()
    s2 = next(r for r in plan2.document["stages"] if r.get("id") == te.STAGE_E0_ID)
    del s2["terrain"]["kind_task"]
    with pytest.raises(ValueError, match="kind_task"):
        te.e0_push_off_kinds(plan2)
    p = _plan()
    s3 = next(r for r in p.document["stages"] if r.get("id") == te.STAGE_E0_ID)
    s3["terrain"]["kind_task"]["C"]["gap"] = {}
    with pytest.raises(ValueError, match="explicit push"):
        te.e0_push_off_kinds(p)
    cfg = _env_cfg(); del cfg.events.ex40_push
    with pytest.raises(ValueError, match="no push event term"):
        cr.apply_column_push_gate(cfg, [False])


def test_train_start_declares_the_arg_checks_equality_and_calls_the_seam():
    src = (ROOT / "foothold_s2" / "scripts" / "train_start.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "prepare_e0_env_cfg"]
    assert len(calls) == 1
    assert src.count('"--ex42_terrain_mesh_dir"') == 2                    # pre-parser and runtime parser
    assert "args_cli.ex42_terrain_mesh_dir != _pre_args.ex42_terrain_mesh_dir" in src
    assert "--ex42_terrain_mesh_dir (combined mesh)" in src


MANAGER_BASE = pathlib.Path("/home/jay/mai/projects/IsaacLab/source/isaaclab/isaaclab/managers/manager_base.py")


def _installed_term_check():
    """The installed ManagerBase._resolve_common_term_cfg, compiled on its own (no Kit needed)."""
    import inspect
    tree = ast.parse(MANAGER_BASE.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_resolve_common_term_cfg")
    fn.decorator_list = []
    module = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {"inspect": inspect, "ManagerTermBaseCfg": Term, "ManagerTermBase": object, "string_to_callable": None,
          "annotations": None}
    exec(compile(module, str(MANAGER_BASE), "exec"), ns)
    fake = types.SimpleNamespace(_env=types.SimpleNamespace(sim=types.SimpleNamespace(is_playing=lambda: False)))
    return lambda name, term: ns["_resolve_common_term_cfg"](fake, name, term, min_argc=2)


@pytest.mark.skipif(not MANAGER_BASE.is_file(), reason="Isaac Lab source not on this machine")
def test_installed_event_manager_argument_check_accepts_the_gated_term_and_rejects_the_old_shape():
    check = _installed_term_check()
    plain = Term(func=_inner_push, mode="interval", params={"velocity_range": {"x": (-1, 1)}})
    check("plain", plain)                                           # the check itself works on a normal term
    with pytest.raises(ValueError, match="expects mandatory parameters"):
        check("bad", Term(func=_inner_push, mode="interval", params={"nope": 1}))
    cfg = _env_cfg()
    cr.apply_column_push_gate(cfg, [False, True])
    check("ex40_push", cfg.events.ex40_push)                        # same params, same signature: passes
    old = Term(func=cr.push_gated_by_column, mode="interval",       # the shape that broke gym.make
               params={"inner": _inner_push, "push_off": torch.tensor([False, True]), "velocity_range": {}})
    with pytest.raises(ValueError, match="expects mandatory parameters"):
        check("old", old)
