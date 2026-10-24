"""T5 probe 고정 칸(평지 계열 2 + random_rough 2, 레벨 0): 종류 이름으로 고르고 실제 이름을 기록한다 (SONNET-X25). CPU 만."""

from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.eval import fixed_terrain as ft
from foothold_s2.eval import probe_tiles as PT
from foothold_s2.terrains import columns

CONT = columns.CONTINUOUS


def test_b_continuous_layout_picks_slope_level0_and_random_rough_by_name():
    names = PT.column_names(CONT, 23)
    levels, types, flat_kind, tiles = PT.pick(names)

    assert flat_kind == "hf_pyramid_slope" and types.tolist() == [18, 19, 14, 17] and levels.tolist() == [0, 0, 0, 0]       # B 의 23 열: 18~19 경사 피라미드, 14~17 random_rough
    assert [t["kind"] for t in tiles] == ["hf_pyramid_slope", "hf_pyramid_slope", "random_rough", "random_rough"] and all(t["level"] == 0 for t in tiles)
    assert all(names[t["col"]] == t["kind"] for t in tiles)                                   # 열 번호와 이름이 어긋나지 않는다


def test_a_real_flat_column_is_preferred_and_a_layout_without_either_is_refused():
    props = {**CONT, "flat": 0.04}
    names = PT.column_names(props, 25)
    _, types, flat_kind, _ = PT.pick(names)

    assert flat_kind == "flat" and names[types[0]] == "flat" and names[types[1]] == "flat"
    with pytest.raises(ValueError, match="평지 계열"):
        PT.pick(["pyramid_stairs", "random_rough", "random_rough"])
    with pytest.raises(ValueError, match="2 개 미만"):
        PT.pick(["hf_pyramid_slope", "hf_pyramid_slope", "random_rough"])
    with pytest.raises(ValueError, match="4 env"):
        PT.pick(PT.column_names(CONT, 23), 64)


def test_record_names_the_kinds_and_says_when_flat_is_only_a_gentle_slope():
    levels, types, flat_kind, tiles = PT.pick(PT.column_names(CONT, 23))
    rec = PT.record(levels, types, flat_kind, tiles, 10, 23)
    line = ft.describe(rec)

    assert "hf_pyramid_slope 레벨 0 x 2 env(열 18,19)" in line and "random_rough 레벨 0 x 2 env(열 14,17)" in line and "% 23" not in line and "4 env" in line
    assert rec["flat_note"] and "경사" in rec["flat_note"] and rec["assignment_sha256"] == ft.assignment_sha256(levels, types)
    props = {**CONT, "flat": 0.04}
    lv2, ty2, fk2, tl2 = PT.pick(PT.column_names(props, 25))

    assert PT.record(lv2, ty2, fk2, tl2, 10, 25)["flat_note"] is None


def test_installed_isaaclab_uses_the_same_column_formula_as_our_copy():
    src = Path("C:/isaac/IsaacLab/source/isaaclab/isaaclab/terrains/terrain_generator.py")
    if not src.exists():
        pytest.skip("Isaac Lab 소스 없음")
    text = src.read_text(encoding="utf-8")

    assert "np.min(np.where(index / self.cfg.num_cols + 0.001 < np.cumsum(proportions))[0])" in text and "proportions /= np.sum(proportions)" in text
    assert "index / num_cols + 0.001 < cum" in Path(columns.__file__).read_text(encoding="utf-8")


def _raw(props, cols, rows=10, n=4):
    origins = torch.randn(rows, cols, 3)
    levels, types = torch.randint(0, rows, (n,)), torch.randint(0, cols, (n,))
    terrain = SimpleNamespace(terrain_origins=origins, terrain_levels=levels, terrain_types=types, env_origins=origins[levels, types].clone(),
                              cfg=SimpleNamespace(terrain_generator=SimpleNamespace(num_cols=cols, sub_terrains={k: SimpleNamespace(proportion=v) for k, v in props.items()})))
    scene = SimpleNamespace(terrain=terrain, env_origins=terrain.env_origins)

    return SimpleNamespace(scene=scene)


def test_apply_to_overwrites_levels_types_and_origins_and_returns_the_named_record():
    raw = _raw(CONT, 23)
    rec = PT.apply_to(raw)
    t = raw.scene.terrain

    assert t.terrain_levels.tolist() == [0, 0, 0, 0] and t.terrain_types.tolist() == [18, 19, 14, 17] and torch.equal(t.env_origins, t.terrain_origins[t.terrain_levels, t.terrain_types])
    assert rec["num_envs"] == 4 and [x["kind"] for x in rec["tiles"]][2] == "random_rough"
    bad = _raw(CONT, 23)
    bad.scene.terrain.cfg.terrain_generator.num_cols = 30

    with pytest.raises(RuntimeError, match="num_cols"):
        PT.apply_to(bad)


def test_the_unnamed_formula_describe_is_unchanged_for_the_64_env_fixed_layout():
    rec = {"rows": 10, "cols": 23, "levels_used": 3, "num_envs": 64, "assignment_sha256": "ab" * 32}

    assert ft.describe(rec).startswith("고정 칸 · 레벨 0~2 만(64 env 배치 23/23/18) · 종류 = env 번호 % 23 열")
