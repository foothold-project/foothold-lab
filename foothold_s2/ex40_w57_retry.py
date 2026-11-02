"""Retry only a failed W57 phase in a fresh evaluation bundle and separate ledger.

This never edits the original evaluation, score ledger, or watch state. The
operator invokes the Kit child only after reviewing the CPU provenance check.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from foothold_s2.ex40_eval_once import BASH, AXIS, DEFAULT_CONFIG, DEFAULT_TABLE, ROOT
from foothold_s2.ex40_score import config, judge, sha256
from foothold_s2.eval.w57_checkpoint_hash import hash_checkpoint


ATTEMPT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
PHASE_FILES = ("map64/map_modes.json", "stand_eval_gt/stand.json",
               "stand_eval_gt/stand_raw.npz", "stand_probe_prop_only/stand.json",
               "stand_probe_prop_only/stand_raw.npz", "stand_eval_pred/stand.json",
               "stand_eval_pred/stand_raw.npz", "map64_b3/map_modes.json")


def _save(path: Path, row: dict) -> None:
    path.write_text(json.dumps(row, ensure_ascii=False, sort_keys=True,
                               indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _prior(prior_dir: Path, checkpoint: Path, cfg_path: Path,
           table_path: Path) -> tuple[dict, dict[str, str]]:
    receipt_path = prior_dir / "eval_receipt.json"
    prior = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    cfg = config(cfg_path)
    axis_rc = prior.get("steps", {}).get("axis_v2", {}).get("rc")
    if (prior.get("state") != "failed" or type(axis_rc) is not int or axis_rc == 0
            or prior.get("checkpoint_sha256") != sha256(checkpoint)
            or Path(prior.get("checkpoint", "")).resolve() != checkpoint.resolve()
            or prior.get("score_config_sha256") != sha256(cfg_path)
            or prior.get("table_sha256") != sha256(table_path)
            or prior.get("device") != cfg["device"]
            or prior.get("arm") not in ("A", "B")
            or prior.get("stage") not in cfg["stages"]):
        raise ValueError("prior failed evaluation identity differs")
    required = {"map64", "stand_eval_gt", "stand_probe_prop_only", "stand_eval_pred"}
    if (cfg["stages"][prior["stage"]].get("relative_commands")
            or cfg["stages"][prior["stage"]].get("judge_walk_half")):
        required.add("map64_b3")
    if any(prior["steps"].get(name, {}).get("rc") != 0 for name in required):
        raise ValueError("a non-W57 phase failed; W57-only retry is invalid")
    sources = {}
    for name in PHASE_FILES:
        if name.startswith("map64_b3/") and "map64_b3" not in required:
            continue
        path = prior_dir / name
        if not path.is_file():
            raise ValueError(f"prior evidence missing: {name}")
        sources[name] = sha256(path)
    # Preserve the declared per-env reconstruction arrays for retry reports.
    map_path = prior_dir / 'map64/map_modes.json'
    map_row = json.loads(map_path.read_text(encoding='utf-8-sig'))
    for name in map_row.get('env_arrays', {}).values():
        array = (map_path.parent / name).resolve()
        if not array.is_relative_to(map_path.parent.resolve()) or not array.is_file():
            raise ValueError('prior declared map array missing or outside evidence folder')
        sources[array.relative_to(prior_dir.resolve()).as_posix()] = sha256(array)
    return prior, {"eval_receipt.json": sha256(receipt_path), **sources}


def _child(checkpoint: Path, axis_out: Path, device: str, cfg: dict) -> int:
    env = os.environ.copy()
    env.pop("CUDA_VISIBLE_DEVICES", None)
    env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
             | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    command = [str(BASH), str(AXIS), str(checkpoint), str(axis_out),
               device, "64", "2", str(cfg["map_steps"])]
    _save(axis_out.parent / "retry_command.json", {"argv": command, "cwd": str(ROOT),
          "stdin": "DEVNULL", "device": device})
    with (axis_out.parent / "retry_stdout.log").open("wb") as stdout, \
            (axis_out.parent / "retry_stderr.log").open("wb") as stderr:
        return subprocess.run(command, cwd=ROOT, env=env, check=False,
                              stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                              creationflags=flags).returncode


@contextmanager
def _writer_lock(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    lock = root / "w57_retry.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError("retry writer active; separate ledger unchanged") from exc
    try:
        yield
    finally:
        os.close(fd)
        lock.unlink()


def retry(prior_dir: Path, checkpoint: Path, retry_root: Path, attempt_id: str,
          *, cfg_path: Path = DEFAULT_CONFIG, table_path: Path = DEFAULT_TABLE,
          runner=_child) -> dict:
    if not ATTEMPT.fullmatch(attempt_id):
        raise ValueError("retry attempt ID must be a short path-safe identifier")
    prior, source_hashes = _prior(prior_dir, checkpoint, cfg_path, table_path)
    with _writer_lock(retry_root):
        return _retry_locked(prior_dir, checkpoint, retry_root, attempt_id,
                             cfg_path, table_path, runner, prior, source_hashes)


def _retry_locked(prior_dir: Path, checkpoint: Path, retry_root: Path, attempt_id: str,
                  cfg_path: Path, table_path: Path, runner, prior: dict,
                  source_hashes: dict[str, str]) -> dict:
    ledger = retry_root / "w57_retry_ledger.jsonl"
    if ledger.is_file() and any(json.loads(line).get("attempt_id") == attempt_id
                                for line in ledger.read_text(encoding="utf-8-sig").splitlines()
                                if line):
        raise ValueError("retry attempt ID already present in separate ledger")
    out = retry_root / f"w57_retry_{checkpoint.stem}_{attempt_id}"
    if out.exists():
        raise FileExistsError(f"retry attempt already exists: {out}")
    out.mkdir(parents=True)
    for name in source_hashes:
        if name == "eval_receipt.json":
            continue
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(prior_dir / name, target)
        if sha256(target) != source_hashes[name]:
            raise ValueError(f"copied evidence changed: {name}")
    cfg = config(cfg_path)
    error = None
    hash_receipt=out/'checkpoint_sha256.txt'
    preflight_sha=None
    try:
        preflight_sha=hash_checkpoint(checkpoint,hash_receipt)
        if preflight_sha!=prior['checkpoint_sha256']:
            raise ValueError('retry checkpoint preflight differs from original')
        rc = runner(checkpoint, out / "axis_v2", prior["device"], cfg)
    except (OSError, RuntimeError, ValueError) as exc:
        rc, error = -1, f"{type(exc).__name__}: {exc}"
    axis_path = out / "axis_v2/axis_v2.json"
    axis_sha = sha256(axis_path) if rc == 0 and axis_path.is_file() else None
    score, _ = judge(checkpoint, prior["stage"], out, cfg_path,
                     table_path, prior["arm"])
    if sha256(checkpoint) != prior["checkpoint_sha256"]:
        raise ValueError("checkpoint changed during retry; no ledger row written")
    for name, digest in source_hashes.items():
        if sha256(prior_dir / name) != digest:
            raise ValueError(f"prior evidence changed during retry: {name}; no ledger row written")
    if rc != 0 or axis_sha is None:
        score["verdict"] = "HOLD"
        score["problems"].append({"kind": "HOLD", "cell": "W57_retry",
                                  "reason": f"retry child rc={rc} or axis receipt missing"})
    score["retry_attempt_id"] = attempt_id
    score["prior_evaluation_receipt"] = str(prior_dir / "eval_receipt.json")
    # The retry has its own completion receipt. Original failed receipts and
    # primary ledgers remain immutable; success is never inferred from a folder.
    steps = {name: {**step, "reused_from": str(prior_dir)}
             for name, step in prior["steps"].items() if name != "axis_v2"}
    steps["axis_v2"] = {"rc": rc, "source": str(axis_path), "sha256": axis_sha,
                         "error": error}
    receipt = {**prior, "state": "done" if rc == 0 and axis_sha else "failed",
               "steps": steps, "retry_attempt_id": attempt_id,
               "checkpoint_preflight": {"checkpoint_sha256":preflight_sha,
                   "path":str(hash_receipt),"sha256":sha256(hash_receipt) if hash_receipt.is_file() else None},
               "prior_evaluation_receipt": str(prior_dir / "eval_receipt.json"),
               "prior_source_sha256": source_hashes}
    _save(out / "eval_receipt.json", receipt)
    score["evaluation_receipt"] = str(out / "eval_receipt.json")
    _save(out / "score.json", score)
    row = {"format": "foothold-ex40-w57-retry-ledger/1", "attempt_id": attempt_id,
           "checkpoint_iteration": int(checkpoint.stem.split("_")[-1]),
           "checkpoint_sha256": sha256(checkpoint), "stage": prior["stage"],
           "prior_evaluation": str(prior_dir), "prior_source_git_head": prior.get("source_git_head"),
           "prior_source_sha256": source_hashes,
           "retry_evaluation": str(out), "retry_axis_sha256": axis_sha,
           "retry_source_git_head": ((out / "axis_v2/git_head.txt").read_text(encoding="utf-8").strip()
                                     if (out / "axis_v2/git_head.txt").is_file() else None),
           "child_rc": rc, "score_path": str(out / "score.json"),
           "evaluation_receipt": str(out / "eval_receipt.json"),
           "evaluation_receipt_sha256": sha256(out / "eval_receipt.json"),
           "score_sha256": sha256(out / "score.json"), "verdict": score["verdict"],
           "recorded_at": datetime.now(timezone.utc).isoformat(),
           "canonical_watch_state_changed": False}
    _save(out / "retry_receipt.json", row)
    with ledger.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior-eval", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--retry-root", type=Path, required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--check-only", action="store_true", help="CPU validation, no Kit or output")
    args = parser.parse_args()
    if args.check_only:
        prior, sources = _prior(args.prior_eval.resolve(), args.checkpoint.resolve(),
                                args.config.resolve(), args.table.resolve())
        print(json.dumps({"state": "preflight_pass", "attempt_id": args.attempt_id,
                          "prior_source_git_head": prior.get("source_git_head"),
                          "checkpoint_sha256": prior["checkpoint_sha256"],
                          "prior_source_sha256": sources}, sort_keys=True))
        return 0
    row = retry(args.prior_eval.resolve(), args.checkpoint.resolve(),
                args.retry_root.resolve(), args.attempt_id,
                cfg_path=args.config.resolve(), table_path=args.table.resolve())
    print(json.dumps(row, ensure_ascii=False, sort_keys=True))
    return 0 if row["child_rc"] == 0 else 5


if __name__ == "__main__":
    raise SystemExit(main())
