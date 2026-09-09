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

# 이탈·거리 표의 줄 순서. **통과선 이탈이 맨 위**입니다. 판정에 쓰는 자이고,
# 나머지 둘은 관측입니다 (#99 2번).
DRIFT_ROWS = (
    ("통과선 좌우 이탈 (m)", "gate_drift"),
    ("끝점 좌우 이탈 (m)", "endpoint_drift"),
    ("최대 좌우 이탈 (m)", "peak_drift"),
    ("전진 거리 (m)", "forward"),
    ("에피소드 시간 (s)", "duration"),
    ("속도 MAE (m/s)", "velocity_mae"),
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


def numeric_column(episodes, key):
    """수치 열을 float 목록으로. **빈칸은 건너뜁니다.**

    `gate_lateral_drift_m` 은 통과선을 못 넘긴 판에서 빈칸입니다. 그것을 0.0 으로
    읽으면 「도달 못 했다」가 「완벽하게 곧았다」로 뒤집힙니다.

    **열 자체가 없어도 빈 목록입니다.** #99 2번 이전에 나온 CSV 에는
    통과선 열이 아예 없습니다. 그 파일도 이 도구로 계속 읽을 수 있어야 합니다.
    """
    values = []

    for row in episodes:
        raw = row.get(key)

        if raw is None or str(raw).strip() == "":
            continue

        values.append(float(raw))

    return values


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

    # 통과선 위 이탈. 판정에 쓰이는 자다 (#99 2번).
    gate_values = numeric_column(episodes, "gate_lateral_drift_m")

    # 머리(= 실기 라이다 자리) 접촉. **판정에 안 들어간다.** 경고등이다.
    #
    # 열이 아예 없는 옛 CSV 도 그대로 읽힌다. `numeric_column` 이 빈 목록을
    # 돌려주고, 그러면 `head_measured` 가 0 이라 아래 렌더가 절을 통째로 뺀다.
    # 「안 닿았다」와 「안 쟀다」를 이 숫자가 가른다.
    head_counts = numeric_column(episodes, "head_contact_count")
    head_peaks = numeric_column(episodes, "head_contact_peak_n")

    return {
        "terrain": terrain,
        "episodes": n,
        "axes": axes,
        "head_measured": len(head_counts),
        "head_touched": sum(1 for c in head_counts if c > 0),
        "head_count": describe(head_counts),
        "head_peak": describe(head_peaks),
        "gate_drift": describe(gate_values),
        "gate_reached": len(gate_values),
        "endpoint_drift": describe(numeric_column(episodes, "lateral_drift_m")),
        "peak_drift": describe(numeric_column(episodes, "peak_lateral_drift_m")),
        "forward": describe(numeric_column(episodes, "forward_progress_m")),
        "duration": describe(numeric_column(episodes, "duration_s")),
        "velocity_mae": describe(numeric_column(episodes, "velocity_mae_mps")),
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

    for label, key in DRIFT_ROWS:
        d = result[key]
        print(f"{label:<22} {d['mean']:>10.3f} {d['median']:>10.3f} {d['max']:>10.3f}")

    print()
    print(f"낙상(base_contact) {result['fell']} 판 · 시간초과(timeout) {result['timeout']} 판")
    print(f"통과선 도달 {result['gate_reached']}/{n} 판 (도달 못 한 판은 방향 실패)")

    if result["head_measured"]:
        print()
        print("-" * 72)
        print("머리 접촉 (실기 라이다 자리) · 경고등이지 판정이 아님")
        print("-" * 72)
        print(f"닿은 판          {result['head_touched']}/{result['head_measured']}")
        print(f"접촉 스텝 수     평균 {result['head_count']['mean']:.1f}"
              f" · 중앙 {result['head_count']['median']:.1f}"
              f" · 최대 {result['head_count']['max']:.0f}")
        print(f"최대 접촉력 (N)  평균 {result['head_peak']['mean']:.1f}"
              f" · 중앙 {result['head_peak']['median']:.1f}"
              f" · 최대 {result['head_peak']['max']:.1f}")
        print("이 숫자는 위 판정축에 하나도 들어가지 않는다."
              " 「몇 N 부터 부서지는가」는 아직 `미확인`.")

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

    for label, key in DRIFT_ROWS:
        d = result[key]
        print(f"| {label} | {d['mean']:.3f} | {d['median']:.3f} | {d['max']:.3f} |")

    print()
    print(f"낙상 {result['fell']} 판 · 시간초과 {result['timeout']} 판 "
          f"· 통과선 도달 {result['gate_reached']}/{n} 판")

    if result["head_measured"]:
        print()
        print("**머리 접촉 (실기 라이다 자리) · 경고등이지 판정이 아님**")
        print()
        print("| 항목 | 평균 | 중앙 | 최대 |")
        print("|---|---|---|---|")
        print(f"| 접촉 스텝 수 | {result['head_count']['mean']:.1f} "
              f"| {result['head_count']['median']:.1f} "
              f"| {result['head_count']['max']:.0f} |")
        print(f"| 최대 접촉력 (N) | {result['head_peak']['mean']:.1f} "
              f"| {result['head_peak']['median']:.1f} "
              f"| {result['head_peak']['max']:.1f} |")
        print()
        print(f"닿은 판 {result['head_touched']}/{result['head_measured']} "
              "· 이 숫자는 판정축에 하나도 안 들어간다 "
              "· 「몇 N 부터 부서지는가」는 `미확인`")


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
