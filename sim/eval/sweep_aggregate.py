"""난이도 스윕의 칸 30개를 지형별 파일 하나로 모은다.

**하네스 출력은 하나도 안 고친다.** `runs/*/generalization_raw.csv` 는 24열
(`metrics.RAW_COLUMNS`) 그대로 남고, 여기서는 그것을 **읽기만** 한다.

모으는 파일에는 칸 좌표 셋(`difficulty` · `command_vx` · `eval_duration_s`)을
앞에 붙인다. 안 붙이면 30개 칸이 한 파일에서 구별이 안 된다. **좌표는 실행
인자에서 베끼지 않고 그 칸의 `run_manifest.json` 에서 되읽는다.** 인자를 베끼면
덮어쓰기가 안 먹은 칸도 «먹은 것처럼» 적히기 때문이다.

    python sim/eval/sweep_aggregate.py sim/eval/results/20260910-difficulty-sweep

내는 것:
  by_terrain/<지형>/<지형>_sweep.csv   지형 하나의 전 칸 원시 행
  sweep_summary.csv                    (지형 x 속도 x 난이도) 요약 한 줄씩
"""

import csv
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))

if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import metrics  # noqa: E402

# 칸 좌표. 원시 24열 **앞**에 붙는다.
CELL_COLUMNS = ("difficulty", "command_vx", "eval_duration_s")


def read_cell(run_dir):
    """칸 하나. 좌표는 manifest 에서, 행은 원시 CSV 에서."""
    manifest_path = os.path.join(run_dir, "run_manifest.json")
    raw_path = os.path.join(run_dir, "generalization_raw.csv")

    if not (os.path.exists(manifest_path) and os.path.exists(raw_path)):
        return None

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    lower, upper = manifest["terrain_difficulty_range"]

    # 스윕은 칸마다 난이도가 **하나**여야 한다. 범위로 남아 있으면 그 칸은
    # 「난이도 하나」가 아니므로 조용히 섞이기 전에 여기서 죽는다.
    if lower != upper:
        raise RuntimeError(
            f"{run_dir}: 난이도가 범위다 ({lower}, {upper}). 칸 하나에 난이도 하나여야 한다."
        )

    # 행에 붙는 좌표. **이 셋만** 붙는다. 더 넣으면 CSV 열이 늘어난다.
    cell = {
        "difficulty": lower,
        "command_vx": manifest["command_vx_mps"],
        "eval_duration_s": manifest["eval_duration_s"],
    }

    # 문서용 딸림 정보. 행에는 **안** 붙는다.
    # 재현 명령은 기계가 적은 `argv` 를 그대로 쓴다. 사람이 옮겨 적으면
    # 문서와 실제가 조용히 갈라진다.
    meta = {
        "run_dir": os.path.basename(run_dir),
        "argv": manifest.get("argv", []),
        "started_at_utc": manifest.get("started_at_utc", ""),
        "policy_sha256": manifest.get("policy_sha256", ""),
        "difficulty_overridden": manifest.get("terrain_difficulty_overridden"),
        "min_progress_m": manifest.get("min_progress_m"),
        "max_lateral_drift_m": manifest.get("max_lateral_drift_m"),
        "episodes_recorded": manifest.get("episodes_recorded"),
    }

    with open(raw_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise RuntimeError(f"{run_dir}: 원시 행이 없다.")

    # 관문 · 폴더 이름이 주장하는 좌표와 manifest 가 되읽은 값이 같은가.
    #
    # **이것이 없으면 조용히 틀린다.** 칸 이름은 사람이 실행기에 적은 것이고
    # manifest 는 기계가 cfg 에서 되읽은 것이다. 둘이 어긋난 채 모으면
    # 「난이도 0.3 의 결과」라고 적힌 자리에 다른 난이도가 들어앉는다.
    # 그 CSV 는 오류를 내지 않고, 표도 정상으로 보인다.
    name = os.path.basename(run_dir)

    try:
        claimed_vx = float(name.split("-")[0][1:])
        claimed_difficulty = float(name.split("-")[1][1:])
    except (IndexError, ValueError):
        raise RuntimeError(
            f"{run_dir}: 칸 이름이 `v<속도>-d<난이도>` 꼴이 아니다."
        )

    if abs(cell["difficulty"] - claimed_difficulty) > 1e-9:
        raise RuntimeError(
            f"{run_dir}: 폴더는 난이도 {claimed_difficulty} 라는데 "
            f"manifest 는 {cell['difficulty']} 다."
        )

    if abs(cell["command_vx"] - claimed_vx) > 1e-9:
        raise RuntimeError(
            f"{run_dir}: 폴더는 속도 {claimed_vx} 라는데 "
            f"manifest 는 {cell['command_vx']} 다."
        )

    return cell, meta, rows


def quote(token):
    """공백이 든 인수만 따옴표로 감싼다. 붙여넣어 그대로 돌아가야 한다."""
    return f'"{token}"' if (" " in token or "|" in token) else token


def write_terrain_readme(terrain_dir, terrain, rows, metas):
    """지형 하나의 재현 문서. **명령은 manifest 의 `argv` 를 그대로 옮긴다.**"""
    path = os.path.join(terrain_dir, "README.md")

    cells = sorted({(m["command_vx"], m["difficulty"]) for m in metas})
    speeds = sorted({m["command_vx"] for m in metas})
    difficulties = sorted({m["difficulty"] for m in metas})

    sha = {m["policy_sha256"] for m in metas if m["policy_sha256"]}

    lines = [
        f"# `{terrain}` · 난이도 스윕 원시 기록",
        "",
        "> 분류: 실험",
        "> 작성: 오흥재 · 2026-09-10",
        "> 근거: 실측 (Isaac Lab · NVIDIA 공식 체크포인트 · RTX 5080 2대)",
        f"> 요지: `{terrain}` 한 종을 난이도 {len(difficulties)}단계 x 속도 "
        f"{len(speeds)}단계로 {len(rows)}판 잰 원시 기록",
        "> 상태: 초안",
        "",
        "이 폴더의 `%s_sweep.csv` 는 **모아 놓은 것**이고, 정본 원시 파일은"
        % terrain,
        "`../../runs/<칸>/generalization_raw.csv` 입니다. 모으면서 더한 열은",
        "맨 앞 셋(`difficulty` · `command_vx` · `eval_duration_s`)뿐이고,",
        # **숫자를 손으로 적지 않는다.** 열을 더하면 이 문장만 조용히 틀린 채
        # 남는다. 2026-09-10 에 24 -> 27 이 되면서 실제로 그럴 뻔했다.
        "나머지 %d열은 `metrics.RAW_COLUMNS` 그대로입니다." % len(metrics.RAW_COLUMNS),
        "",
        "## 무엇을 쟀나",
        "",
        "| 항목 | 값 |",
        "|---|---|",
        f"| 지형 | `{terrain}` |",
        f"| 난이도 | {', '.join(str(d) for d in difficulties)} |",
        f"| 명령 속도 | {', '.join(str(s) + ' m/s' for s in speeds)} |",
        f"| 칸 | {len(cells)} |",
        f"| 판 | {len(rows)} |",
        f"| 정책 sha256 | `{sorted(sha)[0] if len(sha) == 1 else '칸마다 다름 · 확인 필요'}` |",
        "",
        "**거리 예산을 6 m 로 고정했습니다.** 속도가 바뀌어도 로봇이 갈 수 있는",
        "거리는 6 m 로 같고, 제한 시간만 `6.0 / 속도` 로 바뀝니다",
        "(12초 · 6초 · 4초). 그래서 속도축을 가로질러 전진거리를 그대로 비교할 수",
        "있습니다. 통과선은 세 속도 모두 3 m 입니다.",
        "",
        "## 그대로 다시 돌리는 법",
        "",
        "아래는 **기계가 `run_manifest.json` 에 적은 `argv` 를 그대로 옮긴 것**입니다.",
        "사람이 옮겨 적은 것이 아닙니다. Windows 에서는 앞에",
        "`OMNI_KIT_ACCEPT_EULA=YES` 와 `CUDA_VISIBLE_DEVICES=<번호>` 가 필요합니다.",
        "",
        "```bash",
    ]

    for meta in sorted(metas, key=lambda m: (m["command_vx"], m["difficulty"])):
        argv = meta["argv"]

        if not argv:
            lines.append(f"# {meta['run_dir']}: argv 기록 없음")
            continue

        # `argv[0]` 은 스크립트 경로다. 붙여넣어 그대로 돌게 `python` 을 앞에 세운다.
        lines.append(f"# {meta['run_dir']}")
        lines.append("python " + " ".join(quote(t) for t in argv))
        lines.append("")

    lines += [
        "```",
        "",
        "요약을 다시 뽑으려면 (Isaac 도 GPU 도 필요 없습니다):",
        "",
        "```bash",
        "python sim/eval/sweep_aggregate.py sim/eval/results/20260910-difficulty-sweep",
        f"python sim/eval/report.py {terrain}_sweep.csv",
        "```",
        "",
    ]

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    root = os.path.abspath(sys.argv[1])
    runs_root = os.path.join(root, "runs")

    if not os.path.isdir(runs_root):
        raise SystemExit(f"runs 폴더가 없다: {runs_root}")

    by_terrain = {}
    metas = []
    cells = 0

    for name in sorted(os.listdir(runs_root)):
        run_dir = os.path.join(runs_root, name)

        if not os.path.isdir(run_dir):
            continue

        found = read_cell(run_dir)

        if found is None:
            print(f"  건너뜀 (아직 결과 없음): {name}")
            continue

        cell, meta, rows = found
        cells += 1
        metas.append(dict(cell, **meta))

        for row in rows:
            merged = dict(cell)
            merged.update(row)
            by_terrain.setdefault(row["terrain"], []).append(merged)

    if cells == 0:
        raise SystemExit("모을 칸이 하나도 없다.")

    fieldnames = list(CELL_COLUMNS) + list(metrics.RAW_COLUMNS)

    out_root = os.path.join(root, "by_terrain")
    os.makedirs(out_root, exist_ok=True)

    for terrain, rows in sorted(by_terrain.items()):
        terrain_dir = os.path.join(out_root, terrain)
        os.makedirs(terrain_dir, exist_ok=True)

        path = os.path.join(terrain_dir, f"{terrain}_sweep.csv")

        rows.sort(key=lambda r: (r["command_vx"], r["difficulty"],
                                 int(r["env_id"]), int(r["episode"])))

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"  {path}  ({len(rows)}행)")

        write_terrain_readme(terrain_dir, terrain, rows, metas)

    # (지형 x 속도 x 난이도) 요약. `metrics.summarize` 를 칸마다 다시 부른다.
    summary_path = os.path.join(root, "sweep_summary.csv")
    summary_fields = list(CELL_COLUMNS) + list(metrics.SUMMARY_COLUMNS)

    summary_rows = []

    for terrain, rows in sorted(by_terrain.items()):
        groups = {}

        for row in rows:
            groups.setdefault((row["command_vx"], row["difficulty"]), []).append(row)

        for (vx, difficulty), group in sorted(groups.items()):
            # `summarize` 는 판정 열이 진짜 불리언이어야 한다. CSV 에서 되읽은
            # "True"/"False" 를 되돌려 준다.
            restored = []

            for row in group:
                copy = dict(row)

                for key in ("overall_success", "survival_success", "progress_success",
                            "tracking_success", "direction_success"):
                    copy[key] = (row[key] == "True")

                restored.append(copy)

            summarized = metrics.summarize(restored, [terrain])[0]

            summarized.update({
                "difficulty": difficulty,
                "command_vx": vx,
                "eval_duration_s": group[0]["eval_duration_s"],
            })

            summary_rows.append(summarized)

    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"\n칸 {cells}개 · 지형 {len(by_terrain)}종 · 요약 {len(summary_rows)}줄")
    print(summary_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
