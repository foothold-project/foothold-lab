"""CPU-only launch plan for the proposed EX-40 continuous curriculum.

The lead may use the emitted argv with run_ex40.sh after a Kit smoke review.
This module never starts Isaac or a training child.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from foothold_s2.curriculum.continuous import Plan
from foothold_s2.prestart_check import inspect_args


ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "foothold_s2/curriculum/ex40.yaml"
BASELINE = Path("C:/mai/wt/foothold-lab/impl-sb/logs/rsl_rl/foothold_s2_sb/"
                "2026-10-26_01-17-47_sb-main/params")
from foothold_s2.basic_gait_kit import KIT_CACHE_ARG


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_args(*, arm: str, device: str, end_by: str, log_root: Path,
               score_dir: Path, smoke: bool,
               table: Path = TABLE) -> list[str]:
    if arm not in ("A", "B") or device not in ("cuda:0", "cuda:1"):
        raise ValueError("W55 explicit arm and cuda:0|cuda:1 required")
    if not all(p.is_absolute() for p in (log_root, score_dir, table)):
        raise ValueError("W55 launch paths must be absolute")
    plan = Plan(table, arm=arm, smoke_boundaries=(3, 6, 9, 12) if smoke else None)
    if (sha256(BASELINE / "env.yaml") != plan.baseline_env_yaml_sha256 or
            sha256(BASELINE / "agent.yaml") != plan.baseline_agent_yaml_sha256):
        raise ValueError("D68 S-B10 saved configuration SHA mismatch")
    args = ["--headless", "--device", device, "--num_envs", "3072", "--seed", "42",
            "--run_name", f"EX-40-{arm}-{'kit-smoke' if smoke else 'main'}",
            "--end-by", end_by, "--max-wall-s", "345600" if not smoke else "21600",
            "--max_iterations", "15" if smoke else "6001",
            "--command_mode", "basic_gait", "--basic-new-share", "0.30",
            "--basic-log-root", str(log_root), "--basic-stage", "smoke" if smoke else "main",
            "--clock_scatter", "off", "--p_map_off", "0.1",
            "--curriculum", str(table), "--curriculum-arm", arm,
            "--curriculum-score-dir", str(score_dir)]
    if smoke:
        args.append("--curriculum-kit-smoke")
    args.append(KIT_CACHE_ARG)
    return args


def receipt(args: list[str], *, table: Path = TABLE) -> dict:
    parsed = inspect_args(args)
    plan = Plan(table, arm=args[args.index("--curriculum-arm") + 1],
                smoke_boundaries=(3, 6, 9, 12) if "--curriculum-kit-smoke" in args else None)
    if "--resume_from" in args:
        raise ValueError("D68 EX-40 scratch launch forbids a parent checkpoint")
    return {"format": "foothold-ex40-launch/1", "state": "CPU_PREPARED_NOT_LAUNCHED",
            "arm": plan.arm, "curriculum": str(plan.path), "curriculum_sha256": plan.sha256,
            "effective_schedule_sha256": plan.effective_sha256,
            "start": "scratch", "parent": None,
            "baseline_env_yaml_sha256": plan.baseline_env_yaml_sha256,
            "baseline_agent_yaml_sha256": plan.baseline_agent_yaml_sha256,
            "stand_reward": {"four_foot_contact": plan.stages[0].rewards["four_foot_contact_at_stop"],
                             "gap": plan.stand_cfg["gap_weight"], "load": plan.stand_cfg["load_weight"]},
            "parser": parsed, "argv": args,
            "stage_boundaries": {s.id: s.fixed_update for s in plan.stages},
            "kit_verified": False, "training_started": False}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--arm", choices=("A", "B"), required=True)
    p.add_argument("--device", choices=("cuda:0", "cuda:1"), required=True)
    p.add_argument("--end-by", required=True)
    p.add_argument("--log-root", type=Path, required=True)
    p.add_argument("--score-dir", type=Path, required=True)
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--table", type=Path, default=TABLE)
    p.add_argument("--print-args", action="store_true")
    a = p.parse_args(argv)
    args = build_args(arm=a.arm, device=a.device, end_by=a.end_by,
                      log_root=a.log_root, score_dir=a.score_dir, smoke=a.smoke,
                      table=a.table)
    print("\n".join(args) if a.print_args else json.dumps(receipt(args, table=a.table),
                                                    ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
