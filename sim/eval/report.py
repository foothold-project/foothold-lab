"""원시 CSV 한 장에서 발표에 쓸 숫자를 뽑는다. Isaac 도 GPU 도 필요 없다.

`eval_generalization.py` 가 낸 `generalization_raw.csv` 를 읽어 판정 5축 성공률과
이탈 통계, 그리고 **Wilson 95% 신뢰구간**을 냅니다.

**왜 Wilson 인가.** 100판에서 성공률이 0% 나 100% 에 붙으면 흔히 쓰는
정규근사(Wald) 구간이 폭 0 으로 찌그러집니다. 「100판 전부 성공했으니 참값도
100%」가 되어 버립니다. Wilson 은 그 자리에서도 폭을 남깁니다.
100판 · 50% 부근에서 폭은 약 19.2 포인트, 90% 부근에서 약 11.9 포인트,
0% 나 100% 에서도 3.7 포인트가 남습니다.

    python sim/eval/report.py <결과폴더>/generalization_raw.csv
    python sim/eval/report.py <...>.csv --markdown        # 문서에 붙일 표
"""

import argparse
import csv
import math

# 95% 양측. 1.959964 는 표준정규의 0.975 분위수.
Z_95 = 1.959963984540054

JUDGEMENT_AXES = (
    ("overall_success", "종합"),
    ("survival_success", "생존"),
    ("progress_success", "전진"),
    ("tracking_success", "속도추종"),
    ("direction_success", "방향"),
)


def wilson_interval(successes, n, z=Z_95):
    """이항 비율의 Wilson 점수 구간. `(하한, 상한)` 을 비율로 돌려준다.

    0/n 이나 n/n 에서도 폭이 남습니다. 그것이 Wald 대신 쓰는 이유입니다.
    """
    if n <= 0:
        return (0.0, 0.0)

    p = successes / n

    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))

    return (max(0.0, center - half), min(1.0, center + half))


def read_rows(path):
    """원시 CSV 를 읽는다. 판정 열은 `"True"` 문자열이므로 불리언으로 되돌린다.

    `metrics.summarize` 가 판정 열에 `int()` 를 쓰는데 `int("True")` 는 터집니다.
    스냅샷과 같은 제약이라 여기서 맞춰 줍니다.
    """
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    boolean_columns = [name for name, _ in JUDGEMENT_AXES]

    for row in rows:
        for column in boolean_columns:
            row[column] = row[column].strip().lower() == "true"

    return rows


def describe(values):
    """평균 · 최대 · 중앙값. 표본이 없으면 전부 0.0."""
    if not values:
        return {"mean": 0.0, "max": 0.0, "median": 0.0}

    ordered = sorted(values)
    middle = len(ordered) // 2

    if len(ordered) % 2 == 1:
        median = ordered[middle]
    else:
        median = 0.5 * (ordered[middle - 1] + ordered[middle])

    return {
        "mean": sum(values) / len(values),
        "max": max(values),
        "median": median,
    }


def analyse(rows, terrain):
    """지형 하나의 숫자 전부."""
    episodes = [r for r in rows if r["terrain"] == terrain]
    n = len(episodes)

    if n == 0:
        raise ValueError(f"No episodes recorded for terrain {terrain!r}.")

    axes = {}

    for key, label in JUDGEMENT_AXES:
        ok = sum(1 for r in episodes if r[key])
        low, high = wilson_interval(ok, n)

        axes[key] = {
            "label": label,
            "successes": ok,
            "rate": ok / n,
            "wilson_low": low,
            "wilson_high": high,
            "wilson_width_pp": 100.0 * (high - low),
        }

    fell = sum(1 for r in episodes if r["termination_reason"] == "base_contact")
    timeout = sum(1 for r in episodes if r["termination_reason"] == "timeout")

    return {
        "terrain": terrain,
        "episodes": n,
        "axes": axes,
        "endpoint_drift": describe([float(r["lateral_drift_m"]) for r in episodes]),
        "peak_drift": describe([float(r["peak_lateral_drift_m"]) for r in episodes]),
        "forward": describe([float(r["forward_progress_m"]) for r in episodes]),
        "duration": describe([float(r["duration_s"]) for r in episodes]),
        "velocity_mae": describe([float(r["velocity_mae_mps"]) for r in episodes]),
        "fell": fell,
        "timeout": timeout,
    }


def print_plain(result):
    a = result["axes"]
    n = result["episodes"]

    print("=" * 72)
    print(f"지형 {result['terrain']}  ·  {n} 판")
    print("=" * 72)
    print()
    print(f"{'판정축':<10} {'성공':>8} {'성공률':>9}   {'Wilson 95% 구간':>22} {'폭(pp)':>8}")
    print("-" * 72)

    for key, _ in JUDGEMENT_AXES:
        row = a[key]
        print(
            f"{row['label']:<10} {row['successes']:>4d}/{n:<4d}"
            f" {100 * row['rate']:>8.1f}%"
            f"   [{100 * row['wilson_low']:>6.1f}%, {100 * row['wilson_high']:>6.1f}%]"
            f" {row['wilson_width_pp']:>8.1f}"
        )

    print()
    print("-" * 72)
    print(f"{'항목':<22} {'평균':>10} {'중앙':>10} {'최대':>10}")
    print("-" * 72)

    for label, key in (
        ("끝점 좌우 이탈 (m)", "endpoint_drift"),
        ("최대 좌우 이탈 (m)", "peak_drift"),
        ("전진 거리 (m)", "forward"),
        ("에피소드 시간 (s)", "duration"),
        ("속도 MAE (m/s)", "velocity_mae"),
    ):
        d = result[key]
        print(f"{label:<22} {d['mean']:>10.3f} {d['median']:>10.3f} {d['max']:>10.3f}")

    print()
    print(f"낙상(base_contact) {result['fell']} 판 · 시간초과(timeout) {result['timeout']} 판")
    print("=" * 72)


def print_markdown(result):
    a = result["axes"]
    n = result["episodes"]

    print(f"### {result['terrain']} · {n} 판")
    print()
    print("| 판정축 | 성공 | 성공률 | Wilson 95% 구간 | 폭 |")
    print("|---|---|---|---|---|")

    for key, _ in JUDGEMENT_AXES:
        row = a[key]
        print(
            f"| {row['label']} | {row['successes']}/{n} "
            f"| {100 * row['rate']:.1f}% "
            f"| {100 * row['wilson_low']:.1f}% ~ {100 * row['wilson_high']:.1f}% "
            f"| {row['wilson_width_pp']:.1f} pp |"
        )

    print()
    print("| 항목 | 평균 | 중앙 | 최대 |")
    print("|---|---|---|---|")

    for label, key in (
        ("끝점 좌우 이탈 (m)", "endpoint_drift"),
        ("최대 좌우 이탈 (m)", "peak_drift"),
        ("전진 거리 (m)", "forward"),
        ("에피소드 시간 (s)", "duration"),
        ("속도 MAE (m/s)", "velocity_mae"),
    ):
        d = result[key]
        print(f"| {label} | {d['mean']:.3f} | {d['median']:.3f} | {d['max']:.3f} |")

    print()
    print(f"낙상 {result['fell']} 판 · 시간초과 {result['timeout']} 판")


def main():
    parser = argparse.ArgumentParser(description="원시 CSV 에서 요약 숫자와 Wilson 구간을 낸다.")
    parser.add_argument("raw_csv", help="generalization_raw.csv 경로")
    parser.add_argument("--terrain", default=None, help="지형 이름. 없으면 CSV 에 있는 것 전부")
    parser.add_argument("--markdown", action="store_true", help="문서에 붙일 표로 출력")

    args = parser.parse_args()

    rows = read_rows(args.raw_csv)

    if args.terrain is not None:
        wanted = [args.terrain]
    else:
        wanted = []

        for row in rows:
            if row["terrain"] not in wanted:
                wanted.append(row["terrain"])

    for i, terrain in enumerate(wanted):
        if i:
            print()

        result = analyse(rows, terrain)

        if args.markdown:
            print_markdown(result)
        else:
            print_plain(result)


if __name__ == "__main__":
    main()
