"""Build a D74 stage-end comparison from pinned EX-40 evaluation receipts.

This is a descriptive report. Only survival differences above three of 64
are labelled as a gain or loss. Continuous metrics have no repeat band yet.
"""

from __future__ import annotations

import json
import math
import statistics
from datetime import datetime
from pathlib import Path

from foothold_s2.eval.map_mode_cells import commands
from foothold_s2.ex40_score import sha256


MODES = ("eval_gt", "probe_prop_only", "eval_pred")
FEET = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")
ERRORS = ("vx_abs_error_mean_alive_mps", "vy_abs_error_mean_alive_mps",
          "wz_abs_error_mean_alive_radps")
SURVIVAL_BAND = 3


def _number(value, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{label} missing or nonfinite")
    return float(value)


def _source(score: dict, name: str) -> tuple[dict, str]:
    source = Path(score["sources"][name])
    if not source.is_file():
        raise ValueError(f"stage report source missing: {name}")
    row = json.loads(source.read_text(encoding="utf-8-sig"))
    if row.get("checkpoint_sha256") != score["checkpoint_sha256"] or row.get("envs") != 64:
        raise ValueError(f"stage report source checkpoint or env count differs: {name}")
    return row, sha256(source)


def _median(values, label: str) -> float:
    if not values:
        raise ValueError(f"{label} has no samples")
    return statistics.median(_number(value, label) for value in values)


def snapshot(score: dict) -> dict:
    """Use all 13 commands in all three modes, regardless of stage judge subset."""
    map_row, map_sha = _source(score, "map64")
    axis, axis_sha = _source(score, "axis_v2")
    expected = set(commands("extended"))
    if set(map_row.get("modes", {})) != set(MODES) or len(expected) != 13:
        raise ValueError("stage report needs W15 13 commands and three map modes")
    if set(axis.get("modes", {})) != set(MODES):
        raise ValueError("stage report needs W57 three modes")
    w15, w57, stand, source_sha = {}, {}, {}, {"map64": map_sha, "axis_v2": axis_sha}
    for mode in MODES:
        cases = map_row["modes"][mode]
        if not expected <= set(cases):
            raise ValueError("stage report W15 command missing")
        for name in sorted(expected):
            case = cases[name]
            alive = case.get("alive_envs_at_end")
            rows = case.get("per_env", [])
            if type(alive) is not int or not 0 <= alive <= 64 or len(rows) != 64:
                raise ValueError("stage report W15 survival or per-env rows missing")
            values = {}
            for field in ERRORS:
                alive_values = [row[field] for row in rows if row.get("samples_alive", 0) > 0]
                values[field] = _median(alive_values, field) if alive_values else None
            w15[f"{mode}/{name}"] = {"alive_envs_at_end": alive, "tracking_medians": values}
        stand_row, stand_sha = _source(score, f"stand_{mode}")
        source_sha[f"stand_{mode}"] = stand_sha
        rows = stand_row.get("per_env", [])
        if len(rows) != 64:
            raise ValueError("stage report stance env rows missing")
        foot_row = {}
        for foot in FEET:
            foot_row[foot] = {field: _median([row["feet"][foot][field] for row in rows], field)
                              for field in ("contact_fraction_gt1n", "mean_fz_over_mg", "sole_gap_p95_m")}
        lateral = [abs((row["feet"]["FL_foot"]["contact_fraction_gt1n"]
                        + row["feet"]["RL_foot"]["contact_fraction_gt1n"]
                        - row["feet"]["FR_foot"]["contact_fraction_gt1n"]
                        - row["feet"]["RR_foot"]["contact_fraction_gt1n"]) / 2) for row in rows]
        stand[mode] = {"feet": foot_row, "contact_left_right_gap_median": _median(lateral, "stand symmetry")}
        for name, case in axis["modes"][mode].items():
            alive = case.get("alive_at_end")
            if type(alive) is not int or not 0 <= alive <= 64:
                raise ValueError("stage report W57 survival missing")
            w57[f"{mode}/{name}"] = {"alive_at_end": alive,
                "stop_end_error_median_rad": case.get("stop_end_error_median_rad"),
                "yaw_final_minus_start_median_rad": case.get("yaw_final_minus_start_median_rad"),
                "contact_left_right_gap_median": case.get("contact_left_right_gap_median")}
            for field, value in w57[f"{mode}/{name}"].items():
                if value is not None:
                    _number(value, field)
    return {"w15": w15, "w57": w57, "stand": stand, "source_sha256": source_sha}


def dr_readback(run: Path, update: int) -> dict:
    """Read only the Kit train_extra row for this exact numbered checkpoint."""
    path = run / "train_extra.jsonl"
    if not path.is_file():
        return {"state": "미측", "reason": "train_extra.jsonl 없음"}
    found = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        row = json.loads(line)
        if row.get("it") == update and isinstance(row.get("ex40_dr"), dict):
            found.append(row["ex40_dr"])
    if len(found) != 1 or found[0].get("update") != update:
        return {"state": "미측", "reason": "해당 회차 DR 실현 기록 없음 또는 중복"}
    row = found[0]
    scale = _number(row.get("scale"), "DR scale")
    samples = row.get("actual_samples", {})
    if not isinstance(samples, dict):
        raise ValueError("DR actual samples malformed")
    realized = {}
    for name, values in samples.items():
        if type(values.get("count")) is not int or values["count"] < 1:
            raise ValueError("DR actual sample count invalid")
        realized[name] = {key: _number(values.get(key), f"DR {name} {key}")
                          for key in ("min", "max", "mean")}
        realized[name]["count"] = values["count"]
    return {"state": "측정", "scale": scale, "actual_samples": realized,
            "delay_readback": row.get("delay_readback"), "pending_values": row.get("pending_values", []),
            "source": str(path), "source_sha256": sha256(path)}


def _delta(current: dict, previous: dict | None) -> tuple[list[dict], list[dict], list[dict]]:
    if previous is None:
        return [], [], []
    gains, losses, unchanged = [], [], []
    for section, field in (("w15", "alive_envs_at_end"), ("w57", "alive_at_end")):
        for name, current_row in current[section].items():
            old_row = previous[section].get(name)
            if old_row is None:
                continue
            diff = current_row[field] - old_row[field]
            item = {"cell": f"{section}/{name}", "before": old_row[field],
                    "after": current_row[field], "delta": diff, "repeat_band_envs": SURVIVAL_BAND}
            (gains if diff > SURVIVAL_BAND else losses if diff < -SURVIVAL_BAND else unchanged).append(item)
    return gains, losses, unchanged


def build(current_score: dict, previous_score: dict | None, run: Path, *,
          previous_run: Path | None = None) -> dict:
    current = snapshot(current_score)
    previous = snapshot(previous_score) if previous_score is not None else None
    gains, losses, unchanged = _delta(current, previous)
    update = current_score["checkpoint_iteration"]
    return {"format": "foothold-ex40-stage-report/1", "stage": current_score["from"],
            "checkpoint_iteration": update, "checkpoint_sha256": current_score["checkpoint_sha256"],
            "previous_stage": previous_score["from"] if previous_score else None,
            "previous_checkpoint_iteration": previous_score["checkpoint_iteration"] if previous_score else None,
            "current": current, "previous": previous, "dr_current": dr_readback(run, update),
            "dr_previous": (dr_readback(previous_run or run, previous_score["checkpoint_iteration"])
                            if previous_score else None),
            "gains": gains, "losses": losses, "unchanged": unchanged,
            "caution": "생존 ±3/64 이내는 차이 없음. 연속값 반복 폭은 미측정이므로 판정하지 않음."}


def markdown(row: dict) -> str:
    stage, update = row["stage"], row["checkpoint_iteration"]
    lines = [f"# EX-40 {stage} m{update} 단계 끝 비교", "",
             "> 분류: 실험 평가", f"> 작성: scripter · {datetime.now().astimezone():%Y-%m-%d}",
             "> 근거: EX-40 평가 원자료 · 점수 원장 · D74",
             "> 요지: 단계 끝과 앞 단계 끝을 같은 평가 칸에서 대조",
             "> 상태: 자동 생성 · 반복 폭 제한", "",
             f"앞 단계: {row['previous_stage'] or '없음'} · "
             f"m{row['previous_checkpoint_iteration'] if row['previous_checkpoint_iteration'] is not None else '없음'}", ""]
    for title, key in (("얻은 점", "gains"), ("잃은 점", "losses")):
        lines += [f"## {title}", ""]
        lines += [f"- {item['cell']}: {item['before']} → {item['after']} ({item['delta']:+d}/64)"
                  for item in row[key]] or ["- 생존 차이가 반복 폭 ±3/64를 넘는 칸 없음"]
        lines.append("")
    current, previous = row["current"], row["previous"]
    lines += ["## W15 13×3", "", "| 칸 | 생존 전→후 | 생존 변화 | vx/vy/wz 오차 전→후 |",
              "|---|---:|---:|---|"]
    for name, after in current["w15"].items():
        before = previous["w15"].get(name) if previous else None
        old_survival = before["alive_envs_at_end"] if before else None
        diff = after["alive_envs_at_end"] - old_survival if old_survival is not None else None
        label = ("미측" if diff is None else "차이 없음" if abs(diff) <= SURVIVAL_BAND
                 else f"{diff:+d}/64")
        errors = ", ".join(
            f"{before['tracking_medians'].get(field) if before else '미측'}→"
            f"{after['tracking_medians'].get(field)}" for field in ERRORS)
        lines.append(f"| {name} | {old_survival if old_survival is not None else '미측'}→"
                     f"{after['alive_envs_at_end']} | {label} | {errors} |")
    lines += ["", "## W57 · 방향과 접촉 대칭", "",
              "| 칸 | 생존 전→후 | 생존 변화 | 목표 정지 오차 전→후 rad | 좌우 접촉 차 전→후 |",
              "|---|---:|---:|---:|---:|"]
    for name, after in current["w57"].items():
        before = previous["w57"].get(name) if previous else None
        old_survival = before["alive_at_end"] if before else None
        diff = after["alive_at_end"] - old_survival if old_survival is not None else None
        label = ("미측" if diff is None else "차이 없음" if abs(diff) <= SURVIVAL_BAND
                 else f"{diff:+d}/64")
        old_error = before.get("stop_end_error_median_rad") if before else "미측"
        old_symmetry = before.get("contact_left_right_gap_median") if before else "미측"
        lines.append(f"| {name} | {old_survival if old_survival is not None else '미측'}→"
                     f"{after['alive_at_end']} | {label} | {old_error}→"
                     f"{after['stop_end_error_median_rad']} | {old_symmetry}→"
                     f"{after['contact_left_right_gap_median']} |")
    lines += ["", "## 정지 발별 간격 · 하중", "",
              "| 모드 · 발 | 간격 p95 중앙값 전→후 m | 하중 중앙값 전→후 mg비 | 접촉률 전→후 |",
              "|---|---:|---:|---:|"]
    for mode in MODES:
        for foot in FEET:
            after = current["stand"][mode]["feet"][foot]
            before = previous["stand"][mode]["feet"][foot] if previous else {}
            lines.append(f"| {mode}/{foot} | {before.get('sole_gap_p95_m', '미측')}→"
                         f"{after['sole_gap_p95_m']} | {before.get('mean_fz_over_mg', '미측')}→"
                         f"{after['mean_fz_over_mg']} | {before.get('contact_fraction_gt1n', '미측')}→"
                         f"{after['contact_fraction_gt1n']} |")
    lines += ["", "## DR 배율 · 실현 범위", "",
              "| 항목 | 앞 단계 | 현재 단계 |", "|---|---|---|"]
    before_dr, after_dr = row["dr_previous"] or {}, row["dr_current"]
    lines.append(f"| 배율 | {before_dr.get('scale', '미측')} | {after_dr.get('scale', '미측')} |")
    keys = set(before_dr.get("actual_samples", {})) | set(after_dr.get("actual_samples", {}))
    for name in sorted(keys):
        def span(source):
            sample = source.get("actual_samples", {}).get(name)
            return f"{sample['min']}~{sample['max']} (n={sample['count']})" if sample else "미측"
        lines.append(f"| {name} | {span(before_dr)} | {span(after_dr)} |")
    lines += ["", "## 다음 단계 주의", "", f"- {row['caution']}",
              f"- DR 현재: {row['dr_current']['state']}.",
              "- GT · 복원 · 가림 모드는 따로 기록하며 평균으로 합치지 않음.", ""]
    return "\n".join(lines)
