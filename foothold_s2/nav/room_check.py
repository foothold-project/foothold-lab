"""HiPAN 방 검사 도구 (DESIGN-HIPAN-ROOMS-1117 3.4 · 5.2): 생성한 방 묶음에 판정 줄 여덟을 걸어 표 · 그림 · 종료 코드를 낸다. numpy · scipy (그림만 matplotlib). Kit 없음.

쓰는 법: python -m foothold_s2.nav.room_check --count 100 --out <폴더> [--figure-seeds 1000,1001,1002,1003,1004,1005] [--pairs-starts 10 --pairs-goals 15 --planner-pairs 20]
판정 줄 (결과 전에 고정 · 설계 3.4): 같은 자 = 0.1 m 격자 8 방향 최단 길이 / 직선 거리 · 로봇 반폭 0.2 m 만큼 막힌 칸을 부풀림 · 직선 4 m 이상 · 방마다 시작 10 x 목표 15 = 150 쌍.
 1 통과 가능 칸 방마다 55~80 %          2 굴곡 비 중앙값 (100 방을 모아) 1.12 이상      3 굴곡 비 1.2 넘는 쌍 35 % 이상
 4 굴곡 비 1.5 넘는 쌍 15~45 %          5 막다른 타일 방마다 3 개 이상                   6 이어짐 98 % 이상 · 시작점 64 개 전부 그 안
 7 가장 좁은 통과 폭 0.8 m 이상         8 계획기 길 / 격자 최단 중앙값 1.15 이하 (곧게 펴기 켠 길)
방마다 줄 (1 · 5 · 6 · 7) 은 통과한 방 수를 센다 (make_room 이 수락 조건으로 이미 걸러 내므로 100 이어야 한다). 하나라도 못 넘으면 종료 코드 1."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from foothold_s2.nav import grade_map as gm
from foothold_s2.nav import gvd_astar
from foothold_s2.nav import room_generator as rg

GRADE_TABLE = Path(__file__).resolve().parent / "grade_table_draft.yaml"
LINES = {"free_frac": (0.55, 0.80), "tort_median_min": 1.12, "frac_gt_1_2_min": 0.35, "frac_gt_1_5": (0.15, 0.45), "dead_end_min": 3,
         "connected_min": 0.98, "passage_min_m": 0.8, "planner_ratio_max": 1.15}
INFLATE_CELLS = 2                    # 로봇 반폭 0.2 m
MIN_STRAIGHT_M = 4.0
SQ2 = 2 ** 0.5


def inflate(blocked: np.ndarray, cells: int = INFLATE_CELLS) -> np.ndarray:
    return ndimage.binary_dilation(blocked, iterations=cells)


def grid_graph(free: np.ndarray):
    """0.1 m 격자 8 방향 그래프 (대각선은 두 옆칸이 다 자유일 때만 · 길이 sqrt 2). 돌려주는 값: (csr 행렬, 셀 -> 마디 번호 배열 (-1 = 막힘))."""
    n, m = free.shape
    node = np.full((n, m), -1, np.int64)
    node[free] = np.arange(int(free.sum()))
    rows, cols, w = [], [], []
    for di, dj, wt in ((1, 0, 1.0), (0, 1, 1.0), (1, 1, SQ2), (1, -1, SQ2)):
        i0, i1 = (0, n - di)
        j0, j1 = (0, m - dj) if dj >= 0 else (-dj, m)
        a = free[i0:i1, j0:j1]
        b = free[i0 + di:i1 + di, j0 + dj:j1 + dj]
        ok = a & b
        if di and dj:
            ok &= free[i0 + di:i1 + di, j0:j1] & free[i0:i1, j0 + dj:j1 + dj]
        ii, jj = np.nonzero(ok)
        rows.append(node[ii + i0, jj + j0]); cols.append(node[ii + i0 + di, jj + j0 + dj]); w.append(np.full(len(ii), wt))
    r, c, ww = np.concatenate(rows), np.concatenate(cols), np.concatenate(w)
    k = int(free.sum())
    return csr_matrix((np.concatenate([ww, ww]), (np.concatenate([r, c]), np.concatenate([c, r]))), shape=(k, k)), node


def sample_pairs(free: np.ndarray, rng: np.random.Generator, n_starts: int, n_goals: int, res: float = rg.RES, min_m: float = MIN_STRAIGHT_M):
    """가장 큰 자유 덩어리 안에서 시작 n_starts x 목표 n_goals. 돌려주는 값: [(시작 셀, 목표 셀, 직선 m, 격자 최단 m)]. 직선이 min_m 아래인 쌍은 버린다."""
    big = gm.largest_component_mask(free)
    cells = np.argwhere(big)
    graph, node = grid_graph(big)
    src = cells[rng.choice(len(cells), min(n_starts, len(cells)), replace=False)]
    dist = dijkstra(graph, directed=False, indices=node[src[:, 0], src[:, 1]])
    out = []
    for s, d in zip(src, dist):
        for t in cells[rng.choice(len(cells), min(n_goals, len(cells)), replace=False)]:
            straight = float(np.linalg.norm((t - s) * res))
            if straight >= min_m and np.isfinite(d[node[t[0], t[1]]]):
                out.append((tuple(s), tuple(t), straight, float(d[node[t[0], t[1]]]) * res))
    return out


def ratio_stats(r: np.ndarray) -> dict:
    return {"median": float(np.median(r)), "p90": float(np.percentile(r, 90)), "gt_1_2": float((r >= 1.2).mean()), "gt_1_5": float((r >= 1.5).mean()), "gt_2_0": float((r >= 2.0).mean())}


def check_room(seed: int, cfg: rg.RoomConfig, table: dict, rng: np.random.Generator, n_starts: int, n_goals: int, planner_pairs: int, n_start_points: int = 64) -> dict:
    spec, room = rg.make_room(seed, cfg)
    g = gm.make_grade_map(room, table)
    free = gm.passable(g)
    big = gm.largest_component_mask(free)
    pairs = sample_pairs(~inflate(~free), rng, n_starts, n_goals)
    tort = np.array([p[3] / p[2] for p in pairs])
    starts = rg.start_points(room, n_start_points, seed)
    sc = np.floor(starts[:, :2] / rg.RES).astype(int)
    starts_ok = bool(big[sc[:, 0], sc[:, 1]].all())
    ratios_p, ratios_raw = [], []
    for k in rng.choice(len(pairs), min(planner_pairs, len(pairs)), replace=False):
        (s, t, straight, short) = pairs[k]
        a, b = (np.array(s) + 0.5) * rg.RES, (np.array(t) + 0.5) * rg.RES
        try:
            p1 = gvd_astar.find_path(g, a, b, straighten=True)
            p0 = gvd_astar.find_path(g, a, b)
        except ValueError:
            continue
        if p1.found and p0.found:
            ratios_p.append(p1.length_m / short)
            ratios_raw.append(p0.length_m / short)
    return {"seed": seed, "tries": spec["tries"], "wall_keep": spec["maze"]["wall_keep"], "free_frac": float(free.mean()), "connected_frac": float(big.sum() / max(free.sum(), 1)),
            "dead_end_tiles": rg.dead_end_tiles(spec), "passage_m": rg.passage_width_m(free), "starts_in_component": starts_ok, "tort": tort, "planner_ratio": np.array(ratios_p), "planner_ratio_raw": np.array(ratios_raw),
            "walls": sum(p["type"] == "wall" for p in spec["primitives"]), "blocked_tiles": len(spec["maze"]["blocked"]), "doors": sum(1 for e in spec["maze"]["edges"] if e[4])}


def judge(rooms: list[dict]) -> dict:
    n = len(rooms)
    tort = np.concatenate([r["tort"] for r in rooms])
    pr = np.concatenate([r["planner_ratio"] for r in rooms])
    st = ratio_stats(tort)
    lo, hi = LINES["free_frac"]
    per = {"free_frac": sum(lo <= r["free_frac"] <= hi for r in rooms), "dead_end": sum(r["dead_end_tiles"] >= LINES["dead_end_min"] for r in rooms),
           "connected": sum(r["connected_frac"] >= LINES["connected_min"] and r["starts_in_component"] for r in rooms), "passage": sum(r["passage_m"] >= LINES["passage_min_m"] for r in rooms)}
    lo5, hi5 = LINES["frac_gt_1_5"]
    lines = [
        ("1 통과 가능 칸 방마다 55~80 %", f"{per['free_frac']}/{n} 방 (최소 {min(r['free_frac'] for r in rooms) * 100:.1f} · 최대 {max(r['free_frac'] for r in rooms) * 100:.1f} %)", per["free_frac"] == n),
        ("2 굴곡 비 중앙값 1.12 이상", f"{st['median']:.3f} (p90 {st['p90']:.2f})", st["median"] >= LINES["tort_median_min"]),
        ("3 굴곡 비 1.2 넘는 쌍 35 % 이상", f"{st['gt_1_2'] * 100:.1f} %", st["gt_1_2"] >= LINES["frac_gt_1_2_min"]),
        ("4 굴곡 비 1.5 넘는 쌍 15~45 %", f"{st['gt_1_5'] * 100:.1f} % (2.0 넘는 쌍 {st['gt_2_0'] * 100:.1f} %)", lo5 <= st["gt_1_5"] <= hi5),
        ("5 막다른 타일 방마다 3 개 이상", f"{per['dead_end']}/{n} 방 (평균 {np.mean([r['dead_end_tiles'] for r in rooms]):.1f} 개)", per["dead_end"] == n),
        ("6 이어짐 98 % 이상 · 시작점 64 개 전부 안", f"{per['connected']}/{n} 방 (최소 {min(r['connected_frac'] for r in rooms) * 100:.1f} %)", per["connected"] == n),
        ("7 가장 좁은 통과 폭 0.8 m 이상", f"{per['passage']}/{n} 방 (최소 {min(r['passage_m'] for r in rooms):.2f} m)", per["passage"] == n),
        ("8 계획기 길 / 격자 최단 중앙값 1.15 이하", f"{np.median(pr):.3f} (p90 {np.percentile(pr, 90):.2f} · 곧게 펴기 끔 {np.median(np.concatenate([r['planner_ratio_raw'] for r in rooms])):.3f} · 쌍 {len(pr)})", float(np.median(pr)) <= LINES["planner_ratio_max"]),
    ]
    return {"lines": [{"name": a, "value": b, "pass": bool(c)} for a, b, c in lines], "all_pass": all(c for _, _, c in lines), "tortuosity": st, "pairs": int(len(tort)), "planner_pairs": int(len(pr))}


def table_text(res: dict, rooms: list[dict]) -> str:
    out = [f"HiPAN 방 {len(rooms)} 개 판정 (시드 {rooms[0]['seed']}~{rooms[-1]['seed']} · wall_keep {sorted({r['wall_keep'] for r in rooms})} · 굴곡 쌍 {res['pairs']} · 계획기 쌍 {res['planner_pairs']})", "",
           "| 판정 줄 | 값 | 판정 |", "|---|---|---|"]
    out += [f"| {l['name']} | {l['value']} | {'통과' if l['pass'] else '실패'} |" for l in res["lines"]]
    out += ["", f"전체: {'통과' if res['all_pass'] else '실패'}", "",
            "참고: 방당 수락 재시도 평균 %.1f회 (최대 %d) · 방당 막힌 타일 평균 %.1f · 벽 조각 평균 %.0f · 문 평균 %.1f" % (
                np.mean([r["tries"] for r in rooms]), max(r["tries"] for r in rooms), np.mean([r["blocked_tiles"] for r in rooms]), np.mean([r["walls"] for r in rooms]), np.mean([r["doors"] for r in rooms]))]
    for k in sorted({r["wall_keep"] for r in rooms}):
        sub = [r for r in rooms if r["wall_keep"] == k]
        st = ratio_stats(np.concatenate([r["tort"] for r in sub]))
        out.append(f"keep {k}: 방 {len(sub)} · 굴곡 비 중앙값 {st['median']:.3f} · 1.2 넘는 쌍 {st['gt_1_2'] * 100:.0f} % · 1.5 넘는 쌍 {st['gt_1_5'] * 100:.0f} % · 막다른 타일 평균 {np.mean([r['dead_end_tiles'] for r in sub]):.1f}")
    return "\n".join(out)


def figure(seeds: list[int], cfg: rg.RoomConfig, table: dict, path: Path, rng: np.random.Generator) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 3, figsize=(21, 14))
    for ax, seed in zip(axes.ravel(), seeds):
        spec, room = rg.make_room(seed, cfg)
        g = gm.make_grade_map(room, table)
        free = gm.passable(g)
        ax.imshow((~free).T, cmap="gray_r", origin="lower", extent=(0, rg.ROOM_M, 0, rg.ROOM_M), vmin=0, vmax=1.3)
        pairs = sample_pairs(~inflate(~free), rng, 6, 4)
        shown, rr = 0, []
        for (s, t, straight, short) in pairs:
            if shown >= 4:
                break
            a, b = (np.array(s) + 0.5) * rg.RES, (np.array(t) + 0.5) * rg.RES
            p = gvd_astar.find_path(g, a, b, straighten=True)
            if not p.found or straight < 8.0:
                continue
            ax.plot(p.points[:, 0], p.points[:, 1], lw=2.2)
            ax.plot([a[0], b[0]], [a[1], b[1]], ls=":", lw=0.9, color="k")
            ax.plot(*a, "*", ms=13, color="tab:red"); ax.plot(*b, "o", ms=8, color="tab:green")
            rr.append(p.length_m / straight); shown += 1
        m = spec["metrics"]
        ax.set_title(f"room seed {seed} (keep {spec['maze']['wall_keep']}): passable {m['free_frac'] * 100:.0f} % · dead-end tiles {m['dead_end_tiles']} · narrowest {m['passage_m']} m\n"
                     f"planner path / straight {', '.join(f'{x:.2f}' for x in rr)}", fontsize=12)
        ax.set_xticks(range(0, 21, 2)); ax.set_yticks(range(0, 21, 2)); ax.grid(alpha=0.15)
    fig.suptitle("HiPAN G3 rooms, top view (black = wall or blocked block, colour = planner path (straightened), dotted = straight line, star = start, circle = goal)", fontsize=14)
    fig.tight_layout()
    fig.savefig(path, dpi=70)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--count", type=int, default=100); p.add_argument("--seed0", type=int, default=0); p.add_argument("--out", required=True)
    p.add_argument("--pairs-starts", type=int, default=10); p.add_argument("--pairs-goals", type=int, default=15); p.add_argument("--planner-pairs", type=int, default=20)
    p.add_argument("--figure-seeds", default="1000,1001,1002,1003,1004,1005", help="그림에 그릴 방 시드 여섯 (G3 방과 같게). 빈 문자열이면 그림 없음")
    p.add_argument("--grade-table", default=str(GRADE_TABLE))
    a = p.parse_args(argv)
    t0 = time.time()
    cfg, table = rg.RoomConfig(sparse_patch_kinds=()), gm.load_grade_table(a.grade_table)
    rng = np.random.default_rng(0)
    rooms = []
    for seed in range(a.seed0, a.seed0 + a.count):
        rooms.append(check_room(seed, cfg, table, rng, a.pairs_starts, a.pairs_goals, a.planner_pairs))
        if (len(rooms)) % 10 == 0:
            print(f"{len(rooms)}/{a.count} rooms · {time.time() - t0:.0f} s", flush=True)
    res = judge(rooms)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    text = table_text(res, rooms)
    (out / "rooms_judge.md").write_text(text + "\n", encoding="utf-8")
    slim = [{k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in r.items() if k not in ("tort", "planner_ratio", "planner_ratio_raw")} for r in rooms]
    (out / "rooms_judge.json").write_text(json.dumps({"config": {"layout": cfg.layout, "block_frac": cfg.block_frac, "keep_choices": cfg.keep_choices, "door_frac": cfg.door_frac, "door_m": cfg.door_m, "free_range": cfg.free_range,
                                                       "min_dead_end_tiles": cfg.min_dead_end_tiles, "min_passage_m": cfg.min_passage_m}, "lines": LINES, "result": res, "rooms": slim},
                                                      ensure_ascii=False, indent=1), encoding="utf-8")
    if a.figure_seeds:
        figure([int(x) for x in a.figure_seeds.split(",")], cfg, table, out / "rooms_top_g3.png", np.random.default_rng(5))
    print(text)
    return 0 if res["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
