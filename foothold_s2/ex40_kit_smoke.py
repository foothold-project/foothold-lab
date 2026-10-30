"""Read-only post-run receipt check for a lead-operated EX-40 Kit smoke."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def check(receipt_path: Path, run_log: Path, rc: int) -> dict:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    if receipt.get("state") != "CPU_PREPARED_NOT_LAUNCHED" or receipt.get("stage_boundaries") != {
            "B1": 1501, "B2": 1503, "B3": 1506, "T0": 1509}:
        raise ValueError("EX-40 smoke launch receipt or stage boundaries differ")
    if rc != 0 or "Traceback" in run_log.read_text(encoding="utf-8", errors="replace"):
        raise ValueError("EX-40 Kit child failed or traceback present")
    root = Path(receipt["argv"][receipt["argv"].index("--basic-log-root") + 1]) / "smoke"
    runs = [p for p in root.glob(f"EX-40-{receipt['arm']}-kit-smoke_*") if p.is_dir()]
    if len(runs) != 1:
        raise ValueError("EX-40 smoke must have exactly one isolated child run")
    run = runs[0]
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8-sig"))
    modes = manifest.get("modes") or {}
    cfg = modes.get("continuous_curriculum") or {}
    if (cfg.get("sha256") != receipt.get("curriculum_sha256")
            or cfg.get("effective_schedule_sha256") != receipt.get("effective_schedule_sha256")
            or cfg.get("arm") != receipt["arm"]
            or modes.get("contract") != "basic_gait_ex40"):
        raise ValueError("EX-40 actual Kit manifest differs from CPU launch contract")
    env_cfg = (run / "params/env.yaml").read_text(encoding="utf-8")
    if any(token not in env_cfg for token in ("curriculum_mode", "ex39_thigh_calf_pos_l1",
                                               "ex39_four_foot_stop", "track_ang_vel", "track_lin_vel")):
        raise ValueError("EX-40 actual Kit environment cfg lacks command or reward terms")
    start = json.loads((run / "basic_start_receipt.json").read_text(encoding="utf-8-sig"))
    if start.get("num_envs") != 3072 or start.get("env_seed") != 42 or start.get("command_seed") != 42:
        raise ValueError("EX-40 actual Kit env/command seed or env count differs")
    rows = [json.loads(line) for line in (run / "stage_log.jsonl").read_text(encoding="utf-8").splitlines()]
    entered = [(row.get("to"), row.get("iteration")) for row in rows if row.get("event") == "stage_enter"]
    if entered != list(receipt["stage_boundaries"].items()):
        raise ValueError("EX-40 Kit did not enter all planned stages at their update boundaries")
    if next(row for row in rows if row.get("event") == "stage_enter" and row.get("to") == "T0").get("force_gt") is not False:
        raise ValueError("EX-40 T0 did not release forced GT map selection")
    if not any(row.get("event") == "env_reset_applied" for row in rows):
        raise ValueError("EX-40 Kit did not observe a per-env reset stage adoption")
    status = json.loads((run / "train_start_status.json").read_text(encoding="utf-8-sig"))
    if status.get("state") != "done" or status.get("iter") != 1510 or not (run / "model_1510.pt").is_file():
        raise ValueError("EX-40 Kit smoke did not complete and save model_1510")
    checkpoint_sha = hashlib.sha256((run / "model_1510.pt").read_bytes()).hexdigest()
    if status.get("sha256") != checkpoint_sha:
        raise ValueError("EX-40 completed checkpoint SHA and status differ")
    return {"state": "PASS", "run_dir": str(run), "stages": entered,
            "reset_adoptions": sum(row.get("event") == "env_reset_applied" for row in rows),
            "checkpoint": str(run / "model_1510.pt"), "checkpoint_sha256": checkpoint_sha}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--receipt", type=Path, required=True)
    p.add_argument("--run-log", type=Path, required=True)
    p.add_argument("--rc", type=int, required=True)
    a = p.parse_args(argv)
    print(json.dumps(check(a.receipt, a.run_log, a.rc), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
