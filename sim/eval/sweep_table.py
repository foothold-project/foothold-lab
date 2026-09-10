"""스윕 요약을 사람이 읽는 표로. `sweep_summary.csv` 만 읽는다 (Isaac 도 GPU 도 불필요).

    python sim/eval/sweep_table.py sim/eval/results/20260910-difficulty-sweep

내는 것은 (지형 x 속도) 한 줄에 난이도 10칸이 늘어선 표다. 어느 난이도에서
통과로 넘어가는지가 한 눈에 보이는 것이 목적이다.
"""

import csv
import os
import sys


def wilson(successes, n, z=1.96):
    """Wilson 95% 구간. 0% · 100% 에서도 폭이 남는다."""
    if n == 0:
        return (0.0, 0.0)

    phat = successes / n
    denom = 1.0 + z * z / n
    centre = (phat + z * z / (2 * n)) / denom
    margin = (z / denom) * ((phat * (1 - phat) / n + z * z / (4 * n * n)) ** 0.5)

    return (max(0.0, centre - margin), min(1.0, centre + margin))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    root = os.path.abspath(sys.argv[1])
    path = os.path.join(root, "sweep_summary.csv")

    rows = list(csv.DictReader(open(path, encoding="utf-8")))

    speeds = sorted({float(r["command_vx"]) for r in rows})
    diffs = sorted({float(r["difficulty"]) for r in rows})
    terrains = ["gap", "rails", "pit", "stepping_stones", "floating_ring"]

    cell = {}

    for r in rows:
        key = (r["terrain"], float(r["command_vx"]), float(r["difficulty"]))
        cell[key] = r

    for axis, label in (("overall_success_rate", "종합 성공률"),
                        ("survival_rate", "생존률"),
                        ("mean_forward_progress_m", "평균 전진 (m)")):
        print()
        print(f"### {label}")
        print()
        print("| 지형 | 속도 | " + " | ".join(f"{d:.1f}" for d in diffs) + " |")
        print("|---|---|" + "---|" * len(diffs))

        for terrain in terrains:
            for vx in speeds:
                cells = []

                for d in diffs:
                    r = cell.get((terrain, vx, d))

                    if r is None:
                        cells.append("`-`")
                        continue

                    value = float(r[axis])

                    if axis == "mean_forward_progress_m":
                        cells.append(f"{value:.2f}")
                    else:
                        pct = 100 * value
                        # 통과(50% 이상)는 굵게. 어디서 넘어가는지 눈에 띄게.
                        cells.append(f"**{pct:.0f}%**" if pct >= 50 else f"{pct:.0f}%")

                print(f"| `{terrain}` | {vx} | " + " | ".join(cells) + " |")

    # 통과로 넘어가는 난이도. 「벽이 어디인가」의 답.
    print()
    print("### 통과선을 넘는 난이도 (종합 50% 이상이 되는 가장 낮은 난이도)")
    print()
    print("| 지형 | " + " | ".join(f"{v} m/s" for v in speeds) + " |")
    print("|---|" + "---|" * len(speeds))

    for terrain in terrains:
        cells = []

        for vx in speeds:
            passing = [d for d in diffs
                       if (terrain, vx, d) in cell
                       and float(cell[(terrain, vx, d)]["overall_success_rate"]) >= 0.5]

            if passing:
                best = max(passing)
                n = int(cell[(terrain, vx, best)]["episodes"])
                k = round(float(cell[(terrain, vx, best)]["overall_success_rate"]) * n)
                lo, hi = wilson(k, n)
                cells.append(f"**{best:.1f}** ({100*lo:.0f}~{100*hi:.0f}%)")
            else:
                cells.append("없음")

        print(f"| `{terrain}` | " + " | ".join(cells) + " |")

    print()
    print("「가장 낮은 난이도」가 아니라 **통과하는 가장 높은 난이도**를 적었다.")
    print("난이도가 오를수록 어려워지므로, 이 값이 그 지형의 «벽» 이다.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
