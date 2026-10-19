"""옛 하네스 결과와의 대조 (41 §11 L1 대조). 순수 파이썬.

원칙: 어긋나면 새 하네스를 고친다. 옛 값을 고치지 않고, 숫자를 맞추려고 판정을 바꾸지 않는다.
어긋난 칸은 «어느 칸이 얼마나» 표로 남긴다 (원인 후보는 사람이 읽고 붙인다).
"""

import os

from foothold_s2.eval import cells, manifest

TOLERANCE = 0.02


def cell_means(rows_by_cell):
    """{(set, terrain, speed): overall 비율} -> 48 칸 평균, 범위 안 32 칸 평균."""
    all_vals = list(rows_by_cell.values())
    in_range = [v for (_s, _t, sp), v in rows_by_cell.items() if sp in cells.AXIS1_IN_RANGE_SPEEDS]

    return {
        "n_cells": len(all_vals),
        "mean_all": sum(all_vals) / len(all_vals) if all_vals else None,
        "n_in_range": len(in_range),
        "mean_in_range": sum(in_range) / len(in_range) if in_range else None,
    }


def load_axis1_cells(root, summary_name, overall_key):
    """`root/<set>/.../v<speed>/` 아래 요약 CSV 를 칸별 overall 비율로. 없는 칸은 건너뛴다."""
    out = {}

    for dirpath, _dirs, files in os.walk(root):
        if summary_name not in files:
            continue

        for row in manifest.read_csv(os.path.join(dirpath, summary_name)):
            set_name = row.get("set") or _guess_set(dirpath)
            speed = float(row["speed"]) if row.get("speed") else _guess_speed(dirpath)
            out[(set_name, row["terrain"], speed)] = float(row[overall_key])

    return out


def _guess_set(path):
    p = path.replace("\\", "/")

    return "rough6" if "/rough6/" in p else "unseen10"


def _guess_speed(path):
    p = path.replace("\\", "/")
    leaf = p.rstrip("/").split("/")[-1]

    return float(leaf[1:])


def diff_table(new, old, tolerance=TOLERANCE):
    """칸마다 새 값 - 옛 값. 허용 안 벗어난 칸 수와 가장 큰 차이를 같이 낸다."""
    rows = []

    for key in sorted(set(new) | set(old)):
        a, b = new.get(key), old.get(key)
        delta = None if a is None or b is None else a - b
        rows.append({"set": key[0], "terrain": key[1], "speed": key[2], "new": a, "old": b,
                     "delta": delta, "within": None if delta is None else abs(delta) <= tolerance})

    known = [r for r in rows if r["delta"] is not None]

    return rows, {
        "cells_compared": len(known),
        "cells_outside_tolerance": sum(1 for r in known if not r["within"]),
        "max_abs_delta": max((abs(r["delta"]) for r in known), default=None),
        "missing_in_new": sum(1 for r in rows if r["new"] is None),
        "missing_in_old": sum(1 for r in rows if r["old"] is None),
    }


def episode_level_match(new_raw_path, old_raw_path):
    """같은 (지형, env, 판 번호) 끼리 판정을 맞대 본다. 같은 시드에서 판 단위로 같은지."""
    new = {(r["terrain"], r["env_id"], r["episode"]): r for r in manifest.read_csv(new_raw_path)}
    old = {(r["terrain"], r["env_id"], r["episode"]): r for r in manifest.read_csv(old_raw_path)}
    keys = sorted(set(new) & set(old))
    same = 0
    diffs = []

    for k in keys:
        a = str(new[k]["overall_success"]) == str(old[k]["overall_success"])

        if a:
            same += 1
        else:
            diffs.append(k)

    return {"joined": len(keys), "same_overall": same, "differ": diffs[:20],
            "only_new": len(set(new) - set(old)), "only_old": len(set(old) - set(new))}


def axis1_report(new_root, old_root, out_csv=None):
    """축 1 48 칸 대조. 새 도구 `axis1_summary.csv` 와 옛 `generalization_summary.csv` 를 칸 단위로 맞댄다.

    돌려주는 것: 칸 표, 요약(칸 수 · 허용 밖 칸 수 · 최대 차이), 새 · 옛 평균(48 · 범위 안 32 · 속도별),
    판 단위 일치(같은 (지형, env, 판) 의 overall 이 같은 비율).
    """
    new = load_axis1_cells(new_root, "axis1_summary.csv", "overall_success")
    old = load_axis1_cells(old_root, "generalization_summary.csv", "overall_success_rate")
    rows, summary = diff_table(new, old)

    per_speed = {}

    for speed in cells.AXIS1_SPEEDS:
        a = [v for (_s, _t, sp), v in new.items() if sp == speed]
        b = [v for (_s, _t, sp), v in old.items() if sp == speed]
        per_speed[speed] = {"new": sum(a) / len(a) if a else None, "old": sum(b) / len(b) if b else None,
                            "n_new": len(a), "n_old": len(b)}

    episodes = {}

    for dirpath, _dirs, files in os.walk(new_root):
        if "axis1_raw.csv" not in files:
            continue

        leaf = os.path.relpath(dirpath, new_root).replace("\\", "/")
        old_dir = None

        for od, _d, of in os.walk(old_root):
            if "generalization_raw.csv" in of and os.path.relpath(od, old_root).replace("\\", "/").replace("/d0.5", "") == leaf:
                old_dir = od

        if old_dir:
            episodes[leaf] = episode_level_match(os.path.join(dirpath, "axis1_raw.csv"),
                                                 os.path.join(old_dir, "generalization_raw.csv"))

    if out_csv:
        manifest.write_csv(out_csv, rows)

    return {"rows": rows, "summary": summary, "means_new": cell_means(new), "means_old": cell_means(old),
            "per_speed": per_speed, "episodes": episodes}
