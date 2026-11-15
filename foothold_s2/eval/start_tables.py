"""START 시험지 결과 표 (SC-3). 순수 파이썬: `start_raw.csv` 에서 센다. 손으로 쓴 숫자 없음.

  python -m foothold_s2.eval.start_tables --root <start 폴더> --out <표 폴더> [--policies e1,v2,nvidia]

만드는 것
  start_cells.csv     판 x 종류 x 레벨(0..9, ALL): R_body · S · J_body 비율 + Wilson, 주파율, 판 수
  start_pooled.csv    판 x 종류(ALL 레벨 한 줄) + 판 x 「4 종 R 평균」 (S2 관문 G1 · G3 · F26 이 쓰는 값)
  start_top_level.csv 레벨 9(최고 난이도)만 따로

정의: R_body = 몸통이 스폰에서 6.5 m(= 듬성한 구간 6 m + 출발 단 0.5 m, 도착 단 입구) 닿았다. 41 §5 의 「네 발이 유효
지지면 위」 조건은 넣지 않았다. 주파율 = 쓰러지기 전에 간 거리 / 6.5 m (0..1). MEV 는 이 실행에서 재지 않았다(미측정).
「4 종 R 평균」 은 네 종류의 R_body 비율을 같은 비중으로 평균한 것이다 (레벨은 10 단 균등 표본이라 레벨 평균을 겸한다).
"""

import argparse
import os

from foothold_s2.eval import manifest, rsj, start_sheet


def _bool(text):
    return {"True": True, "False": False}.get(text)


def _num(text):
    return float(text) if text not in ("", None) else None


def read_raw(path):
    rows = []

    for row in manifest.read_csv(path):
        for col in ("R_body", "S", "J_body", "yaw_dev_flag"):
            row[col] = _bool(row.get(col, ""))

        for col in ("cmd_progress_m", "crossing_ratio"):
            row[col] = _num(row.get(col, ""))

        row["level"] = int(row["level"])
        rows.append(row)

    return rows


def cell(picked):
    out = {"episodes": len(picked)}
    r = rsj.summarize_rsj(picked)

    for key, val in r.items():
        out[key + "_rate"] = val["rate"]
        out[key + "_lo"] = val["lo"]
        out[key + "_hi"] = val["hi"]

    cross = [x["crossing_ratio"] for x in picked if x["crossing_ratio"] is not None]
    out["mean_crossing_ratio"] = sum(cross) / len(cross) if cross else None

    return out


def build(root, policies):
    cells, pooled, top = [], [], []

    for policy in policies:
        path = os.path.join(root, policy, "start_raw.csv")

        if not os.path.isfile(path):
            continue

        rows = read_raw(path)
        per_kind_r = {}

        for kind in start_sheet.KINDS:
            of_kind = [r for r in rows if r["kind"] == kind]
            levels = sorted({r["level"] for r in of_kind})

            for level in levels:
                c = cell([r for r in of_kind if r["level"] == level])
                cells.append(dict(policy=policy, kind=kind, level=level, **c))

                if level == start_sheet.LEVELS - 1:
                    top.append(dict(policy=policy, kind=kind, level=level, **c))

            allc = cell(of_kind)
            cells.append(dict(policy=policy, kind=kind, level="ALL", **allc))
            pooled.append(dict(policy=policy, kind=kind, **allc))
            per_kind_r[kind] = allc["R_body_rate"]

        mean_r = sum(per_kind_r.values()) / len(per_kind_r)
        pooled.append(dict(policy=policy, kind="MEAN_OF_4_KINDS_R_body", R_body_rate=mean_r,
                           episodes=len(rows)))

    return cells, pooled, top


def _uniform(rows):
    names = []

    for row in rows:
        for key in row:
            if key not in names:
                names.append(key)

    return [{k: r.get(k) for k in names} for r in rows]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--policies", default="e1,v2,nvidia")
    args = parser.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    cells, pooled, top = build(args.root, args.policies.split(","))

    for name, rows in (("start_cells.csv", cells), ("start_pooled.csv", pooled), ("start_top_level.csv", top)):
        if rows:
            manifest.write_csv(os.path.join(args.out, name), _uniform(rows))
            print("쓴 표", name, len(rows), "줄")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
