"""듬성 칸 평가의 지형 종류별 집계 (SONNET-X26j). 순수 numpy, Kit 없음.

종류마다: env 수 · 끝 생존 수 · 몸 vx 적분 중앙값 · «건넘» 수. 건넘 = 처음 window_s 초 안에 칸 원점에서 전진(+x) 방향 거리가 한 번이라도 칸 길이의 절반 이상.
칸 길이는 지형 cfg 의 size[0] 에서 읽어 넘긴다(여기서 정하지 않는다). 원자료(vx · fwd · alive 배열)는 평가가 npz 로 남기므로 이 함수로 다시 낼 수 있다.
"""

from __future__ import annotations

import json
import sys

import numpy as np


def by_kind(kinds, vx, fwd, alive, dt: float, tile_len_m: float, window_s: float = 6.0) -> dict:
    """kinds: env 별 종류 이름 (N). vx · fwd · alive: (S, N) 몸 vx · 칸 원점에서 전진 거리 · 그 스텝 시작에 살아 있었는가."""
    vx, fwd, alive = np.asarray(vx, dtype=float), np.asarray(fwd, dtype=float), np.asarray(alive, dtype=bool)
    steps = min(int(round(window_s / dt)), fwd.shape[0])
    dist = (vx * alive).sum(0) * dt
    fwd_alive = np.where(alive[:steps], fwd[:steps], -np.inf)                       # 쓰러져 reset 된 뒤의 순간이동 위치는 세지 않는다
    fwd_max = fwd_alive.max(0)
    crossed = fwd_max >= tile_len_m / 2.0
    kinds = np.asarray(list(kinds))
    out = {}

    for k in dict.fromkeys(kinds.tolist()):
        m = kinds == k
        out[k] = {"envs": int(m.sum()), "alive_at_end": int(alive[-1][m].sum()), "body_vx_integral_median_m": float(np.median(dist[m])),
                  "crossed": int(crossed[m].sum()), "fwd_max_median_m": float(np.median(np.where(np.isfinite(fwd_max[m]), fwd_max[m], 0.0))), "crossed_rule": f"{window_s:g} s 안에 칸 원점에서 전진 거리 >= 칸 길이 {tile_len_m:g} m 의 절반"}

    return out


def from_files(map_modes_json: str, npz: str, mode: str, cmd: str, window_s: float = 6.0) -> dict:
    """저장한 평가 결과 json 과 npz 로 다시 낸다."""
    res = json.load(open(map_modes_json, encoding="utf-8"))
    a = np.load(npz)
    kinds = [t["kind"] for t in res["fixed_terrain"]["tiles"]]

    return by_kind(kinds, a["vx"], a["fwd"], a["alive"], float(a["dt"]), float(a["tile_len_m"]), window_s)


if __name__ == "__main__":
    print(json.dumps(from_files(*sys.argv[1:5]), ensure_ascii=False, indent=1))
