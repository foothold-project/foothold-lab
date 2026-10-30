"""Sequential EX-40 checkpoint evaluator and score/2 writer, CPU coordinator.

Run this in a hidden operator-owned window after the frozen training launch.
Each checkpoint gets one immutable evaluation directory and one score receipt.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from foothold_s2.curriculum.continuous import Plan
from foothold_s2.ex40_eval_once import DEFAULT_CONFIG, DEFAULT_TABLE, ROOT
from foothold_s2.ex40_score import config, judge, require_shadow_plan, sha256, stage_end_updates
from foothold_s2.ex40_stage_report import build as build_stage_report, markdown as stage_markdown


MODEL = re.compile(r"model_(\d+)\.pt\Z")


def _atomic(path: Path, row: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(row, ensure_ascii=False, indent=2,
                                    allow_nan=False) + "\n", encoding="utf-8")
    for attempt in range(200):
        try:
            os.replace(temporary, path)
            break
        except PermissionError:
            if attempt == 199:
                raise
            time.sleep(.01)


def _atomic_text(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    for attempt in range(200):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 199:
                raise
            time.sleep(.01)


def _stage(run: Path, iteration: int, plan: Plan) -> str:
    events = (run / "stage_log.jsonl").read_text(encoding="utf-8-sig").splitlines()
    entered = [json.loads(line) for line in events if '"stage_enter"' in line]
    matching = [row for row in entered if row.get("event") == "stage_enter"
                and type(row.get("iteration")) is int and row["iteration"] <= iteration]
    if not matching:
        raise ValueError("actual stage_enter evidence absent for checkpoint")
    latest = max(matching, key=lambda row: row["iteration"])
    if latest.get("effective_schedule_sha256") != plan.effective_sha256:
        raise ValueError("actual stage schedule hash differs")
    stage = latest.get("to")
    if stage not in [item.id for item in plan.stages]:
        raise ValueError("actual stage name differs from plan")
    return stage


def _models(run: Path, cfg: dict) -> list[tuple[int, Path]]:
    found = []
    for path in run.glob("model_*.pt"):
        match = MODEL.fullmatch(path.name)
        if match:
            update = int(match.group(1))
            if update >= cfg["checkpoint_first"] and update % cfg["checkpoint_stride"] == 0:
                found.append((update, path))
    return sorted(found)


def _stable(path: Path, seconds: float, sleep=time.sleep) -> str | None:
    try:
        before = (path.stat().st_size, sha256(path))
        sleep(seconds)
        after = (path.stat().st_size, sha256(path))
    except OSError:
        return None
    return after[1] if before == after and after[0] > 0 else None


def _manifest_digest(run: Path, update: int) -> str | None:
    """The trainer has completed this numbered save only after pinning its SHA."""
    try:
        manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8-sig"))
        if manifest.get("schema") != "foothold-manifest/1":
            return None
        if int(manifest["progress"]["completed_updates"]) < update + 1:
            return None
        digest = manifest["checkpoints"].get(f"model_{update}.pt")
        return digest if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _ledger_rows(out_root: Path) -> list[dict]:
    path = out_root / "score_ledger.jsonl"
    if not path.is_file():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line]
    updates = [row.get("checkpoint_iteration") for row in rows]
    if any(type(update) is not int for update in updates) or len(set(updates)) != len(updates):
        raise ValueError("score ledger has a malformed or duplicate checkpoint iteration")
    return rows


def _ledger_append(out_root: Path, row: dict) -> None:
    out_root.mkdir(parents=True, exist_ok=True)
    with (out_root / "score_ledger.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _ledger_result(run: Path, out_root: Path, update: int, digest: str, stage: str,
                   score_path: Path, verdict: str) -> dict:
    row = {"format": "foothold-ex40-score-ledger/1", "checkpoint_iteration": update,
           "checkpoint_sha256": digest, "stage": stage, "verdict": verdict,
           "score_path": str(score_path), "score_sha256": sha256(score_path),
           "stage_log_reference": str(run / "stage_log.jsonl"),
           "recorded_at": datetime.now(timezone.utc).isoformat()}
    _ledger_append(out_root, row)
    return row


def _child(checkpoint: Path, out: Path, stage: str, arm: str,
           cfg_path: Path, table: Path) -> dict:
    flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
             | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    started = time.monotonic()
    argv = [sys.executable, "-m", "foothold_s2.ex40_eval_once",
            "--checkpoint", str(checkpoint), "--out", str(out), "--stage", stage,
            "--arm", arm, "--config", str(cfg_path), "--table", str(table),
            "--device", "cuda:1"]
    rc = subprocess.run(argv, cwd=ROOT, check=False, creationflags=flags).returncode
    receipt = out / "eval_receipt.json"
    row = json.loads(receipt.read_text(encoding="utf-8-sig")) if receipt.is_file() else {}
    return {"rc": rc, "seconds": time.monotonic() - started, "receipt": row}


def process_once(run: Path, out_root: Path, score_dir: Path, cfg_path: Path,
                 table: Path, arm: str, state: dict, *, evaluator=_child,
                 sleep=time.sleep) -> dict:
    cfg, plan = config(cfg_path), Plan(table, arm=arm)
    require_shadow_plan(plan, cfg)
    boundaries = stage_end_updates(plan, cfg)
    if (state.get("format") != "foothold-ex40-score-watch/1"
            or state.get("config_sha256") != sha256(cfg_path)
            or state.get("table_sha256") != sha256(table)
            or state.get("arm") != arm):
        raise ValueError("watch state identity changed")
    ledger_by_update = {row["checkpoint_iteration"]: row for row in _ledger_rows(out_root)}
    for name, finished in state["done"].items():
        pinned = _manifest_digest(run, int(name))
        if pinned is not None and pinned != finished.get("checkpoint_sha256"):
            raise ValueError(f"completed checkpoint {name} changed in manifest")
        if (int(name) not in ledger_by_update
                or ledger_by_update[int(name)].get("checkpoint_sha256") != finished.get("checkpoint_sha256")):
            raise ValueError(f"completed checkpoint {name} has no matching score ledger entry")
    candidates = [(n, p) for n, p in _models(run, cfg) if str(n) not in state["done"]]
    if not candidates:
        return {"state": "idle"}
    update, checkpoint = candidates[0]
    pinned = _manifest_digest(run, update)
    if pinned is None:
        return {"state": "pending", "update": update, "reason": "manifest_checkpoint_not_committed"}
    digest = _stable(checkpoint, cfg["checkpoint_stable_seconds"], sleep)
    if digest is None or digest != pinned:
        return {"state": "pending", "update": update, "reason": "checkpoint_size_or_SHA_not_stable_or_manifest_mismatch"}
    for row in _ledger_rows(out_root):
        if row.get("checkpoint_iteration") == update:
            if (row.get("checkpoint_sha256") != digest
                    or not Path(row.get("score_path", "")).is_file()
                    or sha256(Path(row["score_path"])) != row.get("score_sha256")):
                raise ValueError(f"checkpoint {update} ledger conflicts with source or score")
            result = {"state": row["verdict"], "stage": row["stage"],
                      "checkpoint_sha256": digest, "score_path": row["score_path"],
                      "recovered_from_ledger": True}
            state["done"][str(update)] = result
            return result
    try:
        stage = _stage(run, update, plan)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"state": "pending", "update": update,
                "reason": f"actual_stage_receipt_not_ready: {type(exc).__name__}"}
    if update in boundaries and boundaries[update] != stage:
        raise ValueError(f"stage-end checkpoint {update} has wrong stage {stage}")
    out = out_root / f"model_{update}_{digest[:12]}"
    if out.exists():
        score, _ = judge(checkpoint, stage, out, cfg_path, table, arm)
        score["verdict"] = "HOLD"
        score["problems"].append({"kind": "HOLD", "cell": "evaluation",
                                  "reason": "prior_partial_or_duplicate_evaluation"})
        interrupted = out / "score_interrupted.json"
        if not interrupted.exists():
            _atomic(interrupted, score)
        score_dir.mkdir(parents=True, exist_ok=True)
        target = score_dir / f"score_{update}_{digest[:12]}_interrupted.json"
        if not target.exists():
            _atomic(target, score)
        _ledger_result(run, out_root, update, digest, stage, target, "HOLD")
        state["done"][str(update)] = {"state": "HOLD", "stage": stage,
                                      "reason": "prior_partial_or_duplicate_evaluation",
                                      "output_path": str(out), "checkpoint_sha256": digest,
                                      "score_path": str(target)}
        return state["done"][str(update)]
    try:
        evidence = evaluator(checkpoint, out, stage, arm, cfg_path, table)
    except Exception as exc:
        evidence = {"rc": 1, "seconds": 0, "receipt": {"state": "failed",
                                                      "reason": f"{type(exc).__name__}: {exc}"}}
    elapsed = float(evidence.get("seconds", 0))
    state["last_eval_seconds"] = elapsed
    baseline = state["stage_baseline"].get(stage)
    score, basis = judge(checkpoint, stage, out, cfg_path, table, arm, baseline)
    if evidence.get("rc") != 0 or evidence.get("receipt", {}).get("state") != "done":
        score["verdict"] = "HOLD"
        score["problems"].append({"kind": "HOLD", "cell": "evaluation_child",
                                  "reason": "evaluation_failed_or_completion_receipt_missing: " +
                                  str(evidence.get("receipt", {}).get("reason", evidence.get("rc")))})
    if sha256(checkpoint) != digest:
        score["verdict"] = "HOLD"
        score["problems"].append({"kind": "HOLD", "cell": "checkpoint", "reason": "checkpoint_changed_during_evaluation"})
    score["evaluation_seconds"] = elapsed
    score["evaluation_receipt"] = str(out / "eval_receipt.json")
    out.mkdir(parents=True, exist_ok=True)
    _atomic(out / "score.json", score)
    score_dir.mkdir(parents=True, exist_ok=True)
    target = score_dir / f"score_{update}_{digest[:12]}.json"
    if target.exists():
        raise FileExistsError(f"score receipt already exists: {target}")
    _atomic(target, score)
    if (stage not in state["stage_baseline"] and basis
            and evidence.get("rc") == 0 and evidence.get("receipt", {}).get("state") == "done"):
        state["stage_baseline"][stage] = basis
    _ledger_result(run, out_root, update, digest, stage, target, score["verdict"])
    state["done"][str(update)] = {"state": score["verdict"], "stage": stage,
                                  "output_path": str(out), "checkpoint_sha256": digest,
                                  "score_path": str(target),
                                  "seconds": elapsed}
    return state["done"][str(update)]


def completion(run: Path, out_root: Path, cfg_path: Path, table: Path,
               arm: str, state: dict) -> dict:
    """Close only after the final training receipt and every numbered score."""
    cfg, plan = config(cfg_path), Plan(table, arm=arm)
    boundaries = stage_end_updates(plan, cfg)
    try:
        training = json.loads((run / "train_start_status.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {"state": "waiting_for_training_receipt"}
    if training.get("state") in ("stopped_saved", "failed"):
        if any(str(n) not in state["done"] for n, _ in _models(run, cfg)):
            return {"state": "waiting_for_remaining_scores"}
        return {"state": "training_not_complete", "training_state": training["state"]}
    if training.get("state") != "done":
        return {"state": "waiting_for_training"}
    last = cfg["final_checkpoint_update"]
    final_path = run / f"model_{last}.pt"
    final_sha = _manifest_digest(run, last)
    if (training.get("iter") != last or not isinstance(training.get("checkpoint"), str)
            or Path(training["checkpoint"]).resolve() != final_path.resolve()
            or final_sha is None or training.get("sha256") != final_sha
            or not final_path.is_file() or sha256(final_path) != final_sha):
        return {"state": "final_training_receipt_mismatch"}
    rows = {row["checkpoint_iteration"]: row for row in _ledger_rows(out_root)}
    required = range(cfg["checkpoint_first"], last + 1, cfg["checkpoint_stride"])
    first_pending = None
    first_problem = None
    for update in required:
        pinned = _manifest_digest(run, update)
        saved = state["done"].get(str(update))
        ledger = rows.get(update)
        if pinned is None or saved is None or ledger is None:
            first_pending = update if first_pending is None else first_pending
            continue
        score_path = Path(ledger["score_path"])
        if (saved.get("checkpoint_sha256") != pinned
                or ledger.get("checkpoint_sha256") != pinned
                or saved.get("stage") != _stage(run, update, plan)
                or update in boundaries and saved["stage"] != boundaries[update]
                or not score_path.is_file() or sha256(score_path) != ledger.get("score_sha256")):
            first_problem = first_problem or {"state": "score_or_checkpoint_mismatch", "update": update}
            continue
        if saved.get("state") not in ("PASS", "FAIL"):
            first_problem = first_problem or {"state": "score_hold", "update": update}
            continue
        score = json.loads(score_path.read_text(encoding="utf-8-sig"))
        stage_cfg = cfg["stages"][saved["stage"]]
        phases = {"map64", "stand_eval_gt", "stand_probe_prop_only", "stand_eval_pred"}
        if stage_cfg.get("relative_commands") or stage_cfg.get("judge_walk_half"):
            phases.add("map64_b3")
        if stage_cfg["axis_goal"] or update in boundaries:
            phases.add("axis_v2")
        receipt_path = Path(score.get("evaluation_receipt", ""))
        if not receipt_path.is_file():
            first_problem = first_problem or {"state": "evaluation_receipt_missing", "update": update}
            continue
        receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
        if (score.get("verdict") != saved["state"]
                or score.get("checkpoint_sha256") != pinned
                or receipt.get("state") != "done"
                or not phases <= set(receipt.get("steps", {}))
                or any(receipt["steps"][phase].get("rc") != 0 for phase in phases)
                or not phases <= set(score.get("sources", {}))
                or any(not Path(score["sources"][phase]).is_file() for phase in phases)):
            first_problem = first_problem or {"state": "stage_end_evidence_missing" if update in boundaries
                                               else "evaluation_evidence_missing", "update": update}
    if first_pending is not None:
        return {"state": "waiting_for_remaining_scores", "first_missing": first_pending}
    if first_problem is not None:
        return first_problem
    return {"state": "done", "final_checkpoint": str(final_path),
            "final_sha256": final_sha, "evaluated": len(required),
            "stage_end_updates": list(boundaries)}


def stage_reports(run: Path, out_root: Path, cfg_path: Path, table: Path, arm: str,
                  *, telegram_sender: Path | None = None, lab_feed: Path | None = None,
                  sender=None) -> dict:
    """Publish each complete boundary once from the score ledger, never stage_log.

    A sender failure is recorded as uncertain and never retried automatically.
    The operator can inspect the report and delivery row before retrying.
    """
    cfg = config(cfg_path)
    boundaries = stage_end_updates(Plan(table, arm=arm), cfg)
    by_update = {row["checkpoint_iteration"]: row for row in _ledger_rows(out_root)}
    report_root = out_root / "stage_reports"
    report_root.mkdir(parents=True, exist_ok=True)
    published = []
    first_pending = None
    first_hold = None
    previous = None
    for update, stage in boundaries.items():
        ledger = by_update.get(update)
        if ledger is None:
            first_pending = first_pending or update
            break
        score_path = Path(ledger["score_path"])
        if (ledger["stage"] != stage or ledger["verdict"] not in ("PASS", "FAIL")
                or not score_path.is_file() or sha256(score_path) != ledger["score_sha256"]):
            first_pending = first_pending or update
            break
        score = json.loads(score_path.read_text(encoding="utf-8-sig"))
        if score.get("checkpoint_iteration") != update or score.get("from") != stage:
            raise ValueError("stage report score identity mismatch")
        target = report_root / f"stage_{stage}_m{update}"
        report_path = target.with_suffix(".json")
        markdown_path = target.with_suffix(".md")
        try:
            if report_path.exists() or markdown_path.exists():
                if not (report_path.exists() and markdown_path.exists()):
                    raise ValueError("stage report pair incomplete")
                existing = json.loads(report_path.read_text(encoding="utf-8-sig"))
                if (existing.get("checkpoint_sha256") != score["checkpoint_sha256"]
                        or existing.get("previous_checkpoint_iteration") !=
                        (previous["checkpoint_iteration"] if previous else None)):
                    raise ValueError("stage report conflicts with pinned score")
                for name, digest in existing["current"]["source_sha256"].items():
                    if sha256(Path(score["sources"][name])) != digest:
                        raise ValueError(f"stage report source changed: {name}")
            else:
                report = build_stage_report(score, previous, run)
                _atomic(report_path, report)
                markdown_path.write_text(stage_markdown(report), encoding="utf-8")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            first_hold = first_hold or {"update": update, "reason": f"{type(exc).__name__}: {exc}"}
            previous = score
            continue
        published.append({"stage": stage, "update": update, "path": str(markdown_path),
                          "json": str(report_path), "sha256": sha256(report_path)})
        if telegram_sender is not None:
            delivery_path = target.with_suffix(".delivery.json")
            if not delivery_path.exists():
                text_path = target.with_suffix(".telegram.txt")
                report = json.loads(report_path.read_text(encoding="utf-8-sig"))
                summary = (f"EX-40 {stage} m{update} 평가 완료. 얻은 점 {len(report['gains'])}칸, "
                           f"잃은 점 {len(report['losses'])}칸, 차이 없음 {len(report['unchanged'])}칸. "
                           "상황판: https://ai-ws01.tail025053.ts.net/lab/ex40_stage_reports.html "
                           f"상세: {markdown_path}")
                text_path.write_text(summary + "\n", encoding="utf-8")
                if sender is None:
                    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    attempt = subprocess.run([sys.executable, str(telegram_sender), str(text_path)],
                                             capture_output=True, text=True, timeout=90,
                                             creationflags=flags, check=False)
                    accepted = attempt.returncode == 0 and attempt.stdout.split(maxsplit=1)[:1] == ["0"]
                else:
                    accepted = bool(sender(telegram_sender, text_path))
                _atomic(delivery_path, {"state": "sent" if accepted else "uncertain",
                                        "summary_sha256": sha256(text_path),
                                        "sender_path": str(telegram_sender)})
            if json.loads(delivery_path.read_text(encoding="utf-8"))["state"] != "sent":
                first_hold = first_hold or {"update": update, "reason": "telegram_delivery_uncertain"}
        previous = score
    if lab_feed is not None:
        _atomic(lab_feed, {"format": "foothold-ex40-lab-feed/1", "stage_reports": published,
                           "first_pending": first_pending})
        items = []
        for item in published:
            report = json.loads(Path(item["json"]).read_text(encoding="utf-8"))
            items.append("<li><strong>" + html.escape(item["stage"]) + " m" + str(item["update"])
                         + "</strong> · 얻은 점 " + str(len(report["gains"]))
                         + "칸 · 잃은 점 " + str(len(report["losses"]))
                         + "칸 · 상세 문서: <code>" + html.escape(item["path"])
                         + "</code></li>")
        page = ("<!doctype html><html lang='ko'><meta charset='utf-8'>"
                "<title>EX-40 단계 끝 보고</title><main><h1>EX-40 단계 끝 보고</h1>"
                "<p>생존 반복 폭 ±3/64 이내는 차이 없음. 원자료 숫자는 각 문서와 JSON에 있습니다.</p>"
                "<ol>" + "".join(items) + "</ol></main></html>\n")
        _atomic_text(lab_feed.with_suffix(".html"), page)
    return {"state": "hold" if first_hold else "pending" if first_pending is not None else "done",
            "published": len(published), "first_pending": first_pending, "first_hold": first_hold}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--out-root", type=Path, required=True)
    p.add_argument("--score-dir", type=Path, required=True)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    p.add_argument("--arm", choices=("A", "B"), required=True)
    p.add_argument("--once", action="store_true")
    p.add_argument("--telegram-sender", type=Path,
                   default=Path("C:/Users/AI-WS01/s2_lab/tools_lead/tg_send.py"))
    p.add_argument("--no-telegram", action="store_true")
    p.add_argument("--lab-feed", type=Path,
                   default=Path("C:/Users/AI-WS01/s2_lab/lab_status/ex40_stage_reports.json"))
    args = p.parse_args(argv)
    args.run_dir = args.run_dir.resolve()
    args.out_root = args.out_root.resolve()
    args.score_dir = args.score_dir.resolve()
    args.config = args.config.resolve()
    args.table = args.table.resolve()
    if not args.run_dir.is_dir() or args.out_root == args.score_dir:
        p.error("training run must exist and output and score roots must differ")
    cfg = config(args.config)
    require_shadow_plan(Plan(args.table, arm=args.arm), cfg)
    args.out_root.mkdir(parents=True, exist_ok=True)
    lock = args.out_root / "watch.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        p.error("another watch owns this root, or a crash lock needs operator review")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(str(os.getpid()))
        path = args.out_root / "watch_state.json"
        state = (json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else {
            "format": "foothold-ex40-score-watch/1", "config_sha256": sha256(args.config),
            "table_sha256": sha256(args.table), "arm": args.arm,
            "done": {}, "stage_baseline": {}, "last_eval_seconds": 0})
        while True:
            result = process_once(args.run_dir, args.out_root, args.score_dir,
                                  args.config, args.table, args.arm, state)
            reports = stage_reports(args.run_dir, args.out_root, args.config, args.table,
                                    args.arm, telegram_sender=None if args.no_telegram else args.telegram_sender,
                                    lab_feed=args.lab_feed)
            end = completion(args.run_dir, args.out_root, args.config, args.table, args.arm, state)
            if end["state"] == "done" and reports["state"] != "done":
                end = ({"state": "stage_report_hold", "detail": reports["first_hold"]}
                       if reports["state"] == "hold" else
                       {"state": "waiting_for_stage_reports", "first_missing": reports["first_pending"]})
            if end["state"] in ("done", "training_not_complete", "score_hold",
                                "score_or_checkpoint_mismatch", "stage_end_evidence_missing",
                                "evaluation_receipt_missing", "evaluation_evidence_missing",
                                "final_training_receipt_mismatch", "stage_report_hold"):
                state["terminal"] = end
                _atomic(args.out_root / "watch_completion.json", end)
            _atomic(path, state)
            print(json.dumps({"evaluation": result, "reports": reports, "completion": end}, ensure_ascii=False), flush=True)
            if args.once:
                return 0
            if "terminal" in state:
                return 0 if end["state"] == "done" else 5
            time.sleep(cfg["check_interval_seconds"])
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
