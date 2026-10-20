"""N1b: 시작 발판, 방향별 여유, 시작점 없음의 판정 제외. CPU 전용."""

import numpy as np
import pytest

from foothold_s2.eval import sparse_starts
from foothold_s2.terrains import sparse_terrains


@pytest.mark.parametrize("kind", ["stepping_stones_high", "gaps", "balance_beams", "stepping_beams"])
@pytest.mark.parametrize("cmd", [(-.3, 0., 0.), (0., .2, 0.), (0., -.2, 0.)])
def test_start_is_supported_and_full_motion_stays_in_sparse_zone(kind, cmd):
    tile = sparse_terrains.build_tile(kind, .5)
    result = sparse_starts.select_start(tile.boxes[3:], cmd)
    assert result["status"] == "ready"
    start = np.array(result["origin"])
    assert sparse_starts.valid_start(start, tile.boxes[3:], cmd)
    end = start[:2] + np.array(cmd[:2]) * 2.
    assert 1. <= end[0] <= 7. and 2. <= end[1] <= 6.
    assert 0. <= end[0] <= 8. and 0. <= end[1] <= 8.
    assert result["reference_m"] == pytest.approx(np.linalg.norm(cmd[:2]) * 2)


def test_old_entry_platform_is_rejected_for_backwards():
    tile = sparse_terrains.build_tile("gaps", .5)
    assert not sparse_starts.valid_start((.5, 4., 0.), tile.boxes, (-.3, 0., 0.))


def test_nearest_valid_patch_and_height_are_selected():
    boxes = np.array([[2., 3., 3., 5., -1., .04],
                      [3.8, 4.2, 3.8, 4.2, -1., -.03]])
    chosen = sparse_starts.select_start(boxes, (0., .2, 0.))
    assert chosen["origin"] == pytest.approx([4., 4., -.03])


def test_no_patch_and_over_max_distance_are_explicit_exclusions():
    for boxes, cmd, reason in [
        ([], (0., .2, 0.), "no_supported_patch"),
        ([[1., 1.4, 3., 5., -1., 0.]], (-.3, 0., 0.), "no_supported_patch"),
        ([[3., 5., 3., 5., -1., 0.]], (-.31, 0., 0.), "reference_over_0.6"),
    ]:
        result = sparse_starts.select_start(boxes, cmd)
        assert result["status"] == "no_start" and result["origin"] is None
        assert result["reason"] == reason and result["eligible"] is False


def test_margin_is_applied_beyond_endpoint():
    # 2초 끝점은 y=5.9지만 몸 길이 여유 0.3까지 두면 띠 밖이다.
    boxes = np.array([[3.9, 4.1, 5.5, 5.6, -1., 0.]])
    result = sparse_starts.select_start(boxes, (0., .2, 0.))
    assert result["status"] == "no_start"


def test_observed_side_above_point_three_keeps_actual_distance():
    tile = sparse_terrains.build_tile("gaps", .5)
    result = sparse_starts.select_start(tile.boxes[3:], (0., .35, 0.))
    assert result["status"] == "ready"
    assert result["reference_m"] == pytest.approx(.7)
    assert sparse_starts.valid_start(result["origin"], tile.boxes[3:], (0., .35, 0.))


def test_no_start_is_reported_and_not_pooled_as_a_result(tmp_path):
    from foothold_s2.eval import manifest, s0_chain, s0_tables

    jobs = s0_chain.expand_jobs("e1", str(tmp_path), ("axis3",), vy_obs=.31)
    job = next(j for j in jobs if "sparse_left" in j["name"] and "__vy_obs" in j["name"])
    assert job["rows"] == 700  # 완료 검증이 실제 생성기의 제외 원장을 확인한 뒤 수를 조정한다.
    from pathlib import Path
    out = Path(job["out"])
    out.mkdir(parents=True)
    plan = {name: sparse_starts.select_start([], (0., .31, 0.)) for name in sparse_starts.KINDS}
    manifest.write_json(str(out / "axis3_starts.json"), plan)
    manifest.write_csv(str(out / "axis3_raw.csv"), [
        {"terrain": "gaps_start", "S": True, "J_body": True, "R_body": True}])
    pooled, terrain = s0_tables.axis3_tables(str(tmp_path), ["e1"], vy_obs=.31)
    cell = next(r for r in pooled if r["direction"] == "left" and r["variant"] == "observed")
    assert cell["status"] == "no_start" and not cell["gate_eligible"]
    skipped = [r for r in terrain if r["direction"] == "left"]
    assert len(skipped) == 4
    assert all(r["status"] == "no_start" and not r["gate_eligible"] for r in skipped)
    assert all(r.get("S_rate") is None for r in skipped)


def test_reset_fix_applies_only_to_start_tiles_and_every_reset():
    import types
    import torch

    calls = []
    def original(env, ids, **params):
        calls.append((ids.tolist(), params))
    cfg = types.SimpleNamespace(func=original, params={"pose_range": {
        "x": (-.1, .1), "y": (-.1, .1), "yaw": (-.08, .08)}, "velocity_range": {}})
    class Manager:
        def get_term_cfg(self, name):
            assert name == "reset_base"
            return cfg
        def set_term_cfg(self, name, value):
            assert value is cfg
    raw = types.SimpleNamespace(event_manager=Manager(), num_envs=3, device="cpu",
                                scene=types.SimpleNamespace(terrain=types.SimpleNamespace(
                                    terrain_types=torch.tensor([0, 1, 1]))))
    sparse_starts.install_fixed_reset(raw, ["boxes", "gaps_start"])
    for ids in (torch.tensor([0, 1, 2]), torch.tensor([2])):
        cfg.func(raw, ids, **cfg.params)
    assert calls[0][0] == [0] and calls[0][1]["pose_range"]["x"] == (-.1, .1)
    assert calls[1][0] == [1, 2] and calls[2][0] == [2]
    for _, params in calls[1:]:
        assert all(params["pose_range"][a] == (0., 0.) for a in ("x", "y", "yaw"))


@pytest.fixture
def installed_legacy_geometry():
    """설치된 순수 형상 함수만 AST로 읽는다. Isaac 패키지·Kit는 import하지 않는다."""
    import ast
    import copy
    import functools
    from pathlib import Path
    import types
    import trimesh

    root = Path("C:/isaac/IsaacLab/source/isaaclab/isaaclab/terrains")
    if not root.is_dir():
        pytest.skip("설치본 Isaac Lab 순수 형상 소스 없음")
    ns = dict(np=np, trimesh=trimesh, copy=copy, functools=functools)
    def load(path, names):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        nodes = [ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)]
        nodes += [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
        exec(compile(module, str(path), "exec"), ns)
    load(root / "trimesh/utils.py", ["make_border"])
    load(root / "trimesh/mesh_terrains.py", ["gap_terrain", "floating_ring_terrain"])
    load(root / "height_field/utils.py", ["height_field_to_mesh", "convert_height_field_to_mesh"])
    load(root / "height_field/hf_terrains.py", ["stepping_stones_terrain"])
    source = Path(__file__).parents[3] / "sim/eval/generalization_env_cfg.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    cfg = next(n.value for n in tree.body if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "GO2_UNSEEN_TERRAINS_CFG" for t in n.targets))
    args = {kw.arg: kw.value for kw in cfg.keywords}
    subs = args["sub_terrains"]
    result = {}
    for key, node in zip(subs.keys, subs.values):
        name = ast.literal_eval(key)
        if name not in ("gap", "stepping_stones", "floating_ring"):
            continue
        values = {k: ast.literal_eval(args[k]) for k in
                  ("size", "horizontal_scale", "vertical_scale", "slope_threshold")}
        values.update({kw.arg: ast.literal_eval(kw.value) for kw in node.keywords})
        item = types.SimpleNamespace(**values)
        fn = ns[name + "_terrain"]
        result[name] = (item, fn)
    return result


@pytest.mark.parametrize("name", ["gap", "stepping_stones", "floating_ring"])
@pytest.mark.parametrize("cmd", [(-.3, 0., 0.), (0., .2, 0.), (0., -.2, 0.)])
def test_installed_legacy_generators_have_supported_start_and_bounded_endpoint(installed_legacy_geometry, name, cmd):
    cfg, fn = installed_legacy_geometry[name]
    state = np.random.get_state()
    try:
        np.random.seed(42)
        meshes, _ = fn(.5, cfg)
    finally:
        np.random.set_state(state)
    result = sparse_starts.legacy_start(name, cfg, .5, meshes, cmd)
    assert result["status"] == "ready"
    zone, floor = sparse_starts.legacy_region(name, cfg, .5)
    boxes = sparse_starts.support_boxes(meshes, floor)
    start = np.array(result["origin"])
    assert any(b[0] - 1e-7 <= start[0] <= b[1] + 1e-7 and
               b[2] - 1e-7 <= start[1] <= b[3] + 1e-7 and abs(b[5] - start[2]) < 1e-7 for b in boxes)
    velocity = np.array(cmd[:2])
    end = start[:2] + velocity * 2 + velocity / np.linalg.norm(velocity) * .3
    assert np.all(end >= np.array(zone)[:, 0] - 1e-7)
    assert np.all(end <= np.array(zone)[:, 1] + 1e-7)


def test_unknown_legacy_region_is_excluded():
    import types
    result = sparse_starts.legacy_start("unknown", types.SimpleNamespace(size=(8., 8.)), .5, [], (-.3, 0., 0.))
    assert result["status"] == "no_start" and result["origin"] is None
    assert result["reason"] == "sparse_region_unavailable"


def test_legacy_assembly_uses_checked_mesh_and_never_falls_back(installed_legacy_geometry, monkeypatch):
    import copy
    import types
    from foothold_s2.eval import terrain_sets
    subs = {}
    for name, (cfg, fn) in installed_legacy_geometry.items():
        cfg.function = fn
        subs[name] = cfg
    base = types.SimpleNamespace(size=(8., 8.), horizontal_scale=.1, vertical_scale=.005,
                                 slope_threshold=.75, sub_terrains=subs)
    monkeypatch.setattr(terrain_sets, "v2_generator", lambda _: (copy.deepcopy(base), None))
    cfg = terrain_sets.merged_generator(list(subs), .5, 42, start_cmd=(-.3, 0., 0.))
    assert cfg.num_cols == 3 and cfg.use_cache is False
    for name, sub in cfg.sub_terrains.items():
        meshes, origin = sub.function(.5, sub)
        assert origin == pytest.approx(cfg.axis3_starts[name]["origin"])
        first = meshes[0].vertices.copy()
        meshes[0].apply_translation([100., 0., 0.])
        again, _ = sub.function(.5, sub)
        assert again[0].vertices == pytest.approx(first)
    monkeypatch.setattr(sparse_starts, "legacy_start",
                        lambda *args: dict(status="no_start", origin=None, eligible=False))
    cfg = terrain_sets.merged_generator(list(subs), .5, 42, start_cmd=(-.3, 0., 0.))
    assert cfg.num_cols == 0 and not cfg.sub_terrains


def test_all_excluded_entry_writes_status_without_running_policy_and_requires_evidence(tmp_path):
    import ast
    import os
    from pathlib import Path
    import types
    from foothold_s2.eval import cells, manifest, rsj, s0_chain, terrain_sets

    job = next(j for j in s0_chain.expand_jobs("e1", str(tmp_path), ("axis3",))
               if "sparse_left" in j["name"])
    out = Path(job["out"])
    out.mkdir(parents=True)
    plan = {name: sparse_starts.select_start([], (0., .2, 0.))
            for name in cells.TERRAIN_GROUPS["sparse"]}
    def no_policy(*args, **kwargs):
        raise AssertionError("시작점 없는 판을 실행함")
    ns = dict(cells=cells, manifest=manifest, rsj=rsj, os=os, run_episode_axis=no_policy,
              policy_record=no_policy, terrain_sets=types.SimpleNamespace(
                  merged_generator=lambda *a, **kw: types.SimpleNamespace(axis3_starts=plan, sub_terrains={})))
    ns["args"] = types.SimpleNamespace(cmd="0,0.2,0", group="sparse", terrains="all", direction="left",
                                      difficulty=.5, seed=42, cmd_basis="fixed", out=str(out), episodes=100)
    ns["finish"] = lambda path, data: manifest.write_json(str(Path(path) / "run_manifest.json"), data)
    tree = ast.parse(Path(terrain_sets.__file__).with_name("run_eval.py").read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name in ("do_axis3", "save_episode_outputs")]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<axis3_entry>", "exec"), ns)
    ns["do_axis3"]()
    assert manifest.read_csv(str(out / "axis3_raw.csv")) == []
    summary = manifest.read_csv(str(out / "axis3_summary.csv"))
    assert len(summary) == 7 and all(r["status"] == "no_start" for r in summary)
    (out / "rc.txt").write_text("rc=0")
    (out / "run.log").write_text("explicit exclusions")
    assert s0_chain.job_done(job)
    # 누락한 판을 시작점 제외로 위장하려면 두 원장의 상태·이름이 맞아야 한다.
    bad = dict(plan)
    bad.pop("gap")
    manifest.write_json(str(out / "axis3_starts.json"), bad)
    assert not s0_chain.job_done(job)
