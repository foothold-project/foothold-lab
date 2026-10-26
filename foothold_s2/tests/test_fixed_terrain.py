"""평가용 고정 지형 칸 (SONNET-X25). CPU 만."""

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from foothold_s2.eval import compare_map_modes as cmp
from foothold_s2.eval import fixed_terrain as ft
from foothold_s2.tests.test_ex3031_window1 import _fake_result
from foothold_s2.tests.test_eval_g0_reference import _g0

ROOT = Path(__file__).resolve().parents[2]


def _raw(num_envs=64, rows=10, cols=20, seed=0):
    g = torch.Generator().manual_seed(seed)
    origins = torch.randn(rows, cols, 3, generator=g)
    levels = torch.randint(0, rows, (num_envs,), generator=g)                # task 마다 다른 초기 칸(실제 상황)
    types = torch.randint(0, cols, (num_envs,), generator=g)
    terrain = SimpleNamespace(terrain_origins=origins, terrain_levels=levels, terrain_types=types, env_origins=origins[levels, types].clone())
    scene = SimpleNamespace(terrain=terrain)
    scene.env_origins = terrain.env_origins                                 # InteractiveScene.env_origins 는 terrain 의 것을 돌려준다

    return SimpleNamespace(scene=scene)


def test_assignment_is_deterministic_and_covers_low_levels_and_all_columns():
    lv, ty = ft.fixed_assignment(64, 10, 20)

    assert lv.max() == ft.LEVELS_USED - 1 and ty.max() == 19 and (lv[:20] == 0).all() and (lv[20:40] == 1).all() and (ty[:20] == np.arange(20)).all()
    assert ft.assignment_sha256(*ft.fixed_assignment(64, 10, 20)) == ft.assignment_sha256(lv, ty)


def test_different_tasks_with_different_initial_tiles_get_the_same_hash_after_apply():
    a, b = _raw(seed=1), _raw(seed=2)

    assert not torch.equal(a.scene.terrain.terrain_levels, b.scene.terrain.terrain_levels)          # 적용 전에는 칸이 다르다(관문이 거절하던 상황)
    ia, ib = ft.apply(a), ft.apply(b)

    assert ia["assignment_sha256"] == ib["assignment_sha256"] and torch.equal(a.scene.terrain.terrain_levels, b.scene.terrain.terrain_levels)
    assert torch.equal(a.scene.terrain.env_origins, a.scene.terrain.terrain_origins[a.scene.terrain.terrain_levels, a.scene.terrain.terrain_types])


def test_grid_mismatch_is_refused_not_called_the_same_tile():
    with pytest.raises(ValueError, match="행 수"):
        ft.fixed_assignment(64, 2, 20)
    assert ft.assignment_sha256(*ft.fixed_assignment(64, 10, 20)) != ft.assignment_sha256(*ft.fixed_assignment(64, 10, 18))


def test_apply_refuses_when_scene_origins_diverge():
    raw = _raw()
    raw.scene.env_origins = torch.zeros_like(raw.scene.env_origins)

    with pytest.raises(RuntimeError, match="env_origins"):
        ft.apply(raw)


def _with_fixed(res):
    out = json.loads(json.dumps(res))
    out["fixed_terrain"] = {"rows": 10, "cols": 20, "levels_used": 3, "num_envs": 64, "assignment_sha256": "ab" * 32}

    return out


def test_compare_requires_the_same_fixed_terrain_record_for_columns_and_reference():
    base = _with_fixed(_fake_result())

    cmp.table({"parent": base, "ex30": _with_fixed(_fake_result())})
    with pytest.raises(ValueError, match="fixed_terrain"):
        cmp.table({"parent": base, "ex30": _fake_result()})                                   # 한쪽만 고정 칸
    other = _with_fixed(_fake_result())
    other["fixed_terrain"]["assignment_sha256"] = "cd" * 32

    with pytest.raises(ValueError, match="fixed_terrain"):
        cmp.table({"parent": base, "ex30": other})
    g0 = _with_fixed(_g0())

    assert "지도 없음 참조 열" in cmp.table({"parent": base}, g0)
    with pytest.raises(ValueError, match="fixed_terrain"):
        cmp.table({"parent": base}, _g0())


def test_eval_script_applies_it_after_reset_and_before_the_hash_and_shell_scripts_pass_the_flag():
    src = (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text(encoding="utf-8")

    assert '"--fixed-terrain"' in src and src.index("fixed_terrain.apply(raw, args.fixed_level)") < src.index("th = hashlib.sha256(") and src.count("env.reset()") == 2
    assert "고정 지형 칸이 reset 뒤에 바뀌었다" in src
    for name in ("run_eval_map_modes.sh", "run_eval_g0_reference.sh"):
        text = (ROOT / "foothold_s2" / name).read_text(encoding="utf-8")

        assert "--fixed-terrain" in text and "$FIXED" in text and "\r" not in text


def test_table_header_states_what_was_fixed_and_what_it_does_not_represent():
    base = _with_fixed(_fake_result())
    line = ft.describe(base["fixed_terrain"])

    assert "고정 칸 · 레벨 0~2 만(64 env 배치 24/20/20) · 종류 = env 번호 % 20 열" in line
    rec = {"rows": 10, "cols": 23, "levels_used": 3, "num_envs": 64, "assignment_sha256": "ab" * 32}
    exact = ft.describe(rec)

    assert exact.startswith("고정 칸 · 레벨 0~2 만(64 env 배치 23/23/18) · 종류 = env 번호 % 23 열 · 학습 분포(레벨 0~9) 대표 아님")
    out = cmp.table({"parent": base})

    assert "지형: 고정 칸" in out and "대표 아님" in out
    assert "고정 안 함" in cmp.table({"parent": _fake_result()})
    g0 = _with_fixed(_g0())

    assert out.count("대표 아님") == 1 and "지도 없음 참조 열" in cmp.table({"parent": base}, g0)


def test_main_runs_with_only_a_parent_and_a_reference(tmp_path, capsys):
    p, g = tmp_path / "p.json", tmp_path / "g.json"
    p.write_text(json.dumps(_with_fixed(_fake_result())), encoding="utf-8")
    g.write_text(json.dumps(_with_fixed(_g0())), encoding="utf-8")
    cmp.main(["x", str(p), "--reference", str(g)])

    assert "지도 없음 참조 열" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        cmp.main(["x", str(p)])


def test_eval_script_asserts_root_is_near_the_env_origin_after_reset():
    src = (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text(encoding="utf-8")

    assert "START_OFFSET_MAX_M = 0.5" in src and "root_pos_w[:, :2] - raw.scene.env_origins[:, :2]" in src and "start_offset_max_m" in src
    assert src.index("fixed_terrain.apply(raw, args.fixed_level)") < src.index("START_OFFSET_MAX_M + 1.0e-3") < src.index("th = hashlib.sha256(")
