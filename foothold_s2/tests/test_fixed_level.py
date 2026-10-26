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


def test_level_without_fixed_terrain_or_out_of_range_is_refused_before_the_app_launches():
    for rel in ("eval/eval_map_modes.py", "eval/turn_probe.py"):
        src = (ROOT / "foothold_s2" / rel).read_text(encoding="utf-8")
        launch = src.index("app = AppLauncher(args).app")

        assert src.index("args.fixed_level is not None and not args.fixed_terrain") < launch
        assert src.index("not 0 <= args.fixed_level <= 9") < launch
        assert src.count("--fixed-level 은 --fixed-terrain 과 같이만 쓴다") == 1


def _fake(sha, extra):
    from foothold_s2.tests.test_fixed_terrain import _fake_result

    res = _fake_result()
    res["fixed_terrain"] = {"rows": 10, "cols": 23, "levels_used": 3, "num_envs": 64, "assignment_sha256": sha, **extra}

    return res


def test_compare_accepts_an_old_record_and_a_new_one_with_the_same_array_and_refuses_another_array():
    from foothold_s2.eval import compare_map_modes as cmp

    old, new = _fake("ab" * 32, {}), _fake("ab" * 32, {"levels": [0, 1, 2], "fixed_level": None})
    cmp.check_same_conditions({"old": old, "new": new})                                       # 기록 칸만 늘었고 배열 SHA 가 같으면 같은 칸
    other = _fake("cd" * 32, {"levels": [6], "fixed_level": 6})

    with pytest.raises(ValueError, match="fixed_terrain"):
        cmp.check_same_conditions({"old": old, "other": other})
    for key, val in (("rows", 9), ("cols", 20), ("num_envs", 16)):
        bad = _fake("ab" * 32, {})
        bad["fixed_terrain"][key] = val

        with pytest.raises(ValueError, match="fixed_terrain"):
            cmp.check_same_conditions({"old": old, "bad": bad})


def test_reference_column_follows_the_same_array_rule():
    from foothold_s2.eval import compare_map_modes as cmp
    from foothold_s2.tests.test_eval_g0_reference import _g0

    first = _fake("ab" * 32, {"levels": [0, 1, 2], "fixed_level": None})
    ref = _g0()
    ref["fixed_terrain"] = _fake("ab" * 32, {})["fixed_terrain"]                                # 옛 기록(칸 수 적음) + 같은 배열
    cmp.check_reference({"parent": first}, ref)
    ref["fixed_terrain"] = _fake("cd" * 32, {})["fixed_terrain"]

    with pytest.raises(ValueError, match="fixed_terrain"):
        cmp.check_reference({"parent": first}, ref)


# ---------------------------------------------------------------- 듬성 지형 고정 칸 (--terrain-set sparse50)
SPARSE64 = {0: "8ec13148fdc6", 1: "ac5ad60c8e08", 2: "a6d2cd008188", 6: "c876380b3ff7"}          # 64 env 칸 해시 앞 12 자리(고정 기록)
NAMES50 = columns.column_types(columns.FULL, columns.FULL_COLS)


def _raw50(num_envs):
    raw = _raw(num_envs, 10, 50)
    raw.scene.terrain.cfg.terrain_generator.sub_terrains = {n: SimpleNamespace(proportion=p) for n, p in columns.FULL.items()}

    return raw


@pytest.mark.parametrize("level", [0, 1, 2, 6])
def test_sparse_fixed_cells_use_only_the_five_sparse_names_at_the_asked_level_and_the_hash_is_pinned(level):
    raw = _raw50(64)
    rec = ft.apply_sparse(raw, level)
    kinds = {t["kind"] for t in rec["tiles"]}

    assert kinds == {"stepping_stones_low", "stepping_stones_high", "balance_beams", "stepping_beams", "gaps"}        # 연속 7 종과 flat 은 없다
    assert set(rec["levels"]) == {level} and rec["fixed_level"] == level and rec["terrain_set"] == "sparse50"
    assert rec["assignment_sha256"][:12] == SPARSE64[level] and rec["num_envs"] == 64 and rec["cols"] == 50
    assert all(NAMES50[t["col"]] == t["kind"] for t in rec["tiles"]) and sorted({t["col"] for t in rec["tiles"]}) == list(range(23, 48))
    assert raw.scene.terrain.terrain_levels.eq(level).all()


def test_sparse_fixed_cells_refuse_a_23_column_generator_and_a_bad_level():
    with pytest.raises(RuntimeError, match="50 열"):
        ft.apply_sparse(_raw(64, 10, 23), 0)
    with pytest.raises(ValueError, match="고정 레벨"):
        ft.apply_sparse(_raw50(64), 10)


def test_default_hashes_are_untouched_by_the_sparse_option():
    levels, types = ft.fixed_assignment(64, 10, 23)

    assert ft.assignment_sha256(levels, types)[:12] == OLD64


def test_eval_map_modes_wires_the_sparse_set_and_refuses_it_without_a_level_before_kit():
    src = (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text(encoding="utf-8")

    assert src.index('parser.error("--terrain-set sparse50') < src.index("AppLauncher(args).app")
    assert "build_generator({**continuous_subterrains(), **sparse_terrains.sparse_subterrains()}, columns.FULL_COLS)" in src
    assert "fixed_terrain.apply_sparse(raw, args.fixed_level) if parser_sparse" in src
