"""CPU-only EX-40 checkpoint summaries from the immutable score ledger.

This consumer never changes training, scoring, or evaluation artifacts. A
dedicated documentation worktree is required for publication.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import time
from contextlib import contextmanager

from foothold_s2.ex40_score import sha256
from foothold_s2.ex40_stage_publish import (
    BRANCH, GITHUB, STAGE_DIR, _run, _send, _sync_remote, _validate_repo,
)


MODES = ("eval_gt", "probe_prop_only", "eval_pred")
CASES = ("fwd0.5", "fwd1.0", "spin+1.2", "spin-1.2", "stop")
FEET = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")
BAND = 3
STAGE_END = {1500, 3000, 4500, 5000, 5500, 6000, 7500, 8000}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True,
                               allow_nan=False) + "\n", encoding="utf-8")
    for attempt in range(200):
        try:
            os.replace(temp, path)
            return
        except PermissionError:
            if attempt == 199:
                raise
            time.sleep(.01)


def _finite(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f"{label} is absent or nonfinite")
    return float(value)


def ledger_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()]
    updates = [row.get("checkpoint_iteration") for row in rows]
    if len(updates) != len(set(updates)) or updates != sorted(updates):
        raise ValueError("duplicate or unordered score ledger update")
    for row in rows:
        if row.get("format") != "foothold-ex40-score-ledger/1":
            raise ValueError("score ledger format mismatch")
    return rows


def pinned_score(ledger: dict) -> dict:
    score_path = Path(ledger["score_path"])
    checkpoint = Path(ledger["checkpoint_path"])
    if not score_path.is_file() or sha256(score_path) != ledger["score_sha256"]:
        raise ValueError("score file absent or SHA mismatch")
    if not checkpoint.is_file() or sha256(checkpoint) != ledger["checkpoint_sha256"]:
        raise ValueError("checkpoint absent or SHA mismatch")
    score = _read_json(score_path)
    if (score.get("checkpoint_iteration") != ledger["checkpoint_iteration"]
            or score.get("checkpoint_sha256") != ledger["checkpoint_sha256"]
            or score.get("from") != ledger["stage"]
            or score.get("verdict") != ledger["verdict"]):
        raise ValueError("score and ledger identity mismatch")
    for name, source in score["sources"].items():
        row = _read_json(Path(source))
        if row.get("checkpoint_sha256") != ledger["checkpoint_sha256"]:
            raise ValueError(f"source checkpoint mismatch: {name}")
    return score


def _extra(run: Path, update: int) -> dict:
    found = []
    for line in (run / "train_extra.jsonl").read_text(encoding="utf-8-sig").splitlines():
        row = json.loads(line)
        if row.get("it") == update:
            found.append(row)
    if len(found) != 1:
        raise ValueError("exact train_extra update missing or duplicated")
    return found[0]


def _training(run: Path, update: int, final: int, *, include_curves: bool) -> dict:
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

    paths = sorted(run.glob("events.out.tfevents.*"))
    if len(paths) != 1:
        raise ValueError("training TensorBoard file absent or ambiguous")
    accumulator = EventAccumulator(str(paths[0]), size_guidance={"scalars": 0})
    accumulator.Reload()
    tags = set(accumulator.Tags()["scalars"])
    required = ("Train/mean_reward", "Train/mean_episode_length")
    if not set(required) <= tags:
        raise ValueError("required training scalar missing")
    reward = [event for event in accumulator.Scalars(required[0]) if event.step <= update]
    episode = [event for event in accumulator.Scalars(required[1]) if event.step <= update]
    if not reward or reward[-1].step != update or not episode:
        raise ValueError("checkpoint has no matching reward event")
    recent = reward[max(0, len(reward) - 26):]
    if len(recent) < 2 or recent[-1].step == recent[0].step:
        raise ValueError("not enough training samples for rate")
    seconds_per_update = (recent[-1].wall_time - recent[0].wall_time) / (
        recent[-1].step - recent[0].step)
    if seconds_per_update <= 0:
        raise ValueError("nonpositive training rate")
    end_time = datetime.fromtimestamp(reward[-1].wall_time).astimezone()
    first_time = datetime.fromtimestamp(reward[0].wall_time).astimezone()
    eta = end_time + timedelta(seconds=max(0, final - update) * seconds_per_update)
    curves = {}
    if include_curves:
        for tag in sorted(tags):
            if tag.startswith("Episode_Reward/") or tag in required:
                curves[tag] = [[event.step, _finite(event.value, tag)] for event in
                               accumulator.Scalars(tag) if event.step <= update]
    return {"at": end_time.isoformat(), "elapsed_s": (end_time - first_time).total_seconds(),
            "seconds_per_update": seconds_per_update, "eta": eta.isoformat(),
            "reward": _finite(reward[-1].value, "reward"),
            "episode_length": _finite(episode[-1].value, "episode_length"),
            "curves": curves, "event_source": str(paths[0]),
            "checkpoint_event_values_sha256": hashlib.sha256(json.dumps({
                tag: [(event.step, event.wall_time, event.value) for event in
                      accumulator.Scalars(tag) if event.step <= update]
                for tag in required}, sort_keys=True).encode("utf-8")).hexdigest()}


def _median(rows: list[dict], field: str) -> float | None:
    values = [_finite(row[field], field) for row in rows if row.get("samples_alive", 0) > 0]
    return statistics.median(values) if values else None


def _map_cells(score: dict) -> tuple[dict, dict]:
    import numpy as np

    source = Path(score["sources"]["map64"])
    raw = _read_json(source)
    if set(raw.get("modes", {})) != set(MODES) or raw.get("envs") != 64:
        raise ValueError("map64 mode or env count mismatch")
    cells, map_error = {}, {}
    for mode in MODES:
        if not set(CASES) <= set(raw["modes"][mode]):
            raise ValueError(f"map64 command missing for {mode}")
        names = list(CASES) + sorted(n for n, v in raw["modes"][mode].items()
                                     if n not in CASES and isinstance(v, dict) and "per_env" in v
                                     and "alive_envs_at_end" in v)
        for name in names:
            case = raw["modes"][mode][name]
            rows = case["per_env"]
            if len(rows) != 64:
                raise ValueError("map64 per-env rows missing")
            errors = {field: _median(rows, field) for field in (
                "vx_abs_error_mean_alive_mps", "vy_abs_error_mean_alive_mps",
                "wz_abs_error_mean_alive_radps")}
            npz_path = source.parent / f"env_arrays_{mode}_{name}.npz"
            with np.load(npz_path, allow_pickle=False) as arr:
                alive = arr["alive_end"]
                if len(alive) != 64 or int(alive.sum()) != case["alive_envs_at_end"]:
                    raise ValueError("map64 survival JSON/NPZ mismatch")
                values = arr["map_err_inrange_mean_cm"]
                steps = arr["map_err_inrange_steps"]
                if len(values) != 64 or len(steps) != 64:
                    raise ValueError("map error env count mismatch")
                finite = np.isfinite(values) & (steps > 0)
                map_error[f"{mode}/{name}"] = {
                    "mean_of_env_means_cm": float(values[finite].mean()) if finite.any() else None,
                    "env_count": int(finite.sum()), "npz_sha256": sha256(npz_path)}
            cells[f"{mode}/{name}"] = {"alive": case["alive_envs_at_end"],
                                          "tracking_median": errors}
    return cells, map_error


def _stand(score: dict) -> dict:
    import numpy as np

    result = {}
    for mode in MODES:
        path = Path(score["sources"][f"stand_{mode}"])
        row = _read_json(path)
        if row.get("envs") != 64 or len(row["per_env"]) != 64:
            raise ValueError("stand env count mismatch")
        feet = {}
        for foot in FEET:
            feet[foot] = {key: statistics.median(
                _finite(env["feet"][foot][key], f"{foot}/{key}") for env in row["per_env"])
                for key in ("contact_fraction_gt1n", "mean_fz_over_mg", "sole_gap_p95_m")}
        with np.load(path.parent / "stand_raw.npz", allow_pickle=False) as raw:
            force = raw["force_z"]
            alive = raw["alive"]
            skip = round(float(row["skip_seconds"]) / float(row["dt"]))
            if force.shape != (150, 64, 4) or alive.shape != (150, 64):
                raise ValueError("stand raw shape mismatch")
            sampled = alive[skip:]
            simultaneous = ((force[skip:] > 1.0).all(axis=2) & sampled)
            denominators = sampled.sum(axis=0)
            sufficient = (denominators > 0) & (simultaneous.sum(axis=0) >= .9 * denominators)
            all_four = int(sufficient.sum())
        result[mode] = {"feet": feet, "all_four_90pct_envs": all_four,
                        "stand_sha256": sha256(path),
                        "raw_sha256": sha256(path.parent / "stand_raw.npz")}
    return result


def build_row(ledger: dict, score: dict, previous: dict | None, final: int) -> dict:
    update = ledger["checkpoint_iteration"]
    run = Path(ledger["run_dir"])
    extra = _extra(run, update)
    cells, map_error = _map_cells(score)
    deltas = []
    if previous is not None:
        for name, current in cells.items():
            if name not in previous["cells"]:
                continue
            before = previous["cells"][name]["alive"]
            delta = current["alive"] - before
            if abs(delta) > BAND:
                deltas.append({"cell": name, "before": before, "after": current["alive"],
                               "delta": delta})
    import yaml

    config_path = run / "params" / "env.yaml"
    config = yaml.load(config_path.read_text(encoding="utf-8-sig"), Loader=yaml.BaseLoader)
    weights = {name: _finite(float(term["weight"]), f"reward {name}")
               for name, term in config["rewards"].items()}
    stand_passed = {}
    for mode in MODES:
        key = f"{mode}/flat_stand" + ("_record_only" if mode == "eval_pred" else "")
        if key not in score["cells"]:
            raise ValueError("flat stand score missing")
        stand_passed[mode] = score["cells"][key]["passed_envs"]
    return {"format": "foothold-ex40-checkpoint-report/1", "update": update,
            "stage": ledger["stage"], "verdict": ledger["verdict"],
            "problems": score.get("problems", []),
            "score_created_at": score["created_at"],
            "checkpoint_sha256": ledger["checkpoint_sha256"],
            "score_sha256": ledger["score_sha256"],
            "training": _training(run, update, final, include_curves=update in STAGE_END),
            "command_slots": extra["command_slots"], "dr": extra["ex40_dr"],
            "cells": cells, "map_error": map_error, "stand": _stand(score),
            "judged": sorted(k.split("/", 1)[1] for k in score["cells"]
                             if k.startswith("eval_gt/") and "flat_stand" not in k),
            "stand_passed": stand_passed, "initial_reward_weights": weights,
            "changed_cells_over_band": deltas,
            "previous_update": previous["update"] if previous else None,
            "sources": {"run": str(run), "score": ledger["score_path"],
                        "map64": score["sources"]["map64"],
                        "map64_sha256": sha256(Path(score["sources"]["map64"])),
                        "env_yaml_sha256": sha256(config_path)}}


def problem_text(row: dict) -> str:
    """lead 11/01: HOLD · FAIL 의 이유를 채점기 원문 그대로(칸 · 이유)."""
    return " · ".join(f"{p.get('kind')} {p.get('cell')}: {p.get('reason')}" for p in row.get("problems", []))


def insights(row: dict) -> list[str]:
    """lead 10/31 D79: 의미 있는 점 2~4 줄. 기준은 그림자 판정과 같은 값(생존 60/64, 오차 0.15)."""
    out, below = [], []
    for mode in ("eval_gt", "probe_prop_only"):
        for name in row.get("judged") or CASES:
            if f"{mode}/{name}" not in row["cells"]:
                continue
            cell = row["cells"][f"{mode}/{name}"]
            errs = [v for v in cell["tracking_median"].values() if v is not None]
            worst = max(errs) if errs else None
            if cell["alive"] < 60 or (worst is not None and worst > 0.15):
                tag = "정답" if mode == "eval_gt" else "끔"
                below.append(f"{name}({tag} 생존 {cell['alive']}" + (f", 오차 {worst:.3f}" if worst is not None else "") + ")")
    out.append("미달 칸: " + (", ".join(below) if below else "없음 (생존 ≥60 · 오차 ≤0.15)"))
    changed = row["changed_cells_over_band"]
    out.append("앞 저장본 대비 생존 변화(±3 초과): " + (", ".join(
        f"{x['cell']} {x['before']}→{x['after']}" for x in changed) or "없음"))
    feet = row["stand"]["eval_gt"]["feet"]
    low = min(FEET, key=lambda f: feet[f]["mean_fz_over_mg"])
    out.append(f"서 있기: 네 발 동시 접촉 {row['stand']['eval_gt']['all_four_90pct_envs']}/64, 가장 약한 발 {low} "
               f"{feet[low]['mean_fz_over_mg']:.2f} mg (RR {feet['RR_foot' if 'RR_foot' in feet else 'RR']['mean_fz_over_mg']:.2f})")
    left, right = (row["cells"][f"eval_gt/spin{s}1.2"]["tracking_median"]["wz_abs_error_mean_alive_radps"] for s in ("+", "-"))
    if left is not None and right is not None:
        out.append(f"좌우 회전 오차 {left:.3f}/{right:.3f} (차 {right - left:+.3f}, +면 오른쪽이 약함)")
    return out


def markdown(row: dict, *, stage_doc: str | None = None, video: str | None = None,
             charts: list[str] | None = None) -> str:
    update, train = row["update"], row["training"]
    stage_end = update in STAGE_END
    lines = [f"# EX-40 {row['stage']} m{update} {'단계 끝' if stage_end else '저장본'} 진행 보고", "",
             "> 분류: 실험 평가", f"> 작성: scripter · {datetime.now().astimezone():%Y-%m-%d}",
             "> 근거: EX-40 점수 원장 · 평가 원자료 · TensorBoard · train_extra",
             "> 요지: 저장본 평가와 학습 진행을 원자료에서 기록",
             "> 상태: 자동 생성 · 그림자 판정 · 독립 평가", "",
             "## 핵심", ""] + [f"- {line}" for line in insights(row)] + ["",
             f"- 완료: m{update}, 학습 기록 {train['at']}, 점수 {row['score_created_at']}",
             f"- 경과 {train['elapsed_s'] / 3600:.2f} h, 최근 {train['seconds_per_update']:.2f} s/update, 예상 끝 {train['eta']}",
             f"- 단계 {row['stage']}, 그림자 판정 {row['verdict']}, 앞 저장본 m{row['previous_update'] or '없음'}",
             *([f"- 판정 이유: {problem_text(row)}"] if row.get("problems") else []),
             f"- 학습 보상 {train['reward']:.4f}, 에피소드 길이 {train['episode_length']:.2f}", "",
             "## 설정과 실현", "",
             "- 명령 비율 (학습 실현): " + ", ".join(
                 f"{name} {value:.3f}" for name, value in row["command_slots"]["frac"].items() if value),
             "- 보상 시작 가중: " + ", ".join(
                 f"{name} {value:g}" for name, value in row["initial_reward_weights"].items()),
             "- 이 가중치는 저장된 시작 cfg 기준이다. 단계 중 변경은 별도 단계 보고와 대조한다.",
             f"- DR 배율 {row['dr']['scale']}; 실제 표본: " + ", ".join(
                 f"{name} {sample['min']}~{sample['max']} (n={sample['count']})"
                 for name, sample in row["dr"].get("actual_samples", {}).items()), "",
             "## 평가 칸 × 지도 3모드 (그림자 판정 대상은 단계에서 배운 칸)", "",
             "| 모드/칸 | 생존 /64 | vx 오차 m/s | vy 오차 m/s | wz 오차 rad/s | 복원 지도 cm (env 수) |",
             "|---|---:|---:|---:|---:|---:|"]
    for mode in MODES:
        for name in [k.split("/", 1)[1] for k in row["cells"] if k.startswith(mode + "/")]:
            key = f"{mode}/{name}"
            cell, err = row["cells"][key], row["map_error"][key]
            values = cell["tracking_median"]
            fmt = lambda value: "미측" if value is None else f"{value:.3f}"
            lines.append(f"| {key} | {cell['alive']} | {fmt(values['vx_abs_error_mean_alive_mps'])} | "
                         f"{fmt(values['vy_abs_error_mean_alive_mps'])} | "
                         f"{fmt(values['wz_abs_error_mean_alive_radps'])} | "
                         f"{fmt(err['mean_of_env_means_cm'])} ({err['env_count']}) |")
        key = f"{mode}/flat_stand"
        lines.append(f"| {key} | {row['stand_passed'][mode]}/64 (정지 통과) | 미측 | 미측 | 미측 | 미측 |")
    lines += ["", "복원 지도 값은 NPZ의 `map_err_inrange_mean_cm` 유한 env 평균이다. GT의 0도 별도 기록하며 모드를 합치지 않는다.",
              "", "## 서 있기 네 발", "",
              "| 모드/발 | 접촉률 중앙값 | 수직 하중 중앙값 /mg | 간격 p95 중앙값 mm |",
              "|---|---:|---:|---:|"]
    for mode in MODES:
        for foot in FEET:
            vals = row["stand"][mode]["feet"][foot]
            lines.append(f"| {mode}/{foot} | {vals['contact_fraction_gt1n']:.3f} | "
                         f"{vals['mean_fz_over_mg']:.3f} | {vals['sole_gap_p95_m'] * 1000:.2f} |")
        lines.append(f"| {mode}/네 발 동시 접촉 ≥90% env | {row['stand'][mode]['all_four_90pct_envs']}/64 |  |  |")
    lines += ["", "## 변화와 좌우", ""]
    changed = row["changed_cells_over_band"]
    lines += [f"- {item['cell']}: {item['before']}→{item['after']} ({item['delta']:+d}/64)"
              for item in changed] or ["- 생존 차이 ±3/64를 넘는 칸 없음. 이 범위는 차이 없음으로 표시한다."]
    for mode in MODES:
        left, right = (row["cells"][f"{mode}/spin{sign}1.2"] for sign in ("+", "-"))
        lines.append(f"- {mode} 회전 좌/우 생존 {left['alive']}/{right['alive']}/64; "
                     f"요속도 오차 {left['tracking_median']['wz_abs_error_mean_alive_radps']:.3f}/"
                     f"{right['tracking_median']['wz_abs_error_mean_alive_radps']:.3f} rad/s.")
    lines += ["- 전진 yaw 누적: 미측 (이 평가 NPZ에 yaw 시계열 없음).", ""]
    if stage_end:
        lines += ["## 단계 끝 전체 보고", "",
                  f"- W15 13×3, W57, DR, 단계별 그림: {stage_doc or '점수기 단계 보고 대기'}",
                  f"- CMP 영상: {video or '미촬영 · EX-40 설정과 전 프레임 검증 영수증 대기'}", ""]
        if charts:
            lines += ["### 이 저장본의 학습 · 평가 그림", ""]
            lines += [f"![{name}]({name})" for name in charts]
            lines.append("")
    lines += ["## 출처", "", f"- 저장본 SHA256 `{row['checkpoint_sha256']}`",
              f"- 점수 SHA256 `{row['score_sha256']}`",
              f"- 평가 원자료: `{row['sources']['map64']}`", ""]
    result = "\n".join(lines)
    if "\u2014" in result:
        raise ValueError("em dash in report")
    return result


def _telegram(row: dict, link: str, local: Path, push_error: str | None = None,
              stage_doc: str | None = None, video: str | None = None) -> str:
    train = row["training"]
    changed = row["changed_cells_over_band"]
    change = ", ".join(f"{x['cell']} {x['delta']:+d}" for x in changed[:3]) or "변화 없음"
    stand = row["stand"]["eval_pred"]["all_four_90pct_envs"]
    gt_left = row["cells"]["eval_gt/spin+1.2"]["alive"]
    gt_right = row["cells"]["eval_gt/spin-1.2"]["alive"]
    lines = [f"EX-40 m{row['update']} · {row['stage']} · 그림자 {row['verdict']}",
             *(["판정 이유: " + problem_text(row)] if row.get("problems") else []),
             f"속도 {train['seconds_per_update']:.1f}s/회 · 예상 끝 {train['eta']}",
             f"변한 칸(±3 초과): {change}",
             f"서 있기 네 발 {stand}/64 · GT 좌/우 회전 생존 {gt_left}/{gt_right}/64",
             *insights(row)[:3],
             (f"push 실패 · 로컬: {local}" if push_error else
              f"보고: {link} · 로컬: {local}")]
    if stage_doc:
        lines[3] += f" · 단계 전체: {stage_doc} · CMP: {video or '대기'}"
    return "\n".join(lines) + "\n"


def _video_receipt(directory: Path | None, row: dict,
                   request: dict | None = None) -> str | None:
    """Accept only a completed EX-40 GPU1 CMP with full frame readback."""
    if directory is None:
        return None
    path = directory / f"m{row['update']}.cmp.json"
    if not path.exists():
        return None
    receipt = _read_json(path)
    if (receipt.get("format") != "foothold-ex40-cmp/1"
            or receipt.get("checkpoint_sha256") != row["checkpoint_sha256"]
            or (request is not None and receipt.get("previous_stage_sha256") !=
                request["previous_stage_sha256"])
            or receipt.get("gpu_index") != 1
            or receipt.get("status") != "PASS"):
        raise ValueError("CMP receipt identity or status mismatch")
    count = receipt.get("frame_count")
    if type(count) is not int or count <= 0 or receipt.get("decoded_frames") != count:
        raise ValueError("CMP frame readback incomplete")
    video = Path(receipt["mp4"])
    if not video.is_file() or sha256(video) != receipt.get("mp4_sha256"):
        raise ValueError("CMP file absent or SHA mismatch")
    import cv2

    capture = cv2.VideoCapture(str(video))
    decoded = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            decoded += 1
            if not math.isfinite(float(frame.mean())) or float(frame.mean()) <= 10:
                raise ValueError(f"CMP dark or invalid frame {decoded}")
    finally:
        capture.release()
    if decoded != count:
        raise ValueError("CMP decoded file frame count differs from receipt")
    return str(video)


def _cmp_request(state_dir: Path, row: dict, ledger: list[dict]) -> Path:
    """Record the GPU1 handoff; this CPU consumer never starts a renderer."""
    update = row["update"]
    path = state_dir / f"m{update}.cmp.request.json"
    earlier = [entry for entry in ledger if entry["checkpoint_iteration"] in STAGE_END
               and entry["checkpoint_iteration"] < update]
    previous = earlier[-1] if earlier else None
    initial = Path(row["sources"]["run"]) / "model_0.pt"
    previous_path = previous["checkpoint_path"] if previous else str(initial) if initial.is_file() else None
    previous_sha = previous["checkpoint_sha256"] if previous else sha256(initial) if initial.is_file() else None
    request = {"format": "foothold-ex40-cmp-request/1", "update": update,
               "checkpoint_sha256": row["checkpoint_sha256"],
               "checkpoint": str(Path(row["sources"]["run"]) / f"model_{update}.pt"),
               "previous_stage_checkpoint": previous_path,
               "previous_stage_sha256": previous_sha,
               "previous_label": f"m{previous['checkpoint_iteration']}" if previous else "m0 initial",
               "gpu_index": 1, "requires_score_gpu1_idle": True,
               "required_receipt": "foothold-ex40-cmp/1, full decoded frame count, MP4 SHA",
               "state": "pending_validated_EX40_recorder"}
    if path.exists() and _read_json(path) != request:
        raise ValueError("CMP request changed for a pinned checkpoint")
    if not path.exists():
        _write_json(path, request)
    return path


def _stage_charts(state_dir: Path, current: dict, folder: Path, stem: str) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    history = []
    for path in state_dir.glob("m*.row.json"):
        prior = _read_json(path)
        if prior["update"] <= current["update"]:
            history.append(prior)
    history.sort(key=lambda item: item["update"])
    if not history or history[-1]["checkpoint_sha256"] != current["checkpoint_sha256"]:
        raise ValueError("stage chart history lacks current checkpoint")
    if len({item["update"] for item in history}) != len(history):
        raise ValueError("stage chart history has duplicate update")

    output = []
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), constrained_layout=True)
    curves = current["training"]["curves"]
    for tag in ("Train/mean_reward", "Train/mean_episode_length"):
        values = curves.get(tag)
        if not values:
            raise ValueError(f"missing stage training curve {tag}")
        ax = axes[0 if tag == "Train/mean_reward" else 1]
        ax.plot([point[0] for point in values], [point[1] for point in values])
        ax.set(xlabel="update", ylabel=tag)
    path = folder / f"{stem}_training.png"
    fig.savefig(path, dpi=150, metadata={"Software": "EX-40 checkpoint reporter"})
    plt.close(fig)
    output.append(path)

    reward_tags = [tag for tag in curves if tag.startswith("Episode_Reward/")]
    if not reward_tags:
        raise ValueError("no reward term curves")
    fig, ax = plt.subplots(figsize=(11, 7))
    for tag in reward_tags:
        values = curves[tag]
        if values:
            ax.plot([point[0] for point in values], [point[1] for point in values],
                    label=tag.split("/", 1)[1], linewidth=.8)
    ax.set(xlabel="update", ylabel="logged episode reward term", title="Reward terms")
    ax.legend(fontsize=7, ncol=3)
    path = folder / f"{stem}_reward_terms.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", metadata={"Software": "EX-40 checkpoint reporter"})
    plt.close(fig)
    output.append(path)

    ticks = [item["update"] for item in history]
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), constrained_layout=True)
    for mode in MODES:
        for cell in ("fwd0.5", "fwd1.0", "spin+1.2", "spin-1.2", "stop"):
            key = f"{mode}/{cell}"
            axes[0].plot(ticks, [item["cells"][key]["alive"] for item in history],
                         label=key, linewidth=.8)
        key = f"{mode}/fwd1.0"
        values = [item["map_error"][key]["mean_of_env_means_cm"] for item in history]
        axes[1].plot(ticks, [np.nan if val is None else val for val in values],
                     label=mode)
    axes[0].set(xlabel="update", ylabel="survivors /64")
    axes[0].legend(fontsize=6, ncol=3)
    axes[1].set(xlabel="update", ylabel="map error cm (mean of finite env means)")
    axes[1].legend()
    path = folder / f"{stem}_evaluation.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", metadata={"Software": "EX-40 checkpoint reporter"})
    plt.close(fig)
    output.append(path)

    fig, ax = plt.subplots(figsize=(10, 5))
    for foot in FEET:
        ax.plot(ticks, [item["stand"]["eval_pred"]["feet"][foot]["mean_fz_over_mg"]
                        for item in history], marker="o", label=foot)
    ax.set(xlabel="update", ylabel="median normal load /mg", title="Stand foot load")
    ax.legend()
    path = folder / f"{stem}_foot_load.png"
    fig.savefig(path, dpi=150, metadata={"Software": "EX-40 checkpoint reporter"})
    plt.close(fig)
    output.append(path)
    return output


def publish(row: dict, repo: Path, state_dir: Path, telegram_sender: Path,
            *, sender=None, dry_run: bool = False, stage_doc: str | None = None,
            video: str | None = None) -> dict:
    update = row["update"]
    receipt = state_dir / f"m{update}.report.json"
    if receipt.exists():
        old = _read_json(receipt)
        if old["checkpoint_sha256"] != row["checkpoint_sha256"]:
            raise ValueError("existing report has different checkpoint")
        if old["state"] in ("sent", "delivery_uncertain", "delivery_pending"):
            return old
    stem = f"PROGRESS-EX40-{row['stage']}-m{update}"
    if dry_run:
        folder = state_dir / "dry-run"
    else:
        _validate_repo(repo, BRANCH)
        _sync_remote(repo, BRANCH)
        folder = repo / STAGE_DIR
    folder.mkdir(parents=True, exist_ok=True)
    doc = folder / f"{stem}.md"
    charts = _stage_charts(state_dir, row, folder, stem) if update in STAGE_END else []
    body = markdown(row, stage_doc=stage_doc, video=video,
                    charts=[path.name for path in charts])
    if doc.exists() and doc.read_text(encoding="utf-8-sig") != body:
        raise ValueError("existing report differs from pinned inputs")
    doc.write_text(body, encoding="utf-8")
    data = folder / f"{stem}.json"
    # TensorBoard file SHA changes while training. Store only curves up to this checkpoint.
    compact = dict(row)
    compact["training"] = {key: value for key, value in row["training"].items()
                           if key != "curves"}
    _write_json(data, compact)
    if dry_run:
        return {"state": "dry_run", "doc": str(doc), "data": str(data),
                "checkpoint_sha256": row["checkpoint_sha256"]}
    paths = [path.relative_to(repo).as_posix() for path in (doc, data, *charts)]
    if any(not path.startswith(STAGE_DIR.as_posix() + "/") for path in paths):
        raise ValueError("report path escaped approved directory")
    _run(repo, "add", "--", *paths)
    staged = _run(repo, "diff", "--cached", "--name-only").splitlines()
    if any(name not in paths for name in staged):
        raise ValueError("unowned path staged")
    if staged:
        _run(repo, "commit", "-m", f"EX-40 m{update} checkpoint progress (#555)")
    commit = _run(repo, "rev-parse", "HEAD")
    if _run(repo, "status", "--porcelain"):
        raise ValueError("publication worktree dirty")
    link = f"{GITHUB}/{commit}/{STAGE_DIR.as_posix()}/{doc.name}"
    push_error = None
    try:
        _run(repo, "push", "origin", f"HEAD:{BRANCH}")
        remote = _run(repo, "ls-remote", "origin", f"refs/heads/{BRANCH}").split()
        if not remote or remote[0] != commit:
            raise RuntimeError("remote readback mismatch")
    except RuntimeError as exc:
        push_error = str(exc)
    message = state_dir / f"m{update}.telegram.txt"
    message.parent.mkdir(parents=True, exist_ok=True)
    message.write_text(_telegram(row, link, doc, push_error, stage_doc, video), encoding="utf-8")
    # A crash during the sender call is ambiguous. Persist that state before
    # making the external call so restart cannot duplicate a delivered alert.
    pending = {"state": "delivery_pending", "checkpoint_sha256": row["checkpoint_sha256"],
               "update": update, "doc": str(doc), "commit": commit,
               "link": None if push_error else link, "push_error": push_error,
               "telegram_sha256": sha256(message)}
    _write_json(receipt, pending)
    accepted = bool(sender(telegram_sender, message)) if sender else _send(message, telegram_sender)
    result = {"state": "push_failed" if push_error else "sent" if accepted else "delivery_uncertain",
              "checkpoint_sha256": row["checkpoint_sha256"], "update": update,
              "doc": str(doc), "commit": commit, "link": None if push_error else link,
              "push_error": push_error, "telegram_accepted": accepted}
    _write_json(receipt, result)
    return result


def run_once(ledger: Path, repo: Path, state_dir: Path, telegram_sender: Path,
             final: int, *, dry_run: bool = False, sender=None,
             video_receipts: Path | None = None) -> list[dict]:
    rows = ledger_rows(ledger)
    results, previous = [], None
    for entry in rows:
        row = None
        try:
            cached = state_dir / f"m{entry['checkpoint_iteration']}.row.json"
            if cached.exists():
                old = _read_json(cached)
                if old["checkpoint_sha256"] != entry["checkpoint_sha256"]:
                    raise ValueError("cached row checkpoint differs from ledger")
                receipt = state_dir / f"m{entry['checkpoint_iteration']}.report.json"
                if receipt.exists() and _read_json(receipt).get("state") in (
                        "sent", "delivery_uncertain", "delivery_pending"):
                    previous = old
                    results.append(_read_json(receipt))
                    continue
            score = pinned_score(entry)
            row = build_row(entry, score, previous, final)
            if cached.exists() and _read_json(cached) != row:
                raise ValueError("current inputs differ from pinned report snapshot")
            if not cached.exists():
                _write_json(cached, row)
            # The scorer publishes full stage reports independently. Link only a
            # receipt bound to this checkpoint; never describe a missing CMP as done.
            stage_doc = None
            video = None
            if row["update"] in STAGE_END:
                receipt = ledger.parent / "stage_reports" / f"stage_{row['stage']}_m{row['update']}.publish.json"
                if receipt.exists():
                    stage_state = _read_json(receipt)
                    if (stage_state.get("checkpoint_sha256") == row["checkpoint_sha256"]
                            and stage_state.get("state") == "sent"):
                        stage_doc = stage_state.get("link")
                request_path = _cmp_request(state_dir, row, rows)
                request = _read_json(request_path)
                video = _video_receipt(video_receipts, row, request)
                if not dry_run and (not stage_doc or not video):
                    results.append({"state": "pending_stage_full_report",
                                    "update": row["update"], "stage_report_ready": bool(stage_doc),
                                    "cmp_ready": bool(video), "cmp_request": str(request_path)})
                    previous = row
                    continue
            results.append(publish(row, repo, state_dir, telegram_sender, sender=sender,
                                   dry_run=dry_run, stage_doc=stage_doc, video=video))
            previous = row
        except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
            failure = {"state": "HOLD", "update": entry["checkpoint_iteration"],
                       "checkpoint_sha256": entry["checkpoint_sha256"],
                       "error": f"{type(exc).__name__}: {exc}"}
            _write_json(state_dir / f"m{entry['checkpoint_iteration']}.error.json", failure)
            results.append(failure)
            if row is not None:
                previous = row
    return results


@contextmanager
def _single_writer(path: Path):
    import msvcrt

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError("checkpoint reporter already running") from exc
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--publish-worktree", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--telegram-sender", type=Path, required=True)
    parser.add_argument("--final-update", type=int, default=8000)
    parser.add_argument("--video-receipts", type=Path)
    parser.add_argument("--poll-s", type=float, default=30)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    with _single_writer(args.state_dir / "reporter.lock"):
        while True:
            try:
                rows = run_once(args.ledger, args.publish_worktree, args.state_dir,
                                args.telegram_sender, args.final_update, dry_run=args.dry_run,
                                video_receipts=args.video_receipts)
                status = {"state": "HOLD" if any(row["state"] == "HOLD" for row in rows) else "ok",
                          "rows": len(rows), "last": rows[-1] if rows else None,
                          "holds": [row for row in rows if row["state"] == "HOLD"]}
            except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
                status = {"state": "HOLD", "error": f"{type(exc).__name__}: {exc}"}
                _write_json(args.state_dir / "reporter_status.json", status)
                print(json.dumps(status, ensure_ascii=False), flush=True)
                if args.once:
                    return 1
                time.sleep(args.poll_s)
                continue
            _write_json(args.state_dir / "reporter_status.json", status)
            print(json.dumps(status, ensure_ascii=False), flush=True)
            if args.once:
                return 1 if status["state"] == "HOLD" else 0
            time.sleep(args.poll_s)


if __name__ == "__main__":
    raise SystemExit(main())
