"""방 -> 통과 가능 등급 지도 (PLAN-HIPAN-V2 §5.2 · M4 · 22-NAV-ENV §3). numpy · scipy.

셀 종류 (room_generator.CELL_*) 와 등급표 (grade_table yaml) 로 셀마다 등급 · 비용을 정한다. 추정은 없다: 생성기가 아는 정보다.
등급: FREE 0 (평지 · 거친 면) · CONNECTED_ROUGH 1 (계단) · SPARSE 2 (징검돌 · 평균대 · 하위가 넘는 폭의 틈) · BLOCKED 3 · OVERHEAD 4 (머리 위 장애물 아래 통과).
머리 위: 여유 >= stand_clearance 면 서서 통과 (비용 1). 아니고 자세 스위치가 켜져 있고 여유 >= crawl_clearance 면 숙여 통과 (비용 2). 그 밖은 막음.
(계획 §5.2 는 스위치 꺼짐일 때 「막음」 이라 적었다. 서서 지나갈 만큼 높은 탁자까지 막는 뜻인지 불분명해 여유가 충분하면 통과로 둠 · 가정.)
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from foothold_s2.nav import room_generator as rg

FREE, CONNECTED_ROUGH, SPARSE, BLOCKED, OVERHEAD = 0, 1, 2, 3, 4
GRADE_NAMES = ("free", "connected", "sparse", "blocked", "overhead")


def load_grade_table(path) -> dict:
    raw = Path(path).read_bytes()
    t = yaml.safe_load(raw)
    for k in ("costs", "stand_clearance_m", "crawl_clearance_m", "max_gap_cross_m", "rows"):
        if k not in t:
            raise ValueError(f"grade table lacks {k}")
    if t["crawl_clearance_m"] > t["stand_clearance_m"]:
        raise ValueError("crawl clearance must not exceed stand clearance")
    t["kinds"] = {r["kind"]: r for r in t["rows"]}
    t["sha256"] = hashlib.sha256(raw).hexdigest()
    return t


@dataclass
class GradeMap:
    grade: np.ndarray      # (200, 200) uint8
    cost: np.ndarray       # (200, 200) float32, 막음 = inf
    height: np.ndarray
    clearance: np.ndarray
    pose_active: bool
    table_sha256: str
    res: float = rg.RES


def make_grade_map(room: rg.Room, table: dict, pose_active: bool = False) -> GradeMap:
    c = room.cell
    g = np.full(c.shape, BLOCKED, np.uint8)
    cost = np.full(c.shape, np.inf, np.float32)
    costs = table["costs"]

    def put(mask, grade, value):
        g[mask] = grade
        cost[mask] = value

    put((c == rg.CELL_FLAT) | (c == rg.CELL_ROUGH), FREE, costs["free"])
    put(c == rg.CELL_STAIRS, CONNECTED_ROUGH, costs["connected"])
    put(c == rg.CELL_FOOTHOLD, SPARSE, costs["sparse"])
    put((c == rg.CELL_GAP_PIT) & (room.gap_width <= table["max_gap_cross_m"] + 1e-9), SPARSE, costs["sparse"])
    # 하위 통과 레벨을 넘는 패치는 띠 안 전부 막음
    for idx, kind in enumerate(rg.PATCH_KINDS):
        row = table["kinds"].get(kind)
        cap = -1 if row is None else int(row["max_passed_level"])
        too_hard = (room.patch_kind == idx) & (room.patch_level > cap) & np.isin(c, (rg.CELL_FOOTHOLD, rg.CELL_GAP_PIT))
        put(too_hard, BLOCKED, np.inf)
    over = c == rg.CELL_OVERHEAD
    stand = over & (room.clearance >= table["stand_clearance_m"])
    crawl = over & ~stand & bool(pose_active) & (room.clearance >= table["crawl_clearance_m"])
    put(stand, OVERHEAD, costs["overhead_stand"])
    put(crawl, OVERHEAD, costs["overhead_crawl"])
    return GradeMap(g, cost, room.height.astype(np.float32), room.clearance.astype(np.float32),
                    bool(pose_active), table["sha256"])


def save_grade_map(gm: GradeMap, path) -> None:
    np.savez_compressed(path, grade=gm.grade, cost=gm.cost, height=gm.height, clearance=gm.clearance,
                        res=np.float64(gm.res), pose_active=np.bool_(gm.pose_active), table_sha256=np.array(gm.table_sha256))


def load_grade_map(path) -> GradeMap:
    d = np.load(path, allow_pickle=False)
    g = d["grade"]
    if g.ndim != 2 or d["cost"].shape != g.shape or g.dtype != np.uint8:
        raise ValueError("grade_map.npz shapes differ")
    return GradeMap(g, d["cost"], d["height"], d["clearance"], bool(d["pose_active"]), str(d["table_sha256"]), float(d["res"]))


def passable(gm: GradeMap) -> np.ndarray:
    return gm.grade != BLOCKED


def largest_component_mask(mask: np.ndarray) -> np.ndarray:
    from scipy import ndimage

    lab, n = ndimage.label(mask)
    if not n:
        return np.zeros_like(mask)
    return lab == (np.argmax(np.bincount(lab.ravel())[1:]) + 1)


def sample_free_points(gm: GradeMap, rng: np.random.Generator, n: int, margin_m: float = 0.3) -> np.ndarray:
    """무충돌 위치 균등 표본 (22 §6.6). 가장 큰 통과 가능 덩어리 안에서 BLOCKED 와 margin 이상 떨어진 평지 · 거친 면 · 계단 셀의 중심 (m, 방 모서리 기준 xy)."""
    from scipy import ndimage

    dist = ndimage.distance_transform_edt(gm.grade != BLOCKED) * gm.res          # 막힌 셀까지 거리
    ok = (dist > margin_m) & np.isin(gm.grade, (FREE, CONNECTED_ROUGH)) & largest_component_mask(passable(gm))
    cells = np.argwhere(ok)
    if not len(cells):
        raise ValueError("no free cell")
    return (cells[rng.integers(0, len(cells), n)] + 0.5) * gm.res
