"""CPU-only D55 launch contract for the EX-39 heading pair."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from foothold_s2.basic_gait_ex38_continue import check_parent
from foothold_s2.basic_gait_launch import build_args
from foothold_s2.commands.mixed_core import ex39_shares
from foothold_s2.sol23f_contract import EX39_PARENT_SHA256


def prepare(arm: str, device: str, parent: str, parent_sha256: str, end_by: str,
            log_root: str, updates: int = 1500, levels: int = 3) -> tuple[list[str], dict]:
    if arm not in ("A", "B") or (updates, levels) not in ((1500, 3), (3000, 4)):
        raise ValueError("EX-39 accepts A/B and (1500,L0..2) or (3000,L0..3)")
    if parent_sha256 != EX39_PARENT_SHA256:
        raise ValueError("EX-39 parent SHA256 is not pinned model_3001.pt")
    parent_row = check_parent(parent, parent_sha256)
    if parent_row["completed_update"] != 3001:
        raise ValueError("EX-39 parent must finish update 3001")
    args = build_args("parent", device, end_by, 0.30, parent,
                      log_root=log_root, stage="main", ex38=True)
    def replace(flag: str, value: str) -> None:
        args[args.index(flag) + 1] = value
    replace("--run_name", f"EX-39{arm}-basic-heading")
    replace("--basic-new-share", "0.4")
    replace("--max_iterations", str(3002 + updates))
    args.remove("--basic-ex38")
    args.extend(["--basic-ex39-arm", arm, "--basic-ex39-parent-sha", parent_sha256,
                 "--basic-ex39-updates", str(updates), "--basic-ex39-level-count", str(levels)])
    # The real train parser and parent/limit validation run again in prestart_check.
    return args, {"arm": arm, "run_name": f"EX-39{arm}-basic-heading", "parent": parent_row,
                  "parent_sha256": parent_sha256, "first_update": 3002,
                  "last_update": 3001 + updates, "max_iterations": 3002 + updates,
                  "additional_updates": updates, "terrain_levels": list(range(levels)),
                  "command_shares": ex39_shares(), "heading": "off" if arm == "A" else
                  "forward 15 percentage points; spin 3+3 percentage points",
                  "reward_change_common": {"thigh_calf_pos_l1": -0.01,
                                           "stand_four_foot_contact_proposed": 0.1},
                  "unchanged": "EX-38 PPO, perception, existing reward weights and lin_vel_z=0",
                  "judge_exclusion": {"post_treatment_updates": [3002, 3301],
                                      "subsequent_resume_first_updates": 30},
                  "deadline_role": "upper_bound_only", "physical_resume_identical": False,
                  "feet_regulation": "candidate_only", "training_started": False,
                  "argv": args}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=("A", "B"), required=True)
    parser.add_argument("--device", choices=("cuda:0", "cuda:1"), required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--parent-sha256", required=True)
    parser.add_argument("--end-by", required=True)
    parser.add_argument("--log-root", type=Path, required=True)
    parser.add_argument("--updates", type=int, choices=(1500, 3000), default=1500)
    parser.add_argument("--levels", type=int, choices=(3, 4), default=3)
    parser.add_argument("--print-args", action="store_true")
    a = parser.parse_args(argv)
    args, row = prepare(a.arm, a.device, str(a.parent), a.parent_sha256, a.end_by,
                        str(a.log_root), a.updates, a.levels)
    if a.print_args:
        print("\n".join(args))
    else:
        print(json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
