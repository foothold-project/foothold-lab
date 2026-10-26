"""듬성 칸 기하 재현 (SONNET-X26n) · STEPS 연동. CPU, 생성기 흉내(Kit 없이 Isaac 의 난이도 규칙을 되풀이)."""

from pathlib import Path

import numpy as np
import pytest

from foothold_s2.eval import geometry_hash as GH
from foothold_s2.eval import kind_stats as K
from foothold_s2.terrains import columns
from foothold_s2.terrains import sparse_terrains as sp

ROOT = Path(__file__).resolve().parents[2]
ISAAC_GEN = Path("C:/isaac/IsaacLab/source/isaaclab/isaaclab/terrains/terrain_generator.py")
NAMES = columns.column_types(columns.FULL, columns.FULL_COLS)
ROWS = 10


def _generate(seed):
    """Isaac `_generate_curriculum_terrains` 의 열 우선 · 줄 순서와 난이도 식(줄 + U(0,1)) / 줄 수 를 되풀이해 SideTable 에 기록한다."""
    rng = np.random.default_rng(seed)
    table = sp.SideTable()

    for col, name in enumerate(NAMES):
        for row in range(ROWS):
            d = (row + rng.uniform()) / ROWS

            if name in sp.KINDS:
                table.record(name, d, sp.build_tile(name, d))

    return table


def _rec(table, cells):
    return GH.geometry_record(table, NAMES, ROWS, cells)


def test_the_replicated_difficulty_rule_is_what_the_installed_isaac_does():
    if not ISAAC_GEN.exists():
        pytest.skip("설치 Isaac Lab 소스 없음")
    src = ISAAC_GEN.read_text(encoding="utf-8")

    assert "difficulty = (sub_row + self.np_rng.uniform()) / self.cfg.num_rows" in src and "seed = np.random.get_state()[1][0]" in src
    assert "for sub_col in range(self.cfg.num_cols)" in src and src.index("for sub_col in range") < src.index("for sub_row in range")


def test_same_seed_gives_the_same_geometry_hashes_and_another_seed_or_level_gives_another():
    cells = [(0, 23), (0, 30), (0, 35), (0, 45), (2, 23), (6, 23), (6, 35)]
    a, b = _rec(_generate(GH.SPARSE_GEOMETRY_SEED), cells), _rec(_generate(GH.SPARSE_GEOMETRY_SEED), cells)

    assert a == b and a["seed"] == GH.SPARSE_GEOMETRY_SEED                                    # 같은 칸 두 번: 같은 해시(칸별 · 전체)
    c = _rec(_generate(GH.SPARSE_GEOMETRY_SEED + 1), cells)

    assert c["total"] != a["total"] and sum(c["per_cell"][k] != a["per_cell"][k] for k in a["per_cell"]) >= 5       # seed 를 바꾸면 기하가 달라진다(고정하는 까닭)
    assert len({a["per_cell"][k] for k in a["per_cell"]}) == len(cells)                         # 레벨 · 열이 다르면 다른 해시
    assert a["per_cell"]["L0c23"] != a["per_cell"]["L6c23"] and a["per_cell"]["L0c23"] != a["per_cell"]["L0c30"]


def test_a_missing_or_shifted_call_order_is_refused():
    t = _generate(1)
    t.calls.pop(0)

    with pytest.raises(RuntimeError):
        GH.tiles_by_cell(t, NAMES, ROWS)
    t2 = _generate(1)
    t2.calls[0], t2.calls[1] = t2.calls[1], t2.calls[0]                                       # 같은 종류 줄 순서가 바뀜 -> 레벨 어긋남

    with pytest.raises(RuntimeError, match="호출 순서"):
        GH.tiles_by_cell(t2, NAMES, ROWS)


def test_eval_fixes_the_generator_seed_resets_the_side_table_and_records_the_hash():
    src = (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text(encoding="utf-8")

    assert "seed=geometry_hash.SPARSE_GEOMETRY_SEED" in src and 'res["terrain_geometry_sha256"] = _gh.geometry_record(' in src
    assert src.index("sparse_terrains.SIDE_TABLE.__init__()") < src.index("seed=geometry_hash.SPARSE_GEOMETRY_SEED") < src.index("gym.make(args.task")


# ---------------------------------------------------------------- STEPS


def test_steps_argument_defaults_to_300_and_reaches_the_evaluator():
    sh = (ROOT / "foothold_s2/eval/run_sparse_eval.sh").read_text(encoding="utf-8")

    assert 'STEPS="${STEPS:-300}"' in sh and '--steps "$STEPS"' in sh and "--steps 300" not in sh


def test_each_command_is_held_for_every_step_of_the_run_and_the_crossing_window_follows_the_run_length():
    src = (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text(encoding="utf-8")
    loop = src.split("for k in range(S):")[1].split("alive = alive & ~dones.bool()")[0]

    assert "term.vel_command_b[:, :3] = torch.tensor(cmd, device=dev)" in loop                  # 매 step 같은 명령으로 덮어씀(전 구간 같은 명령)
    assert "resampling_time_range = (1.0e9, 1.0e9)" in src
    call = next(ln for ln in src.splitlines() if "kind_stats.by_kind(kinds" in ln)

    assert "window_s" not in call and "pos=POS" in call                                         # 창을 따로 주지 않는다 = 기록 전체(STEPS)
    S, dt = 750, 0.02
    fwd = np.linspace(0.0, 7.5, S)[:, None]                                                      # 15 s 동안 1.0 m/s 로 직진: 6.5 m 는 step 650 쯤
    pos = np.zeros((S, 1, 3))
    pos[:, 0, 0] = fwd[:, 0]
    out = K.by_kind(["gaps"], np.ones((S, 1)), fwd, np.ones((S, 1), dtype=bool), dt, pos=pos)

    assert out["gaps"]["crossed"] == 1 and "15" in out["gaps"]["crossed_rule"]
    short = K.by_kind(["gaps"], np.ones((300, 1)), fwd[:300], np.ones((300, 1), dtype=bool), dt, pos=pos[:300])

    assert short["gaps"]["crossed"] == 0                                                         # 300 step 는 닿을 수 없다(기본값 그대로의 한계)
