"""EX-42 틈 · 평균대 열 처방 후보 셋 (CPU · Isaac 없음): 가장자리 마스크 열 넓힘 · 듬성 열 선속도 추종 원문 식 · 틈 빠짐 종료 발판 평면 기준.
세 스위치는 환경 변수이고 기본 꺼짐이다: 꺼져 있으면 영수증 · 식 · 종료가 옛 것과 같아야 한다."""
import json
import os
import types
from pathlib import Path

import numpy as np
import pytest
import torch

from foothold_s2 import ex42_gap_switches as gs
from foothold_s2.terrains import ex42_edge_masks as em

MESH = Path(os.environ.get("EX42_GAP_SWITCH_TEST_MESH", "/mnt/win-d/mai/data/foothold/sonnet_beam_mesh_1119/b2m_rpy_lv"))
needs_mesh = pytest.mark.skipif(not (MESH / "terrain_mesh.npz").is_file(), reason="beam mesh not on this machine")


def _table():
    from foothold_s2.terrains.ex42_column_reset import build_column_table
    fam = ["A"] * 50 + ["B"] * 12 + ["C"] * 7 + ["D"] * 3 + ["E"] * 4
    return build_column_table(fam)


# ---- 환경 변수 읽기 ------------------------------------------------------------------------------------------------------------------------

def test_off_by_default_and_the_receipt_is_empty():
    sw = gs.read_switches(_table(), {})
    assert not gs.any_on(sw) and gs.receipt(sw) == {} and sw["edge_columns"] == sw["min_columns"] == sw["plane_columns"] == ()


def test_kinds_resolve_to_the_columns_of_the_real_table_and_are_checked():
    t = _table()
    sw = gs.read_switches(t, {gs.ENV_EDGE: "B/gap,B/beam,C/gap", gs.ENV_MIN: "A/gaps,B/gap", gs.ENV_PLANE: "A/gaps,B/gap,C/gap"})
    assert sw["edge_columns"] == (56, 59, 62) and sw["plane_columns"] == (45, 46, 47, 56, 62) and sw["min_columns"] == (45, 46, 47, 56)
    assert gs.receipt(sw)["gap_switches"]["edge_extra_kinds"] == ["B/gap", "B/beam", "C/gap"]
    for bad in ("B/nothing", "gap", "B/gap,B/gap", "b/gap", "B/gap;C/gap"):
        with pytest.raises(ValueError):
            gs.read_switches(t, {gs.ENV_MIN: bad})


# ---- 후보 2: 선속도 추종 식 ----------------------------------------------------------------------------------------------------------------

def test_min_form_forgives_overspeed_only_on_the_listed_envs_and_matches_the_exact_form_elsewhere():
    std = 0.5 ** 0.5
    cmd = torch.tensor([[1.0, 0.0]] * 4)
    vel = torch.tensor([[1.4, 0.0], [0.6, 0.0], [1.0, 0.0], [1.4, 0.0]])
    on = torch.tensor([True, True, True, False])
    out = gs.track_lin_mixed(vel, cmd, std, on)
    exact = torch.exp(-torch.sum((cmd - vel) ** 2, dim=-1) / std ** 2)
    assert float(out[0]) == pytest.approx(1.0)                              # 과속 무벌점
    assert float(out[1]) == pytest.approx(float(exact[1]))                  # 모자라면 같은 벌점
    assert float(out[2]) == pytest.approx(1.0)
    assert float(out[3]) == pytest.approx(float(exact[3])) and float(out[3]) < 1.0       # 열 밖은 정확 추종 (과속도 벌점)
    assert torch.equal(gs.track_lin_mixed(vel, cmd, std, torch.zeros(4, dtype=torch.bool)), exact)          # 전부 열 밖 = 옛 식 그대로


def test_min_form_matches_the_start_reward_function_on_every_listed_env():
    """START 원문 식 함수 (start_rewards.track_lin_vel_min_form) 와 같은 값: 같은 식을 두 곳에 쓰지 않았음을 소스로 대조."""
    src = (Path(__file__).resolve().parents[1] / "rewards" / "start_rewards.py").read_text(encoding="utf-8")
    assert "torch.minimum(asset.data.root_lin_vel_b[:, :2], cmd) - cmd" in src
    std, vel, cmd = 0.7, torch.randn(64, 2), torch.randn(64, 2)
    want = torch.exp(-torch.sum((torch.minimum(vel, cmd) - cmd) ** 2, dim=-1) / std ** 2)
    assert torch.allclose(gs.track_lin_mixed(vel, cmd, std, torch.ones(64, dtype=torch.bool)), want)


def test_column_mask_and_cfg_wiring_keep_the_term_name_and_the_std_field():
    types_ = torch.tensor([0, 56, 62, 45, 3])
    assert gs.column_env_mask(types_, (45, 56), 76).tolist() == [False, True, False, True, False]
    assert not gs.column_env_mask(types_, (), 76).any()
    cfg = types.SimpleNamespace(rewards=types.SimpleNamespace(track_lin_vel=types.SimpleNamespace(func="old", params={"command_name": "base_velocity", "std": 0.7})),
                                terminations=types.SimpleNamespace(foot_below_ground=types.SimpleNamespace(params={"margin": 0.25})))
    gs.apply_cfg(cfg, gs.read_switches(_table(), {gs.ENV_MIN: "B/gap", gs.ENV_PLANE: "C/gap"}), track_func="new")
    assert cfg.rewards.track_lin_vel.func == "new" and cfg.rewards.track_lin_vel.params == {"command_name": "base_velocity", "std": 0.7, "min_columns": [56]}
    assert cfg.terminations.foot_below_ground.params == {"margin": 0.25, "plane_columns": [62]}
    untouched = types.SimpleNamespace(rewards=types.SimpleNamespace(track_lin_vel=types.SimpleNamespace(func="old", params={"std": 0.7})),
                                      terminations=types.SimpleNamespace(foot_below_ground=types.SimpleNamespace(params={})))
    gs.apply_cfg(untouched, gs.read_switches(_table(), {}), track_func="new")
    assert untouched.rewards.track_lin_vel.func == "old" and untouched.terminations.foot_below_ground.params == {}


# ---- 후보 3: 종료 ---------------------------------------------------------------------------------------------------------------------------

def _fake_env(foot_z, ground_z, origin_z, col, level=0, n_cols=76):
    """한 env: 발 네 개 z · 가장 가까운 스캔 점 z (발 바로 아래 한 점) · 타일 원점 z · 지형 열."""
    feet = torch.zeros(1, 4, 3); feet[0, :, 2] = torch.tensor(foot_z)
    hits = torch.zeros(1, 1, 3); hits[0, 0, 2] = ground_z
    origins = torch.zeros(10, n_cols, 3); origins[:, col, 2] = origin_z
    class _Scene:
        sensors = {"scan": types.SimpleNamespace(data=types.SimpleNamespace(ray_hits_w=hits))}
        terrain = types.SimpleNamespace(terrain_types=torch.tensor([col]), terrain_levels=torch.tensor([level]), terrain_origins=origins)

        def __getitem__(self, key):
            return types.SimpleNamespace(data=types.SimpleNamespace(body_pos_w=feet))

    scene = _Scene()
    return types.SimpleNamespace(scene=scene)


def _done(env, **kw):
    from foothold_s2.tasks import mdp_extra
    ids = types.SimpleNamespace(name="robot", body_ids=slice(None))
    return bool(mdp_extra.foot_below_ground(env, None, types.SimpleNamespace(name="scan"), ids, margin=0.25, **kw)[0])


def test_a_foot_in_the_pit_does_not_end_the_episode_with_the_scan_rule_but_does_with_the_plane_rule():
    env = _fake_env([0.0, 0.0, -0.35, -0.35], ground_z=-0.35, origin_z=0.0, col=62)           # 발 아래 가장 가까운 스캔 점 = 틈 바닥 (발과 같은 높이)
    assert not _done(env)                                                                     # 지금 식: 끝나지 않는다
    assert _done(env, plane_columns=[62])                                                    # 처방: 출발 발판 평면 -0.25 아래 -> 끝남
    assert not _done(env, plane_columns=[56, 45])                                            # 다른 열만 켜면 이 열은 옛 식 그대로
    shallow = _fake_env([0.0, 0.0, -0.2, -0.2], ground_z=-0.2, origin_z=0.0, col=62)
    assert not _done(shallow, plane_columns=[62])                                            # 0.25 m 안쪽은 끝나지 않는다


def test_the_plane_is_the_tile_origin_not_world_zero_and_the_old_rule_still_fires_on_a_real_drop():
    raised = _fake_env([0.1, 0.1, 0.0, 0.0], ground_z=0.1, origin_z=0.3, col=56)               # 발판 평면 0.3: 발 0.0 은 0.3 아래 -> 끝남
    assert _done(raised, plane_columns=[56]) and not _done(raised)
    assert gs.feet_below_plane(torch.tensor([[0.0, 0.0, -0.26, 0.0]]), torch.tensor([0.0]))[0]
    drop = _fake_env([0.0, 0.0, -0.9, 0.0], ground_z=0.0, origin_z=0.0, col=3)                # 열 밖 env: 스캔 식이 그대로 끝냄
    assert _done(drop, plane_columns=[56]) and _done(drop)


# ---- 후보 1: 가장자리 마스크 ----------------------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def real():
    d = np.load(MESH / "terrain_mesh.npz", allow_pickle=False)
    arrays = {k: d[k] for k in d.files}
    terrain = json.loads((MESH / "terrain_manifest.json").read_text(encoding="utf-8-sig"))
    covered = set(int(c) for c in arrays["edge_columns"])
    specs = em.extra_specs(terrain, ("B/gap", "B/beam", "C/gap"), 10, covered=covered)
    return arrays, specs, em.build_extra_masks(arrays["vertices"], arrays["faces"], arrays["origins"], specs)


@needs_mesh
def test_specs_read_the_tiles_from_the_terrain_manifest(real):
    _, specs, _ = real
    assert [(s["kind"], s["col"], s["size_x"], s["size_y"], s["x_start"], s["y0"]) for s in specs] == [
        ("B/gap", 56, 12.0, 12.0, -60.0, 302.0), ("B/beam", 59, 12.0, 12.0, -60.0, 338.0), ("C/gap", 62, 9.0, 9.0, -45.0, 404.0)]


@needs_mesh
def test_masks_exist_on_the_new_columns_and_the_covered_columns_are_refused(real):
    arrays, specs, built = real
    for b in built:
        assert b["inner"].any() and b["outer"].any(), b["kind"]
        assert b["inner"].shape[0] == 10
    assert built[0]["inner"][5].sum() > 0 and built[2]["inner"][9].sum() > 0               # 틈 수준 5 · C 틈 수준 9 에 가장자리
    terrain = json.loads((MESH / "terrain_manifest.json").read_text(encoding="utf-8-sig"))
    with pytest.raises(ValueError, match="already carry"):
        em.extra_specs(terrain, ("A/gaps",), 10, covered={int(c) for c in arrays["edge_columns"]})
    with pytest.raises(ValueError):
        em.extra_specs(terrain, ("A/nothing",), 10)


def _tables(arrays, built=None):
    loaded = em.load_edge_masks(MESH / "terrain_mesh.npz")
    tbl = em.EdgeTables(loaded, 76, "cpu")
    if built is not None:
        tbl.add_extra(built)
    return tbl


@needs_mesh
def test_the_foot_term_reads_the_new_columns_and_leaves_every_other_column_bit_for_bit(real):
    arrays, specs, built = real
    base, plus = _tables(arrays), _tables(arrays, built)
    check = plus.self_check()
    assert {e["kind"] for e in check["extra"]} == {"B/gap", "B/beam", "C/gap"} and all(e["value_on_inner"] > 0 for e in check["extra"])
    gen = torch.Generator().manual_seed(7)
    n = 512
    types_ = torch.randint(0, 76, (n,), generator=gen)
    levels = torch.randint(0, 10, (n,), generator=gen)
    origin = torch.as_tensor(arrays["origins"])[levels, types_][:, :2]
    feet = origin[:, None, :] + (torch.rand(n, 4, 2, generator=gen) - 0.5) * 4.0
    contact = torch.rand(n, 4, generator=gen) > 0.3
    a, b = base.penalty(feet, contact, levels, types_), plus.penalty(feet, contact, levels, types_)
    new_cols = torch.isin(types_, torch.tensor([56, 59, 62]))
    assert torch.equal(a[~new_cols], b[~new_cols])                         # 다른 열 (A 마스크 열 포함) 은 그대로
    assert (a[new_cols] == 0).all()                                         # 옛 표는 새 열에서 0
    assert (b[new_cols] > 0).any()                                          # 새 표는 가장자리 위 발에서 0 이 아님
    assert (b >= 0).all()
    off = plus.penalty(feet, torch.zeros_like(contact), levels, types_)
    assert (off == 0).all()                                                 # 접촉이 없으면 0


@needs_mesh
def test_a_foot_on_the_gap_edge_is_penalised_and_a_foot_on_the_support_is_not(real):
    arrays, specs, built = real
    tbl = _tables(arrays, built)
    gap = built[0]
    r = 9
    inner = np.argwhere(gap["inner"][r])
    assert len(inner) > 0
    x = gap["x_start"] + gap["size_x"] * r + (inner[0][0] + 0.5) * em.RES
    y = gap["y0"] + (inner[0][1] + 0.5) * em.RES
    contact = torch.ones(1, 1, dtype=torch.bool)
    lv, ty = torch.tensor([r]), torch.tensor([56])
    assert float(tbl.penalty(torch.tensor([[[x, y]]], dtype=torch.float32), contact, lv, ty)[0]) > 0
    flat = np.argwhere(~gap["inner"][r] & ~gap["outer"][r])
    fx = gap["x_start"] + gap["size_x"] * r + (flat[0][0] + 0.5) * em.RES
    fy = gap["y0"] + (flat[0][1] + 0.5) * em.RES
    assert float(tbl.penalty(torch.tensor([[[fx, fy]]], dtype=torch.float32), contact, lv, ty)[0]) == 0.0


@needs_mesh
def test_the_mesh_files_are_not_touched_by_the_switch(real):
    """런타임 마스크라 메시 npz · 매니페스트 sha (계획이 못 박은 것) 는 그대로: 이 시험은 npz 에 새 배열이 없음을 확인."""
    arrays, _, _ = real
    assert set(arrays) == {"vertices", "faces", "origins", "column_family", "flags", *em.EDGE_KEYS}
    assert arrays["edge_columns"].tolist() == list(range(23, 48))


@needs_mesh
def test_attach_builds_the_extra_masks_from_the_contract_and_the_receipt_shows_them():
    from foothold_s2.scripts.ex42_training_entry import attach_edge_tables
    def raw():
        return types.SimpleNamespace(device="cpu", reward_manager=types.SimpleNamespace(get_term_cfg=lambda name: types.SimpleNamespace(weight=-1.0)))
    plain = {"column_table": [0] * 76, "foot_edge_weight": -1.0, "edge_masks_npz": str(MESH / "terrain_mesh.npz")}
    r0 = raw()
    out0 = attach_edge_tables(r0, plain)
    assert "extra" not in out0["self_check"] and r0.ex42_edge_tables.extra == []                          # 꺼짐: 옛 영수증 그대로
    r1 = raw()
    out1 = attach_edge_tables(r1, {**plain, "gap_switches": {"edge_extra_kinds": ["B/gap", "B/beam", "C/gap"]}})
    assert [e["column"] for e in out1["self_check"]["extra"]] == [56, 59, 62]
    assert [e["col"] for e in r1.ex42_edge_tables.extra] == [56, 59, 62]
    with pytest.raises(ValueError, match="already carry"):
        attach_edge_tables(raw(), {**plain, "gap_switches": {"edge_extra_kinds": ["A/gaps"]}})


def test_prepare_refuses_extra_edge_kinds_without_a_foot_edge_weight():
    src = (Path(__file__).resolve().parents[1] / "scripts" / "ex42_training_entry.py").read_text(encoding="utf-8")
    assert "non-zero foot_edge_weight in the plan row" in src and "gap_switches.apply_cfg(env_cfg, switches, track_func)" in src
    assert src.count("gap_switches.read_switches(table)") == 1
