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

DEFINITION = ("step 오차 = nanmean(|refined - gt_map|) * 100 [cm, 512 칸, 결측 -1.0 칸도 포함, NaN 만 제외] (영상 compose_25e.recon_error_series 와 같다); "
              "cellmax = nanmax(|refined - gt_map|) * 100 [cm]; env 별 값은 살아 있는 step 에서만(mean = step 오차 평균, max = cellmax 의 최댓값)")


def step_error(refined, gt_map):
    """(N,32,16) 두 텐서(torch) -> (mean_cm (N,), cellmax_cm (N,)) torch. NaN 만 있는 env 는 NaN."""
    import torch

    d = (refined.detach().float() - gt_map.detach().float()).abs().reshape(refined.shape[0], -1)
    mean = torch.nanmean(d, dim=1) * 100.0
    mx = torch.where(torch.isnan(d), torch.full_like(d, float("-inf")), d).amax(dim=1) * 100.0
    mx = torch.where(torch.isinf(mx), torch.full_like(mx, float("nan")), mx)

    return mean, mx


def record(last: dict, result, gt_map) -> None:
    """_advance 의 반환값(result[2] = out 사전)에 refined 가 있으면 이번 step 의 오차를 last["e"] 에 둔다(지도 없는 체크포인트는 비워 둔다)."""
    out = result[2]

    if isinstance(out, dict) and out.get("refined") is not None:
        last["e"] = step_error(out["refined"], gt_map)
    else:
        last["e"] = None


def env_aggregate(mean_series, cellmax_series, alive) -> dict:
    """(S,N) 세 배열(numpy) -> env 별 {mean_cm, cellmax_cm, valid_steps}. 살아 있고 값이 유한한 step 만 센다. 없으면 NaN."""
    m, x, al = np.asarray(mean_series, dtype=np.float64), np.asarray(cellmax_series, dtype=np.float64), np.asarray(alive, dtype=bool)
    ok = al & np.isfinite(m)
    n = ok.sum(0)
    mean = np.where(n > 0, np.where(ok, m, 0.0).sum(0) / np.maximum(n, 1), np.nan)
    okx = al & np.isfinite(x)
    cmax = np.where(okx.any(0), np.where(okx, x, -np.inf).max(0), np.nan)

    return {"mean_cm": mean.astype(np.float32), "cellmax_cm": cmax.astype(np.float32), "valid_steps": n.astype(np.int32)}


# ---------------- 종류 x 레벨 묶음 x 모드 집계 (저장된 npz 에서) ----------------
LEVEL_GROUPS = {"L0~2": (0, 1, 2), "L3": (3,), "L6": (6,), "L9": (9,)}


def group_stats(z, kinds=None) -> dict:
    """한 npz -> {종류: {env, mean_of_mean_cm, median_of_mean_cm, max_of_cellmax_cm, mean_of_cellmax_cm}}. env 평균은 NaN 제외."""
    kind = z["kind"].astype(str)
    em, ex = z["map_err_mean_cm"].astype(np.float64), z["map_err_cellmax_cm"].astype(np.float64)
    out = {}

    for k in (kinds or sorted(set(kind.tolist()))):
        m = kind == k
        a, b = em[m], ex[m]
        a, b = a[np.isfinite(a)], b[np.isfinite(b)]
        out[k] = {"envs": int(m.sum()), "valid_envs": int(a.size),
                  "mean_of_mean_cm": float(a.mean()) if a.size else None, "median_of_mean_cm": float(np.median(a)) if a.size else None,
                  "mean_of_cellmax_cm": float(b.mean()) if b.size else None, "max_of_cellmax_cm": float(b.max()) if b.size else None}

    return out


def report(folders: dict, modes=("eval_gt", "eval_pred", "probe_prop_only"), cmds=("fwd0.5", "fwd1.0")) -> dict:
    """folders: {레벨 묶음 이름: [평가 폴더, ...]} (한 묶음에 폴더가 여럿이면 모드별로 있는 npz 를 쓴다). -> {묶음: {모드: {명령: group_stats}}}"""
    res = {}

    for g, dirs in folders.items():
        for mode in modes:
            for c in cmds:
                for d in dirs:
                    f = Path(d) / ("env_arrays_%s_%s.npz" % (mode, c))

                    if f.is_file():
                        z = np.load(f, allow_pickle=False)

                        if "map_err_mean_cm" in z.files:
                            res.setdefault(g, {}).setdefault(mode, {})[c] = group_stats(z)

    return res


def to_md(res: dict) -> str:
    lines = ["# 복원 지도 오차 (cm, |refined - gt_map| 512 칸 평균), 종류 x 레벨 x 모드", "", DEFINITION, ""]

    for g, modes in res.items():
        for mode, cmds in modes.items():
            for c, kinds in cmds.items():
                lines += ["## %s · %s · %s" % (g, mode, c), "", "| 종류 | env | 유효 env | env 평균의 평균 | env 평균의 중앙값 | 칸 최대의 평균 | 칸 최대의 최댓값 |", "|---|---|---|---|---|---|---|"]
                f = lambda v: "-" if v is None else "%.2f" % v                                  # noqa: E731

                for k, v in kinds.items():
                    lines.append("| %s | %d | %d | %s | %s | %s | %s |" % (k, v["envs"], v["valid_envs"], f(v["mean_of_mean_cm"]), f(v["median_of_mean_cm"]), f(v["mean_of_cellmax_cm"]), f(v["max_of_cellmax_cm"])))

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
