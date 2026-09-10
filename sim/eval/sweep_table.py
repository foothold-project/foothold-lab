"""스윕 요약을 사람이 읽는 표로. `sweep_summary.csv` 만 읽는다 (Isaac 도 GPU 도 불필요).

    python sim/eval/sweep_table.py sim/eval/results/20260910-difficulty-sweep

내는 것은 (지형 x 속도) 한 줄에 난이도 10칸이 늘어선 표다. 어느 난이도에서
통과로 넘어가는지가 한 눈에 보이는 것이 목적이다.
"""

import csv
import os
import sys


def dlabel(value):
    """난이도 이름표. **소수 둘째 자리를 잘라 먹지 않는다.**

    `%.1f` 로 찍으면 0.12 와 0.14 가 둘 다 «0.1» 이 되어 표의 열 이름이 겹친다.
    칸 폴더 이름에서 같은 실수를 한 번 했고, 표에서도 똑같이 났다.
    """
    return f"{value:.1f}" if round(value, 1) == round(value, 2) else f"{value:.2f}"


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

    # 지형 목록은 **데이터에서 읽는다.** 박아 두면 지형 집합이 바뀔 때 조용히
    # 빈 표가 나온다 (rough6 를 처음 돌렸을 때 실제로 그럴 뻔했다).
    # 아는 순서가 있으면 그 순서를, 없으면 CSV 에 나온 순서를 쓴다.
    PREFERRED = (
        "gap", "rails", "pit", "stepping_stones", "floating_ring",
        "pyramid_stairs", "pyramid_stairs_inv", "boxes", "random_rough",
        "hf_pyramid_slope", "hf_pyramid_slope_inv",
    )

    present = []

    for r in rows:
        if r["terrain"] not in present:
            present.append(r["terrain"])

    terrains = [t for t in PREFERRED if t in present]
    terrains += [t for t in present if t not in PREFERRED]

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
        print("| 지형 | 속도 | " + " | ".join(dlabel(d) for d in diffs) + " |")
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

                # **단조롭지 않으면 「벽」이라는 말이 거짓말이 된다.**
                # `best` 보다 쉬운 난이도인데 떨어지는 칸이 있으면 이 열은
                # 「여기까지 된다」로 읽히면 안 된다. 표시를 붙여 소리를 낸다.
                dips = [d for d in diffs
                        if d < best and (terrain, vx, d) in cell
                        and float(cell[(terrain, vx, d)]["overall_success_rate"]) < 0.5]

                mark = " `비단조`" if dips else ""

                cells.append(f"**{dlabel(best)}** ({100*lo:.0f}~{100*hi:.0f}%){mark}")
            else:
                cells.append("없음")

        print(f"| `{terrain}` | " + " | ".join(cells) + " |")

    print()
    print("「가장 낮은 난이도」가 아니라 **통과하는 가장 높은 난이도**를 적었다.")
    print("난이도가 오를수록 어려워지면 이 값이 그 지형의 «벽» 이다.")
    print()
    print("**`비단조` 가 붙은 칸은 벽으로 읽으면 안 된다.** 그 값보다 쉬운 난이도인데")
    print("떨어지는 칸이 있다는 뜻이고, 그러면 난이도축이 그 지형의 어려움을")
    print("한 방향으로 나타내지 못한다는 뜻이다.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
