"""듬성 칸 종류별 집계 (SONNET-X26j). 답을 아는 가짜 배열. CPU."""

import json
from pathlib import Path

import numpy as np

from foothold_s2.eval import kind_stats as K

ROOT = Path(__file__).resolve().parents[2]
DT = 0.02


def _arrays(S=300):
    kinds = ["gaps", "gaps", "gaps", "balance_beams", "balance_beams"]
    fwd = np.zeros((S, 5))
    fwd[:, 0] = np.linspace(0, 6.0, S)                          # 6 s 안에 6 m: 건넘 (절반 = 4 m)
    fwd[:, 1] = np.linspace(0, 3.9, S)                          # 3.9 m: 못 건넘
    fwd[250:, 2] = 5.0                                          # 5 s 지나서 5 m: 6 s 안(300 step)이라 건넘
    fwd[:, 3] = np.linspace(0, 4.0, S)                          # 정확히 절반: 건넘 (>=)
    fwd[:, 4] = 1.0
    vx = np.tile(np.array([1.0, 0.5, 0.0, 0.7, 0.2]), (S, 1))
    alive = np.ones((S, 5), dtype=bool)
    alive[100:, 1] = False                                      # 1 번 env 는 100 step 에 쓰러짐
    alive[:, 4] = np.arange(S)[:, None][:, 0] < 50

    return kinds, vx, fwd, alive


def test_per_kind_counts_alive_median_and_crossed_by_a_known_input():
    kinds, vx, fwd, alive = _arrays()
    out = K.by_kind(kinds, vx, fwd, alive, DT, 8.0)

    assert out["gaps"]["envs"] == 3 and out["gaps"]["crossed"] == 2 and out["gaps"]["alive_at_end"] == 2
    assert out["balance_beams"]["envs"] == 2 and out["balance_beams"]["crossed"] == 1 and out["balance_beams"]["alive_at_end"] == 1
    assert abs(out["gaps"]["body_vx_integral_median_m"] - np.median([6.0, 0.5 * 100 * DT, 0.0])) < 1e-9        # 중앙값 = 1.0 (살아 있던 구간만 적분)
    assert list(out) == ["gaps", "balance_beams"]


def test_the_threshold_comes_from_the_tile_length_and_the_window_is_six_seconds():
    kinds, vx, fwd, alive = _arrays()

    assert K.by_kind(kinds, vx, fwd, alive, DT, 12.0)["gaps"]["crossed"] == 1                  # 칸 길이 12 m 면 절반 6 m: 0 번 env 만(6.0 >= 6.0)
    late = fwd.copy()
    late[:, 0] = 0.0
    late[299, 0] = 9.0

    assert K.by_kind(kinds, vx, late, alive, DT, 8.0, window_s=5.0)["gaps"]["crossed"] == 0       # 5 s 창(250 step)이면 마지막 step 의 9 m 와 250 step 뒤 5 m 는 안 센다
    assert K.by_kind(kinds, vx, late, alive, DT, 8.0)["gaps"]["crossed"] == 2                        # 기본 6 s 창(300 step)이면 둘 다 센다


def test_the_files_roundtrip_gives_the_same_numbers(tmp_path):
    kinds, vx, fwd, alive = _arrays()
    np.savez(tmp_path / "a.npz", vx=vx, fwd=fwd, alive=alive, dt=DT, tile_len_m=8.0)
    json.dump({"fixed_terrain": {"tiles": [{"kind": k} for k in kinds]}}, open(tmp_path / "m.json", "w"))

    assert K.from_files(str(tmp_path / "m.json"), str(tmp_path / "a.npz"), "eval_gt", "fwd0.5") == K.by_kind(kinds, vx, fwd, alive, DT, 8.0)


def test_eval_adds_the_columns_only_for_the_sparse_set_and_reads_the_tile_length_from_the_cfg():
    src = (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text(encoding="utf-8")

    assert "if parser_sparse:                                                                # 새 키" in src
    assert "tile_len = float(raw.scene.terrain.cfg.terrain_generator.size[0])" in src and "tile_len = 4" not in src and "tile_len = 8" not in src
    row_keys = src.split('row = {"body_vx_integral_median_m"')[1].split("}\n")[0]

    assert "by_kind" not in row_keys                                                         # 기존 키 묶음은 그대로, by_kind 는 듬성에서만 덧붙는다


def test_a_teleport_after_falling_does_not_count_as_crossing():
    S = 300
    fwd = np.zeros((S, 1))
    fwd[120:, 0] = 7.0                                          # 쓰러져 reset 된 뒤 다른 칸에서 7 m 처럼 보이는 위치
    alive = np.ones((S, 1), dtype=bool)
    alive[100:, 0] = False
    out = K.by_kind(["gaps"], np.zeros((S, 1)), fwd, alive, DT, 8.0)

    assert out["gaps"]["crossed"] == 0 and out["gaps"]["fwd_max_median_m"] == 0.0


def test_eval_levels_the_start_yaw_for_the_sparse_set_and_records_the_hashes_of_the_files_it_read():
    src = (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text(encoding="utf-8")
    sh = (ROOT / "foothold_s2/eval/run_sparse_eval.sh").read_text(encoding="utf-8")

    assert "st[:, 3:7] = torch.tensor([1.0, 0.0, 0.0, 0.0]" in src and "시작 yaw 를 0 으로 맞추지 못했다" in src and "SOURCE_SHA256" in src
    assert 'status --short -- foothold_s2' in sh and sh.index("exit 3") < sh.index("KIT=") or sh.index("exit 3") < sh.index("for LV in")


def test_source_hashes_cover_every_foothold_module_that_was_loaded_by_the_end():
    src = (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text(encoding="utf-8")

    assert 'startswith("foothold_s2")' in src and src.index('res["source_sha256"] = {m.__name__') > src.index("MAPMODE_DONE") - 5000 and src.index('res["source_sha256"] = {m.__name__') < src.index("MAPMODE_DONE")
