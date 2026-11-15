"""G1 지도 입력 통계 기록 (SONNET-X23, EX-23). Kit 없이 시험된다. 기존 runner 를 고치지 않고 지각 모듈의 step 을 감싸서 쓴다.

START 구조에서 actor 는 지도 칸을 직접 받지 않는다: 지각 추정기(IE)가 «정답 지도 H^b (use_gt 가 참인 env) 또는 TR-Net 이 복원한 지도(거짓인 env)» 를 받아 est 51 칸을 만들고
actor 는 그 est 를 받는다. 이 기록은 IE 로 들어가는 지도 값을 매 iteration 평균 내어 `map_stats.jsonl` 에 한 줄씩 쓰고, 첫 iteration 과 50 회마다 run.log 에도 한 줄 찍는다.

정답 지도(env 의 gt_map 묶음)는 h = z_hit - z_base 를 ±1 m 로 자른 값이다(못 맞힌 광선은 -1). 그래서 평지에서는 «0 근처» 가 아니라 «모든 칸이 -(몸 높이)» 로 거의 같은 상수(약 -0.25~-0.4)이고
계단이면 칸마다 단 높이만큼 다르다. 그래서 지형 모양의 지표는 칸 사이 표준편차(cell_std)이고, 0 근처 비율(abs_lt_0p05)은 «지면이 몸 높이 근처로 올라온 칸» 의 비율이다.

iteration 번호는 step 호출 수 // steps_per_iter 로 센다(수집 한 번 = 한 iteration 의 steps_per_iter 번 호출).
"""

from __future__ import annotations

import json
import os

import torch


def map_stats(gt_map: torch.Tensor, use_gt: torch.Tensor, refined: torch.Tensor | None = None) -> dict:
    """gt_map (N, 32, 16) · use_gt (N,) bool · refined (N, 32, 16) 또는 None. 한 번의 step 에서 IE 로 가는 지도의 통계."""
    g = gt_map.detach().float()
    flat = g.reshape(g.shape[0], -1)
    out = {"gt_mean": float(g.mean()), "gt_std": float(g.std()), "gt_cell_std": float(flat.std(dim=1).mean()),             # 칸 사이 표준편차(env 평균): 평지 ~0 · 계단 > 0
           "gt_missed_frac": float((g == -1.0).float().mean()), "gt_abs_lt_0p05": float((g.abs() < 0.05).float().mean()),
           "use_gt_frac": float(use_gt.float().mean())}

    if refined is not None:
        r = refined.detach().float()
        eff = torch.where(use_gt[:, None, None], g, r)
        out.update({"refined_mean": float(r.mean()), "refined_std": float(r.std()), "eff_mean": float(eff.mean()), "eff_std": float(eff.std())})
    else:
        out.update({"eff_mean": float(g.mean()), "eff_std": float(g.std())})

    return out


class MapStatsRecorder:
    """runner.perception 의 step 을 감싸 step 마다 `map_stats` 를 모으고 iteration 끝에 평균을 쓴다."""

    def __init__(self, runner, log_dir: str, print_every: int = 50):
        self.runner = runner
        self.log_dir = log_dir
        self.steps_per_iter = int(runner.num_steps_per_env)
        self.print_every = print_every
        self.calls = 0
        self.acc: dict[str, float] = {}
        self.in_step = False
        self._last_refined = None

    def attach(self) -> None:
        p = self.runner.perception
        orig_step, orig_adv = p.step, p._advance
        rec = self

        def advance(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map, *map_off):
            out = orig_adv(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map, *map_off)

            if rec.in_step:
                rec._last_refined = out[2].get("refined")

            return out

        def step(st, inp, gt_map, deterministic=False):
            rec.in_step = True
            rec._last_refined = None

            try:
                est = orig_step(st, inp, gt_map, deterministic)
            finally:
                rec.in_step = False

            rec.add(gt_map, st.use_gt, rec._last_refined)

            return est

        p._advance = advance
        p.step = step

    def add(self, gt_map, use_gt, refined) -> None:
        s = map_stats(gt_map.reshape(gt_map.shape[0], 32, 16), use_gt, refined)

        for k, v in s.items():
            self.acc[k] = self.acc.get(k, 0.0) + v

        self.calls += 1

        if self.calls % self.steps_per_iter == 0:
            self.flush(self.calls // self.steps_per_iter - 1)

    def flush(self, it: int) -> dict:
        row = {"it": it, **{k: v / self.steps_per_iter for k, v in self.acc.items()}}
        self.acc = {}

        if self.log_dir is not None:
            with open(os.path.join(self.log_dir, "map_stats.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        if it == 0 or it % self.print_every == 0:
            print("[G1] 지도 입력 통계 it=%d 정답지도 평균 %.3f 표준편차 %.3f 칸간편차 %.3f 미검출(-1) %.3f |x|<0.05 %.3f · 정답 사용 비율 %.2f · IE 입력 평균 %.3f 표준편차 %.3f" % (
                it, row["gt_mean"], row["gt_std"], row["gt_cell_std"], row["gt_missed_frac"], row["gt_abs_lt_0p05"], row["use_gt_frac"], row["eff_mean"], row["eff_std"]), flush=True)

        return row
