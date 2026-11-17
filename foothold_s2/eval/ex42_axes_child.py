"""CPU 탐침 자식 (EX-42 새 학습 축 · planner run_child_est.py 의 줄인 사본 + 복원 지도 구멍 기록).
planner 의 /home/jay/mai/tmp/planner/again/noise_probe/run_child_est.py 와 같은 길 (eval_map_modes 를 runpy 로 돌리면서 명령 칸을 PROBE_CASES 로 덮어쓰고
actor 가 받는 est 와 실제 몸 선속도를 step 마다 적음, 평균 행동). 더한 것: map_error.record 를 감싸 step 마다 (복원 지도 대 정답 지도) 구멍 통계 6 칸을 같이 적는다
(ex42_axes.hole_stats) · 0.5 초마다 (SNAP_EVERY step) 두 지도 한 장씩도 남긴다. 평가기 · 학습 코드는 안 바뀐다 (이 프로세스 안에서만 감쌈).
쓰는 법: PROBE_CASES="0.1/0;0/0.2" PROBE_EXTRA=<npz 앞부분> python -B -m foothold_s2.eval.ex42_axes_child <eval_map_modes 인자>   (칸 n 의 출력 = <EXTRA>_<n>.npz)"""
import os
import runpy
import sys

import numpy as np

from foothold_s2.eval import adapters, ex42_axes, map_error, map_mode_cells
from foothold_s2.runners import start_runner

CASES = [tuple(float(x) for x in item.split("/")) for item in os.environ["PROBE_CASES"].split(";")]
EXTRA = os.environ["PROBE_EXTRA"]
SNAP_EVERY = int(os.environ.get("AXES_SNAP_EVERY", "25"))
state = {"case": -1, "rows": [], "holes": [], "snaps": [], "calls": 0}
_disable = map_mode_cells.disable_heading_for_fixed_eval
_assert = map_mode_cells.assert_heading_off_for_fixed_eval
RUNNER = next(value for name, value in vars(start_runner).items() if isinstance(value, type) and "_ppo_obs" in vars(value))
_ppo_obs = RUNNER._ppo_obs
_record = map_error.record


def ppo_obs(self, raw, est):
    state["rows"].append((est.detach().float().cpu().numpy().copy(), raw["base_vel"].detach().float().cpu().numpy().copy()))
    return _ppo_obs(self, raw, est)


def record(last, result, gt_map, rel=None):
    _record(last, result, gt_map, rel)
    out = result[2]
    n = int(gt_map.shape[0])
    if isinstance(out, dict) and out.get("refined") is not None:
        r = out["refined"].detach().float().cpu().numpy().reshape(n, *gt_map.shape[1:])
        g = gt_map.detach().float().cpu().numpy()
        state["holes"].append(ex42_axes.hole_stats(r, g))
        if len(state["holes"]) % SNAP_EVERY == 1:
            state["snaps"].append((len(state["holes"]) - 1, r.astype(np.float16), g.astype(np.float16)))
    else:
        state["holes"].append(np.full((n, len(ex42_axes.HOLE_COLUMNS)), np.nan))


def write(term) -> None:
    vx, vy = CASES[state["case"] % len(CASES)]
    term.vel_command_b[:, 0] = vx
    term.vel_command_b[:, 1] = vy
    term.vel_command_b[:, 2] = 0.0


def flush() -> None:
    if state["rows"]:
        est, true = (np.stack([row[i] for row in state["rows"]]) for i in range(2))
        extra = {}
        if state["holes"]:
            extra["holes"] = np.stack(state["holes"]).astype(np.float32)
        if state["snaps"]:
            extra["snap_step"] = np.array([s[0] for s in state["snaps"]])
            extra["snap_refined"] = np.stack([s[1] for s in state["snaps"]])
            extra["snap_gt"] = np.stack([s[2] for s in state["snaps"]])
        np.savez(f"{EXTRA}_{state['case']}.npz", est=est, true=true, command=np.array(CASES[state["case"] % len(CASES)]), **extra)
    state["rows"], state["holes"], state["snaps"] = [], [], []


def disable(term):
    _disable(term)
    flush()
    state["case"] += 1
    write(term)


def check(term):
    _assert(term)
    write(term)


RUNNER._ppo_obs = ppo_obs
map_error.record = record
map_mode_cells.disable_heading_for_fixed_eval = disable
map_mode_cells.assert_heading_off_for_fixed_eval = check
sys.argv = ["eval_map_modes"] + sys.argv[1:]
try:
    runpy.run_module("foothold_s2.eval.eval_map_modes", run_name="__main__")
finally:
    flush()
