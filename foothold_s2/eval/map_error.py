"""X27m: 복원 지도 오차 |refined - gt_map| (cm). 영상의 오차 숫자와 같은 정정의(runner-26a compose_25e.recon_error_series).

한 정책 step 의 오차 = nanmean(|refined - gt_map|) * 100 (512 칸 평균, cm). gt_map 의 결측 표식(-1.0)도 빼지 않는다(영상 식과 같게, NaN 만 뺀다).
추가로 step 의 «가장 큰 한 칸 오차» (nanmax, cm)를 같이 남긴다. env 별 값은 살아 있는 step 만으로 낸다.
이 모듈은 평가 루프(eval_map_modes)가 부르고, 종류 x 레벨 집계(report)는 저장된 env_arrays npz 만 읽는다.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

DEFINITION = ("(a) inrange = 정답 지도가 -1.0 이 아닌 칸만의 nanmean(|refined - gt_map|) * 100 [cm] 과 nanmax [cm]. 정답 -1.0 은 두 경우가 섞인 포화값이다: "
              "광선이 지형을 못 맞힘(NaN · Inf 를 -1.0 으로 바꿈) 또는 기준 높이보다 1 m 이상 아래(clip, start_obs.height_rel_base). 둘 다 (a) 에서 빠지므로 깊은 구덩이 바닥도 (a) 에 없다; "
              "(b) all = 정답 -1.0 칸도 넣은 nanmean(|refined - gt_map|) * 100 [cm] (512 칸, 영상 compose_25e.recon_error_series 와 같은 식) 과 nanmax; "
              "(c) gt_sat_frac = 정답이 -1.0 인 칸의 비율, 그것을 ray_miss_frac(광선 못 맞힘, 센서 원자료가 비유한)과 clip_low_frac(원자료가 유한하고 <= -1 m)로 가른 비율; "
              "(d) nonfinite_cells = |refined - gt_map| 가 비유한(NaN · ±Inf)인 칸 수. 비유한 칸은 (a) (b) 의 평균 · 최대에서 빼되 조용히 버리지 않고 (d) 로 세어 남긴다; "
              "env 별 값은 살아 있는 step 에서만(mean = step 값의 평균, cellmax = step 칸 최대의 최댓값). 표의 머리는 (a); (b) 는 -1.0 칸 하나가 100 cm 안팎으로 평균을 끌어올려 «복원이 나쁨» 과 «정답이 포화» 가 섞인다")
SERIES = ("inrange_mean", "inrange_cellmax", "all_mean", "all_cellmax", "gt_sat_frac", "nonfinite_cells", "ray_miss_frac", "clip_low_frac")                     # step_error 가 돌려주는 순서


def step_error(refined, gt_map, rel=None):
    """(N,32,16) 두 텐서(torch) -> 여덟 (N,) torch 텐서 (SERIES 순서). rel = 센서 원자료 z_hit - z_base (N,512), 없으면 ray_miss_frac · clip_low_frac 은 NaN. cm 는 x100. 유효 칸이 하나도 없으면 valid_* 는 NaN. 비유한 칸(NaN · ±Inf)은 평균 · 최대에서 빼고 nonfinite_cells 로 센다."""
    import torch

    n = refined.shape[0]
    d = (refined.detach().float() - gt_map.detach().float()).abs().reshape(n, -1)
    miss = (gt_map.detach().float().reshape(n, -1) == -1.0)
    fin = torch.isfinite(d)
    full_nan = torch.full_like(d, float("nan"))
    d = torch.where(fin, d, full_nan)                                                         # 비유한 칸은 NaN 으로 바꿔 평균 · 최대에서 뺀다(개수는 아래에서 센다)

    def nmean(x):
        return torch.nanmean(x, dim=1) * 100.0

    def nmax(x):
        m = torch.where(torch.isnan(x), torch.full_like(x, float("-inf")), x).amax(dim=1) * 100.0

        return torch.where(torch.isinf(m), torch.full_like(m, float("nan")), m)

    dv = torch.where(miss, full_nan, d)

    if rel is None:
        ray = clip = torch.full((n,), float("nan"), device=d.device)
    else:
        r = rel.detach().float().reshape(n, -1)
        ray = (~torch.isfinite(r)).float().mean(dim=1)                                          # 광선이 못 맞힘(NaN · ±Inf): start_obs 가 -1.0 으로 바꾼다
        clip = (torch.isfinite(r) & (r <= -1.0)).float().mean(dim=1)                            # 맞혔지만 기준 높이보다 1 m 이상 아래: clamp 로 -1.0

    return nmean(dv), nmax(dv), nmean(d), nmax(d), miss.float().mean(dim=1), (~fin).float().sum(dim=1), ray, clip


def record(last: dict, result, gt_map, rel=None) -> None:
    """_advance 의 반환값(result[2] = out 사전)에 refined 가 있으면 이번 step 의 오차 여덟 값을 last["e"] 에 둔다(지도 없는 체크포인트는 비워 둔다)."""
    out = result[2]

    if isinstance(out, dict) and out.get("refined") is not None:
        last["e"] = step_error(out["refined"], gt_map, rel)

        if rel is not None:                                                                     # 센서 원자료에서 정답 지도를 다시 만들어 넘겨받은 gt_map 과 같은지(분류의 근거) 최대 차이를 쌓는다
            import torch

            g = torch.nan_to_num(rel.detach().float().reshape(gt_map.shape[0], -1), nan=-1.0, posinf=-1.0, neginf=-1.0).clamp(-1.0, 1.0)
            last["rebuild_maxdiff"] = max(float(last.get("rebuild_maxdiff", 0.0)), float((g - gt_map.detach().float().reshape(g.shape)).abs().max()))
    else:
        last["e"] = None


def _mean_alive(series, alive):
    x, al = np.asarray(series, dtype=np.float64), np.asarray(alive, dtype=bool)
    ok = al & np.isfinite(x)
    n = ok.sum(0)

    return np.where(n > 0, np.where(ok, x, 0.0).sum(0) / np.maximum(n, 1), np.nan).astype(np.float32), n.astype(np.int32)


def _max_alive(series, alive):
    x, al = np.asarray(series, dtype=np.float64), np.asarray(alive, dtype=bool)
    ok = al & np.isfinite(x)

    return np.where(ok.any(0), np.where(ok, x, -np.inf).max(0), np.nan).astype(np.float32)


def env_aggregate(series: dict, alive) -> dict:
    """series: SERIES 이름 -> (S,N) numpy. 살아 있고 값이 유한한 step 만 센다(없으면 NaN). 돌려주는 키는 npz 의 map_err_* 이름이다."""
    out = {}
    out["map_err_inrange_mean_cm"], out["map_err_inrange_steps"] = _mean_alive(series["inrange_mean"], alive)
    out["map_err_inrange_cellmax_cm"] = _max_alive(series["inrange_cellmax"], alive)
    out["map_err_all_mean_cm"], out["map_err_all_steps"] = _mean_alive(series["all_mean"], alive)
    out["map_err_all_cellmax_cm"] = _max_alive(series["all_cellmax"], alive)
    out["map_err_gt_sat_frac_mean"], _n = _mean_alive(series["gt_sat_frac"], alive)
    out["map_err_ray_miss_frac_mean"], _n = _mean_alive(series["ray_miss_frac"], alive)
    out["map_err_clip_low_frac_mean"], _n = _mean_alive(series["clip_low_frac"], alive)
    nf, al = np.asarray(series["nonfinite_cells"], dtype=np.float64), np.asarray(alive, dtype=bool)
    nf = np.where(al, np.nan_to_num(nf, nan=0.0), 0.0)                                           # 살아 있는 step 의 비유한 칸 수(계열이 비어 있는 NaN 은 0)
    out["map_err_nonfinite_cells_total"] = nf.sum(0).astype(np.int64)
    out["map_err_nonfinite_steps"] = (nf > 0).sum(0).astype(np.int32)

    return out


# ---------------- 종류 x 레벨 묶음 x 모드 집계 (저장된 npz 에서) ----------------
LEVEL_GROUPS = {"L0~2": (0, 1, 2), "L3": (3,), "L6": (6,), "L9": (9,)}


def _fin(x):
    x = np.asarray(x, dtype=np.float64)

    return x[np.isfinite(x)]


def group_stats(z, kinds=None) -> dict:
    """한 npz -> {종류: {...}}. 머리는 (a) 결측 제외 값; (b) 영상 식 값과 (c) 결측 비율은 옆 칸. env 평균은 NaN 제외."""
    kind = z["kind"].astype(str)
    out = {}

    for k in (kinds or sorted(set(kind.tolist()))):
        m = kind == k
        va, vx = _fin(z["map_err_inrange_mean_cm"][m]), _fin(z["map_err_inrange_cellmax_cm"][m])
        ba, bx = _fin(z["map_err_all_mean_cm"][m]), _fin(z["map_err_all_cellmax_cm"][m])
        mf = _fin(z["map_err_gt_sat_frac_mean"][m])
        rm, cl = _fin(z["map_err_ray_miss_frac_mean"][m]), _fin(z["map_err_clip_low_frac_mean"][m])
        nfc, nfs = z["map_err_nonfinite_cells_total"][m], z["map_err_nonfinite_steps"][m]
        out[k] = {"envs": int(m.sum()), "inrange_envs": int(va.size),
                  "a_mean_of_mean_cm": float(va.mean()) if va.size else None, "a_median_of_mean_cm": float(np.median(va)) if va.size else None,
                  "a_max_of_cellmax_cm": float(vx.max()) if vx.size else None,
                  "b_mean_of_mean_cm": float(ba.mean()) if ba.size else None, "b_max_of_cellmax_cm": float(bx.max()) if bx.size else None,
                  "c_gt_sat_frac_mean": float(mf.mean()) if mf.size else None,
                  "c_ray_miss_frac_mean": float(rm.mean()) if rm.size else None, "c_clip_low_frac_mean": float(cl.mean()) if cl.size else None,
                  "d_nonfinite_cells_total": int(nfc.sum()), "d_nonfinite_steps_total": int(nfs.sum()), "d_nonfinite_envs": int((nfc > 0).sum())}

    return out


def report(folders: dict, modes=("eval_gt", "eval_pred", "probe_prop_only"), cmds=("fwd0.5", "fwd1.0")) -> dict:
    """folders: {레벨 묶음 이름: [평가 폴더, ...]} -> {묶음: {모드: {명령: group_stats}}}. 오차 키가 없는 옛 npz 는 건너뛴다."""
    res = {}

    for g, dirs in folders.items():
        for mode in modes:
            for c in cmds:
                for d in dirs:
                    f = Path(d) / ("env_arrays_%s_%s.npz" % (mode, c))

                    if f.is_file():
                        z = np.load(f, allow_pickle=False)

                        if "map_err_inrange_mean_cm" in z.files and "map_err_nonfinite_cells_total" in z.files:
                            res.setdefault(g, {}).setdefault(mode, {})[c] = group_stats(z)

    return res


def to_md(res: dict) -> str:
    lines = ["# 복원 지도 오차 (cm), 종류 x 레벨 x 모드. 머리 = (a) 정답이 -1.0 이 아닌 칸만의 값", "", DEFINITION, ""]
    f = lambda v: "-" if v is None else "%.2f" % v                                               # noqa: E731
    fr = lambda v: "-" if v is None else "%.3f" % v                                              # noqa: E731

    for g, modes in res.items():
        for mode, cmds in modes.items():
            for c, kinds in cmds.items():
                lines += ["## %s · %s · %s" % (g, mode, c), "",
                          "| 종류 | env | 유효 env | (a) env 평균의 평균 | (a) 중앙값 | (a) 칸 최대의 최댓값 | (b) 영상 식 평균 | (b) 칸 최대의 최댓값 | (c) 정답 -1.0 칸 비율 | (c) 광선 못 맞힘 | (c) 1 m 아래 clip | (d) 비유한 칸 수 · step 수 · env 수 |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]

                for k, v in kinds.items():
                    lines.append("| %s | %d | %d | %s | %s | %s | %s | %s | %s |" % (k, v["envs"], v["inrange_envs"], f(v["a_mean_of_mean_cm"]), f(v["a_median_of_mean_cm"]), f(v["a_max_of_cellmax_cm"]),
                                                                                       f(v["b_mean_of_mean_cm"]), f(v["b_max_of_cellmax_cm"]), "-" if v["c_gt_sat_frac_mean"] is None else "%.3f" % v["c_gt_sat_frac_mean"]) + " %s | %s | %d · %d · %d |" % (fr(v["c_ray_miss_frac_mean"]), fr(v["c_clip_low_frac_mean"]), v["d_nonfinite_cells_total"], v["d_nonfinite_steps_total"], v["d_nonfinite_envs"]))

                lines.append("")

    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", action="append", required=True, help="이름=폴더 (예 L0~2=.../m2000/map64). 여러 번")
    ap.add_argument("--out-prefix", required=True)
    a = ap.parse_args(argv)
    folders = {}

    for g in a.group:
        name, _, path = g.partition("=")
        folders.setdefault(name, []).append(path)

    res = report(folders)
    Path(a.out_prefix + ".json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    Path(a.out_prefix + ".md").write_text(to_md(res), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
