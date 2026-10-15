"""Read one stage-0 run folder (attended or unattended) and classify it the way ASTRA 17y/17z want the
report split: START_FAILURE / PARTIAL / FULL_ROWS_HOLD, with the fields that must not be confused:
normal completed steps vs raw rows vs an emergency row, the raw device-UUID evidence, conversion
records, the supervisor receipt and the family-empty evidence. Read-only. It never says PASS.

  python -B s2_summarize_run_a4.py <run_dir>          (prints JSON, then a plain Korean block)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def tail_lines(path, n=25):
    try:
        data = Path(path).read_bytes()[-20000:].decode("utf-8", errors="replace")
    except OSError:
        return []
    return data.splitlines()[-n:]


def summarize(run: Path) -> dict:
    out, usd, ctl, logs, watch = run / "out", run / "usd", run / "ctl", run / "logs", run / "watch"
    rows = sorted((out / "raw_rows").glob("row_*.npz")) if (out / "raw_rows").is_dir() else []
    launch, progress = read_json(out / "launch.json"), read_json(out / "progress.json")
    failure, completion = read_json(out / "failure.json"), read_json(out / "completion.json")
    stage_fail, cleanup = read_json(out / "stage_failure.json"), read_json(out / "cleanup.json")
    device, cfg = read_json(out / "device_binding.json"), read_json(out / "final_cfg.json")
    meta, check = read_json(out / "meta.json"), read_json(out / "check.json")
    receipts = sorted(ctl.glob("claims/*/stage0.receipt.json")) if ctl.is_dir() else []
    receipt = read_json(receipts[0]) if receipts else None
    attempt_start = read_json(next(iter(sorted(ctl.glob("claims/*/attempt_start.json"))), run / "none"))
    status = read_json(ctl / "status.json")
    isolate, assigned = read_json(usd / "isolate_state.json"), usd / "assigned.jsonl"
    n_rows = len(rows)
    last_valid = (progress or {}).get("last_valid_step", -1)
    if n_rows == 0:
        kind = "START_FAILURE"
    elif completion is not None and n_rows >= 256:
        kind = "FULL_ROWS_HOLD"
    else:
        kind = "PARTIAL"
    started = (launch or {}).get("started_epoch")
    ended = (completion or failure or {}).get("ended_epoch")
    first_error = None
    if failure:
        first_error = failure.get("error")
    elif stage_fail:
        first_error = "%s at step %s: %s" % (stage_fail.get("stage"), stage_fail.get("step"), stage_fail.get("error"))
    elif device and device.get("hold"):
        first_error = "device binding: %s" % device["hold"]
    summary = {
        "classification": kind,
        "label": "attended or unattended single information collection, HOLD_INFORMATION_ONLY, optimizer 0, no follow-up training",
        "run_dir": str(run),
        "normal_completed_steps": last_valid + 1 if isinstance(last_valid, int) else None,
        "raw_rows": n_rows,
        "emergency_row": (stage_fail or {}).get("emergency_raw"),
        "stage_failure": stage_fail,
        "first_error": first_error,
        "traceback_tail": (failure or {}).get("traceback", "").splitlines()[-12:] if failure else [],
        "cleanup": cleanup or (failure or completion or {}).get("cleanup"),
        "device_binding": device,
        "child_started_epoch": started,
        "child_ended_epoch": ended,
        "child_seconds": (ended - started) if started and ended else None,
        "mesh_probe_present": (out / "mesh_probe.json").is_file(),
        "final_cfg_present": cfg is not None,
        "asset_path_in_cfg": (cfg or {}).get("asset_path"),
        "checker_verdict": check,
        "meta_flags": {k: (meta or {}).get(k) for k in ("terrain_assignment_verified", "mesh_collision_verified",
                                                        "fixed_pose_verified", "control_steps")},
        "usd_isolate_state": isolate,
        "usd_assigned_lines": (sum(1 for _ in assigned.open(encoding="utf-8")) if assigned.is_file() else None),
        "supervisor_receipt": None if receipt is None else {
            "verdict": receipt.get("verdict"), "exit_code": (receipt.get("record") or {}).get("exit_code"),
            "family_active_count": (receipt.get("record") or {}).get("family_active_count"),
            "control_steps_reported_by_supervisor": (receipt.get("record") or {}).get("control_steps")},
        "supervisor_final_status": status,
        "attempt_start_argv_head": (attempt_start or {}).get("argv", [])[:4],
        "gate_result": read_json(watch / "gate_result.json"),
        "kill_receipt": read_json(watch / "kill_receipt.json"),
        "launch_record": read_json(watch / "launch_record.json"),
        "child_log_tail": tail_lines(logs / "child.log"),
        "note": "control_steps in the supervisor receipt counts raw rows (partial_rows), not completed control steps",
    }
    return summary


def korean_block(s: dict) -> str:
    kinds = {"START_FAILURE": "시작 실패 (수집 0 행)", "PARTIAL": "부분 수집", "FULL_ROWS_HOLD": "256 행 수집 후 검증 보류"}
    lines = ["결과: %s" % kinds[s["classification"]],
             "정상 완료 걸음 %s · 보존된 원시 행 %s · 비상 저장 행 %s" % (s["normal_completed_steps"], s["raw_rows"], s["emergency_row"]),
             "첫 오류: %s" % (s["first_error"] or "기록 없음"),
             "자식 실행 시간(초): %s" % (None if s["child_seconds"] is None else round(s["child_seconds"], 1)),
             "장치 UUID 원 값 기록: %s" % (None if not s["device_binding"] else
                                      (s["device_binding"].get("evidence") or s["device_binding"].get("hold"))),
             "변환 기록: isolate_state=%s · assigned 줄=%s" % (s["usd_isolate_state"], s["usd_assigned_lines"]),
             "감독기 영수증: %s" % (s["supervisor_receipt"],),
             "정리: %s" % (s["cleanup"],),
             "문구: 참석 단회 정보 수집, HOLD_INFORMATION_ONLY, optimizer 0, 후속 학습 없음. 256 행이나 종료 코드만으로 S2 통과 또는 0 단계 PASS 라고 쓰지 않는다."]
    return "\n".join(lines)


def main():
    run = Path(sys.argv[1])
    s = summarize(run)
    print(json.dumps(s, indent=2, ensure_ascii=False, default=str))
    print("\n----\n" + korean_block(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
