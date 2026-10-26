"""듬성 칸 종류별 집계 (SONNET-X26j · X26m). 답을 아는 가짜 배열. CPU."""

import json
from pathlib import Path

import numpy as np

from foothold_s2.eval import kind_stats as K
from foothold_s2.eval import start_sheet as ss

ROOT = Path(__file__).resolve().parents[2]
DT = 0.02
S = 400                                                         # 8 s
REF = ss.REFERENCE_M
STAND = 0.34                                                    # 서 있는 몸 z(출발 단 윗면 0 기준)


def _case(fwd_end, z_drop_at=None, z_drop=0.24, die_at=None, teleport=None):
    """env 하나: 전진 거리가 0 에서 fwd_end 까지 직선 증가. z_drop_at 번째 step 에 몸이 z_drop 만큼 내려간다."""
    f = np.linspace(0.0, fwd_end, S)
    z = np.full(S, STAND)
    a = np.ones(S, dtype=bool)

    if z_drop_at is not None:
        z[z_drop_at:] = STAND - z_drop
    if die_at is not None:
        a[die_at:] = False
    if teleport is not None:
        f[teleport[0]:] = teleport[1]

    return f, z, a


def _pack(cases):
    fwd = np.stack([c[0] for c in cases], axis=1)
    z = np.stack([c[1] for c in cases], axis=1)
    alive = np.stack([c[2] for c in cases], axis=1)
    pos = np.zeros((S, len(cases), 3))
    pos[:, :, 0], pos[:, :, 2] = fwd, z

    return fwd, pos, alive, np.full_like(fwd, 0.7)


def test_crossing_is_reaching_the_arrival_ledge_while_alive_and_on_the_footing():
    cases = [_case(7.0),                                      # 0 끝까지 걸음: 건넘
             _case(6.0),                                      # 1 6 m 까지만: 도착 단(6.5 m) 못 닿음
             _case(7.0, z_drop_at=100),                       # 2 100 step(1.4 m 지점)에 구덩이로 내려가 대각선으로 7 m 까지 감: 건넘 아님
             _case(7.0, die_at=150),                          # 3 쓰러짐(종료)
             _case(2.0, teleport=(300, 9.0)),                 # 4 쓰러져 reset 된 뒤 순간이동 위치 9 m: 건넘 아님
             _case(7.0, z_drop_at=399, z_drop=0.05)]          # 5 마지막 step 에 5 cm 내려감(오차 안): 건넘
    cases[4] = (cases[4][0], cases[4][1], np.arange(S) < 300)
    fwd, pos, alive, vx = _pack(cases)
    kinds = ["gaps", "gaps", "balance_beams", "balance_beams", "stepping_beams", "stepping_beams"]
    out = K.by_kind(kinds, vx, fwd, alive, DT, pos=pos)

    assert out["gaps"]["crossed"] == 1 and out["gaps"]["fell"] == 0 and out["gaps"]["envs"] == 2
    assert out["balance_beams"]["crossed"] == 0 and out["balance_beams"]["fell"] == 1                         # 2 번은 떨어짐, 3 번은 쓰러짐(종료)
    assert out["stepping_beams"]["crossed"] == 1 and out["stepping_beams"]["fell"] == 0
    assert out["gaps"]["fall_test"] is True and f"{REF:g}" in out["gaps"]["crossed_rule"]


def test_the_threshold_is_the_reference_distance_from_the_sheet_and_not_hardcoded():
    assert K.by_kind.__defaults__[0] == ss.REFERENCE_M == 6.5
    src = (ROOT / "foothold_s2/eval/kind_stats.py").read_text(encoding="utf-8")

    assert "6.5" not in src.split("def by_kind")[1] and "threshold_m: float = ss.REFERENCE_M" in src


def test_a_fall_stays_a_fall_even_if_the_body_climbs_back_up():
    f = np.linspace(0.0, 7.0, S)
    z = np.full(S, STAND)
    z[50:150] = 0.04                                          # 구덩이에 내려갔다가 올라옴
    pos = np.zeros((S, 1, 3))
    pos[:, 0, 0], pos[:, 0, 2] = f, z
    out = K.by_kind(["gaps"], np.full((S, 1), 0.7), f[:, None], np.ones((S, 1), dtype=bool), DT, pos=pos)

    assert out["gaps"]["crossed"] == 0 and out["gaps"]["fell"] == 1


def test_without_the_height_array_the_result_says_it_could_not_test_the_fall():
    fwd, pos, alive, vx = _pack([_case(7.0)])
    out = K.by_kind(["gaps"], vx, fwd, alive, DT)

    assert out["gaps"]["crossed"] == 1 and out["gaps"]["fall_test"] is False


def test_drop_tolerance_matches_the_terrain_edge_threshold():
    from foothold_s2.terrains import sparse_terrains

    assert K.EDGE_DROP_M == sparse_terrains.EDGE_DROP_M


def test_recompute_pairs_each_npz_with_its_json_and_skips_a_folder_without_one(tmp_path):
    fwd, pos, alive, vx = _pack([_case(7.0), _case(3.0)])
    (tmp_path / "ok").mkdir()
    (tmp_path / "bad").mkdir()
    np.savez(tmp_path / "ok" / "arrays_a.npz", vx=vx, fwd=fwd, alive=alive, dt=DT, tile_len_m=8.0, pos=pos)
    np.savez(tmp_path / "bad" / "arrays_a.npz", vx=vx, fwd=fwd, alive=alive, dt=DT, tile_len_m=8.0, pos=pos)
    json.dump({"fixed_terrain": {"tiles": [{"kind": "gaps"}, {"kind": "gaps"}]}}, open(tmp_path / "ok" / "map_modes.json", "w"))
    out = K.recompute([str(tmp_path / "*" / "arrays_*.npz")], str(tmp_path / "t.json"))
    ok, bad = out[str(tmp_path / "ok" / "arrays_a.npz")], out[str(tmp_path / "bad" / "arrays_a.npz")]

    assert ok["gaps"]["crossed"] == 1 and ok["gaps"]["envs"] == 2 and "error" in bad and (tmp_path / "t.json").exists()


def test_eval_adds_the_columns_only_for_the_sparse_set_and_passes_the_height_array():
    src = (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text(encoding="utf-8")

    assert "if parser_sparse:                                                                # 새 키" in src
    assert "kind_stats.by_kind(kinds, vx, FW.cpu().numpy(), al, dt, pos=POS.cpu().numpy(), start_support=START_SUPPORT)" in src and "start_support=START_SUPPORT)" in src
    row_keys = src.split('row = {"body_vx_integral_median_m"')[1].split("}\n")[0]

    assert "by_kind" not in row_keys


def test_eval_levels_the_start_yaw_for_the_sparse_set_and_records_the_hashes_of_the_files_it_read():
    src = (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text(encoding="utf-8")
    sh = (ROOT / "foothold_s2/eval/run_sparse_eval.sh").read_text(encoding="utf-8")

    assert "st[:, 3:7] = torch.tensor([1.0, 0.0, 0.0, 0.0]" in src and "시작 yaw 를 0 으로 맞추지 못했다" in src
    assert 'status --short -- foothold_s2' in sh and sh.index("exit 3") < sh.index("for LV in")


def test_source_hashes_follow_the_spec_name_so_a_dash_m_main_script_is_included():
    src = (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text(encoding="utf-8")
    key = src.split("def _module_key")[1].split("res[\"source_sha256\"] = {}")[0]

    assert "__spec__" in key and "getattr(spec, \"name\", None)" in key
    ns = {}
    exec("def _module_key" + key.split("\n\n\n")[0], ns)                                                   # 함수 본문만 떼어 실행
    mod = type("M", (), {"__name__": "__main__", "__spec__": type("S", (), {"name": "foothold_s2.eval.eval_map_modes"})()})()

    assert ns["_module_key"](mod) == "foothold_s2.eval.eval_map_modes"
    assert ns["_module_key"](type("M", (), {"__name__": "foothold_s2.runners.start_runner", "__spec__": None})()) == "foothold_s2.runners.start_runner"


def test_a_pit_start_is_not_a_crossing_and_is_counted_as_a_start_off_the_footing():
    """reviewer 반례: 빔 밖 구덩이에서 시작해 바닥을 걸어 도착 단에 오른다. 시작 높이 기준이면 낙하에 안 걸렸다. 절대 문턱이면 건넘 아님."""
    f = np.linspace(0.0, 7.0, S)
    zs = np.stack([np.full(S, 0.11), np.full(S, STAND)], axis=1)         # 0 구덩이 바닥을 걷는다 · 1 발판 위
    fwd = np.stack([f, f], axis=1)
    pos = np.zeros((S, 2, 3))
    pos[:, :, 0], pos[:, :, 2] = fwd, zs
    pos[0, 1, 0] = K.start_edge_x() - 0.1                                # 1 번은 출발 단 끝 0.1 m 에서 시작
    out = K.by_kind(["balance_beams"] * 2, np.full((S, 2), 0.7), fwd, np.ones((S, 2), dtype=bool), DT, pos=pos)["balance_beams"]

    assert out["crossed"] == 1 and out["fell"] == 1 and out["start_fell_within_1s"] == 1 and out["start_edge"] == 1 and "start_offbeam" not in out


def test_the_start_platform_top_is_read_from_the_tile_geometry_and_not_hardcoded():
    from foothold_s2.terrains import sparse_terrains

    assert K.start_top_z() == 0.0 and K.start_edge_x() == ss.ZONE_X[0] - sparse_terrains.SPAWN_XY[0]
    assert "0.25" not in (ROOT / "foothold_s2/eval/kind_stats.py").read_text(encoding="utf-8").split("def by_kind")[1].split("def from_files")[0]


def test_start_offbeam_compares_the_start_lane_with_the_beam_lanes_of_the_pit_zone_for_real_start_positions():
    """출발 단은 칸 x 0~1 폭 전체라 실제 시작(x 0.5 +-0.5, y 4.0 +-0.5)은 늘 발판 위다. 빔 밖은 시작 y 줄에 구덩이 구역(칸 x 1~7) 발판이 없는가로 가른다(reviewer 수용: 줄 12 · 16 잡힘, 38 빠짐)."""
    from foothold_s2.eval import geometry_hash as G
    from foothold_s2.terrains import sparse_terrains as sp

    found = None

    for d in np.linspace(0.02, 0.98, 40):                                  # 시작 y 범위 안에 빔 줄과 빈 줄이 둘 다 있는 balance 칸 하나를 찾는다
        tile = sp.build_tile("balance_beams", float(d))
        g = sp.height_grid(tile.boxes)
        i0, i1 = int(round(1.0 / sp.MASK_RES)), int(round(7.0 / sp.MASK_RES))
        ys = np.arange(g.shape[1]) * sp.MASK_RES
        lane = np.array([g[i0:i1, k].max() for k in range(g.shape[1])])
        rel = ys - sp.SPAWN_XY[1]
        inside = np.abs(rel) <= 0.5
        on, off = inside & (lane >= -0.05), inside & (lane < -0.05)

        if on.any() and off.any():
            found = (tile, float(rel[on][0]), float(rel[off][0]), float(d))
            break
    assert found is not None
    tile, y_on, y_off, d = found
    tiles = [{"level": sp.level_of(d), "col": 0}] * 3
    rel_xy = np.array([[0.4, y_on], [-0.4, y_off], [0.0, y_off]])           # 실제 시작 분포 안(x +-0.5)
    real = G.tiles_by_cell
    G.tiles_by_cell = lambda *_a, **_k: {(sp.level_of(d), 0): tile}         # 칸 묶기 규칙은 test_geometry_hash 가 따로 시험한다
    try:
        sup = G.start_support(None, None, 10, tiles, rel_xy)
    finally:
        G.tiles_by_cell = real

    assert sup.tolist() == [True, False, False]
    pos = np.zeros((S, 3, 3))
    pos[:, :, 2] = STAND
    both = K.by_kind(["balance_beams"] * 2 + ["stepping_stones_low"], np.full((S, 3), 0.7), np.zeros((S, 3)), np.ones((S, 3), dtype=bool), DT, pos=pos, start_support=sup)
    out = both["balance_beams"]

    assert "start_offbeam" not in both["stepping_stones_low"]                                                  # 징검돌에는 내지 않는다(돌 사이 y 틈으로 부풀림)
    assert out["start_offbeam"] == 1 and out["start_fell_within_1s"] == 0                                   # 떨어지지 않아도 빔 밖 줄 시작은 센다


def test_threshold_sensitivity_marks_the_env_whose_crossing_changes_with_the_fall_threshold_and_the_metric_stays_at_0_25():
    f = np.linspace(0.0, 7.0, S)
    zs = np.stack([np.full(S, STAND), np.full(S, 0.255), np.full(S, 0.11)], axis=1)       # 발판 위 · 문턱 0.25 에 5 mm 위 · 구덩이 바닥
    fwd = np.stack([f] * 3, axis=1)
    pos = np.zeros((S, 3, 3))
    pos[:, :, 0], pos[:, :, 2] = fwd, zs
    out = K.by_kind(["gaps"] * 3, np.full((S, 3), 0.7), fwd, np.ones((S, 3), dtype=bool), DT, pos=pos)["gaps"]

    assert out["crossed"] == 2 and out["crossed_by_fall_threshold"] == {"0.225": 2, "0.25": 2, "0.275": 1} and out["threshold_sensitive_envs"] == [1]
    assert K.FALL_BELOW_TOP_M == 0.25


def test_start_support_is_computed_from_the_robot_start_pose_of_this_command_and_not_from_a_buffer_made_later():
    """reviewer 막음: START_SUPPORT 가 아직 안 만든 POS 를 읽으면 첫 명령에서 NameError, 읽혀도 앞 명령의 값이다."""
    src = (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text(encoding="utf-8")
    i = src.index("START_SUPPORT = _gh.start_support(")
    stmt = src[i:src.index(chr(10), src.index("offset 과 같은 값", i))]

    assert "POS" not in stmt and "robot.data.root_pos_w[:, :2] - raw.scene.env_origins[:, :2]" in stmt
    assert src.index("POS = torch.zeros(") > i                                               # POS 는 이 문장 뒤에 만들어진다: 이 문장이 POS 를 읽으면 안 된다
    assert src.index("START_SUPPORT = _gh.start_support(") < src.index("offset = (robot.data.root_pos_w")


def test_no_buffer_in_the_eval_loop_is_read_before_it_is_created():
    """가짜 env 시험은 Kit 경로를 안 타서 NameError 를 못 잡았다. 평가 파일 안에서 버퍼 이름을 처음 읽는 줄이 처음 만드는 줄보다 앞서면 실패."""
    import ast

    tree = ast.parse((ROOT / "foothold_s2/eval/eval_map_modes.py").read_text(encoding="utf-8"))
    names = ("POS", "FW", "YAW", "DN", "AL", "VX", "START_SUPPORT")
    first = {}

    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id in names:
            key = (n.id, "store" if isinstance(n.ctx, ast.Store) else "load")
            first[key] = min(first.get(key, n.lineno), n.lineno)

    for name in names:
        assert (name, "store") in first and first[(name, "store")] <= first[(name, "load")], (name, first)


def test_the_short_kit_check_exists_and_commands_are_filterable_before_kit():
    src = (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text(encoding="utf-8")
    sh = (ROOT / "foothold_s2/eval/smoke_sparse_start.sh").read_text(encoding="utf-8")

    assert src.index("--commands 는") < src.index("AppLauncher(args).app") and "--steps 50" in sh and "--commands fwd1.0" in sh
