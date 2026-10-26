"""--fixed-level N (고정 칸의 레벨 올리기). CPU 만. 기본값이면 기존 해시(c3884d68 · 7f49a1e9)가 그대로고, N=6 이면 레벨 6 칸이다."""

import ast
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from foothold_s2.eval import fixed_terrain as ft
from foothold_s2.eval import probe_tiles as PT
from foothold_s2.terrains import columns

ROOT = Path(__file__).resolve().parents[2]
OLD64, OLD16 = "c3884d686592", "7f49a1e935ea"                      # 기록된 기존 칸 해시 앞 12 자리(b1500 · sb50 평가 json)


def _raw(num_envs, rows=10, cols=23, names=None):
    origins = torch.arange(rows * cols * 3, dtype=torch.float32).reshape(rows, cols, 3)
    levels = torch.randint(0, rows, (num_envs,), generator=torch.Generator().manual_seed(1))
    types = torch.randint(0, cols, (num_envs,), generator=torch.Generator().manual_seed(2))
    terrain = SimpleNamespace(terrain_origins=origins, terrain_levels=levels, terrain_types=types, env_origins=origins[levels, types].clone())
    terrain.cfg = SimpleNamespace(terrain_generator=SimpleNamespace(num_cols=cols, sub_terrains={n: SimpleNamespace(proportion=p) for n, p in columns.CONTINUOUS.items()}))
    scene = SimpleNamespace(terrain=terrain)
    scene.env_origins = terrain.env_origins

    return SimpleNamespace(scene=scene)


def test_default_hashes_are_unchanged():
    lv, ty = ft.fixed_assignment(64, 10, 23)

    assert ft.assignment_sha256(lv, ty)[:12] == OLD64 and sorted(set(lv.tolist())) == [0, 1, 2]
    lv, ty, flat, _ = PT.pick(PT.column_names(columns.CONTINUOUS, 23), 16)

    assert ft.assignment_sha256(lv, ty)[:12] == OLD16 and set(lv.tolist()) == {0}


def test_default_apply_records_keep_the_old_hash_and_add_the_levels():
    rec = ft.apply(_raw(64))

    assert rec["assignment_sha256"][:12] == OLD64 and rec["levels"] == [0, 1, 2] and rec["fixed_level"] is None and rec["levels_used"] == 3
    rec = PT.apply_to(_raw(16))

    assert rec["assignment_sha256"][:12] == OLD16 and rec["levels"] == [0] and rec["fixed_level"] == 0 and rec["levels_used"] == 1


def test_level_6_puts_every_env_on_level_6_and_keeps_the_column_kinds():
    raw = _raw(64)
    rec = ft.apply(raw, 6)
    base_lv, base_ty = ft.fixed_assignment(64, 10, 23)

    assert rec["levels"] == [6] and rec["fixed_level"] == 6 and rec["assignment_sha256"][:12] != OLD64
    assert (raw.scene.terrain.terrain_levels == 6).all() and np.array_equal(raw.scene.terrain.terrain_types.numpy(), base_ty)          # 열 종류 배열은 그대로
    assert torch.equal(raw.scene.terrain.env_origins, raw.scene.terrain.terrain_origins[6, raw.scene.terrain.terrain_types])
    raw = _raw(16)
    rec = PT.apply_to(raw, 6)
    tiles = rec["tiles"]

    assert rec["levels"] == [6] and all(t["level"] == 6 for t in tiles) and rec["assignment_sha256"][:12] != OLD16
    assert [t["col"] for t in tiles] == [18] * 4 + [19] * 4 + [14] * 4 + [17] * 4 and [t["kind"] for t in tiles][::4] == ["hf_pyramid_slope", "hf_pyramid_slope", "random_rough", "random_rough"]
    assert (raw.scene.terrain.terrain_levels == 6).all() and "더는 평지가 아니다" in rec["flat_note"]


def test_describe_says_the_level_and_the_old_wording_stays_for_the_default():
    assert "레벨 6 만" in ft.describe(ft.apply(_raw(64), 6)) and "레벨 0~2 만" in ft.describe(ft.apply(_raw(64)))
    assert "레벨 6" in ft.describe(PT.apply_to(_raw(16), 6))


def test_bad_levels_are_refused():
    for bad in (-1, 10, 99, 2.5, True):
        with pytest.raises(ValueError, match="고정 레벨"):
            ft.fixed_assignment(64, 10, 23, bad)
        with pytest.raises(ValueError, match="고정 레벨"):
            PT.apply_to(_raw(16), bad)


def test_cli_flags_and_script_wiring():
    for rel in ("eval/eval_map_modes.py", "eval/turn_probe.py"):
        src = (ROOT / "foothold_s2" / rel).read_text(encoding="utf-8")

        assert '"--fixed-level", type=int, default=None' in src
    assert "fixed_terrain.apply(raw, args.fixed_level)" in (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text(encoding="utf-8")
    tp = (ROOT / "foothold_s2/eval/turn_probe.py").read_text(encoding="utf-8")

    assert tp.count("probe_tiles.apply_to(raw, args.fixed_level)") == 2                     # 회전 시행 · 전진 걸음 구간 둘 다
    sh = (ROOT / "foothold_s2/eval/run_sb_eval.sh").read_text(encoding="utf-8")

    assert sh.count("$LEVEL_FLAG") == 2 and 'LEVEL_FLAG="--fixed-level $LEVEL"' in sh
    for rel in ("eval/eval_map_modes.py", "eval/turn_probe.py"):
        ast.parse((ROOT / "foothold_s2" / rel).read_text(encoding="utf-8"))
