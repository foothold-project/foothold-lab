"""X27j: env_arrays_<모드>_<명령>.npz 를 지형 종류별로 모아 표로 만든다(눈 끄고 걷기 = probe_prop_only 가 «가림»).

사용: python -m foothold_s2.eval.ex35_terrain_report --dir <저장본 평가 폴더>/map64 [--dir ...] --out-prefix <경로>
종류마다: env 수 · 거리 중앙값 · 평균(본체 vx 적분 m) · 끝 생존 비율 · 종료된 env 수. 판정에는 넣지 않는다(카드 개정 전, 기록용).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def per_kind(npz_path) -> dict:
    z = np.load(npz_path, allow_pickle=False)
    kind = z["kind"].astype(str)
    out = {}

    for k in sorted(set(kind.tolist())):
        m = kind == k
        d = z["body_vx_integral_m"][m]
        out[k] = {"envs": int(m.sum()), "levels": sorted({int(v) for v in z["terrain_level"][m]}), "cols": sorted({int(v) for v in z["terrain_col"][m]}),
                  "dist_median_m": float(np.median(d)), "dist_mean_m": float(d.mean()), "alive_end_fraction": float(z["alive_end"][m].mean()),
                  "terminated_envs": int((z["end_reason"].astype(str)[m] == "terminated").sum())}

    return out


def report(folders) -> dict:
    res = {}

    for folder in folders:
        for f in sorted(Path(folder).glob("env_arrays_*.npz")):
            res.setdefault(str(folder), {})[f.stem[len("env_arrays_"):]] = per_kind(f)

    return res


def to_md(res) -> str:
    lines = ["# 지형 종류별 거리 · 생존 (env_arrays 에서 집계, 기록용)", ""]

    for folder, cases in res.items():
        for case, kinds in cases.items():
            lines += ["## %s · %s" % (folder, case), "", "| 종류 | env | 거리 중앙값 m | 거리 평균 m | 끝 생존 | 종료 env |", "|---|---|---|---|---|---|"]

            for k, v in kinds.items():
                lines.append("| %s | %d | %.3f | %.3f | %.2f | %d |" % (k, v["envs"], v["dist_median_m"], v["dist_mean_m"], v["alive_end_fraction"], v["terminated_envs"]))

            lines.append("")

    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", action="append", required=True)
    ap.add_argument("--out-prefix", required=True)
    a = ap.parse_args(argv)
    res = report(a.dir)
    Path(a.out_prefix + ".json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    Path(a.out_prefix + ".md").write_text(to_md(res), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
