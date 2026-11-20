"""EX-42 합친 메시용 발 가장자리 마스크 (inner 2.5 cm · outer 5 cm 띠). 순수 numpy (Isaac 없음).

START 의 foot_edge 항 (16 §2) 은 칸별 마스크표 (env.s2_tables) 를 읽는데, 합친 메시 환경에는 그 표가 없어 항이 0 이었다.
여기서는 마스크를 합친 메시 자체의 윗면 높이에서 만든다: 칸 (8 x 8 m) 마다 2.5 cm 격자로 윗면을 그리고 (`rasterize_top`)
sparse_terrains.edge_masks (낙하 0.2 m 이상인 세로 모서리 양쪽 한 칸 = inner, 그 바깥 한 칸 = outer) 를 그대로 쓴다.
그래서 징검돌 · 외다리 (balance_beams · stepping_beams) · 틈 (gaps) 등 어느 듬성한 종류든 같은 식이고, 새 종류는 `EDGE_KINDS` 에 이름만 더한다.

저장: 메시 npz 에 배열 `edge_inner_bits` · `edge_outer_bits` (packbits, (rows, K, H*W/8)) · `edge_columns` (K,) · `edge_meta` (json 문자열) 를 더한다.
vertices · faces 는 그대로라 geometry sha (mesh_sha256) 는 옛 메시와 같다. 마스크 sha 는 `edge_masks_sha256` 로 따로 기록한다.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np

EDGE_FAMILY = "A"                     # 이 가족의 칸만 마스크를 만든다 (칸 8 x 8 m · 합친 메시의 첫 가족, 줄 x 열 = rows x 50)
EDGE_KINDS = ("stepping_stones_low", "stepping_stones_high", "balance_beams", "stepping_beams", "gaps")
RES = 0.025
TILE = (8.0, 8.0)
DROP_M = 0.2
FLOOR = -10.0
EDGE_KEYS = ("edge_inner_bits", "edge_outer_bits", "edge_columns", "edge_meta")


def tile_corner(row: int, col: int, rows: int, cols: int, tile=TILE) -> tuple[float, float]:
    """Isaac Lab 생성기는 격자를 (-size_x * rows / 2, -size_y * cols / 2) 에서 시작해 놓는다 (ex42_combined 머리 설명). 첫 가족 (offset 0) 의 칸 모서리."""
    return -tile[0] * rows / 2.0 + tile[0] * row, -tile[1] * cols / 2.0 + tile[1] * col


def rasterize_top(vertices: np.ndarray, faces: np.ndarray, x0: float, y0: float, nx: int, ny: int, res: float = RES) -> np.ndarray:
    """(nx, ny) 윗면 높이 격자. 칸 중심 (x0 + (i + .5) res, y0 + (j + .5) res) 에서 삼각형 안이면 보간 높이, 겹치면 높은 쪽. 덮이지 않은 칸은 FLOOR."""
    grid = np.full((nx, ny), FLOOR)
    tri = vertices[faces]                                          # (F, 3, 3)
    for t in tri:
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = t
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-12:                                       # 윗면에서 보아 면적 0 (세로 면)
            continue
        i0 = max(int(np.floor((min(ax, bx, cx) - x0) / res)), 0)
        i1 = min(int(np.ceil((max(ax, bx, cx) - x0) / res)), nx)
        j0 = max(int(np.floor((min(ay, by, cy) - y0) / res)), 0)
        j1 = min(int(np.ceil((max(ay, by, cy) - y0) / res)), ny)
        if i0 >= i1 or j0 >= j1:
            continue
        px = x0 + (np.arange(i0, i1) + 0.5) * res
        py = y0 + (np.arange(j0, j1) + 0.5) * res
        gx, gy = np.meshgrid(px, py, indexing="ij")
        l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / det
        l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / det
        l3 = 1.0 - l1 - l2
        eps = -1e-9
        inside = (l1 >= eps) & (l2 >= eps) & (l3 >= eps)
        if not inside.any():
            continue
        z = l1 * az + l2 * bz + l3 * cz
        sub = grid[i0:i1, j0:j1]
        grid[i0:i1, j0:j1] = np.where(inside, np.maximum(sub, z), sub)
    return grid


def column_kinds_of_family_a(count: int) -> list[str]:
    from foothold_s2.terrains import columns
    return list(columns.column_types(columns.FULL, count))


def build_edge_masks(vertices: np.ndarray, faces: np.ndarray, origins: np.ndarray, column_family: list[str],
                     kinds: tuple[str, ...] = EDGE_KINDS, res: float = RES, drop: float = DROP_M) -> dict[str, Any]:
    """합친 메시에서 EDGE_FAMILY 의 `kinds` 열마다 (줄 전부) inner · outer 마스크를 만든다. 반환: {inner (R, K, H, W) bool, outer, columns, meta}."""
    from foothold_s2.terrains import sparse_terrains as st
    rows, n_cols = origins.shape[:2]
    fam = [i for i, f in enumerate(column_family) if f == EDGE_FAMILY]
    if not fam or fam != list(range(fam[0], fam[0] + len(fam))) or fam[0] != 0:
        raise ValueError("edge masks expect family A to be the first contiguous columns of the mesh")
    names = column_kinds_of_family_a(len(fam))
    cols = [c for c in fam if names[c] in kinds]
    if not cols:
        raise ValueError("no edge-kind columns in the mesh")
    nx, ny = int(round(TILE[0] / res)), int(round(TILE[1] / res))
    cx = (vertices[faces][:, :, 0].min(1) + vertices[faces][:, :, 0].max(1)) / 2.0
    cy = (vertices[faces][:, :, 1].min(1) + vertices[faces][:, :, 1].max(1)) / 2.0
    inner = np.zeros((rows, len(cols), nx, ny), bool); outer = np.zeros_like(inner)
    uncovered = 0
    for k, c in enumerate(cols):
        for r in range(rows):
            x0, y0 = tile_corner(r, c, rows, len(fam))
            o = origins[r, c]
            if not (x0 <= o[0] <= x0 + TILE[0] and y0 <= o[1] <= y0 + TILE[1]):
                raise ValueError(f"origin of tile ({r},{c}) lies outside the tile computed from the generator centring")
            pick = (cx >= x0) & (cx < x0 + TILE[0]) & (cy >= y0) & (cy < y0 + TILE[1])
            grid = rasterize_top(vertices, faces[pick], x0, y0, nx, ny, res)
            uncovered += int((grid <= FLOOR).sum())
            hole = grid <= FLOOR
            if hole.any():                                          # 덮이지 않은 칸은 덮인 칸의 중앙값으로 채워 가짜 모서리를 막는다 (개수는 meta 에 남김)
                grid = np.where(hole, float(np.median(grid[~hole])) if (~hole).any() else 0.0, grid)
            inner[r, k], outer[r, k] = st.edge_masks(grid, drop)
    meta = {"family": EDGE_FAMILY, "kinds": list(kinds), "column_kinds": {int(c): names[c] for c in cols}, "tile": list(TILE), "resolution_m": res,
            "drop_m": drop, "rows": rows, "family_columns": len(fam), "uncovered_cells": uncovered,
            "corner": "x0 = -tile_x*rows/2 + tile_x*row ; y0 = -tile_y*family_columns/2 + tile_y*col (mesh frame = world frame)"}
    return {"inner": inner, "outer": outer, "columns": np.array(cols, dtype=np.int64), "meta": meta}


def extra_specs(terrain_manifest: dict[str, Any], kinds: tuple[str, ...], rows: int, covered: set[int] | None = None) -> list[dict[str, Any]]:
    """EX42_EDGE_EXTRA_KINDS: 메시 자리표 (terrain_manifest.json 의 kind 별 geometry_selection 칸 범위) 로 칸 크기 · 모서리를 읽는다.
    반환: 열마다 {kind, col, size_x, size_y, x_start, y0}. 이미 마스크가 있는 열 (A 가족) 이나 연속 지형 · 칸 범위가 안 맞는 kind 는 ValueError."""
    out: list[dict[str, Any]] = []
    for name in kinds:
        family, kind = name.split("/")
        hits = [k for k in terrain_manifest["kinds"] if k.get("family") == family and k.get("kind") == kind]
        if len(hits) != 1:
            raise ValueError(f"edge extra kind {name}: {len(hits)} entries in the terrain manifest (want 1)")
        sel = hits[0]["geometry_selection"]
        cols = [int(c) for c in sel["columns"]]
        (x0, y0, _), (x1, y1, _) = sel["bounds_m"]
        size_x, size_y = (x1 - x0) / rows, (y1 - y0) / len(cols)
        if size_x <= 0 or size_y <= 0 or abs(size_x - size_y) > 1e-3 or sorted(sel["rows"]) != list(range(rows)):
            raise ValueError(f"edge extra kind {name}: tile is not a square {rows}-row tile (size {size_x} x {size_y})")
        if covered and set(cols) & covered:
            raise ValueError(f"edge extra kind {name}: columns {sorted(set(cols) & covered)} already carry edge masks")
        for i, c in enumerate(sorted(cols)):
            out.append({"kind": name, "col": c, "size_x": size_x, "size_y": size_y, "x_start": x0, "y0": y0 + size_y * i})
    if len({s["col"] for s in out}) != len(out):
        raise ValueError("edge extra kinds share a column")
    return out


def build_extra_masks(vertices: np.ndarray, faces: np.ndarray, origins: np.ndarray, specs: list[dict[str, Any]],
                      res: float = RES, drop: float = DROP_M) -> list[dict[str, Any]]:
    """`extra_specs` 의 열마다 (줄 전부) inner · outer 마스크 (rows, H, W) bool. 식은 A 가족 마스크와 같다 (rasterize_top -> sparse_terrains.edge_masks)."""
    from foothold_s2.terrains import sparse_terrains as st
    rows = origins.shape[0]
    tri_x, tri_y = vertices[faces][:, :, 0], vertices[faces][:, :, 1]
    cx, cy = (tri_x.min(1) + tri_x.max(1)) / 2.0, (tri_y.min(1) + tri_y.max(1)) / 2.0
    built = []
    for sp in specs:
        nx, ny = int(round(sp["size_x"] / res)), int(round(sp["size_y"] / res))
        inner = np.zeros((rows, nx, ny), bool); outer = np.zeros_like(inner)
        uncovered = 0
        for r in range(rows):
            x0 = sp["x_start"] + sp["size_x"] * r
            o = origins[r, sp["col"]]
            if not (x0 <= o[0] <= x0 + sp["size_x"] and sp["y0"] <= o[1] <= sp["y0"] + sp["size_y"]):
                raise ValueError(f"origin of tile ({r},{sp['col']}) lies outside the tile read from the terrain manifest")
            pick = (cx >= x0) & (cx < x0 + sp["size_x"]) & (cy >= sp["y0"]) & (cy < sp["y0"] + sp["size_y"])
            grid = rasterize_top(vertices, faces[pick], x0, sp["y0"], nx, ny, res)
            hole = grid <= FLOOR
            uncovered += int(hole.sum())
            if hole.any():
                grid = np.where(hole, float(np.median(grid[~hole])) if (~hole).any() else 0.0, grid)
            inner[r], outer[r] = st.edge_masks(grid, drop)
        built.append({**sp, "inner": inner, "outer": outer, "uncovered_cells": uncovered})
    return built


def pack_masks(built: dict[str, Any]) -> dict[str, np.ndarray]:
    r, k = built["inner"].shape[:2]
    out = {"edge_inner_bits": np.packbits(built["inner"].reshape(r, k, -1), axis=-1), "edge_outer_bits": np.packbits(built["outer"].reshape(r, k, -1), axis=-1),
           "edge_columns": built["columns"], "edge_meta": np.array(json.dumps(built["meta"], sort_keys=True))}
    return out


def masks_sha256(packed: dict[str, np.ndarray]) -> str:
    h = hashlib.sha256()
    for key in EDGE_KEYS:
        v = packed[key]
        h.update(key.encode()); h.update(np.ascontiguousarray(v).tobytes() if key != "edge_meta" else str(v).encode())
    return h.hexdigest()


def load_edge_masks(npz_path) -> dict[str, Any] | None:
    """npz 에 마스크가 없으면 None (옛 메시 · 항은 지금처럼 0). 있으면 {inner, outer (R, K, H, W) bool, columns, meta}."""
    data = np.load(npz_path, allow_pickle=False)
    present = [k for k in EDGE_KEYS if k in data.files]
    if not present:
        return None
    if len(present) != len(EDGE_KEYS):
        raise ValueError(f"mesh npz has a partial edge-mask set: {present}")
    meta = json.loads(str(data["edge_meta"]))
    r, k = data["edge_inner_bits"].shape[:2]
    h = int(round(meta["tile"][0] / meta["resolution_m"])); w = int(round(meta["tile"][1] / meta["resolution_m"]))
    unpack = lambda a: np.unpackbits(a, axis=-1, count=h * w).astype(bool).reshape(r, k, h, w)
    return {"inner": unpack(data["edge_inner_bits"]), "outer": unpack(data["edge_outer_bits"]), "columns": data["edge_columns"].astype(np.int64), "meta": meta}


class EdgeTables:
    """env.ex42_edge_tables: 칸별 마스크 (torch) + 발 월드 좌표 -> 칸 좌표 변환. `foot_edge_term` 이 읽는다 (start_rewards).

    inner · outer (rows, K, H, W) bool, `col_to_k` (합친 메시 열 수,) = 그 열의 마스크 번호 (마스크 없는 열은 -1 · 항이 0).
    `shift` = (tile_x * rows / 2, tile_y * family_columns / 2): 월드 좌표 + shift - 줄 x tile = 칸 안 좌표.
    """

    def __init__(self, loaded: dict[str, Any], total_columns: int, device: str):
        import torch
        meta = loaded["meta"]
        self.inner = torch.as_tensor(loaded["inner"], device=device)
        self.outer = torch.as_tensor(loaded["outer"], device=device)
        k = torch.full((total_columns,), -1, dtype=torch.long, device=device)
        for i, c in enumerate(loaded["columns"].tolist()):
            k[c] = i
        self.col_to_k = k
        self.tile = tuple(meta["tile"]); self.res = float(meta["resolution_m"])
        self.shift = torch.tensor([self.tile[0] * meta["rows"] / 2.0, self.tile[1] * meta["family_columns"] / 2.0], device=device)
        self.meta = meta
        self.extra: list[dict[str, Any]] = []

    def drop_columns(self, columns) -> dict[str, Any]:
        """EX42_EDGE_PENALTY_OFF_KINDS: 그 열의 마스크 번호를 -1 로 (마스크 없는 열과 같은 길 · 항 0). 끄기 전 · 뒤에 그 열 inner 칸 한가운데 발로 값을 재서 돌려준다
        (끄기 전 > 0 · 뒤 0 이 아니면 오류). 다른 열의 번호 · 표는 그대로."""
        import torch
        dev = self.inner.device
        cols = [int(c) for c in columns]
        probes = []
        for col in cols:
            k = int(self.col_to_k[col])
            if k < 0:
                raise ValueError(f"EX-42 edge penalty off: column {col} has no edge mask (nothing to turn off)")
            r, cell = next(((r, torch.nonzero(self.inner[r, k])[0]) for r in range(self.inner.shape[0]) if bool(self.inner[r, k].any())), (None, None))
            if r is None:
                raise ValueError(f"EX-42 edge penalty off: column {col} mask is empty")
            fam = int(round(self.shift[1].item() * 2 / self.tile[1]))
            x = -self.tile[0] * self.inner.shape[0] / 2.0 + self.tile[0] * r + (cell[0].item() + 0.5) * self.res
            y = -self.tile[1] * fam / 2.0 + self.tile[1] * col + (cell[1].item() + 0.5) * self.res
            probes.append((col, r, torch.tensor([[[x, y]]], device=dev, dtype=torch.float32)))
        one = torch.ones(1, 1, dtype=torch.bool, device=dev)
        before = [float(self.penalty(f, one, torch.tensor([r], device=dev), torch.tensor([c], device=dev))[0]) for c, r, f in probes]
        self.col_to_k[cols] = -1
        after = [float(self.penalty(f, one, torch.tensor([r], device=dev), torch.tensor([c], device=dev))[0]) for c, r, f in probes]
        if not all(b > 0 for b in before) or any(a != 0.0 for a in after):
            raise RuntimeError(f"EX-42 edge penalty off did not take: before {before} after {after}")
        self.off_columns = tuple(cols)
        return {"columns": cols, "inner_before": before, "inner_after": after}

    def add_extra(self, built: list[dict[str, Any]]) -> None:
        """`build_extra_masks` 결과를 붙인다 (EX42_EDGE_EXTRA_KINDS). 이 열의 값은 기존 표가 0 이던 열이라 합치기만 하면 된다."""
        import torch
        dev = self.inner.device
        for b in built:
            self.extra.append({"kind": b["kind"], "col": int(b["col"]), "size_x": float(b["size_x"]), "size_y": float(b["size_y"]), "x_start": float(b["x_start"]),
                               "y0": float(b["y0"]), "inner": torch.as_tensor(b["inner"], device=dev), "outer": torch.as_tensor(b["outer"], device=dev)})

    def _extra_penalty(self, feet_xy, contact, levels, types):
        import torch
        from foothold_s2.rewards import core
        total = torch.zeros(feet_xy.shape[0], dtype=feet_xy.dtype, device=feet_xy.device)
        for ex in self.extra:
            on = (types == ex["col"])[:, None]
            h, w = ex["inner"].shape[-2:]
            ix = torch.floor((feet_xy[..., 0] - (ex["x_start"] + levels.to(feet_xy.dtype) * ex["size_x"])[:, None]) / self.res).long()
            iy = torch.floor((feet_xy[..., 1] - ex["y0"]) / self.res).long()
            ok = on & (ix >= 0) & (ix < h) & (iy >= 0) & (iy < w)
            ix, iy = ix.clamp(0, h - 1), iy.clamp(0, w - 1)
            lv = levels[:, None].expand_as(ix)
            inner, outer = ex["inner"][lv, ix, iy].float() * ok.float(), ex["outer"][lv, ix, iy].float() * ok.float()
            total = total + torch.sum(contact.float() * (core.EDGE_OMEGA[0] * inner + core.EDGE_OMEGA[1] * outer), dim=-1)
        return total

    def penalty(self, feet_xy, contact, levels, types):
        """(N,) 발 가장자리 값 (부호는 가중치가). 마스크가 없는 열은 0 (EX42_EDGE_EXTRA_KINDS 로 붙인 열은 그 마스크)."""
        import torch
        from foothold_s2.rewards import core
        base = self._base_penalty(feet_xy, contact, levels, types)
        return base + self._extra_penalty(feet_xy, contact, levels, types) if self.extra else base

    def _base_penalty(self, feet_xy, contact, levels, types):
        import torch
        from foothold_s2.rewards import core
        k = self.col_to_k[types]
        corner = torch.stack([levels.to(feet_xy.dtype) * self.tile[0], types.to(feet_xy.dtype) * self.tile[1]], dim=-1)[:, None, :]   # 칸 모서리 (월드 + shift 좌표): 줄 x tile_x, 실제 열 x tile_y
        idx = torch.floor((feet_xy + self.shift - corner) / self.res).long()
        h, w = self.inner.shape[-2:]
        ok = (idx[..., 0] >= 0) & (idx[..., 0] < h) & (idx[..., 1] >= 0) & (idx[..., 1] < w) & (k >= 0)[:, None]
        ix, iy = idx[..., 0].clamp(0, h - 1), idx[..., 1].clamp(0, w - 1)
        lv, kk = levels[:, None].expand_as(ix), k.clamp(min=0)[:, None].expand_as(ix)
        inner = self.inner[lv, kk, ix, iy].float() * ok.float()
        outer = self.outer[lv, kk, ix, iy].float() * ok.float()
        return torch.sum(contact.float() * (core.EDGE_OMEGA[0] * inner + core.EDGE_OMEGA[1] * outer), dim=-1)

    def self_check(self) -> dict[str, Any]:
        """붙인 텐서로 계산 한 번: 첫 마스크 칸의 첫 inner 격자 중앙에 발을 두면 항이 0 이 아니어야 하고, 칸 바깥 · 마스크 없는 열은 0 이어야 한다. 아니면 오류 (조용히 0 인 항을 막는다)."""
        import torch
        if not bool(self.inner.any()) or not bool(self.outer.any()):
            raise RuntimeError("EX-42 edge tables are attached but empty")
        r, k = [int(v[0]) for v in torch.nonzero(self.inner.flatten(2).any(-1))[:1].T]
        cell = torch.nonzero(self.inner[r, k])[0]
        col = int((self.col_to_k == k).nonzero()[0])
        rows = self.inner.shape[0]
        fam = int(round(self.shift[1].item() * 2 / self.tile[1]))
        x = -self.tile[0] * rows / 2.0 + self.tile[0] * r + (cell[0].item() + 0.5) * self.res
        y = -self.tile[1] * fam / 2.0 + self.tile[1] * col + (cell[1].item() + 0.5) * self.res
        dev = self.inner.device
        feet = torch.tensor([[[x, y]]], device=dev, dtype=torch.float32); contact = torch.ones(1, 1, dtype=torch.bool, device=dev)
        v = self.penalty(feet, contact, torch.tensor([r], device=dev), torch.tensor([col], device=dev))
        if not float(v[0]) > 0.0:
            raise RuntimeError(f"EX-42 edge tables are attached but the foot term reads 0 on an inner cell (row {r}, column {col})")
        outside = self.penalty(feet + 1000.0, contact, torch.tensor([r], device=dev), torch.tensor([col], device=dev))
        if float(outside[0]) != 0.0:
            raise RuntimeError("EX-42 edge tables: a foot outside the tile reads non-zero")
        out = {"row": r, "column": col, "value_on_inner": float(v[0])}
        if self.extra:
            out["extra"] = self._extra_self_check()
        return out

    def _extra_self_check(self) -> list[dict[str, Any]]:
        """붙인 열마다: 첫 inner 칸 중앙에 발을 두면 항이 0 이 아니고, 칸 바깥은 0 이어야 한다. 아니면 오류."""
        import torch
        dev = self.inner.device
        res = []
        for ex in self.extra:
            rr = int(torch.nonzero(ex["inner"].flatten(1).any(-1))[0])
            cell = torch.nonzero(ex["inner"][rr])[0]
            x = ex["x_start"] + ex["size_x"] * rr + (cell[0].item() + 0.5) * self.res
            y = ex["y0"] + (cell[1].item() + 0.5) * self.res
            feet = torch.tensor([[[x, y]]], device=dev, dtype=torch.float32); contact = torch.ones(1, 1, dtype=torch.bool, device=dev)
            lv, ty = torch.tensor([rr], device=dev), torch.tensor([ex["col"]], device=dev)
            v = float(self.penalty(feet, contact, lv, ty)[0])
            out = float(self.penalty(feet + 1000.0, contact, lv, ty)[0])
            if not v > 0.0 or out != 0.0:
                raise RuntimeError(f"EX-42 extra edge masks {ex['kind']} (column {ex['col']}): value on an inner cell {v}, outside the tile {out}")
            res.append({"kind": ex["kind"], "column": ex["col"], "row": int(rr), "value_on_inner": v})
        return res
