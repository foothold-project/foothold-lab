"""J-T4: 답 아는 시험의 기댓값 생성기 (JUDGE-SPEC v0.2 6 절). 원자료 경로 -> 기댓값 JSON(경로 · SHA · 값).

판정 코드(`foothold_s2.eval.judge_stats` · `judge_gate`)를 부르지 않는다. 같은 식을 **따로** 적어(순수 파이썬 반복문) 원자료에서 만든다.
그래서 판정 코드와 이 생성기가 같은 숫자를 내면 식이 두 번 독립으로 맞은 것이고, 둘이 다르면 어느 쪽이 틀렸는지 적어서 lead 에 올린다.
기댓값을 손으로 옮기지 않는다: 이 파일의 `SPEC_REFERENCE` 는 «명세에 적힌 값»(손으로 옮긴 참고값)이고, 생성기 출력과의 차이가 표기 오차(소수 4자리) 안인지만 본다.

원자료 위치는 환경변수로 바꿀 수 있다: JUDGE_LOGS_ROOT(impl-turncases/logs) · JUDGE_T5_ROOT(impl-t5/logs/onset_sweep) · JUDGE_W2_PARENT(parent_b1500/map_modes.json).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np

LOGS = Path(os.environ.get("JUDGE_LOGS_ROOT", "C:/mai/wt/foothold-lab/impl-turncases/logs"))
T5 = Path(os.environ.get("JUDGE_T5_ROOT", "C:/mai/wt/foothold-lab/impl-t5/logs/onset_sweep"))
W2_PARENT = Path(os.environ.get("JUDGE_W2_PARENT", "C:/mai/wt/foothold-lab/impl-w2/logs_gate/eval/parent_b1500/map_modes.json"))

# 부호 표(명세 1.1): 판정 코드의 PROTOCOLS 를 읽지 않고 따로 적는다. 시험이 둘이 같은지 대조한다.
SIGN = {"indep_left": +1, "indep_right": -1, "left_then_right": -1, "right_then_left": +1, "fwd_then_left": +1, "fwd_then_right": -1}
CASES = tuple(SIGN)
FEET = [4, 8, 14, 18]


def sha256_file(path) -> str:
    h = hashlib.sha256()

    with open(path, "rb") as f:
        h.update(f.read())

    return h.hexdigest()


def one_case(npz_path, case) -> dict:
    """한 경우: env 마다 반복문으로 q_e 와 네 발 접촉 비율을 구한다."""
    z = np.load(npz_path)
    alive, kept, wz, force = z["alive"], z["kept"], z["wz"], z["force"]
    sign = SIGN[case]
    qs, cs, allq, pooled_sum, pooled_n = [], [], [], 0.0, 0

    for e in range(alive.shape[0]):
        n = 0
        s = 0.0
        f = 0

        for t in range(alive.shape[1]):
            if alive[e, t]:
                n += 1
                s += float(wz[e, t])
                f += int(all(force[e, t, i] > 1.0 for i in FEET))
                pooled_sum += float(wz[e, t])
                pooled_n += 1

        if n == 0:
            continue

        q = sign * s / n
        allq.append(q)

        if kept[e]:
            qs.append(q)
            cs.append(f / n)

    return {"Q": sum(qs) / len(qs) if qs else None, "C": sum(cs) / len(cs) if cs else None, "kept": int(sum(1 for k in kept if k)),
            "alive_end": int(sum(1 for a in alive[:, -1] if a)), "pooled": sign * pooled_sum / pooled_n if pooled_n else None,
            "all_envs": sum(allq) / len(allq) if allq else None, "n_ge06": sum(1 for q in qs if q >= 0.6), "sha256": sha256_file(npz_path)}


def six_dir(d) -> dict:
    d = Path(d)

    return {c: one_case(d / ("arrays_%s.npz" % c), c) for c in CASES if (d / ("arrays_%s.npz" % c)).exists()}


def map64(path) -> dict:
    j = json.load(open(path, encoding="utf-8"))
    out = {"sha256": sha256_file(path), "cell_sha": j["fixed_terrain"]["assignment_sha256"], "modes": {}}

    for mode, cmds in j["modes"].items():
        out["modes"][mode] = {c: {"fwd_m": v["body_vx_integral_median_m"], "yaw": v["yaw_follow_median"], "alive": v["alive_envs_at_end"]} for c, v in cmds.items()}

    return out


def median(xs):
    xs = sorted(xs)
    n = len(xs)

    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def build() -> dict:
    """6 절 전체의 기댓값 사전."""
    e = {"logs_root": str(LOGS), "t5_root": str(T5)}
    e["two_three"] = {  # 2.3 표의 여섯 행
        "b1500_indep_right": six_dir(LOGS / "six_cases/b1500")["indep_right"],
        "g0b_m1500": six_dir(LOGS / "g0b_eval/m1500/turn16"),
        "b1500_prop": six_dir(LOGS / "b1500_baseline/rep1/turn16_probe_prop_only"),
        "b50_m1510": six_dir(LOGS / "six_cases/b50_m1510"),
    }
    # 6.1
    col = {}

    for n in range(1000, 1500, 50):
        col[n] = map64(T5 / ("b_m%d/map_modes.json" % n))["modes"]["eval_gt"]

    col[1500] = map64(W2_PARENT)["modes"]["eval_gt"]
    e["b_column"] = {str(n): {"left": m["spin+1.2"]["yaw"], "right": m["spin-1.2"]["yaw"], "min": min(m["spin+1.2"]["yaw"], m["spin-1.2"]["yaw"]),
                              "fwd10": m["fwd1.0"]["fwd_m"], "alive10": m["fwd1.0"]["alive"]} for n, m in col.items()}
    mins = [v["min"] for v in e["b_column"].values()]
    e["b_column_summary"] = {"min_median": median(mins), "left_median": median([v["left"] for v in e["b_column"].values()]),
                             "right_median": median([v["right"] for v in e["b_column"].values()]), "warn_below_030": sum(1 for x in mins if x < 0.30)}
    # 6.2
    ab = {}

    for tag in ("a50", "b50"):
        for n in range(1510, 1551, 10):
            m = map64(T5 / ("%s_m%d/map_modes.json" % (tag, n)))["modes"]["eval_gt"]
            ab["%s_%d" % (tag, n)] = {"left": m["spin+1.2"]["yaw"], "right": m["spin-1.2"]["yaw"]}

    e["ab50"] = ab
    e["b1500_repeat"] = {k: map64(T5 / "b_m1500_repeat/map_modes.json")["modes"]["eval_gt"][k]["yaw"] for k in ("spin+1.2", "spin-1.2")}
    # 6.3 · 6.4
    e["six_b1500"] = six_dir(LOGS / "six_cases/b1500")
    e["six_b50_m1510"] = six_dir(LOGS / "six_cases/b50_m1510")
    e["six_a50_m1550"] = six_dir(LOGS / "six_cases/a50_m1550")
    # 6.5
    e["g0b_m1000"] = six_dir(LOGS / "g0b_eval/m1000/turn16")
    e["g0b_m1500"] = six_dir(LOGS / "g0b_eval/m1500/turn16")
    e["g0b_m1500_map64"] = map64(LOGS / "g0b_eval/m1500/map64/map_modes.json")["modes"]["none"]
    # 6.6
    rep = {}

    for r in ("rep1", "rep2"):
        rep[r] = six_dir(LOGS / ("b1500_baseline/%s/turn16_eval_gt" % r))

    e["rep"] = rep
    # 6.7
    e["b1500_prop_map64"] = map64(LOGS / "b1500_baseline/rep1/map64/map_modes.json")["modes"]
    # 6.8
    sb = {}

    for n in (100, 200, 300, 400):
        d = LOGS / ("sb50_eval/m%d" % n)
        sb[str(n)] = {"map64": map64(d / "map64/map_modes.json")["modes"],
                      "turn": {m: six_dir(d / ("turn16_%s" % m)) for m in ("eval_gt", "probe_prop_only")}}

    e["sb50"] = sb

    return e


# ------------------------------------------------------------------ 명세에 적힌 값(손으로 옮긴 참고값). 시험이 생성기 출력과의 차이를 표기 오차 안에서 본다.

SPEC_REFERENCE = {
    "two_three": {   # (pooled, env 동일 가중 전체, kept 평균 Q, kept)
        "b1500_indep_right": (0.2467, 0.2552, 0.2250, 15),
        "g0b_left_then_right": (0.4010, 0.5009, 0.3884, 10),
        "g0b_right_then_left": (0.4445, 0.4038, 0.4630, 14),
        "prop_indep_left": (0.0231, -0.0425, 0.0640, 6),
        "prop_right_then_left": (0.3824, 0.4356, 0.3614, 8),
        "b50_m1510_left_then_right": (0.6505, 0.6505, 0.6505, 16),
    },
    "b_column": {1000: (0.1902, 0.0833, 5.673, 62), 1050: (0.1079, 0.6260, 5.849, 63), 1100: (0.7754, 0.8511, 6.009, 64), 1150: (0.5903, 0.8576, 5.794, 63),
                 1200: (0.4877, 0.2846, 5.704, 64), 1250: (0.3639, 0.2648, 5.523, 63), 1300: (0.7117, 0.2235, 5.597, 63), 1350: (0.5754, 0.1654, 5.250, 63),
                 1400: (0.2650, 0.2369, 5.662, 62), 1450: (0.1940, 0.1321, 5.345, 58), 1500: (0.8730, 0.1480, 5.653, 60)},
    "b_column_summary": {"min_median": 0.2235, "left_median": 0.4877, "right_median": 0.2369, "warn_below_030": 9},
    "ab50": {"a50": {1510: (0.5593, 0.5354), 1520: (0.3903, 0.1505), 1530: (0.4231, 0.1311), 1540: (0.3235, 0.1439), 1550: (0.3884, 0.1270)},
             "b50": {1510: (0.8305, 0.8804), 1520: (0.7572, 0.5520), 1530: (0.6844, 0.3796), 1540: (0.7781, 0.1211), 1550: (0.7667, 0.1979)}},
    "b1500_repeat": (0.8705, 0.1451),
    "six": {   # 6.3: (B1500 Q, C, kept), (m1510 Q, C, kept, q>=0.6 수)
        "indep_left": ((1.0070, 0.3975, 16), (0.9475, 0.3881, 16, 15)),
        "indep_right": ((0.2250, 0.8245, 15), (0.9456, 0.3840, 16, 14)),
        "left_then_right": ((0.2303, 0.8966, 16), (0.6505, 0.6222, 16, 9)),
        "right_then_left": ((1.0383, 0.4564, 16), (0.9091, 0.4180, 16, 16)),
        "fwd_then_left": ((0.8901, 0.4373, 16), (0.9730, 0.3656, 16, 16)),
        "fwd_then_right": ((0.4884, 0.6123, 16), (0.9622, 0.3630, 16, 14)),
    },
    "a50_m1550": {"indep_left": 0.4138, "right_then_left": 0.3431, "fwd_then_left": 0.3817, "indep_right": 0.1709},   # 6.4
    "g0b": {   # 6.5: (m1000 Q, C, kept), (m1500 Q, C, kept, alive_end)
        "indep_left": ((0.4436, 0.4753, 16), (0.5285, 0.4750, 9, 9)),
        "indep_right": ((0.1067, 0.9255, 16), (0.3178, 0.7560, 11, 11)),
        "left_then_right": ((0.1699, 0.9117, 16), (0.3884, 0.7591, 10, 13)),
        "right_then_left": ((0.4099, 0.4948, 16), (0.4630, 0.5986, 14, 15)),
        "fwd_then_left": ((0.3695, 0.5479, 16), (0.3645, 0.5756, 16, 16)),
        "fwd_then_right": ((0.2072, 0.8772, 15), (0.2977, 0.8139, 14, 14)),
    },
    "rep": {   # 6.6: (rep1 Q, rep2 Q, rep1 C, rep2 C)
        "indep_left": (1.0125, 1.0320, 0.4006, 0.3944), "indep_right": (0.2375, 0.2324, 0.8258, 0.8443),
        "left_then_right": (0.1907, 0.2740, 0.9217, 0.8646), "right_then_left": (1.0110, 1.0497, 0.4578, 0.4449),
        "fwd_then_left": (0.9580, 0.9654, 0.4186, 0.4200), "fwd_then_right": (0.3165, 0.3369, 0.7743, 0.7559),
    },
    "prop": {   # 6.7: (pooled, env 전체, Q kept, kept)
        "indep_left": (0.0231, -0.0425, 0.0640, 6), "indep_right": (0.1849, 0.2487, 0.1562, 12), "left_then_right": (0.0261, 0.1497, 0.0165, 12),
        "right_then_left": (0.3824, 0.4356, 0.3614, 8), "fwd_then_left": (0.1732, 0.2109, 0.1593, 8), "fwd_then_right": (0.1518, 0.1199, 0.1477, 12),
    },
    "prop_map64": {"fwd0.5": (0.067, 52), "fwd1.0": (0.527, 43), "spin+1.2": (0.0575, 21), "spin-1.2": (0.1783, 46)},
    "sb50": {   # 6.8: m -> (eval_gt fwd0.5, fwd1.0, 생존 fwd0.5, 생존 fwd1.0), (probe_prop_only ...)
        100: ((0.061, 0.059, 64, 64), (0.062, 0.059, 64, 64)),
        200: ((2.006, 3.444, 64, 62), (1.956, 3.924, 64, 62)),
        300: ((2.699, 4.951, 64, 64), (2.727, 4.991, 64, 64)),
        400: ((2.546, 5.592, 64, 63), (2.549, 5.506, 64, 63)),
    },
}


def main(out_path=None) -> str:
    text = json.dumps(build(), ensure_ascii=False, indent=1, sort_keys=True, default=lambda o: float(o) if isinstance(o, np.floating) else int(o))

    if out_path:
        Path(out_path).write_text(text, encoding="utf-8", newline="\n")

    return text


if __name__ == "__main__":
    import sys

    main(sys.argv[1] if len(sys.argv) > 1 else None)
