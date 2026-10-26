"""듬성 칸 평가의 지형 종류별 집계 (SONNET-X26j · X26m). 순수 numpy, Kit 없음.

종류마다: env 수 · 끝 생존 수 · 몸 vx 적분 중앙값 · «건넘» 수 · 떨어진 env 수.
건넘 = 살아 있고 발판 위에 있는 동안 칸 원점(출발 단)에서 전진(+x) 거리가 도착 단까지의 거리 REFERENCE_M(start_sheet, 6.5 m)에 닿음.
발판 위 = 몸 높이가 자리 잡은 서 있는 높이(step 25~50 중앙값)보다 drop_tol_m(= EDGE_DROP_M 의 절반)넘게 내려가지 않음. 한 번 내려가면(구덩이 바닥 · 빔 아래) 그 시점부터 건넘 불가(되돌아 올라가도 안 침).
칸 상자는 쓰지 않는다: 같은 (종류, 레벨)이어도 칸 기하가 난이도 무작위 정도(시드는 (종류, 난이도) 해시, 난이도는 줄 안 무작위)로 달라 저장된 평가의 정확한 상자를 모른다.
원자료(vx · fwd · alive · pos · dones 배열)는 평가가 npz 로 남기므로 이 모듈로 다시 낼 수 있다: python -m foothold_s2.eval.kind_stats --recompute <npz 또는 폴더 글롭...>
"""

from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np

from foothold_s2.eval import start_sheet as ss

EDGE_DROP_M = 0.2                    # sparse_terrains.EDGE_DROP_M 와 같은 값(그 모듈은 trimesh 등을 부르지 않지만 순환을 피해 값만 둔다, 시험이 같은지 대조)
DROP_TOL_M = EDGE_DROP_M / 2.0


def by_kind(kinds, vx, fwd, alive, dt: float, threshold_m: float = ss.REFERENCE_M, window_s: float | None = None, pos=None, drop_tol_m: float = DROP_TOL_M) -> dict:
    """kinds: env 별 종류 이름 (N). vx · fwd · alive: (S, N). pos: (S, N, 3) 칸 원점 기준 월드 위치(없으면 발판 판정을 못 해 fall_test False 로 낸다). window_s None = 기록 전체."""
    vx, fwd, alive = np.asarray(vx, dtype=float), np.asarray(fwd, dtype=float), np.asarray(alive, dtype=bool)
    steps = fwd.shape[0] if window_s is None else min(int(round(window_s / dt)), fwd.shape[0])
    dist = (vx * alive).sum(0) * dt
    ok = alive[:steps].copy()                                         # 쓰러져 reset 된 뒤의 순간이동 위치는 세지 않는다

    if pos is not None:
        z = np.asarray(pos, dtype=float)[:steps, :, 2]
        z_ref = np.median(z[min(25, steps - 1):min(50, steps)], axis=0)       # 시작 높이: reset 직후 떨어지며 자리 잡은 뒤(0.5~1 s)의 서 있는 높이(step 0 의 spawn 높이 0.4 m 는 쓰지 않는다)
        low = z < (z_ref - drop_tol_m)[None, :]
        fell = np.logical_or.accumulate(low & ok, axis=0)             # 살아 있는 동안 한 번이라도 내려가면 그 뒤로 영구
        ok &= ~fell
        fell_any = fell[-1]
    else:
        fell_any = np.zeros(fwd.shape[1], dtype=bool)
    fwd_ok = np.where(ok, fwd[:steps], -np.inf)
    fwd_max = fwd_ok.max(0)
    fwd_max_fin = np.where(np.isfinite(fwd_max), fwd_max, 0.0)
    crossed = fwd_max >= threshold_m
    kinds = np.asarray(list(kinds))
    out = {}

    for k in dict.fromkeys(kinds.tolist()):
        m = kinds == k
        out[k] = {"envs": int(m.sum()), "alive_at_end": int(alive[-1][m].sum()), "body_vx_integral_median_m": float(np.median(dist[m])),
                  "crossed": int(crossed[m].sum()), "fell": int(fell_any[m].sum()), "fwd_max_median_m": float(np.median(fwd_max_fin[m])),
                  "crossing_ratio_median": float(np.median(np.clip(fwd_max_fin[m] / threshold_m, 0.0, 1.0))),
                  "crossed_rule": f"살아 있고 몸 높이가 시작보다 {drop_tol_m:g} m 넘게 내려가지 않은 동안 칸 원점에서 전진 거리 >= {threshold_m:g} m (도착 단), 기록 {steps * dt:g} s",
                  "fall_test": pos is not None}

    return out


def from_files(map_modes_json: str, npz: str, window_s: float | None = None) -> dict:
    """저장한 평가 결과 json 과 npz 로 다시 낸다."""
    res = json.load(open(map_modes_json, encoding="utf-8"))
    a = np.load(npz)
    kinds = [t["kind"] for t in res["fixed_terrain"]["tiles"]]
    pos = a["pos"] if "pos" in a.files else None

    return by_kind(kinds, a["vx"], a["fwd"], a["alive"], float(a["dt"]), ss.REFERENCE_M, window_s, pos)


def recompute(patterns, out_json=None) -> dict:
    """npz 경로(글롭 허용)마다 같은 폴더의 map_modes.json 과 짝지어 종류별 표를 다시 낸다. 반환: {npz 경로: 종류별 표 또는 {"error": ...}}."""
    table = {}

    for pat in patterns:
        for npz in sorted(glob.glob(pat)):
            mm = os.path.join(os.path.dirname(npz), "map_modes.json")

            if not os.path.isfile(mm):
                table[npz] = {"error": "map_modes.json 없음(평가가 끝까지 안 갔거나 옛 폴더)"}
                continue
            try:
                table[npz] = from_files(mm, npz)
            except Exception as exc:                                  # 한 폴더 실패가 나머지를 막지 않는다
                table[npz] = {"error": repr(exc)}

    if out_json:
        json.dump(table, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    return table


if __name__ == "__main__":
    args = sys.argv[1:]

    if args and args[0] == "--recompute":
        out = None
        if "--out" in args:
            i = args.index("--out")
            out = args[i + 1]
            args = args[:i] + args[i + 2:]
        print(json.dumps(recompute(args[1:], out), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(from_files(args[0], args[1]), ensure_ascii=False, indent=1))
