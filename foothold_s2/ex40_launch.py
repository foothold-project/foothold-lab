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
from foothold_s2.curriculum.continuous import KIT_SMOKE_BOUNDARIES
from foothold_s2.curriculum.ex40_dr import require_launchable
from foothold_s2.prestart_check import inspect_args


ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "foothold_s2/curriculum/ex40.yaml"
INTENTIONAL_CURRICULUM_DIFFERENCE = "S-B10 대비 의도된 차이 1: 지형 승급 판정 세계 좌표(결정 8)"
INTENTIONAL_TERRAIN_DIFFERENCE = "S-B10 대비 의도된 차이 2: 지형 자동 승급 끔(L0~2 고정, 팀장 결정 대기)"
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
    plan = Plan(table, arm=arm, smoke_boundaries=KIT_SMOKE_BOUNDARIES if smoke else None)
    if (sha256(BASELINE / "env.yaml") != plan.baseline_env_yaml_sha256 or
            sha256(BASELINE / "agent.yaml") != plan.baseline_agent_yaml_sha256):
        raise ValueError("D68 S-B10 saved configuration SHA mismatch")
    args = ["--headless", "--device", device, "--num_envs", "3072", "--seed", "42",
            "--run_name", f"EX-40-{arm}-{'kit-smoke' if smoke else 'main'}",
            "--end-by", end_by, "--max-wall-s", "345600" if not smoke else "21600",
            "--max_iterations", "18" if smoke else "6501",
            "--command_mode", "basic_gait", "--basic-new-share", "0.30",
            "--basic-log-root", str(log_root), "--basic-stage", "smoke" if smoke else "main",
            "--clock_scatter", "off", "--p_map_off", "0.1",
            "--curriculum", str(table), "--curriculum-arm", arm,
            "--curriculum-score-dir", str(score_dir)]
    if smoke:
        args.append("--curriculum-kit-smoke")
    args.append(KIT_CACHE_ARG)
    return args


def receipt(args: list[str], *, table: Path = TABLE, resume_source: str | None = None,
            expected_finish: str | None = None) -> dict:
    parsed = inspect_args(args)
    plan = Plan(table, arm=args[args.index("--curriculum-arm") + 1],
                smoke_boundaries=KIT_SMOKE_BOUNDARIES if "--curriculum-kit-smoke" in args else None)
    parent = None
    segment_index = 0
    if "--resume_from" in args:
        from foothold_s2.ex40_continue import check_parent

        path = args[args.index("--resume_from") + 1]
        parent = check_parent(path, args[args.index("--basic-ex40-parent-sha") + 1],
                              curriculum_path=table, arm=plan.arm)
        segment_index = int(args[args.index("--basic-ex40-segment-index") + 1])
        if segment_index != parent["segment_index"] + 1:
            raise ValueError("EX-40 launch receipt segment does not follow its verified parent")
    start = "resume" if parent else "scratch"
    return {"format": "foothold-ex40-launch/1", "state": "CPU_PREPARED_NOT_LAUNCHED",
            "arm": plan.arm, "curriculum": str(plan.path), "curriculum_sha256": plan.sha256,
            "effective_schedule_sha256": plan.effective_sha256,
            "start": start, "origin_start": "scratch",
            "parent": parent, "segment_index": segment_index,
            "resume_source_receipt": resume_source,
            "expected_finish": expected_finish,
            "resume_preserves": (["stage", "optimizer", "learning_rate", "B1_origin",
                                  "map_switch", "collection_update", "environment_state", "RNG"]
                                 if parent else []),
            "baseline_env_yaml_sha256": plan.baseline_env_yaml_sha256,
            "baseline_agent_yaml_sha256": plan.baseline_agent_yaml_sha256,
            "intentional_baseline_differences": [INTENTIONAL_CURRICULUM_DIFFERENCE,
                                                 INTENTIONAL_TERRAIN_DIFFERENCE],
            "stand_sensor_evidence": "ex40-v5",
            "stand_reward": {"four_foot_contact": plan.stages[0].rewards["four_foot_contact_at_stop"],
                             "gap": plan.stand_cfg["gap_weight"], "load": plan.stand_cfg["load_weight"]},
            "parser": parsed, "argv": args,
            "terrain_curriculum": plan.terrain_curriculum,
            "stage_boundaries": {s.id: s.fixed_update for s in plan.stages},
            "kit_verified": False, "training_started": False}


def prepare_resume(spec_path: Path, *, arm: str, device: str, end_by: str,
                   log_root: Path, score_dir: Path) -> tuple[list[str], dict]:
    from foothold_s2.ex40_continue import build_resume_args, check_parent

    spec_path = spec_path.resolve(strict=True)
    spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
    source_path = Path(spec["source_receipt"]).resolve(strict=True)
    source = json.loads(source_path.read_text(encoding="utf-8-sig"))
    parent = {"checkpoint": str(Path(spec["checkpoint"]).resolve(strict=True)),
              "checkpoint_sha256": str(spec["checkpoint_sha256"])}
    verified = check_parent(parent["checkpoint"], parent["checkpoint_sha256"], arm=arm)
    source_args = source.get("argv") or []
    expected_source = {
        "--curriculum-arm": arm, "--device": device,
        "--basic-log-root": str(log_root.resolve()),
        "--curriculum-score-dir": str(score_dir.resolve()),
    }
    for flag, value in expected_source.items():
        if source_args.count(flag) != 1 or source_args[source_args.index(flag) + 1] != value:
            raise ValueError(f"EX-40 resume source differs at {flag}")
    args = build_resume_args(source, verified, end_by=end_by,
                             expected_finish=spec["expected_finish"], arm=arm)
    row = receipt(args, table=Path(source["curriculum"]),
                  resume_source=str(source_path), expected_finish=spec["expected_finish"])
    row["resume_spec"] = str(spec_path)
    row["resume_source_manifest"] = str(Path(parent["checkpoint"]).parent / "manifest.json")
    row["parent_segment_index"] = verified["segment_index"]
    return args, row


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--arm", choices=("A", "B"))
    p.add_argument("--device", choices=("cuda:0", "cuda:1"))
    p.add_argument("--end-by")
    p.add_argument("--log-root", type=Path)
    p.add_argument("--score-dir", type=Path)
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--table", type=Path, default=TABLE)
    p.add_argument("--resume-spec", type=Path)
    p.add_argument("--print-args", action="store_true")
    a = p.parse_args(argv)
    if a.resume_spec:
        if a.smoke or None in (a.arm, a.device, a.end_by, a.log_root, a.score_dir):
            p.error("--resume-spec requires arm, device, end-by, log-root and score-dir, and cannot be smoke")
        try:
            require_launchable(a.table)
        except ValueError as exc:
            p.error(str(exc))
        args, row = prepare_resume(a.resume_spec, arm=a.arm, device=a.device,
                                   end_by=a.end_by, log_root=a.log_root, score_dir=a.score_dir)
        print("\n".join(args) if a.print_args else json.dumps(row, ensure_ascii=False,
                                                            sort_keys=True, indent=2))
        return 0
    if None in (a.arm, a.device, a.end_by, a.log_root, a.score_dir):
        p.error("scratch launch requires arm, device, end-by, log-root and score-dir")
    try:
        require_launchable(a.table)
    except ValueError as exc:
        p.error(str(exc))
    args = build_args(arm=a.arm, device=a.device, end_by=a.end_by,
                      log_root=a.log_root, score_dir=a.score_dir, smoke=a.smoke,
                      table=a.table)
    print("\n".join(args) if a.print_args else json.dumps(receipt(args, table=a.table),
                                                    ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
