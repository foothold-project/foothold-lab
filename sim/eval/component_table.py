# -*- coding: utf-8 -*-
"""`overall_success` 를 **네 성분으로 펴서** 지형 x 속도 x 정책 표로 낸다.

분류: 운영
작성: Claude 세션 (오흥재 지시) · 2026-09-20
근거: inbox/jay/20260920-H-design.md 5절 · 요약 CSV 의 네 성분 열
요지: 이미 나와 있는 요약 CSV 를 다시 읽어 성분을 펴 놓는다. 시뮬을 다시 안 돌린다
상태: 확정
판: v1.0

## 무엇을 하나

평가 하네스는 **모든 지형에 같은 종목**을 묻는다.

```
overall_success = 생존 AND 전진(3 m) AND 속도추종(MAE <= 0.25) AND 방향(횡이탈 <= 0.75 m)
```

요약 CSV 에는 그 **네 성분이 이미 따로** 적혀 있다. 이 파일은 그것을
**지형 x 속도 x 정책으로 펴 놓기만** 한다.

## 이 파일이 «안» 하는 것

- **어느 성분이 그 지형의 기준인가를 안 정한다.** 팀장 승인 전이다
- **`overall_success` 를 안 바꾸고 안 내린다.** 성적표는 그것 하나다
- **판정을 안 한다.** Wilson 도 안 돌린다. 여기 나오는 숫자는 «읽는 자리» 다

왜 이렇게까지 좁히나. 기준 초안은 **F 와 v1 의 숫자를 본 뒤에** 쓰였다.
그대로 쓰면 **결과에 맞춘 기준**이 된다. 예측표를 판정 전에 박는 것과 같은
이유로, 기준은 **숫자를 보기 전에** 정해져야 한다.

## 왜 성분을 펴 보나

`gap` 1.5 에서 v1 은 **틈을 100 % 건넜고 100 % 똑바로 갔는데 종합이 68 %** 다.
32 퍼센트포인트가 「건넜는데 속도를 못 맞춰서」 실패로 세어졌다. **틈 앞에서
느려지는 것이 옳은 행동일 수 있는데 지금 종합 기준은 그것을 벌준다.**

그것이 **사실인지** 이 표가 보여 준다. **어떻게 할지는 이 표가 안 정한다.**
"""

from __future__ import annotations

import argparse
import csv
import json
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 정책마다 축 1 결과가 있는 자리. `maindata-v1` 만 속도 폴더 이름이 다르다.
RUNS = {
    "foothold-v1": os.path.join("sim", "eval", "results", "maindata-v1", "foothold-v1"),
    "D": os.path.join("sim", "eval", "results", "20260918-D-axis1"),
    "E": os.path.join("sim", "eval", "results", "20260920-E-axis1"),
    "F": os.path.join("sim", "eval", "results", "20260920-F-axis1"),
    "G": os.path.join("sim", "eval", "results", "20260920-G-axis1"),
    "H": os.path.join("sim", "eval", "results", "20260920-H-axis1"),
}
V1_SPEED_DIRS = {"v0.5": "v0.5", "v1.0": "v1", "v1.5": "v1.5"}
SPEEDS = {"v0.5": 0.5, "v1.0": 1.0, "v1.5": 1.5}

# CSV 열 이름 -> 표에 쓸 이름. **이 넷이 AND 로 묶여 overall 이 된다.**
COMPONENTS = (
    ("survival_rate", "생존"),
    ("progress_success_rate", "전진"),
    ("tracking_success_rate", "속도추종"),
    ("direction_success_rate", "방향"),
)


def read_rows():
    """다섯(또는 여섯) 판의 요약 CSV 를 전부 읽어 평평한 행으로."""
    rows = []
    missing = []

    for policy, root in RUNS.items():
        for terrain_set in ("unseen10", "rough6"):
            for tag, vx in SPEEDS.items():
                speed_dir = V1_SPEED_DIRS[tag] if policy == "foothold-v1" else tag
                path = os.path.join(REPO_ROOT, root, terrain_set, "d0.5",
                                    speed_dir, "generalization_summary.csv")

                if not os.path.isfile(path):
                    missing.append(f"{policy}/{terrain_set}/{tag}")
                    continue

                with open(path, encoding="utf-8-sig", newline="") as handle:
                    for row in csv.DictReader(handle):
                        entry = {
                            "policy": policy,
                            "terrain_set": terrain_set,
                            "terrain": row["terrain"],
                            "command_vx_mps": vx,
                            "episodes": int(float(row["episodes"])),
                            "overall_pct": round(float(row["overall_success_rate"]) * 100, 1),
                        }
                        for column, label in COMPONENTS:
                            entry[label] = round(float(row[column]) * 100, 1)

                        # 네 성분을 낮은 순으로. `overall` 은 넷의 AND 라
                        # **언제나 최저 성분 이하**다.
                        ordered = sorted(COMPONENTS, key=lambda c: entry[c[1]])
                        entry["최저성분"] = ordered[0][1]
                        entry["최저값"] = entry[ordered[0][1]]

                        # **둘째로 낮은 성분과 종합의 차.** 이것이 「한 성분만
                        # 걸려 깎인 양」이다. 최저 성분과 종합의 차는 거의
                        # 언제나 0 이라 아무것도 안 보인다 (AND 라 overall 은
                        # 최저 이하이고, 실패가 같은 판에 겹치면 같아진다).
                        entry["둘째값"] = entry[ordered[1][1]]
                        entry["한성분비용"] = round(
                            entry["둘째값"] - entry["overall_pct"], 1)

                        # 최저 성분과 종합의 차 · 0 이면 실패가 «같은 판» 에
                        # 겹쳐 있다는 뜻이고, 크면 서로 다른 판에서 깨진 것이다.
                        entry["성분간겹침차"] = round(
                            entry["최저값"] - entry["overall_pct"], 1)

                        rows.append(entry)

    return rows, missing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(
        REPO_ROOT, "sim", "eval", "results", "20260920-components"))
    parser.add_argument("--min_gap", type=float, default=10.0,
                        help="이 퍼센트포인트 이상 벌어진 칸만 표로 찍는다")
    args = parser.parse_args()

    rows, missing = read_rows()

    if not rows:
        raise SystemExit("요약 CSV 를 하나도 못 읽었다")

    os.makedirs(args.out, exist_ok=True)

    fields = (["policy", "terrain_set", "terrain", "command_vx_mps", "episodes",
               "overall_pct"] + [label for _, label in COMPONENTS]
              + ["최저성분", "최저값", "둘째값", "한성분비용", "성분간겹침차"])

    csv_path = os.path.join(args.out, "components.csv")

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    policies = sorted({r["policy"] for r in rows})

    print(f"칸 {len(rows)} 개 · 정책 {len(policies)} ({', '.join(policies)})")

    if missing:
        print(f"없는 판 {len(missing)} 개: {', '.join(missing[:6])}"
              + (" ..." if len(missing) > 6 else ""))

    # -- **한 성분만 걸려 깎인 칸.** 나머지 셋은 높은데 종합이 낮은 자리다.
    wide = [r for r in rows if r["한성분비용"] >= args.min_gap]
    wide.sort(key=lambda r: -r["한성분비용"])

    print()
    print(f"둘째로 낮은 성분이 종합보다 {args.min_gap:.0f} %p 이상 높은 칸 "
          f"{len(wide)} 개")
    print("**한 성분 하나가 그 칸을 혼자 끌어내린 자리다.**")
    print(f"{'정책':<12}{'지형':<20}{'vx':>5}{'종합':>6}"
          + "".join(f"{label:>9}" for _, label in COMPONENTS)
          + f"{'최저':>10}{'비용':>7}")

    for r in wide[:40]:
        print(f"{r['policy']:<12}{r['terrain']:<20}{r['command_vx_mps']:>5}"
              f"{r['overall_pct']:>6.0f}"
              + "".join(f"{r[label]:>9.0f}" for _, label in COMPONENTS)
              + f"{r['최저성분']:>10}{r['한성분비용']:>7.0f}")

    # -- 실패가 서로 «다른» 판에서 났는가. 0 이면 같은 판이 다 깨진 것이다.
    spread = [r for r in rows if r["성분간겹침차"] > 0]
    print()
    print(f"최저 성분보다도 종합이 더 낮은 칸 {len(spread)} 개 "
          f"(서로 다른 판에서 다른 성분이 깨진 자리)")
    for r in sorted(spread, key=lambda r: -r["성분간겹침차"])[:10]:
        print(f"  {r['policy']:<12}{r['terrain']:<18}{r['command_vx_mps']:>5}"
              f"  종합 {r['overall_pct']:>5.0f}  최저 {r['최저값']:>5.0f}"
              f"  차 {r['성분간겹침차']:>5.0f}")

    # -- 어느 성분이 가장 자주 최저인가. **기준을 정하는 것이 아니라 세는 것이다.**
    counts = {}

    for r in rows:
        key = (r["terrain"], r["최저성분"])
        counts[key] = counts.get(key, 0) + 1

    print("\n지형마다 «가장 낮은 성분» 이 무엇이었나 (칸 수)")
    print("**이것은 기준이 아니다. 센 것이다.**")

    terrains = sorted({r["terrain"] for r in rows})

    print(f"{'지형':<22}" + "".join(f"{label:>10}" for _, label in COMPONENTS))
    for terrain in terrains:
        print(f"{terrain:<22}"
              + "".join(f"{counts.get((terrain, label), 0):>10}"
                        for _, label in COMPONENTS))

    payload = {
        "schema": "foothold-component-table/1",
        "built_by": "sim/eval/component_table.py",
        "note": (
            "overall_success 를 네 성분으로 편 것이다. **기준을 정하지 않는다.** "
            "어느 성분이 그 지형의 기준인가는 팀장 승인 전이고, 성적표는 "
            "overall_success 하나로 둔다. 여기 숫자는 «읽는 자리» 이지 "
            "합격선이 아니다"
        ),
        "components_are": "생존 AND 전진 AND 속도추종 AND 방향 = overall_success",
        "policies": policies,
        "missing_runs": missing,
        "rows": rows,
    }

    json_path = os.path.join(args.out, "components.json")

    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    print(f"\n적었습니다: {os.path.relpath(csv_path, REPO_ROOT)}")
    print(f"           {os.path.relpath(json_path, REPO_ROOT)}")


if __name__ == "__main__":
    main()
