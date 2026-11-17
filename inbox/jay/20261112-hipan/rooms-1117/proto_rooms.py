"""길과 벽으로 된 방의 원형 생성기 (설계 DESIGN-HIPAN-ROOMS-1117 의 숫자를 정하려고 만든 것 · planner-lx 11/17 · numpy 만 · 코드 정본 아님).

방 20 x 20 m · 격자 0.1 m · 타일 2 m (10 x 10).
 1. 막힌 덩어리: 타일의 block_frac 를 1~3 타일짜리 덩어리로 막는다 (논문 그림 2 의 큰 덩어리).
 2. 얇은 벽: 남은 자유 타일 위에 미로 (무작위 신장 나무) 를 만들고, 나무에 없는 타일 경계의 벽을 keep 확률로만 남긴다
    (keep 1 = 완전 미로 · 막다른 길 많음 / keep 0 = 벽 없음). 남긴 벽에도 door 확률로 문 (폭 1.0 m) 을 낸다.
 3. 바깥 둘레 벽 0.3 m. 자유 타일은 한 덩어리로 이어져 있다 (신장 나무가 보장).
잰다: 통과 가능 칸 비율 · 최단 (0.1 m 격자 8 방향) / 직선 비의 분포 · 막다른 타일 수 (자유 이웃이 하나인 타일).
쓰는 법: python -I proto_rooms.py [그림만이면 fig]"""
import heapq
import sys

import numpy as np

N, TILE, NT, RES = 200, 20, 10, 0.1
WALL_T = 2            # 얇은 벽 두께 0.2 m
DOOR = 10             # 문 폭 1.0 m
SQ2 = 2 ** 0.5


def make(seed, block_frac=0.22, keep=0.55, door=0.35):
    rng = np.random.default_rng(seed)
    blocked = np.zeros((NT, NT), bool)
    target = int(block_frac * NT * NT); tries = 0
    while blocked.sum() < target and tries < 500:
        tries += 1
        i, j = rng.integers(0, NT, 2); h, w = rng.integers(1, 3, 2) if rng.random() < 0.7 else (1, 1)
        if rng.random() < 0.3:
            h, w = (3, 1) if rng.random() < 0.5 else (1, 3)
        cand = blocked.copy(); cand[i:i + h, j:j + w] = True
        if connected(~cand):
            blocked = cand
    free_t = ~blocked
    # 신장 나무 (자유 타일)
    cells = [tuple(c) for c in np.argwhere(free_t)]
    start = cells[rng.integers(len(cells))]
    seen = {start}; stack = [start]; open_edge = set()
    while stack:
        c = stack[-1]
        nb = [(c[0] + a, c[1] + b) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)) if 0 <= c[0] + a < NT and 0 <= c[1] + b < NT and free_t[c[0] + a, c[1] + b] and (c[0] + a, c[1] + b) not in seen]
        if not nb:
            stack.pop(); continue
        n = nb[rng.integers(len(nb))]
        seen.add(n); open_edge.add(frozenset((c, n))); stack.append(n)
    grid = np.zeros((N, N), bool)                       # True = 막힘
    for i, j in np.argwhere(blocked):
        grid[i * TILE:(i + 1) * TILE, j * TILE:(j + 1) * TILE] = True
    walls = []
    for i in range(NT):
        for j in range(NT):
            if not free_t[i, j]:
                continue
            for a, b in ((1, 0), (0, 1)):
                p, q = i + a, j + b
                if p >= NT or q >= NT or not free_t[p, q]:
                    continue
                e = frozenset(((i, j), (p, q)))
                if e in open_edge:
                    continue                             # 나무 가지: 늘 열림
                if rng.random() >= keep:
                    continue                             # 벽을 안 세움
                has_door = rng.random() < door
                off = int(rng.integers(3, TILE - DOOR - 2)) if has_door else None
                if a == 1:                               # x 방향 경계: x = p * TILE 에 y 로 뻗은 벽
                    x0 = p * TILE - WALL_T // 2; seg = np.ones(TILE, bool)
                    if has_door:
                        seg[off:off + DOOR] = False
                    grid[x0:x0 + WALL_T, j * TILE:(j + 1) * TILE] |= seg[None, :]
                else:
                    y0 = q * TILE - WALL_T // 2; seg = np.ones(TILE, bool)
                    if has_door:
                        seg[off:off + DOOR] = False
                    grid[i * TILE:(i + 1) * TILE, y0:y0 + WALL_T] |= seg[:, None]
                walls.append((i, j, a, b, has_door))
    grid[:3, :] = True; grid[-3:, :] = True; grid[:, :3] = True; grid[:, -3:] = True
    # 막다른 타일: 벽 · 문을 따져 실제로 드나들 수 있는 이웃 타일이 하나뿐
    closed = {frozenset(((i, j), (i + a, j + b))) for i, j, a, b, d in walls if not d}
    dead = 0
    for c in cells:
        deg = 0
        for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + a, c[1] + b)
            if 0 <= n[0] < NT and 0 <= n[1] < NT and free_t[n] and frozenset((c, n)) not in closed:
                deg += 1
        dead += deg == 1
    return grid, {"blocked_tiles": int(blocked.sum()), "walls": len(walls), "doors": sum(1 for w in walls if w[4]), "dead_end_tiles": dead}


def connected(free):
    cells = np.argwhere(free)
    if len(cells) == 0:
        return False
    seen = np.zeros_like(free); st = [tuple(cells[0])]; seen[st[0]] = True; n = 1
    while st:
        i, j = st.pop()
        for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            p, q = i + a, j + b
            if 0 <= p < free.shape[0] and 0 <= q < free.shape[1] and free[p, q] and not seen[p, q]:
                seen[p, q] = True; n += 1; st.append((p, q))
    return n == len(cells)


def dijkstra(free, src, parent=False):
    n, m = free.shape
    d = np.full((n, m), np.inf); d[src] = 0.0; pq = [(0.0, src)]; par = {}
    while pq:
        c, (i, j) = heapq.heappop(pq)
        if c > d[i, j]:
            continue
        for di, dj, w in ((1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, SQ2), (1, -1, SQ2), (-1, 1, SQ2), (-1, -1, SQ2)):
            a, b = i + di, j + dj
            if 0 <= a < n and 0 <= b < m and free[a, b] and (w == 1 or (free[i, b] and free[a, j])) and c + w < d[a, b]:
                d[a, b] = c + w; heapq.heappush(pq, (c + w, (a, b)))
                if parent:
                    par[(a, b)] = (i, j)
    return (d, par) if parent else d


def inflate(grid, r=2):
    """로봇 반폭 0.2 m 만큼 막힌 칸을 부풀린다 (문 1.0 m 는 0.6 m 로 남는다)."""
    g = grid.copy()
    for _ in range(r):
        h = g.copy(); h[1:] |= g[:-1]; h[:-1] |= g[1:]; h[:, 1:] |= g[:, :-1]; h[:, :-1] |= g[:, 1:]; g = h
    return g


def detour(grid, rng, starts=10, goals=15, min_m=4.0):
    free = ~inflate(grid)
    cells = np.argwhere(free); out = []
    for s in cells[rng.choice(len(cells), starts, replace=False)]:
        d = dijkstra(free, tuple(s))
        for t in cells[rng.choice(len(cells), goals, replace=False)]:
            st = float(np.linalg.norm((t - s) * RES))
            if st >= min_m and np.isfinite(d[tuple(t)]):
                out.append(d[tuple(t)] * RES / st)
    return np.array(out)


def table():
    rng = np.random.default_rng(1)
    print("| block_frac | keep | door | 통과 가능 칸 | 굴곡 비 중앙값 | p90 | 1.2 넘는 쌍 | 1.5 넘는 쌍 | 2.0 넘는 쌍 | 막다른 타일 (방당 평균) | 벽 · 문 (방당) |")
    for bf, keep, door in ((0.22, 0.0, 0.35), (0.22, 0.35, 0.35), (0.22, 0.55, 0.35), (0.22, 0.75, 0.35), (0.22, 1.0, 0.0), (0.30, 0.55, 0.35), (0.15, 0.55, 0.35)):
        R, fr, dead, w, dr = [], [], [], [], []
        for seed in range(24):
            g, info = make(seed, bf, keep, door)
            R.append(detour(g, rng)); fr.append((~g).mean()); dead.append(info["dead_end_tiles"]); w.append(info["walls"]); dr.append(info["doors"])
        r = np.concatenate(R)
        print(f"| {bf} | {keep} | {door} | {np.mean(fr) * 100:.0f} % | {np.median(r):.2f} | {np.percentile(r, 90):.2f} | {(r >= 1.2).mean() * 100:.0f} % | {(r >= 1.5).mean() * 100:.0f} % | {(r >= 2.0).mean() * 100:.0f} % | {np.mean(dead):.1f} | {np.mean(w):.0f} · {np.mean(dr):.0f} |", flush=True)


def figure():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rng = np.random.default_rng(5)
    fig, axes = plt.subplots(1, 3, figsize=(21, 7.4))
    for ax, seed in zip(axes, (3, 11, 17)):
        g, info = make(seed, 0.22, 0.55, 0.35)
        free = ~inflate(g); cells = np.argwhere(free)
        ax.imshow(g.T, cmap="gray_r", origin="lower", extent=(0, 20, 0, 20), vmin=0, vmax=1.3)
        k = 0; ratios = []
        while k < 4:
            s = tuple(cells[rng.integers(len(cells))]); d, par = dijkstra(free, s, parent=True)
            t = tuple(cells[rng.integers(len(cells))])
            st = np.linalg.norm((np.array(t) - np.array(s)) * RES)
            if st < 8 or not np.isfinite(d[t]):
                continue
            path = [t]
            while path[-1] != s:
                path.append(par[path[-1]])
            p = (np.array(path) + 0.5) * RES
            ax.plot(p[:, 0], p[:, 1], lw=2.2); ax.plot([p[0, 0], p[-1, 0]], [p[0, 1], p[-1, 1]], ls=":", lw=0.9, color="k")
            ax.plot(*p[-1], "o", ms=8, color="tab:green"); ax.plot(*p[0], "*", ms=13, color="tab:red")
            ratios.append(d[t] * RES / st); k += 1
        ax.set_title(f"seed {seed}: passable {(~g).mean() * 100:.0f} % · walls {info['walls']} (doors {info['doors']}) · dead-end tiles {info['dead_end_tiles']} · path/straight {', '.join(f'{x:.2f}' for x in ratios)}", fontsize=11)
        ax.set_xticks(range(0, 21, 2)); ax.set_yticks(range(0, 21, 2)); ax.grid(alpha=0.15)
    fig.suptitle("prototype rooms 20 x 20 m (black = wall or blocked block, colour = shortest path with 0.2 m robot margin, dotted = straight, circle = start, star = goal)", fontsize=13)
    fig.tight_layout(); fig.savefig("/home/jay/mai/tmp/planner/hipan_rooms/proto_rooms.png", dpi=80)
    print("figure saved")


if __name__ == "__main__":
    figure() if len(sys.argv) > 1 else table()
