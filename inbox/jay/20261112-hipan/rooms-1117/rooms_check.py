"""HiPAN G3 방 여섯을 논문 벤치마크 방과 같은 자로 잰다 (planner-lx 11/17 · lead 21:50 · CPU).
우리 방: G3 영수증 (room_manifest.json 의 rooms) 을 room_generator.build_room 으로 다시 세우고 등급 지도 (통과 가능 칸) 를 만든다.
논문 방: benchmark-rooms/rooms.npz (Fig. 5 실측 격자 · 0 자유 · 1 머리 위 · 2 수직). 머리 위는 통과로 본 판과 막힌 판 둘 다.
같은 자: 0.1 m 격자 8 방향 최단 길이 (Dijkstra) / 직선 거리. 시작 20 곳 x 목표 15 곳 (직선 2 m 이상 · 같은 덩어리 안).
더: 우리 계획기 (gvd_astar.find_path) 로 낸 경로 길이 / 직선 도 우리 방에서 잰다 (학습이 실제로 쓰는 길).
출력: 표 + rooms_top.png (우리 여섯 · 논문 넷 · 벽과 표본 경로)."""
import heapq
import json
import sys

import numpy as np

sys.path.insert(0, "/home/jay/mai/tmp/planner/hipan_rooms/src")
from foothold_s2.nav import grade_map as gm  # noqa: E402
from foothold_s2.nav import gvd_astar, room_generator as rg  # noqa: E402

R = "/home/jay/data/foothold/hipan/runpod_hipan_g3/20261117_210740/remote/rooms_receipt"
OUT = "/home/jay/mai/tmp/planner/hipan_rooms"
SQ2 = 2 ** 0.5


def dijkstra(free, src):
    n, m = free.shape
    d = np.full((n, m), np.inf); d[src] = 0.0; pq = [(0.0, src)]
    while pq:
        c, (i, j) = heapq.heappop(pq)
        if c > d[i, j]:
            continue
        for di, dj, w in ((1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, SQ2), (1, -1, SQ2), (-1, 1, SQ2), (-1, -1, SQ2)):
            a, b = i + di, j + dj
            if 0 <= a < n and 0 <= b < m and free[a, b] and (w == 1 or (free[i, b] and free[a, j])) and c + w < d[a, b]:
                d[a, b] = c + w; heapq.heappush(pq, (c + w, (a, b)))
    return d


def detour(free, rng, starts=20, goals=15, res=0.1, min_m=2.0):
    """(직선 m, 최단 m) 쌍들. 가장 큰 자유 덩어리 안에서만."""
    big = gm.largest_component_mask(free)
    cells = np.argwhere(big)
    out = []
    for s in cells[rng.choice(len(cells), starts, replace=False)]:
        d = dijkstra(big, tuple(s))
        for t in cells[rng.choice(len(cells), goals * 3, replace=False)]:
            st = float(np.linalg.norm((t - s) * res))
            if st >= min_m and np.isfinite(d[tuple(t)]):
                out.append((st, float(d[tuple(t)]) * res))
            if len([1 for _ in out]) % goals == 0 and len(out) and len(out) // goals >= 1 and len(out) % goals == 0:
                pass
    return np.array(out), big


def line(name, free, pairs, extra=""):
    r = pairs[:, 1] / pairs[:, 0]
    return (f"| {name} | {free.mean() * 100:.1f} % | {np.median(r):.2f} | {np.percentile(r, 90):.2f} | {(r >= 1.2).mean() * 100:.0f} % | {(r >= 1.5).mean() * 100:.0f} % | "
            f"{np.median(pairs[:, 0]):.1f} m | {len(r)} | {extra} |")


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    man = json.load(open(R + "/room_manifest.json"))
    table = gm.load_grade_table("/home/jay/mai/tmp/planner/hipan_rooms/src/foothold_s2/nav/grade_table_draft.yaml")
    rng = np.random.default_rng(0)
    rows = ["| 방 | 통과 가능 칸 | 최단/직선 중앙값 | p90 | 1.2 배 넘는 쌍 | 1.5 배 넘는 쌍 | 직선 중앙값 | 쌍 수 | 덧 |", "|---|---|---|---|---|---|---|---|---|"]
    fig, axes = plt.subplots(2, 5, figsize=(25, 10)); axes = axes.ravel(); k = 0
    for i, spec in enumerate(man["rooms"]):
        room = rg.build_room({"seed": spec.get("seed", i), "size_m": man["size_m"], "tiles": spec.get("tiles"), "primitives": spec["primitives"]})
        g = gm.make_grade_map(room, table)
        free = gm.passable(g)
        pairs, big = detour(free, rng)
        prim = {}
        for p in spec["primitives"]:
            prim[p["type"]] = prim.get(p["type"], 0) + 1
        # 우리 계획기 길
        ratios = []
        pts_keep = []
        for _ in range(40):
            s, t = gm.sample_free_points(g, rng, 2)
            if np.linalg.norm(s - t) < 2.0:
                continue
            try:
                p = gvd_astar.find_path(g, s, t)
            except ValueError:
                continue
            if p.found:
                L = float(np.linalg.norm(np.diff(p.points, axis=0), axis=1).sum()); ratios.append(L / float(np.linalg.norm(s - t))); pts_keep.append(p.points)
        ratios = np.array(ratios)
        extra = f"계획기 길/직선 중앙값 {np.median(ratios):.2f} · p90 {np.percentile(ratios, 90):.2f} (n {len(ratios)}) · 벽 {prim.get('wall', 0)} 탁자 {prim.get('table', 0)} 상자 {prim.get('box', 0)} 거친 면 {prim.get('rough', 0)} 계단 {prim.get('stairs', 0)}"
        rows.append(line(f"우리 방 {i}", free, pairs, extra))
        ax = axes[k]; k += 1
        ax.imshow(~free.T, cmap="gray_r", origin="lower", extent=(0, 20, 0, 20), vmin=0, vmax=1.6)
        for q in pts_keep[:8]:
            ax.plot(q[:, 0], q[:, 1], lw=1.6)
            ax.plot([q[0, 0], q[-1, 0]], [q[0, 1], q[-1, 1]], lw=0.6, ls=":", color="k")
        ax.set_title(f"our room {i}: passable {free.mean() * 100:.0f} % · walls {prim.get('wall', 0)}", fontsize=13); ax.set_xticks([]); ax.set_yticks([])
    z = np.load("/home/jay/mai/wt/foothold-lab/fable-25a/inbox/jay/20261112-hipan/benchmark-rooms/rooms.npz")
    for name in z.files:
        grid = z[name]
        for lab, free in (("머리 위 통과", grid != 2), ("머리 위 막음", grid == 0)):
            pairs, big = detour(free, rng)
            rows.append(line(f"논문 {name} ({lab})", free, pairs, f"격자 {grid.shape}"))
        if k < len(axes):
            ax = axes[k]; k += 1
            ax.imshow(grid, cmap="gray_r", vmin=0, vmax=2.6); ax.set_title(f"paper Fig. 5 {name}: free {(grid == 0).mean() * 100:.0f} %", fontsize=13); ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("top view: our G3 rooms (black = not passable, colour = planner paths, dotted = straight line) vs paper benchmark rooms (grey = overhead, black = vertical)", fontsize=15)
    fig.tight_layout(); fig.savefig(OUT + "/rooms_top.png", dpi=80)
    print("\n".join(rows))


if __name__ == "__main__":
    main()
