"""Build an EX-42 M-stage measurement table from recorded logs and GPU samples."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
from statistics import median


ITERATION_TIME = re.compile(r"Iteration time:\s*([0-9]+(?:\.[0-9]+)?)\s*s", re.I)
ITERATION = re.compile(r"Learning iteration\s+(\d+)\s*/\s*(\d+)")
BASELINE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*초/회\s*=\s*EX-41 Windows")
TARGET_ROW = re.compile(
    r"^\|\s*(11/\d+\s+\d+:\d+)\s*\|\s*([0-9.]+)\s*초/회.*?\|\s*([0-9.]+)\s*초/회")
ORDER_RELATIVE = Path("inbox/jay/20261104-ex41-restart/LINUX-DAY-EXPERIMENT-ORDER.md")


def schedule_reference(source: Path) -> tuple[float, list[dict]]:
    document = (source / ORDER_RELATIVE).read_text(encoding="utf-8")
    baseline_match = BASELINE.search(document)
    if not baseline_match:
        raise ValueError("Windows single-GPU baseline missing from M schedule")
    baseline = float(baseline_match.group(1))
    targets = []
    for line in document.splitlines():
        match = TARGET_ROW.match(line)
        if match:
            targets.append({"start": match.group(1), "target_1114_s": float(match.group(2)),
                            "target_1121_s": float(match.group(3))})
    if len(targets) != 3:
        raise ValueError("expected exactly three M schedule target rows")
    return baseline, targets


def gpu_maxima(path: Path) -> dict[int, dict[str, float | int | None]]:
    result: dict[int, dict[str, float | int | None]] = {}
    if not path.is_file():
        return result
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            try:
                index = int(row["index"])
                util = float(row["utilization_pct"])
                memory = int(float(row["memory_mib"]))
            except (ValueError, TypeError, KeyError):
                continue
            current = result.setdefault(index, {"samples": 0, "max_util_pct": None,
                                                 "max_memory_mib": None})
            current["samples"] += 1
            current["max_util_pct"] = max(float(current["max_util_pct"] or 0), util)
            current["max_memory_mib"] = max(int(current["max_memory_mib"] or 0), memory)
    return result


def stage_row(stage: Path, baseline_s: float) -> dict:
    record = json.loads((stage / "stage.json").read_text(encoding="utf-8"))
    raw_log = (stage / "train.log").read_text(encoding="utf-8", errors="replace")
    times = [float(value) for value in ITERATION_TIME.findall(raw_log)]
    iterations = [int(num) for num, _ in ITERATION.findall(raw_log)]
    # The first two updates contain setup cost; no value is reported if fewer than three ran.
    measured = median(times[2:]) if len(times) >= 3 else None
    effective = (measured / (record["ranks"] * record["envs_per_rank"] / 3072)
                 if measured is not None else None)
    gpu = gpu_maxima(stage / "gpu.csv")
    private = Path(record["rank1_private"]) if record["rank1_private"] else None
    rank1_is_separate = private is None or not private.is_relative_to(Path(record["shared_run"]))
    saved = stage / "run" / f"model_{record['updates_requested']}.pt"
    checkpoint_sha = None
    if saved.is_file():
        with saved.open("rb") as stream:
            checkpoint_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    status = ("oom" if "out of memory" in raw_log.lower() or
              any("out of memory" in p.read_text(encoding="utf-8", errors="replace").lower()
                  for p in stage.glob("train.rank*.log"))
              else "complete" if (record["state"] == "exited"
                                  and all(rc == 0 for rc in record["returncodes"])
                                  and record["traceback_count"] == 0
                                  and iterations and max(iterations) >= record["updates_requested"]
                                  and rank1_is_separate
                                  and (record["ranks"] == 1
                                       or record["rank1_private_file_count"] > 0))
              else "failed")
    return {
        "stage": record["name"], "status": status, "ranks": record["ranks"],
        "envs_per_rank": record["envs_per_rank"], "total_envs": record["ranks"] * record["envs_per_rank"],
        "requested_updates": record["updates_requested"],
        "last_logged_iteration": max(iterations) if iterations else None,
        "iteration_time_samples": len(times), "median_s_excluding_first_two": measured,
        "effective_s_per_3072_env_update": effective,
        "windows_27_8_speedup": baseline_s / effective if effective else None,
        "gpu0_max_util_pct": gpu.get(0, {}).get("max_util_pct"),
        "gpu1_max_util_pct": gpu.get(1, {}).get("max_util_pct"),
        "gpu0_max_memory_mib": gpu.get(0, {}).get("max_memory_mib"),
        "gpu1_max_memory_mib": gpu.get(1, {}).get("max_memory_mib"),
        "rank1_private_path_separate": rank1_is_separate,
        "rank1_shared_path_count": record["rank1_shared_path_count"],
        "rank1_private_file_count": record["rank1_private_file_count"],
        "traceback_count": record["traceback_count"], "returncodes": record["returncodes"],
        "checkpoint_sha256": checkpoint_sha,
    }


def write_table(root: Path, source: Path | None = None) -> dict:
    source = source or Path(__file__).resolve().parents[2]
    baseline, targets = schedule_reference(source)
    rows = [stage_row(path, baseline) for path in sorted(root.iterdir())
            if path.is_dir() and (path / "stage.json").is_file()]
    if not rows:
        raise ValueError("no completed stage receipts")
    table = {"format": "ex42-m-measurement/1", "source_order": str(source / ORDER_RELATIVE),
             "windows_baseline_s": baseline, "schedule_targets": targets,
             "rows": rows,
             "limits": ["M3 effective seconds normalizes 6144 to 3072 env transitions.",
                        "Training timing is not independent W15 performance evaluation.",
                        "Rank-1 shared count is a path separation check, not per-writer tracing.",
                        "Schedule targets exclude evaluation and video GPU time."]}
    (root / "summary.json").write_text(
        json.dumps(table, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    fields = list(rows[0])
    with (root / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    md = ["# EX-42 M1~M4 속도 측정", "",
          "> 분류: CPU 집계", "> 작성: scripter-lx · 원자료 자동 생성",
          f"> 근거: `{root}` · `{source / ORDER_RELATIVE}`",
          "> 요지: rank 0 학습 로그의 첫 두 회를 빼고 회당 초 중앙값을 계산한다.",
          "> 상태: 측정 집계 · 독립 성능 판정 아님", "",
          "| 판 | 상태 | 전체 env | 초/회 | 3072 env 환산 초 | Windows 대비 | GPU0/1 최대 사용률 | 최대 메모리 MiB 0/1 | rank1 공유 경로 |",
          "|---|---|---:|---:|---:|---:|---|---|---:|"]
    for row in rows:
        def fmt(value, digits=2):
            return "미측" if value is None else f"{value:.{digits}f}"
        md.append(f"| {row['stage']} | {row['status']} | {row['total_envs']} | "
                  f"{fmt(row['median_s_excluding_first_two'])} | "
                  f"{fmt(row['effective_s_per_3072_env_update'])} | "
                  f"{fmt(row['windows_27_8_speedup'])}× | "
                  f"{fmt(row['gpu0_max_util_pct'], 0)}/{fmt(row['gpu1_max_util_pct'], 0)} | "
                  f"{fmt(row['gpu0_max_memory_mib'], 0)}/{fmt(row['gpu1_max_memory_mib'], 0)} | "
                  f"{row['rank1_shared_path_count']} |")
    md.extend(["", "## 일정 기준", "",
               "| 시작 기준 | 11/14 필요 초/회 | 11/21 필요 초/회 | 해당 속도 배수 |",
               "|---|---:|---:|---|"])
    for target in targets:
        md.append(f"| {target['start']} | {target['target_1114_s']:.1f} | "
                  f"{target['target_1121_s']:.1f} | "
                  f"{baseline / target['target_1114_s']:.2f}× / "
                  f"{baseline / target['target_1121_s']:.2f}× |")
    md.extend(["", "M4의 model_50 SHA는 summary.json에 있다. 저장본의 W15 독립 평가는 이 속도 표에서 수행하지 않는다.",
               "rank1 공유 경로 0은 별도 임시 출력 경로 계약을 확인한 값이며 파일 작성자 추적 결과는 아니다.",
               "일정 기준은 평가·영상 GPU 시간을 포함하지 않는다.", ""])
    (root / "summary.md").write_text("\n".join(md), encoding="utf-8")
    return table


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    result = write_table(args.root, args.source)
    print(json.dumps({"rows": len(result["rows"]), "summary": str(args.root / "summary.md")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
