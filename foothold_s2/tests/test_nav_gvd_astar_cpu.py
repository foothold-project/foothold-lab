from pathlib import Path

import numpy as np
import pytest

from foothold_s2.nav import grade_map as gm
from foothold_s2.nav import gvd_astar as ga
from foothold_s2.nav import room_generator as rg

NAV = Path(__file__).resolve().parents[1] / "nav"
TABLE = gm.load_grade_table(NAV / "grade_table_draft.yaml")


def _room_map(name, pose=False):
    return gm.make_grade_map(rg.build_room(rg.load_spec(NAV / "rooms" / f"{name}.yaml")), TABLE, pose)


def _cells(path):
    return (path.points / 0.1).astype(int)


def test_wall_room_detours_through_the_opening():
    g = _room_map("known_wall")
    p = ga.find_path(g, (5.0, 5.0), (15.0, 5.0))
    assert p.found and p.length_m > 10.0 * 1.4                    # 직선 10 m 보다 훨씬 김
    c = _cells(p)
    cross = c[(c[:, 0] >= 99) & (c[:, 0] <= 102)]
    assert len(cross) and (cross[:, 1] >= 160).all()               # 벽 (y < 160) 을 지나지 않고 열린 틈새로
    assert (g.grade[c[:, 0], c[:, 1]] != gm.BLOCKED).all()


def test_crossable_gap_is_crossed_and_too_wide_gap_gives_no_path():
    a = _room_map("known_gap05")
    p = ga.find_path(a, (5.0, 10.0), (15.0, 10.0))
    c = _cells(p)
    assert p.found and (a.grade[c[:, 0], c[:, 1]] == gm.SPARSE).any() and p.length_m < 15.0
    b = _room_map("known_gap09")
    q = ga.find_path(b, (5.0, 10.0), (15.0, 10.0))
    assert not q.found and q.points.shape == (0, 2) and np.isinf(q.cost)
    same_side = ga.find_path(b, (3.0, 10.0), (8.0, 14.0))
    assert same_side.found


def _bridge_map(sparse_cost):
    """6 x 6 m 방: x 3.0~3.6 에 벽 (y 전체) · 폭 0.4 m 듬성한 다리 (y 2.8~3.2) · y 5.5 이상은 열린 틈새."""
    n = 60
    grade = np.zeros((n, n), np.uint8)
    cost = np.ones((n, n), np.float32)
    grade[30:36, :55] = gm.BLOCKED
    cost[30:36, :55] = np.inf
    grade[30:36, 28:32] = gm.SPARSE
    cost[30:36, 28:32] = sparse_cost
    for sl in ((slice(None), slice(0, 1)), (slice(None), slice(59, 60)), (slice(0, 1), slice(None)), (slice(59, 60), slice(None))):
        grade[sl] = gm.BLOCKED
        cost[sl] = np.inf                                           # 바깥 벽 (없으면 가장자리에 GVD 가 안 생김)
    z = np.zeros((n, n), np.float32)
    return gm.GradeMap(grade, cost, z, z, False, "x", 0.1)


def test_cost_decides_between_a_short_sparse_bridge_and_a_long_free_detour():
    cheap = ga.find_path(_bridge_map(3.0), (1.0, 3.0), (5.0, 3.0), ramp_m=1.0)
    assert cheap.found and cheap.length_m < 5.0                     # 다리 (3 x 0.6 m + 3.4 m = 5.2) 직통
    dear = ga.find_path(_bridge_map(50.0), (1.0, 3.0), (5.0, 3.0), ramp_m=1.0)
    assert dear.found and dear.length_m > 7.0                       # 비싸면 열린 틈새로 돌아감
    assert dear.cost < 50.0 * 0.6 and dear.cost == pytest.approx(dear.length_m, rel=0.05)


def test_path_points_include_the_exact_start_and_goal_and_stay_on_passable_cells():
    g = _room_map("known_wall")
    p = ga.find_path(g, (4.55, 6.05), (16.05, 12.35))
    assert np.allclose(p.points[0], (4.55, 6.05)) and np.allclose(p.points[-1], (16.05, 12.35))
    assert np.isclose(p.length_m, np.linalg.norm(np.diff(p.points, axis=0), axis=1).sum())


def test_blocked_start_and_outside_points_are_refused():
    g = _room_map("known_wall")
    with pytest.raises(ValueError):
        ga.find_path(g, (10.05, 5.0), (15.0, 5.0))                  # 벽 위
    with pytest.raises(ValueError):
        ga.find_path(g, (25.0, 5.0), (15.0, 5.0))


def test_low_passage_opens_only_when_the_pose_switch_is_on():
    spec = {"seed": 0, "size_m": 20.0, "primitives": [
        {"type": "box", "x": 10.0, "y": y, "w": 0.6, "z0": 0.3, "h": 0.5} for y in np.arange(0.2, 19.8, 0.6)]}
    room = rg.build_room(spec)
    off, on = gm.make_grade_map(room, TABLE, False), gm.make_grade_map(room, TABLE, True)
    assert not ga.find_path(off, (5.0, 10.0), (15.0, 10.0)).found
    p = ga.find_path(on, (5.0, 10.0), (15.0, 10.0))
    assert p.found and p.cost > p.length_m + 0.5                     # 숙여 지나는 셀 (비용 2) 이 한 칸 이상 들어감
    free = gm.make_grade_map(rg.build_room({"seed": 0, "size_m": 20.0, "primitives": []}), TABLE)
    f = ga.find_path(free, (5.0, 10.0), (15.0, 10.0))
    assert f.cost == pytest.approx(f.length_m, rel=1e-6)             # 자유 셀만이면 비용 = 길이


def test_gvd_marks_the_medial_line_between_two_walls():
    grade = np.zeros((40, 40), np.uint8)
    grade[:, :3] = gm.BLOCKED
    grade[:, -3:] = gm.BLOCKED
    gv = ga.gvd_mask(grade)
    cols = np.nonzero(gv.any(0))[0]
    assert cols.min() >= 18 and cols.max() <= 21                    # 두 벽 가운데 (열 3~36 의 한가운데 19.5)


def test_every_sampled_pair_in_generated_rooms_finds_a_path():
    for s in range(4):
        _, room = rg.make_room(s, grade_table=TABLE["kinds"])
        g = gm.make_grade_map(room, TABLE)
        pts = gm.sample_free_points(g, np.random.default_rng(s), 6)
        for i in range(0, 6, 2):
            p = ga.find_path(g, pts[i], pts[i + 1])
            assert p.found, (s, i)
            mid = np.concatenate([np.linspace(p.points[k], p.points[k + 1], 8) for k in range(len(p.points) - 1)])
            c = (mid / 0.1).astype(int)
            assert (g.grade[c[:, 0], c[:, 1]] != gm.BLOCKED).all(), (s, i)       # 노드 사이 · 시작 · 목표 직선도 벽을 안 지남


# ---- 건너뛰기 간선 (리뷰 #730: 징검돌 · 징검보가 늘 통과 불가였다) ------------------------------------------------
KINDS = ("stepping_stones_low", "stepping_stones_high", "balance_beams", "stepping_beams", "gaps")
JUMP_KINDS = ("stepping_stones_low", "stepping_stones_high", "stepping_beams")      # 돌 · 보 사이가 막힌 칸이라 건너뛰어야 하는 것


@pytest.mark.parametrize("kind", KINDS)
def test_every_patch_kind_has_a_room_that_can_only_be_crossed_over_the_strip(kind):
    g = _room_map(f"known_cross_{kind}")
    p = ga.find_path(g, (5.0, 10.0), (15.0, 10.0))
    assert p.found and p.length_m < 12.0                                   # 돌아가는 길이 없다: 띠 위를 건넌다
    c = _cells(p)
    assert (g.grade[c[:, 0], c[:, 1]] != gm.BLOCKED).all()                 # 발 디딜 수 있는 셀에만 닿는다
    inside = c[(c[:, 0] >= 72) & (c[:, 0] <= 128)]                 # 띠 (x 7~13 m) 안쪽 · 가장자리 평지 제외
    assert len(inside) and (g.grade[inside[:, 0], inside[:, 1]] == gm.SPARSE).all()
    steps = np.linalg.norm(np.diff(path_xy(p), axis=0), axis=1)
    jumped = bool((steps > 0.25).any())
    assert jumped == (kind in JUMP_KINDS)                                  # 돌 · 보는 건너뛰기로, 평균대 · 틈은 이어진 셀로


def path_xy(p):
    return p.points[1:-1]                                                  # 시작 · 목표 직선 꼬리는 뺀다


@pytest.mark.parametrize("kind", JUMP_KINDS)
def test_the_gaps_between_stones_stay_blocked_and_a_small_stride_gives_no_path(kind):
    g = _room_map(f"known_cross_{kind}")
    strip = g.grade[70:130, 80:120]
    assert (strip == gm.BLOCKED).any()                                     # 돌 사이를 SPARSE 로 칠하지 않았다 (실제 디딤 위치를 잃지 않는다)
    assert not ga.find_path(g, (5.0, 10.0), (15.0, 10.0), stride_m=0.1).found
    assert ga.find_path(g, (5.0, 10.0), (15.0, 10.0), stride_m=0.3).found  # 이 생성기의 돌 사이 틈은 0.3 m 안 (레벨 1)
    off = gm.GradeMap(g.grade, g.cost, g.height, g.clearance, g.pose_active, g.table_sha256, g.res)   # 보폭 0 = 간선 없음
    assert not ga.find_path(off, (5.0, 10.0), (15.0, 10.0)).found


@pytest.mark.parametrize("kind", JUMP_KINDS)
def test_the_table_stride_covers_every_level_the_table_lets_the_lower_policy_pass(kind):
    cap = int(TABLE["kinds"][kind]["max_passed_level"])
    base = rg.load_spec(NAV / "rooms" / f"known_cross_{kind}.yaml")
    for level in range(cap + 1):
        spec = {**base, "primitives": [dict(p, level=level) if p["type"] == "patch" else p for p in base["primitives"]]}
        g = gm.make_grade_map(rg.build_room(spec), TABLE)
        assert g.stride_m == TABLE["max_stride_m"] == 0.7
        assert ga.find_path(g, (5.0, 10.0), (15.0, 10.0)).found, (kind, level)


def test_a_patch_level_above_the_table_stays_blocked_even_with_jump_edges():
    base = rg.load_spec(NAV / "rooms" / "known_cross_stepping_stones_high.yaml")
    spec = {**base, "primitives": [dict(p, level=3) if p["type"] == "patch" else p for p in base["primitives"]]}
    g = gm.make_grade_map(rg.build_room(spec), TABLE)
    assert not (g.grade[70:130, 80:120] == gm.SPARSE).any()
    assert not ga.find_path(g, (5.0, 10.0), (15.0, 10.0)).found


def _two_stones(patch_a, patch_b, between=gm.BLOCKED, gap=3):
    n = 30
    grade = np.full((n, n), gm.BLOCKED, np.uint8)
    patch = np.full((n, n), -1, np.int16)
    grade[10, 10] = grade[10, 11 + gap] = gm.SPARSE
    patch[10, 10], patch[10, 11 + gap] = patch_a, patch_b
    if between != gm.BLOCKED:
        grade[10, 11:11 + gap] = between
    z = np.zeros((n, n), np.float32)
    return gm.GradeMap(grade, np.where(grade == gm.BLOCKED, np.inf, 1.0).astype(np.float32), z, z, False, "x", 0.1,
                       0.7, patch)


def test_jump_edges_need_the_same_patch_a_blocked_gap_and_a_gap_within_the_stride():
    assert len(ga.jump_edges(_two_stones(0, 0))) == 1                          # 같은 패치 · 막힌 틈 0.3 m
    assert len(ga.jump_edges(_two_stones(0, 1))) == 0                          # 다른 패치끼리는 잇지 않는다
    assert len(ga.jump_edges(_two_stones(-1, -1))) == 0                        # 패치 밖 (일반 지형) 은 잇지 않는다
    assert len(ga.jump_edges(_two_stones(0, 0, gap=9))) == 0                   # 틈 0.9 m > 보폭 0.7 m
    assert len(ga.jump_edges(_two_stones(0, 0), stride_m=0.1)) == 0
    assert len(ga.jump_edges(_two_stones(0, 0, gap=3), stride_m=0.35)) == 1     # 틈 0.3 m <= 0.35 m
    assert len(ga.jump_edges(_two_stones(0, 0, gap=4), stride_m=0.35)) == 0     # 틈 0.4 m > 0.35 m (탐색 반경 안이라도 보폭이 가른다)
    mid = _two_stones(0, 0, gap=3)
    mid.grade[10, 12] = gm.SPARSE                                               # 두 돌 사이에 돌이 하나 더: 그 돌을 건너뛰어 곧장 잇지 않고 한 칸씩 잇는다
    mid.patch[10, 12] = 0
    assert sorted(int(e[1]) for e in ga.jump_edges(mid)) == [10, 12]
    assert len(ga.jump_edges(_two_stones(0, 0, between=gm.FREE))) == 0         # 사이가 막힌 칸만이 아니면 보통 간선이 맡는다
    joined = _two_stones(0, 0)
    joined.grade[10, 11:14] = gm.FREE                                          # 이어진 길이 있으면 (같은 덩어리) 간선을 만들지 않는다
    assert len(ga.jump_edges(joined)) == 0
    old = gm.GradeMap(*(_two_stones(0, 0).__dict__[k] for k in ("grade", "cost", "height", "clearance", "pose_active", "table_sha256", "res")))
    assert len(ga.jump_edges(old)) == 0                                        # 패치 번호 없는 옛 지도 = 간선 없음
