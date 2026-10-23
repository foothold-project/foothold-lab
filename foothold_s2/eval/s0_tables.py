"""S0 결과 표 만들기 (41 형식). 순수 파이썬: 원자료 CSV 에서 읽어 센다. 손으로 쓴 숫자 없음.

  python -m foothold_s2.eval.s0_tables --root <s0 폴더> --out <표 폴더> [--policies e1,v2,nvidia]

만드는 것
  axis1_cells.csv      판 x 48칸: overall 과 성분 넷, R_body/S/J_body 와 Wilson, 평균(48 · 범위 안 32 · 속도별)
  axis2_cells.csv      판 x 아홉 칸: 기본 시드 판정 + 시드 셋 값 + 시드 셋 중 문턱 못 넘은 수
  axis3_cells.csv      판 x 지형군 x 방향(23칸): 풀링한 R/S/J, 명령 방향 진행, 방향 이탈 비율, 열 `basis`
  axis3_by_terrain.csv 판 x 지형군 x 방향 x 지형 (평균대 · 빔처럼 따로 볼 때)
  compare_policies.csv 칸마다 세 판을 나란히 (판 비교 CSV)
「범위 밖」 칸은 측정하지 않았으므로 `status=out_of_range` 행으로만 남긴다 (값 칸은 빈 칸).
"""

import argparse
import json
import os

from foothold_s2.eval import cells, compare, manifest, rsj, s0_chain


def _bool(text):
    if text in ("True", "true"):
        return True
    if text in ("False", "false"):
        return False

    return None


def _num(text):
    return float(text) if text not in ("", None) else None


BOOL_COLS = ("overall_success", "survival_success", "progress_success", "tracking_success",
             "direction_success", "R_body", "S", "J_body", "yaw_dev_flag", "gate_ok")
NUM_COLS = ("forward_progress_m", "peak_lateral_drift_m", "velocity_mae_mps", "cmd_progress_ratio",
            "cmd_progress_ratio_capped", "yaw_follow_ratio", "yaw_dev_deg", "heading_err_deg",
            "lateral_dev_m", "gate_lateral_dev_m", "gate_lateral_drift_m")


def read_rows(path):
    out = []

    for row in manifest.read_csv(path):
        for col in BOOL_COLS:
            if col in row:
                row[col] = _bool(row[col])

        for col in NUM_COLS:
            if col in row:
                row[col] = _num(row[col])

        out.append(row)

    return out


def axis1_table(root, policies):
    rows = []

    for policy in policies:
        base = os.path.join(root, policy, "axis1") if policy != "e1" else _e1_axis1(root)
        values = {}

        for set_name, names in cells.AXIS1_SETS.items():
            for speed in cells.AXIS1_SPEEDS:
                path = os.path.join(base, set_name, "v%s" % speed, "axis1_raw.csv")

                if not os.path.isfile(path):
                    continue

                raw = read_rows(path)

                for terrain in names:
                    picked = [r for r in raw if r["terrain"] == terrain]
                    cell = rsj.summarize_axis1_cell(picked)
                    values[(set_name, terrain, speed)] = cell["overall_success"]
                    rows.append(dict(policy=policy, set=set_name, terrain=terrain, speed=speed,
                                     in_range=speed in cells.AXIS1_IN_RANGE_SPEEDS,
                                     **{k: v for k, v in cell.items()}))

        means = compare.cell_means(values)
        rows.append(dict(policy=policy, set="ALL", terrain="mean_48", speed="", in_range="",
                         overall_success=means["mean_all"], episodes=means["n_cells"]))
        rows.append(dict(policy=policy, set="ALL", terrain="mean_in_range_32", speed="", in_range=True,
                         overall_success=means["mean_in_range"], episodes=means["n_in_range"]))

    return _uniform(rows)


def _e1_axis1(root):
    """E1 축 1 은 연쇄 전에 따로 돌려 둔 폴더가 있을 수 있다 (`<root>/../axis1_e1`)."""
    own = os.path.join(root, "e1", "axis1")

    return own if os.path.isdir(own) else os.path.join(os.path.dirname(root.rstrip("/\\")), "axis1_e1")


def axis2_table(root, policies):
    rows = []

    for policy in policies:
        try:
            for r in compare.axis2_seed_table(os.path.join(root, policy)):
                rows.append(dict(policy=policy, seeds="%s" % (cells.AXIS2_SEEDS,), **r))
        except FileNotFoundError:
            continue

    return rows


def axis3_tables(root, policies, vy_obs=None):
    pooled_rows = []
    terrain_rows = []

    for policy in policies:
        value = vy_obs.get(policy) if isinstance(vy_obs, dict) else vy_obs
        for spec in cells.axis3_table(vy_obs=value):
            base = dict(policy=policy, group=spec["group"], direction=spec["direction"],
                        status=spec["status"], basis=spec.get("basis", ""),
                        variant=spec.get("variant", ""), gate_eligible=spec.get("gate_eligible"),
                        label=spec.get("label", ""))

            if spec["status"] != "measure":
                pooled_rows.append(base)
                continue

            raw = []
            exclusions = set()

            for cmd in spec["commands"]:
                tag = s0_chain.axis3_job_tag(spec, cmd)
                path = os.path.join(root, policy, "axis3", tag, "axis3_raw.csv")
                starts_path = os.path.join(os.path.dirname(path), "axis3_starts.json")
                if os.path.isfile(starts_path):
                    with open(starts_path, encoding="utf-8") as handle:
                        plan = json.load(handle)
                    exclusions.update(n for n, start in plan.items() if start["status"] == "no_start")

                if os.path.isfile(path):
                    raw += read_rows(path)

            raw = [r for r in raw if r["terrain"] not in exclusions]
            base["excluded_start_terrains"] = ";".join(sorted(exclusions))
            if exclusions:
                base["gate_eligible"] = False
                base["label"] = "일부 지형 시작점 없음 · 합산 판정 제외"
            for terrain in sorted(exclusions):
                terrain_rows.append(dict(base, terrain=terrain, status="no_start",
                                         label="시작점 없음 · 판정 제외", gate_eligible=False))
            if not raw:
                pooled_rows.append(dict(base, status="no_start" if exclusions else "not_run",
                                        gate_eligible=False))
                continue

            pooled_rows.append(dict(base, commands=";".join(s0_chain._cmd_text(c) for c in spec["commands"]),
                                    **rsj.summarize_axis3_cell(raw)))

            for terrain in sorted({r["terrain"] for r in raw}):
                picked = [r for r in raw if r["terrain"] == terrain]
                terrain_rows.append(dict(base, terrain=terrain, gate_eligible=spec.get("gate_eligible"),
                                         label=spec.get("label", ""), **rsj.summarize_axis3_cell(picked)))

    return _uniform(pooled_rows), _uniform(terrain_rows)


def _uniform(rows):
    """CSV 열을 모든 행의 합집합으로 맞춘다 (없는 칸은 빈 칸)."""
    names = []

    for row in rows:
        for key in row:
            if key not in names:
                names.append(key)

    return [{k: r.get(k) for k in names} for r in rows]


def compare_policies(axis1_rows, axis3_rows):
    """칸마다 세 판을 나란히. 축 1 은 overall, 축 3 은 J_body 와 생존."""
    out = []
    by_cell = {}

    for r in axis1_rows:
        if r["terrain"].startswith("mean_"):
            key = ("axis1", r["terrain"], "", "")
        else:
            key = ("axis1", r["set"] + "/" + r["terrain"], "", str(r["speed"]))

        by_cell.setdefault(key, {})[r["policy"]] = r.get("overall_success")

    for r in axis3_rows:
        direction = r["direction"] + ("/" + r["variant"] if r.get("variant") else "")
        if r.get("status") != "measure":
            key = ("axis3", r["group"], direction, r.get("status"))
            by_cell.setdefault(key, {})[r["policy"]] = None
            continue

        by_cell.setdefault(("axis3", r["group"], direction, "J_body|S"), {})[r["policy"]] =             "%s|%s" % (r.get("J_body_rate"), r.get("S_rate"))
        # 방향 이탈 비율과 명령 방향 진행도 꼭 나란히 둔다 (41 §9 「방향 이탈 <= 0.1」 이 달성 가능한 기준인지 보는 근거).
        by_cell.setdefault(("axis3", r["group"], direction, "yaw_dev_rate"), {})[r["policy"]] =             r.get("yaw_dev_rate")
        by_cell.setdefault(("axis3", r["group"], direction, "progress_capped"), {})[r["policy"]] =             r.get("mean_cmd_progress_ratio_capped")

    policies = sorted({r["policy"] for r in axis1_rows} | {r["policy"] for r in axis3_rows})

    for (axis, a, b, c), vals in by_cell.items():
        row = {"axis": axis, "cell": a, "direction": b, "extra": c}
        row.update({p: vals.get(p) for p in policies})
        out.append(row)

    return out


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--policies", default="e1,v2,nvidia")
    parser.add_argument("--vy_obs", action="append", default=[],
                        help="실행 때와 같은 POLICY=MPS 관측값, 반복 가능")
    args = parser.parse_args(argv)

    policies = args.policies.split(",")
    try:
        observed = s0_chain.parse_vy_obs(args.vy_obs, policies)
    except ValueError as exc:
        parser.error(str(exc))
    os.makedirs(args.out, exist_ok=True)

    a1 = axis1_table(args.root, policies)
    a2 = axis2_table(args.root, policies)
    a3, a3t = axis3_tables(args.root, policies, vy_obs=observed)

    for name, rows in (("axis1_cells.csv", a1), ("axis2_cells.csv", a2), ("axis3_cells.csv", a3),
                       ("axis3_by_terrain.csv", a3t), ("compare_policies.csv", compare_policies(a1, a3))):
        if rows:
            manifest.write_csv(os.path.join(args.out, name), rows)
            print("쓴 표", name, len(rows), "줄")
        else:
            print("빈 표(쓰지 않음)", name)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
